"""Centralized search: one search over every module, the same way in all of them.

Each category is a provider: the module's own list ViewSet (its queryset, its permissions and
its `?search=` — search_fields and keywords) and how one of its records shows as a result. So
a word finds here exactly what it finds in that module's grid, and nobody sees a category they
could not open. Pages (the system's modules) are searched in the frontend (their names are
translations there).

Every result has the same shape: id, title, subtitle, meta, badge {text, color} or null,
search (what to type in the module's grid to find it), amount {value, currency} or null and,
for people, photo_version.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _

from catalogs.views import AssetClassViewSet, ManufacturerViewSet, VerticalViewSet
from customers.views import CustomerViewSet
from efmv.views import EfmvAnalysisViewSet
from inventory.views import AssetViewSet, WarehouseViewSet
from pricing.views import AveragePriceViewSet
from service_providers.models import ServiceKind
from service_providers.views import ServiceProviderViewSet
from users.display import display_name
from users.models import user_photo_version
from users.views import UserViewSet

Result = dict[str, Any]


@dataclass(frozen=True)
class Provider:
    # The category's key (the frontend names it and knows where its results open)
    key: str
    view: type
    result: Callable[[Any, Any], Result]


def _result(obj, title, *, subtitle="", meta="", badge=None, search=None, **extra) -> Result:
    return {
        "id": obj.pk,
        "title": title,
        "subtitle": subtitle,
        "meta": meta,
        "badge": badge,
        "search": search if search is not None else title,
        "amount": None,
        **extra,
    }


ACTIVE, INACTIVE = _("Active"), _("Inactive")
ENABLED, DISABLED = _("Enabled"), _("Disabled")


def _active(flag: bool, on=ACTIVE, off=INACTIVE):
    return {"text": str(on), "color": "success"} if flag else {"text": str(off), "color": "default"}


def _place(obj) -> str:
    return " / ".join(part for part in (obj.city, obj.state) if part)


def _analysis(obj, request) -> Result:
    customer = obj.customer.trade_name or obj.customer.name
    return _result(
        obj,
        obj.code,
        # With its external reference (e.g. the CRM opportunity), which the search also finds
        subtitle=" · ".join(part for part in (customer, obj.external_reference) if part),
        meta=display_name(obj.account_manager, viewer=request.user),
        badge={"text": obj.vertical.name, "color": "primary"} if obj.vertical_id else None,
    )


def _price(obj, request) -> Result:
    result = _result(
        obj,
        f"{obj.manufacturer.name} {obj.model}",
        subtitle=obj.asset_class.name,
        meta=obj.description,
        search=obj.model,
    )
    result["amount"] = {"value": str(obj.original_value), "currency": obj.currency}
    return result


def _customer(obj, request) -> Result:
    return _result(
        obj,
        obj.trade_name or obj.name,
        subtitle=obj.name if obj.trade_name else obj.tax_id,
        meta=_place(obj),
        badge=_active(obj.is_active),
        search=obj.name,
    )


def _asset(obj, request) -> Result:
    model = obj.asset_model
    return _result(
        obj,
        obj.horizon_id,
        subtitle=f"{model.manufacturer.name} {model.name}",
        meta=obj.serial,
        badge={"text": obj.get_status_display(), "color": "info"},
    )


def _user(obj, request) -> Result:
    roles = sorted(role.name for role in obj.roles.all())
    return _result(
        obj,
        display_name(obj, viewer=request.user),
        subtitle=obj.email,
        meta=", ".join(roles),
        badge=None if obj.is_active else _active(False),
        search=obj.username,
        photo_version=user_photo_version(obj),
    )


def _provider(obj, request) -> Result:
    return _result(
        obj,
        obj.trade_name or obj.name,
        subtitle=obj.name if obj.trade_name else obj.tax_id,
        meta=", ".join(str(ServiceKind(kind).label) for kind in obj.services),
        badge=_active(obj.is_active),
        search=obj.name,
    )


def _warehouse(obj, request) -> Result:
    return _result(
        obj,
        obj.name,
        subtitle=obj.code,
        meta=_place(obj),
        badge=_active(obj.is_active),
    )


def _vertical(obj, request) -> Result:
    return _result(obj, obj.name, badge=_active(obj.is_enabled, ENABLED, DISABLED), meta=obj.notes)


def _asset_class(obj, request) -> Result:
    sub = obj.sub_vertical
    return _result(
        obj,
        obj.name,
        subtitle=f"{sub.vertical.name} / {sub.name}" if sub.name else sub.vertical.name,
        badge=_active(obj.is_enabled, ENABLED, DISABLED),
        icon=obj.icon,
    )


def _manufacturer(obj, request) -> Result:
    return _result(obj, obj.name, badge=_active(obj.is_enabled, ENABLED, DISABLED))


# In the order the tabs show them
PROVIDERS: tuple[Provider, ...] = (
    Provider("efmv_analyses", EfmvAnalysisViewSet, _analysis),
    Provider("average_prices", AveragePriceViewSet, _price),
    Provider("customers", CustomerViewSet, _customer),
    Provider("assets", AssetViewSet, _asset),
    Provider("users", UserViewSet, _user),
    Provider("service_providers", ServiceProviderViewSet, _provider),
    Provider("warehouses", WarehouseViewSet, _warehouse),
    Provider("verticals", VerticalViewSet, _vertical),
    Provider("asset_classes", AssetClassViewSet, _asset_class),
    Provider("manufacturers", ManufacturerViewSet, _manufacturer),
)
