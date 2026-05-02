from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer dell'utente loggato. Espone il ruolo per il routing frontend."""
    role = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_staff', 'is_superuser', 'role')
        read_only_fields = ('id', 'is_staff', 'is_superuser', 'role')

    def get_role(self, user):
        groups = set(user.groups.values_list('name', flat=True))
        if 'proprietari' in groups:
            return 'proprietario'
        if 'inquilini' in groups:
            return 'inquilino'
        if user.is_superuser:
            return 'proprietario'
        return None
