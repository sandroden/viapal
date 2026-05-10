"""Signals dell'app properties.

Genera automaticamente i Receivable di causale CAPARRA quando viene valorizzata
la caparra su TenantProfile (versamento) o la sua restituzione. Idempotente:
salvando lo stesso TenantProfile più volte non duplica i Receivable.

La generazione scatta anche al post_save di RoomAssignment per gestire il caso
"tenant creato con caparra ma senza ancora alcun assignment" (rare ma possibile
in fase di setup iniziale).
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import RoomAssignment, TenantProfile

log = logging.getLogger(__name__)


def _crea_caparra_versamento(tenant: TenantProfile) -> None:
    if tenant.deposito_versato is None or tenant.deposito_versato <= Decimal("0"):
        return

    from billing.models import Receivable, StatoPagamento

    esiste = Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.CAPARRA,
        importo_dovuto__gt=0,
    ).exists()
    if esiste:
        return

    primo = tenant.assignments.order_by("valid_from", "id").first()
    if primo is None:
        log.info(
            "Caparra versata per tenant %s ma nessun RoomAssignment: "
            "Receivable verrà generato al primo assignment.",
            tenant.pk,
        )
        return

    data_evento = tenant.data_versamento_deposito or primo.valid_from
    Receivable.objects.create(
        assignment=primo,
        causale=Receivable.Causale.CAPARRA,
        descrizione="Caparra (versamento)",
        competenza_da=data_evento,
        competenza_a=None,
        scadenza=data_evento,
        importo_dovuto=tenant.deposito_versato,
        stato=StatoPagamento.ATTESO,
    )


def _crea_caparra_restituzione(tenant: TenantProfile) -> None:
    if tenant.deposito_restituito is None or tenant.deposito_restituito <= Decimal("0"):
        return

    from billing.models import Receivable, StatoPagamento

    esiste = Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.CAPARRA,
        importo_dovuto__lt=0,
    ).exists()
    if esiste:
        return

    ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
    if ultimo is None:
        log.info(
            "Caparra restituita per tenant %s ma nessun RoomAssignment.",
            tenant.pk,
        )
        return

    data_evento = (
        tenant.data_restituzione_deposito
        or ultimo.valid_to
        or date.today()
    )
    Receivable.objects.create(
        assignment=ultimo,
        causale=Receivable.Causale.CAPARRA,
        descrizione="Caparra (restituzione)",
        competenza_da=data_evento,
        competenza_a=None,
        scadenza=data_evento,
        importo_dovuto=-tenant.deposito_restituito,
        stato=StatoPagamento.ATTESO,
    )


@receiver(post_save, sender=TenantProfile)
def genera_receivable_caparra_da_tenant(sender, instance, **kwargs):
    _crea_caparra_versamento(instance)
    _crea_caparra_restituzione(instance)


@receiver(post_save, sender=RoomAssignment)
def genera_receivable_caparra_da_assignment(sender, instance, created, **kwargs):
    """Recupera il caso in cui il tenant aveva già caparra valorizzata
    al momento della creazione del primo assignment."""
    if not created:
        return
    _crea_caparra_versamento(instance.tenant)
    _crea_caparra_restituzione(instance.tenant)
