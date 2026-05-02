from django.middleware.csrf import get_token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token_view(request):
    """Endpoint che fa settare il cookie csrftoken al frontend prima del login."""
    return Response({'csrftoken': get_token(request)})
