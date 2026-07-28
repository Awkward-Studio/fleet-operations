from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from billing.models import LegalEntity, TaxRegime
from billing.tax_service import TaxService


class TaxServiceTests(SimpleTestCase):
    def setUp(self):
        self.entity = LegalEntity(
            legal_name="Index Fleet",
            gstin="27AAACA9876A1Z4",
            state_code="27",
        )

    def test_intra_state_uses_cgst_and_sgst(self):
        context = TaxService.determine_context(
            legal_entity=self.entity,
            customer_gstin="27AAACA1234A1Z5",
            place_of_supply="Maharashtra (27)",
        )
        result = TaxService.calculate_line(Decimal("2500.00"), context=context)

        self.assertEqual(context.regime, TaxRegime.INTRA_STATE)
        self.assertEqual(result.cgst_amount, Decimal("62.50"))
        self.assertEqual(result.sgst_amount, Decimal("62.50"))
        self.assertEqual(result.igst_amount, Decimal("0.00"))
        self.assertEqual(result.line_total, Decimal("2625.00"))

    def test_inter_state_combines_rate_into_igst(self):
        context = TaxService.determine_context(
            legal_entity=self.entity,
            customer_gstin="29AAACA1234A1Z5",
            place_of_supply="Karnataka (29)",
        )
        result = TaxService.calculate_line(Decimal("2500.00"), context=context)

        self.assertEqual(context.regime, TaxRegime.INTER_STATE)
        self.assertEqual(result.cgst_amount, Decimal("0.00"))
        self.assertEqual(result.sgst_amount, Decimal("0.00"))
        self.assertEqual(result.igst_rate, Decimal("5.00"))
        self.assertEqual(result.igst_amount, Decimal("125.00"))

    def test_unregistered_customer_uses_place_of_supply_state(self):
        context = TaxService.determine_context(
            legal_entity=self.entity,
            place_of_supply="Delhi (07)",
        )

        self.assertEqual(context.customer_state_code, "07")
        self.assertEqual(context.regime, TaxRegime.INTER_STATE)

    def test_invalid_gstin_is_rejected(self):
        with self.assertRaises(ValidationError):
            TaxService.determine_context(
                legal_entity=self.entity,
                customer_gstin="INVALID",
                place_of_supply="Maharashtra (27)",
            )

    def test_missing_supplier_registration_is_rejected(self):
        with self.assertRaises(ValidationError):
            TaxService.determine_context(
                legal_entity=LegalEntity(legal_name="Unconfigured"),
                place_of_supply="Maharashtra (27)",
            )

    def test_rounding_is_half_up(self):
        context = TaxService.determine_context(
            legal_entity=self.entity,
            place_of_supply="Maharashtra (27)",
        )
        result = TaxService.calculate_line(Decimal("100.20"), context=context)

        self.assertEqual(result.cgst_amount, Decimal("2.51"))
        self.assertEqual(result.sgst_amount, Decimal("2.51"))
