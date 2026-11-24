"""Fixtures shared by the inventory's tests: a warehouse with a dock, an inspection queue, a
stock area and a quarantine; a notebook model; users with the inventory roles."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from catalogs.models import AssetClass, AssetModel, Manufacturer, SubVertical, Tracking, Vertical
from customers.models import Customer
from users.models import (
    COMMERCIAL_FINANCE,
    INSPECTION_TECHNICIAN,
    INVENTORY_SUPERVISOR,
    RECEIVER,
    REMARKETING_ANALYST,
    STOREKEEPER,
    Role,
)
from users.testing import make_account_manager

from . import receiving, services
from .models import ErasureTool, Location, LotErasureTool, PenaltyRate, Warehouse
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


@pytest.fixture
def analyst(db):
    return user_with_roles("analyst", REMARKETING_ANALYST)


@pytest.fixture
def commercial(db):
    return user_with_roles("commercial", COMMERCIAL_FINANCE)


@pytest.fixture
def customer(db):
    manager = make_account_manager("Ana", "Souza", "ana@example.com")
    return Customer.objects.create(
        name="Transportes Rápidos Ltda", tax_id="11222333000181", primary_account_manager=manager
    )


# --- Inspection (Phases 3 and 4) -----------------------------------------------------------


@pytest.fixture
def technician(db):
    return user_with_roles("technician", INSPECTION_TECHNICIAN)


@pytest.fixture
def setup(notebook, notebook_class, places, receiver, supervisor, warehouse, customer):
    """A notebook (data storage; kit and test script; front photo required) waiting for
    inspection, its lot's erasure tool defined and a penalty table."""
    notebook.kit_checklist = [
        {"item": "Charger", "essential": False},
        {"item": "Battery", "essential": True},
    ]
    notebook.test_script = ["Boots", "Keyboard"]
    notebook.save()
    notebook_class.required_photo_kinds = ["front"]
    notebook_class.save()
    lot = receiving.open_lot(
        warehouse=warehouse, customer=customer, dock=places["dock"], user=receiver
    )
    asset = receiving.triage_unit(lot, user=receiver, asset_model=notebook, serial="ABC0001")
    receiving.close_lot(lot, user=receiver)
    tool = ErasureTool.objects.create(name="Blancco", version="7.1", methods=["purge"])
    tool.asset_classes.add(notebook_class)
    LotErasureTool.objects.create(
        lot=lot, asset_class=notebook_class, tool=tool, method="purge", defined_by=supervisor
    )
    for kind, value in (
        ("missing_item", "150.00"),
        ("heavy_cleaning", "80.00"),
        ("access_block", "500.00"),
    ):
        PenaltyRate.objects.create(
            asset_class=notebook_class,
            finding_kind=kind,
            value=Decimal(value),
            valid_from=date(2026, 1, 1),
        )
    asset.refresh_from_db()
    return {"asset": asset, "lot": lot, "tool": tool}
