import pytest
from django.contrib.auth import get_user_model

from .models import Role, UserProfile
from .permissions import is_administrator

User = get_user_model()
USERS = "/api/users/"
ROLES = "/api/roles/"
STRONG = "Horizon-pass-2026"


@pytest.fixture
def admin_role(db):
    return Role.administrator()


@pytest.fixture
def admin(admin_role):
    user = User.objects.create_user("ana", password=STRONG, first_name="Ana", last_name="Souza")
    admin_role.users.add(user)
    return user


@pytest.fixture
def admin_client(client, admin):
    client.force_login(admin)
    return client


@pytest.fixture
def analyst_role(db):
    return Role.objects.create(name="Analyst", description="Prices")


def _post(client, url, data):
    return client.post(url, data, content_type="application/json")


def _patch(client, url, data):
    return client.patch(url, data, content_type="application/json")


# --- Who is an administrator ------------------------------------------------------------------


def test_administrator_role_exists_and_is_a_system_role(admin_role):
    assert (admin_role.name, admin_role.is_system) == ("Administrator", True)


def test_is_administrator(admin, db):
    assert is_administrator(admin)
    other = User.objects.create_user("bruno", password=STRONG)
    assert not is_administrator(other)
    assert is_administrator(User.objects.create_superuser("root", password=STRONG))
    admin.is_active = False
    assert not is_administrator(admin)


def test_only_administrators_manage_users_and_roles(client, db):
    user = User.objects.create_user("bruno", password=STRONG)
    client.force_login(user)
    assert client.get(USERS).status_code == 403
    assert client.get(ROLES).status_code == 403
    assert _post(client, ROLES, {"name": "X"}).status_code == 403


def test_me_tells_whether_the_user_is_an_administrator(admin_client):
    data = admin_client.get("/api/auth/me/").json()
    assert data["is_admin"] is True
    assert data["roles"] == ["Administrator"]


# --- Users ------------------------------------------------------------------------------------


def test_create_user_with_roles(admin_client, analyst_role, admin_role):
    r = _post(
        admin_client,
        USERS,
        {
            "username": " carla ",
            "first_name": "Carla",
            "last_name": "Mendes",
            "email": " Carla@Example.com ",
            "password": STRONG,
            "roles": [analyst_role.pk, admin_role.pk],
        },
    )
    assert r.status_code == 201, r.json()
    data = r.json()
    assert "password" not in data
    assert (data["username"], data["email"], data["full_name"]) == (
        "carla",
        "carla@example.com",
        "Carla Mendes",
    )
    assert [role["name"] for role in data["roles_detail"]] == ["Administrator", "Analyst"]
    carla = User.objects.get(username="carla")
    assert carla.check_password(STRONG)
    assert is_administrator(carla)


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"username": "x"}, "password"),  # required when creating
        ({"username": "x", "password": "123"}, "password"),  # too weak
        ({"username": "x", "password": "password1234"}, "password"),  # too common
        ({"username": "ANA", "password": STRONG}, "username"),  # taken (any case)
        ({"username": "x", "password": STRONG, "email": "nope"}, "email"),
    ],
)
def test_user_validation(admin_client, data, field):
    r = _post(admin_client, USERS, data)
    assert r.status_code == 400
    assert field in r.json()


def test_edit_user_and_set_a_new_password(admin_client, analyst_role):
    bruno = User.objects.create_user("bruno", password=STRONG)
    r = _patch(
        admin_client, f"{USERS}{bruno.pk}/", {"first_name": "Bruno", "roles": [analyst_role.pk]}
    )
    assert r.status_code == 200, r.json()
    bruno.refresh_from_db()
    assert bruno.check_password(STRONG)  # unchanged without a password
    assert list(bruno.roles.values_list("name", flat=True)) == ["Analyst"]
    r = _patch(admin_client, f"{USERS}{bruno.pk}/", {"password": "Another-pass-2026"})
    assert r.status_code == 200
    bruno.refresh_from_db()
    assert bruno.check_password("Another-pass-2026")


def test_search_and_active_filter(admin_client, analyst_role):
    bruno = User.objects.create_user("bruno", password=STRONG, email="bruno@corp.com")
    analyst_role.users.add(bruno)
    User.objects.create_user("carla", password=STRONG, is_active=False)

    def names(params):
        return [u["username"] for u in admin_client.get(USERS, params).json()["results"]]

    assert names({}) == ["ana", "bruno", "carla"]
    assert names({"search": "corp"}) == ["bruno"]
    assert names({"search": "analyst"}) == ["bruno"]
    assert names({"is_active": "false"}) == ["carla"]


def test_cannot_lock_yourself_out(admin_client, admin, admin_role):
    url = f"{USERS}{admin.pk}/"
    r = _patch(admin_client, url, {"is_active": False})
    assert (r.status_code, r.json()["detail"]) == (409, "You cannot deactivate your own user.")
    r = _patch(admin_client, url, {"roles": []})
    assert r.status_code == 409
    assert "Administrator role" in r.json()["detail"]
    assert admin_client.delete(url).status_code == 409
    admin.refresh_from_db()
    assert admin.is_active and admin.roles.filter(pk=admin_role.pk).exists()


def test_the_last_administrator_remains(client, admin, admin_role, db):
    second = User.objects.create_user("bruno", password=STRONG)
    admin_role.users.add(second)
    client.force_login(second)
    # While another one remains, an administrator can lose the role…
    assert _patch(client, f"{USERS}{admin.pk}/", {"roles": []}).status_code == 200
    # …or be deactivated (here: back as administrator first)
    admin_role.users.add(admin)
    assert _patch(client, f"{USERS}{admin.pk}/", {"is_active": False}).status_code == 200
    # Now "bruno" is the only active administrator: removing it would leave none
    r = _patch(client, f"{USERS}{second.pk}/", {"roles": []})
    assert r.status_code == 409


def test_deleting_administrators(client, admin, db):
    second = User.objects.create_user("second", password=STRONG)
    Role.administrator().users.add(second)
    client.force_login(second)
    assert client.delete(f"{USERS}{admin.pk}/").status_code == 204
    # Now "second" is the only administrator and cannot remove itself
    assert client.delete(f"{USERS}{second.pk}/").status_code == 409


def test_users_with_records_cannot_be_deleted(admin_client, db):
    from system.models import SystemSettings

    bruno = User.objects.create_user("bruno", password=STRONG)
    SystemSettings.objects.update_or_create(pk=1, defaults={"updated_by": bruno})
    r = admin_client.delete(f"{USERS}{bruno.pk}/")
    assert r.status_code == 409
    assert "Deactivate" in r.json()["detail"]
    other = User.objects.create_user("carla", password=STRONG)
    assert admin_client.delete(f"{USERS}{other.pk}/").status_code == 204


# --- Roles ------------------------------------------------------------------------------------


def test_roles_crud(admin_client, analyst_role, admin):
    r = _post(admin_client, ROLES, {"name": "  Pricing   team ", "description": "Prices"})
    assert r.status_code == 201, r.json()
    assert r.json()["name"] == "Pricing team"
    assert _post(admin_client, ROLES, {"name": "pricing TEAM"}).status_code == 400
    listed = admin_client.get(ROLES).json()["results"]
    assert [(x["name"], x["users_count"]) for x in listed] == [
        ("Account Manager", 0),
        ("Administrator", 1),
        ("Analyst", 0),
        ("Pricing team", 0),
    ]
    role_id = r.json()["id"]
    assert _patch(admin_client, f"{ROLES}{role_id}/", {"name": "Pricing"}).status_code == 200
    assert admin_client.delete(f"{ROLES}{role_id}/").status_code == 204


def test_system_roles_cannot_be_changed_or_deleted(admin_client, admin_role):
    url = f"{ROLES}{admin_role.pk}/"
    r = admin_client.delete(url)
    assert (r.status_code, r.json()["detail"]) == (409, "System roles cannot be deleted.")
    for data in ({"name": "Boss"}, {"description": "Everything"}):
        r = _patch(admin_client, url, data)
        assert r.status_code == 400
        assert r.json()["non_field_errors"] == ["System roles cannot be changed."]
    admin_role.refresh_from_db()
    assert (admin_role.name, admin_role.description) == (
        "Administrator",
        "Full access to the system.",
    )


def test_roles_given_to_users_cannot_be_deleted(admin_client, analyst_role):
    analyst_role.users.add(User.objects.create_user("bruno", password=STRONG))
    r = admin_client.delete(f"{ROLES}{analyst_role.pk}/")
    assert r.status_code == 409
    assert Role.objects.filter(pk=analyst_role.pk).exists()


# --- How users are shown ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("names", "display", "order", "expected"),
    [
        (("ana", "Ana", "Souza"), "full_name", "first_last", "Ana Souza"),
        (("ana", "Ana", "Souza"), "full_name", "last_first", "Souza, Ana"),
        (("ana", "Ana", "Souza"), "first_name", "last_first", "Ana"),
        (("ana", "Ana", "Souza"), "username", "first_last", "ana"),
        (("ana", " Ana  Maria ", ""), "full_name", "last_first", "Ana Maria"),
        (("ana", "", "Souza"), "full_name", "first_last", "Souza"),
        (("ana", "", ""), "full_name", "last_first", "ana"),
        (("ana", "", "Souza"), "first_name", "first_last", "Souza"),  # falls back
    ],
)
def test_format_user_name(names, display, order, expected):
    from .display import format_user_name

    assert format_user_name(*names, display, order) == expected


def _set_display(client, display, order="first_last"):
    r = _patch(
        client,
        "/api/auth/preferences/",
        {"user_name_display": display, "full_name_order": order},
    )
    assert r.status_code == 200, r.json()


def test_users_are_shown_as_each_user_wants(admin_client, client):
    assert admin_client.get("/api/auth/me/").json()["name"] == "Ana Souza"
    _set_display(admin_client, "full_name", "last_first")
    assert admin_client.get("/api/auth/me/").json()["name"] == "Souza, Ana"
    # The users grid shows the full name in that order
    listed = admin_client.get(USERS).json()["results"][0]
    assert listed["full_name"] == "Souza, Ana"
    _set_display(admin_client, "username")
    assert admin_client.get("/api/auth/me/").json()["name"] == "ana"
    _set_display(admin_client, "first_name")
    assert admin_client.get("/api/auth/me/").json()["name"] == "Ana"
    # Another user still sees full names, first name first (their own preference)
    bruno = User.objects.create_user("bruno", first_name="Bruno", last_name="Lima")
    Role.administrator().users.add(bruno)
    client.force_login(bruno)
    listed = {u["username"]: u["full_name"] for u in client.get(USERS).json()["results"]}
    assert listed["ana"] == "Ana Souza"


# --- Photos ---------------------------------------------------------------------------------

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _photo(client, user_id, content=JPEG, name="me.jpg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return client.post(f"{USERS}{user_id}/photo/", {"file": SimpleUploadedFile(name, content)})


@pytest.mark.django_db(transaction=True)
def test_user_photos(admin_client, admin, client, media):
    import os

    bruno = User.objects.create_user("bruno", password=STRONG)
    assert admin_client.get(f"{USERS}{bruno.pk}/photo/").status_code == 404
    r = _photo(admin_client, bruno.pk)
    assert r.status_code == 201, r.json()
    version = r.json()["photo_version"]
    assert version
    assert admin_client.get(f"{USERS}{bruno.pk}/").json()["photo_version"] == version

    # Anyone signed in sees it (e.g. their own in the top bar); only administrators change it
    client.force_login(bruno)
    assert client.get("/api/auth/me/").json()["photo_version"] == version
    r = client.get(f"{USERS}{bruno.pk}/photo/")
    assert (r.status_code, r["Content-Type"]) == (200, "image/jpeg")
    assert _photo(client, bruno.pk).status_code == 403
    assert client.delete(f"{USERS}{bruno.pk}/photo/").status_code == 403

    # Deleting the user removes the file
    path = UserProfile.objects.get(user=bruno).photo.path
    assert os.path.exists(path)
    client.force_login(admin)
    assert client.delete(f"{USERS}{bruno.pk}/").status_code == 204
    assert not os.path.exists(path)


def test_user_photo_must_be_an_image(admin_client, admin, media):
    r = _photo(admin_client, admin.pk, b"%PDF", "cv.pdf")
    assert r.status_code == 400
    assert admin_client.get("/api/auth/me/").json()["photo_version"] is None


# --- Employee data and account managers -----------------------------------------------------


@pytest.fixture
def industry(db):
    from catalogs.models import SubVertical, Vertical

    vertical = Vertical.objects.create(name="Industry")
    SubVertical.objects.create(vertical=vertical, **SubVertical.general_defaults())
    return vertical


EMPLOYEE = {
    "id_document_type": "cpf",
    "id_document_number": "529.982.247-25",
    "employee_number": " E-1042 ",
    "nationality": "br",
    "birth_date": "1990-05-17",
    "job_title": "Account  Manager",
    "department": "Sales",
    "work_location": "São Paulo",
    "hire_date": "2020-02-03",
    "phone": "+55 11 3000-0000",
    "mobile_phone": "+55 11 99999-0000",
}


def test_account_manager_is_a_system_role(admin_client):
    role = Role.account_manager()
    assert (role.name, role.is_system) == ("Account Manager", True)
    r = admin_client.delete(f"{ROLES}{role.pk}/")
    assert r.status_code == 409


def test_employee_data_is_saved_with_the_user(admin_client, admin, industry):
    r = _post(
        admin_client,
        USERS,
        {
            "username": "carla",
            "first_name": "Carla",
            "last_name": "Mendes",
            "password": STRONG,
            "roles": [Role.account_manager().pk],
            "manager": admin.pk,
            "verticals": [industry.pk],
            **EMPLOYEE,
        },
    )
    assert r.status_code == 201, r.json()
    data = r.json()
    assert (data["id_document_type"], data["id_document_number"]) == ("cpf", "52998224725")
    assert (data["employee_number"], data["nationality"]) == ("E-1042", "BR")
    assert (data["job_title"], data["department"]) == ("Account Manager", "Sales")
    assert (data["birth_date"], data["hire_date"]) == ("1990-05-17", "2020-02-03")
    assert (data["manager"], data["manager_name"]) == (admin.pk, "Ana Souza")
    assert data["verticals_detail"] == [{"id": industry.pk, "name": "Industry", "is_enabled": True}]
    assert data["has_password"] is True
    carla = User.objects.get(username="carla")
    assert carla.profile.employee_number == "E-1042"
    # Edit only some fields: the others stay
    r = _patch(admin_client, f"{USERS}{carla.pk}/", {"department": "Key Accounts"})
    assert r.status_code == 200
    assert (r.json()["department"], r.json()["job_title"]) == ("Key Accounts", "Account Manager")


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"id_document_type": "cpf", "id_document_number": "111.111.111-11"}, "id_document_number"),
        ({"id_document_number": "123"}, "id_document_type"),
        ({"id_document_type": "passport"}, "id_document_number"),
        ({"nationality": "Brazil"}, "nationality"),
        ({"birth_date": "2999-01-01"}, "birth_date"),
        ({"birth_date": "1990-01-01", "hire_date": "1980-01-01"}, "hire_date"),
        ({"id_document_type": "unknown", "id_document_number": "1"}, "id_document_type"),
    ],
)
def test_employee_data_validation(admin_client, data, field):
    r = _post(admin_client, USERS, {"username": "x", "password": STRONG, **data})
    assert r.status_code == 400
    assert field in r.json(), r.json()


def test_documents_and_employee_numbers_are_not_repeated(admin_client, admin):
    _patch(admin_client, f"{USERS}{admin.pk}/", {**EMPLOYEE})
    r = _post(
        admin_client,
        USERS,
        {
            "username": "x",
            "password": STRONG,
            "id_document_type": "cpf",
            "id_document_number": "52998224725",
            "employee_number": "e-1042",
        },
    )
    assert r.status_code == 400
    assert set(r.json()) == {"id_document_number", "employee_number"}


def test_nobody_is_their_own_manager(admin_client, admin):
    r = _patch(admin_client, f"{USERS}{admin.pk}/", {"manager": admin.pk})
    assert r.status_code == 400
    assert "manager" in r.json()


def test_verticals_only_for_account_managers(admin_client, industry):
    bruno = User.objects.create_user("bruno", password=STRONG)
    r = _patch(admin_client, f"{USERS}{bruno.pk}/", {"verticals": [industry.pk]})
    assert r.json()["verticals_detail"] == []  # not an account manager
    r = _patch(
        admin_client,
        f"{USERS}{bruno.pk}/",
        {"roles": [Role.account_manager().pk], "verticals": [industry.pk]},
    )
    assert [v["name"] for v in r.json()["verticals_detail"]] == ["Industry"]
    # An account manager may work in no vertical at all
    r = _patch(admin_client, f"{USERS}{bruno.pk}/", {"verticals": []})
    assert r.json()["verticals_detail"] == []
    # Losing the role clears them
    _patch(admin_client, f"{USERS}{bruno.pk}/", {"verticals": [industry.pk]})
    r = _patch(admin_client, f"{USERS}{bruno.pk}/", {"roles": []})
    assert r.json()["verticals_detail"] == []


def test_users_filtered_by_role(admin_client):
    from .testing import make_account_manager

    make_account_manager("Bruno", "Lima", "bruno@example.com")
    r = admin_client.get(USERS, {"role": "account_manager"})
    assert [u["username"] for u in r.json()["results"]] == ["bruno"]
    r = admin_client.get(USERS, {"role": Role.administrator().pk})
    assert [u["username"] for u in r.json()["results"]] == ["ana"]


def _customer(primary, secondaries=()):
    from customers.models import Customer

    customer = Customer.objects.create(
        name="Acme", tax_id="11222333000181", primary_account_manager=primary
    )
    customer.secondary_account_managers.set(secondaries)
    return customer


def test_account_managers_of_customers_keep_the_role_and_cannot_be_deleted(admin_client):
    from .testing import make_account_manager

    bruno = make_account_manager("Bruno", "Lima", "bruno@example.com")
    carla = make_account_manager("Carla", "Mendes", "carla@example.com")
    _customer(bruno, [carla])
    for user in (bruno, carla):
        r = _patch(admin_client, f"{USERS}{user.pk}/", {"roles": []})
        assert r.status_code == 409
        assert "Account Manager role" in r.json()["detail"]
        assert admin_client.delete(f"{USERS}{user.pk}/").status_code == 409
    # Deactivating is fine (their records stay)
    assert _patch(admin_client, f"{USERS}{bruno.pk}/", {"is_active": False}).status_code == 200


def test_account_manager_list_for_everyone(client, db, industry):
    from .testing import make_account_manager

    bruno = make_account_manager("Bruno", "Lima", "bruno@example.com", [industry])
    carla = make_account_manager("Carla", "Mendes", "carla@example.com")
    carla.is_active = False
    carla.save()
    User.objects.create_user("plain", password=STRONG)
    client.force_login(User.objects.create_user("viewer", password=STRONG))
    data = client.get("/api/account-managers/").json()
    assert [m["full_name"] for m in data["results"]] == ["Bruno Lima"]  # active, with the role
    assert data["results"][0]["verticals_detail"][0]["name"] == "Industry"
    r = client.get("/api/account-managers/", {"vertical": industry.pk, "search": "lima"})
    assert [m["id"] for m in r.json()["results"]] == [bruno.pk]
    # Read-only
    assert client.post("/api/account-managers/", {}).status_code == 405


def test_users_without_a_password_are_flagged(admin_client):
    bruno = User.objects.create_user("bruno")
    bruno.set_unusable_password()
    bruno.save()
    r = admin_client.get(f"{USERS}{bruno.pk}/")
    assert r.json()["has_password"] is False


def test_users_and_roles_have_keywords(admin_client, analyst_role):
    r = _post(
        admin_client,
        USERS,
        {"username": "carla", "password": STRONG, "keywords": ["Field  Team", "SP"]},
    )
    assert r.status_code == 201, r.json()
    assert r.json()["keywords"] == ["field team", "sp"]
    assert User.objects.get(username="carla").profile.keywords == ["field team", "sp"]
    found = admin_client.get(USERS, {"search": "field"}).json()["results"]
    assert [u["username"] for u in found] == ["carla"]

    r = _patch(admin_client, f"{ROLES}{analyst_role.pk}/", {"keywords": ["Pricing"]})
    assert r.json()["keywords"] == ["pricing"]
    found = admin_client.get(ROLES, {"search": "pric"}).json()["results"]
    assert [role["name"] for role in found] == ["Analyst"]


def test_roles_list_their_members(admin_client, analyst_role, admin):
    carla = User.objects.create_user("carla", first_name="Carla", last_name="Mendes")
    analyst_role.users.add(carla, admin)
    role = next(r for r in admin_client.get(ROLES).json()["results"] if r["name"] == "Analyst")
    assert role["users_count"] == 2
    assert [(m["full_name"], m["is_active"]) for m in role["members"]] == [
        ("Ana Souza", True),
        ("Carla Mendes", True),
    ]
    assert set(role["members"][0]) == {"id", "full_name", "photo_version", "is_active"}
