from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from .verification import normalize_phone, register_verified_user
from .password_reset import reset_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "is_active", "is_staff", "password")
        read_only_fields = ("id",)

    def validate_password(self, value):
        password_validation.validate_password(value, self.instance)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "This field is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for name, value in validated_data.items():
            setattr(instance, name, value)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance


class PhoneVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=32)

    def validate_phone_number(self, value):
        return normalize_phone(value)


class PasswordResetSerializer(PhoneVerificationSerializer):
    verification_id = serializers.UUIDField(write_only=True)
    verification_code = serializers.RegexField(r"^[0-9]{6}$", write_only=True, error_messages={"invalid": "Telegramdan olingan 6 xonali kodni kiriting."})
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Parollar bir xil bo‘lishi kerak."})
        return attrs

    def create(self, validated_data):
        reset_password(validated_data)
        return validated_data


class RegistrationSerializer(UserSerializer):
    phone_number = serializers.CharField(max_length=32, required=True)
    verification_id = serializers.UUIDField(write_only=True)
    verification_code = serializers.RegexField(r"^[0-9]{6}$", write_only=True, error_messages={"invalid": "Telegramdan olingan 6 xonali kodni kiriting."})

    def validate_phone_number(self, value):
        return normalize_phone(value)

    def create(self, validated_data):
        return register_verified_user(validated_data)

    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    role = serializers.ChoiceField(
        choices=[User.Role.DRIVER, User.Role.DISPATCHER],
        default=User.Role.DISPATCHER,
    )

    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "password", "verification_id", "verification_code")


class ProfileSerializer(UserSerializer):
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "is_staff", "password", "current_password")
        # The phone is verified via Telegram at registration and identifies the
        # account for password reset, so users cannot change it here.
        read_only_fields = ("id", "username", "is_staff", "phone_number")

    role = serializers.CharField(read_only=True)

    def validate(self, attrs):
        current = attrs.pop("current_password", "")
        if attrs.get("password") and not self.instance.check_password(current):
            raise serializers.ValidationError({"current_password": "Enter your current password correctly."})
        return super().validate(attrs)


class SecureTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        user = User.objects.filter(pk=token.payload.get(api_settings.USER_ID_CLAIM)).first()
        if user is None or token.payload.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed("Session expired. Please sign in again.")
        return super().validate(attrs)
