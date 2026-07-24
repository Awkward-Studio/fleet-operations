from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("fleet.urls")),
    path("api/fleet/", include("fleet.urls")),
    path("api/", include("media_store.urls")),
    path("api/rentals/", include("rentals.urls")),
    path("api/billing/", include("billing.urls")),
    path("api/makemytrip/", include("makemytrip.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

