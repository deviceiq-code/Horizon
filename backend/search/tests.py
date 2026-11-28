"""Centralized search (search/registry.py): each category searched by its module's own list."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalogs.models import Manufacturer, Vertical
from customers.models import Customer
from entities.models import BusinessEntity
from users.models import Role
from users.testing import make_account_manager

CNPJ = "11.222.333/0001-81"


@pytest.fixture
def data(db):
    manager = make_account_manager("Ana", "Souza", "ana@example.com")
    Customer.objects.create(
        name="Transportes Deere Ltda", trade_name="TransDeere", tax_id=CNPJ,
        city="Campinas", state="SP", primary_account_manager=manager,
    )  # fmt: skip
    Manufacturer.objects.create(name="John Deere")
    Vertical.objects.create(name="AGR Deere", is_enabled=False)
    return manager


def _client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _search(client, **params):
    response = client.get("/api/search/", params)
    assert response.status_code == 200
    return response.json()


def test_one_search_over_every_module_with_counts_and_a_few_results(data):
    body = _search(_client(data), q="deere")
    assert body["q"] == "deere"
    by_key = {c["key"]: c for c in body["categories"]}
    # Only categories with matches, in the registry's order
    assert [c["key"] for c in body["categories"]] == [
        "business_entities",
        "verticals",
        "manufacturers",
    ]
    customer = by_key["business_entities"]["results"][0]
    assert by_key["business_entities"]["count"] == 1
    assert customer["title"] == "TransDeere"
    assert customer["subtitle"] == "Transportes Deere Ltda"
    # Its roles, then where it is
    assert customer["meta"] == "Customer · Campinas / SP"
    assert customer["badge"] == {"text": "Active", "color": "success"}
    # What to type in the module's grid to find it
    assert customer["search"] == "Transportes Deere Ltda"
    assert by_key["verticals"]["results"][0]["badge"] == {"text": "Disabled", "color": "default"}


def test_finds_what_the_modules_grid_finds_keywords_and_account_managers_too(data):
    BusinessEntity.objects.filter(name__startswith="Transportes").update(
        keywords=["forestry fleet"]
    )
    assert _search(_client(data), q="forestry")["categories"][0]["key"] == "business_entities"
    assert _search(_client(data), q="souza")["categories"][0]["key"] == "business_entities"


def test_one_category_gives_more_results_the_others_only_their_count(data):
    for n in range(7):
        Manufacturer.objects.create(name=f"Deere Parts {n}")
    client = _client(data)
    everything = {c["key"]: c for c in _search(client, q="deere")["categories"]}
    assert (everything["manufacturers"]["count"], len(everything["manufacturers"]["results"])) == (
        8,
        5,
    )
    one = {c["key"]: c for c in _search(client, q="deere", category="manufacturers")["categories"]}
    assert len(one["manufacturers"]["results"]) == 8
    entities = one["business_entities"]
    assert entities["count"] == 1 and entities["results"] == []


def test_users_only_for_administrators(data):
    get_user_model().objects.create_user("deere.operator", email="op@deere.com")
    assert "users" not in [c["key"] for c in _search(_client(data), q="deere")["categories"]]
    admin = get_user_model().objects.create_user("boss", password="x")
    Role.administrator().users.add(admin)
    users = next(c for c in _search(_client(admin), q="deere")["categories"] if c["key"] == "users")
    result = users["results"][0]
    assert (result["subtitle"], result["search"]) == ("op@deere.com", "deere.operator")
    assert "photo_version" in result


def test_short_queries_find_nothing_and_signing_in_is_required(data):
    assert _search(_client(data), q=" d ")["categories"] == []
    assert APIClient().get("/api/search/", {"q": "deere"}).status_code == 403


def test_results_in_the_users_language(data):
    from accounts.models import UserPreferences

    UserPreferences.for_user(data)
    UserPreferences.objects.filter(user=data).update(language="pt-br")
    customers = _search(_client(data), q="deere")["categories"][0]
    assert customers["results"][0]["badge"]["text"] == "Ativo"
