"""People's photos (account managers, users): a small square picture (the browser crops and
resizes it), stored in MEDIA_ROOT under a random name and served through the API.

Models use `PhotoMixin` with a `photo` FileField; views answer /<id>/photo/ with
`photo_response`.
"""

import posixpath

from django.db import transaction
from django.http import FileResponse, Http404
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from pricing.documents import PHOTO_EXTENSIONS, check_document, clean_filename, content_type_for

# The browser sends a small square picture; this only guards against oversized files
MAX_PHOTO_MB = 5


def photo_version(photo) -> str | None:
    """Changes with every new photo (its random file name); None without one."""
    return posixpath.splitext(posixpath.basename(photo.name))[0] if photo else None


class PhotoMixin:
    """For models with a `photo` FileField: replace/remove it and delete the old file."""

    def set_photo(self, content) -> None:
        """Store a new photo (replacing the previous file) or remove it (content=None)."""
        old = self.photo.name
        if content is None:
            self.photo = ""
        else:
            self.photo.save(content.name, content, save=False)
        self.save()
        remove_file_later(self.photo.storage, old)


def remove_file_later(storage, name: str) -> None:
    """Delete a stored file once the current transaction is committed."""
    if name:
        transaction.on_commit(lambda: storage.delete(name))


def photo_response(request, obj, *, can_change: bool, saved_data=None):
    """GET: the image. POST (multipart, "file"): set or replace it. DELETE: remove it.
    `saved_data(obj)`: the body answered after a POST."""
    if request.method == "GET":
        if not obj.photo:
            raise Http404
        try:
            handle = obj.photo.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        return FileResponse(handle, content_type=content_type_for(obj.photo.name))
    if not can_change:
        return Response(
            {"detail": _("You do not have permission to perform this action.")},
            status=status.HTTP_403_FORBIDDEN,
        )
    if request.method == "DELETE":
        if not obj.photo:
            raise Http404
        obj.set_photo(None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    upload = request.FILES.get("file")
    if upload is None:
        return Response(
            {"file": [_("Choose a file to upload.")]}, status=status.HTTP_400_BAD_REQUEST
        )
    errors = check_document(
        clean_filename(upload.name or ""),
        upload.size,
        MAX_PHOTO_MB * 1024 * 1024,
        {
            "bad_type": _("This type of file is not accepted. Accepted: %(types)s."),
            "too_large": _("The file is too large (maximum %(max)s MB)."),
            "empty": _("The file is empty."),
        },
        PHOTO_EXTENSIONS,
    )
    if errors:
        return Response({"file": errors}, status=status.HTTP_400_BAD_REQUEST)
    obj.set_photo(upload)
    body = saved_data(obj) if saved_data else {"photo_version": photo_version(obj.photo)}
    return Response(body, status=status.HTTP_201_CREATED)
