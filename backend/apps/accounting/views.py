"""
ViewSet per l'app accounting. Solo proprietari.
"""
from rest_framework.viewsets import ReadOnlyModelViewSet

from accounting.models import InterOwnerEntry, OwnerLedgerEntry
from accounting.serializers import InterOwnerEntrySerializer, OwnerLedgerEntrySerializer
from accounts.permissions import IsProprietario


class OwnerLedgerEntryViewSet(ReadOnlyModelViewSet):
    """Partitario ufficiale tra i proprietari. Solo proprietari."""

    serializer_class = OwnerLedgerEntrySerializer
    permission_classes = [IsProprietario]
    queryset = OwnerLedgerEntry.objects.select_related(
        "owner",
        "riferimento_payment",
        "riferimento_charge",
        "riferimento_expense",
    ).order_by("-data")


class InterOwnerEntryViewSet(ReadOnlyModelViewSet):
    """Partitario bilaterale tra proprietari. Solo proprietari."""

    serializer_class = InterOwnerEntrySerializer
    permission_classes = [IsProprietario]
    queryset = InterOwnerEntry.objects.select_related(
        "owner_da",
        "owner_a",
        "riferimento_loan",
        "riferimento_expense",
    ).order_by("-data")
