"""URL configuration per Viapal."""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]
