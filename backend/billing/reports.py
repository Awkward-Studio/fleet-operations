from decimal import Decimal
from django.db.models import Sum
from .models import Invoice, InvoiceStatus, PaymentReceipt, TripExpense, JournalEntry, JournalLine


class FinanceReportService:
    @staticmethod
    def get_financial_summary():
        total_invoiced = Invoice.objects.filter(status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID]).aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")

        total_collected = PaymentReceipt.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_expenses = TripExpense.objects.filter(status="APPROVED").aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        receivables_balance = Invoice.objects.filter(status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID]).aggregate(
            total=Sum("balance_amount")
        )["total"] or Decimal("0.00")

        return {
            "total_invoiced": total_invoiced,
            "total_collected": total_collected,
            "total_expenses": total_expenses,
            "receivables_balance": receivables_balance,
        }

    @staticmethod
    def export_tally_xml(invoice: Invoice) -> str:
        """Generates Tally Prime / ERP 9 XML Sales Voucher format."""
        xml = f"""<TALLYMESSAGE xmlns:UDF="TallyUDF">
    <VOUCHER VCHTYPE="Sales" ACTION="Create">
        <DATE>{invoice.issue_date.strftime('%Y%m%d') if invoice.issue_date else ''}</DATE>
        <NARRATION>Index Fleet Sales Invoice #{invoice.invoice_number}</NARRATION>
        <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
        <VOUCHERNUMBER>{invoice.invoice_number}</VOUCHERNUMBER>
        <PARTYLEDGERNAME>{invoice.billing_name_snapshot}</PARTYLEDGERNAME>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{invoice.billing_name_snapshot}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>YES</ISDEEMEDPOSITIVE>
            <AMOUNT>-{invoice.total_amount:.2f}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Passenger Transport Revenue</LEDGERNAME>
            <ISDEEMEDPOSITIVE>NO</ISDEEMEDPOSITIVE>
            <AMOUNT>{invoice.taxable_amount:.2f}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Output CGST</LEDGERNAME>
            <ISDEEMEDPOSITIVE>NO</ISDEEMEDPOSITIVE>
            <AMOUNT>{invoice.cgst_amount:.2f}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Output SGST</LEDGERNAME>
            <ISDEEMEDPOSITIVE>NO</ISDEEMEDPOSITIVE>
            <AMOUNT>{invoice.sgst_amount:.2f}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
</TALLYMESSAGE>"""
        return xml
