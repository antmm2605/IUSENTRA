"""Raccoglie dal gestionale tutto ciò che serve alla lettura del fascicolo.

La lettura (`pct.fascicolo_lettura`) lavora su dati semplici. Qui, e solo qui,
si va a prenderli dove vivono: il fascicolo e i suoi depositi, le attività, i
documenti con il testo indicizzato e il catalogo dal contenuto, i presidi
delle notifiche, scadenze e agenda, la conformità, la regia operativa e il
quadro economico. Ogni sorgente è facoltativa: se una non risponde, la lettura
si fa con le altre e lo dichiara nelle lacune, invece di fallire.
"""

from __future__ import annotations

from typing import Any

from pct.fascicolo_lettura import DatiLettura, costruisci_lettura, lettura_come_payload
from web.helpers import get_clienti, get_fascicoli, get_fatturazione, get_practice_engine, get_preventivi_readonly, get_scadenziario, get_soggetti

from .document_context import load_document_context
from .fascicolo_sections_context import _agenda_fascicolo_rows, _serialize_appuntamento, _serialize_attivita, _serialize_scadenza
from .operational_context import load_economic_context, load_fascicolo_compliance_context

MASSIMO_PRESIDI = 50


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum(value: Any) -> str:
    return _clean(getattr(value, "value", value))


def _fascicolo_dict(fascicolo: Any) -> dict[str, Any]:
    campi = (
        "id", "numero", "titolo", "controparte", "oggetto", "tribunale", "giudice", "sezione", "numero_rg", "anno_rg",
        "tipo_procedimento", "area_pratica", "codice_oggetto_pst", "valore_causa", "data_apertura", "data_chiusura",
        "data_prima_udienza", "data_notifica_citazione", "data_prossima_udienza", "avvocato_referente",
        "canale_operativo", "source", "stato_pratica_operativa",
    )
    dati = {campo: getattr(fascicolo, campo, "") for campo in campi}
    dati["cliente"] = _clean(getattr(fascicolo, "nome_cliente", ""))
    dati["stato"] = _enum(getattr(fascicolo, "stato", ""))
    dati["tipo"] = _enum(getattr(fascicolo, "tipo", ""))
    return dati


def _deposito_dict(deposito: Any) -> dict[str, Any]:
    campi = (
        "id", "timestamp", "stato", "tipo_atto", "pec_destinatario", "messaggio", "ricevuta_accettazione",
        "ricevuta_consegna", "ricevuta_controlli_automatici", "esito_controlli", "ricevuta_cancelleria", "note",
        "nome_atto_principale", "id_deposito_esterno", "fonte_portale", "servizio_portale",
    )
    dati = {campo: getattr(deposito, campo, "") for campo in campi}
    dati["documenti_ids"] = list(getattr(deposito, "documenti_ids", []) or [])
    dati["titolo"] = _clean(getattr(deposito, "nome_atto_principale", "") or getattr(deposito, "tipo_atto", ""))
    return dati


def _catalogo(fascicolo_id: str) -> list[dict[str, Any]]:
    try:
        from flask import has_app_context

        if not has_app_context():
            return []
        from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

        assegnazioni = build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), fascicolo_id)
    except Exception:
        return []
    righe: list[dict[str, Any]] = []
    visti: set[str] = set()
    for voce in assegnazioni:
        identificativo = _clean(getattr(voce, "document_id", ""))
        if not identificativo or identificativo in visti:
            continue
        visti.add(identificativo)
        righe.append({
            "document_id": identificativo,
            "document_label": _clean(getattr(voce, "document_label", "")),
            "document_section": _clean(getattr(voce, "document_section", "")),
            "document_nature": _clean(getattr(voce, "document_nature", "")),
            "status": _clean(getattr(voce, "status", "")),
            "confidence": int(getattr(voce, "confidence", 0) or 0),
            "legal_area": _clean(getattr(voce, "legal_area", "")),
        })
    return righe


def _presidi_notifiche(fascicolo_id: str) -> list[dict[str, Any]]:
    try:
        from web.services.notification_presidia_payloads import build_presidia_list_payload
        from web.services.notification_presidia_runtime import build_notification_presidio_repository

        payload = build_presidia_list_payload(build_notification_presidio_repository(), {"fascicolo": fascicolo_id, "limit": MASSIMO_PRESIDI})
        return [dict(item) for item in list(payload.get("items") or [])]
    except Exception:
        return []


def _regia(fascicolo_id: str) -> dict[str, Any]:
    try:
        from web.services.react_practice_engine_bridge import build_react_practice_engine_payload

        payload = build_react_practice_engine_payload(
            fascicolo_id=fascicolo_id, get_fascicoli=get_fascicoli, get_clienti=get_clienti,
            get_preventivi=get_preventivi_readonly, get_fatturazione=get_fatturazione, get_practice_engine=get_practice_engine,
        )
    except Exception:
        return {}
    testata = dict(payload.get("header") or {})
    validazione = dict(payload.get("validation") or {})
    blocchi = []
    for voce in list(validazione.get("blockers") or []):
        if isinstance(voce, dict):
            blocchi.append({"message": _clean(voce.get("message")), "suggested_action": _clean(voce.get("suggestedAction") or voce.get("suggested_action"))})
        else:
            blocchi.append({"message": _clean(getattr(voce, "message", "")), "suggested_action": _clean(getattr(voce, "suggested_action", ""))})
    return {
        "operational_state": _clean(testata.get("operationalState") or payload.get("page_state")),
        "next_action": _clean(testata.get("nextAction") or payload.get("message")),
        "completion": int(testata.get("completion") or 0),
        "blockers": blocchi,
    }


def _parti(fascicolo_id: str) -> list[dict[str, Any]]:
    try:
        coppie = list(get_soggetti().parti_fascicolo(fascicolo_id))
    except Exception:
        return []
    righe: list[dict[str, Any]] = []
    for parte, soggetto in coppie:
        ruolo = _enum(getattr(parte, "ruolo", "") or getattr(parte, "qualifica", "") or getattr(parte, "tipo", ""))
        nome = _clean(getattr(soggetto, "nome_completo", "") or getattr(soggetto, "denominazione", "") or getattr(soggetto, "nome", ""))
        if nome:
            righe.append({"ruolo": ruolo.replace("_", " ").lower(), "nome": nome})
    return righe


def _sicuro(funzione, fallback):
    try:
        return funzione()
    except Exception:
        return fallback


def raccogli_dati_lettura(fascicolo_id: str) -> DatiLettura | None:
    target = _clean(fascicolo_id)
    if not target:
        return None
    fascicolo = _sicuro(lambda: get_fascicoli().get(target), None)
    if not fascicolo:
        return None
    documenti = _sicuro(lambda: load_document_context(fascicolo_id=target, limit=None), [])
    return DatiLettura(
        fascicolo=_fascicolo_dict(fascicolo),
        documenti=list(documenti or []),
        catalogo=_catalogo(target),
        attivita=[_serialize_attivita(voce) for voce in list(getattr(fascicolo, "attivita", []) or [])],
        depositi=[_deposito_dict(voce) for voce in list(getattr(fascicolo, "depositi_pct", []) or [])],
        notifiche=_presidi_notifiche(target),
        scadenze=_sicuro(lambda: [_serialize_scadenza(voce) for voce in get_scadenziario().tutte(id_fascicolo=target, solo_aperte=False)], []),
        appuntamenti=_sicuro(lambda: [_serialize_appuntamento(voce) for voce in _agenda_fascicolo_rows(target, fascicolo)], []),
        conformita=_sicuro(lambda: load_fascicolo_compliance_context(fascicolo_id=target), {}),
        regia=_regia(target),
        economico=_sicuro(lambda: load_economic_context(fascicolo_id=target), {}),
        parti=_parti(target),
    )


def load_fascicolo_lettura_context(*, pratica_id: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    """La lettura completa del fascicolo, o un dizionario vuoto se non c'è."""
    dati = raccogli_dati_lettura(_clean(pratica_id) or _clean(fascicolo_id))
    if dati is None:
        return {}
    return lettura_come_payload(costruisci_lettura(dati))


__all__ = ["load_fascicolo_lettura_context", "raccogli_dati_lettura"]
