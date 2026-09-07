# Previsionale utenze d'uscita: da EXTRA + marcatore nelle note a UTENZE con
# campo proprio (``previsionale``) e rettifica legata via ``conguaglio_di``.

import django.db.models.deletion
from django.db import migrations, models

MARKER_PREVISIONALE = "previsionale_utenze"
MARKER_CONGUAGLIO = "conguaglio_previsionale"


def _pulisci_note(note: str) -> str:
    righe = [
        r for r in (note or "").splitlines()
        if MARKER_PREVISIONALE not in r and MARKER_CONGUAGLIO not in r
    ]
    return "\n".join(righe).strip()


def converti(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    previsionali = Receivable.objects.filter(
        causale="extra", note__contains=MARKER_PREVISIONALE
    )
    for prev in previsionali:
        prev.causale = "utenze"
        prev.previsionale = True
        prev.note = _pulisci_note(prev.note)
        prev.save(update_fields=["causale", "previsionale", "note"])
    rettifiche = Receivable.objects.filter(
        causale="extra", note__startswith=f"{MARKER_CONGUAGLIO}:"
    )
    for rett in rettifiche:
        prima_riga = rett.note.splitlines()[0]
        prev_id = int(prima_riga.split(":", 1)[1].strip())
        rett.causale = "utenze"
        rett.conguaglio_di_id = prev_id
        rett.note = _pulisci_note(rett.note)
        rett.save(update_fields=["causale", "conguaglio_di", "note"])


def ripristina(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    for rett in Receivable.objects.filter(conguaglio_di__isnull=False):
        rett.causale = "extra"
        rett.note = f"{MARKER_CONGUAGLIO}:{rett.conguaglio_di_id}\n{rett.note}".strip()
        rett.save(update_fields=["causale", "note"])
        prev = rett.conguaglio_di
        prev.note = f"{prev.note}\n{MARKER_CONGUAGLIO}:{rett.id}".strip()
        prev.save(update_fields=["note"])
    for prev in Receivable.objects.filter(previsionale=True):
        prev.causale = "extra"
        prev.note = f"{MARKER_PREVISIONALE}\n{prev.note}".strip()
        prev.save(update_fields=["causale", "note"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0034_expense_allegato_validators"),
    ]

    operations = [
        migrations.AddField(
            model_name="receivable",
            name="previsionale",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Utenze stimate all'uscita, da compensare con le bollette "
                    "reali (causale=utenze, senza periodo)."
                ),
                verbose_name="previsionale",
            ),
        ),
        migrations.AddField(
            model_name="receivable",
            name="conguaglio_di",
            field=models.ForeignKey(
                blank=True,
                help_text="Per la rettifica: il previsionale che compensa.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="conguagli",
                to="billing.receivable",
                verbose_name="conguaglio del previsionale",
            ),
        ),
        migrations.RunPython(converti, ripristina),
    ]
