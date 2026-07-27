from rest_framework import permissions
from .models import CorporateRole

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
