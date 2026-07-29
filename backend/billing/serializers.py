from rest_framework import serializers
from .models import CloseoutAuditEvent, InvoiceAuditEvent, InvoiceDocument, LegalEntity, FinancialYear, FiscalPeriod, TripCloseout, TripCharge, Invoice, InvoiceLine, InvoiceTrip, CreditNote
from fleet.serializers import TripSerializer
from .services import BillabilityService


class LegalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntity
        fields = "__all__"


class TripChargeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = TripCharge
        fields = "__all__"
        read_only_fields = ["closeout", "is_approved", "approved_by", "approved_at", "created_by"]


class CloseoutAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = CloseoutAuditEvent
        fields = "__all__"


class TripCloseoutSerializer(serializers.ModelSerializer):
    extra_charges = TripChargeSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    trip_details = TripSerializer(source="trip", read_only=True)
    audit_events = CloseoutAuditEventSerializer(many=True, read_only=True)

    class Meta:
        model = TripCloseout
        fields = "__all__"
        read_only_fields = [
            "actual_km",
            "actual_hours",
            "billing_ready",
            "approved_by",
            "approved_at",
            "submitted_by",
            "submitted_at",
            "final_charge_snapshot",
            "final_taxable_amount",
            "final_tax_amount",
            "final_total_amount",
            "quote_variance_amount",
            "quote_variance_percent",
        ]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = "__all__"
        read_only_fields = ["invoice"]


class InvoiceAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = InvoiceAuditEvent
        fields = "__all__"


class InvoiceDocumentSerializer(serializers.ModelSerializer):
    delivery_attempts = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceDocument
        fields = "__all__"

    def get_delivery_attempts(self, obj):
        return [
            {
                "id": attempt.id,
                "recipients": attempt.recipients,
                "channel": attempt.channel,
                "status": attempt.status,
                "failure_message": attempt.failure_message,
                "attempted_at": attempt.attempted_at,
            }
            for attempt in obj.delivery_attempts.all()
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    legal_entity_name = serializers.CharField(source="legal_entity.legal_name", read_only=True)
    audit_events = InvoiceAuditEventSerializer(many=True, read_only=True)
    source_trips = serializers.SerializerMethodField()
    journal_summary = serializers.SerializerMethodField()
    payment_summary = serializers.SerializerMethodField()
    documents = InvoiceDocumentSerializer(many=True, read_only=True)

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
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
        ]

    def get_source_trips(self, obj):
        return [
            {
                "trip_id": link.trip_id,
                "closeout_id": (
                    link.trip.closeout.id
                    if hasattr(link.trip, "closeout")
                    else None
                ),
                "route": f"{link.trip.pickup_city} → {link.trip.drop_city}",
                "booking_type": link.trip.booking_type,
                "pricing_amount_status": link.trip.pricing_amount_status,
                "final_total_amount": (
                    str(link.trip.final_total_amount)
                    if link.trip.final_total_amount is not None
                    else None
                ),
            }
            for link in obj.invoice_trips.select_related("trip").all()
        ]

    def get_journal_summary(self, obj):
        journal = obj.legal_entity.journals.filter(
            source_type="INVOICE", source_id=str(obj.id)
        ).prefetch_related("lines").first()
        if not journal:
            return None
        return {
            "id": journal.id,
            "entry_number": journal.entry_number,
            "debit_total": str(sum((line.debit_amount for line in journal.lines.all()), 0)),
            "credit_total": str(sum((line.credit_amount for line in journal.lines.all()), 0)),
        }

    def get_payment_summary(self, obj):
        allocations = obj.allocations.select_related("receipt").all()
        return {
            "paid_amount": str(obj.paid_amount),
            "balance_amount": str(obj.balance_amount),
            "allocations": [
                {
                    "id": allocation.id,
                    "receipt_id": allocation.receipt_id,
                    "receipt_number": allocation.receipt.receipt_number,
                    "allocated_amount": str(allocation.allocated_amount),
                    "tds_amount": str(allocation.tds_amount),
                }
                for allocation in allocations
            ],
        }


class BillableTripSerializer(TripSerializer):
    billing_eligibility = serializers.SerializerMethodField()
    grouping_key = serializers.SerializerMethodField()
    amount_summary = serializers.SerializerMethodField()
    closeout_summary = serializers.SerializerMethodField()
    bill_to_snapshot = serializers.SerializerMethodField()

    class Meta(TripSerializer.Meta):
        fields = TripSerializer.Meta.fields + [
            "billing_eligibility",
            "grouping_key",
            "amount_summary",
            "closeout_summary",
            "bill_to_snapshot",
        ]

    def get_billing_eligibility(self, obj):
        result = BillabilityService.evaluate(obj)
        return {
            "eligible": result.eligible,
            "bill_to_key": result.bill_to_key,
            "estimated_taxable_amount": str(result.estimated_taxable_amount),
            "blockers": [
                {"code": blocker.code, "message": blocker.message}
                for blocker in result.blockers
            ],
        }

    def get_grouping_key(self, obj):
        return BillabilityService.grouping_key(obj)

    def get_amount_summary(self, obj):
        return {
            key: str(value) if key.endswith("_amount") else value
            for key, value in BillabilityService.amount_summary(obj).items()
        }

    def get_closeout_summary(self, obj):
        closeout = getattr(obj, "closeout", None)
        if not closeout:
            return None
        return {
            "id": closeout.id,
            "status": closeout.status,
            "actual_km": str(closeout.actual_km),
            "actual_hours": str(closeout.actual_hours),
            "final_total_amount": (
                str(closeout.final_total_amount)
                if closeout.final_total_amount is not None
                else None
            ),
            "variance_amount": (
                str(closeout.quote_variance_amount)
                if closeout.quote_variance_amount is not None
                else None
            ),
            "variance_percent": (
                str(closeout.quote_variance_percent)
                if closeout.quote_variance_percent is not None
                else None
            ),
            "approved_extra_count": closeout.extra_charges.filter(
                is_approved=True
            ).count(),
        }

    def get_bill_to_snapshot(self, obj):
        return {
            "type": obj.bill_to_type,
            "key": obj.bill_to_key,
            "name": obj.bill_to_name_snapshot,
            "address": obj.bill_to_address_snapshot,
            "gstin": obj.bill_to_gstin_snapshot,
            "email": obj.bill_to_email_snapshot,
            "phone": obj.bill_to_phone_snapshot,
        }


from .models import PaymentReceipt, PaymentAllocation

class PaymentReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    legal_entity_name = serializers.CharField(source="legal_entity.legal_name", read_only=True)

    class Meta:
        model = PaymentReceipt
        fields = "__all__"


class PaymentAllocationSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source="receipt.receipt_number", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = "__all__"


class CreditNoteSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    legal_entity_name = serializers.CharField(source="legal_entity.legal_name", read_only=True)

    class Meta:
        model = CreditNote
        fields = "__all__"
