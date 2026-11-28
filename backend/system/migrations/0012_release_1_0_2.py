"""Version 1.0.2 (system/releases.py: each commit on main adds its own release this way)."""

import datetime

from django.db import migrations

VERSION = "1.0.2"
RELEASED_ON = datetime.date(2026, 11, 28)
NOTES = {
    "en": [
        "Average prices show who created them (their first version) and who changed them last "
        "— a new version, or their photo or documents —, and when.",
        "eFMV analyses show when they were created and last changed, and by whom, on a line of "
        "their own in the header; the printed report shows who changed it last too.",
        "Grids with more than three actions per row keep them all in a \"…\" menu.",
        "A double click on a row opens it: an average price's details, or an eFMV analysis.",
        "Settings › Appearance › Home: show or hide the Data Journal and the System Journal, "
        "and place them one under the other or side by side.",
    ],
    "pt-br": [
        "Os preços médios mostram quem os criou (a primeira versão) e quem os alterou por "
        "último — uma nova versão, ou a foto ou os documentos —, e quando.",
        "As análises eFMV mostram quando foram criadas e alteradas pela última vez, e por quem, "
        "numa linha própria do cabeçalho; o relatório impresso também mostra quem a alterou "
        "por último.",
        "Grids com mais de três ações por linha mantêm todas elas num menu \"…\".",
        "Um duplo clique numa linha a abre: os detalhes de um preço médio, ou uma análise eFMV.",
        "Configurações › Aparência › Home: mostrar ou ocultar o Journal de Dados e o Journal de "
        "Sistema, e colocá-los um embaixo do outro ou lado a lado.",
    ],
    "es": [
        "Los precios promedio muestran quién los creó (su primera versión) y quién los modificó "
        "por última vez — una nueva versión, o su foto o sus documentos —, y cuándo.",
        "Los análisis eFMV muestran cuándo se crearon y se modificaron por última vez, y por "
        "quién, en una línea propia del encabezado; el informe impreso también muestra quién lo "
        "modificó por última vez.",
        "Las grillas con más de tres acciones por fila las mantienen todas en un menú \"…\".",
        "Un doble clic en una fila la abre: los detalles de un precio promedio, o un análisis "
        "eFMV.",
        "Configuración › Apariencia › Home: mostrar u ocultar el Journal de Datos y el Journal "
        "del Sistema, y ubicarlos uno debajo del otro o lado a lado.",
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
    dependencies = [("system", "0011_release_1_0_1")]

    operations = [migrations.RunPython(forwards, backwards)]
