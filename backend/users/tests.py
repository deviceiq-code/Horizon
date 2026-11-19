import pytest
from django.contrib.auth import get_user_model

from .models import Role
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


def _set_display(display, order="first_last"):
    from system.models import SystemSettings

    SystemSettings.objects.update_or_create(
        pk=1, defaults={"user_name_display": display, "full_name_order": order}
    )


def test_users_are_shown_as_set_in_the_system(admin_client):
    assert admin_client.get("/api/auth/me/").json()["name"] == "Ana Souza"
    _set_display("full_name", "last_first")
    assert admin_client.get("/api/auth/me/").json()["name"] == "Souza, Ana"
    # The users grid shows the full name in that order
    listed = admin_client.get(USERS).json()["results"][0]
    assert listed["full_name"] == "Souza, Ana"
    _set_display("username")
    assert admin_client.get("/api/auth/me/").json()["name"] == "ana"
    _set_display("first_name")
    assert admin_client.get("/api/auth/me/").json()["name"] == "Ana"


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
    path = bruno.profile.photo.path
    assert os.path.exists(path)
    client.force_login(admin)
    assert client.delete(f"{USERS}{bruno.pk}/").status_code == 204
    assert not os.path.exists(path)


def test_user_photo_must_be_an_image(admin_client, admin, media):
    r = _photo(admin_client, admin.pk, b"%PDF", "cv.pdf")
    assert r.status_code == 400
    assert admin_client.get("/api/auth/me/").json()["photo_version"] is None
