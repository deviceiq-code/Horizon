"""Keywords: every record created with a "New" form has them (customers, users, roles, verticals,
asset classes, manufacturers, average prices, eFMV analyses).

They are free words that relate and find records: lowercase, single spaces, no blanks or
duplicates, at most MAX_KEYWORDS of at most MAX_KEYWORD_LENGTH characters each, in the order
they were given. The list's search (`?search=`) also finds a record by any keyword containing
the typed text.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import CharField, F, Func, Q, Value
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from rest_framework import filters, serializers

MAX_KEYWORDS = 30
MAX_KEYWORD_LENGTH = 50


def keywords_field() -> ArrayField:
    """The model field (an empty list by default)."""
    return ArrayField(
        models.CharField(max_length=MAX_KEYWORD_LENGTH),
        default=list,
        blank=True,
        verbose_name=gettext_lazy("keywords"),
    )


def normalize_keywords(values) -> list[str]:
    """Lowercase, single spaces, no blanks or duplicates, in order. Too many → ValidationError."""
    keywords: list[str] = []
    for value in values or []:
        keyword = " ".join((value or "").split()).lower()
        if keyword and keyword not in keywords:
            keywords.append(keyword)
    if len(keywords) > MAX_KEYWORDS:
        raise serializers.ValidationError(
            _("Use at most %(max)d keywords.") % {"max": MAX_KEYWORDS}
        )
    return keywords


class KeywordsField(serializers.ListField):
    """Serializer field: a list of keywords, normalized on input (blank entries dropped)."""

    def __init__(self, **kwargs):
        kwargs.setdefault(
            "child", serializers.CharField(max_length=MAX_KEYWORD_LENGTH, allow_blank=True)
        )
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return normalize_keywords(super().to_internal_value(data))


class KeywordSearchFilter(filters.SearchFilter):
    """Regular search, plus any keyword containing the typed text. The view's
    `keywords_lookup` says where the keywords are (default "keywords"; e.g. "profile__keywords")."""

    def filter_queryset(self, request, queryset, view):
        filtered = super().filter_queryset(request, queryset, view)
        term = " ".join(request.query_params.get(self.search_param, "").split()).lower()
        if not term:
            return filtered
        lookup = getattr(view, "keywords_lookup", "keywords")
        with_keywords = queryset.annotate(
            keywords_text=Func(
                F(lookup), Value(" | "), function="array_to_string", output_field=CharField()
            )
        )
        return queryset.filter(
            Q(pk__in=filtered.values("pk"))
            | Q(pk__in=with_keywords.filter(keywords_text__contains=term).values("pk"))
        )
