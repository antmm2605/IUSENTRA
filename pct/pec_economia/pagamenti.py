"""Record pagamento contributo unificato per il presidio PEC.

Traduce la classificazione CU (`pct.pec_economia.contributo_unificato`) nei
record `payments` dello schema `iusentra.pec.legal_event_understanding.v2`,
persistiti in `pec_legal_payments`. Ogni record dice al motore cosa fare
(`workflow_action`) e mantiene la revisione professionale obbligatoria.
"""

from __future__ import annotations

from typing import Any

from pct.pec_economia.contributo_unificato import (
    CATEGORIA_ESENZIONE,
    CATEGORIA_RICEVUTA_PAGAMENTO,
    CATEGORIA_RICHIESTA_VERSAMENTO,
    ClassificazioneContributoUnificato,
)
from pct.pec_economia.eventi import eventi_contributo_unificato

PAYMENT_EVENT_CU_PAGATO = "contributo_unificato_pagato"
PAYMENT_EVENT_CU_ESENTE = "contributo_unificato_esente"
PAYMENT_EVENT_CU_DA_VERSARE = "contributo_unificato_da_versare"

_PAYMENT_EVENT_PER_CATEGORIA = {
    CATEGORIA_RICEVUTA_PAGAMENTO: PAYMENT_EVENT_CU_PAGATO,
    CATEGORIA_ESENZIONE: PAYMENT_EVENT_CU_ESENTE,
    CATEGORIA_RICHIESTA_VERSAMENTO: PAYMENT_EVENT_CU_DA_VERSARE,
}

_WORKFLOW_ACTION_PER_CATEGORIA = {
    CATEGORIA_RICEVUTA_PAGAMENTO: (
        "Registrare il contributo unificato come pagato nella scheda economica "
        "del fascicolo collegato: la ricevuta telematica (PagoPA/RT o F23/F24) "
        "è la prova del versamento ex art. 192 D.P.R. 115/2002."
    ),
    CATEGORIA_ESENZIONE: (
        "Registrare l'esenzione dal contributo unificato: non aprire incasso né "
        "richiesta di versamento; conservare l'autocertificazione o il titolo di "
        "esenzione (art. 9 c. 1-bis / art. 76 D.P.R. 115/2002) nel fascicolo."
    ),
    CATEGORIA_RICHIESTA_VERSAMENTO: (
        "Presidiare la richiesta di versamento del contributo unificato: "
        "verificare importo e termine, poi pagare tramite PagoPA/F23 e "
        "archiviare la quietanza nel fascicolo."
    ),
}

_TITOLO_AZIONE_PER_CATEGORIA = {
    CATEGORIA_RICEVUTA_PAGAMENTO: "Contributo unificato pagato da registrare",
    CATEGORIA_ESENZIONE: "Esenzione contributo unificato da registrare",
    CATEGORIA_RICHIESTA_VERSAMENTO: "Contributo unificato da versare",
}


def payment_record_contributo_unificato(
    classificazione: ClassificazioneContributoUnificato,
) -> dict[str, Any]:
    """Costruisce il record payment V2 per la classificazione CU."""

    categoria = classificazione.categoria
    importo = None if categoria == CATEGORIA_ESENZIONE else classificazione.importo
    evidenza_testo = classificazione.titolo or classificazione.label or "Contributo unificato rilevato."
    return {
        "payment_event_type": _PAYMENT_EVENT_PER_CATEGORIA.get(categoria, PAYMENT_EVENT_CU_PAGATO),
        "beneficiary": "erario",
        "payer": "parte",
        "lawyer_direct_credit": False,
        "amounts": {
            "compensi": None,
            "esborsi": None,
            "spese_generali_15": None,
            "cpa": None,
            "iva": None,
            "totale_testuale": importo,
            "totale_stimato": importo,
        },
        "workflow_action": _WORKFLOW_ACTION_PER_CATEGORIA.get(categoria, ""),
        "action_title": _TITOLO_AZIONE_PER_CATEGORIA.get(categoria, "Contributo unificato da presidiare"),
        "human_review_required": True,
        "contributo_unificato": classificazione.to_dict(),
        "evidence": [
            {
                "source": classificazione.fonte or "presidio PEC",
                "text": evidenza_testo[:260],
                "confidence": 0.9 if categoria == CATEGORIA_RICEVUTA_PAGAMENTO else 0.8,
            }
        ],
    }


def integra_contributo_unificato(
    classification: dict[str, Any],
    payments: list[dict[str, Any]],
    classificazione: ClassificazioneContributoUnificato | None,
) -> None:
    """Integra la classificazione CU in eventi e pagamenti del presidio.

    Se esiste un'evidenza specifica (ricevuta/esenzione/richiesta) sostituisce
    il record generico ``contributo_unificato`` estratto dal solo dispositivo,
    evitando il doppio conteggio nella stessa PEC.
    """

    if classificazione is None:
        return
    payments[:] = [
        payment
        for payment in payments
        if str(payment.get("payment_event_type") or "") != "contributo_unificato"
    ]
    payments.append(payment_record_contributo_unificato(classificazione))
    events = classification.get("events")
    if isinstance(events, list):
        for code in eventi_contributo_unificato(classificazione):
            if code not in events:
                events.append(code)


__all__ = [
    "PAYMENT_EVENT_CU_DA_VERSARE",
    "PAYMENT_EVENT_CU_ESENTE",
    "PAYMENT_EVENT_CU_PAGATO",
    "integra_contributo_unificato",
    "payment_record_contributo_unificato",
]
