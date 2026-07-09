from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DriverViewSet, TripViewSet, VehicleViewSet, availability, dashboard_summary


router = DefaultRouter()
router.register("drivers", DriverViewSet)
router.register("vehicles", VehicleViewSet)
router.register("trips", TripViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("availability/", availability),
    path("dashboard/summary/", dashboard_summary),
]

