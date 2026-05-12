from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer dell'utente loggato. Espone il ruolo per il routing frontend
    e — per i proprietari — l'`owner_profile_id` e i conti bancari attivi, in
    modo che il frontend possa pre-compilare il conto destinatario quando
    l'utente registra un pagamento o una spesa."""
    role = serializers.SerializerMethodField()
    owner_profile_id = serializers.SerializerMethodField()
    bank_accounts = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_staff', 'is_superuser', 'role',
                  'owner_profile_id', 'bank_accounts')
        read_only_fields = ('id', 'is_staff', 'is_superuser', 'role',
                            'owner_profile_id', 'bank_accounts')

    def get_role(self, user):
        groups = set(user.groups.values_list('name', flat=True))
        if 'proprietari' in groups:
            return 'proprietario'
        if 'inquilini' in groups:
            return 'inquilino'
        if user.is_superuser:
            return 'proprietario'
        return None

    def _owner_profile(self, user):
        from properties.models import OwnerProfile
        return OwnerProfile.objects.filter(user=user).first()

    def get_owner_profile_id(self, user):
        op = self._owner_profile(user)
        return op.id if op else None

    def get_bank_accounts(self, user):
        op = self._owner_profile(user)
        if not op:
            return []
        return [
            {
                "id": acct.id,
                "banca": acct.banca,
                "intestatario": acct.intestatario,
                "iban": acct.iban,
                "owner_id": acct.owner_id,
            }
            for acct in op.bank_accounts.filter(attivo=True).order_by(
                "ordinamento", "banca"
            )
        ]
