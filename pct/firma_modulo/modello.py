"""Il campo firma di un modulo: dov'e', quanto e' grande, dove finisce il tratto."""

from __future__ import annotations

from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Modello
# ---------------------------------------------------------------------------

@dataclass
class CampoFirma:
    nome: str
    etichetta: str
    pagina: int                     # 0-based
    rect: tuple[float, float, float, float]   # riquadro del campo, in punti
    zona: tuple[float, float, float, float]   # riquadro dove finisce la firma
    larghezza_pagina: float
    altezza_pagina: float

    def as_dict(self) -> dict:
        return asdict(self)
