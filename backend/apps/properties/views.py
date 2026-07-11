"""
ViewSet per l'app properties.
"""
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsPropertyMember
from properties.context import get_request_property
from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)
from properties.serializers import (
    CessioneAssignmentSerializer,
    ContractSerializer,
    OwnerBankAccountSerializer,
    OwnerProfileSerializer,
    RoomAssignmentSerializer,
    RoomSerializer,
    TenantDocumentSerializer,
    TenantProfileSerializer,
    TenantProfileWriteSerializer,
    TenantSelfUpdateSerializer,
)


def _is_gestione(user):
    """True se l'utente sta dal lato gestione (membro di almeno un immobile)."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.property_memberships.exists())
    )


class ProtectedDestroyMixin:
    """DELETE di oggetti referenziati da FK PROTECT → 409 con messaggio
    chiaro invece del 500 di ``ProtectedError``."""

    protected_detail = (
        "Impossibile eliminare: l'oggetto è referenziato da altri dati."
    )

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": self.protected_detail},
                status=status.HTTP_409_CONFLICT,
            )


def _valida_owner_membro(owner_profile, prop, campo):
    """400 se ``owner_profile`` (facoltativo) non è membro dell'immobile."""
    from rest_framework.exceptions import ValidationError

    if owner_profile is None:
        return
    if not owner_profile.user.property_memberships.filter(property=prop).exists():
        raise ValidationError(
            {campo: "Il proprietario indicato non è membro di questo immobile."}
        )


class OwnerProfileViewSet(ReadOnlyModelViewSet):
    """Profili proprietario dei membri dell'immobile attivo."""

    serializer_class = OwnerProfileSerializer
    permission_classes = [IsPropertyMember]
    queryset = OwnerProfile.objects.select_related("user").order_by("nominativo")

    def get_queryset(self):
        prop = get_request_property(self.request)
        return super().get_queryset().filter(
            user__property_memberships__property=prop
        ).distinct()


class TenantProfileViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, ReadOnlyModelViewSet
):
    """
    Profili inquilini.
    - Proprietari: vedono tutti. Per default la lista mostra solo gli attivi
      (con assignment in corso oggi); query param ``?solo_attivi=0`` per
      includere anche gli storici. In alternativa, ``?anno=YYYY`` filtra gli
      inquilini con almeno un assignment che si sovrappone all'anno indicato
      (ha la precedenza su ``solo_attivi``).
    - Inquilini: vedono solo il proprio.
    - Scrittura (create/update) riservata ai membri operativi dell'immobile
      attivo: la creazione genera anche lo User collegato (vedi
      ``TenantProfileWriteSerializer``); l'action ``invita`` manda l'email
      di primo accesso.
    """

    serializer_class = TenantProfileSerializer

    def get_permissions(self):
        # ``me`` resta self-service dell'inquilino (GET/PATCH); le altre
        # scritture sono riservate ai membri operativi dell'immobile.
        if self.action == "me":
            return [IsInquilinoSelf()]
        if self.request.method not in SAFE_METHODS:
            return [IsPropertyMember()]
        return [IsInquilinoSelf()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TenantProfileWriteSerializer
        return TenantProfileSerializer

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))

    @action(detail=True, methods=["post"], url_path="invita")
    def invita(self, request, pk=None):
        """Invia all'inquilino l'email di invito (link imposta-password)."""
        from accounts.inviti import invia_invito_inquilino

        tenant = self.get_object()
        esito = invia_invito_inquilino(tenant, request=request)
        if esito["esito"] != "inviato":
            return Response(esito, status=status.HTTP_400_BAD_REQUEST)
        return Response(esito)

    def get_queryset(self):
        user = self.request.user
        qs = TenantProfile.objects.select_related("user").order_by("nominativo")
        if not _is_gestione(user):
            return qs.filter(user=user)
        qs = qs.filter(property=get_request_property(self.request))

        # I filtri di "attività" valgono solo per la lista: il dettaglio (e
        # quindi update/invita) deve raggiungere anche gli inquilini appena
        # creati (senza assignment) e quelli storici.
        if self.action != "list":
            return qs

        anno_param = self.request.query_params.get("anno")
        if anno_param:
            try:
                anno = int(anno_param)
            except (TypeError, ValueError):
                anno = None
            if anno is not None:
                self._anno_filtro = anno
                inizio = datetime.date(anno, 1, 1)
                fine = datetime.date(anno, 12, 31)
                return qs.filter(
                    assignments__valid_from__lte=fine,
                ).filter(
                    Q(assignments__valid_to__isnull=True)
                    | Q(assignments__valid_to__gt=inizio)
                ).distinct()

        solo_attivi = self.request.query_params.get("solo_attivi", "1")
        if solo_attivi in ("0", "false", "False"):
            return qs

        oggi = datetime.date.today()
        return qs.filter(
            assignments__valid_from__lte=oggi,
        ).filter(
            Q(assignments__valid_to__isnull=True)
            | Q(assignments__valid_to__gt=oggi)
        ).distinct()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if not (user.is_authenticated and _is_gestione(user)):
            return ctx

        from billing.dashboard_views import _resti_per_anno, _sbilancio_progressivo
        from billing.models import Receivable

        anno_filtro = getattr(self, "_anno_filtro", None)
        tenants = list(self.filter_queryset(self.get_queryset()))
        if not tenants:
            ctx["saldi_totali"] = {}
            if anno_filtro is not None:
                ctx["saldi_anno"] = {}
            return ctx

        tenant_ids = [t.id for t in tenants]
        base_qs = (
            Receivable.objects
            .filter(assignment__tenant_id__in=tenant_ids)
            .exclude(causale=Receivable.Causale.DEPOSITO)
        )

        # Dovuto/pagato per (tenant, anno di competenza) in un colpo solo.
        dovuto_pagato: dict[int, dict[int, list]] = {}
        for row in base_qs.values(
            "assignment__tenant_id", "competenza_da__year"
        ).annotate(
            d=Coalesce(Sum("importo_dovuto"), Decimal("0")),
            p=Coalesce(Sum("importo_pagato"), Decimal("0")),
        ):
            t = row["assignment__tenant_id"]
            y = row["competenza_da__year"] or 0
            dovuto_pagato.setdefault(t, {})[y] = [row["d"], row["p"]]

        # Sbilancio reale (= pagato − dovuto + resti dei bonifici) per ogni
        # inquilino. Coerente con TenantSituazioneView: ``saldo_totale`` è il
        # progressivo cumulato fino all'anno selezionato (non conosce il
        # futuro); senza filtro anno è il totale complessivo.
        saldi_totali: dict[int, float] = {}
        saldi_anno: dict[int, float] = {}
        for t in tenants:
            per_anno, totale = _sbilancio_progressivo(
                dovuto_pagato.get(t.id, {}), _resti_per_anno(t)
            )
            if anno_filtro is not None:
                prog = 0.0
                for x in per_anno:
                    if x["anno"] <= anno_filtro:
                        prog = x["saldo_progressivo"]
                saldi_totali[t.id] = prog
                ent = next((x for x in per_anno if x["anno"] == anno_filtro), None)
                saldi_anno[t.id] = ent["saldo_anno"] if ent else 0.0
            else:
                saldi_totali[t.id] = totale["sbilancio_reale"]

        ctx["saldi_totali"] = saldi_totali
        if anno_filtro is not None:
            ctx["saldi_anno"] = saldi_anno
        return ctx

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Profilo dell'inquilino loggato, con aggiornamento self-service.

        GET restituisce i propri dati; PATCH consente di modificare solo i
        campi concessi (nominativo, telefono, codice fiscale) tramite
        ``TenantSelfUpdateSerializer``.
        """
        tenant = getattr(request.user, "tenant_profile", None)
        if tenant is None:
            return Response(
                {"detail": "Nessun profilo inquilino associato all'utente."},
                status=404,
            )
        if request.method == "PATCH":
            serializer = TenantSelfUpdateSerializer(
                tenant, data=request.data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = TenantSelfUpdateSerializer(
                tenant, context={"request": request}
            )
        return Response(serializer.data)


class TenantDocumentViewSet(ModelViewSet):
    """
    Documenti degli inquilini (CI, CF, passaporto, permesso, contratto lavoro).
    - Inquilini: vedono, caricano ed eliminano solo i propri (il ``tenant`` è
      forzato al proprio profilo, indipendentemente dal payload).
    - Proprietari: vedono tutti, filtrabili con ``?tenant=<id>``; in scrittura
      devono indicare il ``tenant`` nel payload.
    """

    serializer_class = TenantDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = TenantDocument.objects.select_related("tenant", "tenant__user")
        if not _is_gestione(user):
            return qs.filter(tenant__user=user)
        qs = qs.filter(tenant__property=get_request_property(self.request))
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if _is_gestione(user):
            tenant = serializer.validated_data.get("tenant")
            if tenant is None:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"tenant": "Campo obbligatorio per i proprietari."})
            if tenant.property_id != get_request_property(self.request).pk:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("L'inquilino appartiene a un altro immobile.")
        else:
            tenant = getattr(user, "tenant_profile", None)
            if tenant is None:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Nessun profilo inquilino associato all'utente.")
        serializer.save(tenant=tenant, caricato_da=user)


class RoomViewSet(ProtectedDestroyMixin, ModelViewSet):
    """
    Stanze.
    - Proprietari: tutte, con CRUD completo (scrittura riservata ai membri
      operativi; la property è assegnata dal server sull'immobile attivo).
    - Inquilini: solo lettura delle stanze con assignment attivo per sé.
    """

    serializer_class = RoomSerializer
    protected_detail = (
        "Impossibile eliminare la stanza: ha assegnazioni collegate. "
        "Rimuovere prima le assegnazioni."
    )

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [IsPropertyMember()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        today = datetime.date.today()
        if _is_gestione(user):
            return Room.objects.filter(property=get_request_property(self.request))
        # Stanze dove l'inquilino ha un assignment attivo oggi
        return Room.objects.filter(
            assignments__tenant__user=user,
            assignments__valid_from__lte=today,
        ).filter(
            Q(assignments__valid_to__isnull=True) | Q(assignments__valid_to__gt=today)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(property=get_request_property(self.request))


class RoomAssignmentViewSet(ProtectedDestroyMixin, ModelViewSet):
    """
    Assegnazioni stanza.
    - Proprietari: tutte, con CRUD completo (scrittura riservata ai membri
      operativi). Create/update passano da ``full_clean`` del modello: date
      coerenti, nessuna sovrapposizione sulla stessa stanza, stanza e
      inquilino dello stesso immobile (che deve essere quello attivo).
    - Inquilini: solo lettura delle proprie.

    Action ``cessione`` (POST, detail): wizard di cessione stanza.
    """

    serializer_class = RoomAssignmentSerializer
    protected_detail = (
        "Impossibile eliminare l'assegnazione: ha addebiti collegati."
    )

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [IsPropertyMember()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = RoomAssignment.objects.select_related("room", "tenant", "tenant__user").order_by(
            "-valid_from"
        )
        if _is_gestione(user):
            return qs.filter(room__property=get_request_property(self.request))
        return qs.filter(tenant__user=user)

    def _full_clean_o_400(self, obj):
        """``full_clean`` del modello → 400 DRF con i messaggi originali."""
        from rest_framework.exceptions import ValidationError

        try:
            obj.full_clean()
        except DjangoValidationError as e:
            raise ValidationError(
                e.message_dict if hasattr(e, "error_dict") else e.messages
            )

    def _valida_assignment(self, serializer):
        """Coerenza property (stanza e inquilino sull'immobile attivo) e
        validazione completa del modello (no-overlap, date)."""
        from rest_framework.exceptions import ValidationError

        prop = get_request_property(self.request)
        inst = serializer.instance

        def _val(campo, default=None):
            if campo in serializer.validated_data:
                return serializer.validated_data[campo]
            return getattr(inst, campo, default)

        room = _val("room")
        tenant = _val("tenant")
        if room is not None and room.property_id != prop.pk:
            raise ValidationError(
                {"room": "La stanza appartiene a un altro immobile."}
            )
        if tenant is not None and tenant.property_id != prop.pk:
            raise ValidationError(
                {"tenant": "L'inquilino appartiene a un altro immobile."}
            )
        conto = _val("bank_account_affitto")
        if conto is not None and not conto.owner.user.property_memberships.filter(
            property=prop
        ).exists():
            raise ValidationError(
                {"bank_account_affitto": "Conto estraneo a questo immobile."}
            )

        obj = RoomAssignment(
            pk=inst.pk if inst else None,
            room=room,
            tenant=tenant,
            valid_from=_val("valid_from"),
            valid_to=_val("valid_to"),
            canone_mensile=_val("canone_mensile"),
            bank_account_affitto=conto,
            costo_cessione=_val("costo_cessione"),
            data_atto_cessione=_val("data_atto_cessione"),
            note=_val("note", "") or "",
        )
        if inst is not None:
            # L'istanza rappresenta un update: senza questo flag full_clean
            # segnalerebbe il pk come duplicato.
            obj._state.adding = False
        self._full_clean_o_400(obj)

    def perform_create(self, serializer):
        self._valida_assignment(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._valida_assignment(serializer)
        serializer.save()

    @action(detail=True, methods=["post"], url_path="cessione")
    def cessione(self, request, pk=None):
        """Wizard cessione stanza: chiude l'assignment corrente a
        ``data_fine`` e ne apre uno nuovo dal giorno dopo per il nuovo
        inquilino, in transazione atomica.

        Body: ``{data_fine, nuovo_tenant, canone_mensile, costo_cessione?,
        data_atto_cessione?}``. Il ``costo_cessione`` sul nuovo assignment
        attiva i side-effect esistenti (Receivable registrazione 50% +
        Expense proprietari 50%, vedi ``properties/signals.py``).
        """
        from django.db import transaction
        from rest_framework.exceptions import ValidationError

        corrente = self.get_object()
        ser = CessioneAssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        prop = get_request_property(request)
        nuovo_tenant = v["nuovo_tenant"]
        if nuovo_tenant.property_id != prop.pk:
            raise ValidationError(
                {"nuovo_tenant": "L'inquilino appartiene a un altro immobile."}
            )
        data_fine = v["data_fine"]

        with transaction.atomic():
            corrente.valid_to = data_fine
            self._full_clean_o_400(corrente)
            corrente.save()

            nuovo = RoomAssignment(
                room=corrente.room,
                tenant=nuovo_tenant,
                valid_from=data_fine + datetime.timedelta(days=1),
                canone_mensile=v["canone_mensile"],
                costo_cessione=v.get("costo_cessione"),
                data_atto_cessione=v.get("data_atto_cessione"),
            )
            # Un errore qui (es. overlap col successivo) annulla anche la
            # chiusura del corrente: tutto-o-niente.
            self._full_clean_o_400(nuovo)
            nuovo.save()

        out = self.get_serializer
        return Response(
            {"chiuso": out(corrente).data, "nuovo": out(nuovo).data},
            status=status.HTTP_201_CREATED,
        )


class ContractViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Contratti di locazione dell'immobile attivo (CRUD per i membri
    operativi; la property è assegnata dal server)."""

    serializer_class = ContractSerializer
    permission_classes = [IsPropertyMember]
    queryset = Contract.objects.all()
    protected_detail = (
        "Impossibile eliminare il contratto: ha dati collegati."
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_pagatore(self, serializer):
        _valida_owner_membro(
            serializer.validated_data.get("default_pagatore_bollette"),
            get_request_property(self.request),
            "default_pagatore_bollette",
        )

    def perform_create(self, serializer):
        self._valida_pagatore(serializer)
        serializer.save(property=get_request_property(self.request))

    def perform_update(self, serializer):
        self._valida_pagatore(serializer)
        serializer.save()


class OwnerBankAccountViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Conti bancari dei membri dell'immobile attivo.

    Visibilità fra co-membri (decisione 2026-07-11): chi condivide un
    immobile col titolare vede i suoi conti. Scrittura solo sui PROPRI
    conti: l'owner è sempre il profilo del richiedente.
    """

    serializer_class = OwnerBankAccountSerializer
    permission_classes = [IsPropertyMember]
    queryset = OwnerBankAccount.objects.select_related("owner").order_by(
        "owner__nominativo", "ordinamento"
    )
    protected_detail = (
        "Impossibile eliminare il conto: ha movimenti bancari collegati."
    )

    def get_queryset(self):
        prop = get_request_property(self.request)
        return super().get_queryset().filter(
            owner__user__property_memberships__property=prop
        ).distinct()

    def _profilo_richiedente(self):
        from rest_framework.exceptions import PermissionDenied

        profilo = getattr(self.request.user, "owner_profile", None)
        if profilo is None:
            raise PermissionDenied(
                "Nessun profilo proprietario associato all'utente."
            )
        return profilo

    def _richiedi_titolare(self, conto):
        from rest_framework.exceptions import PermissionDenied

        if self.request.user.is_superuser:
            return
        if conto.owner.user_id != self.request.user.pk:
            raise PermissionDenied("Puoi modificare solo i tuoi conti.")

    def perform_create(self, serializer):
        serializer.save(owner=self._profilo_richiedente())

    def perform_update(self, serializer):
        self._richiedi_titolare(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._richiedi_titolare(instance)
        instance.delete()


# ---------------------------------------------------------------------------
# Immobili: CRUD, membri, quote, inviti (multiproprietà — Fase B)
# ---------------------------------------------------------------------------


class PropertyViewSet(ModelViewSet):
    """Immobili dell'utente.

    - list/retrieve: gli immobili di cui si è membri;
    - create: qualsiasi utente lato gestione (membro di almeno un immobile);
      chi crea diventa membro col ruolo indicato in ``ruolo_creatore``
      (default 'proprietario', con quota 1.0);
    - update: membri operativi (proprietario/gestore);
    - destroy: solo ruolo 'proprietario' e solo se l'immobile è vuoto.

    Azioni annidate: ``membri`` (GET/POST/DELETE), ``quote`` (GET/POST),
    ``inviti`` (POST).
    """

    from properties.serializers import PropertySerializer

    serializer_class = PropertySerializer

    def get_queryset(self):
        from properties.context import properties_accessibili
        from properties.models import Property

        return Property.objects.filter(
            pk__in=properties_accessibili(self.request.user).values("pk")
        ).order_by("nome")

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated

        return [IsAuthenticated()]

    def _ruolo(self, prop):
        from properties.context import ruolo_su_property

        return ruolo_su_property(self.request.user, prop)

    def _richiedi_operativo(self, prop):
        from rest_framework.exceptions import PermissionDenied

        from properties.models import PropertyMembership

        if self._ruolo(prop) not in (
            PropertyMembership.Ruolo.PROPRIETARIO,
            PropertyMembership.Ruolo.GESTORE,
        ):
            raise PermissionDenied("Operazione riservata a proprietari e gestori.")

    def _richiedi_proprietario(self, prop):
        from rest_framework.exceptions import PermissionDenied

        from properties.models import PropertyMembership

        if self._ruolo(prop) != PropertyMembership.Ruolo.PROPRIETARIO:
            raise PermissionDenied("Operazione riservata ai proprietari dell'immobile.")

    def create(self, request, *args, **kwargs):
        from django.db import transaction
        from rest_framework import status as st
        from rest_framework.exceptions import PermissionDenied

        from properties.models import OwnerProfile, OwnershipShare, PropertyMembership

        user = request.user
        if not (user.is_superuser or user.property_memberships.exists()):
            raise PermissionDenied(
                "Solo chi gestisce già un immobile può crearne di nuovi."
            )

        ruolo_creatore = request.data.get(
            "ruolo_creatore", PropertyMembership.Ruolo.PROPRIETARIO
        )
        if ruolo_creatore not in (
            PropertyMembership.Ruolo.PROPRIETARIO,
            PropertyMembership.Ruolo.GESTORE,
        ):
            return Response(
                {"detail": "ruolo_creatore deve essere 'proprietario' o 'gestore'."},
                status=st.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            prop = serializer.save()
            PropertyMembership.objects.create(
                property=prop, user=user, ruolo=ruolo_creatore,
            )
            if ruolo_creatore == PropertyMembership.Ruolo.PROPRIETARIO:
                profilo, _ = OwnerProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "nominativo": user.get_full_name() or user.username,
                    },
                )
                OwnershipShare.objects.create(
                    property=prop,
                    owner=profilo,
                    quota=Decimal("1.0000"),
                    valid_from=datetime.date.today(),
                )
        out = self.get_serializer(prop)
        return Response(out.data, status=st.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        self._richiedi_operativo(self.get_object())
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        from django.db.models.deletion import ProtectedError
        from rest_framework import status as st

        prop = self.get_object()
        self._richiedi_proprietario(prop)
        try:
            # Le quote create automaticamente alla creazione non rendono
            # "pieno" un immobile: un immobile senza dati operativi deve
            # restare cancellabile.
            from django.db import transaction

            with transaction.atomic():
                prop.ownership_shares.all().delete()
                prop.delete()
        except ProtectedError:
            return Response(
                {"detail": "L'immobile non è vuoto: rimuovere prima stanze, "
                           "contratti e dati collegati."},
                status=st.HTTP_409_CONFLICT,
            )
        return Response(status=st.HTTP_204_NO_CONTENT)

    # --- membri -------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="membri")
    def membri(self, request, pk=None):
        from rest_framework import status as st

        from properties.models import PropertyMembership
        from properties.serializers import PropertyMembershipSerializer

        prop = self.get_object()
        if request.method == "GET":
            qs = prop.memberships.select_related("user").order_by("user__username")
            return Response(PropertyMembershipSerializer(qs, many=True).data)

        self._richiedi_proprietario(prop)
        ser = PropertyMembershipSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        membership = PropertyMembership(
            property=prop,
            user=ser.validated_data["user"],
            ruolo=ser.validated_data["ruolo"],
            invitato_da=request.user,
        )
        try:
            membership.full_clean()
        except DjangoValidationError as e:
            return Response(
                {"detail": "; ".join(e.messages)}, status=st.HTTP_400_BAD_REQUEST
            )
        membership.save()
        return Response(
            PropertyMembershipSerializer(membership).data, status=st.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["delete", "patch"],
        url_path=r"membri/(?P<membership_id>\d+)",
    )
    def membro_dettaglio(self, request, pk=None, membership_id=None):
        from django.shortcuts import get_object_or_404
        from rest_framework import status as st

        from properties.models import PropertyMembership
        from properties.serializers import PropertyMembershipSerializer

        prop = self.get_object()
        self._richiedi_proprietario(prop)
        membership = get_object_or_404(
            PropertyMembership, pk=membership_id, property=prop
        )

        if request.method == "PATCH":
            ruolo = request.data.get("ruolo")
            if ruolo not in dict(PropertyMembership.Ruolo.choices):
                return Response(
                    {"detail": "Ruolo non valido."}, status=st.HTTP_400_BAD_REQUEST
                )
            if (
                membership.ruolo == PropertyMembership.Ruolo.PROPRIETARIO
                and ruolo != PropertyMembership.Ruolo.PROPRIETARIO
                and not prop.memberships.filter(
                    ruolo=PropertyMembership.Ruolo.PROPRIETARIO
                ).exclude(pk=membership.pk).exists()
            ):
                return Response(
                    {"detail": "L'immobile deve avere almeno un proprietario."},
                    status=st.HTTP_409_CONFLICT,
                )
            membership.ruolo = ruolo
            membership.save(update_fields=["ruolo"])
            return Response(PropertyMembershipSerializer(membership).data)

        # DELETE
        if (
            membership.ruolo == PropertyMembership.Ruolo.PROPRIETARIO
            and not prop.memberships.filter(
                ruolo=PropertyMembership.Ruolo.PROPRIETARIO
            ).exclude(pk=membership.pk).exists()
        ):
            return Response(
                {"detail": "L'immobile deve avere almeno un proprietario."},
                status=st.HTTP_409_CONFLICT,
            )
        membership.delete()
        return Response(status=st.HTTP_204_NO_CONTENT)

    # --- quote --------------------------------------------------------------

    @action(detail=True, methods=["get", "post"], url_path="quote")
    def quote(self, request, pk=None):
        """GET: quote correnti e storiche. POST: nuovo assetto dal
        ``valid_from`` indicato (chiude le quote aperte e crea il nuovo set,
        in transazione atomica; la somma deve fare 1.0)."""
        from django.db import transaction
        from rest_framework import status as st

        from properties.models import OwnershipShare, PropertyMembership
        from properties.serializers import (
            OwnershipShareSerializer,
            QuoteReplaceSerializer,
        )

        prop = self.get_object()
        if request.method == "GET":
            qs = prop.ownership_shares.select_related("owner").order_by(
                "-valid_from", "owner__nominativo"
            )
            return Response(OwnershipShareSerializer(qs, many=True).data)

        self._richiedi_proprietario(prop)
        ser = QuoteReplaceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        valid_from = ser.validated_data["valid_from"]
        voci = ser.validated_data["quote"]

        totale = Decimal("0")
        normalizzate = []
        visti: set[int] = set()
        for voce in voci:
            try:
                user_id = int(voce["user"])
                quota = Decimal(str(voce["quota"]))
            except (KeyError, TypeError, ValueError, ArithmeticError):
                return Response(
                    {"detail": "Ogni voce deve avere 'user' e 'quota'."},
                    status=st.HTTP_400_BAD_REQUEST,
                )
            if user_id in visti:
                return Response(
                    {"detail": f"Utente {user_id} ripetuto nelle quote."},
                    status=st.HTTP_400_BAD_REQUEST,
                )
            visti.add(user_id)
            membership = prop.memberships.filter(
                user_id=user_id, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
            ).select_related("user__owner_profile").first()
            if membership is None:
                return Response(
                    {"detail": f"L'utente {user_id} non è proprietario dell'immobile."},
                    status=st.HTTP_400_BAD_REQUEST,
                )
            profilo = getattr(membership.user, "owner_profile", None)
            if profilo is None:
                return Response(
                    {"detail": f"L'utente {user_id} non ha un profilo proprietario."},
                    status=st.HTTP_400_BAD_REQUEST,
                )
            normalizzate.append((profilo, quota))
            totale += quota
        if abs(totale - Decimal("1")) > Decimal("0.001"):
            return Response(
                {"detail": f"La somma delle quote è {totale}: deve fare 1.0."},
                status=st.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            aperte = prop.ownership_shares.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gt=valid_from),
                valid_from__lt=valid_from,
            )
            aperte.update(valid_to=valid_from)
            prop.ownership_shares.filter(valid_from__gte=valid_from).delete()
            nuove = [
                OwnershipShare.objects.create(
                    property=prop, owner=profilo, quota=quota, valid_from=valid_from,
                )
                for profilo, quota in normalizzate
            ]
        return Response(
            OwnershipShareSerializer(nuove, many=True).data,
            status=st.HTTP_201_CREATED,
        )

    # --- inviti -------------------------------------------------------------

    @action(detail=True, methods=["post"], url_path="inviti")
    def inviti(self, request, pk=None):
        from rest_framework import status as st

        from accounts.inviti import invia_invito_membro
        from properties.serializers import InvitoMembroSerializer

        prop = self.get_object()
        self._richiedi_proprietario(prop)
        ser = InvitoMembroSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        esito = invia_invito_membro(
            prop,
            ser.validated_data["email"],
            ser.validated_data["ruolo"],
            nominativo=ser.validated_data.get("nominativo", ""),
            invitato_da=request.user,
        )
        if esito["esito"] != "inviato":
            return Response(
                {"detail": esito["errore"]}, status=st.HTTP_400_BAD_REQUEST
            )
        return Response(esito, status=st.HTTP_201_CREATED)
