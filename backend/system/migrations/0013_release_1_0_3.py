"""Version 1.0.3 (system/releases.py: each commit on main adds its own release this way)."""

import datetime

from django.db import migrations

VERSION = "1.0.3"
RELEASED_ON = datetime.date(2026, 11, 28)
NOTES = {
    "en": [
        "The Home's journals keep to a comfortable reading length: \"Read More\" unfolds them, "
        "and the System Journal then shows every version.",
        "The path at the top of the page now starts at Home.",
    ],
    "pt-br": [
        "Os journals da Home ficam num tamanho confortável de leitura: \"Ler Mais\" os "
        "desdobra, e o Journal de Sistema então mostra todas as versões.",
        "O caminho no topo da página agora começa em Home.",
    ],
    "es": [
        "Los journals de la Home se mantienen en un largo cómodo de lectura: \"Leer Más\" los "
        "despliega, y el Journal del Sistema entonces muestra todas las versiones.",
        "La ruta en la parte superior de la página ahora empieza en Home.",
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
    dependencies = [("system", "0012_release_1_0_2")]

    operations = [migrations.RunPython(forwards, backwards)]
