from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forward(apps, schema_editor):
    """Point every customer to the users that the account managers became (same email)."""
    Customer = apps.get_model("customers", "Customer")
    User = apps.get_model("auth", "User")

    def user_of(manager):
        return User.objects.get(email__iexact=manager.email)

    for customer in Customer.objects.all():
        customer.primary_user = user_of(customer.primary_account_manager)
        customer.save(update_fields=["primary_user"])
        customer.secondary_users.set(
            [user_of(m) for m in customer.secondary_account_managers.all()]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0002_primary_and_secondary_account_managers"),
        ("users", "0005_account_managers_become_users"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="primary_user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="secondary_users",
            field=models.ManyToManyField(blank=True, related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
        migrations.RemoveField(model_name="customer", name="primary_account_manager"),
        migrations.RemoveField(model_name="customer", name="secondary_account_managers"),
        migrations.RenameField(
            model_name="customer", old_name="primary_user", new_name="primary_account_manager"
        ),
        migrations.RenameField(
            model_name="customer",
            old_name="secondary_users",
            new_name="secondary_account_managers",
        ),
        migrations.AlterField(
            model_name="customer",
            name="primary_account_manager",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_customers",
                to=settings.AUTH_USER_MODEL,
                verbose_name="primary account manager",
            ),
        ),
        migrations.AlterField(
            model_name="customer",
            name="secondary_account_managers",
            field=models.ManyToManyField(
                blank=True,
                related_name="secondary_customers",
                to=settings.AUTH_USER_MODEL,
                verbose_name="secondary account managers",
            ),
        ),
    ]
