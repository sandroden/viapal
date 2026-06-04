from django.conf import settings
from django.contrib.auth import get_user_model
from dj_rest_auth.serializers import PasswordResetSerializer
from rest_framework import serializers


def spa_password_reset_url(request, user, temp_key):
    """Genera il link di reset/invito puntando alla **SPA** invece che al
    dominio Django.

    ``AllAuthPasswordResetForm.save()`` (usato da dj-rest-auth quando allauth è
    installato) accetta un ``url_generator`` opzionale con questa firma. L'uid è
    codificato con l'helper di allauth (``user_pk_to_url_str`` → base36 per PK
    interi), coerente con quanto si aspetta ``PasswordResetConfirmSerializer``.
    La pagina ``/imposta-password/<uid>/<token>`` della SPA posta poi a
    ``/api/auth/password/reset/confirm/``.
    """
    from allauth.account.utils import user_pk_to_url_str

    uid = user_pk_to_url_str(user)
    base = (settings.APP_BASE_URL or '').rstrip('/')
    return f"{base}/imposta-password/{uid}/{temp_key}"


class UserSerializer(serializers.ModelSerializer):
    """Serializer dell'utente loggato. Espone il ruolo per il routing frontend
    e — per i proprietari — l'`owner_profile_id` e i conti bancari attivi, in
    modo che il frontend possa pre-compilare il conto destinatario quando
    l'utente registra un pagamento o una spesa."""
    role = serializers.SerializerMethodField()
    owner_profile_id = serializers.SerializerMethodField()
    bank_accounts = serializers.SerializerMethodField()
    is_impersonated = serializers.SerializerMethodField()
    impersonator_username = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'is_staff', 'is_superuser', 'role',
                  'owner_profile_id', 'bank_accounts',
                  'is_impersonated', 'impersonator_username')
        read_only_fields = ('id', 'is_staff', 'is_superuser', 'role',
                            'owner_profile_id', 'bank_accounts',
                            'is_impersonated', 'impersonator_username')

    def get_is_impersonated(self, user):
        """True se la sessione corrente sta impersonando (django-hijack)."""
        request = self.context.get('request')
        return bool(getattr(getattr(request, 'user', None), 'is_hijacked', False))

    def get_impersonator_username(self, user):
        """Username del proprietario che sta impersonando, se attivo."""
        request = self.context.get('request')
        if not request or not getattr(request.user, 'is_hijacked', False):
            return None
        history = request.session.get('hijack_history', [])
        if not history:
            return None
        try:
            orig = get_user_model().objects.get(pk=history[-1])
        except get_user_model().DoesNotExist:
            return None
        return orig.username

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


class SpaPasswordResetSerializer(PasswordResetSerializer):
    """Serializer di reset password che fa puntare il link alla SPA.

    Registrato in ``REST_AUTH['PASSWORD_RESET_SERIALIZER']``. Sovrascrive solo
    ``get_email_options`` per iniettare ``url_generator``; testo/oggetto
    dell'email restano quelli di allauth (template
    ``account/email/password_reset_key_*``), che stampano ``password_reset_url``.
    """

    def get_email_options(self):
        return {'url_generator': spa_password_reset_url}
