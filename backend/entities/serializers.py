"""Business entities and their roles, written together: the entity's fields plus one key per
role — an object turns it on (or changes it), null removes it, absent leaves it as it is.
A role other records point to cannot be removed (409: deactivate it instead)."""

from django.db import transaction
from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from config.audit import AuditedSerializerMixin
from config.keywords import KeywordsField
from config.parties import CompanyFieldsMixin
from customers.models import ContractType, Customer
from service_providers.models import ServiceKind, ServiceProvider
from users.display import full_name_in, person_ref
from users.models import is_account_manager

from . import hierarchy
from .models import BusinessEntity, Buyer, EntityRole, Supplier, SupplyKind


class RoleInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "role_in_use"


ROLE_IN_USE = {
    EntityRole.CUSTOMER: _(
        "This entity is the customer of analyses, appointments or disposals: the Customer role "
        "cannot be removed. Deactivate it instead."
    ),
    EntityRole.SUPPLIER: _("Records point to this supplier: the role cannot be removed."),
    EntityRole.SERVICE_PROVIDER: _(
        "This entity runs warehouses or was used in transfers or disposals: the Service Provider "
        "role cannot be removed. Deactivate it instead."
    ),
    EntityRole.BUYER: _(
        "This entity bought assets in disposals: the Buyer role cannot be removed. "
        "Deactivate it instead."
    ),
}


# --- Roles -------------------------------------------------------------------------------------


class CustomerRoleSerializer(serializers.ModelSerializer):
    # Write: primary_account_manager (id, required), secondary_account_managers (ids) and
    # contract_types (ContractType values; optional — a prospect has none).
    contract_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ContractType.choices),
        allow_empty=True,
        required=False,
    )
    primary_account_manager_name = serializers.SerializerMethodField()
    secondary_account_managers_detail = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "is_active",
            "contract_types",
            "primary_account_manager",
            "primary_account_manager_name",
            "secondary_account_managers",
            "secondary_account_managers_detail",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {"secondary_account_managers": {"required": False}}

    def get_primary_account_manager_name(self, obj) -> str:
        return full_name_in(self.context, obj.primary_account_manager)

    def get_secondary_account_managers_detail(self, obj) -> list[dict]:
        refs = [person_ref(self.context, m) for m in obj.secondary_account_managers.all()]
        return sorted(refs, key=lambda ref: ref["full_name"].lower())

    def validate_contract_types(self, value):
        """No repeats; kept in the order of the choices."""
        chosen = set(value)
        return [kind for kind in ContractType.values if kind in chosen]

    def validate_primary_account_manager(self, value):
        if not is_account_manager(value):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    def validate_secondary_account_managers(self, value):
        if any(not is_account_manager(user) for user in value):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    def validate(self, attrs):
        primary = attrs.get("primary_account_manager")
        if primary is not None and primary in attrs.get("secondary_account_managers", []):
            raise serializers.ValidationError(
                {
                    "secondary_account_managers": _(
                        "The primary account manager cannot also be a secondary one."
                    )
                }
            )
        return attrs


class ServiceProviderRoleSerializer(serializers.ModelSerializer):
    services = serializers.ListField(
        child=serializers.ChoiceField(choices=ServiceKind.choices), allow_empty=True
    )
    # Warehouses it runs (read-only; Asset Management › Inventory)
    warehouses_count = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProvider
        fields = ["id", "is_active", "services", "warehouses_count"]
        read_only_fields = ["id"]

    def get_warehouses_count(self, obj) -> int:
        return obj.warehouses.count()

    def validate_services(self, value):
        """At least one; no repeats; kept in the order of the choices."""
        chosen = set(value)
        if not chosen:
            raise serializers.ValidationError(_("Choose at least one service."))
        return [kind for kind in ServiceKind.values if kind in chosen]


class SupplierRoleSerializer(serializers.ModelSerializer):
    supplies = serializers.ListField(
        child=serializers.ChoiceField(choices=SupplyKind.choices), allow_empty=True
    )

    class Meta:
        model = Supplier
        fields = ["id", "is_active", "supplies"]
        read_only_fields = ["id"]

    def validate_supplies(self, value):
        """Products and/or services: at least one, in the choices' order."""
        chosen = set(value)
        if not chosen:
            raise serializers.ValidationError(_("Choose products, services or both."))
        return [kind for kind in SupplyKind.values if kind in chosen]


class BuyerRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Buyer
        fields = ["id", "is_active"]
        read_only_fields = ["id"]


ROLE_SERIALIZERS = {
    EntityRole.CUSTOMER: CustomerRoleSerializer,
    EntityRole.SUPPLIER: SupplierRoleSerializer,
    EntityRole.SERVICE_PROVIDER: ServiceProviderRoleSerializer,
    EntityRole.BUYER: BuyerRoleSerializer,
}


def entity_ref(entity: BusinessEntity | None) -> dict | None:
    if entity is None:
        return None
    return {
        "id": entity.pk,
        "name": entity.name,
        "trade_name": entity.trade_name,
        "tax_id": entity.tax_id,
        "country": entity.country,
    }


# --- The entity -------------------------------------------------------------------------------


class BusinessEntitySerializer(
    AuditedSerializerMixin, CompanyFieldsMixin, serializers.ModelSerializer
):
    keywords = KeywordsField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=BusinessEntity.objects.all(), allow_null=True, required=False
    )
    parent_detail = serializers.SerializerMethodField()
    # The entity at the top of its group (itself when it has no head office)
    group_detail = serializers.SerializerMethodField()
    branches_count = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    customer = CustomerRoleSerializer(allow_null=True, required=False)
    supplier = SupplierRoleSerializer(allow_null=True, required=False)
    service_provider = ServiceProviderRoleSerializer(allow_null=True, required=False)
    buyer = BuyerRoleSerializer(allow_null=True, required=False)

    class Meta:
        model = BusinessEntity
        fields = [
            "id",
            "name",
            "trade_name",
            "tax_id",
            "country",
            "parent",
            "parent_detail",
            "group_detail",
            "branches_count",
            "contact_name",
            "email",
            "phone",
            "postal_code",
            "street",
            "number",
            "complement",
            "district",
            "city",
            "state",
            "is_active",
            "notes",
            "keywords",
            "roles",
            *EntityRole.values,
            "created_at",
            "updated_at",
            "created_by_name",
            "updated_by_name",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # Uniqueness of (country, tax_id) is checked in validate() with a friendlier message
        validators = []

    # --- Reading ---------------------------------------------------------------------------

    def _parents(self) -> dict[int, int | None]:
        """Every entity's head office, read once per response."""
        cache = self.context.setdefault("_entity_parents", {})
        if not cache:
            cache.update(BusinessEntity.objects.values_list("id", "parent_id"))
        return cache

    def get_parent_detail(self, obj) -> dict | None:
        return entity_ref(obj.parent)

    def get_group_detail(self, obj) -> dict | None:
        if obj.parent_id is None and not self.get_branches_count(obj):
            return None  # on its own: no group
        parents = self._parents()
        root_id = hierarchy.group_root(obj.pk, parents.get)
        if root_id == obj.pk:
            return entity_ref(obj)
        return entity_ref(BusinessEntity.objects.filter(pk=root_id).first())

    def get_branches_count(self, obj) -> int:
        count = getattr(obj, "branches_total", None)
        return count if count is not None else obj.branches.count()

    def get_roles(self, obj) -> list[str]:
        return obj.roles()

    # --- Rules -----------------------------------------------------------------------------

    def validate(self, attrs):
        errors = self.address_errors(attrs)
        errors.update(
            self.tax_id_errors(attrs, _("A business entity with this tax ID already exists."))
        )
        # The head office: never itself nor one of its branches (at any depth)
        if "parent" in attrs and attrs["parent"] is not None and self.instance is not None:
            parents = dict(BusinessEntity.objects.values_list("id", "parent_id"))
            if hierarchy.creates_cycle(self.instance.pk, attrs["parent"].pk, parents.get):
                errors["parent"] = _(
                    "An entity cannot have itself or one of its branches as its head office."
                )
        errors.update(self._role_errors(attrs))
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _role_errors(self, attrs) -> dict:
        errors = {}
        existing = {
            role: (self.instance.role(role) if self.instance is not None else None)
            for role in EntityRole.values
        }
        customer = attrs.get(EntityRole.CUSTOMER)
        if customer and existing[EntityRole.CUSTOMER] is None:
            if not customer.get("primary_account_manager"):
                errors[EntityRole.CUSTOMER] = {
                    "primary_account_manager": [_("This field is required.")]
                }
        provider = attrs.get(EntityRole.SERVICE_PROVIDER)
        current = existing[EntityRole.SERVICE_PROVIDER]
        if provider and "services" in provider and current is not None:
            if ServiceKind.WAREHOUSING not in provider["services"] and current.warehouses.exists():
                errors[EntityRole.SERVICE_PROVIDER] = {
                    "services": [
                        _(
                            "This provider runs warehouses: warehousing cannot be removed from "
                            "its services."
                        )
                    ]
                }
        if provider is not None and current is None and "services" not in provider:
            errors[EntityRole.SERVICE_PROVIDER] = {"services": [_("Choose at least one service.")]}
        supplier = attrs.get(EntityRole.SUPPLIER)
        if supplier is not None and existing[EntityRole.SUPPLIER] is None:
            if "supplies" not in supplier:
                errors[EntityRole.SUPPLIER] = {
                    "supplies": [_("Choose products, services or both.")]
                }
        return errors

    # --- Writing ---------------------------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        roles = {
            role: validated_data.pop(role) for role in EntityRole.values if role in validated_data
        }
        entity = super().create(validated_data)
        self._save_roles(entity, roles)
        return entity

    @transaction.atomic
    def update(self, instance, validated_data):
        roles = {
            role: validated_data.pop(role) for role in EntityRole.values if role in validated_data
        }
        entity = super().update(instance, validated_data)
        self._save_roles(entity, roles)
        return entity

    def _save_roles(self, entity: BusinessEntity, roles: dict):
        for role, data in roles.items():
            current = entity.role(role)
            if data is None:
                if current is not None:
                    try:
                        with transaction.atomic():
                            current.delete()
                    except ProtectedError as error:
                        raise RoleInUse(ROLE_IN_USE[role]) from error
                    # The entity forgets the deleted role (reverse one-to-one cache)
                    entity._state.fields_cache.pop(role, None)
                continue
            data = dict(data)
            secondaries = data.pop("secondary_account_managers", None)
            if current is None:
                model = ROLE_SERIALIZERS[role].Meta.model
                current = model.objects.create(entity=entity, **data)
            else:
                for field, value in data.items():
                    setattr(current, field, value)
                current.save()
            if secondaries is not None:
                current.secondary_account_managers.set(secondaries)
            setattr(entity, role, current)
