"""Serializer dei lead — due mondi separati di proposito.

``LeadBotSerializer`` non sa nominare i campi di lavorazione, e
``LeadLavorazioneSerializer`` non sa nominare quelli del bot. È così che
l'invariante di proprietà dei campi regge: non per disciplina di chi manda il
payload, ma perché il campo sbagliato non esiste nel serializer.
"""
from django.utils import timezone
from rest_framework import serializers

from .models import Lead

# I campi che il bot possiede e riscrive a ogni upsert dello stesso post.
CAMPI_BOT = (
    "canale",
    "group_id",
    "group_label",
    "author_name",
    "author_url",
    "permalink",
    "link_messenger",
    "testo",
    "analisi",
    "commento_proposto",
    "privato_proposto",
    "seen_at",
)


class LeadBotSerializer(serializers.ModelSerializer):
    """Un lead in arrivo dal bot. ``post_id`` è la chiave dell'upsert."""

    post_id = serializers.CharField(max_length=64)
    # Oggi il bot gira solo sui gruppi; il campo è qui perché quando leggerà
    # anche le risposte ai nostri post non serva un secondo endpoint.
    canale = serializers.ChoiceField(
        choices=Lead.Canale.choices, default=Lead.Canale.FB_GRUPPO
    )

    class Meta:
        model = Lead
        fields = ("post_id", *CAMPI_BOT)


class LeadBulkUpsertSerializer(serializers.Serializer):
    """Involucro del payload. La lista resta grezza di proposito.

    Con ``LeadBotSerializer(many=True)`` una riga malformata farebbe fallire
    l'intero blocco, e la coda del bot — che ritenta sempre lo stesso blocco —
    resterebbe ferma per sempre su quella riga. Le righe si validano una per
    una nella view: quella rotta si scarta e si segnala, le altre passano.
    """

    leads = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class LeadSerializer(serializers.ModelSerializer):
    """Lettura: quello che la pagina mostra."""

    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    canale_display = serializers.CharField(source="get_canale_display", read_only=True)
    preso_da_nome = serializers.SerializerMethodField()
    manuale = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lead
        fields = (
            "id",
            "post_id",
            "manuale",
            "canale",
            "canale_display",
            "group_id",
            "group_label",
            "author_name",
            "author_url",
            "contatto",
            "permalink",
            "link_messenger",
            "testo",
            "analisi",
            "commento_proposto",
            "privato_proposto",
            "seen_at",
            "stato",
            "stato_display",
            "preso_da",
            "preso_da_nome",
            "preso_at",
            "contattato_at",
            "risposto_at",
            "note",
            "foto",
            "created_at",
        )
        read_only_fields = fields

    def get_preso_da_nome(self, obj) -> str:
        if not obj.preso_da:
            return ""
        return obj.preso_da.get_full_name() or obj.preso_da.username


class LeadLavorazioneSerializer(serializers.ModelSerializer):
    """Scrittura umana: solo lo stato di lavorazione.

    ``preso_da`` non è qui: la presa in carico passa dall'azione dedicata, che
    la assegna a chi chiama — nessuno prende in carico al posto di un altro.
    """

    class Meta:
        model = Lead
        fields = ("stato", "note", "foto")

    def update(self, instance, validated_data):
        segna_passaggi(instance, validated_data.get("stato", instance.stato))
        return super().update(instance, validated_data)


def segna_passaggi(lead, nuovo_stato):
    """Le date dei passaggi si marcano la prima volta e non si spostano più.

    Un ritorno a "nuovo" per errore non deve cancellare la storia, e le
    statistiche per canale contano chi *ha* risposto, anche se poi ha trovato
    altro. Chi risponde è stato contattato: se si salta il passaggio
    intermedio, la data di contatto si mette lo stesso.
    """
    adesso = timezone.now()
    contattato = nuovo_stato in (Lead.Stato.CONTATTATO, Lead.Stato.RISPOSTO)
    if contattato and lead.contattato_at is None:
        lead.contattato_at = adesso
    if nuovo_stato == Lead.Stato.RISPOSTO and lead.risposto_at is None:
        lead.risposto_at = adesso


# Le chiavi di ``analisi`` che una persona compila a mano. Il bot ne scrive
# anche altre (stanze_compatibili, motivo): qui si accettano solo queste, così
# un PATCH non può infilare nel JSON cose che la pagina non sa mostrare.
CHIAVI_ANALISI_MANUALE = ("zona", "budget_max", "disponibile_da")


class LeadManualeSerializer(LeadLavorazioneSerializer):
    """Un contatto inserito a mano da un canale che il bot non copre.

    Estende la lavorazione con i campi descrittivi: qui li scrivono le
    persone, non c'è un bot che li possiede. Vale solo per i lead con
    ``post_id`` vuoto — su un lead del bot il PATCH resta quello di
    lavorazione, e la view sceglie il serializer in base al lead.
    """

    canale = serializers.ChoiceField(choices=Lead.Canale.choices)
    author_name = serializers.CharField(max_length=200)
    analisi = serializers.DictField(required=False)

    class Meta:
        model = Lead
        fields = (
            "canale",
            "author_name",
            "contatto",
            "author_url",
            "permalink",
            "testo",
            "analisi",
            "stato",
            "note",
            "foto",
        )

    def validate_analisi(self, valore):
        pulita = {}
        for chiave in CHIAVI_ANALISI_MANUALE:
            v = valore.get(chiave)
            if v not in (None, ""):
                pulita[chiave] = v
        return pulita

    def create(self, validated_data):
        lead = Lead(**validated_data)
        lead.property = self.context["property"]
        # "Visto il" per un contatto manuale è il momento in cui lo si
        # registra: è la data che ordina la lista e che le statistiche
        # usano come ultimo contatto del canale.
        lead.seen_at = timezone.now()
        segna_passaggi(lead, lead.stato)
        lead.full_clean(exclude=["property"])
        lead.save()
        return lead
