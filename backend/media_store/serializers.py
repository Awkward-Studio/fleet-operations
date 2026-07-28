from rest_framework import serializers

from .models import UploadedAsset
from .storage import get_asset_url


class UploadedAssetSerializer(serializers.ModelSerializer):
    href = serializers.SerializerMethodField()

    class Meta:
        model = UploadedAsset
        fields = [
            "id",
            "kind",
            "original_name",
            "content_type",
            "checksum_sha256",
            "is_private",
            "created_at",
            "href",
        ]
        read_only_fields = fields

    def get_href(self, obj):
        request = self.context.get("request")
        url = get_asset_url(obj)
        if not url:
            return None
        return request.build_absolute_uri(url) if request else url
