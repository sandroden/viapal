"""Anonimizza la copia di produzione usata per l'ambiente demo (riprese video).

Si esegue SOLO su ``viapal_demo`` (``ENV=demo``) e UNA SOLA VOLTA: gli importi
vengono scalati (x 0,7) e una seconda esecuzione li scalerebbe due volte. Una
tabella ``demo_anonimizzazione`` (creata con SQL grezzo, niente migrazioni)
funge da marcatore di idempotenza.

Che cosa fa, in una sola transazione:

* persone (utenti, proprietari, inquilini, conti bancari) -> nomi, username,
  email, telefoni, codici fiscali, IBAN (checksum valido), nascita, residenza
  finti, coerenti ovunque; password di tutti = ``demo2026``. Gli inquilini
  diventano italiani (nomi per generazione, nascite da tutta Italia) tranne
  ``INQUILINO_STRANIERO_USER_ID``, che resta straniero;
* immobili e luoghi -> Novara, "Via dei Tigli", testi della galleria;
* testo libero di ogni modello (descrizioni dei movimenti, note, notifiche,
  modelli di documento...) con dizionario reale->finto + regex di pulizia;
* lead del bot Facebook riscritti con testi sintetici;
* importi x 0,7 con riparazione al centesimo degli invarianti;
* file (documenti, bollette, allegati) sostituiti da segnaposto PDF/immagine
  allo stesso percorso (le foto di galleria/stanze/immobile restano: le copia
  ``copia_media_demo``);
* cancellati sessioni, log admin, sottoscrizioni push, token, email in coda;
* verifica finale: nessun dato reale deve restare in nessuna colonna testuale.

Rifare da zero (dopo ``jmb-sync``, che aggiorna ``viapal``)::

    dropdb -p 5434 viapal_demo && createdb -p 5434 -T viapal viapal_demo
    cd backend && ENV=demo uv run python manage.py migrate
    ENV=demo uv run python manage.py anonimizza_demo [--dry-run]
    ENV=dev VIAPAL_DB_NAME=viapal_demo uv run python manage.py copia_media_demo
    ENV=demo uv run python manage.py cura_demo_video

``--dry-run`` esegue tutto in una transazione e fa rollback, stampando il
report (nessun file scritto, nessun marcatore).
"""
from __future__ import annotations

import difflib
import hashlib
import os
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Sum

from properties import anonimizza_demo as an

NOMI_TERZI_DEFAULT = os.path.expanduser("~/.config/viapal-demo/nomi-terzi.txt")
PASSWORD_DEMO = "demo2026"
# l'ABI dell'IBAN finto non e' assegnato: la banca non puo' essere una vera
BANCHE_FITTIZIE = ["Banca del Novarese", "Cassa di Risparmio Demo", "Banca Popolare dei Tigli",
                   "Credito Piemontese Demo"]
SEED = "viapal-demo-2026"
# Gli inquilini finti sono tutti italiani tranne uno (id dell'utente in
# produzione): un ex inquilino recente della Casa dei Tigli (giugno-settembre
# 2026), visibile nella ripartizione utenze di luglio ma non protagonista di
# nessuna scena. Gli inquilini attivi sono tutti protagonisti delle riprese.
INQUILINO_STRANIERO_USER_ID = 95

CAMPI_FOTO = an.CAMPI_FOTO  # foto che restano vere (le copia copia_media_demo)

# DecimalField NON scalati, con il motivo
ESCLUSI_DECIMALI = {
    ("properties.OwnershipShare", "quota"): "quota di proprietà (frazione, non un importo)",
    ("properties.Room", "superficie_mq"): "superficie in mq",
    ("billing.UtilityBill", "consumo"): "consumo (kWh / m³), non un importo",
}

# Modelli svuotati
DA_CANCELLARE = [
    "sessions.Session", "admin.LogEntry", "notifications.PushSubscription",
    "authtoken.Token", "account.EmailConfirmation",
]

# Modelli/campi testuali che il passaggio generico non deve toccare
MODELLI_NO_TESTO = {
    "auth.Permission", "auth.Group", "contenttypes.ContentType", "sessions.Session",
    "admin.LogEntry", "authtoken.Token", "authtoken.TokenProxy",
    "account.EmailConfirmation", "notifications.PushSubscription", "leads.Lead",
}
CAMPI_NO_TESTO = {("auth.User", "password"), ("sites.Site", "domain"), ("sites.Site", "name")}
# I modelli di documento hanno cifre e "euro" che non sono importi della casa
CAMPI_SENZA_IMPORTI = {("properties.DocumentTemplate", "corpo_html")}

TABELLE_NO_SCAN = {"django_migrations", "django_content_type", "auth_permission",
                   "auth_group", "django_site"}
COLONNE_NO_SCAN = {
    ("auth_user", "password"),
    ("properties_property", "foto_hero"), ("properties_property", "foto_planimetria"),
    ("properties_property", "foto_mappa"), ("properties_galleryimage", "image"),
    ("properties_room", "foto"),
}


class _Rollback(Exception):
    pass


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


# ---------------------------------------------------------------------------
# Persone
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    user_ids: list
    owner: object = None
    tenant: object = None
    nome: str = ""           # reale
    cognome: str = ""        # reale
    sesso: str = "M"
    estera: bool = False
    categoria: str = ""
    f_nome: str = ""         # finto (eventualmente due token)
    f_cognome: str = ""
    username: str = ""       # finto del profilo principale
    email: str = ""
    telefono: str = ""
    shift: int = 0
    comune_nascita: tuple = ()   # (comune, sigla/EE, belfiore)
    ruoli: list = field(default_factory=list)


class Contesto:
    """Tutto cio' che serve a sostituire dati reali con dati finti."""

    def __init__(self):
        self.scr = an.Scrubber(seed=SEED)
        self.persone: list[Persona] = []
        self.reali: set[str] = set()          # token reali (minuscoli) per la verifica
        self.valori_reali: set[str] = set()   # email/IBAN/CF/telefoni reali
        self.luoghi: dict[str, str] = {}
        self.vie: dict[str, str] = {}
        self.usati_nomi: set[str] = set()
        self.usati_cognomi: set[str] = set()
        self.usernames: set[str] = set()
        self.emails: set[str] = set()
        self.cognomi_cache: dict[str, str] = {}
        self.pool_comuni_no = list(an.COMUNI_NO)
        self.pool_vie = list(an.VIE_FINTE)
        self.mappa: list[tuple[str, str]] = []  # (reale, finto) per --mostra-mappa
        self.cat_i = 0


class Command(BaseCommand):
    help = __doc__

    def create_parser(self, prog_name, subcommand, **kwargs):
        from argparse import RawDescriptionHelpFormatter
        kwargs.setdefault("formatter_class", RawDescriptionHelpFormatter)
        return super().create_parser(prog_name, subcommand, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Fa tutto in una transazione e poi rollback (report, nessun file).")
        parser.add_argument("--ignora-residui", action="store_true",
                            help="Non fallire se la verifica trova dati reali residui.")
        parser.add_argument("--nomi-terzi", metavar="FILE", default=NOMI_TERZI_DEFAULT,
                            help="File (un nome per riga, # commenti) con nomi di terzi che "
                                 "compaiono nei testi e non sono in anagrafica. Va tenuto "
                                 f"FUORI dal repo (default: {NOMI_TERZI_DEFAULT}).")
        parser.add_argument("--campioni", metavar="FILE",
                            help="Scrive su FILE le parole non italiane/inglesi rimaste nei testi "
                                 "(per cercare a occhio nomi di terzi sfuggiti).")
        parser.add_argument("--mostra-mappa", action="store_true",
                            help="Stampa la mappa reale->finto dei nomi (contiene dati reali!).")

    # ------------------------------------------------------------------ main
    def handle(self, *args, **opts):
        nome_db = settings.DATABASES["default"]["NAME"]
        if nome_db != "viapal_demo" or not getattr(settings, "DEMO", False):
            raise CommandError(
                f"Rifiuto: servono ENV=demo e db 'viapal_demo' (db attuale: {nome_db}, "
                f"DEMO={getattr(settings, 'DEMO', False)}).")
        self.dry = opts["dry_run"]
        self.opts = opts
        self.out = self.stdout.write
        try:
            with transaction.atomic():
                self._esegui()
                if self.dry:
                    raise _Rollback()
        except _Rollback:
            self.out(self.style.WARNING("\n--dry-run: rollback eseguito, nessuna modifica."))

    # ---------------------------------------------------------------- orchestr
    def _esegui(self):
        with connection.cursor() as c:
            c.execute("CREATE TABLE IF NOT EXISTS demo_anonimizzazione "
                      "(eseguita_il timestamptz NOT NULL DEFAULT now())")
            c.execute("SELECT count(*) FROM demo_anonimizzazione")
            if c.fetchone()[0]:
                raise CommandError(
                    "Anonimizzazione gia' eseguita su questo db (tabella demo_anonimizzazione): "
                    "rifai il db da zero (vedi --help).")

        self.out(self.style.MIGRATE_HEADING("1. Metriche prima"))
        prima = self._metriche()

        self.out(self.style.MIGRATE_HEADING("2. Contesto (persone, luoghi, dizionario)"))
        ctx = Contesto()
        self.ctx = ctx
        self._costruisci_contesto(ctx)

        self.out(self.style.MIGRATE_HEADING("3. Testo libero di tutti i modelli"))
        self._testo_generico(ctx)

        self.out(self.style.MIGRATE_HEADING("4. Persone, immobili, lead"))
        self._persone(ctx)
        self._immobili(ctx)
        self._lead(ctx)
        self._bollette(ctx)
        self._contabilita_proprietari()

        self.out(self.style.MIGRATE_HEADING("5. Importi x 0,7"))
        self._importi()

        self.out(self.style.MIGRATE_HEADING("6. Pulizia (sessioni, log, push, token)"))
        self._pulizia()

        self.out(self.style.MIGRATE_HEADING("7. File segnaposto"))
        self._file(ctx)

        self.out(self.style.MIGRATE_HEADING("8. Password"))
        self._password()

        self.out(self.style.MIGRATE_HEADING("9. Metriche dopo e confronto"))
        dopo = self._metriche()
        self._confronta(prima, dopo)

        self.out(self.style.MIGRATE_HEADING("10. Verifica residui"))
        self._verifica(ctx)

        if self.opts["campioni"]:
            self._campioni(self.opts["campioni"])
        with connection.cursor() as c:
            c.execute("INSERT INTO demo_anonimizzazione DEFAULT VALUES")
        self._report_utenti(ctx)
        if self.opts["mostra_mappa"]:
            self.out("\nMappa reale -> finto (dati reali!):")
            for r, f in sorted(ctx.mappa):
                self.out(f"  {r!r:45} -> {f!r}")

    # ======================================================== costruzione contesto
    def _costruisci_contesto(self, ctx: Contesto):
        User = get_user_model()
        OwnerProfile = apps.get_model("properties", "OwnerProfile")
        TenantProfile = apps.get_model("properties", "TenantProfile")
        Property = apps.get_model("properties", "Property")
        Contract = apps.get_model("properties", "Contract")
        Membership = apps.get_model("properties", "PropertyMembership")

        users = list(User.objects.order_by("pk"))
        owners = {o.user_id: o for o in OwnerProfile.objects.all()}
        tenants = {t.user_id: t for t in TenantProfile.objects.all()}

        # gruppi: stesso utente profilo, oppure stessa email
        parent = {u.pk: u.pk for u in users}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        by_email: dict = {}
        for u in users:
            e = (u.email or "").strip().lower()
            if e:
                if e in by_email:
                    parent[find(u.pk)] = find(by_email[e])
                else:
                    by_email[e] = u.pk
        gruppi: dict = {}
        for u in users:
            gruppi.setdefault(find(u.pk), []).append(u)

        sistema = {"admin", "bot"}
        scr = ctx.scr
        reali = ctx.reali

        def aggiungi_reali(*stringhe):
            for s in stringhe:
                for t in an.tokens_nome(s or ""):
                    if an.token_significativo(t):
                        reali.add(t.lower())

        # --- token reali di partenza (servono a filtrare i pool) ---------------
        for u in users:
            aggiungi_reali(u.first_name, u.last_name, u.username, u.email.split("@")[0])
        for p in list(owners.values()) + list(tenants.values()):
            aggiungi_reali(p.nome, p.cognome, p.nominativo)
        for p in list(owners.values()) + list(tenants.values()):
            aggiungi_reali(p.residenza_via, p.residenza_comune, p.comune_nascita,
                           getattr(p, "documento_autorita", ""))
        for c in Contract.objects.all():
            aggiungi_reali(c.ufficio_registrazione)
        for p in Property.objects.all():
            aggiungi_reali(p.comune, p.via, p.nome)
        terzi = self._leggi_terzi()
        for t in terzi:
            reali.add(t.lower())
        ctx.reali_nomi = set(reali)

        # --- luoghi (prima delle persone: servono per i reali) -------------------
        props = list(Property.objects.order_by("pk"))
        fake_prop = [
            {"nome": "Casa dei Tigli", "slug": "casa-dei-tigli", "via_nome": "dei Tigli",
             "comune": "Novara", "cap": "28100"},
            {"nome": "Casa dei Gelsomini", "slug": "casa-dei-gelsomini",
             "via_nome": "dei Gelsomini", "comune": "Galliate", "cap": "28066"},
        ]
        ctx.fake_prop = {}
        for i, p in enumerate(props):
            fp = fake_prop[i] if i < len(fake_prop) else {
                "nome": f"Casa {i + 1}", "slug": f"casa-{i + 1}", "via_nome": "dei Pioppi",
                "comune": an.COMUNI_NO[(i + 3) % len(an.COMUNI_NO)][0], "cap": "28100"}
            ctx.fake_prop[p.pk] = fp
            ctx.luoghi[p.comune.lower()] = fp["comune"]
            # nome della via = parole significative di "Via Palestrina"
            for t in an.tokens_nome(p.via):
                if an.token_significativo(t):
                    scr.aggiungi_nome(t, fp["via_nome"])
                    ctx.vie[t.lower()] = fp["via_nome"]
                    reali.add(t.lower())
            if p.cap:
                scr.aggiungi_nome(p.cap, fp["cap"])
            # lo slug entra nei percorsi dei file (bollette/<slug>/...): se contiene il
            # nome della via ("viapessi") va cambiato; "viapal" e' il prodotto e resta
            if any(t in p.slug.lower() for t in ctx.vie) and p.slug != fp["slug"]:
                scr.percorsi[p.slug] = fp["slug"]
            # idem per il nome dell'immobile nei testi ("invitato come proprietario di ViaPessi")
            if any(t in p.nome.lower() for t in ctx.vie):
                scr.aggiungi_nome(p.nome, fp["nome"])
            ctx.usati_nomi.add(fp["comune"].lower())
        scr.regex_extra = [
            (rf"/g/{re.escape(p.slug)}(?![\w-])", f"/g/{ctx.fake_prop[p.pk]['slug']}")
            for p in props
        ]
        # località e citta' che compaiono nei testi della galleria / dei lead
        extra_luoghi = {"brianza": "Novarese", "villa reale": "Castello Visconteo",
                        "parco di monza": "Parco dei Tigli", "san gerardo": "Maggiore della Carità"}
        for k, v in extra_luoghi.items():
            scr.aggiungi_nome(k, v)
        scr.aggiungi_nome("viapal.e-den.it", "viapal.example.com")
        scr.aggiungi_nome("e-den.it", "example.com")
        scr.regex_extra.append((r"s3\.viapal\.example\.com", "s3.viapal.example.com"))

        def luogo_finto(nome: str) -> str:
            k = nome.strip().lower()
            if not k:
                return ""
            if k not in ctx.luoghi:
                while ctx.pool_comuni_no:
                    cand = ctx.pool_comuni_no.pop(0)[0]
                    if cand.lower() not in ctx.usati_nomi and cand.lower() not in reali:
                        ctx.usati_nomi.add(cand.lower())
                        ctx.luoghi[k] = cand
                        break
                else:
                    ctx.luoghi[k] = "Cerano"
            return ctx.luoghi[k]
        ctx.luogo_finto = luogo_finto

        def via_finta(via: str) -> str:
            """Nome finto (senza tipo) per le vie diverse da quelle degli immobili."""
            k = via.strip().lower()
            if k not in ctx.vie:
                ctx.vie[k] = ctx.pool_vie.pop(0) if ctx.pool_vie else "Roma"
            return ctx.vie[k]
        ctx.via_finta = via_finta

        # --- persone ---------------------------------------------------------------
        indice = 0
        for gid in sorted(gruppi):
            membri = gruppi[gid]
            ha_profilo = any(u.pk in owners or u.pk in tenants for u in membri)
            if not ha_profilo and all(u.username in sistema for u in membri):
                continue
            pers = Persona(user_ids=[u.pk for u in membri])
            pers.owner = next((owners[u.pk] for u in membri if u.pk in owners), None)
            pers.tenant = next((tenants[u.pk] for u in membri if u.pk in tenants), None)
            prof = pers.owner or pers.tenant
            self._nome_cognome_reali(pers, prof, membri)
            self._origine(pers, prof)
            ctx.persone.append(pers)
            indice += 1

        # ordine stabile: per id del primo utente
        ctx.persone.sort(key=lambda p: min(p.user_ids))
        for pers in ctx.persone:
            self._genera_finto(ctx, pers, users, owners, tenants)

        # --- token dei finti gia' usati + aziende (non sono nomi di persona) -------------
        for pers in ctx.persone:
            for t in (pers.f_nome + " " + pers.f_cognome).split():
                scr.token_noti.add(t.lower())
        Supplier = apps.get_model("billing", "Supplier")
        scr.aziende = {w.lower() for s_ in Supplier.objects.values_list("nome", flat=True)
                       for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}", s_)}
        scr.aziende |= {"edison", "enel", "acea", "wind", "windtre", "generali", "italia",
                        "poste", "agenzia", "entrate", "energia", "iren", "magis"}
        scr.vietati = ctx.reali_nomi
        # --- nomi di terzi dal file locale ----------------------------------------------
        for t in terzi:
            scr.aggiungi_nome(t, scr._terzo(t))
        self.out(f"   nomi di terzi dal file: {len(terzi)}")

        # --- luoghi dalle anagrafiche -------------------------------------------------
        for prof in list(owners.values()) + list(tenants.values()):
            if prof.residenza_comune:
                luogo_finto(prof.residenza_comune)
            m = re.match(r"(?i)\s*comune di\s+(.+)", prof.documento_autorita or "") \
                if hasattr(prof, "documento_autorita") else None
            if m:
                luogo_finto(m.group(1))
        for c in Contract.objects.exclude(ufficio_registrazione=""):
            luogo_finto(c.ufficio_registrazione)
        for k, v in list(ctx.luoghi.items()):
            for t in {k} | {x.lower() for x in an.tokens_nome(k) if len(x) >= 5}:
                scr.aggiungi_nome(t, v)
                reali.add(t)
        # vie delle residenze
        for prof in list(owners.values()) + list(tenants.values()):
            via = prof.residenza_via or ""
            if any(t in via.lower() for t in ctx.vie):
                continue
            for t in an.tokens_nome(re.sub(r"\d+", " ", via)):
                if an.token_significativo(t) and len(t) >= 4:
                    scr.aggiungi_nome(t, via_finta(t))
                    reali.add(t.lower())

        # --- membership: ruoli ---------------------------------------------------------
        for m in Membership.objects.select_related("user", "property"):
            for pers in ctx.persone:
                if m.user_id in pers.user_ids:
                    pers.ruoli.append((m.ruolo, m.property_id))

        # --- valori reali da cercare nella verifica ---------------------------------------
        for u in users:
            if u.email and u.username not in sistema:
                ctx.valori_reali.add(u.email.lower())
        for prof in list(owners.values()) + list(tenants.values()):
            for v in (prof.codice_fiscale,):
                if v:
                    ctx.valori_reali.add(re.sub(r"[^A-Za-z0-9]", "", v).lower())
            if prof.telefono:
                ctx.valori_reali.add("tel:" + an.normalizza_telefono(prof.telefono))
            if getattr(prof, "email_alt", ""):
                ctx.valori_reali.add(prof.email_alt.lower())
        OBA = apps.get_model("properties", "OwnerBankAccount")
        for a in OBA.objects.all():
            if a.iban:
                ctx.valori_reali.add(re.sub(r"\s", "", a.iban).lower())
        # tutti i nomi del dizionario sono "token reali" da cercare
        ctx.verifica_tokens = {k for k in scr.nomi
                               if len(k) >= 3 and k not in an.TOKEN_COMUNI
                               and k not in ("viapal.e-den.it", "e-den.it")}
        ctx.verifica_tokens.update({"viapal.e-den.it", "e-den.it"})
        self.out(f"   persone: {len(ctx.persone)}, chiavi dizionario: {len(scr.nomi)}, "
                 f"luoghi: {len(ctx.luoghi)}, vie: {len(ctx.vie)}")
        if self.opts["mostra_mappa"]:
            for k, v in scr.nomi.items():
                ctx.mappa.append((k, v))

    def _leggi_terzi(self) -> list:
        percorso = self.opts.get("nomi_terzi")
        if not percorso or not os.path.exists(percorso):
            self.stdout.write(self.style.WARNING(
                f"   nessun file di nomi di terzi ({percorso}): i nomi non in anagrafica "
                "che compaiono nei testi resteranno (vedi --campioni)"))
            return []
        out = []
        with open(percorso, encoding="utf-8") as fh:
            for riga in fh:
                riga = riga.split("#")[0].strip()
                for t in an.tokens_nome(riga):
                    if an.token_significativo(t) and t.lower() not in out:
                        out.append(t.lower())
        return out

    # ---- nome/cognome reali di una persona -------------------------------------------
    def _nome_cognome_reali(self, pers: Persona, prof, membri):
        nome = _norm(prof.nome if prof else "") or next(
            (_norm(u.first_name) for u in membri if u.first_name), "")
        cogn = _norm(prof.cognome if prof else "") or next(
            (_norm(u.last_name) for u in membri if u.last_name), "")
        nomin = _norm(prof.nominativo if prof else "")
        if nomin:
            tn = nomin.split()
            if not nome and not cogn:
                nome, cogn = tn[0], " ".join(tn[1:])
            elif nome and not cogn:
                cogn = " ".join(t for t in tn if t.lower() not in nome.lower().split())
            elif cogn and not nome:
                nome = " ".join(t for t in tn if t.lower() not in cogn.lower().split())
        if not nome and not cogn:
            u = membri[0]
            parti = [p for p in re.split(r"[-_.]", u.username) if p and p != "storico"]
            nome = parti[0].capitalize() if parti else u.username
            cogn = " ".join(p.capitalize() for p in parti[1:])
        pers.nome, pers.cognome = nome, cogn

    # Z-code del paese di nascita -> categoria di nomi finti dello stesso ambito
    ZMAP: ClassVar[dict] = {"Z222": "india", "Z209": "srilanka", "Z330": "marocco", "Z243": "turchia",
            "Z604": "colombia", "Z611": "colombia", "Z337": "zimbabwe", "Z336": "egitto"}
    CITTMAP: ClassVar[tuple] = (("turc", "turchia"), ("maroc", "marocco"), ("marric", "marocco"),
               ("ind", "india"), ("sri", "srilanka"), ("colomb", "colombia"),
               ("zimb", "zimbabwe"), ("egiz", "egitto"))

    def _origine(self, pers: Persona, prof):
        cf = re.sub(r"[^A-Za-z0-9]", "", (prof.codice_fiscale if prof else "") or "").upper()
        belfiore = cf[11:15] if len(cf) >= 15 else ""
        citt = (getattr(prof, "cittadinanza", "") or "").strip().lower()
        pers.estera = an.origine_estera(
            proprietario=pers.owner is not None, cittadinanza=citt, belfiore=belfiore,
            straniero_scelto=INQUILINO_STRANIERO_USER_ID in pers.user_ids)
        if pers.estera:
            pers.categoria = self.ZMAP.get(belfiore, "") or next(
                (cat for key, cat in self.CITTMAP if key in citt), "")
        sesso = None
        if len(cf) >= 11 and cf[9:11].isdigit():
            sesso = "F" if int(cf[9:11]) > 40 else "M"
        if sesso is None:
            primo = (pers.nome.split() or [""])[0].lower()
            sesso = "F" if primo.endswith("a") and primo not in {"luca", "andrea"} else "M"
        pers.sesso = sesso

    # ---- generazione del finto per una persona ------------------------------------------
    def _scegli(self, ctx, pool, usati, vietati_sub=True):
        reali = ctx.reali_nomi
        for cand in pool:
            low = cand.lower()
            if low in usati or low in reali:
                continue
            if any((r in low or low in r) for r in reali if len(r) >= 5 and len(low) >= 4):
                continue
            usati.add(low)
            return cand
        return None

    def _genera_finto(self, ctx, pers: Persona, users, owners, tenants):
        scr = ctx.scr
        rng = random.Random(f"{SEED}|{min(pers.user_ids)}")
        cats = list(an.CATEGORIE_ESTERE)
        # inquilino italiano: pool propri (nomi per generazione, cognomi e nascite
        # di tutta Italia), disgiunti da quelli di proprietari, lead e terzi
        inquilino_it = pers.owner is None and pers.tenant is not None and not pers.estera
        nomi_ripiego, cogn_ripiego = an.NOMI_F + an.NOMI_M, an.COGNOMI_IT
        if pers.estera:
            if not pers.categoria:
                pers.categoria = cats[ctx.cat_i % len(cats)]
                ctx.cat_i += 1
            _citt, _z, _citta, nm, nf, cogn_pool = an.CATEGORIE_ESTERE[pers.categoria]
            pool_nomi = list(nf if pers.sesso == "F" else nm)
            pool_cogn = list(cogn_pool)
            rng.shuffle(pool_nomi)
            rng.shuffle(pool_cogn)
        elif inquilino_it:
            anno = an.anno_nascita(pers.tenant.data_nascita, pers.tenant.codice_fiscale)
            pool_nomi = an.pool_nomi_inquilino(pers.sesso, anno, rng)
            pool_cogn = list(an.COGNOMI_INQUILINI)
            rng.shuffle(pool_cogn)
            nomi_ripiego = pool_nomi
            cogn_ripiego = an.COGNOMI_INQUILINI
        else:
            pool_nomi = list(an.NOMI_F if pers.sesso == "F" else an.NOMI_M)
            pool_cogn = list(an.COGNOMI_IT)
            rng.shuffle(pool_nomi)
            rng.shuffle(pool_cogn)
        # nomi
        n_tok = max(1, min(2, len(an.tokens_nome(pers.nome))))
        f_tokens = []
        for _ in range(n_tok):
            c = self._scegli(ctx, pool_nomi, ctx.usati_nomi) or self._scegli(
                ctx, rng.sample(nomi_ripiego, len(nomi_ripiego)),
                ctx.usati_nomi) or f"Nome{len(ctx.usati_nomi)}"
            f_tokens.append(c)
        pers.f_nome = " ".join(f_tokens)
        # cognome (stesso cognome reale -> stesso cognome finto)
        # (un inquilino che ha il cognome vero di un proprietario non ne prende il finto)
        chiave_c = re.sub(r"\W", "", pers.cognome.lower())
        if chiave_c:
            chiave_c = ("inquilino|" if inquilino_it else "") + chiave_c
            if chiave_c not in ctx.cognomi_cache:
                ctx.cognomi_cache[chiave_c] = self._scegli(
                    ctx, pool_cogn, ctx.usati_cognomi) or self._scegli(
                    ctx, rng.sample(cogn_ripiego, len(cogn_ripiego)),
                    ctx.usati_cognomi) or f"Cognome{len(ctx.usati_cognomi)}"
            pers.f_cognome = ctx.cognomi_cache[chiave_c]
        else:
            # nominativo con il solo nome ("Silvia"): un cognome finto lo si da' lo
            # stesso (la home saluta col nome, il resto mostra nome e cognome)
            pers.f_cognome = self._scegli(
                ctx, pool_cogn, ctx.usati_cognomi) or self._scegli(
                ctx, rng.sample(cogn_ripiego, len(cogn_ripiego)),
                ctx.usati_cognomi) or f"Cognome{len(ctx.usati_cognomi)}"
        # nascita
        if pers.estera:
            citt = an.CATEGORIE_ESTERE[pers.categoria]
            pers.comune_nascita = (rng.choice(citt[2]), "EE", citt[1])
        elif inquilino_it:
            pers.comune_nascita = rng.choice(an.COMUNI_NASCITA_INQUILINI)
        else:
            pers.comune_nascita = rng.choice(an.COMUNI_NASCITA)
        pers.shift = rng.choice([-1, 1]) * rng.randrange(20, 400)

        # --- dizionario ------------------------------------------------------------------
        r_nome = an.tokens_nome(pers.nome)
        f_nome_tok = pers.f_nome.split()
        mappa_nome: dict = {}
        for i, t in enumerate(r_nome):
            if an.token_significativo(t):
                f = f_nome_tok[min(i, len(f_nome_tok) - 1)]
                scr.aggiungi_nome(t, f)
                mappa_nome[t.lower()] = f
        if len(r_nome) > 1:
            scr.aggiungi_nome("".join(r_nome), "".join(f_nome_tok))
            scr.aggiungi_nome(" ".join(r_nome), " ".join(f_nome_tok))
        if pers.cognome:
            fc = pers.f_cognome
            scr.aggiungi_nome(pers.cognome, fc)
            scr.aggiungi_nome(re.sub(r"[\s'’.]", "", pers.cognome), fc)
            for t in an.tokens_nome(pers.cognome):
                if an.token_significativo(t):
                    scr.aggiungi_nome(t, fc)
        # nominativo / varianti (refusi) dei profili e degli utenti
        prof = pers.owner or pers.tenant
        stringhe = []
        for u in users:
            if u.pk in pers.user_ids:
                stringhe += [u.first_name, u.last_name]
        if prof:
            stringhe += [prof.nominativo, prof.nome, prof.cognome]
        for s in stringhe:
            for t in an.tokens_nome(s or ""):
                if not an.token_significativo(t) or t.lower() in scr.nomi:
                    continue
                f = self._simile(t, r_nome, f_nome_tok, pers)
                if f:
                    scr.aggiungi_nome(t, f)
        # username / email: alias
        vecchi_username = []
        for u in users:
            if u.pk in pers.user_ids:
                vecchi_username.append(u)
        primo = an.asciiz(f_nome_tok[0]) or "utente"
        cogn_a = an.asciiz(pers.f_cognome)
        principale = next((u for u in vecchi_username if u.pk in owners or u.pk in tenants),
                          vecchi_username[0])
        for u in vecchi_username:
            if u.pk == principale.pk:
                nuovo = primo
                if u.username.startswith("storico_"):
                    nuovo = f"storico_{primo}"
            else:
                nuovo = f"{cogn_a or 'utente'}-{primo}"
            base, k = nuovo, 2
            while nuovo in ctx.usernames:
                nuovo = f"{base}{k}"
                k += 1
            ctx.usernames.add(nuovo)
            u._nuovo_username = nuovo
            scr.aggiungi_nome(u.username, nuovo, sovrascrivi=True)
            for t in re.split(r"[-_.]", u.username):
                if (len(t) >= 4 and t.lower() not in scr.nomi
                        and t.lower() not in ("storico", "admin")):
                    f = self._simile(t, r_nome, f_nome_tok, pers, soglia=0.7)
                    if f:
                        scr.aggiungi_nome(t, f)
            parte_locale = (u.email or "").split("@")[0]
            for t in re.split(r"[-_.+]", parte_locale):
                if (len(t) >= 4 and t.lower() not in scr.nomi
                        and t.lower() not in ("storico", "admin")):
                    f = self._simile(t, r_nome, f_nome_tok, pers, soglia=0.7)
                    if f:
                        scr.aggiungi_nome(t, f)
        pers.username = principale._nuovo_username
        # email finta
        local = f"{primo}.{cogn_a}" if cogn_a else primo
        base, k = local, 2
        while f"{local}@example.com" in ctx.emails:
            local = f"{base}{k}"
            k += 1
        pers.email = f"{local}@example.com"
        ctx.emails.add(pers.email)
        scr.fakes.add(pers.email)
        emails_reali = {(u.email or "").strip().lower() for u in vecchi_username if u.email}
        if prof and getattr(prof, "email_alt", ""):
            emails_reali.add(prof.email_alt.strip().lower())
        for e in emails_reali:
            scr.emails[e] = pers.email
        # telefono
        if prof and prof.telefono:
            pers.telefono = scr.telefono_finto(prof.telefono)
        # i token reali del persona servono a filtrare i pool delle persone successive
        ctx.reali_nomi |= {k for k in scr.nomi if len(k) >= 3}

    def _simile(self, token, r_nome, f_nome_tok, pers, soglia=0.8):
        t = token.lower()
        migliore, punteggio = None, 0.0
        for r in r_nome:
            if not an.token_significativo(r):
                continue
            rl = r.lower()
            sc = 1.0 if (t in rl or rl in t) and min(len(t), len(rl)) >= 4 else \
                difflib.SequenceMatcher(None, t, rl).ratio()
            if sc > punteggio:
                migliore, punteggio = ("n", rl), sc
        for r in an.tokens_nome(pers.cognome):
            if not an.token_significativo(r):
                continue
            rl = r.lower()
            sc = 1.0 if (t in rl or rl in t) and min(len(t), len(rl)) >= 4 else \
                difflib.SequenceMatcher(None, t, rl).ratio()
            if sc > punteggio:
                migliore, punteggio = ("c", rl), sc
        if migliore is None or punteggio < soglia:
            # token di un nominativo che non assomiglia a niente: sta tra i nomi
            if soglia >= 0.8 and pers.f_cognome and token[:1].isupper():
                return pers.f_cognome
            return None
        if migliore[0] == "c":
            return pers.f_cognome
        idx = [x.lower() for x in an.tokens_nome(pers.nome)].index(migliore[1])
        return f_nome_tok[min(idx, len(f_nome_tok) - 1)]

    # ============================================================ testo generico
    def _testo_generico(self, ctx):
        scr = ctx.scr
        totale = 0
        for model in apps.get_models():
            label = model._meta.label
            if label in MODELLI_NO_TESTO:
                continue
            campi = []
            for f in model._meta.concrete_fields:
                t = f.get_internal_type()
                if (label, f.name) in CAMPI_NO_TESTO or f.primary_key or f.choices:
                    continue
                if t in ("CharField", "TextField", "EmailField", "URLField", "JSONField"):
                    campi.append(f)
            if not campi:
                continue
            nomi_campi = [f.name for f in campi]
            da_salvare = []
            for obj in model.objects.all().only("pk", *nomi_campi).iterator():
                cambiato = False
                for f in campi:
                    v = getattr(obj, f.name)
                    if v in (None, "", {}, []):
                        continue
                    importi = (label, f.name) not in CAMPI_SENZA_IMPORTI
                    if f.get_internal_type() == "JSONField":
                        nuovo = scr.scrub_json(v, importi=importi)
                    else:
                        nuovo = self._scrub_campo(label, f.name, v, importi)
                    if nuovo != v:
                        setattr(obj, f.name, nuovo)
                        cambiato = True
                if cambiato:
                    da_salvare.append(obj)
            if da_salvare:
                model.objects.bulk_update(da_salvare, nomi_campi, batch_size=200)
                totale += len(da_salvare)
                self.out(f"   {label}: {len(da_salvare)} righe")
        self.out(f"   totale righe toccate: {totale}")

    def _scrub_campo(self, label, nome_campo, valore, importi):
        scr = self.ctx.scr
        if re.search(r"Contabilit[àa]\.xlsx|\[conti2023|ContiAffittoUtenze", valore):
            # note di importazione dai fogli storici: citano importi e file privati
            return "Importato dall'archivio storico."
        if nome_campo == "note":
            valore = an.nota_neutra(valore)
        testo = scr.scrub(valore, importi=importi)
        if label == "billing.BankTransaction" and nome_campo in ("descrizione", "note"):
            testo = scr.scrub_ordinanti(testo)
        return testo

    # ================================================================== persone
    def _persone(self, ctx):
        User = get_user_model()
        scr = ctx.scr
        OBA = apps.get_model("properties", "OwnerBankAccount")
        utenti = {u.pk: u for u in User.objects.all()}
        da_salvare_u = []
        for pers in ctx.persone:
            for uid in pers.user_ids:
                u = utenti[uid]
                u.username = scr.nomi.get(u.username.lower(), u.username)
                # la home saluta con first_name: senza, ripiega sullo username
                u.first_name = pers.f_nome
                u.last_name = pers.f_cognome
                da_salvare_u.append(u)
        User.objects.bulk_update(da_salvare_u, ["username", "first_name", "last_name"])
        # EmailAddress: la email e' gia' stata sostituita dal passaggio generico

        for pers in ctx.persone:
            for prof in (pers.owner, pers.tenant):
                if prof is None:
                    continue
                # per gli inquilini l'eta' viene dal codice fiscale vero (in memoria):
                # quello nel db e' gia' finto (passaggio generico) e darebbe un anno
                # a caso, incoerente con la generazione del nome scelto
                cf_nascita = (prof.codice_fiscale
                              if prof is pers.tenant and pers.owner is None else None)
                prof = type(prof).objects.get(pk=prof.pk)
                self._anagrafica(ctx, pers, prof, cf_nascita)
        # documenti caricati: niente permesso di soggiorno fra gli inquilini italiani
        TenantDocument = apps.get_model("properties", "TenantDocument")
        italiani = [p.tenant.pk for p in ctx.persone if p.tenant and not p.estera]
        n = TenantDocument.objects.filter(tenant_id__in=italiani,
                                          tipo="permesso_soggiorno").update(tipo="carta_identita")
        self.out(f"   permessi di soggiorno di inquilini italiani -> carta d'identita': {n}")
        # conti bancari: IBAN finti validi, intestatario = proprietario finto
        for a in OBA.objects.select_related("owner"):
            a.iban = scr.iban_finto(a.iban) if a.iban else a.iban
            a.banca = BANCHE_FITTIZIE[a.pk % len(BANCHE_FITTIZIE)]
            pers = next((p for p in ctx.persone if p.owner and p.owner.pk == a.owner_id), None)
            if pers:
                a.intestatario = _norm(f"{pers.f_nome} {pers.f_cognome}")
            a.save(update_fields=["iban", "intestatario", "banca"])

    def _anagrafica(self, ctx, pers: Persona, prof, cf_nascita=None):
        scr = ctx.scr
        rng = random.Random(f"{SEED}|ana|{type(prof).__name__}|{prof.pk}")
        prof.nome = pers.f_nome if prof.nome else prof.nome
        prof.cognome = pers.f_cognome if prof.cognome else prof.cognome
        nomin = _norm(f"{pers.f_nome} {pers.f_cognome}")
        # inquilini: nominativo pulito (nome finto + cognome finto), senza i pezzi
        # corti del vero che il dizionario non tocca ("Jo-")
        if (prof.nominativo and len(prof.nominativo.split()) > 1
                and cf_nascita is None):
            nomin = scr.scrub(prof.nominativo, importi=False)
        prof.nominativo = nomin
        # nascita
        nascita = prof.data_nascita
        if nascita and nascita.year > date.today().year:
            nascita = None  # refuso nei dati originali: si ricava dal codice fiscale
        cf = re.sub(r"[^A-Za-z0-9]", "", cf_nascita or prof.codice_fiscale or "").upper()
        if nascita is None and len(cf) >= 11 and cf[6:8].isdigit() and cf[9:11].isdigit():
            mese = an.MESI_CF.find(cf[8]) + 1
            giorno = int(cf[9:11]) % 40 or 1
            anno = int(cf[6:8])
            anno += 2000 if anno <= 15 else 1900
            try:
                nascita = date(anno, mese or 1, min(giorno, 28))
            except ValueError:
                nascita = None
        if nascita is None and prof.codice_fiscale:
            nascita = date(1985, 1, 1) + timedelta(days=rng.randrange(0, 5500))
        if nascita:
            nascita = nascita + timedelta(days=pers.shift)
            prof.data_nascita = nascita
        com, prov, belf = pers.comune_nascita
        if prof.comune_nascita or prof.codice_fiscale:
            prof.comune_nascita = com
            prof.provincia_nascita = prov if (prof.provincia_nascita or prof.codice_fiscale) else ""
        if prof.cittadinanza or pers.estera:
            prof.cittadinanza = (an.CATEGORIE_ESTERE[pers.categoria][0].capitalize()
                                 if pers.estera else "Italiana")
        if prof.codice_fiscale and nascita:
            prof.codice_fiscale = an.codice_fiscale(
                pers.f_cognome or pers.f_nome, pers.f_nome, nascita, pers.sesso, belf)
            scr.fakes.add(prof.codice_fiscale)
        if prof.telefono:
            prof.telefono = pers.telefono or scr.telefono_finto(prof.telefono)
        # residenza
        via_reale = prof.residenza_via or ""
        if via_reale:
            if any(t in via_reale.lower() for t in
                   {k for k, v in ctx.vie.items() if v in
                    [fp["via_nome"] for fp in ctx.fake_prop.values()]}):
                prof.residenza_via = scr.scrub(via_reale, importi=False)
            else:
                civico = rng.randrange(1, 90)
                prof.residenza_via = f"Via {rng.choice(an.VIE_FINTE)} {civico}"
        if prof.residenza_comune:
            prof.residenza_comune = ctx.luogo_finto(prof.residenza_comune)
            cap = next((c for n, c in an.COMUNI_NO if n == prof.residenza_comune), "")
            if not cap:
                for fp in ctx.fake_prop.values():
                    if fp["comune"] == prof.residenza_comune:
                        cap = fp["cap"]
            if prof.residenza_provincia:
                prof.residenza_provincia = "NO"
            if prof.residenza_cap:
                prof.residenza_cap = cap or "28100"
        if hasattr(prof, "email_alt") and prof.email_alt:
            prof.email_alt = pers.email
        if hasattr(prof, "documento_numero") and prof.documento_numero:
            prof.documento_numero = scr.codice_finto(prof.documento_numero)
        if hasattr(prof, "documento_autorita") and prof.documento_autorita:
            m = re.match(r"(?i)\s*comune di\s+(.+)", prof.documento_autorita)
            prof.documento_autorita = (f"Comune di {ctx.luogo_finto(m.group(1))}" if m
                                       else scr.scrub(prof.documento_autorita, importi=False))
        if hasattr(prof, "documento_tipo"):
            # un italiano non ha il permesso di soggiorno, il passaporto lo da' la Questura
            prof.documento_tipo, prof.documento_autorita = an.documento_coerente(
                prof.documento_tipo, prof.documento_autorita, estera=pers.estera,
                comune=prof.residenza_comune)
        if hasattr(prof, "documento_data_rilascio") and prof.documento_data_rilascio:
            prof.documento_data_rilascio += timedelta(days=rng.randrange(-30, 30))
        prof.save()

    # ================================================================== immobili
    def _immobili(self, ctx):
        scr = ctx.scr
        Property = apps.get_model("properties", "Property")
        Contract = apps.get_model("properties", "Contract")
        DocumentShare = apps.get_model("properties", "DocumentShare")
        for p in Property.objects.order_by("pk"):
            fp = ctx.fake_prop[p.pk]
            p.nome = fp["nome"]
            p.slug = fp["slug"]
            p.comune = fp["comune"]
            p.cap = fp["cap"]
            p.provincia = "NO"
            tp = p.testi_pubblici or {}
            if tp:
                pos = tp.get("posizione") or {}
                pos.update({
                    "mezzi": "Fermata bus a 4 min a piedi (linee per stazione e per il centro). "
                             "Molto ben servita da servizi commerciali (bar, farmacia, supermercato)",
                    "indirizzo": f"Via {fp['via_nome']}, {fp['comune']} (zona parco). "
                                 "200 metri dal parco, 500 dal Castello Visconteo,",
                })
                tp["posizione"] = {k: v for k, v in pos.items()}
                if tp.get("hero_titolo"):
                    # il titolo non deve ripetere l'indirizzo che la pagina mostra sotto
                    tp["hero_titolo"] = fp["nome"]
                p.testi_pubblici = tp
            p.save()
        for c in Contract.objects.all():
            rng = random.Random(f"{SEED}|contratto|{c.pk}")
            if c.numero_registrazione:
                c.numero_registrazione = f"{rng.randrange(1000, 999999):06d}"
            if c.codice_identificativo:
                c.codice_identificativo = scr.codice_finto(c.codice_identificativo)
            c.save()
        for s in DocumentShare.objects.all():
            s.token = hashlib.sha256(f"{SEED}|share|{s.pk}".encode()).hexdigest()[:len(s.token) or 32]
            s.save(update_fields=["token"])

    # ===================================================================== lead
    def _lead(self, ctx):
        Lead = apps.get_model("leads", "Lead")
        scr = ctx.scr
        gruppi: dict = {}
        nomi_gruppi: dict = {}
        reali = ctx.reali_nomi
        prof = ["lavoro nella sanità", "studio all'università", "lavoro nella logistica",
                "lavoro in un'azienda della zona", "faccio un tirocinio", "lavoro nel commercio",
                "lavoro nel settore informatico", "lavoro in un ufficio", "insegno",
                "lavoro nella ristorazione"]
        zone = ["Novara", "Novara centro", "Galliate", "Trecate", "Oleggio", "Cameri"]
        n = 0
        for lead in Lead.objects.select_related("property").order_by("pk"):
            rng = random.Random(f"{SEED}|lead|{lead.pk}")
            slug = ctx.fake_prop.get(lead.property_id, {}).get("slug", "casa")
            nome, cognome, _origine = an.genera_nome_lead(rng, reali)
            autore = f"{nome} {cognome}"
            uid = str(100000000000000 + int(hashlib.sha256(f"{SEED}u{lead.pk}".encode())
                                              .hexdigest()[:10], 16) % 899999999999999)
            pid = str(3000000000000000 + int(hashlib.sha256(f"{SEED}p{lead.pk}".encode())
                                               .hexdigest()[:10], 16) % 999999999999999)

            def gruppo(v):
                if not v:
                    return v
                if v not in gruppi:
                    if re.fullmatch(r"\d+", v) or v.startswith("__"):
                        gruppi[v] = str(1000000000000000 + int(hashlib.sha256(
                            f"{SEED}g{v}".encode()).hexdigest()[:12], 16) % 899999999999999)
                    else:
                        gruppi[v] = f"AFFITTI.NOVARA.ZONA{len(gruppi) + 1}"
                return gruppi[v]

            def etichetta(v):
                """Nome finto del gruppo, stabile per id (il bot spesso non lo conosce)."""
                chiave = v or "__senza_id__"
                if chiave not in nomi_gruppi:
                    nomi_gruppi[chiave] = an.nome_gruppo_finto(len(nomi_gruppi))
                return nomi_gruppi[chiave]
            con_riga_autore = bool(lead.author_name) and lead.testo.startswith(
                lead.author_name + "\n")
            gid = gruppo(lead.group_id)
            gid_url = gid or gruppo("__predefinito__")
            if lead.group_id or lead.group_label:
                # sempre un nome: senza, le statistiche mostrerebbero "gruppo <id>"
                lead.group_label = etichetta(lead.group_id or lead.group_label)
            lead.group_id = gid
            if lead.post_id:
                lead.post_id = pid
            if lead.author_name:
                lead.author_name = autore
            if lead.author_url:
                lead.author_url = f"https://www.facebook.com/groups/{gid_url}/user/{uid}/"
            if lead.permalink:
                lead.permalink = f"https://www.facebook.com/groups/{gid_url}/posts/{pid}/"
            if lead.link_messenger:
                lead.link_messenger = f"https://m.me/{uid}"
            if lead.contatto:
                lead.contatto = (autore if re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}", lead.contatto)
                                 and "@" not in lead.contatto else scr.scrub(lead.contatto, importi=False))
            budget = rng.choice([300, 350, 400, 450, 500])
            zona = rng.choice(zone)
            mestiere = rng.choice(prof)
            eta = rng.randrange(21, 42)
            durata = rng.choice(["6 mesi", "un anno", "lungo periodo"])
            if lead.testo:
                corpo = rng.choice(TEMPLATI_POST).format(
                    nome=nome, eta=eta, mestiere=mestiere, zona=zona, budget=budget,
                    durata=durata)
                lead.testo = f"{autore}\n{corpo}" if con_riga_autore else corpo
            if isinstance(lead.analisi, dict) and lead.analisi:
                a = dict(lead.analisi)
                if a.get("zona"):
                    a["zona"] = f"{zona} e dintorni"
                if "motivo" in a and a["motivo"]:
                    a["motivo"] = (f"Cerca stanza a {zona}; compatibile con le "
                                   f"stanze libere. Contratto {durata}.")
                if a.get("budget_max"):
                    a["budget_max"] = budget
                lead.analisi = scr.scrub_json(a, importi=False)
            if lead.commento_proposto:
                lead.commento_proposto = (
                    f"Ciao {nome}, ti ho scritto in privato: trovi le foto della casa qui "
                    f"https://viapal.example.com/g/{slug}")
            if lead.privato_proposto:
                lead.privato_proposto = (
                    f"Ciao {nome}, ho visto il tuo post: abbiamo delle stanze singole libere "
                    f"in un appartamento di 180 mq a Novara, in via dei Tigli, a 200 metri dal "
                    f"parco. Le stanze sono ampie e luminose; i due bagni sono condivisi fra "
                    f"tutti. Foto e prezzi li trovi qui: https://viapal.example.com/g/{slug}")
            if lead.note:
                lead.note = rng.choice(NOTE_LEAD)
            lead.foto = ""  # ritaglio del profilo: e' il volto di una persona reale
            lead.save()
            n += 1
        self.out(f"   lead riscritti: {n}")

    # ================================================================== bollette
    def _bollette(self, ctx):
        """Numeri e nomi file delle bollette in un formato da fattura vera.

        I numeri originali sono nomi di file importati ("utenze-mz-gas-...") e
        tradiscono luogo e provenienza; la descrizione della spesa collegata
        (che li cita) viene riscritta con la stessa funzione dell'app.
        """
        from billing.signals import _descrizione_expense_da_bolletta
        UtilityBill = apps.get_model("billing", "UtilityBill")
        Expense = apps.get_model("billing", "Expense")
        usati: set = set()
        mappa: dict = {}
        n = 0
        for b in UtilityBill.objects.select_related("supplier").order_by("pk"):
            num = an.numero_bolletta_finto(SEED, b.pk, b.periodo_da)
            k = 0
            while num in usati:
                k += 1
                num = an.numero_bolletta_finto(SEED, f"{b.pk}-{k}", b.periodo_da)
            usati.add(num)
            vecchio_numero = b.numero_fattura
            b.numero_fattura = num
            campi = {"numero_fattura": num}
            if re.match(r"tipo=\w+,\s*file=", b.note or ""):
                campi["note"] = ""   # residuo dell'import: cita il nome del file originale
            mappa[vecchio_numero] = num
            if b.file_pdf:
                slug = ctx.fake_prop.get(b.immobile_id, {}).get("slug", "casa")
                nome = (f"bollette/{slug}/{b.periodo_da:%Y}/{b.periodo_da:%m}/"
                        f"{b.prodotto}-{num}.pdf")
                campi["file_pdf"] = nome
            # update(): niente signal (non si risincronizza la spesa)
            UtilityBill.objects.filter(pk=b.pk).update(**campi)
            if b.expense_id:
                Expense.objects.filter(pk=b.expense_id).update(
                    descrizione=_descrizione_expense_da_bolletta(b))
            n += 1
        # spese che citano il numero senza essere collegate alla bolletta (duplicati d'import)
        orfane = 0
        for e in Expense.objects.filter(descrizione__contains=" n. "):
            nuova = e.descrizione
            for vecchio, num in mappa.items():
                nuova = nuova.replace(f"n. {vecchio} ", f"n. {num} ")
            if nuova != e.descrizione:
                Expense.objects.filter(pk=e.pk).update(descrizione=nuova)
                orfane += 1
        self.out(f"   bollette rinumerate: {n} (spese non collegate riscritte: {orfane})")

    # ============================================= contabilita' fra proprietari
    def _contabilita_proprietari(self):
        """Le note libere dei proprietari raccontano fatti privati: etichette neutre."""
        InterOwnerEntry = apps.get_model("accounting", "InterOwnerEntry")
        voci = list(InterOwnerEntry.objects.all())
        for e in voci:
            e.descrizione = an.descrizione_fra_proprietari(
                e.importo, e.data, spesa=bool(e.riferimento_expense_id),
                prestito=bool(e.riferimento_loan_id),
                regolazione=bool(e.riferimento_settlement_id),
                bonifico=bool(e.bank_transaction_id))
            e.note = ""
        InterOwnerEntry.objects.bulk_update(voci, ["descrizione", "note"])
        altri = 0
        for label in ("accounting.InterOwnerLoan", "accounting.OwnerLedgerEntry",
                      "accounting.OwnerSettlement", "accounting.WithholdingRule"):
            model = apps.get_model(label)
            campi = [f.name for f in model._meta.concrete_fields
                     if f.name in ("descrizione", "note")]
            oggetti = list(model.objects.all())
            for o in oggetti:
                for nome in campi:
                    v = getattr(o, nome)
                    setattr(o, nome, "" if nome == "note" else an.nota_neutra(v, massimo=60))
            if oggetti and campi:
                model.objects.bulk_update(oggetti, campi)
            altri += len(oggetti)
        self.out(f"   movimenti fra proprietari: {len(voci)} riscritti (+{altri} altri registri)")

    # ================================================================== importi
    def _importi(self):
        from billing.models import (
            BankTransaction,
            BankTransactionAllocation,
            Receivable,
        )
        InterOwnerEntry = apps.get_model("accounting", "InterOwnerEntry")
        TenantProfile = apps.get_model("properties", "TenantProfile")
        RoomAssignment = apps.get_model("properties", "RoomAssignment")

        allocs = {a.pk: (a.bank_transaction_id, a.receivable_id, a.importo)
                  for a in BankTransactionAllocation.objects.all()}
        bts = {b.pk: b.importo for b in BankTransaction.objects.all()}
        recs0 = {r.pk: (r.importo_dovuto, r.importo_pagato) for r in Receivable.objects.all()}
        rip = an.ripara_importi(allocs, bts, recs0)

        # --- scrittura (bulk_update: nessun signal) ---
        oggetti = list(BankTransactionAllocation.objects.all())
        for a in oggetti:
            a.importo = rip.allocazioni[a.pk]
        BankTransactionAllocation.objects.bulk_update(oggetti, ["importo"], batch_size=500)
        oggetti = list(BankTransaction.objects.all())
        for b in oggetti:
            b.importo = rip.movimenti[b.pk]
        BankTransaction.objects.bulk_update(oggetti, ["importo"], batch_size=500)
        recs = list(Receivable.objects.all())
        for r in recs:
            r.importo_dovuto = rip.addebiti_dovuto[r.pk]
            r.importo_pagato = rip.addebiti_pagato[r.pk]
        Receivable.objects.bulk_update(recs, ["importo_dovuto", "importo_pagato"], batch_size=500)
        self.out(f"   allocazioni {len(allocs)}, movimenti {len(bts)}, addebiti {len(recs0)}")

        gestiti = {
            ("billing.BankTransaction", "importo"), ("billing.BankTransactionAllocation", "importo"),
            ("billing.Receivable", "importo_dovuto"), ("billing.Receivable", "importo_pagato"),
            ("accounting.InterOwnerEntry", "importo"),
            ("properties.TenantProfile", "deposito_versato"),
            ("properties.TenantProfile", "deposito_da_restituire"),
            ("properties.RoomAssignment", "costo_cessione"),
        }

        # --- movimenti fra proprietari legati a un bonifico: stesso importo del bonifico ---
        entries = list(InterOwnerEntry.objects.all())
        for e in entries:
            if e.bank_transaction_id and abs(e.importo) == abs(bts[e.bank_transaction_id]):
                e.importo = an._segno(e.importo) * abs(rip.movimenti[e.bank_transaction_id])
            else:
                e.importo = an.scala(e.importo)
        InterOwnerEntry.objects.bulk_update(entries, ["importo"])

        # --- deposito: versato = somma dei Receivable di versamento, se prima lo era ---
        dep = Receivable.objects.filter(causale="deposito")
        pos0, pos1, neg0, neg1 = {}, {}, {}, {}
        for r in dep:
            t = r.assignment.tenant_id
            old = recs0[r.pk][0]
            if old > 0:
                pos0[t] = pos0.get(t, Decimal(0)) + old
                pos1[t] = pos1.get(t, Decimal(0)) + r.importo_dovuto
            elif old < 0:
                neg0[t] = neg0.get(t, Decimal(0)) + old
                neg1[t] = neg1.get(t, Decimal(0)) + r.importo_dovuto
        profili = list(TenantProfile.objects.all())
        for t in profili:
            dv0, dr0 = t.deposito_versato, t.deposito_da_restituire
            if dv0 is not None and t.pk in pos0 and dv0 == pos0[t.pk]:
                t.deposito_versato = pos1[t.pk]
            else:
                t.deposito_versato = an.scala(dv0)
            if dr0 is None:
                t.deposito_da_restituire = None
            elif dv0 is not None and dr0 == dv0:
                t.deposito_da_restituire = t.deposito_versato
            elif t.pk in neg0 and dr0 == -neg0[t.pk]:
                t.deposito_da_restituire = -neg1[t.pk]
            else:
                t.deposito_da_restituire = an.scala(dr0)
        TenantProfile.objects.bulk_update(profili, ["deposito_versato", "deposito_da_restituire"])

        # --- costo cessione: totale = 2 x quota inquilino, se prima lo era ---
        reg = {}
        for r in Receivable.objects.filter(causale="registrazione"):
            reg.setdefault(r.assignment_id, []).append((recs0[r.pk][0], r.importo_dovuto))
        ass = list(RoomAssignment.objects.all())
        for a in ass:
            if a.costo_cessione is None:
                continue
            nuovo = an.scala(a.costo_cessione)
            for old, new in reg.get(a.pk, []):
                if old * 2 == a.costo_cessione:
                    nuovo = new * 2
            a.costo_cessione = nuovo
        RoomAssignment.objects.bulk_update(ass, ["costo_cessione"])

        # --- tutti gli altri DecimalField ---
        self.scalati = []
        for model in apps.get_models():
            for f in model._meta.concrete_fields:
                if f.get_internal_type() != "DecimalField":
                    continue
                chiave = (model._meta.label, f.name)
                if chiave in ESCLUSI_DECIMALI:
                    continue
                self.scalati.append(chiave)
                if chiave in gestiti:
                    continue
                oggetti = list(model.objects.exclude(**{f.name: None}))
                for o in oggetti:
                    setattr(o, f.name, an.scala(getattr(o, f.name)))
                model.objects.bulk_update(oggetti, [f.name], batch_size=500)
        # JSON con importi (snapshot dei settlement)
        OwnerSettlement = apps.get_model("accounting", "OwnerSettlement")
        n_snap = OwnerSettlement.objects.exclude(snapshot={}).count()
        if n_snap:
            self.stdout.write(self.style.WARNING(
                f"   ATTENZIONE: {n_snap} OwnerSettlement con snapshot JSON non scalato"))
        self.out(f"   campi scalati: {len(self.scalati)}")

    # ================================================================== pulizia
    def _pulizia(self):
        for label in DA_CANCELLARE:
            model = apps.get_model(label)
            n = model.objects.count()
            model.objects.all().delete()
            self.out(f"   {label}: {n} righe cancellate")

    # ==================================================================== file
    def _file(self, ctx):
        scr = ctx.scr
        daf = []
        for model in apps.get_models():
            label = model._meta.label
            for f in model._meta.concrete_fields:
                if f.get_internal_type() not in ("FileField", "ImageField"):
                    continue
                if (label, f.name) in CAMPI_FOTO:
                    continue
                for obj in model.objects.exclude(**{f.name: ""}).exclude(**{f.name + "__isnull": True}):
                    nome = getattr(obj, f.name).name
                    nuovo = scr.scrub_percorso(nome)
                    if nuovo != nome:
                        model.objects.filter(pk=obj.pk).update(**{f.name: nuovo})
                        setattr(obj, f.name, nuovo)
                    daf.append((obj, f, nuovo))
        self.out(f"   file da generare: {len(daf)}")
        if self.dry:
            self.out("   (dry-run: nessun file scritto)")
            return
        scritti = 0
        for obj, f, nome in daf:
            titolo, righe = self._contenuto_segnaposto(obj, f)
            percorso = f.storage.path(nome)
            radice = os.path.realpath(f.storage.location)
            if not os.path.realpath(percorso).startswith(radice) or "demo" not in radice:
                raise CommandError(f"Percorso fuori dalle cartelle demo: {percorso}")
            os.makedirs(os.path.dirname(percorso), exist_ok=True)
            ext = os.path.splitext(nome)[1].lower()
            with open(percorso, "wb") as fh:
                if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                    fh.write(immagine_segnaposto(titolo, righe, ext))
                elif ext in (".xml", ".txt", ".csv"):
                    fh.write(an.ascii_sicuro("Documento di esempio - dati fittizi\n" + titolo + "\n"
                                             + "\n".join(righe)).encode())
                else:
                    fh.write(pdf_segnaposto(titolo, righe))
            scritti += 1
        self.out(f"   file scritti: {scritti}")

    def _contenuto_segnaposto(self, obj, campo):
        label = obj._meta.label
        righe = []
        titolo = obj._meta.verbose_name.capitalize()
        if label == "properties.TenantDocument":
            titolo = obj.get_tipo_display()
            righe = [f"Intestatario: {obj.tenant.nominativo}"]
            if obj.descrizione:
                righe.append(obj.descrizione)
        elif label == "properties.PropertyDocument":
            titolo = obj.get_tipo_display()
            righe = [f"Immobile: {obj.property.nome}"]
            if obj.descrizione:
                righe.append(obj.descrizione)
        elif label == "billing.UtilityBill":
            titolo = f"Bolletta {obj.get_prodotto_display()}"
            righe = [f"Fornitore: {obj.supplier.nome}",
                     f"Periodo: {obj.periodo_da:%d/%m/%Y} - {obj.periodo_a:%d/%m/%Y}",
                     f"Importo totale: {obj.importo_totale:.2f} EUR"]
            if obj.numero_fattura:
                righe.append(f"Fattura n. {obj.numero_fattura}")
        elif label == "billing.Expense":
            titolo = "Allegato di spesa"
            righe = [obj.descrizione, f"Importo: {obj.importo:.2f} EUR"]
        elif label == "billing.Receivable":
            titolo = "Ricevuta di pagamento"
            righe = [obj.descrizione or obj.get_causale_display(),
                     f"Importo: {obj.importo_dovuto:.2f} EUR"]
        return titolo, righe

    # ================================================================ password
    def _password(self):
        User = get_user_model()
        h = make_password(PASSWORD_DEMO)
        n = User.objects.update(password=h)
        self.out(f"   password impostata su {n} utenti")

    # ================================================================= metriche
    def _metriche(self) -> dict:
        from billing.models import BankTransaction, Receivable
        m = {"righe": {}, "somme": {}, "stati": Counter()}
        for model in apps.get_models():
            if model._meta.label in DA_CANCELLARE:
                continue
            m["righe"][model._meta.label] = model.objects.count()
        for model in apps.get_models():
            for f in model._meta.concrete_fields:
                if f.get_internal_type() == "DecimalField":
                    k = (model._meta.label, f.name)
                    m["somme"][k] = (model.objects.aggregate(s=Sum(f.name))["s"] or Decimal(0),
                                     model.objects.exclude(**{f.name: None}).count())
        for r in Receivable.objects.all():
            m["stati"]["receivable " + r.stato] += 1
            tot = r.allocations.aggregate(s=Sum("importo"))["s"]
            if tot is not None and r.allocations.exists():
                saldato = abs(tot) + an.SOGLIA_RECEIVABLE >= abs(r.importo_dovuto) and tot != 0
                m["stati"]["receivable con allocazioni: saldato per regola" if saldato
                           else "receivable con allocazioni: aperto per regola"] += 1
        for b in BankTransaction.objects.all():
            m["stati"]["movimento " + b.stato_riconciliazione] += 1
        return m

    def _confronta(self, prima: dict, dopo: dict):
        errori = []
        self.out("   Conteggi (prima -> dopo):")
        for k in sorted(set(prima["stati"]) | set(dopo["stati"])):
            a, d = prima["stati"][k], dopo["stati"][k]
            marca = "" if a == d else "  <-- DIVERSO"
            self.out(f"     {k:55} {a:5} -> {d:5}{marca}")
            if a != d:
                errori.append(f"conteggio '{k}' cambiato: {a} -> {d}")
        for k in prima["righe"]:
            if prima["righe"][k] != dopo["righe"].get(k):
                errori.append(f"righe di {k}: {prima['righe'][k]} -> {dopo['righe'].get(k)}")
        self.out("   Somme per campo (prima -> dopo, rapporto):")
        for k in sorted(prima["somme"]):
            s0, n0 = prima["somme"][k]
            s1, _n1 = dopo["somme"][k]
            if k in ESCLUSI_DECIMALI:
                self.out(f"     {k[0]}.{k[1]:24} {s0:>12} -> {s1:>12}  (escluso)")
                if s0 != s1:
                    errori.append(f"{k} escluso ma cambiato")
                continue
            rapporto = (s1 / s0) if s0 else Decimal(0)
            fuori = abs(s1 - s0 * an.FATTORE) > max(Decimal("0.50"), Decimal(n0) * Decimal("0.03"))
            self.out(f"     {k[0]}.{k[1]:24} {s0:>12} -> {s1:>12}  x{rapporto:.4f}"
                     + ("  <-- FUORI TOLLERANZA" if fuori else ""))
            if fuori:
                errori.append(f"somma {k}: {s0} -> {s1}")
        if errori:
            raise CommandError("Confronto prima/dopo fallito:\n  " + "\n  ".join(errori))
        self.out(self.style.SUCCESS("   Conteggi identici, somme ~ 0,7x: OK"))
        self.out("\n   Campi scalati: " + ", ".join(f"{a}.{b}" for a, b in sorted(self.scalati)))
        self.out("   DecimalField esclusi:")
        for (a, b), motivo in ESCLUSI_DECIMALI.items():
            self.out(f"     {a}.{b}: {motivo}")

    # ================================================================= verifica
    def _verifica(self, ctx):
        scr = ctx.scr
        with connection.cursor() as c:
            c.execute("""SELECT table_name, column_name, data_type
                         FROM information_schema.columns
                         WHERE table_schema='public'
                           AND data_type IN ('character varying','text','json','jsonb','character')
                         ORDER BY 1,2""")
            colonne = [(t, col, dt) for t, col, dt in c.fetchall()
                       if t not in TABELLE_NO_SCAN and (t, col) not in COLONNE_NO_SCAN]

            def esc(k):
                return re.sub(r"([^A-Za-z0-9\s])", r"\\\1", k)

            toks = sorted(ctx.verifica_tokens, key=len, reverse=True)
            alt = "|".join(esc(k) for k in toks)
            rx_parola = f"(?<![[:alnum:]])({alt})(?![[:alnum:]])"
            lunghi = [k for k in toks if len(k) >= 8]
            medi = [k for k in toks if 5 <= len(k) < 8]
            rx_medi = "(" + "|".join(esc(k) for k in medi) + ")" if medi else None
            avvisi = []
            rx_sottost = "(" + "|".join(esc(k) for k in lunghi) + ")"
            valori = [v for v in ctx.valori_reali if not v.startswith("tel:") and len(v) >= 5]
            rx_valori = "(" + "|".join(esc(v) for v in valori) + ")" if valori else None
            tel_reali = {v[4:] for v in ctx.valori_reali if v.startswith("tel:")}
            residui = []
            for t, col, dt in colonne:
                cast = f'"{col}"::text'
                for nome_rx, rx in (("parola", rx_parola), ("sottostringa", rx_sottost),
                                    ("valore", rx_valori)):
                    if rx is None:
                        continue
                    c.execute(f'SELECT count(*), min((regexp_match({cast}, %s, \'i\'))[1]), '
                              f'min(left({cast}, 90)) FROM "{t}" WHERE {cast} ~* %s', [rx, rx])
                    n, tok, es = c.fetchone()
                    if n:
                        residui.append((t, col, nome_rx, n, f"[{tok}] {es}"))
                c.execute(f'SELECT count(*), min(left({cast}, 90)) FROM "{t}" '
                          f'WHERE {cast} ~* %s', [an.RE_PRIVATI_SQL])
                n, es = c.fetchone()
                if n:
                    residui.append((t, col, "privato", n, es))
                if rx_medi:
                    c.execute(f'SELECT count(*), min((regexp_match({cast}, %s, \'i\'))[1]), '
                              f'min(left({cast}, 90)) FROM "{t}" WHERE {cast} ~* %s',
                              [rx_medi, rx_medi])
                    n, tok, es = c.fetchone()
                    if n:
                        avvisi.append((t, col, n, f"[{tok}] {es}"))
                # pattern generici: email / IBAN / CF / telefono non finti
                for nome_rx, rx, ok in (
                    ("email", RE_EMAIL_SQL, lambda m: m.lower().endswith(an.DOMINI_AMMESSI)
                     or m.lower() in scr.fakes),
                    ("iban", RE_IBAN_SQL, lambda m: re.sub(r"\s", "", m).upper() in scr.fakes),
                    ("piva", RE_PIVA_SQL, lambda m: m in scr.fakes),
                    ("cf", RE_CF_SQL, lambda m: m.upper() in scr.fakes),
                    ("tel", RE_TEL_SQL, lambda m: an.normalizza_telefono(m) in scr.fakes
                     or len(an.normalizza_telefono(m)) not in (9, 10)),
                ):
                    c.execute(f'SELECT m[1] FROM "{t}", regexp_matches({cast}, %s, \'gi\') AS m '
                              f"WHERE {cast} ~* %s LIMIT 200", [rx, rx])
                    trovati = [r[0] for r in c.fetchall()]
                    if nome_rx == "tel":
                        trovati = [f"{x} (reale={an.normalizza_telefono(x) in tel_reali}, "
                                   f"fake={an.normalizza_telefono(x) in scr.fakes})"
                                   for x in trovati
                                   if an.normalizza_telefono(x) in tel_reali or not ok(x)]
                    else:
                        trovati = [x for x in trovati if not ok(x)]
                    if trovati:
                        c.execute(f'SELECT left({cast}, 200) FROM "{t}" WHERE {cast} ~* %s LIMIT 1',
                                  [rx])
                        residui.append((t, col, nome_rx, len(trovati),
                                        f"{trovati[0]} :: {c.fetchone()[0]}"))
        self.out(f"   colonne scandite: {len(colonne)}")
        if avvisi:
            self.out(f"   AVVISI (token di 5-7 lettere dentro altre parole, da guardare a occhio): "
                     f"{len(avvisi)}")
            for t, col, n, es in avvisi:
                self.out(f"     {t}.{col} x{n}: {es!r}")
        if residui:
            self.stdout.write(self.style.ERROR(f"   RESIDUI: {len(residui)}"))
            for t, col, tipo, n, es in residui:
                self.out(f"     {t}.{col} [{tipo}] x{n}: {es!r}")
            if not self.opts["ignora_residui"]:
                raise CommandError("Verifica fallita: dati reali residui (vedi sopra).")
        else:
            self.out(self.style.SUCCESS("   Residui: 0"))

    def _campioni(self, percorso):
        """Parole sconosciute (ne' italiane ne' inglesi) rimaste nei testi, con un contesto."""
        def carica(p):
            try:
                return {w.strip().lower() for w in open(p, encoding="utf-8", errors="ignore")}
            except OSError:
                return set()
        noti = carica("/usr/share/dict/italian") | carica("/usr/share/dict/american-english")
        trovate: dict = {}
        with connection.cursor() as c:
            c.execute("""SELECT table_name, column_name FROM information_schema.columns
                         WHERE table_schema='public'
                           AND data_type IN ('character varying','text','jsonb')
                           AND table_name ~ '^(billing|properties|accounting|notifications|leads|auth_user|account_)'
                         ORDER BY 1,2""")
            for t, col in c.fetchall():
                if (t, col) in COLONNE_NO_SCAN:
                    continue
                c2 = connection.cursor()
                c2.execute(f'SELECT "{col}"::text FROM "{t}" WHERE "{col}" IS NOT NULL')
                for (v,) in c2.fetchall():
                    for w in re.findall(r"[A-Za-zÀ-ÿ']{4,}", v):
                        k = w.lower()
                        if k in noti or k.rstrip("s") in noti:
                            continue
                        trovate.setdefault(k, [0, f"{t}.{col}", v[:90].replace("\n", " ")])
                        trovate[k][0] += 1
        with open(percorso, "w", encoding="utf-8") as fh:
            for k in sorted(trovate):
                n, dove, es = trovate[k]
                fh.write(f"{k}\t{n}\t{dove}\t{es}\n")
        self.out(f"   campioni: {len(trovate)} parole in {percorso}")
        colonne = [("billing_banktransaction", "descrizione"), ("billing_banktransaction", "note"),
                   ("billing_expense", "descrizione"), ("billing_expense", "note"),
                   ("billing_receivable", "descrizione"), ("billing_receivable", "note"),
                   ("properties_roomassignment", "note"), ("properties_contract", "note"),
                   ("properties_contract", "nome"), ("properties_tenantprofile", "note_pagamento"),
                   ("properties_ownerprofile", "note"), ("accounting_interownerentry", "descrizione"),
                   ("leads_lead", "note"), ("billing_utilitybill", "note"),
                   ("billing_supplier", "nome"), ("billing_supplier", "contatto")]
        with open(percorso + ".testi", "w", encoding="utf-8") as fh, connection.cursor() as c:
            for t, cols in (
                ("auth_user", "id, username, first_name, last_name, email, is_superuser"),
                ("account_emailaddress", "user_id, email, verified"),
                ("properties_ownerprofile", "nominativo, nome, cognome, data_nascita, comune_nascita, provincia_nascita, cittadinanza, residenza_via, residenza_comune, residenza_provincia, residenza_cap, codice_fiscale, telefono"),
                ("properties_tenantprofile", "nominativo, nome, cognome, data_nascita, comune_nascita, provincia_nascita, cittadinanza, residenza_via, residenza_comune, residenza_cap, codice_fiscale, telefono, email_alt, documento_numero, documento_autorita"),
                ("properties_ownerbankaccount", "banca, intestatario, iban"),
                ("properties_property", "nome, indirizzo, via, civico, cap, comune, provincia, slug, testi_pubblici"),
                ("properties_contract", "nome, ufficio_registrazione, numero_registrazione, serie_registrazione, codice_identificativo"),
                ("properties_tenantdocument", "file, descrizione"),
                ("properties_propertydocument", "file, descrizione"),
                ("billing_expense", "allegato"),
                ("properties_documentshare", "token, destinatario"),
                ("leads_lead", "post_id, author_name, author_url, permalink, group_id, group_label, contatto, left(testo, 300), analisi, commento_proposto"),
            ):
                c.execute(f"SELECT {cols} FROM {t} ORDER BY 1 LIMIT 40")
                fh.write(f"\n##### {t}\n")
                for riga in c.fetchall():
                    fh.write(" | ".join(str(x).replace("\n", " / ")[:300] for x in riga) + "\n")
            for t, col in colonne:
                c.execute(f'SELECT DISTINCT "{col}" FROM "{t}" WHERE "{col}" <> \'\' ORDER BY 1')
                fh.write(f"\n=== {t}.{col}\n")
                for (v,) in c.fetchall():
                    fh.write(v.replace("\n", " | ")[:260] + "\n")

    # ================================================================== report
    def _report_utenti(self, ctx):
        User = get_user_model()
        Property = apps.get_model("properties", "Property")
        nomi_prop = {p.pk: p.nome for p in Property.objects.all()}
        self.out("\nUtenti demo (password: " + PASSWORD_DEMO + "):")
        self.out(f"  {'username':28} {'ruolo':45}")
        for u in User.objects.order_by("pk"):
            pers = next((p for p in ctx.persone if u.pk in p.user_ids), None)
            ruoli = []
            if u.is_superuser:
                ruoli.append("superuser")
            if pers:
                for r, pid in sorted(set(pers.ruoli)):
                    ruoli.append(f"{r} ({nomi_prop.get(pid, pid)})")
                if pers.tenant and not pers.owner:
                    ruoli.append("inquilino")
            if not ruoli:
                ruoli.append("sistema / tecnico")
            self.out(f"  {u.username:28} {', '.join(ruoli)}")
        if ctx.persone:
            prinsipale = max(
                (p for p in ctx.persone if p.owner),
                key=lambda p: (sum(1 for r, _ in p.ruoli if r == "proprietario"), len(p.ruoli)),
                default=None)
            if prinsipale:
                self.out(f"\nProprietario principale: {prinsipale.username}")


RE_EMAIL_SQL = r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
RE_IBAN_SQL = r"(?<![A-Za-z0-9])(IT[0-9]{2}(?: ?[A-Za-z0-9]){23})(?![A-Za-z0-9])"
RE_PIVA_SQL = r"(?<![A-Za-z0-9])(IT[0-9]{11})(?![A-Za-z0-9])"
RE_CF_SQL = r"(?<![A-Za-z0-9])([A-Z]{6}[0-9]{2}[A-EHLMPR-T][0-9]{2}[A-Z][0-9]{3}[A-Z])(?![A-Za-z0-9])"
RE_TEL_SQL = r"(?<![A-Za-z0-9+])((?:(?:\+|00)?39[ ./-]?)?3[0-9]{2}[ ./-]?[0-9]{3}[ ./-]?[0-9]{3,4})(?![0-9])"

NOTE_LEAD = [
    "Scritto su Messenger", "Inviato messaggio privato", "Cerca solo per qualche mese",
    "Vuole vedere la stanza il fine settimana", "Budget un po' basso", "Studente fuori sede",
    "Richiamare la prossima settimana", "Ha chiesto se sono ammessi animali",
    "Interessato, aspetto risposta", "Cerca vicino alla stazione",
]

TEMPLATI_POST = [
    "Buongiorno a tutti, sono {nome}, {eta} anni, {mestiere}. Cerco una stanza singola a "
    "{zona} o nei dintorni, per {durata}. Budget massimo {budget} euro al mese spese incluse. "
    "Non fumo e non ho animali. Scrivetemi in privato, grazie!",
    "Ciao a tutti! Mi chiamo {nome} e {mestiere} a {zona}. Sto cercando una stanza "
    "in appartamento condiviso, disponibile subito, contratto regolare. Posso arrivare a "
    "{budget} euro. Persona tranquilla e ordinata.",
    "Salve, cerco una sistemazione a {zona} o vicino. Ho {eta} anni, {mestiere}, posso fornire referenze. "
    "Mi serve una stanza per {durata}. Budget {budget} euro mensili. Grazie a chi mi contatterà.",
    "Buonasera, sono {nome}. Cerco camera in affitto a {zona}, preferibilmente vicino ai mezzi. "
    "{mestiere}, con contratto stabile. Disponibile a visionare la stanza in qualsiasi "
    "momento.",
    "Cerco stanza singola a {zona} per {durata}. {eta} anni, {mestiere}, non fumatore. "
    "Massimo {budget} euro al mese. Messaggi in privato.",
    "Ciao, mi presento: {nome}, {eta} anni, {mestiere}. Mi trasferisco a {zona} e cerco una "
    "camera in un appartamento con altre persone. Budget fino a {budget} euro. Grazie!",
]


# ---------------------------------------------------------------------------
# Segnaposto
# ---------------------------------------------------------------------------


def pdf_segnaposto(titolo: str, righe: list) -> bytes:
    from html import escape

    from weasyprint import HTML
    titolo = an.ascii_sicuro(titolo)
    corpo = "".join(f"<p>{escape(an.ascii_sicuro(r))}</p>" for r in righe if r)
    html = f"""<html><head><meta charset='utf-8'><style>
      @page {{ size: A4; margin: 2.5cm }}
      body {{ font-family: sans-serif; color: #222 }}
      h1 {{ font-size: 20pt; margin-bottom: 4pt }}
      .avviso {{ border: 1px dashed #888; padding: 10pt; color: #666; margin: 14pt 0 }}
    </style></head><body>
      <h1>Documento di esempio - dati fittizi</h1>
      <div class='avviso'>Ambiente demo: nessun dato reale in questo file.</div>
      <h2>{escape(titolo)}</h2>{corpo}
    </body></html>"""
    return HTML(string=html).write_pdf()


def immagine_segnaposto(titolo: str, righe: list, ext: str) -> bytes:
    import io

    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (900, 560), (238, 240, 244))
    d = ImageDraw.Draw(img)
    try:
        grande, medio = ImageFont.load_default(size=34), ImageFont.load_default(size=24)
    except TypeError:
        grande = medio = ImageFont.load_default()
    d.rectangle([20, 20, 880, 540], outline=(150, 155, 165), width=3)
    d.text((50, 60), "Documento di esempio - dati fittizi", fill=(40, 40, 50), font=grande)
    d.text((50, 130), an.ascii_puro(titolo), fill=(60, 60, 70), font=medio)
    y = 190
    for r in righe:
        d.text((50, y), an.ascii_puro(r)[:60], fill=(80, 80, 90), font=medio)
        y += 40
    buf = io.BytesIO()
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
           ".gif": "GIF"}[ext]
    img.save(buf, fmt)
    return buf.getvalue()
