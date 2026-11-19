"""Specification templates (per asset class) and the values filled in for an asset.

A template is a list of fields, e.g. for the asset class Excavators:

    [{"key": "operating_hours", "label": "Operating hours", "kind": "number", "unit": "h",
      "required": True}, ...]

An asset (e.g. an average price row) stores a *snapshot*: each field with the value given, so
later template changes never alter past records. Pure functions; no database.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

KINDS = ("text", "number")
MAX_FIELDS = 30
MAX_LABEL = 60
MAX_UNIT = 20
MAX_TEXT_VALUE = 200


class SpecError(ValueError):
    """Invalid template or values. `errors` maps a field key (or "__all__") to messages."""

    def __init__(self, errors: dict[str, list[str]]):
        super().__init__(errors)
        self.errors = errors


def slugify_key(label: str) -> str:
    """ "Operating hours (h)" → "operating_hours_h" (ASCII, stable identifier)."""
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_label.lower()).strip("_") or "field"


def normalize_template(fields: list[dict], messages: dict[str, str]) -> list[dict]:
    """Validate and clean a template. Keys are kept when given (so renaming a label keeps the
    key), otherwise generated from the label. Raises SpecError with messages per position.

    `messages` provides the (translated) texts: blank_label, duplicate_label, invalid_kind,
    too_many, too_long.
    """
    if len(fields) > MAX_FIELDS:
        raise SpecError({"__all__": [messages["too_many"]]})
    errors: dict[str, list[str]] = {}
    seen_labels: set[str] = set()
    seen_keys: set[str] = set()
    result = []
    for index, field in enumerate(fields):
        label = " ".join(str(field.get("label", "")).split())
        unit = " ".join(str(field.get("unit", "") or "").split())
        kind = field.get("kind", "text")
        problems = []
        if not label:
            problems.append(messages["blank_label"])
        elif label.lower() in seen_labels:
            problems.append(messages["duplicate_label"])
        if len(label) > MAX_LABEL or len(unit) > MAX_UNIT:
            problems.append(messages["too_long"])
        if kind not in KINDS:
            problems.append(messages["invalid_kind"])
        if problems:
            errors[str(index)] = problems
            continue
        seen_labels.add(label.lower())
        key = slugify_key(str(field.get("key") or label))
        base, n = key, 2
        while key in seen_keys:
            key, n = f"{base}_{n}", n + 1
        seen_keys.add(key)
        result.append(
            {
                "key": key,
                "label": label,
                "kind": kind,
                "unit": unit,
                "required": bool(field.get("required", False)),
            }
        )
    if errors:
        raise SpecError(errors)
    return result


def snapshot_values(
    template: list[dict], values: dict[str, object], messages: dict[str, str]
) -> list[dict]:
    """Check the values given for a template and return the snapshot to store.

    Empty values are allowed for optional fields (kept as ""). Numbers are stored as decimal
    strings ("2500.5"); comma or dot accepted. `messages`: required, invalid_number, too_long,
    unknown_field.
    """
    known = {field["key"] for field in template}
    errors: dict[str, list[str]] = {
        key: [messages["unknown_field"]] for key in values if key not in known
    }
    snapshot = []
    for field in template:
        raw = values.get(field["key"], "")
        text = " ".join(str(raw if raw is not None else "").split())
        if not text:
            if field["required"]:
                errors[field["key"]] = [messages["required"]]
        elif field["kind"] == "number":
            try:
                number = Decimal(text.replace(",", "."))
                if not number.is_finite():
                    raise InvalidOperation
                text = format(number.normalize(), "f")
            except InvalidOperation:
                errors[field["key"]] = [messages["invalid_number"]]
        elif len(text) > MAX_TEXT_VALUE:
            errors[field["key"]] = [messages["too_long"]]
        snapshot.append({**field, "value": text})
    if errors:
        raise SpecError(errors)
    return snapshot
