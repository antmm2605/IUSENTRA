"""Il quadro del fascicolo (``GET /api/v1/ui/fascicoli/<id>/quadro``): raccolta dei dati già materializzati.

Fonti, tutte già calcolate e mai riletture di documenti (regola «Registro delle letture»):
- stato della pratica: il record del fascicolo (``pct/fascicolo_stato_pratica.py``), lo stesso della Lettura;
- prossimo passo: la Lettura del fascicolo se è già pronta nella sua cache; altrimenti il passo del conto economico;
- termini: scadenziario (scadenze aperte del fascicolo) e udienze in attesa del fascicolo, solo future;
- economia: il conto economico, con lo stato unico del contributo unificato;
- notifiche: la sintesi degli obblighi di notifica salvata dal giro in sfondo (``obblighi_notifica_sintesi``);
- documenti e PEC: documenti del fascicolo, voci del catalogo, PEC collegate e collegamenti da confermare.
Ogni fonte che manca diventa una frase onesta («da verificare»): il quadro non risponde mai con un errore 500.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _sicuro(funzione: Callable[[], Any], ripiego: Any, cosa: str) -> Any:
    try:
        return funzione()
    except Exception as exc:  # una fonte assente non ferma il quadro
        logger.warning("Quadro del fascicolo: %s non disponibile (%s)", cosa, exc)
        return ripiego


def lettura_in_cache(fascicolo_id: str) -> dict[str, Any] | None:
    """La Lettura già pronta (stessa chiave della scheda), senza mai calcolarla qui."""
    from web.blueprints.api_v1_react import _LETTURA_CACHE, _lettura_cache_key

    grezzo = _LETTURA_CACHE.get(_lettura_cache_key(fascicolo_id))
    if not grezzo:
        return None
    lettura = (json.loads(grezzo) or {}).get("lettura")
    return lettura if isinstance(lettura, dict) else None


def termini_futuri(fascicolo: Any) -> list[dict[str, str]]:
    from pct.fascicolo_document_presidio import is_identity_expiry_observation
    from web.helpers import get_scadenziario

    fid = _testo(getattr(fascicolo, "id", ""))
    termini = [{"data": _testo(s.data_scadenza)[:10], "titolo": _testo(s.titolo), "tipo": "scadenza"}
               for s in get_scadenziario().tutte(id_fascicolo=fid, solo_aperte=True)]
    for attivita in getattr(fascicolo, "attivita", []) or []:
        if _testo(getattr(attivita, "esito", "")).upper() != "IN_ATTESA" or is_identity_expiry_observation(attivita):
            continue
        tipo = "udienza" if _testo(getattr(attivita, "tipo", "")).upper() == "UDIENZA" else "scadenza"
        termini.append({"data": _testo(getattr(attivita, "data", ""))[:10], "titolo": _testo(getattr(attivita, "titolo", "")), "tipo": tipo})
    return termini


def documenti_da_classificare(fascicolo: Any) -> int:
    """Documenti senza voce di catalogo attiva o con la voce da rivedere."""
    from web.services.document_intelligence_runtime import build_document_ai_repository, document_ai_tenant_id

    fid = _testo(getattr(fascicolo, "id", ""))
    stati = build_document_ai_repository().catalog_status_by_document(document_ai_tenant_id(), fid)
    return sum(1 for d in getattr(fascicolo, "documenti", []) or []
               if stati.get(_testo(getattr(d, "id", "")), "review_required") == "review_required")


def conteggio_pec_fascicolo(fascicolo: Any, lettura: dict[str, Any] | None) -> dict[str, Any]:
    from pct.fascicolo_pec_conteggio import conteggio_pec
    from web.services.fascicolo_lettura_verifiche import leggi_registro

    if lettura and isinstance((lettura.get("pec") or {}).get("conteggio"), dict):
        return dict(lettura["pec"]["conteggio"])
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    fid = _testo(getattr(fascicolo, "id", ""))
    collegate = sum(1 for o in registro_corrente().oggetti(tenant_corrente(), fid) if getattr(o, "tipo", "") == "pec" and getattr(o, "presente", True))
    pec_letto = (lettura or {}).get("pec") or {"totale": collegate, "da_controllare": []}
    return conteggio_pec(pec_letto, leggi_registro(fid))


def quadro_fascicolo(fascicolo: Any) -> dict[str, Any]:
    from pct.fascicolo_quadro import riga_documenti, riga_economia, riga_notifiche, riga_prossimo_passo, riga_termini
    from pct.fascicolo_stato_pratica import stato_pratica_da_fascicolo
    from web.services.fascicolo_conto_economico_runtime import conto_economico_fascicolo
    from web.services.obblighi_notifica_sintesi import leggi as sintesi_obblighi

    fid = _testo(getattr(fascicolo, "id", ""))
    oggi = datetime.now(ROME_TZ).date()
    stato = _sicuro(lambda: stato_pratica_da_fascicolo(fascicolo),
                    {"codice": "in_corso", "etichetta": "Stato da verificare", "dettaglio": ""}, "stato della pratica")
    lettura = _sicuro(lambda: lettura_in_cache(fid), None, "Lettura in cache")
    conto = _sicuro(lambda: conto_economico_fascicolo(fid), {}, "conto economico") or {}
    righe_conto = list(conto.get("righe") or [])
    contributo = next((r.get("statoContributo") for r in righe_conto if r.get("voce") == "contributo_unificato"), None)
    prossimo_economico = _testo((conto.get("percorso") or {}).get("prossimoPasso"))
    passi = lettura.get("prossimi_passi") if lettura else None
    ripiego = f"Dal conto economico: {prossimo_economico}" if prossimo_economico and stato["codice"] != "in_corso" else ""
    sintesi = _sicuro(lambda: sintesi_obblighi(fid), None, "obblighi di notifica")
    pec = _sicuro(lambda: conteggio_pec_fascicolo(fascicolo, lettura), {"collegate": 0, "da_confermare": 0}, "conteggio PEC")
    righe = [
        riga_prossimo_passo(list(passi) if isinstance(passi, list) else None, ripiego=ripiego),
        riga_termini(_sicuro(lambda: termini_futuri(fascicolo), [], "termini"), oggi=oggi),
        # Il passo economico già usato come prossimo passo non si ripete nella riga dell'economia.
        riga_economia(contributo, righe_conto, "" if ripiego and not passi else prossimo_economico),
        riga_notifiche(None if sintesi is None else list(sintesi.get("obblighi") or []), oggi=oggi),
        riga_documenti(len(getattr(fascicolo, "documenti", []) or []),
                       _sicuro(lambda: documenti_da_classificare(fascicolo), None, "catalogo"), pec),
    ]
    if not conto:
        righe[2] = {**righe[2], "testo": "Economia da verificare: il conto economico non è disponibile in questo momento.",
                    "livello": "info"}
    return {"ok": True, "stato": stato, "righe": righe, "generato_il": datetime.now(ROME_TZ).replace(microsecond=0).isoformat()}


__all__ = ["conteggio_pec_fascicolo", "documenti_da_classificare", "lettura_in_cache", "quadro_fascicolo", "termini_futuri"]
