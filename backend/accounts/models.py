from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    DISPATCHER = "dispatcher", "Dispatcher"
    ACCOUNTANT = "accountant", "Accountant"
    COMMERCIAL = "commercial", "Commercial"


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
        else:
            return ["read_customers", "dispatch_trips"]
