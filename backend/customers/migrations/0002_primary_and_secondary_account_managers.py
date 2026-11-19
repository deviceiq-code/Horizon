# The customer's single, optional account manager becomes the required primary account manager
# (renamed, so existing links are kept) and secondary account managers are added.

import django.db.models.deletion
from django.db import migrations, models


def require_account_manager(apps, schema_editor):
    """The primary becomes mandatory: stop with a clear message if any customer has none."""
    Customer = apps.get_model("customers", "Customer")
    missing = list(
        Customer.objects.filter(primary_account_manager__isnull=True).values_list("id", "name")[:20]
    )
    if missing:
        listed = ", ".join(f"#{pk} {name}" for pk, name in missing)
        raise RuntimeError(
            "These customers have no account manager; set one (e.g. in the Django admin) "
            f"before running this migration: {listed}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("account_managers", "0002_accountmanager_verticals"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="customer",
            old_name="account_manager",
            new_name="primary_account_manager",
        ),
        migrations.RunPython(require_account_manager, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customer",
            name="primary_account_manager",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_customers",
                to="account_managers.accountmanager",
                verbose_name="primary account manager",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="secondary_account_managers",
            field=models.ManyToManyField(
                blank=True,
                related_name="secondary_customers",
                to="account_managers.accountmanager",
                verbose_name="secondary account managers",
            ),
        ),
    ]
