import datetime
from decimal import ROUND_CEILING
from dataclasses import dataclass
from decimal import Decimal
from django.db import transaction
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
    TripCloseout,
    CloseoutStatus,
)
from .tax_service import TaxService, money
from fleet.models import MeteringPolicy, PricingAmountStatus, Trip, TripStatus


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
    def create_from_trip_completion(trip_id: int, event_key: str | None = None) -> TripCloseout:
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
        return CloseoutService.derive_actual_quantities(closeout)


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def generate_invoice_draft(legal_entity: LegalEntity, trip_ids: list, created_by=None) -> Invoice:
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
    def post_invoice_journal(invoice: Invoice) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine

        with transaction.atomic():
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
    def post_fuel_journal(fuel_transaction, trip_expense) -> "JournalEntry":
        from .models import LedgerAccount, AccountType, JournalEntry, JournalLine
        with transaction.atomic():
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
    def record_receipt(legal_entity, customer, amount, payment_method="BANK_TRANSFER", reference_number="", created_by=None):
        from .models import PaymentReceipt
        with transaction.atomic():
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
                payment_method=payment_method,
                reference_number=reference_number,
                created_by=created_by,
            )
            return receipt

    @staticmethod
    def allocate_payment(receipt, invoice, amount, tds_amount=Decimal("0.00")):
        from .models import PaymentAllocation
        if amount > receipt.unapplied_amount:
            raise ValidationError("Allocation amount cannot exceed receipt unapplied balance.")
        if (amount + tds_amount) > invoice.balance_amount:
            raise ValidationError("Allocation amount cannot exceed invoice remaining balance.")

        with transaction.atomic():
            allocation = PaymentAllocation.objects.create(
                receipt=receipt,
                invoice=invoice,
                allocated_amount=amount,
                tds_amount=tds_amount,
            )

            receipt.unapplied_amount -= amount
            receipt.save()

            total_credit = amount + tds_amount
            invoice.paid_amount += total_credit
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.PAID
            elif invoice.paid_amount > Decimal("0.00"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            invoice.save()

            return allocation
