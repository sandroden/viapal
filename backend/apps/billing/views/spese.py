"""
ViewSet su spese, categorie, fornitori e quote condominio.
"""

from accounts.permissions import (
    IsPropertyMember,
)
from django.db import transaction
from django.db.models import Q
from properties.context import get_request_property
from properties.views import ProtectedDestroyMixin, _valida_owner_membro
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from billing.models import (
    BankTransaction,
    Expense,
    ExpenseCategory,
    Supplier,
    TenantCondominioRate,
)
from billing.serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    SupplierSerializer,
    TenantCondominioRateSerializer,
)


class ExpenseCategoryViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Categorie di spesa dell'immobile attivo (CRUD per i membri operativi;
    la property è assegnata dal server)."""

    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsPropertyMember]
    queryset = ExpenseCategory.objects.all().order_by("nome")
    pagination_class = None
    protected_detail = (
        "Impossibile eliminare la categoria: ha spese collegate."
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_codice_univoco(self, serializer):
        """Anticipa il vincolo unique (property, codice) con un 400 chiaro."""
        from rest_framework.exceptions import ValidationError

        codice = serializer.validated_data.get("codice")
        if codice is None:
            return
        qs = ExpenseCategory.objects.filter(
            property=get_request_property(self.request), codice=codice
        )
        if serializer.instance is not None:
            qs = qs.exclude(pk=serializer.instance.pk)
        if qs.exists():
            raise ValidationError(
                {"codice": "Esiste già una categoria con questo codice."}
            )

    def perform_create(self, serializer):
        self._valida_codice_univoco(serializer)
        serializer.save(property=get_request_property(self.request))

    def perform_update(self, serializer):
        self._valida_codice_univoco(serializer)
        serializer.save()


class SupplierViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Fornitori dell'immobile attivo (CRUD per i membri operativi; la
    property è assegnata dal server)."""

    serializer_class = SupplierSerializer
    permission_classes = [IsPropertyMember]
    queryset = Supplier.objects.all().order_by("nome")
    pagination_class = None
    protected_detail = (
        "Impossibile eliminare il fornitore: ha spese o bollette collegate."
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))


class TenantCondominioRateViewSet(ModelViewSet):
    """Quote di spese condominiali a carico degli inquilini dell'immobile
    attivo: la base dell'immobile (``tenant`` vuoto) e le eccezioni per
    singolo inquilino. CRUD per i membri operativi; la property è assegnata
    dal server.

    Filtro opzionale ``?tenant=<id>``: la base più le eccezioni di
    quell'inquilino, cioè le righe che concorrono al suo canone.
    """

    serializer_class = TenantCondominioRateSerializer
    permission_classes = [IsPropertyMember]
    queryset = TenantCondominioRate.objects.select_related("tenant").order_by(
        "-valid_from"
    )
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset().filter(
            property=get_request_property(self.request)
        )
        tenant = self.request.query_params.get("tenant")
        if tenant:
            qs = qs.filter(Q(tenant__isnull=True) | Q(tenant_id=tenant))
        return qs

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))


class ExpenseViewSet(ModelViewSet):
    """Spese immobile. Solo proprietari (full CRUD).

    In creazione accetta i campi extra ``crea_bank_transaction``,
    ``bt_owner_account``, ``bt_data``, ``bt_descrizione`` (vedi
    ``ExpenseSerializer``) per registrare contestualmente il movimento bancario
    in uscita corrispondente. La BT non ha legame strutturale con la Expense;
    l'allineamento è implicito (stessa data e importo opposto)."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsPropertyMember]
    queryset = Expense.objects.select_related(
        "category", "supplier", "anticipata_da_owner",
        "riferimento_quota_owner", "utility_bill",
    ).order_by("-data")

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_appartenenza_property(self, validated, prop):
        """``anticipata_da_owner``/``riferimento_quota_owner`` devono essere
        membri dell'immobile attivo; ``category``/``supplier`` devono
        appartenere alla stessa property: sono FK a queryset globale."""
        _valida_owner_membro(
            validated.get("anticipata_da_owner"), prop, "anticipata_da_owner"
        )
        _valida_owner_membro(
            validated.get("riferimento_quota_owner"), prop, "riferimento_quota_owner"
        )
        category = validated.get("category")
        if category is not None and category.property_id != prop.id:
            raise ValidationError(
                {"category": "La categoria non appartiene all'immobile attivo."}
            )
        supplier = validated.get("supplier")
        if supplier is not None and supplier.property_id != prop.id:
            raise ValidationError(
                {"supplier": "Il fornitore non appartiene all'immobile attivo."}
            )

    def perform_create(self, serializer):
        from properties.models import OwnerBankAccount
        prop = get_request_property(self.request)
        validated = serializer.validated_data
        crea_bt = validated.pop("crea_bank_transaction", True)
        bt_owner_account_id = validated.pop("bt_owner_account", None)
        bt_data = validated.pop("bt_data", None)
        bt_descrizione = validated.pop("bt_descrizione", "") or ""

        self._valida_appartenenza_property(validated, prop)

        # Se l'anticipante non è esplicito ma c'è un conto BT, derivalo da lì:
        # il conto appartiene a un proprietario e la spesa è "anticipata" da lui.
        account = None
        if crea_bt and bt_owner_account_id:
            from rest_framework.exceptions import PermissionDenied

            # Il conto di una spesa è quello di chi ha anticipato il denaro,
            # non quello su cui l'immobile incassa: oltre ai conti in uso qui
            # si accetta un conto del richiedente. Senza questa eccezione un
            # gestore non potrebbe registrare una spesa pagata di tasca sua.
            account = OwnerBankAccount.objects.filter(
                Q(properties=prop) | Q(owner__user=self.request.user),
                pk=bt_owner_account_id,
            ).distinct().first()
            if account is None:
                raise PermissionDenied(
                    "Conto non in uso su questo immobile né tuo."
                )
            if validated.get("anticipata_da_owner") is None:
                validated["anticipata_da_owner"] = account.owner

        with transaction.atomic():
            expense = serializer.save(property=prop)
            if crea_bt and account is not None:
                BankTransaction.objects.create(
                    data=bt_data or expense.data,
                    descrizione=bt_descrizione or (
                        expense.descrizione or
                        (expense.category.nome if expense.category else "Spesa")
                    ),
                    importo=-expense.importo,
                    owner_account=account,
                    note="",
                )

    def perform_update(self, serializer):
        prop = get_request_property(self.request)
        validated = serializer.validated_data
        # I campi write-only della BT contestuale valgono solo in creazione:
        # tolti prima del save, così non finiscono in setattr sull'istanza.
        for campo in ("crea_bank_transaction", "bt_owner_account", "bt_data", "bt_descrizione"):
            validated.pop(campo, None)
        self._valida_appartenenza_property(validated, prop)
        serializer.save()
