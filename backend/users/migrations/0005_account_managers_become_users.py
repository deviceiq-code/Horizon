from django.contrib.auth.hashers import make_password
from django.db import migrations


def forward(apps, schema_editor):
    """Every user gets a profile; the "Account Manager" system role is created; every account
    manager becomes a user with that role (the user with the same email, or a new one that
    signs in once an administrator sets a password), keeping photo and verticals."""
    User = apps.get_model("auth", "User")
    Role = apps.get_model("users", "Role")
    UserProfile = apps.get_model("users", "UserProfile")
    AccountManager = apps.get_model("account_managers", "AccountManager")

    for user in User.objects.all():
        UserProfile.objects.get_or_create(user=user)

    role, _created = Role.objects.get_or_create(
        key="account_manager",
        defaults={
            "name": "Account Manager",
            "description": "Can be the account manager of customers.",
            "is_system": True,
        },
    )

    for manager in AccountManager.objects.all():
        user = User.objects.filter(email__iexact=manager.email).first()
        if user is None:
            base = manager.email.split("@")[0].lower() or "user"
            username, n = base, 2
            while User.objects.filter(username__iexact=username).exists():
                username, n = f"{base}{n}", n + 1
            user = User.objects.create(
                username=username,
                email=manager.email.lower(),
                first_name=manager.first_name,
                last_name=manager.last_name,
                password=make_password(None),  # no password yet
                is_active=True,
            )
        profile, _created = UserProfile.objects.get_or_create(user=user)
        if manager.photo and not profile.photo:
            profile.photo = manager.photo.name
            profile.save(update_fields=["photo"])
        profile.verticals.add(*manager.verticals.all())
        role.users.add(user)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_employee_profile"),
        ("account_managers", "0004_first_last_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
