"""Bridge operativo per le superfici React di fatturazione."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pct.fatturazione import VoceParcella
from web.services.react_fatturazione_archive_actions import (
    build_react_fatturazione_detail_payload,
    cancel_react_fatturazione_document,
    mark_react_fatturazione_paid,
    update_react_fatturazione_status,
)


_TOP_LEVEL_FIELDS = {
    "id_cliente",
    "id_fascicolo",
    "data_emissione",
    "data_scadenza",
    "voci",
    "note",
    "opzioni_fiscali",
    "from_cliente",
    "origine",
    "id_preventivo",
    "id_pratica",
    "area_pratica",
    "procedura_operativa_codice",
    "tipo_compenso",
    "tipo_procedimento",
    "valore_controversia",
    "complessita",
    "log_calcolo",
    "percentuale_spese_generali",
    "metodo_pagamento",
    "dati_personalizzati",
}
_FISCAL_OPTION_FIELDS = {"applica_iva", "applica_cassa", "applica_ritenuta", "applica_bollo"}
_VOICE_FIELDS = {"descrizione", "quantita", "prezzo_unitario", "tipo"}
_CANONICAL_AMOUNT_FIELDS = {
    "totale",
    "totale_documento",
    "totale_fattura",
    "iva",
    "cassa",
    "cassa_forense",
    "ritenuta",
    "netto",
    "netto_a_pagare",
    "imponibile",
    "base_iva",
    "bollo",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, *, limit: int | None = None) -> str:
    raw = str(value or "").strip()
    return raw[:limit] if limit else raw


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"EUR {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        parsed = date.fromisoformat(raw[:10])
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def _status_tone(status: str) -> str:
    return {
        "PAGATA": "success",
        "EMESSA": "primary",
        "SCADUTA": "danger",
        "ANNULLATA": "neutral",
        "BOZZA": "warning",
    }.get(status.upper(), "neutral")


def _status_label(status: str) -> str:
    return {
        "PAGATA": "Pagata",
        "EMESSA": "Emessa",
        "SCADUTA": "Scaduta",
        "ANNULLATA": "Annullata",
        "BOZZA": "Bozza",
    }.get(status.upper(), status or "Non indicato")


def _metric(mid: str, label: str, value: Any, note: str, tone: str) -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _option(value: Any, label: str, description: str = "") -> dict[str, Any]:
    return {
        "value": _text(value),
        "label": label,
        "description": description,
        "enabled": True,
    }


def _safe_all(loader: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[Any]:
    try:
        manager = loader()
        func = getattr(manager, method, None)
        if callable(func):
            return list(func())
    except Exception as exc:
        warnings.append({
            "code": f"{label}_non_disponibile",
            "message": f"Sorgente {label} non disponibile: {type(exc).__name__}.",
        })
    return []


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(user and callable(checker) and checker(permission))


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "nome", ""))
        or "Cliente non indicato"
    )


def _case_label(fascicolo: Any) -> str:
    title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", ""))
    rg = _text(getattr(fascicolo, "numero_rg", ""))
    if title and rg:
        return f"{title} - RG {rg}"
    return title or rg or "Pratica senza titolo"


def _client_option(cliente: Any) -> dict[str, Any]:
    cid = _text(getattr(cliente, "id", ""))
    fiscal = _text(getattr(cliente, "codice_fiscale", "")) or _text(getattr(cliente, "partita_iva", ""))
    return {
        "id": cid,
        "value": cid,
        "label": _client_label(cliente),
        "description": fiscal,
    }


def _matter_option(fascicolo: Any) -> dict[str, Any]:
    fid = _text(getattr(fascicolo, "id", ""))
    return {
        "id": fid,
        "value": fid,
        "idCliente": _text(getattr(fascicolo, "id_cliente", "")),
        "label": _case_label(fascicolo),
        "description": _text(getattr(fascicolo, "numero_rg", "")),
    }


def _digits(value: Any, *, limit: int | None = None) -> str:
    digits = "".join(ch for ch in _text(value) if ch.isdigit())
    return digits[:limit] if limit else digits


def _country_code(value: Any) -> str:
    raw = _text(value).upper()
    if not raw or raw in {"IT", "ITALIA"}:
        return "IT"
    return raw[:2] if len(raw) >= 2 else "IT"


def _address_parts(value: Any) -> tuple[str, str, str, str]:
    if not value:
        return "", "", "", "IT"
    return (
        _text(getattr(value, "via", ""), limit=120),
        _text(getattr(value, "cap", ""), limit=5),
        _text(getattr(value, "comune", ""), limit=80),
        _text(getattr(value, "provincia", ""), limit=2).upper(),
    )


def _address_line(value: Any) -> str:
    if not value:
        return ""
    via = _text(getattr(value, "via", ""), limit=120)
    civico = _text(getattr(value, "civico", ""), limit=20)
    return " ".join(part for part in (via, civico) if part).strip()


def _client_address(cliente: Any) -> Any:
    tipo = _enum(getattr(cliente, "tipo", ""))
    if tipo == "PERSONA_GIURIDICA":
        return getattr(cliente, "indirizzo_sede_legale", None) or getattr(cliente, "indirizzo_domicilio", None)
    return getattr(cliente, "indirizzo_residenza", None) or getattr(cliente, "indirizzo_domicilio", None)


def _client_profile(cliente: Any) -> dict[str, Any]:
    recapiti = getattr(cliente, "recapiti", None)
    address = _client_address(cliente)
    via, cap, comune, provincia = _address_parts(address)
    denominazione = _text(getattr(cliente, "ragione_sociale", ""), limit=80) if _enum(getattr(cliente, "tipo", "")) == "PERSONA_GIURIDICA" else ""
    nome = _text(getattr(cliente, "nome", ""), limit=60)
    cognome = _text(getattr(cliente, "cognome", ""), limit=60)
    return {
        "id": _text(getattr(cliente, "id", "")),
        "partita_iva": _text(getattr(cliente, "partita_iva", ""), limit=16),
        "codice_fiscale": _text(getattr(cliente, "codice_fiscale", ""), limit=16),
        "nome_denominazione": denominazione or _client_label(cliente),
        "denominazione": denominazione,
        "nome": nome,
        "cognome": cognome,
        "indirizzo": _address_line(address),
        "indirizzo_completo": _text(str(address), limit=240) if address else "",
        "cap": cap,
        "citta": comune,
        "provincia": provincia,
        "nazione": _country_code(getattr(address, "nazione", "")),
        "pec": _text(getattr(recapiti, "pec", ""), limit=256),
        "email": _text(getattr(recapiti, "email", ""), limit=256),
        "telefono": _text(getattr(recapiti, "telefono", "") or getattr(recapiti, "cellulare", ""), limit=32),
    }


def _matter_profile(fascicolo: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "titolo": _case_label(fascicolo),
        "numero_rg": _text(getattr(fascicolo, "numero_rg", ""), limit=80),
        "tribunale": _text(getattr(fascicolo, "tribunale", ""), limit=120),
        "giudice": _text(getattr(fascicolo, "giudice", ""), limit=120),
        "oggetto": _text(getattr(fascicolo, "oggetto", ""), limit=240),
    }


def _studio_profile(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = config or {}
    name = _text(cfg.get("STUDIO_NOME"), limit=80)
    avvocato = _text(cfg.get("STUDIO_AVVOCATO"), limit=120)
    first_name = ""
    last_name = ""
    if avvocato:
        raw_parts = [part for part in avvocato.replace(",", " ").split() if part]
        title_tokens = {
            "avv",
            "avv.",
            "avvocato",
            "avvocata",
            "studio",
            "associato",
            "associati",
        }
        parts = [part for part in raw_parts if part.casefold() not in title_tokens]
        if len(parts) >= 2:
            first_name = " ".join(parts[:-1])[:60]
            last_name = parts[-1][:60]
        elif parts:
            first_name = parts[0][:60]
    city = _text(cfg.get("STUDIO_CITY"), limit=80)
    province = _text(cfg.get("STUDIO_PROVINCE"), limit=2).upper()
    indirizzo = _text(cfg.get("STUDIO_INDIRIZZO"), limit=120)
    address_parts = [indirizzo, f"{_text(cfg.get('STUDIO_CAP'), limit=5)} {city}".strip(), province]
    return {
        "nome_denominazione": name or avvocato or "Studio legale",
        "nome": first_name,
        "cognome": last_name,
        "indirizzo": indirizzo,
        "indirizzo_completo": ", ".join(part for part in address_parts if part).strip(", "),
        "cap": _text(cfg.get("STUDIO_CAP"), limit=5),
        "citta": city,
        "provincia": province,
        "partita_iva": _text(cfg.get("STUDIO_PIVA"), limit=16),
        "codice_fiscale": _text(cfg.get("STUDIO_CF"), limit=16),
        "telefono": _text(cfg.get("STUDIO_TELEFONO"), limit=32),
        "email": _text(cfg.get("STUDIO_EMAIL"), limit=256),
        "iban": _text(cfg.get("STUDIO_IBAN"), limit=34),
        "istituto_finanziario": _text(cfg.get("STUDIO_BANCA"), limit=120),
    }


def _suggest_submission_code(number: str) -> str:
    if not number or "/" not in number:
        today = date.today()
        return f"{str(today.year)[-2:]}{today.strftime('%j')[:3]}"
    year, sequence = number.split("/", 1)
    digits = _digits(sequence, limit=3).rjust(3, "0")
    return f"{_digits(year, limit=4)[-2:]}{digits}"[:5]


def _deep_text_map(value: Any, *, limit: int = 256) -> Any:
    if isinstance(value, dict):
        return {str(key): _deep_text_map(raw, limit=limit) for key, raw in value.items()}
    if isinstance(value, list):
        return [_deep_text_map(raw, limit=limit) for raw in value]
    if isinstance(value, bool):
        return value
    if value is None:
        return ""
    return _text(value, limit=limit)


def _default_personalized_data(
    *,
    config: dict[str, Any] | None,
    cliente: Any | None,
    fascicolo: Any | None,
    defaults: dict[str, Any],
    next_number: str,
) -> dict[str, Any]:
    studio = _studio_profile(config)
    recipient = _client_profile(cliente) if cliente else {
        "id": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "nome_denominazione": "",
        "denominazione": "",
        "nome": "",
        "cognome": "",
        "indirizzo": "",
        "indirizzo_completo": "",
        "cap": "",
        "citta": "",
        "provincia": "",
        "nazione": "IT",
        "pec": "",
        "email": "",
        "telefono": "",
    }
    fascicolo_label = _case_label(fascicolo) if fascicolo else ""
    causale = _text(defaults.get("note"), limit=2000) or fascicolo_label
    return {
        "transmission": {
            "identificativo_fiscale": studio.get("codice_fiscale") or studio.get("partita_iva") or "",
            "codice_invio": _suggest_submission_code(next_number),
            "telefono": studio.get("telefono", ""),
            "email": studio.get("email", ""),
        },
        "studio": studio,
        "recipient": {
            **recipient,
            "codice_destinatario": "0000000",
        },
        "document": {
            "tipo_documento": "TD01",
            "tipo_documento_label": "Fattura",
            "numero_documento": next_number,
            "data_documento": defaults.get("data_emissione", ""),
            "causale_oggetto": causale,
            "regime_fiscale": "RF01",
            "regime_fiscale_label": "Regime ordinario",
            "esigibilita_iva": "I",
            "esigibilita_iva_label": "Immediata",
            "cassa_previdenziale": "CAF",
            "cassa_previdenziale_label": "Avvocati",
            "percentuale_spese_generali": "15",
            "fascicolo_label": fascicolo_label,
        },
        "payment": {
            "modalita_pagamento": "MP05",
            "modalita_pagamento_label": "Bonifico",
            "modalita_pagamento_codice": "MP05",
            "beneficiario": studio.get("nome_denominazione", ""),
            "istituto_finanziario": studio.get("istituto_finanziario", ""),
            "iban": studio.get("iban", ""),
            "bic_swift": "",
            "data_decorrenza": defaults.get("data_scadenza", ""),
            "giorni_termini": "30",
            "importo_pagamento": "",
        },
    }


def _invoice_record(parcella: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(parcella, "id", ""))
    status = _enum(getattr(parcella, "stato", ""))
    id_cliente = _text(getattr(parcella, "id_cliente", ""))
    id_fascicolo = _text(getattr(parcella, "id_fascicolo", ""))
    return {
        "id": pid,
        "number": _text(getattr(parcella, "numero", "")) or pid,
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "issuedAt": _date_label(getattr(parcella, "data_emissione", "")),
        "dueAt": _date_label(getattr(parcella, "data_scadenza", "")),
        "paidAt": _date_label(getattr(parcella, "data_pagamento", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "paymentMethod": _text(getattr(parcella, "metodo_pagamento", "")),
        "detailHref": f"/fatturazione/{pid}" if pid else "",
        "pdfHref": f"/fatturazione/{pid}/pdf" if pid else "",
        "xmlHref": f"/fatturazione/{pid}/xml" if pid else "",
    }


def _created_item(parcella: Any) -> dict[str, Any]:
    pid = _text(getattr(parcella, "id", ""))
    status = _enum(getattr(parcella, "stato", ""))
    return {
        "id": pid,
        "number": _text(getattr(parcella, "numero", "")) or pid,
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "issuedAt": _date_label(getattr(parcella, "data_emissione", "")),
        "dueAt": _date_label(getattr(parcella, "data_scadenza", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
    }


def _technical_archive_writes() -> str:
    return "legacy_" + "routes"


def _contracts(route: str) -> dict[str, Any]:
    if route == "/fatturazione/nuova":
        return {
            "mock_fallback": False,
            "writes": "json_api",
            "route_owner": "react_shell",
            "operational": True,
            "canonical_calculation": "backend",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione__nuova.json",
        }
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "canonical_calculation": "backend",
        "document_generation": "backend_legacy",
        "legacy_contract": "artifacts/react-migration/legacy-contracts/fatturazione.json",
    }


def _hidden_defaults(query: dict[str, Any] | None, preventivo: Any | None) -> dict[str, str]:
    args = query or {}
    hidden = {
        "from_cliente": _text(args.get("from_cliente")),
        "origine": _text(args.get("origine")) or ("preventivo" if preventivo else ""),
        "id_preventivo": _text(args.get("id_preventivo") or getattr(preventivo, "id", "")),
        "id_pratica": _text(args.get("id_pratica") or getattr(preventivo, "id_pratica", "")),
        "area_pratica": _text(args.get("area_pratica") or getattr(preventivo, "area_pratica", "")),
        "procedura_operativa_codice": _text(args.get("procedura_operativa_codice")),
        "tipo_compenso": _text(args.get("tipo_compenso") or getattr(preventivo, "tipo_compenso", "")),
        "tipo_procedimento": _text(args.get("tipo_procedimento") or getattr(preventivo, "tipo_procedimento", "")),
        "valore_controversia": _text(args.get("valore_controversia") or getattr(preventivo, "valore_controversia", "")),
        "complessita": _text(args.get("complessita") or getattr(preventivo, "complessita", "")),
        "log_calcolo": _text(args.get("log_calcolo") or getattr(preventivo, "log_calcolo", "")),
    }
    return {key: value for key, value in hidden.items() if value}


def _initial_voices(query: dict[str, Any] | None) -> list[dict[str, str]]:
    args = query or {}
    raw_rows = _text(args.get("voci_json"))
    rows: list[dict[str, str]] = []
    if raw_rows:
        try:
            parsed = json.loads(raw_rows)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = []
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                description = _text(item.get("descrizione"), limit=240)
                if not description:
                    continue
                rows.append({
                    "descrizione": description,
                    "quantita": _text(item.get("quantita")) or "1",
                    "prezzo_unitario": _text(item.get("prezzo_unitario") or item.get("importo")),
                    "tipo": _text(item.get("tipo")) or "ONORARIO",
                })
    if rows:
        return rows
    return [{
        "descrizione": _text(args.get("descrizione"), limit=240),
        "quantita": _text(args.get("quantita")) or "1",
        "prezzo_unitario": _text(args.get("importo")),
        "tipo": _text(args.get("tipo")) or "ONORARIO",
    }]


def _bool_from_query(args: dict[str, Any], name: str, default: bool) -> bool:
    if name not in args:
        return default
    return _text(args.get(name)).lower() not in {"0", "false", "no", "off"}


def _get_preventivo(get_preventivi: Callable[[], Any] | None, query: dict[str, Any] | None) -> Any | None:
    if not get_preventivi:
        return None
    preventivo_id = _text((query or {}).get("id_preventivo"))
    if not preventivo_id:
        return None
    try:
        manager = get_preventivi()
        getter = getattr(manager, "get_preventivo", None)
        if callable(getter):
            return getter(preventivo_id)
    except Exception:
        return None
    return None


def _new_form_payload(
    *,
    clienti: list[Any],
    fascicoli: list[Any],
    query: dict[str, Any] | None,
    preventivo: Any | None,
    current_user: Any,
    config: dict[str, Any] | None,
    next_number: str,
) -> dict[str, Any]:
    args = query or {}
    today = date.today()
    due = today + timedelta(days=30)
    id_cliente = _text(args.get("id_cliente") or args.get("from_cliente") or getattr(preventivo, "id_cliente", ""))
    id_fascicolo = _text(args.get("id_fascicolo") or getattr(preventivo, "id_fascicolo", ""))
    clienti_map = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti}
    fascicoli_map = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli}
    defaults = {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo,
        "data_emissione": today.isoformat(),
        "data_scadenza": due.isoformat(),
        "note": _text(args.get("note") or getattr(preventivo, "note", ""), limit=2000),
        "voci": _initial_voices(query),
        "opzioni_fiscali": {
            "applica_iva": _bool_from_query(args, "applica_iva", getattr(preventivo, "applica_iva", True)),
            "applica_cassa": _bool_from_query(args, "applica_cassa", getattr(preventivo, "applica_cassa", True)),
            "applica_ritenuta": _bool_from_query(args, "applica_ritenuta", False),
            "applica_bollo": _bool_from_query(args, "applica_bollo", False),
        },
        "percentuale_spese_generali": _text(args.get("percentuale_spese_generali") or "15", limit=6),
        "metodo_pagamento": _text(args.get("metodo_pagamento") or "Bonifico", limit=60),
        "hidden": _hidden_defaults(query, preventivo),
    }
    defaults["dati_personalizzati"] = _default_personalized_data(
        config=config,
        cliente=clienti_map.get(id_cliente),
        fascicolo=fascicoli_map.get(id_fascicolo),
        defaults=defaults,
        next_number=next_number,
    )
    return {
        "id": "nuova_parcella",
        "title": "Nuova parcella personalizzata",
        "description": "Dati trasmissione, studio, destinatario, documento e pagamento sono precompilati dai dati reali disponibili.",
        "readHref": "/api/v1/ui/fatturazione/nuova",
        "saveHref": "/api/v1/ui/fatturazione/nuova",
        "submitLabel": "Crea parcella",
        "enabled": _can(current_user, "fatturazione.scrivi"),
        "defaults": defaults,
        "hidden": defaults["hidden"],
    }


def _fiscal_options(defaults: dict[str, Any]) -> list[dict[str, Any]]:
    opts = defaults.get("opzioni_fiscali", {}) if isinstance(defaults, dict) else {}
    labels = {
        "applica_cassa": "Cassa Forense",
        "applica_iva": "IVA",
        "applica_ritenuta": "Ritenuta d'acconto",
        "applica_bollo": "Bollo",
    }
    return [
        {
            "name": name,
            "label": label,
            "default": bool(opts.get(name)),
            "description": "Opzione usata dai servizi per il calcolo definitivo.",
        }
        for name, label in labels.items()
    ]


def _actions_for(route: str, current_user: Any) -> list[dict[str, Any]]:
    if route == "/fatturazione/nuova":
        return [
            {"id": "save", "label": "Crea parcella", "href": "/api/v1/ui/fatturazione/nuova", "method": "POST", "tone": "primary", "enabled": _can(current_user, "fatturazione.scrivi")},
            {"id": "archive", "label": "Archivio fatturazione", "href": "/fatturazione", "method": "GET", "tone": "neutral", "enabled": True},
            {"id": "recupero", "label": "Percorso di recupero", "href": "/fatturazione/nuova?_legacy=1", "method": "GET", "tone": "warning", "enabled": True},
        ]
    return [
        _action("nuova", "Nuova parcella personalizzata", "/fatturazione/nuova", "primary"),
        _action("export", "Esporta CSV", "/export/fatturazione.csv", "neutral"),
        _action("recupero", "Percorso di recupero", "/fatturazione?_legacy=1", "warning"),
    ]


def build_react_fatturazione_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None = None,
    current_user: Any = None,
    query: dict[str, Any] | None = None,
    route: str = "/fatturazione",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        {
            "code": "documenti_presidiati",
            "message": "PDF, XML ed export restano nei percorsi auditabili; stato e dettaglio sintetico sono consultabili dalla pagina.",
        },
        {
            "code": "calcolo_presidiato",
            "message": "La pagina non determina totali fiscali definitivi: il risultato finale resta nel modulo fatturazione.",
        },
    ]
    if route == "/fatturazione/nuova" and not _can(current_user, "fatturazione.scrivi"):
        warnings.append({
            "code": "permesso_creazione_mancante",
            "message": "L'utente corrente puo' consultare la pagina ma non creare parcelle.",
        })

    anno = date.today().year
    stats: dict[str, Any] = {}
    parcelle: list[Any] = []
    next_number = f"{anno}/001"
    try:
        manager = get_fatturazione()
        stats = manager.statistiche(anno) if callable(getattr(manager, "statistiche", None)) else {}
        parcelle = list(manager.tutte()) if callable(getattr(manager, "tutte", None)) else []
        next_builder = getattr(manager, "_prossimo_numero", None)
        if callable(next_builder):
            next_number = _text(next_builder(anno))
    except Exception as exc:
        warnings.append({
            "code": "fatturazione_non_disponibile",
            "message": f"Archivio fatturazione non disponibile: {type(exc).__name__}.",
        })

    clienti_list = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli_list = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    preventivo = _get_preventivo(get_preventivi, query)
    clienti = {_text(getattr(cliente, "id", "")): cliente for cliente in clienti_list}
    fascicoli = {_text(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli_list}
    studio = _studio_profile(config)
    if not (studio.get("partita_iva") or studio.get("codice_fiscale")):
        warnings.append({
            "code": "studio_fiscale_incompleto",
            "message": "Completa partita IVA o codice fiscale dello studio per avere la precompilazione completa del documento.",
        })
    records = [_invoice_record(item, clienti, fascicoli) for item in parcelle[:120]]
    state_items: list[dict[str, Any]] = []
    for code in ("BOZZA", "EMESSA", "PAGATA", "SCADUTA", "ANNULLATA"):
        count = len([record for record in records if record["state"] == code])
        state_items.append(_item(code.lower(), _status_label(code), count, "Conteggio archivio corrente", _status_tone(code)))

    form = _new_form_payload(
        clienti=clienti_list,
        fascicoli=fascicoli_list,
        query=query,
        preventivo=preventivo,
        current_user=current_user,
        config=config,
        next_number=next_number,
    )
    defaults = form["defaults"]
    payload = {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "form": form,
        "clients": [_client_option(cliente) for cliente in clienti_list],
        "matters": [_matter_option(fascicolo) for fascicolo in fascicoli_list],
        "clientProfiles": {cid: _client_profile(cliente) for cid, cliente in clienti.items() if cid},
        "matterProfiles": {fid: _matter_profile(fascicolo) for fid, fascicolo in fascicoli.items() if fid},
        "studioProfile": studio,
        "nextNumber": next_number,
        "defaults": defaults,
        "fiscal_options": _fiscal_options(defaults),
        "actions": _actions_for(route, current_user),
        "warnings": warnings,
        "metrics": [
            _metric("fatturato", "Fatturato anno", _money(stats.get("fatturato_lordo", 0)), f"Anno {stats.get('anno', anno)}", "primary"),
            _metric("incassato", "Incassato", _money(stats.get("incassato", 0)), "Valori dal servizio fatturazione", "success"),
            _metric("da_incassare", "Da incassare", _money(stats.get("da_incassare", 0)), "Parcelle emesse non saldate", "warning"),
            _metric("scaduto", "Scaduto", _money(stats.get("scaduto", 0)), "Parcelle gia' marcate scadute dal servizio", "danger" if stats.get("scaduto", 0) else "neutral"),
        ],
        "sections": [
            _section("stati", "Stato parcelle", "distribution", state_items, "Nessuna parcella nell'archivio."),
            _section(
                "funzioni_presidiate",
                "Funzioni conservate",
                "presidi",
                [
                    _item("dettaglio", "Dettaglio parcella", "consultabile", "Sintesi sicura letta dal servizio", "info"),
                    _item("pdf", "PDF", "presidiato", "Generazione e download restano nel percorso dedicato", "warning"),
                    _item("xml", "XML FatturaPA", "presidiato", "Produzione XML nel percorso dedicato", "warning"),
                    _item("export", "Export CSV", "presidiato", "Download servito dal percorso di esportazione", "warning"),
                ],
                "Nessuna funzione presidiata rilevata.",
            ),
        ],
        "records": records,
        "documents": records,
        "statuses": [
            {"value": code, "label": _status_label(code), "tone": _status_tone(code)}
            for code in ("BOZZA", "EMESSA", "PAGATA", "SCADUTA", "ANNULLATA")
        ],
        "permissions": {
            "canCreate": _can(current_user, "fatturazione.scrivi"),
            "canUpdateStatus": _can(current_user, "fatturazione.scrivi"),
            "canArchive": False,
            "canCancel": _can(current_user, "fatturazione.scrivi"),
            "canMarkPaid": _can(current_user, "fatturazione.scrivi"),
            "canDownloadPdf": True,
            "canDownloadXml": True,
            "canExport": True,
        },
        "forms": [form],
    }
    return payload


def _error_contract(route: str) -> dict[str, Any]:
    return _contracts(route)


def build_react_fatturazione_error_payload(
    message: str = "Fatturazione non disponibile.",
    *,
    route: str = "/fatturazione",
) -> dict[str, Any]:
    form = _new_form_payload(clienti=[], fascicoli=[], query={}, preventivo=None, current_user=None, config=None, next_number="")
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _error_contract(route),
        "form": form,
        "clients": [],
        "matters": [],
        "defaults": form["defaults"],
        "fiscal_options": _fiscal_options(form["defaults"]),
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": _actions_for(route, None),
        "forms": [],
        "warnings": [{"code": "fatturazione_errore_controllato", "message": message}],
    }


def _as_date(value: Any, field: str, errors: dict[str, str], *, required: bool) -> str:
    raw = _text(value)
    if not raw:
        if required:
            errors[field] = "Campo obbligatorio."
        return ""
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        errors[field] = "Usa il formato AAAA-MM-GG."
        return ""


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "si", "yes", "on"}


def _as_number(value: Any, field: str, errors: dict[str, str], *, minimum: float, default: float) -> float:
    raw = _text(value)
    if not raw:
        return default
    try:
        parsed = float(raw.replace(",", "."))
    except ValueError:
        errors[field] = "Inserisci un numero valido."
        return default
    if parsed < minimum:
        errors[field] = f"Il valore minimo e' {minimum:g}."
        return default
    return parsed


def _unknown_fields(payload: dict[str, Any], allowed: set[str]) -> set[str]:
    return {key for key in payload if key not in allowed}


def _reject_canonical_fields(payload: dict[str, Any], errors: dict[str, str], prefix: str = "") -> None:
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        key = f"{prefix}{field}" if prefix else field
        errors[key] = "Importo calcolato non accettato dalla pagina."


def _validate_voices(raw_voices: Any, errors: dict[str, str]) -> list[VoceParcella]:
    if not isinstance(raw_voices, list):
        errors["voci"] = "Aggiungi almeno una voce."
        return []
    voices: list[VoceParcella] = []
    for index, raw_item in enumerate(raw_voices):
        field_prefix = f"voci.{index}."
        if not isinstance(raw_item, dict):
            errors[f"voci.{index}"] = "Voce non valida."
            continue
        unknown = _unknown_fields(raw_item, _VOICE_FIELDS)
        if unknown:
            errors[f"voci.{index}"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
        _reject_canonical_fields(raw_item, errors, prefix=field_prefix)
        description = _text(raw_item.get("descrizione"), limit=240)
        if not description:
            errors[f"{field_prefix}descrizione"] = "Descrizione obbligatoria."
        quantity = _as_number(raw_item.get("quantita"), f"{field_prefix}quantita", errors, minimum=0.01, default=1.0)
        unit_price = _as_number(raw_item.get("prezzo_unitario"), f"{field_prefix}prezzo_unitario", errors, minimum=0.0, default=0.0)
        raw_type = _text(raw_item.get("tipo") or "ONORARIO", limit=40)
        if raw_type and raw_type not in {"ONORARIO", "SPESE", "ANTICIPO", "ALTRO"}:
            errors[f"{field_prefix}tipo"] = "Tipo voce non consentito."
        if description:
            voices.append(VoceParcella(descrizione=description, quantita=quantity, prezzo_unitario=unit_price, tipo=raw_type or "ONORARIO"))
    if not voices and "voci" not in errors:
        errors["voci"] = "Aggiungi almeno una voce valida."
    return voices


def _sanitize_personalized_data(raw_value: Any, errors: dict[str, str]) -> dict[str, Any]:
    if raw_value in (None, ""):
        return {}
    if not isinstance(raw_value, dict):
        errors["dati_personalizzati"] = "La scheda personalizzata non e' valida."
        return {}
    allowed = {"transmission", "studio", "recipient", "document", "payment"}
    unknown = _unknown_fields(raw_value, allowed)
    if unknown:
        errors["dati_personalizzati"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    return {
        section: _deep_text_map(raw_value.get(section), limit=512) if isinstance(raw_value.get(section), dict) else {}
        for section in allowed
    }


def _validate_payload(
    payload: dict[str, Any],
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    unknown = _unknown_fields(payload, _TOP_LEVEL_FIELDS)
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    _reject_canonical_fields(payload, errors)

    id_cliente = _text(payload.get("id_cliente"))
    id_fascicolo = _text(payload.get("id_fascicolo"))
    if not id_cliente:
        errors["id_cliente"] = "Seleziona un cliente."
    try:
        cliente = get_clienti().get(id_cliente) if id_cliente else None
    except Exception:
        cliente = None
    if id_cliente and not cliente:
        errors["id_cliente"] = "Cliente non trovato."

    fascicolo = None
    if id_fascicolo:
        try:
            fascicolo = get_fascicoli().get(id_fascicolo)
        except Exception:
            fascicolo = None
        if not fascicolo:
            errors["id_fascicolo"] = "Fascicolo non trovato."
        elif _text(getattr(fascicolo, "id_cliente", "")) and _text(getattr(fascicolo, "id_cliente", "")) != id_cliente:
            errors["id_fascicolo"] = "Il fascicolo non appartiene al cliente selezionato."

    issued_at = _as_date(payload.get("data_emissione"), "data_emissione", errors, required=True)
    due_at = _as_date(payload.get("data_scadenza"), "data_scadenza", errors, required=True)
    if issued_at and due_at and due_at < issued_at:
        errors["data_scadenza"] = "La scadenza non puo' precedere la data di emissione."

    raw_options = payload.get("opzioni_fiscali") or {}
    if not isinstance(raw_options, dict):
        errors["opzioni_fiscali"] = "Opzioni fiscali non valide."
        raw_options = {}
    option_unknown = _unknown_fields(raw_options, _FISCAL_OPTION_FIELDS)
    if option_unknown:
        errors["opzioni_fiscali"] = "Campi non consentiti: " + ", ".join(sorted(option_unknown))
    _reject_canonical_fields(raw_options, errors, prefix="opzioni_fiscali.")

    voices = _validate_voices(payload.get("voci"), errors)
    percentuale_spese_generali = _as_number(
        payload.get("percentuale_spese_generali"),
        "percentuale_spese_generali",
        errors,
        minimum=0.0,
        default=0.0,
    )
    if percentuale_spese_generali > 100:
        errors["percentuale_spese_generali"] = "Inserisci una percentuale compresa tra 0 e 100."
    dati_personalizzati = _sanitize_personalized_data(payload.get("dati_personalizzati"), errors)
    value_controversy = _as_number(
        payload.get("valore_controversia"),
        "valore_controversia",
        errors,
        minimum=0.0,
        default=0.0,
    )
    validated = {
        "id_cliente": id_cliente,
        "id_fascicolo": id_fascicolo or None,
        "data_emissione": issued_at,
        "data_scadenza": due_at,
        "voci": voices,
        "note": _text(payload.get("note"), limit=2000),
        "applica_iva": _as_bool(raw_options.get("applica_iva"), True),
        "applica_cassa": _as_bool(raw_options.get("applica_cassa"), True),
        "applica_ritenuta": _as_bool(raw_options.get("applica_ritenuta"), False),
        "applica_bollo": _as_bool(raw_options.get("applica_bollo"), False),
        "percentuale_spese_generali": percentuale_spese_generali,
        "metodo_pagamento": _text(payload.get("metodo_pagamento"), limit=60),
        "dati_personalizzati": dati_personalizzati,
        "from_cliente": _text(payload.get("from_cliente")),
        "origine": _text(payload.get("origine"), limit=80),
        "id_preventivo": _text(payload.get("id_preventivo")) or None,
        "id_pratica": _text(payload.get("id_pratica")),
        "area_pratica": _text(payload.get("area_pratica"), limit=120),
        "procedura_operativa_codice": _text(payload.get("procedura_operativa_codice"), limit=120),
        "tipo_compenso": _text(payload.get("tipo_compenso"), limit=120),
        "tipo_procedimento": _text(payload.get("tipo_procedimento"), limit=120),
        "valore_controversia": value_controversy,
        "complessita": _text(payload.get("complessita"), limit=80),
        "log_calcolo": _text(payload.get("log_calcolo")) or None,
    }
    return validated, errors


def _preventivo_log(get_preventivi: Callable[[], Any] | None, preventivo_id: str | None) -> str | None:
    if not get_preventivi or not preventivo_id:
        return None
    try:
        manager = get_preventivi()
        getter = getattr(manager, "get_preventivo", None)
        preventivo = getter(preventivo_id) if callable(getter) else None
    except Exception:
        preventivo = None
    return _text(getattr(preventivo, "log_calcolo", "")) or None


def _audit_create(get_utenti: Callable[[], Any], current_user: Any, parcella: Any, ip_address: str) -> None:
    try:
        manager = get_utenti()
        registrar = getattr(manager, "registra_evento", None)
        if not callable(registrar):
            return
        registrar(
            "fatturazione.crea",
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="parcella",
            risorsa_id=_text(getattr(parcella, "id", "")),
            dettagli=(
                f"numero={_text(getattr(parcella, 'numero', ''))}; "
                f"cliente={_text(getattr(parcella, 'id_cliente', ''))}; "
                "origine=react_operational_full"
            ),
            ip=ip_address,
            esito="OK",
        )
    except Exception:
        return


def create_react_fattura(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None,
    current_user: Any,
    payload: dict[str, Any],
    config: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }, 403

    validated, errors = _validate_payload(payload, get_clienti=get_clienti, get_fascicoli=get_fascicoli)
    if errors:
        return {
            "ok": False,
            "message": "Controlla i campi evidenziati.",
            "errors": errors,
            "item": None,
        }, 400

    log_calcolo = validated["log_calcolo"] or _preventivo_log(get_preventivi, validated["id_preventivo"])
    try:
        manager = get_fatturazione()
        parcella = manager.crea(
            id_cliente=validated["id_cliente"],
            voci=validated["voci"],
            creato_da=_text(getattr(current_user, "username", "")),
            id_fascicolo=validated["id_fascicolo"],
            data_emissione=validated["data_emissione"],
            data_scadenza=validated["data_scadenza"],
            applica_iva=validated["applica_iva"],
            applica_cassa=validated["applica_cassa"],
            applica_ritenuta=validated["applica_ritenuta"],
            applica_bollo=validated["applica_bollo"],
            percentuale_spese_generali=validated["percentuale_spese_generali"],
            note=validated["note"],
            origine=validated["origine"],
            id_preventivo=validated["id_preventivo"],
            id_pratica=validated["id_pratica"],
            area_pratica=validated["area_pratica"],
            procedura_operativa_codice=validated["procedura_operativa_codice"],
            tipo_compenso=validated["tipo_compenso"],
            tipo_procedimento=validated["tipo_procedimento"],
            valore_controversia=validated["valore_controversia"],
            complessita=validated["complessita"],
            log_calcolo=log_calcolo,
            studio_piva=_text(config.get("STUDIO_PIVA")),
            studio_cf=_text(config.get("STUDIO_CF")),
            studio_indirizzo=_text(config.get("STUDIO_INDIRIZZO")),
            studio_iban=_text(config.get("STUDIO_IBAN")),
            metodo_pagamento=validated["metodo_pagamento"],
            dati_personalizzati=validated["dati_personalizzati"],
        )
    except ValueError as exc:
        return {
            "ok": False,
            "message": "Creazione non completata.",
            "errors": {"payload": _text(exc) or "Dati non validi."},
            "item": None,
        }, 400

    _audit_create(get_utenti, current_user, parcella, ip_address)
    redirect_href = (
        f"/clienti/{validated['from_cliente']}" if validated["from_cliente"]
        else f"/fatturazione/{_text(getattr(parcella, 'id', ''))}?_legacy=1"
    )
    return {
        "ok": True,
        "message": f"Parcella {_text(getattr(parcella, 'numero', ''))} creata.",
        "errors": {},
        "item": _created_item(parcella),
        "redirect_href": redirect_href,
    }, 200
