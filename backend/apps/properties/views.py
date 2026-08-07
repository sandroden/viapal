"""
ViewSet per l'app properties.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Exists, Max, OuterRef, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsPropertyMember
from properties.context import get_request_property
from properties.fascicolo import costruisci_fascicolo
from properties.models import (
    Contract,
    DocumentTemplate,
    GalleryArea,
    GalleryImage,
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Property,
    PropertyDocument,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)
from properties.serializers import (
    CessioneAssignmentSerializer,
    ContractSerializer,
    DocumentTemplateSerializer,
    GalleryAreaSerializer,
    GalleryImageSerializer,
    OwnerBankAccountSerializer,
    OwnerProfileSerializer,
    PrimaAssegnazioneSerializer,
    PropertyDocumentSerializer,
    PropertySerializer,
    PublicGallerySerializer,
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


class OwnerProfileViewSet(mixins.UpdateModelMixin, ReadOnlyModelViewSet):
    """Profili proprietario dei membri dell'immobile attivo.

    Scrittura (PATCH): il titolare aggiorna la propria anagrafica; i
    proprietari dell'immobile possono completare quella degli altri membri
    (i documenti generati chiedono i dati di tutti i comproprietari). Il
    gestore no, coerente con membri e quote. L'anagrafica è globale: vale
    per tutti gli immobili in cui il profilo compare.
    """

    serializer_class = OwnerProfileSerializer
    permission_classes = [IsPropertyMember]
    queryset = OwnerProfile.objects.select_related("user").order_by("nominativo")

    def get_queryset(self):
        prop = get_request_property(self.request)
        return super().get_queryset().filter(
            user__property_memberships__property=prop
        ).distinct()

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated

        if self.action in ("update", "partial_update"):
            # Il gate vero è object-level in ``perform_update``: qui non
            # applichiamo il blocco sola_lettura di ``IsPropertyMember``,
            # altrimenti un membro in sola lettura non potrebbe aggiornare
            # nemmeno la propria anagrafica.
            return [IsAuthenticated()]
        return [IsPropertyMember()]

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            from properties.serializers import OwnerProfileUpdateSerializer

            return OwnerProfileUpdateSerializer
        return OwnerProfileSerializer

    def _richiedi_titolare_o_proprietario(self, profilo):
        from rest_framework.exceptions import PermissionDenied

        from properties.context import ruolo_su_property
        from properties.models import PropertyMembership

        user = self.request.user
        if user.is_superuser or profilo.user_id == user.pk:
            return
        prop = get_request_property(self.request)
        if ruolo_su_property(user, prop) == PropertyMembership.Ruolo.PROPRIETARIO:
            return
        raise PermissionDenied(
            "Puoi modificare solo la tua anagrafica; quella degli altri "
            "membri è riservata ai proprietari dell'immobile."
        )

    def perform_update(self, serializer):
        self._richiedi_titolare_o_proprietario(serializer.instance)
        serializer.save()


class TenantProfileViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, ReadOnlyModelViewSet
):
    """
    Profili inquilini.
    - Proprietari: vedono tutti. Per default la lista mostra solo gli attivi
      (con assignment in corso oggi); query param ``?solo_attivi=0`` per
      includere anche gli storici. In alternativa, ``?anno=YYYY`` filtra gli
      inquilini con almeno un assignment che si sovrappone all'anno indicato
      (ha la precedenza su ``solo_attivi``). ``?con_assignment=1`` (componibile
      con gli altri filtri) tiene solo gli inquilini con almeno una
      assegnazione — passata, presente o futura — escludendo i profili
      creati e mai assegnati.
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
        # ``ha_assignment``: il frontend distingue i profili mai assegnati
        # (badge + azione "assegna" in lista). Exists → nessuna N+1.
        qs = (
            TenantProfile.objects.select_related("user")
            .annotate(
                ha_assignment=Exists(
                    RoomAssignment.objects.filter(tenant=OuterRef("pk"))
                )
            )
            .order_by("nominativo")
        )
        if not _is_gestione(user):
            return qs.filter(user=user)
        qs = qs.filter(property=get_request_property(self.request))

        # I filtri di "attività" valgono solo per la lista: il dettaglio (e
        # quindi update/invita) deve raggiungere anche gli inquilini appena
        # creati (senza assignment) e quelli storici.
        if self.action != "list":
            return qs

        # ``con_assignment=1``: solo inquilini con almeno una assegnazione
        # (anche futura o già chiusa). Esclude i profili "fantasma" creati e
        # mai assegnati; tipicamente usato con ``solo_attivi=0``.
        if self.request.query_params.get("con_assignment") in ("1", "true", "True"):
            qs = qs.filter(assignments__isnull=False).distinct()

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
                # Include anche i profili senza alcuna assegnazione: un
                # inquilino appena creato (es. prima-assegnazione fallita)
                # deve restare visibile nella lista di default, non solo
                # con "Mostra anche storici".
                return qs.filter(
                    Q(assignments__isnull=True)
                    | (
                        Q(assignments__valid_from__lte=fine)
                        & (
                            Q(assignments__valid_to__isnull=True)
                            | Q(assignments__valid_to__gt=inizio)
                        )
                    )
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
    # JSONParser serve alla sola action ``genera``: gli upload continuano a
    # viaggiare in multipart, DRF sceglie in base al Content-Type.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in {"genera", "generabili"}:
            # Generare un documento è un atto della proprietà, non
            # dell'inquilino.
            return [IsPropertyMember()]
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

    @action(detail=False, methods=["get"], url_path="fascicolo")
    def fascicolo(self, request):
        """Checklist dei documenti con gli stati (valido/scadenza/scaduto/…).

        L'inquilino ottiene il proprio fascicolo; il proprietario quello
        dell'inquilino indicato in ``?tenant=<id>`` (dell'immobile attivo).
        """
        from rest_framework.exceptions import PermissionDenied, ValidationError

        documenti = list(self.get_queryset())
        if _is_gestione(request.user):
            tenant_id = request.query_params.get("tenant")
            if not tenant_id:
                raise ValidationError({"tenant": "Indicare l'inquilino."})
            tenant = get_object_or_404(
                TenantProfile,
                pk=tenant_id,
                property=get_request_property(request),
            )
        else:
            tenant = getattr(request.user, "tenant_profile", None)
            if tenant is None:
                raise PermissionDenied("Nessun profilo inquilino associato all'utente.")
        return Response(costruisci_fascicolo(tenant, documenti))

    @action(detail=False, methods=["get"], url_path="generabili")
    def generabili(self, request):
        """Documenti che l'applicazione sa produrre per un inquilino.

        Il fascicolo elenca solo i file che esistono: senza questo elenco
        non ci sarebbe modo di sapere *cosa* si può generare. È una GET
        perché non produce nulla — a differenza dell'anteprima, che passa
        dal generatore e resta una POST.

        ``?tenant=<id>`` (dell'immobile attivo); per ciascun documento,
        ``esistente`` è il PDF che abbiamo già prodotto, se c'è.
        """
        from properties.documenti import GENERATORI

        tenant = self._tenant_per_elenco(request)
        return Response(
            {
                "tenant": tenant.pk,
                "documenti": [
                    {
                        "codice": str(documento.chiave),
                        "titolo": documento.titolo,
                        "tipo": str(documento.tipo_documento),
                        "tipo_display": TenantDocument.Tipo(
                            documento.tipo_documento
                        ).label,
                        "esistente": self._esistente(tenant, documento.tipo_documento),
                    }
                    for documento in GENERATORI.values()
                ],
            }
        )

    @action(detail=False, methods=["post"], url_path="genera")
    def genera(self, request):
        """Anteprima o generazione di un documento PDF per un inquilino.

        Body: ``{tenant, documento, dry_run=True, assignment?}``.

        Con ``dry_run`` (default) non scrive nulla e restituisce l'elenco
        dei dati mancanti, ciascuno col posto in cui compilarlo; con
        ``dry_run=false`` genera il PDF e lo salva come ``TenantDocument``.
        Convenzione condivisa con l'invio dei riepiloghi addebiti.

        Essendo una POST, il ruolo ``sola_lettura`` non vede nemmeno
        l'anteprima: stesso compromesso già accettato altrove.
        """
        from rest_framework.exceptions import ValidationError

        from properties.documenti import DatiInsufficienti, anteprima

        tenant = self._tenant_per_generazione(request)
        codice = request.data.get("documento")
        assignment = self._assignment_per_generazione(request, tenant)
        try:
            esito = anteprima(tenant, codice, assignment=assignment)
        except KeyError:
            raise ValidationError({"documento": "Documento non riconosciuto."})
        except DatiInsufficienti as e:
            raise ValidationError({"detail": str(e)})

        esistente = self._documento_generato(tenant, esito["documento"])
        esito["esistente"] = self._riferimento(esistente)
        if request.data.get("dry_run", True):
            return Response(esito)

        if not esito["completo"]:
            raise ValidationError(
                {"detail": "Dati incompleti.", "mancanti": esito["mancanti"]}
            )
        documento = self._salva_generato(request, tenant, codice, assignment)
        return Response(
            {
                **self.get_serializer(documento).data,
                "sostituito": esistente.pk if esistente else None,
            },
            status=status.HTTP_201_CREATED,
        )

    def _tenant_per_generazione(self, request):
        return self._tenant_indicato(request, request.data.get("tenant"))

    def _tenant_per_elenco(self, request):
        return self._tenant_indicato(request, request.query_params.get("tenant"))

    @staticmethod
    def _tenant_indicato(request, tenant_id):
        from rest_framework.exceptions import ValidationError

        if not tenant_id:
            raise ValidationError({"tenant": "Indicare l'inquilino."})
        return get_object_or_404(
            TenantProfile, pk=tenant_id, property=get_request_property(request)
        )

    def _assignment_per_generazione(self, request, tenant):
        assignment_id = request.data.get("assignment")
        if not assignment_id:
            return None
        return get_object_or_404(
            RoomAssignment, pk=assignment_id, tenant=tenant
        )

    @staticmethod
    def _documento_generato(tenant, tipo):
        """Il PDF prodotto dal sistema per quel tipo, se già esiste."""
        return tenant.documenti.filter(tipo=tipo, generato=True).first()

    @staticmethod
    def _riferimento(documento):
        """Il minimo per dire «ne esiste già uno, del giorno tale»."""
        if documento is None:
            return None
        return {
            "id": documento.pk,
            "descrizione": documento.descrizione,
            "created_at": documento.created_at,
        }

    def _esistente(self, tenant, tipo):
        return self._riferimento(self._documento_generato(tenant, tipo))

    def _salva_generato(self, request, tenant, codice, assignment):
        """Genera il PDF e sostituisce il precedente, se il sistema ne
        aveva già prodotto uno.

        Sostituisce **solo** i documenti con ``generato=True``: il flusso
        reale è genera → stampa → firma → scansiona → ricarica sotto lo
        stesso tipo, e una rigenerazione non deve distruggere l'unico
        originale firmato.
        """
        from django.core.files.base import ContentFile
        from django.db import transaction

        from properties.documenti import genera_pdf

        pdf, nome_file, tipo = genera_pdf(tenant, codice, assignment=assignment)
        with transaction.atomic():
            for vecchio in tenant.documenti.filter(tipo=tipo, generato=True):
                vecchio.file.delete(save=False)
                vecchio.delete()
            return TenantDocument.objects.create(
                tenant=tenant,
                tipo=tipo,
                file=ContentFile(pdf, name=nome_file),
                descrizione=f"generato il {datetime.date.today():%d/%m/%Y}",
                generato=True,
                caricato_da=request.user,
            )

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


class PropertyDocumentViewSet(ModelViewSet):
    """
    Documenti dell'immobile (contratto, side letter, registrazione,
    regolamento condominiale).
    - Lato gestione: CRUD completo sull'immobile attivo (scrittura preclusa
      al ruolo sola_lettura); la ``property`` è sempre quella della richiesta.
    - Inquilini: sola lettura dei documenti del proprio immobile marcati
      ``visibile_inquilini`` (sezione "Documenti della casa").
    """

    serializer_class = PropertyDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method not in SAFE_METHODS:
            return [IsPropertyMember()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = PropertyDocument.objects.select_related("property", "contract")
        if not _is_gestione(user):
            tenant = getattr(user, "tenant_profile", None)
            if tenant is None:
                return qs.none()
            # Un documento collegato a un contratto è una carta di quel
            # contratto: la vede solo chi ci sta dentro. Senza contratto
            # sull'assegnazione l'inquilino non ne vede nessuna.
            miei_contratti = RoomAssignment.objects.filter(
                tenant=tenant, contract__isnull=False
            ).values_list("contract_id", flat=True)
            return qs.filter(
                property_id=tenant.property_id, visibile_inquilini=True
            ).filter(Q(contract__isnull=True) | Q(contract_id__in=miei_contratti))
        return qs.filter(property=get_request_property(self.request))

    def _valida_contratto(self, serializer, prop):
        """Il contratto, se indicato, è di questo immobile."""
        from rest_framework.exceptions import ValidationError

        contract = serializer.validated_data.get("contract")
        if contract is not None and contract.property_id != prop.pk:
            raise ValidationError(
                {"contract": "Il contratto appartiene a un altro immobile."}
            )

    def perform_create(self, serializer):
        prop = get_request_property(self.request)
        self._valida_contratto(serializer, prop)
        serializer.save(property=prop, caricato_da=self.request.user)

    def perform_update(self, serializer):
        self._valida_contratto(serializer, get_request_property(self.request))
        serializer.save()


class RoomViewSet(ProtectedDestroyMixin, ModelViewSet):
    """
    Stanze.
    - Proprietari: tutte, con CRUD completo (scrittura riservata ai membri
      operativi; la property è assegnata dal server sull'immobile attivo),
      inclusi i campi galleria (upload foto via multipart). Create/update
      passano da ``full_clean``: su un immobile a unità intera non è
      possibile creare una seconda stanza (vedi ``Room.clean``).
    - Inquilini: solo lettura delle stanze con assignment attivo per sé.
    """

    serializer_class = RoomSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
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

    # Campi scrivibili di Room (esclusa 'property', assegnata dal server).
    _CAMPI_SCRIVIBILI = (
        "nome", "superficie_mq", "foto", "ordinamento",
        "colore", "descrizione", "disponibile", "libera_dal",
        "prezzo_mensile", "pubblica",
    )

    def _full_clean_o_400(self, obj):
        from rest_framework.exceptions import ValidationError

        try:
            obj.full_clean(exclude=["foto"])
        except DjangoValidationError as e:
            raise ValidationError(
                e.message_dict if hasattr(e, "error_dict") else e.messages
            )

    def _val_room(self, serializer, prop):
        """Ricostruisce l'istanza Room (creazione o update) per full_clean,
        senza toccare i file caricati (esclusi dalla validazione).

        Un campo assente sia da ``validated_data`` sia dall'istanza (caso:
        creazione con payload minimo, campo senza default esplicito nel
        model) va omesso dal costruttore, non forzato a ``None``: altrimenti
        ``Room(colore=None, ...)`` fallirebbe ``full_clean`` su un CharField
        non nullable invece di prendere il default del modello ("").
        """
        inst = serializer.instance
        kwargs = {}
        for campo in self._CAMPI_SCRIVIBILI:
            if campo == "foto":
                continue
            if campo in serializer.validated_data:
                kwargs[campo] = serializer.validated_data[campo]
            elif inst is not None:
                kwargs[campo] = getattr(inst, campo)

        obj = Room(pk=inst.pk if inst else None, property=prop, **kwargs)
        if inst is not None:
            obj._state.adding = False
        return obj

    def perform_create(self, serializer):
        prop = get_request_property(self.request)
        self._full_clean_o_400(self._val_room(serializer, prop))
        serializer.save(property=prop)

    def perform_update(self, serializer):
        prop = serializer.instance.property
        self._full_clean_o_400(self._val_room(serializer, prop))
        serializer.save()


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
        if conto is not None and not conto.properties.filter(pk=prop.pk).exists():
            raise ValidationError(
                {"bank_account_affitto": "Conto non in uso su questo immobile."}
            )
        contract = _val("contract")
        if contract is not None and contract.property_id != prop.pk:
            raise ValidationError(
                {"contract": "Il contratto appartiene a un altro immobile."}
            )

        obj = RoomAssignment(
            pk=inst.pk if inst else None,
            room=room,
            tenant=tenant,
            contract=contract,
            valid_from=_val("valid_from"),
            valid_to=_val("valid_to"),
            canone_mensile=_val("canone_mensile"),
            bank_account_affitto=conto,
            costo_cessione=_val("costo_cessione"),
            data_atto_cessione=_val("data_atto_cessione"),
            subentra_a=_val("subentra_a"),
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
        if corrente.valid_to is not None:
            raise ValidationError(
                {"detail": "L'assegnazione è già chiusa: non può essere ceduta."}
            )
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
                # Subentrare vuol dire entrare nel contratto del cedente:
                # è quello che dice l'atto di subentro. Correggibile poi
                # dall'assegnazione, se il subentrante firma un contratto suo.
                contract=corrente.contract,
                valid_from=data_fine + datetime.timedelta(days=1),
                canone_mensile=v["canone_mensile"],
                costo_cessione=v.get("costo_cessione"),
                data_atto_cessione=v.get("data_atto_cessione"),
                # Qui il subentro è certo, non dedotto: lo registriamo così
                # l'atto di subentro sa chi è l'uscente.
                subentra_a=corrente,
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

    @action(detail=False, methods=["post"], url_path="prima-assegnazione")
    def prima_assegnazione(self, request):
        """Crea il primo RoomAssignment di un inquilino nuovo: canone,
        ciclo di fatturazione, deposito (con rate opzionali), quota
        condominio specifica opzionale e primo addebito affitto (pro-rata
        sul mese parziale), in un'unica operazione atomica.

        Ordine critico per i signal di ``properties/signals.py``
        (``genera_receivable_deposito_da_*``, idempotenti sulla presenza di
        un Receivable DEPOSITO positivo): il ciclo di fatturazione e
        l'assignment sono salvati PRIMA di valorizzare il deposito sul
        tenant, cosicché i signal risultino no-op quando scattano; le rate
        vengono create qui a mano e solo alla fine si imposta
        ``tenant.deposito_versato``, che fa ripartire il signal ma lo trova
        già idempotente (le rate esistono già) e non duplica nulla.
        """
        from django.db import transaction
        from rest_framework.exceptions import ValidationError

        prop = get_request_property(request)
        ser = PrimaAssegnazioneSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        tenant = v["tenant"]
        room = v.get("room")
        valid_from = v["valid_from"]

        if room is None:
            # Immobile a unità intera: risolve (o crea, se per qualche
            # motivo manca ancora) l'unica Room implicita della property.
            # Immobile a stanze: 'room' è obbligatorio.
            if prop.tipo_gestione == Property.TipoGestione.UNITA_INTERA:
                room = prop.rooms.first()
                if room is None:
                    room = Room.objects.create(property=prop, nome="Appartamento")
            else:
                raise ValidationError({"room": "Selezionare la stanza."})

        if room.property_id != prop.pk:
            raise ValidationError(
                {"room": "La stanza appartiene a un altro immobile."}
            )
        if tenant.property_id != prop.pk:
            raise ValidationError(
                {"tenant": "L'inquilino appartiene a un altro immobile."}
            )
        if tenant.assignments.filter(valid_to__isnull=True).exists():
            raise ValidationError(
                {"tenant": "L'inquilino ha già un'assegnazione in corso."}
            )

        # Il contratto sotto cui entra. Un `contract` assente dalla richiesta
        # significa "non me ne sono occupato": si propone quello attivo alla
        # data. Un `contract: null` esplicito significa "nessun contratto" e
        # va rispettato — è la scelta di chi non vuole che veda quelle carte.
        if "contract" in v:
            contract = v["contract"]
        else:
            contract = prop.contratto_attivo(valid_from)
        if contract is not None and contract.property_id != prop.pk:
            raise ValidationError(
                {"contract": "Il contratto appartiene a un altro immobile."}
            )

        deposito_totale = v.get("deposito_totale")
        rate_deposito = v.get("rate_deposito") or []
        if deposito_totale is not None:
            from billing.models import Receivable

            deposito_gia_registrato = (
                Receivable.objects.filter(
                    assignment__tenant=tenant,
                    causale=Receivable.Causale.DEPOSITO,
                    importo_dovuto__gt=0,
                ).exists()
                or tenant.deposito_versato > 0
            )
            if deposito_gia_registrato:
                raise ValidationError(
                    {"deposito_totale": "Deposito già registrato per questo inquilino."}
                )

        quota_condominio_mensile = v.get("quota_condominio_mensile")
        contratto_attivo_quota = None
        quota_diversa = False
        if quota_condominio_mensile is not None:
            from billing.models import TenantCondominioRate

            # Il contratto, se c'è, è solo il documento in cui la quota è
            # pattuita: la quota resta registrabile anche senza.
            contratto_attivo_quota = prop.contratto_attivo(valid_from)
            quota_generica_corrente = (
                TenantCondominioRate.objects.filter(
                    property=prop,
                    tenant__isnull=True,
                    valid_from__lte=valid_from,
                )
                .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=valid_from))
                .order_by("-valid_from")
                .first()
            )
            quota_diversa = (
                quota_generica_corrente is None
                or quota_generica_corrente.importo_mensile.quantize(Decimal("0.01"))
                != quota_condominio_mensile.quantize(Decimal("0.01"))
            )

        with transaction.atomic():
            tenant.ciclo_fatturazione = v["ciclo_fatturazione"]
            tenant.save(update_fields=["ciclo_fatturazione", "updated_at"])

            nuovo = RoomAssignment(
                room=room,
                tenant=tenant,
                contract=contract,
                valid_from=valid_from,
                canone_mensile=v["canone_mensile"],
            )
            self._full_clean_o_400(nuovo)
            nuovo.save()

            rate_deposito_ids: list[int] = []
            if deposito_totale is not None:
                from billing.models import Receivable, StatoPagamento

                n = len(rate_deposito)
                for i, rata in enumerate(rate_deposito, start=1):
                    descrizione = (
                        "Deposito (versamento)"
                        if n == 1
                        else f"Deposito (versamento) — rata {i}/{n}"
                    )
                    rec = Receivable.objects.create(
                        assignment=nuovo,
                        causale=Receivable.Causale.DEPOSITO,
                        descrizione=descrizione,
                        competenza_da=rata["scadenza"],
                        competenza_a=None,
                        scadenza=rata["scadenza"],
                        importo_dovuto=rata["importo"],
                        stato=StatoPagamento.ATTESO,
                    )
                    rate_deposito_ids.append(rec.pk)

                tenant.deposito_versato = deposito_totale
                tenant.data_versamento_deposito = (
                    v.get("data_versamento_deposito") or valid_from
                )
                tenant.save(
                    update_fields=[
                        "deposito_versato",
                        "data_versamento_deposito",
                        "updated_at",
                    ]
                )

            quota_condominio_creata = False
            if quota_condominio_mensile is not None and quota_diversa:
                from billing.models import TenantCondominioRate

                TenantCondominioRate.objects.create(
                    property=prop,
                    contract=contratto_attivo_quota,
                    tenant=tenant,
                    valid_from=valid_from,
                    importo_mensile=quota_condominio_mensile,
                    note="Creata da prima assegnazione",
                )
                quota_condominio_creata = True

            # Primo addebito affitto: genera i canoni dal mese di ingresso
            # fino al mese corrente (uno solo, se l'ingresso è futuro), con
            # il pro-rata sul mese parziale già gestito dal calcolo. Va fatto
            # DOPO la quota specifica, che entra nel canone pieno; la
            # generazione è idempotente per (assignment, competenza).
            from billing.calc.rent import genera_pagamenti_mese

            rent_receivable_ids: list[int] = []
            oggi = datetime.date.today()
            cursore = valid_from.replace(day=1)
            fine = max(oggi.replace(day=1), cursore)
            while cursore <= fine:
                esito = genera_pagamenti_mese(
                    cursore.year,
                    cursore.month,
                    tenant_id=tenant.pk,
                    property=prop,
                )
                rent_receivable_ids.extend(esito.get("payments", []))
                cursore = (
                    cursore.replace(year=cursore.year + 1, month=1)
                    if cursore.month == 12
                    else cursore.replace(month=cursore.month + 1)
                )

        return Response(
            {
                "assignment": self.get_serializer(nuovo).data,
                "rate_deposito_ids": rate_deposito_ids,
                "rent_receivable_ids": rent_receivable_ids,
                "quota_condominio_creata": quota_condominio_creata,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="rigenera-receivable")
    def rigenera_receivable(self, request, pk=None):
        """Rigenera gli addebiti d'affitto dell'assegnazione dopo una
        correzione (canone e/o data di inizio sbagliati all'inserimento).

        Per ogni mese interessato — l'unione dei mesi dei Receivable AFFITTO
        già esistenti e dei mesi da ``valid_from`` a oggi (o a ``valid_to``
        se precedente) — richiama ``genera_pagamenti_mese`` con ``force``:
        la guardia allocations è applicata lì (un Receivable con incassi
        imputati non viene mai sovrascritto), così come il rilink dei
        Receivable rimasti su un altro assignment dello stesso inquilino.

        Dopo il loop elimina gli orfani: Receivable AFFITTO di questo
        assignment senza allocations la cui chiave non è più stata generata
        (es. il mese pieno sostituito dal pro-rata dopo lo spostamento di
        ``valid_from``). Gli orfani CON allocations restano intatti e sono
        conteggiati in ``skippati_per_allocation``; gli orfani pro-rata
        (``is_aggiustamento``) ancora dentro il periodo dell'assegnazione
        potrebbero essere rettifiche manuali legittime: per prudenza non si
        eliminano e finiscono in ``non_eliminati_ambigui``.
        """
        from django.db import transaction

        from billing.calc.rent import genera_pagamenti_mese
        from billing.models import Receivable

        assignment = self.get_object()
        prop = get_request_property(request)

        def _mese_succ(d: datetime.date) -> datetime.date:
            if d.month == 12:
                return d.replace(year=d.year + 1, month=1)
            return d.replace(month=d.month + 1)

        # Mesi da rigenerare: quelli dei Receivable esistenti (coprono anche
        # le generazioni anticipate) più il range valid_from → oggi/valid_to
        # (copre i mesi nuovi se la data di inizio è stata anticipata).
        mesi: set[tuple[int, int]] = set(
            Receivable.objects.filter(
                assignment=assignment, causale=Receivable.Causale.AFFITTO
            )
            .values_list("competenza_da__year", "competenza_da__month")
            .distinct()
        )
        cursore = assignment.valid_from.replace(day=1)
        fine = datetime.date.today().replace(day=1)
        if assignment.valid_to is not None:
            fine = min(fine, assignment.valid_to.replace(day=1))
        fine = max(fine, cursore)  # ingresso futuro: almeno il primo mese
        while cursore <= fine:
            mesi.add((cursore.year, cursore.month))
            cursore = _mese_succ(cursore)

        creati = 0
        aggiornati = 0
        eliminati = 0
        ambigui = 0
        skip_alloc_ids: set[int] = set()
        receivable_ids: set[int] = set()

        with transaction.atomic():
            for anno, mese in sorted(mesi):
                esito = genera_pagamenti_mese(
                    anno,
                    mese,
                    force=True,
                    tenant_id=assignment.tenant_id,
                    property=prop,
                )
                creati += esito["creati"]
                aggiornati += esito["aggiornati"]
                skip_alloc_ids.update(
                    d["receivable_id"] for d in esito["skippati_per_allocation"]
                )
                receivable_ids.update(esito["payments"])

            # Pulizia orfani: chiavi (competenza_da, competenza_a) non più
            # prodotte dalla rigenerazione.
            orfani = Receivable.objects.filter(
                assignment=assignment, causale=Receivable.Causale.AFFITTO
            ).exclude(pk__in=receivable_ids)
            for rec in orfani:
                if rec.allocations.exists():
                    # Guardia allocations: il dato riconciliato è intoccabile.
                    skip_alloc_ids.add(rec.pk)
                    receivable_ids.add(rec.pk)
                    continue
                fuori_periodo = rec.competenza_da < assignment.valid_from or (
                    assignment.valid_to is not None
                    and (
                        rec.competenza_da > assignment.valid_to
                        or (
                            rec.competenza_a is not None
                            and rec.competenza_a > assignment.valid_to
                        )
                    )
                )
                if fuori_periodo or not rec.is_aggiustamento:
                    rec.delete()
                    eliminati += 1
                else:
                    # Pro-rata dentro il periodo ma con chiave non rigenerata:
                    # potrebbe essere una rettifica manuale. Non si elimina.
                    ambigui += 1
                    receivable_ids.add(rec.pk)

        return Response(
            {
                "creati": creati,
                "aggiornati": aggiornati,
                "skippati_per_allocation": len(skip_alloc_ids),
                "eliminati": eliminati,
                "non_eliminati_ambigui": ambigui,
                "receivable_ids": sorted(receivable_ids),
            }
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


class DocumentTemplateViewSet(ModelViewSet):
    """Modelli dei documenti generati, uno per immobile.

    Il testo dei documenti è un dato dell'immobile, non codice: si carica
    da qui. Le due action di supporto servono a chi scrive un modello —
    l'esempio da cui partire e l'elenco dei segnaposto disponibili — e
    sono entrambe derivate dal generatore, quindi non possono divergere da
    quello che la generazione sostituirà davvero.
    """

    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsPropertyMember]
    queryset = DocumentTemplate.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError

        prop = get_request_property(self.request)
        codice = serializer.validated_data.get("codice")
        # ``property`` è assegnata dal server, quindi DRF non può dedurre il
        # vincolo di unicità: senza questo controllo si arriverebbe a un
        # IntegrityError invece che a un 400 leggibile.
        if DocumentTemplate.objects.filter(property=prop, codice=codice).exists():
            raise ValidationError(
                {"codice": "Esiste già un modello per questo documento: modificalo."}
            )
        serializer.save(property=prop)

    @staticmethod
    def _codice(request):
        from rest_framework.exceptions import ValidationError

        from properties.documenti import GENERATORI

        codice = request.query_params.get("codice")
        if codice not in GENERATORI:
            raise ValidationError({"codice": "Documento non riconosciuto."})
        return codice

    @action(detail=False, methods=["get"], url_path="esempio")
    def esempio(self, request):
        """HTML di esempio versionato nel repository, da adattare."""
        from properties.documenti import esempio

        codice = self._codice(request)
        return Response({"codice": codice, "corpo_html": esempio(codice)})

    @action(detail=False, methods=["get"], url_path="segnaposto")
    def segnaposto(self, request):
        """Segnaposto disponibili nel modello di quel documento."""
        from properties.documenti import GENERATORI, segnaposto

        codice = self._codice(request)
        return Response(
            {
                "codice": codice,
                "titolo": GENERATORI[codice].titolo,
                "segnaposto": segnaposto(codice),
            }
        )


class OwnerBankAccountViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Conti bancari in uso sull'immobile attivo.

    Non più "i conti dei membri" (decisione 2026-07-11, superata il
    2026-08-07): la membership diceva che un gestore doveva vedersi proporre
    i propri conti come destinazione dei bonifici di un immobile altrui. Ora
    conta il collegamento esplicito ``properties``.

    Scrittura sui dati del conto solo al titolare (+ superuser); collegare e
    scollegare un conto dall'immobile spetta invece a chi lo gestisce.
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
        return super().get_queryset().per_property(prop)

    def _profilo_richiedente(self):
        from rest_framework.exceptions import PermissionDenied

        profilo = getattr(self.request.user, "owner_profile", None)
        if profilo is None:
            if self.request.user.is_superuser:
                raise PermissionDenied(
                    "Sei superuser senza profilo proprietario: scegli "
                    "l'intestatario del conto tra i membri."
                )
            raise PermissionDenied(
                "Nessun profilo proprietario associato all'utente."
            )
        return profilo

    def _owner_per_create(self):
        """L'owner del conto è il profilo del richiedente; il superuser può
        indicarne un altro col campo ``owner`` (coerente col bypass di
        ``_richiedi_titolare``), purché membro dell'immobile attivo."""
        from rest_framework.exceptions import ValidationError

        owner_id = self.request.data.get("owner")
        if owner_id and self.request.user.is_superuser:
            prop = get_request_property(self.request)
            profilo = OwnerProfile.objects.filter(
                pk=owner_id, user__property_memberships__property=prop
            ).first()
            if profilo is None:
                raise ValidationError(
                    {"owner": "Il profilo indicato non è membro dell'immobile."}
                )
            return profilo
        return self._profilo_richiedente()

    def _richiedi_titolare(self, conto):
        from rest_framework.exceptions import PermissionDenied

        if self.request.user.is_superuser:
            return
        if conto.owner.user_id != self.request.user.pk:
            raise PermissionDenied("Puoi modificare solo i tuoi conti.")

    def _richiedi_gestione(self, prop):
        """Collegare/scollegare un conto è un atto di gestione dell'immobile,
        non di titolarità del conto: la fa chi lo amministra, per qualsiasi
        conto dei membri (come già sceglie il conto utenze fra quelli altrui).
        """
        from rest_framework.exceptions import PermissionDenied

        from properties.context import ruolo_su_property
        from properties.models import PropertyMembership

        ruolo = ruolo_su_property(self.request.user, prop)
        if ruolo not in (
            PropertyMembership.Ruolo.PROPRIETARIO,
            PropertyMembership.Ruolo.GESTORE,
        ):
            raise PermissionDenied(
                "Serve essere proprietario o gestore dell'immobile."
            )

    def perform_create(self, serializer):
        # Un conto creato dal pannello di un immobile nasce in uso lì.
        conto = serializer.save(owner=self._owner_per_create())
        conto.properties.add(get_request_property(self.request))

    def perform_update(self, serializer):
        self._richiedi_titolare(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._richiedi_titolare(instance)
        instance.delete()

    @action(detail=False, methods=["get"])
    def collegabili(self, request):
        """I conti dei membri non ancora in uso su questo immobile.

        Alimenta il dialog "Usa un conto esistente": è il solo punto in cui
        compaiono conti estranei all'immobile, quindi solo quelli attivi (un
        conto dismesso non si propone), senza IBAN in chiaro e riservato a chi
        può davvero collegarli — un `sola_lettura` non deve poter enumerare i
        conti che il pannello nasconde apposta.
        """
        prop = get_request_property(request)
        self._richiedi_gestione(prop)
        conti = (
            OwnerBankAccount.objects.filter(
                attivo=True,
                owner__user__property_memberships__property=prop,
            )
            .exclude(properties=prop)
            .select_related("owner")
            .order_by("owner__nominativo", "ordinamento")
            .distinct()
        )
        return Response([
            {
                "id": c.id,
                "owner": c.owner_id,
                "owner_nominativo": c.owner.nominativo,
                "banca": c.banca,
                "intestatario": c.intestatario,
                "iban_finale": c.iban[-4:],
            }
            for c in conti
        ])

    @action(detail=True, methods=["post"])
    def collega(self, request, pk=None):
        """Mette il conto in uso su questo immobile."""
        prop = get_request_property(request)
        self._richiedi_gestione(prop)
        conto = get_object_or_404(
            OwnerBankAccount.objects.filter(
                owner__user__property_memberships__property=prop
            ).distinct(),
            pk=pk,
        )
        conto.properties.add(prop)
        return Response(self.get_serializer(conto).data)

    @action(detail=True, methods=["post"])
    def scollega(self, request, pk=None):
        """Toglie il conto da questo immobile, lasciandolo intatto altrove.

        È l'azione da usare quando un conto non c'entra con l'immobile:
        eliminarlo non si può (e non si deve) se ha movimenti.
        """
        from rest_framework.exceptions import ValidationError

        prop = get_request_property(request)
        self._richiedi_gestione(prop)
        conto = get_object_or_404(self.get_queryset(), pk=pk)

        if prop.bank_account_utenze_id == conto.pk:
            raise ValidationError(
                "È il conto per incassi e utenze dell'immobile: cambialo "
                "prima di toglierlo."
            )
        assegnazioni = RoomAssignment.objects.filter(
            room__property=prop, bank_account_affitto=conto
        )
        if assegnazioni.exists():
            nomi = ", ".join(
                sorted(str(a.tenant) for a in assegnazioni.select_related("tenant"))
            )
            raise ValidationError(
                f"È il conto dell'affitto di {nomi}: cambialo prima di toglierlo."
            )

        conto.properties.remove(prop)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    ``inviti`` (POST). Aggiunta e invito membri: proprietari e gestori;
    modifica/rimozione membri e quote: solo proprietari.
    """

    from properties.serializers import PropertySerializer

    serializer_class = PropertySerializer
    # MultiPart per l'upload delle immagini singleton della galleria
    # (hero/planimetria/mappa), JSON per il resto.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

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
                share = OwnershipShare(
                    property=prop,
                    owner=profilo,
                    quota=Decimal("1.0000"),
                    valid_from=datetime.date.today(),
                )
                share.full_clean()
                share.save()
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

        self._richiedi_operativo(prop)
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
        if membership.ruolo == PropertyMembership.Ruolo.PROPRIETARIO:
            from properties.models import get_or_create_owner_profile

            get_or_create_owner_profile(membership.user)
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
            if ruolo == PropertyMembership.Ruolo.PROPRIETARIO:
                from properties.models import get_or_create_owner_profile

                get_or_create_owner_profile(membership.user)
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
            # Blocca la property: due POST /quote concorrenti sullo stesso
            # immobile si serializzano invece di intrecciare le proprie
            # letture/scritture del set di quote.
            prop_locked = Property.objects.select_for_update().get(pk=prop.pk)
            aperte = prop_locked.ownership_shares.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gt=valid_from),
                valid_from__lt=valid_from,
            )
            aperte.update(valid_to=valid_from)
            prop_locked.ownership_shares.filter(valid_from__gte=valid_from).delete()
            nuove = [
                OwnershipShare.objects.create(
                    property=prop_locked, owner=profilo, quota=quota, valid_from=valid_from,
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
        self._richiedi_operativo(prop)
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


class _GalleryPropertyScopedMixin:
    """Scoping multiproprietà per i viewset della galleria: si lavora sempre
    sull'immobile attivo della richiesta, mai su quello indicato dal client."""

    def _property_attiva(self, serializer=None):
        from rest_framework.exceptions import ValidationError

        prop = get_request_property(self.request)
        if serializer is not None:
            inviata = serializer.validated_data.get("property")
            if inviata is not None and inviata.pk != prop.pk:
                raise ValidationError(
                    {"property": "Immobile diverso da quello attivo."}
                )
        return prop


class GalleryImageViewSet(_GalleryPropertyScopedMixin, ModelViewSet):
    """Foto della galleria pubblica (spazi comuni e stanze).

    Scrittura riservata ai membri operativi dell'immobile attivo. L'upload
    accetta sia file (``q-file``, drag&drop) sia blob incollati (Ctrl-V):
    è sempre una POST multipart.
    """

    serializer_class = GalleryImageSerializer
    permission_classes = [IsPropertyMember]
    # MultiPart per l'upload (file), JSON per i PATCH di metadati (formato,
    # didascalia, ordinamento) senza reinviare l'immagine.
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = GalleryImage.objects.select_related("property", "room", "area").filter(
            property=get_request_property(self.request)
        )
        room_id = self.request.query_params.get("room")
        if room_id:
            qs = qs.filter(room_id=room_id)
        area_id = self.request.query_params.get("area")
        if area_id:
            qs = qs.filter(area_id=area_id)
        return qs

    def perform_create(self, serializer):
        prop = self._property_attiva(serializer)
        # Nuove foto in coda alla loro sezione (camera/ambiente/immobile): con
        # l'ordinamento a 0 di default, in una sezione già riordinata si
        # infilerebbero dopo la prima foto invece che in fondo.
        data = serializer.validated_data
        qs = GalleryImage.objects.filter(property=prop)
        if data.get("room"):
            qs = qs.filter(room=data["room"])
        elif data.get("area"):
            qs = qs.filter(area=data["area"])
        else:
            qs = qs.filter(room__isnull=True, area__isnull=True)
        ultimo = qs.aggregate(m=Max("ordinamento"))["m"]
        serializer.save(
            property=prop,
            caricato_da=self.request.user,
            ordinamento=0 if ultimo is None else ultimo + 1,
        )

    def perform_update(self, serializer):
        self._property_attiva(serializer)
        serializer.save()


class GalleryAreaViewSet(_GalleryPropertyScopedMixin, ModelViewSet):
    """Ambienti comuni della galleria (cucina, soggiorno, bagni…).

    Scrittura riservata ai membri operativi dell'immobile attivo. Non sono
    oggetti d'affitto: nessun legame con assegnazioni/canone.
    """

    serializer_class = GalleryAreaSerializer
    permission_classes = [IsPropertyMember]

    def get_queryset(self):
        return GalleryArea.objects.select_related("property").filter(
            property=get_request_property(self.request)
        )

    def perform_create(self, serializer):
        serializer.save(property=self._property_attiva(serializer))

    def perform_update(self, serializer):
        self._property_attiva(serializer)
        serializer.save()


class PublicGalleryView(RetrieveAPIView):
    """Payload pubblico della galleria di un immobile, senza autenticazione.

    Unica view AllowAny del progetto: espone solo i campi pubblici tramite
    ``PublicGallerySerializer``. 404 se l'immobile non è pubblicato. Lo
    slug identifica l'immobile: intrinsecamente per-property.
    """

    serializer_class = PublicGallerySerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "slug"

    def get_queryset(self):
        return Property.objects.filter(pubblica=True).prefetch_related(
            "rooms", "rooms__gallery_images", "gallery_areas", "gallery_areas__gallery_images"
        )


class InformativaPrivacyView(APIView):
    """Dati dinamici per l'informativa privacy dell'inquilino (art. 13 GDPR).

    I titolari del trattamento sono i proprietari con quota attiva oggi
    sull'immobile dell'inquilino; il gestore della piattaforma (responsabile
    ex art. 28) viene dai settings, sovrascrivibili in local.py.
    """

    def get(self, request):
        profilo = getattr(request.user, "tenant_profile", None)
        if profilo is None:
            raise Http404("Informativa disponibile solo per account inquilino.")
        oggi = datetime.date.today()
        shares = (
            OwnershipShare.objects.filter(
                property=profilo.property, valid_from__lte=oggi
            )
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=oggi))
            .select_related("owner__user")
            .order_by("owner__nominativo")
        )
        titolari = [
            {
                "nominativo": share.owner.nominativo,
                "email": share.owner.user.email or None,
            }
            for share in shares
        ]
        return Response(
            {
                "immobile": {
                    "nome": profilo.property.nome,
                    "indirizzo": profilo.property.indirizzo,
                },
                "titolari": titolari,
                "gestore": {
                    "nome": settings.PRIVACY_GESTORE_NOME,
                    "email": settings.PRIVACY_GESTORE_EMAIL,
                },
                "aggiornata_il": settings.PRIVACY_INFORMATIVA_AGGIORNATA,
            }
        )
