# Asset classes now belong to a sub-vertical (instead of a vertical), get an icon and a
# remarketing rating made of four 0–5 star ratings (replacing the single 0–10 rating),
# keywords (to relate assets) and notes.
#
# Existing asset classes move to the General sub-vertical of their vertical. Their old 0–10
# rating cannot be converted into the four new ratings, so it is dropped and they stay
# "not rated" (null) until edited; the API requires the four ratings when saving.

import django.contrib.postgres.fields
import django.core.validators
import django.db.models.deletion
import django.db.models.functions.text
from decimal import Decimal

from django.db import migrations, models

import catalogs.models

RATINGS = ["liquidity", "value_retention", "technology_renewal", "usage_breadth"]
VERBOSE = {
    "liquidity": "liquidity",
    "value_retention": "value retention",
    "technology_renewal": "technology renewal",
    "usage_breadth": "usage breadth",
}


def move_to_general_sub_vertical(apps, schema_editor):
    AssetClass = apps.get_model("catalogs", "AssetClass")
    SubVertical = apps.get_model("catalogs", "SubVertical")
    general = {
        s.vertical_id: s.id for s in SubVertical.objects.filter(is_general=True)
    }
    for asset_class in AssetClass.objects.all():
        asset_class.sub_vertical_id = general[asset_class.vertical_id]
        asset_class.save(update_fields=["sub_vertical"])


def move_back_to_vertical(apps, schema_editor):
    AssetClass = apps.get_model("catalogs", "AssetClass")
    for asset_class in AssetClass.objects.select_related("sub_vertical"):
        asset_class.vertical_id = asset_class.sub_vertical.vertical_id
        asset_class.save(update_fields=["vertical"])


def star_field(name):
    return models.DecimalField(
        decimal_places=1,
        max_digits=2,
        null=True,
        validators=[
            django.core.validators.MinValueValidator(Decimal("0")),
            django.core.validators.MaxValueValidator(Decimal("5")),
            catalogs.models.validate_half_star,
        ],
        verbose_name=VERBOSE[name],
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0003_manufacturer_assetclass"),
    ]

    operations = [
        # 1. Link to the sub-vertical (nullable while the data is moved)
        migrations.AddField(
            model_name="assetclass",
            name="sub_vertical",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asset_classes",
                to="catalogs.subvertical",
                verbose_name="sub-vertical",
            ),
        ),
        migrations.RunPython(move_to_general_sub_vertical, move_back_to_vertical),
        migrations.AlterField(
            model_name="assetclass",
            name="sub_vertical",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="asset_classes",
                to="catalogs.subvertical",
                verbose_name="sub-vertical",
            ),
        ),
        # 2. Drop the vertical link and the single 0–10 rating
        migrations.RemoveConstraint(
            model_name="assetclass", name="asset_class_unique_name_per_vertical"
        ),
        migrations.RemoveConstraint(model_name="assetclass", name="asset_class_rating_range"),
        migrations.RemoveField(model_name="assetclass", name="vertical"),
        migrations.RemoveField(model_name="assetclass", name="rating"),
        # 3. Icon and the four remarketing ratings
        migrations.AddField(
            model_name="assetclass",
            name="icon",
            field=models.CharField(default="mdi-cube-outline", max_length=60, verbose_name="icon"),
        ),
        *[
            migrations.AddField(model_name="assetclass", name=name, field=star_field(name))
            for name in RATINGS
        ],
        # 4. Keywords (to relate assets) and notes
        migrations.AddField(
            model_name="assetclass",
            name="keywords",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=50),
                blank=True,
                default=list,
                size=None,
                verbose_name="keywords",
            ),
        ),
        migrations.AddField(
            model_name="assetclass",
            name="notes",
            field=models.TextField(blank=True, verbose_name="notes"),
        ),
        migrations.AddConstraint(
            model_name="assetclass",
            constraint=models.UniqueConstraint(
                models.F("sub_vertical"),
                django.db.models.functions.text.Lower("name"),
                name="asset_class_unique_name_per_sub_vertical",
            ),
        ),
        *[
            migrations.AddConstraint(
                model_name="assetclass",
                constraint=models.CheckConstraint(
                    condition=models.Q(**{f"{name}__isnull": True})
                    | models.Q(**{f"{name}__gte": Decimal("0"), f"{name}__lte": Decimal("5")}),
                    name=f"asset_class_{name}_range",
                ),
            )
            for name in RATINGS
        ],
    ]
