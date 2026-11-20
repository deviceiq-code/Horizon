from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def fill_unit_values(apps, schema_editor):
    """Items saved before the value was typed take the current average price's value."""
    Item = apps.get_model("efmv", "EfmvScenarioItem")
    AveragePrice = apps.get_model("pricing", "AveragePrice")
    for item in Item.objects.filter(unit_value__isnull=True):
        row = (
            AveragePrice.objects.filter(lineage=item.price_lineage, deleted_at__isnull=True)
            .order_by("-created_at", "-id")
            .first()
        ) or AveragePrice.objects.filter(lineage=item.price_lineage).order_by("-created_at").first()
        item.unit_value = row.original_value if row else Decimal("0.01")
        item.save(update_fields=["unit_value"])


class Migration(migrations.Migration):
    dependencies = [
        ("efmv", "0001_initial"),
        ("pricing", "0005_photo_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="efmvscenarioitem",
            name="unit_value",
            field=models.DecimalField(
                decimal_places=2, max_digits=14, null=True, verbose_name="unit value"
            ),
        ),
        migrations.RunPython(fill_unit_values, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="efmvscenarioitem",
            name="unit_value",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=14,
                validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                verbose_name="unit value",
            ),
        ),
    ]
