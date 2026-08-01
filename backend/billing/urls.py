from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LegalEntityViewSet, TripCloseoutViewSet, InvoiceViewSet,
    PaymentReceiptViewSet, PaymentAllocationViewSet, CreditNoteViewSet,
    OTASettlementBatchViewSet
)

router = DefaultRouter()
router.register(r"entities", LegalEntityViewSet, basename="entity")
router.register(r"closeouts", TripCloseoutViewSet, basename="closeout")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"receipts", PaymentReceiptViewSet, basename="receipt")
router.register(r"allocations", PaymentAllocationViewSet, basename="allocation")
router.register(r"credit-notes", CreditNoteViewSet, basename="credit-note")
router.register(r"ota-settlements", OTASettlementBatchViewSet, basename="ota-settlement")

urlpatterns = [
    path("", include(router.urls)),
]
