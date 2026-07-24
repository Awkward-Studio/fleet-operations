import os
import uuid

from django.conf import settings
from django.db import models


def asset_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1] or ""
    return f"{instance.kind}/{instance.id}{ext}"


class UploadedAsset(models.Model):
    KIND_IMAGE = "image"
    KIND_INVOICE = "invoice"
    KIND_PDF = "pdf"

    KIND_CHOICES = [
        (KIND_IMAGE, "Image"),
        (KIND_INVOICE, "Invoice"),
        (KIND_PDF, "PDF"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    file_url = models.URLField(null=True, blank=True)
    storage_key = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    is_private = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_assets",
    )
    metadata = models.JSONField(default=dict, blank=True)
    # file = models.FileField(upload_to=asset_upload_to)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind}:{self.original_name or self.file_url or str(self.id)}"


class UploadedAssetAccessAudit(models.Model):
    ACTION_CREATED = "created"
    ACTION_ACCESSED = "accessed"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_ACCESSED, "Accessed"),
    ]

    asset = models.ForeignKey(UploadedAsset, related_name="access_audits", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_access_audits",
    )
    action = models.CharField(max_length=24, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.asset_id} {self.action} at {self.created_at:%Y-%m-%d %H:%M:%S}"
