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
    return scrub_mapping(
        {
            "id": data.get("id"),
            "nome": data.get("nome"),
            "cognome": data.get("cognome"),
            "nome_completo": data.get("nome_completo") or clean_spaces(f"{data.get('cognome', '')} {data.get('nome', '')}"),
            "tipo": enum_value(data.get("tipo")),
            "stato": enum_value(data.get("stato")),
            "codice_fiscale": data.get("codice_fiscale") or data.get("identificativo_fiscale"),
            "partita_iva": data.get("partita_iva"),
            "email": recapiti.get("email") or data.get("email"),
            "pec": recapiti.get("pec") or data.get("pec"),
            "telefono": recapiti.get("telefono") or data.get("telefono"),
            "procedimenti": data.get("procedimenti") or [],
        }
    )


def serialize_soggetto(record: Any) -> dict[str, Any]:
    data = as_mapping(record)
    recapiti = data.get("recapiti") if isinstance(data.get("recapiti"), dict) else {}
    return scrub_mapping(
        {
            "id": data.get("id"),
            "nome": data.get("nome"),
            "cognome": data.get("cognome"),
            "ragione_sociale": data.get("ragione_sociale"),
            "nome_completo": data.get("nome_completo") or clean_spaces(f"{data.get('cognome', '')} {data.get('nome', '')}"),
            "tipo": enum_value(data.get("tipo")),
            "codice_fiscale": data.get("codice_fiscale"),
            "partita_iva": data.get("partita_iva"),
            "email": recapiti.get("email") or data.get("email"),
            "pec": recapiti.get("pec") or data.get("pec"),
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
