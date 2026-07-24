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
from django.db.models import F, Q

from properties.models import (
    OwnershipShare,
    Property,
    PropertyMembership,
    RoomAssignment,
    TenantProfile,
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

        # 2. Quote attive per property: somma = 1.0, owner con membership,
        #    nessun owner duplicato. NB: usiamo il queryset grezzo, NON
        #    quote_attive_at() — quest'ultima riproporziona a 1.0 quando la
        #    somma non torna, quindi il controllo su di essa non fallisce
        #    mai (ed è keyed per owner: i duplicati collasserebbero).
        for prop in props:
            attive = list(
                OwnershipShare.objects.select_related("owner").filter(
                    property=prop, valid_from__lte=oggi,
                ).filter(
                    Q(valid_to__isnull=True) | Q(valid_to__gt=oggi)
                )
            )
            if not attive:
                avvisi.append(f"{prop}: nessuna quota di proprietà attiva oggi.")
                continue
            totale = sum((s.quota for s in attive), start=Decimal("0"))
            if abs(totale - Decimal("1")) > Decimal("0.001"):
                errori.append(f"{prop}: somma quote attive = {totale} (atteso 1.0).")

            owner_ids_visti: set[int] = set()
            owner_ids_duplicati: dict[int, "OwnershipShare"] = {}
            for s in attive:
                if s.owner_id in owner_ids_visti:
                    owner_ids_duplicati[s.owner_id] = s
                owner_ids_visti.add(s.owner_id)
            for s in owner_ids_duplicati.values():
                errori.append(
                    f"{prop}: {s.owner} ha più quote attive oggi (owner duplicato)."
                )

            for s in attive:
                ok = PropertyMembership.objects.filter(
                    property=prop,
                    user=s.owner.user_id,
                    ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
                ).exists()
                if not ok:
                    errori.append(
                        f"{prop}: {s.owner} ha una quota ma non è membro 'proprietario'."
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

        # 5. Coerenza cross-property fra Receivable(causale=utenze) e il suo
        #    UtilityChargePeriod: entrambi puntano (indirettamente) a un
        #    immobile ma non c'è alcun vincolo DB che li tenga allineati —
        #    assignment.room.property e utility_period.property potrebbero
        #    divergere se un periodo utenze viene agganciato per errore a un
        #    addebito di un altro immobile. (Il vecchio check qui —
        #    `Receivable.objects.filter(assignment__room__property__isnull=True)`
        #    — era vacuo: tutte le FK della catena sono NOT NULL, quindi non
        #    poteva mai dare risultati; questo lo sostituisce con un
        #    invariante derivato realmente falsificabile.)
        from billing.models import Receivable

        incoerenti_utenze = Receivable.objects.filter(
            causale=Receivable.Causale.UTENZE, utility_period__isnull=False,
        ).exclude(
            utility_period__property=F("assignment__room__property")
        ).select_related("utility_period", "assignment__room")
        for r in incoerenti_utenze:
            errori.append(
                f"Receivable {r.pk} ({r}): periodo utenze su immobile "
                f"{r.utility_period.property_id}, assegnazione su "
                f"{r.assignment.room.property_id}."
            )

        # --- Report -------------------------------------------------------
        for a in avvisi:
            self.stdout.write(self.style.WARNING(f"AVVISO: {a}"))
        if errori:
            for e in errori:
                self.stdout.write(self.style.ERROR(f"ERRORE: {e}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Multiproprietà: integrità OK."))
