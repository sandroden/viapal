"""
Movimenti bancari: lista, riconciliazione e import.
"""
from decimal import Decimal

from accounts.permissions import (
    IsPropertyMember,
)
from django.db import transaction
from django.db.models import Q, Sum
from properties.context import get_request_property
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
)
from billing.serializers import (
    BankTransactionBulkImportInputSerializer,
    BankTransactionSerializer,
    ReceivableForReconcileSerializer,
)
from billing.signals import _riallinea_receivable

from ._common import BillingPagination


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
    permission_classes = [IsPropertyMember]
    pagination_class = BillingPagination

    def get_queryset(self):
        # I movimenti dei conti in uso su questo immobile. `BankTransaction`
        # non ha una FK a Property: il conto è l'unico aggancio, quindi
        # l'isolamento fra immobili poggia interamente sul collegamento.
        prop = get_request_property(self.request)
        qs = (
            BankTransaction.objects
            .filter(owner_account__properties=prop)
            .select_related("owner_account__owner")
            .prefetch_related(
                "allocations__receivable__assignment__tenant",
                "allocations__receivable__utility_period",
            )
            .order_by("-data")
            .distinct()
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
                tenant = TenantProfile.objects.get(pk=tenant_id, property=prop)
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

    permission_classes = [IsPropertyMember]

    _TOLLERANZA = Decimal("0.01")

    def post(self, request):
        prop = get_request_property(request)
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

        # Perimetro immobile: le BT devono stare su conti in uso
        # sull'immobile attivo e i Receivable appartenergli.
        if replace_set:
            bt_ok = set(
                BankTransaction.objects.filter(
                    pk__in=replace_set,
                    owner_account__properties=prop,
                ).values_list("pk", flat=True)
            )
            if bt_ok != replace_set:
                return Response(
                    {"detail": "Transazioni estranee a questo immobile."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        rec_ids = {
            int(raw["receivable"])
            for raw in items
            if isinstance(raw, dict) and str(raw.get("receivable", "")).isdigit()
        }
        if rec_ids:
            rec_ok = set(
                Receivable.objects.filter(
                    pk__in=rec_ids,
                    assignment__room__property=prop,
                ).values_list("pk", flat=True)
            )
            if rec_ok != rec_ids:
                return Response(
                    {"detail": "Addebiti estranei a questo immobile."},
                    status=status.HTTP_403_FORBIDDEN,
                )

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

    permission_classes = [IsPropertyMember]
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    PREFISSO_NOTA = "Precedente: "

    def post(self, request):
        serializer = BankTransactionBulkImportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.validated_data["owner_account"]
        # Il conto dev'essere il proprio (caso normale: si importa il proprio
        # estratto) oppure in uso su un immobile di cui si è membri.
        condiviso = (
            request.user.is_superuser
            or account.owner.user_id == request.user.pk
            or account.properties.filter(memberships__user=request.user).exists()
        )
        if not condiviso:
            return Response(
                {"detail": "Conto estraneo ai tuoi immobili."},
                status=status.HTTP_403_FORBIDDEN,
            )
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
