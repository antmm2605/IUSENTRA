"""Il risultato degli obblighi di notifica condiviso da Quadro, pannello e scadenziario.

Il motore conserva il risultato integrale con l'impronta delle fonti e la
sintesi usata dal Quadro. Le vecchie righe con la sola sintesi restano leggibili
finché il ciclo del fascicolo non consegna il risultato integrale.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from flask import g, has_request_context

logger = logging.getLogger(__name__)

CHIAVE = "obblighi-notifica-sintesi:v1"
DURATA = timedelta(days=30)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def compatta(obblighi: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Conserva i campi necessari a mostrare gli obblighi senza nuovi calcoli."""
    return [{"atto": _testo(o.get("etichetta") or o.get("atti") or o.get("documento")), "stato": _testo(o.get("stato")),
             "scadenza": _testo(o.get("scadenza"))[:10],
             **({"natura": "ordinatorio", "termine_da_verificare": any(
                    dato.get("campo") in {"udienza", "notifica_estero", "sospensione_feriale"}
                    for dato in o.get("dati_mancanti") or ())}
                if o.get("natura") == "ordinatorio" else {}),
             **({"regola": "sentenza_notifica_breve",
                 "documenti": sorted({oid for f in [o, *(o.get("fonti_documentali") or [])]
                                      if (oid := _testo(f.get("documentoId")))})}
                if o.get("regola") == "sentenza_notifica_breve" else {}),
             # I termini che nascono dalla sentenza notificata (pct.sentenza_notificata): breve, giudicato, art. 14 D.L. 669/1996.
             **({"termini": termini} if (termini := [{"codice": _testo(c.get("codice")), "deadline": _testo(c.get("deadline"))[:10],
                                                     "precetto_dal": _testo(c.get("precetto_dal"))[:10], "norma": _testo(c.get("norma"))}
                                                    for c in o.get("calcoli") or [] if c.get("codice")]) else {})}
            for o in obblighi if _testo(o.get("etichetta") or o.get("atti"))]


def valuta(fascicolo: Any) -> list[dict[str, Any]]:
    """Riusa il calcolo corrente o prepara una volta il risultato dalle fonti SQL."""
    from web.services.obblighi_notifica_fonti import impronta, riferimento_corrente
    from web.services.obblighi_notifica_runtime import obblighi_fascicolo

    fid = _testo(fascicolo.id)
    riferimento = riferimento_corrente(fid)
    record = _leggi_record(fid)
    pronto = _dettaglio(record) if record and riferimento and record.get("riferimento") == riferimento else None
    if pronto is not None:
        g._obblighi_in_calcolo = (fid, riferimento, record["impronta"], pronto)
        return pronto

    revisione = impronta(fid) if riferimento else None
    precedente = _dettaglio(record) if record and revisione and record.get("impronta") == revisione else None
    obblighi = precedente if precedente is not None else obblighi_fascicolo(fascicolo, rigoroso=bool(revisione))
    if riferimento and revisione:
        g._obblighi_in_calcolo = (fid, riferimento, revisione, obblighi)
    return obblighi


def salva(fascicolo_id: str, obblighi: Iterable[Mapping[str, Any]]) -> None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        scade = (datetime.now(timezone.utc) + DURATA).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        fid = _testo(fascicolo_id)
        valutati = g.get("_obblighi_in_calcolo") if has_request_context() else None
        completo = {}
        if valutati and valutati[0] == fid and valutati[3] is obblighi:
            from web.services.obblighi_notifica_fonti import impronta, riferimento_corrente

            riferimento = riferimento_corrente(fid)
            if not riferimento:
                return
            if riferimento != valutati[1]:
                if impronta(fid) != valutati[2] or riferimento_corrente(fid) != riferimento:
                    return  # una fonte è cambiata durante la valutazione
            esistente = _leggi_record(fid)
            if esistente and esistente.get("riferimento") == riferimento and _dettaglio(esistente) == obblighi:
                return
            completo = {"riferimento": riferimento, "impronta": valutati[2], "dettaglio": obblighi}
        payload = json.dumps({"obblighi": compatta(obblighi),
                              "calcolata_il": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                              **completo}, ensure_ascii=False)
        registro_corrente().payload_cache_set(tenant_corrente(), fid, CHIAVE, payload, expires_at=scade)
    except Exception as exc:  # la sintesi è un'accelerazione: il calcolo resta valido anche senza
        logger.debug("Sintesi degli obblighi di notifica non salvata per %s: %s", fascicolo_id, exc)


def _integra_identita(sintesi: dict[str, Any], fascicolo_id: str) -> dict[str, Any]:
    obblighi = sintesi.get("obblighi") or []
    if not any(voce.get("atto") == "Sentenza" and not voce.get("regola") for voce in obblighi):
        return sintesi

    from web.services.pannelli_pronti_runtime import voce_del_profilo

    voce = voce_del_profilo(fascicolo_id, "obblighi-notifica", precedente=True)
    if voce is None or not sintesi.get("calcolata_il"):
        return sintesi
    # La sintesi è scritta prima del payload integrale dalla stessa vista.
    # Lo scarto ammette l'arrotondamento ai secondi del registro.
    sintetizzata = datetime.fromisoformat(sintesi["calcolata_il"])
    archiviata = datetime.fromisoformat(voce.calcolato_il)
    if not timedelta(0) <= archiviata - sintetizzata <= timedelta(seconds=2):
        return sintesi
    completo = json.loads(voce.corpo) if voce.corpo else {}
    if not completo.get("ok") or not isinstance(completo.get("obblighi"), list):
        return sintesi
    proposta = compatta(completo["obblighi"])
    # Recupera soltanto l'identità da una proiezione dello stesso profilo che
    # concorda con tutti gli stati, le date e i calcoli già salvati.
    campi_identita = {"regola", "documenti"}
    ridotta = [{k: v for k, v in voce.items() if k not in campi_identita} for voce in proposta]
    if ridotta == obblighi:
        return {**sintesi, "obblighi": proposta}
    return sintesi


def _dettaglio(record: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if record is not None and record.get("impronta") and isinstance(record.get("dettaglio"), list):
        return record["dettaglio"]
    return None


def leggi_completi(fascicolo_id: str) -> list[dict[str, Any]] | None:
    """Solo il risultato integrale ancorato alle fonti attuali, anche quando è vuoto."""
    from web.services.obblighi_notifica_fonti import riferimento_corrente

    record = _leggi_record(fascicolo_id)
    if record and record.get("riferimento") and record["riferimento"] == riferimento_corrente(fascicolo_id):
        return _dettaglio(record)
    return None


def _leggi_record(fascicolo_id: str) -> dict[str, Any] | None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        grezzo = registro_corrente().payload_cache_get(tenant_corrente(), _testo(fascicolo_id), CHIAVE)
        record = json.loads(grezzo) if grezzo else None
        return record if isinstance(record, dict) else None
    except Exception as exc:
        logger.debug("Obblighi di notifica non leggibili per %s: %s", fascicolo_id, exc)
        return None


def leggi(fascicolo_id: str) -> dict[str, Any] | None:
    record = _leggi_record(fascicolo_id)
    if record is None:
        return None
    sintesi = {k: v for k, v in record.items() if k not in {"impronta", "riferimento", "dettaglio"}}
    if record.get("impronta"):
        from web.services.obblighi_notifica_fonti import riferimento_corrente

        riferimento = record.get("riferimento")
        if not riferimento or riferimento != riferimento_corrente(fascicolo_id):
            return None
        dettaglio = _dettaglio(record)
        if dettaglio is not None and any(o.get("natura") == "ordinatorio" for o in dettaglio):
            return {**sintesi, "obblighi": compatta(dettaglio)}
        return sintesi
    try:
        return _integra_identita(sintesi, fascicolo_id)
    except (TypeError, ValueError, AttributeError):
        return sintesi


__all__ = ["CHIAVE", "compatta", "leggi", "leggi_completi", "salva", "valuta"]
