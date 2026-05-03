"""URL configuration per Viapal."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

api_v1_patterns = [
    path("", include("properties.api_urls")),
    path("", include("billing.api_urls")),
    path("", include("billing.dashboard_urls")),
    path("", include("accounting.api_urls")),
    path("", include("notifications.api_urls")),
]

urlpatterns = [
    path('admin_tools/', include('admin_tools.urls')),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/v1/', include(api_v1_patterns)),
    path('accounts/', include('allauth.urls')),
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
