import datetime
import csv
import io
from collections import Counter
from decimal import ROUND_CEILING
from dataclasses import dataclass
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from .models import (
    LegalEntity,
    FinancialYear,
    FiscalPeriod,
    DocumentSequence,
    DocumentType,
    Invoice,
    InvoiceLine,
    InvoiceTrip,
    InvoiceStatus,
    OTABillingArrangement,
    OTAAuditEvent,
    OTABookingSnapshot,
    OTACounterparty,
    OTASettlementBatch,
    OTASettlementLine,
    OTASettlementLineClassification,
    OTASettlementStatus,
    TripCloseout,
    CloseoutStatus,
)
from .tax_service import TaxService, money
from fleet.models import MeteringPolicy, PricingAmountStatus, Trip, TripStatus
from django.utils import timezone
from typing import Optional


def check_period_lock(date_val) -> None:
    if not date_val:
        return
    if isinstance(date_val, datetime.datetime):
        date_val = date_val.date()
    elif isinstance(date_val, str):
        try:
            date_val = datetime.date.fromisoformat(date_val[:10])
        except ValueError:
            return
    period = FiscalPeriod.objects.filter(start_date__lte=date_val, end_date__gte=date_val).first()
    if period and period.is_locked:
        raise ValidationError(f"The fiscal period '{period.name}' is locked. Mutations are prohibited.")


@dataclass(frozen=True)
class BillabilityBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class BillabilityResult:
    eligible: bool
    blockers: tuple[BillabilityBlocker, ...]
    bill_to_key: str
    estimated_taxable_amount: Decimal


class BillabilityService:
    @staticmethod
    def evaluate(trip: Trip) -> BillabilityResult:
        blockers = []

        if trip.status != TripStatus.COMPLETED:
            blockers.append(BillabilityBlocker(
                "STATUS_NOT_COMPLETED",
                "Trip must be completed before invoicing.",
            ))

        closeout = getattr(trip, "closeout", None)
        if closeout is None:
            blockers.append(BillabilityBlocker(
                "CLOSEOUT_MISSING",
                "Trip closeout has not been submitted.",
            ))
        else:
            if closeout.status != CloseoutStatus.BILLING_READY or not closeout.billing_ready:
                blockers.append(BillabilityBlocker(
                    "CLOSEOUT_NOT_APPROVED",
                    "Trip closeout must be approved and marked billing-ready before invoicing.",
                ))
            if closeout.end_odometer_km <= closeout.start_odometer_km:
                blockers.append(BillabilityBlocker(
                    "EVIDENCE_MISSING",
                    "Approved closeout requires reconciled start and end odometer evidence.",
                ))

        if trip.pricing_amount_status not in (
            PricingAmountStatus.QUOTED,
            PricingAmountStatus.FINALIZED,
        ):
            blockers.append(BillabilityBlocker(
                "AMOUNT_UNCLASSIFIED",
                "Trip pricing must be explicitly quoted or finalized.",
            ))
            taxable = Decimal("0.00")
        else:
            prefix = (
                "final"
                if trip.pricing_amount_status == PricingAmountStatus.FINALIZED
                else "quoted"
            )
            taxable = getattr(trip, f"{prefix}_taxable_amount")
            tax = getattr(trip, f"{prefix}_tax_amount")
            total = getattr(trip, f"{prefix}_total_amount")
            if (
                taxable is None
                or tax is None
                or total is None
                or money(taxable + tax) != money(total)
            ):
                blockers.append(BillabilityBlocker(
                    "AMOUNT_UNRECONCILED",
                    "Trip taxable, tax, and gross amounts do not reconcile.",
                ))
                taxable = Decimal("0.00")

        if InvoiceTrip.objects.filter(trip_id=trip.id).exists():
            blockers.append(BillabilityBlocker(
                "ALREADY_INVOICED",
                "Trip is already reserved by an invoice.",
            ))

        if not trip.bill_to_key or not trip.bill_to_name_snapshot:
            blockers.append(BillabilityBlocker(
                "BILL_TO_MISSING",
                "A persisted bill-to identity and billing name are required.",
            ))

        if trip.customer_id and trip.customer.po_required and not trip.po_number:
            blockers.append(BillabilityBlocker(
                "PO_REQUIRED",
                "This customer requires a purchase order number.",
            ))

        return BillabilityResult(
            eligible=not blockers,
            blockers=tuple(blockers),
            bill_to_key=trip.bill_to_key,
            estimated_taxable_amount=money(taxable),
        )

    @staticmethod
    def grouping_key(trip: Trip) -> dict:
        return {
            "bill_to_key": trip.bill_to_key,
            "booking_channel": trip.booking_type,
            "currency": trip.contract.currency if trip.contract_id else "INR",
            "po_number": trip.po_number,
            "billing_cycle": (trip.pricing_snapshot or {}).get(
                "billing_cycle", "ON_DEMAND"
            ),
        }

    @staticmethod
    def amount_summary(trip: Trip) -> dict:
        prefix = (
            "final"
            if trip.pricing_amount_status == PricingAmountStatus.FINALIZED
            else "quoted"
        )
        taxable = getattr(trip, f"{prefix}_taxable_amount") or Decimal("0.00")
        tax = getattr(trip, f"{prefix}_tax_amount") or Decimal("0.00")
        total = getattr(trip, f"{prefix}_total_amount") or Decimal("0.00")
        return {
            "source": prefix.upper(),
            "taxable_amount": money(taxable),
            "tax_amount": money(tax),
            "total_amount": money(total),
        }


class CloseoutService:
    @staticmethod
    def _pricing_metering_policy(trip: Trip) -> str:
        snapshot = trip.pricing_snapshot or {}
        return (
            snapshot.get("package", {}).get("metering_policy")
            or snapshot.get("contract", {}).get("metering_policy")
            or MeteringPolicy.GARAGE_TO_GARAGE
        )

    @staticmethod
    def derive_actual_quantities(closeout: TripCloseout) -> TripCloseout:
        policy = closeout.metering_policy or CloseoutService._pricing_metering_policy(closeout.trip)
        milestones = closeout.milestone_snapshot or {}
        blockers = [
            blocker
            for blocker in (closeout.blockers or [])
            if not blocker.get("code", "").startswith("METERING_")
        ]
        start_km = closeout.start_odometer_km
        end_km = closeout.end_odometer_km
        start_at = closeout.actual_pickup_at
        end_at = closeout.actual_drop_at
        odometer_source = "trip_checklist"
        time_source = "trip_checklist"

        if policy in (MeteringPolicy.PICKUP_TO_DROP, MeteringPolicy.AIRPORT_TRANSFER):
            pickup = milestones.get("pickup") or milestones.get("garage_departure")
            drop = milestones.get("drop")

            pickup_odom = pickup.get("odometer_km") if pickup else None
            drop_odom = drop.get("odometer_km") if drop else None

            if pickup_odom is None or drop_odom is None:
                blockers.append({
                    "code": "METERING_PICKUP_DROP_ODOMETER_MISSING",
                    "message": "Pickup and drop odometer milestones are required for this metering policy.",
                })
                start_km = end_km = Decimal("0")
            else:
                start_km = Decimal(str(pickup_odom))
                end_km = Decimal(str(drop_odom))
                odometer_source = "milestone_snapshot.pickup/drop"

            pickup_time = pickup.get("timestamp") if pickup else None
            drop_time = drop.get("timestamp") if drop else None

            if not pickup_time or not drop_time:
                blockers.append({
                    "code": "METERING_PICKUP_DROP_TIME_MISSING",
                    "message": "Pickup and drop timestamps are required for this metering policy.",
                })
                start_at = end_at = None
            else:
                start_at = datetime.datetime.fromisoformat(pickup_time)
                end_at = datetime.datetime.fromisoformat(drop_time)
                time_source = "milestone_snapshot.pickup/drop"
        elif policy == MeteringPolicy.FIXED_PACKAGE:
            odometer_source = "informational_trip_checklist"
        elif policy in (
            MeteringPolicy.GARAGE_TO_GARAGE,
            MeteringPolicy.OUTSTATION_DAILY_MINIMUM,
        ):
            if end_km <= start_km:
                blockers.append({
                    "code": "METERING_GARAGE_ODOMETER_INVALID",
                    "message": "Garage departure and return odometers must be present and increasing.",
                })
            if not start_at or not end_at:
                blockers.append({
                    "code": "METERING_GARAGE_TIME_MISSING",
                    "message": "Garage departure and return timestamps are required.",
                })

        if end_km < start_km:
            blockers.append({
                "code": "METERING_ODOMETER_REVERSED",
                "message": "End odometer cannot precede start odometer.",
            })
            actual_km = Decimal("0")
        else:
            actual_km = end_km - start_km
        if start_at and end_at and end_at >= start_at:
            seconds = Decimal(str((end_at - start_at).total_seconds()))
            actual_hours = seconds / Decimal("3600")
        else:
            actual_hours = Decimal("0")

        closeout.metering_policy = policy
        closeout.actual_km = money(actual_km)
        closeout.actual_hours = money(actual_hours)
        closeout.quantity_provenance = {
            "metering_policy": policy,
            "odometer_source": odometer_source,
            "time_source": time_source,
            "start_odometer_km": str(start_km),
            "end_odometer_km": str(end_km),
            "start_at": start_at.isoformat() if start_at else None,
            "end_at": end_at.isoformat() if end_at else None,
        }
        closeout.blockers = blockers
        if blockers and closeout.status == CloseoutStatus.SUBMITTED:
            closeout.status = CloseoutStatus.EXCEPTION_REVIEW
        closeout.save(update_fields=[
            "metering_policy",
            "actual_km",
            "actual_hours",
            "quantity_provenance",
            "blockers",
            "status",
            "updated_at",
        ])
        return closeout

    @staticmethod
    @transaction.atomic
    def rerate_from_original_snapshot(closeout_id: int) -> TripCloseout:
        closeout = (
            TripCloseout.objects.select_for_update()
            .select_related("trip")
            .prefetch_related("extra_charges")
            .get(pk=closeout_id)
        )
        trip = closeout.trip
        snapshot = trip.pricing_snapshot or {}
        terms = snapshot.get("rate_terms")
        blockers = [
            blocker
            for blocker in (closeout.blockers or [])
            if blocker.get("code") != "ORIGINAL_RATE_TERMS_MISSING"
        ]
        if not terms:
            blockers.append({
                "code": "ORIGINAL_RATE_TERMS_MISSING",
                "message": "The original quote did not freeze rate terms; re-rating is not permitted.",
            })
            closeout.blockers = blockers
            closeout.status = CloseoutStatus.EXCEPTION_REVIEW
            closeout.save(update_fields=["blockers", "status", "updated_at"])
            return closeout

        d = lambda key: Decimal(str(terms.get(key, "0")))
        actual_hours = Decimal(closeout.actual_hours)
        actual_km = Decimal(closeout.actual_km)
        duty_type = snapshot.get("package", {}).get("duty_type", "")
        is_outstation = duty_type == "OUTSTATION"
        days = (
            max(Decimal("1"), (actual_hours / Decimal("24")).to_integral_value(rounding=ROUND_CEILING))
            if is_outstation
            else Decimal("1")
        )
        included_hours = d("included_hours") * days
        included_km = d("included_km") * days
        effective_km = max(actual_km, d("daily_minimum_km") * days if is_outstation else Decimal("0"))
        excess_hours = max(Decimal("0"), actual_hours - included_hours)
        excess_km = max(Decimal("0"), effective_km - included_km)
        waiting_hours = Decimal(closeout.waiting_minutes) / Decimal("60")
        night_count = Decimal(str(closeout.source_snapshot.get("night_charge_count", 0)))
        driver_days = days if is_outstation else Decimal("0")
        components = {
            "base": money(d("base_rate") * days),
            "excess_hours": money(excess_hours * d("extra_hour_rate")),
            "excess_km": money(excess_km * d("extra_km_rate")),
            "waiting": money(waiting_hours * d("waiting_rate_per_hour")),
            "night": money(night_count * d("night_charge")),
            "driver_allowance": money(driver_days * d("driver_allowance_per_day")),
        }
        package_pre_discount = money(sum(components.values(), Decimal("0")))
        package_discount = money(package_pre_discount * d("discount_percent") / Decimal("100"))
        manual_components = []
        manual_total = Decimal("0")
        for charge in closeout.extra_charges.filter(is_approved=True).order_by("id"):
            signed_amount = -charge.amount if charge.category == "DISCOUNT" else charge.amount
            signed_amount = money(signed_amount)
            manual_total += signed_amount
            manual_components.append({
                "id": charge.id,
                "category": charge.category,
                "amount": str(signed_amount),
                "description": charge.description,
                "receipt_attachment_url": charge.receipt_attachment_url,
            })
        taxable = money(package_pre_discount - package_discount + manual_total)
        if taxable < Decimal("0"):
            raise ValidationError("Final taxable amount cannot be negative.")
        cgst = money(taxable * d("cgst_rate") / Decimal("100"))
        sgst = money(taxable * d("sgst_rate") / Decimal("100"))
        tax = money(cgst + sgst)
        total = money(taxable + tax)
        quoted_total = trip.quoted_total_amount or Decimal(str(snapshot.get("total_amount", "0")))
        variance = money(total - quoted_total)
        variance_percent = (
            money(variance * Decimal("100") / quoted_total)
            if quoted_total
            else Decimal("0.00")
        )
        closeout.final_calculation_version = "closeout-actual-v1"
        closeout.final_taxable_amount = taxable
        closeout.final_tax_amount = tax
        closeout.final_total_amount = total
        closeout.quote_variance_amount = variance
        closeout.quote_variance_percent = variance_percent
        closeout.final_charge_snapshot = {
            "calculation_version": closeout.final_calculation_version,
            "original_quote": {
                "calculation_version": snapshot.get("calculation_version"),
                "rate_book": snapshot.get("rate_book"),
                "package": snapshot.get("package"),
                "rate_terms": terms,
                "quoted_total_amount": str(money(quoted_total)),
            },
            "actuals": {
                "hours": str(actual_hours),
                "km": str(actual_km),
                "effective_km": str(effective_km),
                "outstation_days": str(days),
                "waiting_minutes": closeout.waiting_minutes,
            },
            "components": {key: str(value) for key, value in components.items()},
            "package_discount": str(package_discount),
            "approved_manual_components": manual_components,
            "manual_components_total": str(money(manual_total)),
            "taxable_amount": str(taxable),
            "cgst_amount": str(cgst),
            "sgst_amount": str(sgst),
            "tax_amount": str(tax),
            "total_amount": str(total),
            "quote_variance_amount": str(variance),
            "quote_variance_percent": str(variance_percent),
        }
        closeout.blockers = blockers
        closeout.save(update_fields=[
            "final_charge_snapshot",
            "final_calculation_version",
            "final_taxable_amount",
            "final_tax_amount",
            "final_total_amount",
            "quote_variance_amount",
            "quote_variance_percent",
            "blockers",
            "updated_at",
        ])
        return closeout

    @staticmethod
    @transaction.atomic
    def create_from_trip_completion(
    trip_id: int,
    event_key: Optional[str] = None
) -> TripCloseout:
        trip = (
            Trip.objects.select_for_update()
            .select_related("checklist", "driver", "vehicle")
            .get(pk=trip_id)
        )
        if trip.status != TripStatus.COMPLETED:
            raise ValidationError("Trip must be completed before closeout creation.")

        existing = TripCloseout.objects.select_for_update().filter(trip=trip).first()
        if existing:
            return existing

        checklist = getattr(trip, "checklist", None)
        blockers = []
        evidence = {}
        start_odometer = Decimal("0")
        end_odometer = Decimal("0")
        actual_pickup_at = None
        actual_drop_at = None
        if checklist is None:
            blockers.append({
                "code": "CHECKLIST_MISSING",
                "message": "Start/end checklist evidence is missing.",
            })
        else:
            start_odometer = Decimal(checklist.start_odometer_km)
            actual_pickup_at = checklist.created_at
            evidence["start_odometer_asset_id"] = str(checklist.start_odometer_asset_id)
            evidence["start_checklist_id"] = checklist.id
            if checklist.end_odometer_km is None:
                blockers.append({
                    "code": "END_ODOMETER_MISSING",
                    "message": "End odometer reading is missing.",
                })
            else:
                end_odometer = Decimal(checklist.end_odometer_km)
                actual_drop_at = checklist.updated_at
            if not checklist.end_odometer_asset_id:
                blockers.append({
                    "code": "END_ODOMETER_EVIDENCE_MISSING",
                    "message": "End odometer evidence attachment is missing.",
                })
            else:
                evidence["end_odometer_asset_id"] = str(checklist.end_odometer_asset_id)

        status = CloseoutStatus.EXCEPTION_REVIEW if blockers else CloseoutStatus.SUBMITTED
        closeout = TripCloseout.objects.create(
            trip=trip,
            status=status,
            actual_pickup_at=actual_pickup_at,
            actual_drop_at=actual_drop_at,
            start_odometer_km=start_odometer,
            end_odometer_km=end_odometer,
            source_event_key=event_key or None,
            source_snapshot={
                "trip_id": trip.id,
                "trip_status": trip.status,
                "driver_id": trip.driver_id,
                "vehicle_id": trip.vehicle_id,
                "completion_distance_km": str(trip.distance_km or "0.00"),
                "checklist_id": checklist.id if checklist else None,
            },
            evidence_snapshot=evidence,
            milestone_snapshot={
                "garage_departure": {
                    "timestamp": actual_pickup_at.isoformat() if actual_pickup_at else None,
                    "odometer_km": str(start_odometer),
                },
                "pickup": {
                    "timestamp": actual_pickup_at.isoformat() if actual_pickup_at else None,
                    "odometer_km": str(start_odometer),
                },
                "drop": {
                    "timestamp": actual_drop_at.isoformat() if actual_drop_at else None,
                    "odometer_km": str(end_odometer),
                },
            },
            metering_policy=CloseoutService._pricing_metering_policy(trip),
            blockers=blockers,
        )
        closeout = CloseoutService.derive_actual_quantities(closeout)
        if trip.pricing_snapshot and "rate_terms" in trip.pricing_snapshot:
            closeout = CloseoutService.rerate_from_original_snapshot(closeout.id)
        return closeout


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def generate_invoice_draft(legal_entity: LegalEntity, trip_ids: list, created_by=None) -> Invoice:
        check_period_lock(datetime.date.today())
        if not trip_ids:
            raise ValidationError("At least one trip must be provided to generate an invoice draft.")

        trips = list(
            Trip.objects.select_for_update().filter(id__in=trip_ids).select_related(
                "customer", "closeout", "contract"
            )
        )
        if len(trips) != len(trip_ids):
            raise ValidationError("One or more specified trips could not be found.")

        customer = trips[0].customer
        bill_to_key = trips[0].bill_to_key
        booking_channel = trips[0].booking_type
        currency = trips[0].contract.currency if trips[0].contract_id else "INR"
        po_number = trips[0].po_number
        billing_cycle = (
            trips[0].pricing_snapshot.get("billing_cycle", "ON_DEMAND")
            if trips[0].pricing_snapshot
            else "ON_DEMAND"
        )
        for t in trips:
            result = BillabilityService.evaluate(t)
            if not result.eligible:
                details = "; ".join(
                    f"{blocker.code}: {blocker.message}"
                    for blocker in result.blockers
                )
                raise ValidationError(
                    f"Trip #{t.id} is not billable. {details}"
                )
            if result.bill_to_key != bill_to_key:
                raise ValidationError(
                    "BILL_TO_MISMATCH: All invoice trips must share the same persisted bill-to identity."
                )
            trip_currency = t.contract.currency if t.contract_id else "INR"
            trip_cycle = (
                t.pricing_snapshot.get("billing_cycle", "ON_DEMAND")
                if t.pricing_snapshot
                else "ON_DEMAND"
            )
            if t.booking_type != booking_channel:
                raise ValidationError(
                    "CHANNEL_MISMATCH: Corporate, direct, and OTA trips cannot share one invoice."
                )
            if trip_currency != currency:
                raise ValidationError(
                    "CURRENCY_MISMATCH: All invoice trips must use the same currency."
                )
            if trip_cycle != billing_cycle:
                raise ValidationError(
                    "BILLING_CYCLE_MISMATCH: All invoice trips must use the same billing cycle."
                )
            if t.po_number != po_number:
                raise ValidationError(
                    "PO_MISMATCH: All invoice trips must use the same purchase order."
                )

        today = datetime.date.today()
        # Find active financial year & period
        fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
        if not fy:
            # Fallback to latest open financial year
            fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year + 1, 3, 31),
                )

        period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
        if not period:
            period = fy.periods.first()
            if not period:
                period = FiscalPeriod.objects.create(
                    financial_year=fy,
                    period_number=1,
                    name=f"{today:%b %Y}",
                    start_date=datetime.date(today.year, today.month, 1),
                    end_date=datetime.date(today.year, today.month, 28),
                )

        with transaction.atomic():
            context = TaxService.determine_context(
                legal_entity=legal_entity,
                customer_gstin=trips[0].bill_to_gstin_snapshot,
                place_of_supply="Maharashtra (27)",
            )
            invoice = Invoice.objects.create(
                legal_entity=legal_entity,
                customer=customer,
                bill_to_type=trips[0].bill_to_type,
                bill_to_key=trips[0].bill_to_key,
                booking_channel=trips[0].booking_type,
                billing_cycle=billing_cycle,
                status=InvoiceStatus.DRAFT,
                currency=currency,
                financial_year=fy,
                fiscal_period=period,
                issue_date=today,
                due_date=today + datetime.timedelta(days=customer.payment_terms_days if customer else 0),
                po_number=trips[0].po_number,
                billing_name_snapshot=trips[0].bill_to_name_snapshot,
                billing_address_snapshot=trips[0].bill_to_address_snapshot,
                gstin_snapshot=trips[0].bill_to_gstin_snapshot,
                billing_email_snapshot=trips[0].bill_to_email_snapshot,
                billing_phone_snapshot=trips[0].bill_to_phone_snapshot,
                supplier_state_code_snapshot=context.supplier_state_code,
                customer_state_code_snapshot=context.customer_state_code,
                tax_regime=context.regime,
                created_by=created_by,
            )

            total_taxable = Decimal("0.00")
            total_cgst = Decimal("0.00")
            total_sgst = Decimal("0.00")
            total_igst = Decimal("0.00")

            for t in trips:
                InvoiceTrip.objects.create(invoice=invoice, trip=t)

                amount_prefix = (
                    "final"
                    if t.pricing_amount_status == PricingAmountStatus.FINALIZED
                    else "quoted"
                )
                taxable = getattr(t, f"{amount_prefix}_taxable_amount")
                snapshot = t.pricing_snapshot or {}
                itemized = snapshot.get("itemized_charges", {})
                contract = t.contract
                rate_terms = snapshot.get("rate_terms", {})
                taxes = snapshot.get("taxes", {})

                def _get_rate(key):
                    if contract and getattr(contract, key, None) is not None:
                        return getattr(contract, key)
                    if key in itemized and itemized[key] is not None:
                        return itemized[key]
                    if key in rate_terms and rate_terms[key] is not None:
                        return rate_terms[key]
                    if key in taxes and taxes[key] is not None:
                        return taxes[key]
                    return "2.50"

                cgst_rate = Decimal(str(_get_rate("cgst_rate")))
                sgst_rate = Decimal(str(_get_rate("sgst_rate")))
                tax = TaxService.calculate_line(
                    taxable_value=taxable,
                    cgst_rate=cgst_rate,
                    sgst_rate=sgst_rate,
                    context=context,
                )

                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=f"Trip #{t.id}: {t.pickup_city} to {t.drop_city} ({t.duty_type or 'Local/Outstation'})",
                    quantity=Decimal("1.00"),
                    unit_rate=tax.taxable_value,
                    taxable_value=tax.taxable_value,
                    cgst_rate=tax.cgst_rate,
                    cgst_amount=tax.cgst_amount,
                    sgst_rate=tax.sgst_rate,
                    sgst_amount=tax.sgst_amount,
                    igst_rate=tax.igst_rate,
                    igst_amount=tax.igst_amount,
                    tax_regime=tax.regime,
                    source_type="TRIP_PRICING",
                    source_id=str(t.id),
                    calculation_version=snapshot.get("calculation_version", ""),
                    pricing_snapshot=snapshot,
                    line_total=tax.line_total,
                )

                total_taxable += tax.taxable_value
                total_cgst += tax.cgst_amount
                total_sgst += tax.sgst_amount
                total_igst += tax.igst_amount

                if (
                    hasattr(t, "closeout")
                    and t.closeout
                    and t.closeout.status == CloseoutStatus.BILLING_READY
                    and t.pricing_amount_status != PricingAmountStatus.FINALIZED
                ):
                    # Legacy quoted trips carry extras as separate invoice lines.
                    # Finalized trips already include approved extras in their
                    # frozen final-charge snapshot and must not double count them.
                    for charge in t.closeout.extra_charges.filter(is_approved=True):
                        charge_tax = TaxService.calculate_line(
                            taxable_value=charge.amount,
                            cgst_rate=cgst_rate,
                            sgst_rate=sgst_rate,
                            context=context,
                        )

                        InvoiceLine.objects.create(
                            invoice=invoice,
                            description=f"Trip #{t.id} Extra: {charge.get_category_display()} - {charge.description or ''}".strip(),
                            quantity=Decimal("1.00"),
                            unit_rate=charge_tax.taxable_value,
                            taxable_value=charge_tax.taxable_value,
                            cgst_rate=charge_tax.cgst_rate,
                            cgst_amount=charge_tax.cgst_amount,
                            sgst_rate=charge_tax.sgst_rate,
                            sgst_amount=charge_tax.sgst_amount,
                            igst_rate=charge_tax.igst_rate,
                            igst_amount=charge_tax.igst_amount,
                            tax_regime=charge_tax.regime,
                            source_type="TRIP_CHARGE",
                            source_id=str(charge.id),
                            calculation_version=snapshot.get("calculation_version", ""),
                            pricing_snapshot={
                                "trip_id": t.id,
                                "charge_category": charge.category,
                                "approved_closeout_id": t.closeout.id,
                            },
                            line_total=charge_tax.line_total,
                        )
                        total_taxable += charge_tax.taxable_value
                        total_cgst += charge_tax.cgst_amount
                        total_sgst += charge_tax.sgst_amount
                        total_igst += charge_tax.igst_amount

            subtotal = total_taxable
            grand_total = subtotal + total_cgst + total_sgst + total_igst

            invoice.subtotal = subtotal
            invoice.taxable_amount = total_taxable
            invoice.cgst_amount = total_cgst
            invoice.sgst_amount = total_sgst
            invoice.igst_amount = total_igst
            invoice.total_amount = grand_total
            invoice.balance_amount = grand_total
            invoice.save()

            return invoice

    @staticmethod
    def issue_invoice(invoice: Invoice, created_by=None) -> Invoice:
        if invoice.status in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PAID]:
            return invoice

        with transaction.atomic():
            check_period_lock(datetime.date.today())
            prefix = f"INV/{invoice.financial_year.name.replace(' ', '')}/"
            inv_number = DocumentSequence.get_next_number(
                legal_entity=invoice.legal_entity,
                financial_year=invoice.financial_year,
                document_type=DocumentType.INVOICE,
                prefix=prefix,
            )
            invoice.invoice_number = inv_number
            invoice.status = InvoiceStatus.ISSUED
            invoice.issue_date = datetime.date.today()
            invoice.save()

            PostingEngine.post_invoice_journal(invoice)
            return invoice


class PostingEngine:
    @staticmethod
    def _posting_context(entry_date=None, legal_entity=None):
        entry_date = entry_date or datetime.date.today()
        fy = FinancialYear.objects.filter(
            start_date__lte=entry_date,
            end_date__gte=entry_date,
            is_closed=False,
        ).first()
        if not fy:
            fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
        if not fy:
            fy = FinancialYear.objects.create(
                name=f"FY {entry_date.year}-{str(entry_date.year + 1)[-2:]}",
                start_date=datetime.date(entry_date.year, 4, 1),
                end_date=datetime.date(entry_date.year + 1, 3, 31),
            )
        period = FiscalPeriod.objects.filter(
            financial_year=fy,
            start_date__lte=entry_date,
            end_date__gte=entry_date,
        ).first() or fy.periods.first()
        legal_entity = legal_entity or LegalEntity.objects.filter(is_active=True).first()
        if not legal_entity:
            legal_entity = LegalEntity.objects.create(legal_name="Primary Fleet Entity", is_active=True)
        return legal_entity, fy, period

    @staticmethod
    def _account(code, name, account_type, external_mapping_code=""):
        from .models import LedgerAccount

        account, _ = LedgerAccount.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": account_type,
                "external_mapping_code": external_mapping_code or code,
            },
        )
        return account

    @staticmethod
    def _assert_balanced(journal, entry_number):
        total_debits = sum(line.debit_amount for line in journal.lines.all())
        total_credits = sum(line.credit_amount for line in journal.lines.all())
        if money(total_debits) != money(total_credits):
            raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

    @staticmethod
    def _line(journal, account, debit, credit, narration, linkage):
        from .models import JournalLine

        debit = money(debit)
        credit = money(credit)
        if debit == Decimal("0.00") and credit == Decimal("0.00"):
            return None
        return JournalLine.objects.create(
            journal_entry=journal,
            account=account,
            debit_amount=debit,
            credit_amount=credit,
            narration=narration,
            linkage=linkage,
        )

    @staticmethod
    def post_ota_booking_journal(snapshot) -> "JournalEntry":
        from .models import AccountType, JournalEntry, OTASettlementStatus

        with transaction.atomic():
            snapshot = snapshot.__class__.objects.select_for_update().select_related("trip", "counterparty").get(pk=snapshot.pk)
            entry_date = snapshot.trip.pickup_at.date() if snapshot.trip.pickup_at else datetime.date.today()
            check_period_lock(entry_date)
            legal_entity, fy, period = PostingEngine._posting_context(entry_date)

            ota_receivable = PostingEngine._account("1110", "OTA Settlement Receivable", AccountType.ASSET, "OTA_AR_1110")
            commission_expense = PostingEngine._account("5200", "OTA Commission Expense", AccountType.EXPENSE, "OTA_COMM_5200")
            input_gst = PostingEngine._account("1200", "Input GST Receivable", AccountType.ASSET, "TAX_1200")
            withholding_receivable = PostingEngine._account("1300", "TDS Receivable", AccountType.ASSET, "TDS_1300")
            ota_adjustment = PostingEngine._account("5210", "OTA Cancellation and Fare Adjustment", AccountType.EXPENSE, "OTA_ADJ_5210")
            revenue = PostingEngine._account("4000", "Passenger Transport Revenue", AccountType.REVENUE, "REV_4000")

            entry_number = f"JV/OTA/BOOK/{snapshot.id}"
            linkage = {
                "trip_id": snapshot.trip_id,
                "provider_code": snapshot.counterparty.code,
                "provider_booking_id": snapshot.provider_booking_id,
                "ota_booking_snapshot_id": snapshot.id,
                "billing_arrangement": snapshot.counterparty.billing_arrangement,
            }
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": entry_date,
                    "source_type": "OTA_BOOKING",
                    "source_id": str(snapshot.id),
                    "narration": f"OTA booking commercial posting for {snapshot.counterparty.code} {snapshot.provider_booking_id}",
                    "linkage": linkage,
                },
            )
            journal.linkage = linkage
            journal.lines.all().delete()

            PostingEngine._line(journal, ota_receivable, snapshot.net_expected, 0, "Expected net receivable from OTA", linkage)
            PostingEngine._line(journal, commission_expense, snapshot.commission_amount, 0, "OTA commission expense", linkage)
            PostingEngine._line(journal, input_gst, snapshot.commission_tax, 0, "Input GST on OTA commission", linkage)
            PostingEngine._line(journal, withholding_receivable, snapshot.withholding_amount, 0, "Withholding receivable", linkage)
            PostingEngine._line(journal, ota_adjustment, snapshot.cancellation_amount, 0, "OTA cancellation adjustment", linkage)
            PostingEngine._line(journal, revenue, 0, snapshot.gross_fare, "Gross OTA trip revenue", linkage)
            PostingEngine._assert_balanced(journal, entry_number)
            journal.save(update_fields=["linkage"])
            snapshot.settlement_status = OTASettlementStatus.PENDING
            snapshot.save(update_fields=["settlement_status", "updated_at"])
            return journal

    @staticmethod
    def post_ota_settlement_journal(line) -> "JournalEntry":
        from .models import (
            AccountType,
            JournalEntry,
            OTASettlementLineClassification,
            OTASettlementStatus,
        )

        with transaction.atomic():
            line = line.__class__.objects.select_for_update().select_related(
                "batch", "batch__counterparty", "booking_snapshot", "booking_snapshot__trip"
            ).get(pk=line.pk)
            entry_date = line.batch.payout_date or datetime.date.today()
            check_period_lock(entry_date)
            legal_entity, fy, period = PostingEngine._posting_context(entry_date)

            bank = PostingEngine._account("1000", "Bank & Cash Account", AccountType.ASSET, "CASH_1000")
            ota_receivable = PostingEngine._account("1110", "OTA Settlement Receivable", AccountType.ASSET, "OTA_AR_1110")
            short_expense = PostingEngine._account("5220", "OTA Short Settlement Expense", AccountType.EXPENSE, "OTA_SHORT_5220")
            excess_income = PostingEngine._account("4020", "OTA Excess Settlement Income", AccountType.REVENUE, "OTA_EXCESS_4020")
            unmatched_cash = PostingEngine._account("2350", "Unmatched OTA Cash Clearing", AccountType.LIABILITY, "OTA_UNMATCHED_2350")

            entry_number = f"JV/OTA/SETTLE/{line.id}"
            snapshot = line.booking_snapshot
            linkage = {
                "settlement_batch_id": line.batch_id,
                "settlement_batch_reference": line.batch.batch_reference,
                "settlement_line_id": line.id,
                "provider_code": line.batch.counterparty.code,
                "provider_booking_id": line.provider_booking_id,
                "ota_booking_snapshot_id": snapshot.id if snapshot else None,
                "trip_id": snapshot.trip_id if snapshot else None,
                "classification": line.classification,
            }
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": entry_date,
                    "source_type": "OTA_SETTLEMENT_LINE",
                    "source_id": str(line.id),
                    "narration": f"OTA settlement line posting for {line.batch.counterparty.code} {line.provider_booking_id}",
                    "linkage": linkage,
                },
            )
            journal.linkage = linkage
            journal.lines.all().delete()

            PostingEngine._line(journal, bank, line.received_amount, 0, "OTA payout received", linkage)
            if snapshot and line.classification not in (
                OTASettlementLineClassification.MISSING,
                OTASettlementLineClassification.DUPLICATE,
                OTASettlementLineClassification.CANCELLED,
            ):
                PostingEngine._line(journal, ota_receivable, 0, line.expected_amount, "Clear OTA expected receivable", linkage)
                if line.variance_amount < Decimal("0.00"):
                    PostingEngine._line(journal, short_expense, abs(line.variance_amount), 0, "OTA short settlement variance", linkage)
                elif line.variance_amount > Decimal("0.00"):
                    PostingEngine._line(journal, excess_income, 0, line.variance_amount, "OTA excess settlement variance", linkage)
            else:
                PostingEngine._line(journal, unmatched_cash, 0, line.received_amount, "Unmatched OTA cash held for review", linkage)

            PostingEngine._assert_balanced(journal, entry_number)
            journal.save(update_fields=["linkage"])
            line.settlement_status = (
                OTASettlementStatus.SETTLED
                if line.classification == OTASettlementLineClassification.EXACT
                else OTASettlementStatus.EXCEPTION
            )
            line.save(update_fields=["settlement_status", "updated_at"])
            return journal

    @staticmethod
    def post_ota_settlement_batch(batch) -> list:
        journals = []
        for line in batch.lines.select_related(
            "batch",
            "batch__counterparty",
            "booking_snapshot",
            "booking_snapshot__trip",
            "booking_snapshot__counterparty",
        ).order_by("id"):
            if line.booking_snapshot_id:
                journals.append(PostingEngine.post_ota_booking_journal(line.booking_snapshot))
            journals.append(PostingEngine.post_ota_settlement_journal(line))
        return journals

    @staticmethod
    def post_ota_journal_reversal(original_journal, reason="") -> "JournalEntry":
        from .models import JournalEntry

        with transaction.atomic():
            original_journal = JournalEntry.objects.select_for_update().prefetch_related("lines", "lines__account").get(pk=original_journal.pk)
            today = datetime.date.today()
            check_period_lock(today)
            legal_entity, fy, period = PostingEngine._posting_context(today, original_journal.legal_entity)
            entry_number = f"{original_journal.entry_number}/REV"
            linkage = {
                **(original_journal.linkage or {}),
                "reverses_journal_entry_id": original_journal.id,
                "reverses_entry_number": original_journal.entry_number,
                "reversal_reason": reason,
            }
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": f"{original_journal.source_type}_REVERSAL",
                    "source_id": original_journal.source_id,
                    "narration": f"Reversal of {original_journal.entry_number}: {reason}",
                    "linkage": linkage,
                },
            )
            journal.linkage = linkage
            journal.lines.all().delete()
            for original_line in original_journal.lines.all():
                PostingEngine._line(
                    journal,
                    original_line.account,
                    original_line.credit_amount,
                    original_line.debit_amount,
                    f"Reversal: {original_line.narration}",
                    {**(original_line.linkage or {}), "reverses_journal_line_id": original_line.id},
                )
            PostingEngine._assert_balanced(journal, entry_number)
            journal.save(update_fields=["linkage"])
            return journal

    @staticmethod
    def ota_provider_control_reconciliation(counterparty, as_of=None) -> dict:
        from .models import JournalLine

        as_of = as_of or datetime.date.today()
        lines = JournalLine.objects.filter(
            journal_entry__entry_date__lte=as_of,
            journal_entry__linkage__provider_code=counterparty.code,
            account__code__in=["1110", "2350"],
        ).select_related("account")
        balances = {}
        for journal_line in lines:
            balances.setdefault(journal_line.account.code, Decimal("0.00"))
            balances[journal_line.account.code] += journal_line.debit_amount - journal_line.credit_amount
        return {
            "counterparty_code": counterparty.code,
            "as_of": as_of.isoformat(),
            "ota_settlement_receivable": str(money(balances.get("1110", Decimal("0.00")))),
            "unmatched_ota_cash": str(money(balances.get("2350", Decimal("0.00")))),
        }

    @staticmethod
    def post_invoice_journal(invoice: Invoice) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            check_period_lock(invoice.issue_date)
            ar_account, _ = LedgerAccount.objects.get_or_create(
                code="1100",
                defaults={"name": "Accounts Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "AR_1100"},
            )
            rev_account, _ = LedgerAccount.objects.get_or_create(
                code="4000",
                defaults={"name": "Passenger Transport Revenue", "account_type": AccountType.REVENUE, "external_mapping_code": "REV_4000"},
            )
            cgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2100",
                defaults={"name": "Output CGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2100"},
            )
            sgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2200",
                defaults={"name": "Output SGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2200"},
            )
            igst_account, _ = LedgerAccount.objects.get_or_create(
                code="2250",
                defaults={
                    "name": "Output IGST Payable",
                    "account_type": AccountType.LIABILITY,
                    "external_mapping_code": "TAX_2250",
                },
            )

            entry_number = f"JV/INV/{invoice.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": invoice.legal_entity,
                    "financial_year": invoice.financial_year,
                    "fiscal_period": invoice.fiscal_period,
                    "entry_date": invoice.issue_date,
                    "source_type": "INVOICE",
                    "source_id": str(invoice.id),
                    "narration": f"Journal entry for Invoice #{invoice.invoice_number or invoice.id}",
                },
            )

            # Clear old lines if re-posting
            journal.lines.all().delete()

            # Dr Accounts Receivable
            JournalLine.objects.create(
                journal_entry=journal,
                account=ar_account,
                debit_amount=invoice.total_amount,
                credit_amount=Decimal("0.00"),
                narration=f"Arising from Invoice #{invoice.invoice_number}",
            )

            # Cr Revenue
            JournalLine.objects.create(
                journal_entry=journal,
                account=rev_account,
                debit_amount=Decimal("0.00"),
                credit_amount=invoice.taxable_amount,
                narration="Taxable revenue",
            )

            # Cr CGST
            if invoice.cgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=cgst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.cgst_amount,
                    narration="Output CGST",
                )

            # Cr SGST
            if invoice.sgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=sgst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.sgst_amount,
                    narration="Output SGST",
                )

            if invoice.igst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=igst_account,
                    debit_amount=Decimal("0.00"),
                    credit_amount=invoice.igst_amount,
                    narration="Output IGST",
                )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal

    @staticmethod
    def post_invoice_reversal(invoice: Invoice) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            today = datetime.date.today()
            check_period_lock(today)

            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
            if not fy:
                fy = invoice.financial_year
            period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
            if not period:
                period = invoice.fiscal_period

            ar_account, _ = LedgerAccount.objects.get_or_create(
                code="1100",
                defaults={"name": "Accounts Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "AR_1100"},
            )
            rev_account, _ = LedgerAccount.objects.get_or_create(
                code="4000",
                defaults={"name": "Passenger Transport Revenue", "account_type": AccountType.REVENUE, "external_mapping_code": "REV_4000"},
            )
            cgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2100",
                defaults={"name": "Output CGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2100"},
            )
            sgst_account, _ = LedgerAccount.objects.get_or_create(
                code="2200",
                defaults={"name": "Output SGST Payable", "account_type": AccountType.LIABILITY, "external_mapping_code": "TAX_2200"},
            )
            igst_account, _ = LedgerAccount.objects.get_or_create(
                code="2250",
                defaults={
                    "name": "Output IGST Payable",
                    "account_type": AccountType.LIABILITY,
                    "external_mapping_code": "TAX_2250",
                },
            )

            entry_number = f"JV/INV/REV/{invoice.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": invoice.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": "INVOICE_REVERSAL",
                    "source_id": str(invoice.id),
                    "narration": f"Reversal journal entry for Invoice #{invoice.invoice_number or invoice.id}",
                },
            )

            journal.lines.all().delete()

            JournalLine.objects.create(
                journal_entry=journal,
                account=ar_account,
                debit_amount=Decimal("0.00"),
                credit_amount=invoice.total_amount,
                narration=f"Reversal arising from Invoice #{invoice.invoice_number}",
            )

            JournalLine.objects.create(
                journal_entry=journal,
                account=rev_account,
                debit_amount=invoice.taxable_amount,
                credit_amount=Decimal("0.00"),
                narration="Reversal of taxable revenue",
            )

            if invoice.cgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=cgst_account,
                    debit_amount=invoice.cgst_amount,
                    credit_amount=Decimal("0.00"),
                    narration="Reversal of Output CGST",
                )

            if invoice.sgst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=sgst_account,
                    debit_amount=invoice.sgst_amount,
                    credit_amount=Decimal("0.00"),
                    narration="Reversal of Output SGST",
                )

            if invoice.igst_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=igst_account,
                    debit_amount=invoice.igst_amount,
                    credit_amount=Decimal("0.00"),
                    narration="Reversal of Output IGST",
                )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Reversal journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal

    @staticmethod
    def post_receipt_journal(receipt) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            date_val = receipt.receipt_date
            check_period_lock(date_val)

            fy = getattr(receipt, "financial_year", None)
            if not fy:
                fy = FinancialYear.objects.filter(start_date__lte=date_val, end_date__gte=date_val, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.first()
            period = getattr(receipt, "fiscal_period", None)
            if not period:
                period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=date_val, end_date__gte=date_val).first()

            bank_account, _ = LedgerAccount.objects.get_or_create(
                code="1000",
                defaults={"name": "Bank & Cash Account", "account_type": AccountType.ASSET, "external_mapping_code": "CASH_1000"},
            )
            ar_account, _ = LedgerAccount.objects.get_or_create(
                code="1100",
                defaults={"name": "Accounts Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "AR_1100"},
            )

            entry_number = f"JV/REC/{receipt.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": receipt.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": date_val,
                    "source_type": "PAYMENT_RECEIPT",
                    "source_id": str(receipt.id),
                    "narration": f"Payment Receipt #{receipt.reference_number or receipt.id} from customer {receipt.customer.display_name}",
                },
            )

            journal.lines.all().delete()

            # Dr Bank
            JournalLine.objects.create(
                journal_entry=journal,
                account=bank_account,
                debit_amount=receipt.amount,
                credit_amount=Decimal("0.00"),
                narration=f"Collection on Receipt #{receipt.id}",
            )

    @staticmethod
    def post_journal_reversal(original_journal, reason="") -> "JournalEntry":
        from .models import JournalEntry

        with transaction.atomic():
            original_journal = JournalEntry.objects.select_for_update().prefetch_related("lines", "lines__account").get(pk=original_journal.pk)
            today = datetime.date.today()
            check_period_lock(today)
            legal_entity, fy, period = PostingEngine._posting_context(today, original_journal.legal_entity)
            entry_number = f"{original_journal.entry_number}/REV"
            linkage = {
                **(original_journal.linkage or {}),
                "reverses_journal_entry_id": original_journal.id,
                "reverses_entry_number": original_journal.entry_number,
                "reversal_reason": reason,
            }
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": f"{original_journal.source_type}_REVERSAL",
                    "source_id": original_journal.source_id,
                    "narration": f"Reversal of {original_journal.entry_number}: {reason}",
                    "linkage": linkage,
                },
            )
            journal.linkage = linkage
            journal.lines.all().delete()
            for original_line in original_journal.lines.all():
                PostingEngine._line(
                    journal,
                    original_line.account,
                    original_line.credit_amount,
                    original_line.debit_amount,
                    f"Reversal: {original_line.narration}",
                    {**(original_line.linkage or {}), "reverses_journal_line_id": original_line.id},
                )
            PostingEngine._assert_balanced(journal, entry_number)
            journal.save(update_fields=["linkage"])
            return journal

    @staticmethod
    def post_receipt_journal(receipt) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            date_val = receipt.receipt_date
            check_period_lock(date_val)

            fy = getattr(receipt, "financial_year", None)
            if not fy:
                fy = FinancialYear.objects.filter(start_date__lte=date_val, end_date__gte=date_val, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.first()
            period = getattr(receipt, "fiscal_period", None)
            if not period:
                period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=date_val, end_date__gte=date_val).first()

            bank_account = PostingEngine._account("1000", "Bank & Cash Account", AccountType.ASSET, "CASH_1000")
            unapplied_cash_account = PostingEngine._account("2360", "Unapplied Customer Cash", AccountType.LIABILITY, "UNAPPLIED_2360")

            entry_number = f"JV/REC/{receipt.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": receipt.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": date_val,
                    "source_type": "PAYMENT_RECEIPT",
                    "source_id": str(receipt.id),
                    "narration": f"Payment Receipt #{receipt.reference_number or receipt.id} from customer {receipt.customer.display_name}",
                },
            )

            journal.lines.all().delete()

            # Dr Bank
            PostingEngine._line(
                journal,
                bank_account,
                receipt.amount,
                0,
                f"Collection on Receipt #{receipt.id}",
                {}
            )

            # Cr Unapplied Cash Clearing (Liability)
            PostingEngine._line(
                journal,
                unapplied_cash_account,
                0,
                receipt.amount,
                f"Unapplied payment from customer on Receipt #{receipt.id}",
                {}
            )

            PostingEngine._assert_balanced(journal, entry_number)
            return journal

    @staticmethod
    def post_allocation_journal(allocation) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            date_val = allocation.created_at.date() if allocation.created_at else datetime.date.today()
            check_period_lock(date_val)

            fy = getattr(allocation.receipt, "financial_year", None)
            if not fy:
                fy = FinancialYear.objects.filter(start_date__lte=date_val, end_date__gte=date_val, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.first()
            period = getattr(allocation.receipt, "fiscal_period", None)
            if not period:
                period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=date_val, end_date__gte=date_val).first()

            unapplied_cash_account = PostingEngine._account("2360", "Unapplied Customer Cash", AccountType.LIABILITY, "UNAPPLIED_2360")
            ar_account = PostingEngine._account("1100", "Accounts Receivable", AccountType.ASSET, "AR_1100")
            tds_account = PostingEngine._account("1300", "TDS Receivable", AccountType.ASSET, "TDS_1300")

            entry_number = f"JV/ALLOC/{allocation.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": allocation.receipt.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": date_val,
                    "source_type": "PAYMENT_ALLOCATION",
                    "source_id": str(allocation.id),
                    "narration": f"Payment allocation for Invoice #{allocation.invoice.invoice_number} / Receipt #{allocation.receipt.id}",
                },
            )

            journal.lines.all().delete()

            # Dr Unapplied Cash Clearing (Liability)
            PostingEngine._line(
                journal,
                unapplied_cash_account,
                allocation.allocated_amount,
                0,
                f"Allocation of payment {allocation.id} to Invoice #{allocation.invoice.invoice_number}",
                {}
            )

            # Cr AR (Accounts Receivable) for allocated amount
            PostingEngine._line(
                journal,
                ar_account,
                0,
                allocation.allocated_amount,
                f"AR credit for allocation {allocation.id}",
                {}
            )

            if allocation.tds_amount > Decimal("0.00"):
                # Dr TDS Receivable
                PostingEngine._line(
                    journal,
                    tds_account,
                    allocation.tds_amount,
                    0,
                    f"TDS deducted on allocation {allocation.id}",
                    {}
                )

                # Cr AR (Accounts Receivable) for TDS amount
                PostingEngine._line(
                    journal,
                    ar_account,
                    0,
                    allocation.tds_amount,
                    f"AR credit for TDS on allocation {allocation.id}",
                    {}
                )

            PostingEngine._assert_balanced(journal, entry_number)
            return journal

    @staticmethod
    def post_credit_note_journal(credit_note) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            date_val = credit_note.created_at.date() if credit_note.created_at else datetime.date.today()
            check_period_lock(date_val)

            fy = credit_note.invoice.financial_year
            period = credit_note.invoice.fiscal_period

            rev_account = PostingEngine._account("4000", "Passenger Transport Revenue", AccountType.REVENUE, "REV_4000")
            ar_account = PostingEngine._account("1100", "Accounts Receivable", AccountType.ASSET, "AR_1100")
            cgst_account = PostingEngine._account("2100", "Output CGST Payable", AccountType.LIABILITY, "TAX_2100")
            sgst_account = PostingEngine._account("2200", "Output SGST Payable", AccountType.LIABILITY, "TAX_2200")
            igst_account = PostingEngine._account("2250", "Output IGST Payable", AccountType.LIABILITY, "TAX_2250")

            entry_number = f"JV/CN/{credit_note.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": credit_note.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": date_val,
                    "source_type": "CREDIT_NOTE",
                    "source_id": str(credit_note.id),
                    "narration": f"Credit Note #{credit_note.credit_note_number} against Invoice #{credit_note.invoice.invoice_number}: {credit_note.reason}",
                },
            )

            journal.lines.all().delete()

            # Dr Revenue (taxable amount)
            PostingEngine._line(
                journal,
                rev_account,
                credit_note.taxable_amount,
                0,
                f"Revenue reduction from Credit Note {credit_note.credit_note_number}",
                {}
            )

            # Dr CGST
            if credit_note.cgst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    cgst_account,
                    credit_note.cgst_amount,
                    0,
                    f"CGST reduction from Credit Note {credit_note.credit_note_number}",
                    {}
                )

            # Dr SGST
            if credit_note.sgst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    sgst_account,
                    credit_note.sgst_amount,
                    0,
                    f"SGST reduction from Credit Note {credit_note.credit_note_number}",
                    {}
                )

            # Dr IGST
            if credit_note.igst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    igst_account,
                    credit_note.igst_amount,
                    0,
                    f"IGST reduction from Credit Note {credit_note.credit_note_number}",
                    {}
                )

            # Cr AR (total amount)
            PostingEngine._line(
                journal,
                ar_account,
                0,
                credit_note.total_amount,
                f"AR credit for Credit Note {credit_note.credit_note_number}",
                {}
            )

            PostingEngine._assert_balanced(journal, entry_number)
            return journal

    @staticmethod
    def post_debit_note_journal(debit_note) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
            date_val = debit_note.created_at.date() if debit_note.created_at else datetime.date.today()
            check_period_lock(date_val)

            fy = debit_note.invoice.financial_year
            period = debit_note.invoice.fiscal_period

            rev_account = PostingEngine._account("4000", "Passenger Transport Revenue", AccountType.REVENUE, "REV_4000")
            ar_account = PostingEngine._account("1100", "Accounts Receivable", AccountType.ASSET, "AR_1100")
            cgst_account = PostingEngine._account("2100", "Output CGST Payable", AccountType.LIABILITY, "TAX_2100")
            sgst_account = PostingEngine._account("2200", "Output SGST Payable", AccountType.LIABILITY, "TAX_2200")
            igst_account = PostingEngine._account("2250", "Output IGST Payable", AccountType.LIABILITY, "TAX_2250")

            entry_number = f"JV/DN/{debit_note.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": debit_note.legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": date_val,
                    "source_type": "DEBIT_NOTE",
                    "source_id": str(debit_note.id),
                    "narration": f"Debit Note #{debit_note.debit_note_number} against Invoice #{debit_note.invoice.invoice_number}: {debit_note.reason}",
                },
            )

            journal.lines.all().delete()

            # Dr AR (total amount)
            PostingEngine._line(
                journal,
                ar_account,
                debit_note.total_amount,
                0,
                f"AR debit for Debit Note {debit_note.debit_note_number}",
                {}
            )

            # Cr Revenue (taxable amount)
            PostingEngine._line(
                journal,
                rev_account,
                0,
                debit_note.taxable_amount,
                f"Revenue addition from Debit Note {debit_note.debit_note_number}",
                {}
            )

            # Cr CGST
            if debit_note.cgst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    cgst_account,
                    0,
                    debit_note.cgst_amount,
                    f"CGST addition from Debit Note {debit_note.debit_note_number}",
                    {}
                )

            # Cr SGST
            if debit_note.sgst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    sgst_account,
                    0,
                    debit_note.sgst_amount,
                    f"SGST addition from Debit Note {debit_note.debit_note_number}",
                    {}
                )

            # Cr IGST
            if debit_note.igst_amount > Decimal("0.00"):
                PostingEngine._line(
                    journal,
                    igst_account,
                    0,
                    debit_note.igst_amount,
                    f"IGST addition from Debit Note {debit_note.debit_note_number}",
                    {}
                )

            PostingEngine._assert_balanced(journal, entry_number)
            return journal

    @staticmethod
    def post_fuel_journal(fuel_transaction, trip_expense) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine
        with transaction.atomic():
            check_period_lock(datetime.date.today())
            fuel_exp_acc, _ = LedgerAccount.objects.get_or_create(
                code="5100",
                defaults={"name": "Fuel Expense", "account_type": AccountType.EXPENSE, "external_mapping_code": "EXP_5100"}
            )
            gst_in_acc, _ = LedgerAccount.objects.get_or_create(
                code="1200",
                defaults={"name": "Input GST Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "TAX_1200"}
            )
            payable_acc, _ = LedgerAccount.objects.get_or_create(
                code="2300",
                defaults={"name": "Fuel Payables / Cash", "account_type": AccountType.LIABILITY, "external_mapping_code": "PAY_2300"}
            )

            today = datetime.date.today()
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year+1, 3, 31),
                )
            period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
            if not period:
                period = fy.periods.first()

            legal_entity = LegalEntity.objects.filter(is_active=True).first()
            if not legal_entity:
                legal_entity = LegalEntity.objects.create(
                    legal_name="Primary Fleet Entity",
                    is_active=True,
                )

            entry_number = f"JV/FUEL/{fuel_transaction.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": "FUEL",
                    "source_id": str(fuel_transaction.id),
                    "narration": f"Journal entry for Fuel purchase for {fuel_transaction.vehicle.registration_number} @ {fuel_transaction.vendor}",
                },
            )

            journal.lines.all().delete()

            taxable_amt = fuel_transaction.total_amount - fuel_transaction.tax_amount
            JournalLine.objects.create(
                journal_entry=journal,
                account=fuel_exp_acc,
                debit_amount=taxable_amt,
                credit_amount=Decimal("0.00"),
                narration=f"Fuel cost excl tax",
            )
            if fuel_transaction.tax_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=gst_in_acc,
                    debit_amount=fuel_transaction.tax_amount,
                    credit_amount=Decimal("0.00"),
                    narration="Input GST on fuel purchase",
                )

            JournalLine.objects.create(
                journal_entry=journal,
                account=payable_acc,
                debit_amount=Decimal("0.00"),
                credit_amount=fuel_transaction.total_amount,
                narration=f"Amount payable to {fuel_transaction.vendor}",
            )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal

    @staticmethod
    def post_fuel_reversal_journal(fuel_transaction) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine
        with transaction.atomic():
            check_period_lock(datetime.date.today())
            fuel_exp_acc, _ = LedgerAccount.objects.get_or_create(
                code="5100",
                defaults={"name": "Fuel Expense", "account_type": AccountType.EXPENSE, "external_mapping_code": "EXP_5100"}
            )
            gst_in_acc, _ = LedgerAccount.objects.get_or_create(
                code="1200",
                defaults={"name": "Input GST Receivable", "account_type": AccountType.ASSET, "external_mapping_code": "TAX_1200"}
            )
            payable_acc, _ = LedgerAccount.objects.get_or_create(
                code="2300",
                defaults={"name": "Fuel Payables / Cash", "account_type": AccountType.LIABILITY, "external_mapping_code": "PAY_2300"}
            )

            today = datetime.date.today()
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
            if not fy:
                fy = FinancialYear.objects.filter(is_closed=False).order_by("-start_date").first()
            if not fy:
                fy = FinancialYear.objects.create(
                    name=f"FY {today.year}-{str(today.year+1)[-2:]}",
                    start_date=datetime.date(today.year, 4, 1),
                    end_date=datetime.date(today.year+1, 3, 31),
                )
            period = FiscalPeriod.objects.filter(financial_year=fy, start_date__lte=today, end_date__gte=today).first()
            if not period:
                period = fy.periods.first()

            legal_entity = LegalEntity.objects.filter(is_active=True).first()
            if not legal_entity:
                legal_entity = LegalEntity.objects.create(
                    legal_name="Primary Fleet Entity",
                    is_active=True,
                )

            entry_number = f"JV/FUEL/REV/{fuel_transaction.id}"
            journal, _ = JournalEntry.objects.get_or_create(
                entry_number=entry_number,
                defaults={
                    "legal_entity": legal_entity,
                    "financial_year": fy,
                    "fiscal_period": period,
                    "entry_date": today,
                    "source_type": "FUEL_REVERSAL",
                    "source_id": str(fuel_transaction.id),
                    "narration": f"Reversal of Fuel purchase for {fuel_transaction.vehicle.registration_number} @ {fuel_transaction.vendor} (Orig JV/FUEL/{fuel_transaction.id})",
                },
            )

            journal.lines.all().delete()

            JournalLine.objects.create(
                journal_entry=journal,
                account=payable_acc,
                debit_amount=fuel_transaction.total_amount,
                credit_amount=Decimal("0.00"),
                narration=f"Reversal of payable for {fuel_transaction.vendor}",
            )

            taxable_amt = fuel_transaction.total_amount - fuel_transaction.tax_amount
            JournalLine.objects.create(
                journal_entry=journal,
                account=fuel_exp_acc,
                debit_amount=Decimal("0.00"),
                credit_amount=taxable_amt,
                narration=f"Reversal of fuel cost",
            )

            if fuel_transaction.tax_amount > Decimal("0.00"):
                JournalLine.objects.create(
                    journal_entry=journal,
                    account=gst_in_acc,
                    debit_amount=Decimal("0.00"),
                    credit_amount=fuel_transaction.tax_amount,
                    narration="Reversal of Input GST on fuel",
                )

            total_debits = sum(line.debit_amount for line in journal.lines.all())
            total_credits = sum(line.credit_amount for line in journal.lines.all())
            if total_debits != total_credits:
                raise ValidationError(f"Journal entry #{entry_number} is unbalanced: Dr ₹{total_debits} vs Cr ₹{total_credits}")

            return journal


class PaymentService:
    @staticmethod
    def record_receipt(legal_entity, customer, amount, currency="INR", payment_method="BANK_TRANSFER", reference_number="", created_by=None, idempotency_key=None):
        from .models import PaymentReceipt
        if amount <= 0:
            raise ValidationError("Receipt amount must be greater than zero.")
        
        with transaction.atomic():
            check_period_lock(datetime.date.today())
            if idempotency_key:
                existing = PaymentReceipt.objects.filter(idempotency_key=idempotency_key).first()
                if existing:
                    return existing

            fy = FinancialYear.objects.filter(is_closed=False).first()
            prefix = f"REC/{fy.name.replace(' ', '')}/" if fy else "REC/2026/"
            rec_num = DocumentSequence.get_next_number(
                legal_entity=legal_entity,
                financial_year=fy,
                document_type=DocumentType.RECEIPT,
                prefix=prefix,
            )
            receipt = PaymentReceipt.objects.create(
                receipt_number=rec_num,
                legal_entity=legal_entity,
                customer=customer,
                amount=amount,
                unapplied_amount=amount,
                currency=currency,
                payment_method=payment_method,
                reference_number=reference_number,
                idempotency_key=idempotency_key,
                created_by=created_by,
            )
            PostingEngine.post_receipt_journal(receipt)
            return receipt

    @staticmethod
    def allocate_payment(receipt, invoice, amount, tds_amount=Decimal("0.00")):
        from .models import PaymentAllocation
        if amount < 0 or tds_amount < 0:
            raise ValidationError("Allocation and TDS amounts cannot be negative.")
        if amount == 0 and tds_amount == 0:
            raise ValidationError("Must allocate a positive amount or TDS amount.")
        if receipt.is_reversed:
            raise ValidationError("Cannot allocate from a reversed receipt.")
        if invoice.status == InvoiceStatus.VOID:
            raise ValidationError("Cannot allocate to a voided invoice.")
        if receipt.legal_entity_id != invoice.legal_entity_id:
            raise ValidationError("Receipt and invoice must belong to the same legal entity.")
        if receipt.customer_id != invoice.customer_id:
            raise ValidationError("Receipt and invoice must belong to the same customer.")
        if receipt.currency != invoice.currency:
            raise ValidationError("Receipt and invoice currency must match.")
        if amount > receipt.unapplied_amount:
            raise ValidationError("Allocation amount cannot exceed receipt unapplied balance.")
        if (amount + tds_amount) > invoice.balance_amount:
            raise ValidationError("Allocation amount cannot exceed invoice remaining balance.")

        with transaction.atomic():
            check_period_lock(datetime.date.today())
            # Lock both receipt and invoice to prevent concurrent overallocation
            receipt_db = receipt.__class__.objects.select_for_update().get(pk=receipt.pk)
            invoice_db = invoice.__class__.objects.select_for_update().get(pk=invoice.pk)
            
            # Recheck balances after lock
            if amount > receipt_db.unapplied_amount:
                raise ValidationError("Allocation amount cannot exceed receipt unapplied balance.")
            if (amount + tds_amount) > invoice_db.balance_amount:
                raise ValidationError("Allocation amount cannot exceed invoice remaining balance.")

            allocation = PaymentAllocation.objects.create(
                receipt=receipt_db,
                invoice=invoice_db,
                allocated_amount=amount,
                tds_amount=tds_amount,
            )

            receipt_db.unapplied_amount -= amount
            receipt_db.save()

            total_credit = amount + tds_amount
            invoice_db.paid_amount += total_credit
            if invoice_db.paid_amount >= invoice_db.total_amount:
                invoice_db.status = InvoiceStatus.PAID
            elif invoice_db.paid_amount > Decimal("0.00"):
                invoice_db.status = InvoiceStatus.PARTIALLY_PAID
            invoice_db.save()

            # Update the passed objects in-place
            receipt.unapplied_amount = receipt_db.unapplied_amount
            invoice.paid_amount = invoice_db.paid_amount
            invoice.status = invoice_db.status
            invoice.balance_amount = invoice_db.balance_amount

            PostingEngine.post_allocation_journal(allocation)

            return allocation

    @staticmethod
    def reverse_receipt(receipt, reason="", reversed_by=None):
        from .models import JournalEntry
        if receipt.is_reversed:
            raise ValidationError("Receipt is already reversed.")
        with transaction.atomic():
            check_period_lock(datetime.date.today())
            receipt = receipt.__class__.objects.select_for_update().get(pk=receipt.pk)
            
            # Reverse all active allocations associated with this receipt
            for allocation in receipt.allocations.filter(is_reversed=False):
                PaymentService.reverse_allocation(allocation)
                
            receipt.is_reversed = True
            receipt.reversal_reason = reason
            receipt.unapplied_amount = Decimal("0.00")
            receipt.save()
            
            # Post reversal journal entry
            orig_journal = JournalEntry.objects.filter(source_type="PAYMENT_RECEIPT", source_id=str(receipt.id)).first()
            if orig_journal:
                PostingEngine.post_journal_reversal(orig_journal, f"Reversal of Receipt #{receipt.receipt_number}: {reason}")
                
            return receipt

    @staticmethod
    def reverse_allocation(allocation):
        from .models import JournalEntry
        if allocation.is_reversed:
            raise ValidationError("Allocation is already reversed.")
        with transaction.atomic():
            check_period_lock(datetime.date.today())
            allocation = allocation.__class__.objects.select_for_update().get(pk=allocation.pk)
            receipt = allocation.receipt.__class__.objects.select_for_update().get(pk=allocation.receipt.pk)
            invoice = allocation.invoice.__class__.objects.select_for_update().get(pk=allocation.invoice.pk)
            
            allocation.is_reversed = True
            allocation.save()
            
            # Put amount back into receipt unapplied balance
            if not receipt.is_reversed:
                receipt.unapplied_amount += allocation.allocated_amount
                receipt.save()
                
            # Subtract from invoice paid amount
            total_credit = allocation.allocated_amount + allocation.tds_amount
            invoice.paid_amount -= total_credit
            
            # Recheck status of invoice
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.PAID
            elif invoice.paid_amount > Decimal("0.00"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            else:
                invoice.status = InvoiceStatus.ISSUED
            invoice.save()
            
            # Post reversal journal entry
            orig_journal = JournalEntry.objects.filter(source_type="PAYMENT_ALLOCATION", source_id=str(allocation.id)).first()
            if orig_journal:
                PostingEngine.post_journal_reversal(orig_journal, f"Reversal of allocation {allocation.id}")
                
            return allocation


class OTACommercialService:
    @staticmethod
    def quantize(value) -> Decimal:
        return money(Decimal(str(value or "0")))

    @staticmethod
    def provider_config(ota_source: str) -> dict:
        code = (ota_source or "").replace(" ", "").upper()
        counterparty = (
            OTACounterparty.objects.filter(code__iexact=code).first()
            or OTACounterparty.objects.filter(name__iexact=ota_source or "").first()
        )
        if not counterparty:
            return {
                "counterparty_code": code or "",
                "billing_arrangement": OTABillingArrangement.OTA_INVOICE,
                "commission_tax_rate": Decimal("0.00"),
                "exception": None,
            }
        return {
            "counterparty_code": counterparty.code,
            "billing_arrangement": counterparty.billing_arrangement,
            "commission_tax_rate": Decimal(counterparty.commission_tax_rate),
            "exception": (
                "UNSUPPORTED_BILLING_ARRANGEMENT"
                if counterparty.billing_arrangement == OTABillingArrangement.EXCEPTION_REVIEW
                else None
            ),
        }

    @staticmethod
    def calculate_expected_net(
        *,
        gross_fare,
        commission_rate=Decimal("0.00"),
        commission_amount=None,
        commission_tax_rate=Decimal("0.00"),
        commission_tax_amount=None,
        withholding_rate=Decimal("0.00"),
        withholding_amount=None,
        adjustments=Decimal("0.00"),
        billing_arrangement=OTABillingArrangement.OTA_INVOICE,
        currency="INR",
    ) -> dict:
        gross = OTACommercialService.quantize(gross_fare)
        commission_rate = Decimal(str(commission_rate or "0"))
        withholding_rate = Decimal(str(withholding_rate or "0"))
        commission_tax_rate = Decimal(str(commission_tax_rate or "0"))
        commission = (
            OTACommercialService.quantize(commission_amount)
            if commission_amount is not None
            else OTACommercialService.quantize(gross * commission_rate / Decimal("100"))
        )
        commission_tax = (
            OTACommercialService.quantize(commission_tax_amount)
            if commission_tax_amount is not None
            else OTACommercialService.quantize(commission * commission_tax_rate / Decimal("100"))
        )
        withholding = (
            OTACommercialService.quantize(withholding_amount)
            if withholding_amount is not None
            else OTACommercialService.quantize(gross * withholding_rate / Decimal("100"))
        )
        adjustment_amount = OTACommercialService.quantize(adjustments)
        net = OTACommercialService.quantize(
            gross - commission - commission_tax - withholding + adjustment_amount
        )
        exception = None
        if billing_arrangement == OTABillingArrangement.EXCEPTION_REVIEW:
            exception = "UNSUPPORTED_BILLING_ARRANGEMENT"
        explanation = {
            "formula": "gross_fare - commission_amount - commission_tax_amount - withholding_amount + adjustments = net_expected",
            "gross_fare": str(gross),
            "commission_amount": str(commission),
            "commission_tax_amount": str(commission_tax),
            "withholding_amount": str(withholding),
            "adjustments": str(adjustment_amount),
            "net_expected": str(net),
        }
        formula_total = OTACommercialService.quantize(
            gross - commission - commission_tax - withholding + adjustment_amount
        )
        if formula_total != net:
            exception = exception or "FORMULA_RECONCILIATION_FAILED"
        return {
            "currency": (currency or "INR").upper(),
            "billing_arrangement": billing_arrangement,
            "gross_customer_fare": str(gross),
            "commission_rate": str(OTACommercialService.quantize(commission_rate)),
            "commission_amount": str(commission),
            "commission_tax_rate": str(OTACommercialService.quantize(commission_tax_rate)),
            "commission_tax_amount": str(commission_tax),
            "withholding_rate": str(OTACommercialService.quantize(withholding_rate)),
            "withholding_amount": str(withholding),
            "adjustments": str(adjustment_amount),
            "expected_net_settlement": str(net),
            "formula_explanation": explanation,
            "exception": exception,
        }


class OTASettlementImportService:
    REQUIRED_LINE_FIELDS = ("provider_booking_id", "received_amount")

    @staticmethod
    def _amount(value) -> Decimal:
        amount = money(Decimal(str(value or "0")))
        if amount < Decimal("0.00"):
            raise ValidationError("Settlement amounts cannot be negative.")
        return amount

    @staticmethod
    def parse_csv(content: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(content or ""))
        lines = []
        for row in reader:
            lines.append({
                "provider_booking_id": row.get("provider_booking_id") or row.get("booking_reference") or row.get("booking_id"),
                "received_amount": row.get("received_amount") or row.get("amount") or row.get("net_amount"),
                "currency": row.get("currency") or "INR",
                "source": "CSV",
                "raw": row,
            })
        return lines

    @classmethod
    def import_batch(
        cls,
        *,
        counterparty_code: str,
        batch_reference: str,
        lines: Optional[list[dict]] = None,
        csv_content: str = "",
        currency: str = "INR",
        payout_date=None,
        source_system: str = "API",
        actor=None,
        idempotency_key: str = "",
    ) -> dict:
        if not counterparty_code:
            raise ValidationError({"counterparty_code": "Counterparty code is required."})
        if not batch_reference:
            raise ValidationError({"batch_reference": "Batch reference is required."})
        import_lines = list(lines or [])
        if csv_content:
            import_lines.extend(cls.parse_csv(csv_content))
        if not import_lines:
            raise ValidationError({"lines": "At least one settlement line is required."})

        normalized_currency = (currency or "INR").strip().upper()
        refs = [
            str(line.get("provider_booking_id") or "").strip()
            for line in import_lines
        ]
        if any(not ref for ref in refs):
            raise ValidationError({"provider_booking_id": "Every settlement line needs a provider booking reference."})
        duplicates = {ref for ref, count in Counter(refs).items() if count > 1}
        seen = set()

        with transaction.atomic():
            try:
                counterparty = OTACounterparty.objects.select_for_update().get(code__iexact=counterparty_code)
            except OTACounterparty.DoesNotExist:
                raise ValidationError({"counterparty_code": "Unknown OTA counterparty."})
            batch, created = OTASettlementBatch.objects.select_for_update().get_or_create(
                counterparty=counterparty,
                batch_reference=batch_reference,
                defaults={
                    "currency": normalized_currency,
                    "payout_beneficiary_name": counterparty.payout_beneficiary_name,
                    "payout_beneficiary_account": counterparty.payout_beneficiary_account,
                    "payout_date": payout_date,
                    "source_system": source_system,
                    "monetary_sources": {"import": source_system},
                },
            )
            batch.currency = normalized_currency
            batch.payout_date = payout_date or batch.payout_date
            batch.source_system = source_system
            batch.lines.all().delete()

            classifications = Counter()
            totals = {
                "gross_amount": Decimal("0.00"),
                "commission_amount": Decimal("0.00"),
                "withholding_amount": Decimal("0.00"),
                "net_expected": Decimal("0.00"),
                "actual_payout_amount": Decimal("0.00"),
            }
            response_lines = []

            for index, raw_line in enumerate(import_lines, start=1):
                provider_ref = str(raw_line.get("provider_booking_id") or "").strip()
                line_currency = str(raw_line.get("currency") or normalized_currency).strip().upper()
                if line_currency != normalized_currency:
                    raise ValidationError({"currency": f"Line {index} currency does not match batch currency."})
                received = cls._amount(raw_line.get("received_amount"))
                snapshot = OTABookingSnapshot.objects.filter(
                    counterparty=counterparty,
                    provider_booking_id=provider_ref,
                ).select_related("trip").first()

                classification = OTASettlementLineClassification.PENDING
                expected = Decimal("0.00")
                line_status = OTASettlementStatus.EXCEPTION
                booking_for_line = snapshot

                if provider_ref in duplicates and provider_ref in seen:
                    classification = OTASettlementLineClassification.DUPLICATE
                    booking_for_line = None
                elif snapshot is None:
                    classification = OTASettlementLineClassification.MISSING
                else:
                    expected = money(snapshot.net_expected)
                    if snapshot.settlement_status == OTASettlementStatus.CANCELLED or snapshot.trip.status.upper() == "CANCELLED":
                        classification = OTASettlementLineClassification.CANCELLED
                        line_status = OTASettlementStatus.EXCEPTION
                    elif received == expected:
                        classification = OTASettlementLineClassification.EXACT
                        line_status = OTASettlementStatus.SETTLED
                    elif received < expected:
                        classification = OTASettlementLineClassification.SHORT
                    else:
                        classification = OTASettlementLineClassification.EXCESS

                variance = money(received - expected)
                line = OTASettlementLine.objects.create(
                    batch=batch,
                    booking_snapshot=booking_for_line,
                    provider_booking_id=provider_ref,
                    currency=normalized_currency,
                    expected_amount=expected,
                    received_amount=received,
                    variance_amount=variance,
                    classification=classification,
                    settlement_status=line_status,
                    monetary_sources={
                        "expected_amount": "OTA_BOOKING_SNAPSHOT" if snapshot else "UNMATCHED_PROVIDER_REFERENCE",
                        "received_amount": source_system,
                        "provider_booking_id": source_system,
                    },
                )
                seen.add(provider_ref)
                classifications[classification] += 1
                totals["actual_payout_amount"] += received
                if snapshot and classification not in (
                    OTASettlementLineClassification.DUPLICATE,
                    OTASettlementLineClassification.MISSING,
                ):
                    totals["gross_amount"] += snapshot.gross_fare
                    totals["commission_amount"] += snapshot.commission_amount + snapshot.commission_tax
                    totals["withholding_amount"] += snapshot.withholding_amount
                    totals["net_expected"] += expected
                    if classification == OTASettlementLineClassification.EXACT:
                        snapshot.settlement_status = OTASettlementStatus.SETTLED
                    else:
                        snapshot.settlement_status = OTASettlementStatus.EXCEPTION
                    snapshot.save(update_fields=["settlement_status", "updated_at"])

                response_lines.append({
                    "id": line.id,
                    "provider_booking_id": provider_ref,
                    "booking_snapshot_id": snapshot.id if snapshot else None,
                    "classification": classification,
                    "expected_amount": str(expected),
                    "received_amount": str(received),
                    "variance_amount": str(variance),
                })

            batch.gross_amount = money(totals["gross_amount"])
            batch.commission_amount = money(totals["commission_amount"])
            batch.withholding_amount = money(totals["withholding_amount"])
            batch.net_expected = money(totals["net_expected"])
            batch.actual_payout_amount = money(totals["actual_payout_amount"])
            batch.settlement_status = (
                OTASettlementStatus.SETTLED
                if set(classifications) == {OTASettlementLineClassification.EXACT}
                else OTASettlementStatus.EXCEPTION
            )
            batch.monetary_sources = {
                "gross_amount": "MATCHED_OTA_BOOKING_SNAPSHOTS",
                "commission_amount": "MATCHED_OTA_BOOKING_SNAPSHOTS",
                "withholding_amount": "MATCHED_OTA_BOOKING_SNAPSHOTS",
                "net_expected": "MATCHED_OTA_BOOKING_SNAPSHOTS",
                "actual_payout_amount": source_system,
            }
            batch.save()

            OTAAuditEvent.objects.create(
                action="SETTLEMENT_IMPORT" if created else "SETTLEMENT_IMPORT_RERUN",
                entity_type="OTASettlementBatch",
                entity_id=str(batch.id),
                actor=actor if (actor and actor.is_authenticated) else None,
                request_idempotency_key=idempotency_key,
                snapshot={
                    "counterparty_code": counterparty.code,
                    "batch_reference": batch_reference,
                    "classifications": dict(classifications),
                    "line_count": len(response_lines),
                },
            )

        return {
            "batch_id": batch.id,
            "batch_reference": batch.batch_reference,
            "status": batch.settlement_status,
            "currency": batch.currency,
            "net_expected": str(batch.net_expected),
            "actual_payout_amount": str(batch.actual_payout_amount),
            "classification_counts": dict(classifications),
            "lines": response_lines,
        }


class OTAProfitabilityReportService:
    @staticmethod
    def build(counterparty_code="", status="") -> dict:
        from .models import (
            ExpenseStatus,
            JournalEntry,
            OTABookingSnapshot,
            OTASettlementLineClassification,
            TripCharge,
            TripExpense,
        )

        snapshots = (
            OTABookingSnapshot.objects.select_related("trip", "trip__vehicle", "trip__driver", "counterparty")
            .prefetch_related("settlement_lines", "settlement_lines__batch")
            .order_by("-trip__pickup_at", "-id")
        )
        if counterparty_code:
            snapshots = snapshots.filter(counterparty__code__iexact=counterparty_code)
        if status:
            snapshots = snapshots.filter(settlement_status=status)

        rows = []
        totals = {
            "gross_fare": Decimal("0.00"),
            "net_expected": Decimal("0.00"),
            "received_amount": Decimal("0.00"),
            "approved_costs": Decimal("0.00"),
            "contribution_margin": Decimal("0.00"),
        }
        exception_count = 0
        incomplete_count = 0

        for snapshot in snapshots:
            trip = snapshot.trip
            settlement_line = (
                snapshot.settlement_lines.select_related("batch")
                .order_by("-updated_at", "-id")
                .first()
            )
            approved_expenses = TripExpense.objects.filter(
                trip=trip,
                status__in=[ExpenseStatus.APPROVED, ExpenseStatus.SETTLED],
            )
            pending_expenses = TripExpense.objects.filter(trip=trip, status=ExpenseStatus.SUBMITTED).exists()
            approved_expense_total = approved_expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            approved_charge_total = Decimal("0.00")
            try:
                closeout = trip.closeout
            except Trip.closeout.RelatedObjectDoesNotExist:
                closeout = None
            closeout_ready = False
            if closeout:
                approved_charge_total = closeout.extra_charges.filter(is_approved=True).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
                closeout_ready = bool(closeout.billing_ready)

            approved_costs = money(approved_expense_total + approved_charge_total)
            received = money(settlement_line.received_amount) if settlement_line else Decimal("0.00")
            revenue_basis = "ACTUAL_SETTLEMENT" if settlement_line else "EXPECTED_NET"
            fleet_revenue = received if settlement_line else money(snapshot.net_expected)
            contribution_margin = money(fleet_revenue - approved_costs)
            margin_incomplete = pending_expenses or not closeout_ready
            if margin_incomplete:
                incomplete_count += 1
            if settlement_line and settlement_line.classification != OTASettlementLineClassification.EXACT:
                exception_count += 1
            elif not settlement_line:
                exception_count += 1

            booking_journal = JournalEntry.objects.filter(source_type="OTA_BOOKING", source_id=str(snapshot.id)).first()
            settlement_journal = (
                JournalEntry.objects.filter(source_type="OTA_SETTLEMENT_LINE", source_id=str(settlement_line.id)).first()
                if settlement_line
                else None
            )
            row = {
                "trip": {
                    "id": trip.id,
                    "route": f"{trip.pickup_city} to {trip.drop_city}",
                    "pickup_at": trip.pickup_at.isoformat() if trip.pickup_at else None,
                    "status": trip.status,
                    "customer_name": trip.customer_name,
                    "vehicle": trip.vehicle.registration_number if trip.vehicle_id else "",
                    "driver": trip.driver.name if trip.driver_id else "",
                },
                "external": {
                    "provider_code": snapshot.counterparty.code,
                    "provider_name": snapshot.counterparty.name,
                    "provider_booking_id": snapshot.provider_booking_id,
                    "partner_reference_number": snapshot.partner_reference_number,
                    "provider_trip_id": snapshot.provider_trip_id,
                },
                "waterfall": {
                    "currency": snapshot.currency,
                    "gross_fare": str(snapshot.gross_fare),
                    "fare_tax": str(snapshot.fare_tax),
                    "commission_amount": str(snapshot.commission_amount),
                    "commission_tax": str(snapshot.commission_tax),
                    "withholding_amount": str(snapshot.withholding_amount),
                    "cancellation_amount": str(snapshot.cancellation_amount),
                    "net_expected": str(snapshot.net_expected),
                    "formula": "gross_fare - commission_amount - commission_tax - withholding_amount - cancellation_amount = net_expected",
                },
                "settlement": {
                    "batch_id": settlement_line.batch_id if settlement_line else None,
                    "batch_reference": settlement_line.batch.batch_reference if settlement_line else "",
                    "payout_date": settlement_line.batch.payout_date.isoformat() if settlement_line and settlement_line.batch.payout_date else None,
                    "classification": settlement_line.classification if settlement_line else "MISSING",
                    "status": settlement_line.settlement_status if settlement_line else snapshot.settlement_status,
                    "expected_amount": str(settlement_line.expected_amount) if settlement_line else str(snapshot.net_expected),
                    "received_amount": str(received),
                    "variance_amount": str(settlement_line.variance_amount) if settlement_line else str(money(Decimal("0.00") - snapshot.net_expected)),
                },
                "profitability": {
                    "revenue_basis": revenue_basis,
                    "fleet_revenue": str(fleet_revenue),
                    "approved_expenses": str(money(approved_expense_total)),
                    "approved_closeout_charges": str(money(approved_charge_total)),
                    "approved_costs": str(approved_costs),
                    "contribution_margin": str(contribution_margin),
                    "margin_incomplete": margin_incomplete,
                    "incomplete_reasons": [
                        reason
                        for reason, enabled in (
                            ("CLOSEOUT_NOT_BILLING_READY", not closeout_ready),
                            ("PENDING_EXPENSE_REVIEW", pending_expenses),
                        )
                        if enabled
                    ],
                },
                "journals": {
                    "booking_journal": booking_journal.entry_number if booking_journal else "",
                    "settlement_journal": settlement_journal.entry_number if settlement_journal else "",
                },
            }
            rows.append(row)
            totals["gross_fare"] += snapshot.gross_fare
            totals["net_expected"] += snapshot.net_expected
            totals["received_amount"] += received
            totals["approved_costs"] += approved_costs
            totals["contribution_margin"] += contribution_margin

        return {
            "summary": {
                "trip_count": len(rows),
                "exception_count": exception_count,
                "incomplete_margin_count": incomplete_count,
                "gross_fare": str(money(totals["gross_fare"])),
                "net_expected": str(money(totals["net_expected"])),
                "received_amount": str(money(totals["received_amount"])),
                "approved_costs": str(money(totals["approved_costs"])),
                "contribution_margin": str(money(totals["contribution_margin"])),
            },
            "results": rows,
        }


class AuditService:
    @staticmethod
    def serialize_model(instance) -> dict:
        import uuid
        import json
        if not instance:
            return {}
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if isinstance(value, (datetime.date, datetime.datetime)):
                data[field.name] = value.isoformat()
            elif isinstance(value, Decimal):
                data[field.name] = str(value)
            elif isinstance(value, uuid.UUID):
                data[field.name] = str(value)
            elif hasattr(value, "id"):
                data[field.name] = str(value.id)
            else:
                try:
                    data[field.name] = value
                except Exception:
                    data[field.name] = str(value)
        return data

    @staticmethod
    def compute_hash(data: dict) -> str:
        import json
        import hashlib
        from django.core.serializers.json import DjangoJSONEncoder
        serialized = json.dumps(data, sort_keys=True, cls=DjangoJSONEncoder)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def record_event(actor, action, instance, before_snapshot=None, reason="", request_idempotency_key="") -> "FinancialAuditEvent":
        from .models import FinancialAuditEvent
        
        entity_type = instance.__class__.__name__
        entity_id = str(instance.id)
        
        after_snapshot = AuditService.serialize_model(instance)
        after_hash = AuditService.compute_hash(after_snapshot)
        
        before_snapshot = before_snapshot or {}
        before_hash = AuditService.compute_hash(before_snapshot) if before_snapshot else ""
        
        return FinancialAuditEvent.objects.create(
            actor=actor if (actor and actor.is_authenticated) else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_snapshot=before_snapshot,
            before_snapshot_hash=before_hash,
            after_snapshot=after_snapshot,
            after_snapshot_hash=after_hash,
            reason=reason,
            request_idempotency_key=request_idempotency_key,
        )


class CreditNoteService:
    @staticmethod
    @transaction.atomic
    def create_credit_note(invoice, reason, lines_data, created_by=None) -> "CreditNote":
        from .models import CreditNote, CreditNoteLine, InvoiceStatus, CreditNoteStatus, FinancialYear
        from django.db.models import Sum

        if invoice.status not in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]:
            raise ValidationError(f"Credit notes can only be created for ISSUED, SENT, or PARTIALLY_PAID invoices, not {invoice.status}.")

        today = datetime.date.today()
        fy = invoice.financial_year
        if not fy:
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
        if not fy:
            raise ValidationError("No active financial year found to generate sequence.")
        
        from .models import DocumentSequence, DocumentType
        seq, _ = DocumentSequence.objects.get_or_create(
            legal_entity=invoice.legal_entity,
            financial_year=fy,
            document_type=DocumentType.CREDIT_NOTE,
            defaults={"prefix": "CN/", "current_number": 0, "padding_digits": 5}
        )
        seq.current_number += 1
        seq.save(update_fields=["current_number"])
        cn_number = f"{seq.prefix}{fy.name.split()[-1]}/{str(seq.current_number).zfill(seq.padding_digits)}"

        credit_note = CreditNote.objects.create(
            credit_note_number=cn_number,
            invoice=invoice,
            legal_entity=invoice.legal_entity,
            reason=reason,
            total_amount=Decimal("0.00"),
            taxable_amount=Decimal("0.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            igst_amount=Decimal("0.00"),
            status=CreditNoteStatus.DRAFT,
            created_by=created_by
        )

        total_amount = Decimal("0.00")
        taxable_amount = Decimal("0.00")
        cgst_amount = Decimal("0.00")
        sgst_amount = Decimal("0.00")
        igst_amount = Decimal("0.00")

        for line_data in lines_data:
            inv_line_id = line_data.get("invoice_line_id")
            description = line_data.get("description", "")
            qty = Decimal(str(line_data.get("quantity", 1)))
            unit_rate = Decimal(str(line_data.get("unit_rate", 0)))

            if not description and inv_line_id:
                from .models import InvoiceLine
                inv_line = InvoiceLine.objects.get(id=inv_line_id)
                description = inv_line.description

            line_taxable = qty * unit_rate
            
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = Decimal("0.00")
            
            if inv_line_id:
                from .models import InvoiceLine
                inv_line = InvoiceLine.objects.get(id=inv_line_id)
                cgst_rate = inv_line.cgst_rate
                sgst_rate = inv_line.sgst_rate
                igst_rate = inv_line.igst_rate
                
                already_credited_qty = CreditNoteLine.objects.filter(
                    credit_note__invoice=invoice,
                    credit_note__status=CreditNoteStatus.APPROVED,
                    invoice_line=inv_line
                ).aggregate(total=Sum("quantity"))["total"] or Decimal("0.00")
                if already_credited_qty + qty > inv_line.quantity:
                    raise ValidationError(f"Quantity to credit ({qty}) exceeds remaining invoiced quantity ({inv_line.quantity - already_credited_qty}).")

            line_cgst = (line_taxable * cgst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_sgst = (line_taxable * sgst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_igst = (line_taxable * igst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_total = line_taxable + line_cgst + line_sgst + line_igst

            CreditNoteLine.objects.create(
                credit_note=credit_note,
                invoice_line_id=inv_line_id,
                description=description,
                quantity=qty,
                unit_rate=unit_rate,
                taxable_value=line_taxable,
                cgst_rate=cgst_rate,
                cgst_amount=line_cgst,
                sgst_rate=sgst_rate,
                sgst_amount=line_sgst,
                igst_rate=igst_rate,
                igst_amount=line_igst,
                line_total=line_total
            )

            total_amount += line_total
            taxable_amount += line_taxable
            cgst_amount += line_cgst
            sgst_amount += line_sgst
            igst_amount += line_igst

        credit_note.total_amount = total_amount
        credit_note.taxable_amount = taxable_amount
        credit_note.cgst_amount = cgst_amount
        credit_note.sgst_amount = sgst_amount
        credit_note.igst_amount = igst_amount
        credit_note.save(update_fields=["total_amount", "taxable_amount", "cgst_amount", "sgst_amount", "igst_amount"])

        if total_amount > invoice.balance_amount:
            raise ValidationError(f"Credit note amount ({total_amount}) cannot exceed invoice remaining balance ({invoice.balance_amount}).")

        AuditService.record_event(created_by, "CREATE_CREDIT_NOTE", credit_note)
        return credit_note

    @staticmethod
    @transaction.atomic
    def approve_credit_note(credit_note, approved_by=None) -> "CreditNote":
        from .models import CreditNoteStatus, InvoiceStatus
        if credit_note.status != CreditNoteStatus.DRAFT:
            raise ValidationError(f"Only DRAFT credit notes can be approved, not {credit_note.status}.")

        credit_note.status = CreditNoteStatus.APPROVED
        credit_note.approved_by = approved_by
        credit_note.approved_at = timezone.now()
        credit_note.save(update_fields=["status", "approved_by", "approved_at"])

        PostingEngine.post_credit_note_journal(credit_note)

        invoice = credit_note.invoice
        invoice.balance_amount -= credit_note.total_amount
        if invoice.balance_amount <= Decimal("0.00"):
            invoice.balance_amount = Decimal("0.00")
            invoice.status = InvoiceStatus.PAID
        elif invoice.balance_amount < invoice.total_amount:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        invoice.save(update_fields=["balance_amount", "status"])

        AuditService.record_event(approved_by, "APPROVE_CREDIT_NOTE", credit_note)
        return credit_note

    @staticmethod
    @transaction.atomic
    def void_credit_note(credit_note, voided_by=None) -> "CreditNote":
        from .models import CreditNoteStatus, InvoiceStatus, JournalEntry
        if credit_note.status == CreditNoteStatus.VOID:
            raise ValidationError("Credit note is already VOID.")

        original_status = credit_note.status
        credit_note.status = CreditNoteStatus.VOID
        credit_note.save(update_fields=["status"])

        if original_status == CreditNoteStatus.APPROVED:
            journal = JournalEntry.objects.filter(source_type="CREDIT_NOTE", source_id=str(credit_note.id)).first()
            if journal:
                PostingEngine.post_journal_reversal(journal, "Voiding credit note")

            invoice = credit_note.invoice
            invoice.balance_amount += credit_note.total_amount
            if invoice.balance_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.ISSUED
            else:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            invoice.save(update_fields=["balance_amount", "status"])

        AuditService.record_event(voided_by, "VOID_CREDIT_NOTE", credit_note)
        return credit_note


class DebitNoteService:
    @staticmethod
    @transaction.atomic
    def create_debit_note(invoice, reason, lines_data, created_by=None) -> "DebitNote":
        from .models import DebitNote, DebitNoteLine, InvoiceStatus, DebitNoteStatus, FinancialYear
        from django.db.models import Sum

        if invoice.status not in [InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID]:
            raise ValidationError(f"Debit notes can only be created for valid invoices, not {invoice.status}.")

        today = datetime.date.today()
        fy = invoice.financial_year
        if not fy:
            fy = FinancialYear.objects.filter(start_date__lte=today, end_date__gte=today, is_closed=False).first()
        if not fy:
            raise ValidationError("No active financial year found to generate sequence.")
        
        from .models import DocumentSequence, DocumentType
        seq, _ = DocumentSequence.objects.get_or_create(
            legal_entity=invoice.legal_entity,
            financial_year=fy,
            document_type=DocumentType.DEBIT_NOTE,
            defaults={"prefix": "DN/", "current_number": 0, "padding_digits": 5}
        )
        seq.current_number += 1
        seq.save(update_fields=["current_number"])
        dn_number = f"{seq.prefix}{fy.name.split()[-1]}/{str(seq.current_number).zfill(seq.padding_digits)}"

        debit_note = DebitNote.objects.create(
            debit_note_number=dn_number,
            invoice=invoice,
            legal_entity=invoice.legal_entity,
            reason=reason,
            total_amount=Decimal("0.00"),
            taxable_amount=Decimal("0.00"),
            cgst_amount=Decimal("0.00"),
            sgst_amount=Decimal("0.00"),
            igst_amount=Decimal("0.00"),
            status=DebitNoteStatus.DRAFT,
            created_by=created_by
        )

        total_amount = Decimal("0.00")
        taxable_amount = Decimal("0.00")
        cgst_amount = Decimal("0.00")
        sgst_amount = Decimal("0.00")
        igst_amount = Decimal("0.00")

        for line_data in lines_data:
            inv_line_id = line_data.get("invoice_line_id")
            description = line_data.get("description", "")
            qty = Decimal(str(line_data.get("quantity", 1)))
            unit_rate = Decimal(str(line_data.get("unit_rate", 0)))

            if not description and inv_line_id:
                from .models import InvoiceLine
                inv_line = InvoiceLine.objects.get(id=inv_line_id)
                description = inv_line.description

            line_taxable = qty * unit_rate
            
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = Decimal("0.00")
            
            if inv_line_id:
                from .models import InvoiceLine
                inv_line = InvoiceLine.objects.get(id=inv_line_id)
                cgst_rate = inv_line.cgst_rate
                sgst_rate = inv_line.sgst_rate
                igst_rate = inv_line.igst_rate

            line_cgst = (line_taxable * cgst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_sgst = (line_taxable * sgst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_igst = (line_taxable * igst_rate / Decimal("100.00")).quantize(Decimal("0.01"))
            line_total = line_taxable + line_cgst + line_sgst + line_igst

            DebitNoteLine.objects.create(
                debit_note=debit_note,
                invoice_line_id=inv_line_id,
                description=description,
                quantity=qty,
                unit_rate=unit_rate,
                taxable_value=line_taxable,
                cgst_rate=cgst_rate,
                cgst_amount=line_cgst,
                sgst_rate=sgst_rate,
                sgst_amount=line_sgst,
                igst_rate=igst_rate,
                igst_amount=line_igst,
                line_total=line_total
            )

            total_amount += line_total
            taxable_amount += line_taxable
            cgst_amount += line_cgst
            sgst_amount += line_sgst
            igst_amount += line_igst

        debit_note.total_amount = total_amount
        debit_note.taxable_amount = taxable_amount
        debit_note.cgst_amount = cgst_amount
        debit_note.sgst_amount = sgst_amount
        debit_note.igst_amount = igst_amount
        debit_note.save(update_fields=["total_amount", "taxable_amount", "cgst_amount", "sgst_amount", "igst_amount"])

        AuditService.record_event(created_by, "CREATE_DEBIT_NOTE", debit_note)
        return debit_note

    @staticmethod
    @transaction.atomic
    def approve_debit_note(debit_note, approved_by=None) -> "DebitNote":
        from .models import DebitNoteStatus, InvoiceStatus
        if debit_note.status != DebitNoteStatus.DRAFT:
            raise ValidationError(f"Only DRAFT debit notes can be approved, not {debit_note.status}.")

        debit_note.status = DebitNoteStatus.APPROVED
        debit_note.approved_by = approved_by
        debit_note.approved_at = timezone.now()
        debit_note.save(update_fields=["status", "approved_by", "approved_at"])

        PostingEngine.post_debit_note_journal(debit_note)

        invoice = debit_note.invoice
        invoice.balance_amount += debit_note.total_amount
        invoice.total_amount += debit_note.total_amount
        invoice.taxable_amount += debit_note.taxable_amount
        invoice.cgst_amount += debit_note.cgst_amount
        invoice.sgst_amount += debit_note.sgst_amount
        invoice.igst_amount += debit_note.igst_amount

        if invoice.balance_amount > Decimal("0.00"):
            if invoice.balance_amount < invoice.total_amount:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            else:
                invoice.status = InvoiceStatus.ISSUED
        invoice.save(update_fields=["balance_amount", "total_amount", "taxable_amount", "cgst_amount", "sgst_amount", "igst_amount", "status"])

        AuditService.record_event(approved_by, "APPROVE_DEBIT_NOTE", debit_note)
        return debit_note

    @staticmethod
    @transaction.atomic
    def void_debit_note(debit_note, voided_by=None) -> "DebitNote":
        from .models import DebitNoteStatus, InvoiceStatus, JournalEntry
        if debit_note.status == DebitNoteStatus.VOID:
            raise ValidationError("Debit note is already VOID.")

        original_status = debit_note.status
        debit_note.status = DebitNoteStatus.VOID
        debit_note.save(update_fields=["status"])

        if original_status == DebitNoteStatus.APPROVED:
            journal = JournalEntry.objects.filter(source_type="DEBIT_NOTE", source_id=str(debit_note.id)).first()
            if journal:
                PostingEngine.post_journal_reversal(journal, "Voiding debit note")

            invoice = debit_note.invoice
            invoice.balance_amount -= debit_note.total_amount
            invoice.total_amount -= debit_note.total_amount
            invoice.taxable_amount -= debit_note.taxable_amount
            invoice.cgst_amount -= debit_note.cgst_amount
            invoice.sgst_amount -= debit_note.sgst_amount
            invoice.igst_amount -= debit_note.igst_amount

            if invoice.balance_amount <= Decimal("0.00"):
                invoice.balance_amount = Decimal("0.00")
                invoice.status = InvoiceStatus.PAID
            elif invoice.balance_amount < invoice.total_amount:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            else:
                invoice.status = InvoiceStatus.ISSUED

            invoice.save(update_fields=["balance_amount", "total_amount", "taxable_amount", "cgst_amount", "sgst_amount", "igst_amount", "status"])

        AuditService.record_event(voided_by, "VOID_DEBIT_NOTE", debit_note)
        return debit_note
