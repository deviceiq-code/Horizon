from django.db import migrations

ROLES = {
    "receiver": (
        "Receiver",
        "Opens receiving lots, triages assets, prints labels, records occurrences and moves "
        "assets.",
    ),
    "inspection_technician": (
        "Inspection Technician",
        "Inspects assets: photos, findings, data erasure certificates, checks block releases.",
    ),
    "storekeeper": (
        "Storekeeper",
        "Moves, puts away, picks and ships assets, counts inventory and receives transfers.",
    ),
    "inventory_supervisor": (
        "Inventory Supervisor",
        "Approves inspection reports, findings, transfers and adjustments; accepts occurrences.",
    ),
    "commercial_finance": (
        "Commercial and Finance",
        "Reads inspection reports, notifies customers, records disputes and creates disposals.",
    ),
}


def create_roles(apps, schema_editor):
    """The inventory's system roles (a role with the same name becomes the system one)."""
    Role = apps.get_model("users", "Role")
    for key, (name, description) in ROLES.items():
        role = Role.objects.filter(name__iexact=name).first()
        if role is None:
            Role.objects.create(key=key, name=name, description=description, is_system=True)
        else:
            role.key, role.is_system = key, True
            role.save(update_fields=["key", "is_system"])


class Migration(migrations.Migration):
    dependencies = [("users", "0006_keywords")]

    operations = [migrations.RunPython(create_roles, migrations.RunPython.noop)]
