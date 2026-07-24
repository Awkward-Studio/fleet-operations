from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContractAllowanceViewSet,
    ContractRateViewSet,
    CorporateContractViewSet,
    CorporateCustomerViewSet,
    CustomerContactViewSet,
    DriverViewSet,
    TripViewSet,
    VehicleViewSet,
    FuelTransactionViewSet,
    availability,
    dashboard_summary,
    quote_api,
)

router = DefaultRouter()
router.register("drivers", DriverViewSet)
router.register("vehicles", VehicleViewSet)
router.register("trips", TripViewSet)
router.register("fuel-transactions", FuelTransactionViewSet, basename="fuel-transaction")
router.register("customers", CorporateCustomerViewSet, basename="customer")
router.register("contacts", CustomerContactViewSet, basename="contact")
router.register("contracts", CorporateContractViewSet, basename="contract")
router.register("rates", ContractRateViewSet, basename="rate")
router.register("allowances", ContractAllowanceViewSet, basename="allowance")

urlpatterns = [
    path("", include(router.urls)),
    path("pricing/quote/", quote_api),
    path("quote/", quote_api),
    path("availability/", availability),
    path("dashboard/summary/", dashboard_summary),
]
