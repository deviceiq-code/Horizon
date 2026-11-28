from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_entity_link'),
        ('entities', '0002_from_customers_and_providers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customer',
            options={'ordering': ['entity__name'], 'verbose_name': 'customer', 'verbose_name_plural': 'customers'},
        ),
        migrations.RemoveConstraint(
            model_name='customer',
            name='customer_unique_tax_id',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='city',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='complement',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='country',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='district',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='email',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='keywords',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='name',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='notes',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='number',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='phone',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='postal_code',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='state',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='street',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='tax_id',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='trade_name',
        ),
        migrations.AlterField(
            model_name='customer',
            name='entity',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s', to='entities.businessentity', verbose_name='business entity'),
        ),
    ]
