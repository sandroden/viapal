"""Data migration: copia i valori di caparra da RoomAssignment al TenantProfile.

Per ogni TenantProfile:
- deposito_versato: il valore massimo tra i suoi RoomAssignment (per gestire
  il caso Arun dove più assignment riportano lo stesso valore, ma anche
  eventuali correzioni post-hoc);
- data_versamento_deposito: valid_from del primo assignment del tenant;
- deposito_restituito / data_restituzione_deposito: presi dall'assignment del
  tenant che li ha valorizzati (di norma l'ultimo).

Reverse: best-effort, ripopola RoomAssignment con i valori del tenant.
"""
from decimal import Decimal

from django.db import migrations


def copia_da_assignment_a_tenant(apps, schema_editor):
    TenantProfile = apps.get_model("properties", "TenantProfile")
    RoomAssignment = apps.get_model("properties", "RoomAssignment")

    for tenant in TenantProfile.objects.all():
        assignments = list(
            RoomAssignment.objects.filter(tenant=tenant).order_by("valid_from", "id")
        )
        if not assignments:
            continue

        versamenti = [a.deposito_versato for a in assignments if a.deposito_versato]
        if versamenti:
            tenant.deposito_versato = max(versamenti)
        else:
            tenant.deposito_versato = Decimal("0")
        tenant.data_versamento_deposito = assignments[0].valid_from

        with_restituito = [
            a for a in assignments if a.deposito_restituito is not None
        ]
        if with_restituito:
            ultimo = with_restituito[-1]
            tenant.deposito_restituito = ultimo.deposito_restituito
            tenant.data_restituzione_deposito = ultimo.data_restituzione_deposito

        tenant.save(
            update_fields=[
                "deposito_versato",
                "data_versamento_deposito",
                "deposito_restituito",
                "data_restituzione_deposito",
            ]
        )


def copia_tenant_su_primo_assignment(apps, schema_editor):
    """Reverse: ripopola il primo RoomAssignment di ogni tenant con i
    valori salvati su TenantProfile (best-effort, perde dettaglio se
    su più assignment erano divergenti)."""
    TenantProfile = apps.get_model("properties", "TenantProfile")
    RoomAssignment = apps.get_model("properties", "RoomAssignment")

    for tenant in TenantProfile.objects.all():
        primo = (
            RoomAssignment.objects.filter(tenant=tenant)
            .order_by("valid_from", "id")
            .first()
        )
        if primo is None:
            continue
        if tenant.deposito_versato:
            primo.deposito_versato = tenant.deposito_versato
        primo.deposito_restituito = tenant.deposito_restituito
        primo.data_restituzione_deposito = tenant.data_restituzione_deposito
        primo.save(
            update_fields=[
                "deposito_versato",
                "deposito_restituito",
                "data_restituzione_deposito",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0004_tenant_caparra_fields"),
    ]

    operations = [
        migrations.RunPython(
            copia_da_assignment_a_tenant,
            copia_tenant_su_primo_assignment,
        ),
    ]
