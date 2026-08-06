"""Seed della configurazione utenze per gli immobili esistenti.

Per ogni Property esistente crea le righe 'luce' e 'gas' con
gestione=proprieta: erano le uniche voci attese nel comportamento storico
(hardcoded), quindi il seed le rende esplicite senza cambiare nulla. Crea
anche 'tari' con gestione=proprieta, ma solo se la property ha almeno un
AnnualUtilityCost — altrimenti non c'è modo di dedurre se la TARI sia
gestita dalla proprietà o dall'inquilino, e si lascia alla configurazione
manuale.

Idempotente (get_or_create): non tocca righe già presenti (es. modificate
a mano prima di rieseguire la migrazione su un altro ambiente). Il reverse
è un no-op: cancellare le righe seed toglierebbe configurazione valida
anche se nel frattempo modificata a mano.
"""
from django.db import migrations


def seed_utility_services(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    PropertyUtilityService = apps.get_model("billing", "PropertyUtilityService")
    AnnualUtilityCost = apps.get_model("billing", "AnnualUtilityCost")

    for prop in Property.objects.all():
        for voce in ("luce", "gas"):
            PropertyUtilityService.objects.get_or_create(
                property=prop, voce=voce, defaults={"gestione": "proprieta"}
            )
        if AnnualUtilityCost.objects.filter(property=prop).exists():
            PropertyUtilityService.objects.get_or_create(
                property=prop, voce="tari", defaults={"gestione": "proprieta"}
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0030_propertyutilityservice"),
    ]

    operations = [
        migrations.RunPython(seed_utility_services, noop),
    ]
