import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import TaxRegime


MONEY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def rate(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def state_code_from_gstin(gstin: str) -> str:
    value = (gstin or "").strip().upper()
    if not value:
        return ""
    if not re.fullmatch(r"\d{2}[A-Z0-9]{13}", value):
        raise ValidationError({"gstin": "GSTIN must be 15 characters and start with a two-digit state code."})
    return value[:2]


def state_code_from_place_of_supply(place_of_supply: str) -> str:
    value = (place_of_supply or "").strip()
    match = re.search(r"\((\d{2})\)\s*$", value) or re.match(r"^(\d{2})\b", value)
    return match.group(1) if match else ""


@dataclass(frozen=True)
class TaxContext:
    supplier_state_code: str
    customer_state_code: str
    regime: str


@dataclass(frozen=True)
class LineTax:
    taxable_value: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    line_total: Decimal
    regime: str


class TaxService:
    @staticmethod
    def determine_context(*, legal_entity, customer_gstin="", place_of_supply="") -> TaxContext:
        supplier_state = (legal_entity.state_code or "").strip()
        if not re.fullmatch(r"\d{2}", supplier_state):
            supplier_state = state_code_from_gstin(legal_entity.gstin)
        if not supplier_state:
            raise ValidationError(
                {"legal_entity": "A valid two-digit supplier state code or GSTIN is required for tax determination."}
            )

        customer_state = state_code_from_gstin(customer_gstin)
        if not customer_state:
            customer_state = state_code_from_place_of_supply(place_of_supply)
        if not customer_state:
            raise ValidationError(
                {"place_of_supply": "A customer GSTIN or place of supply containing a state code is required."}
            )

        regime = (
            TaxRegime.INTRA_STATE
            if supplier_state == customer_state
            else TaxRegime.INTER_STATE
        )
        return TaxContext(
            supplier_state_code=supplier_state,
            customer_state_code=customer_state,
            regime=regime,
        )

    @staticmethod
    def calculate_line(
        taxable_value,
        *,
        context: TaxContext,
        cgst_rate=Decimal("2.50"),
        sgst_rate=Decimal("2.50"),
        zero_rated=False,
    ) -> LineTax:
        taxable = money(taxable_value)
        if taxable < Decimal("0.00"):
            raise ValidationError({"taxable_value": "Taxable value cannot be negative."})

        cgst_pct = rate(cgst_rate)
        sgst_pct = rate(sgst_rate)
        if any(value < Decimal("0.00") or value > Decimal("100.00") for value in (cgst_pct, sgst_pct)):
            raise ValidationError({"tax_rate": "Tax rates must be between 0 and 100."})

        if zero_rated:
            regime = TaxRegime.ZERO_RATED
            cgst_pct = sgst_pct = igst_pct = Decimal("0.00")
            cgst = sgst = igst = Decimal("0.00")
        elif context.regime == TaxRegime.INTRA_STATE:
            regime = context.regime
            igst_pct = Decimal("0.00")
            cgst = money(taxable * cgst_pct / Decimal("100.00"))
            sgst = money(taxable * sgst_pct / Decimal("100.00"))
            igst = Decimal("0.00")
        else:
            regime = context.regime
            igst_pct = rate(cgst_pct + sgst_pct)
            cgst_pct = sgst_pct = Decimal("0.00")
            cgst = sgst = Decimal("0.00")
            igst = money(taxable * igst_pct / Decimal("100.00"))

        return LineTax(
            taxable_value=taxable,
            cgst_rate=cgst_pct,
            cgst_amount=cgst,
            sgst_rate=sgst_pct,
            sgst_amount=sgst,
            igst_rate=igst_pct,
            igst_amount=igst,
            line_total=money(taxable + cgst + sgst + igst),
            regime=regime,
        )
