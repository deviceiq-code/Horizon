"""The inventory's daily routine — run it once a day (cron), e.g.:

    0 6 * * *  cd /path/to/horizon/backend && uv run python manage.py check_deadlines

Expires access blocks past their deadline (RN-20), makes findings chargeable when nobody
disputed them in time (RN-22), escalates disputes past their analysis deadline and creates the
alerts (deadlines near, aging per status). Running it twice changes nothing more.
"""

from django.core.management.base import BaseCommand

from inventory.followups import check_deadlines


class Command(BaseCommand):
    help = "Inventory daily routine: deadlines of blocks and disputes, alerts."

    def handle(self, *args, **options):
        counts = check_deadlines()
        self.stdout.write(
            "expired blocks: {expired_blocks} · findings now chargeable: {chargeable} · "
            "escalated disputes: {escalated} · new alerts: {alerts}".format(**counts)
        )
