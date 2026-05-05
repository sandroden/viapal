"""Formattazione date in italiano, indipendente dal locale di sistema."""
from datetime import date

_MESI_FULL = (
    "",
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


def format_mese(d: date) -> str:
    """Nome italiano del mese in minuscolo (es. ``"maggio"``)."""
    return _MESI_FULL[d.month]


def format_mese_anno(d: date) -> str:
    """Nome italiano del mese seguito dall'anno (es. ``"maggio 2026"``)."""
    return f"{_MESI_FULL[d.month]} {d.year}"
