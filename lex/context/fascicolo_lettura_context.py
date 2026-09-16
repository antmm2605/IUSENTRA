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
from web.services.fascicolo_pec_presidio import messaggi_pec_per_fascicolo

from .document_context import load_document_context
from .fascicolo_sections_context import _agenda_fascicolo_rows, _serialize_appuntamento, _serialize_attivita, _serialize_scadenza
from .operational_context import _float_value, _serialize_parcella

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
    dati["archivio_pronto"] = bool(getattr(fascicolo, "archivio_pronto", False))
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


def _contesto_di_sistema() -> dict[str, Any]:
    return {"user": None, "user_id": "lettura-fascicolo", "skip_permission_check": True}


def _archivio_completo(archivio: dict[str, Any]) -> bool:
    return bool(((archivio or {}).get("stato") or {}).get("completa"))


def _documento_leggero(documento: Any) -> dict[str, Any]:
    identificativo = _clean(getattr(documento, "id", "") or getattr(documento, "document_id", ""))
    nome = _clean(
        getattr(documento, "nome", "")
        or getattr(documento, "nome_file", "")
        or getattr(documento, "filename", "")
        or getattr(documento, "titolo", "")
        or identificativo
    )
    return {
        "id": identificativo,
        "nome": nome,
        "tipo": _enum(getattr(documento, "tipo", "")) or "Documento",
        "data_documento": _clean(getattr(documento, "data_documento", "") or getattr(documento, "data_caricamento", "") or getattr(documento, "creato_il", ""))[:10],
        "data_caricamento": _clean(getattr(documento, "data_caricamento", "") or getattr(documento, "creato_il", ""))[:10],
        "firmato": bool(getattr(documento, "firmato", False)),
        "lex_read": True,
        "id_deposito_pct": _clean(getattr(documento, "id_deposito_pct", "")),
    }


def _catalogo_da_archivio(documenti: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalogo: list[dict[str, Any]] = []
    for documento in documenti:
        identificativo = _clean(documento.get("id"))
        if not identificativo:
            continue
        tipo = _clean(documento.get("tipo")).replace("_", " ").title() or "Documento"
        catalogo.append({
            "document_id": identificativo,
            "indexed": True,
            "supported": True,
            "document_label": tipo,
            "document_section": "allegati",
            "document_nature": "",
            "status": "confirmed",
            "confidence": 100,
            "legal_area": "",
        })
    return catalogo


def _catalogo(fascicolo_id: str) -> list[dict[str, Any]]:
    """Il catalogo dal contenuto, documento per documento, con il flag «letto dal presidio» (indexed)."""
    try:
        from flask import has_app_context

        if not has_app_context():
            return []
        from web.services.document_intelligence_runtime import build_document_catalog_payload

        payload = build_document_catalog_payload(fascicolo_id, process=False, user_context=_contesto_di_sistema())
    except Exception:
        return []
    righe: list[dict[str, Any]] = []
    visti: set[str] = set()
    for voce in list(payload.get("documents") or []):
        identificativo = _clean(voce.get("document_id"))
        if not identificativo or identificativo in visti:
            continue
        visti.add(identificativo)
        assegnazione = voce.get("assignment") if isinstance(voce.get("assignment"), dict) else {}
        righe.append({
            "document_id": identificativo,
            "indexed": bool(voce.get("indexed")),
            "supported": bool(voce.get("supported", True)),
            "document_label": _clean(assegnazione.get("document_label")),
            "document_section": _clean(assegnazione.get("document_section")),
            "document_nature": _clean(assegnazione.get("document_nature")),
            "status": _clean(assegnazione.get("status")),
            "confidence": int(assegnazione.get("confidence") or 0),
            "legal_area": _clean(assegnazione.get("legal_area")),
        })
    return righe


def _documenti_non_scaricati(fascicolo_id: str) -> list[str]:
    """I nomi dei documenti censiti dal portale ma non presenti nel fascicolo (il presidio non può leggerli)."""
    try:
        from flask import has_app_context

        if not has_app_context():
            return []
        from web.services.document_intelligence_runtime import build_lex_indexing_summary_payload

        riepilogo = build_lex_indexing_summary_payload(fascicolo_id, process=False, user_context=_contesto_di_sistema(), apply_automations=False)
    except Exception:
        return []
    nomi: list[str] = []
    for avviso in list(riepilogo.get("warnings") or []):
        testo = str(avviso or "")
        if "No such file" in testo or "non trovato" in testo.lower():
            nomi.append(testo.split(":", 1)[0].strip())
    return nomi


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
    # I documenti richiesti dal profilo e non ancora presenti: sono i «mancanti» della conformità.
    mancanti = []
    for slot in list(payload.get("documentSlots") or []):
        if not isinstance(slot, dict):
            continue
        stato = _clean(slot.get("status") or slot.get("state")).lower()
        if stato in {"missing", "mancante", "required", "richiesto", "da_acquisire"} or (slot.get("required") and not slot.get("present")):
            etichetta = _clean(slot.get("label") or slot.get("title") or slot.get("name"))
            if etichetta:
                mancanti.append({"label": etichetta})
    return {
        "operational_state": _clean(testata.get("operationalState") or payload.get("page_state")),
        "page_state": _clean(payload.get("page_state")),
        "next_action": _clean(testata.get("nextAction") or (payload.get("message") if payload.get("page_state") != "profilo_da_confermare" else "")),
        "completion": int(testata.get("completion") or 0),
        "blockers": blocchi,
        "missing_documents": mancanti,
    }


def _economico(fascicolo_id: str) -> dict[str, Any]:
    """Il quadro economico del fascicolo senza la ricerca semantica dei preventivi (che costa mezzo secondo)."""
    try:
        gestore_preventivi = get_preventivi_readonly()
        preventivi = list(gestore_preventivi.preventivi_per_fascicolo(fascicolo_id))
        conferimenti = list(gestore_preventivi.conferimenti_per_fascicolo(fascicolo_id))
    except Exception:
        preventivi, conferimenti = [], []
    try:
        parcelle = list(get_fatturazione().per_fascicolo(fascicolo_id))
    except Exception:
        parcelle = []
    attive = [voce for voce in parcelle if _enum(getattr(voce, "stato", "")).upper() not in {"BOZZA", "ANNULLATA"}]
    fatturato = round(sum(_float_value(getattr(voce, "totale", 0.0)) for voce in attive), 2)
    incassato = round(sum(_float_value(getattr(voce, "totale", 0.0)) for voce in attive if _enum(getattr(voce, "stato", "")).upper() == "PAGATA"), 2)
    # Il presidio economico del fascicolo (controllo pagamenti: contributo unificato,
    # spese, liquidazione del giudice letta dalla sentenza, parcella) e il contesto
    # delle sentenze economiche: sono la stessa fonte della pagina del fascicolo.
    presidio: dict[str, Any] = {}
    sentenze: dict[str, Any] = {}
    try:
        from web.services.react_fascicoli_bridge import _sentenze_economiche, payment_summary_for_fascicolo_fast

        fascicolo = get_fascicoli().get(fascicolo_id)
        if fascicolo is not None:
            presidio = dict(payment_summary_for_fascicolo_fast(fascicolo, parcelle=parcelle) or {})
            sentenze = dict(_sentenze_economiche(fascicolo_id, presidio) or {})
    except Exception:
        presidio, sentenze = {}, {}
    return {
        "presidio": presidio,
        "sentenze": sentenze,
        "summary": {
            "preventivi_count": len(preventivi),
            "conferimenti_count": len(conferimenti),
            "parcelle_count": len(parcelle),
            "totale_preventivato": round(sum(_float_value(getattr(voce, "totale", 0.0)) for voce in preventivi), 2),
            "totale_conferito": round(sum(_float_value(getattr(voce, "compenso_pattuito", getattr(voce, "onorario_pattuito", 0.0))) for voce in conferimenti), 2),
            "totale_fatturato": fatturato,
            "totale_incassato": incassato,
            "saldo_aperto": round(max(fatturato - incassato, 0.0), 2),
        },
        "parcelle": [{**_serialize_parcella(voce), "metodo_pagamento": _enum(getattr(voce, "metodo_pagamento", ""))} for voce in attive],
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
    archivio = _sicuro(lambda: _archivio(fascicolo), {})
    if _archivio_completo(archivio):
        documenti = [_documento_leggero(voce) for voce in list(getattr(fascicolo, "documenti", []) or [])]
        catalogo = _catalogo_da_archivio(documenti)
    else:
        documenti = [dict(voce) for voce in list(_sicuro(lambda: load_document_context(fascicolo_id=target, limit=None), []) or [])]
        catalogo = _catalogo(target)
    verifiche = _verifiche(target)
    # I documenti censiti dal portale ma non scaricati: dagli avvisi dell'indice o dall'ultima verifica automatica.
    if not _archivio_completo(archivio):
        non_scaricati = set(_documenti_non_scaricati(target)) | {
            _clean(nome) for nome in list(((verifiche.get("esiti") or {}).get("documenti") or {}).get("non_scaricati") or [])
        }
        for voce in documenti:
            voce["da_acquisire"] = _clean(voce.get("nome")) in non_scaricati
    regia = _regia(target)
    return DatiLettura(
        fascicolo=_fascicolo_dict(fascicolo),
        documenti=list(documenti or []),
        catalogo=catalogo,
        attivita=[_serialize_attivita(voce) for voce in list(getattr(fascicolo, "attivita", []) or [])],
        depositi=[_deposito_dict(voce) for voce in list(getattr(fascicolo, "depositi_pct", []) or [])],
        notifiche=_presidi_notifiche(target),
        scadenze=_sicuro(lambda: [_serialize_scadenza(voce) for voce in get_scadenziario().tutte(id_fascicolo=target, solo_aperte=False)], []),
        appuntamenti=_sicuro(lambda: [_serialize_appuntamento(voce) for voce in _agenda_fascicolo_rows(target, fascicolo)], []),
        # La conformità completa costa mezzo secondo per fascicolo: i documenti
        # mancanti arrivano dalla regia, che li calcola già; i blocchi sono i suoi.
        conformita={"missing_documents": list(regia.get("missing_documents") or [])},
        regia=regia,
        economico=_economico(target),
        parti=_parti(target),
        pec=_sicuro(lambda: messaggi_pec_per_fascicolo(fascicolo), []),
        verifiche=verifiche,
        archivio=archivio,
    )


def _archivio(fascicolo: Any) -> dict[str, Any]:
    """L'archivio delle letture come lo espone la lettura: mai una lettura, solo ciò che i motori hanno già collaudato."""
    from pct.archivio_letture import eventi_letti, riassunto_archivio, ruoli_letti, udienze_e_termini
    from web.services.archivio_letture_runtime import fatti_fascicolo, stato_archivio_payload

    fatti = fatti_fascicolo(fascicolo, verifiche=None)
    stato = stato_archivio_payload(fascicolo)
    return {
        "riassunto": riassunto_archivio(fatti),
        "azioni": udienze_e_termini(fatti),
        "eventi": eventi_letti(fatti),
        "ruoli": ruoli_letti(fatti),
        "stato": dict(stato.get("lettura_automatica") or {}),
        "collaudo": dict(stato.get("collaudo_lettore") or {}),
    }


def _verifiche(fascicolo_id: str) -> dict[str, Any]:
    try:
        from flask import current_app, g, has_app_context

        if not has_app_context():
            return {}
        from web.services.fascicolo_lettura_verifiche import leggi_registro

        return leggi_registro(fascicolo_id, paths=dict(getattr(g, "data_paths", {}) or {}), config=current_app.config)
    except Exception:
        return {}


def load_fascicolo_lettura_context(*, pratica_id: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    """La lettura completa del fascicolo, o un dizionario vuoto se non c'è."""
    dati = raccogli_dati_lettura(_clean(pratica_id) or _clean(fascicolo_id))
    if dati is None:
        return {}
    return lettura_come_payload(costruisci_lettura(dati))


__all__ = ["load_fascicolo_lettura_context", "raccogli_dati_lettura"]
