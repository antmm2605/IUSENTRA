"""Confronto destinazione deposito con le tabelle di Studio Telematico."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).with_name("data") / "cataloghi" / "studio_telematico_uffici_deposito.json"
OBJECT_CATALOG_PATH = Path(__file__).with_name("data") / "cataloghi" / "codici_oggetto_pst.json"

ROLE_REGISTRY_CODES = {
    "CassazioneCivile": {"CASSCI"},
    "Contenzioso": {"CC"},
    "EsecuzioniCivili": {"ESM"},
    "EspropriazioniImmobiliari": {"ESIM"},
    "GiudiceDiPace": {"GDP"},
    "Lavoro": {"LAV"},
    "Minorenni": {"MIN"},
    "ProcedimentoUnitario": {"FALL", "PU"},
    "VolontariaGiurisdizione": {"VG", "FALL"},
}

ROLE_RITES = {
    "Contenzioso": {"ordinario", "ingiunzione"},
    "EsecuzioniCivili": {"esecuzioni"},
    "EspropriazioniImmobiliari": {"esecuzioni"},
    "Lavoro": {"lavoro"},
    "VolontariaGiurisdizione": {"fallimentare"},
}


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


@lru_cache(maxsize=1)
def load_destination_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_object_catalog() -> dict[str, Any]:
    return json.loads(OBJECT_CATALOG_PATH.read_text(encoding="utf-8"))


def _object_registry_for_deposit(deposit_key: str) -> str:
    normalized = str(deposit_key or "").upper()
    if "SIECIC" in normalized:
        return "SIECIC"
    if "SIGP" in normalized:
        return "SIGP"
    if "CASSAZIONE" in normalized:
        return "CASSAZIONE"
    if "UNEP" in normalized:
        return "UNEP"
    if "SICID" in normalized:
        return "SICID"
    return ""


def _find_object_code(code: str) -> dict[str, Any] | None:
    clean_code = str(code or "").strip()
    if not clean_code:
        return None
    records = load_object_catalog().get("records") or []
    return next(
        (item for item in records if isinstance(item, dict) and str(item.get("codice") or "").strip() == clean_code),
        None,
    )


def _find_office(catalog: dict[str, Any], code: str, name: str) -> dict[str, Any] | None:
    offices = list(catalog.get("offices") or [])
    clean_code = str(code or "").strip()
    if clean_code:
        exact = next((item for item in offices if str(item.get("code") or "").strip() == clean_code), None)
        if exact:
            return exact
    clean_name = _normalise(name)
    if clean_name:
        return next((item for item in offices if _normalise(item.get("name")) == clean_name), None)
    return None


def audit_deposit_destination(
    *,
    office_code: str,
    office_name: str,
    office_pec: str,
    ministerial_role: str,
    deposit_key: str,
    object_code: str = "",
) -> dict[str, Any]:
    catalog = load_destination_catalog()
    object_catalog = load_object_catalog()
    office = _find_office(catalog, office_code, office_name)
    checks: list[dict[str, Any]] = []

    def add(code: str, passed: bool, expected: Any, actual: Any) -> None:
        checks.append({"code": code, "passed": bool(passed), "expected": expected, "actual": actual})

    add("ufficio_tabella", office is not None, office_code or office_name, (office or {}).get("code", ""))
    if not office:
        return {
            "ok": False,
            "source": catalog.get("source", {}),
            "object_source": object_catalog.get("fonte", {}),
            "office": None,
            "checks": checks,
            "errors": ["Ufficio non presente nella tabella sorgente di Studio Telematico."],
        }

    source_pec = str(office.get("pec") or "").strip().lower()
    actual_pec = str(office_pec or "").strip().lower()
    add("pec_ufficio", not source_pec or source_pec == actual_pec, source_pec, actual_pec)

    services = {str(item or "").upper() for item in office.get("services") or []}
    required_service = ""
    if deposit_key.startswith("Introduttivi_SIGP::") or "_SIGP::" in deposit_key:
        required_service = "JPW_SIGP"
    elif "SIECIC" in deposit_key:
        required_service = "JPW_SIECIC"
    elif "SICID" in deposit_key:
        required_service = "JPW_SICID"
    elif "CASSAZIONE" in deposit_key:
        required_service = "JPW_CASSCI"
    if required_service:
        add("servizio_deposito", required_service in services, required_service, sorted(services))

    registry_codes = {
        str(item.get("code") or "").upper()
        for item in office.get("registries") or []
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    }
    expected_registries = ROLE_REGISTRY_CODES.get(str(ministerial_role or "").strip(), set())
    if registry_codes and expected_registries:
        add(
            "registro_sezione",
            bool(registry_codes.intersection(expected_registries)),
            sorted(expected_registries),
            sorted(registry_codes),
        )

    source_rites = {
        str(item.get("rite") or "").strip().casefold()
        for item in office.get("rites") or []
        if isinstance(item, dict) and str(item.get("rite") or "").strip()
    }
    expected_rites = ROLE_RITES.get(str(ministerial_role or "").strip(), set())
    if source_rites and expected_rites:
        add(
            "rito_materia",
            bool(source_rites.intersection(expected_rites)),
            sorted(expected_rites),
            sorted(source_rites),
        )

    clean_object_code = str(object_code or "").strip()
    if clean_object_code:
        object_record = _find_object_code(clean_object_code)
        expected_object_registry = _object_registry_for_deposit(deposit_key)
        object_registries = {
            str(item or "").upper() for item in (object_record or {}).get("registri") or [] if str(item or "").strip()
        }
        object_ok = bool(object_record) and bool((object_record or {}).get("attivo", True))
        if expected_object_registry:
            object_ok = object_ok and expected_object_registry in object_registries
        add(
            "codice_oggetto_tabella",
            object_ok,
            {
                "codice": clean_object_code,
                "registro": expected_object_registry,
            },
            {
                "presente": bool(object_record),
                "attivo": bool((object_record or {}).get("attivo", False)),
                "registri": sorted(object_registries),
                "codice_padre": str((object_record or {}).get("codicePadre") or ""),
                "descrizione_padre": str((object_record or {}).get("descrizionePadre") or ""),
            },
        )

    errors = [str(item["code"]) for item in checks if item["passed"] is not True]
    return {
        "ok": not errors,
        "source": catalog.get("source", {}),
        "object_source": object_catalog.get("fonte", {}),
        "office": office,
        "checks": checks,
        "errors": errors,
    }
