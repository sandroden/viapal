"""Rimappa le assegnazioni stanza sulla numerazione della planimetria.

Contesto (2026-07): la ricostruzione storica ha abbinato gli inquilini alle
stanze con una numerazione arbitraria, mentre le righe ``Room`` — tramite le
foto e i prezzi caricati dalla galleria pubblica — corrispondono alla
numerazione della planimetria, che è quella ufficiale. Stessa riga, due stanze
fisiche diverse a seconda del sottosistema.

Questo command sposta le FK ``RoomAssignment.room`` secondo la permutazione
verificata con Sandro (canoni reali ↔ prezzi in galleria):

    Camera 1 → Camera 3   (Maria Severa, canone 470 = prezzo pl.3)
    Camera 2 → Camera 4   (Bruno, canone 520 = prezzo pl.4)
    Camera 3 → Camera 2   (Arun; pl.2 è l'unica "Occupata" in galleria)
    Camera 4 → Camera 1   (la stanza libera: fisicamente la pl.1 da 400€)
    Camera 5 → Camera 5   (Diana, già corretta)

Le foto della galleria e i Receivable NON si toccano: le prime sono già
ancorate alla planimetria, i secondi pendono dagli assignment e seguono da
soli. Gli update avvengono per elenco di id raccolti PRIMA di scrivere (la
permutazione contiene cicli) e via ``queryset.update()`` per non innescare i
signal.

Idempotente e fail-safe: verifica lo stato atteso pre-migrazione (occupanti
correnti sulle righe vecchie); se trova lo stato post-migrazione esce con
"già applicato"; in ogni altro caso si rifiuta di toccare i dati. Di default
è un dry-run: serve --apply per scrivere.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

PERMUTAZIONE = {
    "Camera 1": "Camera 3",
    "Camera 2": "Camera 4",
    "Camera 3": "Camera 2",
    "Camera 4": "Camera 1",
    # Camera 5 resta dov'è
}

# Occupanti attesi (assignment aperto) PRIMA della migrazione, per riconoscere
# lo stato. Sottoinsieme stabile: tenant il cui nominativo contiene la chiave.
ATTESI_PRE = {
    "Camera 1": "Maria Severa",
    "Camera 2": "Bruno",
    "Camera 3": "Arun",
    "Camera 5": "Diana",
}


class Command(BaseCommand):
    help = "Sposta le RoomAssignment sulla numerazione della planimetria (dry-run di default)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Applica davvero (senza: solo dry-run).",
        )
        parser.add_argument(
            "--property", type=int, default=1,
            help="Id dell'immobile (default 1, Viapal).",
        )

    def _occupante(self, room):
        oggi = datetime.date.today()
        att = (
            room.assignments.filter(valid_from__lte=oggi, valid_to__isnull=True)
            .select_related("tenant")
            .first()
        )
        return att.tenant.nominativo if att else None

    def handle(self, *args, **opts):
        from properties.models import Room, RoomAssignment

        prop_id = opts["property"]
        rooms = {r.nome: r for r in Room.objects.filter(property_id=prop_id)}
        mancanti = set(PERMUTAZIONE) - set(rooms)
        if mancanti:
            raise CommandError(f"Stanze non trovate sull'immobile {prop_id}: {mancanti}")

        def stato_compatibile(attesi):
            esito = []
            for nome, atteso in attesi.items():
                occ = self._occupante(rooms[nome])
                ok = occ is not None and atteso.lower() in occ.lower()
                esito.append((nome, atteso, occ, ok))
            return esito

        pre = stato_compatibile(ATTESI_PRE)
        post_attesi = {PERMUTAZIONE.get(k, k): v for k, v in ATTESI_PRE.items()}
        post = stato_compatibile(post_attesi)

        if all(ok for *_, ok in post):
            self.stdout.write(self.style.SUCCESS("Già applicato: nulla da fare."))
            return
        if not all(ok for *_, ok in pre):
            for nome, atteso, occ, ok in pre:
                marker = "ok" if ok else "MISMATCH"
                self.stdout.write(f"  {nome}: atteso ~{atteso!r}, trovato {occ!r} [{marker}]")
            raise CommandError(
                "Stato inatteso: né pre né post migrazione. Nessuna modifica."
            )

        # Raccolta id per stanza di origine PRIMA di qualunque write: la
        # permutazione ha cicli (1→3→2→4→1) e update sequenziali sui
        # queryset sposterebbero due volte gli stessi record.
        piani = []
        for da, a in PERMUTAZIONE.items():
            ids = list(
                RoomAssignment.objects.filter(room=rooms[da]).values_list("pk", flat=True)
            )
            piani.append((da, a, ids))
            self.stdout.write(f"  {da} → {a}: {len(ids)} assignment")

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING("Dry-run: nessuna modifica (usa --apply)."))
            return

        with transaction.atomic():
            for da, a, ids in piani:
                # .update() diretto: niente signal, niente full_clean (la
                # bigezione preserva i non-overlap per costruzione).
                RoomAssignment.objects.filter(pk__in=ids).update(room=rooms[a])

        self.stdout.write(self.style.SUCCESS("Rimappatura applicata."))
        for nome in sorted(rooms):
            self.stdout.write(f"  {nome}: occupante ora {self._occupante(rooms[nome])!r}")
