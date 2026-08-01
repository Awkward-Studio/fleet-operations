from rest_framework import permissions
from .models import CorporateRole, UserRole

class IsCorporateAdmin(permissions.BasePermission):
    """
    Allows access only to authenticated users who are Corporate Admins of the specified company.
    If company ID is passed in request data or query parameters, it validates membership in that company.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers and system admins bypass corporate checks
        if request.user.is_superuser:
            return True

        # Check if user has any active corporate admin membership
        active_memberships = request.user.active_memberships
        company_id = request.data.get("company") or request.query_params.get("company")
        
        if company_id:
            return active_memberships.filter(company_id=company_id, role=CorporateRole.ADMIN).exists()
        
        # If no specific company requested, allow if they are admin of at least one company
        return active_memberships.filter(role=CorporateRole.ADMIN).exists()


class HasFinancialRolePermission(permissions.BasePermission):
    """
    Enforces role-based action level permissions for financial mutations and views.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return True
            
        role = request.user.role
        action = getattr(view, "action", None)
        if action is None:
            return True
            
        view_name = view.__class__.__name__
        
        # LegalEntity actions
        if view_name == "LegalEntityViewSet":
            if action in ["list", "retrieve"]:
                return role in [UserRole.COMMERCIAL, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
            elif action in ["create", "update", "partial_update", "destroy"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
                
        # Closeout actions
        elif view_name == "TripCloseoutViewSet":
            if action in ["list", "retrieve"]:
                return role in [UserRole.DISPATCHER, UserRole.COMMERCIAL, UserRole.OPERATIONS_APPROVER, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
            elif action in ["submit", "add_charge"]:
                return role in [UserRole.DISPATCHER, UserRole.COMMERCIAL, UserRole.OPERATIONS_APPROVER, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action in ["approve", "return_for_changes", "reopen", "approve_charge"]:
                return role in [UserRole.COMMERCIAL, UserRole.OPERATIONS_APPROVER, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action == "mark_billing_ready":
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action == "reconciliation":
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
                
        # Invoice actions
        elif view_name == "InvoiceViewSet":
            if action in ["list", "retrieve", "eligible_trips", "grouping_preview"]:
                return role in [UserRole.COMMERCIAL, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
            elif action in ["generate_draft", "submit_review", "issue", "record_delivery"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action in ["approve", "void"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action in ["download_official_pdf", "download_duty_slip_pdf", "html_preview", "document", "tally_xml"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
                
        # Receipt, Allocation, CreditNote, TripExpense actions
        elif view_name in ["PaymentReceiptViewSet", "PaymentAllocationViewSet", "CreditNoteViewSet", "TripExpenseViewSet"]:
            if action in ["list", "retrieve"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
            elif action in ["create", "update", "partial_update"]:
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
            elif action == "destroy":
                return role in [UserRole.FINANCE_APPROVER]

        elif view_name == "OTASettlementBatchViewSet":
            if action in ["list", "retrieve", "profitability"]:
                return role in [UserRole.COMMERCIAL, UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER, UserRole.AUDITOR]
            elif action == "import_batch":
                return role in [UserRole.ACCOUNTANT, UserRole.FINANCE_APPROVER]
                
        return False


class HasLegalEntityScope(permissions.BasePermission):
    """
    Restricts access to objects belonging only to assigned legal entities.
    """
    def has_permission(self, request, view):
        # We also enforce query filters in get_queryset to handle list responses
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return True
        assigned = request.user.assigned_legal_entities.all()
        if not assigned.exists():
            return True
            
        obj_entity = getattr(obj, "legal_entity", None)
        if obj_entity is None and hasattr(obj, "invoice"):
            obj_entity = getattr(obj.invoice, "legal_entity", None)
        if obj_entity is None and hasattr(obj, "receipt"):
            obj_entity = getattr(obj.receipt, "legal_entity", None)
            
        return obj_entity in assigned


class HasCustomerScope(permissions.BasePermission):
    """
    Restricts access to objects belonging to customer scope.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return True
        active_companies = request.user.active_memberships.values_list("company_id", flat=True)
        if not active_companies.exists():
            return True
            
        obj_customer_id = getattr(obj, "customer_id", None)
        if obj_customer_id is None and hasattr(obj, "trip"):
            obj_customer_id = getattr(obj.trip, "customer_id", None)
            
        return obj_customer_id in active_companies

