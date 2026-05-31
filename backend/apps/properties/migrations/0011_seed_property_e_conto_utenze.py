"""Crea l'immobile unico esistente, collega le stanze e imposta il conto utenze.

Solo creazione/aggancio: i conti affitto sulle assegnazioni restano vuoti
(override on-demand), come da scelta di non pre-assegnare a tappeto.
Idempotente e no-op su DB senza stanze (es. test, che creano i propri dati).
"""
from datetime import date

from django.db import migrations
from django.db.models import Q


def crea_property(apps, schema_editor):
    Room = apps.get_model("properties", "Room")
    if not Room.objects.exists():
        return  # DB vuoto (test/fresh): niente da agganciare

    Property = apps.get_model("properties", "Property")
    Contract = apps.get_model("properties", "Contract")
    OwnerBankAccount = apps.get_model("properties", "OwnerBankAccount")

    # Conto domiciliazione utenze = conto primario del proprietario che, per
    # convenzione, anticipa le bollette nel contratto IN VIGORE più recente
    # (si ignorano contratti chiusi o con decorrenza futura: dati anomali).
    oggi = date.today()
    conto_utenze = None
    contratto = (
        Contract.objects.filter(
            default_pagatore_bollette__isnull=False,
            data_decorrenza__lte=oggi,
        )
        .filter(Q(termine__isnull=True) | Q(termine__gte=oggi))
        .order_by("-data_decorrenza")
        .first()
    )
    if contratto:
        conto_utenze = (
            OwnerBankAccount.objects.filter(
                owner=contratto.default_pagatore_bollette, attivo=True
            )
            .order_by("ordinamento", "banca")
            .first()
        )

    prop, _ = Property.objects.get_or_create(
        nome="Viapal",
        defaults={"bank_account_utenze": conto_utenze},
    )
    if conto_utenze and prop.bank_account_utenze_id is None:
        prop.bank_account_utenze = conto_utenze
        prop.save(update_fields=["bank_account_utenze"])

    Room.objects.filter(property__isnull=True).update(property=prop)


def reverse(apps, schema_editor):
    Room = apps.get_model("properties", "Room")
    Property = apps.get_model("properties", "Property")
    Room.objects.update(property=None)
    Property.objects.filter(nome="Viapal").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0010_roomassignment_bank_account_affitto_and_more"),
    ]

    operations = [
        migrations.RunPython(crea_property, reverse),
    ]
