from django.contrib import admin

from .models import UploadedAsset, UploadedAssetAccessAudit


@admin.register(UploadedAsset)
class UploadedAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "original_name", "content_type", "checksum_sha256", "is_private", "created_at")
    list_filter = ("kind", "is_private", "created_at")
    search_fields = ("id", "original_name", "checksum_sha256", "storage_key")


@admin.register(UploadedAssetAccessAudit)
class UploadedAssetAccessAuditAdmin(admin.ModelAdmin):
    list_display = ("asset", "user", "action", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("asset__id", "asset__original_name", "user__username")
