"""Serializer dei lead — due mondi separati di proposito.

``LeadBotSerializer`` non sa nominare i campi di lavorazione, e
``LeadLavorazioneSerializer`` non sa nominare quelli del bot. È così che
l'invariante di proprietà dei campi regge: non per disciplina di chi manda il
payload, ma perché il campo sbagliato non esiste nel serializer.
"""
from rest_framework import serializers

from .models import Lead

# I campi che il bot possiede e riscrive a ogni upsert dello stesso post.
CAMPI_BOT = (
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

    class Meta:
        model = Lead
        fields = ("post_id", *CAMPI_BOT)


class LeadBulkUpsertSerializer(serializers.Serializer):
    """Payload del bot: la lista dei lead di un giro."""

    leads = LeadBotSerializer(many=True)

    def validate_leads(self, valore):
        if not valore:
            raise serializers.ValidationError("Nessun lead da caricare.")
        visti = set()
        for lead in valore:
            pid = lead["post_id"]
            if pid in visti:
                raise serializers.ValidationError(f"post_id ripetuto nel payload: {pid}")
            visti.add(pid)
        return valore


class LeadSerializer(serializers.ModelSerializer):
    """Lettura: quello che la pagina mostra."""

    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    preso_da_nome = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = (
            "id",
            "post_id",
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
            "stato",
            "stato_display",
            "preso_da",
            "preso_da_nome",
            "preso_at",
            "contattato_at",
            "note",
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
        fields = ("stato", "note")

    def update(self, instance, validated_data):
        from django.utils import timezone

        nuovo = validated_data.get("stato", instance.stato)
        # "Contattato" è il momento che conta per capire a che punto siamo:
        # si marca la prima volta e non si sposta più (un ritorno a "nuovo"
        # per errore non deve cancellare la storia).
        if nuovo == Lead.Stato.CONTATTATO and instance.contattato_at is None:
            instance.contattato_at = timezone.now()
        return super().update(instance, validated_data)
