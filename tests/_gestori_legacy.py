"""Per i test che leggono un template: aggiunge il codice dei gestori evento convertiti.

Dalla 2.411.0 il codice degli attributi ``on<evento>`` dei template sta nel
registro ``web/static/js/iu-gestori-registro.js`` (CSP senza 'unsafe-inline').
"""

from __future__ import annotations

from pathlib import Path

from scripts.csp_gestori_legacy import carica_registro, chiavi_usate

ROOT = Path(__file__).resolve().parents[1]


def template_con_gestori(percorso: str | Path) -> str:
    testo = (ROOT / percorso).read_text(encoding="utf-8") if not Path(percorso).is_absolute() else Path(percorso).read_text(encoding="utf-8")
    registro = carica_registro()
    codice = "\n".join(registro[k] for k in sorted(chiavi_usate([testo])) if k in registro)
    return testo + "\n<!-- gestori evento -->\n" + codice
