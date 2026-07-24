import hashlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .models import UploadedAsset, UploadedAssetAccessAudit


class StorageConfigurationError(Exception):
    pass


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR") if request else None
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") if request else None


def audit_asset_access(asset, request, action):
    UploadedAssetAccessAudit.objects.create(
        asset=asset,
        user=request.user if request and request.user.is_authenticated else None,
        action=action,
        ip_address=get_client_ip(request),
    )


def upload_asset(upload, *, kind, folder="uploads", request=None, metadata=None):
    backend = getattr(settings, "MEDIA_STORAGE_BACKEND", "local")
    if backend != "local":
        raise StorageConfigurationError(f"Unsupported media storage backend: {backend}")

    file_bytes = upload.read()
    checksum = hashlib.sha256(file_bytes).hexdigest()
    storage_key = default_storage.save(f"{folder}/{upload.name}", ContentFile(file_bytes))

    asset = UploadedAsset.objects.create(
        kind=kind,
        file_url=f"{settings.MEDIA_URL}{storage_key}",
        storage_key=storage_key,
        checksum_sha256=checksum,
        uploaded_by=request.user if request and request.user.is_authenticated else None,
        original_name=upload.name,
        content_type=getattr(upload, "content_type", "") or "",
        metadata={
            "storage_backend": backend,
            **(metadata or {}),
        },
    )
    audit_asset_access(asset, request, UploadedAssetAccessAudit.ACTION_CREATED)
    return asset
