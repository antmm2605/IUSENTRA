"""Normalizzazione del catalogo documenti SIGP/PST per IUSENTRA.

Questo modulo NON interroga il portale e NON fa scraping HTML.
Riceve un elenco documenti gia' ottenuto da un canale autorizzato
(Local Connector, PST/PdA, Model Office o acquisizione assistita) e lo
porta nel formato della tabella sigp_sync_documenti.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _pick(mapping: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(str(value).replace(" ", "").replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _to_bool(value: Any, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "vero", "yes", "si", "scaricabile", "available"}:
        return True
    if text in {"0", "false", "falso", "no", "non_scaricabile", "unavailable"}:
        return False
    return default


def _derive_uid(item: dict[str, Any], nome_file: str, tipo_atto: str, data_deposito: str) -> str:
    explicit = _text(
        _pick(
            item,
            "documento_uid",
            "uid",
            "id",
            "id_documento",
            "idDocumento",
            "id_cat",
            "idCat",
            "idAtto",
            "id_allegato",
            "idAllegato",
            "uuid",
        )
    )
    if explicit:
        return explicit
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    base = "|".join(part for part in (nome_file, tipo_atto, data_deposito, digest) if part)
    return f"DOC-{hashlib.sha256(base.encode('utf-8')).hexdigest()[:24]}"


def extract_document_items(raw_catalog: Any) -> list[dict[str, Any]]:
    """Estrae gli item documento da varie forme di payload.

    Forme accettate:
    - [ {...}, {...} ]
    - {"documenti": [...]}
    - {"documents": [...]}
    - {"catalogo": {"documenti": [...]}}
    - {"payload": {"documenti": [...]}}
    - {"fascicolo": {"documenti": [...]}}
    """
    if isinstance(raw_catalog, list):
        return [item for item in raw_catalog if isinstance(item, dict)]

    if not isinstance(raw_catalog, dict):
        raise ValueError("Il catalogo documenti SIGP deve essere JSON oggetto o lista.")

    candidates: list[Any] = [
        raw_catalog.get("documenti"),
        raw_catalog.get("documents"),
        raw_catalog.get("items"),
        raw_catalog.get("atti"),
        raw_catalog.get("provvedimenti"),
        raw_catalog.get("allegati"),
    ]

    for nested_key in ("catalogo", "payload", "fascicolo", "data", "result", "risultato"):
        nested = raw_catalog.get(nested_key)
        if isinstance(nested, dict):
            candidates.extend(
                [
                    nested.get("documenti"),
                    nested.get("documents"),
                    nested.get("items"),
                    nested.get("atti"),
                    nested.get("provvedimenti"),
                    nested.get("allegati"),
                ]
            )

    items: list[dict[str, Any]] = []
    for candidate in candidates:
        for item in _as_list(candidate):
            if isinstance(item, dict):
                items.append(item)

    return items


def normalize_document_catalog(raw_catalog: Any) -> list[dict[str, Any]]:
    """Normalizza il catalogo documenti nella forma DB sigp_sync_documenti."""
    items = extract_document_items(raw_catalog)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        nome_file = _text(
            _pick(
                item,
                "nome_file",
                "nomeFile",
                "filename",
                "fileName",
                "nome",
                "name",
                "titolo",
                "descrizioneFile",
            )
        )
        nome_originario = _text(_pick(item, "nome_originario", "nomeOriginario", "original_filename", "originalFilename"))
        tipo_atto = _text(_pick(item, "tipo_atto", "tipoAtto", "tipo_documento", "tipoDocumento", "tipo", "type"))
        classificazione = _text(_pick(item, "classificazione", "categoria", "category", "classe", default=tipo_atto))
        sezione = _text(_pick(item, "sezione", "section", "area", default="DocumentiFascicolo"))
        data_deposito = _text(_pick(item, "data_deposito", "dataDeposito", "deposito", "depositDate"))
        data_documento = _text(_pick(item, "data_documento", "dataDocumento", "data", "date", "documentDate"))
        depositante = _text(_pick(item, "depositante", "mittente", "sender", "autore", "author"))
        uid = _derive_uid(item, nome_file, tipo_atto, data_deposito or data_documento)

        key = uid or f"{nome_file}|{tipo_atto}|{data_deposito}|{data_documento}"
        if key in seen:
            continue
        seen.add(key)

        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = [value for value in (sezione, classificazione, tipo_atto) if value]

        normalized.append(
            {
                "documento_uid": uid,
                "id_deposito": _text(_pick(item, "id_deposito", "idDeposito", "idBusta", "id_busta", "msg_id", "msgId")),
                "id_repeatto": _text(_pick(item, "id_repeatto", "idRepeatTo", "IDREPEATTO", "repeatTo")),
                "nome_file": nome_file,
                "nome_originario": nome_originario,
                "sezione": sezione,
                "classificazione": classificazione,
                "tipo_atto": tipo_atto,
                "data_deposito": data_deposito,
                "data_documento": data_documento,
                "depositante": depositante,
                "mime_type": _text(_pick(item, "mime_type", "mimeType", "contentType", default="application/pdf")),
                "dimensione_bytes": _to_int(_pick(item, "dimensione_bytes", "dimensioneBytes", "size", "bytes", default=0)),
                "scaricabile": _to_bool(_pick(item, "scaricabile", "disponibile", "downloadable", "available", default=True)),
                "path_locale": _text(_pick(item, "path_locale", "percorso_rel", "percorso", "localPath")),
                "sha256": _text(_pick(item, "sha256", "hash", "digest")),
                "tags": tags,
                "raw": item,
            }
        )

    return normalized
