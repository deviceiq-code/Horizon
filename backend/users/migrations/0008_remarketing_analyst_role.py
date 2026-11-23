from django.db import migrations


def create_role(apps, schema_editor):
    """The Remarketing Analyst system role (a role with the same name becomes the system one)."""
    Role = apps.get_model("users", "Role")
    name = "Remarketing Analyst"
    role = Role.objects.filter(name__iexact=name).first()
    if role is None:
        Role.objects.create(
            key="remarketing_analyst",
            name=name,
            description=(
                "Schedules receivings and shipments and prepares the expected lists agreed with "
                "customers."
            ),
            is_system=True,
        )
    else:
        role.key, role.is_system = "remarketing_analyst", True
        role.save(update_fields=["key", "is_system"])


class Migration(migrations.Migration):
    dependencies = [("users", "0007_inventory_roles")]

    operations = [migrations.RunPython(create_role, migrations.RunPython.noop)]
