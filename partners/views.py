from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Company, CompanyMember
from .serializers import CompanyMemberSerializer, CompanySerializer, InvitationSerializer


def is_owner(company, user):
    return user.is_staff or company.memberships.active().filter(user=user, role=CompanyMember.Role.OWNER).exists()


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.select_related("created_by").prefetch_related("memberships").all().order_by("id")
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("list", "retrieve") and (not self.request.user.is_staff or self.request.query_params.get("mine") == "1"):
            queryset = queryset.filter(memberships__user=self.request.user, memberships__accepted_at__isnull=False)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        company = serializer.save(created_by=self.request.user)
        CompanyMember.objects.create(
            company=company, user=self.request.user,
            role=CompanyMember.Role.OWNER, can_post_cargo=True, accepted_at=timezone.now(),
        )

    def perform_update(self, serializer):
        if not is_owner(serializer.instance, self.request.user):
            raise PermissionDenied("Only a company owner can edit this company.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_owner(instance, self.request.user):
            raise PermissionDenied("Only a company owner can delete this company.")
        instance.delete()


class CompanyMemberViewSet(viewsets.ModelViewSet):
    serializer_class = CompanyMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_company(self):
        company = get_object_or_404(Company, pk=self.kwargs["company_pk"])
        user = self.request.user
        if not user.is_staff and not company.memberships.active().filter(user=user).exists():
            raise PermissionDenied("You are not a member of this company.")
        if self.request.method not in permissions.SAFE_METHODS and not is_owner(company, user):
            raise PermissionDenied("Only a company owner can manage members.")
        return company

    def get_queryset(self):
        return CompanyMember.objects.filter(company=self.get_company()).select_related("user", "company").order_by("id")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = self.get_company()
        return context

    def perform_update(self, serializer):
        member = serializer.instance
        if member.accepted_at and member.role == CompanyMember.Role.OWNER and serializer.validated_data.get("role") == CompanyMember.Role.MEMBER:
            if member.company.memberships.active().filter(role=CompanyMember.Role.OWNER).count() == 1:
                raise ValidationError({"role": "The last owner cannot be demoted."})
        serializer.save()

    def perform_destroy(self, instance):
        if instance.accepted_at and instance.role == CompanyMember.Role.OWNER:
            if instance.company.memberships.active().filter(role=CompanyMember.Role.OWNER).count() == 1:
                raise ValidationError({"role": "The last owner cannot be removed."})
        instance.delete()


class InvitationViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Pending company invitations of the current user: accept or decline (DELETE)."""

    serializer_class = InvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CompanyMember.objects.filter(user=self.request.user, accepted_at__isnull=True).select_related("company").order_by("-joined_at")

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        invitation = self.get_object()
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
        return Response(status=204)
