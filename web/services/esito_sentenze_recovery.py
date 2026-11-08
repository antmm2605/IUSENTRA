"""Recupero puntuale dell'esito delle sentenze lette prima dell'estrazione dell'esito.

L'estrazione dell'esito e delle spese dal dispositivo (e dell'estinzione dichiarata da un'ordinanza) (``pct/archivio_letture/estrazione_esito.py``) è arrivata dopo
la prima lettura di molte sentenze; per scelta di progetto il rilascio non riavvia una rilettura generale
(``VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI``). Così una sentenza del 2026 letta prima restava senza «spese compensate»
e il conto economico non lo sapeva (RG 2962/2023 Giudice di Pace di Palmi, collaudo 08/11/2026).

Qui il recupero riguarda **solo** i documenti che il catalogo indica come sentenze, ordinanze o provvedimenti del giudice, letti dal motore documenti con
l'impronta corrente e privi dei fatti dell'esito: si usa il testo già salvato (OCR o indice), mai il file, e il
risultato si aggiunge ai fatti della stessa lettura passando dal registro delle letture. Se il dispositivo non si
riconosce, un fatto di controllo con la versione dell'estrazione evita di riprovare a ogni giro.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CAMPI_ESITO = {"esito_sentenza", "spese_sentenza", "estinzione_processo"}
# Provvedimenti che possono decidere o chiudere la causa: sentenze e ordinanze (es. estinzione, artt. 307-309 c.p.c.).
_ETICHETTE = ("sentenza", "ordinanza", "provvedimento")
CAMPO_CONTROLLO = "esito_controllato"


def _sentenze_del_catalogo(fascicolo_id: str) -> set[str]:
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    return {
        str(getattr(a, "document_id", "") or "")
        for a in build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), fascicolo_id)
        if str(getattr(a, "document_label", "") or "").strip().lower().startswith(_ETICHETTE)
        and str(getattr(a, "status", "") or "") != "rejected"
    }


def recupera_esiti(fascicolo: Any, registro: Any, tenant: str, *, sentenze: set[str] | None = None,
                   testo_salvato: Any = None) -> dict[str, int]:
    """Aggiunge esito e spese alle sentenze già lette che non li hanno; restituisce i conteggi."""
    from pct.archivio_letture.estrazione_esito import VERSIONE_ESTRAZIONE_ESITO, estrai_esito
    from pct.registro_letture.fatti_repository import Fatto
    from web.services.archivio_letture_runtime import _attribuisci, _testo_indice, _testo_ocr

    fid = str(getattr(fascicolo, "id", "") or "")
    esito = {"controllate": 0, "recuperate": 0}
    if not fid:
        return esito
    sentenze = _sentenze_del_catalogo(fid) if sentenze is None else sentenze
    if not sentenze:
        return esito
    documenti = {str(getattr(d, "id", "")): d for d in getattr(fascicolo, "documenti", []) or []}
    letture = {(l.oggetto_id, l.sha256): l for l in registro.letture(tenant, fid, lettore="motore_documenti") if l.stato == "letto"}
    leggi = testo_salvato or (lambda documento: _testo_ocr(documento) or _testo_indice(fascicolo, documento))
    for oggetto in registro.oggetti(tenant, fid):
        lettura = letture.get((oggetto.oggetto_id, oggetto.impronta))
        if oggetto.tipo != "documento" or not oggetto.presente or oggetto.oggetto_id not in sentenze or lettura is None:
            continue
        precedenti = [f for f in registro.fatti_oggetto(tenant, oggetto.tipo, oggetto.oggetto_id)
                      if f.fascicolo_id == fid and f.sha256 == oggetto.impronta and f.motore == "documenti"]
        if any(f.campo in CAMPI_ESITO or (f.campo == CAMPO_CONTROLLO and f.valore == VERSIONE_ESTRAZIONE_ESITO) for f in precedenti):
            continue
        documento = documenti.get(oggetto.oggetto_id)
        testo = str(leggi(documento) or "") if documento is not None else ""
        if not testo.strip() or testo.lstrip().startswith("PCTENC"):
            continue  # nessun testo salvato: ci penserà la lettura del documento, non si apre il file qui
        esito["controllate"] += 1
        nuovi = estrai_esito(testo, origine="indice")
        if nuovi:
            esito["recuperate"] += 1
        else:
            nuovi = [Fatto(categoria="evento", campo=CAMPO_CONTROLLO, valore=VERSIONE_ESTRAZIONE_ESITO,
                           valore_letto="dispositivo non riconosciuto", etichetta="Esito della sentenza non riconosciuto",
                           contesto="", posizione=0, origine="indice", verifica="verificata", confidenza=1.0,
                           prove=[{"codice": "controllo", "esito": "ok", "dettaglio": "recupero puntuale dell'esito"}])]
        registro.registra_fatti(tenant, fid, oggetto, "documenti", [*precedenti, *_attribuisci(nuovi, oggetto, "documenti")],
                                versione=lettura.versione_lettore)
    if esito["recuperate"]:
        logger.info("Esito recuperato per %s sentenze del fascicolo %s", esito["recuperate"], fid)
    return esito


__all__ = ["CAMPO_CONTROLLO", "recupera_esiti"]
