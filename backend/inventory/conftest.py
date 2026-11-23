"""Fixtures shared by the inventory's tests: a warehouse with a dock, an inspection queue, a
stock area and a quarantine; a notebook model; users with the inventory roles."""

import pytest
from django.contrib.auth import get_user_model

from catalogs.models import AssetClass, AssetModel, Manufacturer, SubVertical, Tracking, Vertical
from users.models import INVENTORY_SUPERVISOR, RECEIVER, STOREKEEPER, Role

from . import services
from .models import Location, Warehouse
from .states import AreaType

User = get_user_model()


def user_with_roles(username: str, *keys: str):
    user = User.objects.create_user(username, password="strong-password-123")
    for key in keys:
        Role.system(key).users.add(user)
    return user


@pytest.fixture
def storekeeper(db):
    return user_with_roles("storekeeper", STOREKEEPER)


@pytest.fixture
def receiver(db):
    return user_with_roles("receiver", RECEIVER)


@pytest.fixture
def supervisor(db):
    return user_with_roles("supervisor", INVENTORY_SUPERVISOR)


@pytest.fixture
def admin(db):
    return User.objects.create_superuser("admin", password="strong-password-123")


@pytest.fixture
def nobody(db):
    """Signed in, without inventory roles."""
    return User.objects.create_user("nobody", password="strong-password-123")


def client_for(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def warehouse(db):
    return Warehouse.objects.create(name="CD Barueri", state="SP")


@pytest.fixture
def places(warehouse):
    """The warehouse's areas by type."""

    def make(segment, area_type, parent=None):
        base = parent.code if parent else warehouse.code
        return Location.objects.create(
            warehouse=warehouse,
            parent=parent,
            segment=segment,
            code=f"{base}-{segment}",
            area_type=area_type,
        )

    stock = make("EST", AreaType.STOCK)
    return {
        "dock": make("DOC", AreaType.DOCK),
        "queue": make("FIL", AreaType.INSPECTION_QUEUE),
        "bench": make("BAN", AreaType.BENCH),
        "quarantine": make("QUA", AreaType.QUARANTINE),
        "stock": stock,
        "shelf": make("A1", AreaType.STOCK, parent=stock),
        "scrap": make("SUC", AreaType.SCRAP),
    }


@pytest.fixture
def notebook_class(db):
    vertical = Vertical.objects.create(name="Information Technology")
    sub = SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    return AssetClass.objects.create(
        name="Notebook",
        plural_name="Notebooks",
        sub_vertical=sub,
        spec_template=[
            {"key": "ram_gb", "label": "RAM", "kind": "number", "unit": "GB", "required": True},
            {"key": "color", "label": "Color", "kind": "text", "unit": "", "required": False},
        ],
    )


@pytest.fixture
def notebook(notebook_class):
    dell = Manufacturer.objects.create(name="Dell")
    return AssetModel.objects.create(
        manufacturer=dell,
        name="Latitude 5440",
        asset_class=notebook_class,
        specs=[
            {**notebook_class.spec_template[0], "value": "16"},
            {**notebook_class.spec_template[1], "value": ""},
        ],
        serial_regex=r"[A-Z0-9]{7}",
        has_storage=True,
    )


@pytest.fixture
def cables(notebook_class):
    acme = Manufacturer.objects.create(name="Acme")
    return AssetModel.objects.create(
        manufacturer=acme,
        name="USB-C Cable",
        asset_class=notebook_class,
        tracking=Tracking.QUANTITY,
    )


@pytest.fixture
def make_asset(notebook, places, admin):
    """Register an asset at the dock (IN_TRIAGE)."""
    counter = iter(range(1000))

    def make(serial=None, **kwargs):
        serial = serial if serial is not None else f"ABC{next(counter):04d}"
        return services.register_entry(
            asset_model=notebook, location=places["dock"], user=admin, serial=serial, **kwargs
        )

    return make
