from django.contrib import admin
from django.urls import path, include, re_path
from image.views import redirect_by_slug
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("image.urls")),
    # QR 단축 URL 리다이렉트: /s/<slug>
    re_path(r"^s/(?P<slug>[-a-zA-Z0-9_]+)/?$", redirect_by_slug, name="qr_redirect"),


    # OpenAPI 스키마(JSON)
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # Swagger UI
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
