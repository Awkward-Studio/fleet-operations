import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    DISPATCHER = "dispatcher", "Dispatcher"
    ACCOUNTANT = "accountant", "Accountant"
    COMMERCIAL = "commercial", "Commercial"
    DRIVER = "driver", "Driver"


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=24,
        choices=UserRole.choices,
        default=UserRole.ADMIN,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_commercial_admin(self):
        return self.is_superuser or self.role in [UserRole.ADMIN, UserRole.COMMERCIAL, UserRole.ACCOUNTANT]

    @property
    def permissions_list(self):
        if self.is_superuser or self.role == UserRole.ADMIN:
            return ["read_customers", "write_customers", "read_contracts", "write_contracts", "dispatch_trips"]
        elif self.role in [UserRole.COMMERCIAL, UserRole.ACCOUNTANT]:
            return ["read_customers", "write_customers", "read_contracts", "write_contracts"]
        elif self.role == UserRole.DRIVER:
            return []
        else:
            return ["read_customers", "dispatch_trips"]

    @property
    def active_memberships(self):
        from django.utils import timezone
        today = timezone.now().date()
        # Query active memberships
        qs = self.corporate_memberships.filter(is_active=True, suspended_at__isnull=True)
        active_ids = []
        for m in qs:
            if m.start_date and m.start_date > today:
                continue
            if m.end_date and m.end_date < today:
                continue
            active_ids.append(m.id)
        return self.corporate_memberships.filter(id__in=active_ids)


class CorporateRole(models.TextChoices):
    ADMIN = "admin", "Corporate Admin"
    TRAVEL_DESK = "travel_desk", "Travel Desk Executive"
    REQUESTER = "requester", "Requester"
    APPROVER = "approver", "Approver"
    FINANCE = "finance", "Finance Viewer"
    SUPPORT = "support", "Sales/Support"
    READ_ONLY = "read_only", "Read-Only"


ROLE_PERMISSIONS = {
    CorporateRole.ADMIN: [
        "manage_members", "view_bookings", "create_bookings", "approve_bookings",
        "view_invoices", "view_guests", "manage_guests", "view_statements"
    ],
    CorporateRole.TRAVEL_DESK: [
        "view_bookings", "create_bookings", "view_guests", "manage_guests"
    ],
    CorporateRole.REQUESTER: [
        "view_bookings", "create_bookings"
    ],
    CorporateRole.APPROVER: [
        "view_bookings", "approve_bookings"
    ],
    CorporateRole.FINANCE: [
        "view_bookings", "view_invoices", "view_statements"
    ],
    CorporateRole.SUPPORT: [
        "view_bookings", "view_guests"
    ],
    CorporateRole.READ_ONLY: [
        "view_bookings"
    ],
}


class CorporateMembership(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="corporate_memberships",
    )
    company = models.ForeignKey(
        "rentals.CorporateCustomer",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=24,
        choices=CorporateRole.choices,
        default=CorporateRole.READ_ONLY,
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.company.name} ({self.role})"


class CorporateInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    company = models.ForeignKey(
        "rentals.CorporateCustomer",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    role = models.CharField(
        max_length=24,
        choices=CorporateRole.choices,
        default=CorporateRole.READ_ONLY,
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        from django.utils import timezone
        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"Invite for {self.email} to {self.company.name} ({self.role})"

