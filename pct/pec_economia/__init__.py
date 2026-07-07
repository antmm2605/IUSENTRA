"""Classificazione economica del presidio PEC — contributo unificato.

Base normativa: D.P.R. 115/2002 (art. 9 per la debenza, art. 9 c. 1-bis e
art. 76 per esenzione/autocertificazione, art. 13 per gli scaglioni);
D.M. 44/2011 e circuito PagoPA/RT per la ricevuta telematica di pagamento.

Il pacchetto non duplica le regole di estrazione: riusa gli estrattori
deterministici di `pct.fascicolo_sentenza_economica` (fonte unica delle
regex CU) e li adatta al flusso del presidio PEC, così la classificazione
resta identica tra vista economica dei fascicoli e presidio PEC.
"""

from pct.pec_economia.contributo_unificato import (
    CATEGORIA_ESENZIONE,
    CATEGORIA_RICEVUTA_PAGAMENTO,
    CATEGORIA_RICHIESTA_VERSAMENTO,
    ClassificazioneContributoUnificato,
    classifica_contributo_unificato_pec,
)
from pct.pec_economia.eventi import eventi_contributo_unificato
from pct.pec_economia.pagamenti import (
    integra_contributo_unificato,
    payment_record_contributo_unificato,
)

__all__ = [
    "CATEGORIA_ESENZIONE",
    "CATEGORIA_RICEVUTA_PAGAMENTO",
    "CATEGORIA_RICHIESTA_VERSAMENTO",
    "ClassificazioneContributoUnificato",
    "classifica_contributo_unificato_pec",
    "eventi_contributo_unificato",
    "integra_contributo_unificato",
    "payment_record_contributo_unificato",
]
