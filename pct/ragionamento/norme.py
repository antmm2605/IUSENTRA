"""Le norme che il ragionamento applica: una sola fonte, il registro verificato della conoscenza procedurale.

Il registro `pct/procedura_fasi/fonti.py` porta per ogni norma l'URL Normattiva, la data di consultazione e un
estratto del testo vigente; le norme del ragionamento vi entrano staticamente da
`pct/procedura_fasi/fonti_ragionamento.py`. Qui si legge soltanto, senza modificare il registro: una norma chiesta
e non registrata non si inventa, `scheda()` solleva un errore e un test la scopre subito.
"""

from __future__ import annotations

from typing import Any

from pct.procedura_fasi.fonti import FONTI
from pct.procedura_fasi.fonti_ragionamento import FONTI_RAGIONAMENTO as AGGIUNTE


def scheda(identificativo: str) -> dict[str, Any]:
    """La voce della norma nel registro; errore se manca."""
    voce = FONTI.get(identificativo)
    if not voce:
        raise KeyError(f"norma non registrata: {identificativo}")
    return {"id": identificativo, **voce}


def norme(*identificativi: str) -> list[dict[str, Any]]:
    return [scheda(i) for i in identificativi]


__all__ = ["AGGIUNTE", "norme", "scheda"]
