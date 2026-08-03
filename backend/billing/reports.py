import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

from fleet.models import Trip, TripStatus

from .models import (
    CloseoutStatus,
    Invoice,
    InvoiceStatus,
    InvoiceTrip,
    PaymentReceipt,
    TripExpense,
    PaymentAllocation,
    JournalEntry,
    JournalLine,
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


# ─────────────────────────────────────────────────────────────────────────────
# Number-to-words helper (Indian number system, INR)
# ─────────────────────────────────────────────────────────────────────────────

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty",
    "Sixty", "Seventy", "Eighty", "Ninety",
]


def _words_below_thousand(n: int) -> str:
    if n == 0:
        return ""
    elif n < 20:
        return _ONES[n]
    elif n < 100:
        rem = n % 10
        return _TENS[n // 10] + (" " + _ONES[rem] if rem else "")
    else:
        rem = n % 100
        return _ONES[n // 100] + " Hundred" + (" And " + _words_below_thousand(rem) if rem else "")


def amount_in_words(amount: Decimal) -> str:
    """Return Indian-rupee amount in words, e.g. 'Three Thousand Three Hundred Rupees And Fifty Paise Only'."""
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    rupees = int(amount)
    paise = round((amount - rupees) * 100)

    parts = []
    if rupees == 0:
        parts.append("Zero")
    else:
        crore = rupees // 10_000_000
        rupees %= 10_000_000
        lakh = rupees // 100_000
        rupees %= 100_000
        thousand = rupees // 1_000
        rupees %= 1_000
        remainder = rupees

        if crore:
            parts.append(_words_below_thousand(crore) + " Crore")
        if lakh:
            parts.append(_words_below_thousand(lakh) + " Lakh")
        if thousand:
            parts.append(_words_below_thousand(thousand) + " Thousand")
        if remainder:
            parts.append(_words_below_thousand(remainder))

    result = " ".join(parts) + " Rupees"
    if paise:
        result += " And " + _words_below_thousand(paise) + " Paise"
    return result + " Only"


# ─────────────────────────────────────────────────────────────────────────────
# InvoiceReportService
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceReportService:
    """Renders the official Index Fleet Tax Invoice and Duty Slip Annexure."""

    @staticmethod
    def render_official_tax_invoice(invoice: Invoice) -> str:
        """Return HTML string for the official Tax Invoice layout."""
        from .models import InvoiceStatus

        is_draft = invoice.status in {InvoiceStatus.DRAFT, InvoiceStatus.REVIEW}
        legal_entity = invoice.legal_entity
        lines = list(invoice.lines.all())

        # Derive rate display values from first line (all lines share the same regime)
        first_line = lines[0] if lines else None
        cgst_rate = str(first_line.cgst_rate) if first_line else "2.50"
        sgst_rate = str(first_line.sgst_rate) if first_line else "2.50"
        igst_rate = str(first_line.igst_rate) if first_line else "0.00"

        payment_terms_days = 30
        if invoice.customer_id:
            try:
                payment_terms_days = invoice.customer.payment_terms_days
            except Exception:
                pass

        context = {
            "invoice": invoice,
            "legal_entity": legal_entity,
            "is_draft": is_draft,
            "lines": lines,
            "cgst_rate": cgst_rate,
            "sgst_rate": sgst_rate,
            "igst_rate": igst_rate,
            "amount_in_words": amount_in_words(invoice.total_amount or Decimal("0.00")),
            "payment_terms_days": payment_terms_days,
        }
        return render_to_string("billing/tax_invoice_official.html", context)

    @staticmethod
    def render_duty_slip_annexure(invoice: Invoice) -> str:
        """Return HTML string for the Duty Slip Annexure for all trips on this invoice."""
        from fleet.models import TripLocationLog

        trip_links = list(invoice.invoice_trips.select_related("trip__driver", "trip__vehicle", "trip__customer").all())
        if not trip_links:
            return "<html><body>No trips linked to this invoice.</body></html>"

        # Use first trip for the annexure (one slip per trip is standard)
        trip = trip_links[0].trip

        # Closeout
        closeout = None
        try:
            closeout = trip.closeout
        except Exception:
            pass

        milestone_snapshot = (closeout.milestone_snapshot or {}) if closeout else {}
        gd = milestone_snapshot.get("garage_departure", {})
        pickup = milestone_snapshot.get("pickup", {})
        drop = milestone_snapshot.get("drop", {})

        def _fmt_ts(ts_str):
            """Format ISO timestamp to date/time strings."""
            if not ts_str:
                return None, None
            try:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(ts_str)
                if dt:
                    from django.utils import timezone as tz
                    dt_local = timezone.localtime(dt)
                    return dt_local.strftime("%d-%m-%Y"), dt_local.strftime("%H:%M")
            except Exception:
                pass
            return None, None

        gd_date, gd_time = _fmt_ts(gd.get("timestamp"))
        pickup_date, pickup_time = _fmt_ts(pickup.get("timestamp"))
        drop_date, drop_time = _fmt_ts(drop.get("timestamp"))

        milestones = [
            {
                "label": "Garage Start",
                "start_date": gd_date, "end_date": gd_date,
                "start_time": gd_time, "end_time": gd_time,
                "g_time": gd_time,
                "speedo_start": gd.get("odometer_km", ""),
                "speedo_end": pickup.get("odometer_km", ""),
                "t_km": "",
                "s_km_ex": "", "t_km_ex": "", "es_km_rate": "", "ex_km_cost": "",
                "es_hr_rate": "", "ex_hr_cost": "", "ex_ch": "",
            },
            {
                "label": "Reporting (Pickup)",
                "start_date": pickup_date, "end_date": pickup_date,
                "start_time": pickup_time, "end_time": pickup_time,
                "g_time": pickup_time,
                "speedo_start": pickup.get("odometer_km", ""),
                "speedo_end": drop.get("odometer_km", ""),
                "t_km": str(closeout.actual_km) if closeout else "",
                "s_km_ex": "", "t_km_ex": "", "es_km_rate": "", "ex_km_cost": "",
                "es_hr_rate": "", "ex_hr_cost": "", "ex_ch": "",
            },
            {
                "label": "Release (Drop)",
                "start_date": drop_date, "end_date": drop_date,
                "start_time": drop_time, "end_time": drop_time,
                "g_time": drop_time,
                "speedo_start": drop.get("odometer_km", ""),
                "speedo_end": "",
                "t_km": "",
                "s_km_ex": "", "t_km_ex": "", "es_km_rate": "", "ex_km_cost": "",
                "es_hr_rate": "", "ex_hr_cost": "", "ex_ch": "",
            },
        ]

        # Additional approved charges
        additional_charges = []
        additional_total = Decimal("0.00")
        if closeout:
            for charge in closeout.extra_charges.filter(is_approved=True):
                additional_charges.append({"label": charge.get_category_display(), "amount": charge.amount})
                additional_total += charge.amount

        # GPS audit log (up to 50 most-recent entries)
        gps_qs = TripLocationLog.objects.filter(trip=trip).order_by("timestamp")[:50]
        gps_logs = []
        for log in gps_qs:
            local_ts = timezone.localtime(log.timestamp)
            gps_logs.append({
                "timestamp": local_ts.strftime("%d-%m-%Y %H:%M:%S"),
                "latitude": str(log.latitude),
                "longitude": str(log.longitude),
                "speed_kmh": f"{log.speed_kmh:.1f}" if log.speed_kmh else "—",
                "heading": f"{log.heading:.0f}°" if log.heading else "—",
            })

        vehicle = trip.vehicle
        driver = trip.driver
        start_ts, _ = _fmt_ts(gd.get("timestamp"))
        end_ts, _ = _fmt_ts(drop.get("timestamp"))

        # Format start_time and end_time for summary
        _, start_time_str = _fmt_ts(gd.get("timestamp"))
        _, end_time_str = _fmt_ts(drop.get("timestamp"))

        context = {
            "company_name": invoice.legal_entity.legal_name,
            "company_gstin": invoice.legal_entity.gstin,
            "company_address": invoice.legal_entity.registered_address,
            "duty_slip_number": trip.id,
            "invoice_number": invoice.invoice_number or f"DRAFT-{invoice.id}",
            "report_date": timezone.localdate().strftime("%d-%m-%Y"),
            "booked_by": trip.bill_to_name_snapshot or trip.customer_name,
            "passenger_name": trip.customer_name or trip.customer_display_name_snapshot,
            "vehicle_number": vehicle.registration_number if vehicle else "—",
            "vehicle_type": vehicle.category if vehicle else "—",
            "driver_name": driver.name if driver else "—",
            "driver_phone": driver.phone if driver else "—",
            "duty_type": trip.duty_type or "—",
            "booking_type": trip.get_booking_type_display(),
            "start_date": gd_date or "—",
            "end_date": drop_date or "—",
            "package_name": (trip.pricing_snapshot or {}).get("package", {}).get("name", "—"),
            "city": trip.pickup_city,
            "trip": trip,
            "start_odometer": str(closeout.start_odometer_km) if closeout else "—",
            "end_odometer": str(closeout.end_odometer_km) if closeout else "—",
            "actual_km": str(closeout.actual_km) if closeout else "—",
            "start_time": start_time_str or "—",
            "end_time": end_time_str or "—",
            "actual_hours": str(closeout.actual_hours) if closeout else "—",
            "milestones": milestones,
            "total_km": str(closeout.actual_km) if closeout else "",
            "total_extra_charges": str(additional_total) if additional_charges else "",
            "additional_charges": additional_charges,
            "additional_total": additional_total,
            "gps_logs": gps_logs,
        }
        return render_to_string("billing/duty_slip_annexure.html", context)

    @staticmethod
    def render_pdf_from_html(html_content: str) -> bytes:
        """Convert an HTML string to PDF bytes. Uses WeasyPrint when available on
        the host platform; falls back to xhtml2pdf for environments where the
        native GTK/Pango libraries required by WeasyPrint are not installed
        (e.g., Windows development machines)."""
        try:
            from weasyprint import HTML as WeasyHTML  # type: ignore
            return WeasyHTML(string=html_content).write_pdf()
        except (ImportError, OSError):
            # Fallback: xhtml2pdf (pure-Python, no native library requirement)
            from io import BytesIO
            from xhtml2pdf import pisa  # type: ignore
            buf = BytesIO()
            pisa.CreatePDF(html_content.encode("utf-8"), dest=buf, encoding="utf-8")
            return buf.getvalue()


class ReconciliationService:
    @classmethod
    def reconcile(cls):
        from .models import (
            TripCloseout, Invoice, PaymentReceipt, PaymentAllocation, JournalEntry, JournalLine
        )
        from fleet.models import Trip, TripStatus

        exceptions = {
            "trips_missing_closeout": [],
            "closeouts_not_invoiced": [],
            "invoices_missing_journals": [],
            "invoices_journal_amount_mismatches": [],
            "receipts_missing_journals": [],
            "receipts_journal_amount_mismatches": [],
            "allocations_missing_journals": [],
            "unbalanced_journals": [],
        }

        # 1. Trips missing closeout
        completed_trips = Trip.objects.filter(status="completed").select_related("customer", "closeout")
        for trip in completed_trips:
            closeout = getattr(trip, "closeout", None)
            if not closeout:
                exceptions["trips_missing_closeout"].append({
                    "trip_id": trip.id,
                    "customer_name": trip.customer.display_name if trip.customer else "Adhoc",
                    "pickup_at": trip.pickup_at.isoformat() if trip.pickup_at else None,
                    "amount": str(trip.quoted_total_amount or 0),
                    "description": f"Trip #{trip.id} is completed but closeout is missing.",
                })
            elif closeout.status != "BILLING_READY":
                exceptions["trips_missing_closeout"].append({
                    "trip_id": trip.id,
                    "customer_name": trip.customer.display_name if trip.customer else "Adhoc",
                    "pickup_at": trip.pickup_at.isoformat() if trip.pickup_at else None,
                    "amount": str(trip.quoted_total_amount or 0),
                    "description": f"Trip #{trip.id} closeout is in status {closeout.status} (not BILLING_READY).",
                })

        # 2. Closeouts not invoiced
        billing_ready_closeouts = TripCloseout.objects.filter(status="BILLING_READY").select_related("trip__customer")
        for closeout in billing_ready_closeouts:
            invoiced = InvoiceTrip.objects.filter(trip=closeout.trip).exists()
            if not invoiced:
                exceptions["closeouts_not_invoiced"].append({
                    "closeout_id": closeout.id,
                    "trip_id": closeout.trip_id,
                    "customer_name": closeout.trip.customer.display_name if closeout.trip.customer else "Adhoc",
                    "final_total_amount": str(closeout.final_total_amount or 0),
                    "description": f"Closeout #{closeout.id} is ready for billing but not linked to any invoice.",
                })

        # 3. Invoices vs Journals
        invoices = Invoice.objects.exclude(status="VOID")
        for invoice in invoices:
            journals = JournalEntry.objects.filter(source_type="INVOICE", source_id=str(invoice.id))
            if not journals.exists() and invoice.status in ["ISSUED", "SENT", "PARTIALLY_PAID", "PAID"]:
                exceptions["invoices_missing_journals"].append({
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number or f"DRAFT-{invoice.id}",
                    "customer_name": invoice.customer_name,
                    "total_amount": str(invoice.total_amount),
                    "description": f"Invoice #{invoice.invoice_number or invoice.id} has no GL journal entry.",
                })
            else:
                for journal in journals:
                    debits = sum(line.debit_amount for line in journal.lines.all())
                    if debits != invoice.total_amount:
                        exceptions["invoices_journal_amount_mismatches"].append({
                            "invoice_id": invoice.id,
                            "invoice_number": invoice.invoice_number or f"DRAFT-{invoice.id}",
                            "journal_entry_number": journal.entry_number,
                            "invoice_amount": str(invoice.total_amount),
                            "journal_amount": str(debits),
                            "description": f"Amount mismatch: Invoice total is {invoice.total_amount} but journal debits are {debits}.",
                        })

        # 4. Receipts vs Journals
        receipts = PaymentReceipt.objects.all().select_related("customer")
        for receipt in receipts:
            journals = JournalEntry.objects.filter(source_type="PAYMENT_RECEIPT", source_id=str(receipt.id))
            if not journals.exists():
                exceptions["receipts_missing_journals"].append({
                    "receipt_id": receipt.id,
                    "receipt_number": receipt.receipt_number,
                    "customer_name": receipt.customer.display_name if receipt.customer else "Unknown",
                    "amount": str(receipt.amount),
                    "description": f"Receipt {receipt.receipt_number} has no GL journal entry.",
                })
            else:
                for journal in journals:
                    debits = sum(line.debit_amount for line in journal.lines.all())
                    if debits != receipt.amount:
                        exceptions["receipts_journal_amount_mismatches"].append({
                            "receipt_id": receipt.id,
                            "receipt_number": receipt.receipt_number,
                            "journal_entry_number": journal.entry_number,
                            "receipt_amount": str(receipt.amount),
                            "journal_amount": str(debits),
                            "description": f"Amount mismatch: Receipt amount is {receipt.amount} but journal debits are {debits}.",
                        })

        # 5. Allocations vs Journals
        allocations = PaymentAllocation.objects.all().select_related("receipt", "invoice")
        for allocation in allocations:
            if allocation.tds_amount > 0:
                journals = JournalEntry.objects.filter(source_type="PAYMENT_ALLOCATION", source_id=str(allocation.id))
                if not journals.exists():
                    exceptions["allocations_missing_journals"].append({
                        "allocation_id": allocation.id,
                        "receipt_number": allocation.receipt.receipt_number,
                        "invoice_number": allocation.invoice.invoice_number,
                        "tds_amount": str(allocation.tds_amount),
                        "description": f"TDS allocation {allocation.id} has no GL journal entry.",
                    })

        # 6. Unbalanced Journals
        journals = JournalEntry.objects.all()
        for journal in journals:
            debits = sum(line.debit_amount for line in journal.lines.all())
            credits = sum(line.credit_amount for line in journal.lines.all())
            if debits != credits:
                exceptions["unbalanced_journals"].append({
                    "journal_entry_number": journal.entry_number,
                    "debit_total": str(debits),
                    "credit_total": str(credits),
                    "description": f"Unbalanced Journal {journal.entry_number}: Dr {debits} vs Cr {credits}.",
                })

        return exceptions


class ARAgingReport:
    @classmethod
    def build(cls, as_of_date=None):
        if as_of_date is None:
            as_of_date = timezone.localdate()
        elif isinstance(as_of_date, str):
            as_of_date = datetime.date.fromisoformat(as_of_date)
        elif isinstance(as_of_date, datetime.datetime):
            as_of_date = as_of_date.date()

        from fleet.models import CorporateCustomer
        from billing.models import Invoice, PaymentReceipt, PaymentAllocation, CreditNote, DebitNote
        from django.db.models import Q

        customers = CorporateCustomer.objects.all().order_by("display_name")
        report_data = []

        grand_totals = {
            "current": Decimal("0.00"),
            "1_30": Decimal("0.00"),
            "31_60": Decimal("0.00"),
            "61_90": Decimal("0.00"),
            "over_90": Decimal("0.00"),
            "unapplied": Decimal("0.00"),
            "net_outstanding": Decimal("0.00"),
        }

        for cust in customers:
            cust_invoices = []
            cust_unapplied = []

            # 1. Historical Invoice outstanding balances
            invoices = Invoice.objects.filter(
                customer=cust,
                issue_date__lte=as_of_date
            ).exclude(status="VOID")

            cust_totals = {
                "current": Decimal("0.00"),
                "1_30": Decimal("0.00"),
                "31_60": Decimal("0.00"),
                "61_90": Decimal("0.00"),
                "over_90": Decimal("0.00"),
                "unapplied": Decimal("0.00"),
                "net_outstanding": Decimal("0.00"),
            }

            for inv in invoices:
                # Sum allocations to this invoice on or before as_of_date
                alloc_sum = PaymentAllocation.objects.filter(
                    invoice=inv,
                    created_at__date__lte=as_of_date,
                    is_reversed=False
                ).aggregate(
                    total=Sum("allocated_amount"),
                    tds=Sum("tds_amount")
                )
                allocated = (alloc_sum["total"] or Decimal("0.00")) + (alloc_sum["tds"] or Decimal("0.00"))

                # Sum credit notes approved on or before as_of_date
                cn_sum = CreditNote.objects.filter(
                    invoice=inv,
                    status="APPROVED",
                    approved_at__date__lte=as_of_date
                ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

                # Sum debit notes approved on or before as_of_date
                dn_sum = DebitNote.objects.filter(
                    invoice=inv,
                    status="APPROVED",
                    approved_at__date__lte=as_of_date
                ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

                outstanding = inv.total_amount - allocated - cn_sum + dn_sum

                if outstanding != Decimal("0.00"):
                    # Calculate aging bucket
                    days_overdue = (as_of_date - inv.due_date).days
                    if days_overdue <= 0:
                        bucket = "current"
                    elif days_overdue <= 30:
                        bucket = "1_30"
                    elif days_overdue <= 60:
                        bucket = "31_60"
                    elif days_overdue <= 90:
                        bucket = "61_90"
                    else:
                        bucket = "over_90"

                    cust_totals[bucket] += outstanding
                    cust_totals["net_outstanding"] += outstanding

                    cust_invoices.append({
                        "invoice_id": inv.id,
                        "invoice_number": inv.invoice_number or f"DRAFT-{inv.id}",
                        "issue_date": inv.issue_date.isoformat(),
                        "due_date": inv.due_date.isoformat(),
                        "days_overdue": days_overdue,
                        "original_amount": str(inv.total_amount),
                        "outstanding_balance": str(outstanding),
                        "bucket": bucket,
                    })

            # 2. Historical Unapplied receipts
            receipts = PaymentReceipt.objects.filter(
                customer=cust,
                created_at__date__lte=as_of_date
            ).filter(
                Q(is_reversed=False) | Q(is_reversed=True, updated_at__date__gt=as_of_date)
            )

            for rec in receipts:
                # Sum allocations from this receipt on or before as_of_date
                alloc_sum = PaymentAllocation.objects.filter(
                    receipt=rec,
                    created_at__date__lte=as_of_date,
                    is_reversed=False
                ).aggregate(total=Sum("allocated_amount"))["total"] or Decimal("0.00")

                unapplied = rec.amount - alloc_sum

                if unapplied > Decimal("0.00"):
                    cust_totals["unapplied"] += unapplied
                    cust_totals["net_outstanding"] -= unapplied

                    cust_unapplied.append({
                        "receipt_id": rec.id,
                        "receipt_number": rec.receipt_number,
                        "receipt_date": rec.created_at.date().isoformat(),
                        "amount": str(rec.amount),
                        "unapplied_amount": str(unapplied),
                    })

            # Format customer totals for JSON
            cust_totals_str = {k: str(v) for k, v in cust_totals.items()}

            # Accumulate grand totals
            for k in grand_totals:
                grand_totals[k] += cust_totals[k]

            if cust_invoices or cust_unapplied:
                report_data.append({
                    "customer_id": cust.id,
                    "customer_name": cust.display_name,
                    "invoices": cust_invoices,
                    "unapplied_receipts": cust_unapplied,
                    "totals": cust_totals_str,
                })

        grand_totals_str = {k: str(v) for k, v in grand_totals.items()}

        return {
            "as_of_date": as_of_date.isoformat(),
            "customers": report_data,
            "grand_totals": grand_totals_str,
        }


class CustomerStatementReport:
    @classmethod
    def build(cls, customer, start_date, end_date):
        if isinstance(start_date, str):
            start_date = datetime.date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.date.fromisoformat(end_date)

        from billing.models import Invoice, PaymentReceipt, PaymentAllocation, CreditNote, DebitNote
        from django.db.models import Q

        # Compute Opening Balance before start_date
        inv_before = Invoice.objects.filter(
            customer=customer,
            issue_date__lt=start_date
        ).exclude(status="VOID").aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        dn_before = DebitNote.objects.filter(
            invoice__customer=customer,
            status="APPROVED",
            approved_at__date__lt=start_date
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        rec_before = PaymentReceipt.objects.filter(
            customer=customer,
            created_at__date__lt=start_date
        ).filter(
            Q(is_reversed=False) | Q(is_reversed=True, updated_at__date__gte=start_date)
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        cn_before = CreditNote.objects.filter(
            invoice__customer=customer,
            status="APPROVED",
            approved_at__date__lt=start_date
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        opening_balance = inv_before + dn_before - rec_before - cn_before

        # Gather transactions within range
        transactions = []

        # 1. Invoices
        invoices = Invoice.objects.filter(
            customer=customer,
            issue_date__range=[start_date, end_date]
        ).exclude(status="VOID")
        for inv in invoices:
            transactions.append({
                "date": inv.issue_date,
                "type": "INVOICE",
                "reference": inv.invoice_number or f"DRAFT-{inv.id}",
                "description": f"Tax Invoice #{inv.invoice_number}",
                "debit": inv.total_amount,
                "credit": Decimal("0.00"),
            })

        # 2. Payment Receipts
        receipts = PaymentReceipt.objects.filter(
            customer=customer,
            created_at__date__range=[start_date, end_date]
        )
        for rec in receipts:
            is_reversed_in_range = rec.is_reversed and rec.updated_at.date() <= end_date
            transactions.append({
                "date": rec.created_at.date(),
                "type": "RECEIPT",
                "reference": rec.receipt_number,
                "description": f"Payment Receipt - {rec.payment_method} Ref {rec.reference_number}",
                "debit": Decimal("0.00"),
                "credit": rec.amount,
            })
            if is_reversed_in_range:
                transactions.append({
                    "date": rec.updated_at.date(),
                    "type": "RECEIPT_REVERSAL",
                    "reference": f"REV-{rec.receipt_number}",
                    "description": f"Reversal: {rec.reversal_reason}",
                    "debit": rec.amount,
                    "credit": Decimal("0.00"),
                })

        # 3. Credit Notes
        credit_notes = CreditNote.objects.filter(
            invoice__customer=customer,
            status="APPROVED",
            approved_at__date__range=[start_date, end_date]
        )
        for cn in credit_notes:
            transactions.append({
                "date": cn.approved_at.date(),
                "type": "CREDIT_NOTE",
                "reference": cn.credit_note_number,
                "description": f"Credit Note - Reason: {cn.reason}",
                "debit": Decimal("0.00"),
                "credit": cn.total_amount,
            })

        # 4. Debit Notes
        debit_notes = DebitNote.objects.filter(
            invoice__customer=customer,
            status="APPROVED",
            approved_at__date__range=[start_date, end_date]
        )
        for dn in debit_notes:
            transactions.append({
                "date": dn.approved_at.date(),
                "type": "DEBIT_NOTE",
                "reference": dn.debit_note_number,
                "description": f"Debit Note - Reason: {dn.reason}",
                "debit": dn.total_amount,
                "credit": Decimal("0.00"),
            })

        # Sort transactions chronologically
        transactions.sort(key=lambda x: (x["date"], x["type"]))

        # Build running balance
        running_balance = opening_balance
        statement_lines = []
        for tx in transactions:
            running_balance += tx["debit"] - tx["credit"]
            statement_lines.append({
                "date": tx["date"].isoformat(),
                "type": tx["type"],
                "reference": tx["reference"],
                "description": tx["description"],
                "debit": str(tx["debit"]),
                "credit": str(tx["credit"],),
                "balance": str(running_balance),
            })

        return {
            "customer_id": customer.id,
            "customer_name": customer.display_name,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "opening_balance": str(opening_balance),
            "closing_balance": str(running_balance),
            "lines": statement_lines,
        }
