from django.db import migrations


class Migration(migrations.Migration):
    """Account managers are now users with the "Account Manager" role (users app)."""

    dependencies = [
        ("account_managers", "0004_first_last_name"),
        ("customers", "0003_account_managers_are_users"),
        ("users", "0005_account_managers_become_users"),
    ]

    operations = [migrations.DeleteModel(name="AccountManager")]
