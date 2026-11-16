"""Recupero puntuale dell'esito delle sentenze lette prima dell'estrazione dell'esito.

L'estrazione dell'esito e delle spese dal dispositivo (e dell'estinzione dichiarata da un'ordinanza) (``pct/archivio_letture/estrazione_esito.py``) è arrivata dopo
la prima lettura di molte sentenze; per scelta di progetto il rilascio non riavvia una rilettura generale
(``VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI``). Così una sentenza del 2026 letta prima restava senza «spese compensate»
e il conto economico non lo sapeva (RG 2962/2023 Giudice di Pace di Palmi, collaudo 08/11/2026).

Qui il recupero riguarda **solo** i documenti che il catalogo indica come sentenze, ordinanze o provvedimenti del giudice, letti dal motore documenti con
l'impronta corrente e privi dei fatti dell'esito o con una liquidazione automatica senza importo: si usa il testo già salvato (OCR o indice), mai il file, e il
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


def accoda_liquidazioni_incomplete(registro: Any, tenant: str, *, prima_di: str, limite: int) -> int:
    """Rimette nella coda ordinaria un lotto di letture storiche da completare."""
    from pct.archivio_letture.estrazione_esito import VERSIONE_ESTRAZIONE_ESITO

    if not tenant or limite <= 0:
        return 0
    with registro.connection() as conn:
        righe = conn.execute(
            """
            SELECT f.fascicolo_id
            FROM letture_fatti f
            LEFT JOIN letture_eventi e ON e.tenant_id=f.tenant_id AND e.fascicolo_id=f.fascicolo_id
            WHERE f.tenant_id=? AND f.tipo='documento' AND f.motore='documenti'
              AND f.categoria='evento' AND f.campo='spese_sentenza' AND f.verifica='verificata'
              AND (f.valore IN ('condanna','compensazione_parziale')
                   OR f.valore LIKE ? OR f.valore LIKE ?)
              AND f.valore NOT LIKE ?
              AND (e.stato IS NULL OR (e.stato='idle' AND e.aggiornato_il<? AND e.last_error=''))
              AND EXISTS (
                  SELECT 1 FROM letture_oggetti o
                  WHERE o.tenant_id=f.tenant_id AND o.fascicolo_id=f.fascicolo_id
                    AND o.tipo=f.tipo AND o.oggetto_id=f.oggetto_id AND o.presente=1
                    AND f.sha256=CASE WHEN o.sha256<>'' THEN LOWER(o.sha256)
                        WHEN o.sha256_archivio<>'' THEN 'archivio:' || LOWER(o.sha256_archivio)
                        ELSE 'dimensione:' || CAST(o.dimensione AS TEXT) END
              )
              AND NOT EXISTS (
                  SELECT 1 FROM letture_fatti v
                  WHERE v.tenant_id=f.tenant_id AND v.fascicolo_id=f.fascicolo_id AND v.tipo=f.tipo
                    AND v.oggetto_id=f.oggetto_id AND v.sha256=f.sha256 AND v.motore=f.motore
                    AND v.campo=? AND v.valore=?
              )
            GROUP BY f.fascicolo_id, e.aggiornato_il
            ORDER BY COALESCE(e.aggiornato_il,''), f.fascicolo_id
            LIMIT ?
            """,
            (tenant, 'condanna;%', 'compensazione_parziale;%', '%;importo=%', prima_di,
             CAMPO_CONTROLLO, VERSIONE_ESTRAZIONE_ESITO, int(limite)),
        ).fetchall()
    return sum(bool(registro.accoda_evento(tenant, r["fascicolo_id"], solo_se_fermo=True)) for r in righe)


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
        campi_letti = {f.campo for f in precedenti}
        spese_incomplete = [
            f for f in precedenti
            if f.campo == "spese_sentenza" and getattr(f, "verifica", "") == "verificata"
            and f.valore.split(";")[0] in {"condanna", "compensazione_parziale"}
            and ";importo=" not in f.valore
        ]
        if (
            ({"esito_sentenza", "spese_sentenza", "data_decisione_sentenza"} <= campi_letti and not spese_incomplete
             and (not any(f.campo == "esito_sentenza" and f.valore == "improcedibile" for f in precedenti)
                  or "motivo_esito_sentenza" in campi_letti))
            or "estinzione_processo" in campi_letti
            or any(f.campo == CAMPO_CONTROLLO and f.valore == VERSIONE_ESTRAZIONE_ESITO for f in precedenti)
        ):
            continue
        documento = documenti.get(oggetto.oggetto_id)
        testo = str(leggi(documento) or "") if documento is not None else ""
        if not testo.strip() or testo.lstrip().startswith("PCTENC"):
            continue  # nessun testo salvato: ci penserà la lettura del documento, non si apre il file qui
        esito["controllate"] += 1
        estratti = estrai_esito(testo, origine="indice")
        nuovi = [f for f in estratti if f.campo not in campi_letti]
        if len(spese_incomplete) == 1 and sum(f.campo == "spese_sentenza" for f in precedenti) == 1:
            precedente = spese_incomplete[0]
            for fatto in estratti:
                if (fatto.campo == "spese_sentenza" and ";importo=" in fatto.valore
                        and fatto.valore.split(";")[0] == precedente.valore.split(";")[0]):
                    precedenti.remove(precedente)
                    nuovi.append(fatto)
                    break
        precedenti = [f for f in precedenti if f.campo != CAMPO_CONTROLLO]
        if nuovi:
            esito["recuperate"] += 1
        nuovi.append(Fatto(categoria="evento", campo=CAMPO_CONTROLLO, valore=VERSIONE_ESTRAZIONE_ESITO,
                           valore_letto="dispositivo controllato", etichetta="Controllo del dispositivo",
                           contesto="", posizione=0, origine="indice", verifica="verificata", confidenza=1.0,
                           prove=[{"codice": "controllo", "esito": "ok", "dettaglio": "recupero puntuale dell'esito"}]))
        registro.registra_fatti(tenant, fid, oggetto, "documenti", [*precedenti, *_attribuisci(nuovi, oggetto, "documenti")],
                                versione=lettura.versione_lettore)
    if esito["recuperate"]:
        logger.info("Esito recuperato per %s sentenze del fascicolo %s", esito["recuperate"], fid)
    return esito


def registra_scadenze_precedenti_alla_decisione(fascicolo: Any, registro: Any, tenant: str) -> int:
    """Riconcilia i termini del grado deciso con il dispositivo già letto."""
    from pct.scadenze_superate_sentenza import dispositivo_conclusivo, segnala_scadenze_superate
    from web.helpers import get_scadenziario

    fid = str(getattr(fascicolo, "id", "") or "")
    numero = str(getattr(fascicolo, "numero_rg", "") or "").strip().lstrip("0")
    anno = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    if not fid or not numero or not anno:
        return 0
    ufficiali = {
        str(doc.id) for doc in getattr(fascicolo, "documenti", [])
        if str(getattr(doc, "fonte_documento", "") or "").startswith(("PEC_CANCELLERIA", "PST", "POLISWEB"))
    }
    if not ufficiali:
        return 0
    ruoli = {
        fatto.oggetto_id for fatto in registro.fatti(tenant, fid, campo="numero_ruolo", verifiche=("verificata", "corretta"))
        if "/".join(val.strip().lstrip("0") for val in str(fatto.valore or "").split("/")[:2]) == f"{numero}/{anno}"
    }
    documenti = ufficiali & ruoli
    if not documenti:
        return 0
    impronte = {
        voce.oggetto_id: voce.impronta
        for voce in registro.oggetti(tenant, fid) if voce.tipo == "documento" and voce.presente and voce.oggetto_id in documenti
    }
    conclusioni = {}
    decisioni = {}
    for fatto in registro.fatti(tenant, fid, categoria="evento", verifiche=("verificata", "corretta")):
        if fatto.tipo != "documento" or not fatto.sha256 or fatto.sha256 != impronte.get(fatto.oggetto_id):
            continue
        if fatto.campo == "esito_sentenza" and dispositivo_conclusivo(str(fatto.contesto or "")):
            conclusioni[fatto.oggetto_id] = fatto
        elif fatto.campo == "data_decisione_sentenza":
            decisioni[fatto.oggetto_id] = str(fatto.valore or "").strip()
    date = {decisioni[doc] for doc in conclusioni.keys() & decisioni.keys()}
    if len(date) != 1 or "" in date:
        return 0
    giorno = next(iter(date))
    originale = min(doc for doc in conclusioni if decisioni.get(doc) == giorno)
    return segnala_scadenze_superate(
        get_scadenziario(), fascicolo_id=fid, giorno_sentenza=giorno,
        origine=f"dispositivo verificato nel documento {originale}", documento_conclusivo=originale,
    )


__all__ = ["CAMPO_CONTROLLO", "accoda_liquidazioni_incomplete", "recupera_esiti", "registra_scadenze_precedenti_alla_decisione"]
