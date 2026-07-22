from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    CorporateCustomerViewSet,
    RentalBookingViewSet,
    RentalChecklistViewSet,
    RentalFuelLogViewSet,
    RentalInvoiceViewSet,
    RentalPackageViewSet,
    RentalPricingRuleViewSet,
    driver_portal_today,
    rental_dashboard_summary,
)

router = DefaultRouter()
router.register("customers", CorporateCustomerViewSet)
router.register("packages", RentalPackageViewSet)
router.register("pricing-rules", RentalPricingRuleViewSet)
router.register("bookings", RentalBookingViewSet)
router.register("checklists", RentalChecklistViewSet)
router.register("fuel-logs", RentalFuelLogViewSet)
router.register("invoices", RentalInvoiceViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/summary/", rental_dashboard_summary, name="rental_dashboard_summary"),
    path("driver-portal/today/", driver_portal_today, name="driver_portal_today"),
]
