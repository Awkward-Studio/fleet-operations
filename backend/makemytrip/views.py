"""
Views for MakeMyTrip (Incabs) API integration.
"""

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request

from makemytrip.serializers import (
    SearchSerializer,
    SearchMarketPlaceSerializer,
    BlockSerializer,
    PaidSerializer,
    CancelSerializer,
    CustomerLandedSerializer,
    BookingDetailsQuerySerializer,
)
from makemytrip import services


class SearchView(APIView):
    """
    API View to handle MakeMyTrip Cab Search requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Search requests to the MakeMyTrip API.
        """
        serializer = SearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_search_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class SearchMarketPlaceView(APIView):
    """
    API View to handle MakeMyTrip Cab B2B Marketplace Search requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Marketplace Search requests to the MakeMyTrip API.
        """
        serializer = SearchMarketPlaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_search_marketplace_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class BlockView(APIView):
    """
    API View to handle MakeMyTrip Cab Blocking requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Block requests to the MakeMyTrip API.
        """
        serializer = BlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_block_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class PaidView(APIView):
    """
    API View to handle MakeMyTrip Cab Booking Confirmation/Payment requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Confirmation requests to the MakeMyTrip API.
        """
        serializer = PaidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_paid_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class CancelView(APIView):
    """
    API View to handle MakeMyTrip Cab Booking Cancellation requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Cancellation requests to the MakeMyTrip API.
        """
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_cancel_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class CustomerLandedView(APIView):
    """
    API View to handle MakeMyTrip Customer Landed/Arrived notification requests.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate and proxy Customer Landed requests to the MakeMyTrip API.
        """
        serializer = CustomerLandedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = services.call_customer_landed_api(serializer.validated_data)
        return Response(response_data, status=status.HTTP_200_OK)


class BookingDetailsView(APIView):
    """
    API View to query MakeMyTrip Booking Details.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request: Request, *args, **kwargs) -> Response:
        """
        Validate query params and fetch booking details from MakeMyTrip API.
        """
        serializer = BookingDetailsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        order_ref = serializer.validated_data["order_reference_number"]
        partner_ref = serializer.validated_data.get("partner_reference_number")
        
        response_data = services.call_booking_details_api(
            order_reference_number=order_ref,
            partner_reference_number=partner_ref
        )
        return Response(response_data, status=status.HTTP_200_OK)
