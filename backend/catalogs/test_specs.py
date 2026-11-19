import pytest

from .specs import SpecError, normalize_template, slugify_key, snapshot_values, suggest_values

MSG = {
    "blank_label": "blank",
    "duplicate_label": "duplicate",
    "invalid_kind": "kind",
    "too_many": "too many",
    "too_long": "too long",
    "required": "required",
    "invalid_number": "number",
    "unknown_field": "unknown",
}

HOURS = {
    "key": "hours",
    "label": "Operating hours",
    "kind": "number",
    "unit": "h",
    "required": True,
}
COLOR = {"key": "color", "label": "Color", "kind": "text", "unit": "", "required": False}


@pytest.mark.parametrize(
    ("label", "key"),
    [("Operating hours", "operating_hours"), ("Potência (cv)", "potencia_cv"), ("!!!", "field")],
)
def test_slugify_key(label, key):
    assert slugify_key(label) == key


def test_normalize_template_cleans_and_generates_keys():
    result = normalize_template(
        [
            {"label": "  Operating   hours ", "kind": "number", "unit": " h ", "required": True},
            {"label": "Memória", "kind": "text"},
        ],
        MSG,
    )
    assert result == [
        {
            "key": "operating_hours",
            "label": "Operating hours",
            "kind": "number",
            "unit": "h",
            "required": True,
        },
        {"key": "memoria", "label": "Memória", "kind": "text", "unit": "", "required": False},
    ]


def test_normalize_template_keeps_given_keys_when_labels_change():
    result = normalize_template([{"key": "hours", "label": "Hour meter", "kind": "number"}], MSG)
    assert result[0]["key"] == "hours"


def test_normalize_template_makes_keys_unique():
    result = normalize_template([{"label": "Size (m)"}, {"label": "Size m"}], MSG)
    assert [f["key"] for f in result] == ["size_m", "size_m_2"]


@pytest.mark.parametrize(
    ("fields", "error"),
    [
        ([{"label": ""}], {"0": ["blank"]}),
        ([{"label": "A"}, {"label": "a"}], {"1": ["duplicate"]}),
        ([{"label": "A", "kind": "date"}], {"0": ["kind"]}),
        ([{"label": "x" * 61}], {"0": ["too long"]}),
        ([{"label": f"F{i}"} for i in range(31)], {"__all__": ["too many"]}),
    ],
)
def test_normalize_template_errors(fields, error):
    with pytest.raises(SpecError) as exc:
        normalize_template(fields, MSG)
    assert exc.value.errors == error


def test_snapshot_values():
    snapshot = snapshot_values([HOURS, COLOR], {"hours": " 2.500,50 ".replace(".", "")}, MSG)
    assert snapshot == [{**HOURS, "value": "2500.5"}, {**COLOR, "value": ""}]


@pytest.mark.parametrize(
    ("values", "error"),
    [
        ({}, {"hours": ["required"]}),
        ({"hours": "  "}, {"hours": ["required"]}),
        ({"hours": "abc"}, {"hours": ["number"]}),
        ({"hours": "1", "color": "x" * 201}, {"color": ["too long"]}),
        ({"hours": "1", "weight": "3"}, {"weight": ["unknown"]}),
    ],
)
def test_snapshot_values_errors(values, error):
    with pytest.raises(SpecError) as exc:
        snapshot_values([HOURS, COLOR], values, MSG)
    assert exc.value.errors == error


def test_empty_template_accepts_no_values():
    assert snapshot_values([], {}, MSG) == []


# --- Suggestions --------------------------------------------------------------------------------


def _snap(**values):
    return [{"key": key, "value": value} for key, value in values.items()]


def test_suggest_values_most_used_first_and_merged_spellings():
    snapshots = [
        _snap(cpu="Intel Core Ultra 7 155H"),
        _snap(cpu="intel core  ultra 7 155h"),
        _snap(cpu="Intel Core Ultra 7 155H"),
        _snap(cpu="Intel Core i7"),
        _snap(cpu="AMD Ryzen 7", ram="16"),
        _snap(cpu=""),
        None,
    ]
    assert suggest_values(snapshots, "cpu") == [
        "Intel Core Ultra 7 155H",
        "AMD Ryzen 7",
        "Intel Core i7",
    ]


def test_suggest_values_search_every_word_ignoring_case_and_accents():
    snapshots = [_snap(gear="Câmbio automático"), _snap(gear="Câmbio manual")]
    assert suggest_values(snapshots, "gear", "cambio AUTO") == ["Câmbio automático"]
    assert suggest_values(snapshots, "gear", "manual") == ["Câmbio manual"]
    assert suggest_values(snapshots, "other") == []


def test_suggest_values_limit():
    snapshots = [_snap(cpu=f"CPU {n:02}") for n in range(30)]
    assert len(suggest_values(snapshots, "cpu", limit=20)) == 20
