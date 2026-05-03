"""Migrazione dati: popola Receivable da RentPayment, UtilityCharge, ExtraCharge.

Crea anche le BankTransactionAllocation a partire dalle FK
riconciliato_con_payment / riconciliato_con_charge di BankTransaction, e
valorizza le FK receivable su UtilityChargeLine e su OwnerLedgerEntry.

I tre modelli vecchi e le FK legacy vengono droppati nella migrazione finale.
"""
from django.db import migrations


def popola_receivables(apps, schema_editor):
    RentPayment = apps.get_model("billing", "RentPayment")
    UtilityCharge = apps.get_model("billing", "UtilityCharge")
    ExtraCharge = apps.get_model("billing", "ExtraCharge")
    UtilityChargeLine = apps.get_model("billing", "UtilityChargeLine")
    BankTransaction = apps.get_model("billing", "BankTransaction")
    Receivable = apps.get_model("billing", "Receivable")
    BankTransactionAllocation = apps.get_model("billing", "BankTransactionAllocation")
    OwnerLedgerEntry = apps.get_model("accounting", "OwnerLedgerEntry")

    rent_to_receivable = {}
    utility_to_receivable = {}
    extra_to_receivable = {}

    # --- RentPayment -> Receivable(causale=affitto) ---------------------
    for rp in RentPayment.objects.all().iterator():
        r = Receivable.objects.create(
            assignment_id=rp.assignment_id,
            causale="affitto",
            descrizione="",
            competenza_da=rp.competenza_da,
            competenza_a=rp.competenza_a,
            scadenza=rp.scadenza,
            importo_dovuto=rp.importo_dovuto,
            stato=rp.stato,
            importo_pagato=rp.importo_pagato,
            data_pagamento=rp.data_pagamento,
            incassato_da_owner_id=rp.incassato_da_owner_id,
            bank_account_destinazione_id=rp.bank_account_destinazione_id,
            ricevuta=rp.ricevuta,
            is_aggiustamento=rp.is_aggiustamento,
            utility_period_id=None,
            note=rp.note,
        )
        rent_to_receivable[rp.id] = r.id

    # --- UtilityCharge -> Receivable(causale=utenze) --------------------
    for uc in UtilityCharge.objects.select_related("period").iterator():
        r = Receivable.objects.create(
            assignment_id=uc.assignment_id,
            causale="utenze",
            descrizione="",
            competenza_da=uc.period.periodo_da,
            competenza_a=uc.period.periodo_a,
            scadenza=uc.scadenza,
            importo_dovuto=uc.importo_totale,
            stato=uc.stato,
            importo_pagato=uc.importo_pagato,
            data_pagamento=uc.data_pagamento,
            incassato_da_owner_id=uc.incassato_da_owner_id,
            bank_account_destinazione_id=uc.bank_account_destinazione_id,
            ricevuta=uc.ricevuta,
            is_aggiustamento=False,
            utility_period_id=uc.period_id,
            note=uc.note,
        )
        utility_to_receivable[uc.id] = r.id

    # --- ExtraCharge -> Receivable(causale=extra) -----------------------
    for ec in ExtraCharge.objects.all().iterator():
        r = Receivable.objects.create(
            assignment_id=ec.assignment_id,
            causale="extra",
            descrizione=ec.descrizione,
            competenza_da=ec.data,
            competenza_a=None,
            scadenza=ec.scadenza,
            importo_dovuto=ec.importo,
            stato=ec.stato,
            importo_pagato=ec.importo_pagato,
            data_pagamento=ec.data_pagamento,
            incassato_da_owner_id=ec.incassato_da_owner_id,
            bank_account_destinazione_id=ec.bank_account_destinazione_id,
            ricevuta=None,
            is_aggiustamento=False,
            utility_period_id=None,
            note=ec.note,
        )
        extra_to_receivable[ec.id] = r.id

    # --- UtilityChargeLine.charge -> .receivable ------------------------
    for line in UtilityChargeLine.objects.all().iterator():
        if line.charge_id and line.charge_id in utility_to_receivable:
            line.receivable_id = utility_to_receivable[line.charge_id]
            line.save(update_fields=["receivable"])

    # --- BankTransaction.riconciliato_con_* -> Allocation ---------------
    for bt in BankTransaction.objects.all().iterator():
        if bt.riconciliato_con_payment_id:
            rec_id = rent_to_receivable.get(bt.riconciliato_con_payment_id)
            if rec_id:
                BankTransactionAllocation.objects.create(
                    bank_transaction_id=bt.id,
                    receivable_id=rec_id,
                    importo=bt.importo,
                )
        if bt.riconciliato_con_charge_id:
            rec_id = utility_to_receivable.get(bt.riconciliato_con_charge_id)
            if rec_id:
                BankTransactionAllocation.objects.create(
                    bank_transaction_id=bt.id,
                    receivable_id=rec_id,
                    importo=bt.importo,
                )

    # --- OwnerLedgerEntry.riferimento_payment/charge -> _receivable -----
    for le in OwnerLedgerEntry.objects.all().iterator():
        rec_id = None
        if le.riferimento_payment_id:
            rec_id = rent_to_receivable.get(le.riferimento_payment_id)
        elif le.riferimento_charge_id:
            rec_id = utility_to_receivable.get(le.riferimento_charge_id)
        if rec_id:
            le.riferimento_receivable_id = rec_id
            le.save(update_fields=["riferimento_receivable"])

    # --- Verifica conteggi e somme --------------------------------------
    n_rp = RentPayment.objects.count()
    n_uc = UtilityCharge.objects.count()
    n_ec = ExtraCharge.objects.count()
    n_rec = Receivable.objects.count()
    expected = n_rp + n_uc + n_ec
    assert n_rec == expected, (
        f"Mismatch conteggio Receivable: {n_rec} attesi {expected} "
        f"(rent={n_rp}, utility={n_uc}, extra={n_ec})"
    )


def reverse_popola(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    BankTransactionAllocation = apps.get_model("billing", "BankTransactionAllocation")
    UtilityChargeLine = apps.get_model("billing", "UtilityChargeLine")
    OwnerLedgerEntry = apps.get_model("accounting", "OwnerLedgerEntry")

    UtilityChargeLine.objects.update(receivable=None)
    OwnerLedgerEntry.objects.update(riferimento_receivable=None)
    BankTransactionAllocation.objects.all().delete()
    Receivable.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0008_alter_utilitychargeline_charge_receivable_and_more"),
        ("accounting", "0002_ownerledgerentry_riferimento_receivable_and_more"),
    ]

    operations = [
        migrations.RunPython(popola_receivables, reverse_popola),
    ]
