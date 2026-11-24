from decimal import Decimal as D

from efmv.scope import ScopeGroup as G
from efmv.scope import scope_summary


def test_the_examples():
    # 1. Many Dell laptops
    assert scope_summary([G("Dell", "Laptops", 80)], "en") == "Dell Laptops"
    # 2. Dell laptops and desktops
    groups = [G("Dell", "Laptops", 80), G("Dell", "Desktops", 40)]
    assert scope_summary(groups, "en") == "Dell Laptops and Desktops"
    # 3. Dell laptops and Lenovo desktops
    groups = [G("Dell", "Laptops", 80), G("Lenovo", "Desktops", 40)]
    assert scope_summary(groups, "en") == "Dell Laptops and Lenovo Desktops"
    # 4. Dell desktops and monitors
    groups = [G("Dell", "Desktops", 50), G("Dell", "Monitors", 50)]
    assert scope_summary(groups, "en") == "Dell Desktops and Monitors"
    # 5. Very few desktops: negligible
    groups = [G("Dell", "Laptops", 100), G("Dell", "Desktops", 3)]
    assert scope_summary(groups, "en") == "Dell Laptops"


def test_the_same_class_of_several_manufacturers():
    groups = [G("Dell", "Laptops", 60), G("Lenovo", "Laptops", 40)]
    assert scope_summary(groups, "en") == "Dell and Lenovo Laptops"


def test_rows_of_the_same_asset_add_up():
    groups = [G("Dell", "Laptops", 3), G("Dell", "Desktops", 50), G("Dell", "Laptops", 60)]
    assert scope_summary(groups, "en") == "Dell Laptops and Desktops"


def test_the_threshold():
    groups = [G("Dell", "Laptops", 90), G("Dell", "Desktops", 10)]
    assert scope_summary(groups, "en", D("5")) == "Dell Laptops and Desktops"
    assert scope_summary(groups, "en", D("15")) == "Dell Laptops"
    # Exactly at the threshold: kept
    assert scope_summary(groups, "en", D("10")) == "Dell Laptops and Desktops"


def test_at_most_three_parts():
    groups = [
        G("Dell", "Laptops", 40),
        G("Lenovo", "Desktops", 30),
        G("HP", "Printers", 20),
        G("Cisco", "Switches", 10),
    ]
    assert scope_summary(groups, "en") == (
        "Dell Laptops, Lenovo Desktops, HP Printers and other assets"
    )


def test_each_language_has_its_word_order():
    groups = [G("Dell", "Notebooks", 80), G("Lenovo", "Desktops", 40)]
    assert scope_summary(groups, "pt-br") == "Notebooks Dell e Desktops Lenovo"
    groups = [G("Dell", "Portátiles", 80), G("Dell", "Monitores", 40)]
    assert scope_summary(groups, "es") == "Portátiles y Monitores Dell"


def test_without_assets():
    assert scope_summary([], "en") == ""
    assert scope_summary([G("Dell", "Laptops", 0)], "en") == ""


def test_software_and_services_are_noted():
    from efmv.scope import ScopeGroup, scope_summary

    groups = [ScopeGroup("Dell", "Laptops", 10)]
    assert scope_summary(groups, "en", services=True) == "Dell Laptops (+Service)"
    assert scope_summary(groups, "en", software=True) == "Dell Laptops (+Software)"
    assert (
        scope_summary(groups, "pt-br", services=True, software=True)
        == "Laptops Dell (+Serviço e Software)"
    )
    # Only software and services: the note alone
    assert scope_summary([], "es", services=True, software=True) == "(+Servicio y Software)"
