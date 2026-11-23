import pytest
from rest_framework import serializers

from config.keywords import MAX_KEYWORDS, KeywordsField, normalize_keywords


def test_normalize_keywords():
    given = ["  Linha   AMARELA ", "linha amarela", "", "  ", "Hidráulica"]
    assert normalize_keywords(given) == ["linha amarela", "hidráulica"]
    assert normalize_keywords(None) == []


def test_too_many_keywords():
    with pytest.raises(serializers.ValidationError):
        normalize_keywords([f"k{i}" for i in range(MAX_KEYWORDS + 1)])
    # Repeated ones do not count
    assert len(normalize_keywords(["a"] * 100 + [f"k{i}" for i in range(MAX_KEYWORDS - 1)])) == 30


def test_keywords_field():
    field = KeywordsField()
    assert field.required is False
    assert field.to_internal_value([" A ", "a", "B"]) == ["a", "b"]
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(["x" * 51])
