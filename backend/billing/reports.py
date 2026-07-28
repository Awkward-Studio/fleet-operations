from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from fleet.models import Trip, TripStatus

from .models import (
    CloseoutStatus,
    Invoice,
    InvoiceStatus,
    InvoiceTrip,
    PaymentReceipt,
    TripExpense,
)


class FinanceReportService:
    @staticmethod
    def get_financial_summary():
        total_invoiced = Invoice.objects.filter(
            status__in=[
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.PAID,
            ]
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        total_collected = PaymentReceipt.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        total_expenses = TripExpense.objects.filter(status="APPROVED").aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
        receivables_balance = Invoice.objects.filter(
            status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID]
        ).aggregate(total=Sum("balance_amount"))["total"] or Decimal("0.00")
        return {
            "total_invoiced": total_invoiced,
            "total_collected": total_collected,
            "total_expenses": total_expenses,
            "receivables_balance": receivables_balance,
        }

    @staticmethod
    def export_tally_xml(invoice: Invoice) -> str:
        """Generate the established Tally sales-voucher export."""
        return f"""<TALLYMESSAGE xmlns:UDF="TallyUDF">
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


class CloseoutReconciliationReport:
    """Operational control report over every completed trip.

    Coverage counts are mutually exclusive and reconcile to completed trips.
    Issue categories intentionally overlap because one trip can require several
    corrective actions.
    """

    STALE_HOURS = 48
    LARGE_VARIANCE_PERCENT = Decimal("20.00")

    @classmethod
    def build(cls):
        now = timezone.now()
        trips = list(
            Trip.objects.filter(status=TripStatus.COMPLETED)
            .select_related("closeout", "customer")
            .order_by("-updated_at", "-id")
        )
        invoiced_ids = set(
            InvoiceTrip.objects.filter(trip_id__in=[trip.id for trip in trips])
            .values_list("trip_id", flat=True)
        )
        issues = {
            "missing_closeout": [],
            "stale_review": [],
            "large_variance": [],
            "zero_fare": [],
            "reopened_invoiced": [],
        }
        with_closeout = 0

        for trip in trips:
            row = cls._trip_row(trip)
            try:
                closeout = trip.closeout
            except Trip.closeout.RelatedObjectDoesNotExist:
                closeout = None

            if closeout is None:
                issues["missing_closeout"].append(row)
            else:
                with_closeout += 1
                row.update({
                    "closeout_id": closeout.id,
                    "closeout_status": closeout.status,
                    "variance_percent": str(closeout.quote_variance_percent or "0.00"),
                    "updated_at": closeout.updated_at.isoformat(),
                })
                age_hours = (now - closeout.updated_at).total_seconds() / 3600
                if (
                    closeout.status
                    in {
                        CloseoutStatus.INCOMPLETE,
                        CloseoutStatus.EXCEPTION_REVIEW,
                        CloseoutStatus.SUBMITTED,
                        CloseoutStatus.REOPENED,
                    }
                    and age_hours >= cls.STALE_HOURS
                ):
                    issues["stale_review"].append({**row, "age_hours": round(age_hours, 1)})
                try:
                    variance = abs(Decimal(closeout.quote_variance_percent or 0))
                except (InvalidOperation, TypeError):
                    variance = Decimal("0")
                if variance >= cls.LARGE_VARIANCE_PERCENT:
                    issues["large_variance"].append(row)
                if closeout.status == CloseoutStatus.REOPENED and trip.id in invoiced_ids:
                    issues["reopened_invoiced"].append(row)

            total = trip.final_total_amount if trip.final_total_amount is not None else trip.quoted_total_amount
            if total is None or total <= 0:
                issues["zero_fare"].append(row)

        return {
            "generated_at": now.isoformat(),
            "thresholds": {
                "stale_hours": cls.STALE_HOURS,
                "large_variance_percent": str(cls.LARGE_VARIANCE_PERCENT),
            },
            "coverage": {
                "completed_trips": len(trips),
                "with_closeout": with_closeout,
                "missing_closeout": len(trips) - with_closeout,
                "reconciles": len(trips) == with_closeout + (len(trips) - with_closeout),
            },
            "issue_counts": {key: len(rows) for key, rows in issues.items()},
            "issues": issues,
        }

    @staticmethod
    def _trip_row(trip):
        return {
            "trip_id": trip.id,
            "customer": trip.bill_to_name_snapshot or trip.customer_name,
            "booking_type": trip.booking_type,
            "route": f"{trip.pickup_city} → {trip.drop_city}",
            "completed_at": trip.updated_at.isoformat(),
            "pricing_amount_status": trip.pricing_amount_status,
        }
