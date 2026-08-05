"""Carica sull'immobile i modelli HTML dei documenti generabili.

Il testo dei documenti è un dato (``DocumentTemplate``, uno per immobile) e
nel repository restano solo gli **esempi** (``properties/documenti/esempi/``).
Finché il modello non è caricato il documento non si genera e la cosa compare
fra i dati mancanti. Da interfaccia si fa con Immobile → Modelli documenti
→ "Scarica l'esempio"; questo comando è la stessa cosa in un passo
solo, per la prima configurazione di un immobile.

Idempotente: un modello già presente non viene toccato, perché la copia in
tabella è quella che il proprietario ha adattato e non deve seguire le
modifiche successive all'esempio nel repository. Per sovrascriverla serve
``--force``, che è una decisione esplicita.
"""
from django.core.management.base import BaseCommand, CommandError

from properties.context import resolve_property_cli
from properties.documenti import GENERATORI, esempio
from properties.models import DocumentTemplate


class Command(BaseCommand):
    help = "Carica i modelli documento di esempio su un immobile."

    def add_arguments(self, parser):
        parser.add_argument(
            "--property",
            help="Immobile: id, nome o slug. Obbligatorio se ce n'è più d'uno.",
        )
        parser.add_argument(
            "--codice",
            action="append",
            choices=sorted(GENERATORI),
            help="Solo questo documento (ripetibile). Default: tutti.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sovrascrive il corpo dei modelli già presenti con l'esempio.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra solo cosa farebbe, senza salvare.",
        )

    def handle(self, *args, **options):
        try:
            immobile = resolve_property_cli(options["property"])
        except ValueError as errore:
            raise CommandError(str(errore)) from errore

        codici = options["codice"] or sorted(GENERATORI)
        prefisso = "[DRY-RUN] " if options["dry_run"] else ""

        for codice in codici:
            modello = DocumentTemplate.objects.filter(
                property=immobile, codice=codice
            ).first()
            titolo = GENERATORI[codice].titolo

            if modello and not options["force"]:
                self.stdout.write(f"{prefisso}= già presente: {titolo}")
                continue

            azione = "sovrascritto" if modello else "caricato"
            if not options["dry_run"]:
                DocumentTemplate.objects.update_or_create(
                    property=immobile,
                    codice=codice,
                    defaults={"corpo_html": esempio(codice)},
                )
            self.stdout.write(self.style.SUCCESS(f"{prefisso}+ {azione}: {titolo}"))

        self.stdout.write(
            f"{prefisso}Immobile: {immobile} (id {immobile.pk}). "
            "Il testo va poi adattato da Immobile → Modelli documenti."
        )
