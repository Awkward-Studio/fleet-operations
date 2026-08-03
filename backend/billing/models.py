import datetime
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from decimal import Decimal


class LegalEntity(models.Model):
    legal_name = models.CharField(max_length=150)
    trade_name = models.CharField(max_length=150, blank=True)
    pan = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    state_code = models.CharField(max_length=5, blank=True)
    registered_address = models.TextField(blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=30, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    invoice_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["legal_name"]

    def __str__(self):
        return f"{self.legal_name} ({self.gstin or 'No GSTIN'})"


class FinancialYear(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g. "FY 2025-26"
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        status = "Closed" if self.is_closed else "Open"
        return f"{self.name} ({status})"

    def clean(self):
        super().clean()
        if self.end_date <= self.start_date:
            raise ValidationError({"end_date": "Financial year end date must be after start date."})


class FiscalPeriod(models.Model):
    financial_year = models.ForeignKey(FinancialYear, related_name="periods", on_delete=models.CASCADE)
    period_number = models.PositiveIntegerField()  # 1 to 12
    name = models.CharField(max_length=50)  # e.g. "Apr 2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["financial_year", "period_number"]
        constraints = [
            models.UniqueConstraint(fields=["financial_year", "period_number"], name="unique_period_per_fy")
        ]

    def __str__(self):
        locked = "Locked" if self.is_locked else "Open"
        return f"{self.name} - Period {self.period_number} ({locked})"


class DocumentType(models.TextChoices):
    INVOICE = "INVOICE", "Tax Invoice"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit Note"
    DEBIT_NOTE = "DEBIT_NOTE", "Debit Note"
    RECEIPT = "RECEIPT", "Payment Receipt"
    EXPENSE = "EXPENSE", "Trip / Vendor Expense"
    JOURNAL = "JOURNAL", "Journal Entry"


class DocumentSequence(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, related_name="sequences", on_delete=models.CASCADE)
    financial_year = models.ForeignKey(FinancialYear, related_name="sequences", on_delete=models.CASCADE)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    prefix = models.CharField(max_length=20, default="INV/")
    current_number = models.PositiveIntegerField(default=0)
    padding_digits = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "financial_year", "document_type"],
                name="unique_sequence_per_entity_fy_type",
            )
        ]

    def __str__(self):
        return f"{self.prefix}{str(self.current_number).zfill(self.padding_digits)} ({self.document_type})"

    @classmethod
    def get_next_number(cls, legal_entity, financial_year, document_type, prefix="INV/"):
        with transaction.atomic():
            seq, created = cls.objects.select_for_update().get_or_create(
                legal_entity=legal_entity,
                financial_year=financial_year,
                document_type=document_type,
                defaults={
                    "prefix": prefix,
                    "current_number": 0,
                    "padding_digits": 5,
                },
            )
            seq.current_number += 1
            seq.save(update_fields=["current_number", "updated_at"])
            number_str = str(seq.current_number).zfill(seq.padding_digits)
            return f"{seq.prefix}{number_str}"


class CloseoutStatus(models.TextChoices):
    INCOMPLETE = "INCOMPLETE", "Incomplete"
    SUBMITTED = "SUBMITTED", "Submitted for Review"
    EXCEPTION_REVIEW = "EXCEPTION_REVIEW", "Exception Review"
    APPROVED = "APPROVED", "Approved"
    BILLING_READY = "BILLING_READY", "Billing Ready"
    REOPENED = "REOPENED", "Reopened"


class ChargeCategory(models.TextChoices):
    TOLL = "TOLL", "Toll Charges"
    PARKING = "PARKING", "Parking Fee"
    STATE_PERMIT_TAX = "STATE_PERMIT_TAX", "State / Permit Tax"
    WAITING_CHARGE = "WAITING_CHARGE", "Waiting Charges"
    NIGHT_ALLOWANCE = "NIGHT_ALLOWANCE", "Night Halt Allowance"
    DRIVER_ALLOWANCE = "DRIVER_ALLOWANCE", "Driver Allowance"
    DISCOUNT = "DISCOUNT", "Discount"
    OTHER_EXTRA = "OTHER_EXTRA", "Other Extra Charge"


class TripCloseout(models.Model):
    trip = models.OneToOneField("fleet.Trip", related_name="closeout", on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=CloseoutStatus.choices, default=CloseoutStatus.INCOMPLETE)
    actual_pickup_at = models.DateTimeField(null=True, blank=True)
    actual_drop_at = models.DateTimeField(null=True, blank=True)
    start_odometer_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    end_odometer_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_km = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    metering_policy = models.CharField(max_length=32, blank=True)
    milestone_snapshot = models.JSONField(default=dict, blank=True)
    quantity_provenance = models.JSONField(default=dict, blank=True)
    final_charge_snapshot = models.JSONField(default=dict, blank=True)
    final_calculation_version = models.CharField(max_length=80, blank=True)
    final_taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    final_total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quote_variance_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quote_variance_percent = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    waiting_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    completion_notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_trip_closeouts",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    source_event_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    evidence_snapshot = models.JSONField(default=dict, blank=True)
    blockers = models.JSONField(default=list, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    approved_at = models.DateTimeField(null=True, blank=True)
    billing_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.end_odometer_km < self.start_odometer_km:
            raise ValidationError({"end_odometer_km": "End odometer reading cannot be less than start odometer reading."})

    def save(self, *args, **kwargs):
        if not self.quantity_provenance and self.end_odometer_km >= self.start_odometer_km:
            self.actual_km = self.end_odometer_km - self.start_odometer_km
        if self.status == CloseoutStatus.BILLING_READY:
            self.billing_ready = True
        elif self.status != CloseoutStatus.BILLING_READY:
            self.billing_ready = False
        super().save(*args, **kwargs)

    @property
    def has_blockers(self):
        return bool(self.blockers)

    def __str__(self):
        return f"Closeout Trip #{self.trip_id} ({self.status})"


class TripCharge(models.Model):
    closeout = models.ForeignKey(TripCloseout, related_name="extra_charges", on_delete=models.CASCADE)
    category = models.CharField(max_length=30, choices=ChargeCategory.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    receipt_attachment_url = models.URLField(max_length=500, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_trip_charges",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_trip_charges",
    )

    def __str__(self):
        return f"{self.category}: ₹{self.amount} for Closeout #{self.closeout_id}"


class CloseoutAuditEvent(models.Model):
    closeout = models.ForeignKey(TripCloseout, related_name="audit_events", on_delete=models.CASCADE)
    action = models.CharField(max_length=40)
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="closeout_audit_events",
    )
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    REVIEW = "REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    ISSUED = "ISSUED", "Issued"
    SENT = "SENT", "Sent to Customer"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
    PAID = "PAID", "Paid"
    OVERDUE = "OVERDUE", "Overdue"
    VOID = "VOID", "Void"
    CREDITED = "CREDITED", "Credited / Refunded"


class TaxRegime(models.TextChoices):
    INTRA_STATE = "INTRA_STATE", "Intra-state CGST/SGST"
    INTER_STATE = "INTER_STATE", "Inter-state IGST"
    ZERO_RATED = "ZERO_RATED", "Zero rated / exempt"


class Invoice(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, related_name="invoices", on_delete=models.PROTECT)
    customer = models.ForeignKey("fleet.CorporateCustomer", related_name="invoices", null=True, blank=True, on_delete=models.SET_NULL)
    bill_to_type = models.CharField(max_length=16, blank=True)
    bill_to_key = models.CharField(max_length=100, blank=True, db_index=True)
    booking_channel = models.CharField(max_length=24, blank=True)
    billing_cycle = models.CharField(max_length=24, default="PER_TRIP")
    status = models.CharField(max_length=30, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    financial_year = models.ForeignKey(FinancialYear, related_name="invoices", on_delete=models.PROTECT)
    fiscal_period = models.ForeignKey(FiscalPeriod, related_name="invoices", null=True, blank=True, on_delete=models.PROTECT)
    issue_date = models.DateField(default=datetime.date.today)
    due_date = models.DateField(default=datetime.date.today)
    currency = models.CharField(max_length=10, default="INR")
    place_of_supply = models.CharField(max_length=100, default="Maharashtra (27)")
    supplier_state_code_snapshot = models.CharField(max_length=2, blank=True)
    customer_state_code_snapshot = models.CharField(max_length=2, blank=True)
    tax_regime = models.CharField(
        max_length=24,
        choices=TaxRegime.choices,
        default=TaxRegime.INTRA_STATE,
    )
    po_number = models.CharField(max_length=80, blank=True)
    billing_name_snapshot = models.CharField(max_length=150, blank=True)
    billing_address_snapshot = models.TextField(blank=True)
    gstin_snapshot = models.CharField(max_length=20, blank=True)
    billing_email_snapshot = models.EmailField(blank=True)
    billing_phone_snapshot = models.CharField(max_length=30, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rounding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    submitted_by = models.ForeignKey(
        "accounts.User",
        related_name="submitted_invoices",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        related_name="approved_invoices",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
            if self.pk:
                original = Invoice.objects.get(pk=self.pk)
                if original.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
                    if self.total_amount != original.total_amount:
                        raise ValidationError("Monetary total on an issued invoice cannot be modified.")

    def save(self, *args, **kwargs):
        if self.pk:
            from .models import CreditNote, CreditNoteStatus
            from django.db.models import Sum
            cn_total = self.credit_notes.filter(status=CreditNoteStatus.APPROVED).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
            self.balance_amount = self.total_amount - self.paid_amount - cn_total
            
            if self.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID]:
                if self.balance_amount <= Decimal("0.00"):
                    self.status = InvoiceStatus.PAID
                elif self.balance_amount < self.total_amount:
                    self.status = InvoiceStatus.PARTIALLY_PAID
                else:
                    if self.status != InvoiceStatus.SENT:
                        self.status = InvoiceStatus.ISSUED
        else:
            self.balance_amount = self.total_amount - self.paid_amount
        super().save(*args, **kwargs)

    def __str__(self):
        number = self.invoice_number or f"DRAFT-{self.id}"
        return f"Invoice {number} - ₹{self.total_amount} ({self.status})"


class InvoiceAuditEvent(models.Model):
    invoice = models.ForeignKey(
        Invoice, related_name="audit_events", on_delete=models.CASCADE
    )
    action = models.CharField(max_length=40)
    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class InvoiceDocument(models.Model):
    invoice = models.ForeignKey(
        Invoice, related_name="documents", on_delete=models.CASCADE
    )
    version = models.PositiveIntegerField()
    generation_version = models.CharField(max_length=40, default="invoice-pdf-v1")
    status_snapshot = models.CharField(max_length=30)
    checksum_sha256 = models.CharField(max_length=64)
    attachment = models.OneToOneField(
        "media_store.UploadedAsset",
        related_name="invoice_document",
        on_delete=models.PROTECT,
    )
    is_frozen = models.BooleanField(default=False)
    generated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "version"], name="unique_invoice_document_version"
            )
        ]
        ordering = ["-version"]


class InvoiceDeliveryAttempt(models.Model):
    document = models.ForeignKey(
        InvoiceDocument, related_name="delivery_attempts", on_delete=models.CASCADE
    )
    recipients = models.JSONField(default=list)
    channel = models.CharField(max_length=20, default="EMAIL")
    status = models.CharField(max_length=20)
    failure_message = models.TextField(blank=True)
    attempted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL
    )
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attempted_at"]


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    description = models.CharField(max_length=250)
    sac_hsn_code = models.CharField(max_length=20, default="996601")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_regime = models.CharField(
        max_length=24,
        choices=TaxRegime.choices,
        default=TaxRegime.INTRA_STATE,
    )
    source_type = models.CharField(max_length=32, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    calculation_version = models.CharField(max_length=40, blank=True)
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.description}: ₹{self.line_total}"


class InvoiceTrip(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="invoice_trips", on_delete=models.CASCADE)
    trip = models.OneToOneField("fleet.Trip", related_name="invoice_link", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice #{self.invoice_id} -> Trip #{self.trip_id}"


class CreditNoteStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    APPROVED = "APPROVED", "Approved"
    VOID = "VOID", "Void"


class CreditNote(models.Model):
    credit_note_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, related_name="credit_notes", on_delete=models.PROTECT)
    legal_entity = models.ForeignKey(LegalEntity, related_name="credit_notes", on_delete=models.PROTECT)
    reason = models.CharField(max_length=250)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=CreditNoteStatus.choices, default=CreditNoteStatus.DRAFT)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_credit_notes")
    approved_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    reverses_credit_note = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals")
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Credit Note {self.credit_note_number}: ₹{self.total_amount} ({self.status})"


class CreditNoteLine(models.Model):
    credit_note = models.ForeignKey(CreditNote, related_name="lines", on_delete=models.CASCADE)
    invoice_line = models.ForeignKey(InvoiceLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="credit_note_lines")
    description = models.CharField(max_length=250)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"CN Line: {self.description} - ₹{self.line_total}"


class DebitNoteStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    APPROVED = "APPROVED", "Approved"
    VOID = "VOID", "Void"


class DebitNote(models.Model):
    debit_note_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, related_name="debit_notes", on_delete=models.PROTECT)
    legal_entity = models.ForeignKey(LegalEntity, related_name="debit_notes", on_delete=models.PROTECT)
    reason = models.CharField(max_length=250)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, choices=DebitNoteStatus.choices, default=DebitNoteStatus.DRAFT)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_debit_notes")
    approved_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    reverses_debit_note = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals")
    is_reversed = models.BooleanField(default=False)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_debit_notes")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Debit Note {self.debit_note_number}: ₹{self.total_amount} ({self.status})"


class DebitNoteLine(models.Model):
    debit_note = models.ForeignKey(DebitNote, related_name="lines", on_delete=models.CASCADE)
    invoice_line = models.ForeignKey(InvoiceLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="debit_note_lines")
    description = models.CharField(max_length=250)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"DN Line: {self.description} - ₹{self.line_total}"


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    REVENUE = "REVENUE", "Revenue"
    EXPENSE = "EXPENSE", "Expense"


class LedgerAccount(models.Model):
    code = models.CharField(max_length=30, unique=True)  # e.g. "1100"
    name = models.CharField(max_length=120)  # e.g. "Accounts Receivable"
    account_type = models.CharField(max_length=30, choices=AccountType.choices)
    external_mapping_code = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.account_type})"


class JournalEntry(models.Model):
    entry_number = models.CharField(max_length=50, unique=True)
    legal_entity = models.ForeignKey(LegalEntity, related_name="journals", on_delete=models.PROTECT)
    financial_year = models.ForeignKey(FinancialYear, related_name="journals", on_delete=models.PROTECT)
    fiscal_period = models.ForeignKey(FiscalPeriod, related_name="journals", null=True, blank=True, on_delete=models.PROTECT)
    entry_date = models.DateField(default=datetime.date.today)
    source_type = models.CharField(max_length=50)  # e.g. "INVOICE", "RECEIPT", "EXPENSE"
    source_id = models.CharField(max_length=50)
    narration = models.TextField(blank=True)
    linkage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Journal {self.entry_number} ({self.source_type} #{self.source_id})"


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, related_name="lines", on_delete=models.CASCADE)
    account = models.ForeignKey(LedgerAccount, related_name="journal_lines", on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    narration = models.CharField(max_length=250, blank=True)
    linkage = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.account.code}: Dr ₹{self.debit_amount} | Cr ₹{self.credit_amount}"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer / NEFT / RTGS"
    UPI = "UPI", "UPI Payment"
    CHEQUE = "CHEQUE", "Cheque"
    CASH = "CASH", "Cash"
    CREDIT_CARD = "CREDIT_CARD", "Credit / Debit Card"


class PaymentReceipt(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    legal_entity = models.ForeignKey(LegalEntity, related_name="receipts", on_delete=models.PROTECT)
    customer = models.ForeignKey("fleet.CorporateCustomer", related_name="receipts", null=True, blank=True, on_delete=models.SET_NULL)
    receipt_date = models.DateField(default=datetime.date.today)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    unapplied_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="INR")
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    reverses_receipt = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals")
    is_reversed = models.BooleanField(default=False)
    reversal_reason = models.TextField(blank=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk and self.unapplied_amount is None:
            self.unapplied_amount = self.amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt {self.receipt_number}: {self.currency} {self.amount} ({self.payment_method})"


class PaymentAllocation(models.Model):
    receipt = models.ForeignKey(PaymentReceipt, related_name="allocations", on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, related_name="allocations", on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_reversed = models.BooleanField(default=False)
    reverses_allocation = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reversals")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Allocated {self.allocated_amount} from {self.receipt.receipt_number} to {self.invoice.invoice_number}"


class OTASettlementStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PARTIAL = "PARTIAL", "Partial"
    SETTLED = "SETTLED", "Settled"
    EXCEPTION = "EXCEPTION", "Exception"
    CANCELLED = "CANCELLED", "Cancelled"
    REVERSED = "REVERSED", "Reversed"


class OTASettlementLineClassification(models.TextChoices):
    PENDING = "PENDING", "Pending"
    EXACT = "EXACT", "Exact"
    SHORT = "SHORT", "Short"
    EXCESS = "EXCESS", "Excess"
    MISSING = "MISSING", "Missing"
    DUPLICATE = "DUPLICATE", "Duplicate"
    CANCELLED = "CANCELLED", "Cancelled"


class OTABillingArrangement(models.TextChoices):
    OTA_INVOICE = "OTA_INVOICE", "Tax invoice to OTA"
    RIDER_INVOICE = "RIDER_INVOICE", "Tax invoice to rider"
    SELF_BILLED = "SELF_BILLED", "Self-billed by OTA"
    EXCEPTION_REVIEW = "EXCEPTION_REVIEW", "Exception review"


class OTACounterparty(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=150)
    provider_type = models.CharField(max_length=60, default="OTA")
    default_currency = models.CharField(max_length=3, default="INR")
    billing_arrangement = models.CharField(
        max_length=32,
        choices=OTABillingArrangement.choices,
        default=OTABillingArrangement.OTA_INVOICE,
    )
    commission_tax_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    payout_beneficiary_name = models.CharField(max_length=150, blank=True)
    payout_beneficiary_account = models.CharField(max_length=80, blank=True)
    payout_beneficiary_ifsc = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        self.default_currency = (self.default_currency or "INR").strip().upper()
        if self.commission_tax_rate < 0:
            raise ValidationError({"commission_tax_rate": "Commission tax rate cannot be negative."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class OTABookingSnapshot(models.Model):
    trip = models.OneToOneField("fleet.Trip", related_name="ota_booking_snapshot", on_delete=models.PROTECT)
    counterparty = models.ForeignKey(OTACounterparty, related_name="booking_snapshots", on_delete=models.PROTECT)
    provider_booking_id = models.CharField(max_length=120)
    partner_reference_number = models.CharField(max_length=120, blank=True)
    provider_trip_id = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=3, default="INR")
    gross_fare = models.DecimalField(max_digits=12, decimal_places=2)
    fare_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_basis = models.CharField(max_length=40, default="GROSS_FARE")
    commission_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withholding_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    withholding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cancellation_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_expected = models.DecimalField(max_digits=12, decimal_places=2)
    settlement_status = models.CharField(
        max_length=24,
        choices=OTASettlementStatus.choices,
        default=OTASettlementStatus.PENDING,
    )
    monetary_sources = models.JSONField(default=dict, blank=True)
    source_system = models.CharField(max_length=60, default="MANUAL")
    source_payload_hash = models.CharField(max_length=64, blank=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_ota_booking_snapshots",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_ota_booking_snapshots",
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MONETARY_FIELDS = (
        "gross_fare",
        "fare_tax",
        "commission_amount",
        "commission_tax",
        "withholding_amount",
        "cancellation_amount",
        "net_expected",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["counterparty", "provider_booking_id"],
                name="unique_ota_provider_booking",
            ),
            models.UniqueConstraint(
                fields=["counterparty", "partner_reference_number"],
                condition=~models.Q(partner_reference_number=""),
                name="unique_ota_partner_reference",
            ),
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "INR").strip().upper()
        expected = (
            self.gross_fare
            - self.commission_amount
            - self.commission_tax
            - self.withholding_amount
            - self.cancellation_amount
        )
        if self.net_expected != expected:
            raise ValidationError({"net_expected": "Net expected does not reconcile to OTA commercial amounts."})
        missing_sources = [
            field
            for field in self.MONETARY_FIELDS
            if field not in (self.monetary_sources or {})
        ]
        if missing_sources:
            raise ValidationError({"monetary_sources": f"Missing monetary sources for: {', '.join(missing_sources)}."})
        if self.commission_rate < 0 or self.withholding_rate < 0:
            raise ValidationError("OTA percentage rates cannot be negative.")
        if self.pk and self.settlement_lines.exists():
            original = OTABookingSnapshot.objects.get(pk=self.pk)
            guarded_fields = (
                "provider_booking_id",
                "partner_reference_number",
                "provider_trip_id",
                "currency",
                *self.MONETARY_FIELDS,
                "commission_rate",
                "withholding_rate",
            )
            changed = [
                field
                for field in guarded_fields
                if getattr(original, field) != getattr(self, field)
            ]
            if changed:
                raise ValidationError(
                    {
                        "settlement_status": (
                            "Settled OTA booking snapshots cannot change financial "
                            f"boundary fields: {', '.join(changed)}."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.counterparty.code} booking {self.provider_booking_id} for Trip #{self.trip_id}"


class OTASettlementBatch(models.Model):
    counterparty = models.ForeignKey(OTACounterparty, related_name="settlement_batches", on_delete=models.PROTECT)
    batch_reference = models.CharField(max_length=120)
    currency = models.CharField(max_length=3, default="INR")
    payout_beneficiary_name = models.CharField(max_length=150, blank=True)
    payout_beneficiary_account = models.CharField(max_length=80, blank=True)
    payout_date = models.DateField(null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withholding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_expected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    settlement_status = models.CharField(
        max_length=24,
        choices=OTASettlementStatus.choices,
        default=OTASettlementStatus.PENDING,
    )
    monetary_sources = models.JSONField(default=dict, blank=True)
    source_system = models.CharField(max_length=60, default="MANUAL")
    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_ota_settlement_batches",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_ota_settlement_batches",
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["counterparty", "batch_reference"],
                name="unique_ota_settlement_batch_reference",
            )
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "INR").strip().upper()
        if any(
            value < 0
            for value in (
                self.gross_amount,
                self.commission_amount,
                self.withholding_amount,
                self.net_expected,
                self.actual_payout_amount,
            )
        ):
            raise ValidationError("OTA settlement amounts cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.counterparty.code} settlement {self.batch_reference}"


class OTASettlementLine(models.Model):
    batch = models.ForeignKey(OTASettlementBatch, related_name="lines", on_delete=models.CASCADE)
    booking_snapshot = models.ForeignKey(
        OTABookingSnapshot,
        null=True,
        blank=True,
        related_name="settlement_lines",
        on_delete=models.PROTECT,
    )
    provider_booking_id = models.CharField(max_length=120, blank=True, db_index=True)
    currency = models.CharField(max_length=3, default="INR")
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    variance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    classification = models.CharField(
        max_length=24,
        choices=OTASettlementLineClassification.choices,
        default=OTASettlementLineClassification.PENDING,
    )
    settlement_status = models.CharField(
        max_length=24,
        choices=OTASettlementStatus.choices,
        default=OTASettlementStatus.PENDING,
    )
    monetary_sources = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["batch_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "booking_snapshot"],
                condition=models.Q(booking_snapshot__isnull=False),
                name="unique_ota_settlement_line_booking",
            )
        ]

    def clean(self):
        super().clean()
        self.currency = (self.currency or "INR").strip().upper()
        self.provider_booking_id = (self.provider_booking_id or "").strip()
        if self.booking_snapshot and not self.provider_booking_id:
            self.provider_booking_id = self.booking_snapshot.provider_booking_id
        if self.currency != self.batch.currency:
            raise ValidationError({"currency": "Settlement line currency must match batch and booking snapshot."})
        if self.booking_snapshot and self.currency != self.booking_snapshot.currency:
            raise ValidationError({"currency": "Settlement line currency must match batch and booking snapshot."})
        if not self.booking_snapshot and not self.provider_booking_id:
            raise ValidationError({"provider_booking_id": "Provider booking reference is required for unmatched settlement lines."})
        expected_variance = self.received_amount - self.expected_amount
        if self.variance_amount != expected_variance:
            raise ValidationError({"variance_amount": "Variance must equal received amount minus expected amount."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.batch.batch_reference} line for {self.provider_booking_id}"


class OTAAuditEvent(models.Model):
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=60)
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ota_audit_events",
    )
    snapshot = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    request_idempotency_key = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.entity_type} #{self.entity_id}"


class ExpenseCategory(models.TextChoices):
    FUEL = "FUEL", "Fuel Charges"
    TOLL = "TOLL", "Toll & Fastag"
    PARKING = "PARKING", "Parking Fee"
    STATE_TAX = "STATE_TAX", "State / Entry Permit Tax"
    MAINTENANCE = "MAINTENANCE", "Vehicle Maintenance"
    DRIVER_ALLOWANCE = "DRIVER_ALLOWANCE", "Driver Allowance"
    VENDOR_CHARGE = "VENDOR_CHARGE", "Outsourced Vendor Charge"
    MISC = "MISC", "Miscellaneous Expense"


class ExpenseStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    SETTLED = "SETTLED", "Settled"


class SupplierProfile(models.Model):
    name = models.CharField(max_length=150)
    pan = models.CharField(max_length=20, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    bank_account = models.CharField(max_length=40, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.gstin or 'Vendor'})"


class TripExpense(models.Model):
    trip = models.ForeignKey("fleet.Trip", related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    supplier = models.ForeignKey(SupplierProfile, related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.FUEL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=24, choices=ExpenseStatus.choices, default=ExpenseStatus.SUBMITTED)
    evidence_url = models.URLField(max_length=500, blank=True)
    description = models.CharField(max_length=250, blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category}: ₹{self.amount} ({self.status})"


class FinancialAuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="financial_audit_events",
    )
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=60)
    before_snapshot_hash = models.CharField(max_length=64, blank=True)
    after_snapshot_hash = models.CharField(max_length=64, blank=True)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    request_idempotency_key = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=50, default="WEB_CONSOLE")
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} on {self.entity_type} #{self.entity_id} at {self.timestamp}"


class IdempotencyRegistry(models.Model):
    key = models.CharField(max_length=100, unique=True)
    response_status_code = models.IntegerField()
    response_body = models.TextField()  # JSON string
    request_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"IdempotencyKey {self.key} created at {self.created_at}"
