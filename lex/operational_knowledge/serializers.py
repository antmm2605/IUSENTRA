"""Privacy-safe serializers for operational records."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "apikey",
    "api_key",
    "auth",
    "cookie",
    "session",
    "percorso",
    "path",
    "storage",
    "blob",
    "raw_conn",
    "dsn",
)


def clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def enum_value(value: Any) -> str:
    return clean_spaces(getattr(value, "value", value))


def as_mapping(record: Any) -> dict[str, Any]:
    if record is None:
        return {}
    if isinstance(record, dict):
        return dict(record)
    if is_dataclass(record):
        return asdict(record)
    to_dict = getattr(record, "to_dict", None)
    if callable(to_dict):
        try:
            payload = to_dict()
            if isinstance(payload, dict):
                return dict(payload)
        except Exception:
            pass
    return {
        key: value
        for key, value in vars(record).items()
        if not key.startswith("_")
    } if hasattr(record, "__dict__") else {}


def scrub_mapping(payload: dict[str, Any], *, allow_keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    allowed = set(allow_keys or ())
    result: dict[str, Any] = {}
    for key, value in dict(payload or {}).items():
        clean_key = str(key or "").strip()
        lower = clean_key.lower()
        if allowed and clean_key not in allowed:
            continue
        if any(part in lower for part in SENSITIVE_KEY_PARTS):
            continue
        if isinstance(value, dict):
            result[clean_key] = scrub_mapping(value)
        elif isinstance(value, list):
            result[clean_key] = [
                scrub_mapping(item) if isinstance(item, dict) else _safe_scalar(item)
                for item in value[:20]
            ]
        else:
            result[clean_key] = _safe_scalar(value)
    return result


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return clean_spaces(getattr(value, "value", value))


def object_id(record: Any) -> str:
    data = as_mapping(record)
    return clean_spaces(data.get("id") or data.get("uid") or data.get("numero") or data.get("codice"))


def object_title(record: Any, *keys: str) -> str:
    data = as_mapping(record)
    for key in keys:
        value = clean_spaces(data.get(key))
        if value:
            return value
    for key in ("nome_completo", "titolo", "oggetto", "numero", "nome", "ragione_sociale", "id"):
        value = clean_spaces(data.get(key))
        if value:
            return value
    return "Elemento"


def serialize_cliente(record: Any) -> dict[str, Any]:
    data = as_mapping(record)
    recapiti = data.get("recapiti") if isinstance(data.get("recapiti"), dict) else {}
    documento = data.get("documento") if isinstance(data.get("documento"), dict) else {}
    indirizzo_residenza = _format_address(data.get("indirizzo_residenza"))
    indirizzo_domicilio = _format_address(data.get("indirizzo_domicilio"))
    indirizzo_sede_legale = _format_address(data.get("indirizzo_sede_legale"))
    campi_mancanti = getattr(record, "campi_mancanti_per_conferimento", None)
    documento_scaduto = getattr(getattr(record, "documento", None), "scaduto", None)
    return scrub_mapping(
        {
            "id": data.get("id"),
            "nome": data.get("nome"),
            "cognome": data.get("cognome"),
            "ragione_sociale": data.get("ragione_sociale"),
            "nome_completo": data.get("nome_completo") or clean_spaces(f"{data.get('cognome', '')} {data.get('nome', '')}"),
            "tipo": enum_value(data.get("tipo")),
            "stato": enum_value(data.get("stato")),
            "codice_fiscale": data.get("codice_fiscale") or data.get("identificativo_fiscale"),
            "partita_iva": data.get("partita_iva"),
            "data_nascita": data.get("data_nascita"),
            "luogo_nascita": data.get("luogo_nascita"),
            "provincia_nascita": data.get("provincia_nascita"),
            "nazionalita": data.get("nazionalita"),
            "sesso": data.get("sesso"),
            "forma_giuridica": data.get("forma_giuridica"),
            "codice_ateco": data.get("codice_ateco"),
            "data_costituzione": data.get("data_costituzione"),
            "rappresentante_legale": data.get("rappresentante_legale"),
            "cf_rappresentante": data.get("cf_rappresentante"),
            "indirizzo_residenza": indirizzo_residenza,
            "indirizzo_domicilio": indirizzo_domicilio,
            "indirizzo_sede_legale": indirizzo_sede_legale,
            "email": recapiti.get("email") or data.get("email"),
            "pec": recapiti.get("pec") or data.get("pec"),
            "telefono": recapiti.get("telefono") or data.get("telefono"),
            "cellulare": recapiti.get("cellulare") or data.get("cellulare"),
            "fax": recapiti.get("fax") or data.get("fax"),
            "sito_web": recapiti.get("sito_web") or data.get("sito_web"),
            "documento_tipo": enum_value(documento.get("tipo")),
            "documento_numero": documento.get("numero"),
            "documento_rilasciato_da": documento.get("rilasciato_da"),
            "documento_data_rilascio": documento.get("data_rilascio"),
            "documento_data_scadenza": documento.get("data_scadenza"),
            "documento_scaduto": bool(documento_scaduto) if documento_scaduto is not None else None,
            "avvocato_referente": data.get("avvocato_referente"),
            "data_prima_acquisizione": data.get("data_prima_acquisizione"),
            "provenienza": data.get("provenienza"),
            "note": data.get("note"),
            "procedimenti": data.get("procedimenti") or [],
            "tag": data.get("tag") or [],
            "consenso_trattamento": data.get("consenso_trattamento"),
            "data_consenso": data.get("data_consenso"),
            "modalita_consenso": data.get("modalita_consenso"),
            "campi_mancanti_per_conferimento": list(campi_mancanti or []) if campi_mancanti is not None else [],
            "creato_il": data.get("creato_il"),
            "modificato_il": data.get("modificato_il"),
        }
    )


def _format_address(value: Any) -> str:
    data = value if isinstance(value, dict) else as_mapping(value)
    if not data:
        return ""
    parts = []
    street = clean_spaces(f"{data.get('via', '')} {data.get('civico', '')}")
    city = clean_spaces(" ".join(str(part or "") for part in (data.get("cap"), data.get("comune"))))
    province = clean_spaces(data.get("provincia"))
    country = clean_spaces(data.get("nazione"))
    if street:
        parts.append(street)
    if city and province:
        parts.append(f"{city} ({province})")
    elif city:
        parts.append(city)
    elif province:
        parts.append(province)
    if country and country.lower() != "italia":
        parts.append(country)
    return ", ".join(parts)


def serialize_soggetto(record: Any) -> dict[str, Any]:
    data = as_mapping(record)
    recapiti = data.get("recapiti") if isinstance(data.get("recapiti"), dict) else {}
    indirizzo = _format_address(data.get("indirizzo"))
    return scrub_mapping(
        {
            "record_kind": "soggetto",
            "id": data.get("id"),
            "nome": data.get("nome"),
            "cognome": data.get("cognome"),
            "ragione_sociale": data.get("ragione_sociale"),
            "nome_completo": data.get("nome_completo") or clean_spaces(f"{data.get('cognome', '')} {data.get('nome', '')}"),
            "tipo": enum_value(data.get("tipo")),
            "codice_fiscale": data.get("codice_fiscale"),
            "partita_iva": data.get("partita_iva"),
            "data_nascita": data.get("data_nascita"),
            "luogo_nascita": data.get("luogo_nascita"),
            "provincia_nascita": data.get("provincia_nascita"),
            "sesso": data.get("sesso"),
            "forma_giuridica": data.get("forma_giuridica"),
            "rappresentante_legale": data.get("rappresentante_legale"),
            "qualifica": data.get("qualifica"),
            "ordine": data.get("ordine"),
            "numero_iscrizione": data.get("numero_iscrizione"),
            "indirizzo": indirizzo,
            "email": recapiti.get("email") or data.get("email"),
            "pec": recapiti.get("pec") or data.get("pec"),
            "telefono": recapiti.get("telefono") or data.get("telefono"),
            "cellulare": recapiti.get("cellulare") or data.get("cellulare"),
            "fax": recapiti.get("fax") or data.get("fax"),
            "sito_web": recapiti.get("sito_web") or data.get("sito_web"),
            "id_cliente": data.get("id_cliente"),
            "note": data.get("note"),
            "tag": data.get("tag") or [],
            "creato_il": data.get("creato_il"),
            "modificato_il": data.get("modificato_il"),
        }
    )


def serialize_parte_processuale(record: Any) -> dict[str, Any]:
    fascicolo_id = ""
    parte_raw: Any = record
    soggetto_raw: Any = None
    if isinstance(record, dict) and ("parte" in record or "soggetto" in record):
        parte_raw = record.get("parte") or {}
        soggetto_raw = record.get("soggetto")
        fascicolo_id = clean_spaces(record.get("id_fascicolo"))
    elif isinstance(record, (tuple, list)):
        if record:
            parte_raw = record[0]
        if len(record) > 1:
            soggetto_raw = record[1]
        if len(record) > 2:
            fascicolo_id = clean_spaces(record[2])

    parte = as_mapping(parte_raw)
    soggetto = serialize_soggetto(soggetto_raw) if soggetto_raw is not None else {}
    return scrub_mapping(
        {
            "record_kind": "parte",
            "id": parte.get("id"),
            "id_fascicolo": fascicolo_id or parte.get("id_fascicolo"),
            "id_soggetto": parte.get("id_soggetto") or soggetto.get("id"),
            "ruolo": enum_value(parte.get("ruolo")),
            "note_parte": parte.get("note"),
            "data_aggiunta": parte.get("data_aggiunta"),
            "soggetto_id": soggetto.get("id"),
            "nome_completo": soggetto.get("nome_completo") or soggetto.get("ragione_sociale"),
            "tipo": soggetto.get("tipo"),
            "codice_fiscale": soggetto.get("codice_fiscale"),
            "partita_iva": soggetto.get("partita_iva"),
            "email": soggetto.get("email"),
            "pec": soggetto.get("pec"),
            "telefono": soggetto.get("telefono"),
            "cellulare": soggetto.get("cellulare"),
            "indirizzo": soggetto.get("indirizzo"),
            "qualifica": soggetto.get("qualifica"),
            "ordine": soggetto.get("ordine"),
            "id_cliente": soggetto.get("id_cliente"),
            "note_soggetto": soggetto.get("note"),
        }
    )


def serialize_fascicolo(record: Any) -> dict[str, Any]:
    data = as_mapping(record)
    return scrub_mapping(
        {
            "id": data.get("id"),
            "numero": data.get("numero") or data.get("numero_rg"),
            "rg_completo": data.get("rg_completo"),
            "titolo": data.get("titolo"),
            "oggetto": data.get("oggetto"),
            "id_cliente": data.get("id_cliente"),
            "nome_cliente": data.get("nome_cliente") or data.get("cliente"),
            "controparte": data.get("controparte"),
            "tribunale": data.get("tribunale"),
            "stato": enum_value(data.get("stato")),
            "data_apertura": data.get("data_apertura"),
            "data_prossima_udienza": data.get("data_prossima_udienza"),
            "documenti_count": data.get("documenti_count") or len(data.get("documenti") or []),
            "attivita_count": data.get("attivita_count") or len(data.get("attivita") or []),
        }
    )


def serialize_documento(record: Any) -> dict[str, Any]:
    data = as_mapping(record)
    versions = data.get("versions") if isinstance(data.get("versions"), list) else []
    return scrub_mapping(
        {
            "id": data.get("id"),
            "nome": data.get("nome") or data.get("original_filename") or data.get("safe_filename"),
            "tipo": enum_value(data.get("tipo") or data.get("file_type")),
            "categoria": data.get("categoria"),
            "dimensione": data.get("dimensione") or data.get("size_bytes"),
            "sha256": data.get("sha256"),
            "status": data.get("status"),
            "current_version_id": data.get("current_version_id"),
            "version_count": len(versions),
            "data_caricamento": data.get("data_caricamento") or data.get("created_at"),
            "firmato": data.get("firmato"),
        }
    )


def serialize_email_message(record: Any, *, include_body: bool = False) -> dict[str, Any]:
    data = as_mapping(record)
    allegati = list(data.get("allegati") or [])
    payload = {
        "id": data.get("id"),
        "cartella": enum_value(data.get("cartella")),
        "stato": enum_value(data.get("stato")),
        "mittente": data.get("mittente"),
        "mittente_nome": data.get("mittente_nome"),
        "destinatari": data.get("destinatari"),
        "oggetto": data.get("oggetto"),
        "data": data.get("data") or data.get("ricevuta_il"),
        "anteprima": data.get("anteprima") or clean_spaces(data.get("corpo_testo") or "")[:160],
        "allegati_count": len(allegati),
        "origine": data.get("origine"),
        "stato_pct": data.get("stato_pct"),
        "auto_registrata": data.get("auto_registrata"),
    }
    if include_body:
        payload["corpo_testo"] = clean_spaces(data.get("corpo_testo"))[:6000]
    return scrub_mapping(payload)


def serialize_email_attachment(record: Any, *, index: int = 0, available: bool = False) -> dict[str, Any]:
    data = as_mapping(record)
    return scrub_mapping(
        {
            "index": index,
            "nome": data.get("nome") or data.get("nome_file") or f"Allegato {index + 1}",
            "mime": data.get("mime") or data.get("content_type"),
            "size": data.get("size") or data.get("dimensione"),
            "sha256": data.get("sha256"),
            "archiviato": bool(data.get("archivio_membro")),
            "disponibile": bool(available),
        }
    )


def serialize_generic(record: Any, *, max_keys: int = 40) -> dict[str, Any]:
    payload = scrub_mapping(as_mapping(record))
    return dict(list(payload.items())[:max_keys])
