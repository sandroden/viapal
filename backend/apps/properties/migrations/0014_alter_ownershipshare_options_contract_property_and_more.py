# Multiproprietà — Fase A.
#
# Introduce PropertyMembership e aggancia a Property i modelli finora
# globali (Contract, OwnershipShare, TenantProfile) più Room (che era
# nullable). Backfill: tutte le righe esistenti vengono attribuite
# all'unico immobile esistente; i membri iniziali sono gli utenti del
# gruppo 'proprietari' con OwnerProfile.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _default_property(apps):
    Property = apps.get_model("properties", "Property")
    return Property.objects.order_by("pk").first()


def backfill_property(apps, schema_editor):
    prop = _default_property(apps)

    Contract = apps.get_model("properties", "Contract")
    OwnershipShare = apps.get_model("properties", "OwnershipShare")
    TenantProfile = apps.get_model("properties", "TenantProfile")
    Room = apps.get_model("properties", "Room")

    ha_righe = (
        Contract.objects.exists()
        or OwnershipShare.objects.exists()
        or TenantProfile.objects.exists()
        or Room.objects.exists()
    )
    if not ha_righe:
        return
    if prop is None:
        Property = apps.get_model("properties", "Property")
        prop = Property.objects.create(nome="Immobile")

    Contract.objects.filter(property__isnull=True).update(property=prop)
    OwnershipShare.objects.filter(property__isnull=True).update(property=prop)
    TenantProfile.objects.filter(property__isnull=True).update(property=prop)
    Room.objects.filter(property__isnull=True).update(property=prop)


def backfill_memberships(apps, schema_editor):
    """I membri iniziali dell'immobile esistente: gli utenti del gruppo
    'proprietari' che hanno un OwnerProfile, con ruolo 'proprietario'."""
    prop = _default_property(apps)
    if prop is None:
        return

    OwnerProfile = apps.get_model("properties", "OwnerProfile")
    PropertyMembership = apps.get_model("properties", "PropertyMembership")

    owners = OwnerProfile.objects.filter(
        user__groups__name="proprietari"
    ).select_related("user")
    for owner in owners:
        PropertyMembership.objects.get_or_create(
            property=prop,
            user=owner.user,
            defaults={"ruolo": "proprietario"},
        )

    # Convenzione storica: Sandro anticipa i costi di cessione.
    anticipante = OwnerProfile.objects.filter(
        nominativo__icontains="sandro"
    ).first()
    if anticipante and not prop.owner_anticipa_cessioni_id:
        prop.owner_anticipa_cessioni = anticipante
        prop.save(update_fields=["owner_anticipa_cessioni"])


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0013_tenantdocument"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="ownershipshare",
            options={
                "ordering": ["property__nome", "-valid_from", "owner__nominativo"],
                "verbose_name": "quota di proprietà",
                "verbose_name_plural": "quote di proprietà",
            },
        ),
        migrations.CreateModel(
            name="PropertyMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="creato il"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="aggiornato il"),
                ),
                (
                    "ruolo",
                    models.CharField(
                        choices=[
                            ("proprietario", "Proprietario"),
                            ("gestore", "Gestore"),
                            ("sola_lettura", "Sola lettura"),
                        ],
                        default="proprietario",
                        help_text="Proprietario: gestione piena e partecipazione economica. Gestore: gestione piena ma nessuna quota né partecipazione ai riparti. Sola lettura: consultazione (es. commercialista).",
                        max_length=20,
                        verbose_name="ruolo",
                    ),
                ),
                (
                    "invitato_da",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="memberships_invitate",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="invitato da",
                    ),
                ),
                (
                    "property",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="properties.property",
                        verbose_name="immobile",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="property_memberships",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="utente",
                    ),
                ),
            ],
            options={
                "verbose_name": "membro immobile",
                "verbose_name_plural": "membri immobili",
                "ordering": ["property__nome", "user__username"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("property", "user"), name="property_membership_unique"
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="property",
            name="owner_anticipa_cessioni",
            field=models.ForeignKey(
                blank=True,
                help_text="Proprietario che, per convenzione, anticipa il 50% dei costi di registrazione/cessione contratto di questo immobile.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="properties_anticipo_cessioni",
                to="properties.ownerprofile",
                verbose_name="anticipa i costi di cessione",
            ),
        ),
        # --- FK property: prima nullable, poi backfill, poi NOT NULL ------
        migrations.AddField(
            model_name="contract",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contracts",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="ownershipshare",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ownership_shares",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="tenantprofile",
            name="property",
            field=models.ForeignKey(
                null=True,
                help_text="Immobile in cui l'inquilino affitta: definisce chi può vedere e gestire questo profilo.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenants",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.RunPython(backfill_property, migrations.RunPython.noop),
        migrations.RunPython(backfill_memberships, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contract",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contracts",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="ownershipshare",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ownership_shares",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="tenantprofile",
            name="property",
            field=models.ForeignKey(
                help_text="Immobile in cui l'inquilino affitta: definisce chi può vedere e gestire questo profilo.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenants",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="room",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="rooms",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
    ]
