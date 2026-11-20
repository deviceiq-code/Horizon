"""How users are shown in the app (System settings: username, first name or full name, and
the order of the full name). Use `display_name` wherever a user appears."""

from system.models import FullNameOrder, SystemSettings, UserNameDisplay


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


def name_format() -> tuple[str, str]:
    settings = SystemSettings.current()
    return settings.user_name_display, settings.full_name_order


def display_name(user, fmt: tuple[str, str] | None = None) -> str | None:
    """`fmt`: from name_format(), to read the settings once for many users."""
    if user is None:
        return None
    display, order = fmt or name_format()
    return format_user_name(user.username, user.first_name, user.last_name, display, order)


def display_name_in(context: dict, user) -> str | None:
    """display_name for serializers: the settings are read once per serializer tree."""
    if "name_format" not in context:
        context["name_format"] = name_format()
    return display_name(user, context["name_format"])


def full_name_in(context: dict, user) -> str:
    """The user's full name in the order set in the system settings (always the full name, e.g.
    for account managers in lists); read once per serializer tree."""
    if "name_format" not in context:
        context["name_format"] = name_format()
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
