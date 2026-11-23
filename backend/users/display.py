"""How users are shown in the app — each viewer's own preference (Settings: username, first
name or full name, and the order of the full name). Use `display_name_in` (serializers) or
`display_name` wherever a user appears."""

from accounts.models import FullNameOrder, UserNameDisplay, UserPreferences


def format_user_name(
    username: str, first_name: str, last_name: str, display: str, order: str
) -> str:
    """Pure: the name to show. Falls back to the full name, then the username, when the
    chosen part is empty."""
    first, last = " ".join(first_name.split()), " ".join(last_name.split())
    if display == UserNameDisplay.USERNAME:
        return username
    if display == UserNameDisplay.FIRST_NAME and first:
        return first
    if first and last:
        return f"{last}, {first}" if order == FullNameOrder.LAST_FIRST else f"{first} {last}"
    return first or last or username


DEFAULT_FORMAT = (UserNameDisplay.FULL_NAME.value, FullNameOrder.FIRST_LAST.value)


def name_format(viewer=None) -> tuple[str, str]:
    """How `viewer` (who is looking) wants users shown; the default without one."""
    if viewer is None or not getattr(viewer, "is_authenticated", False):
        return DEFAULT_FORMAT
    preferences = UserPreferences.for_user(viewer)
    return preferences.user_name_display, preferences.full_name_order


def context_format(context: dict) -> tuple[str, str]:
    """The viewer's format for a serializer tree (the request's user), read once."""
    if "name_format" not in context:
        request = context.get("request")
        context["name_format"] = name_format(getattr(request, "user", None))
    return context["name_format"]


def display_name(user, fmt: tuple[str, str] | None = None, viewer=None) -> str | None:
    """`fmt`: from name_format(), to read the preferences once for many users; else `viewer`'s."""
    if user is None:
        return None
    display, order = fmt or name_format(viewer)
    return format_user_name(user.username, user.first_name, user.last_name, display, order)


def display_name_in(context: dict, user) -> str | None:
    """display_name for serializers: as the request's user wants it (read once per tree)."""
    return display_name(user, context_format(context))


def full_name_in(context: dict, user) -> str:
    """The user's full name in the viewer's order (always the full name, e.g. for account
    managers in lists); read once per serializer tree."""
    context_format(context)
    return format_user_name(
        user.username,
        user.first_name,
        user.last_name,
        UserNameDisplay.FULL_NAME,
        context["name_format"][1],
    )


def person_ref(context: dict, user) -> dict:
    """{"id", "full_name"} of a user, as other modules show account managers."""
    return {"id": user.id, "full_name": full_name_in(context, user)}
