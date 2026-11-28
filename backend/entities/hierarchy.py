"""Head offices and groups of business entities (pure: no database).

An entity may point to its head office (`parent`); the tree under an entity without one is its
group. A head office can never be the entity itself nor one of its branches, at any depth.
"""

from collections.abc import Callable, Iterable

from customers.tax_ids import brazilian_tax_id_kind

ParentOf = Callable[[int], int | None]


def creates_cycle(entity_id: int | None, parent_id: int | None, parent_of: ParentOf) -> bool:
    """Whether making `parent_id` the head office of `entity_id` would close a cycle: walking up
    from the head office reaches the entity. A new entity (no id yet) never does."""
    if entity_id is None or parent_id is None:
        return False
    seen: set[int] = set()
    current: int | None = parent_id
    while current is not None:
        if current == entity_id:
            return True
        if current in seen:  # a cycle already there (never saved by Horizon): stop
            return False
        seen.add(current)
        current = parent_of(current)
    return False


def group_root(entity_id: int, parent_of: ParentOf) -> int:
    """The entity at the top of the group: walking up until one without a head office."""
    seen = {entity_id}
    current = entity_id
    while (parent := parent_of(current)) is not None and parent not in seen:
        seen.add(parent)
        current = parent
    return current


def descendants(root_id: int, links: Iterable[tuple[int, int | None]]) -> set[int]:
    """The entity and every branch under it, at any depth; `links` are (id, parent id)."""
    children: dict[int, list[int]] = {}
    for child, parent in links:
        if parent is not None:
            children.setdefault(parent, []).append(child)
    found = {root_id}
    pending = [root_id]
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def cnpj_root(country: str, tax_id: str) -> str | None:
    """The CNPJ's root (its first 8 characters: the company; the rest is the establishment),
    or None when it is not a Brazilian CNPJ."""
    if country != "BR" or brazilian_tax_id_kind(tax_id) != "cnpj":
        return None
    return tax_id[:8]


def is_head_office_cnpj(tax_id: str) -> bool:
    """A CNPJ whose establishment number is 0001 (usually the head office)."""
    return tax_id[8:12] == "0001"
