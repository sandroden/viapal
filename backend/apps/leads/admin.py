"""Admin dei lead: consultazione e sanità, non il posto dove si lavora.

Il lavoro vero si fa in ``/p/cerca-inquilini`` — l'admin serve a chi guarda
sotto il cofano quando un push del bot sembra non essere arrivato.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("author_name", "stato", "preso_da", "zona", "budget", "seen_at")
    list_filter = ("stato", "property", "group_label")
    search_fields = ("author_name", "testo", "post_id")
    date_hierarchy = "seen_at"
    readonly_fields = ("post_id", "seen_at", "created_at", "updated_at", "link")
    fieldsets = (
        (None, {"fields": ("property", "author_name", "author_url", "link", "testo")}),
        ("Analisi del bot", {"fields": ("analisi", "commento_proposto", "privato_proposto")}),
        ("Lavorazione", {"fields": ("stato", "preso_da", "preso_at", "contattato_at", "note")}),
        ("Origine", {"fields": ("post_id", "group_id", "group_label", "permalink", "seen_at")}),
    )

    @admin.display(description="zona")
    def zona(self, obj):
        return (obj.analisi or {}).get("zona") or "—"

    @admin.display(description="budget")
    def budget(self, obj):
        valore = (obj.analisi or {}).get("budget_max")
        return f"{valore}€" if valore else "—"

    @admin.display(description="link")
    def link(self, obj):
        if not obj.permalink:
            return "—"
        return format_html('<a href="{}" target="_blank">apri il post</a>', obj.permalink)
