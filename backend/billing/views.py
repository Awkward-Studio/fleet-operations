import datetime
from decimal import Decimal
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import LegalEntity, TripCloseout, TripCharge, Invoice, CloseoutStatus, InvoiceStatus
from .serializers import BillableTripSerializer, LegalEntitySerializer, TripCloseoutSerializer, TripChargeSerializer, InvoiceSerializer
from .services import BillabilityService, InvoiceService
from fleet.models import Trip


class LegalEntityViewSet(viewsets.ModelViewSet):
    queryset = LegalEntity.objects.filter(is_active=True)
    serializer_class = LegalEntitySerializer
    permission_classes = [permissions.IsAuthenticated]


class TripCloseoutViewSet(viewsets.ModelViewSet):
    queryset = TripCloseout.objects.select_related("trip").prefetch_related("extra_charges").all()
    serializer_class = TripCloseoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        closeout = self.get_object()
        closeout.status = CloseoutStatus.APPROVED
        closeout.billing_ready = True
        closeout.approved_by = request.user if request.user.is_authenticated else None
        closeout.approved_at = datetime.datetime.now(datetime.timezone.utc)
        closeout.save()
        return Response(TripCloseoutSerializer(closeout).data)

    @action(detail=True, methods=["post"])
    def add_charge(self, request, pk=None):
        closeout = self.get_object()
        serializer = TripChargeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(closeout=closeout)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
