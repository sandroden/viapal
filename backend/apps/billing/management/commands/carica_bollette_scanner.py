"""Carica le bollette PDF presenti in una cartella (default ~/scanner) come
UtilityBill dell'immobile indicato.

Strategia: il nome file serve come `numero_fattura` (=basename, per
idempotenza) e come *ripiego* per il prodotto (`utenze-<immobile>-(luce|gas|
acqua)-...`). Tutto il resto — prodotto, importo, periodo, data emissione,
consumo, fornitore — viene estratto direttamente dal PDF tramite la funzione
`estrai_da_pdf` di ``riparsa_bollette_pdf``: il PDF vince sul nome file, che
in archivio si è già rivelato sbagliato (bollette gas chiamate "luce").

Per "rodare" il flusso senza alterare i Receivable degli inquilini:
le UtilityBill sono entità separate dal calcolo dei conguagli (che si basa
sui totali del UtilityChargePeriod), quindi caricarle qui crea solo
l'Expense lato proprietario, non tocca le quote inquilini.
"""
import datetime
import re
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from billing.management.commands.riparsa_bollette_pdf import estrai_da_pdf
from billing.models import Supplier, UtilityBill
from properties.models import OwnerProfile

# Pattern ampio: cattura il prodotto (gas/luce/acqua) ovunque appaia dopo il
# token dell'immobile (`utenze-mz-`, `utenze-nova-`, …), tollerante anche a `_`
# come separatore. Serve solo come ripiego se il PDF non dice il prodotto.
PATTERN = re.compile(
    r"^utenze[-_].*?(?P<prodotto>luce|gas|acqua)[-_].*\.pdf$",
    re.IGNORECASE,
)
# Token dell'immobile: la prima parola dopo `utenze-` (`mz`, `nova`, …), a meno
# che sia il prodotto (nell'archivio storico esistono anche `utenze-gas-mz-…`).
PATTERN_IMMOBILE = re.compile(
    r"^utenze[-_](?!luce|gas|acqua)(?P<token>[a-z0-9]+)[-_]", re.IGNORECASE
)


def _ultimo_giorno_mese(d: datetime.date) -> datetime.date:
    if d.month == 12:
        return datetime.date(d.year + 1, 1, 1) - datetime.timedelta(days=1)
    return datetime.date(d.year, d.month + 1, 1) - datetime.timedelta(days=1)


def _supplier(nome: str, immobile) -> Supplier:
    """Fornitore dell'immobile con quel nome, creandolo se non esiste
    (``Supplier.property`` è obbligatoria: i fornitori non sono condivisi
    tra immobili)."""
    sup = Supplier.objects.filter(property=immobile, nome__iexact=nome).first()
    if sup is None:
        sup = Supplier.objects.create(
            property=immobile, nome=nome, tipo=Supplier.TipoFornitore.ALTRO,
        )
    return sup


class Command(BaseCommand):
    help = (
        "Carica le bollette PDF (utenze-*) presenti in ~/scanner come "
        "UtilityBill, leggendo i metadati direttamente dal PDF. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cartella",
            default=str(Path.home() / "scanner"),
            help="Cartella sorgente (default ~/scanner).",
        )
        parser.add_argument(
            "--glob", default="utenze-*.pdf",
            help=(
                "Glob dei file da caricare (default 'utenze-*.pdf'). Con più "
                "immobili restringerlo, es. 'utenze-nova-*.pdf'."
            ),
        )
        parser.add_argument(
            "--mesi", type=int, default=None,
            help="Solo file con periodo_da negli ultimi N mesi (default tutti).",
        )
        parser.add_argument(
            "--owner-id", type=int, required=True,
            help="ID OwnerProfile da assegnare a pagata_da_owner.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Mostra cosa verrebbe fatto senza scrivere nulla.",
        )
        parser.add_argument(
            "--property", type=str, default=None,
            help="Immobile (id, nome o slug). Obbligatorio se ci sono più immobili.",
        )

    def handle(self, *args, **opts):
        cartella = Path(opts["cartella"]).expanduser()
        if not cartella.is_dir():
            raise CommandError(f"Cartella non trovata: {cartella}")

        try:
            owner = OwnerProfile.objects.get(pk=opts["owner_id"])
        except OwnerProfile.DoesNotExist as exc:
            raise CommandError(
                f"OwnerProfile id={opts['owner_id']} non esiste."
            ) from exc

        from properties.context import resolve_property_cli

        try:
            immobile = resolve_property_cli(opts["property"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        soglia = None
        if opts["mesi"]:
            oggi = datetime.date.today()
            anno_s = oggi.year
            mese_s = oggi.month - opts["mesi"]
            while mese_s <= 0:
                mese_s += 12
                anno_s -= 1
            soglia = datetime.date(anno_s, mese_s, 1)

        files = sorted(cartella.glob(opts["glob"]))
        # Guardia multiproprietà: i nomi file portano il token dell'immobile
        # (`utenze-mz-…`, `utenze-nova-…`). Se il glob ne pesca più di uno si
        # finirebbe per caricare le bollette di una casa sull'altra, e
        # l'idempotenza per numero_fattura renderebbe l'errore definitivo.
        token = {
            m.group("token").lower()
            for m in (PATTERN_IMMOBILE.match(p.name) for p in files)
            if m
        }
        if len(token) > 1:
            raise CommandError(
                f"Il glob '{opts['glob']}' pesca bollette di più immobili "
                f"({', '.join(sorted(token))}): restringilo, es. "
                f"--glob 'utenze-{sorted(token)[0]}-*.pdf'."
            )

        creati = aggiornati_pdf = saltati = errori = 0
        self.stdout.write(
            f"Cartella {cartella}, glob '{opts['glob']}', immobile {immobile}"
        )
        for path in files:
            base = path.stem

            existing = UtilityBill.objects.filter(
                numero_fattura=base, immobile=immobile,
            ).first()
            if existing is None:
                altrove = UtilityBill.objects.filter(
                    numero_fattura=base,
                ).exclude(immobile=immobile).first()
                if altrove is not None:
                    self.stdout.write(self.style.ERROR(
                        f"  skip: {base} è già caricata sull'immobile "
                        f"{altrove.immobile} — controlla --glob e --property"
                    ))
                    errori += 1
                    continue

            # Estrai i metadati dal PDF (prodotto, importo, periodo, ecc.)
            dati = estrai_da_pdf(str(path))

            # Prodotto: dal PDF (POD/PDR e voci di spesa), col nome file come
            # ripiego per i template non riconosciuti.
            prodotto = (dati or {}).get("prodotto")
            if not prodotto:
                m = PATTERN.match(path.name)
                if not m:
                    self.stdout.write(self.style.WARNING(
                        f"  skip: prodotto non riconosciuto — {path.name}"
                    ))
                    saltati += 1
                    continue
                prodotto = m.group("prodotto").lower()

            if existing:
                # Già presente: aggiorna solo file_pdf se mancante.
                # Il riparsing dei metadati è compito di
                # `riparsa_bollette_pdf`, non di questo command.
                if not existing.file_pdf:
                    if not opts["dry_run"]:
                        with path.open("rb") as fh:
                            existing.file_pdf.save(path.name, File(fh), save=True)
                    aggiornati_pdf += 1
                    self.stdout.write(f"  pdf+ {base}")
                else:
                    saltati += 1
                continue

            # Nuovo: crea con metadati dal PDF + fallback ragionevoli
            if not dati or dati.get("importo") is None:
                self.stdout.write(self.style.WARNING(
                    f"  skip: PDF non riconosciuto — {base}"
                ))
                errori += 1
                continue

            periodo_da = dati["periodo_da"]
            periodo_a = dati["periodo_a"] or (
                _ultimo_giorno_mese(periodo_da) if periodo_da else None
            )
            if not periodo_da:
                self.stdout.write(self.style.WARNING(
                    f"  skip: periodo non trovato — {base}"
                ))
                errori += 1
                continue
            if soglia and periodo_da < soglia:
                continue

            data_emiss = dati["data_emissione"] or periodo_a or periodo_da

            supplier = _supplier(dati["fornitore"] or "Sconosciuto", immobile)

            if opts["dry_run"]:
                self.stdout.write(
                    f"  + {base}  prod={prodotto}  importo={dati['importo']}  "
                    f"periodo={periodo_da}/{periodo_a}  forn={supplier.nome}  "
                    f"consumo={dati.get('consumo')}"
                )
            else:
                bill = UtilityBill.objects.create(
                    immobile=immobile,
                    supplier=supplier,
                    prodotto=prodotto,
                    numero_fattura=base,
                    data_emissione=data_emiss,
                    periodo_da=periodo_da,
                    periodo_a=periodo_a,
                    importo_totale=dati["importo"],
                    consumo=dati.get("consumo"),
                    pagata_da_owner=owner,
                )
                with path.open("rb") as fh:
                    bill.file_pdf.save(path.name, File(fh), save=True)
                self.stdout.write(self.style.SUCCESS(f"  + {base}"))
            creati += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Creati: {creati}  PDF aggiornati: {aggiornati_pdf}  "
            f"Saltati: {saltati}  Non riconosciuti/errori: {errori}"
        ))
