import hashlib
import os
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import get_valid_filename

from .models import UploadedAsset, UploadedAssetAccessAudit


class StorageConfigurationError(Exception):
    pass


RAILWAY_BACKENDS = {"railway", "railway_bucket", "s3"}


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


def _normalized_storage_backend():
    return (getattr(settings, "MEDIA_STORAGE_BACKEND", "local") or "local").strip().lower()


def _validate_storage_configuration(backend):
    if backend == "local":
        return
    if backend not in RAILWAY_BACKENDS:
        raise StorageConfigurationError(f"Unsupported media storage backend: {backend}")

    missing = [
        name
        for name in [
            "RAILWAY_BUCKET_ENDPOINT_URL",
            "RAILWAY_BUCKET_NAME",
            "RAILWAY_BUCKET_ACCESS_KEY_ID",
            "RAILWAY_BUCKET_SECRET_KEY",
        ]
        if not getattr(settings, name, "")
    ]
    if missing:
        raise StorageConfigurationError(
            f"Missing Railway bucket configuration: {', '.join(missing)}"
        )


def _asset_storage_key(upload, *, folder, kind):
    now = timezone.now()
    base_name = get_valid_filename(os.path.basename(upload.name or "upload"))
    stem, ext = os.path.splitext(base_name)
    stem = stem[:80] or kind
    return (
        f"{folder.strip('/')}/{now:%Y/%m}/"
        f"{uuid.uuid4().hex}-{stem}{ext.lower()}"
    )


def get_asset_url(asset):
    if not asset.storage_key:
        return asset.file_url
    try:
        return default_storage.url(asset.storage_key)
    except Exception:
        return asset.file_url


def upload_asset(upload, *, kind, folder="uploads", request=None, metadata=None):
    backend = _normalized_storage_backend()
    _validate_storage_configuration(backend)

    file_bytes = upload.read()
    checksum = hashlib.sha256(file_bytes).hexdigest()
    storage_key = default_storage.save(
        _asset_storage_key(upload, folder=folder, kind=kind),
        ContentFile(file_bytes),
    )
    file_url = default_storage.url(storage_key)

    asset = UploadedAsset.objects.create(
        kind=kind,
        file_url=file_url,
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
