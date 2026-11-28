"""Registers created before their creator and last editor were recorded: both become
Fernando's user (fernando.almeida), so every register has them. Dates missing too: a dictionary
word's creation is its last change; a user's last change is its date_joined. Nothing happens
when that user does not exist (e.g. the test database)."""

from django.conf import settings
from django.db import migrations
from django.db.models import F

USERNAME = "fernando.almeida"

AUDITED = [
    ("entities", "BusinessEntity"),
    ("catalogs", "Vertical"),
    ("catalogs", "Manufacturer"),
    ("catalogs", "AssetClass"),
    ("catalogs", "AssetModel"),
    ("inventory", "Warehouse"),
    ("inventory", "PenaltyRate"),
    ("inventory", "ErasureTool"),
    ("users", "Role"),
    ("system", "DictionaryWord"),
    ("users", "UserProfile"),
]


def forwards(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    owner = User.objects.filter(username=USERNAME).first()
    if owner is None:
        return
    for app, name in AUDITED:
        model = apps.get_model(app, name)
        model.objects.filter(created_by__isnull=True).update(created_by=owner)
        model.objects.filter(updated_by__isnull=True).update(updated_by=owner)
    Word = apps.get_model("system", "DictionaryWord")
    Word.objects.filter(created_at__isnull=True).update(created_at=F("updated_at"))
    Profile = apps.get_model("users", "UserProfile")
    for profile in Profile.objects.filter(updated_at__isnull=True).select_related("user"):
        Profile.objects.filter(pk=profile.pk).update(updated_at=profile.user.date_joined)


class Migration(migrations.Migration):
    dependencies = [
        ("system", "0009_dictionaryword_created_at_dictionaryword_created_by_and_more"),
        ("entities", "0004_businessentity_created_by_businessentity_updated_by"),
        ("catalogs", "0012_assetclass_created_by_assetclass_updated_by_and_more"),
        ("inventory", "0014_erasuretool_created_by_erasuretool_updated_by_and_more"),
        ("users", "0011_userprofile_created_by_userprofile_updated_at_and_more"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
