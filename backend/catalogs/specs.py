"""Specification templates (per asset class) and the values filled in for an asset.

A template is a list of fields, e.g. for the asset class Excavators:

    [{"key": "operating_hours", "label": "Operating hours", "kind": "number", "unit": "h",
      "required": True, "options": []}, ...]

Kinds: text, number (with a unit), boolean (yes/no), choice (one of the template's `options`)
and rating (0–5 stars in half steps). Values are always stored as text: numbers "2500.5",
booleans "true"/"false", choices the option as written in the template, ratings "3.5".

An asset (e.g. an average price row) stores a *snapshot*: each field with the value given, so
later template changes never alter past records. Pure functions; no database.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

KINDS = ("text", "number", "boolean", "choice", "rating")
MAX_FIELDS = 30
MAX_OPTIONS = 50
MAX_OPTION = 100
RATING_MAX = Decimal(5)
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
    too_many, too_long, no_options, duplicate_option, too_many_options.
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
        options = _clean_options(field.get("options")) if kind == "choice" else []
        if kind == "choice":
            folded = [option.casefold() for option in options]
            if not options:
                problems.append(messages["no_options"])
            elif len(set(folded)) != len(folded):
                problems.append(messages["duplicate_option"])
            if len(options) > MAX_OPTIONS:
                problems.append(messages["too_many_options"])
            if any(len(option) > MAX_OPTION for option in options):
                problems.append(messages["too_long"])
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
                # Only numbers have a unit
                "unit": unit if kind == "number" else "",
                "required": bool(field.get("required", False)),
                "options": options,
            }
        )
    if errors:
        raise SpecError(errors)
    return result


def _clean_options(raw) -> list[str]:
    """The list items of a choice field: single spaces, blanks dropped, order kept."""
    if not isinstance(raw, list):
        return []
    return [text for text in (" ".join(str(item).split()) for item in raw) if text]


TRUE_WORDS = {"true", "yes", "1", "sim", "si", "y"}
FALSE_WORDS = {"false", "no", "0", "nao", "não", "n"}


def snapshot_values(
    template: list[dict], values: dict[str, object], messages: dict[str, str]
) -> list[dict]:
    """Check the values given for a template and return the snapshot to store.

    Empty values are allowed for optional fields (kept as ""). Numbers are stored as decimal
    strings ("2500.5"); comma or dot accepted. `messages`: required, invalid_number, too_long,
    unknown_field, invalid_boolean, invalid_choice, invalid_rating.
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
        elif field["kind"] == "boolean":
            word = text.casefold()
            if word in TRUE_WORDS:
                text = "true"
            elif word in FALSE_WORDS:
                text = "false"
            else:
                errors[field["key"]] = [messages["invalid_boolean"]]
        elif field["kind"] == "choice":
            # The option as written in the template (typed in any letter case)
            match = next(
                (o for o in field.get("options", []) if o.casefold() == text.casefold()), None
            )
            if match is None:
                errors[field["key"]] = [messages["invalid_choice"]]
            else:
                text = match
        elif field["kind"] == "rating":
            try:
                stars = Decimal(text.replace(",", "."))
                if not (0 <= stars <= RATING_MAX) or (stars * 2) % 1 != 0:
                    raise InvalidOperation
                text = format(stars.normalize(), "f")
            except InvalidOperation:
                errors[field["key"]] = [messages["invalid_rating"]]
        elif len(text) > MAX_TEXT_VALUE:
            errors[field["key"]] = [messages["too_long"]]
        snapshot.append({**field, "value": text})
    if errors:
        raise SpecError(errors)
    return snapshot


def _fold(text: str) -> str:
    """Lowercase without accents, for comparing values ("Câmbio" == "cambio")."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def suggest_values(
    snapshots: Iterable[list[dict]], key: str, search: str = "", limit: int = 20
) -> list[str]:
    """Values already used for a template field, to offer while typing.

    `snapshots`: stored specs of several records. Values that differ only in case or accents
    count as one, shown with their most used spelling. Every word typed in `search` must appear.
    Most used first, then alphabetically.
    """
    words = _fold(search).split()
    spellings: dict[str, Counter[str]] = {}
    for snapshot in snapshots:
        for item in snapshot or []:
            if item.get("key") != key:
                continue
            value = " ".join(str(item.get("value") or "").split())
            if not value:
                continue
            folded = _fold(value)
            if all(word in folded for word in words):
                spellings.setdefault(folded, Counter())[value] += 1
    ranked = sorted(
        spellings.values(),
        key=lambda counts: (-sum(counts.values()), _fold(counts.most_common(1)[0][0])),
    )
    # most_common keeps the first spelling seen on ties
    return [counts.most_common(1)[0][0] for counts in ranked[:limit]]
