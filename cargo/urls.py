from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LoadViewSet
from .city_views import CitySearchView

router = DefaultRouter()
router.register("loads", LoadViewSet, basename="loads")

urlpatterns = [path("cities/", CitySearchView.as_view(), name="city-search"), path("", include(router.urls))]
