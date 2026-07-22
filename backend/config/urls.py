from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("fleet.urls")),
    path("api/", include("media_store.urls")),
    path("api/rentals/", include("rentals.urls")),
    path("api/makemytrip/", include("makemytrip.urls")),
]

