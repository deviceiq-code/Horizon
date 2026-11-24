from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("efmv", "0014_services_to_items"),
    ]

    operations = [
        migrations.RemoveField(
            model_name='efmvscenarioitem',
            name='service_mode',
        ),
        migrations.RemoveField(
            model_name='efmvscenarioitem',
            name='service_name',
        ),
        migrations.RemoveField(
            model_name='efmvscenarioitem',
            name='service_value',
        ),
        migrations.AddConstraint(
            model_name='efmvscenarioitem',
            constraint=models.UniqueConstraint(condition=models.Q(('attached_to__isnull', False)), fields=('attached_to', 'kind'), name='efmv_item_one_attachment_per_kind'),
        ),
        migrations.AddConstraint(
            model_name='efmvscenarioitem',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('kind', 'hw'), ('price_lineage__isnull', False)), models.Q(models.Q(('kind', 'hw'), _negated=True), ('price_lineage__isnull', True)), _connector='OR'), name='efmv_item_price_only_for_hardware'),
        ),
    ]
