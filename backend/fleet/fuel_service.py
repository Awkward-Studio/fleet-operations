from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from .models import FuelTransaction, FuelTransactionStatus, Vehicle


def calculate_vehicle_mileage(vehicle):
    """
    Calculates mileage statistics for all active transactions of a vehicle.
    Returns a list of dictionaries with computed metrics per transaction.
    """
    transactions = list(
        FuelTransaction.objects.filter(
            vehicle=vehicle,
            status__in=[FuelTransactionStatus.SUBMITTED, FuelTransactionStatus.APPROVED],
        )
        .exclude(corrected_by_transaction__isnull=False)
        .order_by("transaction_datetime")
    )

    results = {}
    prev_full_tx = None

    for i, tx in enumerate(transactions):
        prev_tx = transactions[i - 1] if i > 0 else None
        delta_distance = None
        if prev_tx:
            delta_distance = tx.odometer_km - prev_tx.odometer_km

        mileage = None
        consumption_rate = None
        cost_per_km = None
        tax_per_km = None
        is_authoritative = False
        notes = ""

        if tx.is_full_fill:
            if prev_full_tx:
                # Find index of prev_full_tx
                idx_prev = transactions.index(prev_full_tx)
                sub_list = transactions[idx_prev + 1 : i + 1]
                total_qty = sum(item.quantity for item in sub_list)
                total_distance = tx.odometer_km - prev_full_tx.odometer_km

                if total_distance > 0 and total_qty > 0:
                    mileage = Decimal(total_distance) / total_qty
                    consumption_rate = (total_qty / Decimal(total_distance)) * Decimal("100")
                    cost_per_km = sum(item.total_amount for item in sub_list) / Decimal(total_distance)
                    tax_per_km = sum(item.tax_amount for item in sub_list) / Decimal(total_distance)
                    is_authoritative = True
                else:
                    notes = "Odometer reading or quantity mismatch."
            else:
                notes = "First full fill; establishes baseline."
            prev_full_tx = tx
        else:
            # Partial fill: estimate based on immediate previous odo
            if prev_tx and delta_distance and delta_distance > 0 and tx.quantity > 0:
                mileage = Decimal(delta_distance) / tx.quantity
                consumption_rate = (tx.quantity / Decimal(delta_distance)) * Decimal("100")
                cost_per_km = tx.total_amount / Decimal(delta_distance)
                tax_per_km = tx.tax_amount / Decimal(delta_distance)
                notes = "Estimate based on partial fill."
            else:
                notes = "Unable to estimate mileage without valid odometer delta."

        results[tx.id] = {
            "delta_distance": delta_distance,
            "mileage": mileage.quantize(Decimal("0.01")) if mileage is not None else None,
            "consumption_rate": consumption_rate.quantize(Decimal("0.01")) if consumption_rate is not None else None,
            "cost_per_km": cost_per_km.quantize(Decimal("0.01")) if cost_per_km is not None else None,
            "tax_per_km": tax_per_km.quantize(Decimal("0.01")) if tax_per_km is not None else None,
            "is_authoritative": is_authoritative,
            "calculation_notes": notes,
        }

    return results


def detect_anomalies(tx: FuelTransaction) -> tuple[bool, list[str]]:
    """
    Analyzes a transaction for anomalies and returns (has_anomaly, anomaly_flags).
    """
    flags = []
    vehicle = tx.vehicle

    # 1. Duplicate Invoice Number for same Vendor
    if tx.invoice_number and tx.vendor:
        dup_qs = FuelTransaction.objects.filter(
            invoice_number__iexact=tx.invoice_number.strip(),
            vendor__iexact=tx.vendor.strip(),
        ).exclude(status__in=[FuelTransactionStatus.REJECTED, FuelTransactionStatus.REVERSED])
        if tx.pk:
            dup_qs = dup_qs.exclude(pk=tx.pk)
        if dup_qs.exists():
            flags.append("duplicate_invoice")

    # 2. Tank Overfill
    if vehicle.tank_capacity and tx.quantity:
        if tx.quantity > vehicle.tank_capacity * Decimal("1.10"):
            flags.append("tank_overfill")

    # Fetch previous active transaction
    prev_tx = (
        FuelTransaction.objects.filter(
            vehicle=vehicle,
            transaction_datetime__lt=tx.transaction_datetime,
        )
        .exclude(status__in=[FuelTransactionStatus.REJECTED, FuelTransactionStatus.REVERSED])
        .order_by("-transaction_datetime")
        .first()
    )

    # 3. Odometer Checks
    if prev_tx:
        delta = tx.odometer_km - prev_tx.odometer_km
        if delta < 0:
            flags.append("odometer_backwards")
        elif delta > 2000:
            flags.append("odometer_jump")
    else:
        # Check against current vehicle odometer if no prev transaction
        if tx.odometer_km < vehicle.odometer_km:
            flags.append("odometer_backwards")

    # 4. Price Variance (e.g. outside 50 - 150 INR per unit)
    if tx.unit_price:
        if tx.unit_price < Decimal("50.00") or tx.unit_price > Decimal("150.00"):
            flags.append("price_variance")

    # 5. Rapid repeated fill (same vehicle filled within 30 minutes)
    time_min = tx.transaction_datetime - timedelta(minutes=30)
    time_max = tx.transaction_datetime + timedelta(minutes=30)
    rapid_qs = FuelTransaction.objects.filter(
        vehicle=vehicle,
        transaction_datetime__range=(time_min, time_max),
    ).exclude(status__in=[FuelTransactionStatus.REJECTED, FuelTransactionStatus.REVERSED])
    if tx.pk:
        rapid_qs = rapid_qs.exclude(pk=tx.pk)
    if rapid_qs.exists():
        flags.append("rapid_fill")

    # 6. Mileage anomaly (calculated mileage is outside expected bands)
    # We temporarily compute mileage to see if it violates bands
    if tx.is_full_fill and prev_tx:
        # Find previous full fill
        prev_full = (
            FuelTransaction.objects.filter(
                vehicle=vehicle,
                is_full_fill=True,
                transaction_datetime__lt=tx.transaction_datetime,
            )
            .exclude(status__in=[FuelTransactionStatus.REJECTED, FuelTransactionStatus.REVERSED])
            .exclude(corrected_by_transaction__isnull=False)
            .order_by("-transaction_datetime")
            .first()
        )
        if prev_full:
            # sum quantities
            sub_txs = FuelTransaction.objects.filter(
                vehicle=vehicle,
                transaction_datetime__gt=prev_full.transaction_datetime,
                transaction_datetime__lte=tx.transaction_datetime,
            ).exclude(status__in=[FuelTransactionStatus.REJECTED, FuelTransactionStatus.REVERSED])
            total_qty = sum(item.quantity for item in sub_txs)
            total_distance = tx.odometer_km - prev_full.odometer_km
            if total_distance > 0 and total_qty > 0:
                mileage = Decimal(total_distance) / total_qty
                if vehicle.expected_mileage_min and mileage < vehicle.expected_mileage_min:
                    flags.append("mileage_anomaly")
                elif vehicle.expected_mileage_max and mileage > vehicle.expected_mileage_max:
                    flags.append("mileage_anomaly")

    has_anomaly = len(flags) > 0
    return has_anomaly, flags
