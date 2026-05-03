# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app notifications.
Gestisce template messaggi, regole sollecito,
iscrizioni push e log notifiche.
"""
from django.contrib import admin

from jmb.jadmin import JumboModelAdmin, ModalEditMixin

from .models import MessageTemplate, Notification, PushSubscription, ReminderRule


# ---------------------------------------------------------------------------
# MessageTemplate
# ---------------------------------------------------------------------------


@admin.register(MessageTemplate)
class MessageTemplateAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "codice", "titolo", "canale",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("canale",)
    search_fields = ("codice", "titolo")
    ordering = ("codice",)
    fieldsets = (
        ("Template", {
            "fields": ("codice", "titolo", "canale"),
        }),
        ("Testo", {
            "fields": ("corpo",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# ReminderRule
# ---------------------------------------------------------------------------


@admin.register(ReminderRule)
class ReminderRuleAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "applicabile_a", "giorni_offset", "canale",
        "destinatario", "attiva", "template",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("applicabile_a", "canale", "attiva", "destinatario")
    search_fields = ("template__codice",)
    list_select_related = ("template",)
    autocomplete_fields = ("template",)
    ordering = ("applicabile_a", "giorni_offset")
    fieldsets = (
        ("Regola", {
            "fields": ("applicabile_a", "giorni_offset", "canale", "destinatario", "attiva"),
        }),
        ("Template", {
            "fields": ("template",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# PushSubscription
# ---------------------------------------------------------------------------


@admin.register(PushSubscription)
class PushSubscriptionAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "user", "device_label", "ultima_attivita", "created_at",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("created_at",)
    search_fields = ("user__username", "device_label")
    list_select_related = ("user",)
    ordering = ("-created_at",)
    fieldsets = (
        ("Iscrizione", {
            "fields": ("user", "device_label", "ultima_attivita"),
        }),
        ("Chiavi VAPID", {
            "fields": ("endpoint", "p256dh", "auth"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at", "endpoint", "p256dh", "auth")


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


@admin.register(Notification)
class NotificationAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "user", "oggetto", "canale",
        "inviata_at", "letta_at",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("canale", "inviata_at")
    search_fields = ("user__username", "oggetto")
    list_select_related = ("user", "regola")
    autocomplete_fields = ("regola",)
    date_hierarchy = "inviata_at"
    ordering = ("-created_at",)
    fieldsets = (
        ("Notifica", {
            "fields": ("user", "canale", "oggetto", "corpo"),
        }),
        ("Stato invio", {
            "fields": ("inviata_at", "letta_at", "regola"),
        }),
        ("Oggetto collegato", {
            "fields": ("oggetto_riferimento_type", "oggetto_riferimento_id"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = (
        "created_at", "updated_at",
        "inviata_at", "letta_at",
        "oggetto_riferimento_type", "oggetto_riferimento_id",
    )
