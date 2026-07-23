from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LegalEntityViewSet, TripCloseoutViewSet, InvoiceViewSet

router = DefaultRouter()
router.register(r"entities", LegalEntityViewSet, basename="entity")
router.register(r"closeouts", TripCloseoutViewSet, basename="closeout")
router.register(r"invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("", include(router.urls)),
]
