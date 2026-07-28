from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from media_store.models import UploadedAsset, UploadedAssetAccessAudit


class MediaStoreUploadTests(APITestCase):
    def test_image_upload_uses_local_storage_and_records_audit(self):
        response = self.client.post(
            "/api/uploads/images/",
            {
                "file": SimpleUploadedFile(
                    "proof.jpg",
                    b"proof-image",
                    content_type="image/jpeg",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        asset = UploadedAsset.objects.get(id=response.data["id"])
        self.assertEqual(asset.kind, UploadedAsset.KIND_IMAGE)
        self.assertRegex(
            asset.storage_key,
            r"^uploads/image/\d{4}/\d{2}/[0-9a-f]{32}-proof\.jpg$",
        )
        self.assertTrue(asset.file_url.startswith("/media/uploads/image/"))
        self.assertEqual(len(asset.checksum_sha256), 64)
        self.assertTrue(asset.is_private)
        self.assertEqual(asset.metadata["storage_backend"], "local")
        self.assertEqual(
            UploadedAssetAccessAudit.objects.filter(
                asset=asset,
                action=UploadedAssetAccessAudit.ACTION_CREATED,
            ).count(),
            1,
        )

    @override_settings(
        MEDIA_STORAGE_BACKEND="railway",
        RAILWAY_BUCKET_ENDPOINT_URL="",
        RAILWAY_BUCKET_NAME="bucket",
        RAILWAY_BUCKET_ACCESS_KEY_ID="access",
        RAILWAY_BUCKET_SECRET_KEY="secret",
    )
    def test_railway_storage_requires_endpoint_configuration(self):
        response = self.client.post(
            "/api/uploads/images/",
            {
                "file": SimpleUploadedFile(
                    "proof.jpg",
                    b"proof-image",
                    content_type="image/jpeg",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 500)
        self.assertIn("RAILWAY_BUCKET_ENDPOINT_URL", response.data["error"])
