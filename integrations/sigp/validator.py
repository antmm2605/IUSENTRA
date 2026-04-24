"""Validatore XSD per XML SIGP."""

from __future__ import annotations

from .xsd_loader import require_sigp_main_xsd_path


def validate_sigp_xml(xml_bytes: bytes) -> dict:
    try:
        from lxml import etree
    except Exception as exc:
        return {
            "ok": False,
            "code": "LXML_NON_DISPONIBILE",
            "errors": [{"message": f"Dipendenza lxml non disponibile: {exc}"}],
            "xsd": None,
        }

    try:
        xsd_path = require_sigp_main_xsd_path()
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "code": "SIGP_XSD_MANCANTE",
            "errors": [{"message": str(exc)}],
            "xsd": None,
        }

    try:
        xml_doc = etree.fromstring(xml_bytes)
        schema_doc = etree.parse(str(xsd_path))
        schema = etree.XMLSchema(schema_doc)
        valid = schema.validate(xml_doc)
        if valid:
            return {"ok": True, "code": "OK", "errors": [], "xsd": str(xsd_path)}
        return {
            "ok": False,
            "code": "SIGP_XSD_ERRORE",
            "errors": [
                {
                    "line": err.line,
                    "column": err.column,
                    "message": err.message,
                    "domain": err.domain_name,
                    "type": err.type_name,
                }
                for err in schema.error_log
            ],
            "xsd": str(xsd_path),
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "SIGP_VALIDAZIONE_ERRORE",
            "errors": [{"message": str(exc)}],
            "xsd": str(xsd_path),
        }
