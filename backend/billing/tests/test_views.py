import datetime
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from billing.models import CloseoutStatus, LegalEntity, FinancialYear, FiscalPeriod, Invoice, InvoiceStatus, TripCloseout
from fleet.models import BookingType, CorporateCustomer, Driver, PricingAmountStatus, Trip, Vehicle
from accounts.models import User


class BillingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="billing_admin",
            email="billing@indexfleet.com",
            password="password123",
            role="accountant",
        )
        self.client.force_authenticate(user=self.user)
        self.reviewer = User.objects.create_user(
            username="billing_reviewer",
            email="billing-reviewer@indexfleet.com",
            password="password123",
            role="accountant",
        )

        self.entity = LegalEntity.objects.create(
            legal_name="Awkward Fleet Operations Pvt Ltd",
            gstin="27AAACA9876A1Z4",
            state_code="27",
        )
        self.fy = FinancialYear.objects.create(
            name="FY 2025-26",
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        self.customer = CorporateCustomer.objects.create(
            code="ACME_API_TEST",
            legal_name="ACME Logistics Pvt Ltd",
            display_name="ACME Corp",
            gstin="27AAACA1234A1Z5",
            payment_terms_days=30,
        )
        self.vehicle = Vehicle.objects.create(
            registration_number="MH01XY1111",
            make="Toyota",
            model="Camry",
            category="sedan",
            current_city="Mumbai",
            permit_expires_on=datetime.date(2027, 1, 1),
            insurance_expires_on=datetime.date(2027, 1, 1),
            pollution_expires_on=datetime.date(2027, 1, 1),
            fitness_expires_on=datetime.date(2027, 1, 1),
        )
        self.driver = Driver.objects.create(name="Deepak", phone="+919000011122", license_number="DL11223344")

        self.trip = Trip.objects.create(
            customer=self.customer,
            booking_type=BookingType.CORPORATE,
            pickup_city="Mumbai",
            drop_city="Mumbai",
            pickup_at=datetime.datetime(2026, 7, 23, 10, 0, tzinfo=datetime.timezone.utc),
            estimated_drop_at=datetime.datetime(2026, 7, 23, 18, 0, tzinfo=datetime.timezone.utc),
            status="completed",
            vehicle=self.vehicle,
            driver=self.driver,
            fare_amount=Decimal("2400.00"),
            pricing_amount_status=PricingAmountStatus.QUOTED,
            quoted_taxable_amount=Decimal("2400.00"),
            quoted_tax_amount=Decimal("120.00"),
            quoted_total_amount=Decimal("2520.00"),
            pricing_snapshot={
                "calculation_version": "contract-quote-v1",
                "itemized_charges": {
                    "cgst_rate": "2.50",
                    "sgst_rate": "2.50",
                },
            },
        )
        self.closeout = TripCloseout.objects.create(
            trip=self.trip,
            start_odometer_km=100,
            end_odometer_km=180,
            status=CloseoutStatus.BILLING_READY,
        )

    def test_generate_invoice_draft_api(self):
        res = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {
                "legal_entity_id": self.entity.id,
                "trip_ids": [self.trip.id],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "DRAFT")
        self.assertEqual(res.data["subtotal"], "2400.00")

    def test_issue_invoice_api(self):
        draft_res = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {
                "legal_entity_id": self.entity.id,
                "trip_ids": [self.trip.id],
            },
            format="json",
        )
        inv_id = draft_res.data["id"]
        self.client.post(f"/api/billing/invoices/{inv_id}/submit_review/")
        self.client.force_authenticate(user=self.reviewer)
        self.client.post(f"/api/billing/invoices/{inv_id}/approve/")
        issue_res = self.client.post(f"/api/billing/invoices/{inv_id}/issue/")
        self.assertEqual(issue_res.status_code, status.HTTP_200_OK)
        self.assertEqual(issue_res.data["status"], "ISSUED")
        self.assertTrue(issue_res.data["invoice_number"].startswith("INV/"))

    def test_authenticated_browser_billing_flow_uses_canonical_routes(self):
        entities_res = self.client.get("/api/billing/entities/")
        self.assertEqual(entities_res.status_code, status.HTTP_200_OK)
        self.assertEqual(entities_res.data[0]["id"], self.entity.id)

        draft_res = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {
                "legal_entity_id": self.entity.id,
                "trip_ids": [self.trip.id],
            },
            format="json",
        )
        self.assertEqual(draft_res.status_code, status.HTTP_201_CREATED)
        invoice_id = draft_res.data["id"]
        self.assertGreater(len(draft_res.data["lines"]), 0)

        draft_preview = self.client.get(
            f"/api/billing/invoices/{invoice_id}/html_preview/"
        )
        self.assertEqual(draft_preview.status_code, status.HTTP_200_OK)
        self.assertContains(draft_preview, "DRAFT")

        self.client.post(
            f"/api/billing/invoices/{invoice_id}/submit_review/"
        )
        self.client.force_authenticate(user=self.reviewer)
        self.client.post(f"/api/billing/invoices/{invoice_id}/approve/")
        issue_res = self.client.post(
            f"/api/billing/invoices/{invoice_id}/issue/"
        )
        self.assertEqual(issue_res.status_code, status.HTTP_200_OK)
        self.assertEqual(issue_res.data["status"], InvoiceStatus.ISSUED)

        issued_preview = self.client.get(
            f"/api/billing/invoices/{invoice_id}/html_preview/"
        )
        self.assertContains(issued_preview, issue_res.data["invoice_number"])

        export_res = self.client.get(
            f"/api/billing/invoices/{invoice_id}/tally_xml/"
        )
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)
        self.assertEqual(export_res["Content-Type"], "application/xml")
        self.assertContains(export_res, issue_res.data["invoice_number"])

        self.assertEqual(
            self.client.post(
                "/api/billing/invoices/generate_from_trips/",
                {"legal_entity_id": self.entity.id, "trip_ids": [self.trip.id]},
                format="json",
            ).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_billing_routes_require_authentication(self):
        self.client.force_authenticate(user=None)

        for path in (
            "/api/billing/entities/",
            "/api/billing/invoices/",
            "/api/billing/closeouts/",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_eligible_trip_and_grouping_preview_are_server_calculated(self):
        eligible_res = self.client.get(
            "/api/billing/invoices/eligible_trips/?booking_type=CORPORATE"
        )
        self.assertEqual(eligible_res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in eligible_res.data["results"]],
            [self.trip.id],
        )
        queued = eligible_res.data["results"][0]
        self.assertTrue(queued["billing_eligibility"]["eligible"])
        self.assertEqual(
            queued["grouping_key"]["bill_to_key"],
            f"CORPORATE:{self.customer.id}",
        )
        self.assertEqual(queued["amount_summary"]["total_amount"], "2520.00")
        self.assertEqual(queued["closeout_summary"]["id"], self.closeout.id)
        self.assertEqual(eligible_res.data["summary"]["estimated_total_amount"], "2520.00")

        preview_res = self.client.post(
            "/api/billing/invoices/grouping_preview/",
            {
                "trip_ids": [self.trip.id],
                "estimated_taxable_amount": "0.01",
            },
            format="json",
        )
        self.assertEqual(preview_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(preview_res.data["groups"]), 1)
        self.assertEqual(
            preview_res.data["groups"][0]["estimated_taxable_amount"],
            "2400.00",
        )
        self.assertEqual(
            preview_res.data["groups"][0]["bill_to_key"],
            f"CORPORATE:{self.customer.id}",
        )

    def test_blocker_filter_explains_uncompleted_trip(self):
        self.trip.status = "assigned"
        self.trip.save(update_fields=["status"])

        default_res = self.client.get("/api/billing/invoices/eligible_trips/")
        self.assertNotIn(
            self.trip.id,
            [item["id"] for item in default_res.data["results"]],
        )

        blocked_res = self.client.get(
            "/api/billing/invoices/eligible_trips/?blocker=STATUS_NOT_COMPLETED"
        )
        self.assertEqual(
            [item["id"] for item in blocked_res.data["results"]],
            [self.trip.id],
        )
        blocker_codes = {
            item["code"]
            for item in blocked_res.data["results"][0]["billing_eligibility"]["blockers"]
        }
        self.assertIn("STATUS_NOT_COMPLETED", blocker_codes)

    def test_invoice_review_requires_independent_approval_and_audits_issue(self):
        draft = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {"legal_entity_id": self.entity.id, "trip_ids": [self.trip.id]},
            format="json",
        )
        invoice_id = draft.data["id"]
        submitted = self.client.post(
            f"/api/billing/invoices/{invoice_id}/submit_review/"
        )
        self.assertEqual(submitted.data["status"], InvoiceStatus.REVIEW)
        self.assertEqual(
            self.client.post(
                f"/api/billing/invoices/{invoice_id}/approve/"
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=self.reviewer)
        approved = self.client.post(
            f"/api/billing/invoices/{invoice_id}/approve/"
        )
        self.assertEqual(approved.data["status"], InvoiceStatus.APPROVED)
        issued = self.client.post(f"/api/billing/invoices/{invoice_id}/issue/")
        self.assertEqual(issued.data["status"], InvoiceStatus.ISSUED)
        self.assertEqual(
            [event["action"] for event in issued.data["audit_events"]],
            ["SUBMIT_REVIEW", "APPROVE", "ISSUE"],
        )
        self.assertEqual(issued.data["source_trips"][0]["trip_id"], self.trip.id)
        self.assertEqual(
            issued.data["journal_summary"]["debit_total"],
            issued.data["journal_summary"]["credit_total"],
        )
        trip_trace = self.client.get(f"/api/trips/{self.trip.id}/").data[
            "financial_trace"
        ]
        self.assertEqual(trip_trace["invoice"]["id"], invoice_id)
        self.assertIsNotNone(trip_trace["journal"])
        first_document = self.client.get(
            f"/api/billing/invoices/{invoice_id}/document/"
        )
        second_document = self.client.get(
            f"/api/billing/invoices/{invoice_id}/document/"
        )
        self.assertEqual(first_document.status_code, status.HTTP_200_OK)
        self.assertEqual(first_document["Content-Type"], "application/pdf")
        self.assertEqual(first_document["ETag"], second_document["ETag"])
        self.assertTrue(b"".join(first_document.streaming_content).startswith(b"%PDF-1.4"))

        delivery = self.client.post(
            f"/api/billing/invoices/{invoice_id}/record_delivery/",
            {"recipients": ["finance@acme.example"], "status": "SENT"},
            format="json",
        )
        self.assertEqual(delivery.data["status"], InvoiceStatus.SENT)
        self.assertEqual(
            delivery.data["documents"][0]["delivery_attempts"][0]["recipients"],
            ["finance@acme.example"],
        )

    def test_void_requires_reason_and_paid_invoice_routes_to_credit(self):
        draft = self.client.post(
            "/api/billing/invoices/generate_draft/",
            {"legal_entity_id": self.entity.id, "trip_ids": [self.trip.id]},
            format="json",
        )
        invoice_id = draft.data["id"]
        self.assertEqual(
            self.client.post(f"/api/billing/invoices/{invoice_id}/void/").status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        voided = self.client.post(
            f"/api/billing/invoices/{invoice_id}/void/",
            {"reason": "Wrong purchase order"},
            format="json",
        )
        self.assertEqual(voided.data["status"], InvoiceStatus.VOID)

    def test_eligible_queue_supports_server_search_and_pagination(self):
        response = self.client.get(
            "/api/billing/invoices/eligible_trips/",
            {"search": "ACME", "page": 1, "page_size": 1},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["page_size"], 1)
        self.assertIsNone(response.data["next_page"])
        self.assertEqual(response.data["results"][0]["id"], self.trip.id)
