"""
Generazione mensile RentPayment e gestione aggiustamenti pro-rata.

Convenzione pro-rata: giorni effettivi del mese di calendario (luglio=31, febbraio=28).
Scadenza legale: giorno_pagamento + 5 giorni (stessa convenzione per tutti).
"""
import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q


def _ultimo_del_mese(anno: int, mese: int) -> date:
    """Ritorna l'ultimo giorno del mese."""
    return date(anno, mese, calendar.monthrange(anno, mese)[1])


def _giorni_mese(anno: int, mese: int) -> int:
    """Ritorna il numero di giorni del mese (28-31)."""
    return calendar.monthrange(anno, mese)[1]


def _arrotonda(valore: Decimal) -> Decimal:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _anniversary_periodo(
    anno: int, mese: int, anniversary_day: int
) -> tuple[date, date]:
    """Per il ciclo 'ingresso': ritorna (competenza_da, mensilita_completa_a)
    della mensilità che inizia nel mese (anno, mese) con il giorno
    `anniversary_day`.

    Esempio: anniversary_day=9, anno=2025, mese=2 → (9/2/2025, 8/3/2025).

    Edge case mesi corti: se anniversary_day non esiste nel mese (es. 31 in
    febbraio), si usa l'ultimo giorno del mese.
    """
    n_giorni = _giorni_mese(anno, mese)
    giorno_inizio = min(anniversary_day, n_giorni)
    competenza_da = date(anno, mese, giorno_inizio)
    if mese == 12:
        next_anno, next_mese = anno + 1, 1
    else:
        next_anno, next_mese = anno, mese + 1
    next_n_giorni = _giorni_mese(next_anno, next_mese)
    next_giorno = min(anniversary_day, next_n_giorni)
    prossimo_inizio = date(next_anno, next_mese, next_giorno)
    return competenza_da, prossimo_inizio - timedelta(days=1)


def _quota_condominio_per(competenza_da: date) -> Decimal:
    """Ritorna la quota mensile di spese condominio a carico dell'inquilino
    (``TenantCondominioRate``) valida per la data di competenza, o 0 se non
    è configurata.

    Se più record sono validi (es. contratti diversi che si sovrappongono),
    sommiamo: deve esserci una sola quota per inquilino-mese in pratica.
    """
    from billing.models import TenantCondominioRate

    qs = TenantCondominioRate.objects.filter(valid_from__lte=competenza_da).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=competenza_da)
    )
    tot = Decimal("0")
    for r in qs:
        tot += r.importo_mensile
    return tot


def genera_pagamenti_mese(
    anno: int,
    mese: int,
    force: bool = False,
    persist: bool = True,
    tenant_id: int | None = None,
    property=None,
) -> dict:
    """
    Per ogni RoomAssignment attivo (anche parzialmente) nel mese, crea un
    Receivable causale=affitto se non esiste gia' (o lo sovrascrive se
    ``force=True``).

    Algoritmo:
    1. Determina giorno_pagamento di ogni inquilino (TenantProfile.giorno_pagamento_affitto)
    2. Calcola competenza_da/competenza_a:
       competenza_da = max(primo_del_mese, assignment.valid_from)
       competenza_a  = min(ultimo_del_mese, assignment.valid_to o ultimo_del_mese)
    3. Importo:
       - giorni_mese = giorni effettivi del mese (28-31)
       - giorni_competenza = (competenza_a - competenza_da).days + 1
       - canone_dovuto = canone_mensile + quota_condominio_per(competenza_da)
         dove quota_condominio = ``TenantCondominioRate`` valido nel periodo
       - se giorni_competenza < giorni_mese: is_aggiustamento=True,
         importo_dovuto = round(canone_dovuto * giorni_competenza / giorni_mese, 2)
       - altrimenti: is_aggiustamento=False, importo_dovuto = canone_dovuto
    4. Scadenza = data(anno, mese, min(giorno_pagamento, ultimo_del_mese)) + 5gg
    5. Stato iniziale: 'atteso'
    6. Inserisci con get_or_create chiave (assignment, competenza_da, competenza_a)
       Se force=True: usa update_or_create per sovrascrivere.

    Ritorna:
    {
        "anno": ..., "mese": ...,
        "creati": int, "aggiornati": int, "skippati": int,
        "payments": [list di id]
    }
    """
    from billing.models import Receivable, StatoPagamento
    from properties.models import RoomAssignment

    primo_del_mese = date(anno, mese, 1)
    ultimo_mese = _ultimo_del_mese(anno, mese)
    n_giorni_mese = _giorni_mese(anno, mese)

    # Assignment attivi (overlap col mese)
    assignments_qs = RoomAssignment.objects.filter(
        valid_from__lte=ultimo_mese,
    ).filter(
        valid_to__isnull=True,
    ) | RoomAssignment.objects.filter(
        valid_from__lte=ultimo_mese,
        valid_to__gte=primo_del_mese,
    )
    assignments_qs = assignments_qs.distinct().select_related("tenant")
    if property is not None:
        assignments_qs = assignments_qs.filter(room__property=property)
    if tenant_id is not None:
        assignments_qs = assignments_qs.filter(tenant_id=tenant_id)
    # Ordine deterministico per output log cronologico/alfabetico.
    assignments_qs = assignments_qs.order_by("tenant__nominativo")

    creati = 0
    aggiornati = 0
    aggiornati_diversi = 0
    aggiornati_uguali = 0
    skippati = 0
    skippati_per_allocation: list[dict] = []
    skippati_divergenti: list[dict] = []
    duplicati_altro_assignment: list[dict] = []
    rilinkati: list[dict] = []
    payment_ids: list[int] = []
    simulazione: list[dict] = []  # popolato solo se persist=False

    from properties.models import TenantProfile

    for assignment in assignments_qs:
        tenant = assignment.tenant
        ciclo_ingresso = (
            tenant.ciclo_fatturazione == TenantProfile.CicloFatturazione.INGRESSO
        )

        if ciclo_ingresso:
            anniversary_day = assignment.valid_from.day
            competenza_da, mensilita_completa_a = _anniversary_periodo(
                anno, mese, anniversary_day
            )
            # Skip se la mensilità non è dentro l'assignment
            if competenza_da < assignment.valid_from:
                continue
            if assignment.valid_to and competenza_da > assignment.valid_to:
                continue

            # Troncamento dal valid_to (uscita anticipata infra-mensilità)
            if assignment.valid_to and assignment.valid_to < mensilita_completa_a:
                competenza_a = assignment.valid_to
                giorni_mensilita_completa = (mensilita_completa_a - competenza_da).days + 1
                giorni_competenza = (competenza_a - competenza_da).days + 1
                is_aggiustamento = True
                canone_pieno = assignment.canone_mensile + _quota_condominio_per(
                    competenza_da
                )
                importo_dovuto = _arrotonda(
                    canone_pieno
                    * Decimal(giorni_competenza)
                    / Decimal(giorni_mensilita_completa)
                )
            else:
                competenza_a = mensilita_completa_a
                is_aggiustamento = False
                canone_pieno = assignment.canone_mensile + _quota_condominio_per(
                    competenza_da
                )
                importo_dovuto = canone_pieno

            # Scadenza: data di inizio mensilità + 5 giorni
            scadenza = competenza_da + timedelta(days=5)
        else:
            # Ciclo solare (default)
            competenza_da = max(primo_del_mese, assignment.valid_from)
            a_to = assignment.valid_to if assignment.valid_to else ultimo_mese
            competenza_a = min(ultimo_mese, a_to)

            giorni_competenza = (competenza_a - competenza_da).days + 1
            canone_pieno = assignment.canone_mensile + _quota_condominio_per(
                competenza_da
            )

            if giorni_competenza < n_giorni_mese:
                is_aggiustamento = True
                importo_dovuto = _arrotonda(
                    canone_pieno * Decimal(giorni_competenza) / Decimal(n_giorni_mese)
                )
            else:
                is_aggiustamento = False
                importo_dovuto = canone_pieno

            giorno_pagamento = tenant.giorno_pagamento_affitto
            giorno_eff = min(giorno_pagamento, n_giorni_mese)
            data_scadenza_base = date(anno, mese, giorno_eff)
            scadenza = data_scadenza_base + timedelta(days=5)

        defaults_base = {
            "competenza_a": competenza_a,
            "importo_dovuto": importo_dovuto,
            "scadenza": scadenza,
            "is_aggiustamento": is_aggiustamento,
        }
        defaults_create = {**defaults_base, "stato": StatoPagamento.ATTESO}

        esistente = Receivable.objects.filter(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=competenza_da,
            competenza_a=competenza_a,
        ).first()
        # Se sull'assignment corrente non c'è nulla, può esistere su un altro
        # assignment dello stesso tenant (es. rinnovo contratto in continuita').
        # In quel caso NON dobbiamo creare un duplicato: lo segnaliamo.
        altro_assignment_rec = None
        if esistente is None:
            altro_assignment_rec = Receivable.objects.filter(
                assignment__tenant_id=assignment.tenant_id,
                causale=Receivable.Causale.AFFITTO,
                competenza_da=competenza_da,
                competenza_a=competenza_a,
            ).exclude(assignment=assignment).first()

        if not persist:
            if esistente and esistente.allocations.exists():
                azione = "skip_allocation"
            elif altro_assignment_rec is not None and altro_assignment_rec.allocations.exists():
                # Esiste su altro assignment ed è allocato a BT: intoccabile
                azione = "skip_allocation"
            elif altro_assignment_rec is not None and force:
                # Con force: si aggiorna importo e si rilinka all'assignment corrente
                azione = "update_riassocia"
            elif altro_assignment_rec is not None:
                azione = "create_duplicato"
            elif esistente and force:
                azione = "update"
            elif esistente:
                azione = "skip"
            else:
                azione = "create"
            importo_esistente = esistente.importo_dovuto if esistente else None
            altro_importo = (
                altro_assignment_rec.importo_dovuto if altro_assignment_rec else None
            )
            altro_assignment_id = (
                altro_assignment_rec.assignment_id if altro_assignment_rec else None
            )
            if azione in ("update", "skip") and esistente is not None:
                divergenza: bool | None = importo_esistente != importo_dovuto
            elif azione in ("create_duplicato", "update_riassocia"):
                divergenza = altro_importo != importo_dovuto
            else:
                divergenza = None
            simulazione.append({
                "tenant_nominativo": assignment.tenant.nominativo,
                "competenza_da": competenza_da,
                "competenza_a": competenza_a,
                "importo_dovuto": importo_dovuto,
                "importo_esistente": importo_esistente,
                "altro_importo": altro_importo,
                "altro_assignment_id": altro_assignment_id,
                "scadenza": scadenza,
                "is_aggiustamento": is_aggiustamento,
                "azione_prevista": azione,
                "divergenza": divergenza,
            })
            continue

        # ----- Persist -----
        # Se esiste un Receivable per lo stesso tenant nello stesso periodo
        # ma su un altro assignment: con `force` lo aggiorniamo riassociando
        # all'assignment corrente; senza force segnaliamo e skip (no duplicati).
        if esistente is None and altro_assignment_rec is not None:
            if altro_assignment_rec.allocations.exists():
                skippati_per_allocation.append(
                    {
                        "receivable_id": altro_assignment_rec.pk,
                        "assignment_id": assignment.pk,
                        "tenant_nominativo": assignment.tenant.nominativo,
                        "importo_esistente": altro_assignment_rec.importo_dovuto,
                        "importo_calcolato": importo_dovuto,
                    }
                )
                payment_ids.append(altro_assignment_rec.pk)
                continue
            if force:
                importo_pre = altro_assignment_rec.importo_dovuto
                old_assignment_id = altro_assignment_rec.assignment_id
                altro_assignment_rec.assignment = assignment
                for k, v in defaults_base.items():
                    setattr(altro_assignment_rec, k, v)
                altro_assignment_rec.save(
                    update_fields=[*defaults_base.keys(), "assignment", "updated_at"]
                )
                aggiornati += 1
                if importo_pre != importo_dovuto:
                    aggiornati_diversi += 1
                else:
                    aggiornati_uguali += 1
                rilinkati.append(
                    {
                        "receivable_id": altro_assignment_rec.pk,
                        "tenant_nominativo": assignment.tenant.nominativo,
                        "anno": anno,
                        "mese": mese,
                        "old_assignment_id": old_assignment_id,
                        "new_assignment_id": assignment.pk,
                        "importo_pre": importo_pre,
                        "importo_post": importo_dovuto,
                    }
                )
                payment_ids.append(altro_assignment_rec.pk)
                continue
            duplicati_altro_assignment.append(
                {
                    "receivable_id": altro_assignment_rec.pk,
                    "assignment_id_corrente": assignment.pk,
                    "assignment_id_esistente": altro_assignment_rec.assignment_id,
                    "tenant_nominativo": assignment.tenant.nominativo,
                    "anno": anno,
                    "mese": mese,
                    "competenza_da": competenza_da,
                    "competenza_a": competenza_a,
                    "importo_esistente": altro_assignment_rec.importo_dovuto,
                    "importo_calcolato": importo_dovuto,
                }
            )
            payment_ids.append(altro_assignment_rec.pk)
            continue

        if force:
            # In rigenerazione preserviamo `stato`/`data_pagamento`/
            # `importo_pagato`/`incassato_da_owner` se il record esiste già.
            # Guardia integrità: se il Receivable ha allocations bancarie,
            # NON viene sovrascritto (vedi razionale in _persist_receivables di calc/utility.py).
            if esistente and esistente.allocations.exists():
                skippati_per_allocation.append(
                    {
                        "receivable_id": esistente.pk,
                        "assignment_id": assignment.pk,
                        "tenant_nominativo": assignment.tenant.nominativo,
                        "importo_esistente": esistente.importo_dovuto,
                        "importo_calcolato": importo_dovuto,
                    }
                )
                payment = esistente
                payment_ids.append(payment.pk)
                continue
            if esistente:
                payment = esistente
                created = False
                importo_pre = esistente.importo_dovuto
                for k, v in defaults_base.items():
                    setattr(payment, k, v)
                payment.save(
                    update_fields=[*defaults_base.keys(), "updated_at"]
                )
            else:
                payment = Receivable.objects.create(
                    assignment=assignment,
                    causale=Receivable.Causale.AFFITTO,
                    competenza_da=competenza_da,
                    **defaults_create,
                )
                created = True
            if created:
                creati += 1
            else:
                aggiornati += 1
                if importo_pre != importo_dovuto:
                    aggiornati_diversi += 1
                else:
                    aggiornati_uguali += 1
        else:
            # No force: chiave (assignment, causale, competenza_da, competenza_a).
            if esistente is not None:
                skippati += 1
                payment = esistente
                if payment.importo_dovuto != importo_dovuto:
                    skippati_divergenti.append(
                        {
                            "receivable_id": payment.pk,
                            "assignment_id": assignment.pk,
                            "tenant_nominativo": assignment.tenant.nominativo,
                            "anno": anno,
                            "mese": mese,
                            "competenza_da": competenza_da,
                            "competenza_a": competenza_a,
                            "importo_esistente": payment.importo_dovuto,
                            "importo_calcolato": importo_dovuto,
                        }
                    )
            else:
                payment = Receivable.objects.create(
                    assignment=assignment,
                    causale=Receivable.Causale.AFFITTO,
                    competenza_da=competenza_da,
                    **defaults_create,
                )
                creati += 1

        payment_ids.append(payment.pk)

    return {
        "anno": anno,
        "mese": mese,
        "creati": creati,
        "aggiornati": aggiornati,
        "aggiornati_diversi": aggiornati_diversi,
        "aggiornati_uguali": aggiornati_uguali,
        "skippati": skippati,
        "skippati_per_allocation": skippati_per_allocation,
        "skippati_divergenti": skippati_divergenti,
        "duplicati_altro_assignment": duplicati_altro_assignment,
        "rilinkati": rilinkati,
        "payments": payment_ids,
        "simulazione": simulazione,
    }


def aggiustamento_uscita(assignment_id: int, data_uscita: date) -> dict:
    """
    Per uscita anticipata a meta' mese: crea ExtraCharge negativo (rimborso pro-rata)
    sul canone del mese di uscita oltre i giorni effettivi di permanenza.

    Logica:
    - Trova il RentPayment del mese di data_uscita per questo assignment
      (se esiste ed e' per il mese intero, calcola il rimborso per i giorni non goduti)
    - Crea ExtraCharge con importo negativo = canone * giorni_non_goduti / giorni_mese

    Ritorna dict con ExtraCharge creato e dettagli del calcolo.
    """
    from billing.models import Receivable, StatoPagamento
    from properties.models import RoomAssignment

    assignment = RoomAssignment.objects.select_related("tenant").get(pk=assignment_id)
    anno = data_uscita.year
    mese = data_uscita.month
    n_giorni_mese = _giorni_mese(anno, mese)
    primo_del_mese = date(anno, mese, 1)
    ultimo_mese = _ultimo_del_mese(anno, mese)

    # Giorni effettivi di permanenza nel mese di uscita
    giorni_presenti = (data_uscita - primo_del_mese).days + 1
    giorni_non_goduti = n_giorni_mese - giorni_presenti

    if giorni_non_goduti <= 0:
        # Uscita l'ultimo giorno del mese: nessun rimborso
        return {
            "extra_charge": None,
            "giorni_presenti": giorni_presenti,
            "giorni_non_goduti": 0,
            "importo_rimborso": Decimal("0.00"),
            "messaggio": "Uscita l'ultimo giorno del mese, nessun rimborso dovuto.",
        }

    importo_rimborso = _arrotonda(
        assignment.canone_mensile * Decimal(giorni_non_goduti) / Decimal(n_giorni_mese)
    )
    # L'importo e' negativo (accredito all'inquilino)
    importo_negativo = -importo_rimborso

    # Scadenza: giorno di uscita (rimborso immediato)
    scadenza = data_uscita

    extra = Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.EXTRA,
        descrizione=(
            f"Rimborso pro-rata uscita anticipata {data_uscita.strftime('%d/%m/%Y')}: "
            f"{giorni_non_goduti} giorni su {n_giorni_mese}"
        ),
        competenza_da=data_uscita,
        competenza_a=None,
        importo_dovuto=importo_negativo,
        scadenza=scadenza,
        stato=StatoPagamento.ATTESO,
        note=(
            f"Canone {assignment.canone_mensile}€ × "
            f"{giorni_non_goduti}/{n_giorni_mese} giorni = {importo_rimborso}€ rimborso"
        ),
    )

    return {
        "extra_charge": extra,
        "giorni_presenti": giorni_presenti,
        "giorni_non_goduti": giorni_non_goduti,
        "importo_rimborso": importo_rimborso,
    }
