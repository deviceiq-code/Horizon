from django.db import migrations, models


def fill_plurals(apps, schema_editor):
    """Asset classes saved before: the English plural by the usual rules (correctable)."""
    from catalogs.names import english_plural

    AssetClass = apps.get_model("catalogs", "AssetClass")
    for asset_class in AssetClass.objects.all():
        asset_class.plural_name = english_plural(asset_class.name)
        asset_class.save(update_fields=["plural_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0006_asset_class_spec_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="assetclass",
            name="plural_name",
            field=models.CharField(default="", max_length=100, verbose_name="plural name"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="assetclass",
            name="translations",
            field=models.JSONField(blank=True, default=dict, verbose_name="translations"),
        ),
        migrations.RunPython(fill_plurals, migrations.RunPython.noop),
    ]
