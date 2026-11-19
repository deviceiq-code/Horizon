"""Documents of an average price: pure rules and API."""

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from .documents import check_document, clean_filename, content_type_for, extension, opens_inline
from .models import AveragePrice, PriceDocument
from .testing import URL, _new_version, _payload, _post

MESSAGES = {"bad_type": "type %(types)s", "too_large": "large %(max)s", "empty": "empty"}
MB = 1024 * 1024

# --- Pure rules ---------------------------------------------------------------------------------


def test_extension_and_clean_filename():
    assert extension("Catalog.PDF") == "pdf"
    assert extension("noext") == ""
    assert clean_filename("C:\\\\Users\\\\x\\\\My   catalog.pdf") == "My catalog.pdf"
    assert clean_filename("/tmp/a/b.pdf") == "b.pdf"
    long = "x" * 300 + ".pdf"
    assert len(clean_filename(long)) == 255
    assert clean_filename(long).endswith(".pdf")
    assert clean_filename("   ") == "document"


def test_check_document():
    assert check_document("a.pdf", 10, MB, MESSAGES) == []
    assert check_document("a.exe", 10, MB, MESSAGES)[0].startswith("type ")
    assert check_document("a.svg", 10, MB, MESSAGES)[0].startswith("type ")
    assert check_document("a.pdf", 2 * MB, MB, MESSAGES) == ["large 1"]
    assert check_document("a.pdf", 0, MB, MESSAGES) == ["empty"]


def test_content_type_and_inline():
    assert content_type_for("a.pdf") == "application/pdf"
    assert content_type_for("a.xlsx").startswith("application/vnd.openxmlformats")
    assert content_type_for("a.unknown") == "application/octet-stream"
    assert opens_inline("a.PDF") and opens_inline("a.png")
    assert not opens_inline("a.docx")


# --- API ----------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _upload(client, row_id, name="Catalog 2026.pdf", content=b"%PDF-1.4 test"):
    return client.post(f"{URL}{row_id}/documents/", {"file": SimpleUploadedFile(name, content)})


def _docs(client, row_id):
    return client.get(f"{URL}{row_id}/documents/").json()


def test_upload_list_and_download(logged_client, price, user, media):
    r = _upload(logged_client, price.pk)
    assert r.status_code == 201, r.json()
    doc = r.json()
    assert doc["name"] == "Catalog 2026.pdf"
    assert doc["size"] == 13
    assert doc["content_type"] == "application/pdf"
    assert doc["opens_inline"] is True
    assert doc["uploaded_by_name"] == "Ana Souza"
    # Stored under a random name, in the row's folder
    stored = PriceDocument.objects.get(pk=doc["id"]).file.name
    assert stored.startswith(f"price-documents/{price.lineage}/")
    assert "Catalog" not in stored

    assert [d["id"] for d in _docs(logged_client, price.pk)] == [doc["id"]]
    assert logged_client.get(URL).json()["results"][0]["documents_count"] == 1

    r = logged_client.get(f"{URL}{price.pk}/documents/{doc['id']}/download/")
    assert r.status_code == 200
    assert b"".join(r.streaming_content) == b"%PDF-1.4 test"
    assert r["Content-Disposition"].startswith("attachment")
    assert "Catalog 2026.pdf" in r["Content-Disposition"]
    r = logged_client.get(f"{URL}{price.pk}/documents/{doc['id']}/download/", {"inline": "1"})
    assert r["Content-Disposition"].startswith("inline")


def test_office_files_are_never_inline(logged_client, price):
    doc = _upload(logged_client, price.pk, "Specs.docx", b"PK..").json()
    r = logged_client.get(f"{URL}{price.pk}/documents/{doc['id']}/download/", {"inline": "1"})
    assert r["Content-Disposition"].startswith("attachment")


def test_rejected_uploads(logged_client, price, settings):
    r = _upload(logged_client, price.pk, "tool.exe", b"MZ")
    assert r.status_code == 400
    assert "not accepted" in r.json()["file"][0]
    assert _upload(logged_client, price.pk, "empty.pdf", b"").status_code == 400
    settings.PRICE_DOCUMENT_MAX_MB = 1
    r = _upload(logged_client, price.pk, "big.pdf", b"x" * (MB + 1))
    assert r.json()["file"] == ["The file is too large (maximum 1 MB)."]
    r = logged_client.post(f"{URL}{price.pk}/documents/", {})
    assert r.status_code == 400 and "file" in r.json()
    assert PriceDocument.objects.count() == 0


def test_documents_are_shared_by_every_version(logged_client, catalog, price):
    doc = _upload(logged_client, price.pk).json()
    second = _new_version(logged_client, catalog, price.pk, "110000")
    assert AveragePrice.objects.get(pk=second).lineage == price.lineage
    assert [d["id"] for d in _docs(logged_client, second)] == [doc["id"]]
    # Erasing a version keeps them; erasing the last one removes them (and their files)
    logged_client.delete(f"{URL}{second}/")
    assert len(_docs(logged_client, price.pk)) == 1
    assert os.path.exists(PriceDocument.objects.get().file.path)


@pytest.mark.django_db(transaction=True)
def test_files_are_removed_with_their_documents(logged_client, catalog, price):
    first = _upload(logged_client, price.pk).json()
    second = _upload(logged_client, price.pk, "photo.png", b"\x89PNG").json()
    paths = {d.pk: d.file.path for d in PriceDocument.objects.all()}
    assert all(os.path.exists(p) for p in paths.values())

    assert logged_client.delete(f"{URL}{price.pk}/documents/{first['id']}/").status_code == 204
    assert not os.path.exists(paths[first["id"]])
    # Erasing the only version erases the row's remaining documents
    logged_client.delete(f"{URL}{price.pk}/")
    assert PriceDocument.objects.count() == 0
    assert not os.path.exists(paths[second["id"]])


def test_documents_of_another_row_are_not_reachable(logged_client, catalog, price):
    doc = _upload(logged_client, price.pk).json()
    other = _post(logged_client, _payload(catalog, model="Other")).json()["id"]
    assert logged_client.get(f"{URL}{other}/documents/{doc['id']}/download/").status_code == 404
    assert logged_client.delete(f"{URL}{other}/documents/{doc['id']}/").status_code == 404


def test_no_uploads_to_a_deleted_price(logged_client, price):
    logged_client.delete(f"{URL}{price.pk}/history/")
    assert _upload(logged_client, price.pk).status_code == 409


def test_documents_require_login(price):
    assert Client().get(f"{URL}{price.pk}/documents/").status_code == 403


# --- Photo --------------------------------------------------------------------------------------


def _photo(client, row_id, name="front.jpg", content=b"\xff\xd8\xff jpeg"):
    return client.post(f"{URL}{row_id}/photo/", {"file": SimpleUploadedFile(name, content)})


@pytest.mark.django_db(transaction=True)
def test_photo_set_shown_replaced_and_removed(logged_client, catalog, price):
    assert logged_client.get(f"{URL}{price.pk}/photo/").status_code == 404
    first = _photo(logged_client, price.pk).json()["photo_id"]
    # Served inline (shown in the page), returned with the row, not listed as a document
    r = logged_client.get(f"{URL}{price.pk}/photo/")
    assert r.status_code == 200
    assert r["Content-Type"] == "image/jpeg"
    assert b"".join(r.streaming_content) == b"\xff\xd8\xff jpeg"
    assert not r["Content-Disposition"].startswith("attachment")
    listed = logged_client.get(URL).json()["results"][0]
    assert (listed["photo_id"], listed["documents_count"]) == (first, 0)
    assert _docs(logged_client, price.pk) == []
    # Shared by the next version; replacing removes the old file
    second_version = _new_version(logged_client, catalog, price.pk, "110000")
    old_path = PriceDocument.objects.get(pk=first).file.path
    second = _photo(logged_client, second_version, "side.png", b"\x89PNG").json()["photo_id"]
    assert PriceDocument.objects.filter(is_photo=True).count() == 1
    assert not os.path.exists(old_path)
    assert logged_client.get(f"{URL}{price.pk}/").json()["photo_id"] == second
    # Removed
    assert logged_client.delete(f"{URL}{price.pk}/photo/").status_code == 204
    assert logged_client.get(f"{URL}{price.pk}/").json()["photo_id"] is None
    assert logged_client.delete(f"{URL}{price.pk}/photo/").status_code == 404


def test_photo_must_be_an_image(logged_client, price):
    r = _photo(logged_client, price.pk, "catalog.pdf", b"%PDF")
    assert r.status_code == 400
    assert "jpeg, jpg, png, webp" in r.json()["file"][0].replace("gif, ", "")


def test_photo_is_not_a_document(logged_client, price):
    photo = _photo(logged_client, price.pk).json()["photo_id"]
    url = f"{URL}{price.pk}/documents/{photo}/"
    assert logged_client.delete(url).status_code == 404
    assert logged_client.get(f"{url}download/").status_code == 404


def test_no_photo_changes_on_a_deleted_price(logged_client, price):
    logged_client.delete(f"{URL}{price.pk}/history/")
    assert _photo(logged_client, price.pk).status_code == 409
