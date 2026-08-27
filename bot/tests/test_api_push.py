"""Il push su viapal deve poter fallire senza far danni.

Il caso che conta non è quello felice: è il server spento a metà campagna.
Il lead è già arrivato su Telegram, il bot deve tirare dritto, e il contatto
deve restare in coda finché non passa.
"""
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest

from bot.api_push import ApiViapal, payload_da_riga, spedisci_coda
from bot.storage import Archivio


@dataclass
class FintoPost:
    post_id: str = "1"
    permalink: str = "https://fb.com/groups/9/posts/1/"
    author_name: str = "Giulia"
    author_url: str | None = "https://fb.com/u/1"
    text: str = "Cerco singola a Monza"
    link_messenger: str | None = "https://m.me/42"


MESSAGGI = SimpleNamespace(commento_pubblico="ti ho scritto", privato="ciao Giulia…")


def _archivio_con_un_lead(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(
        FintoPost(), {"zona": "Monza", "budget_max": 480}, matched=True,
        notificato=True, messaggi=MESSAGGI,
    )
    return a


# --- coda ------------------------------------------------------------------


def test_solo_i_match_finiscono_in_coda(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"), matched=True, messaggi=MESSAGGI)
    a.registra(FintoPost("2"), matched=False)
    assert [r["post_id"] for r in a.da_pushare()] == ["1"]


def test_un_lead_pushato_esce_dalla_coda(tmp_path):
    a = _archivio_con_un_lead(tmp_path)
    a.segna_pushati(["1"])
    assert a.da_pushare() == []


def test_i_messaggi_composti_sopravvivono_al_giro(tmp_path):
    """Senza, il ritenta del giro dopo manderebbe un lead senza i testi —
    cioè la parte che serve davvero a chi lo lavora."""
    riga = _archivio_con_un_lead(tmp_path).da_pushare()[0]
    assert riga["commento"] == "ti ho scritto"
    assert riga["privato"] == "ciao Giulia…"


# --- traduzione ------------------------------------------------------------


def test_il_payload_traduce_i_nomi(tmp_path):
    riga = _archivio_con_un_lead(tmp_path).da_pushare()[0]
    p = payload_da_riga(riga)
    assert p["testo"] == "Cerco singola a Monza"
    assert p["analisi"] == {"zona": "Monza", "budget_max": 480}
    assert p["commento_proposto"] == "ti ho scritto"
    assert p["link_messenger"] == "https://m.me/42"


def test_analisi_illeggibile_non_fa_saltare_il_push():
    p = payload_da_riga({"post_id": "1", "seen_at": "2026-08-27", "analysis": "{rotto"})
    assert p["analisi"] == {}


# --- best effort -----------------------------------------------------------


def test_push_spento_non_fa_nulla(tmp_path):
    a = _archivio_con_un_lead(tmp_path)
    assert spedisci_coda(None, a) == 0
    assert len(a.da_pushare()) == 1     # e la coda resta intatta


def test_server_giu_lascia_tutto_in_coda(tmp_path, monkeypatch):
    a = _archivio_con_un_lead(tmp_path)
    api = ApiViapal("http://localhost:8020", "bot", "pw", 1)

    def esplode(*_a, **_k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", esplode)
    assert spedisci_coda(api, a) == 0          # non solleva
    assert len(a.da_pushare()) == 1            # e si ritenta al giro dopo


def test_push_riuscito_svuota_la_coda(tmp_path, monkeypatch):
    a = _archivio_con_un_lead(tmp_path)
    api = ApiViapal("http://localhost:8020", "bot", "pw", 1)
    visti = {}

    def finta_post(url, **kw):
        visti["url"] = url
        visti["headers"] = kw["headers"]
        visti["leads"] = kw["json"]["leads"]
        return httpx.Response(
            200,
            json={"creati": 1, "aggiornati": 0},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", finta_post)
    assert spedisci_coda(api, a) == 1
    assert a.da_pushare() == []
    assert visti["url"].endswith("/api/v1/leads/bulk-upsert/")
    assert visti["headers"]["X-Property-Id"] == "1"
    assert visti["leads"][0]["post_id"] == "1"


def test_coda_lunga_avvisa_su_telegram(tmp_path, monkeypatch):
    """Dieci lead fermi non sono un buco di rete: è ora di guardare il server."""
    a = Archivio(tmp_path / "t.db")
    for i in range(10):
        a.registra(FintoPost(str(i)), matched=True, messaggi=MESSAGGI)
    api = ApiViapal("http://localhost:8020", "bot", "pw", 1)
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("giù"))
    )
    allarmi = []
    spedisci_coda(api, a, SimpleNamespace(allarme=allarmi.append))
    assert len(allarmi) == 1
    assert "10 contatti" in allarmi[0]


@pytest.mark.parametrize("stato", [400, 403, 500])
def test_risposte_di_errore_non_svuotano_la_coda(tmp_path, monkeypatch, stato):
    a = _archivio_con_un_lead(tmp_path)
    api = ApiViapal("http://localhost:8020", "bot", "pw", 1)
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(stato, request=httpx.Request("POST", url)),
    )
    assert spedisci_coda(api, a) == 0
    assert len(a.da_pushare()) == 1
