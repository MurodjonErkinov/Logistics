from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Company, CompanyMember


class CompanySerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Company
        fields = (
            "id", "name", "phone_number", "email", "address", "created_by",
            "created_by_username", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_by_username", "created_at", "updated_at")


class CompanyMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    company_id = serializers.IntegerField(source="company.id", read_only=True)

    class Meta:
        model = CompanyMember
        fields = (
            "id", "company_id", "user_id", "user_username", "username",
            "role", "can_post_cargo", "joined_at",
        )
        read_only_fields = ("id", "company_id", "user_id", "user_username", "joined_at")

    def validate(self, attrs):
        if self.instance is None:
            username = attrs.get("username")
            if not username:
                raise serializers.ValidationError({"username": "This field is required."})
            user = get_user_model().objects.filter(username=username, is_active=True).first()
            if user is None:
                raise serializers.ValidationError({"username": "Active user not found."})
            company = self.context["company"]
            if CompanyMember.objects.filter(company=company, user=user).exists():
                raise serializers.ValidationError({"username": "User is already a member."})
            attrs["user"] = user
            attrs.pop("username", None)
        elif "username" in attrs:
            raise serializers.ValidationError({"username": "Member user cannot be changed. Remove and add a membership instead."})
        return attrs

    def create(self, validated_data):
        return CompanyMember.objects.create(company=self.context["company"], **validated_data)
