from django.core.files.uploadedfile import SimpleUploadedFile
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
        self.assertTrue(asset.storage_key.startswith("uploads/image/"))
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
