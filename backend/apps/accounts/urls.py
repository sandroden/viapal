from django.urls import include, path

from .impersonation_views import impersonate_view, stop_impersonation_view
from .views import csrf_token_view

urlpatterns = [
    path('csrf/', csrf_token_view, name='auth-csrf'),
    path('impersonate/stop/', stop_impersonation_view,
         name='auth-impersonate-stop'),
    path('impersonate/<int:tenant_id>/', impersonate_view,
         name='auth-impersonate'),
    path('', include('dj_rest_auth.urls')),
]
