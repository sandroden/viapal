"""
Management command per popolare il database Viapal con dati demo/sviluppo realistici.

Idempotente: può essere rilanciato senza duplicare dati.
Opzione --reset: cancella tutti i dati delle app di dominio prima di reinserire.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Popola il database con dati demo realistici per sviluppo e presentazione."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="Cancella tutti i dati delle app di dominio prima di reinserire (NON tocca admin/auth).",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_domain_data()

        with transaction.atomic():
            self._seed_admin()
            owners, owner_profiles, bank_accounts = self._seed_owners()
            self._seed_ownership_shares(owner_profiles)
            tenant_profiles, tenant_assignments_map = self._seed_tenants()
            rooms = self._seed_rooms()
            contract = self._seed_contract()
            room_assignments = self._seed_room_assignments(rooms, tenant_profiles, tenant_assignments_map)
            self._seed_annual_utility_costs()
            suppliers = self._seed_suppliers(owner_profiles)
            self._seed_utility_bills(suppliers, owner_profiles)
            periods = self._seed_utility_charge_periods()
            self._seed_utility_charges(periods, room_assignments, tenant_profiles)
            self._seed_rent_payments(room_assignments, owner_profiles, bank_accounts)
            self._seed_extra_charges(room_assignments)
            self._seed_expenses(owner_profiles, suppliers)
            self._seed_reminder_rules_and_templates()

        self.stdout.write(self.style.SUCCESS("\nSeed completato con successo!"))

    # -----------------------------------------------------------------------
    # RESET
    # -----------------------------------------------------------------------

    def _reset_domain_data(self):
        """Cancella tutti i dati delle app di dominio (non tocca User/Group/admin)."""
        self.stdout.write(self.style.WARNING("-- RESET: cancellazione dati dominio --"))

        # Import qui per evitare import-time side effects se il comando non viene usato
        from accounting.models import InterOwnerEntry, InterOwnerLoan, OwnerLedgerEntry, OwnerSettlement, WithholdingRule
        from billing.models import (
            AnnualUtilityCost,
            BankTransactionAllocation,
            Expense,
            ExpenseCategory,
            Receivable,
            Supplier,
            UtilityBill,
            UtilityChargeLine,
            UtilityChargePeriod,
        )
        from notifications.models import MessageTemplate, Notification, PushSubscription, ReminderRule
        from properties.models import Contract, OwnerBankAccount, OwnerProfile, OwnershipShare, Room, RoomAssignment, TenantProfile

        Notification.objects.all().delete()
        PushSubscription.objects.all().delete()
        ReminderRule.objects.all().delete()
        MessageTemplate.objects.all().delete()
        InterOwnerEntry.objects.all().delete()
        InterOwnerLoan.objects.all().delete()
        WithholdingRule.objects.all().delete()
        OwnerLedgerEntry.objects.all().delete()
        OwnerSettlement.objects.all().delete()
        BankTransactionAllocation.objects.all().delete()
        UtilityChargeLine.objects.all().delete()
        Receivable.objects.all().delete()
        UtilityChargePeriod.objects.all().delete()
        UtilityBill.objects.all().delete()
        AnnualUtilityCost.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Supplier.objects.all().delete()
        RoomAssignment.objects.all().delete()
        Contract.objects.all().delete()
        Room.objects.all().delete()
        OwnerBankAccount.objects.all().delete()
        OwnershipShare.objects.all().delete()
        OwnerProfile.objects.all().delete()
        TenantProfile.objects.all().delete()
        # Rimuovi utenti demo (non admin/superuser esistenti)
        User.objects.filter(
            username__in=["sandro", "bruna", "fabio", "mariasevera", "davide", "diana", "arun", "eshani", "marco_vecchio"]
        ).delete()

        self.stdout.write(self.style.WARNING("   Dati dominio cancellati."))

    # -----------------------------------------------------------------------
    # ADMIN
    # -----------------------------------------------------------------------

    def _seed_admin(self):
        """Crea superuser admin se non esiste."""
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@viapal.local",
                password="admin",
            )
            self.stdout.write(self.style.SUCCESS("   [admin] Superuser 'admin' creato"))
        else:
            self.stdout.write("   [admin] Superuser 'admin' gia' esistente — skip")

    # -----------------------------------------------------------------------
    # OWNERS
    # -----------------------------------------------------------------------

    def _seed_owners(self):
        """Crea User + OwnerProfile + OwnerBankAccount per i 3 fratelli."""
        from properties.models import OwnerBankAccount, OwnerProfile

        gruppo_proprietari, _ = Group.objects.get_or_create(name="proprietari")

        owners_data = [
            {
                "username": "sandro",
                "password": "sandropwd",
                "first_name": "Sandro",
                "last_name": "Dentella",
                "email": "sandro@viapal.local",
                "is_staff": True,
                "nominativo": "Sandro Dentella",
                "codice_fiscale": "DNTSDR70A01F205Y",
                "telefono": "+39 333 1234567",
                "note": "Sviluppatore del gestionale",
            },
            {
                "username": "bruna",
                "password": "brunapwd",
                "first_name": "Bruna",
                "last_name": "Dentella",
                "email": "bruna@viapal.local",
                "is_staff": False,
                "nominativo": "Bruna Dentella",
                "codice_fiscale": "DNTBRN68D41F205Z",
                "telefono": "+39 335 7654321",
                "note": "",
            },
            {
                "username": "fabio",
                "password": "fabiopwd",
                "first_name": "Fabio",
                "last_name": "Dentella",
                "email": "fabio@viapal.local",
                "is_staff": False,
                "nominativo": "Fabio Dentella",
                "codice_fiscale": "DNTFBA72C15F205X",
                "telefono": "+39 347 9876543",
                "note": "Vive in barca — contatto limitato",
            },
        ]

        owner_profiles = {}
        users_created = []

        for od in owners_data:
            user, created = User.objects.get_or_create(
                username=od["username"],
                defaults={
                    "first_name": od["first_name"],
                    "last_name": od["last_name"],
                    "email": od["email"],
                    "is_staff": od["is_staff"],
                },
            )
            if created:
                user.set_password(od["password"])
                user.save()
                user.groups.add(gruppo_proprietari)
                users_created.append(od["username"])

            profile, _ = OwnerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "nominativo": od["nominativo"],
                    "codice_fiscale": od["codice_fiscale"],
                    "telefono": od["telefono"],
                    "note": od["note"],
                },
            )
            owner_profiles[od["username"]] = profile

        self.stdout.write(
            self.style.SUCCESS(f"   [owners] Proprietari creati/trovati: {list(owner_profiles.keys())}")
        )

        # Bank accounts
        bank_data = [
            {
                "owner_key": "bruna",
                "banca": "BPER Banca",
                "intestatario": "Bruna Dentella",
                "iban": "IT60X0542811101000000123456",
                "attivo": True,
                "ordinamento": 1,
            },
            {
                "owner_key": "sandro",
                "banca": "Banca Intesa Sanpaolo",
                "intestatario": "Sandro Dentella",
                "iban": "IT45R0306909606100000123789",
                "attivo": True,
                "ordinamento": 1,
            },
            {
                "owner_key": "fabio",
                "banca": "Banca Generali",
                "intestatario": "Fabio Dentella",
                "iban": "IT88K0760102600000012345678",
                "attivo": False,
                "ordinamento": 1,
            },
        ]

        bank_accounts = {}
        for bd in bank_data:
            acc, _ = OwnerBankAccount.objects.get_or_create(
                owner=owner_profiles[bd["owner_key"]],
                iban=bd["iban"],
                defaults={
                    "banca": bd["banca"],
                    "intestatario": bd["intestatario"],
                    "attivo": bd["attivo"],
                    "ordinamento": bd["ordinamento"],
                },
            )
            bank_accounts[bd["owner_key"]] = acc

        self.stdout.write(self.style.SUCCESS("   [owners] Conti bancari creati/trovati: 3"))
        return users_created, owner_profiles, bank_accounts

    # -----------------------------------------------------------------------
    # OWNERSHIP SHARES
    # -----------------------------------------------------------------------

    def _seed_ownership_shares(self, owner_profiles):
        """Crea le quote di proprieta' (valid_from 2024-09-01, nessun valid_to)."""
        from properties.models import OwnershipShare

        valid_from = date(2024, 9, 1)
        shares_data = [
            ("sandro", Decimal("0.3334")),
            ("bruna", Decimal("0.3333")),
            ("fabio", Decimal("0.3333")),
        ]

        created = 0
        for owner_key, quota in shares_data:
            profile = owner_profiles[owner_key]
            exists = OwnershipShare.objects.filter(
                owner=profile,
                valid_from=valid_from,
                valid_to__isnull=True,
            ).exists()
            if not exists:
                OwnershipShare.objects.create(
                    owner=profile,
                    valid_from=valid_from,
                    valid_to=None,
                    quota=quota,
                )
                created += 1

        self.stdout.write(
            self.style.SUCCESS(f"   [shares] Quote proprieta' create: {created} (su 3)")
        )

    # -----------------------------------------------------------------------
    # TENANTS
    # -----------------------------------------------------------------------

    def _seed_tenants(self):
        """Crea User + TenantProfile per i 5 inquilini + 1 storico (Marco Vecchio)."""
        from properties.models import TenantProfile

        gruppo_inquilini, _ = Group.objects.get_or_create(name="inquilini")

        tenants_data = [
            {
                "username": "mariasevera",
                "password": "mariaseverapwd",
                "first_name": "Mariasevera",
                "last_name": "Russo",
                "email": "mariasevera@example.com",
                "nominativo": "Mariasevera Russo",
                "codice_fiscale": "RSSMRS85L52H501W",
                "telefono": "+39 320 1112233",
                "email_alt": "m.russo.privata@gmail.com",
                "giorno_pagamento_affitto": 1,
                "frequenza_conguagli": "mensile",
            },
            {
                "username": "davide",
                "password": "davidepwd",
                "first_name": "Davide",
                "last_name": "Bianchi",
                "email": "davide@example.com",
                "nominativo": "Davide Bianchi",
                "codice_fiscale": "BNCDVD90A15F205K",
                "telefono": "+39 347 2223344",
                "email_alt": "",
                "giorno_pagamento_affitto": 10,
                "frequenza_conguagli": "mensile",
            },
            {
                "username": "diana",
                "password": "dianapwd",
                "first_name": "Diana",
                "last_name": "Petrov",
                "email": "diana@example.com",
                "nominativo": "Diana Petrov",
                "codice_fiscale": "PTRDNI92H68Z129Q",
                "telefono": "+39 338 3334455",
                "email_alt": "dianap.ro@outlook.com",
                "giorno_pagamento_affitto": 5,
                "frequenza_conguagli": "mensile",
            },
            {
                "username": "arun",
                "password": "arunpwd",
                "first_name": "Arun",
                "last_name": "Kumar",
                "email": "arun@example.com",
                "nominativo": "Arun Kumar",
                "codice_fiscale": "KMRRAN88R12Z222J",
                "telefono": "+39 349 4445566",
                "email_alt": "",
                "giorno_pagamento_affitto": 15,
                "frequenza_conguagli": "bimestrale",
            },
            {
                "username": "eshani",
                "password": "eshanipwd",
                "first_name": "Eshani",
                "last_name": "Perera",
                "email": "eshani@example.com",
                "nominativo": "Eshani Perera",
                "codice_fiscale": "PRSSHJ95T68Z148M",
                "telefono": "+39 370 5556677",
                "email_alt": "eshani.perera@hotmail.com",
                "giorno_pagamento_affitto": 27,
                "frequenza_conguagli": "mensile",
            },
        ]

        tenant_profiles = {}
        for td in tenants_data:
            user, created = User.objects.get_or_create(
                username=td["username"],
                defaults={
                    "first_name": td["first_name"],
                    "last_name": td["last_name"],
                    "email": td["email"],
                },
            )
            if created:
                user.set_password(td["password"])
                user.save()
                user.groups.add(gruppo_inquilini)

            profile, _ = TenantProfile.objects.get_or_create(
                user=user,
                defaults={
                    "nominativo": td["nominativo"],
                    "codice_fiscale": td["codice_fiscale"],
                    "telefono": td["telefono"],
                    "email_alt": td["email_alt"],
                    "giorno_pagamento_affitto": td["giorno_pagamento_affitto"],
                    "frequenza_conguagli": td["frequenza_conguagli"],
                },
            )
            tenant_profiles[td["username"]] = profile

        # Inquilino storico: Marco Vecchio (ha occupato Camera Avena prima di Arun)
        marco_user, created = User.objects.get_or_create(
            username="marco_vecchio",
            defaults={
                "first_name": "Marco",
                "last_name": "Vecchio",
                "email": "marco.vecchio@example.com",
            },
        )
        if created:
            marco_user.set_password("marcovecchiopwd")
            marco_user.save()
            marco_user.groups.add(gruppo_inquilini)

        marco_profile, _ = TenantProfile.objects.get_or_create(
            user=marco_user,
            defaults={
                "nominativo": "Marco Vecchio",
                "codice_fiscale": "VCCMRC88D15F205P",
                "telefono": "+39 333 9998877",
                "email_alt": "",
                "giorno_pagamento_affitto": 1,
                "frequenza_conguagli": "mensile",
            },
        )
        tenant_profiles["marco_vecchio"] = marco_profile

        self.stdout.write(
            self.style.SUCCESS(f"   [tenants] Inquilini creati/trovati: {len(tenant_profiles)} (5 attivi + 1 storico)")
        )
        return tenant_profiles, {}

    # -----------------------------------------------------------------------
    # ROOMS
    # -----------------------------------------------------------------------

    def _seed_rooms(self):
        """Crea le 5 stanze."""
        from properties.models import Room

        rooms_data = [
            {"nome": "Camera Salvia", "superficie_mq": Decimal("15.00"), "ordinamento": 1},
            {"nome": "Camera Miele", "superficie_mq": Decimal("12.00"), "ordinamento": 2},
            {"nome": "Camera Argilla", "superficie_mq": Decimal("18.00"), "ordinamento": 3},
            {"nome": "Camera Avena", "superficie_mq": Decimal("14.00"), "ordinamento": 4},
            {"nome": "Camera Legno", "superficie_mq": Decimal("16.00"), "ordinamento": 5},
        ]

        rooms = {}
        for rd in rooms_data:
            room, _ = Room.objects.get_or_create(
                nome=rd["nome"],
                defaults={
                    "superficie_mq": rd["superficie_mq"],
                    "ordinamento": rd["ordinamento"],
                },
            )
            rooms[rd["nome"]] = room

        self.stdout.write(self.style.SUCCESS(f"   [rooms] Stanze create/trovate: {len(rooms)}"))
        return rooms

    # -----------------------------------------------------------------------
    # CONTRACT
    # -----------------------------------------------------------------------

    def _seed_contract(self):
        """Crea il contratto unico di locazione."""
        from properties.models import Contract

        contract, created = Contract.objects.get_or_create(
            data_decorrenza=date(2024, 9, 20),
            defaults={
                "data_stipula": date(2024, 9, 15),
                "durata_anni": 4,
                "asseverato": True,
                "regime_fiscale": "cedolare_10",
                "note": "Contratto unico Via Palestrina, Monza, asseverato per cedolare 10%",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"   [contract] Contratto {'creato' if created else 'gia esistente'}")
        )
        return contract

    # -----------------------------------------------------------------------
    # ROOM ASSIGNMENTS
    # -----------------------------------------------------------------------

    def _seed_room_assignments(self, rooms, tenant_profiles, _unused):
        """
        Crea le assegnazioni stanze.

        Canoni mensili:
          Camera Salvia   -> mariasevera  420€
          Camera Miele    -> davide       380€
          Camera Argilla  -> diana        500€
          Camera Avena    -> marco_vecchio (storico) + arun (cessione dal 2025-09-01)
          Camera Legno    -> eshani       450€

        Cessione Camera Avena:
          Marco Vecchio: 2024-09-20 -> 2025-08-31 (data_atto_cessione=2025-08-31)
          Arun:          2025-09-01 -> None       (data_atto_cessione=2025-08-31)
        """
        from properties.models import RoomAssignment

        assignments_specs = [
            {
                "room_nome": "Camera Salvia",
                "tenant_key": "mariasevera",
                "valid_from": date(2024, 9, 20),
                "valid_to": None,
                "canone_mensile": Decimal("420.00"),
                "deposito_versato": Decimal("420.00"),
                "data_atto_cessione": None,
            },
            {
                "room_nome": "Camera Miele",
                "tenant_key": "davide",
                "valid_from": date(2024, 9, 20),
                "valid_to": None,
                "canone_mensile": Decimal("380.00"),
                "deposito_versato": Decimal("380.00"),
                "data_atto_cessione": None,
            },
            {
                "room_nome": "Camera Argilla",
                "tenant_key": "diana",
                "valid_from": date(2024, 9, 20),
                "valid_to": None,
                "canone_mensile": Decimal("500.00"),
                "deposito_versato": Decimal("500.00"),
                "data_atto_cessione": None,
            },
            # Camera Avena: storico Marco Vecchio
            {
                "room_nome": "Camera Avena",
                "tenant_key": "marco_vecchio",
                "valid_from": date(2024, 9, 20),
                "valid_to": date(2025, 8, 31),
                "canone_mensile": Decimal("400.00"),
                "deposito_versato": Decimal("400.00"),
                "data_atto_cessione": date(2025, 8, 31),
            },
            # Camera Avena: Arun subentra con cessione dal 2025-09-01
            {
                "room_nome": "Camera Avena",
                "tenant_key": "arun",
                "valid_from": date(2025, 9, 1),
                "valid_to": None,
                "canone_mensile": Decimal("400.00"),
                "deposito_versato": Decimal("400.00"),
                "data_atto_cessione": date(2025, 8, 31),
            },
            {
                "room_nome": "Camera Legno",
                "tenant_key": "eshani",
                "valid_from": date(2024, 9, 20),
                "valid_to": None,
                "canone_mensile": Decimal("450.00"),
                "deposito_versato": Decimal("450.00"),
                "data_atto_cessione": None,
            },
        ]

        room_assignments = {}
        for spec in assignments_specs:
            room = rooms[spec["room_nome"]]
            tenant = tenant_profiles[spec["tenant_key"]]
            # Chiave unica: stanza + tenant + valid_from
            assignment, created = RoomAssignment.objects.get_or_create(
                room=room,
                tenant=tenant,
                valid_from=spec["valid_from"],
                defaults={
                    "valid_to": spec["valid_to"],
                    "canone_mensile": spec["canone_mensile"],
                    "deposito_versato": spec["deposito_versato"],
                    "data_atto_cessione": spec["data_atto_cessione"],
                },
            )
            key = f"{spec['tenant_key']}_{spec['room_nome'].replace(' ', '_')}"
            room_assignments[key] = assignment

        # Dizionario comodo per accesso per tenant attivo
        room_assignments["mariasevera"] = room_assignments["mariasevera_Camera_Salvia"]
        room_assignments["davide"] = room_assignments["davide_Camera_Miele"]
        room_assignments["diana"] = room_assignments["diana_Camera_Argilla"]
        room_assignments["arun"] = room_assignments["arun_Camera_Avena"]
        room_assignments["eshani"] = room_assignments["eshani_Camera_Legno"]
        room_assignments["marco_vecchio"] = room_assignments["marco_vecchio_Camera_Avena"]

        self.stdout.write(
            self.style.SUCCESS(f"   [assignments] Assegnazioni create/trovate: {len(assignments_specs)} (5 attive + 1 storica)")
        )
        return room_assignments

    # -----------------------------------------------------------------------
    # ANNUAL UTILITY COSTS (TARI)
    # -----------------------------------------------------------------------

    def _seed_annual_utility_costs(self):
        """Crea i costi annuali TARI per 2025 e 2026."""
        from billing.models import AnnualUtilityCost

        tari_data = [
            {
                "voce": "tari",
                "anno": 2025,
                "importo_annuale": Decimal("510.00"),
                "valid_from": date(2025, 1, 1),
                "valid_to": date(2025, 12, 31),
            },
            {
                "voce": "tari",
                "anno": 2026,
                "importo_annuale": Decimal("520.00"),
                "valid_from": date(2026, 1, 1),
                "valid_to": None,
            },
        ]

        created = 0
        for td in tari_data:
            _, is_new = AnnualUtilityCost.objects.get_or_create(
                voce=td["voce"],
                anno=td["anno"],
                defaults={
                    "importo_annuale": td["importo_annuale"],
                    "valid_from": td["valid_from"],
                    "valid_to": td["valid_to"],
                },
            )
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"   [tari] AnnualUtilityCost create: {created} (su 2)"))

    # -----------------------------------------------------------------------
    # SUPPLIERS
    # -----------------------------------------------------------------------

    def _seed_suppliers(self, owner_profiles):
        """Crea i 3 fornitori principali."""
        from billing.models import Supplier

        suppliers_data = [
            {"nome": "Enel Energia", "tipo": "energia"},
            {"nome": "Eni Plenitude", "tipo": "gas"},
            {"nome": "Acque Spa", "tipo": "acqua"},
        ]

        suppliers = {}
        for sd in suppliers_data:
            supplier, _ = Supplier.objects.get_or_create(
                nome=sd["nome"],
                defaults={"tipo": sd["tipo"]},
            )
            suppliers[sd["nome"]] = supplier

        self.stdout.write(self.style.SUCCESS(f"   [suppliers] Fornitori creati/trovati: {len(suppliers)}"))
        return suppliers

    # -----------------------------------------------------------------------
    # UTILITY BILLS
    # -----------------------------------------------------------------------

    def _seed_utility_bills(self, suppliers, owner_profiles):
        """
        Crea bollette luce (Enel, bimestrali) e gas (Eni, bimestrali) per gen-apr 2026.

        Periodi bimestrali 2026:
          Periodo 1: 2025-11-01 -> 2025-12-31 (emessa gennaio 2026)
          Periodo 2: 2026-01-01 -> 2026-02-28 (emessa marzo 2026)
          Periodo 3: 2026-03-01 -> 2026-04-30 (emessa maggio 2026)
          Periodo 4: 2025-09-01 -> 2025-10-31 (storica, emessa novembre 2025)

        Importi luce: stagionale 120-180€ (inverno piu alto)
        Importi gas:  stagionale 80-200€ (inverno piu alto)
        """
        from billing.models import UtilityBill

        bruna_profile = owner_profiles["bruna"]
        enel = suppliers["Enel Energia"]
        eni = suppliers["Eni Plenitude"]

        bills_data = [
            # Luce (Enel) — 4 bimestri
            {
                "supplier": enel,
                "numero_fattura": "ENEL-2025-001",
                "data_emissione": date(2025, 11, 10),
                "periodo_da": date(2025, 9, 1),
                "periodo_a": date(2025, 10, 31),
                "importo_totale": Decimal("145.30"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": enel,
                "numero_fattura": "ENEL-2026-001",
                "data_emissione": date(2026, 1, 12),
                "periodo_da": date(2025, 11, 1),
                "periodo_a": date(2025, 12, 31),
                "importo_totale": Decimal("178.50"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": enel,
                "numero_fattura": "ENEL-2026-002",
                "data_emissione": date(2026, 3, 8),
                "periodo_da": date(2026, 1, 1),
                "periodo_a": date(2026, 2, 28),
                "importo_totale": Decimal("162.80"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": enel,
                "numero_fattura": "ENEL-2026-003",
                "data_emissione": date(2026, 5, 5),
                "periodo_da": date(2026, 3, 1),
                "periodo_a": date(2026, 4, 30),
                "importo_totale": Decimal("124.60"),
                "pagata_da_owner": bruna_profile,
            },
            # Gas (Eni) — 4 bimestri
            {
                "supplier": eni,
                "numero_fattura": "ENI-2025-001",
                "data_emissione": date(2025, 11, 15),
                "periodo_da": date(2025, 9, 1),
                "periodo_a": date(2025, 10, 31),
                "importo_totale": Decimal("98.40"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": eni,
                "numero_fattura": "ENI-2026-001",
                "data_emissione": date(2026, 1, 18),
                "periodo_da": date(2025, 11, 1),
                "periodo_a": date(2025, 12, 31),
                "importo_totale": Decimal("195.20"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": eni,
                "numero_fattura": "ENI-2026-002",
                "data_emissione": date(2026, 3, 12),
                "periodo_da": date(2026, 1, 1),
                "periodo_a": date(2026, 2, 28),
                "importo_totale": Decimal("182.70"),
                "pagata_da_owner": bruna_profile,
            },
            {
                "supplier": eni,
                "numero_fattura": "ENI-2026-003",
                "data_emissione": date(2026, 5, 8),
                "periodo_da": date(2026, 3, 1),
                "periodo_a": date(2026, 4, 30),
                "importo_totale": Decimal("87.30"),
                "pagata_da_owner": bruna_profile,
            },
        ]

        created = 0
        for bd in bills_data:
            _, is_new = UtilityBill.objects.get_or_create(
                numero_fattura=bd["numero_fattura"],
                defaults={
                    "supplier": bd["supplier"],
                    "data_emissione": bd["data_emissione"],
                    "periodo_da": bd["periodo_da"],
                    "periodo_a": bd["periodo_a"],
                    "importo_totale": bd["importo_totale"],
                    "pagata_da_owner": bd["pagata_da_owner"],
                },
            )
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"   [bills] UtilityBill create: {created} (su 8)"))

    # -----------------------------------------------------------------------
    # UTILITY CHARGE PERIODS
    # -----------------------------------------------------------------------

    def _seed_utility_charge_periods(self):
        """Crea 4 periodi mensili di conguaglio (gen-apr 2026)."""
        from billing.models import UtilityChargePeriod

        periods_data = [
            {
                "periodo_da": date(2026, 1, 1),
                "periodo_a": date(2026, 1, 31),
                "stato": "inviato",
                "criterio_ripartizione": "pro_rata_giorni",
                "data_invio": date(2026, 2, 1),
            },
            {
                "periodo_da": date(2026, 2, 1),
                "periodo_a": date(2026, 2, 28),
                "stato": "inviato",
                "criterio_ripartizione": "pro_rata_giorni",
                "data_invio": date(2026, 3, 1),
            },
            {
                "periodo_da": date(2026, 3, 1),
                "periodo_a": date(2026, 3, 31),
                "stato": "inviato",
                "criterio_ripartizione": "pro_rata_giorni",
                "data_invio": date(2026, 4, 1),
            },
            {
                "periodo_da": date(2026, 4, 1),
                "periodo_a": date(2026, 4, 30),
                "stato": "inviato",
                "criterio_ripartizione": "pro_rata_giorni",
                "data_invio": date(2026, 5, 1),
            },
        ]

        periods = {}
        for pd_data in periods_data:
            period, _ = UtilityChargePeriod.objects.get_or_create(
                periodo_da=pd_data["periodo_da"],
                periodo_a=pd_data["periodo_a"],
                defaults={
                    "stato": pd_data["stato"],
                    "criterio_ripartizione": pd_data["criterio_ripartizione"],
                    "data_invio": pd_data["data_invio"],
                },
            )
            key = pd_data["periodo_da"].strftime("%Y-%m")
            periods[key] = period

        self.stdout.write(self.style.SUCCESS(f"   [periods] UtilityChargePeriod create/trovate: {len(periods)}"))
        return periods

    # -----------------------------------------------------------------------
    # UTILITY CHARGES + LINES (5 inquilini x 4 periodi = 20 record)
    # -----------------------------------------------------------------------

    def _seed_utility_charges(self, periods, room_assignments, tenant_profiles):
        """
        Crea UtilityCharge (5 x 4 = 20) e UtilityChargeLine (luce + gas + tari = 3 per charge).

        Importi per periodo (approssimati, somma delle lines == importo_totale):
          Luce quota mensile: ~27-36€ per inquilino (1/5 del bimestrale diviso 2)
          Gas quota mensile:  ~17-39€ per inquilino
          TARI quota mensile: ~8.67€ per inquilino (520/5/12)

        Arrotondamento: le righe sommano esattamente all'importo_totale tramite
        assegnazione esplicita delle frazioni.

        Stato:
          gen, feb, mar 2026 -> 'pagato' con data_pagamento entro scadenza+3
          apr 2026 -> 'atteso' (scadenza futura)
        """
        from billing.models import Receivable, UtilityChargeLine

        # Inquilini attivi con la loro assegnazione
        active_tenants = [
            ("mariasevera", "mariasevera"),
            ("davide", "davide"),
            ("diana", "diana"),
            ("arun", "arun"),
            ("eshani", "eshani"),
        ]

        # Importi per mese per voce (luce, gas, tari) per inquilino
        # Nota: TARI 520€/anno / 5 inquilini / 12 mesi = 8.67€
        # Luce e gas: quota proporzionale bimestrale / 2 mesi / 5 inquilini
        charge_amounts = {
            "2026-01": {
                "luce": Decimal("17.85"),   # 178.50 / 2 bimestri / 5
                "gas":  Decimal("19.52"),   # 195.20 / 2 bimestri / 5
                "tari": Decimal("8.67"),
                "totale": Decimal("46.04"),
            },
            "2026-02": {
                "luce": Decimal("16.28"),   # 162.80 / 2 / 5
                "gas":  Decimal("18.27"),   # 182.70 / 2 / 5
                "tari": Decimal("8.67"),
                "totale": Decimal("43.22"),
            },
            "2026-03": {
                "luce": Decimal("12.46"),   # 124.60 / 2 / 5
                "gas":  Decimal("8.73"),    # 87.30 / 2 / 5
                "tari": Decimal("8.67"),
                "totale": Decimal("29.86"),
            },
            "2026-04": {
                "luce": Decimal("12.46"),
                "gas":  Decimal("8.73"),
                "tari": Decimal("8.67"),
                "totale": Decimal("29.86"),
            },
        }

        # Verifica somme (luce + gas + tari == totale per ogni mese)
        for mese, vals in charge_amounts.items():
            somma = vals["luce"] + vals["gas"] + vals["tari"]
            # Aggiusta il totale alla somma effettiva per consistenza
            charge_amounts[mese]["totale"] = somma

        period_order = ["2026-01", "2026-02", "2026-03", "2026-04"]
        # I primi 3 periodi sono pagati, il 4o e' atteso
        paid_periods = {"2026-01", "2026-02", "2026-03"}

        created_charges = 0
        created_lines = 0

        for period_key in period_order:
            period = periods[period_key]
            amounts = charge_amounts[period_key]
            is_paid = period_key in paid_periods
            data_invio = period.data_invio  # es. 2026-02-01

            for tenant_key, assignment_key in active_tenants:
                assignment = room_assignments[assignment_key]
                scadenza = data_invio + timedelta(days=5)

                charge, charge_created = Receivable.objects.get_or_create(
                    utility_period=period,
                    assignment=assignment,
                    causale=Receivable.Causale.UTENZE,
                    defaults={
                        "competenza_da": period.periodo_da,
                        "competenza_a": period.periodo_a,
                        "importo_dovuto": amounts["totale"],
                        "scadenza": scadenza,
                        "stato": "pagato" if is_paid else "atteso",
                        "data_pagamento": scadenza + timedelta(days=3) if is_paid else None,
                        "importo_pagato": amounts["totale"] if is_paid else None,
                    },
                )

                if charge_created:
                    created_charges += 1
                    lines_data = [
                        ("luce", amounts["luce"], f"Quota luce pro-rata {period_key}"),
                        ("gas", amounts["gas"], f"Quota gas pro-rata {period_key}"),
                        ("tari", amounts["tari"], f"Quota TARI annuale {period_key}"),
                    ]
                    for voce, importo, dettaglio in lines_data:
                        UtilityChargeLine.objects.create(
                            receivable=charge,
                            voce=voce,
                            importo=importo,
                            dettaglio=dettaglio,
                        )
                        created_lines += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"   [charges] Receivable utenze create: {created_charges} (su 20), "
                f"UtilityChargeLine create: {created_lines} (su 60)"
            )
        )

    # -----------------------------------------------------------------------
    # RENT PAYMENTS (5 inquilini x 8 mesi)
    # -----------------------------------------------------------------------

    def _seed_rent_payments(self, room_assignments, owner_profiles, bank_accounts):
        """
        Crea i pagamenti affitto per 8 mesi (ott-2025 -> mag-2026).

        Bruna incassa il 70% dei pagamenti (sul suo conto).
        Sandro incassa il resto.
        Arun: solo da set-2025 (subentra con cessione).

        Stato ultimo mese (mag-2026):
          mariasevera, davide, diana -> 'pagato'
          eshani                     -> 'dichiarato'
          arun                       -> 'atteso'
        """
        from billing.models import Receivable

        bruna_profile = owner_profiles["bruna"]
        sandro_profile = owner_profiles["sandro"]
        bruna_iban = bank_accounts["bruna"]
        sandro_iban = bank_accounts["sandro"]

        # Definizione dei periodi mensili: (competenza_da, competenza_a, mese_key)
        months = []
        for anno, mese in [
            (2025, 10), (2025, 11), (2025, 12),
            (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5),
        ]:
            import calendar
            last_day = calendar.monthrange(anno, mese)[1]
            months.append((date(anno, mese, 1), date(anno, mese, last_day), f"{anno}-{mese:02d}"))

        current_month_key = "2026-05"

        # Stato per l'ultimo mese per tenant
        stato_ultimo_mese = {
            "mariasevera": "pagato",
            "davide": "pagato",
            "diana": "pagato",
            "eshani": "dichiarato",
            "arun": "atteso",
        }

        # Chi incassa per ogni tenant (sandro per davide e eshani, bruna per gli altri)
        incassato_da = {
            "mariasevera": (bruna_profile, bruna_iban),
            "davide": (sandro_profile, sandro_iban),
            "diana": (bruna_profile, bruna_iban),
            "arun": (bruna_profile, bruna_iban),
            "eshani": (sandro_profile, sandro_iban),
        }

        tenant_specs = [
            ("mariasevera", "mariasevera", 1),    # giorno_pagamento=1
            ("davide", "davide", 10),              # giorno_pagamento=10
            ("diana", "diana", 5),                 # giorno_pagamento=5
            ("arun", "arun", 15),                  # giorno_pagamento=15, da set-2025
            ("eshani", "eshani", 27),              # giorno_pagamento=27
        ]

        created = 0
        for tenant_key, assignment_key, giorno_pagamento in tenant_specs:
            assignment = room_assignments[assignment_key]
            canone = assignment.canone_mensile
            owner_profile, iban_account = incassato_da[tenant_key]

            for comp_da, comp_a, mese_key in months:
                # Arun subentra da settembre 2025; ottobre 2025 e' gia' valido
                # (assegnazione dal 2025-09-01, quindi ott-2025 incluso)
                if tenant_key == "arun" and mese_key < "2025-09":
                    continue

                # Scadenza: giorno_pagamento del mese di competenza
                import calendar
                last_valid_day = calendar.monthrange(comp_da.year, comp_da.month)[1]
                giorno_eff = min(giorno_pagamento, last_valid_day)
                scadenza = date(comp_da.year, comp_da.month, giorno_eff)

                is_last_month = (mese_key == current_month_key)
                stato = stato_ultimo_mese[tenant_key] if is_last_month else "pagato"

                if stato == "pagato":
                    data_pagamento = scadenza + timedelta(days=3)
                    importo_pagato = canone
                    incassato = owner_profile
                    iban_dest = iban_account
                elif stato == "dichiarato":
                    data_pagamento = None
                    importo_pagato = None
                    incassato = None
                    iban_dest = None
                else:  # atteso
                    data_pagamento = None
                    importo_pagato = None
                    incassato = None
                    iban_dest = None

                _, is_new = Receivable.objects.get_or_create(
                    assignment=assignment,
                    causale=Receivable.Causale.AFFITTO,
                    competenza_da=comp_da,
                    competenza_a=comp_a,
                    defaults={
                        "importo_dovuto": canone,
                        "importo_pagato": importo_pagato,
                        "data_pagamento": data_pagamento,
                        "scadenza": scadenza,
                        "stato": stato,
                        "incassato_da_owner": incassato,
                        "bank_account_destinazione": iban_dest,
                    },
                )
                if is_new:
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(f"   [rent] Receivable affitto create: {created} (~40 attesi)")
        )

    # -----------------------------------------------------------------------
    # EXTRA CHARGES
    # -----------------------------------------------------------------------

    def _seed_extra_charges(self, room_assignments):
        """Crea 1 Receivable extra di esempio: conguaglio condominiale per Diana."""
        from billing.models import Receivable

        diana_assignment = room_assignments["diana"]

        _, created = Receivable.objects.get_or_create(
            assignment=diana_assignment,
            causale=Receivable.Causale.EXTRA,
            descrizione="Conguaglio condominiale annuale 2025",
            defaults={
                "competenza_da": date(2025, 12, 1),
                "importo_dovuto": Decimal("85.00"),
                "scadenza": date(2025, 12, 31),
                "stato": "pagato",
                "note": "Riparto spese condominiali straordinarie 2025",
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"   [extra] Receivable extra {'creato' if created else 'gia esistente'} (1)")
        )

    # -----------------------------------------------------------------------
    # EXPENSES + EXPENSE CATEGORIES
    # -----------------------------------------------------------------------

    def _seed_expenses(self, owner_profiles, suppliers):
        """Crea categorie spesa e ~6 spese di esempio."""
        from billing.models import Expense, ExpenseCategory

        bruna = owner_profiles["bruna"]
        sandro = owner_profiles["sandro"]
        fabio = owner_profiles["fabio"]

        # Categorie
        categories_data = [
            {"nome": "Manutenzione ordinaria", "codice": "manutenzione", "ripartibile_inquilini": False},
            {"nome": "IMU", "codice": "imu", "ripartibile_inquilini": False},
            {"nome": "TARI", "codice": "tari", "ripartibile_inquilini": True},
            {"nome": "Assicurazione", "codice": "assicurazione", "ripartibile_inquilini": False},
            {"nome": "Cedolare secca", "codice": "cedolare", "ripartibile_inquilini": False},
            {"nome": "Condominio ordinario", "codice": "condominio_ord", "ripartibile_inquilini": True},
        ]

        cats = {}
        for cd in categories_data:
            cat, _ = ExpenseCategory.objects.get_or_create(
                codice=cd["codice"],
                defaults={
                    "nome": cd["nome"],
                    "ripartibile_inquilini": cd["ripartibile_inquilini"],
                },
            )
            cats[cd["codice"]] = cat

        self.stdout.write(self.style.SUCCESS(f"   [expenses] ExpenseCategory create/trovate: {len(cats)}"))

        # Spese
        expenses_data = [
            {
                "data": date(2025, 6, 16),
                "category": cats["imu"],
                "supplier": None,
                "importo": Decimal("450.00"),
                "descrizione": "IMU 2025 — quota Fabio anticipata da Bruna",
                "anticipata_da_owner": bruna,
                "riferimento_quota_owner": fabio,
                "ripartibile_su_inquilini": False,
                "note": "Bruna ha pagato l'IMU per la quota di Fabio",
            },
            {
                "data": date(2025, 7, 31),
                "category": cats["tari"],
                "supplier": None,
                "importo": Decimal("510.00"),
                "descrizione": "TARI F24 2025 — pagamento annuale",
                "anticipata_da_owner": bruna,
                "riferimento_quota_owner": None,
                "ripartibile_su_inquilini": True,
                "note": "F24 TARI 2025 anticipato da Bruna",
            },
            {
                "data": date(2025, 11, 12),
                "category": cats["manutenzione"],
                "supplier": None,
                "importo": Decimal("180.00"),
                "descrizione": "Intervento idraulico — perdita rubinetto bagno",
                "anticipata_da_owner": sandro,
                "riferimento_quota_owner": None,
                "ripartibile_su_inquilini": False,
                "note": "Idraulico Rossi Mario",
            },
            {
                "data": date(2026, 1, 15),
                "category": cats["assicurazione"],
                "supplier": None,
                "importo": Decimal("420.00"),
                "descrizione": "Assicurazione casa 2026 — polizza annuale",
                "anticipata_da_owner": bruna,
                "riferimento_quota_owner": None,
                "ripartibile_su_inquilini": False,
                "note": "",
            },
            {
                "data": date(2026, 3, 20),
                "category": cats["manutenzione"],
                "supplier": None,
                "importo": Decimal("120.00"),
                "descrizione": "Revisione caldaia 2026",
                "anticipata_da_owner": bruna,
                "riferimento_quota_owner": None,
                "ripartibile_su_inquilini": False,
                "note": "Manutenzione annuale obbligatoria",
            },
            {
                "data": date(2026, 4, 30),
                "category": cats["cedolare"],
                "supplier": None,
                "importo": Decimal("680.00"),
                "descrizione": "Acconto cedolare secca 2026 — quota Sandro",
                "anticipata_da_owner": sandro,
                "riferimento_quota_owner": sandro,
                "ripartibile_su_inquilini": False,
                "note": "Acconto 40% cedolare secca su canone annuo stimato",
            },
        ]

        created = 0
        for ed in expenses_data:
            _, is_new = Expense.objects.get_or_create(
                data=ed["data"],
                descrizione=ed["descrizione"],
                defaults={
                    "category": ed["category"],
                    "supplier": ed["supplier"],
                    "importo": ed["importo"],
                    "anticipata_da_owner": ed["anticipata_da_owner"],
                    "riferimento_quota_owner": ed["riferimento_quota_owner"],
                    "ripartibile_su_inquilini": ed["ripartibile_su_inquilini"],
                    "note": ed["note"],
                },
            )
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"   [expenses] Expense create: {created} (su 6)"))

    # -----------------------------------------------------------------------
    # REMINDER RULES + MESSAGE TEMPLATES
    # -----------------------------------------------------------------------

    def _seed_reminder_rules_and_templates(self):
        """Crea template messaggi e regole sollecito per affitto e conguagli."""
        from notifications.models import MessageTemplate, ReminderRule

        # Template messaggi
        templates_data = [
            {
                "codice": "promemoria_affitto_pre",
                "titolo": "Promemoria affitto in scadenza",
                "corpo": (
                    "Ciao {{nominativo}},\n\n"
                    "Ti ricordiamo che il pagamento dell'affitto di {{importo}}€ "
                    "scade il {{scadenza}}.\n\n"
                    "Grazie mille!\nI proprietari di Via Palestrina"
                ),
                "canale": "push",
            },
            {
                "codice": "sollecito_affitto_morbido",
                "titolo": "Sollecito affitto — primo promemoria",
                "corpo": (
                    "Ciao {{nominativo}},\n\n"
                    "Non abbiamo ancora ricevuto il pagamento dell'affitto di {{importo}}€ "
                    "con scadenza {{scadenza}}.\n"
                    "Se hai gia' effettuato il bonifico, puoi ignorare questo messaggio.\n\n"
                    "Grazie,\nI proprietari"
                ),
                "canale": "push",
            },
            {
                "codice": "sollecito_affitto_duro",
                "titolo": "Sollecito affitto — pagamento urgente",
                "corpo": (
                    "Gentile {{nominativo}},\n\n"
                    "Risulta ancora non ricevuto il pagamento dell'affitto di {{importo}}€ "
                    "scaduto il {{scadenza}}.\n"
                    "Ti preghiamo di provvedere al piu' presto o di contattarci.\n\n"
                    "I proprietari di Via Palestrina"
                ),
                "canale": "email",
            },
            {
                "codice": "conguaglio_inviato",
                "titolo": "Utenze inviate",
                "corpo": (
                    "Ciao {{nominativo}},\n\n"
                    "Trovi in allegato le utenze del periodo {{periodo}} "
                    "per un totale di {{importo}}€, con scadenza {{scadenza}}.\n\n"
                    "Per qualsiasi chiarimento siamo a disposizione.\n"
                    "I proprietari"
                ),
                "canale": "push",
            },
        ]

        templates = {}
        for td in templates_data:
            tmpl, _ = MessageTemplate.objects.get_or_create(
                codice=td["codice"],
                defaults={
                    "titolo": td["titolo"],
                    "corpo": td["corpo"],
                    "canale": td["canale"],
                },
            )
            templates[td["codice"]] = tmpl

        self.stdout.write(self.style.SUCCESS(f"   [templates] MessageTemplate create/trovati: {len(templates)}"))

        # Regole sollecito — Affitto (4 regole)
        affitto_rules = [
            {
                "applicabile_a": "affitto",
                "giorni_offset": -1,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "promemoria_affitto_pre",
            },
            {
                "applicabile_a": "affitto",
                "giorni_offset": 2,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "sollecito_affitto_morbido",
            },
            {
                "applicabile_a": "affitto",
                "giorni_offset": 9,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "sollecito_affitto_morbido",
            },
            {
                "applicabile_a": "affitto",
                "giorni_offset": 15,
                "canale": "both",
                "destinatario": "entrambi",
                "template_codice": "sollecito_affitto_duro",
            },
        ]

        # Regole sollecito — Conguagli (4 regole)
        conguaglio_rules = [
            {
                "applicabile_a": "conguaglio",
                "giorni_offset": 0,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "conguaglio_inviato",
            },
            {
                "applicabile_a": "conguaglio",
                "giorni_offset": 5,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "conguaglio_inviato",
            },
            {
                "applicabile_a": "conguaglio",
                "giorni_offset": 10,
                "canale": "push",
                "destinatario": "inquilino",
                "template_codice": "sollecito_affitto_morbido",
            },
            {
                "applicabile_a": "conguaglio",
                "giorni_offset": 20,
                "canale": "both",
                "destinatario": "entrambi",
                "template_codice": "sollecito_affitto_duro",
            },
        ]

        all_rules = affitto_rules + conguaglio_rules
        created_rules = 0

        for rd in all_rules:
            tmpl = templates.get(rd["template_codice"])
            _, is_new = ReminderRule.objects.get_or_create(
                applicabile_a=rd["applicabile_a"],
                giorni_offset=rd["giorni_offset"],
                defaults={
                    "canale": rd["canale"],
                    "destinatario": rd["destinatario"],
                    "template": tmpl,
                    "attiva": True,
                },
            )
            if is_new:
                created_rules += 1

        self.stdout.write(
            self.style.SUCCESS(f"   [reminders] ReminderRule create: {created_rules} (su 8)")
        )
