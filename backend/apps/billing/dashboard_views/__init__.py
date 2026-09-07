"""
Endpoint custom per le dashboard, un modulo per area: ``_common`` (costanti e helper),
``inquilino``, ``proprietario``, ``conto_economico``, ``rendiconto``, ``previsionale``, ``deposito``.
"""
from ._common import (
    CAUSALI_OPERATIVE,
    STATI_DA_PAGARE,
    TIPO_PER_CAUSALE,
    _alloc_per_receivable,
    _build_item_da_pagare,
    _commenti_per_receivable,
    _descrizione_receivable,
)
from .conto_economico import ContoEconomicoView
from .deposito import ChiusuraDepositoView, RestituzioneDepositoView
from .inquilino import DashboardInquilinoView, TenantSituazioneView
from .previsionale import ConguagliaPrevisionaleView, PrevisionaleUtenzeView
from .proprietario import BilancioOwnerDettaglioView, DashboardProprietarioView
from .rendiconto import RendicontoView, _resti_per_anno, _sbilancio_progressivo

__all__ = [
    "CAUSALI_OPERATIVE",
    "STATI_DA_PAGARE",
    "TIPO_PER_CAUSALE",
    "BilancioOwnerDettaglioView",
    "ChiusuraDepositoView",
    "ConguagliaPrevisionaleView",
    "ContoEconomicoView",
    "DashboardInquilinoView",
    "DashboardProprietarioView",
    "PrevisionaleUtenzeView",
    "RendicontoView",
    "RestituzioneDepositoView",
    "TenantSituazioneView",
    "_alloc_per_receivable",
    "_build_item_da_pagare",
    "_commenti_per_receivable",
    "_descrizione_receivable",
    "_resti_per_anno",
    "_sbilancio_progressivo",
]
