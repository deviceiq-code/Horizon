"""Customers and service providers become business entities with their roles: one entity per
country + tax ID (a customer and a provider with the same one become a single entity). When
their values differ, the customer's are kept and the differences are printed for review."""

from django.db import migrations

COMMON = [
    "name", "trade_name", "tax_id", "country", "email", "phone", "postal_code", "street",
    "number", "complement", "district", "city", "state", "notes",
]  # fmt: skip


def forwards(apps, schema_editor):
    Entity = apps.get_model("entities", "BusinessEntity")
    Customer = apps.get_model("customers", "Customer")
    Provider = apps.get_model("service_providers", "ServiceProvider")
    by_tax_id = {}

    def entity_for(record, contact_name=""):
        key = (record.country, record.tax_id)
        entity = by_tax_id.get(key)
        if entity is None:
            entity = Entity.objects.create(
                **{field: getattr(record, field) for field in COMMON},
                contact_name=contact_name,
                keywords=list(record.keywords),
                is_active=record.is_active,
            )
            by_tax_id[key] = entity
            return entity
        # Already an entity (a customer): what differs is reported, the customer's kept
        differences = [
            f"{field}: {getattr(entity, field)!r} ≠ {getattr(record, field)!r}"
            for field in COMMON
            if getattr(entity, field) != getattr(record, field)
        ]
        if differences:
            print(f"\n  Business entity {entity.pk} ({entity.name}) — kept the customer's values:")
            for line in differences:
                print(f"    {line}")
        entity.keywords = list(dict.fromkeys([*entity.keywords, *record.keywords]))[:30]
        entity.contact_name = entity.contact_name or contact_name
        entity.is_active = entity.is_active or record.is_active
        entity.save()
        return entity

    for customer in Customer.objects.order_by("pk"):
        customer.entity = entity_for(customer)
        customer.save(update_fields=["entity"])
    for provider in Provider.objects.order_by("pk"):
        provider.entity = entity_for(provider, provider.contact_name)
        provider.save(update_fields=["entity"])


class Migration(migrations.Migration):
    dependencies = [
        ("entities", "0001_initial"),
        ("customers", "0005_entity_link"),
        ("service_providers", "0002_entity_link"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
