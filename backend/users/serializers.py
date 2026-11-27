import re
from datetime import date

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import UserNameDisplay
from catalogs.models import Vertical
from config.environments import KNOWN as ENVIRONMENTS
from config.environments import current as current_environment
from config.keywords import KeywordsField
from customers.tax_ids import is_valid_cpf, normalize_tax_id

from .display import context_format, format_user_name, full_name_in
from .models import (
    IdDocumentType,
    Role,
    UserProfile,
    is_account_manager,
    user_photo_version,
)

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()
    # Who has the role, by name: {id, full_name, photo_version, is_active} (read-only)
    members = serializers.SerializerMethodField()
    keywords = KeywordsField()

    class Meta:
        model = Role
        fields = [
            "id",
            "key",
            "name",
            "description",
            "keywords",
            "is_system",
            "users_count",
            "members",
            "created_at",
        ]
        read_only_fields = ["id", "key", "is_system", "users_count", "members", "created_at"]

    def get_users_count(self, obj) -> int:
        return getattr(obj, "users_count", None) or obj.users.count()

    def get_members(self, obj) -> list[dict]:
        members = [
            {
                "id": user.id,
                "full_name": full_name_in(self.context, user),
                "photo_version": user_photo_version(user),
                "is_active": user.is_active,
            }
            for user in obj.users.all()
        ]
        return sorted(members, key=lambda m: m["full_name"].lower())

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_system:
            raise serializers.ValidationError(_("System roles cannot be changed."))
        return attrs

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        duplicates = Role.objects.filter(name__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("A role with this name already exists."))
        return value


PROFILE_FIELDS = [
    "environments",
    "id_document_type",
    "id_document_number",
    "employee_number",
    "nationality",
    "birth_date",
    "job_title",
    "department",
    "work_location",
    "manager",
    "hire_date",
    "phone",
    "mobile_phone",
    "verticals",
    "keywords",
]


class UserSerializer(serializers.ModelSerializer):
    """A user of the system with their employee data (kept in the profile). `password`:
    required when creating, optional when editing (sets a new one); never returned.
    `verticals` (business verticals an account manager works in) only count for users with the
    "Account Manager" role: they are cleared otherwise."""

    full_name = serializers.SerializerMethodField()
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), many=True, required=False
    )
    roles_detail = serializers.SerializerMethodField()
    # Changes with every new photo (null without one); the image is at /api/users/<id>/photo/
    photo_version = serializers.SerializerMethodField()
    # False for users created without a password (e.g. former account managers)
    has_password = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

    # Employee data (UserProfile)
    id_document_type = serializers.ChoiceField(
        choices=IdDocumentType.choices,
        source="profile.id_document_type",
        required=False,
        allow_blank=True,
    )
    id_document_number = serializers.CharField(
        source="profile.id_document_number", max_length=40, required=False, allow_blank=True
    )
    employee_number = serializers.CharField(
        source="profile.employee_number", max_length=30, required=False, allow_blank=True
    )
    nationality = serializers.CharField(
        source="profile.nationality", max_length=2, required=False, allow_blank=True
    )
    birth_date = serializers.DateField(source="profile.birth_date", required=False, allow_null=True)
    job_title = serializers.CharField(
        source="profile.job_title", max_length=100, required=False, allow_blank=True
    )
    department = serializers.CharField(
        source="profile.department", max_length=100, required=False, allow_blank=True
    )
    work_location = serializers.CharField(
        source="profile.work_location", max_length=100, required=False, allow_blank=True
    )
    manager = serializers.PrimaryKeyRelatedField(
        source="profile.manager", queryset=User.objects.all(), required=False, allow_null=True
    )
    manager_name = serializers.SerializerMethodField()
    hire_date = serializers.DateField(source="profile.hire_date", required=False, allow_null=True)
    phone = serializers.CharField(
        source="profile.phone", max_length=30, required=False, allow_blank=True
    )
    mobile_phone = serializers.CharField(
        source="profile.mobile_phone", max_length=30, required=False, allow_blank=True
    )
    # Environments the user may sign in to (Live, Development…; at least one)
    environments = serializers.ListField(
        source="profile.environments",
        child=serializers.ChoiceField(choices=ENVIRONMENTS),
        required=False,
        allow_empty=False,
    )
    verticals = serializers.PrimaryKeyRelatedField(
        source="profile.verticals", queryset=Vertical.objects.all(), many=True, required=False
    )
    verticals_detail = serializers.SerializerMethodField()
    keywords = KeywordsField(source="profile.keywords")

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "is_active",
            "roles",
            "roles_detail",
            "photo_version",
            "has_password",
            "password",
            *PROFILE_FIELDS,
            "manager_name",
            "verticals_detail",
            "last_login",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "roles_detail",
            "photo_version",
            "has_password",
            "manager_name",
            "verticals_detail",
            "last_login",
            "date_joined",
        ]

    def get_full_name(self, obj) -> str:
        # Name and last name in the viewer's order (always the full name)
        fmt = context_format(self.context)
        return format_user_name(
            "", obj.first_name, obj.last_name, UserNameDisplay.FULL_NAME, fmt[1]
        )

    def get_photo_version(self, obj) -> str | None:
        return user_photo_version(obj)

    def get_has_password(self, obj) -> bool:
        return obj.has_usable_password()

    def get_manager_name(self, obj) -> str | None:
        manager = obj.profile.manager
        return full_name_in(self.context, manager) if manager else None

    def get_verticals_detail(self, obj) -> list[dict]:
        verticals = sorted(obj.profile.verticals.all(), key=lambda v: v.name.lower())
        return [{"id": v.id, "name": v.name, "is_enabled": v.is_enabled} for v in verticals]

    def get_roles_detail(self, obj) -> list[dict]:
        roles = sorted(obj.roles.all(), key=lambda r: r.name.lower())
        return [{"id": r.id, "key": r.key, "name": r.name, "is_system": r.is_system} for r in roles]

    def validate_username(self, value):
        value = value.strip()
        duplicates = User.objects.filter(username__iexact=value)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(_("A user with this username already exists."))
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        password = attrs.get("password") or ""
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": [_("This field is required.")]})
        if password:
            candidate = self.instance or User(
                username=attrs.get("username", ""),
                email=attrs.get("email", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password, candidate)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        attrs["profile"] = self._validate_profile(attrs.get("profile", {}))
        return attrs

    def _validate_profile(self, data: dict) -> dict:
        errors: dict[str, list[str]] = {}
        current = self.instance.profile if self.instance is not None else None

        def value(field, default=""):
            if field in data:
                return data[field]
            return getattr(current, field) if current is not None else default

        for field in (
            "employee_number",
            "job_title",
            "department",
            "work_location",
            "phone",
            "mobile_phone",
        ):
            if field in data:
                data[field] = " ".join((data[field] or "").split())

        # Identity document: type and number go together; CPF checked
        if "id_document_number" in data:
            data["id_document_number"] = normalize_tax_id(data["id_document_number"] or "")
        kind, number = value("id_document_type"), value("id_document_number")
        if number and not kind:
            errors["id_document_type"] = [_("Choose the document type.")]
        elif kind and not number:
            errors["id_document_number"] = [_("Enter the document number.")]
        elif kind == IdDocumentType.CPF and number and not is_valid_cpf(number):
            errors["id_document_number"] = [_("Invalid CPF.")]
        others = (
            UserProfile.objects.exclude(user=self.instance)
            if self.instance
            else (UserProfile.objects.all())
        )
        if number and others.filter(id_document_type=kind, id_document_number=number).exists():
            errors["id_document_number"] = [_("Another user has this document.")]
        employee = value("employee_number")
        if employee and others.filter(employee_number__iexact=employee).exists():
            errors["employee_number"] = [_("Another user has this employee number.")]

        if "nationality" in data:
            data["nationality"] = (data["nationality"] or "").strip().upper()
            if data["nationality"] and not re.fullmatch(r"[A-Z]{2}", data["nationality"]):
                errors["nationality"] = [_("Choose a country.")]

        birth, hire = value("birth_date", None), value("hire_date", None)
        if birth and birth >= date.today():
            errors["birth_date"] = [_("The birth date must be in the past.")]
        if birth and hire and hire < birth:
            errors["hire_date"] = [_("The hire date cannot be before the birth date.")]

        manager = data.get("manager")
        if manager is not None and self.instance is not None and manager.pk == self.instance.pk:
            errors["manager"] = [_("A user cannot be their own manager.")]

        if "environments" in data:
            # In the order they are offered, each once
            data["environments"] = [e for e in ENVIRONMENTS if e in data["environments"]]
            request = self.context.get("request")
            working_in = current_environment()
            if (
                request is not None
                and self.instance is not None
                and self.instance.pk == request.user.pk
                and working_in not in data["environments"]
            ):
                errors["environments"] = [
                    _("You cannot remove the environment you are working in from yourself.")
                ]

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password")
        profile_data = validated_data.pop("profile", {})
        user = User(**validated_data)
        user.set_password(password)
        user.save()  # the profile is created with the user
        user.roles.set(roles)
        self._save_profile(user, profile_data)
        return user

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        password = validated_data.pop("password", "")
        profile_data = validated_data.pop("profile", {})
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        self._save_profile(instance, profile_data)
        return instance

    def _save_profile(self, user, data: dict) -> None:
        profile = UserProfile.for_user(user)
        verticals = data.pop("verticals", None)
        for field, value in data.items():
            setattr(profile, field, value)
        profile.save()
        # Verticals only count for account managers
        if not is_account_manager(user):
            profile.verticals.clear()
        elif verticals is not None:
            profile.verticals.set(verticals)
        # Read the profile again in the response
        user.profile = profile


class AccountManagerSerializer(serializers.ModelSerializer):
    """An account manager as pickers and lists show it."""

    full_name = serializers.SerializerMethodField()
    photo_version = serializers.SerializerMethodField()
    verticals_detail = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "photo_version",
            "verticals_detail",
        ]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return full_name_in(self.context, obj)

    def get_photo_version(self, obj) -> str | None:
        return user_photo_version(obj)

    def get_verticals_detail(self, obj) -> list[dict]:
        verticals = sorted(obj.profile.verticals.all(), key=lambda v: v.name.lower())
        return [{"id": v.id, "name": v.name, "is_enabled": v.is_enabled} for v in verticals]
