"""Deposito dei lead su viapal, per lavorarli in due da pagina web.

Telegram resta il canale primario: arriva subito, sul telefono, e funziona
anche se il server è spento. Questo è il secondo binario — lo stato condiviso,
che dice chi ha già scritto a chi.

Perciò il push è **best-effort e ritentabile**: non solleva mai dentro al giro,
e i lead non ancora arrivati restano in coda in SQLite (``pushed_at IS NULL``)
finché non passano. Il server può stare giù una giornata senza che si perda
niente: al primo giro utile riparte tutto insieme, e l'endpoint è idempotente.

Se la sezione ``[api]`` non c'è in configurazione, il push è semplicemente
spento e il bot si comporta come prima.
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


def _analisi(riga: dict) -> dict:
    import json

    grezza = riga.get("analysis")
    if not grezza:
        return {}
    try:
        return json.loads(grezza)
    except (ValueError, TypeError):
        return {}


def payload_da_riga(riga: dict) -> dict:
    """Traduce una riga di SQLite nel lead che viapal si aspetta.

    I nomi sono diversi da una parte e dall'altra (``text``/``testo``): la
    traduzione sta qui, e nient'altro deve saperlo.
    """
    return {
        "post_id": riga["post_id"],
        "group_id": riga.get("group_id") or "",
        "group_label": riga.get("group_label") or "",
        "author_name": riga.get("author_name") or "",
        "author_url": riga.get("author_url") or "",
        "permalink": riga.get("permalink") or "",
        "link_messenger": riga.get("link_messenger") or "",
        "testo": riga.get("text") or "",
        "analisi": _analisi(riga),
        "commento_proposto": riga.get("commento") or "",
        "privato_proposto": riga.get("privato") or "",
        "seen_at": riga["seen_at"],
    }


class ApiViapal:
    """Client dell'endpoint bulk-upsert. Un metodo, nessuno stato."""

    def __init__(self, base_url: str, utente: str, password: str, property_id: int | str):
        self.url = base_url.rstrip("/") + "/api/v1/leads/bulk-upsert/"
        self.auth = (utente, password)
        self.property_id = str(property_id)

    def invia(self, righe: list[dict]) -> dict:
        """Manda i lead. Alza ``httpx.HTTPError`` se non passa: il chiamante
        decide se ritentare al giro dopo (spoiler: sì, sempre)."""
        risposta = httpx.post(
            self.url,
            json={"leads": [payload_da_riga(r) for r in righe]},
            auth=self.auth,
            headers={"X-Property-Id": self.property_id},
            timeout=30,
        )
        risposta.raise_for_status()
        return risposta.json()


def spedisci_coda(api: ApiViapal | None, archivio, notifier=None) -> int:
    """Svuota la coda dei lead non ancora arrivati su viapal.

    Torna quanti ne ha spediti. Non solleva mai: un server irraggiungibile non
    deve fermare il giro né far perdere una notifica Telegram già partita.
    """
    if api is None:
        return 0
    righe = archivio.da_pushare()
    if not righe:
        return 0
    try:
        esito = api.invia(righe)
    except httpx.HTTPError as exc:
        # Restano in coda: il prossimo giro ci riprova con tutto il blocco.
        log.warning("push su viapal fallito (%d in coda): %s", len(righe), exc)
        if notifier is not None and len(righe) >= 10:
            # Dieci lead fermi vuol dire che sono ore che non passa: qui non è
            # più un buco di rete, e conviene saperlo mentre la campagna è viva.
            notifier.allarme(
                f"{len(righe)} contatti non arrivano su viapal: {exc}. "
                "Restano in coda, ma controlla il server."
            )
        return 0
    archivio.segna_pushati([r["post_id"] for r in righe])
    log.info(
        "push su viapal: %d creati, %d aggiornati",
        esito.get("creati", 0),
        esito.get("aggiornati", 0),
    )
    return len(righe)
