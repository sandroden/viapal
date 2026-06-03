"""Carica le bollette PDF di Monza presenti in ~/scanner come UtilityBill.

Strategia: il **nome file** serve solo per identificare il prodotto
(`utenze-mz-(luce|gas|acqua)-...`) e come `numero_fattura` (=basename, per
idempotenza). Tutto il resto — importo, periodo, data emissione, consumo,
fornitore — viene estratto direttamente dal PDF tramite la funzione
`estrai_da_pdf` di ``riparsa_bollette_pdf``.

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

# Pattern ampio: cattura il prodotto (gas/luce/acqua) ovunque appaia dopo
# `utenze-mz-`, tollerante anche a `_` come separatore. Tutto il resto del
# nome è ignorato — i metadati arrivano dal PDF.
PATTERN = re.compile(
    r"^utenze[-_]mz[-_].*?(?P<prodotto>luce|gas|acqua)[-_].*\.pdf$",
    re.IGNORECASE,
)


def _ultimo_giorno_mese(d: datetime.date) -> datetime.date:
    if d.month == 12:
        return datetime.date(d.year + 1, 1, 1) - datetime.timedelta(days=1)
    return datetime.date(d.year, d.month + 1, 1) - datetime.timedelta(days=1)


def _supplier_default() -> Supplier:
    sup, _ = Supplier.objects.get_or_create(
        nome="Sconosciuto",
        defaults={"tipo": Supplier.TipoFornitore.ALTRO},
    )
    return sup


class Command(BaseCommand):
    help = (
        "Carica le bollette PDF (utenze-mz-*) presenti in ~/scanner come "
        "UtilityBill, leggendo i metadati direttamente dal PDF. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cartella",
            default=str(Path.home() / "scanner"),
            help="Cartella sorgente (default ~/scanner).",
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

        from properties.models import Property

        immobile = Property.objects.first()

        soglia = None
        if opts["mesi"]:
            oggi = datetime.date.today()
            anno_s = oggi.year
            mese_s = oggi.month - opts["mesi"]
            while mese_s <= 0:
                mese_s += 12
                anno_s -= 1
            soglia = datetime.date(anno_s, mese_s, 1)

        creati = aggiornati_pdf = saltati = errori = 0
        for path in sorted(cartella.glob("utenze-mz-*.pdf")):
            m = PATTERN.match(path.name)
            if not m:
                self.stdout.write(self.style.WARNING(
                    f"  skip: prodotto non riconosciuto — {path.name}"
                ))
                saltati += 1
                continue
            prodotto = m.group("prodotto").lower()
            base = path.stem

            existing = UtilityBill.objects.filter(numero_fattura=base).first()

            # Estrai i metadati dal PDF (importo, periodo, ecc.)
            dati = estrai_da_pdf(str(path))

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

            nome_forn = dati["fornitore"]
            if nome_forn:
                supplier, _ = Supplier.objects.get_or_create(
                    nome=nome_forn,
                    defaults={"tipo": Supplier.TipoFornitore.ALTRO},
                )
            else:
                supplier = _supplier_default()

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
