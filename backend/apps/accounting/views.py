"""
ViewSet per l'app accounting. Solo proprietari.
"""
import datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounting.models import InterOwnerEntry, OwnerLedgerEntry, OwnerSettlement
from accounting.serializers import (
    GeneraSettlementSerializer,
    InterOwnerEntrySerializer,
    MarcaBtInterOwnerSerializer,
    ModificaInterOwnerSerializer,
    OwnerLedgerEntrySerializer,
    OwnerSettlementSerializer,
    PianoRientroVoceSerializer,
    QuadraturaSerializer,
    SaldoLiveSerializer,
    TrasferimentoProprietariSerializer,
)
from accounting.services.bt_inter_owner import (
    BTGiaMarcata,
    disfa_marcatura,
    marca_bt_come_ledger,
)
from accounting.services.saldi_live import (
    calcola_piano_rientro,
    calcola_saldi_correnti,
    verifica_quadratura,
)
from accounting.services.settlement import SettlementGiaEsistente, genera_settlement
from accounts.permissions import IsProprietario
from billing.models.payments import BankTransaction
from properties.context import get_request_property
from properties.models import OwnerProfile


class OwnerLedgerEntryViewSet(ModelViewSet):
    """Partitario ufficiale tra i proprietari. Solo proprietari."""

    serializer_class = OwnerLedgerEntrySerializer
    permission_classes = [IsProprietario]
    queryset = OwnerLedgerEntry.objects.select_related(
        "owner",
        "riferimento_receivable",
        "riferimento_expense",
        "riferimento_settlement",
        "bank_transaction",
    ).order_by("-data")

    def get_queryset(self):
        return super().get_queryset().filter(property=get_request_property(self.request))

    @action(detail=False, methods=["post"], url_path="bt-inter-owner")
    def bt_inter_owner_create(self, request):
        """Marca una BankTransaction come transazione inter-owner.

        Crea voci ledger A o B in base al tipo. Idempotenza protetta da
        SELECT FOR UPDATE: una seconda chiamata su BT già marcata torna 409.
        """
        ser = MarcaBtInterOwnerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        prop = get_request_property(request)
        bt = get_object_or_404(BankTransaction, pk=d["bank_transaction"])
        # La BT e l'eventuale controparte devono appartenere al perimetro
        # dell'immobile della richiesta: niente scritture cross-property.
        membri = prop.memberships.values_list("user_id", flat=True)
        if not bt.owner_account.properties.filter(pk=prop.pk).exists():
            return Response(
                {"detail": "La transazione sta su un conto non in uso su questo immobile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        controparte = None
        if d.get("controparte_owner"):
            controparte = get_object_or_404(OwnerProfile, pk=d["controparte_owner"])
            if controparte.user_id not in membri:
                return Response(
                    {"detail": "La controparte non è membro di questo immobile."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        settlement = None
        if d.get("settlement"):
            settlement = get_object_or_404(
                OwnerSettlement, pk=d["settlement"], property=prop,
            )

        try:
            voci = marca_bt_come_ledger(
                bt,
                property=prop,
                tipo=d["tipo"],
                controparte_owner=controparte,
                settlement=settlement,
                descrizione=d.get("descrizione", "") or "",
                note=d.get("note", "") or "",
            )
        except BTGiaMarcata as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # voci può essere mista (OwnerLedgerEntry / InterOwnerEntry)
        out = []
        for v in voci:
            if isinstance(v, OwnerLedgerEntry):
                out.append({"kind": "ledger_a", **OwnerLedgerEntrySerializer(v).data})
            else:
                out.append({"kind": "ledger_b", **InterOwnerEntrySerializer(v).data})
        return Response(out, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="trasferimento")
    def trasferimento_create(self, request):
        """Registra un bonifico fra proprietari in un colpo solo.

        Crea la `BankTransaction` sul conto indicato e la marca subito come
        `distribuzione`: è il gesto che i proprietari fanno davvero (girare a
        un altro la sua quota di incassi), e che altrimenti richiederebbe due
        passaggi separati, uno dei quali senza strada dal frontend.
        """
        from django.db import transaction as db_transaction
        from django.db.models import Q
        from properties.models import OwnerBankAccount

        ser = TrasferimentoProprietariSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        prop = get_request_property(request)

        # Il conto è di chi muove il denaro: quelli in uso sull'immobile più
        # i propri, stessa eccezione delle spese anticipate di tasca propria.
        account = OwnerBankAccount.objects.filter(
            Q(properties=prop) | Q(owner__user=request.user),
            pk=d["owner_account"],
        ).distinct().select_related("owner").first()
        if account is None:
            return Response(
                {"detail": "Conto non in uso su questo immobile né tuo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        controparte = get_object_or_404(OwnerProfile, pk=d["controparte_owner"])
        if controparte.user_id not in prop.memberships.values_list("user_id", flat=True):
            return Response(
                {"detail": "La controparte non è membro di questo immobile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if controparte == account.owner:
            return Response(
                {"detail": "La controparte deve essere un altro proprietario."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settlement = None
        if d.get("settlement"):
            settlement = get_object_or_404(
                OwnerSettlement, pk=d["settlement"], property=prop,
            )
        segno = -1 if d["direzione"] == "uscita" else 1
        descrizione = d.get("descrizione", "") or (
            f"Quota {'a' if segno < 0 else 'da'} {controparte.nominativo}"
        )
        with db_transaction.atomic():
            bt = BankTransaction.objects.create(
                owner_account=account,
                data=d["data"],
                importo=segno * d["importo"],
                descrizione=descrizione,
                note=d.get("note", "") or "",
            )
            voci = marca_bt_come_ledger(
                bt, property=prop, tipo=d["tipo"],
                controparte_owner=controparte, settlement=settlement,
                descrizione=descrizione, note=d.get("note", "") or "",
            )
        return Response(
            {
                "bank_transaction": bt.pk,
                "voci": OwnerLedgerEntrySerializer(voci, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["delete"], url_path=r"bt-inter-owner/(?P<bt_id>\d+)")
    def bt_inter_owner_delete(self, request, bt_id=None):
        prop = get_request_property(request)
        bt = get_object_or_404(BankTransaction, pk=bt_id)
        # Le marcature di un altro immobile non si toccano da qui.
        estranee = (
            bt.ledger_entries.exclude(property=prop).exists()
            or bt.inter_owner_entries.exclude(property=prop).exists()
        )
        if estranee:
            return Response(
                {"detail": "La transazione ha marcature di un altro immobile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        n = disfa_marcatura(bt)
        return Response({"voci_cancellate": n}, status=status.HTTP_200_OK)

    @bt_inter_owner_delete.mapping.patch
    def bt_inter_owner_update(self, request, bt_id=None):
        """Corregge causale e attribuzione di un movimento già marcato.

        Un bonifico fra proprietari registrato male non si poteva più
        toccare dal frontend: restava disfare la marcatura e rifarla, in due
        passaggi e perdendo la causale. Qui la marcatura viene rifatta in
        una transazione sola, e la causale aggiorna anche la descrizione del
        movimento bancario — che per questi movimenti è scritta da noi, non
        dalla banca. Importo e data non si toccano: quelli li dice la banca.
        """
        from django.db import transaction as db_transaction

        ser = ModificaInterOwnerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        prop = get_request_property(request)
        bt = get_object_or_404(BankTransaction, pk=bt_id)
        if not bt.owner_account.properties.filter(pk=prop.pk).exists():
            return Response(
                {"detail": "La transazione sta su un conto non in uso su questo immobile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        estranee = (
            bt.ledger_entries.exclude(property=prop).exists()
            or bt.inter_owner_entries.exclude(property=prop).exists()
        )
        if estranee:
            return Response(
                {"detail": "La transazione ha marcature di un altro immobile."},
                status=status.HTTP_403_FORBIDDEN,
            )
        membri = prop.memberships.values_list("user_id", flat=True)
        controparte = None
        if d.get("controparte_owner"):
            controparte = get_object_or_404(OwnerProfile, pk=d["controparte_owner"])
            if controparte.user_id not in membri:
                return Response(
                    {"detail": "La controparte non è membro di questo immobile."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        settlement = None
        if d.get("settlement"):
            settlement = get_object_or_404(
                OwnerSettlement, pk=d["settlement"], property=prop,
            )

        descrizione = d.get("descrizione", "") or ""
        try:
            with db_transaction.atomic():
                disfa_marcatura(bt)
                voci = marca_bt_come_ledger(
                    bt, property=prop, tipo=d["tipo"],
                    controparte_owner=controparte, settlement=settlement,
                    descrizione=descrizione, note=d.get("note", "") or "",
                )
                if descrizione and descrizione != bt.descrizione:
                    bt.descrizione = descrizione
                    bt.save(update_fields=["descrizione"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        out = []
        for v in voci:
            if isinstance(v, OwnerLedgerEntry):
                out.append({"kind": "ledger_a", **OwnerLedgerEntrySerializer(v).data})
            else:
                out.append({"kind": "ledger_b", **InterOwnerEntrySerializer(v).data})
        return Response(out, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="saldi-live")
    def saldi_live(self, request):
        """Saldi correnti calcolati al volo. Query param `?at=YYYY-MM-DD`.

        Risposta: {saldi: [...], quadratura: {...}, piano_rientro: [...]}.
        """
        at_raw = request.query_params.get("at")
        try:
            at_date = datetime.date.fromisoformat(at_raw) if at_raw else datetime.date.today()
        except ValueError:
            return Response(
                {"detail": "Parametro `at` non valido (atteso YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prop = get_request_property(request)
        saldi = calcola_saldi_correnti(prop, at_date)
        quadratura = verifica_quadratura(prop, at_date, saldi)
        piano = calcola_piano_rientro(saldi)
        items = [
            {
                "owner": {"id": s.owner.pk, "nominativo": s.owner.nominativo},
                "quota": s.quota,
                "baseline_settlement": s.baseline_settlement,
                "incassi_per_causale": s.incassi_per_causale,
                "spese_per_categoria": s.spese_per_categoria,
                "anticipi_pendenti": s.anticipi_pendenti,
                "bt_inter_owner": s.bt_inter_owner,
                "totale": s.totale,
            }
            for s in saldi.values()
        ]
        piano_items = [
            {
                "da": {"id": v["da"].pk, "nominativo": v["da"].nominativo},
                "a": {"id": v["a"].pk, "nominativo": v["a"].nominativo},
                "importo": v["importo"],
            }
            for v in piano
        ]
        return Response({
            "saldi": SaldoLiveSerializer(items, many=True).data,
            "quadratura": QuadraturaSerializer(quadratura).data,
            "piano_rientro": PianoRientroVoceSerializer(piano_items, many=True).data,
        })


class OwnerSettlementViewSet(ReadOnlyModelViewSet):
    """Chiusure periodiche dei conti tra fratelli. La creazione passa
    dall'action `genera` (con dry-run di anteprima) o dal management
    command omonimo."""

    serializer_class = OwnerSettlementSerializer
    permission_classes = [IsProprietario]
    queryset = OwnerSettlement.objects.order_by("-data")

    def get_queryset(self):
        return super().get_queryset().filter(property=get_request_property(self.request))

    @action(detail=False, methods=["post"], url_path="genera")
    def genera(self, request):
        """Genera/rigenera un settlement. Con dry_run=True calcola lo
        snapshot e fa rollback: serve da anteprima prima della conferma."""
        ser = GeneraSettlementSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d.get("anno"):
            periodo_da = datetime.date(d["anno"], 1, 1)
            periodo_a = datetime.date(d["anno"], 12, 31)
        else:
            periodo_da = d["periodo_da"]
            periodo_a = d["periodo_a"]

        try:
            settlement = genera_settlement(
                get_request_property(request),
                periodo_da,
                periodo_a,
                descrizione=d.get("descrizione") or None,
                reset=d["reset"],
                dry_run=d["dry_run"],
            )
        except SettlementGiaEsistente as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            # In dry-run il record è rollbackato: l'id non è riutilizzabile.
            "id": None if d["dry_run"] else settlement.pk,
            "periodo_da": periodo_da,
            "periodo_a": periodo_a,
            "descrizione": settlement.descrizione,
            "snapshot": settlement.snapshot,
            "dry_run": d["dry_run"],
        }, status=status.HTTP_200_OK if d["dry_run"] else status.HTTP_201_CREATED)


class InterOwnerEntryViewSet(ModelViewSet):
    """Partitario bilaterale tra proprietari. Solo proprietari."""

    serializer_class = InterOwnerEntrySerializer
    permission_classes = [IsProprietario]
    queryset = InterOwnerEntry.objects.select_related(
        "owner_da",
        "owner_a",
        "riferimento_loan",
        "riferimento_expense",
        "bank_transaction",
    ).order_by("-data")

    def get_queryset(self):
        return super().get_queryset().filter(property=get_request_property(self.request))

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))
