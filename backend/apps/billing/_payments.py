"""Risoluzione del conto di destinazione e validazione IBAN per i pagamenti.

Determina, al momento in cui si propone il pagamento, su quale conto un
inquilino deve versare un dato Receivable, e valida l'IBAN prima di esporlo
(evita di generare QR su IBAN placeholder).
"""
import re

from billing.models import Receivable


def conto_per_receivable(r: Receivable):
    """Conto bancario su cui versare l'addebito ``r``.

    - affitto: override sull'assegnazione se presente, altrimenti il conto
      della proprietà (default: si concentra tutto sul conto utenze).
    - utenze/extra: conto di domiciliazione utenze della proprietà.

    Ritorna un OwnerBankAccount o ``None`` se non risolvibile.
    """
    assignment = r.assignment
    if assignment is None:
        return None

    if r.causale == Receivable.Causale.AFFITTO and assignment.bank_account_affitto_id:
        return assignment.bank_account_affitto

    room = assignment.room
    prop = getattr(room, "property", None) if room else None
    return prop.bank_account_utenze if prop else None


# Lunghezze IBAN per codice paese (ISO 13616). Sottoinsieme SEPA + comuni.
_IBAN_LEN = {
    "IT": 27, "SM": 27, "DE": 22, "FR": 27, "ES": 24, "NL": 18, "BE": 16,
    "AT": 20, "PT": 25, "IE": 22, "LU": 20, "FI": 18, "GR": 27, "CH": 21,
    "GB": 22, "SE": 24, "DK": 18, "NO": 15, "PL": 28, "CZ": 24, "SK": 24,
    "HR": 21, "SI": 19, "EE": 20, "LV": 21, "LT": 20, "CY": 28, "MT": 31,
    "BG": 22, "RO": 24, "HU": 28,
}


def iban_valido(iban: str | None) -> bool:
    """Validazione IBAN: formato, lunghezza per paese e checksum mod-97."""
    if not iban:
        return False
    s = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", s or ""):
        return False
    attesa = _IBAN_LEN.get(s[:2])
    if attesa is not None and len(s) != attesa:
        return False
    if not (15 <= len(s) <= 34):
        return False
    # mod-97: sposta i primi 4 caratteri in coda, lettere -> numeri (A=10..Z=35)
    riarrangiato = s[4:] + s[:4]
    numerico = "".join(
        str(ord(c) - 55) if c.isalpha() else c for c in riarrangiato
    )
    return int(numerico) % 97 == 1
