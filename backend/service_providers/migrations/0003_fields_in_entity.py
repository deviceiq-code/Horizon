from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('service_providers', '0002_entity_link'),
        ('entities', '0002_from_customers_and_providers'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='serviceprovider',
            options={'ordering': ['entity__name'], 'verbose_name': 'service provider', 'verbose_name_plural': 'service providers'},
        ),
        migrations.RemoveConstraint(
            model_name='serviceprovider',
            name='service_provider_unique_tax_id',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='city',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='complement',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='country',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='district',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='email',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='keywords',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='name',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='notes',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='number',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='phone',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='postal_code',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='state',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='street',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='tax_id',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='trade_name',
        ),
        migrations.RemoveField(
            model_name='serviceprovider',
            name='contact_name',
        ),
        migrations.AlterField(
            model_name='serviceprovider',
            name='entity',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='service_provider', to='entities.businessentity', verbose_name='business entity'),
        ),
    ]
