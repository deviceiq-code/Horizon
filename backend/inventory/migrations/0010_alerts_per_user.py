"""Alerts are always one user's: an event for a role becomes one alert per user with it, each
read on its own (read_at). No alert existed when this was written; any left without a user
(the former role alerts) are dropped — the daily routine creates them again per user."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def drop_role_alerts(apps, schema_editor):
    apps.get_model("inventory", "Alert").objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0009_inventory_counts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(drop_role_alerts, migrations.RunPython.noop),
        migrations.RemoveField(model_name="alert", name="read_by"),
        migrations.RemoveField(model_name="alert", name="role_key"),
        migrations.AddField(
            model_name="alert",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="read at"),
        ),
        migrations.AlterField(
            model_name="alert",
            name="key",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="alert",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="alerts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("user", "key"), name="inventory_alert_once_per_user"
            ),
        ),
    ]
