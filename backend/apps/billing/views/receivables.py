"""
ViewSet e view sugli addebiti (Receivable).

I tre endpoint storici (rent-payments, utility-charges, extra-charges)
ora si appoggiano al modello unico Receivable filtrando per causale.
"""
import datetime
from decimal import Decimal

from accounts.permissions import (
    IsInquilinoSelf,
    IsPropertyMember,
)
from django.db.models import F, Q, Sum
from properties.context import get_request_property
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from billing._notifiche import notifica_dichiarazione_pagamento
from billing.calc.incassi import (
    IncassoRifiutato,
    registra_incasso,
    residuo_da_incassare,
)
from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    ReceivableComment,
    StatoPagamento,
)
from billing.serializers import (
    BankTransactionSerializer,
    ConfermaPagamentoInputSerializer,
    ExtraChargeSerializer,
    ReceivableForReconcileSerializer,
    RegistraPagamentoInputSerializer,
    RentPaymentSerializer,
    UtilityChargeSerializer,
)
from billing.signals import _riallinea_receivable

from ._common import BillingPagination, _is_proprietario, _valida_conto_incasso


class _ReceivableMixin:
    """Comportamenti comuni dei tre ViewSet su Receivable.

    Le sottoclassi specificano `causale` e `serializer_class`.
    """

    causale: str
    pagination_class = BillingPagination

    def get_permissions(self):
        if self.action in ("dichiara_pagato", "conferma_pagato"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsPropertyMember()]
        return [IsInquilinoSelf()]

    def _base_queryset(self):
        return Receivable.objects.filter(causale=self.causale).select_related(
            "assignment__tenant__user",
            "assignment__room",
            "incassato_da_owner",
            "bank_account_destinazione",
            "utility_period",
        )

    def get_queryset(self):
        qs = self._base_queryset().order_by("-scadenza")
        if _is_proprietario(self.request.user):
            return qs.filter(
                assignment__room__property=get_request_property(self.request)
            )
        return qs.filter(assignment__tenant__user=self.request.user)

    def _valida_property_attiva(self, serializer):
        """L'assignment (e il period, se presente) devono appartenere
        all'immobile attivo: i campi sono FK a queryset globale, quindi vanno
        vincolati qui, non a livello di permission."""
        prop = get_request_property(self.request)
        assignment = serializer.validated_data.get("assignment")
        if assignment is not None and assignment.room.property_id != prop.id:
            raise ValidationError(
                {"assignment": "Assegnazione non appartenente all'immobile attivo."}
            )
        period = serializer.validated_data.get("utility_period")
        if period is not None and period.property_id != prop.id:
            raise ValidationError(
                {"period": "Periodo non appartenente all'immobile attivo."}
            )

    def perform_create(self, serializer):
        self._valida_property_attiva(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._valida_property_attiva(serializer)
        serializer.save()

    @staticmethod
    def _parse_data(valore) -> datetime.date | None:
        """Data ISO dal payload, None se assente o malformata."""
        if not valore:
            return None
        try:
            return datetime.date.fromisoformat(str(valore))
        except ValueError:
            return None

    @staticmethod
    def _nota_dichiarazione(data) -> str:
        """Riga di nota con gli estremi del pagamento dichiarato dall'inquilino."""
        parti = []
        try:
            importo = Decimal(str(data.get("importo_pagato")))
            parti.append(f"{importo:.2f} €".replace(".", ","))
        except Exception:
            pass
        for campo in ("metodo_pagamento", "riferimento", "note"):
            valore = str(data.get(campo) or "").strip()
            if valore:
                parti.append(valore[:200])
        if not parti:
            return ""
        oggi = datetime.date.today().isoformat()
        return f"[Dichiarato il {oggi}] " + " — ".join(parti)

    @action(detail=True, methods=["post"], url_path="dichiara_pagato")
    def dichiara_pagato(self, request, pk=None):
        """Inquilino marca come dichiarato. Solo l'inquilino del receivable."""
        receivable = self.get_object()

        if not _is_proprietario(request.user):
            if receivable.assignment.tenant.user != request.user:
                return Response(
                    {"detail": "Puoi dichiarare solo i tuoi addebiti."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if receivable.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Addebito gia' confermato dai proprietari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # La dichiarazione NON tocca ``importo_pagato``: quel campo riflette
        # la copertura reale (allocazioni bonifico) e sovrascriverlo qui
        # azzererebbe il residuo di un addebito pagato solo in parte.
        # Gli estremi dichiarati finiscono nelle note, a beneficio del
        # proprietario che deve confermare.
        receivable.stato = StatoPagamento.DICHIARATO
        receivable.data_pagamento = (
            self._parse_data(request.data.get("data_pagamento"))
            or datetime.date.today()
        )
        riga_nota = self._nota_dichiarazione(request.data)
        if riga_nota:
            receivable.note = (
                f"{receivable.note}\n{riga_nota}" if receivable.note else riga_nota
            )
        receivable.save(update_fields=["stato", "data_pagamento", "note"])

        # I proprietari devono sapere che c'è un incasso da confermare: senza
        # questo avviso la dichiarazione resta muta fino a quando qualcuno non
        # apre i ritardi. Chi ha premuto il bottone non si avvisa da solo.
        notifica_dichiarazione_pagamento(receivable, autore=request.user)

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="conferma_pagato")
    def conferma_pagato(self, request, pk=None):
        """Proprietario conferma il pagamento: serve il conto su cui è entrato.

        Confermare non è una spunta: è registrare un incasso. Senza il conto
        non sapremmo *chi* ha ricevuto, e l'addebito resterebbe fuori dai saldi
        tra proprietari — il buco che questa firma obbligatoria impedisce.
        Il movimento e l'allocazione li crea ``registra_incasso``; è il signal
        di riallineamento a portare l'addebito a PAGATO.
        """
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono confermare un pagamento."},
                status=status.HTTP_403_FORBIDDEN,
            )

        receivable = self.get_object()

        if receivable.stato not in (
            StatoPagamento.DICHIARATO,
            StatoPagamento.ATTESO,
            StatoPagamento.IN_RITARDO,
        ):
            return Response(
                {"detail": f"Impossibile confermare un addebito in stato '{receivable.stato}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ConfermaPagamentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        prop = receivable.assignment.room.property
        errore = _valida_conto_incasso(v["owner_account"], prop)
        if errore:
            return errore

        importo = v.get("importo") or residuo_da_incassare(receivable)
        data_incasso = (
            v.get("data") or receivable.data_pagamento or datetime.date.today()
        )
        try:
            registra_incasso(
                receivable,
                data=data_incasso,
                importo=importo,
                owner_account=v["owner_account"],
                descrizione=v.get("descrizione") or self._descrizione_incasso(receivable),
                note=v.get("note", ""),
            )
        except IncassoRifiutato as e:
            return Response({"detail": e.detail}, status=e.status_code)

        receivable.refresh_from_db()
        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _descrizione_incasso(receivable) -> str:
        """Descrizione di default del movimento creato confermando."""
        tenant = receivable.assignment.tenant.nominativo
        return f"Incasso {receivable.get_causale_display()} — {tenant}"[:300]

    @action(detail=True, methods=["post"], url_path="rifiuta_pagato")
    def rifiuta_pagato(self, request, pk=None):
        """Proprietario rimbalza una dichiarazione: l'addebito torna da pagare.

        Stato/importo_pagato/data_pagamento vengono ricalcolati dalle
        allocazioni bancarie (la stessa verità del signal di riallineamento),
        così l'inquilino rivede la voce con il residuo reale.
        """
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono rifiutare una dichiarazione."},
                status=status.HTTP_403_FORBIDDEN,
            )

        receivable = self.get_object()

        if receivable.stato != StatoPagamento.DICHIARATO:
            return Response(
                {
                    "detail": "Si può rifiutare solo un addebito dichiarato "
                    f"(stato attuale '{receivable.stato}')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        nota = f"[Dichiarazione rifiutata il {datetime.date.today().isoformat()}]"
        receivable.note = f"{receivable.note}\n{nota}" if receivable.note else nota
        receivable.save(update_fields=["note"])

        _riallinea_receivable(receivable.id)
        receivable.refresh_from_db()

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )


class RentPaymentViewSet(_ReceivableMixin, ModelViewSet):
    """Pagamenti affitto (Receivable causale=affitto)."""

    causale = Receivable.Causale.AFFITTO
    serializer_class = RentPaymentSerializer


class UtilityChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Utenze (Receivable causale=utenze)."""

    causale = Receivable.Causale.UTENZE
    serializer_class = UtilityChargeSerializer

    def _base_queryset(self):
        return super()._base_queryset().select_related("utility_period")

    def get_queryset(self):
        qs = self._base_queryset().order_by("-utility_period__periodo_da")
        if _is_proprietario(self.request.user):
            return qs.filter(
                assignment__room__property=get_request_property(self.request)
            )
        return qs.filter(assignment__tenant__user=self.request.user)


class ExtraChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Addebiti extra (Receivable causale=extra)."""

    causale = Receivable.Causale.EXTRA
    serializer_class = ExtraChargeSerializer
    pagination_class = None  # comportamento legacy: lista plain


class DepositChargeViewSet(_ReceivableMixin, ReadOnlyModelViewSet):
    """Rate di versamento del deposito (Receivable causale=deposito, > 0).

    Sola lettura + dichiara/conferma pagato: le rate nascono dalla prima
    assegnazione o dai signal sul tenant, mai da questo endpoint. Le
    restituzioni (importo negativo) restano fuori.
    """

    causale = Receivable.Causale.DEPOSITO
    serializer_class = ExtraChargeSerializer
    pagination_class = None

    def _base_queryset(self):
        return super()._base_queryset().filter(importo_dovuto__gt=0)


class ReceivableViewSet(ReadOnlyModelViewSet):
    """Receivable in formato compatto per pagina riconciliazione.

    Querystring:
    - ``assignment`` (id), ``tenant`` (id),
    - ``causale`` (csv: ``affitto,utenze,extra``),
    - ``stato`` (csv: ``atteso,in_ritardo,...``),
    - ``riconciliato`` = ``true|false|all`` (default ``all``); confronta
      ``Sum(allocations.importo)`` con ``importo_dovuto``,
    - ``data_da``, ``data_a`` su ``scadenza``.
    """

    serializer_class = ReceivableForReconcileSerializer
    permission_classes = [IsPropertyMember]
    pagination_class = BillingPagination

    def get_queryset(self):
        from django.db.models import Prefetch
        qs = (
            Receivable.objects
            .filter(assignment__room__property=get_request_property(self.request))
            .select_related(
                "assignment__tenant",
                "assignment__room",
                "utility_period",
                # Il conto suggerito del serializer risale a
                # assignment → room → property → conto: senza questi, una
                # coppia di query per riga sulla pagina "Da incassare".
                "assignment__bank_account_affitto",
                "assignment__room__property__bank_account_utenze",
            )
            .prefetch_related(
                Prefetch(
                    "allocations",
                    queryset=BankTransactionAllocation.objects.select_related(
                        "bank_transaction"
                    ),
                )
            )
            .annotate(_alloc=Sum("allocations__importo"))
            .order_by("-scadenza", "-id")
        )

        params = self.request.query_params

        assignment = params.get("assignment")
        if assignment:
            qs = qs.filter(assignment_id=assignment)

        tenant = params.get("tenant")
        if tenant:
            qs = qs.filter(assignment__tenant_id=tenant)

        causale = params.get("causale")
        if causale:
            qs = qs.filter(causale__in=[c.strip() for c in causale.split(",") if c.strip()])

        stato = params.get("stato")
        if stato:
            qs = qs.filter(stato__in=[s.strip() for s in stato.split(",") if s.strip()])

        riconciliato = params.get("riconciliato", "all")
        # Segno-aware: per Receivable positivi "riconciliato" significa
        # alloc>=importo_dovuto; per Receivable negativi (restituzione
        # caparra) significa alloc<=importo_dovuto (entrambi negativi).
        if riconciliato == "true":
            qs = qs.filter(
                Q(importo_dovuto__gt=0, _alloc__gte=F("importo_dovuto"))
                | Q(importo_dovuto__lt=0, _alloc__lte=F("importo_dovuto"))
                | Q(importo_dovuto=0)
            )
        elif riconciliato == "false":
            qs = qs.filter(
                Q(_alloc__isnull=True)
                | Q(importo_dovuto__gt=0, _alloc__lt=F("importo_dovuto"))
                | Q(importo_dovuto__lt=0, _alloc__gt=F("importo_dovuto"))
            )

        data_da = params.get("data_da")
        if data_da:
            qs = qs.filter(scadenza__gte=data_da)
        data_a = params.get("data_a")
        if data_a:
            qs = qs.filter(scadenza__lte=data_a)

        return qs


class RegistraPagamentoReceivableView(APIView):
    """POST /api/v1/receivables/<pk>/registra-pagamento/

    Inserimento veloce di un pagamento ricevuto dal proprietario senza passare
    dall'admin: data + importo + conto. Crea atomicamente:

    1. ``BankTransaction`` in entrata sul conto indicato;
    2. ``BankTransactionAllocation`` che lega BT al Receivable.

    Se l'importo è maggiore del residuo del Receivable, alloca solo il residuo
    e lascia la differenza sulla BT (visibile come "parziale" in
    riconciliazione). Se è minore, alloca tutto: il Receivable resta atteso.
    """

    permission_classes = [IsPropertyMember]

    def post(self, request, pk):
        try:
            receivable = Receivable.objects.get(
                pk=pk,
                assignment__room__property=get_request_property(request),
            )
        except Receivable.DoesNotExist:
            return Response(
                {"detail": "Receivable non trovato."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if receivable.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Receivable già pagato."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = RegistraPagamentoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        # Il conto di destinazione deve essere in uso su questo immobile.
        errore = _valida_conto_incasso(
            v["owner_account"], get_request_property(request)
        )
        if errore:
            return errore

        try:
            bt, _quota = registra_incasso(
                receivable,
                data=v["data"],
                importo=v["importo"],
                owner_account=v["owner_account"],
                descrizione=v["descrizione"],
                note=v.get("note", ""),
            )
        except IncassoRifiutato as e:
            return Response({"detail": e.detail}, status=e.status_code)

        bt_qs = (
            BankTransaction.objects.filter(pk=bt.pk)
            .select_related("owner_account__owner")
            .prefetch_related(
                "allocations__receivable__assignment__tenant",
                "allocations__receivable__utility_period",
            )
        )
        bt_data = BankTransactionSerializer(bt_qs.first()).data

        rec_qs = (
            Receivable.objects.filter(pk=receivable.pk)
            .select_related("assignment__tenant", "utility_period")
            .annotate(_alloc=Sum("allocations__importo"))
        )
        rec_data = ReceivableForReconcileSerializer(rec_qs.first()).data

        return Response(
            {"bank_transaction": bt_data, "receivable": rec_data},
            status=status.HTTP_201_CREATED,
        )


class ReceivableCommentiView(APIView):
    """GET/POST /api/v1/receivables/<pk>/commenti/

    Commenti liberi sull'addebito, visibili sia all'inquilino sia ai
    proprietari. Un commento dell'inquilino viene inoltrato via email ai
    membri proprietari/gestori dell'immobile (best-effort).
    """

    permission_classes = [IsAuthenticated]

    def _get_receivable(self, request, pk):
        """Il receivable se l'utente ha titolo a vederlo, altrimenti None."""
        try:
            receivable = Receivable.objects.select_related(
                "assignment__tenant__user", "assignment__room__property"
            ).get(pk=pk)
        except Receivable.DoesNotExist:
            return None
        user = request.user
        if receivable.assignment.tenant.user_id == user.id:
            return receivable
        if user.is_superuser:
            return receivable
        prop = receivable.assignment.room.property
        if user.property_memberships.filter(property=prop).exists():
            return receivable
        return None

    @staticmethod
    def _serializza(commento) -> dict:
        from billing.commenti import _nome_autore

        return {
            "id": commento.id,
            "autore": _nome_autore(commento.autore),
            "testo": commento.testo,
            "data": commento.created_at.date().isoformat(),
        }

    def get(self, request, pk):
        receivable = self._get_receivable(request, pk)
        if receivable is None:
            return Response(
                {"detail": "Addebito non trovato."},
                status=status.HTTP_404_NOT_FOUND,
            )
        commenti = receivable.commenti.select_related("autore").order_by("created_at")
        return Response([self._serializza(c) for c in commenti])

    def post(self, request, pk):
        from billing.commenti import invia_email_commento

        receivable = self._get_receivable(request, pk)
        if receivable is None:
            return Response(
                {"detail": "Addebito non trovato."},
                status=status.HTTP_404_NOT_FOUND,
            )
        testo = str(request.data.get("testo") or "").strip()
        if not testo:
            return Response(
                {"detail": "Il testo del commento è obbligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        commento = ReceivableComment.objects.create(
            receivable=receivable,
            autore=request.user,
            testo=testo[:2000],
        )
        # Inoltro email ai proprietari solo se a scrivere è l'inquilino.
        esito_email = None
        if receivable.assignment.tenant.user_id == request.user.id:
            esito_email = invia_email_commento(commento)
        return Response(
            {**self._serializza(commento), "email": esito_email},
            status=status.HTTP_201_CREATED,
        )
