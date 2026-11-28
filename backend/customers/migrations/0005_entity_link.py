from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0004_keywords'),
        ('entities', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='entity',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s', to='entities.businessentity', verbose_name='business entity'),
        ),
    ]
