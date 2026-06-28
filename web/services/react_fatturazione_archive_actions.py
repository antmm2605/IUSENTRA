"""Azioni JSON sicure per l'archivio fatturazione React."""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pct.fatturazione import StatoParcella, VoceParcella
from pct.formatting import format_euro_it

_ALLOWED_STATUS_FIELDS = {"stato", "data_pagamento", "metodo_pagamento", "note"}
_ALLOWED_DETAIL_FIELDS = {"voci", "note"}
_ALLOWED_SDI_OUTCOME_FIELDS = {"sdi_stato", "sdi_identificativo", "sdi_ricevuta", "sdi_note", "sdi_data_esito"}
_ALLOWED_COMMERCIALISTA_CHANNELS = {"ordinaria", "pec"}
_ALLOWED_COMMERCIALISTA_ATTACHMENTS = {"pdf", "pdf_xml_firmato"}
_SDI_OUTCOME_STATUSES = {"CONSEGNATA", "MANCATA_CONSEGNA", "SCARTATA", "DECORRENZA_TERMINI", "INVIATA"}
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
_SDI_STATUS_LABELS = {
    "": ("Da registrare", "warning", "XML originale disponibile; invio ed esito SdI devono essere registrati."),
    "PREPARATA": ("Preparata", "warning", "XML preparato; invio SdI non ancora registrato."),
    "INVIATA": ("Inviata", "info", "Invio registrato; attendere ricevuta SdI."),
    "CONSEGNATA": ("Consegnata", "success", "Ricevuta di consegna registrata."),
    "MANCATA_CONSEGNA": ("Mancata consegna", "warning", "Ricevuta di impossibilita' di recapito registrata."),
    "SCARTATA": ("Scartata", "danger", "Ricevuta di scarto: la fattura risulta non emessa e va corretta/ritrasmessa."),
    "DECORRENZA_TERMINI": ("Decorrenza termini", "info", "Esito registrato per decorrenza termini."),
}
_LOCAL_SIGNER_BASE_URL = "http://127.0.0.1:27272"
_MAX_SIGNED_XML_BYTES = 25 * 1024 * 1024


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rome_now() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).isoformat()


def _text(value: Any, *, limit: int | None = None) -> str:
    raw = str(value or "").strip()
    return raw[:limit] if limit else raw


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _money(value: Any) -> str:
    return format_euro_it(value)


def _date_label(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return raw[:10]


def _sdi_status_payload(parcella: Any) -> dict[str, Any]:
    raw_status = _text(getattr(parcella, "sdi_stato", "")).upper()
    label, tone, message = _SDI_STATUS_LABELS.get(
        raw_status,
        (raw_status or "Da registrare", "neutral", "Stato SdI da verificare."),
    )
    return {
        "sdiState": raw_status,
        "sdiStateLabel": label,
        "sdiStateTone": tone,
        "sdiStatusMessage": message,
        "sdiIdentifier": _text(getattr(parcella, "sdi_identificativo", "")),
        "sdiChannel": _text(getattr(parcella, "sdi_canale", "")),
        "sdiSentAt": _text(getattr(parcella, "sdi_data_invio", "")),
        "sdiSentLabel": _date_label(getattr(parcella, "sdi_data_invio", "")),
        "sdiOutcomeAt": _text(getattr(parcella, "sdi_data_esito", "")),
        "sdiOutcomeLabel": _date_label(getattr(parcella, "sdi_data_esito", "")),
        "sdiReceipt": _text(getattr(parcella, "sdi_ricevuta", "")),
        "sdiNote": _text(getattr(parcella, "sdi_note", "")),
    }


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


def _document_payload(parcella: Any) -> dict[str, Any]:
    data = getattr(parcella, "dati_personalizzati", {}) or {}
    if not isinstance(data, dict):
        return {}
    document = data.get("document")
    return document if isinstance(document, dict) else {}


def _is_proforma(parcella: Any) -> bool:
    return _text(_document_payload(parcella).get("documento_operativo")).upper() == "PROFORMA"


def _document_kind_label(parcella: Any) -> str:
    if _is_proforma(parcella):
        return "Proforma"
    return _text(_document_payload(parcella).get("tipo_documento_label")) or "Fattura"


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


def _safe_all(loader: Callable[[], Any], method: str) -> list[Any]:
    try:
        func = getattr(loader(), method, None)
        if callable(func):
            return list(func())
    except Exception:
        return []
    return []


def _record(parcella: Any, clienti: dict[str, Any], fascicoli: dict[str, Any]) -> dict[str, Any]:
    pid = _text(getattr(parcella, "id", ""))
    status = _enum(getattr(parcella, "stato", ""))
    id_cliente = _text(getattr(parcella, "id_cliente", ""))
    id_fascicolo = _text(getattr(parcella, "id_fascicolo", ""))
    payload = {
        "id": pid,
        "number": _text(getattr(parcella, "numero", "")) or pid,
        "customerName": _client_label(clienti.get(id_cliente)),
        "caseId": id_fascicolo,
        "caseTitle": _case_label(fascicoli.get(id_fascicolo)) if id_fascicolo else "",
        "amountDisplay": _money(getattr(parcella, "totale", 0)),
        "issuedAt": _date_label(getattr(parcella, "data_emissione", "")),
        "dueAt": _date_label(getattr(parcella, "data_scadenza", "")),
        "paidAt": _date_label(getattr(parcella, "data_pagamento", "")),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "isProforma": _is_proforma(parcella),
        "documentKindLabel": _document_kind_label(parcella),
        "paymentMethod": _text(getattr(parcella, "metodo_pagamento", "")),
        "detailHref": f"/fatturazione/{pid}" if pid else "",
        "pdfHref": f"/fatturazione/{pid}/pdf" if pid else "",
        "xmlHref": f"/fatturazione/{pid}/xml" if pid else "",
    }
    payload.update(_sdi_status_payload(parcella))
    return payload


def _audit(get_utenti: Callable[[], Any], current_user: Any, action: str, resource_id: str, ip_address: str) -> None:
    try:
        registrar = getattr(get_utenti(), "registra_evento", None)
        if not callable(registrar):
            return
        registrar(
            action,
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="parcella",
            risorsa_id=resource_id,
            dettagli="origine=react_operational_full",
            ip=ip_address,
            esito="OK",
        )
    except Exception:
        return


def _can(user: Any, permission: str) -> bool:
    checker = getattr(user, "ha_permesso", None)
    return bool(user and callable(checker) and checker(permission))


def _safe_payload_fields(payload: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    unknown = {key for key in payload if key not in _ALLOWED_STATUS_FIELDS}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        errors[field] = "Importo calcolato non accettato dalla pagina."
    return errors


def _status_result(item: Any) -> dict[str, Any]:
    status = _enum(getattr(item, "stato", ""))
    payload = {
        "id": _text(getattr(item, "id", "")),
        "number": _text(getattr(item, "numero", "")),
        "amountDisplay": _money(getattr(item, "totale", 0)),
        "state": status,
        "stateLabel": _status_label(status),
        "stateTone": _status_tone(status),
        "isProforma": _is_proforma(item),
        "documentKindLabel": _document_kind_label(item),
        "paidAt": _date_label(getattr(item, "data_pagamento", "")),
        "paymentMethod": _text(getattr(item, "metodo_pagamento", "")),
    }
    payload.update(_sdi_status_payload(item))
    return payload


def _safe_file_token(value: str, fallback: str = "documento") -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", _text(value) or fallback).strip(".-")
    return token[:120] or fallback


def _safe_storage_root(storage_root: str | Path) -> Path:
    root = Path(storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Percorso documento fatturazione non autorizzato.")
    return resolved


def _workflow_data(parcella: Any) -> dict[str, Any]:
    data = getattr(parcella, "dati_personalizzati", {}) or {}
    if not isinstance(data, dict):
        data = {}
    workflow = data.get("fatturapa_workflow")
    return workflow if isinstance(workflow, dict) else {}


def _set_workflow_data(parcella: Any, workflow: dict[str, Any]) -> dict[str, Any]:
    data = getattr(parcella, "dati_personalizzati", {}) or {}
    if not isinstance(data, dict):
        data = {}
    data = dict(data)
    data["fatturapa_workflow"] = dict(workflow)
    return data


def _workflow_payload(parcella: Any, *, sdi_cfg: Any | None = None) -> dict[str, Any]:
    workflow = _workflow_data(parcella)
    signed_xml = workflow.get("signed_xml") if isinstance(workflow.get("signed_xml"), dict) else {}
    sdi_send = workflow.get("sdi_send") if isinstance(workflow.get("sdi_send"), dict) else {}
    commercialista = workflow.get("commercialista") if isinstance(workflow.get("commercialista"), dict) else {}
    return {
        "signedXml": signed_xml,
        "sdiSend": sdi_send,
        "commercialista": commercialista,
        "sdiPecAddress": _text(getattr(sdi_cfg, "pec_notifiche", "")) if sdi_cfg is not None else "",
        "commercialistaEmail": _text(getattr(sdi_cfg, "email_commercialista", "")) if sdi_cfg is not None else "",
        "commercialistaPec": _text(getattr(sdi_cfg, "pec_commercialista", "")) if sdi_cfg is not None else "",
        "commercialistaName": _text(getattr(sdi_cfg, "nome_commercialista", "")) if sdi_cfg is not None else "",
    }


def _float_value(value: Any, field: str, errors: dict[str, str], *, minimum: float = 0.0, default: float = 0.0) -> float:
    raw = _text(value)
    if not raw:
        return default
    try:
        parsed = float(raw.replace(",", "."))
    except ValueError:
        errors[field] = "Valore numerico non valido."
        return default
    if parsed < minimum:
        errors[field] = f"Inserisci un valore maggiore o uguale a {minimum:g}."
        return default
    return parsed


def _validate_detail_voices(raw_voices: Any) -> tuple[list[VoceParcella], dict[str, str]]:
    errors: dict[str, str] = {}
    if not isinstance(raw_voices, list) or not raw_voices:
        return [], {"voci": "Aggiungi almeno una voce."}
    voices: list[VoceParcella] = []
    for index, raw_item in enumerate(raw_voices):
        if not isinstance(raw_item, dict):
            errors[f"voci.{index}"] = "Voce non valida."
            continue
        unknown = {key for key in raw_item if key not in {"descrizione", "quantita", "prezzo_unitario", "tipo"}}
        if unknown:
            errors[f"voci.{index}"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
        descrizione = _text(raw_item.get("descrizione"), limit=240)
        if not descrizione:
            errors[f"voci.{index}.descrizione"] = "Inserisci la descrizione della voce."
        quantita = _float_value(raw_item.get("quantita"), f"voci.{index}.quantita", errors, minimum=0.01, default=1.0)
        prezzo = _float_value(raw_item.get("prezzo_unitario"), f"voci.{index}.prezzo_unitario", errors, minimum=0.0, default=0.0)
        tipo = _text(raw_item.get("tipo") or "ONORARIO", limit=40).upper() or "ONORARIO"
        if descrizione:
            voices.append(VoceParcella(descrizione=descrizione, quantita=quantita, prezzo_unitario=prezzo, tipo=tipo))
    if not voices and "voci" not in errors:
        errors["voci"] = "Aggiungi almeno una voce valida."
    return voices, errors


def _xml_bytes(parcella: Any, cliente: Any, config: dict[str, Any]) -> tuple[bytes, str]:
    from pct.fattura_pa import genera_xml_fattura_pa, nome_file_fattura_pa

    pec_cl = ""
    if cliente and getattr(cliente, "recapiti", None):
        pec_cl = getattr(cliente.recapiti, "pec", "")
    studio_piva = _text(getattr(parcella, "studio_piva", "")) or _text(config.get("STUDIO_PIVA"))
    xml = genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome=_text(config.get("STUDIO_NOME")) or "Studio Legale",
        studio_piva=studio_piva,
        studio_cf=_text(getattr(parcella, "studio_cf", "")) or _text(config.get("STUDIO_CF")),
        studio_indirizzo=_text(getattr(parcella, "studio_indirizzo", "")) or _text(config.get("STUDIO_INDIRIZZO")),
        pec_destinatario=pec_cl,
    )
    return xml, nome_file_fattura_pa(studio_piva, getattr(parcella, "numero", ""))


def _pdf_bytes(parcella: Any, cliente: Any, fascicolo: Any, config: dict[str, Any]) -> tuple[bytes, str]:
    from web.blueprints.fatturazione import _genera_pdf

    buf = _genera_pdf(parcella, cliente, fascicolo, config)
    name = f"parcella_{_safe_file_token(str(getattr(parcella, 'numero', '')).replace('/', '-'))}.pdf"
    return buf.getvalue(), name


def _write_bytes(root: Path, filename: str, payload: bytes) -> dict[str, Any]:
    safe_name = _safe_file_token(filename)
    path = _ensure_inside(root, root / safe_name)
    path.write_bytes(payload)
    return {
        "fileName": safe_name,
        "storageFile": safe_name,
        "sizeBytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "storedAt": _rome_now(),
    }


def _stored_file(root: Path, metadata: dict[str, Any]) -> Path:
    name = _safe_file_token(_text(metadata.get("storageFile") or metadata.get("fileName")))
    if not name:
        raise ValueError("File firmato non disponibile.")
    path = _ensure_inside(root, root / name)
    if not path.is_file():
        raise ValueError("File firmato non trovato nello storage fatturazione.")
    return path


def _attachment_from_path(path: Path, *, filename: str | None = None) -> dict[str, Any]:
    payload = path.read_bytes()
    name = filename or path.name
    return {
        "filename": name,
        "storageFile": path.name,
        "mime_type": mimetypes.guess_type(name)[0] or "application/octet-stream",
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "content_base64": base64.b64encode(payload).decode("ascii"),
    }


def _pec_cfg_payload(pec_cfg: Any) -> dict[str, Any]:
    smtp_port = int(getattr(pec_cfg, "smtp_port", 465) or 465)
    use_ssl = bool(getattr(pec_cfg, "use_ssl", smtp_port == 465))
    indirizzo = _text(getattr(pec_cfg, "indirizzo", ""))
    return {
        "indirizzo": indirizzo,
        "username": _text(getattr(pec_cfg, "username", "")) or indirizzo,
        "from": indirizzo,
        "smtp_host": _text(getattr(pec_cfg, "smtp_host", "")),
        "smtp_port": smtp_port,
        "use_ssl": use_ssl,
        "use_tls": bool(getattr(pec_cfg, "use_tls", not use_ssl)),
    }


def _local_pec_payload(
    *,
    pec_cfg: Any,
    destinatario: str,
    oggetto: str,
    corpo: str,
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        **_pec_cfg_payload(pec_cfg),
        "to": destinatario,
        "subject": oggetto,
        "body": corpo,
        "attachments": attachments,
    }
    return {
        "endpoint": f"{_LOCAL_SIGNER_BASE_URL}/pec/send",
        "requiresCredential": True,
        "channel": "local_signer",
        "message": "Invio PEC reale dal PC locale tramite Local Signer. La credenziale non viene salvata da IUSENTRA.",
        "payload": payload,
    }


def build_react_fatturazione_detail_payload(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    id_documento: str,
    sdi_cfg: Any | None = None,
) -> tuple[dict[str, Any], int]:
    try:
        parcella = get_fatturazione().get(id_documento)
    except Exception:
        parcella = None
    if not parcella:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    clienti = {_text(getattr(item, "id", "")): item for item in _safe_all(get_clienti, "tutti")}
    fascicoli = {_text(getattr(item, "id", "")): item for item in _safe_all(get_fascicoli, "tutti")}
    item = _record(parcella, clienti, fascicoli)
    item["voci"] = [
        {
            "descrizione": _text(getattr(voce, "descrizione", "")),
            "quantita": _text(getattr(voce, "quantita", "")),
            "prezzoUnitario": _text(getattr(voce, "prezzo_unitario", "")),
            "prezzoDisplay": _money(getattr(voce, "prezzo_unitario", 0)),
            "importoDisplay": _money(getattr(voce, "importo", 0)),
            "tipo": _text(getattr(voce, "tipo", "")) or "ONORARIO",
        }
        for voce in list(getattr(parcella, "voci", []) or [])
    ]
    item["note"] = _text(getattr(parcella, "note", ""))
    item["workflow"] = _workflow_payload(parcella, sdi_cfg=sdi_cfg)
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "writes": "json_api", "route_owner": "react_shell", "operational": True},
        "item": item,
        "warnings": [],
    }, 200


def update_react_fatturazione_detail(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    errors: dict[str, str] = {}
    unknown = {key for key in payload if key not in _ALLOWED_DETAIL_FIELDS}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    for field in sorted(_CANONICAL_AMOUNT_FIELDS & set(payload.keys())):
        errors[field] = "Importo calcolato non accettato dalla pagina."
    voices, voice_errors = _validate_detail_voices(payload.get("voci"))
    errors.update(voice_errors)
    if errors:
        return {"ok": False, "message": "Controlla le voci della parcella.", "errors": errors, "item": None}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if not parcella:
            raise KeyError(id_documento)
        if _text(getattr(parcella, "sdi_data_invio", "")):
            return {
                "ok": False,
                "message": "Documento già inviato a SdI: le voci non possono essere modificate da questa pagina.",
                "errors": {"sdi": "Per una fattura già inviata va registrato l'esito o predisposta una rettifica."},
                "item": None,
            }, 409
        updated = manager.aggiorna(id_documento, voci=voices, note=_text(payload.get("note"), limit=2000))
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "fatturazione.dettaglio", id_documento, ip_address)
    return {"ok": True, "message": "Dettaglio parcella aggiornato.", "errors": {}, "item": _status_result(updated)}, 200


def prepare_react_fatturazione_xml_signature(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.leggi"):
        return {"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}, 403
    try:
        parcella = get_fatturazione().get(id_documento)
    except Exception:
        parcella = None
    if not parcella:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}}, 404
    cliente = get_clienti().get(getattr(parcella, "id_cliente", ""))
    xml, filename = _xml_bytes(parcella, cliente, config)
    return {
        "ok": True,
        "message": "XML FatturaPA pronto per la firma digitale.",
        "document": {
            "fileName": filename,
            "mimeType": "application/xml",
            "sizeBytes": len(xml),
            "sha256": hashlib.sha256(xml).hexdigest().upper(),
            "contentBase64": base64.b64encode(xml).decode("ascii"),
        },
        "localSigner": {
            "endpoint": f"{_LOCAL_SIGNER_BASE_URL}/firma",
            "requiresPin": True,
            "message": "Inserisci il PIN solo nel pannello locale: viene usato dal Local Signer sul PC.",
        },
        "errors": {},
    }, 200


def confirm_react_fatturazione_xml_signed(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    storage_root: str | Path,
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "workflow": None}, 403
    signed_b64 = _text(payload.get("signed_base64") or payload.get("firmato_b64") or payload.get("contentBase64"))
    original_name = _safe_file_token(_text(payload.get("fileName") or payload.get("filename")) or f"fattura-{id_documento}.xml")
    if not signed_b64:
        return {"ok": False, "message": "File XML firmato mancante.", "errors": {"signed_base64": "Firma non ricevuta dal Local Signer."}, "workflow": None}, 400
    try:
        signed = base64.b64decode(signed_b64, validate=True)
    except Exception:
        return {"ok": False, "message": "File firmato non valido.", "errors": {"signed_base64": "Contenuto base64 non valido."}, "workflow": None}, 400
    if len(signed) <= 128 or len(signed) > _MAX_SIGNED_XML_BYTES:
        return {"ok": False, "message": "Dimensione XML firmato non valida.", "errors": {"signed_base64": "Controlla il file generato dal Local Signer."}, "workflow": None}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if not parcella:
            raise KeyError(id_documento)
        root = _safe_storage_root(Path(storage_root) / _safe_file_token(id_documento, "fattura"))
        signed_name = original_name if original_name.lower().endswith(".p7m") else f"{original_name}.p7m"
        stored = _write_bytes(root, signed_name, signed)
        workflow = _workflow_data(parcella)
        workflow["signed_xml"] = {
            **stored,
            "originalFileName": original_name,
            "signedBy": _text(payload.get("intestatario"), limit=160),
            "certificateExpires": _text(payload.get("scadenza"), limit=40),
            "localSigner": True,
        }
        updated = manager.aggiorna(
            id_documento,
            dati_personalizzati=_set_workflow_data(parcella, workflow),
            sdi_stato=_text(getattr(parcella, "sdi_stato", "")) or "PREPARATA",
            sdi_note=_text(getattr(parcella, "sdi_note", "")) or "XML FatturaPA firmato digitalmente con Local Signer.",
        )
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "workflow": None}, 404
    except ValueError as exc:
        return {"ok": False, "message": "Salvataggio firma non completato.", "errors": {"storage": _text(exc)}, "workflow": None}, 400
    _audit(get_utenti, current_user, "fatturazione.xml_firmato", id_documento, ip_address)
    return {"ok": True, "message": "XML firmato salvato nella fattura.", "errors": {}, "item": _status_result(updated), "workflow": _workflow_payload(updated)}, 200


def prepare_react_fatturazione_sdi_pec(
    *,
    get_fatturazione: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    storage_root: str | Path,
    pec_cfg: Any,
    sdi_cfg: Any,
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.leggi"):
        return {"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}, 403
    try:
        parcella = get_fatturazione().get(id_documento)
    except Exception:
        parcella = None
    if not parcella:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}}, 404
    destinatario = _text(getattr(sdi_cfg, "pec_notifiche", ""))
    if not destinatario:
        return {"ok": False, "message": "PEC per notifiche SdI non configurata.", "errors": {"pec_notifiche": "Compila la PEC per notifiche SdI in Impostazioni > Canali SdI."}}, 400
    signed_xml = _workflow_data(parcella).get("signed_xml")
    if not isinstance(signed_xml, dict):
        return {"ok": False, "message": "Firma XML richiesta prima della PEC SdI.", "errors": {"signed_xml": "Firma l'XML FatturaPA con Local Signer."}}, 400
    try:
        root = _safe_storage_root(Path(storage_root) / _safe_file_token(id_documento, "fattura"))
        signed_path = _stored_file(root, signed_xml)
    except ValueError as exc:
        return {"ok": False, "message": "XML firmato non disponibile.", "errors": {"signed_xml": _text(exc)}}, 400
    numero = _text(getattr(parcella, "numero", "")) or id_documento
    oggetto = f"Invio FatturaPA {numero} a Sistema di Interscambio"
    corpo = (
        "Si trasmette in allegato il file XML FatturaPA firmato digitalmente per l'invio al Sistema di Interscambio.\n\n"
        f"Documento IUSENTRA: {numero}\n"
        "Invio predisposto da IUSENTRA e completato dal PC locale tramite Local Signer."
    )
    local_pec = _local_pec_payload(
        pec_cfg=pec_cfg,
        destinatario=destinatario,
        oggetto=oggetto,
        corpo=corpo,
        attachments=[_attachment_from_path(signed_path, filename=_text(signed_xml.get("fileName")) or signed_path.name)],
    )
    return {
        "ok": True,
        "message": "PEC SdI pronta per controllo e invio dal PC locale.",
        "draft": {"to": destinatario, "subject": oggetto, "body": corpo, "attachments": [local_pec["payload"]["attachments"][0]]},
        "localPec": local_pec,
        "errors": {},
    }, 200


def confirm_react_fatturazione_sdi_sent(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    message_id = _text(payload.get("message_id") or payload.get("messageId"), limit=240)
    if not message_id:
        return {"ok": False, "message": "Message-ID PEC mancante.", "errors": {"message_id": "Conferma Local Signer incompleta."}, "item": None}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if not parcella:
            raise KeyError(id_documento)
        sent_at = _rome_now()
        workflow = _workflow_data(parcella)
        workflow["sdi_send"] = {
            "sentAt": sent_at,
            "messageId": message_id,
            "recipient": _text(payload.get("destinatario") or payload.get("to"), limit=240),
            "subject": _text(payload.get("oggetto") or payload.get("subject"), limit=240),
            "channel": "PEC locale tramite Local Signer",
        }
        updated = manager.aggiorna(
            id_documento,
            dati_personalizzati=_set_workflow_data(parcella, workflow),
            sdi_stato="INVIATA",
            sdi_canale="PEC locale tramite Local Signer",
            sdi_data_invio=sent_at,
            sdi_ricevuta=message_id,
            sdi_note="PEC SdI inviata dal PC locale; attendere e registrare la ricevuta SdI.",
        )
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "fatturazione.sdi_pec_inviata", id_documento, ip_address)
    return {"ok": True, "message": "Invio PEC SdI registrato sulla fattura.", "errors": {}, "item": _status_result(updated), "workflow": _workflow_payload(updated)}, 200


def record_react_fatturazione_sdi_outcome(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    unknown = {key for key in payload if key not in _ALLOWED_SDI_OUTCOME_FIELDS}
    errors: dict[str, str] = {}
    if unknown:
        errors["payload"] = "Campi non consentiti: " + ", ".join(sorted(unknown))
    status = _text(payload.get("sdi_stato"), limit=40).upper()
    if status not in _SDI_OUTCOME_STATUSES:
        errors["sdi_stato"] = "Seleziona un esito SdI valido."
    if errors:
        return {"ok": False, "message": "Esito SdI non registrato.", "errors": errors, "item": None}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if not parcella:
            raise KeyError(id_documento)
        updated = manager.aggiorna(
            id_documento,
            sdi_stato=status,
            sdi_identificativo=_text(payload.get("sdi_identificativo"), limit=120) or _text(getattr(parcella, "sdi_identificativo", "")),
            sdi_data_esito=_text(payload.get("sdi_data_esito"), limit=40) or _rome_now(),
            sdi_ricevuta=_text(payload.get("sdi_ricevuta"), limit=240) or _text(getattr(parcella, "sdi_ricevuta", "")),
            sdi_note=_text(payload.get("sdi_note"), limit=500),
        )
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "fatturazione.sdi_esito", id_documento, ip_address)
    return {"ok": True, "message": "Esito SdI registrato sulla fattura.", "errors": {}, "item": _status_result(updated), "workflow": _workflow_payload(updated)}, 200


def prepare_react_fatturazione_commercialista(
    *,
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    storage_root: str | Path,
    pec_cfg: Any,
    sdi_cfg: Any,
    config: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.leggi"):
        return {"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}, 403
    channel = _text(payload.get("channel") or payload.get("canale") or "ordinaria").lower()
    attachment_mode = _text(payload.get("attachments") or payload.get("allegati") or "pdf").lower()
    errors: dict[str, str] = {}
    if channel not in _ALLOWED_COMMERCIALISTA_CHANNELS:
        errors["channel"] = "Scegli email ordinaria o PEC."
    if attachment_mode not in _ALLOWED_COMMERCIALISTA_ATTACHMENTS:
        errors["attachments"] = "Scegli PDF oppure PDF più XML firmato."
    email_commercialista = _text(getattr(sdi_cfg, "email_commercialista", ""))
    pec_commercialista = _text(getattr(sdi_cfg, "pec_commercialista", "")) or email_commercialista
    destinatario = pec_commercialista if channel == "pec" else email_commercialista
    if not destinatario:
        if channel == "pec":
            errors["pec_commercialista"] = "Compila la PEC commercialista in Impostazioni > Canali SdI."
        else:
            errors["email_commercialista"] = "Compila l'email commercialista in Impostazioni > Canali SdI."
    if errors:
        return {"ok": False, "message": "Bozza commercialista non preparata.", "errors": errors}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
    except Exception:
        parcella = None
    if not parcella:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}}, 404
    clienti = {_text(getattr(item, "id", "")): item for item in _safe_all(get_clienti, "tutti")}
    fascicoli = {_text(getattr(item, "id", "")): item for item in _safe_all(get_fascicoli, "tutti")}
    cliente = clienti.get(_text(getattr(parcella, "id_cliente", "")))
    fascicolo = fascicoli.get(_text(getattr(parcella, "id_fascicolo", "")))
    try:
        root = _safe_storage_root(Path(storage_root) / _safe_file_token(id_documento, "fattura"))
        pdf, pdf_name = _pdf_bytes(parcella, cliente, fascicolo, config)
        pdf_meta = _write_bytes(root, pdf_name, pdf)
        attachment_paths = [_ensure_inside(root, root / pdf_meta["storageFile"])]
        if attachment_mode == "pdf_xml_firmato":
            signed_xml = _workflow_data(parcella).get("signed_xml")
            if not isinstance(signed_xml, dict):
                return {"ok": False, "message": "XML firmato richiesto per allegarlo al commercialista.", "errors": {"signed_xml": "Firma prima l'XML FatturaPA."}}, 400
            attachment_paths.append(_stored_file(root, signed_xml))
    except ValueError as exc:
        return {"ok": False, "message": "Allegati commercialista non disponibili.", "errors": {"attachments": _text(exc)}}, 400
    numero = _text(getattr(parcella, "numero", "")) or id_documento
    subject = f"Fattura {numero} - documenti per contabilità"
    body = (
        "Gentile Commercialista,\n\n"
        "trasmetto in allegato la documentazione della fattura indicata in oggetto.\n\n"
        f"Cliente: {_client_label(cliente)}\n"
        f"Numero documento: {numero}\n"
        f"Importo: {_money(getattr(parcella, 'totale', 0))}\n\n"
        "Cordiali saluti."
    )
    attachments = [_attachment_from_path(path) for path in attachment_paths]
    response = {
        "ok": True,
        "message": "Bozza commercialista pronta.",
        "draft": {
            "channel": channel,
            "to": destinatario,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "attachmentMode": attachment_mode,
        },
        "errors": {},
    }
    if channel == "pec":
        response["localPec"] = _local_pec_payload(
            pec_cfg=pec_cfg,
            destinatario=destinatario,
            oggetto=subject,
            corpo=body,
            attachments=attachments,
        )
    return response, 200


def send_react_fatturazione_commercialista_email(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    attachment_root: str | Path,
    smtp_cfg: Any,
    studio_name: str,
    messages_db_path: str,
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}, 403
    destinatario = _text(payload.get("to") or payload.get("destinatario"), limit=240)
    subject = _text(payload.get("subject") or payload.get("oggetto"), limit=240)
    body = _text(payload.get("body") or payload.get("corpo"), limit=4000)
    raw_attachments = payload.get("attachmentFiles")
    if not isinstance(raw_attachments, list):
        raw_attachments = []
    if not destinatario or not subject:
        return {"ok": False, "message": "Destinatario e oggetto sono obbligatori.", "errors": {"draft": "Completa la bozza commercialista."}}, 400
    try:
        root = _safe_storage_root(Path(attachment_root) / _safe_file_token(id_documento, "fattura"))
        attachment_paths = [
            str(_stored_file(root, {"storageFile": _safe_file_token(_text(item))}))
            for item in raw_attachments
            if _text(item)
        ]
        from pct.messaggi import ConfigEmail, ConfigMessaggistica, GestioneMessaggi, StatoMessaggio

        config = ConfigMessaggistica(
            email=ConfigEmail(
                smtp_host=_text(getattr(smtp_cfg, "host", "")),
                smtp_port=int(getattr(smtp_cfg, "port", 587) or 587),
                username=_text(getattr(smtp_cfg, "username", "")),
                password=_text(getattr(smtp_cfg, "password", "")),
                use_tls=bool(getattr(smtp_cfg, "use_tls", True)),
                mittente_email=_text(getattr(smtp_cfg, "from_address", "")),
                mittente_nome=_text(getattr(smtp_cfg, "from_name", "")) or studio_name or "Studio Legale",
            )
        )
        messaggi = GestioneMessaggi(config=config, db_path=messages_db_path)
        msg = messaggi.invia_email(
            destinatario=destinatario,
            oggetto=subject,
            corpo_testo=body,
            allegati=attachment_paths,
            id_fascicolo=_text(getattr(get_fatturazione().get(id_documento), "id_fascicolo", "")),
        )
        if getattr(msg, "stato", None) == StatoMessaggio.FALLITO:
            return {"ok": False, "message": _text(getattr(msg, "errore", "")) or "Invio email commercialista non completato.", "errors": {"smtp": "Controlla impostazioni Email SMTP."}}, 400
    except ValueError as exc:
        return {"ok": False, "message": "Allegati commercialista non disponibili.", "errors": {"attachments": _text(exc)}}, 400
    except Exception as exc:
        return {"ok": False, "message": "Invio email commercialista non disponibile.", "errors": {"server": type(exc).__name__}}, 500
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if parcella:
            workflow = _workflow_data(parcella)
            workflow["commercialista"] = {
                "sentAt": _rome_now(),
                "channel": "ordinaria",
                "messageId": _text(getattr(msg, "sid_esterno", "")),
                "recipient": destinatario,
                "attachments": [Path(path).name for path in attachment_paths],
            }
            manager.aggiorna(id_documento, dati_personalizzati=_set_workflow_data(parcella, workflow))
    except Exception:
        pass
    _audit(get_utenti, current_user, "fatturazione.commercialista_email", id_documento, ip_address)
    return {"ok": True, "message": "Email al commercialista inviata e registrata.", "errors": {}, "messageId": _text(getattr(msg, "sid_esterno", ""))}, 200


def confirm_react_fatturazione_commercialista_pec(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}, 403
    message_id = _text(payload.get("message_id") or payload.get("messageId"), limit=240)
    if not message_id:
        return {"ok": False, "message": "Message-ID PEC mancante.", "errors": {"message_id": "Conferma Local Signer incompleta."}}, 400
    try:
        manager = get_fatturazione()
        parcella = manager.get(id_documento)
        if not parcella:
            raise KeyError(id_documento)
        workflow = _workflow_data(parcella)
        workflow["commercialista"] = {
            "sentAt": _rome_now(),
            "channel": "pec",
            "messageId": message_id,
            "recipient": _text(payload.get("destinatario") or payload.get("to"), limit=240),
            "subject": _text(payload.get("oggetto") or payload.get("subject"), limit=240),
        }
        manager.aggiorna(id_documento, dati_personalizzati=_set_workflow_data(parcella, workflow))
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}}, 404
    _audit(get_utenti, current_user, "fatturazione.commercialista_pec", id_documento, ip_address)
    return {"ok": True, "message": "PEC al commercialista registrata sulla fattura.", "errors": {}, "messageId": message_id}, 200


def update_react_fatturazione_status(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    if not _can(current_user, "fatturazione.scrivi"):
        return {"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}, 403
    errors = _safe_payload_fields(payload)
    try:
        status = StatoParcella(_text(payload.get("stato")).upper())
    except ValueError:
        errors["stato"] = "Stato documento non valido."
        status = StatoParcella.BOZZA
    if errors:
        return {"ok": False, "message": "Controlla i campi evidenziati.", "errors": errors, "item": None}, 400
    try:
        manager = get_fatturazione()
        if not manager.get(id_documento):
            raise KeyError(id_documento)
        manager.cambia_stato(
            id_documento,
            status,
            data_pagamento=_text(payload.get("data_pagamento")) or None,
            metodo_pagamento=_text(payload.get("metodo_pagamento")) or None,
        )
        item = manager.get(id_documento)
    except KeyError:
        return {"ok": False, "message": "Documento non trovato.", "errors": {"id_documento": "Identificativo non valido."}, "item": None}, 404
    _audit(get_utenti, current_user, "fatturazione.stato", id_documento, ip_address)
    return {"ok": True, "message": "Stato documento aggiornato.", "errors": {}, "item": _status_result(item)}, 200


def cancel_react_fatturazione_document(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    payload = dict(payload)
    payload["stato"] = StatoParcella.ANNULLATA.value
    return update_react_fatturazione_status(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=current_user,
        id_documento=id_documento,
        payload=payload,
        ip_address=ip_address,
    )


def mark_react_fatturazione_paid(
    *,
    get_fatturazione: Callable[[], Any],
    get_utenti: Callable[[], Any],
    current_user: Any,
    id_documento: str,
    payload: dict[str, Any],
    ip_address: str = "",
) -> tuple[dict[str, Any], int]:
    payload = dict(payload)
    payload["stato"] = StatoParcella.PAGATA.value
    return update_react_fatturazione_status(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=current_user,
        id_documento=id_documento,
        payload=payload,
        ip_address=ip_address,
    )
