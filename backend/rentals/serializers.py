from rest_framework import serializers
from fleet.serializers import DriverSerializer, VehicleSerializer
from .models import (
    CorporateCustomer,
    RentalBooking,
    RentalChecklist,
    RentalFuelLog,
    RentalInvoice,
    RentalPackage,
    RentalPricingRule,
)


class CorporateCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorporateCustomer
        fields = "__all__"


class RentalPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalPackage
        fields = "__all__"


class RentalPricingRuleSerializer(serializers.ModelSerializer):
    company_name = serializers.ReadOnlyField(source="company.name")
    package_name = serializers.ReadOnlyField(source="package.name")

    class Meta:
        model = RentalPricingRule
        fields = "__all__"


class RentalChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalChecklist
        fields = "__all__"


class RentalFuelLogSerializer(serializers.ModelSerializer):
    driver_name = serializers.ReadOnlyField(source="driver.name")
    vehicle_reg = serializers.ReadOnlyField(source="vehicle.registration_number")

    class Meta:
        model = RentalFuelLog
        fields = "__all__"


class RentalInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalInvoice
        fields = "__all__"


class RentalBookingSerializer(serializers.ModelSerializer):
    vehicle = VehicleSerializer(read_only=True)
    driver = DriverSerializer(read_only=True)
    corporate_customer = CorporateCustomerSerializer(read_only=True)
    package = RentalPackageSerializer(read_only=True)
    checklists = RentalChecklistSerializer(many=True, read_only=True)
    invoice = RentalInvoiceSerializer(read_only=True)
    vehicle_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    driver_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    corporate_customer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    package_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = RentalBooking
        fields = "__all__"


class CreateRentalBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalBooking
        fields = [
            "customer_type",
            "customer_name",
            "customer_phone",
            "customer_email",
            "corporate_customer",
            "pickup_address",
            "drop_address",
            "pickup_city",
            "pickup_at",
            "expected_return_at",
            "package",
            "vehicle_category",
            "vehicle",
            "driver",
            "notes",
        ]
