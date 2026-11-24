"""Regole per materia (schede di ``materia_*.py``) aggiunte all'elenco ``REGOLE`` dell'harness."""
from __future__ import annotations

from . import materia_banca_impresa, materia_complementi, materia_integrazioni, materia_civile_cautelare, materia_civile_sostanziale, materia_penale, materia_privacy, materia_varie, materia_esecuzione_monitorio, materia_lavoro_previdenza, materia_pubblico_impiego

MODULI = (materia_pubblico_impiego, materia_lavoro_previdenza, materia_esecuzione_monitorio, materia_civile_cautelare, materia_penale,
          materia_banca_impresa, materia_privacy, materia_civile_sostanziale, materia_varie,
          materia_integrazioni, materia_complementi)

SCHEDE = tuple(s for m in MODULI for s in m.SCHEDE)

from .significato_materie import SIGNIFICATO  # noqa: E402

for _s in SCHEDE:
    if _s.regola in SIGNIFICATO:
        _s.lato, _s.sinonimi, _s.situazioni = SIGNIFICATO[_s.regola]


def indice_significato() -> list[dict]:
    """Per la ricerca per significato: regola, materia, nome, lato, sinonimi e situazioni tipiche (parole del cliente)."""
    return [{"regola": s.regola, "materia": s.materia, "nome": s.nome, "lato": s.lato, "sinonimi": list(s.sinonimi),
             "situazioni": list(s.situazioni)} for s in SCHEDE]
REGOLE_MATERIE = tuple(s.regola_harness() for s in SCHEDE)
