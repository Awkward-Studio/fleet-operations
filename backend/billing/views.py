import datetime
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from .models import LegalEntity, TripCloseout, TripCharge, Invoice, CloseoutStatus, InvoiceStatus
from .serializers import LegalEntitySerializer, TripCloseoutSerializer, TripChargeSerializer, InvoiceSerializer
from .services import InvoiceService


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


