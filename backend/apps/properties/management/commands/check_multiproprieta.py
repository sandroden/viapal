"""
Verifica di integrità del modello multi-proprietà (Fase A).

Controlla che dopo la migrazione/backfill non ci siano record orfani o
incoerenti. Esce con errore (exit code 1) se trova problemi: pensato per
essere lanciato dopo il deploy della migrazione e su un dump di produzione
prima del deploy stesso.

    uv run manage.py check_multiproprieta
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import F

from properties.models import (
    Property,
    PropertyMembership,
    RoomAssignment,
    TenantProfile,
    quote_attive_at,
)


class Command(BaseCommand):
    help = "Verifica l'integrità del modello multi-proprietà (record orfani, quote, coerenza immobili)."

    def handle(self, *args, **opts):
        errori: list[str] = []
        avvisi: list[str] = []

        oggi = datetime.date.today()
        props = list(Property.objects.all())
        self.stdout.write(f"Immobili: {len(props)}")

        if not props:
            self.stdout.write(self.style.WARNING("Nessun immobile: niente da verificare."))
            return

        # 1. Ogni property con dati deve avere almeno un membro proprietario.
        for prop in props:
            n_prop = prop.memberships.filter(
                ruolo=PropertyMembership.Ruolo.PROPRIETARIO
            ).count()
            if n_prop == 0:
                errori.append(f"{prop}: nessun membro con ruolo 'proprietario'.")

        # 2. Quote attive per property: somma = 1.0 e owner con membership.
        for prop in props:
            quote = quote_attive_at(prop, oggi)
            if not quote:
                avvisi.append(f"{prop}: nessuna quota di proprietà attiva oggi.")
                continue
            totale = sum(quote.values(), start=Decimal("0"))
            if abs(totale - Decimal("1")) > Decimal("0.001"):
                errori.append(f"{prop}: somma quote attive = {totale} (atteso 1.0).")
            for owner in quote:
                ok = PropertyMembership.objects.filter(
                    property=prop,
                    user=owner.user_id,
                    ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
                ).exists()
                if not ok:
                    errori.append(
                        f"{prop}: {owner} ha una quota ma non è membro 'proprietario'."
                    )

        # 3. Assignment coerenti: stanza e inquilino sullo stesso immobile.
        incoerenti = RoomAssignment.objects.select_related(
            "room", "tenant"
        ).exclude(room__property=F("tenant__property"))
        for a in incoerenti:
            errori.append(
                f"Assignment {a.pk} ({a}): stanza su immobile "
                f"{a.room.property_id}, inquilino su {a.tenant.property_id}."
            )

        # 4. Inquilini senza immobile o utenti-membri che sono anche inquilini
        #    dello stesso immobile.
        for tp in TenantProfile.objects.select_related("user", "property"):
            doppio = PropertyMembership.objects.filter(
                property=tp.property_id, user=tp.user_id
            ).exists()
            if doppio:
                errori.append(
                    f"{tp.nominativo}: è inquilino E membro di gestione di {tp.property}."
                )

        # 5. Record senza property (non dovrebbe più essere possibile a livello
        #    DB, ma verifichiamo i legami derivati).
        from billing.models import Receivable

        n_rec_orfani = Receivable.objects.filter(
            assignment__room__property__isnull=True
        ).count()
        if n_rec_orfani:
            errori.append(f"{n_rec_orfani} Receivable senza immobile (via assignment.room).")

        # --- Report -------------------------------------------------------
        for a in avvisi:
            self.stdout.write(self.style.WARNING(f"AVVISO: {a}"))
        if errori:
            for e in errori:
                self.stdout.write(self.style.ERROR(f"ERRORE: {e}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Multiproprietà: integrità OK."))
