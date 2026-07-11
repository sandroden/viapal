"""Signals dell'app properties.

Genera automaticamente i Receivable di causale DEPOSITO quando viene valorizzato
il deposito su TenantProfile (versamento) o la sua restituzione. Idempotente:
salvando lo stesso TenantProfile più volte non duplica i Receivable.

La generazione scatta anche al post_save di RoomAssignment per gestire il caso
"tenant creato con deposito ma senza ancora alcun assignment" (rare ma possibile
in fase di setup iniziale).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import RoomAssignment, TenantProfile

log = logging.getLogger(__name__)


def _crea_deposito_versamento(tenant: TenantProfile) -> None:
    if tenant.deposito_versato is None or tenant.deposito_versato <= Decimal("0"):
        return

    from billing.models import Receivable, StatoPagamento

    esiste = Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.DEPOSITO,
        importo_dovuto__gt=0,
    ).exists()
    if esiste:
        return

    primo = tenant.assignments.order_by("valid_from", "id").first()
    if primo is None:
        log.info(
            "Deposito versato per tenant %s ma nessun RoomAssignment: "
            "Receivable verrà generato al primo assignment.",
            tenant.pk,
        )
        return

    data_evento = tenant.data_versamento_deposito or primo.valid_from
    Receivable.objects.create(
        assignment=primo,
        causale=Receivable.Causale.DEPOSITO,
        descrizione="Deposito (versamento)",
        competenza_da=data_evento,
        competenza_a=None,
        scadenza=data_evento,
        importo_dovuto=tenant.deposito_versato,
        stato=StatoPagamento.ATTESO,
    )


def _crea_deposito_restituzione(tenant: TenantProfile) -> None:
    # Trigger: la presenza della data prevista di restituzione. Senza data
    # non c'è restituzione da contabilizzare.
    if tenant.data_restituzione_prevista is None:
        return

    # Importo lordo da rendere: override esplicito, altrimenti pari al
    # deposito versato (caso normale). Il netto effettivo dipende dal saldo
    # dell'inquilino ed è calcolato altrove (simulazione uscita).
    importo = tenant.deposito_da_restituire
    if importo is None or importo <= Decimal("0"):
        importo = tenant.deposito_versato
    if importo is None or importo <= Decimal("0"):
        return

    from billing.models import Receivable, StatoPagamento

    esiste = Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.DEPOSITO,
        importo_dovuto__lt=0,
    ).exists()
    if esiste:
        return

    ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
    if ultimo is None:
        log.info(
            "Restituzione deposito prevista per tenant %s ma nessun "
            "RoomAssignment.",
            tenant.pk,
        )
        return

    data_evento = tenant.data_restituzione_prevista
    Receivable.objects.create(
        assignment=ultimo,
        causale=Receivable.Causale.DEPOSITO,
        descrizione="Deposito (restituzione)",
        competenza_da=data_evento,
        competenza_a=None,
        scadenza=data_evento,
        importo_dovuto=-importo,
        stato=StatoPagamento.ATTESO,
    )


_EXPENSE_CAT_REGISTRAZIONE = ("registrazione-contratti", "Registrazione contratti")


def _owner_anticipante(property):
    """Il proprietario che anticipa il 50% cessione: configurato
    sull'immobile (``Property.owner_anticipa_cessioni``).

    Se non è configurato la Expense non viene creata, ma il Receivable
    inquilino sì: meglio un dato parziale che un crash.
    """
    return property.owner_anticipa_cessioni


def _crea_costo_cessione(assignment: RoomAssignment) -> None:
    """Genera gli effetti del costo di cessione di un RoomAssignment.

    Criterio (volutamente semplice): scatta se ``costo_cessione`` è valorizzato
    sull'assegnazione. Il contratto collettivo non lo valorizza → nessun
    effetto. ``costo_cessione`` è il TOTALE, splittato 50/50:

    - 50% → Receivable causale REGISTRAZIONE all'inquilino entrante;
    - 50% → Expense ripartibile pro-quota tra i proprietari (anticipante
      Sandro), categoria "Registrazione contratti".

    Entrambi datati all'inizio occupazione (``valid_from``). Idempotente: una
    sola coppia per assignment; variazioni dell'importo NON rigenerano.
    """
    costo = assignment.costo_cessione
    if costo is None or costo <= Decimal("0"):
        return

    from billing.models import Expense, ExpenseCategory, Receivable, StatoPagamento

    quota_inquilino = (costo / 2).quantize(Decimal("0.01"))
    quota_proprietari = costo - quota_inquilino
    data_evento = assignment.valid_from

    if not Receivable.objects.filter(
        assignment=assignment,
        causale=Receivable.Causale.REGISTRAZIONE,
    ).exists():
        Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.REGISTRAZIONE,
            descrizione="Registrazione contratto (quota inquilino 50%)",
            competenza_da=data_evento,
            competenza_a=None,
            scadenza=data_evento,
            importo_dovuto=quota_inquilino,
            stato=StatoPagamento.ATTESO,
        )

    marker = f"[auto:cessione:{assignment.pk}]"
    if not Expense.objects.filter(note__contains=marker).exists():
        prop = assignment.room.property
        anticipante = _owner_anticipante(prop)
        if anticipante is None:
            log.warning(
                "Costo cessione assignment %s: nessun 'owner_anticipa_cessioni' "
                "configurato su %s, Expense 50%% proprietari non creata.",
                assignment.pk, prop,
            )
            return
        codice, nome = _EXPENSE_CAT_REGISTRAZIONE
        categoria, _ = ExpenseCategory.objects.get_or_create(
            property=prop,
            codice=codice,
            defaults={"nome": nome, "ripartibile_inquilini": False},
        )
        Expense.objects.create(
            property=prop,
            data=data_evento,
            category=categoria,
            importo=quota_proprietari,
            descrizione=f"Cessione {assignment.room} — {assignment.tenant}",
            anticipata_da_owner=anticipante,
            ripartibile_su_inquilini=False,
            note=marker,
        )


@receiver(post_save, sender=TenantProfile)
def genera_receivable_deposito_da_tenant(sender, instance, **kwargs):
    _crea_deposito_versamento(instance)
    _crea_deposito_restituzione(instance)


@receiver(post_save, sender=RoomAssignment)
def genera_receivable_deposito_da_assignment(sender, instance, created, **kwargs):
    """Recupera il caso in cui il tenant aveva già deposito valorizzato
    al momento della creazione del primo assignment."""
    if created:
        _crea_deposito_versamento(instance.tenant)
        _crea_deposito_restituzione(instance.tenant)
    # Il costo di cessione va valutato anche sugli update: spesso viene
    # valorizzato a mano dopo aver creato l'assegnazione.
    _crea_costo_cessione(instance)
