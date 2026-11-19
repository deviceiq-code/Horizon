from django.db.models import ProtectedError
from django.http import FileResponse, Http404
from django.utils.translation import gettext as _
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from pricing.documents import PHOTO_EXTENSIONS, check_document, clean_filename, content_type_for

from .models import AccountManager
from .serializers import AccountManagerSerializer

# The browser sends a small square picture; this only guards against oversized files
MAX_PHOTO_MB = 5


class AccountManagerViewSet(viewsets.ModelViewSet):
    """CRUD for account managers, including the business verticals they work in.

    List supports ?search= (name, email or vertical name), ?ordering= (id, full_name, email;
    prefix "-" for descending), ?page= and ?page_size=. Photo: GET/POST (multipart, "file";
    replaces)/DELETE /<id>/photo/.
    """

    queryset = AccountManager.objects.prefetch_related("verticals")
    serializer_class = AccountManagerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "email", "verticals__name"]
    ordering_fields = ["id", "full_name", "email"]
    ordering = ["full_name"]

    def destroy(self, request, *args, **kwargs):
        # Primary customers are protected by the foreign key (ProtectedError); secondary ones
        # live in a many-to-many table that would just drop the link, so check them here.
        refused = Response(
            {"detail": _("This account manager has customers and cannot be deleted.")},
            status=status.HTTP_409_CONFLICT,
        )
        if self.get_object().secondary_customers.exists():
            return refused
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return refused

    @action(
        detail=True,
        methods=["get", "post", "delete"],
        url_path="photo",
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request, pk=None):
        """GET: the image. POST (multipart, "file"): set or replace it. DELETE: remove it."""
        manager = self.get_object()
        if request.method == "GET":
            if not manager.photo:
                raise Http404
            try:
                handle = manager.photo.open("rb")
            except FileNotFoundError as exc:
                raise Http404 from exc
            return FileResponse(handle, content_type=content_type_for(manager.photo.name))
        if request.method == "DELETE":
            if not manager.photo:
                raise Http404
            manager.set_photo(None)
            return Response(status=status.HTTP_204_NO_CONTENT)

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": [_("Choose a file to upload.")]}, status=status.HTTP_400_BAD_REQUEST
            )
        name = clean_filename(upload.name or "")
        errors = check_document(
            name,
            upload.size,
            MAX_PHOTO_MB * 1024 * 1024,
            {
                "bad_type": _("This type of file is not accepted. Accepted: %(types)s."),
                "too_large": _("The file is too large (maximum %(max)s MB)."),
                "empty": _("The file is empty."),
            },
            PHOTO_EXTENSIONS,
        )
        if errors:
            return Response({"file": errors}, status=status.HTTP_400_BAD_REQUEST)
        manager.set_photo(upload)
        return Response(self.get_serializer(manager).data, status=status.HTTP_201_CREATED)
