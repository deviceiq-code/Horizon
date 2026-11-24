from decimal import Decimal

from django.db import migrations


def services_to_items(apps, schema_editor):
    """Each service stored on a hardware line becomes a service line attached to it (same
    value and mode, the hardware's quantity, eFMV 0): the figures stay the same."""
    Item = apps.get_model("efmv", "EfmvScenarioItem")
    for item in Item.objects.exclude(service_name=""):
        Item.objects.create(
            scenario_id=item.scenario_id,
            kind="sv",
            description=item.service_name,
            attached_to=item,
            mode=item.service_mode,
            quantity=item.quantity,
            unit_value=item.service_value or Decimal("0"),
            efmv_value=Decimal("0"),
            position=item.position,
        )


def items_to_services(apps, schema_editor):
    Item = apps.get_model("efmv", "EfmvScenarioItem")
    for line in Item.objects.filter(kind="sv", attached_to__isnull=False):
        Item.objects.filter(pk=line.attached_to_id).update(
            service_name=line.description or "Service",
            service_value=line.unit_value,
            service_mode=line.mode,
        )
    Item.objects.exclude(kind="hw").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("efmv", "0013_item_kinds"),
    ]

    operations = [
        migrations.RunPython(services_to_items, items_to_services),
    ]
