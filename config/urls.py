from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from providers.views import get_server_ip
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "app": "Afghan Top Backend"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("get-ip/", get_server_ip), #for the server ip address accessing
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/shopkeepers/", include("apps.shopkeepers.urls")),
    path("api/v1/topup/", include("apps.topup.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/settlements/", include("apps.settlements.urls")),
    path("api/v1/admin/", include("apps.adminpanel.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
