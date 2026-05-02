"""Popola il DB con i dati REALI di Viapal.

Sostituisce seed_demo (dati farlocchi) con anagrafiche, contratti e
assegnazioni stanze prese dai contratti reali in dati/.

Idempotente: rilanciabile, usa get_or_create.

Dati fonte (in dati/, gitignored):
- contratto-collettivo-2.pdf (vecchio 2023-09 -> 2026-08)
- contratto-2025-da-firmare.pdf (nuovo 2025-02 -> 2029-02)
- diana.txt (anagrafica subentrata a Elisa Chiappini)
- movimenti-sandro.csv (estratti conto parsati)
- bollette.csv (UtilityBill da nomi file)

Uso:
  ENV=dev uv run manage.py seed_reali           # popola
  ENV=dev uv run manage.py seed_reali --reset   # cancella TUTTO prima
"""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from properties.models import (
    Contract, OwnerBankAccount, OwnerProfile, OwnershipShare, Room,
    RoomAssignment, TenantProfile,
)
from billing.models import (
    AnnualUtilityCost, BankTransaction, Supplier, UtilityBill,
)
from notifications.models import MessageTemplate, ReminderRule


BASE_DIR = Path(__file__).resolve().parents[5]
DATI_DIR = BASE_DIR / "dati"


# === ANAGRAFICHE PROPRIETARI (dal contratto) ===
PROPRIETARI = [
    {
        "username": "sandro",
        "password": "sandropwd",
        "first_name": "Alessandro",
        "last_name": "Dentella",
        "is_staff": True,
        "nominativo": "Alessandro Dentella",
        "cf": "DNTLSN63D07Z404Z",
        "iban": "IT72I0503401799000000081536",
        "banca": "Webank (BPM)",
    },
    {
        "username": "bruna",
        "password": "brunapwd",
        "first_name": "Bruna Laura",
        "last_name": "Dentella",
        "nominativo": "Bruna Laura Dentella",
        "cf": "DNTBNL61H41Z404Q",
        # IBAN reale da inserire (placeholder per ora)
        "iban": "BRUNA-IBAN-PLACEHOLDER",
        "banca": "BPER (placeholder)",
    },
    {
        "username": "fabio",
        "password": "fabiopwd",
        "first_name": "Fabio Francesco",
        "last_name": "Dentella",
        "nominativo": "Fabio Francesco Dentella",
        "cf": "DNTFFR67P20A794C",
        "iban": "",  # placeholder
        "banca": "",
    },
]

# === ANAGRAFICHE INQUILINI (storici + attuali) ===
# data_pagamento: dal vecchio contratto = entro il 5; dal nuovo = entro il 15
INQUILINI = [
    # Attuali (contratto 2025)
    {
        "username": "eshani",
        "password": "eshanipwd",
        "first_name": "Eshani Nimansha",
        "last_name": "Polkotu Hetti Arachchilage",
        "nominativo": "Eshani Nimansha Polkotu Hetti Arachchilage",
        "cf": "PLKSNN91P66Z209I",
        "giorno_pagamento": 15,
        "stanza_codice": "papa",
    },
    {
        "username": "arun",
        "password": "arunpwd",
        "first_name": "Arun",
        "last_name": "Singarayar",
        "nominativo": "Arun Singarayar",
        "cf": "SNGRNA90C22Z222R",
        "giorno_pagamento": 15,
        "stanza_codice": "ufficio",
    },
    {
        "username": "mariasevera",
        "password": "mariaseverapwd",
        "first_name": "Maria Severa",
        "last_name": "Armas",
        "nominativo": "Maria Severa Armas",
        "cf": "RMSMSV63P21F704B",
        "giorno_pagamento": 5,    # storica, paga ancora come prima
        "stanza_codice": "mamma",
    },
    {
        "username": "elisa",
        "password": "elisapwd",
        "first_name": "Elisa",
        "last_name": "Chiappini",
        "nominativo": "Elisa Chiappini",
        "cf": "CHPLSE90D54Z611V",
        "giorno_pagamento": 15,
        "stanza_codice": "sala",  # poi cessione a Diana
    },
    {
        "username": "diana",
        "password": "dianapwd",
        "first_name": "Diana Carolina",
        "last_name": "Porras Rodriguez",
        "nominativo": "Diana Carolina Porras Rodriguez",
        "cf": "PRRDCR88S41Z604P",
        "giorno_pagamento": 15,
        "stanza_codice": "sala",  # subentra a Elisa
    },
    {
        "username": "davide",
        "password": "davidepwd",
        "first_name": "Davide",
        "last_name": "Di Maio",
        "nominativo": "Davide Di Maio",
        "cf": "DMIDVD99E28C286O",
        "giorno_pagamento": 5,   # storica, paga ancora come prima
        "stanza_codice": "guardaroba",
    },
    {
        "username": "lindy",
        "password": "lindypwd",
        "first_name": "Lindy Jo-Anne",
        "last_name": "Nyathi",
        "nominativo": "Lindy Jo-Anne Nyathi",
        "cf": "NYTLDY92E54Z337Q",
        "giorno_pagamento": 16,  # bonifico ricevuto il 16/12 e 16/01
        "stanza_codice": None,   # storica fugace 21/12/24 - 7/2/25
    },
    # Storici (contratto 2023, usciti)
    {
        "username": "salvatore",
        "password": "salvatorepwd",
        "first_name": "Salvatore",
        "last_name": "D'Angella",
        "nominativo": "Salvatore D'Angella",
        "cf": "DNGSVT88P15G786Q",
        "giorno_pagamento": 30,  # vedeva pagare a fine mese
        "stanza_codice": None,   # storico
    },
    {
        "username": "eugenia",
        "password": "eugeniapwd",
        "first_name": "Eugenia",
        "last_name": "Blundetto",
        "nominativo": "Eugenia Blundetto",
        "cf": "BLNGNE85E67I535Y",
        "giorno_pagamento": 24,
        "stanza_codice": None,
    },
    {
        "username": "marianna",
        "password": "mariannapwd",
        "first_name": "Marianna",
        "last_name": "Di Marino",
        "nominativo": "Marianna Di Marino",
        "cf": "",  # non in contratti, subentro probabilmente
        "giorno_pagamento": 25,
        "stanza_codice": None,
    },
]

# === STANZE ===
# Mappature mie -> Sandro: papà/mamma/ufficio/guardaroba/sala
STANZE = [
    {"codice": "mamma", "nome": "Camera Mamma", "ordinamento": 1},
    {"codice": "papa", "nome": "Camera Papà", "ordinamento": 2},
    {"codice": "ufficio", "nome": "Camera Ufficio", "ordinamento": 3},
    {"codice": "guardaroba", "nome": "Camera Guardaroba", "ordinamento": 4},
    {"codice": "sala", "nome": "Camera Sala", "ordinamento": 5},
]

# === CONTRATTI ===
CONTRATTO_VECCHIO = {
    "data_stipula": date(2023, 8, 15),  # stimato
    "data_decorrenza": date(2023, 9, 1),
    "data_scadenza": date(2026, 8, 31),
    "durata_anni": 3,
    "asseverato": True,
    "regime_fiscale": "cedolare_10",
    "canone_mensile_totale": Decimal("1860.00"),  # 22320/12
    "deposito_totale": Decimal("3720.00"),         # 2 mensilità
    "spese_acconto_mensile": Decimal("280.00"),
    "n_inquilini": 4,
    "note": "Contratto 4 stanze 2023-09 / 2026-08, asseverato cedolare 10%",
}
CONTRATTO_NUOVO = {
    "data_stipula": date(2025, 2, 15),
    "data_decorrenza": date(2025, 2, 15),
    "data_scadenza": date(2029, 2, 14),
    "durata_anni": 4,
    "asseverato": True,
    "regime_fiscale": "cedolare_10",
    "canone_mensile_totale": Decimal("2330.00"),  # 27960/12
    "deposito_totale": Decimal("4660.00"),         # 2 mensilità
    "spese_acconto_mensile": Decimal("350.00"),
    "n_inquilini": 5,
    "note": (
        "Contratto 5 stanze 2025-02 / 2029-02, asseverato cedolare 10%. "
        "Spese condominiali per inquilino partite a 70€/mese e poi alzate "
        "a 90€/mese (caldaia: tengono troppo caldo)."
    ),
}


class Command(BaseCommand):
    help = "Popola il DB con i dati REALI di Viapal (anagrafiche, contratti, assignment)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Cancella TUTTI i dati prima di reinserire")
        parser.add_argument("--skip-bank", action="store_true", help="Salta import BankTransaction")
        parser.add_argument("--skip-bills", action="store_true", help="Salta import UtilityBill")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            self.reset_db()

        self.crea_gruppi()
        owner_profiles = self.crea_proprietari()
        self.crea_quote(owner_profiles)
        self.crea_iban(owner_profiles)
        tenant_profiles = self.crea_inquilini()
        rooms = self.crea_stanze()
        contratto_vecchio = self.crea_contratto(CONTRATTO_VECCHIO, "vecchio")
        contratto_nuovo = self.crea_contratto(CONTRATTO_NUOVO, "nuovo")
        self.crea_assignment(rooms, tenant_profiles, contratto_vecchio, contratto_nuovo)
        self.crea_tari()
        self.crea_supplier()
        self.crea_template_e_reminder()

        if not opts["skip_bills"]:
            self.import_bollette()
        if not opts["skip_bank"]:
            self.import_bank()

        self.stdout.write(self.style.SUCCESS("\n=== seed_reali completato ==="))

    # --- helpers ---
    def reset_db(self):
        from billing.models import (
            UtilityChargeLine, UtilityCharge, UtilityChargePeriod,
            RentPayment, ExtraCharge, Expense, ExpenseCategory,
        )
        from accounting.models import (
            OwnerLedgerEntry, OwnerSettlement, InterOwnerLoan,
            InterOwnerEntry, WithholdingRule,
        )
        ordine = [
            BankTransaction, UtilityChargeLine, UtilityCharge, UtilityChargePeriod,
            UtilityBill, AnnualUtilityCost, RentPayment, ExtraCharge, Expense,
            ExpenseCategory, Supplier, RoomAssignment, OwnerBankAccount,
            OwnershipShare, Contract, Room, TenantProfile, OwnerProfile,
            InterOwnerEntry, InterOwnerLoan, WithholdingRule, OwnerLedgerEntry,
            OwnerSettlement,
        ]
        self.stdout.write("--- RESET DB ---")
        for m in ordine:
            n = m.objects.count()
            m.objects.all().delete()
            if n:
                self.stdout.write(f"  cancellati {n} {m.__name__}")
        # Cancello user tranne admin
        n = User.objects.exclude(username="admin").count()
        User.objects.exclude(username="admin").delete()
        self.stdout.write(f"  cancellati {n} user (mantengo admin)")

    def crea_gruppi(self):
        Group.objects.get_or_create(name="proprietari")
        Group.objects.get_or_create(name="inquilini")

    def crea_proprietari(self):
        gruppo = Group.objects.get(name="proprietari")
        out = {}
        for p in PROPRIETARI:
            user, _ = User.objects.get_or_create(
                username=p["username"],
                defaults={
                    "email": f"{p['username']}@viapal.local",
                    "first_name": p["first_name"],
                    "last_name": p["last_name"],
                    "is_staff": p.get("is_staff", False),
                },
            )
            user.set_password(p["password"])
            user.save()
            user.groups.add(gruppo)
            op, _ = OwnerProfile.objects.update_or_create(
                user=user,
                defaults={
                    "nominativo": p["nominativo"],
                    "codice_fiscale": p["cf"],
                },
            )
            out[p["username"]] = op
        self.stdout.write(self.style.SUCCESS(f"  proprietari: {len(out)}"))
        return out

    def crea_quote(self, owner_profiles):
        # 1/3 ognuno dal 2023-09-01 (inizio contratto vecchio), valid_to=None
        # NB: il modello accetta che la somma sia <= 1, qui mettiamo esattamente 1
        from decimal import ROUND_HALF_UP
        quote = [Decimal("0.3334"), Decimal("0.3333"), Decimal("0.3333")]
        for op, q in zip(owner_profiles.values(), quote):
            OwnershipShare.objects.update_or_create(
                owner=op, valid_from=date(2023, 9, 1),
                defaults={"valid_to": None, "quota": q},
            )
        self.stdout.write("  quote: 1/3 cadauno dal 2023-09-01")

    def crea_iban(self, owner_profiles):
        for p in PROPRIETARI:
            op = owner_profiles[p["username"]]
            if not p["iban"]:
                continue
            OwnerBankAccount.objects.update_or_create(
                owner=op, iban=p["iban"],
                defaults={
                    "banca": p["banca"],
                    "intestatario": p["nominativo"],
                    "attivo": True,
                    "ordinamento": 1,
                },
            )
        self.stdout.write("  IBAN proprietari: aggiornati")

    def crea_inquilini(self):
        gruppo = Group.objects.get(name="inquilini")
        out = {}
        for p in INQUILINI:
            user, _ = User.objects.get_or_create(
                username=p["username"],
                defaults={
                    "email": f"{p['username']}@viapal.local",
                    "first_name": p["first_name"],
                    "last_name": p["last_name"],
                },
            )
            user.set_password(p["password"])
            user.save()
            user.groups.add(gruppo)
            tp, _ = TenantProfile.objects.update_or_create(
                user=user,
                defaults={
                    "nominativo": p["nominativo"],
                    "codice_fiscale": p["cf"],
                    "giorno_pagamento_affitto": p["giorno_pagamento"],
                    "frequenza_conguagli": "mensile",
                },
            )
            out[p["username"]] = tp
        self.stdout.write(self.style.SUCCESS(f"  inquilini: {len(out)}"))
        return out

    def crea_stanze(self):
        out = {}
        for s in STANZE:
            r, _ = Room.objects.update_or_create(
                nome=s["nome"],
                defaults={"ordinamento": s["ordinamento"]},
            )
            out[s["codice"]] = r
        self.stdout.write(self.style.SUCCESS(f"  stanze: {len(out)}"))
        return out

    def crea_contratto(self, cfg, label):
        c, _ = Contract.objects.update_or_create(
            data_stipula=cfg["data_stipula"],
            defaults={
                "data_decorrenza": cfg["data_decorrenza"],
                "durata_anni": cfg["durata_anni"],
                "asseverato": cfg["asseverato"],
                "regime_fiscale": cfg["regime_fiscale"],
                "note": cfg["note"],
            },
        )
        self.stdout.write(f"  contratto {label}: {cfg['data_decorrenza']}")
        return c

    def crea_assignment(self, rooms, tenants, c_vecchio, c_nuovo):
        # Canone per inquilino: 1860/4 = 465 (vecchio); 2330/5 = 466 (nuovo)
        canone_v = Decimal("465.00")
        canone_n = Decimal("466.00")
        deposito_v = canone_v
        deposito_n = canone_n
        # NB: il deposito totale del contratto e' 2 mensilita',
        # ma per inquilino registriamo 1 mensilita' del suo canone

        # Vecchio contratto (2023-09 -> 2025-02-14, prima del nuovo)
        # 4 inquilini: Davide/D'Angella/Mariasevera/Eugenia
        vecchio = [
            ("davide", "guardaroba"),
            ("salvatore", None),     # storica, stanza non specificata: la lascio
            ("mariasevera", "mamma"),
            ("eugenia", None),
        ]
        # Per i due "None" sceglo le stanze libere a caso (papa, sala)
        vecchio_norm = []
        stanze_libere = ["papa", "sala", "ufficio"]
        for u, s in vecchio:
            if s is None:
                s = stanze_libere.pop(0)
            vecchio_norm.append((u, s))

        for u, s in vecchio_norm:
            tp = tenants[u]
            room = rooms[s]
            RoomAssignment.objects.update_or_create(
                tenant=tp, room=room, valid_from=date(2023, 9, 1),
                defaults={
                    "valid_to": date(2025, 2, 14),
                    "canone_mensile": canone_v,
                    "deposito_versato": deposito_v,
                    "data_atto_cessione": None,
                    "note": f"Contratto vecchio (2023-09 / 2025-02): {u} -> {s}",
                },
            )

        # Nuovo contratto (2025-02-15 in poi)
        # 5 inquilini: Eshani/Arun/Mariasevera/Elisa/Davide
        nuovo = [
            ("eshani", "papa"),
            ("arun", "ufficio"),
            ("mariasevera", "mamma"),
            ("elisa", "sala"),
            ("davide", "guardaroba"),
        ]
        for u, s in nuovo:
            tp = tenants[u]
            room = rooms[s]
            # Elisa lascia, Diana subentra il 10/7/2025 (22 gg di luglio).
            # Tra Elisa (uscita) e Diana (entrata) la stanza e' rimasta
            # sfitta qualche settimana -> Elisa esce circa 2025-06-15.
            if u == "elisa":
                vt = date(2025, 6, 15)
                cessione = date(2025, 7, 10)
                note = "Elisa: uscita giu-2025; cessione registrata 10/7/2025 a Diana"
            else:
                vt = None
                cessione = None
                note = f"Contratto nuovo (2025-02-15+): {u} -> {s}"
            RoomAssignment.objects.update_or_create(
                tenant=tp, room=room, valid_from=date(2025, 2, 15),
                defaults={
                    "valid_to": vt,
                    "canone_mensile": canone_n,
                    "deposito_versato": deposito_n,
                    "data_atto_cessione": cessione,
                    "note": note,
                },
            )

        # Lindy: presenza fugace nella stanza "sala" 21/12/24 - 7/2/25
        # (prima che Elisa la prendesse col nuovo contratto del 15/2/25)
        RoomAssignment.objects.update_or_create(
            tenant=tenants["lindy"], room=rooms["sala"],
            valid_from=date(2024, 12, 21),
            defaults={
                "valid_to": date(2025, 2, 7),
                "canone_mensile": canone_v,
                "deposito_versato": Decimal("1060.00"),  # da foglio Bruna
                "data_atto_cessione": None,
                "note": "Lindy Nyathi: contratto temporaneo 21/12/24 - 7/2/25",
            },
        )

        # Diana subentra il 2025-07-10 (22 gg in luglio: 10..31)
        RoomAssignment.objects.update_or_create(
            tenant=tenants["diana"], room=rooms["sala"], valid_from=date(2025, 7, 10),
            defaults={
                "valid_to": None,
                "canone_mensile": canone_n,
                "deposito_versato": deposito_n,
                "data_atto_cessione": date(2025, 7, 10),
                "note": "Diana subentra a Elisa Chiappini (cessione AdE)",
            },
        )

        n = RoomAssignment.objects.count()
        self.stdout.write(self.style.SUCCESS(f"  assignment: {n}"))

    def crea_tari(self):
        AnnualUtilityCost.objects.update_or_create(
            voce="tari", anno=2024,
            defaults={"importo_annuale": Decimal("510.00"),
                      "valid_from": date(2024, 1, 1), "valid_to": date(2024, 12, 31)},
        )
        AnnualUtilityCost.objects.update_or_create(
            voce="tari", anno=2025,
            defaults={"importo_annuale": Decimal("510.00"),
                      "valid_from": date(2025, 1, 1), "valid_to": date(2025, 12, 31)},
        )
        AnnualUtilityCost.objects.update_or_create(
            voce="tari", anno=2026,
            defaults={"importo_annuale": Decimal("520.00"),
                      "valid_from": date(2026, 1, 1), "valid_to": None},
        )
        self.stdout.write("  TARI: 2024+2025+2026")

    def crea_supplier(self):
        for nome, tipo in [
            ("Enel Energia", "energia"), ("Acea Energia", "energia"),
            ("Edison", "energia"), ("Wind/WindTre", "energia"),
            ("Eni Plenitude", "gas"),
        ]:
            Supplier.objects.update_or_create(nome=nome, defaults={"tipo": tipo})
        self.stdout.write("  supplier: 5")

    def crea_template_e_reminder(self):
        templates = [
            ("promemoria_affitto_pre", "Affitto in scadenza",
             "Ciao {{nominativo}}, manca 1 giorno alla scadenza del canone di {{importo}} per {{periodo}}."),
            ("sollecito_affitto_morbido", "Promemoria pagamento affitto",
             "Ciao {{nominativo}}, risulta non pagato il canone di {{importo}} per {{periodo}}. Tutto bene?"),
            ("sollecito_affitto_duro", "Sollecito di pagamento",
             "Ciao {{nominativo}}, l'affitto di {{importo}} per {{periodo}} risulta scaduto da {{giorni}} giorni."),
            ("conguaglio_inviato", "Conguaglio utenze",
             "Ciao {{nominativo}}, il conguaglio utenze di {{periodo}} è {{importo}}, scadenza {{scadenza}}."),
        ]
        for codice, titolo, corpo in templates:
            MessageTemplate.objects.update_or_create(
                codice=codice,
                defaults={"titolo": titolo, "corpo": corpo, "canale": "push"},
            )

        regole = [
            ("affitto", -1, "push", "inquilino", True),
            ("affitto",  2, "push", "inquilino", True),
            ("affitto",  9, "push", "inquilino", True),
            ("affitto", 15, "both", "entrambi",  True),
            ("conguaglio", 0, "push", "inquilino", True),
            ("conguaglio", 5, "push", "inquilino", True),
            ("conguaglio", 10, "push", "inquilino", True),
            ("conguaglio", 20, "both", "entrambi", True),
        ]
        for app, off, can, dest, attiva in regole:
            ReminderRule.objects.get_or_create(
                applicabile_a=app, giorni_offset=off, canale=can,
                destinatario=dest, defaults={"attiva": attiva},
            )
        self.stdout.write("  template + reminder rules: 4 + 8")

    def import_bank(self):
        # Sandro
        try:
            ba_sandro = OwnerBankAccount.objects.get(
                iban="IT72I0503401799000000081536")
            n = self._import_csv_bank(DATI_DIR / "movimenti-sandro.csv", ba_sandro)
            self.stdout.write(self.style.SUCCESS(f"  bank Sandro: {n} BankTransaction nuove"))
        except OwnerBankAccount.DoesNotExist:
            self.stdout.write(self.style.WARNING("  bank Sandro: BA non trovato, skip"))

        # Bruna (CSV multipli per anno)
        try:
            ba_bruna = OwnerBankAccount.objects.get(iban="BRUNA-IBAN-PLACEHOLDER")
            for fname in ["movimenti-bruna-2024.csv", "movimenti-bruna-2025.csv", "movimenti-bruna-2026.csv"]:
                n = self._import_csv_bank(DATI_DIR / fname, ba_bruna)
                self.stdout.write(self.style.SUCCESS(f"  bank Bruna {fname}: {n} BankTransaction nuove"))
        except OwnerBankAccount.DoesNotExist:
            self.stdout.write(self.style.WARNING("  bank Bruna: BA non trovato, skip"))

    def _import_csv_bank(self, path: Path, ba) -> int:
        if not path.exists():
            self.stdout.write(self.style.WARNING(f"  {path.name}: file mancante, skip"))
            return 0
        n_creati = 0
        with open(path) as f:
            for r in csv.DictReader(f):
                _, created = BankTransaction.objects.get_or_create(
                    data=r["data"],
                    importo=Decimal(r["importo_signed"]),
                    descrizione=r["descrizione"][:500],
                    owner_account=ba,
                )
                if created:
                    n_creati += 1
        return n_creati

    def import_bollette(self):
        path = DATI_DIR / "bollette.csv"
        if not path.exists():
            self.stdout.write(self.style.WARNING(f"  bollette: {path} mancante, skip"))
            return
        # Mappa fornitore in Supplier (creandolo se nuovo)
        suppliers = {s.nome.lower().split()[0]: s for s in Supplier.objects.all()}
        # alias
        suppliers["wind3"] = suppliers.get("wind/windtre")
        suppliers["wind"] = suppliers.get("wind/windtre")

        n_creati = 0
        with open(path) as f:
            for r in csv.DictReader(f):
                if not r["importo"]:
                    continue
                anno, mese = int(r["anno"]), int(r["mese"])
                # data_emissione: ultimo del mese (stima)
                from calendar import monthrange
                last = monthrange(anno, mese)[1]
                data_emiss = date(anno, mese, last)
                # Periodo bolletta: bimestrale tipico
                periodo_da = date(anno, mese, 1)
                periodo_a = date(anno, mese, last)
                # Supplier
                fornitore_key = r["fornitore"].lower() if r["fornitore"] else "enel"
                supp = suppliers.get(fornitore_key) or Supplier.objects.first()
                # numero_fattura placeholder
                numero = f"{r['file'].rsplit('.',1)[0]}"
                bill, created = UtilityBill.objects.get_or_create(
                    supplier=supp, numero_fattura=numero,
                    defaults={
                        "data_emissione": data_emiss,
                        "periodo_da": periodo_da,
                        "periodo_a": periodo_a,
                        "importo_totale": Decimal(r["importo"]),
                        "note": f"tipo={r['tipo']}, file={r['file']}",
                    },
                )
                if created:
                    n_creati += 1
        self.stdout.write(self.style.SUCCESS(f"  bollette: {n_creati} UtilityBill nuove"))
