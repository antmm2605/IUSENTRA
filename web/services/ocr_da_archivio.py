"""Il lettore «Testo e ricerca» (OCR) allineato a ciò che il motore documenti ha già letto.

Collaudo del 03/11/2026: il lettore OCR era scritto solo per i documenti caricati a mano (coda OCR al
caricamento); i documenti arrivati dal portale o dalle PEC restavano «da leggere» per sempre (11.776 su
11.962). Qui, senza aprire alcun file, dal registro delle letture:

- un documento di cui il motore documenti ha già un testo (nativo, indice, OCR salvato, contenitore) non
  ha bisogno dell'OCR: la lettura OCR si chiude come letta, con il motivo;
- un documento che il motore documenti ha trovato senza testo entra nella coda OCR, una sola
  volta: la coda rifiuta un documento già letto dall'OCR con la stessa impronta, anche se in errore.

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (impronta e integrità dei documenti informatici letti).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

LETTORE_OCR = "ocr"
LETTORE_DOCUMENTI = "motore_documenti"


def _ha_testo(esito: dict[str, Any]) -> str:
    """L'origine del testo letto dal motore documenti, se c'era un testo."""
    origini = [str(v) for v in list(esito.get("letture") or []) if str(v)]
    return str(esito.get("origine") or (origini[0] if origini else "") or "")


def allinea_ocr_fascicolo(registro: Any, tenant: str, fascicolo: Any) -> dict[str, int]:
    """Chiude le letture OCR non necessarie e accoda all'OCR i soli documenti senza testo. Nessun file aperto."""
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    esito = {"non_necessari": 0, "accodati": 0}
    if not fascicolo_id:
        return esito
    mancanti = registro.da_leggere(tenant, fascicolo_id, LETTORE_OCR, tipi=("documento",))
    if not mancanti:
        return esito
    letture = {(lt.oggetto_id, lt.sha256): lt for lt in registro.letture(tenant, fascicolo_id, lettore=LETTORE_DOCUMENTI)}
    documenti = {str(getattr(d, "id", "")): d for d in list(getattr(fascicolo, "documenti", []) or [])}
    ocr_runtime = current_app.extensions.get("ocr_runtime") if has_app_context() else None
    for oggetto in mancanti:
        lettura = letture.get((oggetto.oggetto_id, oggetto.impronta))
        if lettura is None:
            continue  # il motore documenti non l'ha ancora letto: si decide al giro dopo
        origine = _ha_testo(dict(lettura.esito or {})) if lettura.stato == "letto" else ""
        if origine:
            registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_OCR, stato="letto",
                                 esito={"motivo": f"OCR non necessario: testo già letto ({origine})"})
            esito["non_necessari"] += 1
            continue
        documento = documenti.get(oggetto.oggetto_id)
        # Senza testo (scansione non riconosciuta, pagine senza testo, file da recuperare): un tentativo di OCR
        # dedicato, uno solo. Se fallisce, il worker lo scrive in errore e la coda non lo riaccetta.
        if lettura.stato != "non_leggibile" or documento is None or ocr_runtime is None:
            continue
        try:
            from pct.ocr import estensione_supportata
            from web.helpers import get_fascicoli

            percorso = str(get_fascicoli().percorso_documento(fascicolo_id, documento.id))
            nome = str(getattr(documento, "nome", "") or "")
            if not (estensione_supportata(nome) or estensione_supportata(percorso)):
                continue
            accodato = ocr_runtime.enqueue(
                percorso=percorso, hash_sha256=str(getattr(documento, "hash_sha256", "") or ""), id_fasc=fascicolo_id,
                id_doc=documento.id, nome_doc=nome,
                tipo_doc=str(getattr(getattr(documento, "tipo", None), "value", getattr(documento, "tipo", "")) or ""),
                index_path=str(current_app.config.get("SEARCH_INDEX", "")))
            esito["accodati"] += int(bool(accodato))
        except Exception as exc:  # la coda OCR non ferma la lettura del fascicolo
            logger.warning("OCR non accodato per un documento del fascicolo %s: %s", fascicolo_id, exc)
    return esito


__all__ = ["allinea_ocr_fascicolo"]
