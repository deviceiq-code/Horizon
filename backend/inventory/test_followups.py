"""Phase 4: deadlines (pure), access blocks (RN-20), disputes (RN-14, RN-21, RN-22), charges,
the daily routine (idempotent) and alerts."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from . import followups, inspection
from .conftest import client_for, user_with_roles
from .deadlines import add_days, days_left, is_business_day
from .models import (
    Alert,
    Asset,
    BlockFollowUp,
    BlockStatus,
    DeadlineSetting,
    Dispute,
    FindingStatus,
    Holiday,
    InspectionReport,
    ReportStatus,
)
from .states import AssetStatus, DomainError
from .test_inspection import _complete, _post, _start

API = "/api/inventory"


# --- Deadlines (pure) --------------------------------------------------------------------------


def test_calendar_days():
    assert add_days(date(2026, 11, 20), 15, business=False) == date(2026, 12, 5)


def test_business_days_skip_weekends_and_holidays():
    friday = date(2026, 11, 20)
    assert add_days(friday, 1, business=True) == date(2026, 11, 23)  # Monday
    assert add_days(friday, 5, business=True) == date(2026, 11, 27)
    holidays = {date(2026, 11, 23)}
    assert add_days(friday, 1, business=True, holidays=holidays) == date(2026, 11, 24)
    assert not is_business_day(date(2026, 11, 21), set())
    assert days_left(date(2026, 11, 20), date(2026, 11, 23)) == 3


# --- Helpers -----------------------------------------------------------------------------------


def _approved(client, technician, supervisor, setup, places, block=False):
    """A report approved by the supervisor (with an access block when asked)."""
    report = _start(client, technician, setup, places)
    _complete(client, report["id"])
    if block:
        _post(
            client,
            f"{API}/inspections/{report['id']}/findings/",
            {"kind": "access_block", "block_type": "mdm", "description": "MDM"},
        )
    _post(
        client,
        f"{API}/inspections/{report['id']}/findings/",
        {"kind": "damage", "description": "Dent"},
    )
    _post(client, f"{API}/inspections/{report['id']}/submit/", {})
    client_for(client, supervisor)
    response = _post(client, f"{API}/inspections/{report['id']}/approve/", {})
    assert response.status_code == 200, response.json()
    return InspectionReport.objects.get(pk=report["id"])


@pytest.fixture
def rates(setup, notebook_class):
    from .models import PenaltyRate

    PenaltyRate.objects.create(
        asset_class=notebook_class,
        finding_kind="damage",
        value=Decimal("200"),
        valid_from=date(2026, 1, 1),
    )


# --- Access blocks (RN-20) -------------------------------------------------------------------


def test_block_released_goes_back_to_inspection(
    client, technician, supervisor, commercial, setup, places, rates
):
    report = _approved(client, technician, supervisor, setup, places, block=True)
    asset = Asset.objects.get(pk=setup["asset"].pk)
    assert asset.status == AssetStatus.BLOCKED
    followup = BlockFollowUp.objects.get()
    assert (followup.status, followup.due_date) == (BlockStatus.OPEN, None)

    client_for(client, commercial)
    data = _post(client, f"{API}/blocks/notify/", {"ids": [followup.id]}).json()
    assert data[0]["due_date"] == str(timezone.localdate() + timedelta(days=15))
    _post(client, f"{API}/blocks/{followup.id}/report-release/", {})
    # Checked by a technician: not released → open again
    client_for(client, technician)
    assert (
        _post(client, f"{API}/blocks/{followup.id}/check/", {"released": False}).json()["status"]
        == "open"
    )
    client_for(client, commercial)
    _post(client, f"{API}/blocks/{followup.id}/report-release/", {})
    client_for(client, technician)
    assert (
        _post(client, f"{API}/blocks/{followup.id}/check/", {"released": True}).json()["status"]
        == "released"
    )
    asset.refresh_from_db()
    assert asset.status == AssetStatus.IN_INSPECTION
    draft = asset.reports.get(status=ReportStatus.DRAFT)
    assert draft.version == report.version + 1
    assert draft.findings.get(kind="access_block").status == FindingStatus.CANCELLED


def test_block_expired_rn20_then_decided(
    client, technician, supervisor, commercial, setup, places, rates
):
    _approved(client, technician, supervisor, setup, places, block=True)
    followup = BlockFollowUp.objects.get()
    followups.mark_notified([followup], user=commercial)
    later = timezone.localdate() + timedelta(days=16)
    counts = followups.check_deadlines(today=later)
    assert counts["expired_blocks"] == 1
    followup.refresh_from_db()
    assert followup.status == BlockStatus.EXPIRED
    assert followup.finding.status == FindingStatus.CHARGEABLE
    assert Alert.objects.filter(kind="block_expired").count() == 1
    # Idempotent
    again = followups.check_deadlines(today=later)
    assert (again["expired_blocks"], again["alerts"]) == (0, 0)

    client_for(client, technician)
    assert (
        _post(client, f"{API}/blocks/{followup.id}/decide/", {"decision": "scrap"}).status_code
        == 403
    )
    client_for(client, supervisor)
    assert (
        _post(client, f"{API}/blocks/{followup.id}/decide/", {"decision": "other"}).status_code
        == 400
    )
    data = _post(
        client, f"{API}/blocks/{followup.id}/decide/", {"decision": "scrap", "notes": "No answer"}
    ).json()
    assert (data["status"], data["decision"]) == ("closed", "scrap")
    assert Asset.objects.get(pk=setup["asset"].pk).status == AssetStatus.SCRAP


def test_block_reminders(technician, supervisor, commercial, setup, places, rates, client):
    _approved(client, technician, supervisor, setup, places, block=True)
    followup = BlockFollowUp.objects.get()
    followups.mark_notified([followup], user=commercial)
    followup.refresh_from_db()
    followups.check_deadlines(today=followup.due_date - timedelta(days=3))
    alert = Alert.objects.get(kind="block_due")
    # The role's user gets it as their own
    assert (alert.user, alert.params["days"]) == (commercial, 3)


# --- Disputes (RN-14, RN-21, RN-22) ------------------------------------------------------------


def test_dispute_only_of_a_report_sent_and_in_time_rn21(
    client, technician, supervisor, commercial, setup, places, rates
):
    report = _approved(client, technician, supervisor, setup, places)
    finding = report.findings.get(kind="damage")
    client_for(client, commercial)
    payload = {"report": report.id, "findings": [finding.id], "justification": "The dent was there"}
    assert _post(client, f"{API}/disputes/", payload).json()["field"] == "report"  # not sent
    _post(client, f"{API}/inspections/{report.id}/sent/", {})
    report.refresh_from_db()
    assert report.dispute_deadline is not None
    InspectionReport.objects.filter(pk=report.id).update(
        dispute_deadline=timezone.localdate() - timedelta(days=1)
    )
    assert _post(client, f"{API}/disputes/", payload).json()["field"] == "report"  # too late


def test_dispute_partially_upheld_new_version_rn14(
    client, technician, supervisor, commercial, setup, places, rates
):
    from .models import PenaltyRate

    PenaltyRate.objects.filter(finding_kind="missing_item").update(value=Decimal("150"))
    report = _approved(client, technician, supervisor, setup, places)
    client_for(client, commercial)
    _post(client, f"{API}/inspections/{report.id}/sent/", {})
    # A second finding to dispute partly
    report.findings.create(
        kind="customization",
        description="Sticker",
        value=Decimal("50"),
        status=FindingStatus.APPROVED,
    )
    damage, sticker = report.findings.get(kind="damage"), report.findings.get(kind="customization")
    data = _post(
        client,
        f"{API}/disputes/",
        {
            "report": report.id,
            "findings": [damage.id, sticker.id],
            "justification": "Both existed before",
        },
    ).json()
    assert data["status"] == "open"
    asset = Asset.objects.get(pk=setup["asset"].pk)
    assert asset.held_for_dispute
    damage.refresh_from_db()
    assert damage.status == FindingStatus.DISPUTED
    # The report's technician cannot analyse it
    InspectionReport.objects.filter(pk=report.id).update(technician=supervisor)
    client_for(client, supervisor)
    assert _post(client, f"{API}/disputes/{data['id']}/analyze/", {}).json()["field"] == "analyst"
    InspectionReport.objects.filter(pk=report.id).update(technician=technician)
    assert (
        _post(client, f"{API}/disputes/{data['id']}/analyze/", {}).json()["status"] == "in_analysis"
    )
    decided = _post(
        client,
        f"{API}/disputes/{data['id']}/decide/",
        {
            "decision": "partially_upheld",
            "notes": "Sticker was ours",
            "upheld_findings": [sticker.id],
        },
    ).json()
    assert (decided["status"], decided["decision"]) == ("decided", "partially_upheld")
    new = InspectionReport.objects.get(pk=decided["new_report"])
    assert (new.is_current, new.status, new.version) == (
        True,
        ReportStatus.APPROVED,
        report.version + 1,
    )
    statuses = {f.kind: f.status for f in new.findings.all()}
    assert statuses["customization"] == FindingStatus.CANCELLED
    assert statuses["damage"] == FindingStatus.CHARGEABLE
    asset.refresh_from_db()
    assert not asset.held_for_dispute


def test_dispute_rejected_makes_findings_chargeable(
    supervisor, commercial, technician, setup, places, rates, client
):
    report = _approved(client, technician, supervisor, setup, places)
    inspection.mark_sent(report, user=commercial)
    damage = report.findings.get(kind="damage")
    dispute = followups.register_dispute(
        report, user=commercial, findings=[damage], justification="No"
    )
    with pytest.raises(DomainError):
        followups.decide_dispute(dispute, user=supervisor, decision="rejected", notes="")
    followups.decide_dispute(dispute, user=supervisor, decision="rejected", notes="Photos show it")
    damage.refresh_from_db()
    assert damage.status == FindingStatus.CHARGEABLE


def test_no_dispute_in_time_findings_chargeable_rn22(
    supervisor, commercial, technician, setup, places, rates, client
):
    report = _approved(client, technician, supervisor, setup, places)
    inspection.mark_sent(report, user=commercial)
    report.refresh_from_db()
    assert followups.check_deadlines(today=report.dispute_deadline)["chargeable"] == 0
    assert (
        followups.check_deadlines(today=report.dispute_deadline + timedelta(days=1))["chargeable"]
        == 1
    )
    assert report.findings.get(kind="damage").status == FindingStatus.CHARGEABLE


def test_disputes_past_analysis_are_escalated(
    supervisor, commercial, technician, setup, places, rates, client
):
    report = _approved(client, technician, supervisor, setup, places)
    inspection.mark_sent(report, user=commercial)
    dispute = followups.register_dispute(
        report, user=commercial, findings=[report.findings.get(kind="damage")], justification="No"
    )
    followups.check_deadlines(today=dispute.analysis_due + timedelta(days=1))
    dispute.refresh_from_db()
    assert dispute.status == "escalated"
    assert Alert.objects.filter(kind="dispute_escalated").count() == 1


def test_dispute_deadline_counts_business_days(
    supervisor, commercial, technician, setup, places, rates, client
):
    Holiday.objects.create(date=timezone.localdate() + timedelta(days=1), name="Test")
    setting = DeadlineSetting.of("dispute")
    report = _approved(client, technician, supervisor, setup, places)
    inspection.mark_sent(report, user=commercial)
    report.refresh_from_db()
    expected = add_days(
        timezone.localdate(),
        setting.days,
        business=True,
        holidays={timezone.localdate() + timedelta(days=1)},
    )
    assert report.dispute_deadline == expected


# --- Charges and alerts --------------------------------------------------------------------------


def test_charges(client, supervisor, commercial, technician, setup, places, rates):
    report = _approved(client, technician, supervisor, setup, places)
    report.findings.update(status=FindingStatus.CHARGEABLE)
    client_for(client, commercial)
    rows = client.get(f"{API}/charges/").json()["results"]
    assert [r["kind"] for r in rows] == ["damage"]
    assert rows[0]["asset_detail"]["horizon_id"] == setup["asset"].horizon_id
    response = _post(client, f"{API}/charges/{rows[0]['id']}/charged/", {})
    assert response.json()["status"] == "charged"
    assert client.get(f"{API}/charges/").json()["results"] == []


def test_alerts_are_each_users_own(client, supervisor, receiver, admin):
    other = user_with_roles("supervisor2", "inventory_supervisor")
    assert followups.alert(
        "x:1", "aging", role_key="inventory_supervisor", asset="H1", status="blocked", days=9
    )
    # Once per event and user: running again creates nothing
    assert not followups.alert(
        "x:1", "aging", role_key="inventory_supervisor", asset="H1", status="blocked", days=9
    )
    assert sorted(Alert.objects.values_list("user__username", flat=True)) == [
        "supervisor",
        "supervisor2",
    ]
    # Not the role's: nothing (administrators included — they are not everyone's inbox)
    for outsider in (receiver, admin):
        client_for(client, outsider)
        assert client.get(f"{API}/alerts/count/").json() == {"unread": 0}
    client_for(client, supervisor)
    assert client.get(f"{API}/alerts/count/").json() == {"unread": 1}
    alert = client.get(f"{API}/alerts/").json()["results"][0]
    assert (alert["kind"], alert["params"]["days"], alert["read"]) == ("aging", 9, False)
    _post(client, f"{API}/alerts/{alert['id']}/read/", {})
    assert client.get(f"{API}/alerts/count/").json() == {"unread": 0}
    assert client.get(f"{API}/alerts/").json()["results"][0]["read"] is True
    # Read by one, still unread for the other
    client_for(client, other)
    assert client.get(f"{API}/alerts/count/").json() == {"unread": 1}
    assert client.get(f"{API}/alerts/?unread=true").json()["count"] == 1
    _post(client, f"{API}/alerts/read-all/", {})
    assert client.get(f"{API}/alerts/count/").json() == {"unread": 0}
    # Someone else's alert cannot be read
    mine = Alert.objects.get(user=supervisor)
    assert client.post(f"{API}/alerts/{mine.pk}/read/", {}).status_code == 404


def test_an_event_for_a_role_nobody_has_goes_to_the_administrators(admin, receiver):
    followups.alert("y:1", "block_due", role_key="commercial_finance", asset="H2", days=3)
    assert list(Alert.objects.values_list("user__username", flat=True)) == ["admin"]


def test_an_alert_for_one_user(supervisor, receiver):
    followups.alert("z:1", "aging", user=receiver, asset="H3", status="blocked", days=2)
    assert list(Alert.objects.values_list("user", flat=True)) == [receiver.pk]


def test_run_now_is_for_supervisors(client, supervisor, receiver):
    client_for(client, receiver)
    assert _post(client, f"{API}/deadline-check/", {}).status_code == 403
    client_for(client, supervisor)
    assert _post(client, f"{API}/deadline-check/", {}).json()["alerts"] == 0


def test_deadline_settings(client, supervisor):
    client_for(client, supervisor)
    rows = client.get(f"{API}/deadline-settings/").json()
    assert {r["kind"]: (r["days"], r["business_days"]) for r in rows} == {
        "block_release": (15, False),
        "dispute": (10, True),
        "dispute_analysis": (5, True),
    }
    dispute = next(r for r in rows if r["kind"] == "dispute")
    data = client.patch(
        f"{API}/deadline-settings/{dispute['id']}/",
        {"days": 7, "reminder_days": [1, 3, 3]},
        content_type="application/json",
    ).json()
    assert (data["days"], data["reminder_days"]) == (7, [3, 1])
    assert Dispute.objects.count() == 0


def test_each_alert_has_a_severity_by_its_kind_or_given(supervisor):
    followups.alert("s:1", "block_expired", role_key="inventory_supervisor", asset="H1")
    followups.alert("s:2", "aging", role_key="inventory_supervisor", asset="H1")
    followups.alert("s:3", "count_closed", user=supervisor, severity="success", count="INV-1")
    followups.alert("s:4", "something_new", user=supervisor)
    assert dict(Alert.objects.values_list("key", "severity")) == {
        "s:1": "error",
        "s:2": "warning",
        "s:3": "success",
        "s:4": "info",
    }
    assert set(Alert.objects.values_list("scope", flat=True)) == {"user"}


def test_a_system_notification_reaches_every_active_user_once(client, supervisor, receiver):
    receiver_off = user_with_roles("gone", "receiver")
    receiver_off.is_active = False
    receiver_off.save()
    assert followups.notify_everyone("maintenance:1", "maintenance", severity="info", day="Sunday")
    assert not followups.notify_everyone("maintenance:1", "maintenance", severity="info")
    alerts = Alert.objects.filter(key="maintenance:1")
    assert sorted(a.user.username for a in alerts) == ["receiver", "supervisor"]
    assert {(a.scope, a.severity) for a in alerts} == {("system", "info")}
    # Each reads their own
    client_for(client, receiver)
    row = client.get(f"{API}/alerts/").json()["results"][0]
    assert (row["scope"], row["severity"], row["params"]) == ("system", "info", {"day": "Sunday"})
    _post(client, f"{API}/alerts/{row['id']}/read/", {})
    client_for(client, supervisor)
    assert client.get(f"{API}/alerts/count/").json() == {"unread": 1}
