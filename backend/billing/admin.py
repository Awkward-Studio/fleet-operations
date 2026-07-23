from django.contrib import admin
from .models import LegalEntity, FinancialYear, FiscalPeriod, DocumentSequence, TripCloseout, TripCharge, Invoice, InvoiceLine, InvoiceTrip, CreditNote, LedgerAccount, JournalEntry, JournalLine, PaymentReceipt, PaymentAllocation, SupplierProfile, TripExpense


@admin.register(LegalEntity)
class LegalEntityAdmin(admin.ModelAdmin):
    list_display = ["legal_name", "gstin", "pan", "state_code", "is_active"]
    search_fields = ["legal_name", "trade_name", "gstin", "pan"]


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_closed"]
    list_filter = ["is_closed"]


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ["name", "financial_year", "period_number", "start_date", "end_date", "is_locked"]
    list_filter = ["is_locked", "financial_year"]


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ["legal_entity", "financial_year", "document_type", "prefix", "current_number"]
    list_filter = ["document_type", "legal_entity", "financial_year"]


@admin.register(TripCloseout)
class TripCloseoutAdmin(admin.ModelAdmin):
    list_display = ["trip", "status", "actual_km", "waiting_minutes", "billing_ready"]
    list_filter = ["status", "billing_ready"]


@admin.register(TripCharge)
class TripChargeAdmin(admin.ModelAdmin):
    list_display = ["closeout", "category", "amount", "description"]
    list_filter = ["category"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "legal_entity", "customer", "status", "total_amount", "paid_amount", "balance_amount", "issue_date"]
    list_filter = ["status", "legal_entity", "financial_year"]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ["invoice", "description", "quantity", "unit_rate", "line_total"]


@admin.register(InvoiceTrip)
class InvoiceTripAdmin(admin.ModelAdmin):
    list_display = ["invoice", "trip"]


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ["credit_note_number", "invoice", "total_amount", "reason"]


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "account_type", "external_mapping_code", "is_active"]
    list_filter = ["account_type", "is_active"]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["entry_number", "legal_entity", "entry_date", "source_type", "source_id"]
    list_filter = ["source_type", "legal_entity"]


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display = ["journal_entry", "account", "debit_amount", "credit_amount"]


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ["receipt_number", "customer", "amount", "unapplied_amount", "payment_method", "receipt_date"]
    list_filter = ["payment_method", "legal_entity"]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ["receipt", "invoice", "allocated_amount", "tds_amount"]


@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ["name", "gstin", "pan", "phone", "is_active"]


@admin.register(TripExpense)
class TripExpenseAdmin(admin.ModelAdmin):
    list_display = ["category", "amount", "status", "trip", "supplier", "created_at"]
    list_filter = ["category", "status"]





