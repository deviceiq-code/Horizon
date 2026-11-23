"""Shared input rules of records that identify a company or a place: customers, service
providers (legal name, trade name, tax ID) and warehouses (address and contact only).

Serializers mix them in before `ModelSerializer`: the `validate_<field>` methods normalize each
field and `address_errors` / `tax_id_errors` apply the rules that depend on the country.
"""

import re

from django.db.models import CharField, F, Func, Q, Value
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from customers.tax_ids import brazilian_tax_id_kind, normalize_tax_id

BRAZILIAN_STATES = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}  # fmt: skip

_COUNTRY = re.compile(r"^[A-Z]{2}$")


def collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


class AddressFieldsMixin:
    """Country (ISO 3166-1), contact (email, phone) and address fields."""

    def current(self, attrs, field, default=""):
        """The value being written, or the saved one when the field is not sent."""
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, default) if self.instance else default

    def validate_country(self, value):
        value = (value or "").strip().upper()
        if not _COUNTRY.match(value):
            raise serializers.ValidationError(_("Enter a two-letter country code (ISO 3166-1)."))
        return value

    def validate_email(self, value):
        return (value or "").strip().lower()

    def validate_phone(self, value):
        return collapse_spaces(value)

    def validate_contact_name(self, value):
        return collapse_spaces(value)

    def validate_state(self, value):
        return collapse_spaces(value).upper()

    def validate_city(self, value):
        return collapse_spaces(value)

    def address_errors(self, attrs) -> dict:
        """In Brazil: CEP with 8 digits (stored without the hyphen) and a valid state.
        Elsewhere the postal code is free-form (uppercase). Normalizes `attrs` in place."""
        country = self.current(attrs, "country", "BR") or "BR"
        errors = {}
        if country == "BR":
            if attrs.get("postal_code"):
                digits = re.sub(r"\D", "", attrs["postal_code"])
                if len(digits) != 8:
                    errors["postal_code"] = _("Enter a valid CEP (8 digits).")
                else:
                    attrs["postal_code"] = digits
            state = self.current(attrs, "state")
            if ("state" in attrs or "country" in attrs) and state and state not in BRAZILIAN_STATES:
                errors["state"] = _("Enter a valid Brazilian state (e.g. SP).")
        elif "postal_code" in attrs:
            attrs["postal_code"] = attrs["postal_code"].strip().upper()
        return errors


class CompanyFieldsMixin(AddressFieldsMixin):
    """Legal name, trade name and tax ID (CPF/CNPJ in Brazil, unique per country)."""

    def validate_name(self, value):
        value = collapse_spaces(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate_trade_name(self, value):
        return collapse_spaces(value)

    def validate_tax_id(self, value):
        value = normalize_tax_id(value)
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def tax_id_errors(self, attrs, duplicate_message) -> dict:
        """A valid CPF or CNPJ in Brazil; no other record of the model with the same one."""
        country = self.current(attrs, "country", "BR") or "BR"
        tax_id = self.current(attrs, "tax_id")
        if country == "BR" and ("tax_id" in attrs or "country" in attrs):
            if brazilian_tax_id_kind(tax_id) is None:
                return {"tax_id": _("Enter a valid CPF or CNPJ.")}
        if tax_id:
            duplicates = self.Meta.model.objects.filter(country=country, tax_id=tax_id)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                return {"tax_id": duplicate_message}
        return {}


def column_filters(queryset, params, *, names=("name", "trade_name"), tax_id=True):
    """Column filters of the grids of customers, service providers and warehouses:
    ?name= (any of `names` or a keyword containing it), ?tax_id= (with or without
    punctuation), ?location= (city or state) and ?is_active=true|false."""
    name = " ".join(params.get("name", "").split()).lower()
    if name:
        queryset = queryset.annotate(
            keywords_text=Func(
                F("keywords"), Value(" | "), function="array_to_string", output_field=CharField()
            )
        )
        match = Q(keywords_text__contains=name)
        for field in names:
            match |= Q(**{f"{field}__icontains": name})
        queryset = queryset.filter(match)
    if tax_id:
        typed = normalize_tax_id(params.get("tax_id", ""))
        if typed:
            queryset = queryset.filter(tax_id__contains=typed)
    location = collapse_spaces(params.get("location", ""))
    if location:
        queryset = queryset.filter(Q(city__icontains=location) | Q(state__iexact=location))
    active = params.get("is_active")
    if active in ("true", "false"):
        queryset = queryset.filter(is_active=active == "true")
    return queryset
