"""Il conto bancario diventa visibile per immobile, non per membership.

Finora "i conti di questo immobile" erano quelli di *chiunque* ne fosse
membro: un gestore si vedeva proporre i propri conti come destinazione dei
bonifici di un immobile altrui, e i suoi movimenti bancari finivano nella
riconciliazione di quell'immobile. Il conto resta unico; ``properties`` dice
dove è in uso.

Il backfill collega ogni conto agli immobili dove è *davvero* in uso, da
cinque sorgenti. La quinta (le allocazioni) è quella che non si può omettere:
un conto la cui unica traccia su un immobile sono i movimenti già riconciliati
là (import storici) sparirebbe dalla riconciliazione senza di essa.
"""
from django.db import migrations, models


def _aggiungi(mappa, account_id, property_id):
    if account_id and property_id:
        mappa.setdefault(account_id, set()).add(property_id)


def collega_conti_agli_immobili(apps, schema_editor):
    OwnerBankAccount = apps.get_model("properties", "OwnerBankAccount")
    PropertyMembership = apps.get_model("properties", "PropertyMembership")
    Property = apps.get_model("properties", "Property")
    RoomAssignment = apps.get_model("properties", "RoomAssignment")
    Receivable = apps.get_model("billing", "Receivable")

    per_conto: dict[int, set[int]] = {}

    # 1. l'owner è proprietario dell'immobile. I gestori sono esclusi di
    #    proposito: è il caso da cui nasce questa migrazione.
    conti_per_user: dict[int, list[int]] = {}
    for account_id, user_id in OwnerBankAccount.objects.values_list(
        "id", "owner__user_id"
    ):
        conti_per_user.setdefault(user_id, []).append(account_id)
    for user_id, property_id in PropertyMembership.objects.filter(
        ruolo="proprietario"
    ).values_list("user_id", "property_id"):
        for account_id in conti_per_user.get(user_id, []):
            _aggiungi(per_conto, account_id, property_id)

    # 2. conto per incassi e utenze dell'immobile
    for account_id, property_id in Property.objects.exclude(
        bank_account_utenze=None
    ).values_list("bank_account_utenze_id", "id"):
        _aggiungi(per_conto, account_id, property_id)

    # 3. override del conto affitto su un'assegnazione
    for account_id, property_id in RoomAssignment.objects.exclude(
        bank_account_affitto=None
    ).values_list("bank_account_affitto_id", "room__property_id"):
        _aggiungi(per_conto, account_id, property_id)

    # 4. conto di destinazione fissato su un addebito
    for account_id, property_id in Receivable.objects.exclude(
        bank_account_destinazione=None
    ).values_list("bank_account_destinazione_id", "assignment__room__property_id"):
        _aggiungi(per_conto, account_id, property_id)

    # 5. movimenti già riconciliati con addebiti dell'immobile
    for account_id, property_id in Receivable.objects.filter(
        allocations__isnull=False
    ).values_list(
        "allocations__bank_transaction__owner_account_id",
        "assignment__room__property_id",
    ):
        _aggiungi(per_conto, account_id, property_id)

    for conto in OwnerBankAccount.objects.filter(id__in=per_conto):
        conto.properties.set(per_conto[conto.id])


def scollega_tutti(apps, schema_editor):
    OwnerBankAccount = apps.get_model("properties", "OwnerBankAccount")
    for conto in OwnerBankAccount.objects.all():
        conto.properties.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0035_propertydocument_contract'),
        ('billing', '0031_seed_property_utility_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='ownerbankaccount',
            name='properties',
            field=models.ManyToManyField(blank=True, help_text='Immobili su cui questo conto è in uso: solo lì compare fra le destinazioni dei bonifici e solo lì si vedono i suoi movimenti.', related_name='bank_accounts', to='properties.property', verbose_name='immobili'),
        ),
        migrations.RunPython(collega_conti_agli_immobili, scollega_tutti),
    ]
