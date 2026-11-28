"""GET /api/search/?q=&category=: the centralized search (search/registry.py)."""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .access import module_view
from .registry import PROVIDERS, Provider

# All the categories: a few of each; one category: up to this many
PER_CATEGORY = 5
MAX_RESULTS = 50


def _filtered(provider: Provider, request, q: str):
    """The provider's list, as its own grid would search it — None when the user may not."""
    view = module_view(provider.view, request, {"search": q})
    if view is None:
        return None
    return view.filter_queryset(view.get_queryset())


@api_view(["GET"])
def search(request):
    """Every category the user may open, each with how many records match (`count`) and the
    first ones (`results`); ?category= gives more of one. Empty or one-letter queries: nothing."""
    q = " ".join(request.query_params.get("q", "").split())
    category = request.query_params.get("category", "")
    if len(q) < 2:
        return Response({"q": q, "categories": []})
    limit = MAX_RESULTS if category else PER_CATEGORY
    categories = []
    for provider in PROVIDERS:
        queryset = _filtered(provider, request, q)
        if queryset is None:
            continue
        count = queryset.count()
        if not count:
            continue
        wanted = not category or category == provider.key
        rows = list(queryset[:limit]) if wanted else []
        categories.append(
            {
                "key": provider.key,
                "count": count,
                "results": [provider.result(row, request) for row in rows],
            }
        )
    return Response({"q": q, "categories": categories})
