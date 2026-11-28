"""The Home's journal: what happened in the system lately — counts only (never names, values or
customers) — and what is new in each version (`releases.py`).

`GET /api/system/journal/?days=` (default: the user's `journal_days` preference: 1 = today, 7 or
30): every event of a module the user may open (its own ViewSet, as the centralized search) with
how many happened since then; events that did not happen are left out. Each event says which
module it belongs to — the frontend names it and opens its grid.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone
from django.utils.translation import get_language
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalogs.views import AssetClassViewSet, AssetModelViewSet, ManufacturerViewSet
from efmv.views import EfmvAnalysisViewSet
from entities.views import BusinessEntityViewSet
from inventory.views import (
    AssetViewSet,
    DisposalViewSet,
    InspectionViewSet,
    ReceivingLotViewSet,
    TransferViewSet,
)
from pricing.models import AveragePrice
from pricing.views import AveragePriceViewSet
from search.access import module_view
from users.views import UserViewSet

from .releases import current_version, release_notes

PERIODS = (1, 7, 30)
DEFAULT_DAYS = 7
RELEASES_SHOWN = 5


@dataclass(frozen=True)
class Event:
    # What happened ("efmv_analyses.created"): the frontend's text and the module it opens
    key: str
    view: type
    count: Callable[[object, datetime], int]


def _since(field: str):
    return lambda queryset, since: queryset.filter(**{f"{field}__gte": since}).count()


def _changed(queryset, since) -> int:
    """Changed in the period but created before it (the new ones count apart)."""
    return queryset.filter(updated_at__gte=since, created_at__lt=since).count()


def _new_prices(queryset, since) -> int:
    # Every version counts (the list shows the current ones only): a first version is a price
    return AveragePrice.objects.filter(
        created_at__gte=since, supersedes__isnull=True, deleted_at__isnull=True
    ).count()


def _new_versions(queryset, since) -> int:
    return AveragePrice.objects.filter(
        created_at__gte=since, supersedes__isnull=False, deleted_at__isnull=True
    ).count()


# In the order the journal shows them (by app: Pricing, Asset Management, Administration)
EVENTS: tuple[Event, ...] = (
    Event("efmv_analyses.created", EfmvAnalysisViewSet, _since("created_at")),
    Event("efmv_analyses.updated", EfmvAnalysisViewSet, _changed),
    Event("average_prices.created", AveragePriceViewSet, _new_prices),
    Event("average_prices.versions", AveragePriceViewSet, _new_versions),
    Event("assets.created", AssetViewSet, _since("created_at")),
    Event("receiving_lots.opened", ReceivingLotViewSet, _since("opened_at")),
    Event("inspections.approved", InspectionViewSet, _since("approved_at")),
    Event("disposals.shipped", DisposalViewSet, _since("shipped_at")),
    Event("transfers.received", TransferViewSet, _since("received_at")),
    Event("business_entities.created", BusinessEntityViewSet, _since("created_at")),
    Event("manufacturers.created", ManufacturerViewSet, _since("created_at")),
    Event("asset_classes.created", AssetClassViewSet, _since("created_at")),
    Event("asset_models.created", AssetModelViewSet, _since("created_at")),
    Event("users.created", UserViewSet, _since("date_joined")),
)


def period_start(days: int, now: datetime | None = None) -> datetime:
    """1 = today (since midnight, in the server's time zone); otherwise the last `days` days."""
    now = timezone.localtime(now or timezone.now())
    if days == 1:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(days=days)


def _days(request) -> int:
    typed = request.query_params.get("days", "")
    if typed.isdigit() and int(typed) in PERIODS:
        return int(typed)
    preferences = getattr(request.user, "preferences", None)
    chosen = getattr(preferences, "journal_days", DEFAULT_DAYS)
    return chosen if chosen in PERIODS else DEFAULT_DAYS


@api_view(["GET"])
def journal(request):
    days = _days(request)
    since = period_start(days)
    views: dict[type, object] = {}
    events = []
    for event in EVENTS:
        if event.view not in views:
            view = module_view(event.view, request)
            views[event.view] = view.get_queryset() if view is not None else None
        queryset = views[event.view]
        if queryset is None:
            continue
        count = event.count(queryset, since)
        if count:
            events.append({"key": event.key, "count": count})
    language = get_language() or "en"
    return Response(
        {
            "days": days,
            "since": since.isoformat(),
            "events": events,
            "version": current_version(),
            "releases": release_notes(language, RELEASES_SHOWN),
        }
    )
