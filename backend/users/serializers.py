from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from system.models import UserNameDisplay

from .display import format_user_name, name_format
from .models import Role, user_photo_version

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "key", "name", "description", "is_system", "users_count", "created_at"]
        read_only_fields = ["id", "key", "is_system", "users_count", "created_at"]

    def get_users_count(self, obj) -> int:
        return getattr(obj, "users_count", None) or obj.users.count()

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


class UserSerializer(serializers.ModelSerializer):
    """A user of the system. `password`: required when creating, optional when editing (sets a
    new one); never returned."""

    full_name = serializers.SerializerMethodField()
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), many=True, required=False
    )
    roles_detail = serializers.SerializerMethodField()
    # Changes with every new photo (null without one); the image is at /api/users/<id>/photo/
    photo_version = serializers.SerializerMethodField()
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

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
            "password",
            "last_login",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "roles_detail",
            "photo_version",
            "last_login",
            "date_joined",
        ]

    def get_full_name(self, obj) -> str:
        # Name and last name in the order set in the system settings (always the full name)
        fmt = self.context.setdefault("name_format", name_format())
        return format_user_name(
            "", obj.first_name, obj.last_name, UserNameDisplay.FULL_NAME, fmt[1]
        )

    def get_photo_version(self, obj) -> str | None:
        return user_photo_version(obj)

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
        return attrs

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)
        password = validated_data.pop("password", "")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance
