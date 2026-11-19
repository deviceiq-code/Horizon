from django.db import migrations, models


def split_names(apps, schema_editor):
    """The first word becomes the first name and the rest the last name
    ("Gabriela Nascimento" → "Gabriela" + "Nascimento")."""
    AccountManager = apps.get_model("account_managers", "AccountManager")
    for manager in AccountManager.objects.all():
        words = manager.full_name.split()
        manager.first_name = words[0] if words else ""
        manager.last_name = " ".join(words[1:])
        manager.save(update_fields=["first_name", "last_name"])


def join_names(apps, schema_editor):
    AccountManager = apps.get_model("account_managers", "AccountManager")
    for manager in AccountManager.objects.all():
        manager.full_name = " ".join(f"{manager.first_name} {manager.last_name}".split())
        manager.save(update_fields=["full_name"])


class Migration(migrations.Migration):
    dependencies = [("account_managers", "0003_photo")]

    operations = [
        migrations.AddField(
            model_name="accountmanager",
            name="first_name",
            field=models.CharField(default="", max_length=100, verbose_name="first name"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountmanager",
            name="last_name",
            field=models.CharField(blank=True, max_length=100, verbose_name="last name"),
        ),
        migrations.RunPython(split_names, join_names),
        migrations.AlterField(
            model_name="accountmanager",
            name="full_name",
            field=models.CharField(editable=False, max_length=201, verbose_name="full name"),
        ),
    ]
