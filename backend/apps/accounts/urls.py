from django.urls import include, path

from .views import csrf_token_view

urlpatterns = [
    path('csrf/', csrf_token_view, name='auth-csrf'),
    path('', include('dj_rest_auth.urls')),
]
