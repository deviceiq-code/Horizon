"""Version 1.0.0 (system/releases.py: each delivery adds its own release this way)."""

import datetime

from django.db import migrations

VERSION = "1.0.0"
RELEASED_ON = datetime.date(2026, 11, 28)
NOTES = {'en': ['Business Entities: customers, suppliers, service providers and buyers are now one '
            'register (Administration › Catalogs) — one entity may have several roles, each with '
            'its own tab.',
            'Head offices and groups: an entity may point to its head office; a CNPJ suggests the '
            'one with the same root.',
            'Customers have contract types: renter, lessee, bailee (free loan) and service '
            'customer.',
            'Third-party sales of the inventory go to a buyer; brands may be linked to the '
            'business entity behind them.',
            "Asset Management is the inventory's app (formerly Remarketing); Remarketing is a new "
            'app for the sale of used assets (coming soon).',
            'The Home has a journal: what changed in the last days and what is new in each '
            'version. Its period is in Settings › Appearance.', 'Every register keeps who created it and who changed it last, and when — shown at the bottom of its form.'],
     'pt-br': ['Entidades: clientes, fornecedores, service providers e compradores agora são um '
               'único cadastro (Administração › Cadastros) — uma entidade pode ter vários papéis, '
               'cada um com a sua aba.',
               'Matrizes e grupos: uma entidade pode apontar para a sua matriz; um CNPJ sugere a '
               'de mesma raiz.',
               'Clientes têm modalidades: locatário, arrendatário, comodatário e tomador de '
               'serviços.',
               'As vendas a terceiros do estoque vão para um comprador; as marcas podem ser '
               'ligadas à entidade por trás delas.',
               'Asset Management é o app do estoque (antes Remarketing); Remarketing é um novo app '
               'para a venda de ativos usados (em breve).',
               'A Home tem um journal: o que mudou nos últimos dias e as novidades de cada versão. '
               'O período fica em Configurações › Aparência.', 'Todo cadastro guarda quem o criou e quem o alterou por último, e quando — mostrado no rodapé do seu formulário.'],
     'es': ['Entidades: clientes, proveedores, service providers y compradores ahora son un único '
            'registro (Administración › Catálogos) — una entidad puede tener varios roles, cada '
            'uno con su pestaña.',
            'Casas matrices y grupos: una entidad puede indicar su casa matriz; un CNPJ sugiere la '
            'de misma raíz.',
            'Los clientes tienen modalidades: locatario, arrendatario, comodatario y cliente de '
            'servicios.',
            'Las ventas a terceros del inventario van a un comprador; las marcas pueden vincularse '
            'a la entidad que las respalda.',
            'Asset Management es la app del inventario (antes Remarketing); Remarketing es una '
            'nueva app para la venta de activos usados (próximamente).',
            'La Home tiene un journal: lo que cambió en los últimos días y las novedades de cada '
            'versión. Su período está en Configuración › Apariencia.', 'Todo registro guarda quién lo creó y quién lo modificó por última vez, y cuándo — se muestra al pie de su formulario.']}


def forwards(apps, schema_editor):
    Release = apps.get_model("system", "Release")
    Release.objects.update_or_create(
        version=VERSION, defaults={"released_on": RELEASED_ON, "notes": NOTES}
    )


def backwards(apps, schema_editor):
    apps.get_model("system", "Release").objects.filter(version=VERSION).delete()


class Migration(migrations.Migration):
    dependencies = [("system", "0007_release")]

    operations = [migrations.RunPython(forwards, backwards)]
