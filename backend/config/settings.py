import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

SECRET_KEY = "dev-only-change-me"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "media_store",
    "fleet",
    "accounts",
    "makemytrip",
    "rentals",
    "billing",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Server-side odometer safeguards. Client OCR confidence is never authoritative.
ODOMETER_MAX_START_DELTA_KM = int(os.getenv("ODOMETER_MAX_START_DELTA_KM", "500"))
ODOMETER_MAX_TRIP_DELTA_KM = int(os.getenv("ODOMETER_MAX_TRIP_DELTA_KM", "1000"))

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
RAILWAY_BUCKET_ENDPOINT_URL = (
    os.getenv("RAILWAY_BUCKET_ENDPOINT_URL")
    or os.getenv("RAILWAY_BUCKET_ENPOINT_URL")
    or ""
).strip()
RAILWAY_BUCKET_REGION = os.getenv("RAILWAY_BUCKET_REGION", "auto").strip() or "auto"
RAILWAY_BUCKET_NAME = os.getenv("RAILWAY_BUCKET_NAME", "").strip()
RAILWAY_BUCKET_ACCESS_KEY_ID = os.getenv("RAILWAY_BUCKET_ACCESS_KEY_ID", "").strip()
RAILWAY_BUCKET_SECRET_KEY = os.getenv("RAILWAY_BUCKET_SECRET_KEY", "").strip()
RAILWAY_BUCKET_CUSTOM_DOMAIN = os.getenv("RAILWAY_BUCKET_CUSTOM_DOMAIN", "").strip()
_configured_media_backend = os.getenv("MEDIA_STORAGE_BACKEND")
MEDIA_STORAGE_BACKEND = (
    _configured_media_backend.strip()
    if _configured_media_backend
    else (
        "railway"
        if "test" not in sys.argv
        and all(
            [
                RAILWAY_BUCKET_ENDPOINT_URL,
                RAILWAY_BUCKET_NAME,
                RAILWAY_BUCKET_ACCESS_KEY_ID,
                RAILWAY_BUCKET_SECRET_KEY,
            ]
        )
        else "local"
    )
)

if MEDIA_STORAGE_BACKEND.lower() in {"railway", "railway_bucket", "s3"}:
    STORAGES = {
        "default": {
            "BACKEND": "config.storage_backends.RailwayBucketStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    AWS_ACCESS_KEY_ID = RAILWAY_BUCKET_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = RAILWAY_BUCKET_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = RAILWAY_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = RAILWAY_BUCKET_ENDPOINT_URL
    AWS_S3_REGION_NAME = RAILWAY_BUCKET_REGION
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "private, max-age=0, no-cache",
    }
    if RAILWAY_BUCKET_CUSTOM_DOMAIN:
        AWS_S3_CUSTOM_DOMAIN = RAILWAY_BUCKET_CUSTOM_DOMAIN
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# MakeMyTrip (Incabs) API Settings
MAKEMYTRIP_MOCK_SERVER_URL = "https://private-7902fd-incabsapipartnerdocumentationv3.apiary-mock.com/tracking/pp2"
MAKEMYTRIP_HEADERS = {}

