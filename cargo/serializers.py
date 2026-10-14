from rest_framework import serializers

from partners.models import CompanyMember

from .models import Load
from .vehicle_catalog import BODY_CHOICES


class LoadSerializer(serializers.ModelSerializer):
    posted_by_username = serializers.CharField(source="posted_by.username", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    display_text = serializers.CharField(read_only=True)
    source_url = serializers.SerializerMethodField()

    def get_source_url(self, obj):
        entry = getattr(obj, "telegram_entry", None)
        return entry.post.source_url if entry else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request is not None and not request.user.is_authenticated:
            data["contact_phone"] = ""
            data["alternate_phone"] = ""
            data["display_text"] = ""
        return data

    class Meta:
        model = Load
        fields = (
            "id", "origin", "destination", "origin_lat", "origin_lon", "destination_lat", "destination_lon", "cargo_name", "vehicle_type", "vehicle_kind", "vehicle_size", "weight_tons",
            "is_price_negotiable", "price_amount", "price_basis", "currency", "contact_phone",
            "alternate_phone", "pickup_date", "notes", "status", "posted_by",
            "posted_by_username", "company", "company_name", "display_text", "source_url",
            "created_at", "updated_at",
        )
        extra_kwargs = {"vehicle_type": {"required": False}}
        read_only_fields = (
            "id", "posted_by", "posted_by_username", "company_name", "display_text", "source_url",
            "created_at", "updated_at",
        )

    def validate(self, attrs):
        if "vehicle_type" in attrs and "vehicle_kind" not in attrs:
            attrs["vehicle_kind"] = ""
            attrs["vehicle_size"] = ""
        kind = attrs.get("vehicle_kind", getattr(self.instance, "vehicle_kind", ""))
        size = attrs.get("vehicle_size", getattr(self.instance, "vehicle_size", ""))
        if kind and ("vehicle_kind" in attrs or "vehicle_size" in attrs):
            attrs["vehicle_type"] = dict(BODY_CHOICES)[kind] + (f" · {size}" if size and size != "CUSTOM" else "")
        for point in ("origin", "destination"):
            lat = attrs.get(f"{point}_lat", getattr(self.instance, f"{point}_lat", None))
            lon = attrs.get(f"{point}_lon", getattr(self.instance, f"{point}_lon", None))
            if (lat is None) != (lon is None):
                raise serializers.ValidationError({point: "Provide both latitude and longitude."})
        if not attrs.get("vehicle_type", getattr(self.instance, "vehicle_type", "")):
            raise serializers.ValidationError({"vehicle_type": "Choose a body type or enter the required transport."})
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
