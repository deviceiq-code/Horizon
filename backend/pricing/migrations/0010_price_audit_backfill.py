"""Average prices created before their last change was recorded: each version's last change is
its creation; versions without a creator (and so without a last editor) become Fernando's user
(fernando.almeida). Nothing about users happens when it does not exist (e.g. tests)."""

from django.conf import settings
from django.db import migrations
from django.db.models import F

USERNAME = "fernando.almeida"


def forwards(apps, schema_editor):
    Price = apps.get_model("pricing", "AveragePrice")
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    owner = apps.get_model(app_label, model_name).objects.filter(username=USERNAME).first()
    if owner is not None:
        Price.objects.filter(created_by__isnull=True).update(created_by=owner)
    Price.objects.filter(updated_at__isnull=True).update(updated_at=F("created_at"))
    Price.objects.filter(updated_by__isnull=True).update(updated_by=F("created_by"))


class Migration(migrations.Migration):
    dependencies = [("pricing", "0009_price_updated")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
