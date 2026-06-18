"""Runtime telematico e portali estratto da web.app."""

from __future__ import annotations

import json
import os
import re
import base64
import hashlib
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Flask, g, url_for

from pct.fascicoli import Fascicolo, TipoAttivita, stato_fascicolo_da_descrizione_portale
from pct.practice_engine import DepositReceipt, EvidencePack
from pct.practice_engine.models import new_id
from pct.pst_servizi_catalogo import (
    SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA,
    SERVIZIO_PST_DETTAGLIO_ISTANZE,
    SERVIZIO_PST_DOCUMENTI_FASCICOLO,
    SERVIZIO_PST_RICERCA_SCADENZE,
)
from pct.scadenziario import TipoTermine
from web.services.portal_integration_policy import (
    MODE_DIRECT_INTERNAL,
    MODE_DIRECT_VERIFIED,
    MODE_OFFICIAL_PORTAL_ASSISTED,
    PortalIntegrationPolicy,
    get_portal_integration_policy,
)
from web.services.portale_payload_normalizer import normalize_authorized_portale_payload
from web.services.telematico_resilience import (
    describe_portale_runtime_error,
    run_portale_runtime_operation,
)


def _normalizza_data_portale(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    prefix = text[:10]
    try:
        return date.fromisoformat(prefix).isoformat()
    except ValueError:
        return prefix if re.fullmatch(r"\d{4}-\d{2}-\d{2}", prefix) else ""


def _data_portale_scadenziario_utilizzabile(value: Any, *, today: date | None = None) -> bool:
    normalized = _normalizza_data_portale(value)
    if not normalized:
        return False
    try:
        return date.fromisoformat(normalized) >= (today or date.today())
    except ValueError:
        return False


_SCADENZIARIO_DOCUMENT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Fissazione termine", ("fissazione", "termine")),
    ("Fissazione udienza", ("fissazione", "udienza")),
    ("Sostituzione udienza", ("sostituzione", "udienza")),
    ("Rinvio udienza", ("rinvio", "udienza")),
    ("Trattazione scritta", ("trattazione", "scritta")),
    ("Termine note", ("termine", "note")),
    ("Note sostituzione udienza", ("note", "sostituzione", "udienza")),
    ("Verbale udienza", ("verbale", "udienza")),
    ("Comunicazione udienza", ("comunicazione", "udienza")),
    ("Ordinanza con termini", ("ordinanza", "termine")),
    ("Decreto con termini", ("decreto", "termine")),
    ("Provvedimento con termini", ("provvedimento", "termine")),
)


def _compact_scadenziario_match_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _documenti_scadenziario_da_catalogo(documenti: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_doc in documenti or []:
        if not isinstance(raw_doc, dict):
            continue
        doc = dict(raw_doc)
        searchable = " ".join(
            str(doc.get(key) or "")
            for key in (
                "nome",
                "nome_documento",
                "filename",
                "tipo",
                "tipo_atto",
                "descrizione",
                "oggetto",
            )
        )
        compact = _compact_scadenziario_match_text(searchable)
        motivo = ""
        for label, tokens in _SCADENZIARIO_DOCUMENT_HINTS:
            if all(_compact_scadenziario_match_text(token) in compact for token in tokens):
                motivo = label
                break
        if not motivo:
            continue
        identifier = str(
            doc.get("id_documento")
            or doc.get("id_documento_portale")
            or doc.get("id_cat")
            or doc.get("nome")
            or doc.get("nome_documento")
            or ""
        ).strip()
        if identifier and identifier in seen:
            continue
        if identifier:
            seen.add(identifier)
        candidates.append(
            {
                "id_documento": str(doc.get("id_documento") or doc.get("id_documento_portale") or "").strip(),
                "id_cat": str(doc.get("id_cat") or "").strip(),
                "nome": str(doc.get("nome") or doc.get("nome_documento") or doc.get("filename") or "").strip(),
                "tipo": str(doc.get("tipo") or "").strip(),
                "tipo_atto": str(doc.get("tipo_atto") or "").strip(),
                "data_deposito": str(doc.get("data_deposito") or doc.get("data") or "").strip(),
                "motivo": motivo,
                "richiede_lettura_documento": True,
            }
        )
    return candidates


def _preview_ha_udienza_strutturata(preview: dict[str, Any]) -> bool:
    identity = dict((preview or {}).get("identity") or {})
    if _normalizza_data_portale(identity.get("data_udienza")):
        return True
    for row in list((preview or {}).get("udienze") or []):
        if isinstance(row, dict) and _normalizza_data_portale(row.get("data") or row.get("data_udienza")):
            return True
    return False


def build_telematico_runtime(
    app: Flask,
    *,
    cfg_data_path,
    get_config_studio,
    get_pdp_penale,
    get_telematico,
    get_fascicoli,
    get_clienti,
    get_soggetti,
    get_scadenziario,
    audit,
    sync_pubblica,
    normalizza_nome_match_portale,
    tipo_documento_da_item_portale,
    salva_documento_fascicolo,
    salva_albero_originale_documenti_portale,
    catalogo_documenti_portale_fascicolo,
    gruppa_catalogo_documenti_portale,
    decode_portale_downloaded_items,
    importa_documenti_portale_items,
    portale_ufficiale_label,
    ensure_pdp_penale_case_after_import,
) -> dict[str, Any]:
    _normalizza_nome_match_portale = normalizza_nome_match_portale
    _tipo_documento_da_item_portale = tipo_documento_da_item_portale
    _salva_documento_fascicolo = salva_documento_fascicolo
    _salva_albero_originale_documenti_portale = salva_albero_originale_documenti_portale
    _catalogo_documenti_portale_fascicolo = catalogo_documenti_portale_fascicolo
    _gruppa_catalogo_documenti_portale = gruppa_catalogo_documenti_portale
    _decode_portale_downloaded_items = decode_portale_downloaded_items
    _importa_documenti_portale_items = importa_documenti_portale_items
    _portale_ufficiale_label = portale_ufficiale_label
    _ensure_pdp_penale_case_after_import = ensure_pdp_penale_case_after_import
    _cfg_data_path = cfg_data_path
    def _polis_auth_mode() -> str:
        """
        Restituisce la modalità di autenticazione PST:
          'reale'  — certificato P12/PEM configurato, SOAP mTLS disponibile
          'pkcs11' — token PKCS#11 locale, autenticazione gestita dal dispositivo
          'demo'   — nessun certificato, modalità demo offline
        """
        # Controllo config studio (impostazioni UI)
        try:
            cfg = get_config_studio().config.firma
            preferito = getattr(cfg, "backend_preferito_normalizzato", "auto")
            fmt = getattr(cfg, "backend_firma_operativo_safe", "nessuno")
            if fmt == "pkcs11":
                # Token USB: la chiave privata non è esportabile e non è accessibile
                # dal container Linux su Windows → autenticazione PST solo via browser
                return "pkcs11"
            if fmt in ("p12", "pem"):
                return "reale"
            if preferito != "auto":
                return "demo"
        except Exception:
            pass
        # Fallback legacy su variabili d'ambiente solo in assenza di scelta esplicita
        if os.getenv("PCT_FIRMA_P12"):
            return "reale"
        if os.getenv("PCT_FIRMA_CERT") and os.getenv("PCT_FIRMA_KEY"):
            return "reale"
        return "demo"

    def _polis_demo_mode() -> bool:
        """True solo se non esiste alcun canale reale configurato (né P12/PEM né token PKCS#11)."""
        return _polis_auth_mode() == "demo"

    def _portal_integration_policy(portale: str) -> PortalIntegrationPolicy:
        return get_portal_integration_policy(portale, app.config)

    def _portale_usa_local_signer(portale: str) -> bool:
        portale_norm = (portale or "").strip().lower()
        if portale_norm == "pst":
            return _polis_auth_mode() == "pkcs11"
        return portale_norm in {"pdp", "pat", "ptt"} and _portal_integration_policy(portale_norm).assistant_required

    def _portale_browser_channel_required(portale: str) -> bool:
        """I portali non-PST usano il canale assistito salvo manifest diretto verificato."""
        portale_norm = (portale or "").strip().lower()
        policy = _portal_integration_policy(portale_norm)
        if policy.mode == MODE_DIRECT_INTERNAL:
            return False
        return bool(policy.assistant_required)

    def _portale_demo_mode(portale: str) -> bool:
        """I portali assistiti non devono ricadere nel banner demo del PST."""
        policy = _portal_integration_policy(portale)
        if policy.assistant_required:
            return False
        if policy.mode == MODE_DIRECT_VERIFIED:
            return False
        return _polis_demo_mode()

    def _portale_local_channel_enabled(portale: str) -> bool:
        return _portale_usa_local_signer(portale) or _portale_browser_channel_required(portale)

    def _codice_fiscale_avvocato_portale() -> str:
        try:
            cfg = get_config_studio().config
            return (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            return ""

    def _polis_cert_preferences() -> dict:
        prefer_cf = ""
        try:
            cfg = get_config_studio().config
            prefer_cf = (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            prefer_cf = ""

        if not prefer_cf:
            prefer_cf = str(os.getenv("PCT_CF_AVVOCATO", "") or "").strip().upper()

        match = re.search(r"\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b", prefer_cf)
        prefer_cf = match.group(1) if match else ""

        return {
            "auto": True,
            "prefer_issuer": "ArubaPEC EU Authentica Certificates CA G1|ArubaPEC EU Qualified Certificates CA G1|ArubaPEC",
            "prefer_subject": "auth|autent|autentica|client|tls|web",
            "prefer_cf": prefer_cf,
        }

    _PORTALE_ACQUISIZIONE_SPECS: dict[str, dict[str, Any]] = {
        "pst": {
            "id": "pst",
            "label": "PST / PolisWeb",
            "title": "Importa pratica da PST",
            "subtitle": "Ricerca, verifica e acquisizione guidata del fascicolo telematico",
            "color": "primary",
            "icon": "bi-building-fill-check",
            "home_endpoint": "polisWeb_home",
            "source_label": "Portale Servizi Telematici",
            "requires_local_signer": True,
            "official_url": "https://pst.giustizia.it/PST/",
            "assistant_label": "",
            "assistant_disclaimer": "",
            "deposit_assistant_enabled": False,
            "quick_filters": [
                "civile",
                "lavoro",
                "famiglia",
                "esecuzioni",
                "volontaria",
                "cassazione civile",
                "cassazione penale",
                "recenti",
            ],
        },
        "pdp": {
            "id": "pdp",
            "label": "PDP assistito",
            "title": "Fascicolo penale interno da PDP",
            "subtitle": "Portale ufficiale assistito, import automatico di file, ricevute ed esiti",
            "color": "danger",
            "icon": "bi-shield-exclamation",
            "home_endpoint": "pdp_home",
            "source_label": "Portale Deposito Atti Penale",
            "requires_local_signer": True,
            "official_url": "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp",
            "assistant_label": "Portale ufficiale assistito",
            "assistant_disclaimer": "IUSENTRA apre una sessione assistita locale: l'utente si autentica e opera nel PDP, poi il software importa file, ricevute ed esiti nel fascicolo interno.",
            "deposit_assistant_enabled": True,
            "quick_filters": ["dibattimento", "gip", "gup", "esecuzioni", "attivi", "recenti"],
            "search_ui": {
                "assistito_label": "Imputato / indagato",
                "assistito_placeholder": "Nome imputato o indagato...",
                "show_controparte": False,
                "show_cf": False,
                "show_oggetto": False,
            },
        },
        "pat": {
            "id": "pat",
            "label": "PAT assistito",
            "title": "Fascicolo amministrativo interno da PAT",
            "subtitle": "Portale ufficiale assistito, import automatico di file, ricevute ed esiti",
            "color": "success",
            "icon": "bi-building-check",
            "home_endpoint": "pat_home",
            "source_label": "Processo Amministrativo Telematico",
            "requires_local_signer": True,
            "official_url": "https://pe.prod.cloud.giustizia-amministrativa.it",
            "assistant_label": "Portale ufficiale assistito",
            "assistant_disclaimer": "IUSENTRA apre una sessione assistita locale: l'utente si autentica e opera nel PAT, poi il software importa file, ricevute ed esiti nel fascicolo interno.",
            "deposit_assistant_enabled": True,
            "quick_filters": ["appalti", "urbanistica", "personale", "tributi", "attivi", "recenti"],
        },
        "ptt": {
            "id": "ptt",
            "label": "PTT / SIGIT assistito",
            "title": "Fascicolo tributario interno da PTT / SIGIT",
            "subtitle": "Portale ufficiale assistito, import automatico di fascicolo, ricevute ed esiti",
            "color": "warning",
            "icon": "bi-receipt-cutoff",
            "home_endpoint": "sigit_home",
            "source_label": "Processo Tributario Telematico",
            "requires_local_signer": True,
            "official_url": "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
            "assistant_label": "Portale ufficiale assistito",
            "assistant_disclaimer": "IUSENTRA apre una sessione assistita locale: l'utente si autentica e opera nel PTT/SIGIT, poi il software importa fascicolo, ricevute ed esiti nel fascicolo tributario interno.",
            "deposit_assistant_enabled": True,
            "quick_filters": ["iva", "irpef", "imu", "registro", "attivi", "recenti"],
        },
    }

    def _spec_portale_acquisizione(portale: str) -> dict[str, Any]:
        portale_norm = (portale or "").strip().lower()
        spec = _PORTALE_ACQUISIZIONE_SPECS.get(portale_norm)
        if not spec:
            raise KeyError(f"Portale non supportato: {portale}")
        policy = _portal_integration_policy(portale_norm)
        payload = dict(spec)
        payload.update(
            {
                "integration_mode": policy.mode,
                "direct_allowed": policy.direct_allowed,
                "assistant_required": policy.assistant_required,
            }
        )
        return payload

    def _portale_import_log_path() -> Path:
        return Path(_cfg_data_path("PORTALE_IMPORT_LOG_DB"))

    def _read_json_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []
        return raw if isinstance(raw, list) else []

    def _write_json_list(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _new_import_log_id(portale: str) -> str:
        return f"{portale.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex().upper()}"

    def _append_portale_import_log(entry: dict[str, Any]) -> str:
        path = _portale_import_log_path()
        rows = _read_json_list(path)
        payload = dict(entry)
        log_id = str(payload.get("id") or _new_import_log_id(str(payload.get("portale") or "PORT")))
        payload["id"] = log_id
        payload.setdefault("created_at", datetime.now().isoformat())
        rows.append(payload)
        _write_json_list(path, rows)
        return log_id

    def _update_portale_import_log(log_id: str, updates: dict[str, Any]) -> None:
        if not log_id:
            return
        path = _portale_import_log_path()
        rows = _read_json_list(path)
        for index, row in enumerate(rows):
            if str(row.get("id") or "") != log_id:
                continue
            patched = dict(row)
            patched.update(updates)
            patched["updated_at"] = datetime.now().isoformat()
            rows[index] = patched
            _write_json_list(path, rows)
            return

    def _last_portale_import_log(portale: str) -> dict[str, Any]:
        sorgente = _portale_source_name(portale).strip().upper()
        for row in reversed(_read_json_list(_portale_import_log_path())):
            if str(row.get("portale") or "").strip().upper() == sorgente:
                return dict(row)
        return {}

    def _resolve_ufficio_nome(codice: str) -> str:
        codice = str(codice or "").strip()
        if not codice:
            return ""
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            uff = next((u for u in _get_uff(cache_path).carica() if u.get("codice") == codice), None)
            return str((uff or {}).get("nome") or codice).strip()
        except Exception:
            return codice

    def _portale_source_name(portale: str) -> str:
        return {
            "pst": "PST",
            "pdp": "PDP",
            "pat": "PAT",
            "ptt": "PTT",
        }.get((portale or "").strip().lower(), (portale or "").upper())

    def _telematico_channel_family(portale: str) -> str:
        return {
            "pst": "ministero",
            "pdp": "ministero",
            "pat": "amministrativo",
            "ptt": "tributario",
        }.get((portale or "").strip().lower(), "ministero")

    def _telematico_service_code(portale: str) -> str:
        return {
            "pst": "polisweb_consultazione",
            "pdp": "pdp_penale",
            "pat": "pat_siga",
            "ptt": "ptt_sigit",
        }.get((portale or "").strip().lower(), "polisweb_consultazione")

    def _telematico_internal_status(
        *,
        sync_status: str = "",
        native_status: str = "",
        has_documents: bool = False,
        documents_imported: bool = False,
        needs_manual_review: bool = False,
    ) -> str:
        native = str(native_status or "").strip().upper()
        sync = str(sync_status or "").strip().upper()
        if native in {"RIFIUTATO", "ERRORE_TECNICO"}:
            return "rejected" if native == "RIFIUTATO" else "technical_error"
        if needs_manual_review:
            return "manual_review_required"
        if documents_imported or sync in {"IMPORTATO", "SINCRONIZZATO"}:
            return "import_completed"
        if has_documents:
            return "download_available"
        if native in {"ACCETTATO", "AUTHORIZED"}:
            return "accepted"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        return "draft"

    def _telematico_transmission_status(native_status: str = "", has_documents: bool = False) -> str:
        native = str(native_status or "").strip().upper()
        if native == "RIFIUTATO":
            return "rejected"
        if native == "ERRORE_TECNICO":
            return "technical_error"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        if native in {"ACCETTATO", "AUTHORIZED"} or has_documents:
            return "accepted"
        return "closed"

    def _telematico_document_role(doc: dict[str, Any]) -> str:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        nome = str((doc or {}).get("nome") or "").upper()
        testo = f"{tipo} {nome}"
        if "SENTENZA" in testo:
            return "judgment"
        if "ORDINANZA" in testo or "DECRETO" in testo or "PROVVEDIMENTO" in testo:
            return "judicial_order"
        if "VERBALE" in testo or "UDIENZA" in testo:
            return "hearing_minutes"
        return "main_act" if "RICORSO" in testo or "ATTO" in testo or "MEMORIA" in testo else "attachment"

    def _is_portale_dns_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return any(
            marker in text
            for marker in (
                "nameresolutionerror",
                "failed to resolve",
                "getaddrinfo failed",
                "impossibile risolvere il nome remoto",
                "name or service not known",
                "nodename nor servname provided",
            )
        )

    def _portale_browser_guided_message(portale: str) -> str:
        labels = {
            "pst": "PST / PolisWeb",
            "pdp": "PDP Penale",
            "pat": "PAT",
            "ptt": "PTT",
        }
        label = labels.get((portale or "").strip().lower(), (portale or "").upper())
        if (portale or "").strip().lower() == "pat":
            return (
                "Per PAT si usa il portale ufficiale assistito. "
                "IUSENTRA apre una sessione locale, l'utente si autentica e opera nel PAT, "
                "poi il software importa nel fascicolo interno file, ricevute ed esiti."
            )
        if (portale or "").strip().lower() == "ptt":
            return (
                "Per PTT / SIGIT si usa il portale ufficiale assistito. "
                "IUSENTRA apre una sessione locale, l'utente si autentica e opera nel PTT/SIGIT, "
                "poi il software importa nel fascicolo tributario interno fascicolo, ricevute ed esiti."
            )
        if (portale or "").strip().lower() == "pdp":
            return (
                "Per PDP si usa il portale ufficiale assistito salvo manifest diretto verificato. "
                "IUSENTRA apre una sessione locale, l'utente si autentica e opera nel PDP, "
                "poi il software importa file, ricevute ed esiti nel fascicolo interno."
            )
        return (
            f"L'endpoint ufficiale di {label} non è raggiungibile dal backend server. "
            "Usa l'acquisizione guidata dal browser con Local Signer su questo PC."
        )

    def _normalize_portale_documents(documenti: list[dict]) -> list[dict]:
        def _flatten_document_rows(rows: list[dict], parent: dict[str, Any] | None = None) -> list[dict]:
            flattened: list[dict] = []
            for value in rows or []:
                item = dict(value or {})
                if parent and not (item.get("id_documento_padre") or item.get("parent_id_documento")):
                    parent_id = str(parent.get("id_documento") or parent.get("id_cat") or parent.get("id_reperto") or "").strip()
                    if parent_id:
                        item["id_documento_padre"] = parent_id
                        item["parent_id_documento"] = parent_id
                        item["parent_nome"] = str(parent.get("nome") or parent.get("nome_documento") or "").strip()
                        item["is_allegato"] = True
                children: list[dict] = []
                for key in ("allegati", "attachments", "children", "documenti_collegati", "docs_secondari", "docsSecondari"):
                    raw_children = item.get(key)
                    if isinstance(raw_children, list):
                        children.extend(dict(child or {}) for child in raw_children if isinstance(child, dict))
                flattened.append(item)
                if children:
                    flattened.extend(_flatten_document_rows(children, item))
            return flattened

        def _effective_id_cat(item: dict[str, Any]) -> str:
            explicit = str(item.get("id_cat") or "").strip()
            if explicit:
                return explicit
            candidates = []
            for value in list(item.get("id_documento_candidates") or []):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            for value in (
                item.get("id_documento"),
                item.get("id_documento_portale"),
                item.get("id_cat"),
                item.get("id_repeatto"),
                item.get("id_reperto"),
                item.get("msg_id"),
                item.get("numero_documento"),
                item.get("id_doc_mittente"),
            ):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            return candidates[0] if candidates else ""

        rows: list[dict] = []
        for row in _flatten_document_rows([dict(row or {}) for row in documenti or [] if isinstance(row, dict)]):
            item = dict(row or {})
            candidates = [
                str(value or "").strip()
                for value in list(item.get("id_documento_candidates") or [])
                if str(value or "").strip()
            ]
            id_documento = str(item.get("id_documento") or item.get("id_documento_portale") or "").strip()
            if id_documento and id_documento not in candidates:
                candidates.insert(0, id_documento)
            for candidate in (
                item.get("id_cat"),
                item.get("id_repeatto"),
                item.get("id_reperto"),
                item.get("msg_id"),
            ):
                text = str(candidate or "").strip()
                if text and text not in candidates:
                    candidates.append(text)
            id_cat = _effective_id_cat(item)
            rows.append(
                {
                    "id_documento": id_documento,
                    "nome": str(item.get("nome") or item.get("nome_documento") or "").strip(),
                    "tipo": str(item.get("tipo") or "").strip(),
                    "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or "").strip(),
                    "data_deposito": str(item.get("data_deposito") or item.get("data_documento") or "").strip(),
                    "mittente": str(item.get("mittente") or "").strip(),
                    "dimensione_bytes": int(item.get("dimensione_bytes") or 0),
                    "disponibile": bool(item.get("disponibile", True)),
                    "id_deposito": str(
                        item.get("id_deposito")
                        or item.get("id_deposito_esterno")
                        or item.get("id_deposito_pct")
                        or ""
                    ).strip(),
                    "id_cat": id_cat,
                    "id_repeatto": str(item.get("id_repeatto") or "").strip(),
                    "id_reperto": str(item.get("id_reperto") or "").strip(),
                    "msg_id": str(item.get("msg_id") or "").strip(),
                    "numero_documento": str(item.get("numero_documento") or "").strip(),
                    "id_doc_mittente": str(item.get("id_doc_mittente") or "").strip(),
                    "id_documento_candidates": candidates,
                    "servizio_portale": str(item.get("servizio_portale") or "").strip()
                    or SERVIZIO_PST_DOCUMENTI_FASCICOLO,
                    "sezione_portale": str(item.get("sezione_portale") or "").strip(),
                    "data_documento": str(item.get("data_documento") or "").strip(),
                    "id_documento_padre": str(item.get("id_documento_padre") or item.get("parent_id_documento") or "").strip(),
                    "parent_nome": str(item.get("parent_nome") or "").strip(),
                    "is_allegato": bool(item.get("is_allegato")),
                }
            )
        rows.sort(
            key=lambda doc: (
                doc.get("data_deposito") or "",
                doc.get("nome") or "",
                doc.get("id_documento") or "",
            ),
            reverse=True,
        )
        return rows

    def _group_portale_documents(documenti: list[dict]) -> list[dict]:
        from collections import OrderedDict

        def _solo_data(d: str) -> str:
            """Normalizza a YYYY-MM-DD (coerente con _chiave_deposito_polisweb).

            Gestisce formati multipli (ISO, italiano dd/mm/yyyy, dd-mm-yyyy)
            esattamente come _parse_data in polisWeb.py — altrimenti le chiavi
            di raggruppamento differiscono e lo stesso deposito appare duplicato.
            """
            if not d:
                return ""
            testo = str(d).strip()
            if isinstance(d, date):
                return d.strftime("%Y-%m-%d")
            # Strip parte oraria (T o spazio)
            for sep in ("T", " "):
                if sep in testo:
                    testo = testo.split(sep)[0]
                    break
            candidati = [testo]
            if len(testo) >= 10:
                candidati.append(testo[:10])
            for candidato in candidati:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(candidato, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            return testo[:10] if len(testo) >= 10 else testo

        gruppi: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        for doc in _normalize_portale_documents(documenti):
            chiave = doc["id_deposito"] or f"__{_solo_data(doc['data_deposito'])}__{doc['mittente']}"
            group = gruppi.setdefault(
                chiave,
                {
                    "id_deposito": chiave,
                    "tipo_atto": doc.get("tipo_atto") or doc.get("tipo") or "Deposito",
                    "data_deposito": doc.get("data_deposito") or "",
                    "mittente": doc.get("mittente") or "",
                    "servizio_portale": doc.get("servizio_portale") or SERVIZIO_PST_DOCUMENTI_FASCICOLO,
                    "documenti": [],
                },
            )
            if doc.get("servizio_portale") and not group.get("servizio_portale"):
                group["servizio_portale"] = doc.get("servizio_portale")
            group["documenti"].append(doc)
        return list(gruppi.values())

    def _serialize_portale_search_item(portale: str, fascicolo: Any) -> dict[str, Any]:
        portale = (portale or "").lower()
        if portale == "pst":
            payload = {
                "id_fascicolo": getattr(fascicolo, "id_fascicolo", ""),
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "ruolo": fascicolo.ruolo,
                "stato": fascicolo.stato,
                "oggetto": fascicolo.oggetto,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "parti": list(fascicolo.parti or []),
                "parti_dettaglio": list(fascicolo.parti_dettaglio or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
                "sub_procedimento": getattr(fascicolo, "sub_procedimento", ""),
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.ruolo.replace("_", " ").title()
            oggetto = fascicolo.oggetto
            assistiti = list(fascicolo.parti or [])
            controparti = []
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pdp":
            payload = {
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "tipo_registro": fascicolo.tipo_registro,
                "fase": fascicolo.fase,
                "stato": fascicolo.stato,
                "reato": fascicolo.reato,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "imputati": list(fascicolo.imputati or []),
                "parti_offese": list(fascicolo.parti_offese or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo_registro
            oggetto = fascicolo.reato
            assistiti = list(fascicolo.imputati or [])
            controparti = list(fascicolo.parti_offese or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pat":
            payload = {
                "numero_ricorso": fascicolo.numero_ricorso,
                "anno": fascicolo.anno,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "controinteressati": list(getattr(fascicolo, "controinteressati", []) or []),
                "oggetto": fascicolo.oggetto,
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_ricorso
            anno = fascicolo.anno
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato
        else:
            payload = {
                "numero_rgt": fascicolo.numero_rgt,
                "anno_rgt": fascicolo.anno_rgt,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "oggetto_controversia": fascicolo.oggetto_controversia,
                "valore_controversia": getattr(fascicolo, "valore_controversia", 0.0),
                "note": fascicolo.note,
                "codice_commissione": fascicolo.codice_commissione,
                "nome_commissione": fascicolo.nome_commissione,
            }
            numero = fascicolo.numero_rgt
            anno = fascicolo.anno_rgt
            uff_cod = fascicolo.codice_commissione
            uff_nome = fascicolo.nome_commissione
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto_controversia or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato

        return {
            "external_id": f"{uff_cod}:{numero}:{anno}:{procedimento}",
            "id_fascicolo": str(payload.get("id_fascicolo") or "").strip(),
            "numero": str(numero or "").strip(),
            "anno": int(anno or 0),
            "ufficio_codice": str(uff_cod or "").strip(),
            "ufficio_nome": str(uff_nome or _resolve_ufficio_nome(str(uff_cod or ""))).strip(),
            "procedimento": str(procedimento or "").strip(),
            "sub_procedimento": str(payload.get("sub_procedimento") or "").strip(),
            "sezione": str(payload.get("sezione") or "").strip(),
            "stato": str(stato or "").strip(),
            "oggetto": str(oggetto or "").strip(),
            "parti": assistiti,
            "controparti": controparti,
            "data_iscrizione": str(payload.get("data_iscrizione") or payload.get("data_deposito") or "").strip(),
            "data_udienza": str(payload.get("data_udienza") or "").strip(),
            "ultima_attivita": str(ultima_attivita or "").strip(),
            "payload": payload,
        }

    def _build_portale_preview(portale: str, selection: dict[str, Any], documenti: list[dict]) -> dict[str, Any]:
        selection = dict(selection or {})
        payload = dict(selection.get("payload") or {})
        snapshot = dict(selection.get("snapshot") or {})
        snapshot_identity = dict(
            snapshot.get("fascicolo")
            or snapshot.get("identity")
            or snapshot.get("procedimento")
            or snapshot.get("ricorso")
            or snapshot.get("controversia")
            or {}
        )
        raw_documenti = [dict(row or {}) for row in documenti or [] if isinstance(row, dict)]
        if (portale or "").strip().lower() == "pst":
            for source in (
                snapshot.get("catalogo"),
                snapshot.get("documenti"),
                snapshot.get("documents"),
            ):
                if isinstance(source, list):
                    raw_documenti.extend(dict(row or {}) for row in source if isinstance(row, dict))
            try:
                existing_fascicolo = _find_exact_fascicolo_locale_portale("pst", selection)
            except Exception:
                existing_fascicolo = None
            if existing_fascicolo:
                raw_documenti.extend(
                    dict(row or {})
                    for row in _catalogo_documenti_portale_fascicolo(existing_fascicolo)
                    if isinstance(row, dict)
                )
        docs = _normalize_portale_documents(raw_documenti)
        if (portale or "").strip().lower() == "pst":
            def _doc_content_key(doc: dict[str, Any]) -> str:
                nome = str(
                    doc.get("nome")
                    or doc.get("nome_documento")
                    or doc.get("filename")
                    or ""
                ).strip()
                normalized_name = _normalizza_nome_match_portale(nome)
                if not normalized_name or re.fullmatch(r"documento(?:\s+\d+)?", normalized_name):
                    return ""
                if not re.search(r"\.(pdf|p7m|xml|eml|msg|docx?|rtf|txt)$", nome, re.I) and len(normalized_name) <= 8:
                    return ""
                parent = str(
                    doc.get("id_documento_padre")
                    or doc.get("parent_id_documento")
                    or doc.get("parent_nome")
                    or ""
                ).strip()
                deposito = str(
                    doc.get("id_deposito")
                    or doc.get("id_deposito_esterno")
                    or doc.get("id_deposito_pct")
                    or ""
                ).strip()
                role = "allegato" if doc.get("is_allegato") or parent else "principale"
                return "|".join(
                    part
                    for part in (
                        normalized_name,
                        str(doc.get("data_deposito") or doc.get("data_documento") or "").strip(),
                        str(doc.get("tipo_atto") or doc.get("tipo") or "").strip().lower(),
                        str(doc.get("mittente") or "").strip().lower(),
                        deposito,
                        parent,
                        role,
                    )
                    if part
                )

            filtered_docs: list[dict[str, Any]] = []
            seen_docs: set[str] = set()
            seen_doc_content: set[str] = set()
            for doc in docs:
                identifiers = _portale_document_identifier_values(doc)
                content_key = _doc_content_key(doc)
                if not identifiers and not content_key:
                    continue
                key = "|".join(sorted(identifiers)) if identifiers else ""
                if key and key in seen_docs:
                    continue
                if content_key and content_key in seen_doc_content:
                    continue
                if key:
                    seen_docs.add(key)
                if content_key:
                    seen_doc_content.add(content_key)
                filtered_docs.append(doc)
            docs = filtered_docs
        depositi = _group_portale_documents(docs)
        def _clean(value: Any) -> str:
            return str(value or "").strip()

        def _first_value(*values: Any) -> str:
            for value in values:
                cleaned = _clean(value)
                if cleaned:
                    return cleaned
            return ""

        def _as_int(*values: Any) -> int:
            value = _first_value(*values)
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                return 0

        def _sortable_date(raw: Any) -> tuple[int, datetime]:
            value = _clean(raw)
            if not value:
                return (0, datetime.min)
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S.%f",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y",
            ):
                try:
                    return (1, datetime.strptime(value, fmt))
                except ValueError:
                    continue
            return (0, datetime.min)

        def _date_only(raw: Any) -> str:
            value = _clean(raw)
            if not value:
                return ""
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S.%f",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
            ):
                try:
                    return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return value[:10] if len(value) >= 10 else value

        def _as_list(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, list):
                return [dict(row) for row in value if isinstance(row, dict)]
            return []

        snapshot_sections = dict(snapshot.get("sezioni") or {}) if isinstance(snapshot.get("sezioni"), dict) else {}
        structured_eventi = _as_list(payload.get("eventi")) or _as_list(snapshot.get("eventi")) or _as_list(snapshot_sections.get("storico_fascicolo"))
        structured_udienze = _as_list(payload.get("udienze")) or _as_list(snapshot.get("udienze")) or _as_list(snapshot.get("scadenze_termini")) or _as_list(snapshot_sections.get("scadenze_termini"))
        structured_comunicazioni = _as_list(payload.get("comunicazioni")) or _as_list(snapshot.get("comunicazioni")) or _as_list(snapshot_sections.get("comunicazioni_cancelleria"))
        structured_istanze = _as_list(payload.get("istanze")) or _as_list(snapshot.get("istanze")) or _as_list(snapshot_sections.get("istanze"))
        structured_depositi = _as_list(payload.get("depositi_telematici") or payload.get("depositi")) or _as_list(snapshot.get("depositi_telematici") or snapshot.get("depositi"))

        provvedimenti_count = sum(
            1
            for doc in docs
            if any(token in (doc.get("tipo_atto") or doc.get("tipo") or "").upper() for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))
        )
        data_iscrizione = _first_value(
            selection.get("data_iscrizione"),
            payload.get("data_iscrizione"),
            snapshot_identity.get("data_iscrizione"),
            selection.get("data_deposito"),
            payload.get("data_deposito"),
            snapshot_identity.get("data_deposito"),
        )
        data_udienza = _first_value(selection.get("data_udienza"), payload.get("data_udienza"), snapshot_identity.get("data_udienza"))
        latest_doc_date = ""
        doc_dates = [_clean(doc.get("data_deposito")) for doc in docs if _clean(doc.get("data_deposito"))]
        if doc_dates:
            latest_doc_date = max(doc_dates, key=_sortable_date)
        procedimento = _first_value(
            selection.get("procedimento"),
            payload.get("ruolo"),
            payload.get("tipo_registro"),
            payload.get("tipo"),
            payload.get("sub_procedimento"),
            snapshot_identity.get("procedimento"),
            snapshot_identity.get("ruolo"),
            snapshot_identity.get("tipo_registro"),
            snapshot_identity.get("tipo"),
            snapshot_identity.get("sub_procedimento"),
        )
        stato = _first_value(selection.get("stato"), payload.get("stato"), payload.get("fase"), snapshot_identity.get("stato"), snapshot_identity.get("fase"))
        oggetto = _first_value(
            selection.get("oggetto"),
            payload.get("oggetto"),
            payload.get("reato"),
            payload.get("oggetto_controversia"),
            payload.get("materia"),
            snapshot_identity.get("oggetto"),
            snapshot_identity.get("reato"),
            snapshot_identity.get("oggetto_controversia"),
            snapshot_identity.get("materia"),
        )
        ultima_attivita = _first_value(
            selection.get("ultima_attivita"),
            snapshot_identity.get("ultima_attivita"),
            latest_doc_date,
            data_udienza,
            data_iscrizione,
        )
        eventi = []
        if data_iscrizione:
            eventi.append({"label": "Iscrizione / deposito originario", "data": data_iscrizione, "tipo": "iscrizione"})
        if data_udienza:
            eventi.append({"label": "Udienza rilevata", "data": data_udienza, "tipo": "udienza"})
        for row in structured_eventi:
            label = _first_value(row.get("tipo_evento"), row.get("descrizione"), "Evento da portale")
            data = _date_only(row.get("data_evento") or row.get("data"))
            key = (label.lower(), data, _clean(row.get("evento_uid")))
            if not any(
                (str(ev.get("label") or "").lower(), str(ev.get("data") or ""), str(ev.get("evento_uid") or "")) == key
                for ev in eventi
            ):
                eventi.append(
                    {
                        "label": label,
                        "data": data,
                        "tipo": _first_value(row.get("tipo_evento"), "evento"),
                        "descrizione": _first_value(row.get("descrizione"), row.get("esito")),
                        "evento_uid": _clean(row.get("evento_uid")),
                    }
                )
        udienze = [
            {
                "label": _first_value(row.get("tipo"), row.get("descrizione"), "Udienza"),
                "data": _date_only(row.get("data_udienza") or row.get("data")),
                "ora": _clean(row.get("ora")),
                "tipo": _first_value(row.get("tipo"), "udienza"),
                "descrizione": _first_value(row.get("descrizione"), row.get("esito")),
                "giudice": _clean(row.get("giudice")),
                "udienza_uid": _clean(row.get("udienza_uid")),
            }
            for row in structured_udienze
            if _date_only(row.get("data_udienza") or row.get("data"))
        ]
        documenti_scadenziario = [] if data_udienza or udienze else _documenti_scadenziario_da_catalogo(docs)
        comunicazioni = [
            {
                "id": _clean(row.get("comunicazione_uid")),
                "tipo": _first_value(row.get("tipo"), "Comunicazione"),
                "oggetto": _first_value(row.get("oggetto"), row.get("tipo"), "Comunicazione di cancelleria"),
                "data": _date_only(row.get("data_comunicazione") or row.get("data")),
                "mittente": _clean(row.get("mittente")),
                "destinatario": _clean(row.get("destinatario")),
                "stato": _clean(row.get("stato")),
            }
            for row in structured_comunicazioni
        ]
        istanze = [
            {
                "id": _clean(row.get("evento_uid") or row.get("id")),
                "tipo": _first_value(row.get("tipo_evento"), row.get("tipo"), "Istanza"),
                "oggetto": _first_value(row.get("descrizione"), row.get("oggetto"), row.get("tipo_evento"), "Istanza"),
                "data": _date_only(row.get("data_evento") or row.get("data")),
                "stato": _clean(row.get("esito") or row.get("stato")),
            }
            for row in structured_istanze
        ]
        depositi_telematici = [
            {
                "id": _clean(row.get("deposito_uid") or row.get("id")),
                "tipo_atto": _first_value(row.get("tipo_atto"), row.get("atto_principale"), "Deposito telematico"),
                "data": _date_only(row.get("data_invio") or row.get("data_esito") or row.get("data")),
                "stato": _clean(row.get("stato")),
                "mittente": _clean(row.get("mittente")),
                "messaggio": _clean(row.get("messaggio_esito")),
                "servizio_portale": _clean(row.get("servizio_portale")),
            }
            for row in structured_depositi
        ]
        return {
            "identity": {
                "id_fascicolo": _first_value(selection.get("id_fascicolo"), payload.get("id_fascicolo"), snapshot_identity.get("id_fascicolo")),
                "numero": _first_value(selection.get("numero"), payload.get("numero_rg"), payload.get("numero"), snapshot_identity.get("numero_rg"), snapshot_identity.get("numero")),
                "anno": _as_int(selection.get("anno"), payload.get("anno_rg"), payload.get("anno"), snapshot_identity.get("anno_rg"), snapshot_identity.get("anno")),
                "ufficio_nome": _first_value(selection.get("ufficio_nome"), payload.get("nome_ufficio"), payload.get("ufficio_nome"), snapshot_identity.get("nome_ufficio"), snapshot_identity.get("ufficio_nome")),
                "ufficio_codice": _first_value(selection.get("ufficio_codice"), payload.get("codice_ufficio"), payload.get("ufficio_codice"), snapshot_identity.get("codice_ufficio"), snapshot_identity.get("ufficio_codice")),
                "procedimento": procedimento,
                "sub_procedimento": _first_value(selection.get("sub_procedimento"), payload.get("sub_procedimento"), snapshot_identity.get("sub_procedimento")),
                "sezione": _first_value(selection.get("sezione"), payload.get("sezione"), snapshot_identity.get("sezione")),
                "oggetto": oggetto,
                "stato": stato,
                "data_iscrizione": data_iscrizione,
                "data_udienza": data_udienza,
                "ultima_attivita": ultima_attivita,
            },
            "parti": list(selection.get("parti") or []),
            "controparti": list(selection.get("controparti") or []),
            "difensori": [x for x in list(payload.get("difensori") or []) if str(x).strip()],
            "eventi": eventi,
            "udienze": udienze,
            "comunicazioni": comunicazioni,
            "istanze": istanze,
            "depositi_telematici": depositi_telematici,
            "documenti": docs,
            "documenti_scadenziario": documenti_scadenziario,
            "depositi": depositi,
            "counts": {
                "parti": len(list(selection.get("parti") or [])) + len(list(selection.get("controparti") or [])),
                "difensori": len(list(payload.get("difensori") or [])),
                "eventi": len(eventi),
                "udienze": len(udienze) or (1 if data_udienza else 0),
                "documenti": len(docs),
                "fonti_scadenziario": len(documenti_scadenziario),
                "provvedimenti": provvedimenti_count,
                "depositi": len(depositi),
                "esiti": len(depositi) + len(depositi_telematici),
                "comunicazioni": len(comunicazioni),
                "istanze": len(istanze),
            },
        }

    def _portale_doc_is_provvedimento(doc: dict[str, Any]) -> bool:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        return any(token in tipo for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))

    def _preview_richiede_file_portale(options: dict[str, bool]) -> bool:
        return bool(options.get("importa_documenti") or options.get("importa_provvedimenti"))

    def _portale_document_identifier_values(row: dict[str, Any] | None) -> set[str]:
        strong_values: set[str] = set()
        weak_values: set[str] = set()
        payload = dict(row or {})
        raw_candidates = payload.get("id_documento_candidates")
        for value in (
            payload.get("id_reperto"),
            payload.get("idReperto"),
            payload.get("idRaccoglitore"),
            payload.get("id_raccoglitore"),
            payload.get("msg_id"),
            payload.get("msgId"),
            payload.get("msgid"),
        ):
            text = str(value or "").strip()
            if text and not text.startswith("#"):
                weak_values.add(text)
        if isinstance(raw_candidates, (list, tuple, set)):
            for candidate in raw_candidates:
                text = str(candidate or "").strip()
                if text and not text.startswith("#") and text not in weak_values:
                    strong_values.add(text)
        for value in (
            payload.get("id_documento"),
            payload.get("id_documento_portale"),
            payload.get("idDocumento"),
            payload.get("idDoc"),
            payload.get("id_cat"),
            payload.get("idCat"),
            payload.get("id_repeatto"),
            payload.get("idRepeatto"),
            payload.get("idRepeatTo"),
            payload.get("numero_documento"),
            payload.get("numeroDocumento"),
            payload.get("id_doc_mittente"),
            payload.get("idDocMittente"),
        ):
            text = str(value or "").strip()
            if text and not text.startswith("#"):
                strong_values.add(text)
        strong_values.difference_update(weak_values)
        return strong_values or weak_values

    def _portale_document_deposito_value(row: dict[str, Any] | None) -> str:
        payload = dict(row or {})
        return str(
            payload.get("id_deposito_esterno")
            or payload.get("id_deposito")
            or payload.get("idDeposito")
            or payload.get("id_deposito_pct")
            or ""
        ).strip()

    def _portale_document_name_key(row: dict[str, Any] | None) -> str:
        payload = dict(row or {})
        return _normalizza_nome_match_portale(
            str(
                payload.get("nome")
                or payload.get("nome_documento")
                or payload.get("nomeDocumento")
                or payload.get("filename")
                or payload.get("name")
                or payload.get("nome_file")
                or payload.get("nomeFile")
                or payload.get("nome_file_originale")
                or payload.get("nomeFileOriginale")
                or ""
            ).strip()
        )

    def _portale_document_matches_preview(item: dict[str, Any], preview_doc: dict[str, Any]) -> bool:
        item_ids = _portale_document_identifier_values(item)
        preview_ids = _portale_document_identifier_values(preview_doc)
        if item_ids and preview_ids and item_ids.intersection(preview_ids):
            return True
        item_name = _portale_document_name_key(item)
        preview_name = _portale_document_name_key(preview_doc)
        if not item_name or not preview_name or item_name != preview_name:
            return False
        item_dep = _portale_document_deposito_value(item)
        preview_dep = _portale_document_deposito_value(preview_doc)
        if item_dep and preview_dep and item_dep != preview_dep:
            return False
        return True

    def _merge_preview_metadata_into_portale_items(
        decoded_items: list[dict[str, Any]],
        preview_docs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged_items: list[dict[str, Any]] = []
        for item in decoded_items:
            match = next(
                (preview_doc for preview_doc in preview_docs if _portale_document_matches_preview(item, preview_doc)),
                None,
            )
            if not match:
                merged_items.append(dict(item))
                continue
            merged = dict(match)
            merged.update(item)
            item_id_cat = str(item.get("id_cat") or item.get("idCat") or "").strip()
            item_id_documento = str(
                item.get("id_documento_portale")
                or item.get("id_documento")
                or item.get("idDocumento")
                or item.get("idDoc")
                or ""
            ).strip()
            merged["id_documento_portale"] = str(
                item_id_documento
                or item_id_cat
                or match.get("id_documento_portale")
                or match.get("id_documento")
                or match.get("idDocumento")
                or ""
            ).strip()
            merged["id_cat"] = str(item_id_cat or match.get("id_cat") or match.get("idCat") or "").strip()
            merged["id_repeatto"] = str(
                item.get("id_repeatto")
                or item.get("idRepeatto")
                or item.get("idRepeatTo")
                or match.get("id_repeatto")
                or match.get("idRepeatto")
                or match.get("idRepeatTo")
                or ""
            ).strip()
            merged["id_reperto"] = str(item.get("id_reperto") or item.get("idReperto") or match.get("id_reperto") or match.get("idReperto") or "").strip()
            merged["msg_id"] = str(item.get("msg_id") or item.get("msgId") or match.get("msg_id") or match.get("msgId") or "").strip()
            merged["id_deposito_esterno"] = str(
                item.get("id_deposito_esterno")
                or match.get("id_deposito_esterno")
                or match.get("id_deposito")
                or match.get("idDeposito")
                or ""
            ).strip()
            merged["id_deposito_pct"] = str(item.get("id_deposito_pct") or match.get("id_deposito_pct") or "").strip()
            merged["tipo_atto"] = str(item.get("tipo_atto") or match.get("tipo_atto") or "").strip()
            merged["tipo"] = str(item.get("tipo") or match.get("tipo") or "").strip()
            merged["mittente"] = str(item.get("mittente") or match.get("mittente") or "").strip()
            merged["servizio_portale"] = str(item.get("servizio_portale") or match.get("servizio_portale") or "").strip()
            merged["id_documento_padre"] = str(item.get("id_documento_padre") or match.get("id_documento_padre") or match.get("parent_id_documento") or "").strip()
            merged["parent_nome"] = str(item.get("parent_nome") or match.get("parent_nome") or "").strip()
            merged["is_allegato"] = bool(item.get("is_allegato") or match.get("is_allegato"))
            prefer_preview_date = not _portale_document_identifier_values(item)
            merged["data_documento"] = str(
                (
                    match.get("data_documento")
                    or match.get("data_deposito")
                    or item.get("data_documento")
                )
                if prefer_preview_date
                else (
                    item.get("data_documento")
                    or match.get("data_documento")
                    or match.get("data_deposito")
                )
                or ""
            ).strip()
            merged_items.append(merged)
        return merged_items

    def _filter_portale_items_by_preview_selection(
        decoded_items: list[dict[str, Any]],
        preview_docs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not preview_docs:
            return list(decoded_items)
        return [
            item
            for item in decoded_items
            if any(_portale_document_matches_preview(item, preview_doc) for preview_doc in preview_docs)
        ]

    def _apply_portale_download_mode_to_items(
        decoded_items: list[dict[str, Any]],
        *,
        original: bool,
    ) -> list[dict[str, Any]]:
        modalita_default = "originale" if original else "copia"
        patched: list[dict[str, Any]] = []
        for item in decoded_items:
            row = dict(item)
            modalita = str(row.get("modalita_documento_portale") or "").strip().lower()
            if modalita not in {"originale", "copia"}:
                row["modalita_documento_portale"] = modalita_default
            if row.get("original_documento_portale") is None:
                row["original_documento_portale"] = bool(original)
            patched.append(row)
        return patched

    def _portale_item_is_informativo(row: dict[str, Any] | None) -> bool:
        payload = dict(row or {})
        name = Path(
            str(
                payload.get("nome")
                or payload.get("nome_documento")
                or payload.get("filename")
                or payload.get("name")
                or payload.get("nome_file")
                or payload.get("nome_file_originale")
                or ""
            )
        ).stem
        text = " ".join(
            str(payload.get(key) or "")
            for key in (
                "tipo",
                "tipo_atto",
                "classificazione",
                "receipt_type",
                "categoria",
            )
        )
        compact_name = re.sub(r"[^a-z0-9]+", "", name.casefold())
        compact_text = re.sub(r"[^a-z0-9]+", "", text.casefold())
        return compact_name in {"informazioni", "informazionifascicolo"} or compact_text in {
            "informazioni",
            "informazionifascicolo",
            "catalogoinformazioni",
        }

    def _portale_raw_content_b64(row: dict[str, Any] | None) -> str:
        payload = dict(row or {})
        content_b64 = str(
            payload.get("contenuto_b64")
            or payload.get("content_base64")
            or payload.get("base64")
            or payload.get("contenuto_base64")
            or payload.get("contenutoBase64")
            or payload.get("file_base64")
            or payload.get("fileBase64")
            or payload.get("bytes_base64")
            or payload.get("bytesBase64")
            or ""
        ).strip()
        if content_b64.lower().startswith("data:") and "," in content_b64:
            return content_b64.split(",", 1)[1].strip()
        return content_b64

    def _portale_raw_file_name(row: dict[str, Any] | None) -> str:
        payload = dict(row or {})
        return Path(
            str(
                payload.get("nome")
                or payload.get("filename")
                or payload.get("name")
                or payload.get("nome_documento")
                or payload.get("nomeDocumento")
                or payload.get("nome_file")
                or payload.get("nomeFile")
                or payload.get("nome_file_originale")
                or payload.get("nomeFileOriginale")
                or ""
            )
        ).name

    def _portale_raw_file_has_content(row: dict[str, Any] | None) -> bool:
        content_b64 = _portale_raw_content_b64(row)
        if not content_b64:
            return False
        try:
            return bool(base64.b64decode(content_b64, validate=False))
        except Exception:
            return False

    def _portale_document_hash(item: dict[str, Any] | None) -> str:
        payload = dict(item or {})
        content = payload.get("contenuto")
        if isinstance(content, bytes) and content:
            return hashlib.sha256(content).hexdigest()
        sha = str(payload.get("sha256") or "").strip().lower()
        return sha if re.fullmatch(r"[0-9a-f]{64}", sha) else ""

    def _portale_document_report(
        *,
        files: list[dict[str, Any]],
        preview_docs: list[dict[str, Any]],
        decoded_items: list[dict[str, Any]],
        final_items: list[dict[str, Any]],
        documenti_attesi: int,
    ) -> dict[str, Any]:
        raw_rows = [dict(row or {}) for row in files or [] if isinstance(row, dict)]
        raw_without_content = [
            _portale_raw_file_name(row) or str(row.get("id_documento") or row.get("id_cat") or "documento senza nome")
            for row in raw_rows
            if not _portale_raw_file_has_content(row)
        ]
        informative_keys: set[str] = set()
        for row in [*preview_docs, *decoded_items]:
            if not _portale_item_is_informativo(row):
                continue
            key = _portale_document_name_key(row) or "|".join(sorted(_portale_document_identifier_values(row)))
            informative_keys.add(key or f"informazioni-{len(informative_keys) + 1}")
        reali = []
        for item in final_items:
            name = str(item.get("nome") or item.get("nome_file_originale") or "").strip()
            content = item.get("contenuto")
            sha = _portale_document_hash(item)
            if name and isinstance(content, bytes) and content and sha and not _portale_item_is_informativo(item):
                reali.append({"nome": name, "sha256": sha, "dimensione_bytes": len(content)})
        catalogo_count = max(int(documenti_attesi or 0) - len(reali) - len(informative_keys), 0)
        without_content_count = len(raw_without_content)
        if not raw_rows and documenti_attesi:
            without_content_count = int(documenti_attesi)
        elif raw_rows and not reali and not raw_without_content:
            without_content_count = max(int(documenti_attesi or 0), len(raw_rows))
        missing_preview = []
        for doc in preview_docs:
            if _portale_item_is_informativo(doc):
                continue
            if any(_portale_document_matches_preview(item, doc) for item in final_items):
                continue
            missing_preview.append(str(doc.get("nome") or doc.get("nome_documento") or doc.get("id_documento") or "Documento PST").strip())
        return {
            "documenti_attesi": int(documenti_attesi or 0),
            "file_ricevuti": len(raw_rows),
            "documenti_reali": len(reali),
            "documenti_reali_elenco": reali,
            "documenti_catalogo": catalogo_count,
            "documenti_informativi": len(informative_keys),
            "documenti_senza_contenuto": without_content_count,
            "documenti_senza_contenuto_elenco": raw_without_content[:20],
            "documenti_mancanti": len(missing_preview),
            "documenti_mancanti_elenco": missing_preview[:20],
            "documenti_scartati": max(len(decoded_items) - len(final_items), 0),
        }

    def _portale_import_block_message(report: dict[str, Any]) -> str:
        names = list(report.get("documenti_senza_contenuto_elenco") or report.get("documenti_mancanti_elenco") or [])
        first = str(names[0] if names else "nessun file effettivo").strip()
        return (
            "Importazione PST bloccata per protezione dati: "
            "non sono arrivati file reali importabili, oppure sono presenti solo catalogo o metadati/Informazioni. "
            f"documenti reali presenti {int(report.get('documenti_reali') or 0)}, "
            f"solo catalogo {int(report.get('documenti_catalogo') or 0)}, "
            f"solo Informazioni {int(report.get('documenti_informativi') or 0)}, "
            f"senza contenuto {int(report.get('documenti_senza_contenuto') or 0)}. "
            f"Primo elemento da verificare: {first}. "
            "Azione richiesta: scarica di nuovo i documenti dal Local Signer oppure seleziona i PDF/P7M reali "
            "prima dello Step 7; catalogo, Informazioni e metadati restano tracciati ma non bastano per importare documenti."
        )

    def _merge_portale_items_by_position_when_safe(
        decoded_items: list[dict[str, Any]],
        preview_docs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        importable_preview = [doc for doc in preview_docs if not _portale_item_is_informativo(doc)]
        real_items = [
            item
            for item in decoded_items
            if str(item.get("nome") or "").strip()
            and isinstance(item.get("contenuto"), bytes)
            and item.get("contenuto")
            and not _portale_item_is_informativo(item)
        ]
        if not real_items or len(real_items) != len(importable_preview):
            return []
        merged: list[dict[str, Any]] = []
        for item, preview_doc in zip(real_items, importable_preview):
            row = dict(preview_doc)
            row.update(item)
            row["id_documento_portale"] = str(
                item.get("id_documento_portale")
                or preview_doc.get("id_documento_portale")
                or preview_doc.get("id_documento")
                or ""
            ).strip()
            row["id_cat"] = str(item.get("id_cat") or preview_doc.get("id_cat") or "").strip()
            row["id_repeatto"] = str(item.get("id_repeatto") or preview_doc.get("id_repeatto") or "").strip()
            row["msg_id"] = str(item.get("msg_id") or preview_doc.get("msg_id") or "").strip()
            row["id_deposito_esterno"] = str(
                item.get("id_deposito_esterno")
                or preview_doc.get("id_deposito_esterno")
                or preview_doc.get("id_deposito")
                or ""
            ).strip()
            row["tipo_atto"] = str(item.get("tipo_atto") or preview_doc.get("tipo_atto") or "").strip()
            row["tipo"] = str(item.get("tipo") or preview_doc.get("tipo") or "").strip()
            row["mittente"] = str(item.get("mittente") or preview_doc.get("mittente") or "").strip()
            merged.append(row)
        return merged

    def _filter_portale_preview_by_options(preview: dict[str, Any], options: dict[str, bool]) -> dict[str, Any]:
        view = dict(preview or {})
        docs = _normalize_portale_documents(list(view.get("documenti") or []))
        include_docs = bool(options.get("importa_documenti", True))
        include_provvedimenti = bool(options.get("importa_provvedimenti", True))
        if include_docs and include_provvedimenti:
            filtered_docs = docs
        else:
            filtered_docs = [
                doc
                for doc in docs
                if (
                    _portale_doc_is_provvedimento(doc) and include_provvedimenti
                ) or (
                    not _portale_doc_is_provvedimento(doc) and include_docs
                )
            ]
        filtered_depositi = _group_portale_documents(filtered_docs)
        counts = dict(view.get("counts") or {})
        counts["documenti"] = len(filtered_docs)
        counts["provvedimenti"] = sum(1 for doc in filtered_docs if _portale_doc_is_provvedimento(doc))
        counts["depositi"] = len(filtered_depositi)
        documenti_scadenziario = []
        if not _preview_ha_udienza_strutturata(view):
            documenti_scadenziario = _documenti_scadenziario_da_catalogo(filtered_docs)
        counts["fonti_scadenziario"] = len(documenti_scadenziario)
        view["documenti"] = filtered_docs
        view["documenti_scadenziario"] = documenti_scadenziario
        view["depositi"] = filtered_depositi
        view["counts"] = counts
        return view

    def _normalize_portale_match_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        text = re.sub(r"\s+", " ", text)
        return text

    def _expected_fascicolo_types_for_portale(
        portale: str, selection: dict[str, Any] | None = None
    ) -> set[str]:
        portale_norm = str(portale or "").strip().lower()
        selection = selection or {}
        procedimento = _normalize_portale_match_text(selection.get("procedimento"))
        if portale_norm == "pdp":
            return {"PENALE"}
        if portale_norm == "pat":
            return {"AMMINISTRATIVO"}
        if portale_norm == "ptt":
            return {"TRIBUTARIO", "ALTRO"}
        if procedimento == "PENALE":
            return {"PENALE"}
        if procedimento == "LAVORO":
            return {"LAVORO", "CIVILE"}
        if procedimento in {"FAMIGLIA", "MINORI"}:
            return {"FAMIGLIA", "CIVILE"}
        return {"CIVILE", "LAVORO", "FAMIGLIA", "ALTRO"}

    def _is_fascicolo_type_compatible_for_portale(
        fasc: Fascicolo, portale: str, selection: dict[str, Any] | None = None
    ) -> bool:
        expected = _expected_fascicolo_types_for_portale(portale, selection)
        fasc_type = _normalize_portale_match_text(getattr(getattr(fasc, "tipo", None), "value", ""))
        return not expected or fasc_type in expected

    def _selection_rg_identity(selection: dict[str, Any]) -> dict[str, Any]:
        numero = str(selection.get("numero") or "").strip()
        try:
            anno = int(selection.get("anno") or 0)
        except (TypeError, ValueError):
            anno = 0
        ufficio_nome = str(
            selection.get("ufficio_nome")
            or _resolve_ufficio_nome(str(selection.get("ufficio_codice") or ""))
        ).strip()
        external_id = str(selection.get("external_id") or "").strip()
        return {
            "numero": numero,
            "anno": anno,
            "ufficio_nome": ufficio_nome,
            "external_id": external_id,
        }

    def _fascicolo_matches_selection(
        fasc: Fascicolo,
        portale: str,
        selection: dict[str, Any],
        *,
        strict: bool,
    ) -> bool:
        if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
            return False
        identity = _selection_rg_identity(selection)
        sel_numero = identity["numero"]
        sel_anno = int(identity["anno"] or 0)
        sel_ufficio = _normalize_portale_match_text(identity["ufficio_nome"])
        fasc_numero = str(getattr(fasc, "numero_rg", "") or "").strip()
        try:
            fasc_anno = int(getattr(fasc, "anno_rg", 0) or 0)
        except (TypeError, ValueError):
            fasc_anno = 0
        fasc_ufficio = _normalize_portale_match_text(getattr(fasc, "tribunale", ""))
        if strict:
            return bool(
                sel_numero
                and sel_anno
                and sel_ufficio
                and fasc_numero == sel_numero
                and fasc_anno == sel_anno
                and fasc_ufficio == sel_ufficio
            )
        if fasc_numero and sel_numero and fasc_numero != sel_numero:
            return False
        if fasc_anno and sel_anno and fasc_anno != sel_anno:
            return False
        if fasc_ufficio and sel_ufficio and fasc_ufficio != sel_ufficio:
            return False
        return True

    def _find_exact_fascicolo_locale_portale(
        portale: str, selection: dict[str, Any]
    ) -> Optional[Fascicolo]:
        identity = _selection_rg_identity(selection)
        expected_external_id = identity["external_id"]
        fascicoli = list(get_fascicoli().tutti())
        if expected_external_id:
            for fasc in fascicoli:
                if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
                    continue
                if str(getattr(fasc, "source_external_id", "") or "").strip() == expected_external_id:
                    return fasc
        for fasc in fascicoli:
            if _fascicolo_matches_selection(fasc, portale, selection, strict=True):
                return fasc
        return None

    def _resolve_portale_import_target(
        portale: str,
        selection: dict[str, Any],
        mapping: dict[str, str],
    ) -> tuple[str, Optional[Fascicolo], bool]:
        gf = get_fascicoli()
        requested_mode = mapping.get("mode") or "create_new"
        target_id = str(mapping.get("target_fascicolo_id") or "").strip()
        if requested_mode in {"attach_existing", "update_existing"}:
            if not target_id:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            target = gf.get(target_id)
            if not target:
                telematico_case = get_telematico().get_case(target_id)
                linked_practice_id = str(
                    (telematico_case or {}).get("practice_id")
                    or (telematico_case or {}).get("id_fascicolo")
                    or ""
                ).strip()
                if linked_practice_id:
                    target = gf.get(linked_practice_id)
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if not _fascicolo_matches_selection(target, portale, selection, strict=False):
                raise ValueError("Il fascicolo locale selezionato non è compatibile con il fascicolo del portale.")
            resolved_mode = "update_existing" if requested_mode == "update_existing" else "attach_existing"
            return resolved_mode, target, False
        exact = _find_exact_fascicolo_locale_portale(portale, selection)
        if exact:
            return "update_existing", exact, True
        return "create_new", None, False

    def _find_matching_fascicoli_locali(selection: dict[str, Any]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        numero = str(selection.get("numero") or "").strip()
        anno = int(selection.get("anno") or 0)
        ufficio_nome = str(selection.get("ufficio_nome") or "").strip().upper()
        tokens = [token.strip().upper() for token in list(selection.get("parti") or [])[:2] if token.strip()]
        for fasc in get_fascicoli().tutti():
            same_rg = numero and fasc.numero_rg == numero and int(getattr(fasc, "anno_rg", 0) or 0) == anno
            same_ufficio = ufficio_nome and str(fasc.tribunale or "").strip().upper() == ufficio_nome
            text_hit = any(token in str(fasc.titolo or "").upper() for token in tokens)
            if same_rg or (same_ufficio and text_hit):
                matches.append(
                    {
                        "id": fasc.id,
                        "numero": fasc.numero,
                        "titolo": fasc.titolo,
                        "rg_completo": fasc.rg_completo,
                        "tribunale": fasc.tribunale,
                        "stato": fasc.stato.value,
                        "source": getattr(fasc, "source", "") or "",
                    }
                )
        return matches

    def _sync_existing_fascicolo_from_portale(
        portale: str,
        target: Fascicolo,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        preserve_blank: bool,
        append_import_note: bool,
        user_name: str,
        log_id: str = "",
    ) -> Fascicolo:
        identity = dict(preview.get("identity") or {})
        payload = dict(selection.get("payload") or {})

        def _take(current: Any, incoming: Any) -> Any:
            if preserve_blank and str(current or "").strip():
                return current
            return incoming

        tipo_procedimento = (
            str(selection.get("procedimento") or "").strip()
            or str(payload.get("tipo_registro") or payload.get("tipo") or "").strip()
            or str(target.tipo_procedimento or "").strip()
        )
        update_fields: dict[str, Any] = {
            "tribunale": _take(
                target.tribunale,
                selection.get("ufficio_nome") or identity.get("ufficio_nome") or target.tribunale,
            ),
            "numero_rg": _take(target.numero_rg, selection.get("numero") or target.numero_rg),
            "anno_rg": target.anno_rg or int(selection.get("anno") or 0),
            "oggetto": _take(target.oggetto, identity.get("oggetto") or target.oggetto),
            "sezione": _take(target.sezione, identity.get("sezione") or target.sezione),
            "giudice": _take(
                target.giudice,
                payload.get("giudice") or payload.get("giudice_relatore") or target.giudice,
            ),
            "tipo_procedimento": _take(target.tipo_procedimento, tipo_procedimento),
        }
        if append_import_note:
            nota_import = f"Sincronizzato da {_portale_source_name(portale)} il {date.today().isoformat()}"
            update_fields["note"] = " | ".join(part for part in [target.note.strip(), nota_import] if part)
        stato_portale = stato_fascicolo_da_descrizione_portale(
            identity.get("stato") or selection.get("stato") or payload.get("stato"),
            default=None,
        )
        if stato_portale and stato_portale != target.stato:
            update_fields["stato"] = stato_portale
        updated = get_fascicoli().aggiorna(target.id, **update_fields)
        get_fascicoli().registra_onboarding(
            target.id,
            f"Acquisizione guidata da {_portale_source_name(portale)}",
            note=f"Import log {log_id}" if log_id else "",
            avvocato=user_name,
        )
        return updated

    def _coerce_import_options(data: dict[str, Any], portale: str = "") -> dict[str, bool]:
        def _b(key: str, default: bool = False) -> bool:
            value = data.get(key, default)
            if isinstance(value, bool):
                return value
            return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s", "on"}

        portale_key = str(portale or data.get("portale") or "").strip().lower()
        default_originale_portale = _default_scarica_originale_portale(portale_key)

        return {
            "importa_dati_pratica": _b("importa_dati_pratica", True),
            "importa_parti": _b("importa_parti", True),
            "importa_difensori": _b("importa_difensori", True),
            "importa_eventi": _b("importa_eventi", True),
            "importa_udienze": _b("importa_udienze", True),
            "importa_scadenze": _b("importa_scadenze", True),
            "importa_documenti": _b("importa_documenti", True),
            "importa_provvedimenti": _b("importa_provvedimenti", True),
            "importa_cronologia_depositi": _b("importa_cronologia_depositi", True),
            "importa_esiti_telematici": _b("importa_esiti_telematici", True),
            "solo_nuovi": _b("solo_nuovi", True),
            "aggiorna_pratica_esistente": _b("aggiorna_pratica_esistente", False),
            "sovrascrivi_solo_vuoti": _b("sovrascrivi_solo_vuoti", True),
            "non_toccare_note_interne": _b("non_toccare_note_interne", True),
            "non_duplicare_documenti": _b("non_duplicare_documenti", True),
            "conserva_log_origine_pst": _b("conserva_log_origine_pst", True),
            "scarica_originale_portale": _b("scarica_originale_portale", default_originale_portale),
            "mantieni_albero_originale": _b("mantieni_albero_originale", False),
        }

    def _default_scarica_originale_portale(portale: str = "") -> bool:
        return str(portale or "").strip().lower() != "pst"

    def _scarica_originale_portale_enabled(options: dict[str, Any], portale: str = "") -> bool:
        return bool(
            dict(options or {}).get(
                "scarica_originale_portale",
                _default_scarica_originale_portale(portale),
            )
        )

    def _coerce_mapping(data: dict[str, Any]) -> dict[str, str]:
        target_id = str(
            data.get("target_fascicolo_id")
            or data.get("fascicolo_locale_id")
            or data.get("fascicolo_id")
            or data.get("id_fasc")
            or ""
        ).strip()
        mode = str(data.get("mode") or "create_new").strip() or "create_new"
        if target_id and mode == "create_new":
            mode = "update_existing"
        return {
            "mode": mode,
            "target_fascicolo_id": target_id,
            "area_pratica": str(data.get("area_pratica") or "").strip(),
            "materia": str(data.get("materia") or "").strip(),
            "procedimento": str(data.get("procedimento") or "").strip(),
            "grado": str(data.get("grado") or "").strip(),
            "stato_iniziale": str(data.get("stato_iniziale") or "").strip(),
        }

    def _analyze_portale_import(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        oks: list[dict[str, Any]] = []
        candidates = _find_matching_fascicoli_locali(selection)
        resolved_mode = mapping.get("mode") or "create_new"
        auto_target: Optional[Fascicolo] = None
        auto_integrated = False
        try:
            resolved_mode, auto_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        except Exception as target_error:
            if (mapping.get("mode") or "create_new") in {"attach_existing", "update_existing"}:
                blockers.append(
                    {
                        "label": "Pratica locale non compatibile",
                        "detail": str(target_error),
                        "tone": "danger",
                    }
                )
        counts = dict(preview.get("counts") or {})
        mode = mapping.get("mode") or "create_new"
        target_id = mapping.get("target_fascicolo_id") or ""
        existing_target_mode = mode in {"attach_existing", "update_existing"} and bool(target_id)
        payload = dict(selection.get("payload") or {})
        manual_mode = bool(selection.get("manual_mode") or payload.get("manual_mode"))
        has_udienza_strutturata = _preview_ha_udienza_strutturata(preview)
        documenti_scadenziario = [
            dict(row)
            for row in list(preview.get("documenti_scadenziario") or [])
            if isinstance(row, dict)
        ]
        if not documenti_scadenziario and not has_udienza_strutturata:
            documenti_scadenziario = _documenti_scadenziario_da_catalogo(list(preview.get("documenti") or []))

        if not selection.get("ufficio_codice"):
            blockers.append({"label": "Ufficio giudiziario mancante", "detail": "Seleziona un ufficio valido prima di proseguire.", "tone": "danger"})
        else:
            oks.append({"label": "Ufficio giudiziario risolto", "detail": selection.get("ufficio_nome") or selection.get("ufficio_codice"), "tone": "success"})

        if not selection.get("numero") or not selection.get("anno"):
            blockers.append({"label": "RG incompleto", "detail": "Numero e anno del fascicolo sono obbligatori per una pratica governabile.", "tone": "danger"})
        else:
            oks.append({"label": "Identità fascicolo pronta", "detail": f"{selection.get('numero')}/{selection.get('anno')}", "tone": "success"})

        if options.get("importa_parti") and counts.get("parti", 0) <= 0:
            if existing_target_mode:
                warnings.append({
                    "label": "Parti non esposte dal portale",
                    "detail": "La pratica locale resta primaria: IUSENTRA aggiornerà dati e documenti disponibili senza cancellare assistiti e controparti già presenti.",
                    "tone": "warning",
                })
            elif manual_mode and portale in {"pdp", "pat", "ptt"}:
                warnings.append({
                    "label": "Parti da completare manualmente",
                    "detail": "Il portale non ha restituito parti strutturate: completa assistiti e controparti dal browser ufficiale o direttamente nel gestionale dopo l'importazione.",
                    "tone": "warning",
                })
            else:
                blockers.append({"label": "Parti non disponibili", "detail": "Il fascicolo remoto non espone parti sufficienti per l'importazione guidata.", "tone": "danger"})
        elif counts.get("parti", 0) > 0:
            oks.append({"label": "Parti rilevate", "detail": f"{counts.get('parti', 0)} soggetti disponibili", "tone": "success"})

        if options.get("importa_documenti") and counts.get("documenti", 0) == 0:
            warnings.append({
                "label": "Nessun documento disponibile",
                "detail": (
                    "Puoi importare la pratica anche senza documenti, ma la vista fascicolo restera' parziale."
                    if not manual_mode
                    else "Il catalogo documentale non e' stato esposto dal servizio remoto: importa la pratica e completa documenti e depositi dal portale ufficiale."
                ),
                "tone": "warning",
            })
        elif counts.get("documenti", 0) > 0:
            oks.append({"label": "Catalogo documentale disponibile", "detail": f"{counts.get('documenti', 0)} documenti / {counts.get('depositi', 0)} buste", "tone": "success"})

        if mode in {"attach_existing", "update_existing"} and not target_id:
            blockers.append({"label": "Pratica locale non selezionata", "detail": "Per collegare o aggiornare devi scegliere un fascicolo esistente.", "tone": "danger"})

        if auto_integrated and auto_target is not None:
            warnings.append(
                {
                    "label": "Pratica locale già presente",
                    "detail": f"L'importazione aggiornerà automaticamente {auto_target.titolo} invece di creare un duplicato.",
                    "tone": "warning",
                }
            )
        elif mode == "create_new" and candidates:
            warnings.append({"label": "Possibile duplicato locale", "detail": f"Esistono {len(candidates)} fascicoli con RG o parti compatibili.", "tone": "warning"})

        if options.get("importa_scadenze") and not has_udienza_strutturata:
            if documenti_scadenziario:
                first_doc = documenti_scadenziario[0]
                first_name = str(first_doc.get("nome") or first_doc.get("tipo_atto") or "documento fonte").strip()
                detail = (
                    "Il portale non espone una prossima udienza strutturata: IUSENTRA userà il documento fonte "
                    f"'{first_name}' per ricavare termine o udienza dopo lo scarico, senza generare scadenze non verificate."
                )
                warnings.append(
                    {
                        "label": "Scadenza da documento fonte",
                        "detail": detail,
                        "tone": "warning",
                        "documenti": documenti_scadenziario[:5],
                    }
                )
            else:
                warnings.append({"label": "Nessuna udienza importabile", "detail": "Il portale non espone una prossima udienza da tradurre in scadenziario.", "tone": "warning"})

        score = max(0, min(100, 100 - len(blockers) * 18 - len(warnings) * 7))
        status = "ok" if not blockers and not warnings else ("warning" if not blockers else "block")
        return {
            "status": status,
            "score": score,
            "blockers": blockers,
            "warnings": warnings,
            "ok": oks,
            "existing_matches": candidates,
            "resolved_mode": resolved_mode,
            "auto_integrated": auto_integrated,
            "auto_target_fascicolo_id": getattr(auto_target, "id", "") if auto_target else "",
            "summary_text": (
                "Importazione pronta: nessun blocco rilevato."
                if not blockers
                else f"Risolvi {len(blockers)} blocchi e verifica {len(warnings)} avvisi prima dell'importazione."
            ),
            "next_step": blockers[0] if blockers else (warnings[0] if warnings else {"label": "Pronto per importare", "detail": "Puoi procedere con l'acquisizione guidata.", "tone": "success"}),
        }

    def _selection_to_fascicolo_dataclass(portale: str, selection: dict[str, Any]) -> Any:
        payload = dict((selection or {}).get("payload") or {})
        if portale == "pst":
            from pct.polisWeb import FascicoloPolisWeb

            return FascicoloPolisWeb(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                ruolo=str(payload.get("ruolo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                parti=list(payload.get("parti") or selection.get("parti") or []),
                parti_dettaglio=list(payload.get("parti_dettaglio") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pdp":
            from pct.pdp import FascicoloPDP

            return FascicoloPDP(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                tipo_registro=str(payload.get("tipo_registro") or selection.get("procedimento") or "").strip(),
                fase=str(payload.get("fase") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                reato=str(payload.get("reato") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                imputati=list(payload.get("imputati") or selection.get("parti") or []),
                parti_offese=list(payload.get("parti_offese") or selection.get("controparti") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pat":
            from pct.pat import FascicoloPAT

            return FascicoloPAT(
                numero_ricorso=str(payload.get("numero_ricorso") or selection.get("numero") or "").strip(),
                anno=int(payload.get("anno") or selection.get("anno") or 0),
                tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                materia=str(payload.get("materia") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
                data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
                resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
                controinteressati=list(payload.get("controinteressati") or []),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        from pct.sigit import FascicoloSIGIT

        return FascicoloSIGIT(
            numero_rgt=str(payload.get("numero_rgt") or selection.get("numero") or "").strip(),
            anno_rgt=int(payload.get("anno_rgt") or selection.get("anno") or 0),
            tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
            stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
            materia=str(payload.get("materia") or "").strip(),
            sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
            giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
            data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
            data_udienza=str(payload.get("data_udienza") or "").strip(),
            ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
            resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
            oggetto_controversia=str(payload.get("oggetto_controversia") or selection.get("oggetto") or "").strip(),
            valore_controversia=float(payload.get("valore_controversia") or 0),
            note=str(payload.get("note") or "").strip(),
            codice_commissione=str(payload.get("codice_commissione") or selection.get("ufficio_codice") or "").strip(),
            nome_commissione=str(payload.get("nome_commissione") or selection.get("ufficio_nome") or "").strip(),
        )

    def _documents_to_portale_dataclasses(portale: str, rows: list[dict]) -> list[Any]:
        docs = _normalize_portale_documents(rows)
        if portale != "pst":
            return []
        from pct.polisWeb import DocumentoPolisWeb

        return [
            DocumentoPolisWeb(
                id_documento=row["id_documento"],
                nome=row["nome"],
                tipo=row["tipo"],
                data_deposito=row["data_deposito"],
                mittente=row["mittente"],
                dimensione_bytes=row["dimensione_bytes"],
                disponibile=row["disponibile"],
                id_deposito=row["id_deposito"],
                tipo_atto=row["tipo_atto"],
            )
            for row in docs
        ]

    def _sync_portale_metadata_on_fascicolo(
        portale: str,
        id_fasc: str,
        preview: dict[str, Any],
        registrato_da: str = "",
    ) -> int:
        gf = get_fascicoli()
        synced = 0
        for deposito in list(preview.get("depositi") or []):
            docs = list(deposito.get("documenti") or [])
            if not docs:
                continue
            servizio_portale = str(deposito.get("servizio_portale") or "").strip()
            if not servizio_portale:
                servizio_portale = str((docs[0] or {}).get("servizio_portale") or "").strip()
            if not servizio_portale:
                servizio_portale = SERVIZIO_PST_DOCUMENTI_FASCICOLO
            gf.sincronizza_deposito_portale(
                id_fasc,
                fonte=_portale_source_name(portale),
                id_deposito_esterno=str(deposito.get("id_deposito") or "").strip(),
                tipo_atto=str(deposito.get("tipo_atto") or "").strip(),
                data_deposito=str(deposito.get("data_deposito") or "").strip(),
                mittente=str(deposito.get("mittente") or "").strip(),
                documenti_portale=docs,
                registrato_da=registrato_da,
                note=f"Catalogo ufficiale importato da {_portale_source_name(portale)}",
                nome_atto_principale=str((docs[0] or {}).get("nome") or "").strip(),
                stato="IMPORTATO_DA_PORTALE",
                servizio_portale=servizio_portale,
            )
            synced += 1
        return synced

    def _sync_udienza_e_scadenza(
        id_fasc: str,
        preview: dict[str, Any],
        *,
        crea_attivita: bool,
        crea_scadenza: bool,
        avvocato: str = "",
    ) -> dict[str, int]:
        gf = get_fascicoli()
        gs = get_scadenziario()
        fasc = gf.get(id_fasc)
        if not fasc:
            return {"attivita": 0, "scadenze": 0, "scadenze_scartate": 0, "scadenze_da_documento": 0}
        data_udienza = _normalizza_data_portale(preview.get("identity", {}).get("data_udienza"))
        if not data_udienza:
            documenti_scadenziario = [
                dict(row)
                for row in list(preview.get("documenti_scadenziario") or [])
                if isinstance(row, dict)
            ] or _documenti_scadenziario_da_catalogo(list(preview.get("documenti") or []))
            return {
                "attivita": 0,
                "scadenze": 0,
                "scadenze_scartate": 0,
                "scadenze_da_documento": len(documenti_scadenziario),
            }
        created = {"attivita": 0, "scadenze": 0, "scadenze_scartate": 0, "scadenze_da_documento": 0}
        if crea_attivita:
            exists = any(att.tipo == TipoAttivita.UDIENZA and att.data == data_udienza for att in fasc.attivita)
            if not exists:
                gf.aggiungi_attivita(
                    id_fasc,
                    tipo=TipoAttivita.UDIENZA,
                    data=data_udienza,
                    titolo="Udienza sincronizzata da portale",
                    descrizione=f"Evento importato da {fasc.source or 'portale'}",
                    avvocato=avvocato,
                )
                created["attivita"] += 1
        if crea_scadenza:
            if not _data_portale_scadenziario_utilizzabile(data_udienza):
                created["scadenze_scartate"] += 1
                return created
            exists = [
                sc for sc in gs.tutte(id_fascicolo=id_fasc, solo_aperte=False)
                if sc.data_scadenza == data_udienza and "udienza" in sc.titolo.lower()
            ]
            if not exists:
                gs.nuova(
                    titolo="Udienza da portale",
                    tipo=TipoTermine.UDIENZA,
                    data_scadenza=data_udienza,
                    id_fascicolo=id_fasc,
                    descrizione=f"Scadenza generata da sincronizzazione {fasc.source or 'portale'}",
                    id_utente_responsabile=getattr(g.utente_corrente, "id", "") if getattr(g, "utente_corrente", None) else "",
                )
                created["scadenze"] += 1
        return created

    def _normalize_authorized_portale_payload(
        portale: str,
        raw_payload: dict[str, Any],
    ) -> dict[str, Any]:
        bundle = normalize_authorized_portale_payload(portale, raw_payload)
        selection = dict(bundle.get("selection") or {})
        documenti = list(bundle.get("documenti") or [])
        preview = _build_portale_preview(portale, selection, documenti)
        return {
            "selection": selection,
            "preview": preview,
            "documenti": documenti,
            "raw_payload": dict(bundle.get("raw_payload") or {}),
        }

    def _sync_portale_structured_sections(
        portale: str,
        id_fasc: str,
        preview: dict[str, Any],
        options: dict[str, bool],
        *,
        avvocato: str = "",
    ) -> dict[str, int]:
        gf = get_fascicoli()
        gs = get_scadenziario()
        fasc = gf.get(id_fasc)
        if not fasc:
            return {"attivita": 0, "scadenze": 0, "scadenze_scartate": 0, "comunicazioni": 0, "istanze": 0, "depositi": 0}

        created = {"attivita": 0, "scadenze": 0, "scadenze_scartate": 0, "comunicazioni": 0, "istanze": 0, "depositi": 0}

        def _clean(value: Any) -> str:
            return str(value or "").strip()

        def _date_value(value: Any) -> str:
            return _normalizza_data_portale(value)

        def _activity_type(tipo: str, titolo: str = "") -> TipoAttivita:
            text = f"{tipo} {titolo}".lower()
            if "udienz" in text:
                return TipoAttivita.UDIENZA
            if "iscrizion" in text or "deposito originario" in text:
                return TipoAttivita.ISCRIZIONE_A_RUOLO
            if "comunic" in text or "canceller" in text or "notific" in text:
                return TipoAttivita.COMUNICAZIONE_CANCELLERIA
            if "sentenz" in text or "ordinanz" in text or "decret" in text or "provved" in text:
                return TipoAttivita.PROVVEDIMENTO
            if "rinvio" in text:
                return TipoAttivita.RINVIO
            if "scadenz" in text or "termine" in text:
                return TipoAttivita.TERMINE_SCADENZA
            if "deposit" in text or "istan" in text:
                return TipoAttivita.DEPOSITO_ATTI
            return TipoAttivita.ALTRO

        def _activity_exists(tipo: TipoAttivita, data: str, titolo: str) -> bool:
            normalized = re.sub(r"\s+", " ", titolo.lower()).strip()
            return any(
                att.tipo == tipo
                and str(att.data or "") == data
                and re.sub(r"\s+", " ", str(att.titolo or "").lower()).strip() == normalized
                for att in list(getattr(fasc, "attivita", []) or [])
            )

        def _add_activity(tipo: TipoAttivita, data: str, titolo: str, descrizione: str = "") -> bool:
            data = _date_value(data)
            titolo = titolo or "Evento da portale"
            if _activity_exists(tipo, data, titolo):
                return False
            gf.aggiungi_attivita(
                id_fasc,
                tipo=tipo,
                data=data,
                titolo=titolo,
                descrizione=descrizione,
                avvocato=avvocato,
            )
            created["attivita"] += 1
            return True

        if options.get("importa_eventi", True):
            for event in list(preview.get("eventi") or []):
                tipo_text = _clean(event.get("tipo"))
                titolo = _clean(event.get("label") or event.get("descrizione")) or "Evento da portale"
                tipo_attivita = _activity_type(tipo_text, titolo)
                if tipo_attivita == TipoAttivita.UDIENZA and preview.get("udienze"):
                    continue
                _add_activity(
                    tipo_attivita,
                    _clean(event.get("data")),
                    titolo,
                    _clean(event.get("descrizione")),
                )

        if options.get("importa_udienze", True):
            udienze = list(preview.get("udienze") or [])
            for udienza in udienze:
                data_udienza = _date_value(udienza.get("data") or udienza.get("data_udienza"))
                if not data_udienza:
                    continue
                ora = _clean(udienza.get("ora"))
                titolo = _clean(udienza.get("label") or udienza.get("tipo")) or "Udienza da portale"
                descrizione = _clean(udienza.get("descrizione"))
                if ora:
                    descrizione = " ".join(part for part in (descrizione, f"Ora: {ora}") if part)
                if _add_activity(TipoAttivita.UDIENZA, data_udienza, titolo, descrizione):
                    pass
                if options.get("importa_scadenze", False):
                    if not _data_portale_scadenziario_utilizzabile(data_udienza):
                        created["scadenze_scartate"] += 1
                        continue
                    exists = [
                        sc for sc in gs.tutte(id_fascicolo=id_fasc, solo_aperte=False)
                        if sc.data_scadenza == data_udienza and "udienza" in sc.titolo.lower()
                    ]
                    if not exists:
                        gs.nuova(
                            titolo=titolo,
                            tipo=TipoTermine.UDIENZA,
                            data_scadenza=data_udienza,
                            id_fascicolo=id_fasc,
                            descrizione=descrizione or f"Scadenza generata da sincronizzazione {_portale_source_name(portale)}",
                            id_utente_responsabile=getattr(g.utente_corrente, "id", "") if getattr(g, "utente_corrente", None) else "",
                        )
                        created["scadenze"] += 1

        if options.get("importa_esiti_telematici", True):
            for row in list(preview.get("comunicazioni") or []):
                title = _clean(row.get("oggetto") or row.get("tipo")) or "Comunicazione di cancelleria"
                title_hash = hashlib.sha1(title.encode("utf-8", errors="ignore")).hexdigest()[:12]
                ext_id = _clean(row.get("id")) or f"COM:{_date_value(row.get('data'))}:{title_hash}"
                gf.sincronizza_deposito_portale(
                    id_fasc,
                    fonte=_portale_source_name(portale),
                    id_deposito_esterno=ext_id,
                    tipo_atto=title,
                    data_deposito=_date_value(row.get("data")),
                    mittente=_clean(row.get("mittente")),
                    documenti_portale=[],
                    registrato_da=avvocato,
                    note=_clean(row.get("stato")) or f"Comunicazione importata da {_portale_source_name(portale)}.",
                    nome_atto_principale=title,
                    stato="IMPORTATO_DA_PORTALE",
                    servizio_portale=SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA,
                )
                created["comunicazioni"] += 1

        if options.get("importa_cronologia_depositi", True):
            for row in list(preview.get("istanze") or []):
                title = _clean(row.get("oggetto") or row.get("tipo")) or "Istanza"
                title_hash = hashlib.sha1(title.encode("utf-8", errors="ignore")).hexdigest()[:12]
                ext_id = _clean(row.get("id")) or f"IST:{_date_value(row.get('data'))}:{title_hash}"
                gf.sincronizza_deposito_portale(
                    id_fasc,
                    fonte=_portale_source_name(portale),
                    id_deposito_esterno=ext_id,
                    tipo_atto=title,
                    data_deposito=_date_value(row.get("data")),
                    mittente=_portale_source_name(portale),
                    documenti_portale=[],
                    registrato_da=avvocato,
                    note=_clean(row.get("stato")) or f"Istanza importata da {_portale_source_name(portale)}.",
                    nome_atto_principale=title,
                    stato="IMPORTATO_DA_PORTALE",
                    servizio_portale=SERVIZIO_PST_DETTAGLIO_ISTANZE,
                )
                created["istanze"] += 1
            for row in list(preview.get("depositi_telematici") or []):
                title = _clean(row.get("tipo_atto")) or "Deposito telematico"
                title_hash = hashlib.sha1(title.encode("utf-8", errors="ignore")).hexdigest()[:12]
                ext_id = _clean(row.get("id")) or f"DEP:{_date_value(row.get('data'))}:{title_hash}"
                gf.sincronizza_deposito_portale(
                    id_fasc,
                    fonte=_portale_source_name(portale),
                    id_deposito_esterno=ext_id,
                    tipo_atto=title,
                    data_deposito=_date_value(row.get("data")),
                    mittente=_clean(row.get("mittente")) or _portale_source_name(portale),
                    documenti_portale=[],
                    registrato_da=avvocato,
                    note=_clean(row.get("messaggio") or row.get("stato")) or f"Deposito importato da {_portale_source_name(portale)}.",
                    nome_atto_principale=title,
                    stato="IMPORTATO_DA_PORTALE",
                    servizio_portale=_clean(row.get("servizio_portale")),
                )
                created["depositi"] += 1

        return created

    def _source_snapshot_portale(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        import_log_id: str,
    ) -> dict[str, Any]:
        identity = dict((preview or {}).get("identity") or {})
        counts = dict((preview or {}).get("counts") or {})

        def _clean(value: Any) -> str:
            return str(value or "").strip()

        def _names(values: Any) -> list[str]:
            names: list[str] = []
            seen: set[str] = set()
            if not isinstance(values, list):
                return names
            for item in values:
                if isinstance(item, dict):
                    text = _clean(
                        item.get("nominativo")
                        or item.get("nome")
                        or item.get("denominazione")
                        or item.get("label")
                    )
                else:
                    text = _clean(item)
                key = re.sub(r"\s+", " ", text).casefold()
                if text and key not in seen:
                    seen.add(key)
                    names.append(text)
            return names

        return {
            "portale": _portale_source_name(portale),
            "import_log_id": import_log_id,
            "acquisito_il": datetime.now().isoformat(),
            "external_id": _clean(selection.get("external_id")),
            "numero": _clean(identity.get("numero") or selection.get("numero")),
            "anno": int(identity.get("anno") or selection.get("anno") or 0),
            "ufficio_nome": _clean(identity.get("ufficio_nome") or selection.get("ufficio_nome")),
            "ufficio_codice": _clean(identity.get("ufficio_codice") or selection.get("ufficio_codice")),
            "procedimento": _clean(identity.get("procedimento") or selection.get("procedimento")),
            "sub_procedimento": _clean(identity.get("sub_procedimento") or selection.get("sub_procedimento")),
            "sezione": _clean(identity.get("sezione") or selection.get("sezione")),
            "stato": _clean(identity.get("stato") or selection.get("stato")),
            "oggetto": _clean(identity.get("oggetto") or selection.get("oggetto")),
            "data_iscrizione": _normalizza_data_portale(identity.get("data_iscrizione")),
            "data_udienza": _normalizza_data_portale(identity.get("data_udienza")),
            "ultima_attivita": _clean(identity.get("ultima_attivita") or selection.get("ultima_attivita")),
            "parti": _names((preview or {}).get("parti") or selection.get("parti")),
            "controparti": _names((preview or {}).get("controparti") or selection.get("controparti")),
            "difensori": _names((preview or {}).get("difensori")),
            "counts": {
                "parti": int(counts.get("parti") or 0),
                "documenti": int(counts.get("documenti") or 0),
                "depositi": int(counts.get("depositi") or 0),
                "eventi": int(counts.get("eventi") or 0),
                "udienze": int(counts.get("udienze") or 0),
                "comunicazioni": int(counts.get("comunicazioni") or 0),
                "istanze": int(counts.get("istanze") or 0),
                "esiti": int(counts.get("esiti") or 0),
            },
        }

    def _update_fascicolo_sync_metadata(
        id_fasc: str,
        *,
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any] | None = None,
        import_log_id: str,
        has_conflicts: bool,
        document_sync_enabled: bool,
        events_sync_enabled: bool,
        sync_status: str,
    ) -> Fascicolo:
        return get_fascicoli().aggiorna(
            id_fasc,
            source=_portale_source_name(portale),
            source_external_id=str(selection.get("external_id") or "").strip(),
            last_sync_at=datetime.now().isoformat(),
            sync_status=sync_status,
            import_log_id=import_log_id,
            source_snapshot=_source_snapshot_portale(portale, selection, preview or {}, import_log_id),
            has_conflicts=has_conflicts,
            document_sync_enabled=document_sync_enabled,
            events_sync_enabled=events_sync_enabled,
        )

    def _selection_preview_from_existing_fascicolo_telematico(fasc: Fascicolo) -> tuple[str, dict[str, Any], dict[str, Any]]:
        source_map = {
            "PST": "pst",
            "PDP": "pdp",
            "PAT": "pat",
            "PTT": "ptt",
        }
        portale = source_map.get(str(getattr(fasc, "source", "") or "").strip().upper(), "")
        if not portale:
            return "", {}, {}
        documenti: list[dict[str, Any]] = []
        for dep in list(getattr(fasc, "depositi_pct", []) or []):
            if getattr(dep, "documenti_portale", None):
                documenti.extend(list(dep.documenti_portale or []))
        if not documenti:
            for doc in list(getattr(fasc, "documenti", []) or []):
                if not str(getattr(doc, "id_deposito_pct", "") or "").strip():
                    continue
                documenti.append(
                    {
                        "id_documento": str(doc.id),
                        "nome": str(doc.nome or "").strip(),
                        "tipo": getattr(getattr(doc, "tipo", None), "value", ""),
                        "data_deposito": str(getattr(doc, "data_documento", "") or "").strip(),
                        "mittente": str(fasc.avvocato_referente or fasc.avvocato_dominus or "").strip(),
                        "dimensione_bytes": int(getattr(doc, "dimensione_bytes", 0) or 0),
                        "disponibile": True,
                        "id_deposito": str(getattr(doc, "id_deposito_pct", "") or "").strip(),
                        "tipo_atto": "",
                    }
                )
        selection = {
            "external_id": str(getattr(fasc, "source_external_id", "") or "").strip()
            or f"{fasc.tribunale}:{fasc.numero_rg}:{fasc.anno_rg}:{fasc.tipo_procedimento or getattr(getattr(fasc, 'tipo', None), 'value', '')}",
            "numero": str(getattr(fasc, "numero_rg", "") or "").strip(),
            "anno": int(getattr(fasc, "anno_rg", 0) or 0),
            "ufficio_codice": "",
            "ufficio_nome": str(getattr(fasc, "tribunale", "") or "").strip(),
            "procedimento": str(getattr(fasc, "tipo_procedimento", "") or getattr(getattr(fasc, "tipo", None), "value", "")).strip(),
            "sezione": str(getattr(fasc, "sezione", "") or "").strip(),
            "stato": str(getattr(fasc, "sync_status", "") or getattr(getattr(fasc, "stato", None), "value", "")).strip(),
            "oggetto": str(getattr(fasc, "oggetto", "") or "").strip(),
            "parti": [str(getattr(fasc, "nome_cliente", "") or "").strip()] if str(getattr(fasc, "nome_cliente", "") or "").strip() else [],
            "controparti": [str(getattr(fasc, "controparte", "") or "").strip()] if str(getattr(fasc, "controparte", "") or "").strip() else [],
            "ultima_attivita": str(getattr(fasc, "last_sync_at", "") or getattr(fasc, "modificato_il", "") or "").strip(),
            "payload": {},
        }
        preview = _build_portale_preview(portale, selection, documenti)
        return portale, selection, preview

    def _sync_telematico_case_from_portale(
        portale: str,
        *,
        id_fasc: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        import_log_id: str = "",
        sync_status: str = "",
        document_sync_enabled: bool = False,
        workflow_url: str = "",
        user_name: str = "",
        backfill: bool = False,
    ) -> dict[str, Any]:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return {}
        repo = get_telematico()
        cfg = get_config_studio().config
        identity = dict((preview or {}).get("identity") or {})
        native_status = str(identity.get("stato") or selection.get("stato") or "").strip().upper()
        has_documents = int((preview.get("counts") or {}).get("documenti", 0) or 0) > 0
        portal_case_ref = str(selection.get("external_id") or getattr(fasc, "source_external_id", "") or "").strip()
        existing_case = repo.find_case(
            practice_id=id_fasc,
            service_code=_telematico_service_code(portale),
            portal_case_ref=portal_case_ref or None,
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or None,
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip() or None,
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip() or None,
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0) or None,
        )
        counsel_name = (
            str(getattr(fasc, "avvocato_referente", "") or "").strip()
            or str(getattr(fasc, "avvocato_dominus", "") or "").strip()
            or str(getattr(cfg.studio, "nome_avvocato", "") or "").strip()
            or str(user_name or "").strip()
        )
        counsel_cf = (
            str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
            or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
        )
        case = repo.upsert_case(
            id=str((existing_case or {}).get("id") or "").strip() or None,
            practice_id=id_fasc,
            channel_family=_telematico_channel_family(portale),
            service_code=_telematico_service_code(portale),
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or "Ufficio da completare",
            office_type="",
            district="",
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip(),
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip(),
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0),
            subject_name=str((selection.get("parti") or [getattr(fasc, "nome_cliente", "")])[0] or getattr(fasc, "nome_cliente", "")).strip() or "Parte non definita",
            subject_cf="",
            counterparty_name=str((selection.get("controparti") or [getattr(fasc, "controparte", "")])[0] or getattr(fasc, "controparte", "")).strip(),
            counsel_name=counsel_name or "Difensore da completare",
            counsel_cf=counsel_cf or "N/D",
            portal_case_ref=portal_case_ref or None,
            portal_case_url="",
            workflow_url=workflow_url or None,
            internal_status=_telematico_internal_status(
                sync_status=sync_status or getattr(fasc, "sync_status", ""),
                native_status=native_status,
                has_documents=has_documents,
                documents_imported=bool(document_sync_enabled),
                needs_manual_review=bool(getattr(fasc, "has_conflicts", False)),
            ),
            native_status=native_status or None,
            import_log_id=import_log_id or getattr(fasc, "import_log_id", "") or None,
            notes=str(getattr(fasc, "note", "") or "").strip() or None,
            last_sync_at=str(getattr(fasc, "last_sync_at", "") or datetime.now().isoformat()),
        )
        if not (backfill and existing_case):
            repo.add_event(
                str(case["id"]),
                event_type="telematico_sync",
                event_source="import" if not backfill else "system",
                title=f"{_portale_source_name(portale)} sincronizzato nel core telematico",
                description=f"Pratica {getattr(fasc, 'numero', '')} allineata con il canale {_portale_source_name(portale)}.",
                payload_json={
                    "practice_id": id_fasc,
                    "import_log_id": import_log_id,
                    "documents": int((preview.get('counts') or {}).get('documenti', 0) or 0),
                },
                created_by_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or None,
            )
        depositi = list(preview.get("depositi") or [])
        if not depositi and list(preview.get("documenti") or []):
            depositi = _group_portale_documents(list(preview.get("documenti") or []))
        for deposito in depositi:
            transmission = repo.upsert_transmission(
                str(case["id"]),
                transmission_type="case_import",
                act_type=str(deposito.get("tipo_atto") or "Deposito ufficiale").strip(),
                portal_reference=str(deposito.get("id_deposito") or import_log_id or portal_case_ref or "").strip() or None,
                internal_status=_telematico_transmission_status(native_status, has_documents=bool(deposito.get("documenti"))),
                native_status=native_status or None,
                submitted_at=str(deposito.get("data_deposito") or identity.get("data_iscrizione") or "").strip() or None,
                outcome_at=str(identity.get("ultima_attivita") or deposito.get("data_deposito") or "").strip() or None,
                notes=f"Catalogo {_portale_source_name(portale)} allineato nel core telematico.",
            )
            for doc in list(deposito.get("documenti") or []):
                doc_ref = str(doc.get("id_cat") or doc.get("id_documento") or "").strip()
                tele_doc = repo.upsert_document(
                    str(case["id"]),
                    document_role=_telematico_document_role(doc),
                    document_category=str(doc.get("tipo") or "").strip() or None,
                    title=str(doc.get("nome") or "Documento ufficiale").strip(),
                    original_filename=str(doc.get("nome") or "").strip() or None,
                    file_size_bytes=int(doc.get("dimensione_bytes") or 0) or None,
                    source_type="portal",
                    signed=1 if str(doc.get("nome") or "").lower().endswith(".p7m") else 0,
                    portal_document_ref=doc_ref or None,
                    portal_document_date=str(doc.get("data_deposito") or "").strip() or None,
                    id_deposito=str(deposito.get("id_deposito") or "").strip(),
                    tipo_atto=str(deposito.get("tipo_atto") or doc.get("tipo_atto") or "").strip(),
                    data_deposito=str(doc.get("data_deposito") or deposito.get("data_deposito") or "").strip() or None,
                    mittente=str(doc.get("mittente") or deposito.get("mittente") or "").strip() or None,
                    notes=f"Documento censito da {_portale_source_name(portale)}.",
                )
                repo.link_document_to_transmission(
                    str(transmission["id"]),
                    str(tele_doc["id"]),
                    relation_type="main_act" if tele_doc.get("document_role") == "main_act" else "attachment",
                )
        if has_documents and not document_sync_enabled:
            repo.ensure_task(
                str(case["id"]),
                task_type="download_case_file",
                title="Completare acquisizione documenti dal portale ufficiale",
                description=f"Il fascicolo {_portale_source_name(portale)} ha documenti censiti ma non ancora integrati nel fascicolo locale.",
                priority="high",
                assigned_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or "",
            )
        else:
            repo.close_tasks(str(case["id"]), task_type="download_case_file")
        return case

    def _backfill_telematico_from_existing_fascicoli() -> dict[str, int]:
        summary = {"processed": 0, "failed": 0}
        for fasc in get_fascicoli().tutti():
            if str(getattr(fasc, "source", "") or "").strip().upper() not in {"PST", "PDP", "PAT", "PTT"}:
                continue
            portale, selection, preview = _selection_preview_from_existing_fascicolo_telematico(fasc)
            if not portale or not selection:
                continue
            try:
                _sync_telematico_case_from_portale(
                    portale,
                    id_fasc=fasc.id,
                    selection=selection,
                    preview=preview,
                    import_log_id=str(getattr(fasc, "import_log_id", "") or ""),
                    sync_status=str(getattr(fasc, "sync_status", "") or ""),
                    document_sync_enabled=bool(getattr(fasc, "document_sync_enabled", False)),
                    user_name=getattr(getattr(g, "utente_corrente", None), "username", "") or "",
                    backfill=True,
                )
                summary["processed"] += 1
            except Exception as e:
                summary["failed"] += 1
                app.logger.exception(
                    "Errore backfill telematico fascicolo %s (%s): %s",
                    getattr(fasc, "id", ""),
                    getattr(fasc, "numero", ""),
                    e,
                )
        return summary

    def _telematico_dashboard_warning_message(error: Exception) -> str:
        message = str(error).strip().lower()
        if "archivio telematico temporaneamente non disponibile" in message or "database or disk is full" in message:
            return (
                "Archivio telematico temporaneamente non disponibile. IUSENTRA ha messo in pausa "
                "l'aggiornamento SQLite e continuera' a riprovare automaticamente."
            )
        if "temporaneamente occupato" in message or "database is locked" in message:
            return (
                "Archivio telematico temporaneamente occupato da un aggiornamento in corso. "
                "La pagina resta disponibile e il sistema riprovera' automaticamente."
            )
        return (
            "Cabina telematica disponibile in modalita' ridotta. "
            "Il sistema ha intercettato un errore tecnico e continuera' a lavorare in sicurezza."
        )

    def _importa_o_collega_fascicolo_portale(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
        downloaded_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
        options = _coerce_import_options(dict(options or {}), portale=portale)
        scarica_originale_portale = _scarica_originale_portale_enabled(options, portale)
        selection_dc = _selection_to_fascicolo_dataclass(portale, selection)
        analysis = _analyze_portale_import(portale, selection, preview, options, mapping)
        if analysis["blockers"]:
            first_blocker = dict((analysis.get("blockers") or [{}])[0] or {})
            blocker_label = str(first_blocker.get("label") or first_blocker.get("title") or "Controllo bloccante").strip()
            blocker_detail = str(first_blocker.get("detail") or first_blocker.get("message") or "").strip()
            suffix = f" {blocker_label}: {blocker_detail}" if blocker_detail else f" {blocker_label}."
            raise ValueError(f"Sono presenti blocchi da risolvere prima dell'importazione.{suffix}")
        mode, resolved_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        partial_pst_existing_update = False

        preview_for_files = _filter_portale_preview_by_options(preview, options)
        importa_file_portale = _preview_richiede_file_portale(options)
        files = list(downloaded_files or [])
        counts = preview_for_files.get("counts") or {}
        documenti_attesi = int(counts.get("documenti", 0) or 0)
        selected_preview_docs = list(preview_for_files.get("documenti") or [])
        documenti_attesi_importabili = sum(1 for row in selected_preview_docs if not _portale_item_is_informativo(row))
        decoded_items: list[dict[str, Any]] = []
        decoded_items_raw: list[dict[str, Any]] = []
        document_report: dict[str, Any] = _portale_document_report(
            files=files,
            preview_docs=selected_preview_docs,
            decoded_items=[],
            final_items=[],
            documenti_attesi=documenti_attesi,
        )
        if importa_file_portale and portale == "pst" and documenti_attesi > 0:
            if files:
                decoded_items_raw = _decode_portale_downloaded_items(files)
                importable_raw_items = [
                    item for item in decoded_items_raw if not _portale_item_is_informativo(item)
                ]
                decoded_items = _merge_preview_metadata_into_portale_items(importable_raw_items, selected_preview_docs)
                filtered_items = _filter_portale_items_by_preview_selection(decoded_items, selected_preview_docs)
                if not filtered_items:
                    positional_items = _merge_portale_items_by_position_when_safe(
                        importable_raw_items,
                        selected_preview_docs,
                    )
                    if positional_items:
                        filtered_items = positional_items
                decoded_items = filtered_items
                decoded_items = _apply_portale_download_mode_to_items(
                    decoded_items,
                    original=scarica_originale_portale,
                )
                document_report = _portale_document_report(
                    files=files,
                    preview_docs=selected_preview_docs,
                    decoded_items=decoded_items_raw,
                    final_items=decoded_items,
                    documenti_attesi=documenti_attesi,
                )
            if not files:
                _append_portale_import_log(
                    {
                        "portale": _portale_source_name(portale),
                        "selection": selection,
                        "preview_counts": preview.get("counts") or {},
                        "options": options,
                        "mapping": mapping,
                        "analysis": analysis,
                        "download": {
                            "documenti_attesi": documenti_attesi,
                            "documenti_attesi_importabili": documenti_attesi_importabili,
                            "documenti_decodificati": 0,
                            "report_documentale": document_report,
                        },
                        "status": "bloccata_protezione_dati",
                        "audit_studio": [
                            "Importazione PST avviata",
                            "Importazione bloccata per assenza file reali",
                            "Importazione annullata senza perdita dati",
                        ],
                        "utente": user_name,
                    }
                )
                raise ValueError(_portale_import_block_message(document_report))
            if not decoded_items:
                _append_portale_import_log(
                    {
                        "portale": _portale_source_name(portale),
                        "selection": selection,
                        "preview_counts": preview.get("counts") or {},
                        "options": options,
                        "mapping": mapping,
                        "analysis": analysis,
                        "download": {
                            "documenti_attesi": documenti_attesi,
                            "documenti_attesi_importabili": documenti_attesi_importabili,
                            "documenti_decodificati": len(decoded_items_raw),
                            "report_documentale": document_report,
                        },
                        "status": "bloccata_protezione_dati",
                        "audit_studio": [
                            "Importazione PST avviata",
                            "Importazione bloccata per assenza file reali",
                            "Importazione annullata senza perdita dati",
                        ],
                        "utente": user_name,
                    }
                )
                raise ValueError(_portale_import_block_message(document_report))
            partial_pst_existing_update = len(decoded_items) < documenti_attesi_importabili and mode in {
                "attach_existing",
                "update_existing",
            }
            if len(decoded_items) < documenti_attesi_importabili and not partial_pst_existing_update:
                raise ValueError(
                    f"Importazione PST interrotta: scaricati {len(decoded_items)} documenti su "
                    f"{documenti_attesi_importabili}. Il fascicolo viene aggiornato solo quando il lotto e' completo."
                )

        audit_studio_events: list[str] = []
        if portale == "pst" and importa_file_portale:
            audit_studio_events.append("Importazione PST avviata")
            for row in list(document_report.get("documenti_reali_elenco") or []):
                nome_reale = str((row or {}).get("nome") or "documento").strip()
                audit_studio_events.append(f"Documento reale riconosciuto: {nome_reale}")
            if int(document_report.get("documenti_informativi") or 0):
                audit_studio_events.append("Documento informativo escluso dall'importazione documentale")
            if int(document_report.get("documenti_reali") or 0) == 0 and documenti_attesi > 0:
                audit_studio_events.append("Importazione bloccata per assenza file reali")

        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": options,
                "mapping": mapping,
                "analysis": analysis,
                "download": {
                    "documenti_attesi": documenti_attesi,
                    "documenti_attesi_importabili": documenti_attesi_importabili,
                    "documenti_decodificati": len(decoded_items),
                    "parziale_su_pratica_esistente": partial_pst_existing_update,
                    "report_documentale": document_report,
                },
                "audit_studio": audit_studio_events,
                "utente": user_name,
            }
        )

        gf = get_fascicoli()
        gc = get_clienti()
        gsog = get_soggetti()
        id_fasc = ""
        created = False

        if mode == "create_new":
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_portale_demo_mode(portale))
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.importa_fascicolo(
                    fascicolo_pw=selection_dc,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
            elif portale == "pdp":
                if _portale_local_channel_enabled(portale):
                    from pct.pdp import ClientPDP

                    client = ClientPDP(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pdp import crea_client_pdp

                    client = crea_client_pdp(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            elif portale == "pat":
                if _portale_local_channel_enabled(portale):
                    from pct.pat import ClientPAT

                    client = ClientPAT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pat import crea_client_pat

                    client = crea_client_pat(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            else:
                if _portale_local_channel_enabled(portale):
                    from pct.sigit import ClientSIGIT

                    client = ClientSIGIT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.sigit import crea_client_sigit

                    client = crea_client_sigit(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            if not risultato.successo or not risultato.id_fascicolo_locale:
                raise ValueError(risultato.messaggio or "Importazione non riuscita.")
            id_fasc = risultato.id_fascicolo_locale
            created = True
        else:
            target = resolved_target
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_portale_demo_mode(portale))
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.sincronizza_fascicolo_esistente(
                    fascicolo_pw=selection_dc,
                    fascicolo_locale=target,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
                if not risultato.successo or not risultato.id_fascicolo_locale:
                    raise ValueError(risultato.messaggio or "Sincronizzazione PST non riuscita.")
                id_fasc = risultato.id_fascicolo_locale
            else:
                target = _sync_existing_fascicolo_from_portale(
                    portale,
                    target,
                    selection,
                    preview,
                    preserve_blank=options.get("sovrascrivi_solo_vuoti", True),
                    append_import_note=not options.get("non_toccare_note_interne", True),
                    user_name=user_name,
                    log_id=log_id,
                )
                id_fasc = target.id

        import_result: dict[str, Any] = {
            "documenti_importati": 0,
            "depositi_agganciati": [],
            "lotto_generico": "",
            "staging_archived": "",
        }
        albero_originale_salvato = ""
        catalogo_depositi_synced = 0
        if importa_file_portale:
            catalogo_depositi_synced = _sync_portale_metadata_on_fascicolo(
                portale,
                id_fasc,
                preview_for_files,
                registrato_da=user_name,
            )
            if files:
                fasc_import = gf.get(id_fasc)
                if not fasc_import:
                    raise ValueError("Fascicolo importato non trovato durante l'acquisizione documenti.")
                if not decoded_items:
                    decoded_items = _decode_portale_downloaded_items(files)
                    decoded_items = _merge_preview_metadata_into_portale_items(decoded_items, selected_preview_docs)
                    decoded_items = _filter_portale_items_by_preview_selection(decoded_items, selected_preview_docs)
                    decoded_items = _apply_portale_download_mode_to_items(
                        decoded_items,
                        original=scarica_originale_portale,
                    )
                if not decoded_items:
                    raise ValueError("Il lotto scaricato dal portale non contiene file importabili.")
                if options.get("mantieni_albero_originale"):
                    albero_originale_salvato = _salva_albero_originale_documenti_portale(fasc_import, decoded_items)
                import_result = _importa_documenti_portale_items(
                    gf=gf,
                    fasc=fasc_import,
                    items=decoded_items,
                    note_importazione=f"Acquisizione guidata da {_portale_source_name(portale)}",
                )

        udienza_result = _sync_udienza_e_scadenza(
            id_fasc,
            preview,
            crea_attivita=options.get("importa_eventi") or options.get("importa_udienze"),
            crea_scadenza=options.get("importa_scadenze", False),
            avvocato=user_name,
        )
        structured_result = _sync_portale_structured_sections(
            portale,
            id_fasc,
            preview,
            options,
            avvocato=user_name,
        )

        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            has_conflicts=bool(analysis["warnings"]),
            document_sync_enabled=importa_file_portale,
            events_sync_enabled=options.get("importa_eventi", False) or options.get("importa_udienze", False),
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )

        workflow_url = ""
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=int(import_result.get("documenti_importati", 0) or 0),
                downloaded_files=decoded_items or files,
            )
            if case:
                workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"])

        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview_for_files if preview_for_files else preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=bool(importa_file_portale),
            workflow_url=workflow_url,
            user_name=user_name,
        )

        fasc = gf.get(id_fasc)
        documenti_importati_count = int(import_result.get("documenti_importati", 0) or 0)
        documenti_da_acquisire = max(documenti_attesi - documenti_importati_count, 0)
        if portale == "pst" and importa_file_portale:
            document_report = dict(document_report)
            document_report["documenti_importati"] = documenti_importati_count
            document_report["documenti_gia_presenti_o_riusati"] = max(
                int(document_report.get("documenti_reali") or 0) - documenti_importati_count,
                0,
            )
            final_audit_events = list(audit_studio_events)
            if int(document_report.get("documenti_informativi") or 0):
                final_audit_events.append("Documento informativo escluso dall'importazione documentale")
            if documenti_importati_count:
                final_audit_events.append("Documento importato nel fascicolo")
            if documenti_da_acquisire:
                final_audit_events.append("Importazione completata con documenti ancora da acquisire")
            else:
                final_audit_events.append("Importazione completata")
            _update_portale_import_log(
                log_id,
                {
                    "status": "completata" if not documenti_da_acquisire else "completata_con_avvisi",
                    "download": {
                        "documenti_attesi": documenti_attesi,
                        "documenti_attesi_importabili": documenti_attesi_importabili,
                        "documenti_decodificati": len(decoded_items),
                        "parziale_su_pratica_esistente": partial_pst_existing_update,
                        "report_documentale": document_report,
                    },
                    "audit_studio": final_audit_events,
                },
            )
        return {
            "id_fascicolo": id_fasc,
            "created": created,
            "resolved_mode": mode,
            "auto_integrated": auto_integrated,
            "import_log_id": log_id,
            "quadro_url": url_for("quadro_fascicolo", id_fasc=id_fasc),
            "dettaglio_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc),
            "scadenziario_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-udienze-scadenze",
            "timeline_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-attivita-processuali",
            "documenti_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-documenti-fascicolo",
            "workflow_url": workflow_url,
            "summary": {
                "numero_pratica": getattr(fasc, "numero", ""),
                "titolo": getattr(fasc, "titolo", ""),
                "documenti": documenti_importati_count,
                "documenti_catalogo": documenti_attesi,
                "documenti_da_acquisire": documenti_da_acquisire,
                "documenti_reali": int(document_report.get("documenti_reali") or documenti_importati_count or 0),
                "documenti_informativi": int(document_report.get("documenti_informativi") or 0),
                "documenti_senza_contenuto": int(document_report.get("documenti_senza_contenuto") or 0),
                "documenti_scartati": int(document_report.get("documenti_scartati") or 0),
                "report_documentale": document_report,
                "depositi": len(import_result.get("depositi_agganciati") or [])
                or catalogo_depositi_synced
                or int(preview.get("counts", {}).get("depositi", 0) or 0),
                "scadenze_generate": udienza_result["scadenze"] + structured_result["scadenze"],
                "scadenze_da_documento": udienza_result.get("scadenze_da_documento", 0),
                "scadenze_scartate_per_data_passata": udienza_result.get("scadenze_scartate", 0) + structured_result.get("scadenze_scartate", 0),
                "eventi_generati": udienza_result["attivita"] + structured_result["attivita"],
                "comunicazioni_generate": structured_result["comunicazioni"],
                "istanze_generate": structured_result["istanze"],
                "depositi_telematici_generati": structured_result["depositi"],
                "conflitti_risolti": len(analysis["warnings"]),
                "lotto_generico": str(import_result.get("lotto_generico") or ""),
                "modalita_documento_portale": "originale" if scarica_originale_portale else "copia",
                "catalogo_solo_metadati": bool(importa_file_portale and documenti_attesi > 0 and not files),
                "download_parziale_portale": bool(partial_pst_existing_update),
                "albero_originale_salvato": bool(albero_originale_salvato),
            },
        }

    def _register_direct_portale_import_sync(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        id_fasc: str,
        created: bool,
        user_name: str,
    ) -> str:
        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": {"direct_import": True},
                "mapping": {"mode": "create_new"},
                "analysis": {},
                "utente": user_name,
            }
        )
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return log_id
        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            has_conflicts=False,
            document_sync_enabled=False,
            events_sync_enabled=False,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=0,
                downloaded_files=[],
            )
            workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"]) if case else ""
        else:
            workflow_url = ""
        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=False,
            workflow_url=workflow_url,
            user_name=user_name,
        )
        return log_id

    def _build_access_status_payload(portale: str) -> dict[str, Any]:
        spec = _spec_portale_acquisizione(portale)
        cfg = get_config_studio().config
        firma_cfg = cfg.firma
        auth_mode = _polis_auth_mode()
        policy = _portal_integration_policy(portale)
        browser_channel_required = _portale_browser_channel_required(portale)
        demo_mode = _portale_demo_mode(portale)
        pkcs11_mode = _portale_usa_local_signer(portale) and not demo_mode
        ultimo_log = _last_portale_import_log(portale)
        if policy.assistant_required:
            if portale == "pat":
                status_text = "Portale ufficiale assistito PAT"
            elif portale == "pdp":
                status_text = "Portale ufficiale assistito PDP"
            elif portale == "ptt":
                status_text = "Portale ufficiale assistito PTT / SIGIT"
            else:
                status_text = "Consultazione via browser ufficiale"
            environment_label = "Sessione assistita locale"
        elif policy.mode == MODE_DIRECT_VERIFIED:
            status_text = "Canale diretto verificato"
            environment_label = "Produzione verificata"
        elif demo_mode:
            status_text = "Modalita demo / fallback"
            environment_label = "Simulazione / compatibilita"
        elif pkcs11_mode:
            status_text = "Accesso via Local Signer / Aruba Key"
            environment_label = "Produzione guidata via browser locale"
        else:
            status_text = "Connessione pronta"
            environment_label = "Produzione guidata"
        return {
            "portale": portale,
            "spec": spec,
            "avvocato": str(getattr(cfg.studio, "nome_avvocato", "") or getattr(g.utente_corrente, "username", "") or "").strip(),
            "codice_fiscale_avvocato": str(getattr(firma_cfg, "cf_avvocato", "") or getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper(),
            "backend_firma": str(getattr(firma_cfg, "backend_firma_operativo_safe", "nessuno") or "").strip(),
            "auth_mode": auth_mode,
            "integration_policy": {
                "mode": policy.mode,
                "direct_allowed": policy.direct_allowed,
                "assistant_required": policy.assistant_required,
                "reason": policy.reason,
                "validation_errors": list(policy.validation_errors),
            },
            "integration_mode": policy.mode,
            "direct_allowed": policy.direct_allowed,
            "assistant_required": policy.assistant_required,
            "assistant_label": str(spec.get("assistant_label") or "").strip(),
            "assistant_disclaimer": str(spec.get("assistant_disclaimer") or "").strip(),
            "deposit_assistant_enabled": bool(spec.get("deposit_assistant_enabled")),
            "demo_mode": demo_mode,
            "pkcs11_mode": pkcs11_mode,
            "browser_channel_required": browser_channel_required,
            "cert_preferences": _polis_cert_preferences() if (pkcs11_mode or browser_channel_required) else {},
            "status_text": status_text,
            "test_ok": not demo_mode,
            "last_sync_at": str(ultimo_log.get("created_at") or "").strip(),
            "last_import_log_id": str(ultimo_log.get("id") or "").strip(),
            "environment_label": environment_label,
        }

    def _search_fascicoli_portale_server(portale: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        portale = (portale or "").strip().lower()
        numero = str(query.get("numero") or "").strip() or None
        anno_raw = str(query.get("anno") or "").strip()
        anno = int(anno_raw) if anno_raw.isdigit() else None
        assistito = str(query.get("assistito") or "").strip() or None
        controparte = str(query.get("controparte") or "").strip() or None
        cf = str(query.get("cf") or "").strip() or None
        oggetto = str(query.get("oggetto") or "").strip().lower()
        stato_filter = str(query.get("stato") or "").strip().lower()
        quick = str(query.get("quick_filter") or "").strip().lower()

        # I canali browser/Local Signer sono un percorso operativo previsto,
        # non un guasto runtime: non devono consumare il circuit breaker.
        if portale == "pst" and _portale_local_channel_enabled(portale):
            raise ValueError(
                "Canale PST locale non inizializzato nel browser. "
                "Verifica che Local Signer sia attivo su questo PC e ripeti la ricerca."
            )
        if portale in {"pdp", "pat", "ptt"} and _portale_browser_channel_required(portale):
            raise ValueError(_portale_browser_guided_message(portale))
        if portale not in {"pst", "pdp", "pat", "ptt"}:
            raise ValueError("Portale non supportato per la ricerca guidata.")

        try:
            def _perform_search():
                if portale == "pst":
                    from pct.polisWeb import crea_client
                    from pct.uffici_giudiziari import risolvi_codice_ministero

                    ufficio_raw = str(query.get("ufficio_codice") or query.get("ufficio") or "").strip()
                    ufficio = risolvi_codice_ministero(ufficio_raw) if ufficio_raw else ""
                    if not ufficio:
                        raise ValueError("Seleziona un ufficio giudiziario.")
                    return crea_client(demo=_portale_demo_mode(portale)).ricerca_fascicoli(
                        tribunale=ufficio,
                        numero_rg=numero,
                        anno_rg=anno,
                        nome_parte=assistito or controparte,
                        codice_fiscale_parte=cf,
                    )
                if portale == "pdp":
                    from pct.pdp import crea_client_pdp
                    from pct.uffici_giudiziari import risolvi_codice_ministero

                    ufficio_raw = str(query.get("ufficio_codice") or query.get("ufficio") or "").strip()
                    ufficio = risolvi_codice_ministero(ufficio_raw) if ufficio_raw else ""
                    if not ufficio:
                        raise ValueError("Seleziona un ufficio giudiziario.")
                    return crea_client_pdp(demo=_portale_demo_mode(portale)).ricerca_fascicoli(
                        ufficio=ufficio,
                        numero_rg=numero,
                        anno_rg=anno,
                        nome_imputato=assistito,
                        tipo_registro=str(query.get("registro") or "").strip() or None,
                    )
                if portale == "pat":
                    from pct.pat import crea_client_pat

                    return crea_client_pat(demo=False).ricerca_fascicoli(
                        ufficio=str(query.get("ufficio_codice") or query.get("ufficio") or "").strip(),
                        numero_ricorso=numero,
                        anno=anno,
                        nome_ricorrente=assistito or controparte,
                        materia=str(query.get("materia") or "").strip() or None,
                    )
                if portale == "ptt":
                    from pct.sigit import crea_client_sigit

                    return crea_client_sigit(demo=False).ricerca_fascicoli(
                        commissione=str(query.get("ufficio_codice") or query.get("ufficio") or "").strip(),
                        numero_rgt=numero,
                        anno_rgt=anno,
                        nome_ricorrente=assistito or controparte,
                        tipo=str(query.get("tipo") or "").strip() or None,
                    )
                return []

            fascicoli = run_portale_runtime_operation(
                portale,
                operation="search",
                callable_=_perform_search,
            )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise ValueError(describe_portale_runtime_error(portale, operation="search", exc=e)) from e

        rows = [_serialize_portale_search_item(portale, fascicolo) for fascicolo in fascicoli]
        if oggetto:
            rows = [row for row in rows if oggetto in str(row.get("oggetto") or "").lower()]
        if stato_filter:
            rows = [row for row in rows if stato_filter in str(row.get("stato") or "").lower()]
        if quick:
            rows = [
                row for row in rows
                if quick in str(row.get("procedimento") or "").lower()
                or quick in str(row.get("oggetto") or "").lower()
                or quick in str(row.get("stato") or "").lower()
            ]
        return rows

    def _preview_documenti_portale_server(portale: str, selection: dict[str, Any]) -> list[dict]:
        portale = (portale or "").strip().lower()
        # Come per la ricerca, un canale locale/browser-guided non e' un
        # errore ripetuto del runtime server: evita falsi "sospeso 60s".
        if portale == "pst" and _portale_local_channel_enabled(portale):
            raise ValueError("Anteprima documenti PST via Local Signer del browser richiesta.")
        if portale in {"pdp", "pat", "ptt"} and _portale_browser_channel_required(portale):
            raise ValueError(_portale_browser_guided_message(portale))
        if portale not in {"pst", "pdp", "pat", "ptt"}:
            raise ValueError("Portale non supportato per l'anteprima guidata.")

        try:
            def _perform_preview():
                if portale == "pst":
                    from pct.polisWeb import crea_client

                    return crea_client(demo=_portale_demo_mode(portale)).consulta_documenti(
                        str(selection.get("ufficio_codice") or "").strip(),
                        str(selection.get("numero") or "").strip(),
                        int(selection.get("anno") or 0),
                    )
                if portale == "pdp":
                    from pct.pdp import crea_client_pdp

                    return crea_client_pdp(demo=_portale_demo_mode(portale)).consulta_documenti(
                        str(selection.get("ufficio_codice") or "").strip(),
                        str(selection.get("numero") or "").strip(),
                        int(selection.get("anno") or 0),
                    )
                if portale == "pat":
                    from pct.pat import crea_client_pat

                    return crea_client_pat(demo=False).consulta_documenti(
                        str(selection.get("ufficio_codice") or selection.get("ufficio") or "").strip(),
                        str(selection.get("numero") or "").strip(),
                        int(selection.get("anno") or 0),
                    )
                if portale == "ptt":
                    from pct.sigit import crea_client_sigit

                    return crea_client_sigit(demo=False).consulta_documenti(
                        str(selection.get("ufficio_codice") or selection.get("ufficio") or "").strip(),
                        str(selection.get("numero") or "").strip(),
                        int(selection.get("anno") or 0),
                    )
                return []

            docs = run_portale_runtime_operation(
                portale,
                operation="preview",
                callable_=_perform_preview,
            )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise ValueError(describe_portale_runtime_error(portale, operation="preview", exc=e)) from e
        return [dict(vars(doc)) for doc in docs]

    _ASSISTED_PORTALS = {"ptt", "pat", "pdp"}
    _SAFE_ASSISTANT_EXTENSIONS = {".zip", ".pdf", ".p7m", ".xml", ".json", ".eml", ".msg", ".txt", ".html", ".htm"}
    _DEPOSIT_PROFILE_BY_PORTAL = {
        "ptt": "ptt_sigit",
        "pat": "pat_siga",
        "pdp": "pdp_penale",
    }

    def _require_assisted_portal(portale: str) -> str:
        portale_norm = (portale or "").strip().lower()
        if portale_norm == "pst":
            raise ValueError("PST usa il canale diretto interno e non appartiene al portale ufficiale assistito.")
        if portale_norm not in _ASSISTED_PORTALS:
            raise ValueError("Portale non supportato per la sessione assistita.")
        return portale_norm

    def _portal_official_url(portale: str) -> str:
        return str(_spec_portale_acquisizione(portale).get("official_url") or "").strip()

    def _portal_assistant_sessions_path() -> Path:
        return Path(_cfg_data_path("PORTALE_IMPORT_LOG_DB")).parent / "portal_assistant_sessions.json"

    def _read_json_dict(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_json_dict(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_assisted_sessions() -> dict[str, Any]:
        return _read_json_dict(_portal_assistant_sessions_path())

    def _save_assisted_session(session: dict[str, Any]) -> dict[str, Any]:
        rows = _load_assisted_sessions()
        rows[str(session["session_id"])] = session
        _write_json_dict(_portal_assistant_sessions_path(), rows)
        return session

    def _get_assisted_session(session_id: str) -> dict[str, Any]:
        session = _load_assisted_sessions().get(str(session_id or "").strip())
        if not isinstance(session, dict):
            raise ValueError("Sessione assistita non trovata.")
        return dict(session)

    def _local_connector_call(path: str, *, method: str = "POST", payload: dict[str, Any] | None = None, timeout: float = 2.0) -> dict[str, Any]:
        url = f"http://127.0.0.1:27272{path}"
        data = None if method.upper() == "GET" else json.dumps(payload or {}).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            method=method.upper(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {"ok": False, "raw": parsed}

    def _public_assisted_session(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session.get("session_id", ""),
            "portale": session.get("portale", ""),
            "official_url": session.get("official_url", ""),
            "mode": session.get("mode", MODE_OFFICIAL_PORTAL_ASSISTED),
            "fascicolo_id": session.get("fascicolo_id", ""),
            "deposito_id": session.get("deposito_id", ""),
            "purpose": session.get("purpose", "acquisizione"),
            "status": session.get("status", ""),
            "local_connector_available": bool(session.get("local_connector_available")),
            "downloaded_files": list(session.get("downloaded_files") or []),
            "message": session.get("message", ""),
        }

    def _portal_assistant_start(portale: str, payload: dict[str, Any] | None = None, *, purpose: str = "acquisizione") -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        policy = _portal_integration_policy(portale_norm)
        official_url = _portal_official_url(portale_norm)
        session_id = f"assist_{uuid.uuid4().hex[:16]}"
        session = {
            "session_id": session_id,
            "portale": portale_norm,
            "official_url": official_url,
            "mode": policy.mode,
            "fascicolo_id": str(body.get("fascicolo_id") or body.get("id_fasc") or "").strip(),
            "deposito_id": str(body.get("deposito_id") or "").strip(),
            "purpose": purpose,
            "status": "local_connector_required",
            "local_connector_available": False,
            "local_session_id": "",
            "downloaded_files": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "message": "Avvia Local Signer / Local Connector su questo PC per aprire la sessione assistita.",
        }
        try:
            local = _local_connector_call(
                "/portal-assistant/session/start",
                payload={
                    "session_id": session_id,
                    "portale": portale_norm,
                    "official_url": official_url,
                    "fascicolo_id": session["fascicolo_id"],
                    "deposito_id": session["deposito_id"],
                    "purpose": purpose,
                },
            )
            if local.get("ok") is True:
                session["local_connector_available"] = True
                session["local_session_id"] = str(local.get("session_id") or session_id)
                session["status"] = str(local.get("status") or "sessione_assistita_pronta")
                session["message"] = "Sessione assistita locale pronta."
            else:
                session["message"] = str(local.get("errore") or local.get("message") or session["message"])
        except (OSError, urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            session["message"] = (
                "Local Connector non raggiungibile. Avvia Local Signer su questo PC: "
                "la sessione assistita resta dentro IUSENTRA e non usa link esterni ordinari."
            )
            session["local_error"] = str(exc)
        _save_assisted_session(session)
        return _public_assisted_session(session)

    def _portal_assistant_open(portale: str, session_id: str) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        session = _get_assisted_session(session_id)
        if session.get("portale") != portale_norm:
            raise ValueError("Sessione assistita non coerente con il portale.")
        if not session.get("local_connector_available"):
            return _public_assisted_session(session)
        try:
            local = _local_connector_call(
                f"/portal-assistant/session/{session.get('local_session_id') or session_id}/open",
                payload={"official_url": session.get("official_url", "")},
            )
            if local.get("ok") is True:
                session["status"] = str(local.get("status") or "portale_ufficiale_assistito_aperto")
                session["message"] = "Portale ufficiale aperto nella sessione assistita locale."
        except Exception as exc:
            session["status"] = "local_connector_required"
            session["message"] = "Local Connector non raggiungibile. Avvialo e riprova."
            session["local_error"] = str(exc)
        session["updated_at"] = datetime.now().isoformat()
        _save_assisted_session(session)
        return _public_assisted_session(session)

    def _portal_assistant_watch_downloads(portale: str, session_id: str) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        session = _get_assisted_session(session_id)
        if session.get("portale") != portale_norm:
            raise ValueError("Sessione assistita non coerente con il portale.")
        if not session.get("local_connector_available"):
            return _public_assisted_session(session)
        try:
            local = _local_connector_call(
                f"/portal-assistant/session/{session.get('local_session_id') or session_id}/watch-downloads",
                payload={"portale": portale_norm},
                timeout=4.0,
            )
            if local.get("ok") is True:
                session["status"] = str(local.get("status") or "monitor_download_attivo")
                session["message"] = "Monitor download della sessione assistita attivo."
        except Exception as exc:
            session["status"] = "local_connector_required"
            session["message"] = "Local Connector non raggiungibile per il monitor download."
            session["local_error"] = str(exc)
        session["updated_at"] = datetime.now().isoformat()
        _save_assisted_session(session)
        return _public_assisted_session(session)

    def _portal_assistant_status(portale: str, session_id: str) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        session = _get_assisted_session(session_id)
        if session.get("portale") != portale_norm:
            raise ValueError("Sessione assistita non coerente con il portale.")
        if session.get("local_connector_available"):
            try:
                local = _local_connector_call(
                    f"/portal-assistant/session/{session.get('local_session_id') or session_id}/status",
                    method="GET",
                    timeout=1.5,
                )
                if local.get("ok") is True:
                    session["status"] = str(local.get("status") or session.get("status") or "")
                    session["downloaded_files"] = list(local.get("files") or session.get("downloaded_files") or [])
                    session["message"] = str(local.get("message") or session.get("message") or "")
                    session["updated_at"] = datetime.now().isoformat()
                    _save_assisted_session(session)
            except Exception:
                pass
        return _public_assisted_session(session)

    def _normalize_assisted_file(item: dict[str, Any]) -> dict[str, Any] | None:
        filename = Path(str(item.get("filename") or item.get("name") or "")).name
        if not filename:
            return None
        ext = Path(filename).suffix.lower()
        if ext not in _SAFE_ASSISTANT_EXTENSIONS:
            return None
        content_b64 = str(item.get("content_base64") or item.get("base64") or "").strip()
        sha = str(item.get("sha256") or "").strip().lower()
        size = int(item.get("size") or 0)
        if content_b64:
            try:
                raw = __import__("base64").b64decode(content_b64, validate=True)
                computed = hashlib.sha256(raw).hexdigest()
                if sha and sha != computed:
                    return None
                sha = computed
                size = len(raw)
            except Exception:
                return None
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            return None
        return {
            "filename": filename,
            "nome": filename,
            "nome_file_originale": filename,
            "size": size,
            "dimensione_bytes": size,
            "sha256": sha,
            "detected_at": str(item.get("detected_at") or datetime.now().isoformat()),
            "local_temp_ref": str(item.get("local_temp_ref") or "").strip(),
            "content_base64": content_b64,
            "contenuto_b64": content_b64,
            "source": MODE_OFFICIAL_PORTAL_ASSISTED,
            "origine": MODE_OFFICIAL_PORTAL_ASSISTED,
        }

    def _merge_assisted_files(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in [*existing, *incoming]:
            row = _normalize_assisted_file(dict(item or {}))
            if not row:
                continue
            key = (row["sha256"], row["filename"].lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
        return merged

    def _portal_assistant_collect(portale: str, session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        session = _get_assisted_session(session_id)
        if session.get("portale") != portale_norm:
            raise ValueError("Sessione assistita non coerente con il portale.")
        body = dict(payload or {})
        incoming = body.get("files") if isinstance(body.get("files"), list) else []
        if session.get("local_connector_available"):
            try:
                local = _local_connector_call(
                    f"/portal-assistant/session/{session.get('local_session_id') or session_id}/collect",
                    payload={"portale": portale_norm},
                    timeout=8.0,
                )
                if local.get("ok") is True and isinstance(local.get("files"), list):
                    incoming = [*incoming, *local.get("files")]
                else:
                    session["message"] = str(local.get("errore") or local.get("message") or session.get("message") or "")
            except Exception as exc:
                session["status"] = "local_connector_required"
                session["message"] = "Local Connector non raggiungibile per la raccolta file."
                session["local_error"] = str(exc)
        session["downloaded_files"] = _merge_assisted_files(list(session.get("downloaded_files") or []), incoming)
        session["status"] = "file_ufficiali_raccolti" if session["downloaded_files"] else session.get("status") or "local_connector_required"
        session["updated_at"] = datetime.now().isoformat()
        _save_assisted_session(session)
        return _public_assisted_session(session)

    def _portal_assistant_close(portale: str, session_id: str, *, cancel: bool = False) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        session = _get_assisted_session(session_id)
        if session.get("portale") != portale_norm:
            raise ValueError("Sessione assistita non coerente con il portale.")
        if session.get("local_connector_available"):
            local_path = "cancel" if cancel else "close"
            try:
                _local_connector_call(
                    f"/portal-assistant/session/{session.get('local_session_id') or session_id}/{local_path}",
                    payload={"portale": portale_norm},
                    timeout=4.0,
                )
            except Exception:
                pass
        session["status"] = "sessione_annullata" if cancel else "sessione_chiusa"
        session["updated_at"] = datetime.now().isoformat()
        if cancel:
            session["downloaded_files"] = []
            session["message"] = "Sessione assistita annullata. Nessun file importato."
        else:
            session["message"] = "Sessione assistita chiusa."
        _save_assisted_session(session)
        return _public_assisted_session(session)

    def _practice_engine_repo():
        from pct.practice_engine import PracticeEngineRepository

        return PracticeEngineRepository(str(_cfg_data_path("PRACTICE_ENGINE_DB")))

    def _deposito_precheck_assistito(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        fascicolo_id = str(body.get("fascicolo_id") or body.get("id_fasc") or "").strip()
        tipo_atto = str(body.get("tipo_atto") or "").strip()
        atto_principale_id = str(body.get("atto_principale_id") or body.get("atto_id") or "").strip()
        allegati = [str(x).strip() for x in (body.get("allegati_ids") or body.get("allegati") or []) if str(x).strip()]
        blockers: list[str] = []
        warnings: list[str] = []
        hashes: list[dict[str, Any]] = []
        fascicolo = get_fascicoli().get(fascicolo_id) if fascicolo_id else None
        if not fascicolo:
            blockers.append("Seleziona il fascicolo interno di destinazione.")
        if not tipo_atto:
            blockers.append("Indica il tipo di atto da depositare.")
        if not atto_principale_id:
            blockers.append("Seleziona l'atto principale.")
        documenti = {str(getattr(doc, "id", "")): doc for doc in getattr(fascicolo, "documenti", [])} if fascicolo else {}
        if atto_principale_id and atto_principale_id not in documenti:
            blockers.append("Atto principale non trovato nel fascicolo.")
        for doc_id in [atto_principale_id, *allegati]:
            if not doc_id or doc_id not in documenti:
                continue
            try:
                path = get_fascicoli().percorso_documento(fascicolo_id, doc_id)
                hashes.append(
                    {
                        "documento_id": doc_id,
                        "filename": Path(path).name,
                        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    }
                )
            except Exception:
                hashes.append({"documento_id": doc_id, "sha256": "", "warning": "Hash non calcolabile."})
        if body.get("procura_richiesta") and not body.get("procura_id"):
            blockers.append("Collega la procura richiesta.")
        if body.get("prova_notifica_richiesta") and not body.get("prova_notifica_id"):
            blockers.append("Collega la prova di notifica richiesta.")
        if body.get("pagamento_richiesto") and not body.get("pagamento_id"):
            blockers.append("Collega il contributo o pagamento richiesto.")
        if body.get("firma_digitale_richiesta") and atto_principale_id in documenti:
            doc = documenti[atto_principale_id]
            if not bool(getattr(doc, "firmato_digitalmente", False)):
                warnings.append("Verifica la firma digitale prima di completare il deposito sul portale ufficiale.")
        for field_name, label in (("ufficio", "ufficio"), ("registro", "registro"), ("numero", "numero"), ("anno", "anno")):
            if not str(body.get(field_name) or "").strip():
                warnings.append(f"Completa il dato {label} se richiesto dal portale ufficiale.")
        ok = not blockers
        return {
            "ok": ok,
            "portale": portale_norm,
            "status": "precheck_superato" if ok else "precheck_in_corso",
            "blockers": blockers,
            "warnings": warnings,
            "document_hashes": hashes,
        }

    def _deposito_prepara_assistito(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        precheck = _deposito_precheck_assistito(portale_norm, body)
        if not precheck.get("ok"):
            return {**precheck, "status": "precheck_in_corso"}
        fascicolo_id = str(body.get("fascicolo_id") or body.get("id_fasc") or "").strip()
        repo = _practice_engine_repo()
        session = repo.create_deposit_session(
            fascicolo_id,
            _DEPOSIT_PROFILE_BY_PORTAL[portale_norm],
            portale_norm.upper(),
            status="pronto_per_portale",
            transport_mode=MODE_OFFICIAL_PORTAL_ASSISTED,
            messages=["Pacchetto interno pronto: il deposito si completa sul portale ufficiale assistito."],
        )
        repo.audit(
            fascicolo_id,
            "ASSISTED_PORTAL_DEPOSIT_PREPARED",
            message="Pacchetto deposito assistito preparato.",
            payload={"portale": portale_norm, "deposito_id": session.id, "document_hashes": precheck.get("document_hashes", [])},
        )
        return {
            "ok": True,
            "portale": portale_norm,
            "status": "pronto_per_portale",
            "deposito_id": session.id,
            "fascicolo_id": fascicolo_id,
            "official_url": _portal_official_url(portale_norm),
            "precheck": precheck,
        }

    def _deposito_assistant_start(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = _portal_assistant_start(portale, payload, purpose="deposito")
        if result.get("status") != "local_connector_required":
            result["status"] = "portale_ufficiale_assistito_aperto"
        return result

    def _classifica_ricevuta_deposito(item: dict[str, Any]) -> str:
        explicit = str(item.get("classificazione") or item.get("receipt_type") or "").strip().lower()
        if explicit in {
            "ricevuta_accettazione_deposito",
            "esito_controlli_automatici",
            "esito_segreteria_cancelleria",
            "rifiuto_deposito",
            "anomalia_deposito",
        }:
            return explicit
        text = " ".join(
            str(item.get(key) or "").lower()
            for key in ("filename", "oggetto", "subject", "tipo", "message")
        )
        if "rifiut" in text:
            return "rifiuto_deposito"
        if "anomalia" in text or "errore" in text:
            return "anomalia_deposito"
        if "controll" in text:
            return "esito_controlli_automatici"
        if "segreteria" in text or "cancelleria" in text or "esito" in text:
            return "esito_segreteria_cancelleria"
        return "ricevuta_accettazione_deposito"

    def _status_from_receipt_class(classificazione: str) -> str:
        return {
            "ricevuta_accettazione_deposito": "ricevuta_accettazione_importata",
            "esito_controlli_automatici": "esito_controlli_importato",
            "esito_segreteria_cancelleria": "accettato_da_segreteria",
            "rifiuto_deposito": "rifiutato",
            "anomalia_deposito": "anomalia_da_verificare",
        }.get(classificazione, "anomalia_da_verificare")

    def _pct_state_from_receipt_class(classificazione: str) -> str:
        return {
            "esito_segreteria_cancelleria": "ACCETTATO_CANCELLERIA",
            "rifiuto_deposito": "RIFIUTATO_CANCELLERIA",
            "anomalia_deposito": "ERRORE",
        }.get(classificazione, "IMPORTATO_DA_PORTALE")

    def _ensure_deposit_session_for_receipts(portale: str, fascicolo_id: str, deposito_id: str = ""):
        repo = _practice_engine_repo()
        existing = repo.get_deposit_session(deposito_id) if deposito_id else None
        if existing:
            return repo, existing
        session = repo.create_deposit_session(
            fascicolo_id,
            _DEPOSIT_PROFILE_BY_PORTAL[portale],
            portale.upper(),
            status="deposito_eseguito_sul_portale_da_confermare",
            transport_mode=MODE_OFFICIAL_PORTAL_ASSISTED,
            messages=["Ricevute ufficiali in importazione dal portale assistito."],
        )
        return repo, session

    def _write_evidence_pack(repo, fascicolo_id: str, deposito_id: str, rows: list[dict[str, Any]]) -> EvidencePack:
        evidence_dir = Path(repo.evidence_dir)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"fascicolo_id": fascicolo_id, "deposito_id": deposito_id, "receipts": rows}, ensure_ascii=False, sort_keys=True, indent=2)
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        path = evidence_dir / f"{deposito_id}-official-portal-assisted.json"
        path.write_text(body, encoding="utf-8")
        pack = EvidencePack(
            id=new_id("ep"),
            fascicolo_id=fascicolo_id,
            deposit_session_id=deposito_id,
            path=str(path),
            hash_sha256=sha,
        )
        return repo.save_evidence_pack(pack)

    def _deposito_importa_ricevute_assistito(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        fascicolo_id = str(body.get("fascicolo_id") or body.get("id_fasc") or "").strip()
        if not fascicolo_id or not get_fascicoli().get(fascicolo_id):
            raise ValueError("Fascicolo interno non trovato.")
        deposito_id = str(body.get("deposito_id") or "").strip()
        receipts_raw = body.get("receipts") or body.get("files") or []
        if not isinstance(receipts_raw, list):
            receipts_raw = []
        session_id = str(body.get("assistant_session_id") or body.get("session_id") or "").strip()
        if session_id:
            try:
                assisted = _portal_assistant_collect(portale_norm, session_id, body)
                receipts_raw = [*receipts_raw, *assisted.get("downloaded_files", [])]
            except Exception:
                pass
        repo, dep_session = _ensure_deposit_session_for_receipts(portale_norm, fascicolo_id, deposito_id)
        imported: list[dict[str, Any]] = []
        for item_raw in receipts_raw:
            item = dict(item_raw or {})
            normalized_file = _normalize_assisted_file(item) or {}
            filename = normalized_file.get("filename") or Path(str(item.get("filename") or item.get("name") or "ricevuta_portale")).name
            sha = normalized_file.get("sha256") or str(item.get("sha256") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                content = str(item.get("content") or item.get("testo") or filename).encode("utf-8", errors="ignore")
                sha = hashlib.sha256(content).hexdigest()
            classificazione = _classifica_ricevuta_deposito({**item, **normalized_file})
            status = _status_from_receipt_class(classificazione)
            official_id = str(item.get("id_deposito_ufficiale") or item.get("id_deposito") or body.get("id_deposito_ufficiale") or "").strip()
            esterno = official_id or f"{portale_norm.upper()}-{dep_session.id}-{sha[:12]}"
            oggetto = str(item.get("oggetto") or item.get("subject") or f"Ricevuta deposito {portale_norm.upper()}").strip()
            documenti_portale = [
                {
                    "id_documento": sha[:16],
                    "msg_id": str(item.get("message_id") or item.get("messageId") or "").strip(),
                    "nome": filename,
                    "tipo": classificazione,
                    "data_deposito": str(item.get("data_ufficiale") or item.get("detected_at") or date.today().isoformat())[:10],
                    "mittente": str(item.get("mittente") or "").strip(),
                    "dimensione_bytes": int(item.get("size") or normalized_file.get("size") or 0),
                    "disponibile": True,
                    "id_deposito": esterno,
                    "tipo_atto": classificazione,
                }
            ]
            dep = get_fascicoli().sincronizza_deposito_portale(
                fascicolo_id,
                fonte=f"{portale_norm.upper()} assistito",
                id_deposito_esterno=esterno,
                tipo_atto=classificazione,
                data_deposito=str(item.get("data_ufficiale") or date.today().isoformat())[:10],
                mittente=str(item.get("mittente") or "").strip(),
                documenti_portale=documenti_portale,
                registrato_da=str(getattr(g, "user_email", "") or getattr(getattr(g, "utente_corrente", None), "username", "") or "IUSENTRA"),
                note=(
                    f"{oggetto} | filename={filename} | sha256={sha} | "
                    f"origine=portale ufficiale assistito | portale={portale_norm.upper()}"
                ),
                stato=_pct_state_from_receipt_class(classificazione),
                servizio_portale=SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA,
            )
            receipt = DepositReceipt(
                id=new_id("rcpt"),
                deposit_session_id=dep_session.id,
                fascicolo_id=fascicolo_id,
                receipt_type=classificazione,
                status=status,
                positive=classificazione not in {"rifiuto_deposito", "anomalia_deposito"},
                source=MODE_OFFICIAL_PORTAL_ASSISTED,
                original_name=filename,
                original_hash_sha256=sha,
                payload={
                    "oggetto": oggetto,
                    "mittente": str(item.get("mittente") or "").strip(),
                    "destinatario": str(item.get("destinatario") or "").strip(),
                    "data_ufficiale": str(item.get("data_ufficiale") or "").strip(),
                    "message_id": str(item.get("message_id") or item.get("messageId") or "").strip(),
                    "filename": filename,
                    "sha256": sha,
                    "portale": portale_norm,
                    "id_deposito_ufficiale": official_id,
                    "source": MODE_OFFICIAL_PORTAL_ASSISTED,
                    "fascicolo_deposito_pct_id": getattr(dep, "id", ""),
                },
                message=f"{oggetto} importata nella sezione Comunicazioni/Cancelleria.",
            )
            repo.add_receipt(receipt)
            imported.append({**receipt.payload, "id": receipt.id, "classificazione": classificazione, "status": status})
        if imported:
            dep_session.status = imported[-1].get("status") or dep_session.status
            dep_session.final_receipt_id = imported[-1].get("id") or dep_session.final_receipt_id
            repo.update_deposit_session(dep_session)
            pack = _write_evidence_pack(repo, fascicolo_id, dep_session.id, imported)
            repo.add_timeline_event(
                dep_session.id,
                fascicolo_id,
                "OFFICIAL_PORTAL_RECEIPTS_IMPORTED",
                dep_session.status,
                "Ricevute ed esiti ufficiali importati dal portale assistito.",
                evidence_ref=pack.id,
            )
        return {
            "ok": True,
            "portale": portale_norm,
            "deposito_id": dep_session.id,
            "status": dep_session.status,
            "imported": imported,
            "evidence_pack": repo.get_evidence_pack(dep_session.id).__dict__ if repo.get_evidence_pack(dep_session.id) else {},
        }

    def _strip_assisted_base64(value: Any) -> str:
        text = str(value or "").strip()
        if text.lower().startswith("data:") and "," in text:
            return text.split(",", 1)[1].strip()
        return text

    def _decode_assisted_base64(value: Any) -> bytes:
        content_b64 = _strip_assisted_base64(value)
        if not content_b64:
            return b""
        return base64.b64decode(content_b64, validate=False)

    def _normalize_assisted_import_file(item: dict[str, Any]) -> dict[str, Any] | None:
        row = dict(item or {})
        filename = Path(
            str(
                row.get("nome")
                or row.get("filename")
                or row.get("name")
                or row.get("nome_file_originale")
                or "documento_portale"
            )
        ).name
        if not filename:
            return None
        if Path(filename).suffix.lower() not in _SAFE_ASSISTANT_EXTENSIONS:
            return None
        content_b64 = _strip_assisted_base64(
            row.get("contenuto_b64") or row.get("content_base64") or row.get("base64")
        )
        if not content_b64:
            return None
        try:
            raw = _decode_assisted_base64(content_b64)
        except Exception:
            return None
        if not raw:
            return None
        sha = str(row.get("sha256") or "").strip().lower()
        computed = hashlib.sha256(raw).hexdigest()
        if sha and sha != computed:
            return None
        normalized = {
            "filename": filename,
            "name": filename,
            "nome": filename,
            "nome_file_originale": str(row.get("nome_file_originale") or filename).strip(),
            "contenuto_b64": content_b64,
            "content_base64": content_b64,
            "sha256": computed,
            "size": len(raw),
            "dimensione_bytes": len(raw),
            "data_documento": str(row.get("data_documento") or row.get("data_deposito") or date.today().isoformat())[:10],
            "detected_at": str(row.get("detected_at") or datetime.now().isoformat()),
            "origine": str(row.get("origine") or row.get("source") or row.get("local_temp_ref") or MODE_OFFICIAL_PORTAL_ASSISTED).strip(),
            "source": MODE_OFFICIAL_PORTAL_ASSISTED,
            "content_type": str(row.get("content_type") or "").strip(),
            "id_documento_portale": str(row.get("id_documento_portale") or row.get("id_documento") or "").strip(),
            "id_deposito_esterno": str(row.get("id_deposito_esterno") or row.get("id_deposito") or "").strip(),
            "id_deposito_pct": str(row.get("id_deposito_pct") or "").strip(),
            "tipo_atto": str(row.get("tipo_atto") or "").strip(),
            "tipo": str(row.get("tipo") or "").strip(),
            "mittente": str(row.get("mittente") or "").strip(),
            "servizio_portale": str(row.get("servizio_portale") or "").strip(),
            "id_cat": str(row.get("id_cat") or "").strip(),
            "id_repeatto": str(row.get("id_repeatto") or "").strip(),
            "msg_id": str(row.get("msg_id") or row.get("message_id") or row.get("messageId") or "").strip(),
            "oggetto": str(row.get("oggetto") or row.get("subject") or "").strip(),
            "classificazione": str(row.get("classificazione") or row.get("receipt_type") or "").strip(),
            "id_deposito_ufficiale": str(row.get("id_deposito_ufficiale") or "").strip(),
            "data_ufficiale": str(row.get("data_ufficiale") or row.get("data_documento") or "").strip(),
            "message_id": str(row.get("message_id") or row.get("messageId") or "").strip(),
            "original_documento_portale": bool(row.get("original_documento_portale", True)),
            "modalita_documento_portale": str(row.get("modalita_documento_portale") or "originale").strip(),
        }
        return normalized

    def _assisted_file_is_receipt(item: dict[str, Any]) -> bool:
        text = " ".join(
            str(item.get(key) or "").lower()
            for key in (
                "filename",
                "nome",
                "oggetto",
                "subject",
                "tipo",
                "tipo_atto",
                "classificazione",
                "receipt_type",
            )
        )
        return any(
            token in text
            for token in (
                "ricevuta",
                "accettazione",
                "consegna",
                "esito",
                "segreteria",
                "cancelleria",
                "rifiuto",
                "anomalia",
            )
        )

    def _selection_from_assisted_target(portale: str, fasc: Fascicolo) -> dict[str, Any]:
        numero = str(getattr(fasc, "numero_rg", "") or "").strip()
        anno = int(getattr(fasc, "anno_rg", 0) or 0)
        ufficio = str(getattr(fasc, "tribunale", "") or "").strip()
        procedimento = str(
            getattr(fasc, "tipo_procedimento", "")
            or getattr(getattr(fasc, "tipo", None), "value", "")
            or ""
        ).strip()
        oggetto = str(getattr(fasc, "oggetto", "") or getattr(fasc, "titolo", "") or "").strip()
        payload: dict[str, Any] = {
            "numero_rg": numero,
            "anno_rg": anno,
            "numero": numero,
            "anno": anno,
            "nome_ufficio": ufficio,
            "codice_ufficio": "",
            "tipo": procedimento,
            "oggetto": oggetto,
            "stato": str(getattr(getattr(fasc, "stato", None), "value", "") or "").strip(),
        }
        if portale == "pdp":
            payload.update({"tipo_registro": procedimento, "reato": oggetto})
        elif portale == "pat":
            payload.update({"numero_ricorso": numero, "materia": oggetto})
        elif portale == "ptt":
            payload.update({"numero_rgt": numero, "anno_rgt": anno, "oggetto_controversia": oggetto})
        return {
            "external_id": str(getattr(fasc, "source_external_id", "") or "").strip() or f"{portale.upper()}:{fasc.id}",
            "numero": numero,
            "anno": anno,
            "ufficio_codice": "",
            "ufficio_nome": ufficio,
            "procedimento": procedimento,
            "sezione": str(getattr(fasc, "sezione", "") or "").strip(),
            "stato": str(getattr(fasc, "sync_status", "") or "").strip(),
            "oggetto": oggetto,
            "parti": [str(getattr(fasc, "nome_cliente", "") or "").strip()]
            if str(getattr(fasc, "nome_cliente", "") or "").strip()
            else [],
            "controparti": [str(getattr(fasc, "controparte", "") or "").strip()]
            if str(getattr(fasc, "controparte", "") or "").strip()
            else [],
            "ultima_attivita": datetime.now().isoformat(),
            "payload": payload,
        }

    def _preview_documents_from_assisted_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            rows.append(
                {
                    "id_documento": str(item.get("id_documento_portale") or item.get("sha256") or f"DOC-{index}")[:32],
                    "id_deposito": str(item.get("id_deposito_esterno") or item.get("id_deposito_pct") or "").strip(),
                    "nome": str(item.get("nome") or item.get("filename") or f"documento_{index}").strip(),
                    "tipo": str(item.get("tipo") or item.get("tipo_atto") or "Documento").strip(),
                    "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or "Documento").strip(),
                    "data_deposito": str(item.get("data_documento") or item.get("data_ufficiale") or date.today().isoformat())[:10],
                    "mittente": str(item.get("mittente") or "").strip(),
                    "dimensione_bytes": int(item.get("dimensione_bytes") or item.get("size") or 0),
                    "disponibile": True,
                    "servizio_portale": str(item.get("servizio_portale") or "").strip(),
                }
            )
        return rows

    def _importa_file_assistiti_portale(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        mapping_body = body.get("mapping") if isinstance(body.get("mapping"), dict) else {}
        options_body = body.get("options") if isinstance(body.get("options"), dict) else {}
        fascicolo_id = str(
            body.get("fascicolo_id")
            or body.get("id_fasc")
            or body.get("fascicolo_locale_id")
            or mapping_body.get("target_fascicolo_id")
            or ""
        ).strip()
        gf = get_fascicoli()
        fasc = gf.get(fascicolo_id) if fascicolo_id else None
        if not fasc:
            raise ValueError("Seleziona il fascicolo interno in cui importare file, ricevute ed esiti.")

        files_raw = body.get("downloaded_files") or body.get("files") or []
        if not isinstance(files_raw, list):
            files_raw = []
        session_id = str(body.get("assistant_session_id") or body.get("session_id") or "").strip()
        if session_id:
            assisted = _portal_assistant_collect(portale_norm, session_id, {})
            files_raw = [*files_raw, *assisted.get("downloaded_files", [])]

        normalized_files: list[dict[str, Any]] = []
        seen_files: set[tuple[str, str]] = set()
        for item in files_raw:
            normalized = _normalize_assisted_import_file(dict(item or {}))
            if not normalized:
                continue
            key = (str(normalized.get("sha256") or ""), str(normalized.get("nome") or "").lower())
            if key in seen_files:
                continue
            seen_files.add(key)
            normalized_files.append(normalized)
        if not normalized_files:
            raise ValueError("La sessione assistita non ha consegnato file importabili al fascicolo.")

        decoded_items = _decode_portale_downloaded_items(normalized_files)
        if not decoded_items:
            raise ValueError("I file raccolti non contengono documenti leggibili da importare.")

        user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
        selection = _selection_from_assisted_target(portale_norm, fasc)
        preview = _build_portale_preview(
            portale_norm,
            selection,
            _preview_documents_from_assisted_items(decoded_items),
        )
        document_result = _importa_documenti_portale_items(
            gf=gf,
            fasc=fasc,
            items=decoded_items,
            note_importazione=f"Sessione assistita IUSENTRA da {_portale_source_name(portale_norm)}",
        )

        receipt_files = [row for row in normalized_files if _assisted_file_is_receipt(row)]
        receipt_result: dict[str, Any] = {"imported": []}
        receipt_warning = ""
        if receipt_files:
            try:
                receipt_result = _deposito_importa_ricevute_assistito(
                    portale_norm,
                    {
                        "fascicolo_id": fascicolo_id,
                        "receipts": receipt_files,
                        "assistant_session_id": "",
                    },
                )
            except Exception as exc:
                receipt_warning = str(exc)

        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale_norm),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": {"sessione_assistita_iusentra": True, **options_body},
                "mapping": {"mode": "update_existing", "target_fascicolo_id": fascicolo_id, **mapping_body},
                "analysis": {"warnings": [receipt_warning] if receipt_warning else []},
                "download": {
                    "file_raccolti": len(normalized_files),
                    "documenti_decodificati": len(decoded_items),
                    "ricevute_rilevate": len(receipt_files),
                },
                "utente": user_name,
            }
        )

        _update_fascicolo_sync_metadata(
            fascicolo_id,
            portale=portale_norm,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            has_conflicts=bool(receipt_warning),
            document_sync_enabled=True,
            events_sync_enabled=False,
            sync_status="SINCRONIZZATO",
        )
        _sync_telematico_case_from_portale(
            portale_norm,
            id_fasc=fascicolo_id,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            sync_status="SINCRONIZZATO",
            document_sync_enabled=True,
            workflow_url="",
            user_name=user_name,
        )

        detail_url = url_for("dettaglio_fascicolo", id_fasc=fascicolo_id)
        imported_receipts = list(receipt_result.get("imported") or [])
        summary = {
            "fascicolo_id": fascicolo_id,
            "numero_pratica": str(getattr(fasc, "numero", "") or ""),
            "titolo": str(getattr(fasc, "titolo", "") or ""),
            "documenti": int(document_result.get("documenti_importati", 0) or 0),
            "file_raccolti": len(normalized_files),
            "ricevute": len(imported_receipts),
            "depositi": len(document_result.get("depositi_agganciati") or []) + len(imported_receipts),
            "fascicolo_url": detail_url,
            "message": "File, ricevute ed esiti acquisiti nel fascicolo interno.",
        }
        if receipt_warning:
            summary["avviso_ricevute"] = receipt_warning
        return {
            "id_fascicolo": fascicolo_id,
            "created": False,
            "resolved_mode": "update_existing",
            "import_log_id": log_id,
            "dettaglio_url": detail_url,
            "documenti_url": detail_url + "#sezione-documenti-fascicolo",
            "timeline_url": detail_url + "#sezione-attivita-processuali",
            "summary": summary,
            "documenti": document_result,
            "ricevute": receipt_result,
        }

    def _deposito_finalizza_assistito(portale: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        portale_norm = _require_assisted_portal(portale)
        body = dict(payload or {})
        fascicolo_id = str(body.get("fascicolo_id") or body.get("id_fasc") or "").strip()
        deposito_id = str(body.get("deposito_id") or "").strip()
        repo = _practice_engine_repo()
        session = repo.get_deposit_session(deposito_id) if deposito_id else None
        receipts = repo.list_receipts(deposito_id) if deposito_id else []
        has_official = bool(
            str(body.get("ricevuta_ufficiale_sha256") or "").strip()
            or str(body.get("esito_ufficiale_sha256") or "").strip()
            or str(body.get("id_deposito_ufficiale") or "").strip()
            or any(str(r.original_hash_sha256 or "").strip() for r in receipts)
        )
        if not has_official:
            if session:
                session.status = "anomalia_da_verificare"
                repo.update_deposit_session(session)
                repo.add_timeline_event(
                    session.id,
                    session.fascicolo_id,
                    "ASSISTED_DEPOSIT_FINALIZATION_BLOCKED",
                    session.status,
                    "Finalizzazione bloccata: manca ricevuta o esito ufficiale.",
                )
            return {
                "ok": False,
                "portale": portale_norm,
                "status": "anomalia_da_verificare",
                "message": "Non posso finalizzare senza ricevuta, esito ufficiale o identificativo ufficiale verificato.",
            }
        if not session:
            if not fascicolo_id:
                raise ValueError("Indica il fascicolo interno per finalizzare il deposito.")
            _, session = _ensure_deposit_session_for_receipts(portale_norm, fascicolo_id, "")
        session.status = "acquisito_nel_fascicolo_interno"
        session.acquired_at = datetime.now().isoformat()
        if receipts and not session.final_receipt_id:
            session.final_receipt_id = receipts[-1].id
        repo.update_deposit_session(session)
        repo.add_timeline_event(
            session.id,
            session.fascicolo_id,
            "ASSISTED_DEPOSIT_FINALIZED",
            session.status,
            "Deposito acquisito nel fascicolo interno con evidenza ufficiale.",
        )
        return {
            "ok": True,
            "portale": portale_norm,
            "deposito_id": session.id,
            "status": session.status,
        }

    def _local_signer_tools_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "tools"

    def _local_signer_dist_dir() -> Path:
        return _local_signer_tools_dir() / "dist"

    def _local_signer_source_path() -> Path:
        return _local_signer_tools_dir() / "local_signer.py"

    def _local_ai_bridge_source_path() -> Path:
        return _local_signer_tools_dir() / "local_ai_host_bridge.py"

    def _local_ai_lex_context_source_path() -> Path:
        return _local_signer_tools_dir() / "lex_document_context.py"

    def _local_signer_visible_signature_source_path() -> Path:
        return Path(__file__).resolve().parents[2] / "visible_signature.py"

    def _local_signer_version() -> str:
        source = _local_signer_source_path().read_text(encoding="utf-8")
        match = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', source)
        if not match:
            raise ValueError("Versione Local Signer non trovata in tools/local_signer.py")
        return match.group(1)

    def _local_signer_windows_cmd_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.cmd"

    def _local_signer_windows_cmd_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_cmd_name()

    def _local_signer_windows_exe_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.exe"

    def _local_signer_windows_ps1_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.ps1"

    def _local_signer_windows_offline_ps1_name() -> str:
        """PS1 offline self-contained (generato da build_dist.py) — alternativa all'EXE."""
        return _local_signer_windows_ps1_name()

    def _local_signer_windows_offline_ps1_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_offline_ps1_name()

    def _local_signer_macos_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.command"

    def _local_signer_linux_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.run"

    def _local_signer_python_name() -> str:
        return f"local_signer-{_local_signer_version()}.py"

    def _local_ai_bridge_python_name() -> str:
        return f"local_ai_host_bridge-{_local_signer_version()}.py"

    def _local_ai_lex_context_python_name() -> str:
        return f"lex_document_context-{_local_signer_version()}.py"

    def _local_signer_visible_signature_python_name() -> str:
        return f"visible_signature-{_local_signer_version()}.py"

    def _local_signer_windows_exe_path() -> Path:
        # Restituisce solo il path dell'exe versionato (es. SetupLocalSigner-1.5.10.exe).
        # NON cade in fallback sul generico SetupLocalSigner.exe (potrebbe essere
        # una versione precedente) — se l'exe versionato non esiste il chiamante
        # deve usare la PS1 offline.
        return _local_signer_dist_dir() / _local_signer_windows_exe_name()

    def _local_signer_windows_exe_alias_path() -> Path:
        # Alias non versionato: l'ULTIMO EXE Windows generato (qualsiasi versione).
        # Serve come fallback di prima installazione quando l'EXE della versione
        # corrente non e' ancora stato rigenerato da Windows: un EXE precedente
        # installa comunque Python portatile + venv + sorgenti, e al primo
        # /update il Local Signer aggiorna i sorgenti .py alla versione corrente
        # (vedi _aggiorna_sorgenti_local_signer). Quindi la versione dell'EXE non
        # deve necessariamente coincidere con quella dei sorgenti.
        return _local_signer_dist_dir() / "SetupLocalSigner.exe"

    def _local_signer_uffici_path() -> Path:
        return Path(__file__).resolve().parents[2] / "pct" / "data" / "uffici_ministero.json"

    def _local_signer_uffici_pst_pubblici_path() -> Path:
        return Path(__file__).resolve().parents[2] / "pct" / "data" / "uffici_pst_pubblici.json"

    def _local_signer_macos_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_macos_name()
        legacy = _local_signer_dist_dir() / "InstallaLocalSigner.command"
        if preferred.exists():
            return preferred
        return legacy

    def _local_signer_linux_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_linux_name()
        legacy_run = _local_signer_dist_dir() / "InstallaLocalSigner.run"
        legacy = _local_signer_dist_dir() / "installa_local_signer.sh"
        if preferred.exists():
            return preferred
        if legacy_run.exists():
            return legacy_run
        return legacy

    def _local_signer_allowed_origins(base_url: str) -> str:
        origini = {base_url.rstrip("/")}
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            origini.add(configured)
        origini.add("http://127.0.0.1:8080")
        origini.add("http://localhost:8080")
        origini.add("https://app.iusentra.it")
        origini.add("https://studio-legale-pct-production.up.railway.app")
        return ",".join(sorted(o for o in origini if o))

    def _render_local_signer_windows_ps1(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""# IUSENTRA Local Signer v{version} - Installazione automatica Windows
# Eseguire in PowerShell come utente normale (non richiede amministratore)
# Punto ufficiale download: https://app.iusentra.it/impostazioni?tab=firma

$ErrorActionPreference = 'Stop'
$dir    = "$env:APPDATA\\IUSENTRA\\LocalSigner"
$venv   = "$dir\\.venv"
$py     = "$dir\\local_signer.py"
$aiBridge = "$dir\\local_ai_host_bridge.py"
$lexContext = "$dir\\lex_document_context.py"
$visibleSignature = "$dir\\visible_signature.py"
$moduleDir = "$dir\\local_signer_mod"
$dataDir = "$dir\\data"
$uffici = "$dataDir\\uffici_ministero.json"
$ufficiPstPubblici = "$dataDir\\uffici_pst_pubblici.json"
$starterCmd = "$dir\\\\start_local_signer.cmd"
$starterVbs = "$dir\\\\start_local_signer.vbs"
$pyExe  = "$venv\\\\Scripts\\\\python.exe"
$pywExe = "$venv\\\\Scripts\\\\pythonw.exe"
$allowedOrigins = "{allowed_origins}"
$updateInstallerUrl = "{base_url}/polisWeb/local-signer/setup/windows"
$version = "{version}"

Write-Host "IUSENTRA Local Signer v$version - Installazione..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $dir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $moduleDir | Out-Null

Write-Host "  Scarico local_signer.py..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download" -OutFile $py -UseBasicParsing
Write-Host "  Scarico bridge AI locale..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-ai-bridge" -OutFile $aiBridge -UseBasicParsing
Write-Host "  Scarico parser documenti per Lex..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/lex-document-context" -OutFile $lexContext -UseBasicParsing
Write-Host "  Scarico modulo firma visibile..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/visible-signature" -OutFile $visibleSignature -UseBasicParsing
Write-Host "  Scarico registro uffici PST..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/uffici" -OutFile $uffici -UseBasicParsing
Write-Host "  Scarico catalogo pubblico uffici PST..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/uffici-pst-pubblici" -OutFile $ufficiPstPubblici -UseBasicParsing
Write-Host "  Scarico moduli interni Local Signer..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/__init__.py" -OutFile "$moduleDir\\__init__.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/ai_cache.py" -OutFile "$moduleDir\\ai_cache.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" -OutFile "$moduleDir\\ai_handlers.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/pec_bridge.py" -OutFile "$moduleDir\\pec_bridge.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/security.py" -OutFile "$moduleDir\\security.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/server_bootstrap.py" -OutFile "$moduleDir\\server_bootstrap.py" -UseBasicParsing
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-signer-mod/support_agent.py" -OutFile "$moduleDir\\support_agent.py" -UseBasicParsing

try {{
    $v = python --version 2>&1
    Write-Host "  Python trovato: $v"
}} catch {{
    Write-Host "ERRORE: Python non trovato. Scaricarlo da https://python.org" -ForegroundColor Red
    Read-Host "Premere Invio per uscire"
    exit 1
}}

Write-Host "  Creo ambiente virtuale..."
python -m venv $venv

Write-Host "  Aggiorno pip..."
& $pyExe -m pip install --quiet --upgrade pip

Write-Host "  Installo dipendenze Local Signer..."
    & $pyExe -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf reportlab

function Test-LocalSignerOnline {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        return [bool]$resp.ok
    }} catch {{
        return $false
    }}
}}

function Stop-LocalSignerProcesses {{
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {{
            $_.Name -in @("python.exe", "pythonw.exe") -and
            $_.CommandLine -and
            $_.CommandLine -like "*$py*"
        }} |
        ForEach-Object {{
            try {{
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            }} catch {{
            }}
        }}
}}

Write-Host "  Preparo l'avvio contestuale da IUSENTRA..."
$cmd = @'
@echo off
setlocal
set "DIR=%~dp0"
set "PYW=%DIR%.venv\\Scripts\\pythonw.exe"
set "PY=%DIR%local_signer.py"
set "TARGET=%DIR%local_signer.py"
set "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=__ALLOWED_ORIGINS__"
set "IUSENTRA_LOCAL_SIGNER_UPDATE_URL=__UPDATE_INSTALLER_URL__"
set "FORCE_RESTART=0"
set "SILENT_MODE=0"
set "UPDATE_MODE=0"

if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
if /I "%~1"=="--update" set "UPDATE_MODE=1"
echo %~1 | find /I "iusentra-local-signer://restart" >nul 2>&1 && set "FORCE_RESTART=1"
echo %~1 | find /I "iusentra-local-signer://update" >nul 2>&1 && set "UPDATE_MODE=1"

if "%UPDATE_MODE%"=="1" goto :update

if "%FORCE_RESTART%"=="0" (
powershell -NoProfile -WindowStyle Hidden -Command "try {{ $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) {{ exit 0 }} }} catch {{}}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online
)

powershell -NoProfile -WindowStyle Hidden -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object {{ $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target }} | ForEach-Object {{ try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {{ try {{ Stop-Process -Id $_ -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath $env:PYW -ArgumentList @($env:PY)"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0

:update
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$ErrorActionPreference='Stop'; $url=$env:IUSENTRA_LOCAL_SIGNER_UPDATE_URL; if (-not $url.StartsWith('https://app.iusentra.it/')) {{ exit 2 }}; $target=Join-Path $env:TEMP ('SetupLocalSigner-' + [Guid]::NewGuid().ToString('N') + '.exe'); Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $target; Start-Process -WindowStyle Hidden -FilePath $target -ArgumentList @('/Q')"
exit /b %ERRORLEVEL%
'@
$cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
$cmd = $cmd.Replace('__UPDATE_INSTALLER_URL__', $updateInstallerUrl)
Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII
$vbs = @"
Set shell = CreateObject("WScript.Shell")
Dim extra
extra = " --background"
If WScript.Arguments.Count > 0 Then
  If InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://update") > 0 Then
    extra = " --update"
  ElseIf InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://restart") > 0 Then
    extra = extra & " --force"
  End If
End If
shell.Run Chr(34) & "$starterCmd" & Chr(34) & extra, 0, False
"@
Set-Content -Path $starterVbs -Value $vbs -Encoding ASCII

Write-Host "  Registro il protocollo locale iusentra-local-signer://..."
$protocolRoot = "HKCU:\\Software\\Classes\\iusentra-local-signer"
$commandKey = Join-Path $protocolRoot "shell\\open\\command"
$wscriptExe = Join-Path $env:SystemRoot "System32\\wscript.exe"
$command = "`"$wscriptExe`" `"$starterVbs`" `"%1`""
New-Item -Path $commandKey -Force | Out-Null
Set-Item -Path $protocolRoot -Value "URL:IUSENTRA Local Signer Protocol"
New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
Set-Item -Path $commandKey -Value $command

function Register-LocalSignerStartupShortcut {{
    $startupDir = [Environment]::GetFolderPath("Startup")
    if (-not $startupDir) {{
        return $false
    }}
    New-Item -ItemType Directory -Force -Path $startupDir | Out-Null
    $shortcutPath = Join-Path $startupDir "IUSENTRA Local Signer.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wscriptExe
    $shortcut.Arguments = "`"$starterVbs`""
    $shortcut.WorkingDirectory = $dir
    $shortcut.WindowStyle = 7
    $shortcut.Description = "IUSENTRA Local Signer - avvio automatico al login"
    $shortcut.Save()
    return $true
}}

Write-Host "  Registro l'avvio automatico permanente..."
$taskName = "IUSENTRA Local Signer"
$cmdExe   = Join-Path $env:SystemRoot "System32\\cmd.exe"
$action   = New-ScheduledTaskAction -Execute $cmdExe -Argument "/c `"$starterCmd`" --background"
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit 0 `
    -RestartCount 3 `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$autostartOk = $false
try {{
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "IUSENTRA Local Signer - firma documenti con smart card e token CNS/CIE" `
        -Force | Out-Null
    $autostartOk = $true
}} catch {{
    Write-Host "  AVVISO: Task Scheduler non registrato, uso fallback Startup." -ForegroundColor Yellow
}}
try {{
    if (Register-LocalSignerStartupShortcut) {{
        $autostartOk = $true
    }}
}} catch {{
    Write-Host "  AVVISO: fallback Startup non registrato." -ForegroundColor Yellow
}}
if (-not $autostartOk) {{
    throw "Impossibile registrare l'avvio automatico permanente del Local Signer."
}}

Write-Host "  Avvio Local Signer..."
Stop-LocalSignerProcesses
Start-Sleep -Milliseconds 500
Start-Process -FilePath $starterCmd -ArgumentList "--background" -WindowStyle Hidden

Write-Host "  Attendo che il servizio risponda su 127.0.0.1:27272..."
$online = $false
for ($i = 0; $i -lt 15; $i++) {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        if ($resp.ok) {{
            $online = $true
            break
        }}
    }} catch {{
    }}
    Start-Sleep -Seconds 1
}}

Write-Host ""
if ($online) {{
    Write-Host "Installazione completata! Local Signer v$version pronto." -ForegroundColor Green
    Write-Host "  Il Local Signer e' attivo su http://127.0.0.1:27272"
    Write-Host "  Si avviera' automaticamente ad ogni accesso Windows."
    Write-Host "  Da ora IUSENTRA puo' avviarlo automaticamente quando clicchi Cerca."
}} else {{
    Write-Host "Installazione completata con avviso." -ForegroundColor Yellow
    Write-Host "  Il servizio non ha ancora risposto su http://127.0.0.1:27272"
    Write-Host "  Tornare su IUSENTRA e usare 'Avvia Local Signer' oppure rieseguire l installer."
}}
Write-Host ""
Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
Read-Host "Premere Invio per chiudere"
"""

    def _render_local_signer_macos_command(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/bin/bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="$HOME/Library/Application Support/IUSENTRA/LocalSigner"
DATA_DIR="$DIR/data"
MOD_DIR="$DIR/local_signer_mod"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.iusentra.local-signer.plist"

echo "IUSENTRA Local Signer v$VERSION - Installazione macOS"

mkdir -p "$DIR" "$DATA_DIR" "$MOD_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici-pst-pubblici" -o "$DATA_DIR/uffici_pst_pubblici.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/__init__.py" -o "$MOD_DIR/__init__.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_cache.py" -o "$MOD_DIR/ai_cache.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" -o "$MOD_DIR/ai_handlers.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/pec_bridge.py" -o "$MOD_DIR/pec_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/security.py" -o "$MOD_DIR/security.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/server_bootstrap.py" -o "$MOD_DIR/server_bootstrap.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/support_agent.py" -o "$MOD_DIR/support_agent.py"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf reportlab

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>it.iusentra.local-signer</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DIR/local_signer.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key>
    <string>$ALLOWED_ORIGINS</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/it.iusentra.local-signer"

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://app.iusentra.it/impostazioni?tab=firma"
echo "Tornare su IUSENTRA e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _render_local_signer_linux_sh(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/usr/bin/env bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/iusentra/local-signer"
DATA_DIR="$DIR/data"
MOD_DIR="$DIR/local_signer_mod"
VENV="$DIR/.venv"
PY="$VENV/bin/python"
SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
SERVICE="$SERVICE_DIR/iusentra-local-signer.service"

echo "IUSENTRA Local Signer v$VERSION - Installazione Linux"

mkdir -p "$DIR" "$DATA_DIR" "$MOD_DIR" "$SERVICE_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima con il gestore pacchetti della distribuzione."
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici-pst-pubblici" -o "$DATA_DIR/uffici_pst_pubblici.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/__init__.py" -o "$MOD_DIR/__init__.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_cache.py" -o "$MOD_DIR/ai_cache.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" -o "$MOD_DIR/ai_handlers.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/pec_bridge.py" -o "$MOD_DIR/pec_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/security.py" -o "$MOD_DIR/security.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/server_bootstrap.py" -o "$MOD_DIR/server_bootstrap.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/support_agent.py" -o "$MOD_DIR/support_agent.py"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf reportlab

cat > "$SERVICE" <<EOF
[Unit]
Description=IUSENTRA Local Signer
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
Environment=PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=$ALLOWED_ORIGINS
ExecStart=$PY $DIR/local_signer.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now iusentra-local-signer.service

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://app.iusentra.it/impostazioni?tab=firma"
echo "Tornare su IUSENTRA e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _pdp_penale_workspace_url_for_fascicolo_early(id_fasc: str) -> str:
        id_fasc = str(id_fasc or "").strip()
        if not id_fasc:
            return ""
        try:
            cases = get_pdp_penale().list_cases_for_practice(id_fasc)
        except Exception:
            cases = []
        active_case = next((row for row in cases if str(row.get("id") or "").strip()), None)
        if active_case:
            return url_for(
                "pdp_penale_workspace",
                id_fasc=id_fasc,
                case_id=str(active_case["id"]),
            )
        return url_for("pdp_penale_workspace", id_fasc=id_fasc)

    return {
        "polis_auth_mode": _polis_auth_mode,
        "polis_demo_mode": _polis_demo_mode,
        "portale_demo_mode": _portale_demo_mode,
        "portale_browser_channel_required": _portale_browser_channel_required,
        "polis_cert_preferences": _polis_cert_preferences,
        "portale_local_channel_enabled": _portale_local_channel_enabled,
        "portale_browser_guided_message": _portale_browser_guided_message,
        "is_portale_dns_error": _is_portale_dns_error,
        "codice_fiscale_avvocato_portale": _codice_fiscale_avvocato_portale,
        "spec_portale_acquisizione": _spec_portale_acquisizione,
        "build_access_status_payload": _build_access_status_payload,
        "search_fascicoli_portale_server": _search_fascicoli_portale_server,
        "preview_documenti_portale_server": _preview_documenti_portale_server,
        "build_portale_preview": _build_portale_preview,
        "coerce_import_options": _coerce_import_options,
        "coerce_mapping": _coerce_mapping,
        "analyze_portale_import": _analyze_portale_import,
        "normalize_authorized_portale_payload": _normalize_authorized_portale_payload,
        "importa_o_collega_fascicolo_portale": _importa_o_collega_fascicolo_portale,
        "importa_file_assistiti_portale": _importa_file_assistiti_portale,
        "portal_assistant_start": _portal_assistant_start,
        "portal_assistant_open": _portal_assistant_open,
        "portal_assistant_watch_downloads": _portal_assistant_watch_downloads,
        "portal_assistant_status": _portal_assistant_status,
        "portal_assistant_collect": _portal_assistant_collect,
        "portal_assistant_close": _portal_assistant_close,
        "deposito_precheck_assistito": _deposito_precheck_assistito,
        "deposito_prepara_assistito": _deposito_prepara_assistito,
        "deposito_assistant_start": _deposito_assistant_start,
        "deposito_importa_ricevute_assistito": _deposito_importa_ricevute_assistito,
        "deposito_finalizza_assistito": _deposito_finalizza_assistito,
        "backfill_telematico_from_existing_fascicoli": _backfill_telematico_from_existing_fascicoli,
        "telematico_dashboard_warning_message": _telematico_dashboard_warning_message,
        "local_signer_python_name": _local_signer_python_name,
        "local_ai_bridge_source_path": _local_ai_bridge_source_path,
        "local_ai_bridge_python_name": _local_ai_bridge_python_name,
        "local_ai_lex_context_source_path": _local_ai_lex_context_source_path,
        "local_ai_lex_context_python_name": _local_ai_lex_context_python_name,
        "local_signer_visible_signature_source_path": _local_signer_visible_signature_source_path,
        "local_signer_visible_signature_python_name": _local_signer_visible_signature_python_name,
        "local_signer_uffici_path": _local_signer_uffici_path,
        "local_signer_uffici_pst_pubblici_path": _local_signer_uffici_pst_pubblici_path,
        "local_signer_windows_cmd_path": _local_signer_windows_cmd_path,
        "local_signer_windows_cmd_name": _local_signer_windows_cmd_name,
        "local_signer_windows_exe_path": _local_signer_windows_exe_path,
        "local_signer_windows_exe_alias_path": _local_signer_windows_exe_alias_path,
        "local_signer_windows_exe_name": _local_signer_windows_exe_name,
        "local_signer_windows_offline_ps1_path": _local_signer_windows_offline_ps1_path,
        "local_signer_windows_offline_ps1_name": _local_signer_windows_offline_ps1_name,
        "render_local_signer_windows_ps1": _render_local_signer_windows_ps1,
        "local_signer_windows_ps1_name": _local_signer_windows_ps1_name,
        "local_signer_macos_installer_path": _local_signer_macos_installer_path,
        "local_signer_macos_name": _local_signer_macos_name,
        "render_local_signer_macos_command": _render_local_signer_macos_command,
        "local_signer_linux_installer_path": _local_signer_linux_installer_path,
        "local_signer_linux_name": _local_signer_linux_name,
        "render_local_signer_linux_sh": _render_local_signer_linux_sh,
        "pdp_penale_workspace_url_for_fascicolo_early": _pdp_penale_workspace_url_for_fascicolo_early,
        "serialize_portale_search_item": _serialize_portale_search_item,
        "find_exact_fascicolo_locale_portale": _find_exact_fascicolo_locale_portale,
        "sync_existing_fascicolo_from_portale": _sync_existing_fascicolo_from_portale,
        "register_direct_portale_import_sync": _register_direct_portale_import_sync,
    }
