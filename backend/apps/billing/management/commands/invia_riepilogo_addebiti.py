"""
Management command per l'email di **riepilogo addebiti** agli inquilini.

Uso:
    uv run manage.py invia_riepilogo_addebiti                            # DRY-RUN, tutti gli immobili
    uv run manage.py invia_riepilogo_addebiti --property viapal          # DRY-RUN su un immobile
    uv run manage.py invia_riepilogo_addebiti --property viapal --invia  # invio REALE

``--property`` accetta indifferentemente id, nome o slug dell'immobile.

La forma di default è la **prova a vuoto**: stampa chi riceverebbe cosa senza
spedire niente. Solo ``--invia`` manda le email davvero.

Gli **ex inquilini** (nessuna assegnazione attiva) compaiono nell'elenco ma
non ricevono: i loro arretrati sono quasi sempre partite storiche non
riconciliate. Per sollecitarne uno davvero si passa da ``/p/notifiche``,
spuntandolo a mano; da qui non c'è modo di forzarli.

Finché dura il rodaggio l'invio quotidiano passa da ``/p/notifiche``, dove si
vede l'anteprima e si deselezionano i destinatari. Il comando è già
automatizzabile (non interattivo, exit != 0 sugli errori, reinviare non
altera dati), ma la riga di cron resta **commentata** in
``docs/operazioni-inquilini.md``.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Invia il riepilogo addebiti agli inquilini "
        "(senza --invia è una prova a vuoto)."
    )

    def add_arguments(self, parser):
        from billing.calc.riepilogo import GIORNI_PENDENTI

        parser.add_argument(
            "--property",
            type=str,
            default=None,
            help="Immobile (id, nome o slug). Senza, elabora tutti gli immobili.",
        )
        parser.add_argument(
            "--invia",
            action="store_true",
            default=False,
            help="Invia davvero le email (senza, è un dry-run).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Accettato per simmetria: il dry-run è già il default.",
        )
        parser.add_argument(
            "--tenant",
            type=int,
            default=None,
            metavar="ID",
            help=(
                "Limita a un singolo inquilino (id del profilo). Restringe "
                "l'elenco, non forza l'invio: un ex inquilino resta escluso."
            ),
        )
        parser.add_argument(
            "--escludi",
            type=str,
            default="",
            metavar="ID,ID",
            help="Id inquilini da NON notificare, separati da virgola.",
        )
        parser.add_argument(
            "--giorni",
            type=int,
            default=GIORNI_PENDENTI,
            metavar="N",
            help=(
                "Finestra dei pendenti: voci scadute o in scadenza entro N "
                f"giorni (default {GIORNI_PENDENTI})."
            ),
        )

    def handle(self, *args, **options):
        from properties.models import Property

        from billing.calc.riepilogo import invia_riepiloghi

        dry_run = not options["invia"]
        giorni = options["giorni"]
        if giorni < 0:
            raise CommandError("--giorni non può essere negativo.")

        try:
            escludi = [
                int(x) for x in (options["escludi"] or "").split(",") if x.strip()
            ]
        except ValueError as e:
            raise CommandError("--escludi vuole id numerici separati da virgola.") from e

        tenant_ids = [options["tenant"]] if options["tenant"] else None

        if options.get("property"):
            # `resolve_property_cli` solleva con più immobili quando il valore
            # manca: qui lo usiamo SOLO per risolvere un valore esplicito.
            from properties.context import resolve_property_cli

            try:
                properties = [resolve_property_cli(options["property"])]
            except ValueError as e:
                raise CommandError(str(e)) from e
        else:
            properties = list(Property.objects.all().order_by("nome"))
            if not properties:
                raise CommandError("Nessun immobile nel sistema.")

        errori_totali = 0
        for prop in properties:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(f"[{prop.nome}]"))
            risultato = invia_riepiloghi(
                prop,
                dry_run=dry_run,
                escludi_ids=escludi,
                giorni=giorni,
                tenant_ids=tenant_ids,
            )
            self._stampa(risultato)
            errori_totali += risultato["errori"]

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: nessuna email inviata. "
                    "Per inviare davvero aggiungi --invia."
                )
            )
        elif errori_totali:
            raise CommandError(
                f"{errori_totali} invii falliti (dettagli qui sopra e nel "
                "registro comunicazioni)."
            )

    def _stampa(self, risultato: dict) -> None:
        if not risultato["riepiloghi"]:
            self.stdout.write("  nessun inquilino da riepilogare")
            return
        for r in risultato["riepiloghi"]:
            canone = (
                f"canone {r['canone']['residuo']:.2f}€"
                if r["canone"]
                else "senza canone"
            )
            badge = " [ex inquilino]" if r["uscito"] else ""
            self.stdout.write(
                f"  {r['tenant_nominativo']}{badge} · "
                f"{r['email'] or '(nessuna email)'} · {canone} · "
                f"{len(r['pendenti'])} pendenti · {r.get('esito', '-')}"
            )
            if r.get("errore"):
                self.stdout.write(self.style.ERROR(f"      {r['errore']}"))
        self.stdout.write(
            f"  → {risultato['totale']} riepiloghi, "
            f"{risultato['inviati']} inviati, {risultato['errori']} errori, "
            f"{risultato['push_inviate']} push"
        )
        if risultato.get("ex_inquilini"):
            self.stdout.write(
                f"  non sollecitati perché senza assegnazione attiva "
                f"({len(risultato['ex_inquilini'])}): "
                f"{', '.join(risultato['ex_inquilini'])}"
            )
        if risultato["senza_email"]:
            self.stdout.write(
                self.style.WARNING(
                    f"  senza email: {', '.join(risultato['senza_email'])}"
                )
            )
