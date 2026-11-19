from django.db.models import ProtectedError
from django.utils.translation import gettext as _
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from .models import AccountManager
from .serializers import AccountManagerSerializer


class AccountManagerViewSet(viewsets.ModelViewSet):
    """CRUD for account managers, including the business verticals they work in.

    List supports ?search= (name, email or vertical name), ?ordering= (id, full_name, email;
    prefix "-" for descending), ?page= and ?page_size=.
    """

    queryset = AccountManager.objects.prefetch_related("verticals")
    serializer_class = AccountManagerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "email", "verticals__name"]
    ordering_fields = ["id", "full_name", "email"]
    ordering = ["full_name"]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": _("This account manager has customers and cannot be deleted.")},
                status=status.HTTP_409_CONFLICT,
            )
