"""Third-party sales had their buyer as a customer: it is now a buyer (the Buyer role of the
same entity, given to it when it did not have it), and the sale no longer has a customer."""

from django.db import migrations


def forwards(apps, schema_editor):
    Disposal = apps.get_model("inventory", "Disposal")
    Buyer = apps.get_model("entities", "Buyer")
    for disposal in Disposal.objects.filter(kind="third_party_sale", customer__isnull=False):
        entity_id = disposal.customer.entity_id
        buyer = Buyer.objects.filter(entity_id=entity_id).first()
        if buyer is None:
            buyer = Buyer.objects.create(entity_id=entity_id)
        disposal.buyer = buyer
        disposal.customer = None
        disposal.save(update_fields=["buyer", "customer"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0012_disposal_buyer"),
        ("customers", "0006_fields_in_entity"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
