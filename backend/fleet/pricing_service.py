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


class PricingError(Exception):
    pass


def quantize_decimal(value):
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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

    total_amount = subtotal + cgst_amount + sgst_amount

    explanation = (
        f"Base fare ₹{base_charge} for {rate.included_hours}h/{rate.included_km}km. "
        f"Excess hours: {excess_hours}h @ ₹{rate.extra_hour_rate}/h (₹{excess_hour_charge}). "
        f"Excess km: {excess_km}km @ ₹{rate.extra_km_rate}/km (₹{excess_km_charge}). "
        f"Allowances: ₹{allowance_total}. Taxes: CGST {cgst_rate}% (₹{cgst_amount}) + SGST {sgst_rate}% (₹{sgst_amount})."
    )

    return {
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
        "total_amount": str(total_amount),
        "explanation": explanation,
    }
