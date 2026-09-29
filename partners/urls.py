from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompanyMemberViewSet, CompanyViewSet

router = DefaultRouter()
router.register("companies", CompanyViewSet, basename="companies")

member_list = CompanyMemberViewSet.as_view({"get": "list", "post": "create"})
member_detail = CompanyMemberViewSet.as_view({
    "get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy",
})

urlpatterns = [
    path("companies/<int:company_pk>/members/", member_list, name="company-members-list"),
    path("companies/<int:company_pk>/members/<int:pk>/", member_detail, name="company-members-detail"),
    path("", include(router.urls)),
]
