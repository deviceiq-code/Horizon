from catalogs.names import english_plural, localized


def test_english_plural_of_the_last_word():
    assert english_plural("Laptop") == "Laptops"
    assert english_plural("3D Printer") == "3D Printers"
    assert english_plural("Battery") == "Batteries"
    assert english_plural("Display") == "Displays"
    assert english_plural("Switch") == "Switches"
    assert english_plural("Fax") == "Faxes"
    # Already plural
    assert english_plural("Accessories") == "Accessories"
    assert english_plural("  ") == ""


def test_names_in_a_language_fall_back_to_english():
    translations = {"pt-br": {"name": "Notebook", "plural": "Notebooks"}, "es": {"name": ""}}
    assert localized("Laptop", "Laptops", translations, "pt-br", many=True) == "Notebooks"
    assert localized("Laptop", "Laptops", translations, "pt-br", many=False) == "Notebook"
    assert localized("Laptop", "Laptops", translations, "es", many=True) == "Laptops"
    assert localized("Laptop", "Laptops", translations, "en", many=True) == "Laptops"
    assert localized("Laptop", "Laptops", None, "pt-br", many=False) == "Laptop"


def test_asset_class_names_through_the_api(admin_client, db):
    from catalogs.models import SubVertical, Vertical

    vertical = Vertical.objects.create(name="IT")
    sub = SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    url = "/api/catalogs/asset-classes/"
    data = {"name": "Laptop", "sub_vertical": sub.pk, "icon": "mdi-laptop"}
    # Not sent: the English plural, by the usual rules
    r = admin_client.post(url, data, content_type="application/json")
    assert r.status_code == 201, r.json()
    assert (r.json()["plural_name"], r.json()["translations"]) == ("Laptops", {})
    r = admin_client.post(
        url,
        {
            **data,
            "name": "Desktop",
            "plural_name": " Desktop  computers ",
            "translations": {"pt-br": {"name": "Desktop", "plural": "Desktops"}, "es": {}},
        },
        content_type="application/json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["plural_name"] == "Desktop computers"
    # Empty translations are dropped
    assert r.json()["translations"] == {"pt-br": {"name": "Desktop", "plural": "Desktops"}}
    r = admin_client.post(
        url,
        {**data, "name": "Monitor", "translations": {"fr": {}}},
        content_type="application/json",
    )
    assert r.status_code == 400 and "translations" in r.json()
