from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from partners.models import CompanyMember

from .models import Load
from .serializers import LoadSerializer


class LoadViewSet(viewsets.ModelViewSet):
    queryset = Load.objects.select_related("posted_by", "company").all()
    serializer_class = LoadSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(posted_by=self.request.user)

    def can_manage(self, load):
        user = self.request.user
        if user.is_staff:
            return True
        if load.company_id is None:
            return load.posted_by_id == user.pk
        membership = CompanyMember.objects.filter(company=load.company, user=user).first()
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
