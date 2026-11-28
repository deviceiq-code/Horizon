from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('service_providers', '0001_initial'),
        ('entities', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceprovider',
            name='entity',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='service_provider', to='entities.businessentity', verbose_name='business entity'),
        ),
    ]
