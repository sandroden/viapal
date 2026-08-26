"""Rimette al loro posto i documenti dell'immobile caricati male.

``PropertyDocument`` ha una sola tabella e una FK ``contract`` nullable: il
documento agganciato a un contratto compare sulla riga del contratto, quello
senza compare fra i documenti generali della casa. Finché il tipo non
diceva nulla sull'ambito, lo stesso documento è finito due volte in archivio
— una copia sotto il contratto e una fra i generali — e i file caricati dal
riquadro del contratto hanno preso il tipo indovinato dal nome, spesso
sbagliato.

Questo command applica una lista CHIUSA di correzioni decise caso per caso,
nello stile di ``sana_incassi_senza_incassante``:

  * **Idempotente**: ogni caso controlla lo stato attuale prima di scrivere;
    rilanciarlo non fa nulla.
  * **Fail-safe sul replay in prod**: il record è cercato per frammento di
    nome file, non per id, e ogni caso verifica il tipo che si aspetta di
    trovare. Se qualcosa diverge il caso viene SALTATO con un warning.
  * **La descrizione non si perde**: il doppione da rimuovere spesso è
    quello che porta la descrizione scritta a mano; prima di eliminarlo la
    descrizione passa al gemello che resta.

Il file su storage non viene toccato: ``delete()`` di Django rimuove solo la
riga. Un file orfano non fa danno, un file cancellato per errore sì.

Alla fine elenca i documenti di tipo contrattuale rimasti senza contratto:
sono quelli che la validazione ora rifiuta e che vanno agganciati a mano.

Uso::

    uv run manage.py sistema_documenti_immobile            # dry-run
    uv run manage.py sistema_documenti_immobile --apply
"""
from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from properties.models import PropertyDocument


@dataclass
class CorreggiTipo:
    """Il tipo indovinato dal nome del file era sbagliato."""

    file_contiene: str
    tipo_attuale: str
    tipo_nuovo: str
    perche: str

    def descrivi(self):
        return f"{self.file_contiene}: {self.tipo_attuale} → {self.tipo_nuovo}"


@dataclass
class RimuoviDoppione:
    """Due record per lo stesso documento: resta quello nel posto giusto."""

    file_contiene: str
    """Il doppione da eliminare (quello senza contratto)."""

    gemello_contiene: str
    """Il record da tenere, agganciato al contratto."""

    perche: str

    def descrivi(self):
        return f"{self.file_contiene}: doppione di {self.gemello_contiene}"


# I file di Via Palestrina, marzo 2026: la lettera di accompagnamento e il
# contratto firmato erano stati caricati due volte, una per posto.
CASI = [
    CorreggiTipo(
        file_contiene="lettera-accompagnamento_",
        tipo_attuale=PropertyDocument.Tipo.ALTRO,
        tipo_nuovo=PropertyDocument.Tipo.SIDE_LETTER,
        perche="la lettera di accompagnamento è la side letter del contratto",
    ),
    CorreggiTipo(
        file_contiene="registrazone-contratto-agenzia-entrate",
        tipo_attuale=PropertyDocument.Tipo.CONTRATTO,
        tipo_nuovo=PropertyDocument.Tipo.REGISTRAZIONE_CONTRATTO,
        perche="è la ricevuta di registrazione, non il contratto",
    ),
    CorreggiTipo(
        file_contiene="Regolamento_di_Convivenza",
        tipo_attuale=PropertyDocument.Tipo.ALTRO,
        tipo_nuovo=PropertyDocument.Tipo.REGOLE_CONVIVENZA,
        perche="ora le regole di convivenza hanno un tipo proprio",
    ),
    RimuoviDoppione(
        file_contiene="contratto-2025-firmato.pdf",
        gemello_contiene="contratto-2025-firmato_",
        perche="stesso contratto firmato, caricato due volte",
    ),
    RimuoviDoppione(
        file_contiene="lettera-accompagnamento.pdf",
        gemello_contiene="lettera-accompagnamento_",
        perche="stessa lettera, caricata due volte",
    ),
]


class Command(BaseCommand):
    help = "Corregge tipo e doppioni dei documenti immobile (lista chiusa)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive le correzioni; senza, mostra soltanto cosa farebbe.",
        )

    def handle(self, *args, **opzioni):
        applica = opzioni["apply"]
        if not applica:
            self.stdout.write(self.style.WARNING("DRY-RUN — niente viene scritto.\n"))

        fatti = saltati = 0
        with transaction.atomic():
            for caso in CASI:
                esito = (
                    self._correggi_tipo(caso, applica)
                    if isinstance(caso, CorreggiTipo)
                    else self._rimuovi_doppione(caso, applica)
                )
                if esito:
                    fatti += 1
                else:
                    saltati += 1
            if not applica:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(f"Casi applicati: {fatti} · saltati: {saltati}")
        self._segnala_orfani()
        self._segnala_invisibili()

    # ------------------------------------------------------------------
    # Casi
    # ------------------------------------------------------------------

    def _trova(self, frammento, esclusi=()):
        """Il documento il cui file contiene il frammento, o None.

        Con più di un match non sceglie: preferisce non fare nulla.
        """
        trovati = [
            d
            for d in PropertyDocument.objects.filter(file__contains=frammento)
            if d.pk not in esclusi
        ]
        if len(trovati) != 1:
            return None, len(trovati)
        return trovati[0], 1

    def _correggi_tipo(self, caso, applica):
        doc, quanti = self._trova(caso.file_contiene)
        if doc is None:
            self._salta(caso, f"{quanti} documenti col nome atteso")
            return False
        if doc.tipo == caso.tipo_nuovo:
            self._salta(caso, "già corretto", livello="nota")
            return False
        if doc.tipo != caso.tipo_attuale:
            self._salta(caso, f"tipo inatteso: {doc.tipo}")
            return False

        self.stdout.write(f"  [{doc.pk}] {caso.descrivi()} — {caso.perche}")
        if applica:
            doc.tipo = caso.tipo_nuovo
            doc.save(update_fields=["tipo", "updated_at"])
        return True

    def _rimuovi_doppione(self, caso, applica):
        doc, quanti = self._trova(caso.file_contiene)
        if doc is None:
            self._salta(caso, f"{quanti} documenti col nome atteso", livello="nota")
            return False
        if doc.contract_id:
            self._salta(caso, "è agganciato a un contratto: non è il doppione")
            return False

        gemello, quanti_g = self._trova(caso.gemello_contiene, esclusi={doc.pk})
        if gemello is None:
            self._salta(caso, f"gemello non identificato ({quanti_g} match)")
            return False
        if not gemello.contract_id:
            self._salta(caso, "il gemello non è agganciato a nessun contratto")
            return False

        self.stdout.write(
            f"  [{doc.pk}] {caso.descrivi()} → resta [{gemello.pk}] "
            f"su «{gemello.contract}» — {caso.perche}"
        )
        # La descrizione scritta a mano sta quasi sempre sul doppione: senza
        # questo travaso la si perderebbe insieme al record.
        if doc.descrizione and not gemello.descrizione:
            self.stdout.write(f"        descrizione «{doc.descrizione}» → gemello")
            if applica:
                gemello.descrizione = doc.descrizione
                gemello.save(update_fields=["descrizione", "updated_at"])
        if applica:
            doc.delete()
        return True

    def _salta(self, caso, motivo, livello="warning"):
        stile = self.style.WARNING if livello == "warning" else self.style.SUCCESS
        self.stdout.write(stile(f"  SALTO {caso.descrivi()} — {motivo}"))

    # ------------------------------------------------------------------
    # Diagnosi finale
    # ------------------------------------------------------------------

    def _segnala_orfani(self):
        orfani = PropertyDocument.objects.filter(
            tipo__in=PropertyDocument.TIPI_CONTRATTUALI, contract__isnull=True
        ).select_related("property")
        if not orfani:
            self.stdout.write(
                self.style.SUCCESS("Nessuna carta di contratto senza contratto.")
            )
            return
        self.stdout.write(
            self.style.WARNING(
                "\nCarte di contratto ancora senza contratto "
                "(da agganciare a mano dalla scheda Immobile):"
            )
        )
        for d in orfani:
            self.stdout.write(
                f"  [{d.pk}] {d.property.nome} · {d.get_tipo_display()} · "
                f"{d.descrizione or d.file.name}"
            )

    def _segnala_invisibili(self):
        """Documenti «visibili agli inquilini» che nessun inquilino vede.

        Un documento agganciato a un contratto lo vede solo chi ha
        un'assegnazione **sotto quel contratto**
        (``PropertyDocumentViewSet.get_queryset``). Se nessuna assegnazione
        punta a quel contratto — è il caso quando il collegamento
        assegnazione↔contratto non è mai stato compilato — la spunta
        «visibile agli inquilini» resta accesa senza effetto, e il documento
        sparisce dalla loro pagina senza che nulla lo dica.
        """
        from properties.models import RoomAssignment

        muti = []
        for d in PropertyDocument.objects.filter(
            visibile_inquilini=True, contract__isnull=False
        ).select_related("contract", "property"):
            if not RoomAssignment.objects.filter(contract_id=d.contract_id).exists():
                muti.append(d)
        if not muti:
            return
        self.stdout.write(
            self.style.WARNING(
                "\nSpuntati «visibili agli inquilini» ma invisibili: nessuna "
                "assegnazione è collegata al loro contratto."
            )
        )
        for d in muti:
            self.stdout.write(
                f"  [{d.pk}] {d.get_tipo_display()} · su «{d.contract}» · "
                f"{d.descrizione or d.file.name}"
            )
        self.stdout.write(
            "  Rimedio: collegare le assegnazioni al contratto "
            "(RoomAssignment.contract), non staccare il documento."
        )
