import datetime
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import models

from .models import (
    CorporateContract,
    CorporateCustomer,
    ContractRate,
    ContractAllowance,
    DutyType,
)
from .rate_resolver import RateResolutionError, resolve_rate

CALCULATION_VERSION = "contract-quote-v1"
UNIFIED_CALCULATION_VERSION = "unified-rate-card-v1"


class PricingError(Exception):
    pass


def quantize_decimal(value):
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_package_quote(
    package,
    *,
    planned_hours=0,
    planned_km=0,
    outstation_days=1,
    waiting_hours=0,
    night_charge_count=0,
    driver_allowance_days=0,
    resolution=None,
):
    """Calculate an immutable-ready quote payload from any canonical package."""

    hours = Decimal(str(planned_hours or 0))
    kilometres = Decimal(str(planned_km or 0))
    days = max(Decimal("1"), Decimal(str(outstation_days or 1)))
    waiting = Decimal(str(waiting_hours or 0))
    nights = Decimal(str(night_charge_count or 0))
    allowance_days = Decimal(str(driver_allowance_days or 0))
    if min(hours, kilometres, waiting, nights, allowance_days) < Decimal("0"):
        raise PricingError("Quote input quantities cannot be negative.")

    is_outstation = package.duty_type == DutyType.OUTSTATION
    base_multiplier = days if is_outstation else Decimal("1")
    included_hours = Decimal(package.included_hours) * base_multiplier
    included_km = Decimal(package.included_km) * base_multiplier
    daily_minimum = Decimal(package.daily_minimum_km) * days if is_outstation else Decimal("0")
    effective_km = max(kilometres, daily_minimum)
    excess_hours = max(Decimal("0"), hours - included_hours)
    excess_km = max(Decimal("0"), effective_km - included_km)

    items = {
        "base_charge": quantize_decimal(package.base_rate * base_multiplier),
        "excess_hour_charge": quantize_decimal(excess_hours * package.extra_hour_rate),
        "excess_km_charge": quantize_decimal(excess_km * package.extra_km_rate),
        "waiting_charge": quantize_decimal(waiting * package.waiting_rate_per_hour),
        "night_charge": quantize_decimal(nights * package.night_charge),
        "driver_allowance": quantize_decimal(allowance_days * package.driver_allowance_per_day),
    }
    pre_discount = quantize_decimal(sum(items.values(), Decimal("0")))
    discount_amount = quantize_decimal(pre_discount * package.discount_percent / Decimal("100"))
    taxable_amount = quantize_decimal(pre_discount - discount_amount)
    cgst_amount = quantize_decimal(taxable_amount * package.cgst_rate / Decimal("100"))
    sgst_amount = quantize_decimal(taxable_amount * package.sgst_rate / Decimal("100"))
    tax_amount = quantize_decimal(cgst_amount + sgst_amount)
    total_amount = quantize_decimal(taxable_amount + tax_amount)
    ota_commercial = None
    if package.rate_book.book_type == "OTA":
        if not package.ota_terms_configured:
            raise PricingError(
                f"OTA settlement terms are missing for package '{package.code}'."
            )
        commission = quantize_decimal(total_amount * package.ota_commission_rate / Decimal("100"))
        withholding = quantize_decimal(total_amount * package.ota_withholding_rate / Decimal("100"))
        ota_commercial = {
            "gross_customer_fare": str(total_amount),
            "commission_rate": str(quantize_decimal(package.ota_commission_rate)),
            "commission_amount": str(commission),
            "withholding_rate": str(quantize_decimal(package.ota_withholding_rate)),
            "withholding_amount": str(withholding),
            "expected_net_settlement": str(quantize_decimal(total_amount - commission - withholding)),
            "exception": None,
        }

    return {
        "calculation_version": UNIFIED_CALCULATION_VERSION,
        "rate_book": {
            "id": package.rate_book_id,
            "code": package.rate_book.code,
            "version": package.rate_book.version,
            "type": package.rate_book.book_type,
            "currency": package.rate_book.currency,
        },
        "package": {
            "id": package.id,
            "code": package.code,
            "name": package.name,
            "duty_type": package.duty_type,
            "metering_policy": package.metering_policy,
        },
        "rate_terms": {
            "base_rate": str(quantize_decimal(package.base_rate)),
            "included_hours": str(package.included_hours),
            "included_km": str(package.included_km),
            "extra_hour_rate": str(quantize_decimal(package.extra_hour_rate)),
            "extra_km_rate": str(quantize_decimal(package.extra_km_rate)),
            "daily_minimum_km": str(package.daily_minimum_km),
            "waiting_rate_per_hour": str(quantize_decimal(package.waiting_rate_per_hour)),
            "night_charge": str(quantize_decimal(package.night_charge)),
            "driver_allowance_per_day": str(quantize_decimal(package.driver_allowance_per_day)),
            "discount_percent": str(quantize_decimal(package.discount_percent)),
            "cgst_rate": str(quantize_decimal(package.cgst_rate)),
            "sgst_rate": str(quantize_decimal(package.sgst_rate)),
        },
        "resolution": resolution.as_dict() if resolution else {},
        "inputs": {
            "planned_hours": str(hours),
            "planned_km": str(kilometres),
            "effective_km": str(effective_km),
            "outstation_days": str(days),
            "waiting_hours": str(waiting),
            "night_charge_count": str(nights),
            "driver_allowance_days": str(allowance_days),
        },
        "included": {
            "hours": str(included_hours),
            "km": str(included_km),
            "daily_minimum_km": str(daily_minimum),
        },
        "usage": {
            "excess_hours": str(excess_hours),
            "excess_km": str(excess_km),
        },
        "itemized_charges": {key: str(value) for key, value in items.items()},
        "pre_discount_amount": str(pre_discount),
        "discount_percent": str(quantize_decimal(package.discount_percent)),
        "discount_amount": str(discount_amount),
        "taxable_amount": str(taxable_amount),
        "taxes": {
            "cgst_rate": str(quantize_decimal(package.cgst_rate)),
            "cgst_amount": str(cgst_amount),
            "sgst_rate": str(quantize_decimal(package.sgst_rate)),
            "sgst_amount": str(sgst_amount),
        },
        "tax_amount": str(tax_amount),
        "gross_amount": str(total_amount),
        "total_amount": str(total_amount),
        "ota_commercial": ota_commercial,
    }


def calculate_unified_quote(**inputs):
    calculation_inputs = {
        key: inputs.get(key, 0)
        for key in (
            "planned_hours",
            "planned_km",
            "outstation_days",
            "waiting_hours",
            "night_charge_count",
            "driver_allowance_days",
        )
    }
    try:
        resolution = resolve_rate(
            booking_type=inputs.get("booking_type"),
            pickup_datetime=inputs.get("pickup_datetime"),
            pickup_city=inputs.get("pickup_city"),
            drop_city=inputs.get("drop_city", ""),
            vehicle_category=inputs.get("vehicle_category"),
            duty_type=inputs.get("duty_type"),
            contract_id=inputs.get("contract_id"),
            customer_id=inputs.get("customer_id"),
            ota_source=inputs.get("ota_source", ""),
        )
    except RateResolutionError as exc:
        raise PricingError(str(exc)) from exc
    return calculate_package_quote(
        resolution.package,
        resolution=resolution,
        **calculation_inputs,
    )


def calculate_quote(
    customer_id,
    pickup_datetime,
    pickup_city,
    vehicle_category,
    duty_type,
    planned_hours=0,
    planned_km=0,
    outstation_days=1,
    requested_allowances=None,
):
    if isinstance(pickup_datetime, str):
        try:
            pickup_datetime = datetime.datetime.fromisoformat(pickup_datetime)
        except ValueError:
            raise PricingError("Invalid pickup_datetime format.")

    if timezone.is_naive(pickup_datetime):
        pickup_date = pickup_datetime.date()
    else:
        pickup_date = timezone.localtime(pickup_datetime).date()

    try:
        customer = CorporateCustomer.objects.get(id=customer_id)
    except CorporateCustomer.DoesNotExist:
        raise PricingError(f"Customer with ID '{customer_id}' not found.")

    if not customer.is_active:
        raise PricingError(f"Customer '{customer.display_name}' is inactive.")

    # 1. Resolve active contract
    contracts = CorporateContract.objects.filter(
        customer=customer,
        status="ACTIVE",
        effective_start__lte=pickup_date,
    ).filter(
        models.Q(effective_end__isnull=True) | models.Q(effective_end__gte=pickup_date)
    )

    if not contracts.exists():
        raise PricingError(f"No active corporate contract found for {customer.display_name} on {pickup_date}.")

    if contracts.count() > 1:
        raise PricingError(f"Ambiguous multiple active contracts found for {customer.display_name} on {pickup_date}.")

    contract = contracts.first()

    norm_city = pickup_city.strip().lower() if pickup_city else ""
    norm_category = vehicle_category.strip().lower() if vehicle_category else ""

    # 2. Resolve contract rate
    rates = ContractRate.objects.filter(
        contract=contract,
        city__iexact=norm_city,
        vehicle_category__iexact=norm_category,
        duty_type=duty_type,
    )

    if not rates.exists():
        # fallback to city='*'
        rates = ContractRate.objects.filter(
            contract=contract,
            city="*",
            vehicle_category__iexact=norm_category,
            duty_type=duty_type,
        )

    if not rates.exists():
        raise PricingError(
            f"No matching contract rate found for city='{pickup_city}', category='{vehicle_category}', duty_type='{duty_type}' under contract '{contract.title}'."
        )

    rate = rates.first()

    # 3. Calculations using Decimal
    planned_hours_dec = Decimal(str(planned_hours or 0))
    planned_km_dec = Decimal(str(planned_km or 0))

    base_charge = quantize_decimal(rate.base_rate)
    included_hours_dec = Decimal(str(rate.included_hours))
    included_km_dec = Decimal(str(rate.included_km))

    # Outstation daily minimum
    effective_km = planned_km_dec
    if duty_type == DutyType.OUTSTATION and rate.outstation_daily_min_km:
        min_km = Decimal(str(rate.outstation_daily_min_km)) * Decimal(str(outstation_days))
        if effective_km < min_km:
            effective_km = min_km

    # Excess hours & km
    excess_hours = max(Decimal("0.00"), planned_hours_dec - included_hours_dec)
    excess_km = max(Decimal("0.00"), effective_km - included_km_dec)

    excess_hour_charge = quantize_decimal(excess_hours * rate.extra_hour_rate)
    excess_km_charge = quantize_decimal(excess_km * rate.extra_km_rate)

    # Allowances
    allowance_items = []
    allowance_total = Decimal("0.00")
    if requested_allowances:
        for item in requested_allowances:
            allow_type = item.get("allowance_type") if isinstance(item, dict) else item
            qty = Decimal(str(item.get("quantity", 1))) if isinstance(item, dict) else Decimal("1")
            
            allow_obj = contract.allowances.filter(allowance_type=allow_type).first()
            if allow_obj:
                charge = quantize_decimal(allow_obj.amount * qty)
                allowance_total += charge
                allowance_items.append({
                    "allowance_type": allow_obj.allowance_type,
                    "description": allow_obj.description or allow_obj.get_allowance_type_display(),
                    "unit_amount": str(quantize_decimal(allow_obj.amount)),
                    "quantity": str(qty),
                    "charge": str(charge),
                })

    subtotal = base_charge + excess_hour_charge + excess_km_charge + allowance_total

    cgst_rate = quantize_decimal(contract.cgst_rate)
    sgst_rate = quantize_decimal(contract.sgst_rate)

    cgst_amount = quantize_decimal(subtotal * (cgst_rate / Decimal("100.00")))
    sgst_amount = quantize_decimal(subtotal * (sgst_rate / Decimal("100.00")))

    tax_amount = cgst_amount + sgst_amount
    total_amount = subtotal + tax_amount

    explanation = (
        f"Base fare ₹{base_charge} for {rate.included_hours}h/{rate.included_km}km. "
        f"Excess hours: {excess_hours}h @ ₹{rate.extra_hour_rate}/h (₹{excess_hour_charge}). "
        f"Excess km: {excess_km}km @ ₹{rate.extra_km_rate}/km (₹{excess_km_charge}). "
        f"Allowances: ₹{allowance_total}. Taxes: CGST {cgst_rate}% (₹{cgst_amount}) + SGST {sgst_rate}% (₹{sgst_amount})."
    )

    return {
        "calculation_version": CALCULATION_VERSION,
        "customer": {
            "id": customer.id,
            "code": customer.code,
            "display_name": customer.display_name,
        },
        "contract": {
            "id": contract.id,
            "title": contract.title,
            "version_name": contract.version_name,
            "metering_policy": contract.metering_policy,
        },
        "rate": {
            "id": rate.id,
            "city": rate.city,
            "vehicle_category": rate.vehicle_category,
            "duty_type": rate.duty_type,
        },
        "inputs": {
            "pickup_datetime": pickup_datetime.isoformat(),
            "pickup_city": pickup_city,
            "vehicle_category": vehicle_category,
            "duty_type": duty_type,
            "planned_hours": float(planned_hours_dec),
            "planned_km": float(planned_km_dec),
            "effective_km": float(effective_km),
            "outstation_days": outstation_days,
        },
        "itemized_charges": {
            "base_charge": str(base_charge),
            "included_hours": rate.included_hours,
            "included_km": rate.included_km,
            "excess_hours": str(excess_hours),
            "extra_hour_rate": str(rate.extra_hour_rate),
            "excess_hour_charge": str(excess_hour_charge),
            "excess_km": str(excess_km),
            "extra_km_rate": str(rate.extra_km_rate),
            "excess_km_charge": str(excess_km_charge),
            "allowances": allowance_items,
            "allowances_total": str(allowance_total),
            "subtotal": str(subtotal),
            "cgst_rate": str(cgst_rate),
            "cgst_amount": str(cgst_amount),
            "sgst_rate": str(sgst_rate),
            "sgst_amount": str(sgst_amount),
            "total_amount": str(total_amount),
        },
        "taxable_amount": str(subtotal),
        "tax_amount": str(tax_amount),
        "gross_amount": str(total_amount),
        "total_amount": str(total_amount),
        "explanation": explanation,
    }
