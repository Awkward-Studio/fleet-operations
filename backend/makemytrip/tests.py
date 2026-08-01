"""
Tests for MakeMyTrip (Incabs) API integration.
"""

from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from makemytrip.serializers import (
    SearchSerializer,
    SearchMarketPlaceSerializer,
    BlockSerializer,
    PaidSerializer,
    CancelSerializer,
    CustomerLandedSerializer,
)
from makemytrip import services
from makemytrip.models import MMTBookingLifecycle, MMTLifecycleEvent
from billing.models import OTABookingSnapshot
from fleet.models import TripStatus


class MakeMyTripSerializerTestCase(APITestCase):
    """
    Test cases for request serializers.
    """

    def test_search_serializer_valid(self):
        """
        Test SearchSerializer with valid schema data.
        """
        data = {
            "source": {
                "address": "DLF Place, Gurgaon, Haryana, India",
                "latitude": 28.48968,
                "longitude": 77.09224,
                "city": "Gurgaon"
            },
            "destination": {
                "address": "Jaipur, Rajasthan, India",
                "latitude": 26.91243,
                "longitude": 75.78727,
                "city": "Jaipur"
            },
            "trip_type": "ONE_WAY",
            "start_time": "2021-02-08 19:55:00",
            "search_id": "56c5c8a269702d3a1b0b0000",
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
            "search_tags": ["B2C"],
            "trip_type_details": {
                "basic_trip_type": "OUTSTATION",
                "airport_type": "NONE"
            }
        }
        serializer = SearchSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_search_serializer_invalid(self):
        """
        Test SearchSerializer fails validation with missing required fields.
        """
        data = {
            "trip_type": "ONE_WAY"
        }
        serializer = SearchSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("source", serializer.errors)
        self.assertIn("destination", serializer.errors)

    def test_block_serializer_valid_with_addon_case_insensitive(self):
        """
        Test BlockSerializer validates and normalizes addon 'Value'.
        """
        data = {
            "distance": 230,
            "fare_details": {
                "base_fare": 2010.0,
                "total_driver_charges": 0.0,
                "state_tax": 100.0,
                "toll_charges": 100.0,
                "night_charges": 0.0,
                "total_fare": 2410.0
            },
            "selected_add_ons": [
                {
                    "name": "LANGUAGES",
                    "amount": 100.0,
                    "value": "Hindi,English"  # lowercase value
                }
            ],
            "search_id": "56c5c8a269702d3a1b0b0000",
            "vehicle_type": "sedan",
            "vehicle_subcategory": "basic",
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
            "verification_code": "2748",
            "trip_end_verification_code": "5433",
            "vehicle_details": {
                "type": "hatchback",
                "subcategory": "basic",
                "combustion_type": "Petrol",
                "model": "Swift",
                "carrier": True,
                "make_year_type": "Older",
                "make_year": 2017,
                "cancellation_rule": "SUPER_FLEXI"
            },
            "source": {
                "address": "DLF Place",
                "latitude": 28.48968,
                "longitude": 77.09224
            },
            "destination": {
                "address": "Jaipur",
                "latitude": 26.91243,
                "longitude": 75.78727
            },
            "trip_type_details": {
                "basic_trip_type": "OUTSTATION"
            }
        }
        serializer = BlockSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Verify normalizing "value" to "Value" works
        self.assertEqual(serializer.validated_data["selected_add_ons"][0]["Value"], "Hindi,English")


class MakeMyTripServicesTestCase(APITestCase):
    """
    Test cases for the services layer outbound HTTP requests.
    """

    @patch("makemytrip.services.requests.request")
    def test_call_search_api_success(self, mock_request):
        """
        Test call_search_api returns mock response successfully.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"response": {"distance_booked": 900}}'
        mock_request.return_value = mock_response

        payload = {"dummy": "data"}
        res = services.call_search_api(payload)
        
        self.assertEqual(res["response"]["distance_booked"], 900)
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(kwargs["method"], "POST")
        self.assertIn("partnersearchendpoint", kwargs["url"])

    @patch("makemytrip.services.requests.request")
    def test_call_api_connection_error(self, mock_request):
        """
        Test service functions raise MakeMyTripAPIException when connection fails.
        """
        mock_request.side_effect = requests.exceptions.ConnectionError("DNS failure")
        
        from makemytrip.exceptions import MakeMyTripAPIException
        with self.assertRaises(MakeMyTripAPIException) as context:
            services.call_search_api({})
            
        self.assertEqual(context.exception.status_code, status.HTTP_502_BAD_GATEWAY)


class MakeMyTripViewsTestCase(APITestCase):
    """
    Test cases for views and HTTP routing.
    """

    def _search_payload(self, search_id="56c5c8a269702d3a1b0b0000"):
        return {
            "source": {
                "address": "DLF Place, Gurgaon, Haryana, India",
                "latitude": 28.48968,
                "longitude": 77.09224,
                "city": "Gurgaon"
            },
            "destination": {
                "address": "Jaipur, Rajasthan, India",
                "latitude": 26.91243,
                "longitude": 75.78727,
                "city": "Jaipur"
            },
            "trip_type": "ONE_WAY",
            "start_time": "2026-08-08 19:55:00",
            "end_time": "2026-08-08 23:55:00",
            "search_id": search_id,
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
            "one_way_distance": 230,
            "trip_type_details": {
                "basic_trip_type": "OUTSTATION"
            }
        }

    def _block_payload(self, search_id="56c5c8a269702d3a1b0b0000"):
        return {
            "distance": 230,
            "fare_details": {
                "base_fare": 2010.0,
                "total_driver_charges": 0.0,
                "state_tax": 100.0,
                "toll_charges": 100.0,
                "night_charges": 0.0,
                "total_fare": 2410.0
            },
            "selected_add_ons": [],
            "search_id": search_id,
            "vehicle_type": "sedan",
            "vehicle_subcategory": "basic",
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
            "verification_code": "2748",
            "trip_end_verification_code": "5433",
            "vehicle_details": {
                "type": "sedan",
                "subcategory": "basic",
                "combustion_type": "Petrol",
                "model": "Dzire",
                "carrier": False,
                "make_year_type": "Newer",
                "make_year": 2022,
                "cancellation_rule": "SUPER_FLEXI"
            },
            "source": {
                "address": "DLF Place, Gurgaon, Haryana, India",
                "latitude": 28.48968,
                "longitude": 77.09224,
                "city": "Gurgaon"
            },
            "destination": {
                "address": "Jaipur, Rajasthan, India",
                "latitude": 26.91243,
                "longitude": 75.78727,
                "city": "Jaipur"
            },
            "trip_type_details": {
                "basic_trip_type": "OUTSTATION"
            }
        }

    def _paid_payload(self, partner_reference_number, order_reference_number="MMT-ORDER-1"):
        return {
            "passenger": {
                "name": "MMT Passenger",
                "email": "guest@example.com",
                "phone_number": "+919999999999",
                "country_code": "91",
            },
            "partner_reference_number": partner_reference_number,
            "order_reference_number": order_reference_number,
            "total_fare": 2410.0,
            "amount_to_be_collected": 0.0,
            "platform_fee": 100.0,
            "booking_gst": 100.0,
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
        }

    def test_search_view_post(self):
        """
        Test SearchView validates input, persists lifecycle state, and returns success response.
        """
        url = reverse("search")
        data = self._search_payload()
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"]["success"], True)
        self.assertEqual(MMTBookingLifecycle.objects.get().search_id, data["search_id"])
        self.assertEqual(MMTLifecycleEvent.objects.count(), 1)

    def test_booking_details_view_get(self):
        """
        Test BookingDetailsView validates query params and returns persisted state.
        """
        self.client.post(reverse("search"), self._search_payload(), format="json")
        block = self.client.post(reverse("block"), self._block_payload(), format="json")
        partner_ref = block.data["response"]["partner_reference_number"]
        paid = self.client.post(reverse("paid"), self._paid_payload(partner_ref), format="json")
        self.assertEqual(paid.status_code, status.HTTP_200_OK)

        url = reverse("booking_details")
        response = self.client.get(url, {"order_reference_number": "MMT-ORDER-1"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"]["status"], "PAID")
        self.assertEqual(response.data["response"]["order_reference_number"], "MMT-ORDER-1")

    def test_search_view_post_invalid(self):
        """
        Test SearchView returns 400 Bad Request on invalid data.
        """
        url = reverse("search")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_block_retry_returns_same_partner_reference(self):
        self.client.post(reverse("search"), self._search_payload(), format="json")
        first = self.client.post(reverse("block"), self._block_payload(), format="json")
        second = self.client.post(reverse("block"), self._block_payload(), format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["response"]["partner_reference_number"], second.data["response"]["partner_reference_number"])
        self.assertEqual(MMTBookingLifecycle.objects.count(), 1)
        self.assertEqual(MMTLifecycleEvent.objects.filter(event_type="BLOCK").count(), 1)

    def test_paid_creates_trip_and_ota_snapshot_once_on_retry(self):
        self.client.post(reverse("search"), self._search_payload(), format="json")
        block = self.client.post(reverse("block"), self._block_payload(), format="json")
        partner_ref = block.data["response"]["partner_reference_number"]

        first = self.client.post(reverse("paid"), self._paid_payload(partner_ref), format="json")
        second = self.client.post(reverse("paid"), self._paid_payload(partner_ref), format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["response"]["trip_id"], second.data["response"]["trip_id"])
        lifecycle = MMTBookingLifecycle.objects.get(order_reference_number="MMT-ORDER-1")
        trip = lifecycle.trip
        self.assertEqual(trip.ota_source, "MMT")
        self.assertEqual(trip.customer_name, "MMT Passenger")
        self.assertEqual(trip.pricing_snapshot["verification_code"], "2748")
        self.assertEqual(trip.quoted_total_amount, Decimal("2410.00"))
        snapshot = OTABookingSnapshot.objects.get(trip=trip)
        self.assertEqual(snapshot.provider_booking_id, "MMT-ORDER-1")
        self.assertEqual(snapshot.net_expected, Decimal("2310.00"))
        self.assertEqual(MMTLifecycleEvent.objects.filter(event_type="PAID").count(), 1)

    def test_cancel_marks_trip_cancelled_and_preserves_paid_history(self):
        self.client.post(reverse("search"), self._search_payload(), format="json")
        block = self.client.post(reverse("block"), self._block_payload(), format="json")
        partner_ref = block.data["response"]["partner_reference_number"]
        self.client.post(reverse("paid"), self._paid_payload(partner_ref), format="json")

        cancel_payload = {
            "partner_reference_number": partner_ref,
            "order_reference_number": "MMT-ORDER-1",
            "cancelled_by": "Customer",
            "cancellation_reason": "Plan changed",
            "cancelled_at": "2026-08-08T18:00:00.000Z",
            "vendor_id": "PARTNER_CODE",
            "partner_name": "GOMMT",
        }
        response = self.client.post(reverse("cancel"), cancel_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lifecycle = MMTBookingLifecycle.objects.get(order_reference_number="MMT-ORDER-1")
        self.assertEqual(lifecycle.status, "CANCELLED")
        self.assertEqual(lifecycle.trip.status, TripStatus.CANCELLED)
        self.assertIn("paid", lifecycle.normalized_facts)
        self.assertIn("cancel", lifecycle.normalized_facts)
