"""Registry degli adapter strutturati per Lex."""

from __future__ import annotations

from .agenda import AgendaAdapter
from .anagrafiche import AnagraficheAdapter
from .cabina import CabinaAdapter
from .documenti import DocumentiAdapter
from .fascicoli import FascicoliAdapter
from .fatture import FattureAdapter
from .preventivi import PreventiviAdapter
from .ricerca_legale import RicercaLegaleAdapter
from .scadenziario import ScadenziarioAdapter
from .strumenti import StrumentiAdapter
from .tariffario import TariffarioAdapter
from .telematico import TelematicoAdapter


class LexAdapterRegistry:
    def __init__(self, adapters=None) -> None:
        self.adapters = list(
            adapters
            or [
                CabinaAdapter(),
                FascicoliAdapter(),
                DocumentiAdapter(),
                AgendaAdapter(),
                ScadenziarioAdapter(),
                TelematicoAdapter(),
                AnagraficheAdapter(),
                PreventiviAdapter(),
                TariffarioAdapter(),
                FattureAdapter(),
                StrumentiAdapter(),
                RicercaLegaleAdapter(),
            ]
        )

    def build_packs(self, request, workflow: str, context: dict, evidence: dict):
        packs = []
        for adapter in self.adapters:
            if not adapter.should_include(request, workflow, context, evidence):
                continue
            pack = adapter.build_pack(request, workflow, context, evidence)
            if pack.status == "empty" and not pack.warnings:
                continue
            packs.append(pack)
        return packs


__all__ = [
    "AgendaAdapter",
    "AnagraficheAdapter",
    "CabinaAdapter",
    "DocumentiAdapter",
    "FascicoliAdapter",
    "FattureAdapter",
    "LexAdapterRegistry",
    "PreventiviAdapter",
    "RicercaLegaleAdapter",
    "ScadenziarioAdapter",
    "StrumentiAdapter",
    "TariffarioAdapter",
    "TelematicoAdapter",
]