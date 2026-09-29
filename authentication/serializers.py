from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

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
    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "role", "password")
        read_only_fields = ("id", "username")

    role = serializers.CharField(read_only=True)
