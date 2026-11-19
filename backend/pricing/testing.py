"""Helpers shared by the pricing tests (fixtures are in conftest.py)."""

URL = "/api/average-prices/"

TEMPLATE = [
    {"key": "hours", "label": "Operating hours", "kind": "number", "unit": "h", "required": True},
    {"key": "tracks", "label": "Undercarriage", "kind": "text", "unit": "", "required": False},
]


def _payload(catalog, **overrides):
    return {
        "asset_class": catalog["excavators"].pk,
        "manufacturer": catalog["cat"].pk,
        "model": " 320 GC ",
        "description": "Hydraulic excavator, 20 t class.",
        "specs": {"hours": "2.500".replace(".", ""), "tracks": "Steel"},
        "original_value": "100000.00",
        "points": [
            {"term_months": 12, "mode": "percent", "amount": "70"},
            {"term_months": 24, "mode": "value", "amount": "55000"},
            {"term_months": 36, "mode": "percent", "amount": "42.5"},
        ],
        **overrides,
    }


def _post(client, data):
    return client.post(URL, data, content_type="application/json")


def _new_version(client, catalog, of, value):
    r = _post(client, _payload(catalog, original_value=value, supersedes=of))
    assert r.status_code == 201, r.json()
    return r.json()["id"]
