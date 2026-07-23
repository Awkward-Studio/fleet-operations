from django.contrib import admin

from .models import (
    ContractAllowance,
    ContractRate,
    CorporateContract,
    CorporateCustomer,
    CustomerContact,
    Driver,
    Trip,
    Vehicle,
)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "home_base", "status", "rating"]
    search_fields = ["name", "phone", "license_number"]
    list_filter = ["status", "home_base"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["registration_number", "make", "model", "category", "current_city", "status", "assigned_driver"]
    search_fields = ["registration_number", "make", "model"]
    list_filter = ["status", "category", "current_city"]


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["customer_name", "pickup_city", "drop_city", "pickup_at", "status", "vehicle", "driver"]
    search_fields = ["customer_name", "pickup_city", "drop_city"]
    list_filter = ["status", "ota_source"]


@admin.register(CorporateCustomer)
class CorporateCustomerAdmin(admin.ModelAdmin):
    list_display = ["code", "display_name", "legal_name", "status", "is_active", "gstin"]
    search_fields = ["code", "display_name", "legal_name", "gstin"]
    list_filter = ["status", "is_active"]


@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ["name", "customer", "contact_type", "phone", "email", "is_primary"]
    search_fields = ["name", "phone", "email"]
    list_filter = ["contact_type", "is_primary"]


@admin.register(CorporateContract)
class CorporateContractAdmin(admin.ModelAdmin):
    list_display = ["title", "customer", "version_name", "status", "effective_start", "effective_end"]
    search_fields = ["title", "version_name", "customer__display_name"]
    list_filter = ["status", "metering_policy"]


@admin.register(ContractRate)
class ContractRateAdmin(admin.ModelAdmin):
    list_display = ["contract", "city", "vehicle_category", "duty_type", "base_rate"]
    search_fields = ["city", "vehicle_category", "contract__title"]
    list_filter = ["duty_type", "city", "vehicle_category"]


@admin.register(ContractAllowance)
class ContractAllowanceAdmin(admin.ModelAdmin):
    list_display = ["contract", "allowance_type", "amount"]
    list_filter = ["allowance_type"]
