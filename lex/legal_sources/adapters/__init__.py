"""Built-in disabled-by-default source adapters."""

from __future__ import annotations

from .agcm import AgcmAdapter
from .agenzia_entrate import AgenziaEntrateAdapter
from .anac import AnacAdapter
from .banca_dati_merito import BancaDatiMeritoAdapter
from .camera import CameraAdapter
from .cassazione import CassazioneAdapter
from .corte_costituzionale import CorteCostituzionaleAdapter
from .eurlex import EurLexAdapter
from .garante_privacy import GarantePrivacyAdapter
from .gazzetta_ufficiale import GazzettaUfficialeAdapter
from .giustizia_amministrativa import GiustiziaAmministrativaAdapter
from .hudoc import HudocAdapter
from .leggi_regionali import LeggiRegionaliAdapter
from .normattiva import NormattivaAdapter
from .senato import SenatoAdapter


ADAPTER_CLASSES = (
    NormattivaAdapter,
    GazzettaUfficialeAdapter,
    CorteCostituzionaleAdapter,
    CassazioneAdapter,
    GiustiziaAmministrativaAdapter,
    BancaDatiMeritoAdapter,
    EurLexAdapter,
    HudocAdapter,
    AgenziaEntrateAdapter,
    GarantePrivacyAdapter,
    AnacAdapter,
    AgcmAdapter,
    CameraAdapter,
    SenatoAdapter,
    LeggiRegionaliAdapter,
)


__all__ = [
    "ADAPTER_CLASSES",
    "AgcmAdapter",
    "AgenziaEntrateAdapter",
    "AnacAdapter",
    "BancaDatiMeritoAdapter",
    "CameraAdapter",
    "CassazioneAdapter",
    "CorteCostituzionaleAdapter",
    "EurLexAdapter",
    "GarantePrivacyAdapter",
    "GazzettaUfficialeAdapter",
    "GiustiziaAmministrativaAdapter",
    "HudocAdapter",
    "LeggiRegionaliAdapter",
    "NormattivaAdapter",
    "SenatoAdapter",
]
