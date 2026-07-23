from rest_framework import serializers
from .models import LegalEntity, FinancialYear, FiscalPeriod, TripCloseout, TripCharge, Invoice, InvoiceLine, InvoiceTrip, CreditNote
from fleet.serializers import TripSerializer


class LegalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntity
        fields = "__all__"


class TripChargeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = TripCharge
        fields = "__all__"
        read_only_fields = ["closeout"]


class TripCloseoutSerializer(serializers.ModelSerializer):
    extra_charges = TripChargeSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TripCloseout
        fields = "__all__"
        read_only_fields = ["actual_km", "billing_ready", "approved_by", "approved_at"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = "__all__"
        read_only_fields = ["invoice"]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    legal_entity_name = serializers.CharField(source="legal_entity.legal_name", read_only=True)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = [
            "invoice_number",
            "status",
            "subtotal",
            "discount_amount",
            "taxable_amount",
            "cgst_amount",
            "sgst_amount",
            "igst_amount",
            "rounding_amount",
            "total_amount",
            "paid_amount",
            "balance_amount",
            "created_by",
        ]
