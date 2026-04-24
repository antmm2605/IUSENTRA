"""Normalizzazione payload reali per la sincronizzazione fascicolo SIGP."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _pick(mapping: dict, *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _hash_snapshot(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rg_from_text(value: str) -> tuple[str, str]:
    text = _text(value)
    if "/" not in text:
        return text, ""
    numero, anno = text.split("/", 1)
    return numero.strip(), anno.strip()


def _derive_tags(*values: str) -> list[str]:
    tags: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in tags:
            tags.append(text)
    return tags


def normalize_sigp_sync_payload(raw: dict) -> dict:
    """Converte payload autorizzati PST/PdA/Local Connector in snapshot interno.

    La funzione non contiene fixture, non legge file esempio e non applica limiti:
    tutte le sezioni ricevute dal canale autorizzato vengono riportate nello snapshot.
    """

    if not isinstance(raw, dict):
        raise ValueError("Il payload SIGP deve essere un oggetto JSON.")

    fascicolo_raw = raw.get("fascicolo") or raw.get("case") or raw
    if not isinstance(fascicolo_raw, dict):
        raise ValueError("La sezione fascicolo del payload SIGP non e' valida.")

    rg_text = _text(_pick(fascicolo_raw, "rg", "numero_anno", "numeroAnno"))
    rg_numero, rg_anno = _rg_from_text(rg_text)
    numero_rg = _text(_pick(fascicolo_raw, "numero_rg", "numeroRG", "numero", "numeroFascicolo", default=rg_numero))
    anno_rg = _text(_pick(fascicolo_raw, "anno_rg", "annoRG", "anno", "annoFascicolo", default=rg_anno))
    ufficio = _text(_pick(fascicolo_raw, "ufficio", "ufficio_giudiziario", "denominazioneUfficio", "court"))
    ufficio_codice = _text(_pick(fascicolo_raw, "ufficio_codice", "codice_ufficio", "codiceUfficio"))
    registro = _text(_pick(fascicolo_raw, "registro", "registroRicerca", "tipoRegistro", default="GDP"))

    sigp_uid = _text(
        _pick(
            fascicolo_raw,
            "sigp_uid",
            "uid",
            "id_fascicolo",
            "idFascicolo",
            default=f"SIGP-{ufficio_codice or ufficio}-{registro}-{anno_rg}-{numero_rg}",
        )
    )

    normalized = {
        "origine": "SIGP",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "fascicolo": {
            "sigp_uid": sigp_uid,
            "fascicolo_locale_id": _text(_pick(raw, "fascicolo_locale_id", "fascicoloLocaleId")),
            "ufficio_codice": ufficio_codice,
            "ufficio": ufficio,
            "registro": registro,
            "numero_rg": numero_rg,
            "anno_rg": anno_rg,
            "atto_introduttivo": _text(_pick(fascicolo_raw, "atto_introduttivo", "attoIntroduttivo")),
            "rito": _text(_pick(fascicolo_raw, "rito")),
            "ruolo": _text(_pick(fascicolo_raw, "ruolo")),
            "materia": _text(_pick(fascicolo_raw, "materia")),
            "oggetto": _text(_pick(fascicolo_raw, "oggetto", "subject")),
            "giudice": _text(_pick(fascicolo_raw, "giudice", "judge")),
            "sezione": _text(_pick(fascicolo_raw, "sezione")),
            "stato": _text(_pick(fascicolo_raw, "stato", "stato_procedimento")),
            "data_iscrizione": _text(_pick(fascicolo_raw, "data_iscrizione", "dataIscrizione")),
            "data_prima_comparizione": _text(_pick(fascicolo_raw, "data_prima_comparizione", "dataPrimaComparizione")),
            "data_ultima_udienza": _text(_pick(fascicolo_raw, "data_ultima_udienza", "dataUltimaUdienza")),
        },
        "parti": _normalize_parti(raw),
        "eventi": _normalize_eventi(raw),
        "udienze": _normalize_udienze(raw),
        "documenti": _normalize_documenti(raw),
        "comunicazioni": _normalize_comunicazioni(raw),
        "raw": raw,
    }
    normalized["hash_snapshot"] = _hash_snapshot(
        {
            "fascicolo": normalized["fascicolo"],
            "parti": normalized["parti"],
            "eventi": normalized["eventi"],
            "udienze": normalized["udienze"],
            "documenti": normalized["documenti"],
            "comunicazioni": normalized["comunicazioni"],
        }
    )
    return normalized


def _normalize_parti(raw: dict) -> list[dict]:
    items = raw.get("parti") or raw.get("parties") or (raw.get("fascicolo") or {}).get("parti") or []
    normalized: list[dict] = []
    for item in _as_list(items):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "ruolo": _text(_pick(item, "ruolo", "role")),
                "tipo": _text(_pick(item, "tipo", "type")),
                "nome": _text(_pick(item, "nome", "first_name")),
                "cognome": _text(_pick(item, "cognome", "last_name")),
                "denominazione": _text(_pick(item, "denominazione", "name", "descrizione")),
                "codice_fiscale": _text(_pick(item, "codice_fiscale", "codiceFiscale", "cf")),
                "partita_iva": _text(_pick(item, "partita_iva", "partitaIva", "piva")),
                "difensore": _text(_pick(item, "difensore", "legale", "rappresentato_da")),
                "raw": item,
            }
        )
    return normalized


def _normalize_eventi(raw: dict) -> list[dict]:
    items = raw.get("eventi") or raw.get("events") or []
    return [_normalize_evento(item) for item in _as_list(items) if isinstance(item, dict)]


def _normalize_evento(item: dict) -> dict:
    return {
        "evento_uid": _text(_pick(item, "evento_uid", "uid", "id")),
        "tipo_evento": _text(_pick(item, "tipo_evento", "tipo", "event_type")),
        "descrizione": _text(_pick(item, "descrizione", "description")),
        "data_evento": _text(_pick(item, "data_evento", "data", "date")),
        "data_udienza": _text(_pick(item, "data_udienza", "hearing_date")),
        "esito": _text(_pick(item, "esito", "outcome")),
        "raw": item,
    }


def _normalize_udienze(raw: dict) -> list[dict]:
    items = raw.get("udienze") or raw.get("hearings") or raw.get("scadenze") or []
    normalized: list[dict] = []
    for item in _as_list(items):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "udienza_uid": _text(_pick(item, "udienza_uid", "uid", "id")),
                "data_udienza": _text(_pick(item, "data_udienza", "data", "date")),
                "ora": _text(_pick(item, "ora", "time")),
                "tipo": _text(_pick(item, "tipo", "type")),
                "descrizione": _text(_pick(item, "descrizione", "description")),
                "esito": _text(_pick(item, "esito", "outcome")),
                "raw": item,
            }
        )
    return normalized


def _normalize_documenti(raw: dict) -> list[dict]:
    sections = (
        ("DocumentiFascicolo", raw.get("documenti") or raw.get("documents") or []),
        ("Provvedimenti", raw.get("provvedimenti") or []),
        ("Istanze", raw.get("istanze") or []),
    )
    normalized: list[dict] = []
    seen: set[str] = set()
    for default_section, items in sections:
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            doc = _normalize_documento(item, default_section)
            key = doc["documento_uid"] or f"{doc['nome_file']}|{doc['data_deposito']}|{doc['sezione']}"
            if key in seen:
                continue
            seen.add(key)
            normalized.append(doc)
    return normalized


def _normalize_documento(item: dict, default_section: str) -> dict:
    tipo_atto = _text(_pick(item, "tipo_atto", "tipoAtto", "tipo_documento", "tipo", "type"))
    classificazione = _text(_pick(item, "classificazione", "categoria", "category", default=tipo_atto))
    sezione = _text(_pick(item, "sezione", "section", default=default_section))
    tags = item.get("tags")
    if not isinstance(tags, list):
        tags = _derive_tags(sezione, classificazione, tipo_atto)
    return {
        "documento_uid": _text(_pick(item, "documento_uid", "uid", "id", "id_documento", "idDocumento", "idCat", "id_cat")),
        "id_deposito": _text(_pick(item, "id_deposito", "idDeposito", "id_busta", "msg_id", "msgId")),
        "id_repeatto": _text(_pick(item, "id_repeatto", "idRepeatTo", "IDREPEATTO")),
        "nome_file": _text(_pick(item, "nome_file", "nomeFile", "filename", "nome", "name")),
        "nome_originario": _text(_pick(item, "nome_originario", "nomeOriginario", "original_filename")),
        "sezione": sezione,
        "classificazione": classificazione,
        "tipo_atto": tipo_atto,
        "data_deposito": _text(_pick(item, "data_deposito", "dataDeposito")),
        "data_documento": _text(_pick(item, "data_documento", "dataDocumento", "data")),
        "depositante": _text(_pick(item, "depositante", "mittente")),
        "mime_type": _text(_pick(item, "mime_type", "mimeType")),
        "dimensione_bytes": int(_pick(item, "dimensione_bytes", "dimensioneBytes", "size", default=0) or 0),
        "scaricabile": bool(_pick(item, "scaricabile", "disponibile", default=True)),
        "path_locale": _text(_pick(item, "path_locale", "percorso_rel", "percorso")),
        "sha256": _text(_pick(item, "sha256")),
        "tags": tags,
        "raw": item,
    }


def _normalize_comunicazioni(raw: dict) -> list[dict]:
    items = raw.get("comunicazioni") or raw.get("communications") or raw.get("cancelleria") or []
    normalized: list[dict] = []
    for item in _as_list(items):
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "comunicazione_uid": _text(_pick(item, "comunicazione_uid", "uid", "id", "msg_id", "msgId")),
                "tipo": _text(_pick(item, "tipo", "type")),
                "oggetto": _text(_pick(item, "oggetto", "subject")),
                "data_comunicazione": _text(_pick(item, "data_comunicazione", "data", "date")),
                "mittente": _text(_pick(item, "mittente", "sender")),
                "destinatario": _text(_pick(item, "destinatario", "recipient")),
                "raw": item,
            }
        )
    return normalized
