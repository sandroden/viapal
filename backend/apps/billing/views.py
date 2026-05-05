"""
ViewSet per l'app billing.

I tre endpoint storici (rent-payments, utility-charges, extra-charges)
ora si appoggiano al modello unico Receivable filtrando per causale.
"""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsProprietario  # noqa: F401
from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    Receivable,
    StatoPagamento,
    UtilityBill,
    UtilityChargePeriod,
)
from billing.serializers import (
    BankTransactionSerializer,
    ExpenseSerializer,
    ExtraChargeSerializer,
    ReceivableForReconcileSerializer,
    RentPaymentSerializer,
    UtilityBillSerializer,
    UtilityChargePeriodSerializer,
    UtilityChargeSerializer,
)
from billing.signals import _riallinea_receivable


class BillingPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def _is_proprietario(user) -> bool:
    return user.is_superuser or user.groups.filter(name="proprietari").exists()


def _is_inquilino(user) -> bool:
    return user.groups.filter(name="inquilini").exists()


class _ReceivableMixin:
    """Comportamenti comuni dei tre ViewSet su Receivable.

    Le sottoclassi specificano `causale` e `serializer_class`.
    """

    causale: str
    pagination_class = BillingPagination

    def get_permissions(self):
        if self.action in ("dichiara_pagato", "conferma_pagato"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def _base_queryset(self):
        return Receivable.objects.filter(causale=self.causale).select_related(
            "assignment__tenant__user",
            "assignment__room",
            "incassato_da_owner",
            "bank_account_destinazione",
            "utility_period",
        )

    def get_queryset(self):
        qs = self._base_queryset().order_by("-scadenza")
        if _is_proprietario(self.request.user):
            return qs
        return qs.filter(assignment__tenant__user=self.request.user)

    @action(detail=True, methods=["post"], url_path="dichiara_pagato")
    def dichiara_pagato(self, request, pk=None):
        """Inquilino marca come dichiarato. Solo l'inquilino del receivable."""
        receivable = self.get_object()

        if not _is_proprietario(request.user):
            if receivable.assignment.tenant.user != request.user:
                return Response(
                    {"detail": "Puoi dichiarare solo i tuoi addebiti."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if receivable.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Addebito gia' confermato dai proprietari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receivable.stato = StatoPagamento.DICHIARATO
        receivable.data_pagamento = datetime.date.today()
        receivable.importo_pagato = receivable.importo_dovuto
        receivable.save(update_fields=["stato", "data_pagamento", "importo_pagato"])

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="conferma_pagato")
    def conferma_pagato(self, request, pk=None):
        """Proprietario conferma il pagamento dichiarato."""
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono confermare un pagamento."},
                status=status.HTTP_403_FORBIDDEN,
            )

        receivable = self.get_object()

        if receivable.stato not in (
            StatoPagamento.DICHIARATO,
            StatoPagamento.ATTESO,
            StatoPagamento.IN_RITARDO,
        ):
            return Response(
                {"detail": f"Impossibile confermare un addebito in stato '{receivable.stato}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receivable.stato = StatoPagamento.PAGATO
        if not receivable.importo_pagato:
            receivable.importo_pagato = receivable.importo_dovuto
        if not receivable.data_pagamento:
            receivable.data_pagamento = datetime.date.today()
        receivable.save(update_fields=["stato", "importo_pagato", "data_pagamento"])

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )


class RentPaymentViewSet(_ReceivableMixin, ModelViewSet):
    """Pagamenti affitto (Receivable causale=affitto)."""

    causale = Receivable.Causale.AFFITTO
    serializer_class = RentPaymentSerializer


class UtilityChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Utenze (Receivable causale=utenze)."""

    causale = Receivable.Causale.UTENZE
    serializer_class = UtilityChargeSerializer

    def _base_queryset(self):
        return super()._base_queryset().prefetch_related("utility_lines")

    def get_queryset(self):
        qs = self._base_queryset().order_by("-utility_period__periodo_da")
        if _is_proprietario(self.request.user):
            return qs
        return qs.filter(assignment__tenant__user=self.request.user)


class ExtraChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Addebiti extra (Receivable causale=extra)."""

    causale = Receivable.Causale.EXTRA
    serializer_class = ExtraChargeSerializer
    pagination_class = None  # comportamento legacy: lista plain


class UtilityChargePeriodViewSet(ReadOnlyModelViewSet):
    """Periodi utenze. Solo proprietari."""

    serializer_class = UtilityChargePeriodSerializer
    permission_classes = [IsProprietario]
    queryset = UtilityChargePeriod.objects.all().order_by("-periodo_da")


class UtilityBillViewSet(ReadOnlyModelViewSet):
    """Bollette utenze. Solo proprietari."""

    serializer_class = UtilityBillSerializer
    permission_classes = [IsProprietario]
    queryset = UtilityBill.objects.select_related("supplier", "pagata_da_owner").order_by(
        "-data_emissione"
    )


class ExpenseViewSet(ModelViewSet):
    """Spese immobile. Solo proprietari (full CRUD)."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsProprietario]
    queryset = Expense.objects.select_related(
        "category", "supplier", "anticipata_da_owner", "riferimento_quota_owner"
    ).order_by("-data")


class BankTransactionViewSet(ReadOnlyModelViewSet):
    """Transazioni bancarie. Solo proprietari.

    Querystring:
    - ``data_da``, ``data_a`` (YYYY-MM-DD) — finestra su ``data``.
    - ``riconciliato`` — ``true``/``false``/``all`` (default ``all``).
      Usa i manager ``riconciliate``/``non_riconciliate`` del QuerySet.
    - ``tenant`` (id) — solo BT con almeno un'allocation verso quell'inquilino
      **oppure** non riconciliate (candidate libere).
    - ``owner_account`` (id).
    """

    serializer_class = BankTransactionSerializer
    permission_classes = [IsProprietario]
    pagination_class = BillingPagination

    def get_queryset(self):
        qs = (
            BankTransaction.objects
            .select_related("owner_account")
            .prefetch_related(
                "allocations__receivable__assignment__tenant",
                "allocations__receivable__utility_period",
            )
            .order_by("-data")
        )

        params = self.request.query_params

        data_da = params.get("data_da")
        if data_da:
            qs = qs.filter(data__gte=data_da)
        data_a = params.get("data_a")
        if data_a:
            qs = qs.filter(data__lte=data_a)

        riconciliato = params.get("riconciliato", "all")
        if riconciliato == "true":
            qs = qs.filter(pk__in=BankTransaction.objects.riconciliate().values("pk"))
        elif riconciliato == "false":
            qs = qs.filter(pk__in=BankTransaction.objects.non_riconciliate().values("pk"))

        owner_account = params.get("owner_account")
        if owner_account:
            qs = qs.filter(owner_account_id=owner_account)

        tenant_id = params.get("tenant")
        if tenant_id:
            from properties.models import TenantProfile
            try:
                tenant = TenantProfile.objects.get(pk=tenant_id)
            except TenantProfile.DoesNotExist:
                return qs.none()
            descr_q = Q()
            # Token significativi del nominativo: il cognome basta a matchare
            # bonifici tipo "Bon. da Rossi", quindi cerchiamo ogni parola con
            # almeno 3 caratteri.
            for token in tenant.nominativo.split():
                if len(token) >= 3:
                    descr_q |= Q(descrizione__icontains=token)
            qs = qs.filter(
                Q(allocations__receivable__assignment__tenant_id=tenant_id)
                | descr_q
            ).distinct()

        return qs


class ReceivableViewSet(ReadOnlyModelViewSet):
    """Receivable in formato compatto per pagina riconciliazione.

    Querystring:
    - ``assignment`` (id), ``tenant`` (id),
    - ``causale`` (csv: ``affitto,utenze,extra``),
    - ``stato`` (csv: ``atteso,in_ritardo,...``),
    - ``riconciliato`` = ``true|false|all`` (default ``all``); confronta
      ``Sum(allocations.importo)`` con ``importo_dovuto``,
    - ``data_da``, ``data_a`` su ``scadenza``.
    """

    serializer_class = ReceivableForReconcileSerializer
    permission_classes = [IsProprietario]
    pagination_class = BillingPagination

    def get_queryset(self):
        from django.db.models import Prefetch
        qs = (
            Receivable.objects
            .select_related(
                "assignment__tenant",
                "assignment__room",
                "utility_period",
            )
            .prefetch_related(
                Prefetch(
                    "allocations",
                    queryset=BankTransactionAllocation.objects.select_related(
                        "bank_transaction"
                    ),
                )
            )
            .annotate(_alloc=Sum("allocations__importo"))
            .order_by("-scadenza", "-id")
        )

        params = self.request.query_params

        assignment = params.get("assignment")
        if assignment:
            qs = qs.filter(assignment_id=assignment)

        tenant = params.get("tenant")
        if tenant:
            qs = qs.filter(assignment__tenant_id=tenant)

        causale = params.get("causale")
        if causale:
            qs = qs.filter(causale__in=[c.strip() for c in causale.split(",") if c.strip()])

        stato = params.get("stato")
        if stato:
            qs = qs.filter(stato__in=[s.strip() for s in stato.split(",") if s.strip()])

        riconciliato = params.get("riconciliato", "all")
        if riconciliato == "true":
            qs = qs.filter(_alloc__gte=F("importo_dovuto"))
        elif riconciliato == "false":
            qs = qs.filter(
                Q(_alloc__isnull=True) | Q(_alloc__lt=F("importo_dovuto"))
            )

        data_da = params.get("data_da")
        if data_da:
            qs = qs.filter(scadenza__gte=data_da)
        data_a = params.get("data_a")
        if data_a:
            qs = qs.filter(scadenza__lte=data_a)

        return qs


class ReconciliationBulkView(APIView):
    """POST /api/v1/reconciliations/

    Body::

        {
          "replace_for_transactions": [12, 17],
          "items": [
            {"bank_transaction": 12, "receivable": 105, "importo": "300.00"},
            {"bank_transaction": 17, "receivable": 105, "importo": "100.00"}
          ]
        }

    Sostituisce in blocco le allocations delle BT elencate in
    ``replace_for_transactions`` con quelle in ``items``. Tutto in atomic.
    Le BT presenti in ``items`` ma assenti da ``replace_for_transactions``
    rendono la richiesta 400 (no allocation orfane). Riallinea i Receivable
    toccati (sia quelli vecchi che nuovi) chiamando esplicitamente la funzione
    ``_riallinea_receivable`` perché ``bulk_create`` non emette ``post_save``.
    """

    permission_classes = [IsProprietario]

    _TOLLERANZA = Decimal("0.01")

    def post(self, request):
        replace_for_transactions = request.data.get("replace_for_transactions") or []
        items = request.data.get("items") or []

        if not isinstance(replace_for_transactions, list) or not all(
            isinstance(x, int) for x in replace_for_transactions
        ):
            return Response(
                {"detail": "'replace_for_transactions' deve essere lista di id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(items, list):
            return Response(
                {"detail": "'items' deve essere lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        replace_set = set(replace_for_transactions)

        normalizzati = []
        somme_per_bt: dict[int, Decimal] = {}
        for raw in items:
            if not isinstance(raw, dict):
                return Response(
                    {"detail": "Ogni item deve essere un oggetto."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                bt_id = int(raw["bank_transaction"])
                rec_id = int(raw["receivable"])
                importo = Decimal(str(raw["importo"]))
            except (KeyError, TypeError, ValueError, ArithmeticError):
                return Response(
                    {"detail": "Item malformato: servono bank_transaction, receivable, importo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if bt_id not in replace_set:
                return Response(
                    {"detail": f"BT {bt_id} non in replace_for_transactions."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if importo <= 0:
                return Response(
                    {"detail": "Gli importi delle allocations devono essere > 0."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            normalizzati.append((bt_id, rec_id, importo))
            somme_per_bt[bt_id] = somme_per_bt.get(bt_id, Decimal("0")) + importo

        bts = {bt.id: bt for bt in BankTransaction.objects.filter(pk__in=replace_set)}
        for bt_id in replace_set:
            if bt_id not in bts:
                return Response(
                    {"detail": f"BankTransaction {bt_id} non trovata."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        for bt_id, somma in somme_per_bt.items():
            limite = bts[bt_id].importo
            if somma > limite + self._TOLLERANZA:
                return Response(
                    {
                        "detail": (
                            f"Somma allocata ({somma}) supera importo BT {bt_id} ({limite})."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        receivable_ids = {rec_id for _, rec_id, _ in normalizzati}
        if receivable_ids:
            esistenti = set(
                Receivable.objects.filter(pk__in=receivable_ids).values_list("pk", flat=True)
            )
            mancanti = receivable_ids - esistenti
            if mancanti:
                return Response(
                    {"detail": f"Receivable inesistenti: {sorted(mancanti)}."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Coppie duplicate (bt, receivable) nello stesso payload sono ambigue.
        coppie = [(bt_id, rec_id) for bt_id, rec_id, _ in normalizzati]
        if len(coppie) != len(set(coppie)):
            return Response(
                {"detail": "Coppie (bank_transaction, receivable) duplicate negli items."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            allocs_pre = BankTransactionAllocation.objects.filter(
                bank_transaction_id__in=replace_set
            )
            receivable_ids_pre = set(allocs_pre.values_list("receivable_id", flat=True))
            allocs_pre.delete()

            BankTransactionAllocation.objects.bulk_create([
                BankTransactionAllocation(
                    bank_transaction_id=bt_id,
                    receivable_id=rec_id,
                    importo=importo,
                )
                for bt_id, rec_id, importo in normalizzati
            ])

            tutti_receivable = receivable_ids_pre | receivable_ids
            for r_id in tutti_receivable:
                _riallinea_receivable(r_id)

        bt_qs = (
            BankTransaction.objects.filter(pk__in=replace_set)
            .select_related("owner_account")
            .prefetch_related(
                "allocations__receivable__assignment__tenant",
                "allocations__receivable__utility_period",
            )
        )
        bt_data = BankTransactionSerializer(bt_qs, many=True).data

        rec_qs = (
            Receivable.objects.filter(pk__in=tutti_receivable)
            .select_related("assignment__tenant", "utility_period")
            .annotate(_alloc=Sum("allocations__importo"))
        )
        rec_data = ReceivableForReconcileSerializer(rec_qs, many=True).data

        return Response(
            {"bank_transactions": bt_data, "receivables": rec_data},
            status=status.HTTP_200_OK,
        )
