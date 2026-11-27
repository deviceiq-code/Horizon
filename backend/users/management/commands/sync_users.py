"""Copy Live's users (roles, profiles, preferences) to the other environments (users/sync.py).
It also happens by itself whenever users change and on signing in to another environment;
run it after refreshing a database (e.g. Development copied from Live, README)."""

from django.core.management.base import BaseCommand

from users.sync import sync_users


class Command(BaseCommand):
    help = "Copy Live's users to the other environments (Development…)."

    def handle(self, *args, **options):
        targets = sync_users()
        if targets:
            self.stdout.write(self.style.SUCCESS(f"Users copied to: {', '.join(targets)}"))
        else:
            self.stdout.write("No other environment with a database of its own.")
