"""
Rendiconto dell'inquilino e sbilancio reale (resti dei bonifici).
"""
import datetime
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing._dates import format_mese_anno
from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    StatoPagamento,
)
from properties.models import RoomAssignment, TenantProfile

# ---------------------------------------------------------------------------
# Rendiconto deposito (storico completo da consegnare all'uscita)
# ---------------------------------------------------------------------------

def _nota_riga(dovuto: Decimal, pagato: Decimal) -> str:
    """Codice nota automatica per una riga del rendiconto."""
    if dovuto <= 0:
        return "ok"
    if pagato <= 0:
        return "non_pagata"
    if pagato < dovuto:
        return "parziale"
    if pagato > dovuto:
        return "eccesso"
    return "ok"


def _descr_rendiconto(r: Receivable):
    """(descrizione, data) coerenti per riga di rendiconto e imputazione."""
    p = r.utility_period
    if r.causale == Receivable.Causale.UTENZE and p:
        return (
            f"Utenze {p.periodo_da.isoformat()} → {p.periodo_a.isoformat()}",
            p.periodo_da,
        )
    if r.causale == Receivable.Causale.AFFITTO:
        return (
            r.descrizione or f"Affitto {format_mese_anno(r.competenza_da)}",
            r.competenza_da,
        )
    return (r.descrizione or r.get_causale_display(), r.competenza_da)


def _resti_per_anno(tenant) -> dict[int, Decimal]:
    """Resti dei bonifici dell'inquilino, per anno (data del bonifico).

    Un bonifico è "dell'inquilino" se ha almeno un'allocazione su un suo
    Receivable non-DEPOSITO. Il *resto* è ``importo bonifico − somma di
    TUTTE le sue allocazioni`` (incluse quote finite su altre causali o
    sul deposito): è denaro versato e mai imputato a nulla.

    La sola differenza ``imputato − dovuto`` per riga perde questi resti
    (un bonifico che copre *di più* alloca solo fino al dovuto e
    l'eccedenza non diventa mai un saldo positivo). Vanno riaggiunti per
    ottenere lo sbilancio reale ``versato − dovuto``.
    """
    bt_ids = list(
        BankTransactionAllocation.objects.filter(
            receivable__assignment__tenant=tenant
        )
        .exclude(receivable__causale=Receivable.Causale.DEPOSITO)
        .values_list("bank_transaction_id", flat=True)
        .distinct()
    )
    if not bt_ids:
        return {}
    tot_alloc = dict(
        BankTransactionAllocation.objects.filter(
            bank_transaction_id__in=bt_ids
        )
        .values_list("bank_transaction_id")
        .annotate(t=Coalesce(Sum("importo"), Decimal("0")))
        .values_list("bank_transaction_id", "t")
    )
    resti: dict[int, Decimal] = {}
    for bt in BankTransaction.objects.filter(id__in=bt_ids).only(
        "id", "data", "importo"
    ):
        resto = bt.importo - tot_alloc.get(bt.id, Decimal("0"))
        if resto:
            resti[bt.data.year] = resti.get(bt.data.year, Decimal("0")) + resto
    return resti


def _sbilancio_progressivo(
    dovuto_pagato: dict[int, list], resti: dict[int, Decimal]
):
    """Sbilancio reale per anno + progressivo cronologico.

    ``dovuto_pagato`` = {anno: [dovuto, pagato_imputato]} per i Receivable
    non-DEPOSITO; ``resti`` = output di :func:`_resti_per_anno`.

    Ritorna ``(per_anno, totale)``:

    * ``per_anno`` lista ordinata di dict con ``anno, dovuto, pagato,
      saldo`` (= pagato−dovuto, saldo-imputazioni, nota tecnica),
      ``resto``, ``saldo_anno`` (= saldo + resto, sbilancio reale
      dell'anno) e ``saldo_progressivo`` (cumulato cronologico, "fino a
      fine quell'anno" — non conosce il futuro).
    * ``totale`` dict con ``dovuto, pagato, resto, saldo`` e
      ``sbilancio_reale`` (= ultimo progressivo = Σversato − Σdovuto, al
      netto di quote imputate fuori scope come il deposito).
    """
    anni = sorted(set(dovuto_pagato) | set(resti))
    per_anno = []
    tot_d = tot_p = tot_r = Decimal("0")
    prog = Decimal("0")
    for anno in anni:
        d, p = dovuto_pagato.get(anno, [Decimal("0"), Decimal("0")])
        r = resti.get(anno, Decimal("0"))
        saldo = p - d
        saldo_anno = saldo + r
        prog += saldo_anno
        tot_d += d
        tot_p += p
        tot_r += r
        per_anno.append({
            "anno": anno,
            "dovuto": float(d),
            "pagato": float(p),
            "saldo": float(saldo),
            "resto": float(r),
            "saldo_anno": float(saldo_anno),
            "saldo_progressivo": float(prog),
        })
    totale = {
        "dovuto": float(tot_d),
        "pagato": float(tot_p),
        "resto": float(tot_r),
        "saldo": float(tot_p - tot_d),
        "sbilancio_reale": float(tot_p - tot_d + tot_r),
    }
    return per_anno, totale


class RendicontoView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/rendiconto/

    Storico completo (tutti gli anni) dei Receivable non-DEPOSITO
    dell'inquilino, raggruppati per causale, con differenze per riga,
    imputazioni dei bonifici (ledger), parziali per anno e chiusura del
    deposito. Pensato per essere consegnato alla restituzione.
    Accessibile ai proprietari (qualunque inquilino) e all'inquilino
    stesso (solo il proprio profilo).
    """

    permission_classes = [IsAuthenticated]

    _SEZIONI = (
        (Receivable.Causale.AFFITTO, "Affitti"),
        (Receivable.Causale.UTENZE, "Utenze"),
        (Receivable.Causale.EXTRA, "Addebiti extra"),
        (Receivable.Causale.REGISTRAZIONE, "Registrazione contratto"),
    )

    def get(self, request, tenant_id: int):
        oggi = datetime.date.today()
        try:
            tenant = TenantProfile.objects.select_related("user").get(pk=tenant_id)
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        user = request.user
        is_gestione = user.is_superuser or user.property_memberships.filter(
            property_id=tenant.property_id
        ).exists()
        if not is_gestione and tenant.user_id != user.id:
            return Response(
                {"detail": "Puoi accedere solo ai tuoi dati."}, status=403
            )

        assignments = list(
            RoomAssignment.objects.filter(tenant=tenant).order_by("valid_from")
        )
        periodo_da = assignments[0].valid_from.isoformat() if assignments else None
        if assignments and all(a.valid_to for a in assignments):
            periodo_a = max(a.valid_to for a in assignments).isoformat()
        else:
            periodo_a = None  # rapporto ancora in corso

        # Tutte le allocazioni bonifico→addebito dell'inquilino, in un'unica
        # query. Servono sia per le note di copertura sulle righe sia per il
        # ledger "Versamenti e imputazioni". Il ledger include anche le quote
        # sul DEPOSITO (il bonifico c'è stato davvero); righe, saldi e resti
        # restano invece sul solo perimetro non-DEPOSITO.
        allocs_tutte = list(
            BankTransactionAllocation.objects.filter(
                receivable__assignment__tenant=tenant
            )
            .select_related(
                "bank_transaction",
                "receivable",
                "receivable__utility_period",
            )
            .order_by("bank_transaction__data", "bank_transaction_id", "id")
        )
        allocs = [
            a for a in allocs_tutte
            if a.receivable.causale != Receivable.Causale.DEPOSITO
        ]
        alloc_per_receivable: dict[int, list] = {}
        for a in allocs:
            alloc_per_receivable.setdefault(a.receivable_id, []).append(a)

        # Resto di ogni bonifico = importo − Σ TUTTE le sue allocazioni
        # (anche su altre causali/inquilini/deposito): denaro versato e
        # mai imputato. Lo attribuiamo alla riga "portante" del bonifico
        # (quella con l'allocazione più grande fra i Receivable mostrati)
        # così la differenza resta tracciabile sulla riga invece di
        # comparire come totale misterioso a fine anno.
        bt_lordo: dict[int, Decimal] = {}
        bt_quota_max: dict[int, tuple] = {}  # bt_id -> (importo, receivable_id)
        for a in allocs:
            bt_lordo[a.bank_transaction_id] = a.bank_transaction.importo
            cur = bt_quota_max.get(a.bank_transaction_id)
            if cur is None or a.importo > cur[0]:
                bt_quota_max[a.bank_transaction_id] = (a.importo, a.receivable_id)
        bt_total_alloc = (
            dict(
                BankTransactionAllocation.objects.filter(
                    bank_transaction_id__in=list(bt_lordo)
                )
                .values_list("bank_transaction_id")
                .annotate(t=Coalesce(Sum("importo"), Decimal("0")))
                .values_list("bank_transaction_id", "t")
            )
            if bt_lordo
            else {}
        )
        # resto per bonifico (mostrato come riga propria sotto il bonifico
        # portante) e aggregato per riga portante (per i totali d'anno).
        resto_bt: dict[int, Decimal] = {}
        carrier_bt: dict[int, int] = {}
        resto_riga: dict[int, Decimal] = {}
        for bt_id, lordo in bt_lordo.items():
            resto = lordo - bt_total_alloc.get(bt_id, Decimal("0"))
            if not resto:
                continue
            carrier = bt_quota_max[bt_id][1]
            resto_bt[bt_id] = resto
            carrier_bt[bt_id] = carrier
            resto_riga[carrier] = resto_riga.get(carrier, Decimal("0")) + resto

        # parziali per anno (senza deposito): anno della "data" della riga
        parziali: dict[int, list[Decimal]] = {}
        # resti per anno, attribuiti all'anno della riga portante (così la
        # colonna Differenza mostrata somma esattamente al Saldo dell'anno)
        resti_anno: dict[int, Decimal] = {}

        sezioni = []
        tot_dovuto = Decimal("0")
        tot_pagato = Decimal("0")
        for causale, label in self._SEZIONI:
            qs = (
                Receivable.objects.filter(
                    assignment__tenant=tenant, causale=causale
                )
                .select_related("utility_period")
                .order_by("competenza_da", "id")
            )
            righe = []
            # meta[i] = (mese 'YYYY-MM', dovuto, {bt_id: bt_importo}) per la
            # diff mensile degli affitti (gestisce 2 righe nello stesso mese
            # per cambio stanza a metà mese).
            meta: list[tuple] = []
            sez_dovuto = Decimal("0")
            sez_pagato = Decimal("0")
            for r in qs:
                dovuto = r.importo_dovuto
                pagato = r.importo_pagato or Decimal("0")
                descr, data = _descr_rendiconto(r)
                righe_alloc = alloc_per_receivable.get(r.id, [])
                allocazioni = [
                    {
                        "data": a.bank_transaction.data.isoformat(),
                        "bonifico_totale": float(a.bank_transaction.importo),
                        "quota": float(a.importo),
                        # bonifico "split": ha coperto più del solo importo
                        # imputato a questa riga (eccedenza andata altrove).
                        "split": a.bank_transaction.importo != a.importo,
                        # resto del bonifico (denaro versato e mai imputato):
                        # valorizzato solo sulla riga portante, mostrato
                        # come riga propria sotto il bonifico.
                        "resto": float(
                            resto_bt[a.bank_transaction_id]
                            if carrier_bt.get(a.bank_transaction_id) == r.id
                            else 0
                        ),
                    }
                    for a in righe_alloc
                ]
                resto_r = resto_riga.get(r.id, Decimal("0"))
                mese = f"{data.year:04d}-{data.month:02d}" if data else None
                righe.append({
                    "data": data.isoformat() if data else None,
                    "mese": mese,
                    "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                    "descrizione": descr,
                    "dovuto": float(dovuto),
                    "pagato": float(pagato),
                    # Differenza ONESTA della voce: solo pagato − dovuto.
                    # Il resto dei bonifici è una riga propria (vedi
                    # allocazioni[].resto), non inquina la voce.
                    "diff": float(pagato - dovuto),
                    # Valorizzata solo per gli affitti, solo sull'ultima riga
                    "diff_mese": None,
                    "nota": _nota_riga(dovuto, pagato),
                    "stato": r.stato,
                    "data_pagamento": r.data_pagamento.isoformat()
                    if r.data_pagamento else None,
                    "allocazioni": allocazioni,
                })
                meta.append((
                    mese,
                    dovuto,
                    {
                        a.bank_transaction_id: a.bank_transaction.importo
                        for a in righe_alloc
                    },
                ))
                sez_dovuto += dovuto
                sez_pagato += pagato
                if data:
                    acc = parziali.setdefault(
                        data.year, [Decimal("0"), Decimal("0")]
                    )
                    acc[0] += dovuto
                    acc[1] += pagato
                    if resto_r:
                        resti_anno[data.year] = (
                            resti_anno.get(data.year, Decimal("0")) + resto_r
                        )
            if not righe:
                continue
            if causale == Receivable.Causale.AFFITTO:
                # Diff per mese di competenza: somma dei bonifici (distinti)
                # che hanno pagato l'affitto del mese, meno l'affitto dovuto
                # del mese. L'eventuale eccedenza è il sovra-versato che è
                # andato a coprire le utenze. Mostrata sull'ultima riga del
                # mese; le altre righe del mese restano senza diff.
                ultimo_idx_per_mese: dict[str, int] = {}
                dovuto_per_mese: dict[str, Decimal] = {}
                bt_per_mese: dict[str, dict] = {}
                for idx, (mese, dovuto, bts) in enumerate(meta):
                    if mese is None:
                        continue
                    ultimo_idx_per_mese[mese] = idx
                    dovuto_per_mese.setdefault(mese, Decimal("0"))
                    dovuto_per_mese[mese] += dovuto
                    bt_per_mese.setdefault(mese, {}).update(bts)
                for mese, idx in ultimo_idx_per_mese.items():
                    versato_lordo = sum(
                        bt_per_mese[mese].values(), Decimal("0")
                    )
                    righe[idx]["diff_mese"] = float(
                        versato_lordo - dovuto_per_mese[mese]
                    )
            sezioni.append({
                "causale": causale,
                "label": label,
                "righe": righe,
                "dovuto": float(sez_dovuto),
                "pagato": float(sez_pagato),
                "saldo": float(sez_pagato - sez_dovuto),
            })
            tot_dovuto += sez_dovuto
            tot_pagato += sez_pagato

        saldo = tot_pagato - tot_dovuto

        # Sbilancio reale = saldo-imputazioni + resti dei bonifici (denaro
        # versato e mai imputato a nulla). È il numero che dice davvero
        # "chi deve a chi"; il saldo-imputazioni resta come nota tecnica
        # ("quanto c'è ancora da riconciliare").
        parziali_anno, sbil_tot = _sbilancio_progressivo(parziali, resti_anno)
        sbilancio_reale = Decimal(str(sbil_tot["sbilancio_reale"]))

        # --- Ledger: versamenti (bonifici) e loro imputazioni ---
        versamenti_map: dict[int, dict] = {}
        for a in allocs_tutte:
            bt = a.bank_transaction
            v = versamenti_map.get(bt.id)
            if v is None:
                v = {
                    "data": bt.data.isoformat(),
                    "descrizione": (bt.descrizione or "").strip()[:120],
                    "importo": float(bt.importo),
                    "imputato": Decimal("0"),
                    "imputazioni": [],
                }
                versamenti_map[bt.id] = v
            descr_r, _ = _descr_rendiconto(a.receivable)
            v["imputazioni"].append({
                "descrizione": descr_r,
                "causale": a.receivable.causale,
                "quota": float(a.importo),
            })
            v["imputato"] += a.importo
        versamenti = []
        tot_versato = Decimal("0")
        for v in sorted(versamenti_map.values(), key=lambda x: x["data"]):
            imputato = v.pop("imputato")
            v["imputato"] = float(imputato)
            tot_versato += imputato
            versamenti.append(v)

        # --- Chiusura deposito ---
        from .deposito import importo_suggerito

        versato = tenant.deposito_versato or Decimal("0")
        override = tenant.deposito_da_restituire or Decimal("0")
        # Lordo da rendere: override esplicito, altrimenti l'incassato
        # effettivo (mai il pattuito).
        da_restituire = importo_suggerito(tenant)

        dep_qs = list(
            Receivable.objects.filter(
                assignment__tenant=tenant, causale=Receivable.Causale.DEPOSITO
            ).order_by("competenza_da", "id")
        )
        riga_restituzione = next(
            (r for r in dep_qs if r.importo_dovuto < 0), None
        )
        # Quanto del deposito è stato DAVVERO versato finora (rate pagate):
        # con il deposito a rate `deposito_versato` in anagrafica è il totale
        # pattuito, non quello incassato.
        versato_effettivo = sum(
            (r.importo_pagato or Decimal("0"))
            for r in dep_qs
            if r.importo_dovuto > 0
        )
        restituito_effettivo = bool(
            riga_restituzione
            and riga_restituzione.stato == StatoPagamento.PAGATO
        )
        netto = (
            Decimal("0")
            if restituito_effettivo
            else (da_restituire + sbilancio_reale)
        )
        residuo_debito = -netto if (not restituito_effettivo and netto < 0) else Decimal("0")

        deposito_movimenti = [
            {
                "data": r.competenza_da.isoformat() if r.competenza_da else None,
                "descrizione": r.descrizione or r.get_causale_display(),
                "importo": float(r.importo_dovuto),
                "pagato": float(r.importo_pagato or 0),
                "stato": r.stato,
                "data_pagamento": r.data_pagamento.isoformat()
                if r.data_pagamento else None,
            }
            for r in dep_qs
        ]

        return Response({
            "tenant": {
                "id": tenant.id,
                "nominativo": tenant.nominativo,
                "codice_fiscale": tenant.codice_fiscale or None,
                "email": (tenant.user.email or None) if tenant.user_id else None,
            },
            "periodo": {"da": periodo_da, "a": periodo_a},
            "emesso_il": oggi.isoformat(),
            "sezioni": sezioni,
            "totali": {
                "dovuto": float(tot_dovuto),
                "pagato": float(tot_pagato),
                "saldo": float(saldo),
                "resto": sbil_tot["resto"],
                "sbilancio_reale": sbil_tot["sbilancio_reale"],
            },
            "parziali_anno": parziali_anno,
            "versamenti": versamenti,
            "totale_versato": float(tot_versato),
            "deposito": {
                "versato": float(versato),
                "versato_effettivo": float(versato_effettivo),
                "data_versamento": tenant.data_versamento_deposito.isoformat()
                if tenant.data_versamento_deposito else None,
                "da_restituire": float(da_restituire),
                "override": override > 0,
                "data_restituzione_prevista":
                    tenant.data_restituzione_prevista.isoformat()
                    if tenant.data_restituzione_prevista else None,
                "restituito_effettivo": restituito_effettivo,
                "netto_da_restituire": float(max(netto, Decimal("0"))),
                "residuo_debito": float(residuo_debito),
                "movimenti": deposito_movimenti,
            },
        })
