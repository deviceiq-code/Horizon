import pytest
from django.contrib.auth import get_user_model

from catalogs.models import AssetClass, Manufacturer, SubVertical, Vertical

from .models import AveragePrice
from .testing import TEMPLATE, _payload, _post


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        "tester", password="strong-password-123", first_name="Ana", last_name="Souza"
    )


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def catalog(db):
    industry = Vertical.objects.create(name="Industry")
    SubVertical.objects.create(vertical=industry, **SubVertical.general_defaults())
    yellow = SubVertical.objects.create(
        vertical=industry,
        name="Yellow line",
        risk="high",
        allowed_terms=[12, 24, 36],
        recommended_term=24,
    )
    excavators = AssetClass.objects.create(
        name="Excavators", sub_vertical=yellow, spec_template=TEMPLATE
    )
    cat = Manufacturer.objects.create(name="Caterpillar")
    deere = Manufacturer.objects.create(name="John Deere")
    return {"yellow": yellow, "excavators": excavators, "cat": cat, "deere": deere}


@pytest.fixture
def price(logged_client, catalog):
    r = _post(logged_client, _payload(catalog))
    assert r.status_code == 201, r.json()
    return AveragePrice.objects.get(pk=r.json()["id"])
