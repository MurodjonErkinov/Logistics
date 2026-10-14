from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

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


class RegistrationSerializer(UserSerializer):
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    role = serializers.CharField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "password")


class ProfileSerializer(UserSerializer):
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "is_staff", "password", "current_password")
        read_only_fields = ("id", "username", "is_staff")

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
