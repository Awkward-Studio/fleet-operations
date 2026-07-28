from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone

from .models import CloseoutAuditEvent, LegalEntity, TripCloseout, TripCharge, Invoice, InvoiceTrip, CloseoutStatus, InvoiceStatus
from .serializers import BillableTripSerializer, LegalEntitySerializer, TripCloseoutSerializer, TripChargeSerializer, InvoiceSerializer
from .services import BillabilityService, CloseoutService, InvoiceService
from .reports import CloseoutReconciliationReport
from fleet.models import PricingAmountStatus, Trip
from fleet.permissions import IsCommercialAdmin


class LegalEntityViewSet(viewsets.ModelViewSet):
    queryset = LegalEntity.objects.filter(is_active=True)
    serializer_class = LegalEntitySerializer
    permission_classes = [permissions.IsAuthenticated]


class TripCloseoutViewSet(viewsets.ModelViewSet):
    queryset = TripCloseout.objects.select_related("trip").prefetch_related("extra_charges", "audit_events").all()
    serializer_class = TripCloseoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
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
    @transaction.atomic
    def submit(self, request, pk=None):
        closeout = self.get_object()
        if closeout.status not in (CloseoutStatus.INCOMPLETE, CloseoutStatus.REOPENED, CloseoutStatus.EXCEPTION_REVIEW):
            return Response({"detail": "Closeout is not editable/submittable."}, status=status.HTTP_409_CONFLICT)
        CloseoutService.derive_actual_quantities(closeout)
        CloseoutService.rerate_from_original_snapshot(closeout.id)
        closeout.refresh_from_db()
        if closeout.blockers:
            closeout.status = CloseoutStatus.EXCEPTION_REVIEW
            closeout.save(update_fields=["status", "updated_at"])
            return Response(TripCloseoutSerializer(closeout).data, status=status.HTTP_409_CONFLICT)
        previous = closeout.status
        closeout.status = CloseoutStatus.SUBMITTED
        closeout.submitted_by = request.user
        closeout.submitted_at = timezone.now()
        closeout.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        self._audit(closeout, "SUBMIT", request.user, previous)
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
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
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"], url_path="return")
    @transaction.atomic
    def return_for_changes(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
        if closeout.status not in (CloseoutStatus.SUBMITTED, CloseoutStatus.EXCEPTION_REVIEW):
            return Response({"detail": "Only submitted/exception closeouts can be returned."}, status=status.HTTP_409_CONFLICT)
        reason = self._reason(request)
        previous = closeout.status
        closeout.status = CloseoutStatus.REOPENED
        closeout.save(update_fields=["status", "billing_ready", "updated_at"])
        self._audit(closeout, "RETURN", request.user, previous, reason)
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reopen(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
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
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def mark_billing_ready(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
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
    @transaction.atomic
    def approve_charge(self, request, pk=None):
        self._commercial_or_403(request)
        closeout = self.get_object()
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
        return Response(TripCloseoutSerializer(closeout).data)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("legal_entity", "customer").prefetch_related("lines").all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

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
        return Response(BillableTripSerializer(trips, many=True).data)

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
            key = (
                trip.bill_to_key,
                trip.booking_type,
                trip.contract.currency if trip.contract_id else "INR",
                trip.po_number,
                (trip.pricing_snapshot or {}).get("billing_cycle", "ON_DEMAND"),
            )
            group = groups.setdefault(key, {
                "bill_to_key": trip.bill_to_key,
                "bill_to_name": trip.bill_to_name_snapshot,
                "booking_channel": trip.booking_type,
                "currency": key[2],
                "po_number": trip.po_number,
                "billing_cycle": key[4],
                "trip_ids": [],
                "eligible": True,
                "blockers": [],
                "estimated_taxable_amount": Decimal("0.00"),
            })
            group["trip_ids"].append(trip.id)
            group["estimated_taxable_amount"] += result.estimated_taxable_amount
            if not result.eligible:
                group["eligible"] = False
                group["blockers"].extend(
                    {"trip_id": trip.id, "code": item.code, "message": item.message}
                    for item in result.blockers
                )

        payload = []
        for group in groups.values():
            group["estimated_taxable_amount"] = str(group["estimated_taxable_amount"])
            payload.append(group)
        return Response({"groups": payload})

    @action(detail=False, methods=["post"])
    def generate_draft(self, request):
        legal_entity_id = request.data.get("legal_entity_id")
        trip_ids = request.data.get("trip_ids", [])

        if not legal_entity_id or not trip_ids:
            return Response({"detail": "legal_entity_id and trip_ids are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            entity = LegalEntity.objects.get(id=legal_entity_id)
            invoice = InvoiceService.generate_invoice_draft(entity, trip_ids, created_by=request.user)
            return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        except LegalEntity.DoesNotExist:
            return Response({"detail": "Legal entity not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        invoice = self.get_object()
        try:
            issued = InvoiceService.issue_invoice(invoice, created_by=request.user)
            return Response(InvoiceSerializer(issued).data)
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
    def tally_xml(self, request, pk=None):
        from django.http import HttpResponse
        from .reports import FinanceReportService
        invoice = self.get_object()
        xml = FinanceReportService.export_tally_xml(invoice)
        return HttpResponse(xml, content_type="application/xml")
