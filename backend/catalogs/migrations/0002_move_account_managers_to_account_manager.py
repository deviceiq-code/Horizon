# The account manager ↔ vertical relation now belongs to the account manager
# (AccountManager.verticals). Only Django's model state changes here: the link table and its
# rows are kept and renamed by account_managers/0002, so no data is lost.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="vertical", name="account_managers"),
            ],
            database_operations=[],
        ),
    ]
