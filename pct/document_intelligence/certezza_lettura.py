"""Quando la lettura di un documento è certa e non chiede verifiche all'avvocato (direttiva del 10/11/2026).

Un documento è riconosciuto con certezza se l'avvocato lo ha confermato o corretto, oppure se il catalogo lo ha
identificato dal contenuto (testo estratto e regola di identità con fonte normativa registrata) con affidabilità
pari o superiore alla soglia. Sotto la soglia o con la voce «da rivedere» c'è un dubbio reale e il dato resta da
confermare, con il motivo scritto dal catalogo.

Base: art. 20 CAD (D.Lgs. 82/2005) e art. 3 D.M. 44/2011 sull'integrità del documento informatico; le regole di
identità del catalogo citano la norma che definisce ciascun tipo di atto (pct/document_intelligence/catalog_sources.py).
"""
from __future__ import annotations

from typing import Any

SOGLIA_CERTEZZA = 90
STATI_DECISI_DALL_AVVOCATO = frozenset({"confirmed", "overridden"})


def lettura_certa(stato: Any, affidabilita: Any) -> bool:
    """Vero se la voce del catalogo è decisa dall'avvocato o riconosciuta dal contenuto con affidabilità certa."""
    stato = str(stato or "").strip()
    if stato in STATI_DECISI_DALL_AVVOCATO:
        return True
    if stato != "proposed":
        return False
    try:
        return int(affidabilita or 0) >= SOGLIA_CERTEZZA
    except (TypeError, ValueError):
        return False


__all__ = ["SOGLIA_CERTEZZA", "STATI_DECISI_DALL_AVVOCATO", "lettura_certa"]
