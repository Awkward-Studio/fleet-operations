from decimal import Decimal
import datetime
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from fleet.models import Vehicle, Driver, FuelTransaction, FuelTransactionStatus, FuelType, FuelUnit
from media_store.models import UploadedAsset
from billing.models import TripExpense, LedgerAccount, JournalEntry

User = get_user_model()


class FuelAndMileageTests(APITestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username="commercial_admin",
            email="admin@fleet.com",
            password="adminpassword",
            role="admin",  # maps to is_commercial_admin
        )
        self.client.force_authenticate(user=self.user)

        # Create driver
        self.driver = Driver.objects.create(
            name="Ramesh Kumar",
            phone="9876543210",
            license_number="DL-123456789",
            home_base="Mumbai",
        )

        # Create vehicle
        self.vehicle = Vehicle.objects.create(
            registration_number="MH-01-AB-1234",
            make="Maruti",
            model="Ertiga",
            category="Sedan",
            current_city="Mumbai",
            permit_expires_on=datetime.date(2027, 1, 1),
            insurance_expires_on=datetime.date(2027, 1, 1),
            pollution_expires_on=datetime.date(2027, 1, 1),
            fitness_expires_on=datetime.date(2027, 1, 1),
            odometer_km=10000,
            fuel_type=FuelType.PETROL,
            fuel_unit=FuelUnit.LITRES,
            tank_capacity=Decimal("45.00"),
            expected_mileage_min=Decimal("10.00"),
            expected_mileage_max=Decimal("18.00"),
            baseline_mileage=Decimal("14.00"),
        )

        # Create uploaded assets
        self.receipt = UploadedAsset.objects.create(
            kind=UploadedAsset.KIND_INVOICE,
            file_url="https://imagekit.io/receipt.jpg",
            original_name="receipt.jpg",
        )
        self.odo_photo = UploadedAsset.objects.create(
            kind=UploadedAsset.KIND_IMAGE,
            file_url="https://imagekit.io/odo.jpg",
            original_name="odo.jpg",
        )

    def test_fuel_transaction_reconciliation_validation(self):
        # Test valid math: quantity * unit_price + tax == total
        tx = FuelTransaction(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="Shell Petrol Pump",
            invoice_number="INV-9999",
            transaction_datetime=timezone.now(),
            odometer_km=10100,
            quantity=Decimal("10.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("50.00"),
            total_amount=Decimal("1050.00"), # 10 * 100 + 50 = 1050
        )
        # Should not raise exception
        tx.full_clean()

        # Test invalid math
        tx.total_amount = Decimal("1200.00")
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            tx.full_clean()

    def test_anomaly_detection_tank_overfill(self):
        # Quantity exceeds capacity * 1.10 (45 * 1.10 = 49.50)
        tx = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="Shell",
            invoice_number="INV-001",
            transaction_datetime=timezone.now(),
            odometer_km=10100,
            quantity=Decimal("50.00"), # Overfill!
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("5000.00"),
        )
        # Verify anomaly is flagged
        from fleet.fuel_service import detect_anomalies
        has_anom, flags = detect_anomalies(tx)
        self.assertTrue(has_anom)
        self.assertIn("tank_overfill", flags)

    def test_anomaly_detection_odometer_backwards(self):
        # Current odo less than vehicle odo (10000)
        tx = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="Shell",
            invoice_number="INV-002",
            transaction_datetime=timezone.now(),
            odometer_km=9900, # Backwards odo!
            quantity=Decimal("20.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("2000.00"),
        )
        from fleet.fuel_service import detect_anomalies
        has_anom, flags = detect_anomalies(tx)
        self.assertTrue(has_anom)
        self.assertIn("odometer_backwards", flags)

    def test_mileage_calculation_full_to_full(self):
        now = timezone.now()
        # 1st full fill (baseline)
        tx1 = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="Pump 1",
            invoice_number="I-1",
            transaction_datetime=now - datetime.timedelta(days=2),
            odometer_km=10000,
            quantity=Decimal("30.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("3000.00"),
            is_full_fill=True,
            status=FuelTransactionStatus.APPROVED,
        )

        # 2nd full fill (after 400km, consumed 25 litres)
        tx2 = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="Pump 1",
            invoice_number="I-2",
            transaction_datetime=now,
            odometer_km=10400,
            quantity=Decimal("25.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("2500.00"),
            is_full_fill=True,
            status=FuelTransactionStatus.APPROVED,
        )

        from fleet.fuel_service import calculate_vehicle_mileage
        metrics = calculate_vehicle_mileage(self.vehicle)

        # tx1 is first full fill
        self.assertFalse(metrics[tx1.id]["is_authoritative"])
        
        # tx2 mileage should be 400 km / 25 litres = 16.00 km/l
        self.assertTrue(metrics[tx2.id]["is_authoritative"])
        self.assertEqual(metrics[tx2.id]["mileage"], Decimal("16.00"))

    def test_fuel_transaction_approval_and_accounting_posting(self):
        tx = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="HP Fuel",
            invoice_number="HP-777",
            transaction_datetime=timezone.now(),
            odometer_km=10200,
            quantity=Decimal("15.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("15.00"),
            total_amount=Decimal("1515.00"),
            receipt_asset=self.receipt,
        )

        # Approve via API ViewSet
        url = f"/api/fuel-transactions/{tx.id}/approve/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify status is APPROVED
        tx.refresh_from_db()
        self.assertEqual(tx.status, FuelTransactionStatus.APPROVED)

        # Verify TripExpense was created in billing
        self.assertIsNotNone(tx.expense_posted)
        expense = tx.expense_posted
        self.assertEqual(expense.amount, Decimal("1515.00"))
        self.assertEqual(expense.tax_amount, Decimal("15.00"))

        # Verify JournalEntry was created in billing
        journal = JournalEntry.objects.filter(source_type="FUEL", source_id=str(tx.id)).first()
        self.assertIsNotNone(journal)
        
        # Verify balanced journal lines
        lines = list(journal.lines.all())
        self.assertEqual(len(lines), 3) # Expense, Tax asset, Liability payable
        debits = sum(line.debit_amount for line in lines)
        credits = sum(line.credit_amount for line in lines)
        self.assertEqual(debits, Decimal("1515.00"))
        self.assertEqual(credits, Decimal("1515.00"))

    def test_fuel_transaction_reversal(self):
        # Create and approve transaction
        tx = FuelTransaction.objects.create(
            vehicle=self.vehicle,
            driver=self.driver,
            vendor="HP Fuel",
            invoice_number="HP-888",
            transaction_datetime=timezone.now(),
            odometer_km=10300,
            quantity=Decimal("10.00"),
            unit_price=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
        )
        self.client.post(f"/api/fuel-transactions/{tx.id}/approve/")
        tx.refresh_from_db()

        # Reverse transaction
        response = self.client.post(f"/api/fuel-transactions/{tx.id}/reverse/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        tx.refresh_from_db()
        self.assertEqual(tx.status, FuelTransactionStatus.REVERSED)

        # Verify reversing Journal Entry exists
        rev_journal = JournalEntry.objects.filter(source_type="FUEL_REVERSAL", source_id=str(tx.id)).first()
        self.assertIsNotNone(rev_journal)
        
        # Check balanced reversal journal lines
        lines = list(rev_journal.lines.all())
        debits = sum(line.debit_amount for line in lines)
        credits = sum(line.credit_amount for line in lines)
        self.assertEqual(debits, Decimal("1000.00"))
        self.assertEqual(credits, Decimal("1000.00"))
