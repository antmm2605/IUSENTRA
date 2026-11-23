"""Regole per materia (schede di ``materia_*.py``) aggiunte all'elenco ``REGOLE`` dell'harness."""
from __future__ import annotations

from . import materia_banca_impresa, materia_complementi, materia_civile_cautelare, materia_civile_sostanziale, materia_penale, materia_privacy, materia_varie, materia_esecuzione_monitorio, materia_lavoro_previdenza, materia_pubblico_impiego

MODULI = (materia_pubblico_impiego, materia_lavoro_previdenza, materia_esecuzione_monitorio, materia_civile_cautelare, materia_penale,
          materia_banca_impresa, materia_privacy, materia_civile_sostanziale, materia_varie,
          materia_complementi)

SCHEDE = tuple(s for m in MODULI for s in m.SCHEDE)
REGOLE_MATERIE = tuple(s.regola_harness() for s in SCHEDE)
