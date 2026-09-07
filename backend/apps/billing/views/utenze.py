"""
ViewSet e view sulle utenze: periodi, bollette, costi annuali, servizi, vista inquilino.
"""
import datetime
from decimal import Decimal, InvalidOperation

from accounts.permissions import (
    IsInquilino,
    IsPropertyMember,
)
from django.db.models import F, Q
from properties.context import get_request_property
from properties.views import ProtectedDestroyMixin
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from billing.models import (
    AnnualUtilityCost,
    PropertyUtilityService,
    Receivable,
    UtilityBill,
    UtilityChargePeriod,
)
from billing.serializers import (
    AnnualUtilityCostSerializer,
    PropertyUtilityServiceSerializer,
    UtilityBillSerializer,
    UtilityChargePeriodSerializer,
)


class UtilityChargePeriodViewSet(ReadOnlyModelViewSet):
    """Periodi utenze. Solo proprietari.

    Oltre a lista/dettaglio espone il flusso di **emissione utenze**:

    - ``GET  per-mese?anno=&mese=`` : trova-o-crea il periodo del mese e ne
      riporta la completezza (voci attese presenti/mancanti).
    - ``GET  {id}/anteprima``       : dry-run della ripartizione (conto per
      inquilino), nessuna scrittura.
    - ``POST {id}/emetti``          : persiste i Receivable utenze e porta il
      periodo a stato 'inviato'.
    """

    serializer_class = UtilityChargePeriodSerializer
    permission_classes = [IsPropertyMember]
    queryset = UtilityChargePeriod.objects.all().order_by("-periodo_da")

    # Ordine fisso di presentazione delle voci (indipendente dall'ordine
    # con cui sono state configurate in PropertyUtilityService).
    _ORDINE_VOCI = ["luce", "gas", "acqua", "tari"]

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _completezza(self, period) -> dict:
        """Quali voci sono attese per il periodo e quali sono presenti.

        Le voci attese si leggono da ``PropertyUtilityService``: quelle con
        ``gestione=proprieta``, nell'ordine luce/gas/acqua/tari. L'assenza di
        una riga per una voce significa che quella voce non esiste per
        questa casa (es. TARI a carico dell'inquilino) e quindi non è
        richiesta per la completezza. Se l'immobile non ha ancora nessuna
        riga di configurazione (fallback storico) le attese restano
        luce+gas+tari come nel comportamento precedente.

        ``completo`` = tutte le voci attese **a bolletta** (luce/gas/acqua,
        non la TARI: costo annuale spalmato, non bloccante) sono presenti;
        se non ci sono attese a bolletta, è vero per definizione.

        Le chiavi legacy ``luce``/``gas``/``tari`` restano sempre presenti
        nel risultato (retrocompatibilità); ``acqua`` compare solo se tra
        le voci attese. ``attese`` è la lista ordinata delle voci attese,
        per rendere il frontend data-driven.
        """
        from billing.models import AnnualUtilityCost

        rows = PropertyUtilityService.objects.filter(property_id=period.property_id)
        gestite_da_proprieta = {
            row.voce
            for row in rows
            if row.gestione == PropertyUtilityService.Gestione.PROPRIETA
        }
        if rows:
            attese = [v for v in self._ORDINE_VOCI if v in gestite_da_proprieta]
        else:
            attese = ["luce", "gas", "tari"]

        bills = UtilityBill.objects.filter(
            immobile_id=period.property_id,
            periodo_da__lte=period.periodo_a,
            periodo_a__gte=period.periodo_da,
        )
        presenza = {
            "luce": bills.filter(prodotto=UtilityBill.Prodotto.LUCE).exists(),
            "gas": bills.filter(prodotto=UtilityBill.Prodotto.GAS).exists(),
            "acqua": bills.filter(prodotto=UtilityBill.Prodotto.ACQUA).exists(),
            "tari": (
                AnnualUtilityCost.objects.filter(
                    property_id=period.property_id,
                    voce=AnnualUtilityCost.VoceAnnuale.TARI,
                    valid_from__lte=period.periodo_a,
                )
                .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=period.periodo_da))
                .exists()
            ),
        }

        attese_bolletta = [v for v in attese if v != "tari"]
        completo = all(presenza[v] for v in attese_bolletta) if attese_bolletta else True

        risultato = {
            "luce": presenza["luce"],
            "gas": presenza["gas"],
            "tari": presenza["tari"],
            "completo": completo,
            "attese": attese,
        }
        if "acqua" in attese:
            risultato["acqua"] = presenza["acqua"]
        return risultato

    def _mese_default(self) -> tuple[int, int]:
        """Mese di partenza proposto, ragionando sugli **avvisi**.

        Si guarda l'ultimo periodo con addebiti utenze emessi:

        - se gli avvisi non sono ancora stati inviati (``avvisi_inviati_at``
          nullo), si atterra su **quel** mese: c'è ancora lavoro da fare lì;
        - altrimenti si propone il mese successivo (nuovo periodo da avviare).

        Se non esiste alcun Receivable utenze, fallback al mese corrente.
        """
        ultimo = (
            Receivable.objects.filter(
                assignment__room__property=get_request_property(self.request),
                causale=Receivable.Causale.UTENZE,
                utility_period__isnull=False,
            )
            .select_related("utility_period")
            .order_by("-utility_period__periodo_a")
            .first()
        )
        if ultimo is None:
            oggi = datetime.date.today()
            return oggi.year, oggi.month

        period = ultimo.utility_period
        if period.avvisi_inviati_at is None:
            # Addebito emesso ma avvisi non ancora inviati: si parte da qui.
            return period.periodo_da.year, period.periodo_da.month

        # Avvisi già inviati: si propone il mese successivo.
        base = period.periodo_a
        anno = base.year + (1 if base.month == 12 else 0)
        mese = 1 if base.month == 12 else base.month + 1
        return anno, mese

    @action(detail=False, methods=["get"], url_path="per-mese")
    def per_mese(self, request):
        """Trova o crea il periodo utenze del mese.

        ``anno`` e ``mese`` sono opzionali: se omessi, si usa il mese
        successivo all'ultimo periodo con addebiti utenze emessi.
        """
        import calendar

        ha_anno = "anno" in request.query_params
        ha_mese = "mese" in request.query_params
        if not ha_anno and not ha_mese:
            anno, mese = self._mese_default()
        else:
            try:
                anno = int(request.query_params["anno"])
                mese = int(request.query_params["mese"])
            except (KeyError, ValueError, TypeError):
                return Response(
                    {"detail": "Parametri 'anno' e 'mese' obbligatori (interi)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if not (1 <= mese <= 12):
            return Response(
                {"detail": "Mese fuori range (1-12)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        primo = datetime.date(anno, mese, 1)
        ultimo = datetime.date(anno, mese, calendar.monthrange(anno, mese)[1])

        from properties.context import get_request_property

        prop = get_request_property(request)

        # periodo esistente che copre (anche parzialmente) il mese richiesto:
        # evita di creare doppioni su periodi bimestrali già presenti.
        period = (
            UtilityChargePeriod.objects.filter(
                property=prop, periodo_da__lte=ultimo, periodo_a__gte=primo
            )
            .order_by("periodo_da")
            .first()
        )
        created = False
        if period is None:
            period = UtilityChargePeriod.objects.create(
                property=prop, periodo_da=primo, periodo_a=ultimo
            )
            created = True

        return Response(
            {
                "period": self.get_serializer(period).data,
                "created": created,
                "completezza": self._completezza(period),
                "anno": anno,
                "mese": mese,
            }
        )

    @action(detail=True, methods=["get"], url_path="anteprima")
    def anteprima(self, request, pk=None):
        """Dry-run della ripartizione: conto per inquilino, nessuna scrittura.

        ``?forza=1``: calcola anche un periodo senza bollette luce/gas
        (ripartizione parziale, es. sola TARI).
        """
        from billing.calc.utility import calcola_conguaglio_periodo

        period = self.get_object()
        forza = request.query_params.get("forza") in ("1", "true")
        risultato = calcola_conguaglio_periodo(
            period.id, persist=False, forza_senza_bollette=forza
        )
        risultato["completezza"] = self._completezza(period)
        return Response(risultato)

    @action(detail=True, methods=["post"], url_path="emetti")
    def emetti(self, request, pk=None):
        """Persiste i Receivable utenze e porta il periodo a 'inviato'.

        Body JSON: ``{"forza": true}`` per emettere anche un periodo
        incompleto (manca luce o gas: fornitori con cadenza diversa, bolletta
        non disponibile, utenze intestate all'inquilino). La ripartizione è
        parziale: copre solo le voci presenti.
        """
        from billing.calc.utility import calcola_conguaglio_periodo

        period = self.get_object()
        forza = bool(request.data.get("forza", False))
        comp = self._completezza(period)
        if not comp["completo"] and not forza:
            mancanti = [
                v
                for v in comp.get("attese", ["luce", "gas"])
                if v != "tari" and not comp.get(v)
            ]
            return Response(
                {
                    "detail": "Periodo incompleto: mancano bollette per "
                    f"{', '.join(mancanti)}. Con 'forza' si emette comunque "
                    "la ripartizione parziale.",
                    "completezza": comp,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        risultato = calcola_conguaglio_periodo(
            period.id, persist=True, forza_senza_bollette=forza
        )
        if risultato.get("skipped"):
            return Response(
                {
                    "detail": "Niente da ripartire nel periodo: nessuna "
                    "bolletta né costo annuale attribuibile.",
                    "completezza": comp,
                    "skipped": risultato["skipped"],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        period.refresh_from_db()
        if period.stato != UtilityChargePeriod.StatoPeriodo.INVIATO:
            period.stato = UtilityChargePeriod.StatoPeriodo.INVIATO
            if not period.data_invio:
                period.data_invio = datetime.date.today()
            period.save(update_fields=["stato", "data_invio"])

        risultato["period"] = self.get_serializer(period).data
        return Response(risultato)

    @action(detail=True, methods=["post"], url_path="esclusione-tari")
    def esclusione_tari(self, request, pk=None):
        """Imposta la quota di TARI a carico della proprietà per il periodo.

        Body JSON: ``{"quota_esclusa": "12.00", "motivo": "Stanza 3 sfitta"}``.

        È l'equivalente della ``quota_esclusa`` delle bollette, ma sul mese:
        lo sfitto è un fatto mensile (una stanza vuota a marzo, piena ad
        aprile), quindi il valore vive sul periodo e non sul costo annuale.

        Su un periodo già emesso la modifica è ammessa — come per le bollette
        — ma **non tocca i Receivable già creati**: restano la verità
        contabile finché non si rigenera il periodo. Il frontend lo dice
        esplicitamente dopo il salvataggio.
        """
        from billing.calc.utility import _raccoglie_voci_annual

        period = self.get_object()

        grezzo = request.data.get("quota_esclusa", 0)
        try:
            quota = Decimal(str(grezzo if grezzo not in ("", None) else 0))
        except (InvalidOperation, ValueError):
            return Response(
                {"quota_esclusa": "Valore non numerico."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if quota < 0:
            return Response(
                {"quota_esclusa": "La quota esclusa non può essere negativa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tetto: la TARI lorda del mese. Non è un campo del periodo ma un
        # calcolo (importo annuale / 12 × mesi coperti), quindi il controllo
        # sta qui e non nel clean() del modello.
        tari_lorda = _raccoglie_voci_annual(
            period.property_id, period.periodo_da, period.periodo_a
        ).get("tari", Decimal("0.00"))
        if quota > tari_lorda:
            return Response(
                {
                    "quota_esclusa": "La quota esclusa non può superare la TARI "
                    f"del periodo ({tari_lorda:.2f} €)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        period.quota_esclusa_tari = quota
        period.motivo_esclusione_tari = (
            (request.data.get("motivo") or "")[:200] if quota > 0 else ""
        )
        period.save(update_fields=["quota_esclusa_tari", "motivo_esclusione_tari"])
        return Response(
            {
                "period": self.get_serializer(period).data,
                "tari_lorda": tari_lorda.quantize(Decimal("0.01")),
            }
        )

    @action(detail=True, methods=["post"], url_path="invia-avvisi")
    def invia_avvisi(self, request, pk=None):
        """Invia (o simula con ``dry_run``) gli avvisi utenze agli inquilini.

        Body JSON: ``{"dry_run": true|false}`` (default ``true``).
        Con ``dry_run`` mostra il testo esatto delle email senza inviare nulla,
        così lo si approva prima dell'invio reale.
        """
        from billing.calc.avvisi import invia_avvisi_utenze

        period = self.get_object()
        dry_run = bool(request.data.get("dry_run", True))
        escludi = request.data.get("escludi") or []
        risultato = invia_avvisi_utenze(period, dry_run=dry_run, escludi_ids=escludi)
        return Response(risultato)


class UtilityBillViewSet(ModelViewSet):
    """Bollette utenze. Solo proprietari.

    Upload (POST) richiede solo ``file_pdf`` + ``pagata_da_owner``: tutti
    gli altri campi (prodotto, importo, periodo, data emissione, consumo,
    fornitore) vengono estratti dal PDF (template Acea/Wind3, Enel, Iren e
    Magis riconosciuti). Idempotente per ``numero_fattura`` (= basename).

    Per gli script CLI accetta anche autenticazione HTTP Basic in aggiunta
    alla session.
    """

    serializer_class = UtilityBillSerializer
    permission_classes = [IsPropertyMember]
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = UtilityBill.objects.select_related("supplier", "pagata_da_owner").order_by(
        "-data_emissione"
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            immobile=get_request_property(self.request)
        )

    def create(self, request, *args, **kwargs):
        import os
        import tempfile

        from billing.management.commands.riparsa_bollette_pdf import estrai_da_pdf
        from billing.models import Supplier

        file_pdf = request.FILES.get("file_pdf")
        if not file_pdf:
            return Response({"file_pdf": "richiesto"}, status=400)

        pagata_da_owner_id = (
            request.data.get("pagata_da_owner") or request.data.get("pagata_da_owner_id")
        )
        if not pagata_da_owner_id:
            return Response({"pagata_da_owner": "richiesto"}, status=400)

        numero_fattura = (
            request.data.get("numero_fattura")
            or os.path.splitext(os.path.basename(file_pdf.name))[0]
        )

        existing = UtilityBill.objects.filter(numero_fattura=numero_fattura).first()
        if existing:
            return Response(
                {
                    "detail": "Bolletta già presente.",
                    "id": existing.id,
                    "numero_fattura": existing.numero_fattura,
                },
                status=409,
            )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for chunk in file_pdf.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            dati = estrai_da_pdf(tmp_path)
        finally:
            os.unlink(tmp_path)

        if not dati or dati.get("importo") is None:
            return Response(
                {"detail": "Template PDF non riconosciuto: importo non estraibile."},
                status=400,
            )
        if not dati.get("periodo_da") or not dati.get("periodo_a"):
            return Response(
                {"detail": "Template PDF non riconosciuto: periodo non estraibile."},
                status=400,
            )
        prodotto = dati.get("prodotto") or request.data.get("prodotto")
        if not prodotto:
            return Response(
                {"detail": "Prodotto non identificabile dal PDF (passare 'prodotto' nel form)."},
                status=400,
            )

        # Immobile: dal contesto della richiesta (header X-Property-Id o
        # unico immobile dell'utente). Un eventuale id esplicito nel form
        # deve comunque essere accessibile all'utente.
        from properties.context import get_request_property, properties_accessibili

        immobile_id = (
            request.data.get("immobile")
            or request.data.get("property")
            or request.data.get("property_id")
        )
        if immobile_id:
            immobile = properties_accessibili(request.user).filter(pk=immobile_id).first()
            if immobile is None:
                return Response(
                    {"detail": "Nessun accesso a questo immobile."}, status=403,
                )
        else:
            immobile = get_request_property(request)

        nome_forn = dati.get("fornitore") or request.data.get("supplier_nome") or "Sconosciuto"
        supplier = Supplier.objects.filter(property=immobile, nome__iexact=nome_forn).first()
        if not supplier:
            supplier = Supplier.objects.create(
                property=immobile, nome=nome_forn, tipo=Supplier.TipoFornitore.ALTRO,
            )

        file_pdf.seek(0)
        bill = UtilityBill.objects.create(
            immobile=immobile,
            supplier=supplier,
            prodotto=prodotto,
            numero_fattura=numero_fattura,
            data_emissione=dati.get("data_emissione") or dati["periodo_a"],
            periodo_da=dati["periodo_da"],
            periodo_a=dati["periodo_a"],
            importo_totale=dati["importo"],
            consumo=dati.get("consumo"),
            pagata_da_owner_id=pagata_da_owner_id,
            file_pdf=file_pdf,
        )
        serializer = self.get_serializer(bill)
        return Response(serializer.data, status=201)

    @action(detail=False, methods=["get"], url_path="statistiche")
    def statistiche(self, request):
        """Statistiche mensili luce/gas per grafici di andamento costi.

        Restituisce una lista ordinata per anno/mese con consumi, importi e
        prezzo unitario per luce e gas, più i giorni-persona del mese calcolati
        dagli RoomAssignment attivi (non da UtilityChargePeriod.giorni_totali,
        che è la somma dell'intero periodo bimestrale).
        """
        import calendar
        from collections import defaultdict
        from properties.models import RoomAssignment

        MESI_IT = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                   "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]

        prop = get_request_property(request)

        bills = (
            UtilityBill.objects
            .filter(
                immobile=prop,
                consumo__gt=0,
                prodotto__in=[UtilityBill.Prodotto.LUCE, UtilityBill.Prodotto.GAS],
            )
            .annotate(importo_netto=F("importo_totale") - F("quota_esclusa"))
            .order_by("periodo_da")
            .values("periodo_da", "prodotto", "consumo", "importo_netto")
        )

        # Accumula per (anno, mese, prodotto)
        data: dict = defaultdict(lambda: {"luce": None, "gas": None})
        for bill in bills:
            anno = bill["periodo_da"].year
            mese = bill["periodo_da"].month
            key = (anno, mese)
            slot = "luce" if bill["prodotto"] == UtilityBill.Prodotto.LUCE else "gas"
            if data[key][slot] is None:
                data[key][slot] = {"consumo": Decimal("0"), "importo": Decimal("0")}
            data[key][slot]["consumo"] += bill["consumo"]
            # Netto della quota esclusa: il €/kWh misura l'energia, non gli
            # extra una-tantum (canone RAI, allacci...).
            data[key][slot]["importo"] += bill["importo_netto"]

        # RoomAssignment: serve solo valid_from e valid_to per calcolare i
        # giorni-persona del singolo mese (intersezione assegnazione ∩ mese).
        today = datetime.date.today()
        assignments = list(
            RoomAssignment.objects.filter(room__property=prop)
            .exclude(rinunciata=True)
            .values("valid_from", "valid_to")
        )

        def _giorni_persona_mese(first_day, last_day):
            """Somma i giorni di presenza di tutti gli inquilini nel mese."""
            totale = 0
            for a in assignments:
                a_end = a["valid_to"] or today
                overlap_start = max(a["valid_from"], first_day)
                overlap_end = min(a_end, last_day)
                if overlap_end >= overlap_start:
                    totale += (overlap_end - overlap_start).days + 1
            return totale or None

        def _prezzo_unitario(slot):
            if slot is None or slot["consumo"] == 0:
                return None
            return round(float(slot["importo"]) / float(slot["consumo"]), 3)

        result = []
        for (anno, mese) in sorted(data.keys()):
            first_day = datetime.date(anno, mese, 1)
            last_day = datetime.date(anno, mese, calendar.monthrange(anno, mese)[1])

            luce = data[(anno, mese)]["luce"]
            gas = data[(anno, mese)]["gas"]

            result.append({
                "anno": anno,
                "mese": mese,
                "mese_label": MESI_IT[mese - 1],
                "luce_consumo": float(luce["consumo"]) if luce else None,
                "luce_importo": float(luce["importo"]) if luce else None,
                "luce_prezzo_unitario": _prezzo_unitario(luce),
                "gas_consumo": float(gas["consumo"]) if gas else None,
                "gas_importo": float(gas["importo"]) if gas else None,
                "gas_prezzo_unitario": _prezzo_unitario(gas),
                "presenze": _giorni_persona_mese(first_day, last_day),
            })

        return Response(result)


class AnnualUtilityCostViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Costi utenze annuali (TARI, ecc.) dell'immobile attivo (CRUD per i
    membri operativi; la property è assegnata dal server)."""

    serializer_class = AnnualUtilityCostSerializer
    permission_classes = [IsPropertyMember]
    queryset = AnnualUtilityCost.objects.all().order_by("-anno", "voce")
    pagination_class = None
    protected_detail = (
        "Impossibile eliminare il costo annuale: è referenziato da altri dati."
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))


class PropertyUtilityServiceViewSet(ModelViewSet):
    """Configurazione utenze dell'immobile attivo: quali voci (luce, gas,
    acqua, TARI) esistono per questa casa e chi le gestisce. Una riga per
    voce (unique property+voce); l'assenza di una riga significa che la
    voce non esiste per questa casa.

    CRUD aperto a tutti i membri operativi dell'immobile, **anche i
    gestori** (non solo i proprietari): decisione esplicita, la
    configurazione utenze non è materia riservata alla proprietà come le
    quote o le rimozioni di membri.
    """

    serializer_class = PropertyUtilityServiceSerializer
    permission_classes = [IsPropertyMember]
    queryset = PropertyUtilityService.objects.all().order_by("property", "voce")
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_doppione(self, voce, escludi_pk=None):
        prop = get_request_property(self.request)
        qs = PropertyUtilityService.objects.filter(property=prop, voce=voce)
        if escludi_pk is not None:
            qs = qs.exclude(pk=escludi_pk)
        if qs.exists():
            raise ValidationError(
                {
                    "voce": "Esiste già una configurazione per questa voce "
                    "in questo immobile."
                }
            )

    def perform_create(self, serializer):
        self._valida_doppione(serializer.validated_data.get("voce"))
        serializer.save(property=get_request_property(self.request))

    def perform_update(self, serializer):
        voce = serializer.validated_data.get("voce", serializer.instance.voce)
        self._valida_doppione(voce, escludi_pk=serializer.instance.pk)
        serializer.save()


class UtenzeInquilinoView(APIView):
    """Vista utenze per l'inquilino (sola lettura).

    - ``GET utenze-inquilino/``            : elenco dei periodi GIÀ INVIATI in
      cui l'inquilino ha un addebito utenze.
    - ``GET utenze-inquilino/<period_id>/``: dettaglio del periodo (bollette con
      PDF, composizione, quote di tutti i coinquilini). Accessibile solo se il
      periodo è stato inviato e l'inquilino vi compare.

    Read-only: nessuna modifica possibile lato inquilino.
    """

    permission_classes = [IsInquilino]

    def _tenant(self, request):
        from properties.models import TenantProfile

        return (
            TenantProfile.objects.select_related("user")
            .filter(user=request.user)
            .first()
        )

    def _periodi_inviati(self, tenant):
        """Periodi finalizzati (addebiti emessi) in cui l'inquilino compare.

        Il gate è ``stato=inviato`` (il proprietario ha emesso gli addebiti):
        è da quel momento che il conguaglio è ufficiale e l'inquilino lo vede.
        L'effettivo invio dell'email (``avvisi_inviati_at``) NON è richiesto:
        molti periodi storici hanno addebiti ma nessuna notifica email.
        """
        return (
            UtilityChargePeriod.objects.filter(
                stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
                receivables__causale=Receivable.Causale.UTENZE,
                receivables__assignment__tenant=tenant,
            )
            .distinct()
            .order_by("-periodo_da")
        )

    def _period_dict(self, p) -> dict:
        return {
            "id": p.id,
            "periodo_da": p.periodo_da,
            "periodo_a": p.periodo_a,
            "stato": p.stato,
            "avvisi_inviati_at": p.avvisi_inviati_at,
        }

    def _bollette(self, request, period) -> list:
        bills = (
            UtilityBill.objects.select_related("supplier")
            .filter(
                immobile=period.property_id,
                periodo_da__lte=period.periodo_a,
                periodo_a__gte=period.periodo_da,
            )
            .order_by("prodotto")
        )
        out = []
        for b in bills:
            out.append(
                {
                    "id": b.id,
                    "prodotto": b.prodotto,
                    "supplier_nome": b.supplier.nome if b.supplier_id else "",
                    "consumo": b.consumo,
                    "numero_fattura": b.numero_fattura,
                    "periodo_da": b.periodo_da,
                    "periodo_a": b.periodo_a,
                    "importo_totale": b.importo_totale,
                    "quota_esclusa": b.quota_esclusa,
                    "motivo_esclusione": b.motivo_esclusione,
                    "importo_ripartibile": b.importo_ripartibile,
                    # Path relativo (/media/…): l'app lo serve via proxy stessa
                    # origin, così l'iframe del PDF non incappa in X-Frame-Options.
                    "file_pdf": b.file_pdf.url if b.file_pdf else None,
                }
            )
        return out

    def get(self, request, period_id=None):
        tenant = self._tenant(request)
        if tenant is None:
            return Response(
                {"detail": "Profilo inquilino non trovato."},
                status=status.HTTP_404_NOT_FOUND,
            )

        periodi = self._periodi_inviati(tenant)

        if period_id is None:
            return Response({"periodi": [self._period_dict(p) for p in periodi]})

        period = periodi.filter(id=period_id).first()
        if period is None:
            return Response(
                {"detail": "Periodo non disponibile."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from billing.calc.utility import calcola_conguaglio_periodo

        # ``forza_senza_bollette``: il periodo è già stato emesso, quindi qui
        # si descrive ciò che è stato addebitato. Senza il flag un periodo
        # emesso in ripartizione parziale (solo TARI, luce/gas intestate
        # all'inquilino) tornerebbe vuoto e l'inquilino non vedrebbe nulla.
        ris = calcola_conguaglio_periodo(
            period.id, persist=False, forza_senza_bollette=True
        )

        my_assignment_ids = set(
            Receivable.objects.filter(
                causale=Receivable.Causale.UTENZE,
                utility_period=period,
                assignment__tenant=tenant,
            ).values_list("assignment_id", flat=True)
        )
        quote = [
            {**q, "is_me": q.get("assignment_id") in my_assignment_ids}
            for q in ris.get("quote", [])
        ]

        return Response(
            {
                "period": self._period_dict(period),
                "bollette": self._bollette(request, period),
                "totali_per_voce": ris.get("totali_per_voce", {}),
                "totale_periodo": ris.get("totale_periodo", 0),
                "totale_escluso": ris.get("totale_escluso", 0),
                "esclusioni": ris.get("esclusioni", []),
                "quote": quote,
                "tenant_id": tenant.id,
            }
        )
