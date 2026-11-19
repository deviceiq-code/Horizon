from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from config.photos import photo_response

from .models import AccountManager
from .serializers import AccountManagerSerializer


class AccountManagerViewSet(viewsets.ModelViewSet):
    """CRUD for account managers, including the business verticals they work in.

    List supports ?search= (name, email or vertical name), ?ordering= (id, full_name,
    first_name, last_name, email; prefix "-" for descending), ?page= and ?page_size=.
    Photo: GET/POST (multipart, "file"; replaces)/DELETE /<id>/photo/.
    """

    queryset = AccountManager.objects.prefetch_related("verticals")
    serializer_class = AccountManagerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "verticals__name"]
    ordering_fields = ["id", "full_name", "first_name", "last_name", "email"]
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
        return photo_response(
            request,
            self.get_object(),
            can_change=True,
            saved_data=lambda manager: self.get_serializer(manager).data,
        )
