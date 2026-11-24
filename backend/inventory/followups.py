"""Phase 4: access block follow-ups (RN-20), disputes of reports (RN-14, RN-21, RN-22), the
daily routine and alerts. Status changes of assets go through inventory.services (RN-07);
refusals raise states.DomainError (translated)."""

from django.conf import settings
from django.db import transaction
from django.db.models import F, Max, OuterRef, Subquery
from django.utils import timezone
from django.utils.translation import gettext as _

from pricing.documents import check_document, clean_filename, content_type_for
from users.models import INVENTORY_SUPERVISOR

from . import services
from .deadlines import add_days, days_left
from .inspection import _copy_from
from .models import (
    AgingLimit,
    Alert,
    Asset,
    BlockFollowUp,
    BlockStatus,
    DeadlineKind,
    DeadlineSetting,
    Dispute,
    DisputeDecision,
    DisputeStatus,
    Evidence,
    ExpiredDecision,
    Finding,
    FindingKind,
    FindingStatus,
    Holiday,
    InspectionReport,
    MovementEvent,
    ReportStatus,
)
from .receiving import attachment_messages
from .states import AssetStatus, DomainError


def deadline(kind: str, start=None):
    """The last day of a deadline of this kind counted from `start` (today by default)."""
    setting = DeadlineSetting.of(kind)
    holidays = set(Holiday.objects.values_list("date", flat=True))
    return add_days(
        start or timezone.localdate(),
        setting.days,
        business=setting.business_days,
        holidays=holidays,
    )


def add_evidence(*, upload, user, followup=None, dispute=None) -> Evidence:
    name = clean_filename(upload.name or "")
    errors = check_document(
        name, upload.size, settings.PRICE_DOCUMENT_MAX_MB * 1024 * 1024, attachment_messages()
    )
    if errors:
        raise DomainError(" ".join(str(e) for e in errors), field="file")
    evidence = Evidence(
        followup=followup,
        dispute=dispute,
        name=name,
        size=upload.size,
        content_type=content_type_for(name),
        uploaded_by=user,
    )
    evidence.file.save(name, upload, save=False)
    evidence.save()
    return evidence


# --- Access blocks (RN-20) ---------------------------------------------------------------------


def create_followups(report: InspectionReport) -> list[BlockFollowUp]:
    """Called when a report is approved: one follow-up per access block (not yet notified)."""
    created = []
    for finding in report.findings.filter(kind=FindingKind.ACCESS_BLOCK).exclude(
        status=FindingStatus.CANCELLED
    ):
        followup, made = BlockFollowUp.objects.get_or_create(
            finding=finding,
            defaults={"asset_id": report.asset_id, "block_type": finding.block_type},
        )
        if made:
            created.append(followup)
    return created


@transaction.atomic
def mark_notified(followups, *, user) -> list[BlockFollowUp]:
    """The customer was notified: the release deadline starts."""
    now, due = timezone.now(), deadline(DeadlineKind.BLOCK_RELEASE)
    done = []
    for followup in BlockFollowUp.objects.select_for_update().filter(
        pk__in=[f.pk for f in followups]
    ):
        if followup.status != BlockStatus.OPEN:
            raise DomainError(_("Only open blocks are notified."), field="status")
        if followup.notified_at is None:
            followup.notified_at, followup.due_date = now, due
            followup.save(update_fields=["notified_at", "due_date"])
        done.append(followup)
    return done


def _lock(followup) -> BlockFollowUp:
    return (
        BlockFollowUp.objects.select_for_update()
        .select_related("asset", "finding")
        .get(pk=followup.pk)
    )


@transaction.atomic
def report_release(followup: BlockFollowUp, *, user) -> BlockFollowUp:
    """The customer says the block was released: a technician checks it."""
    followup = _lock(followup)
    if followup.status != BlockStatus.OPEN:
        raise DomainError(_("Only open blocks wait for a release."), field="status")
    followup.status = BlockStatus.RELEASE_REPORTED
    followup.release_reported_at = timezone.now()
    followup.save(update_fields=["status", "release_reported_at"])
    return followup


@transaction.atomic
def check_release(followup: BlockFollowUp, *, user, released: bool) -> BlockFollowUp:
    """Released: the asset goes back to inspection (a new report version, the block finding
    cancelled — erase the data and finish it). Not released: open again, the deadline runs."""
    followup = _lock(followup)
    if followup.status != BlockStatus.RELEASE_REPORTED:
        raise DomainError(_("No release was reported for this block."), field="status")
    followup.checked_by, followup.checked_at = user, timezone.now()
    if not released:
        followup.status = BlockStatus.OPEN
        followup.save(update_fields=["status", "checked_by", "checked_at"])
        return followup
    followup.status = BlockStatus.RELEASED
    followup.save(update_fields=["status", "checked_by", "checked_at"])
    asset = followup.asset
    others_open = asset.block_followups.exclude(pk=followup.pk).filter(
        status__in=[BlockStatus.OPEN, BlockStatus.RELEASE_REPORTED, BlockStatus.EXPIRED]
    )
    if asset.status == AssetStatus.BLOCKED and not others_open.exists():
        current = asset.reports.filter(is_current=True).first()
        if (
            current
            and not asset.reports.filter(
                status__in=[ReportStatus.DRAFT, ReportStatus.AWAITING_APPROVAL]
            ).exists()
        ):
            report = InspectionReport.objects.create(
                asset=asset,
                version=(asset.reports.aggregate(last=Max("version"))["last"] or 0) + 1,
                technician=user,
                new_version_reason=_("Access block released."),
            )
            _copy_from(current, report)
            report.findings.filter(kind=FindingKind.ACCESS_BLOCK).update(
                status=FindingStatus.CANCELLED
            )
        services.change_status(
            asset,
            to_status=AssetStatus.IN_INSPECTION,
            user=user,
            reason=_("Access block released."),
            document_ref=f"block:{followup.pk}",
        )
    return followup


@transaction.atomic
def decide_expired(
    followup: BlockFollowUp, *, user, decision: str, notes: str = ""
) -> BlockFollowUp:
    """A supervisor decides what becomes of an asset whose block expired: parts or scrap (the
    asset goes to scrap; parts are harvested from there) or other (described)."""
    followup = _lock(followup)
    if followup.status != BlockStatus.EXPIRED:
        raise DomainError(_("Only expired blocks need a decision."), field="status")
    if decision not in ExpiredDecision.values:
        raise DomainError(_("Choose the decision."), field="decision")
    if decision == ExpiredDecision.OTHER and not notes.strip():
        raise DomainError(_("Describe the decision."), field="decision_notes")
    followup.status = BlockStatus.CLOSED
    followup.decision, followup.decision_notes = decision, notes.strip()
    followup.decided_by, followup.decided_at = user, timezone.now()
    followup.save()
    asset = followup.asset
    if (
        decision in (ExpiredDecision.PARTS, ExpiredDecision.SCRAP)
        and asset.status == AssetStatus.BLOCKED
    ):
        services.change_status(
            asset,
            to_status=AssetStatus.SCRAP,
            user=user,
            reason=notes or _("Access block expired."),
            document_ref=f"block:{followup.pk}",
        )
    return followup


# --- Disputes (RN-14, RN-21, RN-22) ----------------------------------------------------------


@transaction.atomic
def register_dispute(report: InspectionReport, *, user, findings, justification: str) -> Dispute:
    """The customer disputes findings of a report sent to them, within the deadline (RN-21).
    Disputed findings → disputed; the report's other approved ones → chargeable; the asset is
    held until the decision."""
    report = InspectionReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ReportStatus.APPROVED or not report.is_current:
        raise DomainError(_("Only the current approved report can be disputed."), field="report")
    if report.sent_to_customer_at is None:
        raise DomainError(_("This report was not sent to the customer."), field="report")
    if report.dispute_deadline and timezone.localdate() > report.dispute_deadline:
        raise DomainError(_("The dispute deadline is over."), field="report")
    if not justification.strip():
        raise DomainError(_("Write the customer's justification."), field="justification")
    chosen = list(report.findings.filter(pk__in=[f.pk for f in findings]))
    if not chosen or len(chosen) != len(findings):
        raise DomainError(_("Choose findings of this report."), field="findings")
    if any(f.status != FindingStatus.APPROVED for f in chosen):
        raise DomainError(_("Only approved findings can be disputed."), field="findings")
    dispute = Dispute.objects.create(
        report=report,
        justification=justification.strip(),
        registered_by=user,
        analysis_due=deadline(DeadlineKind.DISPUTE_ANALYSIS),
    )
    dispute.findings.set(chosen)
    Finding.objects.filter(pk__in=[f.pk for f in chosen]).update(status=FindingStatus.DISPUTED)
    report.findings.filter(status=FindingStatus.APPROVED).update(status=FindingStatus.CHARGEABLE)
    Asset.objects.filter(pk=report.asset_id).update(held_for_dispute=True)
    return dispute


def _lock_dispute(dispute) -> Dispute:
    return Dispute.objects.select_for_update().select_related("report").get(pk=dispute.pk)


def _check_analyst(dispute: Dispute, user):
    if dispute.report.technician_id == user.pk:  # RN-14
        raise DomainError(_("The report's technician cannot analyse its dispute."), field="analyst")


@transaction.atomic
def start_analysis(dispute: Dispute, *, user) -> Dispute:
    dispute = _lock_dispute(dispute)
    _check_analyst(dispute, user)
    if dispute.status not in (DisputeStatus.OPEN, DisputeStatus.ESCALATED):
        raise DomainError(_("This dispute is not waiting for analysis."), field="status")
    dispute.status, dispute.analyst = DisputeStatus.IN_ANALYSIS, user
    dispute.save(update_fields=["status", "analyst"])
    return dispute


@transaction.atomic
def decide_dispute(
    dispute: Dispute,
    *,
    user,
    decision: str,
    notes: str,
    upheld_findings=(),
    reinspected: bool = False,
) -> Dispute:
    """Upheld: every disputed finding is cancelled; partially: those chosen are cancelled, the
    rest chargeable; both in a new report version (approved by the analyst — RN-09). Rejected:
    the findings are chargeable. The asset is no longer held."""
    dispute = _lock_dispute(dispute)
    _check_analyst(dispute, user)
    if dispute.status == DisputeStatus.DECIDED:
        raise DomainError(_("This dispute was already decided."), field="status")
    if decision not in DisputeDecision.values:
        raise DomainError(_("Choose the decision."), field="decision")
    if not notes.strip():
        raise DomainError(_("Justify the decision."), field="decision_notes")
    disputed = list(dispute.findings.all())
    if decision == DisputeDecision.UPHELD:
        cancelled = {f.pk for f in disputed}
    elif decision == DisputeDecision.PARTIALLY_UPHELD:
        cancelled = {f.pk for f in upheld_findings} & {f.pk for f in disputed}
        if not cancelled or cancelled == {f.pk for f in disputed}:
            raise DomainError(
                _("Choose some (not all) of the disputed findings to cancel."), field="findings"
            )
    else:
        cancelled = set()

    report = dispute.report
    if cancelled:
        # A new version with the findings adjusted, approved by the analyst
        new = InspectionReport.objects.create(
            asset_id=report.asset_id,
            version=(report.asset.reports.aggregate(last=Max("version"))["last"] or 0) + 1,
            technician=report.technician,
            new_version_reason=_("Dispute %(decision)s: %(notes)s")
            % {"decision": DisputeDecision(decision).label, "notes": notes.strip()},
        )
        _copy_from(report, new)
        keys = {(f.kind, f.item, f.description) for f in disputed if f.pk in cancelled}
        for finding in new.findings.all():
            finding.status = (
                FindingStatus.CANCELLED
                if (finding.kind, finding.item, finding.description) in keys
                else FindingStatus.CHARGEABLE
            )
            finding.approved_by = user
            finding.save(update_fields=["status", "approved_by"])
        report.is_current, report.status = False, ReportStatus.SUPERSEDED
        report.save(update_fields=["is_current", "status"])
        new.status, new.is_current = ReportStatus.APPROVED, True
        new.approved_by, new.approved_at = user, timezone.now()
        new.finished_at = new.approved_at
        new.recommended_destination = report.recommended_destination
        new.sent_to_customer_at = report.sent_to_customer_at
        new.dispute_deadline = report.dispute_deadline
        new.save()
        dispute.new_report = new
        Finding.objects.filter(pk__in=[f.pk for f in disputed]).update(
            status=FindingStatus.CANCELLED
        )
    else:
        Finding.objects.filter(pk__in=[f.pk for f in disputed]).update(
            status=FindingStatus.CHARGEABLE
        )
    dispute.status, dispute.decision = DisputeStatus.DECIDED, decision
    dispute.decision_notes, dispute.decided_at = notes.strip(), timezone.now()
    dispute.reinspected, dispute.analyst = reinspected, dispute.analyst or user
    dispute.save()
    Asset.objects.filter(pk=report.asset_id).update(held_for_dispute=False)
    return dispute


@transaction.atomic
def mark_charged(finding: Finding, *, user) -> Finding:
    """The penalty was charged to the customer (billing happens outside Horizon)."""
    finding = Finding.objects.select_for_update().get(pk=finding.pk)
    if finding.status != FindingStatus.CHARGEABLE:
        raise DomainError(_("Only chargeable findings can be marked as charged."), field="status")
    finding.status = FindingStatus.CHARGED
    finding.save(update_fields=["status"])
    return finding


# --- Alerts and the daily routine --------------------------------------------------------------


def alert(key: str, kind: str, *, ref="", role_key="", user=None, **params) -> bool:
    """Create the alert once (its key); True when it is new."""
    _alert, created = Alert.objects.get_or_create(
        key=key,
        defaults={"kind": kind, "ref": ref, "role_key": role_key, "user": user, "params": params},
    )
    return created


def check_deadlines(today=None) -> dict:
    """The daily routine (idempotent: running it twice changes nothing more)."""
    today = today or timezone.localdate()
    counts = {"expired_blocks": 0, "chargeable": 0, "escalated": 0, "alerts": 0}

    with transaction.atomic():
        # RN-20: blocks past their deadline
        for followup in BlockFollowUp.objects.select_for_update().filter(
            status__in=[BlockStatus.OPEN, BlockStatus.RELEASE_REPORTED], due_date__lt=today
        ):
            followup.status = BlockStatus.EXPIRED
            followup.save(update_fields=["status"])
            Finding.objects.filter(pk=followup.finding_id, status=FindingStatus.APPROVED).update(
                status=FindingStatus.CHARGEABLE
            )
            counts["expired_blocks"] += 1
            counts["alerts"] += alert(
                f"block_expired:{followup.pk}",
                "block_expired",
                ref=f"block:{followup.pk}",
                role_key=INVENTORY_SUPERVISOR,
                asset=followup.asset.horizon_id,
            )

        # RN-22: reports past the dispute deadline without a dispute
        counts["chargeable"] = (
            Finding.objects.filter(
                status=FindingStatus.APPROVED,
                report__is_current=True,
                report__dispute_deadline__lt=today,
            )
            .exclude(
                kind=FindingKind.ACCESS_BLOCK,
                followup__status__in=[BlockStatus.OPEN, BlockStatus.RELEASE_REPORTED],
            )
            .update(status=FindingStatus.CHARGEABLE)
        )

        # Disputes past the analysis deadline: escalated
        for dispute in Dispute.objects.select_for_update().filter(
            status__in=[DisputeStatus.OPEN, DisputeStatus.IN_ANALYSIS], analysis_due__lt=today
        ):
            dispute.status = DisputeStatus.ESCALATED
            dispute.save(update_fields=["status"])
            counts["escalated"] += 1
            counts["alerts"] += alert(
                f"dispute_escalated:{dispute.pk}",
                "dispute_escalated",
                ref=f"dispute:{dispute.pk}",
                role_key=INVENTORY_SUPERVISOR,
                asset=dispute.report.asset.horizon_id,
            )

    # Reminders before the deadlines
    block_setting = DeadlineSetting.of(DeadlineKind.BLOCK_RELEASE)
    for followup in BlockFollowUp.objects.filter(
        status__in=[BlockStatus.OPEN, BlockStatus.RELEASE_REPORTED], due_date__isnull=False
    ).select_related("asset"):
        left = days_left(today, followup.due_date)
        if left in block_setting.reminder_days:
            counts["alerts"] += alert(
                f"block_due:{followup.pk}:{left}",
                "block_due",
                ref=f"block:{followup.pk}",
                role_key="commercial_finance",
                asset=followup.asset.horizon_id,
                days=left,
            )
    analysis_setting = DeadlineSetting.of(DeadlineKind.DISPUTE_ANALYSIS)
    for dispute in Dispute.objects.filter(
        status__in=[DisputeStatus.OPEN, DisputeStatus.IN_ANALYSIS]
    ).select_related("report__asset"):
        left = days_left(today, dispute.analysis_due)
        if left in analysis_setting.reminder_days:
            counts["alerts"] += alert(
                f"dispute_due:{dispute.pk}:{left}",
                "dispute_due",
                ref=f"dispute:{dispute.pk}",
                role_key=INVENTORY_SUPERVISOR,
                asset=dispute.report.asset.horizon_id,
                days=left,
            )

    # Aging: assets longer than allowed in their status (since their last status change)
    limits = {a.status: a.days for a in AgingLimit.objects.exclude(days__isnull=True)}
    if limits:
        last_change = (
            MovementEvent.objects.filter(asset=OuterRef("pk"))
            .exclude(status_after="")
            .exclude(status_before=F("status_after"))
            .order_by("-at")
            .values("at")[:1]
        )
        for asset in Asset.objects.filter(status__in=list(limits)).annotate(
            since=Subquery(last_change)
        ):
            if asset.since is None:
                continue
            days = (today - timezone.localdate(asset.since)).days
            if days > limits[asset.status]:
                counts["alerts"] += alert(
                    f"aging:{asset.pk}:{asset.status}:{timezone.localdate(asset.since)}",
                    "aging",
                    ref=f"asset:{asset.pk}",
                    role_key=INVENTORY_SUPERVISOR,
                    asset=asset.horizon_id,
                    status=asset.status,
                    days=days,
                )
    return counts
