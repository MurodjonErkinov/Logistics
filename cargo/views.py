from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from django.db import transaction
from django.db.models import Q, Count, Exists, OuterRef, Subquery
from django.utils import timezone

from partners.models import CompanyMember

from .models import Load, LoadClaim
from .serializers import LoadSerializer

LIST_LIMIT = 500
MAX_IDS = 200


class LoadViewSet(viewsets.ModelViewSet):
    queryset = Load.objects.select_related("posted_by", "company", "telegram_entry__post").all()
    serializer_class = LoadSerializer

    def get_queryset(self):
        user = self.request.user
        claims = LoadClaim.objects.filter(load_id=OuterRef("pk"), driver_id=user.pk if user.is_authenticated else None)
        queryset = super().get_queryset().annotate(
            claim_count=Count("claims", distinct=True),
            is_claimed=Exists(claims),
            claimed_at=Subquery(claims.values("created_at")[:1]),
        ).order_by("-created_at", "-id")
        available = Q(telegram_entry__expires_at__isnull=True) | Q(telegram_entry__expires_at__gt=timezone.now())
        # Drivers can still open loads they have taken after the listing expires.
        queryset = queryset.filter(available | Q(is_claimed=True))
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("claimed") == "1":
            if not user.is_authenticated:
                raise NotAuthenticated()
            if user.role != "driver":
                raise PermissionDenied("Only drivers can view taken loads.")
            queryset = queryset.filter(is_claimed=True).order_by("-claimed_at", "-id")
        if params.get("status") in (Load.Status.OPEN, Load.Status.CLOSED):
            queryset = queryset.filter(status=params["status"])
        if params.get("mine") == "1":
            if not self.request.user.is_authenticated:
                raise NotAuthenticated()
            owned = CompanyMember.objects.active().filter(user=self.request.user, role=CompanyMember.Role.OWNER).values("company_id")
            queryset = queryset.filter(Q(posted_by=self.request.user) | Q(company_id__in=owned))
        if params.get("ids") is not None:
            ids = [int(value) for value in params["ids"].split(",")[:MAX_IDS] if value.isdigit()]
            queryset = queryset.filter(pk__in=ids)
        # The frontend filters client-side; bound the response to the newest loads.
        return queryset[:LIST_LIMIT]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "map_locations"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(posted_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="map-locations")
    def map_locations(self, request, pk=None):
        from .map_locations import load_map_points
        return Response(load_map_points(self.get_object()))

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        if request.user.role != "driver" or not request.user.is_active:
            raise PermissionDenied("Only active drivers can take loads.")
        if request.data.get("confirmed_contact") is not True:
            raise ValidationError({"confirmed_contact": "Yuk egasi bilan gaplashganingizni tasdiqlang."})
        load = self.get_object()
        with transaction.atomic():
            locked = Load.objects.select_for_update(of=("self",)).select_related("telegram_entry").get(pk=load.pk)
            if locked.posted_by_id == request.user.pk:
                raise ValidationError({"detail": "O‘zingiz joylagan yukni ololmaysiz."})
            existing = LoadClaim.objects.filter(load=locked, driver=request.user).exists()
            entry = getattr(locked, "telegram_entry", None)
            if not existing and (locked.status != Load.Status.OPEN or (entry and entry.expires_at and entry.expires_at <= timezone.now())):
                raise ValidationError({"detail": "Bu yuk e’loni endi aktual emas."})
            _, created = LoadClaim.objects.get_or_create(load=locked, driver=request.user)
        return Response(self.get_serializer(self.get_queryset().get(pk=load.pk)).data, status=201 if created else 200)

    def can_manage(self, load):
        user = self.request.user
        if user.is_staff:
            return True
        if load.company_id is None:
            return load.posted_by_id == user.pk
        membership = CompanyMember.objects.active().filter(company=load.company, user=user).first()
        return membership is not None and (
            membership.role == CompanyMember.Role.OWNER
            or (load.posted_by_id == user.pk and membership.can_post_cargo)
        )

    def perform_update(self, serializer):
        if not self.can_manage(serializer.instance):
            raise PermissionDenied("You cannot edit this load.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.can_manage(instance):
            raise PermissionDenied("You cannot delete this load.")
        instance.delete()
