"""Documents attached to an average price (catalogs, brochures, spec sheets…). Pure rules,
tested: which files are accepted, their stored name and how they are served."""

import mimetypes
import posixpath

# Office, OpenDocument, PDF, plain text and common images. No archives or executables, and no
# HTML/SVG (they could run scripts when opened in the browser).
ALLOWED_EXTENSIONS = frozenset(
    {
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "odt",
        "ods",
        "odp",
        "rtf",
        "txt",
        "csv",
        "jpg",
        "jpeg",
        "png",
        "gif",
        "webp",
    }
)
# The photo of the asset
PHOTO_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "gif", "webp"})
# Opened in the browser instead of downloaded
INLINE_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "gif", "webp"})
MAX_NAME = 255
MAX_DOCUMENTS = 50


def extension(name: str) -> str:
    """Lowercase extension without the dot ("" when there is none)."""
    _, ext = posixpath.splitext(name)
    return ext[1:].lower()


def clean_filename(name: str) -> str:
    """The name to show and download with: no folders, spaces collapsed, at most MAX_NAME
    characters (the extension is kept)."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = " ".join(base.split()) or "document"
    if len(base) <= MAX_NAME:
        return base
    stem, ext = posixpath.splitext(base)
    return stem[: MAX_NAME - len(ext)] + ext


def check_document(
    name: str,
    size: int,
    max_bytes: int,
    messages: dict[str, str],
    allowed: frozenset[str] = ALLOWED_EXTENSIONS,
) -> list[str]:
    """Errors for a file being uploaded (empty when accepted). `messages`: bad_type
    (with %(types)s), too_large (with %(max)s), empty. `allowed`: extensions accepted."""
    errors = []
    if extension(name) not in allowed:
        errors.append(messages["bad_type"] % {"types": ", ".join(sorted(allowed))})
    if size <= 0:
        errors.append(messages["empty"])
    elif size > max_bytes:
        errors.append(messages["too_large"] % {"max": max_bytes // (1024 * 1024)})
    return errors


def content_type_for(name: str) -> str:
    """Media type from the file name (the one sent by the browser is not trusted)."""
    guessed, _ = mimetypes.guess_type(name, strict=False)
    return guessed or "application/octet-stream"


def opens_inline(name: str) -> bool:
    return extension(name) in INLINE_EXTENSIONS
