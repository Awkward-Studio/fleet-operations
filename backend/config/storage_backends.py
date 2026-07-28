from django.conf import settings
from storages.backends.s3 import S3Storage


class RailwayBucketStorage(S3Storage):
    bucket_name = settings.RAILWAY_BUCKET_NAME
    access_key = settings.RAILWAY_BUCKET_ACCESS_KEY_ID
    secret_key = settings.RAILWAY_BUCKET_SECRET_KEY
    endpoint_url = settings.RAILWAY_BUCKET_ENDPOINT_URL
    region_name = settings.RAILWAY_BUCKET_REGION
    addressing_style = "path"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
