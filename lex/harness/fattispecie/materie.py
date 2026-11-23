"""Regole per materia (schede di ``materia_*.py``) aggiunte all'elenco ``REGOLE`` dell'harness."""
from __future__ import annotations

from . import materia_pubblico_impiego

MODULI = (materia_pubblico_impiego,)

SCHEDE = tuple(s for m in MODULI for s in m.SCHEDE)
REGOLE_MATERIE = tuple(s.regola_harness() for s in SCHEDE)
