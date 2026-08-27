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


def test_sopra_il_budget_si_prova_lo_stesso_con_la_piu_economica():
    """Molti scrivono una cifra prima di sapere quanto costa Monza, e la alzano
    quando vedono la casa. Scartarli a priori è un lead perso."""
    cfg = carica(ESEMPIO)
    analisi = analizza(
        _client(_analisi(budget_max=400, stanze_compatibili=[])), cfg, FintoPost()
    )
    assert analisi.match is True
    assert analisi.stanze_compatibili == ["camera-3"]   # totale 550, la più bassa
    assert "sopra il budget" in analisi.motivo


def test_un_budget_dichiarato_rigido_invece_scarta():
    cfg = carica(ESEMPIO)
    analisi = analizza(
        _client(_analisi(budget_max=400, budget_tassativo=True, stanze_compatibili=[])),
        cfg, FintoPost(),
    )
    assert analisi.match is False
    assert "rigido" in analisi.motivo


def test_chi_ha_un_animale_non_riceve_niente():
    """Non è una preferenza: in casa non sono ammessi, e scrivergli è tempo
    perso per tutti e due."""
    cfg = carica(ESEMPIO)
    analisi = analizza(_client(_analisi(animali=True)), cfg, FintoPost())
    assert analisi.match is False
    assert analisi.stanze_compatibili == []
    assert "animale" in analisi.motivo


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


def test_il_prompt_spiega_perche_certe_zone_sono_fuori():
    """La lista da sola non basta: senza il criterio (Monza costa più dei comuni
    intorno) il modello ragiona in chilometri e tiene i lead sbagliati."""
    cfg = carica(ESEMPIO)
    client = _client(_analisi())
    analizza(client, cfg, FintoPost())
    istruzioni = client.messages.parse.call_args.kwargs["system"]
    assert "prezzo di mercato" in istruzioni
    assert "Villasanta" in istruzioni      # la lista arriva comunque


def test_una_coppia_non_sta_in_una_stanza_singola():
    """Le stanze si affittano a uso singolo: marito e moglie non sono un lead."""
    cfg = carica(ESEMPIO)
    analisi = analizza(_client(_analisi(persone_per_stanza=2)), cfg, FintoPost())
    assert analisi.match is False
    assert "uso singolo" in analisi.motivo
    assert analisi.stanze_compatibili == []


def test_chi_cerca_per_una_persona_sola_passa():
    cfg = carica(ESEMPIO)
    analisi = analizza(_client(_analisi(persone_per_stanza=1)), cfg, FintoPost())
    assert analisi.match is True


def test_la_soglia_deriva_dal_tipo_delle_stanze(tmp_path):
    """Se un giorno compare una doppia, la regola si allarga da sola."""
    testo = ESEMPIO.read_text().replace('tipo = "singola"', 'tipo = "doppia"', 1)
    f = tmp_path / "c.toml"
    f.write_text(testo)
    analisi = analizza(_client(_analisi(persone_per_stanza=2)), carica(f), FintoPost())
    assert analisi.match is True
