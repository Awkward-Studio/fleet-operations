from django.contrib import admin

from .models import Driver, Trip, Vehicle


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

