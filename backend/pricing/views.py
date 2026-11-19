from django.conf import settings
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.utils.translation import gettext as _
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from catalogs.specs import suggest_values

from .averages import versions_average
from .documents import (
    ALLOWED_EXTENSIONS,
    MAX_DOCUMENTS,
    PHOTO_EXTENSIONS,
    check_document,
    clean_filename,
    content_type_for,
    opens_inline,
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
    ?manufacturer= (ids), ?ordering= (created_at, model, original_value, asset_class__name,
    manufacturer__name), ?page= and ?page_size=. GET /<id>/ includes the monthly curve and works
    for previous versions too; GET /<id>/history/ lists every version of the row and their
    average. POST /preview/ resolves values typed in the form (nothing saved).
    GET /spec-suggestions/?asset_class=&key=&search= offers specification values already used.
    Documents of the row (shared by all its versions): GET/POST /<id>/documents/ (multipart,
    field "file"), DELETE /<id>/documents/<doc>/, GET /<id>/documents/<doc>/download/
    (?inline=1 opens PDFs and images in the browser). Photo of the asset: GET/POST/DELETE
    /<id>/photo/ (POST replaces it).
    """

    queryset = AveragePrice.objects.select_related(
        "sub_vertical__vertical", "asset_class", "manufacturer", "created_by"
    ).prefetch_related(
        Prefetch("points", queryset=PricePoint.objects.select_related("average_price"))
    )
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
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
            )
        )
        if self.action == "list":
            queryset = queryset.active()
            for param, field in FILTERS.items():
                value = self.request.query_params.get(param, "")
                if value.isdigit():
                    queryset = queryset.filter(**{field: int(value)})
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
        self._document(document_id).delete()
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
            return Response(status=status.HTTP_204_NO_CONTENT)

        upload = request.FILES.get("file")
        if upload is None:
            return _no_file()
        name = clean_filename(upload.name or "")
        errors = _check_upload(name, upload.size, PHOTO_EXTENSIONS)
        if errors:
            return Response({"file": errors}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            photo = PriceDocument.objects.create(
                lineage=row.lineage,
                file=upload,
                name=name,
                size=upload.size,
                content_type=content_type_for(name),
                is_photo=True,
                uploaded_by=request.user,
            )
            if current is not None:
                current.delete()  # replaced
        return Response({"photo_id": photo.pk}, status=status.HTTP_201_CREATED)


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
