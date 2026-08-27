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
"""


class Archivio:
    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso).expanduser()
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

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

    def registra(self, post, analisi=None, matched=False, notificato=False) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO posts "
                "(post_id, author_name, author_url, text, permalink, seen_at, "
                " analysis, matched, notified_at) VALUES (?,?,?,?,?,?,?,?,?)",
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
                ),
            )

    def statistiche(self) -> dict:
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) tot, SUM(matched) match_, "
                "SUM(notified_at IS NOT NULL) notif FROM posts"
            ).fetchone()
            return {"totali": r["tot"], "match": r["match_"] or 0, "notificati": r["notif"] or 0}
