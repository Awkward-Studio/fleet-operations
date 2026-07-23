from rest_framework import permissions


class IsCommercialAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow read-only access to operational users (dispatchers, drivers)
    and full write access to Commercial/Admin/Accountant users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return (
            getattr(request.user, "is_superuser", False)
            or getattr(request.user, "is_commercial_admin", False)
        )


class IsCommercialAdmin(permissions.BasePermission):
    """
    Custom permission requiring Commercial/Admin/Accountant role for all operations.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return (
            getattr(request.user, "is_superuser", False)
            or getattr(request.user, "is_commercial_admin", False)
        )
