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
    portal_packages,
    portal_quote,
    GuestProfileViewSet,
    CorporateApprovalPolicyViewSet,
    BookingRequestViewSet,
)

router = DefaultRouter()
router.register("customers", CorporateCustomerViewSet)
router.register("packages", RentalPackageViewSet)
router.register("pricing-rules", RentalPricingRuleViewSet)
router.register("bookings", RentalBookingViewSet)
router.register("checklists", RentalChecklistViewSet)
router.register("fuel-logs", RentalFuelLogViewSet)
router.register("invoices", RentalInvoiceViewSet)
router.register("portal/guests", GuestProfileViewSet, basename="portal_guests")
router.register("portal/approval-policies", CorporateApprovalPolicyViewSet, basename="portal_approval_policies")
router.register("portal/booking-requests", BookingRequestViewSet, basename="portal_booking_requests")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/summary/", rental_dashboard_summary, name="rental_dashboard_summary"),
    path("driver-portal/today/", driver_portal_today, name="driver_portal_today"),
    path("portal/packages/", portal_packages, name="portal_packages"),
    path("portal/quote/", portal_quote, name="portal_quote"),
]
