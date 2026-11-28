from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import UserPreferences
from catalogs.specs import suggest_values
from config.keywords import KeywordSearchFilter
from system.messages import web_error_message
from system.web import WebError, fetch_image, http_url, search_images

from .averages import versions_average
from .documents import (
    ALLOWED_EXTENSIONS,
    MAX_DOCUMENTS,
    PHOTO_EXTENSIONS,
    check_document,
    clean_filename,
    content_type_for,
    opens_inline,
    photo_name_from_url,
)
from .models import AveragePrice, PriceDocument, PricePoint
from .serializers import (
    AveragePriceCreateSerializer,
    AveragePriceDetailSerializer,
    AveragePricePreviewSerializer,
    AveragePriceSerializer,
    PriceDocumentSerializer,
    VersionsAverageSerializer,
)

FILTERS = {
    "vertical": "sub_vertical__vertical_id",
    "sub_vertical": "sub_vertical_id",
    "asset_class": "asset_class_id",
    "manufacturer": "manufacturer_id",
}


def _filter_list(queryset, params):
    """Column filters of the grid. Values that cannot be read are ignored."""
    for param, field in FILTERS.items():
        value = params.get(param, "")
        if value.isdigit():
            queryset = queryset.filter(**{field: int(value)})
    text = " ".join(params.get("model", "").split())
    if text:
        queryset = queryset.filter(Q(model__icontains=text) | Q(manufacturer__name__icontains=text))
    for param, lookup in (("original_value_min", "gte"), ("original_value_max", "lte")):
        value = _decimal(params.get(param))
        if value is not None:
            queryset = queryset.filter(**{f"original_value__{lookup}": value})
    for param, lookup in (("created_from", "gte"), ("created_to", "lte")):
        value = parse_date(params.get(param) or "") if params.get(param) else None
        if value is not None:
            queryset = queryset.filter(**{f"created_at__date__{lookup}": value})
    return queryset


def _decimal(value):
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


class AveragePriceViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Average prices. Rows are never edited (no PUT/PATCH): to change one, POST a new row with
    "supersedes": <id>; the old one is kept as a previous version. DELETE /<id>/ erases that
    version (the newest one left becomes current); DELETE /<id>/history/ hides every version
    (the row leaves the list; kept in the database).

    List (current versions, not deleted) supports ?search= (model, description, asset class,
    manufacturer, vertical or sub-vertical), ?vertical=, ?sub_vertical=, ?asset_class=,
    ?manufacturer= (ids), ?model= (model or manufacturer contains), ?original_value_min/max=,
    ?created_from/to= (YYYY-MM-DD, inclusive), ?ordering= (created_at, model, original_value,
    asset_class__name, manufacturer__name), ?page= and ?page_size=. GET /<id>/ includes the
    monthly curve and works for previous versions too; GET /<id>/history/ lists every version
    of the row and their average. POST /preview/ resolves values typed in the form (nothing saved).
    GET /spec-suggestions/?asset_class=&key=&search= offers specification values already used.
    Documents of the row (shared by all its versions): GET/POST /<id>/documents/ (multipart,
    field "file"), DELETE /<id>/documents/<doc>/, GET /<id>/documents/<doc>/download/
    (?inline=1 opens PDFs and images in the browser). Photo of the asset: GET/POST/DELETE
    /<id>/photo/ (POST replaces it); POST /<id>/photo/from-url/ downloads it from the internet;
    GET /<id>/photo-suggestions/ searches images (SearXNG, system settings).
    """

    queryset = AveragePrice.objects.select_related(
        "sub_vertical__vertical", "asset_class", "manufacturer", "created_by"
    ).prefetch_related(
        Prefetch("points", queryset=PricePoint.objects.select_related("average_price"))
    )
    filter_backends = [KeywordSearchFilter, filters.OrderingFilter]
    search_fields = [
        "model",
        "description",
        "asset_class__name",
        "manufacturer__name",
        "sub_vertical__name",
        "sub_vertical__vertical__name",
    ]
    ordering_fields = [
        "created_at",
        "model",
        "original_value",
        "asset_class__name",
        "manufacturer__name",
    ]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        documents = (
            PriceDocument.objects.filter(lineage=OuterRef("lineage"), is_photo=False)
            .values("lineage")
            .annotate(n=Count("id"))
            .values("n")
        )
        photo = PriceDocument.objects.filter(lineage=OuterRef("lineage"), is_photo=True)
        queryset = (
            super()
            .get_queryset()
            .annotate(
                documents_count=Coalesce(Subquery(documents, output_field=IntegerField()), 0),
                photo_id=Subquery(photo.values("id")[:1]),
                photo_source_url=Subquery(photo.values("source_url")[:1]),
            )
        )
        if self.action == "list":
            queryset = _filter_list(queryset.active(), self.request.query_params)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return AveragePriceCreateSerializer
        if self.action == "retrieve":
            return AveragePriceDetailSerializer
        return AveragePriceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        row = self.get_queryset().get(pk=row.pk)
        return Response(AveragePriceDetailSerializer(row).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Erase one version for good. If it was the current one, the newest version left
        becomes current."""
        self.get_object().delete_version()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """Resolved values, warnings and monthly curve for the values being typed (not saved)."""
        serializer = AveragePricePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_representation(serializer.validated_data))

    @action(detail=True, methods=["get", "delete"])
    def history(self, request, pk=None):
        """GET: the versions of the row not hidden (newest first) and their average.
        DELETE: hide all of them."""
        row = self.get_object()
        versions = row.versions()
        if request.method == "DELETE":
            if all(v.deleted_at is not None for v in versions):
                return Response(
                    {"detail": _("This average price was already deleted.")},
                    status=status.HTTP_409_CONFLICT,
                )
            row.delete_all_versions(request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        ids = [v.pk for v in versions]
        rows = {r.pk: r for r in self.get_queryset().filter(pk__in=ids)}
        ordered = [rows[i] for i in ids]
        # Hidden versions (left by the former per-version delete) are not part of the history of
        # a row still listed; a row hidden as a whole still shows all its versions
        standing = [r for r in ordered if r.deleted_at is None]
        ordered = standing or ordered
        average = versions_average([(r.original_value, r.anchors()) for r in standing])
        return Response(
            {
                "versions": AveragePriceSerializer(ordered, many=True).data,
                "average": VersionsAverageSerializer(average).data if average else None,
            }
        )

    @action(detail=False, methods=["get"], url_path="spec-suggestions")
    def spec_suggestions(self, request):
        """Values already used for a specification field of an asset class (prices not
        deleted), most used first. ?asset_class=<id>&key=<field key>&search=<text>"""
        asset_class = request.query_params.get("asset_class", "")
        key = request.query_params.get("key", "")
        if not asset_class.isdigit() or not key:
            return Response(
                {"detail": _("Give the asset class and the field key.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        snapshots = AveragePrice.objects.filter(
            asset_class_id=int(asset_class),
            deleted_at__isnull=True,
            specs__contains=[{"key": key}],
        ).values_list("specs", flat=True)
        search = request.query_params.get("search", "")[:100]
        return Response(suggest_values(snapshots, key, search))

    # --- Documents (shared by every version of the row) ---------------------------------------

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="documents",
        parser_classes=[MultiPartParser, FormParser],
    )
    def documents(self, request, pk=None):
        """GET: documents of the row, newest first. POST (multipart, "file"): add one."""
        row = self.get_object()
        documents = PriceDocument.objects.filter(
            lineage=row.lineage, is_photo=False
        ).select_related("uploaded_by")
        if request.method == "GET":
            return Response(PriceDocumentSerializer(documents, many=True).data)

        if row.deleted_at is not None:
            return Response(
                {"detail": _("Documents cannot be added to a deleted average price.")},
                status=status.HTTP_409_CONFLICT,
            )
        upload = request.FILES.get("file")
        if upload is None:
            return _no_file()
        name = clean_filename(upload.name or "")
        errors = _check_upload(name, upload.size)
        if documents.count() >= MAX_DOCUMENTS:
            errors.append(
                _("An average price can have at most %(max)s documents.") % {"max": MAX_DOCUMENTS}
            )
        if errors:
            return Response({"file": errors}, status=status.HTTP_400_BAD_REQUEST)
        document = PriceDocument.objects.create(
            lineage=row.lineage,
            file=upload,
            name=name,
            size=upload.size,
            content_type=content_type_for(name),
            uploaded_by=request.user,
        )
        AveragePrice.mark_changed(row.lineage, request.user)
        return Response(PriceDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    def _document(self, document_id):
        row = self.get_object()
        try:
            return PriceDocument.objects.get(pk=document_id, lineage=row.lineage, is_photo=False)
        except PriceDocument.DoesNotExist as exc:
            raise Http404 from exc

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<document_id>\d+)")
    def delete_document(self, request, pk=None, document_id=None):
        """Remove a document and its stored file."""
        document = self._document(document_id)
        document.delete()
        AveragePrice.mark_changed(document.lineage, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path=r"documents/(?P<document_id>\d+)/download")
    def download_document(self, request, pk=None, document_id=None):
        """The file, with its original name. ?inline=1 opens PDFs and images in the browser."""
        document = self._document(document_id)
        try:
            handle = document.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        inline = request.query_params.get("inline") == "1" and opens_inline(document.name)
        return FileResponse(
            handle,
            as_attachment=not inline,
            filename=document.name,
            content_type=document.content_type,
        )

    # --- Photo (one per row, shared by every version) ------------------------------------------

    @action(
        detail=True,
        methods=["get", "post", "delete"],
        url_path="photo",
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request, pk=None):
        """GET: the image. POST (multipart, "file"): set or replace it. DELETE: remove it."""
        row = self.get_object()
        current = PriceDocument.objects.filter(lineage=row.lineage, is_photo=True).first()
        if request.method == "GET":
            if current is None:
                raise Http404
            try:
                handle = current.file.open("rb")
            except FileNotFoundError as exc:
                raise Http404 from exc
            return FileResponse(handle, content_type=current.content_type, filename=current.name)

        if row.deleted_at is not None:
            return Response(
                {"detail": _("The photo of a deleted average price cannot be changed.")},
                status=status.HTTP_409_CONFLICT,
            )
        if request.method == "DELETE":
            if current is None:
                raise Http404
            current.delete()
            AveragePrice.mark_changed(row.lineage, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)

        upload = request.FILES.get("file")
        if upload is None:
            return _no_file()
        name = clean_filename(upload.name or "")
        errors = _check_upload(name, upload.size, PHOTO_EXTENSIONS)
        if errors:
            return Response({"file": errors}, status=status.HTTP_400_BAD_REQUEST)
        photo = _replace_photo(row, current, upload, name, upload.size, "", request.user)
        return Response({"photo_id": photo.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="photo/from-url")
    def photo_from_url(self, request, pk=None):
        """Set the photo from an image on the internet: {"url": image, "source_url": page it
        was found on (optional)}. The server downloads it (public addresses only)."""
        row = self.get_object()
        if row.deleted_at is not None:
            return Response(
                {"detail": _("The photo of a deleted average price cannot be changed.")},
                status=status.HTTP_409_CONFLICT,
            )
        url = str(request.data.get("url") or "").strip()
        source = http_url(str(request.data.get("source_url") or "")) or http_url(url) or ""
        max_bytes = settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024
        try:
            data, kind, final_url = fetch_image(url, max_bytes)
        except WebError as exc:
            message = web_error_message(exc)
            if exc.code == "too_large":
                message = _("The file is too large (maximum %(max)s MB).") % {
                    "max": settings.PRICE_DOCUMENT_MAX_MB
                }
            return Response({"url": [message]}, status=status.HTTP_400_BAD_REQUEST)
        name = photo_name_from_url(final_url, kind)
        current = PriceDocument.objects.filter(lineage=row.lineage, is_photo=True).first()
        photo = _replace_photo(
            row, current, ContentFile(data, name=name), name, len(data), source[:1000], request.user
        )
        return Response({"photo_id": photo.pk}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="photo-suggestions")
    def photo_suggestions(self, request, pk=None):
        """Images found on the internet (SearXNG, set in the system settings) for the asset.
        ?q= overrides the search ("<manufacturer> <model> <asset class>" by default)."""
        row = self.get_object()
        default = f"{row.manufacturer.name} {row.model} {row.asset_class.name}"
        return _photo_suggestions(request, default)

    @action(detail=False, methods=["get"], url_path="photo-suggestions")
    def photo_suggestions_for(self, request):
        """Images found on the internet for an asset not saved yet (the form): ?q= required."""
        return _photo_suggestions(request, "")


def _photo_suggestions(request, default_query: str):
    """SearXNG images for ?q= (or `default_query`); 409 when photo search is not set up."""
    preferences = UserPreferences.for_user(request.user)
    # Part of the user's Internet Search (Smart Tools): on, with a SearXNG address
    searxng = preferences.searxng_url if preferences.web_search else ""
    if not searxng:
        return Response(
            {"detail": _("Photo search is not set up (Settings → Smart Tools).")},
            status=status.HTTP_409_CONFLICT,
        )
    query = " ".join(str(request.query_params.get("q") or "").split())[:200] or default_query
    if not query:
        return Response(
            {"detail": _("Type what to search for.")}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        results = search_images(searxng, query)
    except WebError as exc:
        return Response({"detail": web_error_message(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({"query": query, "results": results})


def _replace_photo(row, current, content, name, size, source_url, user):
    """Store the new photo of the row and remove the previous one (with its file)."""
    with transaction.atomic():
        photo = PriceDocument.objects.create(
            lineage=row.lineage,
            file=content,
            name=name,
            size=size,
            content_type=content_type_for(name),
            is_photo=True,
            source_url=source_url,
            uploaded_by=user,
        )
        if current is not None:
            current.delete()  # replaced
        AveragePrice.mark_changed(row.lineage, user)
    return photo


def _no_file():
    return Response({"file": [_("Choose a file to upload.")]}, status=status.HTTP_400_BAD_REQUEST)


def _check_upload(name, size, allowed=ALLOWED_EXTENSIONS):
    return check_document(
        name,
        size,
        settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024,
        {
            "bad_type": _("This type of file is not accepted. Accepted: %(types)s."),
            "too_large": _("The file is too large (maximum %(max)s MB)."),
            "empty": _("The file is empty."),
        },
        allowed,
    )
