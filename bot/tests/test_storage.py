from dataclasses import dataclass

from bot.storage import Archivio


@dataclass
class FintoPost:
    post_id: str
    permalink: str = "https://fb.com/p/1"
    author_name: str = "Tizio"
    author_url: str | None = "https://fb.com/u/1"
    text: str = "Cerco stanza"


def test_il_secondo_giro_non_ripropone_il_primo(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"))
    assert a.id_visti() == {"1"}


def test_chi_e_stato_contattato_non_si_ricontatta(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"), matched=True, notificato=True)
    a.registra(FintoPost("2", author_url="https://fb.com/u/2"), matched=False)
    assert a.autori_gia_contattati() == {"https://fb.com/u/1"}


def test_rivedere_lo_stesso_post_non_lo_duplica(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"))
    a.registra(FintoPost("1"))
    assert a.statistiche()["totali"] == 1


# --- il segnalibro di lettura per gruppo --------------------------------------

def test_il_segnalibro_vale_solo_dopo_la_conferma(tmp_path):
    """--estrai annota, --notifica conferma: se il giro muore in mezzo il giro
    dopo riparte da dove si era davvero arrivati a gestire i post."""
    from datetime import datetime
    a = Archivio(tmp_path / "t.db")
    assert a.ultima_ora("g") is None
    a.segna_lettura("g", datetime(2026, 9, 2, 22, 16))
    assert a.ultima_ora("g") is None
    a.conferma_letture()
    assert a.ultima_ora("g") == datetime(2026, 9, 2, 22, 16)


def test_il_segnalibro_non_torna_indietro(tmp_path):
    from datetime import datetime
    a = Archivio(tmp_path / "t.db")
    a.segna_lettura("g", datetime(2026, 9, 2, 22, 16))
    a.conferma_letture()
    a.segna_lettura("g", datetime(2026, 9, 2, 21, 0))
    a.conferma_letture()
    assert a.ultima_ora("g") == datetime(2026, 9, 2, 22, 16)


def test_senza_ora_leggibile_il_segnalibro_resta_dov_era(tmp_path):
    from datetime import datetime
    a = Archivio(tmp_path / "t.db")
    a.segna_lettura("g", datetime(2026, 9, 2, 22, 16))
    a.conferma_letture()
    a.segna_lettura("g", None)
    a.conferma_letture()
    assert a.ultima_ora("g") == datetime(2026, 9, 2, 22, 16)


def test_il_passaggio_profondo_si_segna_anche_senza_segnalibro(tmp_path):
    """Il gruppo nuovo non ha ancora una riga in `letture`: la crea lui."""
    from datetime import date, datetime
    a = Archivio(tmp_path / "t.db")
    assert a.profondo_fatto_il("g") is None
    a.segna_profondo("g", date(2026, 9, 4))
    assert a.profondo_fatto_il("g") == date(2026, 9, 4)
    assert a.ultima_ora("g") is None
    a.segna_lettura("g", datetime(2026, 9, 4, 12, 30))
    a.conferma_letture()
    assert a.profondo_fatto_il("g") == date(2026, 9, 4), "la lettura non cancella il giorno"


def test_il_database_di_prima_riceve_la_colonna_del_passaggio_profondo(tmp_path):
    """Il file di campagna esiste già: la colonna va aggiunta a caldo."""
    import sqlite3
    from datetime import date, datetime
    db = tmp_path / "vecchio.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE letture (group_id TEXT PRIMARY KEY, ultima_ora TEXT, in_sospeso TEXT, letto_il TIMESTAMP)")
        c.execute("INSERT INTO letture VALUES ('g', '2026-09-03T15:08', NULL, 'x')")
    a = Archivio(db)
    a.segna_profondo("g", date(2026, 9, 4))
    assert a.profondo_fatto_il("g") == date(2026, 9, 4)
    assert a.ultima_ora("g") == datetime(2026, 9, 3, 15, 8)
