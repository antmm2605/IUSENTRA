"""Riconvalida degli esiti dell'indice Lex salvati come errore per la sola busta cifrata.

Versioni precedenti registravano come errore («Lettura del messaggio
incompleta: Atto.enc: Busta cifrata destinata all'ufficio giudiziario…») i
messaggi e le copie PEC di deposito che contengono la busta ``Atto.enc``. Con
la regola corrente (`pct.document_intelligence.busta_cifrata`) quella busta è
«non applicabile»: qui gli esiti già salvati si riclassificano senza rileggere
i documenti, aggiornando lo stato conservato:

* nel registro delle letture la lettura ``errore`` dell'indice documentale
  diventa ``non_leggibile`` con il motivo della busta;
* nell'audit del documento si aggiunge l'evento di riclassificazione, così
  l'ultima causa registrata è la nota e la vecchia resta ricostruibile.

Idempotente: una lettura già ``non_leggibile`` o un audit la cui ultima causa
è già la nota non si toccano. Base normativa: D.M. 44/2011 art. 14; Specifiche
tecniche DGSIA (busta crittografata con la chiave pubblica dell'ufficio);
art. 20 CAD per la tracciabilità della riclassificazione.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable

from pct.document_intelligence.audit import record_document_ai_event
from pct.document_intelligence.busta_cifrata import CODICE_BUSTA_CIFRATA, NOTA_BUSTA_CIFRATA

logger = logging.getLogger(__name__)
EVENTO_RICLASSIFICAZIONE = "document_ai.extraction.reclassified"


def riclassifica_buste_cifrate(service: Any, tenant_id: str, fascicolo_id: str, note: Iterable[dict[str, Any]],
                               *, letture_in_errore: dict[tuple[str, str], Any], context: object) -> int:
    """Aggiorna registro e audit per le fonti la cui causa salvata è la busta cifrata; restituisce quante."""
    note = [nota for nota in note if str(nota.get("causa_precedente") or "").strip()]
    if not note:
        return 0
    aggiornate = 0
    for nota in note:
        record_id = str(nota.get("record_id") or "")
        version_id = str(nota.get("version_id") or "")
        if record_id and version_id:
            try:
                record_document_ai_event(
                    service.repository, EVENTO_RICLASSIFICAZIONE, tenant_id=tenant_id, fascicolo_id=fascicolo_id,
                    user_context=context, document_id=record_id, version_id=version_id,
                    sha256=str(nota.get("sha256") or ""), filename=str(nota.get("filename") or ""), status="error",
                    error_code=CODICE_BUSTA_CIFRATA, error_message=NOTA_BUSTA_CIFRATA,
                    payload={"riconvalida": "busta_cifrata", "causa_precedente": str(nota["causa_precedente"])[:500]})
                aggiornate += 1
            except Exception as exc:
                logger.debug("Audit di riclassificazione non registrato per %s: %s", record_id, exc)
    _aggiorna_registro(tenant_id, fascicolo_id, note, letture_in_errore)
    return aggiornate


def _aggiorna_registro(tenant_id: str, fascicolo_id: str, note: list[dict[str, Any]],
                       letture_in_errore: dict[tuple[str, str], Any]) -> None:
    chiavi = [(str(nota.get("document_id") or ""), str(nota.get("sha256") or "")) for nota in note]
    chiavi = [chiave for chiave in chiavi if chiave in letture_in_errore]
    if not chiavi:
        return
    try:
        from pct.registro_letture import Oggetto
        from web.services.registro_letture_runtime import registro_corrente

        registro = registro_corrente()
    except Exception as exc:
        logger.debug("Registro letture non disponibile per la riclassificazione: %s", exc)
        return
    try:
        for documento_id, sha256 in chiavi:
            lettura = letture_in_errore[(documento_id, sha256)]
            registro.segna_letto(
                tenant_id, fascicolo_id, Oggetto(tipo="documento", oggetto_id=documento_id, sha256=sha256),
                "indice_documentale", versione=lettura.versione_lettore, stato="non_leggibile",
                esito={"stato": "not_applicable", "motivo": NOTA_BUSTA_CIFRATA, "error_code": CODICE_BUSTA_CIFRATA,
                       "riconvalida": "busta_cifrata", "causa_precedente": str(lettura.esito.get("motivo") or "")[:500]})
    except Exception as exc:
        logger.debug("Lettura dell'indice documentale non riclassificata: %s", exc)
    finally:
        registro.close()


__all__ = ["EVENTO_RICLASSIFICAZIONE", "riclassifica_buste_cifrate"]
