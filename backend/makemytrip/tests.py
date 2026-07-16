"""
Tests for MakeMyTrip (Incabs) API integration.
"""

from unittest.mock import patch, MagicMock
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
        mock_response.json.return_value = {"response": {"distance_booked": 900}}
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

    @patch("makemytrip.views.services.call_search_api")
    def test_search_view_post(self, mock_service):
        """
        Test SearchView validates input, routes to service, and returns success response.
        """
        mock_service.return_value = {"response": {"success": True}}
        
        url = reverse("search")
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
            "trip_type_details": {
                "basic_trip_type": "OUTSTATION"
            }
        }
        
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"]["success"], True)
        mock_service.assert_called_once()

    @patch("makemytrip.views.services.call_booking_details_api")
    def test_booking_details_view_get(self, mock_service):
        """
        Test BookingDetailsView validates query params and queries service.
        """
        mock_service.return_value = {"response": {"status": "CONFIRMED"}}
        
        url = reverse("booking_details")
        response = self.client.get(url, {"order_reference_number": "NCA701853187611566"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"]["status"], "CONFIRMED")
        mock_service.assert_called_once_with(
            order_reference_number="NCA701853187611566",
            partner_reference_number=None
        )

    def test_search_view_post_invalid(self):
        """
        Test SearchView returns 400 Bad Request on invalid data.
        """
        url = reverse("search")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
