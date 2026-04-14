from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_TELEMATICO_REPOSITORY = Path(__file__).with_name("sql") / "20260414_telematico_repository.sql"

_RECENCY_MARKERS = ("oggi", "ultima", "ultime", "ultimo", "ultimi", "aggiorn", "corrente", "versione")
_MONITORING_MARKERS = ("xsd", "wsdl", "schema", "schemi", "specifiche", "servizi web", "reginde", "news", "versione", "errore t")
_CONSULTAZIONE_MARKERS = ("polisweb", "consult", "fascicolo", "document", "ricerca fascicoli", "accesso atti")
_IMPORT_MARKERS = ("importa", "importazione", "sincronizza", "sincronizzazione", "porta nel gestionale")
_VALIDATION_MARKERS = ("predeposito", "pre deposito", "valida", "validazione", "pdf/a", "pdfa", "busta", "t001", "t002", "t003")
_DEPOSITO_MARKERS = ("deposito", "deposita", "pec", "datiatto", "atto principale", "enc", "busta telematica")
_PDP_MARKERS = ("pdp", "penale", "querela", "procura", "atti penali", "portale deposito atti penali")
_REGINDE_MARKERS = ("reginde", "registro indirizzi", "indirizzo pec")
_PAT_MARKERS = ("pat", "siga", "ptt", "sigit")

_TOPIC_DEFAULTS = {
    "consultazione": {
        "source_ids": ["pst_giustizia", "pst_servizi_web"],
        "action_ids": ["search_pst_cases", "fetch_pst_documents"],
        "capability_ids": ["pst_consultazione_fascicoli", "pst_consultazione_documenti"],
        "channel": "PolisWeb / PST",
        "source_of_truth": "fascicolo",
    },
    "importazione": {
        "source_ids": ["pst_giustizia", "pst_servizi_web"],
        "action_ids": ["import_pst_case", "sync_existing_case"],
        "capability_ids": ["pst_import_fascicolo"],
        "channel": "PolisWeb / PST",
        "source_of_truth": "fascicolo",
    },
    "validazione": {
        "source_ids": ["pst_servizi_web", "pst_download"],
        "action_ids": ["validate_civil_deposit"],
        "capability_ids": ["pct_prevalidazione_civile"],
        "channel": "PCT civile",
        "source_of_truth": "catalogo",
    },
    "deposito": {
        "source_ids": ["pst_servizi_web", "pst_download"],
        "action_ids": ["file_civil_deposit"],
        "capability_ids": ["pct_deposito_civile"],
        "channel": "PEC + busta .enc",
        "source_of_truth": "deposito",
    },
    "deposito_penale": {
        "source_ids": ["pst_pdp_specifiche", "pst_giustizia"],
        "action_ids": ["file_criminal_deposit"],
        "capability_ids": ["pdp_deposito_penale"],
        "channel": "PDP",
        "source_of_truth": "deposito",
    },
    "monitoraggio": {
        "source_ids": ["pst_giustizia", "pst_servizi_web", "pst_download", "pst_pdp_specifiche", "pst_xsd_sici", "pst_xsd_sigp", "pst_xsd_unep", "pst_xsd_cassazione"],
        "action_ids": ["check_xsd_channel_status", "check_wsdl_catalog_status"],
        "capability_ids": ["xsd_monitoraggio", "wsdl_monitoraggio", "reginde_reference"],
        "channel": "PST / XSD / WSDL",
        "source_of_truth": "monitoraggio",
    },
    "handoff": {
        "source_ids": ["pst_giustizia"],
        "action_ids": ["handoff_other_telematic_portal"],
        "capability_ids": ["telematico_handoff_portali"],
        "channel": "Portale esterno / handoff",
        "source_of_truth": "catalogo",
    },
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    return _clean_spaces(value).lower()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _from_json(value: Any, fallback: Any) -> Any:
    text = _clean_spaces(value)
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def _query_terms(question: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for raw in _normalize_text(question).replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _build_search_text(*parts: Any) -> str:
    rows: list[str] = []
    for part in parts:
        if isinstance(part, list):
            for item in part:
                text = _clean_spaces(item)
                if text:
                    rows.append(text)
            continue
        text = _clean_spaces(part)
        if text:
            rows.append(text)
    return "\n".join(rows).strip()


def _payload_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _telematico_source_hit(payload: dict[str, Any]) -> bool:
    bag = " ".join(
        [
            _clean_spaces(payload.get("id")),
            _clean_spaces(payload.get("motore")),
            _clean_spaces(payload.get("nome")),
            _clean_spaces(payload.get("area")),
            _clean_spaces(payload.get("official_url")),
            _clean_spaces(payload.get("monitor_url")),
            _clean_spaces(payload.get("capability")),
            _clean_spaces(payload.get("notes")),
        ]
    ).lower()
    return (
        _clean_spaces(payload.get("motore")) == "procedurale_telematico"
        or "pst" in bag
        or "pdp" in bag
        or "xsd" in bag
        or "wsdl" in bag
        or "reginde" in bag
        or "telematic" in bag
    )


def _detect_topic(question: str) -> str:
    text = _normalize_text(question)
    if any(marker in text for marker in _PAT_MARKERS):
        return "handoff"
    if any(marker in text for marker in _PDP_MARKERS):
        return "deposito_penale"
    if any(marker in text for marker in _VALIDATION_MARKERS):
        return "validazione"
    if any(marker in text for marker in _IMPORT_MARKERS):
        return "importazione"
    if any(marker in text for marker in _CONSULTAZIONE_MARKERS):
        return "consultazione"
    if any(marker in text for marker in _MONITORING_MARKERS):
        return "monitoraggio"
    if any(marker in text for marker in _DEPOSITO_MARKERS):
        return "deposito"
    return "consultazione"


def _detect_channel(question: str, topic: str) -> str:
    text = _normalize_text(question)
    if any(marker in text for marker in _PAT_MARKERS):
        return "PAT / PTT / portale esterno"
    if any(marker in text for marker in _PDP_MARKERS) or topic == "deposito_penale":
        return "PDP"
    if "wsdl" in text:
        return "WSDL"
    if "xsd" in text:
        return "XSD"
    if any(marker in text for marker in _REGINDE_MARKERS):
        return "ReGIndE"
    defaults = _TOPIC_DEFAULTS.get(topic) or {}
    return str(defaults.get("channel") or "PST")


def _score_row(terms: list[str], *parts: Any) -> int:
    haystack = _build_search_text(*parts).lower()
    if not haystack or not terms:
        return 0
    return sum(1 for term in terms if term in haystack)


def _select_ranked(rows: list[dict[str, Any]], terms: list[str], score_parts: tuple[str, ...], limit: int = 5) -> list[dict[str, Any]]:
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        score = _score_row(terms, *[row.get(field) for field in score_parts])
        scored.append((score, -index, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [row for score, _index, row in scored if score > 0][:limit]
    return selected if selected else rows[:limit]


def derive_telematico_repository_db_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_repository.db"))


def derive_telematico_repository_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_repository.json"))


def derive_telematico_catalog_snapshot_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_catalog_snapshot.json"))


def derive_telematico_methods_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_methods_repository.json"))


def derive_telematico_wsdl_modules_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_wsdl_modules_repository.json"))


def derive_telematico_xsd_channels_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_xsd_channels_repository.json"))


def derive_telematico_catalog_sources_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_catalog_sources_repository.json"))


def derive_telematico_sources_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_sources_repository.json"))


def derive_telematico_capabilities_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_capabilities_repository.json"))


def derive_telematico_rules_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_rules_repository.json"))


def derive_telematico_actions_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_actions_repository.json"))


def derive_telematico_wizard_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_wizard_sections_repository.json"))


def derive_telematico_monitoring_json_path(intelligence_db_path: str) -> str:
    return str(Path(intelligence_db_path).resolve().with_name("telematico_monitoring_repository.json"))


def build_telematico_catalog_snapshot_row(snapshot: dict[str, Any], catalog_sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    row = {
        "snapshot_id": "catalog_snapshot",
        "catalog_version": _clean_spaces(snapshot.get("catalog_version")),
        "schema_version": _clean_spaces(snapshot.get("schema_version")),
        "pst_webservices_doc_version": _clean_spaces(snapshot.get("pst_webservices_doc_version")),
        "pst_webservices_wsdl_catalog_version": _clean_spaces(snapshot.get("pst_webservices_wsdl_catalog_version")),
        "pst_dm44_specifiche_revision": _clean_spaces(snapshot.get("pst_dm44_specifiche_revision")),
        "busta_max_bytes": int(snapshot.get("busta_max_bytes") or 0),
        "busta_max_mb": int(snapshot.get("busta_max_mb") or 0),
        "catalog_sources": list(catalog_sources or snapshot.get("catalog_sources") or []),
    }
    row["search_text"] = _build_search_text(
        row.get("catalog_version"),
        row.get("schema_version"),
        row.get("pst_webservices_doc_version"),
        row.get("pst_webservices_wsdl_catalog_version"),
        row.get("pst_dm44_specifiche_revision"),
        f"busta_max_mb {row.get('busta_max_mb')}",
        [item.get("label") for item in row.get("catalog_sources") if isinstance(item, dict)],
    )
    return row


def build_telematico_methods_rows(methods: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in methods or []:
        payload = item.to_dict() if hasattr(item, "to_dict") else dict(item or {})
        row = {
            "method_id": _clean_spaces(payload.get("name")),
            "label": _clean_spaces(payload.get("label")),
            "category": _clean_spaces(payload.get("category")),
            "page": int(payload.get("page") or 0),
            "current_support": _clean_spaces(payload.get("current_support")),
            "notes": _clean_spaces(payload.get("notes")),
        }
        row["search_text"] = _build_search_text(
            row.get("method_id"),
            row.get("label"),
            row.get("category"),
            row.get("current_support"),
            row.get("notes"),
        )
        rows.append(row)
    rows.sort(key=lambda row: (row.get("category") or "", row.get("label") or ""))
    return rows


def build_telematico_wsdl_rows(modules: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in modules or []:
        payload = item.to_dict() if hasattr(item, "to_dict") else dict(item or {})
        row = {
            "module_id": _clean_spaces(payload.get("key")),
            "label": _clean_spaces(payload.get("label")),
            "category": _clean_spaces(payload.get("category")),
            "notes": _clean_spaces(payload.get("notes")),
        }
        row["search_text"] = _build_search_text(row.get("module_id"), row.get("label"), row.get("category"), row.get("notes"))
        rows.append(row)
    rows.sort(key=lambda row: (row.get("category") or "", row.get("label") or ""))
    return rows


def build_telematico_xsd_rows(channels: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in channels or []:
        payload = item.to_dict() if hasattr(item, "to_dict") else dict(item or {})
        row = {
            "channel_id": _clean_spaces(payload.get("key")),
            "label": _clean_spaces(payload.get("label")),
            "area": _clean_spaces(payload.get("area")),
            "download_page_url": _clean_spaces(payload.get("download_page_url")),
            "package_name": _clean_spaces(payload.get("package_name")),
            "package_url": _clean_spaces(payload.get("package_url")),
            "package_date": _clean_spaces(payload.get("package_date")),
            "changelog_name": _clean_spaces(payload.get("changelog_name")),
            "changelog_url": _clean_spaces(payload.get("changelog_url")),
            "status": _clean_spaces(payload.get("status")),
            "status_source_news_date": _clean_spaces(payload.get("status_source_news_date")),
            "status_source_news_url": _clean_spaces(payload.get("status_source_news_url")),
            "applies_to": _clean_spaces(payload.get("applies_to")),
            "notes": _clean_spaces(payload.get("notes")),
            "production_ready": bool(payload.get("production_ready")),
        }
        row["search_text"] = _build_search_text(
            row.get("channel_id"),
            row.get("label"),
            row.get("area"),
            row.get("package_name"),
            row.get("package_date"),
            row.get("status"),
            row.get("status_source_news_date"),
            row.get("applies_to"),
            row.get("notes"),
        )
        rows.append(row)
    rows.sort(key=lambda row: row.get("channel_id") or "")
    return rows


def build_telematico_catalog_source_rows(catalog_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(catalog_sources or [], start=1):
        row = {
            "source_id": f"catalog_source_{index:03d}",
            "label": _clean_spaces(item.get("label")),
            "url": _clean_spaces(item.get("url")),
        }
        row["search_text"] = _build_search_text(row.get("label"), row.get("url"))
        rows.append(row)
    return rows


def build_telematico_sources_rows(fonti_ufficiali: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in (fonti_ufficiali or {}).values():
        payload = source.to_dict() if hasattr(source, "to_dict") else dict(source or {})
        if not _telematico_source_hit(payload):
            continue
        row = {
            "source_id": _clean_spaces(payload.get("id")),
            "nome": _clean_spaces(payload.get("nome")),
            "motore": _clean_spaces(payload.get("motore")),
            "area": _clean_spaces(payload.get("area")),
            "official_url": _clean_spaces(payload.get("official_url")),
            "monitor_url": _clean_spaces(payload.get("monitor_url")),
            "connector_kind": _clean_spaces(payload.get("connector_kind")),
            "cadence": _clean_spaces(payload.get("cadence")),
            "formats": [item for item in (_clean_spaces(x) for x in _as_list(payload.get("formats"))) if item],
            "capability": _clean_spaces(payload.get("capability")),
            "notes": _clean_spaces(payload.get("notes")),
        }
        row["search_text"] = _build_search_text(
            row.get("source_id"),
            row.get("nome"),
            row.get("motore"),
            row.get("area"),
            row.get("official_url"),
            row.get("monitor_url"),
            row.get("connector_kind"),
            row.get("cadence"),
            row.get("formats"),
            row.get("capability"),
            row.get("notes"),
        )
        rows.append(row)
    rows.sort(key=lambda row: (row.get("motore") or "", row.get("nome") or ""))
    return rows


def build_telematico_capability_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "capability_id": "pst_consultazione_fascicoli",
            "label": "Consultazione fascicoli PST",
            "topic": "consultazione",
            "channel": "PolisWeb / PST",
            "support_level": "production",
            "supports_live": True,
            "auto_sync": False,
            "handoff_required": False,
            "requires_certificate": True,
            "authentication_mode": "certificato P12 / area riservata PST",
            "source_of_truth": "fascicolo",
            "operational_text": "Ricerca fascicoli tramite SOAP/QBuilder PST. Consultazione, non deposito.",
        },
        {
            "capability_id": "pst_consultazione_documenti",
            "label": "Consultazione documenti fascicolo PST",
            "topic": "consultazione",
            "channel": "PolisWeb / PST",
            "support_level": "production",
            "supports_live": True,
            "auto_sync": False,
            "handoff_required": False,
            "requires_certificate": True,
            "authentication_mode": "certificato P12 / area riservata PST",
            "source_of_truth": "fascicolo",
            "operational_text": "Consultazione documenti dal fascicolo telematico con raggruppamento per deposito.",
        },
        {
            "capability_id": "pst_import_fascicolo",
            "label": "Importazione e sincronizzazione fascicolo PST",
            "topic": "importazione",
            "channel": "PolisWeb / PST",
            "support_level": "production",
            "supports_live": True,
            "auto_sync": True,
            "handoff_required": False,
            "requires_certificate": True,
            "authentication_mode": "certificato P12 / area riservata PST",
            "source_of_truth": "fascicolo",
            "operational_text": "Importa o sincronizza fascicoli, parti, attivita, depositi e documenti nel gestionale.",
        },
        {
            "capability_id": "pct_prevalidazione_civile",
            "label": "Pre-validazione deposito civile",
            "topic": "validazione",
            "channel": "PCT civile",
            "support_level": "production",
            "supports_live": False,
            "auto_sync": False,
            "handoff_required": False,
            "requires_certificate": False,
            "authentication_mode": "nessuna",
            "source_of_truth": "catalogo",
            "operational_text": "Controlla PDF/A, limiti busta ed errori formali prima del deposito civile.",
        },
        {
            "capability_id": "pct_deposito_civile",
            "label": "Deposito civile via PEC + busta .enc",
            "topic": "deposito",
            "channel": "PEC + busta .enc",
            "support_level": "production",
            "supports_live": True,
            "auto_sync": False,
            "handoff_required": False,
            "requires_certificate": True,
            "authentication_mode": "firma digitale + PEC + ReGIndE",
            "source_of_truth": "deposito",
            "operational_text": "Il deposito civile usa PEC, firma digitale, busta .enc e ricevute. Non passa da PolisWeb.",
        },
        {
            "capability_id": "pdp_deposito_penale",
            "label": "Deposito penale tramite PDP",
            "topic": "deposito_penale",
            "channel": "PDP",
            "support_level": "production",
            "supports_live": True,
            "auto_sync": False,
            "handoff_required": False,
            "requires_certificate": True,
            "authentication_mode": "mTLS / CNS / CIE",
            "source_of_truth": "deposito",
            "operational_text": "Il deposito penale passa dal Portale Deposito Atti Penali con mTLS/CNS/CIE, non da PEC civile.",
        },
        {
            "capability_id": "xsd_monitoraggio",
            "label": "Monitoraggio canali XSD",
            "topic": "monitoraggio",
            "channel": "PST / XSD",
            "support_level": "production",
            "supports_live": False,
            "auto_sync": True,
            "handoff_required": False,
            "requires_certificate": False,
            "authentication_mode": "nessuna",
            "source_of_truth": "monitoraggio",
            "operational_text": "Legge stato di esercizio, pacchetti e changelog dei canali XSD SICI, SIGP, UNEP e Cassazione.",
        },
        {
            "capability_id": "wsdl_monitoraggio",
            "label": "Monitoraggio documentazione e moduli WSDL",
            "topic": "monitoraggio",
            "channel": "PST / WSDL",
            "support_level": "production",
            "supports_live": False,
            "auto_sync": True,
            "handoff_required": False,
            "requires_certificate": False,
            "authentication_mode": "nessuna",
            "source_of_truth": "catalogo",
            "operational_text": "Consulta versioni documentazione servizi web PST e moduli WSDL ufficiali pubblicati.",
        },
        {
            "capability_id": "reginde_reference",
            "label": "Riferimento ReGIndE e codici formali",
            "topic": "monitoraggio",
            "channel": "ReGIndE",
            "support_level": "production",
            "supports_live": False,
            "auto_sync": True,
            "handoff_required": False,
            "requires_certificate": False,
            "authentication_mode": "nessuna",
            "source_of_truth": "catalogo",
            "operational_text": "Usa namespace e regole ufficiali ReGIndE per chiarire errori del mittente e prerequisiti tecnici.",
        },
        {
            "capability_id": "telematico_handoff_portali",
            "label": "Handoff per altri portali telematici",
            "topic": "handoff",
            "channel": "PAT / PTT / portale esterno",
            "support_level": "assistito",
            "supports_live": False,
            "auto_sync": False,
            "handoff_required": True,
            "requires_certificate": True,
            "authentication_mode": "portale esterno autenticato",
            "source_of_truth": "catalogo",
            "operational_text": "Se il canale richiesto non e coperto dai moduli PST/PDP del progetto, Lex deve dichiarare l'handoff senza inventare automazioni inesistenti.",
        },
    ]
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("capability_id"),
            row.get("label"),
            row.get("topic"),
            row.get("channel"),
            row.get("support_level"),
            row.get("authentication_mode"),
            row.get("source_of_truth"),
            row.get("operational_text"),
        )
    return rows


def build_telematico_rule_rows(max_busta_mb: int, max_busta_bytes: int, formal_error_codes: dict[str, str]) -> list[dict[str, Any]]:
    rows = [
        {
            "rule_id": "deposito_civile_canale",
            "topic": "deposito",
            "channel": "PEC + busta .enc",
            "status": "production",
            "severity": "info",
            "rule_text": "Il deposito civile avviene via PEC con busta .enc e non tramite PolisWeb.",
        },
        {
            "rule_id": "polisweb_consultazione",
            "topic": "consultazione",
            "channel": "PolisWeb / PST",
            "status": "production",
            "severity": "info",
            "rule_text": "PolisWeb e canale di consultazione e importazione fascicoli, non di deposito civile.",
        },
        {
            "rule_id": "deposito_penale_canale",
            "topic": "deposito_penale",
            "channel": "PDP",
            "status": "production",
            "severity": "info",
            "rule_text": "Il deposito penale passa dal PDP con mTLS/CNS/CIE.",
        },
        {
            "rule_id": "predocument_validation",
            "topic": "validazione",
            "channel": "PCT civile",
            "status": "production",
            "severity": "alta",
            "rule_text": "Prima del deposito civile va verificata la conformita PDF/A del documento principale.",
        },
        {
            "rule_id": "busta_limit",
            "topic": "validazione",
            "channel": "PST",
            "status": "production",
            "severity": "alta",
            "rule_text": f"La dimensione massima della busta telematica e {max_busta_mb} MB ({max_busta_bytes} byte).",
        },
    ]
    for code in ("T001", "T002", "T003"):
        rows.append(
            {
                "rule_id": f"formal_error_{code.lower()}",
                "topic": "validazione",
                "channel": "PST",
                "status": "production",
                "severity": "alta" if code == "T003" else "media",
                "rule_text": f"{code}: {_clean_spaces(formal_error_codes.get(code))}",
            }
        )
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("rule_id"),
            row.get("topic"),
            row.get("channel"),
            row.get("status"),
            row.get("severity"),
            row.get("rule_text"),
        )
    return rows


def build_telematico_action_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "action_id": "search_pst_cases",
            "label": "Ricerca fascicoli PST",
            "topic": "consultazione",
            "channel": "PolisWeb / PST",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "fascicolo",
            "notes": "Ricerca fascicoli tramite ricerca_fascicoli() con SOAP ufficiale o QBuilder.",
        },
        {
            "action_id": "fetch_pst_documents",
            "label": "Consulta documenti fascicolo PST",
            "topic": "consultazione",
            "channel": "PolisWeb / PST",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "fascicolo",
            "notes": "Consulta documenti del fascicolo tramite consultazioneAvanzataDocumenti o QBuilder.",
        },
        {
            "action_id": "import_pst_case",
            "label": "Importa fascicolo da PST",
            "topic": "importazione",
            "channel": "PolisWeb / PST",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "fascicolo",
            "notes": "Importa fascicolo, parti, attivita, depositi e documenti nel gestionale.",
        },
        {
            "action_id": "sync_existing_case",
            "label": "Sincronizza fascicolo esistente",
            "topic": "importazione",
            "channel": "PolisWeb / PST",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "fascicolo",
            "notes": "Completa un fascicolo locale gia esistente con metadati e depositi da PolisWeb.",
        },
        {
            "action_id": "validate_civil_deposit",
            "label": "Pre-validazione deposito civile",
            "topic": "validazione",
            "channel": "PCT civile",
            "supports_live": False,
            "requires_certificate": False,
            "handoff_required": False,
            "source_of_truth": "catalogo",
            "notes": "Controlla PDF/A, limiti busta e conformita base prima della creazione della busta.",
        },
        {
            "action_id": "file_civil_deposit",
            "label": "Deposita atto civile",
            "topic": "deposito",
            "channel": "PEC + busta .enc",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "deposito",
            "notes": "Crea busta, firma documenti, invia via PEC e traccia le ricevute.",
        },
        {
            "action_id": "file_criminal_deposit",
            "label": "Deposita atto penale",
            "topic": "deposito_penale",
            "channel": "PDP",
            "supports_live": True,
            "requires_certificate": True,
            "handoff_required": False,
            "source_of_truth": "deposito",
            "notes": "Deposito penale tramite PDP con mTLS/CNS/CIE.",
        },
        {
            "action_id": "check_xsd_channel_status",
            "label": "Verifica stato canale XSD",
            "topic": "monitoraggio",
            "channel": "PST / XSD",
            "supports_live": False,
            "requires_certificate": False,
            "handoff_required": False,
            "source_of_truth": "monitoraggio",
            "notes": "Legge stato produzione/preview dei canali XSD e relative news di esercizio.",
        },
        {
            "action_id": "check_wsdl_catalog_status",
            "label": "Verifica catalogo WSDL e documentazione PST",
            "topic": "monitoraggio",
            "channel": "PST / WSDL",
            "supports_live": False,
            "requires_certificate": False,
            "handoff_required": False,
            "source_of_truth": "catalogo",
            "notes": "Consulta versioni documentazione servizi web, catalogo WSDL e pagina download ufficiale PST.",
        },
        {
            "action_id": "handoff_other_telematic_portal",
            "label": "Handoff verso altri portali telematici",
            "topic": "handoff",
            "channel": "Portale esterno",
            "supports_live": False,
            "requires_certificate": True,
            "handoff_required": True,
            "source_of_truth": "catalogo",
            "notes": "Usa handoff quando il canale richiesto non e coperto dai moduli telematici attuali e serve area riservata esterna.",
        },
    ]
    for row in rows:
        row["search_text"] = _build_search_text(
            row.get("action_id"),
            row.get("label"),
            row.get("topic"),
            row.get("channel"),
            row.get("source_of_truth"),
            row.get("notes"),
        )
    return rows


def build_telematico_wizard_rows(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in sections or []:
        row = {
            "section_id": _clean_spaces(item.get("id")),
            "label": _clean_spaces(item.get("label")),
            "icon": _clean_spaces(item.get("icon")),
            "colore": _clean_spaces(item.get("colore")),
            "descrizione": _clean_spaces(item.get("descrizione")),
        }
        row["search_text"] = _build_search_text(row.get("section_id"), row.get("label"), row.get("icon"), row.get("colore"), row.get("descrizione"))
        rows.append(row)
    return rows


def build_telematico_monitoring_rows(source_rows: list[dict[str, Any]], monitor_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_index = {str(row.get("source_id") or ""): row for row in source_rows}
    latest: dict[str, dict[str, Any]] = {}
    for run in monitor_runs or []:
        source_id = _clean_spaces(run.get("source_id"))
        if not source_id or source_id not in source_index:
            continue
        previous = latest.get(source_id)
        current_key = _clean_spaces(run.get("checked_at") or run.get("ended_at") or run.get("started_at"))
        previous_key = _clean_spaces(previous.get("checked_at") or previous.get("ended_at") or previous.get("started_at")) if previous else ""
        if previous is None or current_key >= previous_key:
            latest[source_id] = dict(run)
    rows: list[dict[str, Any]] = []
    for source_id, source in source_index.items():
        run = latest.get(source_id, {})
        row = {
            "source_id": source_id,
            "nome": source.get("nome") or source_id,
            "area": source.get("area") or "",
            "status": _clean_spaces(run.get("status")),
            "status_code": int(run.get("status_code") or 0),
            "changed": bool(run.get("changed")),
            "last_check": _clean_spaces(run.get("checked_at") or run.get("ended_at") or run.get("started_at")),
            "detected_version": _clean_spaces(run.get("detected_version")),
            "detected_package": _clean_spaces(run.get("detected_package")),
            "detected_package_date": _clean_spaces(run.get("detected_package_date")),
            "detected_status": _clean_spaces(run.get("detected_status")),
            "detected_news_date": _clean_spaces(run.get("detected_news_date")),
            "warning": _clean_spaces(run.get("warning")),
            "official_url": source.get("official_url") or "",
            "monitor_url": source.get("monitor_url") or "",
        }
        row["search_text"] = _build_search_text(
            row.get("source_id"),
            row.get("nome"),
            row.get("area"),
            row.get("status"),
            row.get("detected_version"),
            row.get("detected_package"),
            row.get("detected_status"),
            row.get("warning"),
        )
        rows.append(row)
    rows.sort(key=lambda item: (item.get("nome") or "", item.get("source_id") or ""))
    return rows


class GestioneTelematicoRepository:
    def __init__(
        self,
        db_path: str,
        *,
        json_path: str,
        snapshot_json_path: str,
        methods_json_path: str,
        wsdl_json_path: str,
        xsd_json_path: str,
        catalog_sources_json_path: str,
        sources_json_path: str,
        capabilities_json_path: str,
        rules_json_path: str,
        actions_json_path: str,
        wizard_json_path: str,
        monitoring_json_path: str,
    ) -> None:
        self.db_path = str(Path(db_path))
        self.json_path = str(Path(json_path))
        self.snapshot_json_path = str(Path(snapshot_json_path))
        self.methods_json_path = str(Path(methods_json_path))
        self.wsdl_json_path = str(Path(wsdl_json_path))
        self.xsd_json_path = str(Path(xsd_json_path))
        self.catalog_sources_json_path = str(Path(catalog_sources_json_path))
        self.sources_json_path = str(Path(sources_json_path))
        self.capabilities_json_path = str(Path(capabilities_json_path))
        self.rules_json_path = str(Path(rules_json_path))
        self.actions_json_path = str(Path(actions_json_path))
        self.wizard_json_path = str(Path(wizard_json_path))
        self.monitoring_json_path = str(Path(monitoring_json_path))
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_TELEMATICO_REPOSITORY.read_text(encoding="utf-8"))

    def _set_meta(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO telematico_repository_meta (meta_key, meta_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(meta_key) DO UPDATE SET
                    meta_value=excluded.meta_value,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, _clean_spaces(value)),
            )

    def _write_json(self, path: str, payload: dict[str, Any]) -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(target)

    def rebuild_from_payload(self, payload: dict[str, Any]) -> None:
        snapshot = dict(payload.get("catalog_snapshot") or {})
        methods = list(payload.get("methods") or [])
        wsdl_modules = list(payload.get("wsdl_modules") or [])
        xsd_channels = list(payload.get("xsd_channels") or [])
        catalog_sources = list(payload.get("catalog_sources") or [])
        sources = list(payload.get("sources") or [])
        capabilities = list(payload.get("capabilities") or [])
        rules = list(payload.get("rules") or [])
        actions = list(payload.get("actions") or [])
        wizard_sections = list(payload.get("wizard_sections") or [])
        monitoring = list(payload.get("monitoring") or [])
        with self._connect() as conn:
            conn.execute("DELETE FROM telematico_catalog_snapshot")
            conn.execute("DELETE FROM telematico_methods_repository")
            conn.execute("DELETE FROM telematico_wsdl_modules_repository")
            conn.execute("DELETE FROM telematico_xsd_channels_repository")
            conn.execute("DELETE FROM telematico_catalog_sources_repository")
            conn.execute("DELETE FROM telematico_sources_repository")
            conn.execute("DELETE FROM telematico_capabilities_repository")
            conn.execute("DELETE FROM telematico_rules_repository")
            conn.execute("DELETE FROM telematico_actions_repository")
            conn.execute("DELETE FROM telematico_wizard_sections_repository")
            conn.execute("DELETE FROM telematico_monitoring_repository")
            if snapshot:
                conn.execute(
                    """
                    INSERT INTO telematico_catalog_snapshot (
                        snapshot_id, catalog_version, schema_version,
                        pst_webservices_doc_version, pst_webservices_wsdl_catalog_version,
                        pst_dm44_specifiche_revision, busta_max_bytes, busta_max_mb,
                        catalog_sources_json, search_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.get("snapshot_id"),
                        snapshot.get("catalog_version"),
                        snapshot.get("schema_version"),
                        snapshot.get("pst_webservices_doc_version"),
                        snapshot.get("pst_webservices_wsdl_catalog_version"),
                        snapshot.get("pst_dm44_specifiche_revision"),
                        int(snapshot.get("busta_max_bytes") or 0),
                        int(snapshot.get("busta_max_mb") or 0),
                        _to_json(snapshot.get("catalog_sources") or []),
                        snapshot.get("search_text") or "",
                    ),
                )
            conn.executemany(
                """
                INSERT INTO telematico_methods_repository (
                    method_id, label, category, page, current_support, notes, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (row.get("method_id"), row.get("label"), row.get("category"), int(row.get("page") or 0), row.get("current_support"), row.get("notes"), row.get("search_text"))
                    for row in methods
                ],
            )
            conn.executemany(
                """
                INSERT INTO telematico_wsdl_modules_repository (
                    module_id, label, category, notes, search_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [(row.get("module_id"), row.get("label"), row.get("category"), row.get("notes"), row.get("search_text")) for row in wsdl_modules],
            )
            conn.executemany(
                """
                INSERT INTO telematico_xsd_channels_repository (
                    channel_id, label, area, download_page_url, package_name,
                    package_url, package_date, changelog_name, changelog_url, status,
                    status_source_news_date, status_source_news_url, applies_to, notes,
                    production_ready, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("channel_id"),
                        row.get("label"),
                        row.get("area"),
                        row.get("download_page_url"),
                        row.get("package_name"),
                        row.get("package_url"),
                        row.get("package_date"),
                        row.get("changelog_name"),
                        row.get("changelog_url"),
                        row.get("status"),
                        row.get("status_source_news_date"),
                        row.get("status_source_news_url"),
                        row.get("applies_to"),
                        row.get("notes"),
                        1 if row.get("production_ready") else 0,
                        row.get("search_text"),
                    )
                    for row in xsd_channels
                ],
            )
            conn.executemany(
                "INSERT INTO telematico_catalog_sources_repository (source_id, label, url, search_text) VALUES (?, ?, ?, ?)",
                [(row.get("source_id"), row.get("label"), row.get("url"), row.get("search_text")) for row in catalog_sources],
            )
            conn.executemany(
                """
                INSERT INTO telematico_sources_repository (
                    source_id, nome, motore, area, official_url, monitor_url,
                    connector_kind, cadence, formats_json, capability, notes, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("source_id"),
                        row.get("nome"),
                        row.get("motore"),
                        row.get("area"),
                        row.get("official_url"),
                        row.get("monitor_url"),
                        row.get("connector_kind"),
                        row.get("cadence"),
                        _to_json(row.get("formats") or []),
                        row.get("capability"),
                        row.get("notes"),
                        row.get("search_text"),
                    )
                    for row in sources
                ],
            )
            conn.executemany(
                """
                INSERT INTO telematico_capabilities_repository (
                    capability_id, label, topic, channel, support_level,
                    supports_live, auto_sync, handoff_required, requires_certificate,
                    authentication_mode, source_of_truth, operational_text, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("capability_id"),
                        row.get("label"),
                        row.get("topic"),
                        row.get("channel"),
                        row.get("support_level"),
                        1 if row.get("supports_live") else 0,
                        1 if row.get("auto_sync") else 0,
                        1 if row.get("handoff_required") else 0,
                        1 if row.get("requires_certificate") else 0,
                        row.get("authentication_mode"),
                        row.get("source_of_truth"),
                        row.get("operational_text"),
                        row.get("search_text"),
                    )
                    for row in capabilities
                ],
            )
            conn.executemany(
                "INSERT INTO telematico_rules_repository (rule_id, topic, channel, status, rule_text, severity, search_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(row.get("rule_id"), row.get("topic"), row.get("channel"), row.get("status"), row.get("rule_text"), row.get("severity"), row.get("search_text")) for row in rules],
            )
            conn.executemany(
                """
                INSERT INTO telematico_actions_repository (
                    action_id, label, topic, channel, supports_live, requires_certificate,
                    handoff_required, source_of_truth, notes, search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("action_id"),
                        row.get("label"),
                        row.get("topic"),
                        row.get("channel"),
                        1 if row.get("supports_live") else 0,
                        1 if row.get("requires_certificate") else 0,
                        1 if row.get("handoff_required") else 0,
                        row.get("source_of_truth"),
                        row.get("notes"),
                        row.get("search_text"),
                    )
                    for row in actions
                ],
            )
            conn.executemany(
                "INSERT INTO telematico_wizard_sections_repository (section_id, label, icon, colore, descrizione, search_text) VALUES (?, ?, ?, ?, ?, ?)",
                [(row.get("section_id"), row.get("label"), row.get("icon"), row.get("colore"), row.get("descrizione"), row.get("search_text")) for row in wizard_sections],
            )
            conn.executemany(
                """
                INSERT INTO telematico_monitoring_repository (
                    source_id, nome, area, status, status_code, changed,
                    last_check, detected_version, detected_package, detected_package_date,
                    detected_status, detected_news_date, warning, official_url, monitor_url,
                    search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.get("source_id"),
                        row.get("nome"),
                        row.get("area"),
                        row.get("status"),
                        int(row.get("status_code") or 0),
                        1 if row.get("changed") else 0,
                        row.get("last_check"),
                        row.get("detected_version"),
                        row.get("detected_package"),
                        row.get("detected_package_date"),
                        row.get("detected_status"),
                        row.get("detected_news_date"),
                        row.get("warning"),
                        row.get("official_url"),
                        row.get("monitor_url"),
                        row.get("search_text"),
                    )
                    for row in monitoring
                ],
            )
        self._set_meta("signature", _payload_signature(payload))

    def storage_stats(self) -> dict[str, Any]:
        table_names = {
            "telematico_catalog_snapshot": "telematico_catalog_snapshot",
            "telematico_methods_repository": "telematico_methods_repository",
            "telematico_wsdl_modules_repository": "telematico_wsdl_modules_repository",
            "telematico_xsd_channels_repository": "telematico_xsd_channels_repository",
            "telematico_catalog_sources_repository": "telematico_catalog_sources_repository",
            "telematico_sources_repository": "telematico_sources_repository",
            "telematico_capabilities_repository": "telematico_capabilities_repository",
            "telematico_rules_repository": "telematico_rules_repository",
            "telematico_actions_repository": "telematico_actions_repository",
            "telematico_wizard_sections_repository": "telematico_wizard_sections_repository",
            "telematico_monitoring_repository": "telematico_monitoring_repository",
        }
        stats: dict[str, Any] = {}
        with self._connect() as conn:
            for key, table in table_names.items():
                stats[key] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return stats

    def synchronize_runtime(self, payload: dict[str, Any]) -> None:
        self.rebuild_from_payload(payload)
        self.export_repository_json()
        self.export_split_jsons()

    def load_repository_payload(self) -> dict[str, Any]:
        with self._connect() as conn:
            snapshot_row = conn.execute("SELECT * FROM telematico_catalog_snapshot LIMIT 1").fetchone()
            method_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_methods_repository ORDER BY category, label")]
            wsdl_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_wsdl_modules_repository ORDER BY category, label")]
            xsd_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_xsd_channels_repository ORDER BY channel_id")]
            catalog_source_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_catalog_sources_repository ORDER BY source_id")]
            source_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_sources_repository ORDER BY motore, nome")]
            capability_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_capabilities_repository ORDER BY topic, label")]
            rule_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_rules_repository ORDER BY topic, rule_id")]
            action_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_actions_repository ORDER BY topic, label")]
            wizard_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_wizard_sections_repository ORDER BY section_id")]
            monitoring_rows = [dict(row) for row in conn.execute("SELECT * FROM telematico_monitoring_repository ORDER BY nome, source_id")]
        for row in source_rows:
            row["formats"] = _from_json(row.pop("formats_json", "[]"), [])
        snapshot = dict(snapshot_row) if snapshot_row else {}
        if snapshot:
            snapshot["catalog_sources"] = _from_json(snapshot.pop("catalog_sources_json", "[]"), [])
        return {
            "counts": {
                "catalog_snapshot": 1 if snapshot else 0,
                "methods": len(method_rows),
                "wsdl_modules": len(wsdl_rows),
                "xsd_channels": len(xsd_rows),
                "catalog_sources": len(catalog_source_rows),
                "sources": len(source_rows),
                "capabilities": len(capability_rows),
                "rules": len(rule_rows),
                "actions": len(action_rows),
                "wizard_sections": len(wizard_rows),
                "monitoring": len(monitoring_rows),
            },
            "catalog_snapshot": snapshot,
            "methods": method_rows,
            "wsdl_modules": wsdl_rows,
            "xsd_channels": xsd_rows,
            "catalog_sources": catalog_source_rows,
            "sources": source_rows,
            "capabilities": capability_rows,
            "rules": rule_rows,
            "actions": action_rows,
            "wizard_sections": wizard_rows,
            "monitoring": monitoring_rows,
        }

    def export_repository_json(self) -> str:
        payload = self.load_repository_payload()
        output = {"repository": "telematico_repository", **payload}
        return self._write_json(self.json_path, output)

    def export_split_jsons(self, base_dir: str | None = None) -> dict[str, str]:
        payload = self.load_repository_payload()
        if base_dir:
            root = Path(base_dir)
            paths = {
                "repository": root / "telematico_repository.json",
                "catalog_snapshot": root / "telematico_catalog_snapshot.json",
                "methods": root / "telematico_methods_repository.json",
                "wsdl_modules": root / "telematico_wsdl_modules_repository.json",
                "xsd_channels": root / "telematico_xsd_channels_repository.json",
                "catalog_sources": root / "telematico_catalog_sources_repository.json",
                "sources": root / "telematico_sources_repository.json",
                "capabilities": root / "telematico_capabilities_repository.json",
                "rules": root / "telematico_rules_repository.json",
                "actions": root / "telematico_actions_repository.json",
                "wizard_sections": root / "telematico_wizard_sections_repository.json",
                "monitoring": root / "telematico_monitoring_repository.json",
            }
        else:
            paths = {
                "repository": Path(self.json_path),
                "catalog_snapshot": Path(self.snapshot_json_path),
                "methods": Path(self.methods_json_path),
                "wsdl_modules": Path(self.wsdl_json_path),
                "xsd_channels": Path(self.xsd_json_path),
                "catalog_sources": Path(self.catalog_sources_json_path),
                "sources": Path(self.sources_json_path),
                "capabilities": Path(self.capabilities_json_path),
                "rules": Path(self.rules_json_path),
                "actions": Path(self.actions_json_path),
                "wizard_sections": Path(self.wizard_json_path),
                "monitoring": Path(self.monitoring_json_path),
            }
        datasets = {
            "repository": payload,
            "catalog_snapshot": payload.get("catalog_snapshot") or {},
            "methods": payload.get("methods") or [],
            "wsdl_modules": payload.get("wsdl_modules") or [],
            "xsd_channels": payload.get("xsd_channels") or [],
            "catalog_sources": payload.get("catalog_sources") or [],
            "sources": payload.get("sources") or [],
            "capabilities": payload.get("capabilities") or [],
            "rules": payload.get("rules") or [],
            "actions": payload.get("actions") or [],
            "wizard_sections": payload.get("wizard_sections") or [],
            "monitoring": payload.get("monitoring") or [],
        }
        exported: dict[str, str] = {}
        for key, path in paths.items():
            value = datasets.get(key)
            row_count = len(value) if isinstance(value, list) else (1 if value else 0)
            rows = value if isinstance(value, list) else [value] if value else []
            exported[key] = self._write_json(str(path), {"repository": f"telematico_{key}", "count": row_count, "rows": rows})
        return exported

    def resolve_route(self, question: str) -> dict[str, Any]:
        payload = self.load_repository_payload()
        terms = _query_terms(question)
        topic = _detect_topic(question)
        channel = _detect_channel(question, topic)
        defaults = dict(_TOPIC_DEFAULTS.get(topic) or {})
        source_rows = list(payload.get("sources") or [])
        capability_rows = list(payload.get("capabilities") or [])
        action_rows = list(payload.get("actions") or [])
        rule_rows = list(payload.get("rules") or [])
        method_rows = list(payload.get("methods") or [])
        wsdl_rows = list(payload.get("wsdl_modules") or [])
        xsd_rows = list(payload.get("xsd_channels") or [])
        monitoring_rows = list(payload.get("monitoring") or [])
        wizard_rows = list(payload.get("wizard_sections") or [])

        selected_sources = _select_ranked(source_rows, terms, ("search_text",), limit=6)
        if defaults.get("source_ids"):
            default_ids = set(defaults["source_ids"])
            selected_sources = [row for row in source_rows if row.get("source_id") in default_ids] + [row for row in selected_sources if row.get("source_id") not in default_ids]
        selected_sources = selected_sources[:6]

        selected_capabilities = [row for row in capability_rows if row.get("topic") == topic][:4]
        if not selected_capabilities and defaults.get("capability_ids"):
            ids = set(defaults["capability_ids"])
            selected_capabilities = [row for row in capability_rows if row.get("capability_id") in ids][:4]

        selected_actions = [row for row in action_rows if row.get("topic") == topic][:4]
        if not selected_actions and defaults.get("action_ids"):
            ids = set(defaults["action_ids"])
            selected_actions = [row for row in action_rows if row.get("action_id") in ids][:4]

        selected_rules = _select_ranked(rule_rows, terms, ("search_text",), limit=5)
        if topic in {"validazione", "deposito", "deposito_penale"}:
            selected_rules = [row for row in selected_rules if row.get("topic") in {topic, "validazione"}][:5]
        elif topic == "consultazione":
            selected_rules = [row for row in selected_rules if row.get("topic") in {"consultazione", "deposito"}][:5]
        elif topic == "monitoraggio":
            selected_rules = [row for row in selected_rules if row.get("topic") in {"monitoraggio", "validazione"}][:5]

        selected_methods = _select_ranked(method_rows, terms, ("search_text",), limit=5)
        selected_wsdl = _select_ranked(wsdl_rows, terms, ("search_text",), limit=4)
        selected_xsd = _select_ranked(xsd_rows, terms, ("search_text",), limit=4)
        selected_wizard = _select_ranked(wizard_rows, terms, ("search_text",), limit=4)

        selected_source_ids = {row.get("source_id") for row in selected_sources if row.get("source_id")}
        selected_monitoring = [row for row in monitoring_rows if row.get("source_id") in selected_source_ids][:5]

        requires_certificate = any(bool(row.get("requires_certificate")) for row in [*selected_actions, *selected_capabilities])
        requires_handoff = topic == "handoff" or any(bool(row.get("handoff_required")) for row in [*selected_actions, *selected_capabilities])
        needs_live_monitor = topic == "monitoraggio" or any(marker in _normalize_text(question) for marker in _RECENCY_MARKERS)

        reason_bits = [f"topic {topic}", f"canale {channel}"]
        if selected_actions:
            reason_bits.append("azioni " + ", ".join(str(row.get("action_id")) for row in selected_actions[:2]))
        if selected_sources:
            reason_bits.append("fonti " + ", ".join(str(row.get("source_id")) for row in selected_sources[:3]))
        if requires_handoff:
            reason_bits.append("handoff richiesto")
        if requires_certificate:
            reason_bits.append("autenticazione tecnica necessaria")

        return {
            "topic": topic,
            "channel": channel,
            "action": selected_actions[0].get("action_id") if selected_actions else "",
            "source_of_truth": defaults.get("source_of_truth") or "catalogo",
            "needs_live_monitor": bool(needs_live_monitor),
            "requires_certificate": bool(requires_certificate),
            "requires_handoff": bool(requires_handoff),
            "reason": "; ".join(reason_bits),
            "catalog_snapshot": payload.get("catalog_snapshot") or {},
            "source_rows": selected_sources,
            "capability_rows": selected_capabilities,
            "action_rows": selected_actions,
            "rule_rows": selected_rules,
            "method_rows": selected_methods,
            "wsdl_rows": selected_wsdl,
            "xsd_rows": selected_xsd,
            "wizard_rows": selected_wizard,
            "monitoring_rows": selected_monitoring,
        }
