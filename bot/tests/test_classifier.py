"""Test del classifier che non chiamano l'API: coprono la rete di sicurezza,
cioè quello che succede *dopo* la risposta del modello.
"""
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

from bot.classifier import AnalisiPost, ISTRUZIONI, NOTA_TRONCATO, analizza
from bot.config import carica

ESEMPIO = Path(__file__).parent.parent / "config.toml.example"


@dataclass
class FintoPost:
    text: str = "Cerco stanza a Monza"
    troncato: bool = False


def _client(analisi: AnalisiPost) -> Mock:
    client = Mock()
    client.messages.parse.return_value = Mock(parsed_output=analisi)
    return client


def _analisi(**kw) -> AnalisiPost:
    base = dict(
        intent="cerca", tipo_immobile="stanza_singola", match=True,
        stanze_compatibili=["camera-3"], motivo="ok",
    )
    return AnalisiPost(**(base | kw))


def test_una_stanza_affittata_sparisce_anche_se_il_modello_la_propone():
    """Se una stanza esce dal TOML mentre il post è in coda, non dev'essere
    proposta lo stesso: il composer scriverebbe di una camera già presa."""
    cfg = carica(ESEMPIO)
    analisi = analizza(
        _client(_analisi(stanze_compatibili=["camera-3", "camera-inesistente"])),
        cfg, FintoPost(),
    )
    assert analisi.stanze_compatibili == ["camera-3"]


def test_senza_stanze_valide_il_match_decade():
    cfg = carica(ESEMPIO)
    analisi = analizza(
        _client(_analisi(stanze_compatibili=["camera-fantasma"])), cfg, FintoPost()
    )
    assert analisi.match is False
    assert "nessuna stanza libera compatibile" in analisi.motivo


def test_un_post_troncato_avverte_il_modello():
    """Facebook collassa i post lunghi e il click su "Altro" fa perdere il feed:
    il modello dev'essere avvisato che sta leggendo un testo mozzato."""
    cfg = carica(ESEMPIO)
    client = _client(_analisi())
    analizza(client, cfg, FintoPost(troncato=True))
    istruzioni = client.messages.parse.call_args.kwargs["system"]
    assert "TRONCATO" in istruzioni

    client = _client(_analisi())
    analizza(client, cfg, FintoPost(troncato=False))
    assert "TRONCATO" not in client.messages.parse.call_args.kwargs["system"]


def test_il_prompt_elenca_solo_le_stanze_libere():
    cfg = carica(ESEMPIO)
    client = _client(_analisi())
    analizza(client, cfg, FintoPost())
    istruzioni = client.messages.parse.call_args.kwargs["system"]
    assert "camera-3" in istruzioni
    # e il totale, non il solo canone: è il numero da confrontare col budget
    assert "550" in istruzioni
