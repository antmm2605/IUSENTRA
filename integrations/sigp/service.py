"""Servizio centrale del modulo SIGP."""

from __future__ import annotations

from .config import SIGP_AMBIENTI, SIGP_MODULE_NAME, SIGP_MODULE_SUBTITLE, SIGP_OFFICIAL_SOURCES
from .predeposito import check_sigp_predeposito
from .sync_service import get_sigp_sync_status
from .validator import validate_sigp_xml
from .xml_builder import build_sigp_xml
from .xsd_loader import sigp_schema_status


def get_sigp_status() -> dict:
    return {
        "module_name": SIGP_MODULE_NAME,
        "subtitle": SIGP_MODULE_SUBTITLE,
        "schema": sigp_schema_status(),
        "ambienti": SIGP_AMBIENTI,
        "sources": SIGP_OFFICIAL_SOURCES,
        "stati": SIGP_STATI_DEPOSITO,
        "sync": get_sigp_sync_status(),
    }


SIGP_STATI_DEPOSITO = {
    "bozza": "Bozza",
    "xml_generato": "XML generato",
    "xsd_valido": "XSD valido",
    "xsd_errore": "Errore validazione XSD",
    "predeposito_ok": "Predeposito superato",
    "predeposito_ko": "Predeposito non superato",
    "busta_pronta": "Busta pronta",
    "inviato": "Inviato",
    "accettato": "Accettato",
    "scartato": "Scartato",
    "errore": "Errore",
}


def prepara_deposito_sigp(data: dict) -> dict:
    precheck = check_sigp_predeposito(data)
    if not precheck["ok"]:
        return {
            "ok": False,
            "fase": "predeposito",
            "stato": "predeposito_ko",
            "errors": precheck["errors"],
            "warnings": precheck["warnings"],
            "schema": sigp_schema_status(),
        }

    xml_bytes = build_sigp_xml(data)
    validation = validate_sigp_xml(xml_bytes)
    xml_text = xml_bytes.decode("utf-8", errors="replace")

    if not validation["ok"]:
        return {
            "ok": False,
            "fase": "validazione_xsd",
            "stato": "xsd_errore",
            "errors": validation["errors"],
            "warnings": precheck["warnings"],
            "validation_code": validation.get("code", ""),
            "xml": xml_text,
            "xsd": validation.get("xsd"),
            "schema": sigp_schema_status(),
        }

    return {
        "ok": True,
        "fase": "pronto_per_busta",
        "stato": "xsd_valido",
        "errors": [],
        "warnings": precheck["warnings"],
        "xml": xml_text,
        "xsd": validation.get("xsd"),
        "schema": sigp_schema_status(),
    }
