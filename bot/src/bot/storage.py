"""Stato di campagna su SQLite. Serve solo a non riscrivere due volte alla
stessa persona: a campagna chiusa il file .db si cancella e basta.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id      TEXT PRIMARY KEY,
    author_name  TEXT,
    author_url   TEXT,
    text         TEXT,
    permalink    TEXT,
    seen_at      TIMESTAMP NOT NULL,
    analysis     TEXT,
    matched      BOOLEAN,
    notified_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_author ON posts(author_url);
-- Fin dove si è letto ogni gruppo: l'ora del post più recente incontrato.
-- `in_sospeso` è la lettura dell'ultimo --estrai, che diventa `ultima_ora`
-- solo quando --notifica conferma che quei post sono stati gestiti: se il
-- giro muore a metà, il giro dopo riparte dal segnalibro vecchio e li rilegge.
CREATE TABLE IF NOT EXISTS letture (
    group_id     TEXT PRIMARY KEY,
    ultima_ora   TEXT,
    in_sospeso   TEXT,
    letto_il     TIMESTAMP
);
"""

# Colonne aggiunte dopo il primo giro di campagna. Si applicano una per volta
# ignorando l'errore "duplicate column": è la migrazione più semplice che
# funziona su un file che si cancella a fine campagna.
COLONNE_TARDIVE = (
    # I due messaggi composti servono al push: senza, il ritenta di un giro
    # successivo non avrebbe più il testo da mandare.
    ("commento", "TEXT"),
    ("privato", "TEXT"),
    ("group_id", "TEXT"),
    ("group_label", "TEXT"),
    ("link_messenger", "TEXT"),
    # NULL = ancora da mandare a viapal. È tutta la coda che serve.
    ("pushed_at", "TIMESTAMP"),
)


class Archivio:
    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso).expanduser()
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
            for nome, tipo in COLONNE_TARDIVE:
                try:
                    c.execute(f"ALTER TABLE posts ADD COLUMN {nome} {tipo}")
                except sqlite3.OperationalError:
                    pass   # colonna già presente

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.percorso)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def id_visti(self) -> set[str]:
        with self._conn() as c:
            return {r["post_id"] for r in c.execute("SELECT post_id FROM posts")}

    def ultima_ora(self, group_id: str) -> datetime | None:
        """L'ora del post più recente gestito in questo gruppo, o None al
        primo giro. È il segnalibro a cui lo scraper si ferma."""
        with self._conn() as c:
            r = c.execute(
                "SELECT ultima_ora FROM letture WHERE group_id = ?", (group_id,)
            ).fetchone()
        return datetime.fromisoformat(r["ultima_ora"]) if r and r["ultima_ora"] else None

    def segna_lettura(self, group_id: str, ora: datetime | None) -> None:
        """Annota fin dove si è letto, in sospeso: vale dopo `conferma_letture`."""
        if ora is None:
            return      # nessun post con l'ora leggibile: il segnalibro resta dov'era
        with self._conn() as c:
            c.execute(
                "INSERT INTO letture (group_id, in_sospeso, letto_il) VALUES (?, ?, ?) "
                "ON CONFLICT(group_id) DO UPDATE SET in_sospeso = excluded.in_sospeso, "
                "letto_il = excluded.letto_il",
                (group_id, ora.isoformat(timespec="minutes"),
                 datetime.now(timezone.utc).isoformat()),
            )

    def conferma_letture(self) -> None:
        """Le letture in sospeso diventano il segnalibro. Mai all'indietro:
        una prova o un giro parziale non devono far rileggere il già letto."""
        with self._conn() as c:
            c.execute(
                "UPDATE letture SET ultima_ora = CASE "
                "WHEN ultima_ora IS NULL OR in_sospeso > ultima_ora THEN in_sospeso "
                "ELSE ultima_ora END, in_sospeso = NULL WHERE in_sospeso IS NOT NULL"
            )

    def autori_gia_contattati(self) -> set[str]:
        """Deduplica secondaria: chi ripubblica lo stesso annuncio dopo qualche
        giorno non va ricontattato."""
        with self._conn() as c:
            return {
                r["author_url"]
                for r in c.execute(
                    "SELECT DISTINCT author_url FROM posts "
                    "WHERE notified_at IS NOT NULL AND author_url IS NOT NULL"
                )
            }

    def registra(
        self, post, analisi=None, matched=False, notificato=False, messaggi=None
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO posts "
                "(post_id, author_name, author_url, text, permalink, seen_at, "
                " analysis, matched, notified_at, commento, privato, "
                " group_id, group_label, link_messenger) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    post.post_id,
                    post.author_name,
                    post.author_url,
                    post.text,
                    post.permalink,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(analisi, ensure_ascii=False) if analisi else None,
                    matched,
                    datetime.now(timezone.utc).isoformat() if notificato else None,
                    getattr(messaggi, "commento_pubblico", None),
                    getattr(messaggi, "privato", None),
                    getattr(post, "group_id", None),
                    getattr(post, "group_label", None),
                    getattr(post, "link_messenger", None),
                ),
            )

    def da_pushare(self) -> list[dict]:
        """I lead che viapal non ha ancora ricevuto.

        Solo i match: la pagina serve a lavorare i contatti, non a rivedere il
        classificatore — e meno dati di terzi finiscono sul server, meglio è.
        Un lead resta qui finché il push non riesce, quindi il server può
        essere spento per un giorno intero senza che si perda nulla.
        """
        with self._conn() as c:
            righe = c.execute(
                "SELECT * FROM posts WHERE matched AND pushed_at IS NULL"
            ).fetchall()
        return [dict(r) for r in righe]

    def segna_pushati(self, post_ids) -> None:
        ora = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.executemany(
                "UPDATE posts SET pushed_at = ? WHERE post_id = ?",
                [(ora, pid) for pid in post_ids],
            )

    def statistiche(self) -> dict:
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) tot, SUM(matched) match_, "
                "SUM(notified_at IS NOT NULL) notif FROM posts"
            ).fetchone()
            return {"totali": r["tot"], "match": r["match_"] or 0, "notificati": r["notif"] or 0}
