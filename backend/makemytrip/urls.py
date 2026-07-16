"""
URL routing configuration for the MakeMyTrip (Incabs) integration app.
"""

from django.urls import path
from makemytrip.views import (
    SearchView,
    SearchMarketPlaceView,
    BlockView,
    PaidView,
    CancelView,
    CustomerLandedView,
    BookingDetailsView,
)

urlpatterns = [
    # Search Endpoints
    path("partnersearchendpoint", SearchView.as_view(), name="search"),
    path("partnersearchendpoint/", SearchView.as_view()),
    
    # B2B Marketplace Search Endpoints
    path("partnermarketplacesearchendpoint", SearchMarketPlaceView.as_view(), name="search_marketplace"),
    path("partnermarketplacesearchendpoint/", SearchMarketPlaceView.as_view()),
    
    # Block Endpoints
    path("partnerblockendpoint", BlockView.as_view(), name="block"),
    path("partnerblockendpoint/", BlockView.as_view()),
    
    # Confirm Booking (Paid) Endpoints
    path("partnerpaidendpoint", PaidView.as_view(), name="paid"),
    path("partnerpaidendpoint/", PaidView.as_view()),
    
    # Cancellation Endpoints
    path("partnercancelendpoint", CancelView.as_view(), name="cancel"),
    path("partnercancelendpoint/", CancelView.as_view()),
    
    # Customer Landed/Arrived Endpoints
    path("partnercustomerarrivedendpoint", CustomerLandedView.as_view(), name="customer_landed"),
    path("partnercustomerarrivedendpoint/", CustomerLandedView.as_view()),
    
    # Query Booking Details Endpoints
    path("api/partner/v1/booking/details", BookingDetailsView.as_view(), name="booking_details"),
    path("api/partner/v1/booking/details/", BookingDetailsView.as_view()),
]
