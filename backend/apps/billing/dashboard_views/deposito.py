"""
Restituzione esplicita del deposito cauzionale.
"""
import datetime
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPropertyMember
from billing.models import Receivable, StatoPagamento
from properties.models import TenantProfile


def riga_restituzione(tenant: TenantProfile):
    """Il Receivable DEPOSITO negativo (restituzione) più recente, o None."""
    return (
        Receivable.objects.filter(
            assignment__tenant=tenant,
            causale=Receivable.Causale.DEPOSITO,
            importo_dovuto__lt=0,
        )
        .order_by("-competenza_da", "-id")
        .first()
    )


def versato_effettivo(tenant: TenantProfile) -> Decimal:
    """Quanto del deposito è entrato davvero: la somma dei pagamenti sulle
    righe DEPOSITO positive (rate comprese). ``deposito_versato`` in
    anagrafica è il **pattuito**, valorizzato subito dalla prima
    assegnazione anche se nessuna rata è ancora stata incassata."""
    return Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.DEPOSITO,
        importo_dovuto__gt=0,
    ).aggregate(s=Coalesce(Sum("importo_pagato"), Decimal("0")))["s"]


def importo_suggerito(tenant: TenantProfile) -> Decimal:
    """Lordo da rendere: override esplicito, altrimenti il deposito
    effettivamente incassato (mai il pattuito: non si rende ciò che non è
    mai entrato)."""
    override = tenant.deposito_da_restituire or Decimal("0")
    if override > 0:
        return override
    return versato_effettivo(tenant)


def crea_o_aggiorna_restituzione(tenant: TenantProfile, data_rest, importo: Decimal):
    """Crea (o aggiorna, se non ancora riconciliata) il Receivable DEPOSITO
    negativo di restituzione e allinea il profilo. Ritorna ``(riga, creato)``
    oppure ``(None, Response)`` con l'errore."""
    ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
    if ultimo is None:
        return None, Response(
            {"detail": "Nessuna assegnazione: impossibile generare la restituzione."},
            status=409,
        )
    importo = importo.quantize(Decimal("0.01"))
    riga = riga_restituzione(tenant)
    if riga is not None:
        # Guardia allocations: una riga già riconciliata con bonifici non
        # si tocca da qui (vedi invariante allocations).
        if riga.allocations.exists():
            return None, Response(
                {
                    "detail": (
                        "La restituzione è già riconciliata con dei bonifici: "
                        "modificala dalla riconciliazione, non da qui."
                    )
                },
                status=409,
            )
        riga.competenza_da = data_rest
        riga.scadenza = data_rest
        riga.importo_dovuto = -importo
        riga.save(update_fields=["competenza_da", "scadenza", "importo_dovuto"])
        creato = False
    else:
        riga = Receivable.objects.create(
            assignment=ultimo,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=data_rest,
            competenza_a=None,
            scadenza=data_rest,
            importo_dovuto=-importo,
            stato=StatoPagamento.ATTESO,
        )
        creato = True
    # Allinea il profilo. Il signal post_save vede che la riga negativa
    # esiste già e non interferisce (resta idempotente).
    tenant.data_restituzione_prevista = data_rest
    tenant.deposito_da_restituire = importo
    tenant.save(update_fields=["data_restituzione_prevista", "deposito_da_restituire"])
    return riga, creato


class RestituzioneDepositoView(APIView):
    """Gestione esplicita dell'addebito (negativo) di restituzione deposito.

    Sostituisce il trigger implicito ``data_restituzione_prevista`` con
    un'operazione comandata dal frontend, idempotente e *correggibile*: se la
    riga esiste già la aggiorna (data/importo), invece di lasciarla cristallizzata
    al primo salvataggio come fa il signal. Mantiene allineato anche il profilo.

    GET /api/v1/tenants/<tenant_id>/restituzione-deposito/
        → stato corrente + valori suggeriti (data = fine occupazione,
        importo lordo = override o deposito effettivamente incassato).
    POST /api/v1/tenants/<tenant_id>/restituzione-deposito/
        body: {data_restituzione, importo}
        → crea o aggiorna il Receivable DEPOSITO negativo.
    """

    permission_classes = [IsPropertyMember]

    def _riga_restituzione(self, tenant: TenantProfile):
        return riga_restituzione(tenant)

    def _importo_suggerito(self, tenant: TenantProfile) -> Decimal:
        return importo_suggerito(tenant)

    def get(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
        riga = self._riga_restituzione(tenant)
        return Response({
            "tenant_id": tenant.id,
            "esiste": riga is not None,
            "receivable_id": riga.id if riga else None,
            "data_corrente": riga.competenza_da.isoformat() if riga else None,
            "importo_corrente": float(-riga.importo_dovuto) if riga else None,
            "pagato": bool(riga and riga.stato == StatoPagamento.PAGATO),
            "ha_allocazioni": bool(riga and riga.allocations.exists()),
            "data_suggerita": (
                tenant.data_restituzione_prevista.isoformat()
                if tenant.data_restituzione_prevista
                else ultimo.valid_to.isoformat()
                if ultimo and ultimo.valid_to
                else None
            ),
            "importo_suggerito": float(self._importo_suggerito(tenant)),
        })

    def post(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        try:
            data_rest = datetime.date.fromisoformat(request.data["data_restituzione"])
            importo = Decimal(str(request.data["importo"]))
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Body malformato: servono data_restituzione, importo."},
                status=400,
            )
        if importo <= 0:
            return Response(
                {"detail": "L'importo da restituire deve essere positivo."},
                status=400,
            )

        riga, esito = crea_o_aggiorna_restituzione(tenant, data_rest, importo)
        if riga is None:
            return esito
        creato = esito
        importo = importo.quantize(Decimal("0.01"))

        return Response(
            {
                "receivable_id": riga.id,
                "creato": creato,
                "data_restituzione": data_rest.isoformat(),
                "importo": float(importo),
                "stato": riga.stato,
            },
            status=201 if creato else 200,
        )


class ChiusuraDepositoView(APIView):
    """Chiusura dell'inquilino: quanto rendere e con che cosa si compone.

    GET /api/v1/tenants/<tenant_id>/chiusura/
        → il netto da restituire scomposto nelle sue parti: la riga di
        restituzione del deposito (o, se non c'è ancora, il lordo suggerito
        come componente virtuale senza ``receivable_id``), ogni addebito
        aperto con il suo residuo (affitti, utenze, previsionale e relativa
        rettifica, extra) e i resti dei bonifici già ricevuti.
        ``netto = Σ effetti + resti``; ogni componente porta ``effetto`` =
        −residuo, cioè il suo contributo con il verso "denaro che il
        proprietario rende": la restituzione conta positiva, un addebito da
        trattenere negativo, una rettifica (dovuto negativo) positiva.
        ``bonifici``: i movimenti che hanno pagato la restituzione, ciascuno
        con le sue imputazioni (stesso verso) e il resto: è la memoria di
        come si componeva quel che si è reso.
    POST /api/v1/tenants/<tenant_id>/chiusura/
        body: {data, importo (>0, quanto bonificato all'inquilino),
               owner_account, descrizione?, note?}
        → se la riga di restituzione non esiste la crea (lordo suggerito,
        data del bonifico), poi registra il bonifico in uscita come una sola BankTransaction
        allocata a tutte le componenti: la partita compensata del caso
        [segni concordi]. Le componenti positive (trattenute) e le
        rettifiche si allocano per intero; la restituzione prende il resto
        così che la somma delle allocazioni sia esattamente la BT. Se il
        bonifico supera il netto, l'eccedenza resta sulla BT e compare nel
        saldo come debito dell'inquilino; se è inferiore, la restituzione
        resta parzialmente aperta.
    """

    permission_classes = [IsPropertyMember]

    _EPS = Decimal("0.005")

    def _tenant(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            return TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            ), None
        except TenantProfile.DoesNotExist:
            return None, Response({"detail": "Inquilino non trovato."}, status=404)

    def _componenti(self, tenant: TenantProfile):
        from ._common import TIPO_PER_CAUSALE, _descrizione_receivable
        from .rendiconto import _resti_per_anno

        restituzione = riga_restituzione(tenant)
        aperti = (
            Receivable.objects.filter(assignment__tenant=tenant)
            .exclude(causale=Receivable.Causale.DEPOSITO)
            .select_related("utility_period", "assignment__tenant")
            .order_by("competenza_da", "id")
        )
        righe = []
        componenti = []
        if restituzione is not None:
            if abs(
                restituzione.importo_dovuto - (restituzione.importo_pagato or Decimal("0"))
            ) >= self._EPS:
                righe.append(restituzione)
        else:
            suggerito = importo_suggerito(tenant).quantize(Decimal("0.01"))
            if suggerito > 0:
                componenti.append({
                    "receivable_id": None,
                    "tipo": "deposit",
                    "causale": Receivable.Causale.DEPOSITO,
                    "descrizione": "Deposito da rendere (addebito non ancora generato)",
                    "importo_dovuto": float(-suggerito),
                    "residuo": float(-suggerito),
                    "effetto": float(suggerito),
                    "stato": None,
                    "_residuo": -suggerito,
                    "_obj": None,
                })
        for r in aperti:
            residuo = r.importo_dovuto - (r.importo_pagato or Decimal("0"))
            if abs(residuo) >= self._EPS:
                righe.append(r)
        for r in righe:
            residuo = (r.importo_dovuto - (r.importo_pagato or Decimal("0"))).quantize(
                Decimal("0.01")
            )
            componenti.append({
                "receivable_id": r.id,
                "tipo": TIPO_PER_CAUSALE[r.causale],
                "causale": r.causale,
                "descrizione": _descrizione_receivable(r),
                "importo_dovuto": float(r.importo_dovuto),
                "residuo": float(residuo),
                "effetto": float(-residuo),
                "stato": r.stato,
                "_residuo": residuo,
                "_obj": r,
            })
        resti = sum(_resti_per_anno(tenant).values(), Decimal("0")).quantize(
            Decimal("0.01")
        )
        netto = sum((-c["_residuo"] for c in componenti), Decimal("0")) + resti
        return restituzione, componenti, resti, netto.quantize(Decimal("0.01"))

    def get(self, request, tenant_id: int):
        tenant, err = self._tenant(request, tenant_id)
        if err:
            return err
        restituzione, componenti, resti, netto = self._componenti(tenant)
        suggerito = importo_suggerito(tenant)
        pagata = bool(restituzione and restituzione.stato == StatoPagamento.PAGATO)
        ha_assegnazioni = tenant.assignments.exists()
        return Response({
            "bonifici": self._bonifici(restituzione),
            "tenant_id": tenant.id,
            "deposito_versato": float(tenant.deposito_versato or 0),
            "deposito_incassato": float(versato_effettivo(tenant)),
            "importo_restituzione": float(
                -restituzione.importo_dovuto if restituzione else suggerito
            ),
            "restituzione": (
                {
                    "receivable_id": restituzione.id,
                    "importo": float(restituzione.importo_dovuto),
                    "stato": restituzione.stato,
                    "data": restituzione.competenza_da.isoformat(),
                }
                if restituzione
                else None
            ),
            "componenti": [
                {k: v for k, v in c.items() if not k.startswith("_")}
                for c in componenti
            ],
            "resti_bonifici": float(resti),
            "netto": float(netto),
            # Il bonifico complessivo si registra finché la restituzione non
            # è saldata; se la riga manca, il POST la crea.
            "registrabile": bool(
                ha_assegnazioni
                and (
                    (restituzione is None and suggerito > 0)
                    or (
                        restituzione is not None
                        and not pagata
                        and abs(
                            restituzione.importo_dovuto
                            - (restituzione.importo_pagato or 0)
                        )
                        >= self._EPS
                    )
                )
            ),
        })

    def _bonifici(self, restituzione):
        """I movimenti che hanno pagato la restituzione, con tutte le loro
        imputazioni (anche su altri addebiti: è la partita compensata)."""
        from ._common import _descrizione_receivable
        from billing.models import BankTransaction

        if restituzione is None:
            return []
        bts = (
            BankTransaction.objects.filter(allocations__receivable=restituzione)
            .distinct()
            .prefetch_related(
                "allocations__receivable__utility_period",
                "allocations__receivable__assignment__tenant",
            )
            .order_by("data", "id")
        )
        out = []
        for bt in bts:
            allocazioni = []
            tot = Decimal("0")
            for a in bt.allocations.all().order_by("id"):
                tot += a.importo
                allocazioni.append({
                    "receivable_id": a.receivable_id,
                    "causale": a.receivable.causale,
                    "descrizione": _descrizione_receivable(a.receivable),
                    "importo": float(a.importo),
                    "effetto": float(-a.importo),
                })
            out.append({
                "bank_transaction_id": bt.id,
                "data": bt.data.isoformat(),
                "importo": float(bt.importo),
                "descrizione": bt.descrizione,
                "allocazioni": allocazioni,
                "resto": float(bt.importo - tot),
            })
        return out

    def post(self, request, tenant_id: int):
        from django.db import transaction

        from billing.models import BankTransaction, BankTransactionAllocation
        from billing.signals import _riallinea_receivable
        from billing.views._common import _valida_conto_incasso
        from properties.models import OwnerBankAccount

        tenant, err = self._tenant(request, tenant_id)
        if err:
            return err
        try:
            data = datetime.date.fromisoformat(str(request.data["data"]))
            importo = Decimal(str(request.data["importo"])).quantize(Decimal("0.01"))
            owner_account = OwnerBankAccount.objects.get(
                pk=int(request.data["owner_account"])
            )
        except (KeyError, TypeError, ValueError, ArithmeticError,
                OwnerBankAccount.DoesNotExist):
            return Response(
                {"detail": "Body malformato: servono data, importo, owner_account."},
                status=400,
            )
        if importo <= 0:
            return Response(
                {"detail": "L'importo bonificato deve essere positivo."},
                status=400,
            )
        errore = _valida_conto_incasso(owner_account, tenant.property)
        if errore:
            return errore

        if riga_restituzione(tenant) is None:
            lordo = importo_suggerito(tenant)
            if lordo <= 0:
                return Response(
                    {"detail": "Nessun deposito incassato: nulla da restituire."},
                    status=409,
                )
            riga, esito = crea_o_aggiorna_restituzione(tenant, data, lordo)
            if riga is None:
                return esito
        restituzione, componenti, _resti, netto = self._componenti(tenant)
        residuo_rest = restituzione.importo_dovuto - (
            restituzione.importo_pagato or Decimal("0")
        )
        if residuo_rest > -self._EPS:
            return Response(
                {"detail": "La restituzione del deposito risulta già saldata."},
                status=409,
            )
        altre = [c for c in componenti if c["receivable_id"] != restituzione.id]
        somma_altre = sum((c["_residuo"] for c in altre), Decimal("0"))
        # La BT è in uscita: −importo. La restituzione prende ciò che resta
        # dopo le altre componenti, così Σ allocazioni = BT.
        quota_rest = -importo - somma_altre
        if quota_rest > -self._EPS:
            return Response(
                {
                    "detail": (
                        "Il bonifico non copre nemmeno le trattenute "
                        f"({somma_altre:.2f} €): nulla da restituire."
                    )
                },
                status=409,
            )
        # Non allocare sulla restituzione più del suo residuo: l'eccedenza
        # resta sulla BT (debito dell'inquilino, visibile nel saldo).
        if quota_rest < residuo_rest:
            quota_rest = residuo_rest

        descrizione = (request.data.get("descrizione") or "").strip() or (
            f"Restituzione deposito — {tenant.nominativo}"
        )
        with transaction.atomic():
            bt = BankTransaction.objects.create(
                data=data,
                descrizione=descrizione[:300],
                importo=-importo,
                owner_account=owner_account,
                note=(request.data.get("note") or "")[:1000],
            )
            allocazioni = [(restituzione, quota_rest.quantize(Decimal("0.01")))]
            allocazioni += [(c["_obj"], c["_residuo"]) for c in altre]
            for rec, quota in allocazioni:
                BankTransactionAllocation.objects.create(
                    bank_transaction=bt, receivable=rec, importo=quota,
                )
            for rec, _q in allocazioni:
                _riallinea_receivable(rec.id)
        resto = -importo - sum((q for _r, q in allocazioni), Decimal("0"))
        return Response(
            {
                "bank_transaction_id": bt.id,
                "importo": float(-importo),
                "netto_atteso": float(netto),
                "resto": float(resto),
                "allocazioni": [
                    {"receivable_id": r.id, "importo": float(q)}
                    for r, q in allocazioni
                ],
            },
            status=201,
        )
