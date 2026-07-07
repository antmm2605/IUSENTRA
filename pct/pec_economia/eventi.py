"""Eventi presidio PEC derivati dalla classificazione contributo unificato.

I codici evento entrano in `classification.events` dello schema
`iusentra.pec.legal_event_understanding.v2` e nel rulepack versionato
(`pct/data/legal_pec_rules_v2026_08.json`), così il motore sa quale
workflow attivare per ciascuna evidenza CU.
"""

from __future__ import annotations

from pct.pec_economia.contributo_unificato import (
    CATEGORIA_ESENZIONE,
    CATEGORIA_RICEVUTA_PAGAMENTO,
    CATEGORIA_RICHIESTA_VERSAMENTO,
    ClassificazioneContributoUnificato,
)

EVENTO_CU_RICEVUTA = "ricevuta_pagamento_contributo_unificato"
EVENTO_CU_ESENZIONE = "esenzione_contributo_unificato"
EVENTO_CU_RICHIESTA = "richiesta_versamento_contributo_unificato"

_EVENTO_PER_CATEGORIA = {
    CATEGORIA_RICEVUTA_PAGAMENTO: EVENTO_CU_RICEVUTA,
    CATEGORIA_ESENZIONE: EVENTO_CU_ESENZIONE,
    CATEGORIA_RICHIESTA_VERSAMENTO: EVENTO_CU_RICHIESTA,
}


def eventi_contributo_unificato(
    classificazione: ClassificazioneContributoUnificato | None,
) -> list[str]:
    """Ritorna i codici evento da aggiungere alla classificazione PEC."""

    if classificazione is None:
        return []
    code = _EVENTO_PER_CATEGORIA.get(classificazione.categoria)
    return [code] if code else []


__all__ = [
    "EVENTO_CU_ESENZIONE",
    "EVENTO_CU_RICEVUTA",
    "EVENTO_CU_RICHIESTA",
    "eventi_contributo_unificato",
]
