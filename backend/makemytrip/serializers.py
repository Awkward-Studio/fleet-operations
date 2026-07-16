"""
Serializers for MakeMyTrip (Incabs) API request validation.
"""

from rest_framework import serializers


class LocationSerializer(serializers.Serializer):
    """
    Serializer for source, destination, and stopover locations.
    """
    address = serializers.CharField(help_text="Full address text")
    latitude = serializers.FloatField(help_text="Latitude coordinate")
    longitude = serializers.FloatField(help_text="Longitude coordinate")
    city = serializers.CharField(required=False, allow_blank=True, help_text="City name")


class StopoverSerializer(serializers.Serializer):
    """
    Serializer for stopover points.
    """
    address = serializers.CharField(help_text="Stopover address text")
    latitude = serializers.FloatField(help_text="Stopover latitude coordinate")
    longitude = serializers.FloatField(help_text="Stopover longitude coordinate")


class TripTypeDetailsSerializer(serializers.Serializer):
    """
    Serializer for detailed trip classifications.
    """
    basic_trip_type = serializers.CharField(help_text="Basic type e.g., OUTSTATION/TRAIN/AIRPORT")
    airport_type = serializers.CharField(required=False, allow_blank=True, default="NONE", help_text="Airport type e.g., NONE/PICKUP/DROP")
    train_type = serializers.CharField(required=False, allow_blank=True, default="NONE", help_text="Train type e.g., NONE/PICKUP/DROP")


class SearchSerializer(serializers.Serializer):
    """
    Serializer for POST /partnersearchendpoint/ requests.
    """
    source = LocationSerializer(help_text="Pickup location details")
    destination = LocationSerializer(help_text="Dropoff location details")
    trip_type = serializers.CharField(help_text="Type of trip e.g., ONE_WAY/ROUND_TRIP")
    start_time = serializers.CharField(help_text="Trip start time format YYYY-MM-DD HH:MM:SS")
    end_time = serializers.CharField(required=False, allow_blank=True, help_text="Trip end time format YYYY-MM-DD HH:MM:SS")
    search_id = serializers.CharField(help_text="Unique search identifier")
    vendor_id = serializers.CharField(help_text="Vendor identifier code")
    partner_name = serializers.CharField(help_text="Partner name e.g., GOMMT")
    search_tags = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Search tags")
    one_way_distance = serializers.FloatField(required=False, help_text="One way distance in km")
    is_instant_search = serializers.BooleanField(required=False, default=False, help_text="Is instant booking search")
    corporate_id = serializers.CharField(required=False, allow_blank=True, help_text="Corporate identifier")
    stopovers = StopoverSerializer(many=True, required=False, default=list, help_text="List of stopover locations")
    mandatory_inclusions = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Mandatory inclusions")
    mandatory_exclusions = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Mandatory exclusions")
    trip_type_details = TripTypeDetailsSerializer(help_text="Additional trip type details")
    expressway_distance = serializers.FloatField(required=False, help_text="Expressway distance in km")
    expressway_duration = serializers.FloatField(required=False, help_text="Expressway duration in minutes")
    eligible_cancellation_policy = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Eligible cancellation policies")


class SearchItemSerializer(serializers.Serializer):
    """
    Serializer for individual search items in B2B marketplace search.
    """
    supplier_id = serializers.CharField(help_text="Supplier unique identifier")
    search_id = serializers.CharField(help_text="Search unique identifier")


class SearchMarketPlaceSerializer(serializers.Serializer):
    """
    Serializer for POST /partnermarketplacesearchendpoint/ requests.
    """
    source = LocationSerializer(help_text="Pickup location details")
    stopovers = StopoverSerializer(many=True, required=False, default=list, help_text="Stopovers list")
    trip_type = serializers.CharField(help_text="Type of trip e.g., LOCAL_RENTAL")
    start_time = serializers.CharField(help_text="Trip start time format YYYY-MM-DD HH:MM:SS")
    end_time = serializers.CharField(help_text="Trip end time format YYYY-MM-DD HH:MM:SS")
    partner_name = serializers.CharField(help_text="Partner name e.g., GOMMT")
    search_tags = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Search tags")
    package_id = serializers.CharField(required=False, allow_blank=True, help_text="Package ID if local rental")
    mandatory_inclusions = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Mandatory inclusions")
    mandatory_exclusions = serializers.ListField(child=serializers.CharField(), required=False, default=list, help_text="Mandatory exclusions")
    fare_type = serializers.CharField(required=False, allow_blank=True, help_text="Fare type e.g., CONTRACTED")
    features = serializers.CharField(required=False, allow_blank=True, help_text="Features JSON string")
    trip_type_details = TripTypeDetailsSerializer(help_text="Additional trip type details")
    # searches = SearchItemSerializer(many=True, help_text="List of searches per supplier")


class PartnerOfferAppliedSerializer(serializers.Serializer):
    """
    Serializer for partner discount offers.
    """
    type = serializers.CharField(help_text="Discount type")
    coupon = serializers.CharField(help_text="Coupon code")
    amount = serializers.FloatField(help_text="Offer amount value")


class BlockFareDetailsSerializer(serializers.Serializer):
    """
    Serializer for fare details in blocking requests.
    """
    base_fare = serializers.FloatField(help_text="Base fare charge")
    total_driver_charges = serializers.FloatField(default=0.0, help_text="Driver charges")
    state_tax = serializers.FloatField(default=0.0, help_text="State tax amount")
    toll_charges = serializers.FloatField(default=0.0, help_text="Toll charges amount")
    night_charges = serializers.FloatField(default=0.0, help_text="Night charges amount")
    add_ons_price = serializers.FloatField(required=False, default=0.0, help_text="Add-ons price")
    total_fare = serializers.FloatField(help_text="Total fare charge")
    partner_offer_applied = PartnerOfferAppliedSerializer(required=False, allow_null=True, help_text="Applied coupon details")
    airport_entry_fee = serializers.FloatField(required=False, default=0.0, help_text="Airport entry fee")


class AddOnSerializer(serializers.Serializer):
    """
    Serializer for selected booking add-ons.
    """
    name = serializers.CharField(help_text="Name of add-on e.g., CARRIER, LANGUAGES")
    amount = serializers.FloatField(help_text="Charge for the add-on")
    # Using 'Value' with capital V to match API doc, but support case-insensitive fallback in custom clean
    Value = serializers.CharField(required=False, allow_blank=True, help_text="Value string e.g., Hindi,English")
    value = serializers.CharField(required=False, allow_blank=True, help_text="Lowercase alternative for Value")

    def validate(self, attrs):
        # Unify Value and value under 'Value'
        if "value" in attrs and "Value" not in attrs:
            attrs["Value"] = attrs["value"]
        return attrs


class VehicleDetailsSerializer(serializers.Serializer):
    """
    Serializer for vehicle specifics in blocking.
    """
    sku_id = serializers.CharField(required=False, allow_blank=True, help_text="SKU identifier")
    type = serializers.CharField(help_text="Vehicle type e.g., hatchback/sedan")
    subcategory = serializers.CharField(help_text="Subcategory e.g., basic")
    combustion_type = serializers.CharField(help_text="Combustion type e.g., Petrol/CNG/Electric")
    model = serializers.CharField(help_text="Vehicle model name")
    carrier = serializers.BooleanField(help_text="Does the vehicle have a luggage carrier")
    make_year_type = serializers.CharField(help_text="Make year group e.g., Older/Newer/Unknown")
    make_year = serializers.IntegerField(help_text="Year of manufacture")
    cancellation_rule = serializers.CharField(help_text="Cancellation rule code e.g., SUPER_FLEXI")


class BlockSerializer(serializers.Serializer):
    """
    Serializer for POST /partnerblockendpoint/ requests.
    """
    distance = serializers.FloatField(help_text="Total route distance")
    fare_details = BlockFareDetailsSerializer(help_text="Detailed fare breakdown")
    selected_add_ons = AddOnSerializer(many=True, required=False, default=list, help_text="Selected add-ons list")
    search_id = serializers.CharField(help_text="Unique search identifier")
    flight_number = serializers.CharField(required=False, allow_blank=True, help_text="Flight number if airport trip")
    vehicle_type = serializers.CharField(help_text="Vehicle category type")
    vehicle_subcategory = serializers.CharField(help_text="Vehicle subcategory")
    vendor_id = serializers.CharField(help_text="Vendor identifier code")
    partner_name = serializers.CharField(help_text="Partner name e.g., GOMMT")
    verification_code = serializers.CharField(help_text="OTP start verification code")
    trip_end_verification_code = serializers.CharField(help_text="OTP end verification code")
    vehicle_details = VehicleDetailsSerializer(help_text="Details of vehicle to block")
    source = LocationSerializer(help_text="Source pickup location")
    destination = LocationSerializer(help_text="Destination dropoff location")
    stopovers = StopoverSerializer(many=True, required=False, default=list, help_text="Stopovers list")
    trip_type_details = TripTypeDetailsSerializer(help_text="Additional trip type details")


class PassengerSerializer(serializers.Serializer):
    """
    Serializer for passenger info.
    """
    name = serializers.CharField(help_text="Passenger full name")
    email = serializers.EmailField(help_text="Passenger email address")
    phone_number = serializers.CharField(help_text="Passenger contact number")
    country_code = serializers.CharField(required=False, allow_blank=True, default="91", help_text="Country dial code")


class FlightDetailsSerializer(serializers.Serializer):
    """
    Serializer for flight specifics.
    """
    flight_number = serializers.CharField(help_text="Flight number")
    flight_origin_city = serializers.CharField(help_text="Flight origin city")
    flight_destination_city = serializers.CharField(help_text="Flight destination city")
    scheduled_flight_departure = serializers.CharField(help_text="Departure time format YYYY-MM-DDTHH:MM")
    scheduled_flight_arrival = serializers.CharField(help_text="Arrival time format YYYY-MM-DDTHH:MM")


class PaidSerializer(serializers.Serializer):
    """
    Serializer for POST /partnerpaidendpoint/ requests.
    """
    passenger = PassengerSerializer(help_text="Passenger information details")
    partner_reference_number = serializers.CharField(help_text="Unique block reference ID")
    order_reference_number = serializers.CharField(help_text="Unique MMT order reference ID")
    total_fare = serializers.FloatField(help_text="Total fare amount")
    amount_to_be_collected = serializers.FloatField(help_text="Amount to collect from customer")
    platform_fee = serializers.FloatField(required=False, help_text="MMT platform fee")
    booking_gst = serializers.FloatField(required=False, help_text="Booking GST amount")
    vendor_id = serializers.CharField(help_text="Vendor identifier code")
    partner_name = serializers.CharField(help_text="Partner name e.g., GOMMT")
    airport_permit_qr = serializers.CharField(required=False, allow_blank=True, help_text="Airport entry permit QR link")
    flight_details = FlightDetailsSerializer(required=False, help_text="Associated flight details")


class CancelSerializer(serializers.Serializer):
    """
    Serializer for POST /partnercancelendpoint/ requests.
    """
    partner_reference_number = serializers.CharField(help_text="Unique block reference ID")
    order_reference_number = serializers.CharField(help_text="Unique MMT order reference ID")
    cancelled_by = serializers.CharField(help_text="Cancellation source e.g., Customer/CRM")
    cancellation_reason = serializers.CharField(help_text="Reason for booking cancellation")
    cancelled_at = serializers.CharField(help_text="Cancellation time format YYYY-MM-DDTHH:MM:SS.SSSZ")
    vendor_id = serializers.CharField(help_text="Vendor identifier code")
    partner_name = serializers.CharField(help_text="Partner name e.g., GOMMT")


class CustomerLandedSerializer(serializers.Serializer):
    """
    Serializer for POST /partnercustomerarrivedendpoint/ requests.
    """
    booking_id = serializers.CharField(help_text="Order or booking identifier")


class BookingDetailsQuerySerializer(serializers.Serializer):
    """
    Serializer for validating GET /api/partner/v1/booking/details query parameters.
    """
    order_reference_number = serializers.CharField(help_text="Order reference number")
    partner_reference_number = serializers.CharField(required=False, allow_blank=True, help_text="Partner reference number")
