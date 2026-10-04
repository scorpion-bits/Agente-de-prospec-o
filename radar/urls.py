from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.views.generic import RedirectView


def healthz(request):
    """Health check do Cloud Run: sem banco e sem dados (o repositório é público)."""
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("healthz", healthz),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
]
