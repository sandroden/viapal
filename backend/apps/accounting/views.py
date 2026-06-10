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
    OwnerLedgerEntrySerializer,
    OwnerSettlementSerializer,
    PianoRientroVoceSerializer,
    QuadraturaSerializer,
    SaldoLiveSerializer,
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

    @action(detail=False, methods=["post"], url_path="bt-inter-owner")
    def bt_inter_owner_create(self, request):
        """Marca una BankTransaction come transazione inter-owner.

        Crea voci ledger A o B in base al tipo. Idempotenza protetta da
        SELECT FOR UPDATE: una seconda chiamata su BT già marcata torna 409.
        """
        ser = MarcaBtInterOwnerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        bt = get_object_or_404(BankTransaction, pk=d["bank_transaction"])
        controparte = None
        if d.get("controparte_owner"):
            controparte = get_object_or_404(OwnerProfile, pk=d["controparte_owner"])
        settlement = None
        if d.get("settlement"):
            settlement = get_object_or_404(OwnerSettlement, pk=d["settlement"])

        try:
            voci = marca_bt_come_ledger(
                bt,
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

    @action(detail=False, methods=["delete"], url_path=r"bt-inter-owner/(?P<bt_id>\d+)")
    def bt_inter_owner_delete(self, request, bt_id=None):
        bt = get_object_or_404(BankTransaction, pk=bt_id)
        n = disfa_marcatura(bt)
        return Response({"voci_cancellate": n}, status=status.HTTP_200_OK)

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
        saldi = calcola_saldi_correnti(at_date)
        quadratura = verifica_quadratura(at_date, saldi)
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
