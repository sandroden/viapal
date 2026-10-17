"""Funzioni pure per anonimizzare la copia di produzione dell'ambiente demo.

Nessun accesso al database qui dentro: tutto ciò che è testabile senza DB
sta in questo modulo, il comando ``anonimizza_demo`` fa solo da orchestratore.

Contenuto:

* ``scala`` / ``ripara_importi``: scalatura degli importi (x 0,7) e riparazione
  al centesimo degli invarianti (somme delle allocazioni, classi di stato);
* ``genera_iban`` / ``codice_fiscale``: identificativi finti ma formalmente
  validi (checksum corretto);
* ``Scrubber``: sostituzione deterministica di nomi, luoghi, recapiti e codici
  nel testo libero, con confini di parola;
* i pool di nomi, cognomi, luoghi usati per inventare le persone.
"""
from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

FATTORE = Decimal("0.7")
CENT = Decimal("0.01")
ZERO = Decimal(0)

# Soglie delle classi di stato (vedi billing/models/payments.py e signals.py)
TOLLERANZA_BT = Decimal("0.01")   # BankTransaction: TOLLERANZA_ALLOC
SOGLIA_RECEIVABLE = Decimal("1.00")  # signals._SOGLIA


# Foto che restano vere nell'ambiente demo: galleria, stanze, immobile
CAMPI_FOTO = {
    ("properties.Property", "foto_hero"),
    ("properties.Property", "foto_planimetria"),
    ("properties.Property", "foto_mappa"),
    ("properties.GalleryImage", "image"),
    ("properties.Room", "foto"),
}


# ---------------------------------------------------------------------------
# Importi
# ---------------------------------------------------------------------------


def scala(importo: Decimal | None) -> Decimal | None:
    """Importo x 0,7 arrotondato ai centesimi (ROUND_HALF_UP)."""
    if importo is None:
        return None
    return (Decimal(importo) * FATTORE).quantize(CENT, rounding=ROUND_HALF_UP)


def _segno(x: Decimal) -> int:
    return -1 if x < 0 else 1


def _classe(delta: Decimal, soglie: tuple[Decimal, ...]) -> tuple[bool, ...]:
    return tuple(delta > s for s in soglie)


def _adatta(valore0: Decimal, tot0: Decimal | None, tot1: Decimal | None,
            soglie: tuple[Decimal, ...]) -> Decimal:
    """Nuovo valore di un importo che ha allocazioni, dopo la scalatura.

    ``valore0``/``tot0`` sono valore e somma delle allocazioni prima della
    scalatura, ``tot1`` la somma dopo. Regole, nell'ordine:

    * uguaglianza con segno (BT saldata, addebito pari alle allocazioni): il
      nuovo valore e' esattamente ``tot1``;
    * uguaglianza in modulo ma segno discorde (restituzione deposito): stesso
      modulo di ``tot1``, segno del valore originale;
    * altrimenti ``scala(valore)`` corretto di qualche centesimo finche' la
      relazione col totale (``|valore| - |tot|`` rispetto alle soglie) e' la
      stessa di prima.
    """
    if tot0 is None:
        return scala(valore0)
    if valore0 == tot0:
        return tot1
    sgn = _segno(valore0)
    a0, t0 = abs(valore0), abs(tot0)
    if a0 == t0:
        return sgn * abs(tot1)
    t1 = abs(tot1)
    classe0 = _classe(a0 - t0, soglie)
    a1 = abs(scala(valore0))
    if _classe(a1 - t1, soglie) != classe0:
        # sposto il valore di un centesimo per volta, dal piu' vicino
        for k in range(1, 400):
            for cand in (a1 + k * CENT, a1 - k * CENT):
                if cand >= 0 and _classe(cand - t1, soglie) == classe0:
                    a1 = cand
                    break
            else:
                continue
            break
    return sgn * a1


@dataclass
class Riparati:
    allocazioni: dict
    movimenti: dict
    addebiti_dovuto: dict
    addebiti_pagato: dict


def ripara_importi(allocazioni: dict, movimenti: dict, addebiti: dict) -> Riparati:
    """Scala tutti gli importi dell'impianto banca/allocazioni/addebiti.

    * ``allocazioni``: ``{id: (bt_id, receivable_id, importo)}``
    * ``movimenti``: ``{bt_id: importo}``
    * ``addebiti``: ``{receivable_id: (importo_dovuto, importo_pagato)}``

    Le allocazioni sono la base (ognuna scalata e arrotondata); movimento e
    addebito si riallineano alla loro somma dove prima erano pari, mantenendo
    la stessa relazione (parziale / saldato / eccedente) dove non lo erano.
    ``importo_pagato`` (derivato) segue la somma delle allocazioni.
    """
    nuove = {aid: scala(imp) for aid, (_bt, _rc, imp) in allocazioni.items()}
    tot0_bt: dict = {}
    tot1_bt: dict = {}
    tot0_rc: dict = {}
    tot1_rc: dict = {}
    for aid, (bt, rc, imp) in allocazioni.items():
        tot0_bt[bt] = tot0_bt.get(bt, ZERO) + imp
        tot1_bt[bt] = tot1_bt.get(bt, ZERO) + nuove[aid]
        tot0_rc[rc] = tot0_rc.get(rc, ZERO) + imp
        tot1_rc[rc] = tot1_rc.get(rc, ZERO) + nuove[aid]

    # BT: 'pieno' se sum >= importo, 'sovra' se eccede oltre la tolleranza;
    # soglie su (|importo| - |somma|): >0 parziale, >-tol non sovra
    soglie_bt = (ZERO, -TOLLERANZA_BT)
    # Receivable: 'pagato' se |sum| + 1 >= |dovuto|; poi parziale/zero
    soglie_rc = (ZERO, SOGLIA_RECEIVABLE)

    mov = {bt: _adatta(imp, tot0_bt.get(bt), tot1_bt.get(bt), soglie_bt)
           for bt, imp in movimenti.items()}
    dov = {}
    pag = {}
    for rc, (dovuto, pagato) in addebiti.items():
        dov[rc] = _adatta(dovuto, tot0_rc.get(rc), tot1_rc.get(rc), soglie_rc)
        if pagato is None:
            pag[rc] = None
        elif rc in tot1_rc and pagato == tot0_rc[rc]:
            pag[rc] = tot1_rc[rc]
        elif pagato == dovuto:
            pag[rc] = dov[rc]
        else:
            pag[rc] = scala(pagato)
    return Riparati(nuove, mov, dov, pag)


# Importi scritti nel testo: "33,50 €", "36.67€", "€ 500", "1.234,56 euro"
_NUM = r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
_RE_IMPORTO = re.compile(
    rf"(?<![\d.,])(?P<n1>{_NUM})(?P<sp1>\s?)(?P<v1>€|euro\b|eur\b)"
    rf"|(?P<v2>€)(?P<sp2>\s?)(?P<n2>{_NUM})(?![\w])",
    re.IGNORECASE,
)


def _scala_numero_testo(num: str) -> str:
    miglia = bool(re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", num))
    if "," in num:
        valore = Decimal(num.replace(".", "").replace(",", "."))
        sep, con_decimali = ",", True
    elif miglia:
        valore, sep, con_decimali = Decimal(num.replace(".", "")), ",", False
    else:
        con_decimali = "." in num
        valore, sep = Decimal(num), "."
    nuovo = scala(valore)
    if nuovo == nuovo.to_integral_value() and not con_decimali:
        testo = f"{int(nuovo)}"
    else:
        testo = f"{nuovo:.2f}"
    if sep == "," and "." in testo:
        testo = testo.replace(".", ",")
    if miglia:
        intero, _, dec = testo.partition(",")
        intero = f"{int(intero):,}".replace(",", ".")
        testo = intero + ("," + dec if dec else "")
    return testo


def scala_importi_nel_testo(testo: str) -> str:
    """Scala (x 0,7) gli importi scritti accanto a un simbolo di euro."""

    def _sub(m: re.Match) -> str:
        if m.group("n1") is not None:
            return _scala_numero_testo(m.group("n1")) + m.group("sp1") + m.group("v1")
        return m.group("v2") + m.group("sp2") + _scala_numero_testo(m.group("n2"))

    return _RE_IMPORTO.sub(_sub, testo)


# ---------------------------------------------------------------------------
# IBAN e codice fiscale
# ---------------------------------------------------------------------------

_DISPARI = [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14,
            16, 10, 22, 25, 24, 23]


def _lettera_di_controllo(s: str) -> str:
    """Carattere di controllo comune a CIN (IBAN italiano) e codice fiscale."""
    tot = 0
    for i, c in enumerate(s.upper()):
        if c.isdigit():
            pos = int(c)
            tot += _DISPARI[pos] if i % 2 == 0 else pos
        else:
            pos = ord(c) - 65
            tot += _DISPARI[pos] if i % 2 == 0 else pos
    return chr(65 + tot % 26)


def _numerico(s: str) -> str:
    return "".join(str(int(c, 36)) for c in s.upper())


def iban_check_digits(paese: str, bban: str) -> str:
    resto = int(_numerico(bban + paese + "00")) % 97
    return f"{98 - resto:02d}"


def iban_valido(iban: str) -> bool:
    iban = re.sub(r"\s", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    if int(_numerico(iban[4:] + iban[:4])) % 97 != 1:
        return False
    if iban.startswith("IT"):
        return len(iban) == 27 and iban[4] == _lettera_di_controllo(iban[5:])
    return True


ABI_FINTI = ["03069", "05034", "03332", "03015", "05387", "06230", "03127"]


def genera_iban(rng: random.Random) -> str:
    abi = rng.choice(ABI_FINTI)
    cab = f"{rng.randrange(1000, 99999):05d}"
    conto = f"{rng.randrange(10**11, 10**12)}"
    cin = _lettera_di_controllo(abi + cab + conto)
    bban = cin + abi + cab + conto
    return f"IT{iban_check_digits('IT', bban)}{bban}"


MESI_CF = "ABCDEHLMPRST"


def _ascii_lettere(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z]", "", s).upper()


def _consonanti_vocali(s: str) -> tuple[str, str]:
    s = _ascii_lettere(s)
    return ("".join(c for c in s if c not in "AEIOU"),
            "".join(c for c in s if c in "AEIOU"))


def codice_fiscale(cognome: str, nome: str, nascita: date, sesso: str,
                   belfiore: str) -> str:
    """Codice fiscale formalmente valido (algoritmo standard)."""
    cons, voc = _consonanti_vocali(cognome)
    cog = (cons + voc + "XXX")[:3]
    cons, voc = _consonanti_vocali(nome)
    if len(cons) >= 4:
        nom = cons[0] + cons[2] + cons[3]
    else:
        nom = (cons + voc + "XXX")[:3]
    giorno = nascita.day + (40 if sesso == "F" else 0)
    corpo = (f"{cog}{nom}{nascita.year % 100:02d}{MESI_CF[nascita.month - 1]}"
             f"{giorno:02d}{belfiore.upper()}")
    return corpo + _lettera_di_controllo(corpo)


def cf_valido(cf: str) -> bool:
    cf = cf.strip().upper()
    return (bool(re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]", cf))
            and cf[-1] == _lettera_di_controllo(cf[:-1]))


# ---------------------------------------------------------------------------
# Pool di nomi e luoghi finti
# ---------------------------------------------------------------------------

NOMI_M = ["Marco", "Luca", "Andrea", "Matteo", "Giorgio", "Stefano", "Riccardo",
          "Paolo", "Davide", "Federico", "Simone", "Alberto", "Roberto", "Enrico",
          "Claudio", "Massimo", "Daniele", "Gabriele", "Tommaso", "Nicola",
          "Emanuele", "Filippo", "Giacomo", "Lorenzo", "Michele", "Vittorio",
          "Fabrizio", "Leonardo", "Edoardo", "Samuele", "Ettore", "Pietro"]
NOMI_F = ["Giulia", "Francesca", "Chiara", "Valentina", "Sara", "Elena", "Silvia",
          "Laura", "Paola", "Martina", "Alessia", "Federica", "Beatrice", "Irene",
          "Ilaria", "Camilla", "Serena", "Lucia", "Michela", "Elisabetta",
          "Roberta", "Monica", "Cristina", "Daniela", "Eleonora", "Veronica",
          "Margherita", "Teresa", "Viola", "Nadia", "Rebecca", "Greta"]
COGNOMI_IT = ["Valenti", "Ferraris", "Conti", "Moretti", "Galli", "Barbieri",
              "Rinaldi", "Fontana", "Caruso", "Marchetti", "Sartori", "Bellini",
              "Gentile", "Orlando", "Pellegrini", "Santoro", "Mazza", "Cattaneo",
              "Basile", "Fabbri", "Ferrero", "Grassi", "Leoni", "Monti", "Neri",
              "Palumbo", "Riva", "Serra", "Testa", "Vitale", "Zanetti", "Ruggeri",
              "Bianchini", "Colombo", "Donati", "Guidi", "Lombardi", "Messina"]

# categoria -> (cittadinanza, Z-code, città di nascita, nomi M, nomi F, cognomi)
CATEGORIE_ESTERE = {
    "india": ("indiana", "Z222", ["Chennai", "Madurai", "Coimbatore", "Pune", "Jaipur"],
              ["Rohan", "Karthik", "Vikram", "Arjun", "Sanjay", "Rahul"],
              ["Priya", "Kavita", "Anjali", "Meera", "Divya", "Deepa"],
              ["Nair", "Menon", "Iyer", "Pillai", "Reddy", "Krishnan", "Sharma"]),
    "srilanka": ("srilankese", "Z209", ["Colombo", "Kandy", "Galle", "Negombo"],
                 ["Nimal", "Kasun", "Chamara", "Dinesh", "Ruwan"],
                 ["Dilani", "Shanika", "Nadeesha", "Thilini", "Hasini"],
                 ["Perera", "Fernando", "Silva", "Jayasuriya", "Wickramasinghe"]),
    "marocco": ("marocchina", "Z330", ["Casablanca", "Rabat", "Fes", "Marrakech"],
                ["Yassine", "Karim", "Anas", "Mehdi", "Hamza"],
                ["Salma", "Imane", "Nadia", "Khadija", "Yasmina"],
                ["El Amrani", "Benali", "Haddad", "Bennani", "Tazi", "Alaoui"]),
    "turchia": ("turca", "Z243", ["Gaziantep", "Konya", "Bursa", "Adana"],
                ["Emre", "Burak", "Kerem", "Onur", "Serkan"],
                ["Zeynep", "Elif", "Ayse", "Selin", "Deniz"],
                ["Yilmaz", "Demir", "Kaya", "Celik", "Arslan", "Aydin"]),
    "colombia": ("colombiana", "Z604", ["Medellin", "Cali", "Bogota", "Cartagena"],
                 ["Mateo", "Santiago", "Camilo", "Esteban", "Julian"],
                 ["Valeria", "Camila", "Daniela", "Mariana", "Luisa"],
                 ["Gutierrez", "Herrera", "Ospina", "Restrepo", "Cardenas", "Mejia"]),
    "zimbabwe": ("zimbabwese", "Z337", ["Harare", "Bulawayo", "Mutare"],
                 ["Tendai", "Farai", "Tafara", "Blessing"],
                 ["Chipo", "Rudo", "Tsitsi", "Nyasha"],
                 ["Moyo", "Ncube", "Dube", "Sibanda", "Chikwanha"]),
    "egitto": ("egiziana", "Z336", ["Il Cairo", "Alessandria", "Luxor"],
               ["Omar", "Tarek", "Karim", "Youssef"],
               ["Mona", "Heba", "Salma", "Dalia"],
               ["Hassan", "Mahmoud", "Ibrahim", "Farouk", "Saleh"]),
}

# (comune, sigla, belfiore) per le nascite italiane finte
COMUNI_NASCITA = [("Novara", "NO", "F952"), ("Milano", "MI", "F205"),
                  ("Torino", "TO", "L219"), ("Vercelli", "VC", "L750"),
                  ("Alessandria", "AL", "A182"), ("Pavia", "PV", "G388"),
                  ("Varese", "VA", "L682"), ("Bergamo", "BG", "A794"),
                  ("Brescia", "BS", "B157"), ("Cuneo", "CN", "D205"),
                  ("Genova", "GE", "D969"), ("Verona", "VR", "L781"),
                  ("Bologna", "BO", "A944"), ("Firenze", "FI", "D612"),
                  ("Padova", "PD", "G224"), ("Parma", "PR", "G337")]

# (comune, CAP) della provincia di Novara per residenze e luoghi finti
COMUNI_NO = [("Novara", "28100"), ("Trecate", "28069"), ("Galliate", "28066"),
             ("Oleggio", "28047"), ("Borgomanero", "28021"), ("Arona", "28041"),
             ("Cameri", "28062"), ("Romentino", "28068"), ("Cerano", "28060"),
             ("Momo", "28015"), ("Caltignaga", "28010"), ("Bellinzago Novarese", "28043"),
             ("Cassolnovo", "27023"), ("Garbagna Novarese", "28070"),
             ("Granozzo", "28060"), ("Sizzano", "28070")]
VIE_FINTE = ["dei Pioppi", "dei Ciliegi", "dei Mille", "Garibaldi", "Roma", "Mazzini",
             "Cavour", "della Libertà", "dei Gelsi", "Verdi", "Manzoni", "dei Platani",
             "XX Settembre", "Marconi", "dei Salici", "Leopardi", "Dante", "dei Faggi",
             "San Giovanni", "Matteotti", "dei Castagni", "Pascoli", "Volta", "Fermi"]

# Parole che non vanno mai trattate come "token da anonimizzare"
TOKEN_COMUNI = {
    "via", "viale", "piazza", "corso", "largo", "strada", "comune", "cascina",
    "vicolo", "contrada", "localita", "località", "frazione", "dei", "del",
    "della", "delle", "degli", "dello", "san", "santa", "sant", "con", "per",
    "the", "and", "nel", "nei", "una", "uno", "non", "sala", "camera",
    "casa", "italia", "italiana", "milanese", "nova", "mare", "villa",
}
PARTICELLE = {"di", "de", "del", "della", "dal", "da", "d", "la", "lo", "le", "el",
              "al", "van", "von", "ben", "bin", "dos", "das", "do", "du"}


# ---------------------------------------------------------------------------
# Scrubber: sostituzione deterministica nel testo libero
# ---------------------------------------------------------------------------

_CONF = r"(?<![^\W_])(?:{alt})(?![^\W_])"

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_IBAN = re.compile(r"(?<![A-Za-z0-9])IT\d{2}(?:\ ?[A-Za-z0-9]){23}(?![A-Za-z0-9])",
                     re.IGNORECASE)
RE_CF = re.compile(r"(?<![A-Za-z0-9])[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]"
                   r"(?![A-Za-z0-9])", re.IGNORECASE)
RE_TEL = re.compile(r"(?<![\w+])(?:(?:\+|00)?39[\s.-]?)?3\d{2}[\s./-]?\d{3}[\s./-]?\d{3,4}"
                    r"(?!\d)")
RE_CODICE = re.compile(r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])"
                       r"[A-Za-z0-9]{10,}(?![A-Za-z0-9])")
RE_PIVA = re.compile(r"(?<![A-Za-z0-9])IT\d{11}(?![A-Za-z0-9])")
RE_TOKEN_PASSWORD = re.compile(r"(/(?:imposta-password|reimposta-password|"
                               r"reset-password|password-reset|invito)/)[^\s\"'<>)]+")
RE_ORDINANTE = re.compile(r"(?P<pre>(?i:\bbon\.?\s?da)\s+)(?P<coda>(?:[A-Za-zÀ-ÿ'.]+\s*){1,9})")
STOP_ORDINANTE = set("""
AFFITTO FITTO AFITTO AFFITTI CANONE QUOTA UTENZE UTENZA UTENTE OTENZE BOLLETTE BOLLETTA
BILLS BILL CAUZIONE CAPARRA CONGUAGLIO CONSUNTIVO LUCE GAS TARI ASSEVERAZIONE
PAGAMENTO RIMBORSO ANTICIPO SALDO DEPOSITO ACCONTO RATA STANZA CAMERA SPESE SPESA MESE
MESI ANNO PER CON IN NR RIF BONIFICO SEPA CONTI FATTURA REGISTRAZIONE CONTRATTO
GENNAIO FEBBRAIO MARZO APRILE MAGGIO GIUGNO LUGLIO AGOSTO SETTEMBRE OTTOBRE NOVEMBRE
DICEMBRE GEN FEB MAR APR MAG GIU LUG AGO SET OTT NOV DIC JAN OCT NOV DEC
S.P.A. SPA SRL S.R.L. ITALIA GENERALI AGENZIA ENTRATE ENERGIA ASSICURAZIONI SALDO
""".split())
POOL_TERZI = ["Bianchi", "Rossetti", "Marini", "Vicari", "Benedetti", "Cremonesi", "Gallo",
              "Pagani", "Ferretti", "Longo", "Silvestri", "Carbone", "Orsini", "Villa",
              "Sanna", "Amato", "Piras", "Fiore", "Pozzi", "Bruno", "Costa", "Ricci",
              "Giordano", "Mancini", "Rizzo", "Lombardo", "Barone", "Martini", "Parisi",
              "Battaglia", "Farina", "Bernardi", "Monaco", "Valle", "Bassi", "Coppola"]
DOMINI_AMMESSI = ("example.com", "viapal.local", "storico.local", "example.org")


def asciiz(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", s).lower()


def adatta_maiuscole(originale: str, finto: str) -> str:
    lettere = [c for c in originale if c.isalpha()]
    if len(lettere) > 1 and originale.upper() == originale:
        return finto.upper()
    if lettere and originale.lower() == originale:
        return finto.lower()
    if (lettere and originale[:1].isupper() and finto[:1].islower()
            and finto.split()[0].lower() not in PARTICELLE | {"dei", "delle", "degli", "dello"}):
        return finto[:1].upper() + finto[1:]
    return finto


def normalizza_telefono(s: str) -> str:
    cifre = re.sub(r"\D", "", s)
    if cifre.startswith("0039"):
        cifre = cifre[4:]
    elif cifre.startswith("39") and len(cifre) > 10:
        cifre = cifre[2:]
    return cifre


def tokens_nome(s: str) -> list[str]:
    return [t for t in re.split(r"[\s'’.\-_,/]+", s) if t]


def token_significativo(t: str) -> bool:
    return (len(t) >= 3 and t.lower() not in TOKEN_COMUNI
            and t.lower() not in PARTICELLE and not t.isdigit())


@dataclass
class Scrubber:
    """Sostituisce dati reali con dati finti in modo deterministico.

    ``nomi`` mappa chiavi (minuscole) a sostituti: nomi, cognomi, username,
    luoghi, indirizzi... Le chiavi piu' lunghe vincono. ``emails``, ``ibans``,
    ``cfs``, ``telefoni`` mappano valori normalizzati reali -> finti; quelli
    sconosciuti (terzi che compaiono nel testo) ricevono un finto derivato da
    hash. ``fakes`` raccoglie tutto cio' che e' stato inventato, cosi' una
    seconda passata (idempotenza) non lo riscrive.
    """

    seed: str = "viapal-demo-2026"
    nomi: dict = field(default_factory=dict)
    emails: dict = field(default_factory=dict)
    ibans: dict = field(default_factory=dict)
    cfs: dict = field(default_factory=dict)
    telefoni: dict = field(default_factory=dict)
    regex_extra: list = field(default_factory=list)  # [(pattern, repl)] prima di tutto
    fakes: set = field(default_factory=set)
    token_noti: set = field(default_factory=set)   # finti gia' usati (minuscoli)
    aziende: set = field(default_factory=set)      # parole di aziende (minuscole)
    cache_terzi: dict = field(default_factory=dict)
    percorsi: dict = field(default_factory=dict)   # slug reale -> slug finto nei percorsi file
    vietati: set = field(default_factory=set)      # token reali: mai usati come finti
    _re_nomi: re.Pattern | None = None

    # -- hash deterministico -------------------------------------------------
    def _h(self, *parti: str) -> int:
        h = hashlib.sha256((self.seed + "|" + "|".join(parti)).encode()).hexdigest()
        return int(h, 16)

    def _rng(self, *parti: str) -> random.Random:
        return random.Random(self._h(*parti))

    # -- costruzione -----------------------------------------------------------
    def aggiungi_nome(self, reale: str, finto: str, sovrascrivi: bool = False) -> None:
        k = reale.strip().lower()
        if not k:
            return
        if sovrascrivi or k not in self.nomi:
            self.nomi[k] = finto
            if "'" in k:
                self.nomi.setdefault(k.replace("'", "’"), finto)
        self._re_nomi = None

    def _regex_nomi(self) -> re.Pattern | None:
        if self._re_nomi is None and self.nomi:
            chiavi = sorted(self.nomi, key=len, reverse=True)
            alt = "|".join(re.escape(k) for k in chiavi)
            self._re_nomi = re.compile(_CONF.format(alt=alt), re.IGNORECASE)
        return self._re_nomi

    # -- generatori di finti -----------------------------------------------------
    def telefono_finto(self, reale: str) -> str:
        k = normalizza_telefono(reale)
        if k in self.telefoni:
            return self.telefoni[k]
        rng = self._rng("tel", k)
        finto = f"3{rng.randrange(20, 99)} {rng.randrange(100, 999)} {rng.randrange(1000, 9999)}"
        if reale.strip().startswith(("+", "00", "39")):
            finto = "+39 " + finto
        self.telefoni[k] = finto
        self.fakes.add(normalizza_telefono(finto))
        return finto

    def iban_finto(self, reale: str) -> str:
        k = re.sub(r"\s", "", reale).upper()
        if k not in self.ibans:
            self.ibans[k] = genera_iban(self._rng("iban", k))
            self.fakes.add(self.ibans[k])
        return self.ibans[k]

    def cf_finto(self, reale: str) -> str:
        k = reale.strip().upper()
        if k not in self.cfs:
            rng = self._rng("cf", k)
            nascita = date(1960, 1, 1) + timedelta(days=rng.randrange(0, 15000))
            cogn = "".join(rng.choice("BCDFGLMNPRSTVZ") for _ in range(3))
            nom = "".join(rng.choice("BCDFGLMNPRSTVZ") for _ in range(3))
            self.cfs[k] = codice_fiscale(cogn + "AEI", nom + "AEI", nascita,
                                         rng.choice("MF"), "F952")
            self.fakes.add(self.cfs[k])
        return self.cfs[k]

    def email_finta(self, reale: str) -> str:
        k = reale.strip().lower()
        if k not in self.emails:
            self.emails[k] = f"contatto.{self._h('mail', k) % 10**6:06d}@example.com"
            self.fakes.add(self.emails[k])
        return self.emails[k]

    def codice_finto(self, reale: str) -> str:
        rng = self._rng("codice", reale)
        for _ in range(5):
            out = "".join(
                rng.choice("0123456789") if c.isdigit()
                else (rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") if c.isupper()
                      else rng.choice("abcdefghjkmnpqrstuvwxyz"))
                for c in reale)
            if out != reale:
                break
        self.fakes.add(out)
        return out

    # -- sostituzione ------------------------------------------------------------
    @staticmethod
    def _titolo_vicino(testo: str, inizio: int, fine: int) -> bool:
        """True se la parola prima o dopo (separata da spazi) e' in Maiuscola Iniziale."""
        def titolo(w: str) -> bool:
            w = re.sub(r"[^\wÀ-ÿ]", "", w)
            return len(w) >= 2 and w[0].isupper() and w[1:].islower()
        prima = re.search(r"(\S+)\s+$", testo[:inizio])
        dopo = re.match(r"\s+(\S+)", testo[fine:])
        return bool((prima and titolo(prima.group(1))) or (dopo and titolo(dopo.group(1))))

    def scrub_nomi(self, testo: str) -> str:
        rx = self._regex_nomi()
        if rx is None:
            return testo

        def _sub(m: re.Match) -> str:
            orig = m.group(0)
            low = orig.lower()
            finto = self.nomi.get(low)
            if finto is None:
                finto = self.nomi[low.replace("\u2019", "'")]
            if (orig.islower() and orig.isalpha() and finto[:1].isalpha()
                    and self._titolo_vicino(m.string, m.start(), m.end())):
                return finto[:1].upper() + finto[1:]
            return adatta_maiuscole(orig, finto)

        return rx.sub(_sub, testo)

    def scrub_ordinanti(self, testo: str) -> str:
        """Nomi di terzi dopo "BON.DA" nelle causali bancarie.

        Le persone note sono gia' state sostituite dal dizionario (e i loro finti
        sono in ``token_noti``); i nomi che restano nella sequenza che segue
        "BON.DA", fino alla prima parola descrittiva, sono di sconosciuti e
        vengono sostituiti con nomi deterministici.
        """
        def _sub(m: re.Match) -> str:
            toks = re.findall(r"\S+\s*", m.group("coda"))
            visti = 0
            out = []
            fermo = False
            for t in toks:
                nudo = t.strip()
                up = nudo.upper()
                if (fermo or visti >= 6 or not re.fullmatch(r"[A-Za-zÀ-ÿ']+", nudo)
                        or (len(nudo) == 1 and up not in ("E", "D"))
                        or up in STOP_ORDINANTE or up.lower() in self.aziende):
                    fermo = True
                    out.append(t)
                    continue
                visti += 1
                if up in ("E", "D", "DI", "DE", "DA", "LA", "LE", "LO", "EL"):
                    out.append(t)
                elif nudo.lower() in self.token_noti:
                    out.append(t)
                else:
                    f = self._terzo(nudo)
                    out.append(adatta_maiuscole(nudo, f) + t[len(nudo):])
            return m.group("pre") + "".join(out)

        return RE_ORDINANTE.sub(_sub, testo)

    def _terzo(self, token: str) -> str:
        k = token.lower()
        if k not in self.cache_terzi:
            pool = [n for n in POOL_TERZI if n.lower() not in self.token_noti
                    and n.lower() not in self.vietati
                    and n.lower() not in self.cache_terzi.values()]
            self.cache_terzi[k] = pool[self._h("terzo", k) % len(pool)]
            self.token_noti.add(self.cache_terzi[k].lower())
        return self.cache_terzi[k]

    def scrub(self, testo: str, importi: bool = True) -> str:
        """Anonimizza un testo libero (nomi, recapiti, codici, importi)."""
        if not testo:
            return testo
        for pattern, repl in self.regex_extra:
            testo = re.sub(pattern, repl, testo)
        testo = RE_TOKEN_PASSWORD.sub(
            lambda m: m.group(1) + self.codice_finto("x" + str(self._h("pw", m.group(0))))[:6]
            + "/" + self.codice_finto("y" + str(self._h("pw2", m.group(0))))[:20], testo)

        def _email(m):
            e = m.group(0)
            low = e.lower()
            if low in self.emails:
                return self.emails[low]
            if low in self.fakes or low.endswith(DOMINI_AMMESSI):
                return e
            return self.email_finta(e)
        testo = RE_EMAIL.sub(_email, testo)

        def _iban(m):
            k = re.sub(r"\s", "", m.group(0)).upper()
            if k in self.fakes:
                return m.group(0)
            finto = self.iban_finto(k)
            return finto if " " not in m.group(0) else " ".join(
                finto[i:i + 4] for i in range(0, len(finto), 4))
        testo = RE_IBAN.sub(_iban, testo)

        def _cf(m):
            k = m.group(0).upper()
            if k in self.fakes:
                return m.group(0)
            return self.cf_finto(k)
        testo = RE_CF.sub(_cf, testo)

        def _codice(m):
            c = m.group(0)
            if c in self.fakes or c in self.cfs.values():
                return c
            return self.codice_finto(c)
        testo = RE_CODICE.sub(_codice, testo)

        def _tel(m):
            k = normalizza_telefono(m.group(0))
            if k in self.fakes or len(k) not in (9, 10):
                return m.group(0)
            return self.telefono_finto(m.group(0))
        testo = RE_TEL.sub(_tel, testo)

        testo = self.scrub_nomi(testo)
        if importi:
            testo = scala_importi_nel_testo(testo)
        return testo

    def scrub_json(self, valore, importi: bool = True):
        if isinstance(valore, str):
            return self.scrub(valore, importi=importi)
        if isinstance(valore, list):
            return [self.scrub_json(v, importi) for v in valore]
        if isinstance(valore, dict):
            return {k: self.scrub_json(v, importi) for k, v in valore.items()}
        return valore

    def _piva_finta(self, m: re.Match) -> str:
        if m.group(0) in self.fakes:
            return m.group(0)
        finto = "IT" + f"{self._h('piva', m.group(0)) % 10**11:011d}"
        self.fakes.add(finto)
        return finto

    def scrub_percorso(self, percorso: str) -> str:
        """Per i path dei file: solo nomi e luoghi, nessun codice o importo."""
        nuovo = RE_PIVA.sub(self._piva_finta, self.scrub_nomi(percorso))
        for vecchio, finto in self.percorsi.items():
            nuovo = re.sub(rf"(?<![A-Za-z0-9]){re.escape(vecchio)}(?![A-Za-z0-9])", finto,
                           nuovo, flags=re.IGNORECASE)
        if " " not in percorso:
            nuovo = nuovo.replace(" ", "-")
        return nuovo
