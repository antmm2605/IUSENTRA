"""
Adapter ufficiale per i servizi web PST.

Legge il catalogo WSDL ufficiale, mantiene una cache JSON delle interrogazioni
e, quando è configurato l'endpoint SOAP reale, può sincronizzare:
- uffici giudiziari
- registri per ufficio
- riti per registro
- normativa allegata

In assenza di endpoint il modulo continua a fornire metadati ufficiali sul
catalogo WSDL e usa eventuali risultati già presenti in cache.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

from .pst_catalog import (
    PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
    PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME,
)

SOAPENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
WSDL_NS = "http://schemas.xmlsoap.org/wsdl/"
XSD_NS = "http://www.w3.org/2001/XMLSchema"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _slug(text: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in (text or "")).split())


def _first_existing_path(*candidates: str) -> str:
    for item in candidates:
        path = Path(str(item or "")).expanduser()
        if path.exists():
            return str(path)
    return str(Path(candidates[0]).expanduser()) if candidates else ""


@dataclass
class PSTCatalogQueryResult:
    items: list[dict[str, Any]]
    source: str
    method: str
    params: dict[str, Any]
    fetched_at: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PSTOfficialCatalogAdapter:
    def __init__(
        self,
        *,
        wsdl_catalog_zip_path: str = "",
        cache_path: str = "",
        catalog_endpoint: str = "",
        timeout: float = 8.0,
    ) -> None:
        default_zip = Path.home() / "Downloads" / PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME
        self.wsdl_catalog_zip_path = _first_existing_path(
            wsdl_catalog_zip_path,
            os.getenv("PCT_PST_WSDL_CATALOG_ZIP", ""),
            str(default_zip),
        )
        self.cache_path = Path(cache_path).expanduser() if cache_path else None
        self.catalog_endpoint = (catalog_endpoint or "").strip()
        self.timeout = float(timeout or 8.0)
        self._wsdl_metadata: Optional[dict[str, Any]] = None

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path:
            return {"calls": {}, "wsdl": {}}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8") or "{}")
            if not isinstance(payload, dict):
                return {"calls": {}, "wsdl": {}}
            payload.setdefault("calls", {})
            payload.setdefault("wsdl", {})
            return payload
        except Exception:
            return {"calls": {}, "wsdl": {}}

    def _save_cache(self, payload: dict[str, Any]) -> None:
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _cache_key(self, method: str, params: dict[str, Any]) -> str:
        digest = hashlib.sha256(
            json.dumps({"method": method, "params": params}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return f"{method}:{digest}"

    def _load_wsdl_metadata(self) -> dict[str, Any]:
        if self._wsdl_metadata is not None:
            return self._wsdl_metadata

        path = Path(self.wsdl_catalog_zip_path) if self.wsdl_catalog_zip_path else None
        metadata = {
            "present": False,
            "zip_path": str(path) if path else "",
            "entry_name": "",
            "target_namespace": PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE,
            "soap_address": "",
            "operations": {},
            "parsed_at": "",
            "error": "",
        }
        if not path or not path.exists():
            self._wsdl_metadata = metadata
            return metadata

        try:
            with zipfile.ZipFile(path) as zf:
                entry_name = next(
                    (
                        name
                        for name in zf.namelist()
                        if name.lower().endswith("catalogoservizibeanservice.wsdl")
                    ),
                    "",
                )
                if not entry_name:
                    raise FileNotFoundError("CatalogoServiziBeanService.wsdl non trovato nel pacchetto ufficiale.")
                root = ET.fromstring(zf.read(entry_name))
        except Exception as exc:
            metadata["error"] = str(exc)
            self._wsdl_metadata = metadata
            return metadata

        metadata["present"] = True
        metadata["entry_name"] = entry_name
        metadata["target_namespace"] = root.attrib.get("targetNamespace", metadata["target_namespace"])
        metadata["parsed_at"] = _now_iso()

        service = root.find(f".//{{{WSDL_NS}}}service")
        if service is not None:
            for child in service.iter():
                if _local_name(child.tag) == "address":
                    metadata["soap_address"] = child.attrib.get("location", "")
                    break

        operations: dict[str, dict[str, Any]] = {}
        schema_elements: dict[str, list[str]] = {}
        for schema in root.findall(f".//{{{XSD_NS}}}schema"):
            for element in schema.findall(f"{{{XSD_NS}}}element"):
                name = element.attrib.get("name", "")
                if not name:
                    continue
                seq = element.find(f".//{{{XSD_NS}}}sequence")
                if seq is None:
                    schema_elements[name] = []
                    continue
                schema_elements[name] = [
                    child.attrib.get("name", "")
                    for child in seq.findall(f"{{{XSD_NS}}}element")
                    if child.attrib.get("name")
                ]

        for operation in root.findall(f".//{{{WSDL_NS}}}portType/{{{WSDL_NS}}}operation"):
            name = operation.attrib.get("name", "")
            if not name:
                continue
            operations[name] = {
                "request_fields": schema_elements.get(name, []),
                "response_fields": schema_elements.get(f"{name}Response", []),
            }

        metadata["operations"] = operations
        cache = self._load_cache()
        cache["wsdl"] = metadata
        self._save_cache(cache)
        self._wsdl_metadata = metadata
        return metadata

    def get_runtime_snapshot(self) -> dict[str, Any]:
        wsdl = self._load_wsdl_metadata()
        return {
            "wsdl_catalog_present": bool(wsdl.get("present")),
            "wsdl_catalog_zip_path": wsdl.get("zip_path", ""),
            "wsdl_catalog_entry": wsdl.get("entry_name", ""),
            "catalog_namespace": wsdl.get("target_namespace", PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE),
            "catalog_service_address": wsdl.get("soap_address", ""),
            "endpoint_configured": bool(self.catalog_endpoint),
            "endpoint_url": self.catalog_endpoint,
            "timeout_seconds": self.timeout,
            "methods": wsdl.get("operations", {}),
            "cache_path": str(self.cache_path) if self.cache_path else "",
            "supports_live_sync": bool(self.catalog_endpoint),
            "wsdl_error": wsdl.get("error", ""),
        }

    def _element_to_python(self, element: ET.Element) -> Any:
        children = list(element)
        if not children:
            return (element.text or "").strip()
        payload: dict[str, Any] = {}
        for child in children:
            key = _local_name(child.tag)
            value = self._element_to_python(child)
            if key in payload:
                if not isinstance(payload[key], list):
                    payload[key] = [payload[key]]
                payload[key].append(value)
            else:
                payload[key] = value
        return payload

    def _parse_response_items(self, method: str, xml_bytes: bytes) -> list[dict[str, Any]]:
        root = ET.fromstring(xml_bytes)
        body = next((item for item in root.iter() if _local_name(item.tag) == "Body"), None)
        if body is None:
            return []
        response = next(
            (
                item
                for item in body
                if _local_name(item.tag) in {f"{method}Response", f"{method}Return", method}
            ),
            None,
        )
        if response is None:
            return []

        returns = [child for child in list(response) if _local_name(child.tag) == "return"]
        if not returns:
            parsed = self._element_to_python(response)
            if isinstance(parsed, dict):
                return [parsed]
            if parsed:
                return [{"value": parsed}]
            return []

        items: list[dict[str, Any]] = []
        for entry in returns:
            parsed = self._element_to_python(entry)
            if isinstance(parsed, dict):
                items.append(parsed)
            elif parsed:
                items.append({"value": parsed})
        return items

    def _call(self, method: str, params: dict[str, Any]) -> PSTCatalogQueryResult:
        cache = self._load_cache()
        cache_key = self._cache_key(method, params)
        cached_entry = cache.get("calls", {}).get(cache_key)
        if not self.catalog_endpoint:
            if cached_entry:
                return PSTCatalogQueryResult(
                    items=list(cached_entry.get("items") or []),
                    source="cache",
                    method=method,
                    params=params,
                    fetched_at=str(cached_entry.get("fetched_at") or ""),
                )
            return PSTCatalogQueryResult(items=[], source="disabled", method=method, params=params, fetched_at="", error="endpoint_non_configurato")

        wsdl = self._load_wsdl_metadata()
        namespace = wsdl.get("target_namespace") or PST_REGINDE_INTERROGAZIONI_EXT_NAMESPACE
        envelope = ET.Element(f"{{{SOAPENV_NS}}}Envelope")
        ET.SubElement(envelope, f"{{{SOAPENV_NS}}}Header")
        body = ET.SubElement(envelope, f"{{{SOAPENV_NS}}}Body")
        method_el = ET.SubElement(body, f"{{{namespace}}}{method}")
        for key, value in params.items():
            child = ET.SubElement(method_el, key)
            if value not in (None, ""):
                child.text = str(value)

        xml_payload = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
        req = urllib.request.Request(
            self.catalog_endpoint,
            data=xml_payload,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": method,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                items = self._parse_response_items(method, resp.read())
            result = PSTCatalogQueryResult(
                items=items,
                source="live",
                method=method,
                params=params,
                fetched_at=_now_iso(),
            )
            cache.setdefault("calls", {})[cache_key] = result.to_dict()
            self._save_cache(cache)
            return result
        except Exception as exc:
            if cached_entry:
                return PSTCatalogQueryResult(
                    items=list(cached_entry.get("items") or []),
                    source="cache",
                    method=method,
                    params=params,
                    fetched_at=str(cached_entry.get("fetched_at") or ""),
                    error=str(exc),
                )
            return PSTCatalogQueryResult(
                items=[],
                source="error",
                method=method,
                params=params,
                fetched_at="",
                error=str(exc),
            )

    def get_registries_for_office(self, codice_ufficio: str) -> PSTCatalogQueryResult:
        result = self._call("getRegistriFromUfficio", {"codiceUfficio": (codice_ufficio or "").strip()})
        result.items = [
            {
                "codice": str(item.get("codice", "")).strip().upper(),
                "descrizione": str(item.get("descrizione", "")).strip(),
                "codice_applicazione": str(item.get("codiceApplicazione", "")).strip(),
            }
            for item in result.items
            if str(item.get("codice", "")).strip()
        ]
        return result

    def get_riti_for_registry(self, codice_registro: str) -> PSTCatalogQueryResult:
        result = self._call("getRito", {"codiceRegistro": (codice_registro or "").strip().upper()})
        result.items = [
            {
                "id_rito": str(item.get("idRito", "")).strip(),
                "descrizione": str(item.get("descrizione", "")).strip(),
                "registro": str(item.get("registro", "")).strip().upper(),
            }
            for item in result.items
            if str(item.get("idRito", "")).strip() or str(item.get("descrizione", "")).strip()
        ]
        return result

    def get_tipi_ufficio(self, *, comune: str = "", gruppo: str = "") -> PSTCatalogQueryResult:
        result = self._call(
            "getTipiUfficio",
            {"comune": (comune or "").strip(), "gruppo": (gruppo or "").strip()},
        )
        result.items = [
            {
                "tipo_ufficio": str(item.get("tipoUfficio", "")).strip(),
                "descrizione": str(item.get("descTipoUfficio", "")).strip(),
                "gruppo": str(item.get("gruppo", "")).strip(),
            }
            for item in result.items
            if str(item.get("tipoUfficio", "")).strip() or str(item.get("descTipoUfficio", "")).strip()
        ]
        return result

    def get_normativa(self, id_atti_depositabili: str) -> PSTCatalogQueryResult:
        result = self._call(
            "getNormativa",
            {"idAttiDepositabili": (id_atti_depositabili or "").strip()},
        )
        normalized: list[dict[str, Any]] = []
        for item in result.items:
            raw = str(item.get("value", "") or item.get("return", "") or "").strip()
            if not raw:
                continue
            try:
                decoded = base64.b64decode(raw, validate=True)
            except Exception:
                decoded = b""
            normalized.append(
                {
                    "base64": raw,
                    "decoded_bytes": len(decoded),
                }
            )
        result.items = normalized
        return result

    def get_offices(
        self,
        *,
        comune: str = "",
        distretto: str = "",
        tipo_ufficio: str = "",
        penale: bool = False,
    ) -> PSTCatalogQueryResult:
        method = "getListaUfficiPenali" if penale else "getListaUfficiGiudiziari"
        result = self._call(
            method,
            {
                "distretto": (distretto or "").strip(),
                "comune": (comune or "").strip(),
                "tipoUfficio": (tipo_ufficio or "").strip(),
            },
        )
        result.items = [
            {
                "codice_ufficio": str(item.get("codiceUfficio", "")).strip(),
                "descrizione": str(item.get("descrizione", "")).strip(),
                "tipo_ufficio": str(item.get("tipoUfficio", "")).strip(),
                "tipo_ufficio_label": str(item.get("descTipoUfficio", "")).strip(),
                "distretto": str(item.get("distretto", "")).strip(),
                "comune": str(item.get("comune", "")).strip(),
                "provincia": str(item.get("provincia", "")).strip(),
                "regione": str(item.get("regione", "")).strip(),
                "pec": str(item.get("indirizzoPec", "")).strip(),
            }
            for item in result.items
            if str(item.get("codiceUfficio", "")).strip() or str(item.get("descrizione", "")).strip()
        ]
        return result

    def find_office(
        self,
        *,
        office_name: str = "",
        office_code: str = "",
        comune: str = "",
        distretto: str = "",
        penale: bool = False,
    ) -> dict[str, Any]:
        query = self.get_offices(comune=comune, distretto=distretto, penale=penale)
        wanted_code = (office_code or "").strip()
        wanted_name = _slug(office_name)
        for item in query.items:
            if wanted_code and str(item.get("codice_ufficio", "")).strip() == wanted_code:
                return {"item": item, "source": query.source, "matched_on": "code"}
        for item in query.items:
            if wanted_name and _slug(str(item.get("descrizione", ""))) == wanted_name:
                return {"item": item, "source": query.source, "matched_on": "name"}
        for item in query.items:
            if wanted_name and wanted_name in _slug(str(item.get("descrizione", ""))):
                return {"item": item, "source": query.source, "matched_on": "contains"}
        return {"item": {}, "source": query.source, "matched_on": "none"}
