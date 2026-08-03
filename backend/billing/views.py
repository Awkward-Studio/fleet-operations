import hashlib
import json
from functools import wraps
from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    CloseoutAuditEvent, InvoiceAuditEvent, InvoiceDeliveryAttempt, LegalEntity,
    TripCloseout, TripCharge, Invoice, InvoiceTrip, CloseoutStatus, InvoiceStatus,
    IdempotencyRegistry, FinancialAuditEvent, PaymentReceipt, PaymentAllocation, CreditNote,
    CreditNoteStatus, DebitNote, DebitNoteStatus, OTASettlementBatch
)
from .serializers import (
    BillableTripSerializer, LegalEntitySerializer, TripCloseoutSerializer, TripChargeSerializer, InvoiceSerializer,
    PaymentReceiptSerializer, PaymentAllocationSerializer, CreditNoteSerializer, DebitNoteSerializer,
    OTASettlementBatchSerializer, OTASettlementImportSerializer
)
from .services import BillabilityService, CloseoutService, InvoiceService, check_period_lock, PostingEngine, AuditService, OTASettlementImportService, OTAProfitabilityReportService, PaymentService, CreditNoteService, DebitNoteService
from .reports import CloseoutReconciliationReport, ARAgingReport, CustomerStatementReport
from fleet.models import PricingAmountStatus, Trip
from fleet.permissions import IsCommercialAdmin
from accounts.permissions import HasFinancialRolePermission, HasLegalEntityScope, HasCustomerScope
from accounts.models import UserRole


def idempotent_action():
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")
            
            try:
                body_bytes = json.dumps(request.data or {}, sort_keys=True).encode("utf-8")
            except Exception:
                body_bytes = str(request.data or {}).encode("utf-8")
            
            request_hash = hashlib.sha256(body_bytes).hexdigest()
            
            if not key:
                user_id = request.user.id if request.user and request.user.is_authenticated else "anonymous"
                key = f"auto-{user_id}-{request.path}-{request_hash}"
                
            entry = IdempotencyRegistry.objects.filter(key=key).first()
            if entry:
                if entry.request_hash != request_hash:
                    return Response(
                        {"detail": "Idempotency key conflict: key already used for a different request payload."},
                        status=status.HTTP_409_CONFLICT,
                    )
                try:
                    stored_body = json.loads(entry.response_body)
                except Exception:
                    stored_body = entry.response_body
                return Response(stored_body, status=entry.response_status_code)
                
            response = func(self, request, *args, **kwargs)
            
            if response.status_code < 500:
                try:
                    resp_body_str = json.dumps(response.data)
                except Exception:
                    resp_body_str = str(response.data)
                IdempotencyRegistry.objects.create(
                    key=key,
                    response_status_code=response.status_code,
                    response_body=resp_body_str,
                    request_hash=request_hash,
                )
                
            return response
        return wrapper
    return decorator


class LegalEntityViewSet(viewsets.ModelViewSet):
    queryset = LegalEntity.objects.filter(is_active=True)
    serializer_class = LegalEntitySerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasLegalEntityScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            assigned = self.request.user.assigned_legal_entities.all()
            if assigned.exists():
                queryset = queryset.filter(id__in=assigned.values_list("id", flat=True))
        return queryset


class OTASettlementBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OTASettlementBatch.objects.select_related("counterparty").prefetch_related("lines").all()
    serializer_class = OTASettlementBatchSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission]

    @action(detail=False, methods=["post"])
    @idempotent_action()
    def import_batch(self, request):
        serializer = OTASettlementImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = OTASettlementImportService.import_batch(
                counterparty_code=data["counterparty_code"],
                batch_reference=data["batch_reference"],
                lines=data.get("lines"),
                csv_content=data.get("csv_content", ""),
                currency=data.get("currency", "INR"),
                payout_date=data.get("payout_date"),
                source_system=data.get("source_system", "API"),
                actor=request.user,
                idempotency_key=request.headers.get("X-Idempotency-Key", ""),
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def profitability(self, request):
        return Response(
            OTAProfitabilityReportService.build(
                counterparty_code=request.query_params.get("counterparty", ""),
                status=request.query_params.get("status", ""),
            )
        )


class TripCloseoutViewSet(viewsets.ModelViewSet):
    queryset = TripCloseout.objects.select_related("trip").prefetch_related("extra_charges", "audit_events").all()
    serializer_class = TripCloseoutSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasCustomerScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Enforce Customer Scope
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            active_companies = self.request.user.active_memberships.values_list("company_id", flat=True)
            if active_companies.exists():
                queryset = queryset.filter(trip__customer_id__in=active_companies)
                
        closeout_status = self.request.query_params.get("status")
        trip_id = self.request.query_params.get("trip")
        if closeout_status:
            queryset = queryset.filter(status=closeout_status)
        if trip_id:
            queryset = queryset.filter(trip_id=trip_id)
        return queryset.order_by("-updated_at")

    def _commercial_or_403(self, request):
        permission = IsCommercialAdmin()
        if not permission.has_permission(request, self):
            self.permission_denied(request, message="Commercial or accounting permission is required.")

    def _reason(self, request):
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            raise ValidationError({"reason": "A reason is required."})
        return reason

    def _audit(self, closeout, action, actor, from_status, reason=""):
        CloseoutAuditEvent.objects.create(
            closeout=closeout,
            action=action,
            reason=reason,
            actor=actor,
            from_status=from_status,
            to_status=closeout.status,
            snapshot={
                "blockers": closeout.blockers,
                "final_total_amount": str(closeout.final_total_amount) if closeout.final_total_amount is not None else None,
                "billing_ready": closeout.billing_ready,
            },
        )

    @action(detail=False, methods=["get"])
    def reconciliation(self, request):
        self._commercial_or_403(request)
        return Response(CloseoutReconciliationReport.build())

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def submit(self, request, pk=None):
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        if closeout.status not in (CloseoutStatus.INCOMPLETE, CloseoutStatus.REOPENED, CloseoutStatus.EXCEPTION_REVIEW):
            return Response({"detail": "Closeout is not editable/submittable."}, status=status.HTTP_409_CONFLICT)
        CloseoutService.derive_actual_quantities(closeout)
        CloseoutService.rerate_from_original_snapshot(closeout.id)
        closeout.refresh_from_db()
        if closeout.blockers:
            closeout.status = CloseoutStatus.EXCEPTION_REVIEW
            closeout.save(update_fields=["status", "updated_at"])
            AuditService.record_event(request.user, "CLOSEOUT_SUBMIT_FAIL", closeout, before_snap, "Blockers found", request.headers.get("X-Idempotency-Key", ""))
            return Response(TripCloseoutSerializer(closeout).data, status=status.HTTP_409_CONFLICT)
        previous = closeout.status
        closeout.status = CloseoutStatus.SUBMITTED
        closeout.submitted_by = request.user
        closeout.submitted_at = timezone.now()
        closeout.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        self._audit(closeout, "SUBMIT", request.user, previous)
        AuditService.record_event(request.user, "CLOSEOUT_SUBMIT", closeout, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def approve(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        if closeout.status != CloseoutStatus.SUBMITTED:
            return Response({"detail": "Only submitted closeouts can be approved."}, status=status.HTTP_409_CONFLICT)
        if closeout.submitted_by_id == request.user.id:
            return Response({"detail": "Submitter cannot approve their own closeout."}, status=status.HTTP_403_FORBIDDEN)
        if closeout.blockers or closeout.final_total_amount is None:
            return Response({"detail": "Resolve blockers and calculate final charges before approval."}, status=status.HTTP_409_CONFLICT)
        previous = closeout.status
        closeout.status = CloseoutStatus.APPROVED
        closeout.approved_by = request.user
        closeout.approved_at = timezone.now()
        closeout.save(update_fields=["status", "approved_by", "approved_at", "billing_ready", "updated_at"])
        self._audit(closeout, "APPROVE", request.user, previous)
        AuditService.record_event(request.user, "CLOSEOUT_APPROVE", closeout, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"], url_path="return")
    @idempotent_action()
    @transaction.atomic
    def return_for_changes(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        if closeout.status not in (CloseoutStatus.SUBMITTED, CloseoutStatus.EXCEPTION_REVIEW):
            return Response({"detail": "Only submitted/exception closeouts can be returned."}, status=status.HTTP_409_CONFLICT)
        reason = self._reason(request)
        previous = closeout.status
        closeout.status = CloseoutStatus.REOPENED
        closeout.save(update_fields=["status", "billing_ready", "updated_at"])
        self._audit(closeout, "RETURN", request.user, previous, reason)
        AuditService.record_event(request.user, "CLOSEOUT_RETURN", closeout, before_snap, reason, request.headers.get("X-Idempotency-Key", ""))
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def reopen(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        if closeout.status not in (CloseoutStatus.APPROVED, CloseoutStatus.BILLING_READY):
            return Response({"detail": "Only approved closeouts can be reopened."}, status=status.HTTP_409_CONFLICT)
        if InvoiceTrip.objects.filter(trip=closeout.trip).exists():
            return Response({"detail": "An invoice reserves this trip; reverse/void it before reopening."}, status=status.HTTP_409_CONFLICT)
        reason = self._reason(request)
        previous = closeout.status
        closeout.status = CloseoutStatus.REOPENED
        closeout.approved_by = None
        closeout.approved_at = None
        closeout.save(update_fields=["status", "approved_by", "approved_at", "billing_ready", "updated_at"])
        self._audit(closeout, "REOPEN", request.user, previous, reason)
        AuditService.record_event(request.user, "CLOSEOUT_REOPEN", closeout, before_snap, reason, request.headers.get("X-Idempotency-Key", ""))
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def mark_billing_ready(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        if closeout.status != CloseoutStatus.APPROVED:
            return Response({"detail": "Closeout must be approved first."}, status=status.HTTP_409_CONFLICT)
        previous = closeout.status
        closeout.status = CloseoutStatus.BILLING_READY
        closeout.save(update_fields=["status", "billing_ready", "updated_at"])
        trip = closeout.trip
        trip.final_taxable_amount = closeout.final_taxable_amount
        trip.final_tax_amount = closeout.final_tax_amount
        trip.final_total_amount = closeout.final_total_amount
        trip.fare_amount = closeout.final_total_amount
        trip.pricing_amount_status = PricingAmountStatus.FINALIZED
        trip.save(update_fields=[
            "final_taxable_amount",
            "final_tax_amount",
            "final_total_amount",
            "fare_amount",
            "pricing_amount_status",
            "updated_at",
        ])
        self._audit(closeout, "MARK_BILLING_READY", request.user, previous)
        AuditService.record_event(request.user, "CLOSEOUT_MARK_BILLING_READY", closeout, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
        serialized = self.get_queryset().get(pk=closeout.pk)
        return Response(TripCloseoutSerializer(serialized).data)

    @action(detail=True, methods=["post"])
    def add_charge(self, request, pk=None):
        closeout = self.get_object()
        if closeout.status not in (CloseoutStatus.INCOMPLETE, CloseoutStatus.REOPENED, CloseoutStatus.EXCEPTION_REVIEW):
            return Response({"detail": "Charges can only change on editable closeouts."}, status=status.HTTP_409_CONFLICT)
        serializer = TripChargeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(closeout=closeout, created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def approve_charge(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        before_snap = AuditService.serialize_model(closeout)
        charge = closeout.extra_charges.filter(pk=request.data.get("charge_id")).first()
        if not charge:
            return Response({"detail": "Charge not found for this closeout."}, status=status.HTTP_404_NOT_FOUND)
        if charge.created_by_id == request.user.id:
            return Response({"detail": "Charge creator cannot approve their own charge."}, status=status.HTTP_403_FORBIDDEN)
        charge.is_approved = True
        charge.approved_by = request.user
        charge.approved_at = timezone.now()
        charge.save(update_fields=["is_approved", "approved_by", "approved_at"])
        CloseoutService.rerate_from_original_snapshot(closeout.id)
        closeout.refresh_from_db()
        self._audit(closeout, "APPROVE_CHARGE", request.user, closeout.status, f"Charge {charge.id}")
        AuditService.record_event(request.user, "CLOSEOUT_APPROVE_CHARGE", closeout, before_snap, f"Charge {charge.id}", request.headers.get("X-Idempotency-Key", ""))
        return Response(TripCloseoutSerializer(closeout).data)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("legal_entity", "customer").prefetch_related("lines", "audit_events", "documents__delivery_attempts").all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasLegalEntityScope, HasCustomerScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Enforce Customer Scope
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            active_companies = self.request.user.active_memberships.values_list("company_id", flat=True)
            if active_companies.exists():
                queryset = queryset.filter(customer_id__in=active_companies)
                
        # Enforce Legal Entity Scope
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            assigned = self.request.user.assigned_legal_entities.all()
            if assigned.exists():
                queryset = queryset.filter(legal_entity__in=assigned)
                
        return queryset

    def _commercial_or_403(self, request):
        permission = IsCommercialAdmin()
        if not permission.has_permission(request, self):
            self.permission_denied(
                request, message="Commercial or accounting permission is required."
            )

    @staticmethod
    def _audit(invoice, action, actor, previous, reason=""):
        InvoiceAuditEvent.objects.create(
            invoice=invoice,
            action=action,
            actor=actor,
            from_status=previous,
            to_status=invoice.status,
            reason=reason,
            snapshot={
                "invoice_number": invoice.invoice_number,
                "total_amount": str(invoice.total_amount),
                "balance_amount": str(invoice.balance_amount),
            },
        )

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def submit_review(self, request, pk=None):
        self._commercial_or_403(request)
        invoice = self.get_object()
        before_snap = AuditService.serialize_model(invoice)
        if invoice.status != InvoiceStatus.DRAFT:
            return Response(
                {"detail": "Only draft invoices can be submitted for review."},
                status=status.HTTP_409_CONFLICT,
            )
        previous = invoice.status
        invoice.status = InvoiceStatus.REVIEW
        invoice.submitted_by = request.user
        invoice.submitted_at = timezone.now()
        invoice.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        self._audit(invoice, "SUBMIT_REVIEW", request.user, previous)
        AuditService.record_event(request.user, "INVOICE_SUBMIT_REVIEW", invoice, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
        return Response(InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def approve(self, request, pk=None):
        self._commercial_or_403(request)
        invoice = self.get_object()
        before_snap = AuditService.serialize_model(invoice)
        if invoice.status != InvoiceStatus.REVIEW:
            return Response(
                {"detail": "Only invoices in review can be approved."},
                status=status.HTTP_409_CONFLICT,
            )
        if invoice.submitted_by_id == request.user.id or invoice.created_by_id == request.user.id:
            return Response(
                {"detail": "The creator or submitter cannot approve their own invoice."},
                status=status.HTTP_403_FORBIDDEN,
            )
        previous = invoice.status
        invoice.status = InvoiceStatus.APPROVED
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        self._audit(invoice, "APPROVE", request.user, previous)
        AuditService.record_event(request.user, "INVOICE_APPROVE", invoice, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
        return Response(InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    @transaction.atomic
    def void(self, request, pk=None):
        self._commercial_or_403(request)
        check_period_lock(timezone.now().date())
        invoice = self.get_object()
        before_snap = AuditService.serialize_model(invoice)
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response(
                {"reason": "A correction reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invoice.status not in {
            InvoiceStatus.DRAFT,
            InvoiceStatus.REVIEW,
            InvoiceStatus.APPROVED,
            InvoiceStatus.ISSUED,
            InvoiceStatus.SENT,
        }:
            return Response(
                {"detail": "This invoice cannot be voided in its current state."},
                status=status.HTTP_409_CONFLICT,
            )
        if invoice.paid_amount:
            return Response(
                {"detail": "Paid invoices require a credit-note correction."},
                status=status.HTTP_409_CONFLICT,
            )
        previous = invoice.status
        invoice.status = InvoiceStatus.VOID
        invoice.save(update_fields=["status", "updated_at"])

        # Post Reversal Journal Entry if issued or sent
        if previous in [InvoiceStatus.ISSUED, InvoiceStatus.SENT]:
            PostingEngine.post_invoice_reversal(invoice)

        self._audit(invoice, "VOID", request.user, previous, reason)
        AuditService.record_event(request.user, "INVOICE_VOID", invoice, before_snap, reason, request.headers.get("X-Idempotency-Key", ""))
        return Response(InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data)

    @action(detail=False, methods=["get"])
    def eligible_trips(self, request):
        queryset = Trip.objects.select_related(
            "customer", "contract", "closeout"
        ).prefetch_related("closeout__extra_charges")
        if request.query_params.get("customer"):
            queryset = queryset.filter(customer_id=request.query_params["customer"])
        booking_type = request.query_params.get("booking_type") or request.query_params.get("channel")
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type.upper())
        if request.query_params.get("date_from"):
            queryset = queryset.filter(pickup_at__date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            queryset = queryset.filter(pickup_at__date__lte=request.query_params["date_to"])
        if request.query_params.get("po_number") is not None:
            queryset = queryset.filter(po_number=request.query_params["po_number"])
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(customer_name__icontains=search)
                | Q(customer__display_name__icontains=search)
                | Q(pickup_city__icontains=search)
                | Q(drop_city__icontains=search)
                | Q(po_number__icontains=search)
                | Q(bill_to_name_snapshot__icontains=search)
            )

        blocker_code = request.query_params.get("blocker")
        trips = list(queryset.order_by("-pickup_at"))
        if blocker_code:
            trips = [
                trip
                for trip in trips
                if blocker_code in {
                    blocker.code
                    for blocker in BillabilityService.evaluate(trip).blockers
                }
            ]
        else:
            trips = [
                trip for trip in trips
                if BillabilityService.evaluate(trip).eligible
            ]
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(
                100, max(1, int(request.query_params.get("page_size", 25)))
            )
        except ValueError:
            return Response(
                {"detail": "page and page_size must be positive integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = len(trips)
        start = (page - 1) * page_size
        selected = trips[start : start + page_size]
        summary = {
            "eligible_trip_count": count,
            "estimated_taxable_amount": str(
                sum(
                    (
                        BillabilityService.evaluate(trip).estimated_taxable_amount
                        for trip in trips
                    ),
                    Decimal("0.00"),
                )
            ),
            "estimated_tax_amount": str(
                sum(
                    (
                        BillabilityService.amount_summary(trip)["tax_amount"]
                        for trip in trips
                    ),
                    Decimal("0.00"),
                )
            ),
            "estimated_total_amount": str(
                sum(
                    (
                        BillabilityService.amount_summary(trip)["total_amount"]
                        for trip in trips
                    ),
                    Decimal("0.00"),
                )
            ),
        }
        return Response({
            "count": count,
            "page": page,
            "page_size": page_size,
            "next_page": page + 1 if start + page_size < count else None,
            "previous_page": page - 1 if page > 1 else None,
            "summary": summary,
            "results": BillableTripSerializer(selected, many=True).data,
        })

    @action(detail=False, methods=["post"])
    def grouping_preview(self, request):
        trip_ids = request.data.get("trip_ids", [])
        trips = list(
            Trip.objects.filter(id__in=trip_ids).select_related(
                "customer", "contract", "closeout"
            )
        )
        if not trip_ids or len(trips) != len(set(trip_ids)):
            return Response(
                {"detail": "A unique list of existing trip_ids is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        groups = {}
        for trip in trips:
            result = BillabilityService.evaluate(trip)
            grouping_key = BillabilityService.grouping_key(trip)
            key = tuple(grouping_key.values())
            group = groups.setdefault(key, {
                "grouping_key": grouping_key,
                "bill_to_key": grouping_key["bill_to_key"],
                "bill_to_name": trip.bill_to_name_snapshot,
                "bill_to_snapshot": {
                    "type": trip.bill_to_type,
                    "name": trip.bill_to_name_snapshot,
                    "address": trip.bill_to_address_snapshot,
                    "gstin": trip.bill_to_gstin_snapshot,
                    "email": trip.bill_to_email_snapshot,
                    "phone": trip.bill_to_phone_snapshot,
                },
                "booking_channel": grouping_key["booking_channel"],
                "currency": grouping_key["currency"],
                "po_number": grouping_key["po_number"],
                "billing_cycle": grouping_key["billing_cycle"],
                "trip_ids": [],
                "eligible": True,
                "blockers": [],
                "estimated_taxable_amount": Decimal("0.00"),
                "estimated_tax_amount": Decimal("0.00"),
                "estimated_total_amount": Decimal("0.00"),
            })
            group["trip_ids"].append(trip.id)
            amounts = BillabilityService.amount_summary(trip)
            group["estimated_taxable_amount"] += amounts["taxable_amount"]
            group["estimated_tax_amount"] += amounts["tax_amount"]
            group["estimated_total_amount"] += amounts["total_amount"]
            if not result.eligible:
                group["eligible"] = False
                group["blockers"].extend(
                    {"trip_id": trip.id, "code": item.code, "message": item.message}
                    for item in result.blockers
                )

        payload = []
        for group in groups.values():
            for field in (
                "estimated_taxable_amount",
                "estimated_tax_amount",
                "estimated_total_amount",
            ):
                group[field] = str(group[field])
            payload.append(group)
        return Response({"groups": payload})

    @action(detail=False, methods=["get"])
    def aging(self, request):
        as_of_date = request.query_params.get("as_of_date")
        report = ARAgingReport.build(as_of_date=as_of_date)
        return Response(report)

    @action(detail=False, methods=["get"])
    def statement(self, request):
        customer_id = request.query_params.get("customer")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not customer_id or not start_date or not end_date:
            raise ValidationError("customer, start_date, and end_date are required query parameters.")

        from fleet.models import CorporateCustomer
        try:
            customer = CorporateCustomer.objects.get(pk=customer_id)
        except CorporateCustomer.DoesNotExist:
            raise ValidationError("Corporate customer not found.")

        report = CustomerStatementReport.build(customer, start_date, end_date)
        return Response(report)

    @action(detail=False, methods=["post"])
    @idempotent_action()
    def generate_draft(self, request):
        legal_entity_id = request.data.get("legal_entity_id")
        trip_ids = request.data.get("trip_ids", [])

        if not legal_entity_id or not trip_ids:
            return Response({"detail": "legal_entity_id and trip_ids are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entity = LegalEntity.objects.get(id=legal_entity_id)
            invoice = InvoiceService.generate_invoice_draft(entity, trip_ids, created_by=request.user)
            AuditService.record_event(request.user, "INVOICE_GENERATE_DRAFT", invoice, None, "", request.headers.get("X-Idempotency-Key", ""))
            return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        except LegalEntity.DoesNotExist:
            return Response({"detail": "Legal entity not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    @idempotent_action()
    def issue(self, request, pk=None):
        self._commercial_or_403(request)
        invoice = self.get_object()
        before_snap = AuditService.serialize_model(invoice)
        if invoice.status != InvoiceStatus.APPROVED:
            return Response(
                {"detail": "Invoice must be independently approved before issue."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            previous = invoice.status
            issued = InvoiceService.issue_invoice(invoice, created_by=request.user)
            self._audit(issued, "ISSUE", request.user, previous)
            AuditService.record_event(request.user, "INVOICE_ISSUE", issued, before_snap, "", request.headers.get("X-Idempotency-Key", ""))
            return Response(
                InvoiceSerializer(self.get_queryset().get(pk=issued.pk)).data
            )
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def html_preview(self, request, pk=None):
        from django.http import HttpResponse
        from .pdf_service import PDFService
        invoice = self.get_object()
        html = PDFService.render_invoice_html(invoice)
        return HttpResponse(html, content_type="text/html")

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        from django.core.files.storage import default_storage
        from django.http import FileResponse
        from .pdf_service import PDFService

        invoice = self.get_object()
        document = PDFService.get_or_create_document(invoice, request=request)
        response = FileResponse(
            default_storage.open(document.attachment.storage_key, "rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=document.attachment.original_name,
        )
        response["ETag"] = document.checksum_sha256
        response["X-Invoice-Document-Version"] = str(document.version)
        return response

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def record_delivery(self, request, pk=None):
        self._commercial_or_403(request)
        from .pdf_service import PDFService

        invoice = self.get_object()
        if invoice.status not in {
            InvoiceStatus.ISSUED,
            InvoiceStatus.SENT,
            InvoiceStatus.PARTIALLY_PAID,
            InvoiceStatus.PAID,
        }:
            return Response(
                {"detail": "Only issued invoices can be delivered."},
                status=status.HTTP_409_CONFLICT,
            )
        recipients = request.data.get("recipients") or []
        if not isinstance(recipients, list) or not recipients:
            return Response(
                {"recipients": "At least one recipient is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        outcome = str(request.data.get("status", "SENT")).upper()
        if outcome not in {"SENT", "FAILED"}:
            return Response(
                {"status": "Delivery status must be SENT or FAILED."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        document = PDFService.get_or_create_document(invoice, request=request)
        attempt = InvoiceDeliveryAttempt.objects.create(
            document=document,
            recipients=recipients,
            status=outcome,
            failure_message=str(request.data.get("failure_message", "")),
            attempted_by=request.user,
        )
        previous = invoice.status
        if outcome == "SENT" and invoice.status == InvoiceStatus.ISSUED:
            invoice.status = InvoiceStatus.SENT
            invoice.save(update_fields=["status", "updated_at"])
        self._audit(
            invoice,
            "DELIVERY_SENT" if outcome == "SENT" else "DELIVERY_FAILED",
            request.user,
            previous,
            attempt.failure_message,
        )
        return Response(
            InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data
        )

    @action(detail=True, methods=["get"])
    def tally_xml(self, request, pk=None):
        from django.http import HttpResponse
        from .reports import FinanceReportService
        invoice = self.get_object()
        xml = FinanceReportService.export_tally_xml(invoice)
        return HttpResponse(xml, content_type="application/xml")

    @action(detail=True, methods=["get"], url_path="official-pdf")
    def download_official_pdf(self, request, pk=None):
        """Stream the official Tax Invoice as a PDF download."""
        from django.http import HttpResponse
        from .reports import InvoiceReportService

        invoice = self.get_object()
        html_content = InvoiceReportService.render_official_tax_invoice(invoice)
        pdf_bytes = InvoiceReportService.render_pdf_from_html(html_content)
        invoice_label = invoice.invoice_number or f"DRAFT-{invoice.id}"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="tax-invoice-{invoice_label}.pdf"'
        return response

    @action(detail=True, methods=["get"], url_path="duty-slip-pdf")
    def download_duty_slip_pdf(self, request, pk=None):
        """Stream the Duty Slip Annexure for all trips on this invoice as a PDF download."""
        from django.http import HttpResponse
        from .reports import InvoiceReportService

        invoice = self.get_object()
        html_content = InvoiceReportService.render_duty_slip_annexure(invoice)
        pdf_bytes = InvoiceReportService.render_pdf_from_html(html_content)
        invoice_label = invoice.invoice_number or f"DRAFT-{invoice.id}"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="duty-slip-{invoice_label}.pdf"'
        return response

    @action(detail=False, methods=["get"], url_path="reconciliation-dashboard")
    def reconciliation_dashboard(self, request):
        self._commercial_or_403(request)
        from .reports import ReconciliationService
        data = ReconciliationService.reconcile()
        return Response(data)


class PaymentReceiptViewSet(viewsets.ModelViewSet):
    queryset = PaymentReceipt.objects.select_related("customer", "legal_entity").all().order_by("-receipt_date", "-id")
    serializer_class = PaymentReceiptSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasLegalEntityScope, HasCustomerScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            active_companies = self.request.user.active_memberships.values_list("company_id", flat=True)
            if active_companies.exists():
                queryset = queryset.filter(customer_id__in=active_companies)
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            assigned = self.request.user.assigned_legal_entities.all()
            if assigned.exists():
                queryset = queryset.filter(legal_entity__in=assigned)
        return queryset

    @idempotent_action()
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        check_period_lock(timezone.now().date())
        legal_entity_id = request.data.get("legal_entity")
        customer_id = request.data.get("customer")
        amount = Decimal(str(request.data.get("amount", "0.00")))
        currency = request.data.get("currency", "INR")
        payment_method = request.data.get("payment_method", "BANK_TRANSFER")
        reference_number = request.data.get("reference_number", "")
        idempotency_key = request.headers.get("X-Idempotency-Key") or request.data.get("idempotency_key")

        legal_entity = LegalEntity.objects.get(pk=legal_entity_id)
        from fleet.models import CorporateCustomer
        customer = CorporateCustomer.objects.get(pk=customer_id) if customer_id else None

        receipt = PaymentService.record_receipt(
            legal_entity=legal_entity,
            customer=customer,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            reference_number=reference_number,
            created_by=request.user,
            idempotency_key=idempotency_key
        )

        AuditService.record_event(request.user, "RECEIPT_CREATE", receipt, None, "", idempotency_key or "")
        return Response(PaymentReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reverse(self, request, pk=None):
        receipt = self.get_object()
        reason = request.data.get("reason", "")
        if not reason:
            raise ValidationError("A reversal reason is required.")
        reversed_receipt = PaymentService.reverse_receipt(receipt, reason=reason, reversed_by=request.user)
        AuditService.record_event(request.user, "RECEIPT_REVERSE", reversed_receipt, None, reason, "")
        return Response(PaymentReceiptSerializer(reversed_receipt).data)


class PaymentAllocationViewSet(viewsets.ModelViewSet):
    queryset = PaymentAllocation.objects.select_related("receipt", "invoice").all().order_by("-id")
    serializer_class = PaymentAllocationSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission]

    @idempotent_action()
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        check_period_lock(timezone.now().date())
        receipt_id = request.data.get("receipt")
        invoice_id = request.data.get("invoice")
        amount = Decimal(str(request.data.get("allocated_amount", "0.00")))
        tds_amount = Decimal(str(request.data.get("tds_amount", "0.00")))

        receipt = PaymentReceipt.objects.get(pk=receipt_id)
        invoice = Invoice.objects.get(pk=invoice_id)

        allocation = PaymentService.allocate_payment(receipt, invoice, amount, tds_amount)

        AuditService.record_event(request.user, "ALLOCATION_CREATE", allocation, None, "", request.headers.get("X-Idempotency-Key", ""))
        return Response(PaymentAllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reverse(self, request, pk=None):
        allocation = self.get_object()
        reversed_alloc = PaymentService.reverse_allocation(allocation)
        AuditService.record_event(request.user, "ALLOCATION_REVERSE", reversed_alloc, None, "Reversal via API", "")
        return Response(PaymentAllocationSerializer(reversed_alloc).data)


class CreditNoteViewSet(viewsets.ModelViewSet):
    queryset = CreditNote.objects.select_related("invoice", "legal_entity").all().order_by("-created_at", "-id")
    serializer_class = CreditNoteSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasLegalEntityScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            assigned = self.request.user.assigned_legal_entities.all()
            if assigned.exists():
                queryset = queryset.filter(legal_entity__in=assigned)
        return queryset

    @idempotent_action()
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        check_period_lock(timezone.now().date())
        invoice_id = request.data.get("invoice")
        invoice = Invoice.objects.get(pk=invoice_id)
        reason = request.data.get("reason", "")
        lines = request.data.get("lines", [])

        credit_note = CreditNoteService.create_credit_note(
            invoice=invoice,
            reason=reason,
            lines_data=lines,
            created_by=request.user
        )
        return Response(CreditNoteSerializer(credit_note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        credit_note = self.get_object()
        approved = CreditNoteService.approve_credit_note(credit_note, approved_by=request.user)
        return Response(CreditNoteSerializer(approved).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def void(self, request, pk=None):
        credit_note = self.get_object()
        voided = CreditNoteService.void_credit_note(credit_note, voided_by=request.user)
        return Response(CreditNoteSerializer(voided).data)


class DebitNoteViewSet(viewsets.ModelViewSet):
    queryset = DebitNote.objects.select_related("invoice", "legal_entity").all().order_by("-created_at", "-id")
    serializer_class = DebitNoteSerializer
    permission_classes = [permissions.IsAuthenticated, HasFinancialRolePermission, HasLegalEntityScope]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser and self.request.user.role != UserRole.ADMIN:
            assigned = self.request.user.assigned_legal_entities.all()
            if assigned.exists():
                queryset = queryset.filter(legal_entity__in=assigned)
        return queryset

    @idempotent_action()
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        check_period_lock(timezone.now().date())
        invoice_id = request.data.get("invoice")
        invoice = Invoice.objects.get(pk=invoice_id)
        reason = request.data.get("reason", "")
        lines = request.data.get("lines", [])

        debit_note = DebitNoteService.create_debit_note(
            invoice=invoice,
            reason=reason,
            lines_data=lines,
            created_by=request.user
        )
        return Response(DebitNoteSerializer(debit_note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        debit_note = self.get_object()
        approved = DebitNoteService.approve_debit_note(debit_note, approved_by=request.user)
        return Response(DebitNoteSerializer(approved).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def void(self, request, pk=None):
        debit_note = self.get_object()
        voided = DebitNoteService.void_debit_note(debit_note, voided_by=request.user)
        return Response(DebitNoteSerializer(voided).data)

