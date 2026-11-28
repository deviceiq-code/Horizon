"""The inventory's indicators panel (spec §10). Ratios are pure functions (percentages with 5
places — config.decimals); `panel()` gathers the data for a period, a warehouse and/or a
customer.

- Lead time arrival → available (days): entry to the first event making the asset AVAILABLE,
  by customer and asset class.
- Aging by status: days since the last status change, in bands (0–7, 8–30, 31–90, 91+).
- Location accuracy: assets found where expected ÷ assets expected, per count closed.
- Divergences per lot and per customer: triage occurrences ÷ units received.
- Assets without a serial number: not captured ÷ all, by asset class and customer.
- Grade distribution: assets by conservation level (current report), by asset class.
- Blocks released in time: released ÷ closed ones (released, expired, closed).
- Disputes upheld: upheld or partially upheld ÷ decided.
- Penalties found × charged: sums of the findings' values by status.
- Scrap rate: approved reports sending the asset to scrap ÷ approved reports, by asset class
  and customer.
"""

from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, F, Max, Min, Q, Sum
from django.utils import timezone

from config.decimals import percent

from .models import (
    Asset,
    BlockFollowUp,
    BlockStatus,
    CountStatus,
    Destination,
    Dispute,
    DisputeDecision,
    DisputeStatus,
    Finding,
    FindingStatus,
    InspectionReport,
    InventoryCount,
    MovementEvent,
    Occurrence,
    ReceivingLot,
)
from .states import AssetStatus

AGING_BANDS = ((0, 7), (8, 30), (31, 90), (91, None))


# --- Pure ----------------------------------------------------------------------------------------


def ratio(part, whole) -> Decimal | None:
    """part ÷ whole as a percentage with 5 places; None without a whole."""
    if not whole:
        return None
    return percent(Decimal(part) * 100 / Decimal(whole))


def average(values) -> Decimal | None:
    values = list(values)
    if not values:
        return None
    return (Decimal(sum(values)) / len(values)).quantize(Decimal("0.1"))


def band(days: int) -> str:
    """The aging band of a number of days ("0-7", "8-30", "31-90", "91+")."""
    for low, high in AGING_BANDS:
        if high is None or days <= high:
            return f"{low}+" if high is None else f"{low}-{high}"
    return ""


def band_counts(days_by_status: dict[str, list[int]]) -> list[dict]:
    """Per status: assets in each aging band and the oldest."""
    rows = []
    for status_value in AssetStatus.values:
        days = days_by_status.get(status_value)
        if not days:
            continue
        bands = {band(low): 0 for low, _high in AGING_BANDS}
        for value in days:
            bands[band(value)] += 1
        rows.append(
            {"status": status_value, "total": len(days), "bands": bands, "max_days": max(days)}
        )
    return rows


def rows_by(groups: dict[str, tuple[int, int]], *, key="label") -> list[dict]:
    """{label: (part, whole)} → rows with the percentage, the largest wholes first."""
    rows = [
        {key: label, "part": part, "total": whole, "percent": ratio(part, whole)}
        for label, (part, whole) in groups.items()
    ]
    return sorted(rows, key=lambda r: (-r["total"], str(r[key])))


# --- Queries -------------------------------------------------------------------------------------


def as_strings(value):
    """Decimals as strings (as every money and percentage travels in the API)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: as_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_strings(v) for v in value]
    return value


def _range(start: date | None, end: date | None):
    tz = timezone.get_current_timezone()
    low = timezone.make_aware(datetime.combine(start, time.min), tz) if start else None
    high = timezone.make_aware(datetime.combine(end, time.max), tz) if end else None
    return low, high


def _in(field: str, low, high) -> Q:
    q = Q()
    if low:
        q &= Q(**{f"{field}__gte": low})
    if high:
        q &= Q(**{f"{field}__lte": high})
    return q


def _customer(customer) -> str:
    return (customer.trade_name or customer.name) if customer else "—"


def panel(*, start=None, end=None, warehouse=None, customer=None, today=None) -> dict:
    today = today or timezone.localdate()
    low, high = _range(start, end)
    assets = Asset.objects.all()
    if warehouse is not None:
        assets = assets.filter(current_location__warehouse=warehouse)
    if customer is not None:
        assets = assets.filter(customer=customer)
    asset_ids = assets.values("pk")

    # Lead time: entry → first AVAILABLE (assets that became available in the period)
    first_available = (
        MovementEvent.objects.filter(asset_id__in=asset_ids, status_after=AssetStatus.AVAILABLE)
        .exclude(status_before=AssetStatus.AVAILABLE)
        .values("asset_id")
        .annotate(at=Min("at"))
    )
    available_at = {
        row["asset_id"]: row["at"]
        for row in first_available
        if (not low or row["at"] >= low) and (not high or row["at"] <= high)
    }
    lead_customer: dict[str, list[int]] = defaultdict(list)
    lead_class: dict[str, list[int]] = defaultdict(list)
    lead_all = []
    for asset in Asset.objects.filter(pk__in=available_at).select_related(
        "customer__entity", "asset_model__asset_class"
    ):
        days = (available_at[asset.pk] - asset.created_at).days
        lead_all.append(days)
        lead_customer[_customer(asset.customer)].append(days)
        lead_class[asset.asset_model.asset_class.name].append(days)

    def lead_rows(groups):
        return sorted(
            (
                {"label": label, "units": len(days), "average_days": average(days)}
                for label, days in groups.items()
            ),
            key=lambda r: (-r["units"], r["label"]),
        )

    # Aging by status (now)
    last_change = defaultdict(lambda: None)
    for row in (
        MovementEvent.objects.filter(asset_id__in=asset_ids)
        .exclude(status_after="")
        .exclude(status_before=F("status_after"))
        .values("asset_id")
        .annotate(at=Max("at"))
    ):
        last_change[row["asset_id"]] = row["at"]
    aging: dict[str, list[int]] = defaultdict(list)
    for pk, status_value, created in assets.exclude(
        status__in=[AssetStatus.WRITTEN_OFF]
    ).values_list("pk", "status", "created_at"):
        since = last_change[pk] or created
        aging[status_value].append((today - timezone.localtime(since).date()).days)

    # Location accuracy per count closed in the period
    counts = InventoryCount.objects.filter(
        status__in=[CountStatus.CLOSED, CountStatus.FINISHED]
    ).filter(_in("closed_at", low, high))
    if warehouse is not None:
        counts = counts.filter(warehouse=warehouse)
    accuracy = [
        {
            "count": c.code,
            "warehouse": c.warehouse.code,
            "closed_at": c.closed_at,
            "expected": c.expected_assets,
            "matched": c.matched_assets,
            "percent": ratio(c.matched_assets, c.expected_assets),
        }
        for c in counts.select_related("warehouse").order_by("-closed_at")[:20]
    ]
    total_expected = sum(c["expected"] for c in accuracy)
    total_matched = sum(c["matched"] for c in accuracy)

    # Triage divergences per lot and customer (lots opened in the period)
    lots = Asset.objects.filter(lot__isnull=False).filter(_in("lot__opened_at", low, high))
    if warehouse is not None:
        lots = lots.filter(lot__warehouse=warehouse)
    if customer is not None:
        lots = lots.filter(lot__customer=customer)
    units_per_lot = dict(lots.values("lot_id").annotate(n=Count("pk")).values_list("lot_id", "n"))
    occurrences_per_lot = dict(
        Occurrence.objects.filter(lot_id__in=units_per_lot)
        .values("lot_id")
        .annotate(n=Count("pk"))
        .values_list("lot_id", "n")
    )
    lot_groups: dict[str, tuple[int, int]] = {}
    customer_groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for lot in ReceivingLot.objects.filter(pk__in=units_per_lot).select_related("customer__entity"):
        found = occurrences_per_lot.get(lot.pk, 0)
        units = units_per_lot[lot.pk]
        lot_groups[lot.code] = (found, units)
        entry = customer_groups[_customer(lot.customer)]
        entry[0] += found
        entry[1] += units

    # Without a serial number (assets created in the period)
    created = assets.filter(_in("created_at", low, high)).exclude(parent_asset__isnull=False)
    serial_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    serial_customer: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for asset in created.select_related("asset_model__asset_class", "customer__entity"):
        missing = int(asset.serial_status != "captured")
        for groups, label in (
            (serial_class, asset.asset_model.asset_class.name),
            (serial_customer, _customer(asset.customer)),
        ):
            groups[label][0] += missing
            groups[label][1] += 1

    # Grade distribution (assets in stock, by their current report)
    grades: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for class_name, conservation in (
        assets.exclude(status__in=[AssetStatus.WRITTEN_OFF])
        .filter(reports__is_current=True)
        .values_list("asset_model__asset_class__name", "reports__conservation")
    ):
        grades[class_name][conservation or "—"] += 1

    # Blocks released in time and disputes upheld (closed / decided in the period)
    blocks = BlockFollowUp.objects.filter(asset_id__in=asset_ids)
    closed_blocks = blocks.filter(
        status__in=[BlockStatus.RELEASED, BlockStatus.EXPIRED, BlockStatus.CLOSED]
    ).filter(_in("created_at", low, high))
    released = closed_blocks.filter(status=BlockStatus.RELEASED).count()
    disputes = Dispute.objects.filter(
        report__asset_id__in=asset_ids, status=DisputeStatus.DECIDED
    ).filter(_in("decided_at", low, high))
    upheld = disputes.filter(
        decision__in=[DisputeDecision.UPHELD, DisputeDecision.PARTIALLY_UPHELD]
    ).count()

    # Penalties found × charged (findings of current reports approved in the period)
    findings = Finding.objects.filter(
        report__asset_id__in=asset_ids,
        # Only the current version: a new version carries its findings over
        report__is_current=True,
    ).filter(_in("report__approved_at", low, high))
    sums = {
        row["status"]: row["total"] or Decimal("0")
        for row in findings.values("status").annotate(total=Sum("value"))
    }
    found_total = sum((v for k, v in sums.items() if k != FindingStatus.CANCELLED), Decimal("0"))

    # Scrap rate (reports approved in the period)
    reports = InspectionReport.objects.filter(
        asset_id__in=asset_ids, approved_at__isnull=False
    ).filter(_in("approved_at", low, high))
    scrap_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    scrap_customer: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for report in reports.select_related(
        "asset__asset_model__asset_class", "asset__customer__entity"
    ):
        scrapped = int(report.recommended_destination == Destination.SCRAP)
        for groups, label in (
            (scrap_class, report.asset.asset_model.asset_class.name),
            (scrap_customer, _customer(report.asset.customer)),
        ):
            groups[label][0] += scrapped
            groups[label][1] += 1

    def pairs(groups):
        return rows_by({k: (v[0], v[1]) for k, v in groups.items()})

    return {
        "lead_time": {
            "average_days": average(lead_all),
            "units": len(lead_all),
            "by_customer": lead_rows(lead_customer),
            "by_asset_class": lead_rows(lead_class),
        },
        "aging": band_counts(aging),
        "location_accuracy": {
            "percent": ratio(total_matched, total_expected),
            "counts": accuracy,
        },
        "divergences": {
            "by_lot": rows_by(lot_groups)[:20],
            "by_customer": pairs(customer_groups),
        },
        "without_serial": {
            "percent": ratio(
                sum(v[0] for v in serial_class.values()), sum(v[1] for v in serial_class.values())
            ),
            "by_asset_class": pairs(serial_class),
            "by_customer": pairs(serial_customer),
        },
        "grades": [
            {"asset_class": name, "levels": dict(levels), "total": sum(levels.values())}
            for name, levels in sorted(grades.items())
        ],
        "blocks_released": {
            "released": released,
            "closed": closed_blocks.count(),
            "percent": ratio(released, closed_blocks.count()),
        },
        "disputes_upheld": {
            "upheld": upheld,
            "decided": disputes.count(),
            "percent": ratio(upheld, disputes.count()),
        },
        "penalties": {
            "found": f"{found_total:.2f}",
            "chargeable": f"{sums.get(FindingStatus.CHARGEABLE, Decimal('0')):.2f}",
            "charged": f"{sums.get(FindingStatus.CHARGED, Decimal('0')):.2f}",
            "cancelled": f"{sums.get(FindingStatus.CANCELLED, Decimal('0')):.2f}",
        },
        "scrap_rate": {
            "percent": ratio(
                sum(v[0] for v in scrap_class.values()), sum(v[1] for v in scrap_class.values())
            ),
            "by_asset_class": pairs(scrap_class),
            "by_customer": pairs(scrap_customer),
        },
    }
