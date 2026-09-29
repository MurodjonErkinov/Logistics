from rest_framework import serializers

from partners.models import CompanyMember

from .models import Load


class LoadSerializer(serializers.ModelSerializer):
    posted_by_username = serializers.CharField(source="posted_by.username", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    display_text = serializers.CharField(read_only=True)

    class Meta:
        model = Load
        fields = (
            "id", "origin", "destination", "cargo_name", "vehicle_type", "weight_tons",
            "is_price_negotiable", "price_amount", "currency", "contact_phone",
            "alternate_phone", "pickup_date", "notes", "status", "posted_by",
            "posted_by_username", "company", "company_name", "display_text",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "posted_by", "posted_by_username", "company_name", "display_text",
            "created_at", "updated_at",
        )

    def validate(self, attrs):
        company = attrs.get("company")
        request = self.context["request"]
        if self.instance is None:
            if company is not None and not request.user.is_staff:
                membership = CompanyMember.objects.filter(company=company, user=request.user).first()
                if membership is None or not (membership.role == CompanyMember.Role.OWNER or membership.can_post_cargo):
                    raise serializers.ValidationError({"company": "You cannot post for this company."})
        elif "company" in attrs and company != self.instance.company:
            raise serializers.ValidationError({"company": "The posting identity cannot be changed."})

        negotiable = attrs.get(
            "is_price_negotiable",
            self.instance.is_price_negotiable if self.instance else True,
        )
        price = attrs.get("price_amount", self.instance.price_amount if self.instance else None)
        if not negotiable and price is None:
            raise serializers.ValidationError({"price_amount": "Price is required when it is not negotiable."})
        return attrs
