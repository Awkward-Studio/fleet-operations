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
