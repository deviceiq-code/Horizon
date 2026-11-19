# AccountManager.verticals takes over the link table that used to be Vertical.account_managers.
# Both sides use the same columns (accountmanager_id, vertical_id), so renaming the table keeps
# every existing link.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account_managers", "0001_initial"),
        ("catalogs", "0002_move_account_managers_to_account_manager"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="accountmanager",
                    name="verticals",
                    field=models.ManyToManyField(
                        blank=True,
                        related_name="account_managers",
                        to="catalogs.vertical",
                        verbose_name="business verticals",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE catalogs_vertical_account_managers "
                        "RENAME TO account_managers_accountmanager_verticals"
                    ),
                    reverse_sql=(
                        "ALTER TABLE account_managers_accountmanager_verticals "
                        "RENAME TO catalogs_vertical_account_managers"
                    ),
                ),
            ],
        ),
    ]
