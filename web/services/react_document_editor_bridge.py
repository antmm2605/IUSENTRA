"""Payload React per l'editor documentale del fascicolo."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pct.editor import estensione_editabile


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text if text else default


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _date_label(value: Any) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    raw = _text(value)
    if not raw:
        return ""
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _bytes_label(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return ""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} KB"
    return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "read_only": False,
        "writes": "operational_routes",
    }


def _fascicolo_lookup_keys(fascicolo: Any) -> set[str]:
    fields = (
        "id",
        "id_pratica",
        "numero",
        "numero_interno",
        "numero_rg",
        "riferimento",
        "reference",
        "codice",
        "codice_fascicolo",
        "source_external_id",
        "import_log_id",
    )
    keys = {_text(getattr(fascicolo, field, "")) for field in fields}
    fid = _text(getattr(fascicolo, "id", ""))
    keys.update({fid.upper(), fid.lower()})
    return {key for key in keys if key}


def _resolve_fascicolo(repo: Any, requested_id: str) -> Any:
    direct = repo.get(requested_id)
    if direct:
        return direct
    wanted = _text(requested_id).casefold()
    if not wanted:
        return None
    for fascicolo in repo.tutti():
        if wanted in {key.casefold() for key in _fascicolo_lookup_keys(fascicolo)}:
            return fascicolo
    return None


def _document_payload(fascicolo_id: str, doc: Any) -> dict[str, Any]:
    did = _text(getattr(doc, "id", ""))
    name = _text(getattr(doc, "nome", ""), "Documento")
    suffix = Path(name).suffix.lower()
    signed = bool(getattr(doc, "firmato", False) or getattr(doc, "firmato_digitalmente", False) or name.lower().endswith(".p7m"))
    editable = bool(estensione_editabile(name) and not signed)
    locked_reason = ""
    if signed:
        locked_reason = "Il documento risulta firmato digitalmente: aprilo in anteprima o usa la pagina firma per sostituirlo consapevolmente."
    elif not estensione_editabile(name):
        locked_reason = f"Formato {suffix.upper() or 'non riconosciuto'} non supportato dall'editor."

    return {
        "id": did,
        "name": name,
        "extension": suffix.lstrip("."),
        "type": _enum_value(getattr(doc, "tipo", "ALTRO")).replace("_", " "),
        "size": _bytes_label(getattr(doc, "dimensione_bytes", 0)),
        "uploadedAt": _date_label(getattr(doc, "data_caricamento", "")),
        "documentDate": _date_label(getattr(doc, "data_documento", "")),
        "notes": _text(getattr(doc, "note", "")),
        "tags": list(getattr(doc, "tags", []) or []),
        "signed": signed,
        "hash": _text(getattr(doc, "hash_sha256", "")),
        "source": _text(getattr(doc, "fonte_documento", ""), "CARICAMENTO_STUDIO"),
        "editable": editable,
        "lockedReason": locked_reason,
        "portal": {
            "name": _text(getattr(doc, "nome_portale", "")),
            "class": _text(getattr(doc, "classificazione_portale", "")),
            "sender": _text(getattr(doc, "mittente_portale", "")),
            "date": _date_label(getattr(doc, "data_deposito_portale", "")),
        },
        "actions": {
            "preview": f"/fascicoli/{fascicolo_id}/documenti/{did}/visualizza",
            "download": f"/fascicoli/{fascicolo_id}/documenti/{did}/scarica",
            "sign": f"/fascicoli/{fascicolo_id}/documenti/{did}/firma",
            "detail": f"/fascicoli/{fascicolo_id}#documenti",
        },
    }


def build_react_document_editor_payload(
    *,
    get_fascicoli: Callable[[], Any],
    id_fasc: str,
    id_doc: str,
) -> dict[str, Any]:
    """Costruisce il contratto dati reale per la pagina React dell'editor."""

    repo = get_fascicoli()
    fascicolo = _resolve_fascicolo(repo, id_fasc)
    if not fascicolo:
        return {
            "source": "repository_reali",
            "generatedAt": _now(),
            "contracts": _contracts(),
            "notFound": True,
            "message": "Fascicolo non trovato.",
            "fascicolo": {"id": id_fasc, "detailHref": "/fascicoli"},
            "document": {"id": id_doc},
            "endpoints": {},
            "warnings": [],
        }

    fid = _text(getattr(fascicolo, "id", id_fasc), id_fasc)
    doc = next((item for item in getattr(fascicolo, "documenti", []) or [] if _text(getattr(item, "id", "")) == id_doc), None)
    if not doc:
        return {
            "source": "repository_reali",
            "generatedAt": _now(),
            "contracts": _contracts(),
            "notFound": True,
            "message": "Documento non trovato.",
            "fascicolo": {
                "id": fid,
                "ref": _text(getattr(fascicolo, "numero", ""), fid),
                "title": _text(getattr(fascicolo, "titolo", ""), "Fascicolo"),
                "client": _text(getattr(fascicolo, "nome_cliente", "")),
                "detailHref": f"/fascicoli/{fid}#documenti",
            },
            "document": {"id": id_doc},
            "endpoints": {},
            "warnings": [],
        }

    document = _document_payload(fid, doc)
    warnings: list[str] = []
    if document["extension"] == "pdf":
        warnings.append(
            "Il PDF viene trasformato in contenuto modificabile: prima del deposito verifica impaginazione e PDF/A."
        )
    if not document["editable"] and document["lockedReason"]:
        warnings.append(document["lockedReason"])

    return {
        "source": "repository_reali",
        "generatedAt": _now(),
        "contracts": _contracts(),
        "notFound": False,
        "fascicolo": {
            "id": fid,
            "ref": _text(getattr(fascicolo, "numero", ""), fid),
            "title": _text(getattr(fascicolo, "titolo", ""), "Fascicolo"),
            "client": _text(getattr(fascicolo, "nome_cliente", "")),
            "court": _text(getattr(fascicolo, "tribunale", "")),
            "rg": _text(getattr(fascicolo, "numero_rg", "")),
            "detailHref": f"/fascicoli/{fid}#documenti",
            "quadroHref": f"/fascicoli/{fid}/quadro",
        },
        "document": document,
        "endpoints": {
            "loadHtml": f"/api/editor/{fid}/{document['id']}/html",
            "save": f"/api/editor/{fid}/{document['id']}/salva",
            "exportPdf": f"/api/editor/{fid}/{document['id']}/pdf",
            "exportDocx": f"/api/editor/{fid}/{document['id']}/docx",
        },
        "capabilities": {
            "formats": [".docx", ".pdf", ".txt", ".html", ".htm"],
            "autosaveSeconds": 30,
            "localBundle": True,
        },
        "warnings": warnings,
    }
