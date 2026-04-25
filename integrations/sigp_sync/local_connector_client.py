"""Client HTTP per il Local Signer usato dal flusso SIGP/PST.

Il server IUSENTRA non scarica autonomamente dal portale e non salva PIN o
credenziali. Questo client parla con il Local Signer sul PC dello studio e usa
gli endpoint reali gia' esposti da IUSENTRA: /pst/documenti e
/pst/download-documento.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_LOCAL_SIGNER_URL = "http://127.0.0.1:27272"


@dataclass
class LocalConnectorResponse:
    ok: bool
    status_code: int
    payload: dict[str, Any]


class LocalConnectorError(RuntimeError):
    pass


class SigpLocalConnectorClient:
    def __init__(self, base_url: str = "", token: str = "", timeout: int = 45):
        self.base_url = (base_url or DEFAULT_LOCAL_SIGNER_URL).rstrip("/")
        self.token = token or ""
        self.timeout = int(timeout or 45)

    def health(self) -> LocalConnectorResponse:
        """Verifica il Local Signer reale, con fallback allo stato PST."""
        try:
            response = self._request("GET", "/ping", None)
        except LocalConnectorError:
            response = self._request("GET", "/pst/status", None)
        payload = dict(response.payload)
        payload.setdefault("authenticated", bool(payload.get("ok")))
        payload.setdefault("message", "Local Signer raggiungibile su 127.0.0.1.")
        return LocalConnectorResponse(response.ok, response.status_code, payload)

    def preview_documents(self, case_payload: dict[str, Any]) -> dict[str, Any]:
        """Richiede al Local Signer il catalogo documenti del fascicolo."""
        request_payload = _case_to_pst_payload(case_payload)
        response = self._request("POST", "/pst/documenti", request_payload)
        if not response.ok:
            raise LocalConnectorError(_error_message(response.payload, "Preview documenti PST non disponibile."))
        return response.payload

    def download_document(self, document_payload: dict[str, Any]) -> tuple[bytes, str, str]:
        """Scarica un documento tramite Local Signer e restituisce bytes, nome, MIME."""
        case_payload = _case_to_pst_payload(document_payload.get("fascicolo") or {})
        document = document_payload.get("documento") or {}
        request_payload = {
            **case_payload,
            **_document_to_pst_payload(document),
            "original": bool(document_payload.get("original", False)),
        }
        response = self._request("POST", "/pst/download-documento", request_payload)
        if not response.ok:
            raise LocalConnectorError(_error_message(response.payload, "Download documento PST non riuscito."))

        file_payload = response.payload.get("file") or response.payload
        content_b64 = (
            file_payload.get("contenuto_b64")
            or file_payload.get("content_base64")
            or file_payload.get("file_base64")
        )
        if not content_b64:
            raise LocalConnectorError("Il Local Signer non ha restituito il contenuto del file.")

        try:
            content = base64.b64decode(str(content_b64))
        except Exception as exc:  # pragma: no cover - input esterno
            raise LocalConnectorError("Contenuto file PST non decodificabile.") from exc

        filename = (
            _text(file_payload.get("nome"))
            or _text(file_payload.get("filename"))
            or _text(file_payload.get("nome_file"))
            or _text(document.get("nome_file"))
            or "documento-sigp.pdf"
        )
        mime_type = (
            _text(file_payload.get("content_type"))
            or _text(file_payload.get("mime_type"))
            or _text(document.get("mime_type"))
            or "application/octet-stream"
        )
        return content, filename, mime_type

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> LocalConnectorResponse:
        url = f"{self.base_url}{path}"
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method.upper())
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="ignore")
                try:
                    body = json.loads(raw) if raw else {"ok": True}
                except json.JSONDecodeError:
                    body = {"ok": False, "message": raw or "Risposta non JSON dal Local Signer."}
                return LocalConnectorResponse(bool(body.get("ok", response.status < 400)), int(response.status), body)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            try:
                body = json.loads(raw) if raw else {"message": str(exc)}
            except json.JSONDecodeError:
                body = {"message": raw or str(exc)}
            return LocalConnectorResponse(False, int(exc.code), body)
        except urllib.error.URLError as exc:
            raise LocalConnectorError(f"Local Signer non raggiungibile: {exc.reason}") from exc


def _case_to_pst_payload(case_payload: dict[str, Any]) -> dict[str, Any]:
    raw = _raw_dict(case_payload)
    raw_case = raw.get("fascicolo") if isinstance(raw.get("fascicolo"), dict) else {}
    numero_rg = _first(case_payload, raw, "numero_rg", "numero", "numeroRG", "rg_numero")
    anno_rg = _first(case_payload, raw, "anno_rg", "anno", "annoRG", "rg_anno")
    if not numero_rg or not anno_rg:
        numero_from_rg, anno_from_rg = _split_rg(_first(case_payload, raw, "rg", "numeroRegistro"))
        numero_rg = numero_rg or numero_from_rg
        anno_rg = anno_rg or anno_from_rg

    codice_ufficio = _first(
        case_payload,
        raw,
        "ufficio_codice",
        "codice_ufficio",
        "ufficioRicerca",
        "codicePst",
        "codice_pst",
        "codice",
    )
    if not codice_ufficio:
        raise LocalConnectorError("Codice ufficio PST/SIGP mancante nel fascicolo.")
    if not numero_rg or not anno_rg:
        raise LocalConnectorError("Numero e anno RG mancanti nel fascicolo.")

    payload = {
        "codice_ufficio": codice_ufficio,
        "numero_rg": numero_rg,
        "anno_rg": anno_rg,
        "cf_avvocato": _normalize_cf(
            _first(case_payload, raw_case, raw, "cf_avvocato", "codice_fiscale_avvocato", "cfAvvocato", "pa")
        ),
        "cert_thumbprint": _first(case_payload, raw_case, raw, "cert_thumbprint", "certThumbprint", "thumbprint"),
        "pst_session_id": _first(case_payload, raw_case, raw, "pst_session_id", "pstSessionId"),
    }
    return {key: value for key, value in payload.items() if value}


def _document_to_pst_payload(document: dict[str, Any]) -> dict[str, Any]:
    raw = _raw_dict(document)
    id_documento = _first(
        raw,
        document,
        "id_documento",
        "idDocumento",
        "id_documento_portale",
        "idDocumentoPortale",
        "documento_uid",
        "uid",
        "id",
        "id_cat",
        "idCat",
    )
    if not id_documento:
        raise LocalConnectorError("Identificativo portale del documento mancante.")

    payload = {
        "id_documento": id_documento,
        "nome_documento": _first(document, raw, "nome_file", "nomeFile", "nome", "filename", "fileName"),
        "id_cat": _first(raw, document, "id_cat", "idCat"),
        "id_repeatto": _first(raw, document, "id_repeatto", "idRepeatTo", "IDREPEATTO", "repeatTo"),
        "msg_id": _first(raw, document, "msg_id", "msgId"),
        "data_documento": _first(document, raw, "data_documento", "dataDocumento", "data", "date", "data_deposito", "dataDeposito"),
        "id_deposito_esterno": _first(document, raw, "id_deposito", "idDeposito", "idBusta", "id_busta"),
        "id_deposito_pct": _first(raw, document, "id_deposito_pct", "idDepositoPct"),
        "tipo_atto": _first(document, raw, "tipo_atto", "tipoAtto", "tipo", "type"),
    }
    return {key: value for key, value in payload.items() if value}


def _raw_dict(value: dict[str, Any]) -> dict[str, Any]:
    raw = value.get("raw") or value.get("raw_json") or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _first(*args: Any) -> str:
    mappings: list[dict[str, Any]] = [arg for arg in args if isinstance(arg, dict)]
    keys: list[str] = [arg for arg in args if isinstance(arg, str)]
    return _pick(*mappings, keys=tuple(keys))


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _pick(*mappings: dict[str, Any], keys: tuple[str, ...]) -> str:
    for mapping in mappings:
        for key in keys:
            if isinstance(mapping, dict) and mapping.get(key) not in (None, ""):
                return _text(mapping.get(key))
    return ""


def _split_rg(value: Any) -> tuple[str, str]:
    text = _text(value)
    match = re.search(r"(\d+)\s*/\s*(\d{4})", text)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def _normalize_cf(value: Any) -> str:
    text = _text(value)
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return text.strip()


def _error_message(payload: dict[str, Any], default: str) -> str:
    return _text(payload.get("message") or payload.get("errore") or payload.get("error") or default)
