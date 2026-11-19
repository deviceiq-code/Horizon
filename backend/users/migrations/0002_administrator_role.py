from django.db import migrations


def create_administrator(apps, schema_editor):
    """The system role that gives access to everything; given to the existing superusers and
    staff so nobody loses access."""
    Role = apps.get_model("users", "Role")
    User = apps.get_model("auth", "User")
    role, _created = Role.objects.get_or_create(
        key="administrator",
        defaults={
            "name": "Administrator",
            "description": "Full access to the system.",
            "is_system": True,
        },
    )
    role.users.add(*User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True))


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_administrator, migrations.RunPython.noop)]
