"""Version 1.0.1 (system/releases.py: each commit on main adds its own release this way)."""

import datetime

from django.db import migrations

VERSION = "1.0.1"
RELEASED_ON = datetime.date(2026, 11, 28)
NOTES = {
    "en": [
        "How new versions are published was organized: each one now comes with its notes, in "
        "every language. No visible changes.",
    ],
    "pt-br": [
        "A publicação de novas versões foi organizada: cada uma agora vem com as suas notas, em "
        "todos os idiomas. Sem mudanças visíveis.",
    ],
    "es": [
        "Se organizó la publicación de nuevas versiones: cada una ahora viene con sus notas, en "
        "todos los idiomas. Sin cambios visibles.",
    ],
}


def forwards(apps, schema_editor):
    Release = apps.get_model("system", "Release")
    Release.objects.update_or_create(
        version=VERSION, defaults={"released_on": RELEASED_ON, "notes": NOTES}
    )


def backwards(apps, schema_editor):
    apps.get_model("system", "Release").objects.filter(version=VERSION).delete()


class Migration(migrations.Migration):
    dependencies = [("system", "0010_audit_backfill")]

    operations = [migrations.RunPython(forwards, backwards)]
