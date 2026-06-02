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
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsProprietario  # noqa: F401
from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    ExpenseCategory,
    Receivable,
    StatoPagamento,
    UtilityBill,
    UtilityChargePeriod,
)
from billing.serializers import (
    BankTransactionBulkImportInputSerializer,
    BankTransactionSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    ExtraChargeSerializer,
    ReceivableForReconcileSerializer,
    RegistraPagamentoInputSerializer,
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
        return super()._base_queryset().select_related("utility_period")

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
    """Periodi utenze. Solo proprietari.

    Oltre a lista/dettaglio espone il flusso di **emissione utenze**:

    - ``GET  per-mese?anno=&mese=`` : trova-o-crea il periodo del mese e ne
      riporta la completezza (luce/gas/tari presenti).
    - ``GET  {id}/anteprima``       : dry-run della ripartizione (conto per
      inquilino), nessuna scrittura.
    - ``POST {id}/emetti``          : persiste i Receivable utenze e porta il
      periodo a stato 'inviato'.
    """

    serializer_class = UtilityChargePeriodSerializer
    permission_classes = [IsProprietario]
    queryset = UtilityChargePeriod.objects.all().order_by("-periodo_da")

    def _completezza(self, period) -> dict:
        """Quali voci sono presenti per il periodo (hint rapido pre-calcolo).

        ``completo`` = c'è almeno una bolletta luce e una gas che si
        sovrappongono al periodo: solo allora il conteggio ha senso (la TARI è
        un costo fisso che si ribalta da sé).
        """
        from billing.models import AnnualUtilityCost

        bills = UtilityBill.objects.filter(
            periodo_da__lte=period.periodo_a,
            periodo_a__gte=period.periodo_da,
        )
        has_luce = bills.filter(prodotto=UtilityBill.Prodotto.LUCE).exists()
        has_gas = bills.filter(prodotto=UtilityBill.Prodotto.GAS).exists()
        has_tari = (
            AnnualUtilityCost.objects.filter(
                voce=AnnualUtilityCost.VoceAnnuale.TARI,
                valid_from__lte=period.periodo_a,
            )
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=period.periodo_da))
            .exists()
        )
        return {
            "luce": has_luce,
            "gas": has_gas,
            "tari": has_tari,
            "completo": has_luce and has_gas,
        }

    def _mese_default(self) -> tuple[int, int]:
        """Mese di partenza proposto, ragionando sugli **avvisi**.

        Si guarda l'ultimo periodo con addebiti utenze emessi:

        - se gli avvisi non sono ancora stati inviati (``avvisi_inviati_at``
          nullo), si atterra su **quel** mese: c'è ancora lavoro da fare lì;
        - altrimenti si propone il mese successivo (nuovo periodo da avviare).

        Se non esiste alcun Receivable utenze, fallback al mese corrente.
        """
        ultimo = (
            Receivable.objects.filter(
                causale=Receivable.Causale.UTENZE,
                utility_period__isnull=False,
            )
            .select_related("utility_period")
            .order_by("-utility_period__periodo_a")
            .first()
        )
        if ultimo is None:
            oggi = datetime.date.today()
            return oggi.year, oggi.month

        period = ultimo.utility_period
        if period.avvisi_inviati_at is None:
            # Addebito emesso ma avvisi non ancora inviati: si parte da qui.
            return period.periodo_da.year, period.periodo_da.month

        # Avvisi già inviati: si propone il mese successivo.
        base = period.periodo_a
        anno = base.year + (1 if base.month == 12 else 0)
        mese = 1 if base.month == 12 else base.month + 1
        return anno, mese

    @action(detail=False, methods=["get"], url_path="per-mese")
    def per_mese(self, request):
        """Trova o crea il periodo utenze del mese.

        ``anno`` e ``mese`` sono opzionali: se omessi, si usa il mese
        successivo all'ultimo periodo con addebiti utenze emessi.
        """
        import calendar

        ha_anno = "anno" in request.query_params
        ha_mese = "mese" in request.query_params
        if not ha_anno and not ha_mese:
            anno, mese = self._mese_default()
        else:
            try:
                anno = int(request.query_params["anno"])
                mese = int(request.query_params["mese"])
            except (KeyError, ValueError, TypeError):
                return Response(
                    {"detail": "Parametri 'anno' e 'mese' obbligatori (interi)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not (1 <= mese <= 12):
            return Response(
                {"detail": "Mese fuori range (1-12)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        primo = datetime.date(anno, mese, 1)
        ultimo = datetime.date(anno, mese, calendar.monthrange(anno, mese)[1])

        # periodo esistente che copre (anche parzialmente) il mese richiesto:
        # evita di creare doppioni su periodi bimestrali già presenti.
        period = (
            UtilityChargePeriod.objects.filter(
                periodo_da__lte=ultimo, periodo_a__gte=primo
            )
            .order_by("periodo_da")
            .first()
        )
        created = False
        if period is None:
            period = UtilityChargePeriod.objects.create(
                periodo_da=primo, periodo_a=ultimo
            )
            created = True

        return Response(
            {
                "period": self.get_serializer(period).data,
                "created": created,
                "completezza": self._completezza(period),
                "anno": anno,
                "mese": mese,
            }
        )

    @action(detail=True, methods=["get"], url_path="anteprima")
    def anteprima(self, request, pk=None):
        """Dry-run della ripartizione: conto per inquilino, nessuna scrittura."""
        from billing.calc.utility import calcola_conguaglio_periodo

        period = self.get_object()
        risultato = calcola_conguaglio_periodo(period.id, persist=False)
        risultato["completezza"] = self._completezza(period)
        return Response(risultato)

    @action(detail=True, methods=["post"], url_path="emetti")
    def emetti(self, request, pk=None):
        """Persiste i Receivable utenze e porta il periodo a 'inviato'."""
        from billing.calc.utility import calcola_conguaglio_periodo

        period = self.get_object()
        comp = self._completezza(period)
        if not comp["completo"]:
            return Response(
                {
                    "detail": "Periodo incompleto: servono almeno una bolletta "
                    "luce e una gas prima di emettere.",
                    "completezza": comp,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        risultato = calcola_conguaglio_periodo(period.id, persist=True)

        period.refresh_from_db()
        if period.stato != UtilityChargePeriod.StatoPeriodo.INVIATO:
            period.stato = UtilityChargePeriod.StatoPeriodo.INVIATO
            if not period.data_invio:
                period.data_invio = datetime.date.today()
            period.save(update_fields=["stato", "data_invio"])

        risultato["period"] = self.get_serializer(period).data
        return Response(risultato)

    @action(detail=True, methods=["post"], url_path="invia-avvisi")
    def invia_avvisi(self, request, pk=None):
        """Invia (o simula con ``dry_run``) gli avvisi utenze agli inquilini.

        Body JSON: ``{"dry_run": true|false}`` (default ``true``).
        Con ``dry_run`` mostra il testo esatto delle email senza inviare nulla,
        così lo si approva prima dell'invio reale.
        """
        from billing.calc.avvisi import invia_avvisi_utenze

        period = self.get_object()
        dry_run = bool(request.data.get("dry_run", True))
        escludi = request.data.get("escludi") or []
        risultato = invia_avvisi_utenze(period, dry_run=dry_run, escludi_ids=escludi)
        return Response(risultato)


class UtilityBillViewSet(ModelViewSet):
    """Bollette utenze. Solo proprietari.

    Upload (POST) richiede solo ``file_pdf`` + ``pagata_da_owner``: tutti
    gli altri campi (prodotto, importo, periodo, data emissione, consumo,
    fornitore) vengono estratti dal PDF (template Acea/Enel/Wind3
    riconosciuti). Idempotente per ``numero_fattura`` (= basename del file).

    Per gli script CLI accetta anche autenticazione HTTP Basic in aggiunta
    alla session.
    """

    serializer_class = UtilityBillSerializer
    permission_classes = [IsProprietario]
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = UtilityBill.objects.select_related("supplier", "pagata_da_owner").order_by(
        "-data_emissione"
    )

    def create(self, request, *args, **kwargs):
        import os
        import tempfile

        from billing.management.commands.riparsa_bollette_pdf import estrai_da_pdf
        from billing.models import Supplier

        file_pdf = request.FILES.get("file_pdf")
        if not file_pdf:
            return Response({"file_pdf": "richiesto"}, status=400)

        pagata_da_owner_id = (
            request.data.get("pagata_da_owner") or request.data.get("pagata_da_owner_id")
        )
        if not pagata_da_owner_id:
            return Response({"pagata_da_owner": "richiesto"}, status=400)

        numero_fattura = (
            request.data.get("numero_fattura")
            or os.path.splitext(os.path.basename(file_pdf.name))[0]
        )

        existing = UtilityBill.objects.filter(numero_fattura=numero_fattura).first()
        if existing:
            return Response(
                {
                    "detail": "Bolletta già presente.",
                    "id": existing.id,
                    "numero_fattura": existing.numero_fattura,
                },
                status=409,
            )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for chunk in file_pdf.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            dati = estrai_da_pdf(tmp_path)
        finally:
            os.unlink(tmp_path)

        if not dati or dati.get("importo") is None:
            return Response(
                {"detail": "Template PDF non riconosciuto: importo non estraibile."},
                status=400,
            )
        if not dati.get("periodo_da") or not dati.get("periodo_a"):
            return Response(
                {"detail": "Template PDF non riconosciuto: periodo non estraibile."},
                status=400,
            )
        prodotto = dati.get("prodotto") or request.data.get("prodotto")
        if not prodotto:
            return Response(
                {"detail": "Prodotto non identificabile dal PDF (passare 'prodotto' nel form)."},
                status=400,
            )

        nome_forn = dati.get("fornitore") or request.data.get("supplier_nome") or "Sconosciuto"
        supplier = Supplier.objects.filter(nome__iexact=nome_forn).first()
        if not supplier:
            supplier = Supplier.objects.create(
                nome=nome_forn, tipo=Supplier.TipoFornitore.ALTRO,
            )

        file_pdf.seek(0)
        bill = UtilityBill.objects.create(
            supplier=supplier,
            prodotto=prodotto,
            numero_fattura=numero_fattura,
            data_emissione=dati.get("data_emissione") or dati["periodo_a"],
            periodo_da=dati["periodo_da"],
            periodo_a=dati["periodo_a"],
            importo_totale=dati["importo"],
            consumo=dati.get("consumo"),
            pagata_da_owner_id=pagata_da_owner_id,
            file_pdf=file_pdf,
        )
        serializer = self.get_serializer(bill)
        return Response(serializer.data, status=201)


class ExpenseCategoryViewSet(ReadOnlyModelViewSet):
    """Categorie di spesa. Read-only via API: si gestiscono dall'admin Django."""

    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsProprietario]
    queryset = ExpenseCategory.objects.all().order_by("nome")
    pagination_class = None


class ExpenseViewSet(ModelViewSet):
    """Spese immobile. Solo proprietari (full CRUD).

    In creazione accetta i campi extra ``crea_bank_transaction``,
    ``bt_owner_account``, ``bt_data``, ``bt_descrizione`` (vedi
    ``ExpenseSerializer``) per registrare contestualmente il movimento bancario
    in uscita corrispondente. La BT non ha legame strutturale con la Expense;
    l'allineamento è implicito (stessa data e importo opposto)."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsProprietario]
    queryset = Expense.objects.select_related(
        "category", "supplier", "anticipata_da_owner",
        "riferimento_quota_owner", "utility_bill",
    ).order_by("-data")

    def perform_create(self, serializer):
        from properties.models import OwnerBankAccount
        validated = serializer.validated_data
        crea_bt = validated.pop("crea_bank_transaction", True)
        bt_owner_account_id = validated.pop("bt_owner_account", None)
        bt_data = validated.pop("bt_data", None)
        bt_descrizione = validated.pop("bt_descrizione", "") or ""

        # Se l'anticipante non è esplicito ma c'è un conto BT, derivalo da lì:
        # il conto appartiene a un proprietario e la spesa è "anticipata" da lui.
        account = None
        if crea_bt and bt_owner_account_id:
            account = OwnerBankAccount.objects.get(pk=bt_owner_account_id)
            if validated.get("anticipata_da_owner") is None:
                validated["anticipata_da_owner"] = account.owner

        with transaction.atomic():
            expense = serializer.save()
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
            .select_related("owner_account__owner")
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
        # Segno-aware: per Receivable positivi "riconciliato" significa
        # alloc>=importo_dovuto; per Receivable negativi (restituzione
        # caparra) significa alloc<=importo_dovuto (entrambi negativi).
        if riconciliato == "true":
            qs = qs.filter(
                Q(importo_dovuto__gt=0, _alloc__gte=F("importo_dovuto"))
                | Q(importo_dovuto__lt=0, _alloc__lte=F("importo_dovuto"))
                | Q(importo_dovuto=0)
            )
        elif riconciliato == "false":
            qs = qs.filter(
                Q(_alloc__isnull=True)
                | Q(importo_dovuto__gt=0, _alloc__lt=F("importo_dovuto"))
                | Q(importo_dovuto__lt=0, _alloc__gt=F("importo_dovuto"))
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
            if importo == 0:
                return Response(
                    {"detail": "Gli importi delle allocations devono essere ≠ 0."},
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

        # Invariante segno-aware (rilassata): l'unica regola assoluta è
        # ``sign(allocation.importo) == sign(receivable.importo_dovuto)``.
        # Il segno della BT può differire da quello delle singole allocations
        # (es. restituzione caparra con trattenuta per utenze previsionali:
        # BT -984 ↔ alloc -1060 sul Rec restituzione + alloc +76 sul Rec
        # previsionale utenze; somma algebrica -984 = BT.importo).
        receivables_map = {
            r.pk: r for r in Receivable.objects.filter(
                pk__in={rec_id for _, rec_id, _ in normalizzati}
            )
        }
        for bt_id, rec_id, importo in normalizzati:
            rec = receivables_map.get(rec_id)
            if rec is None:
                continue  # gestito sotto come "Receivable inesistente"
            if rec.importo_dovuto != 0 and (
                (importo > 0) != (rec.importo_dovuto > 0)
            ):
                return Response(
                    {
                        "detail": (
                            f"Segno discorde alloc/Receivable (Receivable {rec_id} "
                            f"dovuto {rec.importo_dovuto}, alloc {importo})."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for bt_id, somma in somme_per_bt.items():
            limite = bts[bt_id].importo
            # La somma algebrica delle allocations deve (a) andare nello
            # stesso verso della BT (entrata o uscita) e (b) non eccedere
            # |BT.importo|. Una somma di segno opposto alla BT non ha senso.
            if limite != 0 and somma != 0 and (somma > 0) != (limite > 0):
                return Response(
                    {
                        "detail": (
                            f"Somma allocazioni ({somma}) di segno opposto alla "
                            f"BT {bt_id} ({limite})."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if abs(somma) > abs(limite) + self._TOLLERANZA:
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
            mancanti = receivable_ids - set(receivables_map.keys())
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
            .select_related("owner_account__owner")
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


class RegistraPagamentoReceivableView(APIView):
    """POST /api/v1/receivables/<pk>/registra-pagamento/

    Inserimento veloce di un pagamento ricevuto dal proprietario senza passare
    dall'admin: data + importo + conto. Crea atomicamente:

    1. ``BankTransaction`` in entrata sul conto indicato;
    2. ``BankTransactionAllocation`` che lega BT al Receivable.

    Se l'importo è maggiore del residuo del Receivable, alloca solo il residuo
    e lascia la differenza sulla BT (visibile come "parziale" in
    riconciliazione). Se è minore, alloca tutto: il Receivable resta atteso.
    """

    permission_classes = [IsProprietario]

    def post(self, request, pk):
        try:
            receivable = Receivable.objects.get(pk=pk)
        except Receivable.DoesNotExist:
            return Response(
                {"detail": "Receivable non trovato."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if receivable.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Receivable già pagato."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = RegistraPagamentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        allocato_attuale = (
            receivable.allocations.aggregate(tot=Sum("importo"))["tot"] or Decimal("0")
        )
        residuo = receivable.importo_dovuto - allocato_attuale
        # Invariante: BT/allocation/Receivable hanno tutti lo stesso segno.
        # Receivable > 0 → residuo > 0, importo > 0 (entrata).
        # Receivable < 0 (restituzione deposito) → residuo < 0, importo < 0 (uscita).
        if residuo == 0:
            return Response(
                {"detail": "Receivable già completamente allocato."},
                status=status.HTTP_409_CONFLICT,
            )
        if (residuo > 0) != (v["importo"] > 0):
            atteso = "positivo" if residuo > 0 else "negativo"
            return Response(
                {"detail": f"L'importo deve essere {atteso} (coerente col dovuto)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # |quota| = min(|importo|, |residuo|), preservando il segno del residuo.
        quota = v["importo"] if abs(v["importo"]) <= abs(residuo) else residuo

        with transaction.atomic():
            bt = BankTransaction.objects.create(
                data=v["data"],
                descrizione=v["descrizione"] or "",
                importo=v["importo"],
                owner_account=v["owner_account"],
                note=v.get("note", "") or "",
            )
            BankTransactionAllocation.objects.create(
                bank_transaction=bt,
                receivable=receivable,
                importo=quota,
            )
            _riallinea_receivable(receivable.id)

        bt_qs = (
            BankTransaction.objects.filter(pk=bt.pk)
            .select_related("owner_account__owner")
            .prefetch_related(
                "allocations__receivable__assignment__tenant",
                "allocations__receivable__utility_period",
            )
        )
        bt_data = BankTransactionSerializer(bt_qs.first()).data

        rec_qs = (
            Receivable.objects.filter(pk=receivable.pk)
            .select_related("assignment__tenant", "utility_period")
            .annotate(_alloc=Sum("allocations__importo"))
        )
        rec_data = ReceivableForReconcileSerializer(rec_qs.first()).data

        return Response(
            {"bank_transaction": bt_data, "receivable": rec_data},
            status=status.HTTP_201_CREATED,
        )


class BankTransactionBulkImportView(APIView):
    """POST /api/v1/bank-transactions/bulk-import/

    Caricamento **idempotente** di righe di estratto conto.

    Chiave naturale: ``(owner_account, data, importo)``. Per ogni chiave le
    righe in arrivo vengono appaiate *in ordine* con le ``BankTransaction``
    già presenti sul conto:

    - riga senza corrispondente nel DB        → **creata**;
    - corrispondente con stessa descrizione    → **invariata** (idempotente);
    - corrispondente con descrizione diversa   → la descrizione della banca
      diventa quella ufficiale; la precedente (es. inserita a mano dal
      proprietario col dettaglio scritto dall'inquilino) viene preservata in
      ``note`` come riga ``Precedente: …`` → **aggiornata**;
    - ``BankTransaction`` in più rispetto alle righe in arrivo → lasciate
      intatte (mai cancellate) → conteggiate come ``extra_db``.

    Rilanciare lo stesso file non crea duplicati e non ri-accoda le note
    (la riga ``Precedente: …`` viene aggiunta una sola volta).

    Auth: ``IsProprietario`` (i superuser passano). ``BasicAuthentication`` è
    abilitata di proposito così lo script client può usare HTTP Basic senza
    gestire il CSRF della sessione.
    """

    permission_classes = [IsProprietario]
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    PREFISSO_NOTA = "Precedente: "

    def post(self, request):
        serializer = BankTransactionBulkImportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.validated_data["owner_account"]
        dry_run = serializer.validated_data["dry_run"]
        movimenti = serializer.validated_data["movimenti"]

        from collections import defaultdict

        # Righe in arrivo raggruppate per (data, importo), ordine preservato.
        per_chiave: dict = defaultdict(list)
        for m in movimenti:
            per_chiave[(m["data"], m["importo"])].append(m["descrizione"] or "")

        # BT esistenti sul conto per quelle date/importi, in ordine di id.
        date = {d for (d, _i) in per_chiave}
        importi = {i for (_d, i) in per_chiave}
        esistenti: dict = defaultdict(list)
        qs = (
            BankTransaction.objects.filter(
                owner_account=account, data__in=date, importo__in=importi
            ).order_by("id")
        )
        for bt in qs:
            k = (bt.data, bt.importo)
            if k in per_chiave:
                esistenti[k].append(bt)

        creati = aggiornati = invariati = extra_db = 0
        dettaglio: list = []

        with transaction.atomic():
            for (data_k, importo_k), descrizioni in per_chiave.items():
                bt_list = esistenti.get((data_k, importo_k), [])
                for idx, nuova_descr in enumerate(descrizioni):
                    if idx < len(bt_list):
                        bt = bt_list[idx]
                        if bt.descrizione == nuova_descr:
                            invariati += 1
                            continue
                        vecchia = (bt.descrizione or "").strip()
                        riga_nota = f"{self.PREFISSO_NOTA}{vecchia}"
                        if vecchia and riga_nota not in (bt.note or ""):
                            bt.note = (
                                f"{bt.note}\n{riga_nota}".strip()
                                if bt.note
                                else riga_nota
                            )
                        bt.descrizione = nuova_descr
                        bt.save()
                        aggiornati += 1
                        dettaglio.append(
                            {
                                "azione": "aggiornato",
                                "id": bt.id,
                                "data": str(data_k),
                                "importo": str(importo_k),
                                "descrizione_prima": vecchia,
                                "descrizione_dopo": nuova_descr,
                            }
                        )
                    else:
                        bt = BankTransaction(
                            data=data_k,
                            importo=importo_k,
                            descrizione=nuova_descr,
                            owner_account=account,
                            note="",
                        )
                        bt.save()
                        creati += 1
                        dettaglio.append(
                            {
                                "azione": "creato",
                                "id": bt.id,
                                "data": str(data_k),
                                "importo": str(importo_k),
                                "descrizione_dopo": nuova_descr,
                            }
                        )
                if len(bt_list) > len(descrizioni):
                    extra_db += len(bt_list) - len(descrizioni)

            if dry_run:
                transaction.set_rollback(True)

        return Response(
            {
                "owner_account": account.id,
                "dry_run": dry_run,
                "totale_input": len(movimenti),
                "creati": creati,
                "aggiornati": aggiornati,
                "invariati": invariati,
                "extra_db": extra_db,
                "dettaglio": dettaglio,
            },
            status=status.HTTP_200_OK,
        )
