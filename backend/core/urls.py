"""URL configuration per Viapal."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

# Header admin con l'ambiente: in produzione resta pulito, altrove segnala
# a chiare lettere dove si sta operando.
if settings.ENVIRONMENT == 'production':
    _admin_label = 'Viapal'
else:
    _admin_label = f'Viapal — {settings.ENVIRONMENT.upper()}'
admin.site.site_header = _admin_label
admin.site.site_title = _admin_label  # finisce nel <title> del tab
admin.site.index_title = 'Amministrazione'

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
