"""Endpoint ponte per la migrazione React progressiva.

Questi endpoint restano sottili: espongono dati normalizzati alla shell React
riusando i repository e i servizi esistenti, senza creare una seconda source of
truth frontend.
"""

from __future__ import annotations


import base64
import mimetypes
from pct.formatting import format_euro_it
import hashlib
import io
import ipaddress
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, quote, quote_plus, unquote, unquote_plus, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import certifi
import requests
from flask import Blueprint, Response, current_app, g, jsonify, request, send_file, session, url_for
from werkzeug.exceptions import HTTPException

from pct import __version__ as APP_VERSION
from pct.applicazioni_runtime import TOOL_SCHEMAS, build_tool_result
from pct.auth import RuoloUtente, totp_uri
from pct.clienti import Indirizzo, Recapiti, TipoCliente
from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail
from pct.fatturazione import StatoParcella
from pct.fascicolo_document_catalog import classify_fascicolo_document
from pct.deposito_datiatto_fields import normalize_deposito_professionista_role
from pct.deposito_telematico_catalogo import build_deposit_catalog_payload, resolve_deposit_type_payload
from pct.fascicoli import TipoDocumento
from pct.messaggi import CanaleMsggio, ConfigMessaggistica, GestioneMessaggi, Messaggio, StatoMessaggio
from pct.notifiche_legali import (
    LEGAL_RECIPIENT_ROLES,
    LEGAL_NOTIFICATION_SEND_OPERATION,
    PUBLIC_PEC_REGISTERS,
    build_public_register_confirmation_evidence,
    build_attestazione_conformita_payload,
    build_client_communication,
    generate_attestazione_conformita_pdf_bytes,
    generate_relata_pdf_bytes,
    is_plausible_pec_address,
    normalise_public_register,
    normalise_custom_template,
    prepare_pst_failed_notification_workflow,
    preview_legal_relata,
    validate_custom_template_body,
    template_preview_text,
    validate_non_pec_notification_tracking,
    validate_legal_notification,
    validate_unep_notification_request,
)
from pct.preventivi import StatoPreventivo
from pct.pec_pipeline import extract_message_parts, message_from_bytes
from pct.practice_engine.deposit_orchestrator import prepare_deposit, send_deposit
from pct.practice_engine.deposit_readiness import run_predeposit_check
from pct.practice_engine.evaluator import build_regia_payload, ensure_evidence_pack, ensure_profile_for_fascicolo
from pct.practice_engine.profiles import get_profile
from pct.practice_engine.receipt_tracker import import_receipt
from pct.practice_engine.validators import ValidationContext, validate_slot
from pct.pratiche_collegate_catalog import (
    codice_oggetto_pst_entry,
    looks_like_codice_oggetto_pst,
    resolve_codice_oggetto_pst_payload,
)
from pct.runtime_env import is_managed_cloud_runtime
from pct.scadenziario import PrioritaTermine, TipoTermine
from pct.soggetti import (
    RuoloSoggetto,
    TipoSoggetto,
    normalizza_identificativo_anagrafico,
    normalizza_nome_anagrafico,
)
from pct.strumenti_legali import GestioneStrumentiLegali
from pct.termini_processuali import (
    DeadlinePracticeRepository,
    LEGAL_SOURCES,
    calculate_and_audit,
)
from pct.territorio_italia import get_comune, search_comuni
from pct.uffici_competenti import ricerca_uffici_competenti
from pct.uffici_giudiziari import risolvi_ufficio
from pct.timesheet import StatoTimesheet
from pct.workspace_intelligente import WorkspaceIntelligenteService
from pct.workflow_commerciale import apri_fascicolo_automatico
from web.services.react_agenda_bridge import build_react_agenda_payload
from web.services.react_admin_database_bridge import (
    build_react_admin_database_error_payload,
    build_react_admin_database_payload,
)
from web.services.react_audit_bridge import (
    build_react_audit_detail_payload,
    build_react_audit_error_payload,
    build_react_audit_payload,
)
from web.services.react_clienti_bridge import (
    build_react_cliente_cartella_payload,
    build_react_cliente_modifica_payload,
    build_react_clienti_nuovo_payload,
    build_react_clienti_payload,
    build_react_soggetto_modifica_payload,
)
from web.services.client_document_reader import ClientDocumentReaderError, read_client_document_upload
from web.services.react_condivisioni_bridge import build_react_condivisioni_payload
from web.services.mailbox_sync_runtime import sync_mailboxes_for_current_context
from web.bootstrap.fascicoli_document_helpers import (
    pdf_mobile_preview_html,
    pdf_page_count,
    preview_error_html,
    preview_unavailable_html,
    render_pdf_page_png,
)
from web.services.react_dashboard_cache import (
    DASHBOARD_CACHE_TTL_SECONDS,
    clear_dashboard_payload_cache,
    get_dashboard_payload_cached,
)
from web.services.react_dashboard_health import (
    etichette_sorgenti,
    messaggio_sorgenti_degradate,
    segnala_sorgente_non_disponibile,
    traccia_sorgenti_panoramica,
)
from web.services.react_dashboard_time import adesso_rome, oggi_rome
from web.services.react_regia_worklist import build_regia_worklist
from web.services.reginde_cache_search import (
    default_reginde_cache_db_path,
    default_registro_ppaa_cache_db_path,
    search_reginde_cache,
    search_registro_ppaa_cache,
)
from web.services.react_payload_cache import ReactPayloadTTLCache
from web.services.security_redaction import redacted_json_response
from web.services.signed_attachment_preview import attachment_mimetype, build_attachment_preview_payload
from web.services.react_document_editor_bridge import build_react_document_editor_payload
from web.services.react_document_archive_bridge import build_react_document_archive_payload
from web.services.react_email_bridge import build_react_email_detail_payload, build_react_email_payload
from web.services.react_fascicoli_bridge import (
    build_react_archivio_payload,
    build_react_fascicoli_export_payload,
    build_react_fascicoli_payload,
    build_react_fascicolo_detail_payload,
    build_react_fascicolo_form_payload,
    clear_react_fascicoli_base_cache,
    generate_react_fascicolo_proforma,
    run_react_fascicoli_economic_presidio,
    update_react_fascicolo_deposit_value,
    update_react_fascicolo_payment,
    update_react_fascicolo_status,
)
from web.services.react_messaggi_bridge import build_react_messaggi_nuovo_payload, build_react_messaggi_payload
from web.services.react_notifiche_legali_bridge import (
    build_react_notifiche_legali_payload,
    build_react_notifiche_legali_practice_payload,
    build_react_notifiche_legali_practice_documents_payload,
    sanitize_react_notifiche_legali_payload,
)
from web.services.local_pec_runtime import LOCAL_SIGNER_BASE_URL
from web.services.react_practice_engine_bridge import build_react_practice_engine_payload
from web.services.react_privacy_bridge import build_react_privacy_registro_payload
from web.services.react_scadenziario_bridge import (
    build_react_scadenziario_nuova_payload,
    build_react_scadenziario_payload,
    calculator_templates_for_guide,
    dedupe_calculator_templates,
)
from web.services.pdf_deadline_import import import_pdf_deadlines, preview_pdf_deadlines
from web.services.react_soggetti_bridge import build_react_soggetti_payload
from web.services.react_statistiche_bridge import (
    build_react_statistiche_error_payload,
    build_react_statistiche_payload,
)
from web.services.react_utenti_bridge import (
    build_react_utenti_error_payload,
    build_react_utenti_payload,
    reset_react_utente_password,
    update_react_utente_profile,
    update_react_utente_role,
    update_react_utente_status,
)
from web.services.react_profili_bridge import (
    build_react_profili_error_payload,
    build_react_profili_payload,
    update_react_profili_payload,
)
from web.services.react_backup_bridge import (
    build_react_backup_error_payload,
    build_react_backup_payload,
    create_react_backup,
    verify_react_backup_integrity,
)
from web.services.react_sito_studio_bridge import (
    build_react_sito_articolo_modifica_payload,
    build_react_sito_contatti_payload,
    build_react_sito_studio_error_payload,
    build_react_sito_studio_payload,
    link_react_sito_contatto,
    update_react_sito_articolo,
    update_react_sito_booking_status,
)
from web.services.react_sito_studio_builder_bridge import (
    apply_react_builder_template,
    build_react_sito_studio_builder_payload,
    builder_error_payload,
    create_react_builder_page,
    delete_react_builder_page,
    delete_react_builder_asset,
    duplicate_react_builder_page,
    generate_react_builder_site,
    publish_react_builder_blocks,
    restore_react_builder_revision,
    save_react_builder_blocks,
    save_react_builder_design,
    update_react_builder_page,
    update_react_builder_site,
    upload_react_builder_asset,
    validate_react_builder,
)
from web.services.react_sito_studio_ai_bridge import (
    build_react_sito_studio_ai_error_payload,
    build_react_sito_studio_ai_payload,
    create_react_sito_studio_ai_draft,
    generate_react_sito_studio_ai_article,
    generate_react_sito_studio_ai_image,
    publish_react_sito_studio_ai_article,
)
from web.services.react_studio_bridge import build_react_studio_error_payload, build_react_studio_payload
from web.services.react_impostazioni_bridge import (
    apply_react_impostazioni_fatturazione_to_proformas,
    bootstrap_react_impostazioni_ai,
    build_react_impostazioni_ai_status,
    build_react_impostazioni_error_payload,
    build_react_impostazioni_payload,
    persist_react_deposito_telematico_role,
    run_react_impostazioni_test,
    update_react_impostazioni_firma_certificato,
    update_react_impostazioni_section,
)
from web.services.lex_dataset_training_status import build_lex_dataset_training_status
from web.services.lex_dataset_review_queue import (
    load_lex_dataset_review_queue,
    update_lex_dataset_review_item,
)
from web.services.react_impostazioni_notifications import (
    prepare_notifica_link,
    send_notifica,
    send_promemoria_domani,
)
from web.services.react_impostazioni_calendar import (
    calendar_oauth_callback,
    calendar_oauth_connect,
    connect_apple_calendar_account,
    connect_demo_calendar_account,
    connect_webcal_calendar_account,
    create_calendar_profile,
    delete_calendar_profile,
    disconnect_calendar_account,
    list_calendar_accounts_payload,
    list_calendar_conflicts_payload,
    regenerate_calendar_token,
    resolve_calendar_conflict,
    sync_calendar_account,
    sync_calendar_profile,
    toggle_calendar_profile,
    toggle_linked_calendar,
)
from web.services.react_amministrazione_bridge import (
    build_react_amministrazione_error_payload,
    build_react_amministrazione_payload,
)
from web.services.react_fatturazione_bridge import (
    build_fatturazione_runtime_config,
    build_react_fatturazione_detail_payload,
    build_react_fatturazione_error_payload,
    build_react_fatturazione_payload,
    cancel_react_fatturazione_document,
    create_react_fattura,
    mark_react_fatturazione_paid,
    update_react_fatturazione_numbering,
    update_react_fatturazione_status,
)
from web.services.react_fatturazione_archive_actions import (
    confirm_react_fatturazione_commercialista_pec,
    confirm_react_fatturazione_sdi_sent,
    confirm_react_fatturazione_xml_signed,
    prepare_react_fatturazione_commercialista,
    prepare_react_fatturazione_sdi_pec,
    prepare_react_fatturazione_xml_signature,
    record_react_fatturazione_sdi_outcome,
    send_react_fatturazione_commercialista_email,
    update_react_fatturazione_detail,
)
from web.services.react_compensi_forensi_bridge import (
    build_react_compensi_forensi_error_payload,
    build_react_compensi_forensi_payload,
    calculate_react_compensi_forensi,
)
from web.services.react_tariffario_bridge import (
    build_react_tariffario_detail_payload,
    build_react_tariffario_error_payload,
    build_react_tariffario_payload,
    calculate_react_tariffario,
)
from web.services.react_preventivi_bridge import (
    build_react_conferimento_detail_payload,
    build_react_preventivo_detail_payload,
    build_react_preventivi_error_payload,
    build_react_preventivi_payload,
    create_react_conferimento,
    create_react_preventivo,
    update_react_conferimento_status,
    update_react_preventivo_status,
)
from web.services.react_preventivo_wizard_bridge import (
    WizardPayloadForm,
    build_react_preventivo_wizard_calculation_payload,
    build_react_preventivo_wizard_error_payload,
    build_react_preventivo_wizard_payload,
    default_clause_payload,
    detail_url_for_preventivo,
)
from web.services.react_template_atti_bridge import (
    build_react_template_atti_error_payload,
    build_react_template_atti_payload,
)
from web.services.react_redazione_atti_bridge import (
    build_react_redazione_atti_error_payload,
    build_react_redazione_atti_payload,
    produce_react_redazione_atti,
)
from web.services.react_giurisprudenza_bridge import (
    build_react_giurisprudenza_error_payload,
    build_react_giurisprudenza_new_payload,
    build_react_giurisprudenza_payload,
    create_react_giurisprudenza_record,
)
from web.services.react_legal_intelligence_bridge import (
    build_react_legal_intelligence_error_payload,
    build_react_legal_intelligence_payload,
)
from web.services.react_workflow_agents_bridge import (
    WORKFLOW_AGENT_PERMISSIONS,
    approve_workflow_agent_run,
    build_workflow_agents_payload,
    get_workflow_agent_run,
    list_workflow_agent_approvals,
    preview_workflow_agent,
    reject_workflow_agent_run,
    workflow_agent_error_payload,
    workflow_agent_metrics_payload,
)
from web.services.react_incassi_pagamenti_bridge import (
    build_or_get_react_payment_link,
    build_react_incassi_pagamenti_error_payload,
    build_react_incassi_pagamenti_payload,
    link_react_pagamento_invoice,
    register_react_incasso,
    update_react_pagamento_status,
)
from web.services.react_studio_module_bridge import build_react_studio_module_payload
from web.services.react_telematico_bridge import (
    build_react_telematico_payload,
    build_react_telematico_surface_payload,
    build_react_tribunali_payload,
)
from web.services.quickorganizer_import import (
    QuickOrganizerImportError,
    auto_prepare_status,
    begin_chunked_upload,
    begin_auto_prepare_session,
    cleanup_upload_temp,
    complete_auto_prepare_upload,
    complete_chunked_upload,
    import_quickorganizer_package,
    load_staged_package,
    max_chunked_upload_bytes,
    receive_auto_prepare_chunk,
    receive_chunked_upload,
    save_upload_to_temp,
    stage_referenced_package,
    stage_uploaded_package,
    staging_root_for_anchor,
    start_auto_prepare_upload,
    update_auto_prepare_status,
)
from web.services.react_timesheet_bridge import build_react_timesheet_payload
from web.services.react_wizard_pro_bridge import (
    build_react_wizard_pro_complete_payload,
    build_react_wizard_pro_payload,
    build_react_wizard_pro_step_payload,
)
from web.services.studio_site_runtime import site_admin_identity_or_403
from web.services.feature_flags import feature_disabled_response, feature_flags_payload, is_feature_enabled
from web.services.notification_presidia_runtime import (
    apply_legal_notification_presidia_effective_flags,
)
from web.services.tenant_paths import TenantDataPathError, tenant_data_path
from web.services.tenant_api_auth import api_key_valid_for_request
from web.services.storage_runtime import get_request_storage_runtime, get_request_studio_db
from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from pct.tenant import DbMode
from web.helpers import (
    get_agenda,
    get_calendar_sync,
    get_clienti,
    get_fascicoli,
    get_fatturazione,
    get_legal_intelligence,
    get_legal_update_pipeline,
    get_normative_tables,
    get_pagamenti,
    get_practice_engine,
    get_giurisprudenza,
    get_preventivi,
    get_preventivi_readonly,
    get_scadenziario,
    get_soggetti,
    get_timesheet,
    get_utenti,
    studio_nome,
)

api_v1_react = Blueprint("api_v1_react", __name__, url_prefix="/api/v1/ui")

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
PST_PAGOPA_HOST = "servizipst.giustizia.it"
PST_PAGOPA_ROOT = f"https://{PST_PAGOPA_HOST}/PST/"
PST_PAGOPA_PROXY_PREFIX = "/api/v1/ui/pst/pagopa-proxy/"
PST_PAGOPA_TIMEOUT_SECONDS = 25
PST_PAGOPA_TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/css", "javascript", "application/xml", "text/xml")
PST_PAGOPA_EXTRA_CA_PATH = Path(__file__).resolve().parents[1] / "certs" / "TITrustTechnologiesOVCA.pem"
PST_PAGOPA_ALLOWED_PATH_PREFIXES = ("it/pagopa_", "resources/", "dwr/")
PST_PAGOPA_ALLOWED_PATH_RE = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@%/-]{1,512}$")
PST_PAGOPA_PROXY_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "worker-src 'self' blob:; "
    "frame-src 'self' blob:; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_PST_PAGOPA_ATTR_RE = re.compile(
    r"(?P<prefix>\b(?:href|src|action)\s*=\s*)"
    r"(?:(?P<quote>['\"])(?P<quoted>[^'\"]+)(?P=quote)|(?P<unquoted>[^\s>]+))",
    re.IGNORECASE,
)
_PST_PAGOPA_CSS_URL_RE = re.compile(r"url\((?P<quote>['\"]?)(?P<url>[^)'\"\s][^)'\"]*?)(?P=quote)\)")


@api_v1_react.errorhandler(TenantDataPathError)
def _tenant_data_path_error(error: TenantDataPathError):
    return jsonify({"ok": False, "errore": "Contesto studio non disponibile.", "codice": "tenant_context_required"}), 409


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify(
            {
                "ok": False,
                "error": "unauthorized",
                "message": "Autenticazione richiesta.",
                "code": "unauthorized",
                "errore": "Autenticazione richiesta.",
                "codice": 401,
            }
        ), 401

    return wrapper


def _pst_pagopa_fascicolo_id() -> str:
    raw = str(request.args.get("iusentra_fascicolo") or session.get("pst_pagopa_fascicolo_id") or "").strip()
    if not raw:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", raw):
        return ""
    session["pst_pagopa_fascicolo_id"] = raw
    session.modified = True
    return raw


def _pst_pagopa_query_pairs() -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in request.args.items(multi=True)
        if not str(key).startswith("iusentra_")
    ]


@lru_cache(maxsize=1)
def _pst_pagopa_verify_bundle() -> str:
    """CA bundle per il PST: certifi più intermedio TI Trust mancante nella chain ministeriale."""
    base_path = Path(certifi.where())
    extra_path = PST_PAGOPA_EXTRA_CA_PATH
    if not extra_path.exists():
        return str(base_path)
    base = base_path.read_bytes()
    extra = extra_path.read_bytes()
    digest = hashlib.sha256(extra).hexdigest()[:16]
    bundle_path = Path(tempfile.gettempdir()) / f"iusentra-pst-pagopa-ca-{digest}.pem"
    if not bundle_path.exists():
        bundle_path.write_bytes(base + b"\n" + extra)
    return str(bundle_path)


def _pst_pagopa_target_url(pst_path: str = "") -> str:
    cleaned = _pst_pagopa_safe_path(pst_path)
    if not cleaned:
        return ""
    candidate = urljoin(PST_PAGOPA_ROOT, cleaned)
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or parsed.netloc.lower() != PST_PAGOPA_HOST or not parsed.path.startswith("/PST/"):
        return ""
    query = urlencode(_pst_pagopa_query_pairs(), doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def _pst_pagopa_safe_path(pst_path: str = "") -> str:
    cleaned = str(pst_path or "it/pagopa_altripag.wp").strip().replace("\\", "/")
    if cleaned.startswith("PST/"):
        cleaned = cleaned[4:]
    cleaned = cleaned.lstrip("/")
    parts = [part for part in cleaned.split("/") if part]
    if (
        "://" in cleaned
        or cleaned.startswith("//")
        or not PST_PAGOPA_ALLOWED_PATH_RE.fullmatch(cleaned)
        or any(part == ".." for part in parts)
        or not cleaned.startswith(PST_PAGOPA_ALLOWED_PATH_PREFIXES)
    ):
        return ""
    return "/".join(parts)


def _pst_pagopa_inline_text_response(
    response_body: bytes,
    *,
    status_code: int,
    response_headers: dict[str, str],
    content_type: str,
) -> Response:
    lower_content_type = content_type.lower()
    if "text/html" in lower_content_type or "application/xhtml+xml" in lower_content_type:
        safe_content_type = "text/html; charset=utf-8"
    elif "css" in lower_content_type:
        safe_content_type = "text/css; charset=utf-8"
    elif "javascript" in lower_content_type:
        safe_content_type = "application/javascript"
    elif "xml" in lower_content_type:
        safe_content_type = "application/xml; charset=utf-8"
    else:
        safe_content_type = "text/plain; charset=utf-8"
    suffix = ".html" if safe_content_type.startswith("text/html") else ".txt"
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix="iusentra-pagopa-",
        suffix=suffix,
        delete=False,
    ) as temp_file:
        temp_file.write(response_body)
        temp_path = Path(temp_file.name)
    response = send_file(
        temp_path,
        mimetype=safe_content_type.split(";", 1)[0],
        download_name="pagopa-pst-inline.txt",
        as_attachment=False,
        max_age=0,
    )
    response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
    response.status_code = status_code
    response.headers.update(response_headers)
    response.headers["Content-Type"] = safe_content_type
    return response


def _pst_pagopa_strip_iusentra_query(raw_query: str) -> str:
    pairs = [
        (key, value)
        for key, value in parse_qsl(raw_query, keep_blank_values=True)
        if not str(key).startswith("iusentra_")
    ]
    return urlencode(pairs, doseq=True)


def _pst_pagopa_upstream_referer(target_url: str) -> str:
    referrer = str(request.referrer or "").strip()
    if referrer:
        parsed = urlparse(referrer)
        same_iusentra_host = not parsed.netloc or parsed.netloc == request.host
        if same_iusentra_host and parsed.path.startswith(PST_PAGOPA_PROXY_PREFIX):
            proxy_path = parsed.path.removeprefix(PST_PAGOPA_PROXY_PREFIX).lstrip("/")
            candidate = urljoin(PST_PAGOPA_ROOT, proxy_path)
            candidate_parsed = urlparse(candidate)
            if (
                candidate_parsed.scheme == "https"
                and candidate_parsed.netloc.lower() == PST_PAGOPA_HOST
                and candidate_parsed.path.startswith("/PST/")
            ):
                return urlunparse(
                    (
                        candidate_parsed.scheme,
                        candidate_parsed.netloc,
                        candidate_parsed.path,
                        "",
                        _pst_pagopa_strip_iusentra_query(parsed.query),
                        "",
                    )
                )
        if parsed.scheme == "https" and parsed.netloc.lower() == PST_PAGOPA_HOST and parsed.path.startswith("/PST/"):
            return urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, "", _pst_pagopa_strip_iusentra_query(parsed.query), "")
            )
    parsed_target = urlparse(target_url)
    if "/dwr/" in parsed_target.path:
        return urljoin(PST_PAGOPA_ROOT, "it/pagopa_nuovarich.wp")
    return target_url


def _pst_pagopa_local_page_to_upstream(raw_page: str) -> str:
    value = str(raw_page or "").strip()
    if not value:
        return value
    parsed = urlparse(value)
    path = parsed.path or value
    if path.startswith(PST_PAGOPA_PROXY_PREFIX):
        proxy_path = path.removeprefix(PST_PAGOPA_PROXY_PREFIX).lstrip("/")
        upstream_path = f"/PST/{proxy_path}"
    elif path.startswith("/PST/"):
        upstream_path = path
    else:
        return value
    query = _pst_pagopa_strip_iusentra_query(parsed.query)
    return urlunparse(("", "", upstream_path, "", query, ""))


def _pst_pagopa_rewrite_dwr_body(body: bytes, cookies: Mapping[str, str] | None = None) -> bytes:
    if not body:
        return body
    pst_session_id = str((cookies or {}).get("JSESSIONID") or "").strip()
    text = body.decode("utf-8", errors="replace")
    lines: list[str] = []
    changed = False
    for line in text.splitlines():
        if line.startswith("page="):
            upstream_page = _pst_pagopa_local_page_to_upstream(unquote_plus(line[5:]))
            if upstream_page:
                encoded_page = quote_plus(upstream_page)
                if encoded_page != line[5:]:
                    line = f"page={encoded_page}"
                    changed = True
        elif pst_session_id and line == "httpSessionId=":
            line = f"httpSessionId={pst_session_id}"
            changed = True
        lines.append(line)
    if not changed:
        return body
    suffix = "\n" if text.endswith(("\n", "\r\n")) else ""
    return ("\n".join(lines) + suffix).encode("utf-8")


def _pst_pagopa_rewrite_dwr_javascript(text: str) -> str:
    return re.sub(
        r"(?P<prefix>\._path\s*=\s*)(?P<quote>['\"])/PST/dwr(?P=quote)",
        lambda match: f"{match.group('prefix')}{match.group('quote')}{PST_PAGOPA_PROXY_PREFIX.rstrip('/')}/dwr{match.group('quote')}",
        text,
    )


def _pst_pagopa_proxy_href(raw_url: str, *, base_url: str, fascicolo_id: str) -> str:
    value = str(raw_url or "").strip()
    if not value or value.startswith("#"):
        return value
    if re.match(r"(?i)^(javascript|mailto|tel|data):", value):
        return value
    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return value
    if parsed.netloc.lower() != PST_PAGOPA_HOST or not parsed.path.startswith("/PST/"):
        return absolute
    proxy_path = parsed.path.removeprefix("/PST/").lstrip("/")
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if fascicolo_id and not any(key == "iusentra_fascicolo" for key, _value in query_pairs):
        query_pairs.append(("iusentra_fascicolo", fascicolo_id))
    query = urlencode(query_pairs, doseq=True)
    return f"{PST_PAGOPA_PROXY_PREFIX}{proxy_path}{'?' + query if query else ''}"


def _pst_pagopa_rewrite_text(text: str, *, base_url: str, fascicolo_id: str) -> str:
    def _attr_replace(match: re.Match[str]) -> str:
        quote = match.group("quote") or ""
        raw_url = match.group("quoted") if quote else match.group("unquoted")
        rewritten = _pst_pagopa_proxy_href(raw_url or "", base_url=base_url, fascicolo_id=fascicolo_id)
        return f"{match.group('prefix')}{quote}{rewritten}{quote}"

    def _css_replace(match: re.Match[str]) -> str:
        rewritten = _pst_pagopa_proxy_href(match.group("url"), base_url=base_url, fascicolo_id=fascicolo_id)
        quote = match.group("quote") or ""
        return f"url({quote}{rewritten}{quote})"

    rewritten = _PST_PAGOPA_ATTR_RE.sub(_attr_replace, text)
    rewritten = _PST_PAGOPA_CSS_URL_RE.sub(_css_replace, rewritten)
    rewritten = re.sub(
        r"(?P<quote>['\"])(?P<url>/PST/[^'\"]+)(?P=quote)",
        lambda match: match.group("quote")
        + _pst_pagopa_proxy_href(match.group("url"), base_url=base_url, fascicolo_id=fascicolo_id)
        + match.group("quote"),
        rewritten,
    )
    return rewritten


def _pst_pagopa_runtime_bridge_script(*, base_url: str, fascicolo_id: str) -> str:
    base_json = json.dumps(base_url, ensure_ascii=False)
    fascicolo_json = json.dumps(fascicolo_id, ensure_ascii=False)
    prefix_json = json.dumps(PST_PAGOPA_PROXY_PREFIX, ensure_ascii=False)
    host_json = json.dumps(PST_PAGOPA_HOST, ensure_ascii=False)
    return f"""
<script>
(function(){{
  var baseUrl = {base_json};
  var fascicoloId = {fascicolo_json};
  var proxyPrefix = {prefix_json};
  var pstHost = {host_json};
  function proxiedUrl(raw) {{
    if (!raw || raw.charAt(0) === '#' || /^(javascript|mailto|tel|data):/i.test(raw)) return raw;
    if (raw.indexOf(proxyPrefix) === 0) return raw;
    try {{
      var absolute = new URL(raw, baseUrl);
      if (absolute.hostname !== pstHost || absolute.pathname.indexOf('/PST/') !== 0) return raw;
      var proxyPath = absolute.pathname.replace(/^\\/PST\\/?/, '');
      if (fascicoloId && !absolute.searchParams.has('iusentra_fascicolo')) {{
        absolute.searchParams.append('iusentra_fascicolo', fascicoloId);
      }}
      return proxyPrefix + proxyPath + absolute.search;
    }} catch (error) {{
      return raw;
    }}
  }}
  function rewriteNode(node) {{
    if (!node || !node.getAttribute || !node.setAttribute) return;
    ['href', 'src', 'action'].forEach(function(attr) {{
      var raw = node.getAttribute(attr);
      var next = proxiedUrl(raw);
      if (next && next !== raw) node.setAttribute(attr, next);
    }});
  }}
  function rewriteTree(root) {{
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('[href], [src], [action]').forEach(rewriteNode);
  }}
  document.addEventListener('click', function(event) {{
    var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!link) return;
    var raw = link.getAttribute('href');
    var next = proxiedUrl(raw);
    if (next && next !== raw) {{
      event.preventDefault();
      window.location.href = next;
    }}
  }}, true);
  document.addEventListener('submit', function(event) {{
    rewriteNode(event.target);
  }}, true);
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', function() {{ rewriteTree(document); }});
  }} else {{
    rewriteTree(document);
  }}
  if (window.MutationObserver) {{
    new MutationObserver(function(mutations) {{
      mutations.forEach(function(mutation) {{
        if (mutation.type === 'attributes') {{
          rewriteNode(mutation.target);
          return;
        }}
        mutation.addedNodes.forEach(function(node) {{
          rewriteNode(node);
          rewriteTree(node);
        }});
      }});
    }}).observe(document.documentElement, {{
      attributes: true,
      attributeFilter: ['href', 'src', 'action'],
      childList: true,
      subtree: true
    }});
  }}
}})();
</script>"""


def _pst_pagopa_inject_runtime_bridge(text: str, *, base_url: str, fascicolo_id: str) -> str:
    script = _pst_pagopa_runtime_bridge_script(base_url=base_url, fascicolo_id=fascicolo_id)
    if re.search(r"</body\s*>", text, flags=re.IGNORECASE):
        return re.sub(r"</body\s*>", script + r"\g<0>", text, count=1, flags=re.IGNORECASE)
    return text + script


def _pst_pagopa_filename(response: requests.Response, target_url: str) -> str:
    disposition = str(response.headers.get("Content-Disposition") or "")
    filename = ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, flags=re.IGNORECASE)
    if match:
        filename = unquote(match.group(1).strip().strip('"'))
    if not filename:
        match = re.search(r'filename="?([^";]+)"?', disposition, flags=re.IGNORECASE)
        if match:
            filename = unquote(match.group(1).strip())
    if not filename:
        path_name = Path(urlparse(target_url).path).name
        if path_name.lower().endswith(".pdf"):
            filename = path_name
    if not filename:
        filename = f"ricevuta-pagopa-pst-{datetime.now(ZoneInfo('Europe/Rome')).strftime('%Y%m%d-%H%M%S')}.pdf"
    filename = Path(filename).name
    return filename if filename.lower().endswith(".pdf") else f"{filename}.pdf"


def _pst_pagopa_capture_pdf(fascicolo_id: str, content: bytes, *, filename: str, target_url: str) -> str:
    if not fascicolo_id or not content:
        return ""
    digest = hashlib.sha256(content).hexdigest()
    try:
        gf = _fascicoli_loader()()
        fascicolo = gf.get(fascicolo_id)
        if not fascicolo:
            return ""
        for doc in getattr(fascicolo, "documenti", []) or []:
            if str(getattr(doc, "hash_sha256", "") or "") == digest:
                return str(getattr(doc, "id", "") or "")
        documento = gf.aggiungi_documento(
            fascicolo_id,
            filename,
            TipoDocumento.ALLEGATO,
            content,
            note="Ricevuta PagoPA PST acquisita dal portale ministeriale dentro il fascicolo.",
            tags=["PagoPA", "PST", "ricevuta"],
            caricato_da=_actor_label(),
            fonte_documento="PORTALE_TELEMATICO",
            nome_originale=filename,
            nome_portale=filename,
            classificazione_portale="RICEVUTA_PAGOPA",
            tipo_atto_portale="Ricevuta PagoPA",
            servizio_portale="PST PagoPA",
            id_documento_portale=target_url,
        )
        _audit_event(
            "pst_pagopa.receipt_captured",
            "fascicolo",
            fascicolo_id,
            f"Ricevuta PagoPA PST acquisita: {filename}.",
        )
        return documento.id
    except Exception as exc:
        current_app.logger.warning("Acquisizione ricevuta PagoPA PST non completata: %s", exc)
        return ""


def _puo_leggere_admin_database() -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("utenti.leggi"))


def _puo_leggere_audit() -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("audit.leggi"))


def _puo_leggere_utenti() -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("utenti.leggi"))


@api_v1_react.get("/profilo")
@_richiedi_auth
def profilo_react_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "message": "Sessione utente richiesta."}), 403
    ruolo = getattr(utente, "ruolo", "")
    role_value = getattr(ruolo, "value", str(ruolo or ""))
    temp_secret = str(session.get("totp_temp_secret", "") or "")
    username = str(getattr(utente, "username", "") or "")
    return jsonify(
        {
            "ok": True,
            "user": {
                "id": str(getattr(utente, "id", "") or ""),
                "username": username,
                "email": str(getattr(utente, "email", "") or ""),
                "nome_completo": str(getattr(utente, "nome_completo", "") or ""),
                "ruolo": role_value,
                "ultimo_accesso": str(getattr(utente, "ultimo_accesso", "") or ""),
            },
            "security": {
                "twoFactorEnabled": bool(getattr(utente, "totp_attivato", False)),
                "setupSecret": temp_secret,
                "setupUri": totp_uri(temp_secret, username) if temp_secret and username else "",
            },
            "passwordRequired": bool(getattr(utente, "must_change_password", False)),
        }
    )


def _puo_scrivere_utenti() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("utenti.scrivi"))


def _session_user_can(permission: str) -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)(permission))


def _workflow_agent_user_permissions() -> list[str]:
    if _api_key_valida():
        return list(WORKFLOW_AGENT_PERMISSIONS)
    return [permission for permission in WORKFLOW_AGENT_PERMISSIONS if _session_user_can(permission)]


def _workflow_agent_can_any(*permissions: str) -> bool:
    if _api_key_valida():
        return True
    granted = set(_workflow_agent_user_permissions())
    return any(permission in granted for permission in permissions)


def _workflow_agent_forbidden():
    return jsonify({"ok": False, "code": "forbidden", "message": "Permesso non sufficiente per la Regia Agentica Studio."}), 403


def _puo_leggere_backup() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("backup.leggi"))


def _puo_eseguire_backup() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("backup.esegui"))


def _puo_configurare_impostazioni() -> bool:
    return _api_key_valida() or _session_user_can("admin.configura")


def _puo_importare_studio_telematico() -> bool:
    if _api_key_valida():
        return True
    return (
        _session_user_can("admin.configura")
        or (_session_user_can("fascicoli.scrivi") and _session_user_can("clienti.scrivi"))
    )


def _puo_scrivere_clienti() -> bool:
    return _api_key_valida() or _session_user_can("clienti.scrivi")


def _request_from_loopback() -> bool:
    remote = str(request.remote_addr or "").strip()
    if not remote:
        return False
    try:
        return ipaddress.ip_address(remote).is_loopback
    except ValueError:
        return remote in {"localhost", "127.0.0.1", "::1"}


def _studio_telematico_local_path_enabled() -> bool:
    raw = str(os.getenv("IUSENTRA_STUDIO_TELEMATICO_LOCAL_PATH", "") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if is_managed_cloud_runtime():
        return False
    if raw in {"1", "true", "yes", "on"}:
        return _request_from_loopback()
    return os.name == "nt" and _request_from_loopback()


def _puo_leggere_fatturazione() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("fatturazione.leggi"))


def _puo_scrivere_fatturazione() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("fatturazione.scrivi"))


def _puo_leggere_preventivi() -> bool:
    return _puo_leggere_fatturazione()


def _puo_scrivere_preventivi() -> bool:
    return _puo_scrivere_fatturazione()


def _richiedi_admin_sito_studio_api():
    try:
        site_admin_identity_or_403()
        return None
    except HTTPException as exc:
        description = str(getattr(exc, "description", "") or "Permesso admin.configura richiesto.")
        return jsonify(build_react_sito_studio_error_payload(description)), int(getattr(exc, "code", 403) or 403)


def _studio_avvocato_titolare() -> str:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    config_loader = core_runtime.get("get_config_studio")
    if callable(config_loader):
        try:
            config_manager = config_loader()
            studio = getattr(getattr(config_manager, "config", None), "studio", None)
            avvocato = str(getattr(studio, "avvocato", "") or "").strip()
            if avvocato:
                return avvocato
        except Exception:
            pass
    return str(
        current_app.config.get("STUDIO_AVVOCATO")
        or current_app.config.get("PCT_STUDIO_AVVOCATO")
        or ""
    ).strip()


def _studio_prefill_config() -> dict[str, Any]:
    config = dict(current_app.config)
    avvocato = _studio_avvocato_titolare()
    if avvocato:
        studio = dict(config.get("studio") or {})
        studio["avvocato"] = avvocato
        config["studio"] = studio
        config["STUDIO_AVVOCATO"] = avvocato
        config["PCT_STUDIO_AVVOCATO"] = avvocato
    return config


def _telematico_loader() -> Callable[[], Any]:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    loader = core_runtime.get("get_telematico")
    if callable(loader):
        return loader

    def _missing_telematico() -> Any:
        raise RuntimeError("Runtime telematico non disponibile")

    return _missing_telematico


def _fascicoli_loader() -> Callable[[], Any]:
    loader = _core_runtime_func("get_fascicoli")
    return loader if callable(loader) else get_fascicoli


def _backup_loader() -> Callable[[], Any]:
    loader = _core_runtime_func("get_backup")
    if callable(loader):
        return loader

    def _missing_backup() -> Any:
        raise RuntimeError("Runtime backup non disponibile")

    return _missing_backup


def _template_atti_loader() -> Any:
    from pct.template_atti import GestioneTemplateAtti

    return GestioneTemplateAtti(
        db_path=_cfg_value("TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )


def _studio_config_manager() -> Any:
    loader = _core_runtime_func("get_config_studio")
    if callable(loader):
        return loader()
    from pct.config_studio import GestioneConfigStudio

    return GestioneConfigStudio(config_path=_cfg_value("CONFIG_STUDIO_DB", "./config/studio.json"))


def _studio_timbro_payload() -> dict[str, Any]:
    from pct.studio_timbro import build_studio_timbro

    try:
        config_studio = getattr(_studio_config_manager(), "config", None)
    except Exception:
        config_studio = None
    timbro = build_studio_timbro(
        db_path=_cfg_value("STUDIO_TIMBRO_DB", "./config/studio_timbro.db"),
        config_studio=config_studio,
        app_config=current_app.config,
    )
    return {
        "payload": timbro.to_payload(),
        "lines": timbro.to_lines(),
        "html": timbro.to_html(),
        "text": timbro.to_text(),
        "scope": timbro.scope_payload(),
    }


def _telematico_runtime_func(name: str) -> Callable[..., Any]:
    bundle = current_app.extensions.get("application_runtime_bundle")
    runtime = getattr(bundle, "telematico", {}) if bundle else {}
    func = dict(runtime or {}).get(name)
    if callable(func):
        return func

    def _missing_runtime(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        current_app.logger.warning("Runtime telematico non espone %s.", name)
        return {}

    return _missing_runtime


def _fascicoli_runtime_func(name: str) -> Callable[..., Any]:
    bundle = current_app.extensions.get("application_runtime_bundle")
    runtime = getattr(bundle, "fascicoli", {}) if bundle else {}
    func = dict(runtime or {}).get(name)
    if callable(func):
        return func

    def _missing_runtime(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(f"Runtime fascicoli non disponibile: {name}.")

    return _missing_runtime


def _core_runtime_func(name: str) -> Callable[..., Any] | None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    func = core_runtime.get(name)
    return func if callable(func) else None


def _audit_event(action: str, resource_type: str = "", resource_id: str = "", details: str = "") -> None:
    audit = _core_runtime_func("audit")
    if callable(audit):
        audit(action, resource_type, resource_id, details)


_PUBLIC_JSON_RESERVED_DETAIL = "Dettaglio riservato registrato in sicurezza."
_PUBLIC_JSON_RESERVED_KEYS = {
    "debug",
    "debug_info",
    "errore_tecnico",
    "exception",
    "exception_class",
    "exception_message",
    "exc",
    "exc_info",
    "internal_error",
    "last_error",
    "raw_error",
    "raw_exception",
    "stack",
    "stack_trace",
    "stacktrace",
    "stderr",
    "stdout",
    "traceback",
}
_PUBLIC_JSON_RESERVED_MARKERS = (
    "Traceback (most recent call last):",
    "\n  File ",
    "\nFile ",
    ".py\", line ",
    "RuntimeError:",
    "ValueError:",
    "Exception:",
    "site-packages",
    "psycopg",
    "sqlite3.",
)
_PUBLIC_JSON_SERVER_PATH_RE = re.compile(r"(?i)([A-Z]:\\|/opt/|/home/|/var/task|/app/|site-packages)")


def _public_json_text(value: str) -> str:
    if any(marker in value for marker in _PUBLIC_JSON_RESERVED_MARKERS):
        return _PUBLIC_JSON_RESERVED_DETAIL
    if _PUBLIC_JSON_SERVER_PATH_RE.search(value):
        return _PUBLIC_JSON_RESERVED_DETAIL
    return value[:2000]


def _public_json_payload(value: Any, key: str = "") -> Any:
    normalized_key = str(key or "").strip().lower()
    if normalized_key in _PUBLIC_JSON_RESERVED_KEYS:
        return _PUBLIC_JSON_RESERVED_DETAIL
    if isinstance(value, Mapping):
        return {str(item_key): _public_json_payload(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_public_json_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_public_json_payload(item) for item in value]
    if isinstance(value, str):
        return _public_json_text(value)
    return value


def _jsonify_public_payload(payload: Mapping[str, Any], status: int = 200):
    body = json.dumps(_public_json_payload(dict(payload)), ensure_ascii=False, default=str)
    return current_app.response_class(body, status=status, mimetype="application/json"), status


def _jsonify_domain_payload(payload: dict[str, Any], *, missing_status: int = 404):
    return _jsonify_public_payload(payload, missing_status if payload.get("notFound") else 200)


def _pdf_import_public_result(result: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = dict(_public_json_payload(dict(result)))
    if result.get("ok"):
        safe_message = sanitized.get("message")
        sanitized["message"] = str(safe_message) if safe_message else "Scadenze PDF importate."
    else:
        sanitized["message"] = "Importazione PDF non completata."
        sanitized["errore"] = "Importazione PDF non completata."
    return sanitized


@api_v1_react.before_request
def _phase5_backend_security_guard():
    if not (g.get("utente_corrente") or _api_key_valida()):
        return None
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    keys = ",".join(sorted({violation.key for violation in violations}))
    current_app.logger.warning(
        "policy_denied backend_security_control_param path=%s method=%s keys=%s",
        request.path,
        request.method,
        keys,
    )
    _audit_event(
        "policy_denied.backend_security",
        "api_react",
        request.path,
        f"Parametri riservati bloccati: {keys}.",
    )
    return backend_security_error_response(violations)


def _sync_event(kind: str, module: str, resource_id: str = "") -> None:
    sync_pubblica = _core_runtime_func("sync_pubblica")
    if callable(sync_pubblica):
        sync_pubblica(kind, module, resource_id)


def _actor_label() -> str:
    utente = g.get("utente_corrente")
    return str(
        getattr(utente, "nome_completo", "")
        or getattr(utente, "username", "")
        or getattr(utente, "email", "")
        or "operatore"
    )


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        raw = request.get_json(silent=True)
        return raw if isinstance(raw, dict) else {}
    return {key: value for key, value in request.form.items()}


def _json_validation_error(message: str, errors: dict[str, str], *, status: int = 200):
    return jsonify({"ok": False, "message": message, "errors": errors}), status


def _jsonify_redacted(payload: Any):
    return redacted_json_response(payload)


def _request_json_object() -> tuple[dict[str, Any] | None, Any | None]:
    if not request.is_json:
        return None, _json_validation_error(
            "Payload JSON richiesto.",
            {"payload": "Invia Content-Type application/json."},
            status=400,
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, _json_validation_error(
            "Payload JSON non valido.",
            {"payload": "Il corpo della richiesta deve essere un oggetto JSON."},
            status=400,
        )
    return payload, None


_LOCAL_SIGNER_DIAGNOSTIC_MAX_TEXT = 12000
_LOCAL_SIGNER_DIAGNOSTIC_MAX_ITEMS = 80
_LOCAL_SIGNER_DIAGNOSTIC_SECRET_KEYS = {
    "pin",
    "password",
    "password_pec",
    "authorization",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
}


def _local_signer_diagnostics_path() -> Path:
    telematico_db = Path(
        tenant_data_path(
            "TELEMATICO_DB",
            current_app.config.get("TELEMATICO_DB", "./telematico/workflow.db"),
            require_tenant=True,
        )
    )
    target = telematico_db.parent / "diagnostica-local-signer" / "eventi.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _diagnostic_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)\b(pin|password)\s*[:=]\s*\S+", r"\1=[omesso]", text)
    text = re.sub(r"(?i)\b(authorization|bearer)\s+[\w./+=:-]+", r"\1 [omesso]", text)
    if len(text) > _LOCAL_SIGNER_DIAGNOSTIC_MAX_TEXT:
        return f"{text[:_LOCAL_SIGNER_DIAGNOSTIC_MAX_TEXT]}... [troncato]"
    return text


def _sanitize_local_signer_diagnostic(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in list(value.items())[:_LOCAL_SIGNER_DIAGNOSTIC_MAX_ITEMS]:
            key_text = str(key)
            if key_text.lower() in _LOCAL_SIGNER_DIAGNOSTIC_SECRET_KEYS:
                cleaned[key_text] = "[omesso]"
            else:
                cleaned[key_text] = _sanitize_local_signer_diagnostic(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize_local_signer_diagnostic(item) for item in list(value)[:_LOCAL_SIGNER_DIAGNOSTIC_MAX_ITEMS]]
    if isinstance(value, str):
        return _diagnostic_text(value)
    return value


def _read_local_signer_diagnostics(limit: int = 20) -> list[dict[str, Any]]:
    path = _local_signer_diagnostics_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 100)):]
    except OSError:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            items.append(row)
    return items


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _request_bool(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "si", "yes", "on"}


def _request_int(*names: str, default: int) -> int:
    for name in names:
        raw = request.args.get(name)
        if raw is None:
            continue
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return default
    return default


def _detail_include_sections(default: Iterable[str] | None = None) -> set[str]:
    sections: set[str] = set(default or [])
    raw = str(request.args.get("include") or "").strip()
    if raw:
        sections.update(part.strip().lower() for part in raw.replace(";", ",").replace(" ", ",").split(",") if part.strip())
    return sections


def _regia_context(id_fasc: str) -> dict[str, Any]:
    gf = _fascicoli_loader()()
    fascicolo = gf.get(id_fasc)
    if not fascicolo:
        return {"error": jsonify({"errore": "Fascicolo non trovato.", "codice": 404}), "status": 404}
    gp = get_preventivi_readonly()
    preventivi = gp.preventivi_per_fascicolo(id_fasc)
    conferimenti = gp.conferimenti_per_fascicolo(id_fasc)
    parcelle = get_fatturazione().per_fascicolo(id_fasc)
    cliente = get_clienti().get(getattr(fascicolo, "id_cliente", "")) if getattr(fascicolo, "id_cliente", "") else None
    repo = get_practice_engine()
    profile, resolver_payload = ensure_profile_for_fascicolo(
        repo,
        fascicolo=fascicolo,
        preventivo=preventivi[0] if preventivi else None,
        conferimento=conferimenti[0] if conferimenti else None,
        actor=_actor_label(),
    )
    return {
        "gf": gf,
        "repo": repo,
        "fascicolo": fascicolo,
        "cliente": cliente,
        "preventivi": preventivi,
        "conferimenti": conferimenti,
        "parcelle": parcelle,
        "profile": profile,
        "resolver_payload": resolver_payload,
    }


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _profile_initials(value: str) -> str:
    parts = [part for part in str(value or "").replace(".", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper()


def _cfg_value(key: str, default: str = "") -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if key in paths:
        return str(paths[key] or default)
    return str(current_app.config.get(key, default) or default)


def _tenant_cfg_value(key: str, default: str = "") -> str:
    return tenant_data_path(key, default, require_tenant=True)


def _fatturazione_document_storage_root() -> Path:
    anchor = tenant_data_path("FATTURAZIONE_DB", "./fatturazione/parcelle.json", require_tenant=True)
    return Path(anchor).resolve().parent / "documenti_fatturapa"


def _messaggi_runtime_path() -> str:
    return tenant_data_path("MESSAGGI_DB", "./messaggi/storico.json", require_tenant=True)


def _studio_config_runtime():
    try:
        return getattr(_studio_config_manager(), "config", None)
    except Exception:
        current_app.logger.exception("Configurazione studio non disponibile per API React")
        return None


def _fatturazione_runtime_config() -> dict[str, Any]:
    studio_config = _studio_config_runtime()
    try:
        pagamenti_config = getattr(get_pagamenti(), "config", None)
    except Exception:
        current_app.logger.exception("Configurazione pagamenti tenant non disponibile per fatturazione")
        pagamenti_config = None
    try:
        from web.services.react_impostazioni_bridge import resolve_react_fatturazione_defaults

        fatturazione_defaults = resolve_react_fatturazione_defaults(studio_config)
    except Exception:
        fatturazione_defaults = None
    return build_fatturazione_runtime_config(
        studio_config,
        pagamenti_config,
        fatturazione_defaults=fatturazione_defaults,
    )


def _studio_telematico_staging_root() -> Path:
    fascicoli_db = _tenant_cfg_value("FASCICOLI_DB", "./data/fascicoli/fascicoli.json")
    return staging_root_for_anchor(fascicoli_db)


def _studio_telematico_storage_guard() -> dict[str, Any]:
    domains = (
        ("CLIENTI_DB", "clienti"),
        ("FASCICOLI_DB", "fascicoli"),
        ("SOGGETTI_DB", "soggetti"),
    )
    checked: list[dict[str, Any]] = []
    for config_key, label in domains:
        anchor = _tenant_cfg_value(config_key, "")
        if not anchor:
            continue
        profile = get_request_storage_runtime(anchor)
        selected_mode = str(profile.selected_mode or "").upper()
        if selected_mode not in {DbMode.SQLITE, DbMode.POSTGRESQL, DbMode.MYSQL}:
            checked.append(
                {
                    "domain": label,
                    "selected": selected_mode or DbMode.JSON,
                    "effective": str(profile.effective_mode or DbMode.JSON).upper(),
                    "backend": "json",
                }
            )
            continue
        try:
            backend = get_request_studio_db(anchor)
        except Exception as exc:
            current_app.logger.exception("Backend SQL non disponibile per import pratiche: %s", exc)
            raise QuickOrganizerImportError(
                f"Import bloccato: lo studio è configurato per {selected_mode}, "
                f"ma il database SQL non è disponibile per {label}. Nessun dato viene scritto nei JSON."
            ) from exc
        effective_profile = get_request_storage_runtime(anchor)
        effective_mode = str(effective_profile.effective_mode or "").upper()
        if backend is None or effective_mode not in {DbMode.SQLITE, DbMode.POSTGRESQL}:
            raise QuickOrganizerImportError(
                f"Import bloccato: {label} è configurato per {selected_mode}, "
                "ma il runtime sta ricadendo su JSON. Attiva o migra prima il database SQL dello studio."
            )
        checked.append(
            {
                "domain": label,
                "selected": selected_mode,
                "effective": effective_mode,
                "backend": str(getattr(backend, "backend_kind", "sqlite") or "sqlite"),
                "studioDbPath": str(getattr(effective_profile, "studio_db_path", "") or ""),
            }
        )
    return {
        "guard": "sql-runtime-required-when-configured",
        "domains": checked,
    }


def _studio_telematico_prepare_root() -> Path:
    data_root = (
        current_app.config.get("DATA_DIR")
        or current_app.config.get("PCT_DATA_ROOT")
        or current_app.config.get("DATA_ROOT")
        or os.getenv("IUSENTRA_DATA_DIR")
        or "data"
    )
    return Path(str(data_root)) / "quickorganizer_auto_prepare"


def _studio_telematico_public_token(body: Mapping[str, Any] | None = None) -> str:
    payload = body or {}
    return str(
        request.args.get("token")
        or request.headers.get("X-IUSENTRA-Auto-Import-Token")
        or payload.get("token")
        or ""
    ).strip()


def _studio_telematico_missing_token_response():
    return jsonify({
        "ok": False,
        "errore": "Sessione preparazione non autorizzata.",
        "codice": "preparazione_non_autorizzata",
    }), 401


def _richiedi_auth_studio_telematico_token(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        body = _request_payload() if request.is_json else {}
        token = _studio_telematico_public_token(body if isinstance(body, Mapping) else None)
        if not token:
            return _studio_telematico_missing_token_response()
        g.studio_telematico_auto_prepare_token = token
        g.studio_telematico_auto_prepare_body = body if isinstance(body, Mapping) else {}
        return func(*args, **kwargs)

    return wrapper


class _RequestBodyStorage:
    def __init__(self, stream: Any) -> None:
        self._stream = stream

    def save(self, target: str | Path) -> None:
        with Path(target).open("wb") as output:
            shutil.copyfileobj(self._stream, output, length=1024 * 1024)


_STUDIO_TELEMATICO_DIRECT_UPLOAD_LIMIT_BYTES = 150 * 1024 * 1024
_STUDIO_TELEMATICO_CHUNK_SIZE_BYTES = 64 * 1024 * 1024


def _studio_telematico_import_page(path: str = "/importa-pratiche") -> dict[str, Any]:
    can_import = _puo_importare_studio_telematico()
    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "page": {
            "title": "Importa pratiche",
            "subtitle": (
                "Acquisizione guidata di pratiche, clienti, parti, documenti, comunicazioni e appuntamenti "
                "dal gestionale precedente dello studio."
            ),
            "path": path,
        },
        "permissions": {
            "canImport": can_import,
            "message": "" if can_import else "Per importare le pratiche serve un profilo autorizzato dello studio.",
        },
        "steps": [
            {
                "id": "prepara",
                "label": "Prepara il pacchetto",
                "description": "Sul PC autorizzato raccogli archivio dati, documenti e comunicazioni collegate.",
            },
            {
                "id": "controlla",
                "label": "Controlla completezza",
                "description": "IUSENTRA mostra quante pratiche, parti, documenti e comunicazioni sono pronti.",
            },
            {
                "id": "importa",
                "label": "Acquisisci nello studio",
                "description": "L'import crea fascicoli e anagrafiche senza duplicare quanto già presente.",
            },
        ],
        "acceptedFiles": ".zip,.json,.mdb",
        "localPathEnabled": _studio_telematico_local_path_enabled(),
        "actions": {
            "refresh": "/api/v1/ui/import/quickorganizer",
            "preview": "/api/v1/ui/import/quickorganizer/anteprima",
            "uploadStart": "/api/v1/ui/import/quickorganizer/upload-session",
            "uploadChunk": "/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/chunk",
            "uploadComplete": "/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/completa",
            "prepareStart": "/api/v1/ui/import/quickorganizer/preparazione",
            "run": "/api/v1/ui/import/quickorganizer/esegui",
            "helper": "/static/tools/PreparaPacchettoPratiche.exe",
            "fascicoli": "/fascicoli",
            "clienti": "/clienti",
        },
        "upload": {
            "directLimitBytes": _STUDIO_TELEMATICO_DIRECT_UPLOAD_LIMIT_BYTES,
            "chunkSizeBytes": _STUDIO_TELEMATICO_CHUNK_SIZE_BYTES,
            "maxUploadBytes": max_chunked_upload_bytes(),
        },
        "notes": [
            "Gli archivi grandi vengono caricati a blocchi e ricomposti nello spazio dati dello studio.",
            "Il pacchetto consigliato è l'archivio compresso preparato dal PC autorizzato.",
            "Tutti i documenti e le comunicazioni collegate devono essere inclusi nel pacchetto.",
            "L'archivio dati da solo consente il controllo delle pratiche, ma senza documenti e comunicazioni l'import resta parziale.",
            "Le pratiche già importate vengono riconosciute e aggiornate, non duplicate.",
        ],
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
    }


def _tenant_runtime_label() -> str:
    tenant = g.get("tenant")
    return str(
        g.get("tenant_context_slug", "")
        or g.get("tenant_slug", "")
        or g.get("auth_tenant_slug", "")
        or getattr(tenant, "slug", "")
        or "default"
    )


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        current_app.logger.exception("Dashboard React: sorgente non disponibile (%s).", label)
        # La sezione resta vuota, ma la Panoramica deve poterlo dichiarare:
        # uno zero da archivio caduto non e' uno zero reale.
        segnala_sorgente_non_disponibile(label)
        return fallback


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    for sample in (raw.replace("Z", "+00:00"), raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            if parsed.tzinfo:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    return None


def _parse_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.date()
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _short_text(value: Any, limit: int = 72) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _format_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    today = oggi_rome()
    if parsed.date() == today:
        return parsed.strftime("%H:%M")
    if parsed.date() == today - timedelta(days=1):
        return "ieri"
    if parsed.date() == today + timedelta(days=1):
        return "domani"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _format_date(value: Any) -> str:
    parsed = _parse_date(value)
    if not parsed:
        return ""
    today = oggi_rome()
    if parsed == today:
        return "oggi"
    if parsed == today + timedelta(days=1):
        return "domani"
    if parsed == today - timedelta(days=1):
        return "ieri"
    if parsed.year == today.year:
        return f"{parsed.day} {MONTHS_SHORT[parsed.month - 1]}"
    return parsed.strftime("%d/%m/%Y")


def _row(
    item_id: Any,
    title: Any,
    subtitle: Any = "",
    *,
    time: Any = "",
    avatar: str = "",
    unread: bool = False,
    badge: str = "",
    tone: str = "neutral",
    href: str = "",
) -> dict[str, Any]:
    return {
        "id": str(item_id or ""),
        "title": _short_text(title or "Elemento operativo", 90),
        "subtitle": _short_text(subtitle or "", 120),
        "time": str(time or ""),
        "avatar": avatar,
        "unread": bool(unread),
        "badge": badge,
        "tone": tone,
        "href": href,
    }


def _euro(value: float) -> str:
    return format_euro_it(value)


def _count_agenda_oggi() -> int:
    today = oggi_rome()
    appuntamenti = _safe("agenda", lambda: get_agenda().tutti(), [])
    count = 0
    for item in appuntamenti:
        raw = getattr(item, "data_ora_dt", None) or getattr(item, "data_ora", "")
        parsed = _parse_datetime(raw)
        if parsed and parsed.date() == today:
            count += 1
    return count


def _count_fascicoli_attivi() -> int:
    return len(_safe("fascicoli", lambda: get_fascicoli().tutti(archiviati=False), []))


def _parcelle_da_incassare() -> float:
    parcelle = _safe("fatturazione", lambda: get_fatturazione().tutte(), [])
    escluse = {StatoParcella.PAGATA.value, StatoParcella.ANNULLATA.value}
    totale = 0.0
    for parcella in parcelle:
        stato = _enum_value(getattr(parcella, "stato", ""))
        if stato in escluse:
            continue
        totale += float(getattr(parcella, "netto_a_pagare", 0.0) or getattr(parcella, "totale", 0.0) or 0.0)
    return round(totale, 2)


def _workspace_overview() -> dict[str, Any]:
    service = WorkspaceIntelligenteService(
        agenda=get_agenda(),
        scadenziario=get_scadenziario(),
        fascicoli=get_fascicoli(),
        calendar_sync=get_calendar_sync(),
        giurisprudenza=get_giurisprudenza(),
        snapshot_path=str(current_app.config.get("WORKSPACE_INTELLIGENCE_DB", "")),
    )
    return service.panoramica(horizon_days=14)


def _email_manager() -> GestioneEmailRicevute:
    return GestioneEmailRicevute(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))


def _ordinary_email_manager() -> GestioneEmailRicevute:
    return GestioneEmailRicevute(_tenant_cfg_value("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"))


def _messaggi_manager() -> GestioneMessaggi:
    return GestioneMessaggi(
        ConfigMessaggistica(studio_nome=studio_nome()),
        db_path=_tenant_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
    )


def _messaggi_tutti() -> list[Messaggio]:
    try:
        return _messaggi_manager().tutti()
    except Exception:
        path = Path(_tenant_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"))
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            payloads = raw.values() if isinstance(raw, dict) else raw if isinstance(raw, list) else []
            return [Messaggio.from_dict(item) for item in payloads if isinstance(item, dict)]
        except Exception:
            current_app.logger.exception("Dashboard React: storico messaggi operativo non leggibile.")
            return []


def _email_rows(limit: int = 5) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    pec_emails = _safe("pec", lambda: _email_manager().tutte(cartella=CartellaEmail.INBOX), [])
    ordinary_emails = _safe("email_ordinaria", lambda: _ordinary_email_manager().tutte(cartella=CartellaEmail.INBOX), [])
    pec_emails = sorted(
        pec_emails,
        key=lambda email: _parse_datetime(getattr(email, "timestamp", "")) or datetime.min,
        reverse=True,
    )
    ordinary_emails = sorted(
        ordinary_emails,
        key=lambda email: _parse_datetime(getattr(email, "timestamp", "")) or datetime.min,
        reverse=True,
    )
    pec_rows: list[dict[str, Any]] = []
    mail_rows: list[dict[str, Any]] = []
    pec_unread = sum(1 for email in pec_emails if getattr(email, "stato", "") == StatoEmail.NON_LETTA)
    for email in pec_emails:
        unread = getattr(email, "stato", "") == StatoEmail.NON_LETTA
        title = getattr(email, "mittente_nome", "") or getattr(email, "mittente", "") or "Mittente non indicato"
        subtitle = getattr(email, "oggetto", "") or getattr(email, "anteprima", "") or "Email senza oggetto"
        email_id = str(getattr(email, "id", "") or "")
        row = _row(
            email_id,
            title,
            subtitle,
            time=_format_time(getattr(email, "timestamp", "")),
            unread=unread,
            # Deep link al messaggio: la card deve aprire l'evento, non la lista.
            href=f"/email/messaggio/{quote(email_id)}" if email_id else "/email/",
        )
        if len(pec_rows) < limit:
            pec_rows.append(row)
    for email in ordinary_emails:
        unread = getattr(email, "stato", "") == StatoEmail.NON_LETTA
        title = getattr(email, "mittente_nome", "") or getattr(email, "mittente", "") or "Mittente non indicato"
        subtitle = getattr(email, "oggetto", "") or getattr(email, "anteprima", "") or "Email senza oggetto"
        if len(mail_rows) >= limit:
            break
        email_id = str(getattr(email, "id", "") or "")
        mail_rows.append(
            _row(
                email_id,
                title,
                subtitle,
                time=_format_time(getattr(email, "timestamp", "") or getattr(email, "data", "")),
                unread=unread,
                href=f"/email-ordinaria/messaggio/{quote(email_id)}" if email_id else "/email-ordinaria/",
            )
        )
    return pec_rows, mail_rows, pec_unread


def _initials(value: Any) -> str:
    parts = [part for part in str(value or "").replace("@", " ").replace(".", " ").split() if part]
    if not parts:
        return ""
    return "".join(part[0] for part in parts[:2]).upper()


def _client_message_rows(limit: int = 5) -> tuple[list[dict[str, Any]], int]:
    messages = _messaggi_tutti()
    rows: list[dict[str, Any]] = []
    recent_count = 0
    week_ago = oggi_rome() - timedelta(days=7)
    for message in messages:
        canale = _enum_value(getattr(message, "canale", ""))
        if canale == CanaleMsggio.EMAIL.value:
            continue
        created_date = _parse_date(getattr(message, "creato_il", ""))
        if created_date and created_date >= week_ago:
            recent_count += 1
        stato = _enum_value(getattr(message, "stato", ""))
        badge = ""
        tone = "neutral"
        if stato == StatoMessaggio.IN_CODA.value:
            badge = "IN CODA"
            tone = "warning"
        elif stato == StatoMessaggio.FALLITO.value:
            badge = "ERRORE"
            tone = "danger"
        title = getattr(message, "nome_destinatario", "") or getattr(message, "telefono_destinatario", "") or canale
        subtitle = getattr(message, "oggetto", "") or getattr(message, "corpo", "") or "Messaggio senza testo"
        if len(rows) < limit:
            message_id = str(getattr(message, "id", "") or "")
            rows.append(
                _row(
                    message_id,
                    title,
                    subtitle,
                    time=_format_time(getattr(message, "creato_il", "")),
                    avatar=_initials(title),
                    badge=badge,
                    tone=tone,
                    href=f"/messaggi/{quote(message_id)}" if message_id else "/messaggi",
                )
            )
    return rows, recent_count


def _agenda_rows(limit: int = 6) -> list[dict[str, Any]]:
    today = oggi_rome()
    until = today + timedelta(days=14)
    appuntamenti = _safe("agenda", lambda: get_agenda().tutti(), [])
    rows: list[dict[str, Any]] = []
    for item in appuntamenti:
        parsed = _parse_datetime(getattr(item, "data_ora", ""))
        if not parsed or parsed.date() < today or parsed.date() > until:
            continue
        subtitle = " - ".join(
            part
            for part in [
                getattr(item, "procedimento", ""),
                getattr(item, "tribunale", ""),
                getattr(item, "luogo", ""),
            ]
            if str(part or "").strip()
        )
        badge = "OGGI" if parsed.date() == today else ("DOMANI" if parsed.date() == today + timedelta(days=1) else _format_date(parsed))
        item_id = str(getattr(item, "id", "") or "")
        rows.append(
            _row(
                item_id,
                getattr(item, "titolo", "") or "Appuntamento",
                subtitle,
                time=parsed.strftime("%H:%M"),
                badge=badge.upper(),
                tone="warning" if parsed.date() <= today + timedelta(days=1) else "primary",
                href=f"/agenda/{quote(item_id)}" if item_id else "/agenda",
            )
        )
        if len(rows) >= limit:
            break
    return rows


def _today_operations(overview: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, action in enumerate(list(overview.get("actions") or [])):
        rows.append(
            _row(
                f"action-{index}",
                action.get("title") or "Azione operativa",
                action.get("description") or "",
                badge=action.get("badge") or "Apri",
                tone=action.get("tone") or "primary",
                href=action.get("href") or "/workspace-intelligente",
            )
        )
    if len(rows) < limit:
        for scadenza in list(overview.get("urgent_deadlines") or []):
            deadline_id = str(getattr(scadenza, "id", "") or "")
            rows.append(
                _row(
                    deadline_id,
                    getattr(scadenza, "titolo", "") or "Scadenza urgente",
                    f"Scade {_format_date(getattr(scadenza, 'data_scadenza', ''))}",
                    badge="Apri",
                    tone="danger",
                    href=f"/scadenziario/{quote(deadline_id)}" if deadline_id else "/scadenziario",
                )
            )
            if len(rows) >= limit:
                break
    return rows[:limit]


def _clienti_by_id() -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    return {str(getattr(cliente, "id", "")): cliente for cliente in clienti}


def _incomplete_registry() -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    soggetti = _safe("soggetti", lambda: get_soggetti().tutti(), [])

    clienti_mancanti = [
        item
        for item in clienti
        if list(getattr(item, "campi_mancanti_per_conferimento", []) or [])
    ]
    soggetti_mancanti = [item for item in soggetti if _soggetto_mancante(item)]

    totale = len(clienti) + len(soggetti)
    mancanti = len(clienti_mancanti) + len(soggetti_mancanti)
    percent = 100 if totale == 0 else max(0, min(100, round(((totale - mancanti) / totale) * 100)))
    return {
        "percent": percent,
        "totalMissing": mancanti,
        "items": [
            {"label": "Clienti", "count": len(clienti_mancanti)},
            {"label": "Soggetti", "count": len(soggetti_mancanti)},
        ],
    }


def _soggetto_mancante(soggetto: Any) -> bool:
    nome = str(getattr(soggetto, "nome_completo", "") or "").strip()
    identificativo = str(getattr(soggetto, "identificativo", "") or "").strip()
    recapiti = getattr(soggetto, "recapiti", None)
    indirizzo = getattr(soggetto, "indirizzo", None)
    has_contact = any(
        str(getattr(recapiti, field, "") or "").strip()
        for field in ("telefono", "cellulare", "email", "pec")
    )
    has_address = any(
        str(getattr(indirizzo, field, "") or "").strip()
        for field in ("via", "comune")
    )
    return not (nome and nome != "---" and identificativo and has_contact and has_address)


def _missing_engagements(limit: int = 4) -> tuple[list[dict[str, Any]], int]:
    preventivi = _safe("preventivi", lambda: get_preventivi_readonly(), None)
    if not preventivi:
        return [], 0
    clienti = _clienti_by_id()
    rows: list[dict[str, Any]] = []
    count = 0
    active_states = {
        StatoPreventivo.ACCETTATO.value,
        StatoPreventivo.INVIATO.value,
        StatoPreventivo.APERTO.value,
        StatoPreventivo.VERIFICATO.value,
        StatoPreventivo.GENERATO.value,
    }
    ignored_states = {StatoPreventivo.RIFIUTATO.value, StatoPreventivo.SCADUTO.value, StatoPreventivo.CONVERTITO.value}
    today = oggi_rome()
    for preventivo in preventivi.tutti_preventivi():
        stato = _enum_value(getattr(preventivo, "stato", ""))
        if stato in ignored_states or stato not in active_states:
            continue
        if preventivi.get_conferimento_principale_preventivo(getattr(preventivo, "id", "")):
            continue
        count += 1
        cliente = clienti.get(str(getattr(preventivo, "id_cliente", "")))
        cliente_nome = getattr(cliente, "nome_completo", "") if cliente else ""
        due = _parse_date(getattr(preventivo, "data_scadenza", ""))
        badge = "PROMEMORIA"
        tone = "warning"
        if stato == StatoPreventivo.ACCETTATO.value:
            badge = "URGENTE"
            tone = "danger"
        elif due and due <= today + timedelta(days=3):
            badge = "ALTA"
            tone = "orange"
        if len(rows) < limit:
            preventivo_id = str(getattr(preventivo, "id", "") or "")
            rows.append(
                _row(
                    preventivo_id,
                    cliente_nome or "Cliente non collegato",
                    f"Pratica: {getattr(preventivo, 'oggetto', '') or getattr(preventivo, 'numero', '')}",
                    badge=badge,
                    tone=tone,
                    # Apre direttamente il preventivo da cui generare il conferimento.
                    href=f"/preventivi?preventivo={quote(preventivo_id)}" if preventivo_id else "/preventivi",
                )
            )
    return rows, count


def _expiring_quotes_count() -> int:
    preventivi = _safe("preventivi", lambda: get_preventivi_readonly().tutti_preventivi(), [])
    today = oggi_rome()
    horizon = today + timedelta(days=14)
    active = {StatoPreventivo.INVIATO.value, StatoPreventivo.APERTO.value, StatoPreventivo.VERIFICATO.value}
    count = 0
    for preventivo in preventivi:
        due = _parse_date(getattr(preventivo, "data_scadenza", ""))
        if not due or not (today <= due <= horizon):
            continue
        if _enum_value(getattr(preventivo, "stato", "")) in active:
            count += 1
    return count


def _high_priority_matters(limit: int = 4) -> list[dict[str, Any]]:
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(solo_aperte=True), [])
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(archiviati=False), [])
    by_id = {str(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scadenza in scadenze:
        priority = _enum_value(getattr(scadenza, "priorita", ""))
        if priority not in {PrioritaTermine.CRITICA.value, PrioritaTermine.ALTA.value}:
            continue
        id_fascicolo = str(getattr(scadenza, "id_fascicolo", "") or "")
        if not id_fascicolo or id_fascicolo in seen:
            continue
        fascicolo = by_id.get(id_fascicolo)
        if not fascicolo:
            continue
        seen.add(id_fascicolo)
        rg = getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", "") or getattr(fascicolo, "numero", "")
        rows.append(
            _row(
                id_fascicolo,
                f"{rg} - {getattr(fascicolo, 'titolo', '') or getattr(fascicolo, 'oggetto', '')}",
                getattr(fascicolo, "tribunale", "") or getattr(fascicolo, "nome_cliente", ""),
                badge="URGENTE" if priority == PrioritaTermine.CRITICA.value else "ALTA",
                tone="danger" if priority == PrioritaTermine.CRITICA.value else "orange",
                href=f"/fascicoli/{id_fascicolo}",
            )
        )
        if len(rows) >= limit:
            break
    if len(rows) < limit:
        for fascicolo in fascicoli:
            if not getattr(fascicolo, "has_conflicts", False) or getattr(fascicolo, "id", "") in seen:
                continue
            rows.append(
                _row(
                    getattr(fascicolo, "id", ""),
                    getattr(fascicolo, "titolo", "") or "Fascicolo da verificare",
                    getattr(fascicolo, "tribunale", "") or getattr(fascicolo, "nome_cliente", ""),
                    badge="ALTA",
                    tone="orange",
                    href=f"/fascicoli/{getattr(fascicolo, 'id', '')}",
                )
            )
            if len(rows) >= limit:
                break
    return rows


def _deadline_distribution() -> list[dict[str, Any]]:
    scadenze = _safe("scadenziario", lambda: get_scadenziario().tutte(solo_aperte=True), [])
    buckets = {
        PrioritaTermine.CRITICA.value: {"label": "scadenze critiche", "tone": "danger", "count": 0},
        PrioritaTermine.ALTA.value: {"label": "scadenze ad alta priorita", "tone": "warning", "count": 0},
        PrioritaTermine.MEDIA.value: {"label": "scadenze a priorita media", "tone": "primary", "count": 0},
        PrioritaTermine.BASSA.value: {"label": "scadenze a bassa priorita", "tone": "success", "count": 0},
    }
    for scadenza in scadenze:
        priority = _enum_value(getattr(scadenza, "priorita", PrioritaTermine.MEDIA.value))
        if priority not in buckets:
            priority = PrioritaTermine.MEDIA.value
        buckets[priority]["count"] += 1
    total = sum(int(row["count"]) for row in buckets.values())
    rows: list[dict[str, Any]] = []
    for row in buckets.values():
        count = int(row["count"])
        rows.append(
            {
                "label": f"{count} {row['label']}",
                "count": count,
                "percent": 0 if total == 0 else round((count / total) * 100),
                "tone": row["tone"],
            }
        )
    return rows


def _economic_rows() -> list[dict[str, Any]]:
    oggi = oggi_rome()
    anno = oggi.year
    month_prefix = f"{anno:04d}-{oggi.month:02d}"
    stats = _safe("fatturazione", lambda: get_fatturazione().statistiche(anno), {})
    parcelle = _safe("fatturazione", lambda: get_fatturazione().tutte(), [])
    month_parcelle = [
        item
        for item in parcelle
        if str(getattr(item, "data_emissione", "") or "").startswith(month_prefix)
        and _enum_value(getattr(item, "stato", "")) not in {StatoParcella.BOZZA.value, StatoParcella.ANNULLATA.value}
    ]
    month_paid = [
        item
        for item in parcelle
        if str(getattr(item, "data_pagamento", "") or "").startswith(month_prefix)
        and _enum_value(getattr(item, "stato", "")) == StatoParcella.PAGATA.value
    ]
    timesheet_entries = _safe("timesheet", lambda: get_timesheet().tutte(), [])
    month_time = [
        item
        for item in timesheet_entries
        if str(getattr(item, "data_attivita", "") or "").startswith(month_prefix)
        and _enum_value(getattr(item, "stato", "")) != StatoTimesheet.ANNULLATO.value
    ]
    hours = round(sum(int(getattr(item, "minuti", 0) or 0) for item in month_time) / 60.0, 1)
    return [
        {
            "label": "Fatturato mese",
            "value": _euro(sum(float(getattr(item, "totale", 0.0) or 0.0) for item in month_parcelle)),
            "note": f"{len(month_parcelle)} parcelle emesse",
        },
        {
            "label": "Incassi mese",
            "value": _euro(sum(float(getattr(item, "totale", 0.0) or 0.0) for item in month_paid)),
            "note": f"{len(month_paid)} pagamenti registrati",
        },
        {
            "label": "Da incassare",
            "value": _euro(float(stats.get("da_incassare", 0.0) or 0.0) + float(stats.get("scaduto", 0.0) or 0.0)),
            "note": f"{int(stats.get('totale_in_attesa', 0) or 0) + int(stats.get('totale_scadute', 0) or 0)} parcelle aperte",
        },
        {"label": "Ore lavorate", "value": f"{str(hours).replace('.', ',')} h", "note": f"{len(month_time)} voci timesheet"},
    ]


def _lex_suggestions(
    *,
    urgent_actions: int,
    incomplete_registry: dict[str, Any],
    missing_engagements_count: int,
    high_priority_matters: Iterable[dict[str, Any]],
) -> list[str]:
    suggestions: list[str] = []
    if urgent_actions:
        suggestions.append("Verifica le azioni urgenti prima di aggiornare agenda e fascicoli.")
    if int(incomplete_registry.get("totalMissing") or 0):
        suggestions.append("Completa le anagrafiche mancanti per evitare blocchi in preventivi, incarichi e atti.")
    if missing_engagements_count:
        suggestions.append("Genera o firma i conferimenti incarico collegati ai preventivi pronti.")
    if list(high_priority_matters):
        suggestions.append("Apri i fascicoli con priorita alta e controlla scadenze, udienze e documenti recenti.")
    return suggestions[:3]


def _metrics(
    *,
    urgent_actions: int,
    pec_unread: int,
    client_messages: int,
    expiring_quotes: int,
    missing_engagements_count: int,
) -> list[dict[str, Any]]:
    return [
        {
            "id": "urgent",
            "label": "Azioni urgenti",
            "value": urgent_actions,
            "tag": "URGENTE" if urgent_actions else "",
            "tone": "danger",
            "href": "/workspace-intelligente",
            "actionLabel": "Vai alle azioni",
        },
        {
            "id": "pec",
            "label": "PEC da leggere",
            "value": pec_unread,
            "tag": "OGGI" if pec_unread else "",
            "tone": "primary",
            "href": "/email/",
            "actionLabel": "Apri PEC",
        },
        {
            "id": "messages",
            "label": "Messaggi clienti",
            "value": client_messages,
            "tag": "OGGI" if client_messages else "",
            "tone": "success",
            "href": "/messaggi",
            "actionLabel": "Vai ai messaggi",
        },
        {
            "id": "quotes",
            "label": "Preventivi in scadenza",
            "value": expiring_quotes,
            "tag": "PROMEMORIA" if expiring_quotes else "",
            "tone": "purple",
            "href": "/preventivi",
            "actionLabel": "Apri preventivi",
        },
        {
            "id": "engagements",
            "label": "Conferimenti mancanti",
            "value": missing_engagements_count,
            "tag": "ALTA" if missing_engagements_count else "",
            "tone": "orange",
            "href": "/preventivi",
            "actionLabel": "Completa ora",
        },
    ]


def _fascicoli_preview(limit: int = 5) -> list[dict[str, Any]]:
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(archiviati=False), [])
    out: list[dict[str, Any]] = []
    for fascicolo in fascicoli[:limit]:
        out.append(
            {
                "id": str(getattr(fascicolo, "id", "")),
                "title": str(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo"),
                "rg": str(getattr(fascicolo, "numero_rg", "") or "RG non impostato"),
                "office": str(getattr(fascicolo, "tribunale", "") or "Ufficio non impostato"),
                "status": _enum_value(getattr(fascicolo, "stato", "")),
                "client": str(getattr(fascicolo, "id_cliente", "") or ""),
                "counterparty": str(getattr(fascicolo, "controparte", "") or ""),
                "nextHearing": str(getattr(fascicolo, "data_prossima_udienza", "") or ""),
                "riskScore": 0,
            }
        )
    return out


@api_v1_react.get("/bootstrap")
@_richiedi_auth
def bootstrap():
    utente = g.get("utente_corrente")
    tenant = g.get("tenant")
    display_name = str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "").strip() if utente else ""
    username = str(getattr(utente, "username", "") or "").strip() if utente else ""
    role = _enum_value(getattr(utente, "ruolo", "")) if utente else ""
    return jsonify(
        {
            "product": "IUSENTRA",
            "version": APP_VERSION,
            "shell": "react",
            "mounted_at": "/app-v2",
            "generated_at": _iso_now(),
            "studio": {
                "nome": studio_nome(),
                "tenant": getattr(tenant, "slug", "") if tenant else "",
            },
            "user": {
                "id": getattr(utente, "id", "") if utente else "",
                "username": username,
                "displayName": display_name,
                "role": role,
                "initials": _profile_initials(username or display_name),
            },
            "route_flags": {
                "replace_dashboard": True,
                "replace_regia_operativa": True,
                "replace_global_search": True,
                "replace_agenda": True,
                "replace_fascicoli": True,
                "replace_scadenziario": True,
                "replace_telematico": True,
                "replace_telematico_surfaces": True,
                "replace_tribunali_pec": True,
                "replace_checklist_deposito": True,
                "replace_guida_firma_digitale": True,
                "replace_preventivi": False,
                "replace_sito_studio": False,
                "replace_clienti": True,
                "replace_soggetti": True,
                "replace_email": True,
                "replace_messaggi": True,
            },
        }
    )


@api_v1_react.get("/feature-flags")
@_richiedi_auth
def feature_flags():
    payload = feature_flags_payload(current_app.config)
    payload["flags"] = apply_legal_notification_presidia_effective_flags(
        payload["flags"],
        config=current_app.config,
    )
    return jsonify(payload)


@api_v1_react.get("/workflow-agents")
@_richiedi_auth
def workflow_agents_home():
    if not _workflow_agent_can_any("ai.usa", "legal_skills.leggi", "legal_skills.esegui"):
        return _workflow_agent_forbidden()
    try:
        return jsonify(build_workflow_agents_payload())
    except Exception as exc:
        payload, status = workflow_agent_error_payload(exc)
        return jsonify(payload), status


@api_v1_react.post("/workflow-agents/preview")
@_richiedi_auth
def workflow_agents_preview():
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not _workflow_agent_can_any("ai.usa", "legal_skills.esegui"):
        return _workflow_agent_forbidden()
    payload, error = _request_json_object()
    if error:
        return error
    try:
        return jsonify(
            preview_workflow_agent(
                payload or {},
                actor=_actor_label(),
                user_permissions=_workflow_agent_user_permissions(),
            )
        )
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.get("/workflow-agents/runs/<run_id>")
@_richiedi_auth
def workflow_agents_run_detail(run_id: str):
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not _workflow_agent_can_any("ai.usa", "legal_skills.leggi", "legal_skills.esegui"):
        return _workflow_agent_forbidden()
    try:
        return jsonify(get_workflow_agent_run(run_id))
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.get("/workflow-agents/approvals")
@_richiedi_auth
def workflow_agents_approvals():
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not _workflow_agent_can_any("legal_skills.approva"):
        return _workflow_agent_forbidden()
    try:
        return jsonify(list_workflow_agent_approvals())
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.post("/workflow-agents/runs/<run_id>/approve")
@_richiedi_auth
def workflow_agents_approve(run_id: str):
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not is_feature_enabled("lex.workflowAgents.writeActions", current_app.config):
        return feature_disabled_response("lex.workflowAgents.writeActions")
    if not _workflow_agent_can_any("legal_skills.approva"):
        return _workflow_agent_forbidden()
    payload, error = _request_json_object()
    if error:
        return error
    try:
        return jsonify(
            approve_workflow_agent_run(
                payload or {},
                run_id=run_id,
                actor=_actor_label(),
                user_permissions=_workflow_agent_user_permissions(),
            )
        )
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.post("/workflow-agents/runs/<run_id>/reject")
@_richiedi_auth
def workflow_agents_reject(run_id: str):
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not _workflow_agent_can_any("legal_skills.approva"):
        return _workflow_agent_forbidden()
    payload, error = _request_json_object()
    if error:
        return error
    try:
        return jsonify(reject_workflow_agent_run(payload or {}, run_id=run_id, actor=_actor_label()))
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.get("/workflow-agents/metrics")
@_richiedi_auth
def workflow_agents_metrics():
    if not is_feature_enabled("lex.workflowAgents.enabled", current_app.config):
        return feature_disabled_response("lex.workflowAgents.enabled")
    if not _workflow_agent_can_any("ai.usa", "legal_skills.leggi", "legal_skills.esegui"):
        return _workflow_agent_forbidden()
    try:
        return jsonify(workflow_agent_metrics_payload())
    except Exception as exc:
        body, status = workflow_agent_error_payload(exc)
        return jsonify(body), status


@api_v1_react.get("/global-search")
@_richiedi_auth
def global_search_react_bootstrap():
    from web.blueprints.global_search import _service as global_search_service, _tenant_id as global_search_tenant_id

    service = global_search_service()
    try:
        stats = service.stats({"tenant_id": global_search_tenant_id()})
        return jsonify(
            {
                "ok": True,
                "source": "repository_reali",
                "generated_at": _iso_now(),
                "stats": stats,
                "actions": {
                    "search": "/api/global-search",
                    "stats": "/api/global-search/stats",
                    "reindex": "/api/global-search/reindex",
                },
            }
        )
    finally:
        service.repository.close()


@api_v1_react.get("/clienti")
@_richiedi_auth
def clienti_react_list():
    try:
        return jsonify(build_react_clienti_payload(get_clienti=get_clienti, get_fascicoli=get_fascicoli))
    except Exception:
        current_app.logger.exception("Clienti React: bridge non disponibile.")
        return jsonify({
            "source": "errore_controllato",
            "generated_at": _iso_now(),
            "contracts": {
                "mock_fallback": False,
                "read_only": False,
                "writes": "operational_routes",
                "route_owner": "react_shell",
            },
            "summary": {
                "total": 0,
                "active": 0,
                "potential": 0,
                "archived": 0,
                "withMatters": 0,
                "incomplete": 0,
                "withoutContacts": 0,
                "privacyMissing": 0,
                "documentsExpired": 0,
            },
            "items": [],
            "facets": {
                "types": [{"value": "tutti", "label": "Tutti i tipi", "count": 0}],
                "statuses": [{"value": "tutti", "label": "Tutti gli stati", "count": 0}],
            },
        })


@api_v1_react.post("/clienti/delete")
@_richiedi_auth
def clienti_react_delete():
    payload, error = _request_json_object()
    if error:
        return error
    ids = [str(item or "").strip() for item in list(payload.get("ids") or []) if str(item or "").strip()]
    if not ids:
        return _json_validation_error("Seleziona almeno un cliente da eliminare.", {"ids": "Nessun cliente selezionato."}, status=400)
    clienti_repo = get_clienti()
    deleted: list[str] = []
    missing: list[str] = []
    for cliente_id in ids:
        try:
            clienti_repo.elimina(cliente_id)
            _sync_event("elimina", "clienti", cliente_id)
            deleted.append(cliente_id)
        except KeyError:
            missing.append(cliente_id)
    if not deleted:
        return jsonify({"ok": False, "message": "Nessun cliente eliminato.", "deleted": [], "missing": missing}), 404
    if len(deleted) == 1:
        message = "Cliente eliminato."
    else:
        message = f"{len(deleted)} clienti eliminati."
    return jsonify({"ok": True, "message": message, "deleted": deleted, "missing": missing})


def _voice_cliente_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _voice_cliente_cf(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def _voice_cliente_error_message(error: Exception) -> str:
    message = str(error or "").strip()
    if "Codice fiscale non valido" in message:
        return "Il codice fiscale non ha un formato valido."
    if "Cliente con CF" in message and "presente" in message:
        return "Un cliente con questo codice fiscale è già presente."
    return "Cliente non aggiunto. Controlla i dati obbligatori."


@api_v1_react.post("/clienti/voce/crea")
@_richiedi_auth
def clienti_react_voce_crea():
    if not _puo_scrivere_clienti():
        return jsonify({"ok": False, "message": "Permesso non sufficiente per aggiungere clienti."}), 403

    data = _request_payload()
    nome = _voice_cliente_text(data.get("nome"))
    cognome = _voice_cliente_text(data.get("cognome"))
    codice_fiscale = _voice_cliente_cf(data.get("codice_fiscale"))
    errors: dict[str, str] = {}
    if not nome:
        errors["nome"] = "Inserisci il nome."
    if not cognome:
        errors["cognome"] = "Inserisci il cognome."
    if not codice_fiscale:
        errors["codice_fiscale"] = "Inserisci il codice fiscale."
    elif len(codice_fiscale) != 16:
        errors["codice_fiscale"] = "Il codice fiscale deve avere 16 caratteri."
    if errors:
        return _json_validation_error("Completa nome, cognome e codice fiscale.", errors, status=400)

    try:
        cliente = get_clienti().nuovo(
            TipoCliente.PERSONA_FISICA,
            nome=nome,
            cognome=cognome,
            codice_fiscale=codice_fiscale,
        )
    except ValueError as exc:
        message = _voice_cliente_error_message(exc)
        return _json_validation_error(message, {"codice_fiscale": message}, status=400)

    _sync_event("crea", "clienti", cliente.id)
    _audit_event(
        "clienti.voce.crea",
        "cliente",
        cliente.id,
        "Cliente aggiunto tramite assistente vocale Studio.",
    )
    label = str(getattr(cliente, "nome_completo", "") or f"{cognome} {nome}".strip())
    return jsonify({
        "ok": True,
        "id": cliente.id,
        "message": f"Cliente {label} aggiunto.",
        "redirect": f"/clienti/{cliente.id}",
    }), 201


@api_v1_react.get("/clienti/nuovo")
@_richiedi_auth
def clienti_react_nuovo():
    return jsonify(build_react_clienti_nuovo_payload(
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        query=request.args,
    ))


@api_v1_react.post("/clienti/nuovo/documento/leggi")
@_richiedi_auth
def clienti_react_nuovo_documento_leggi():
    try:
        result = read_client_document_upload(request.files.get("file"))
        return jsonify(result), 200 if result.get("ok") else 422
    except ClientDocumentReaderError as exc:
        message = exc.public_message
        return jsonify({
            "ok": False,
            "message": message,
            "patch": {},
            "fields": [],
            "missing": [],
            "warnings": [message],
        }), exc.status_code


@api_v1_react.get("/territorio/comuni")
@_richiedi_auth
def territorio_react_comuni():
    query = str(request.args.get("q", "") or "").strip()
    try:
        limit = min(50, max(1, int(request.args.get("limit", 20) or 20)))
    except ValueError:
        limit = 20
    comuni = [comune.to_dict() for comune in search_comuni(query, limit=limit)]
    return jsonify({
        "ok": True,
        "query": query,
        "total": len(comuni),
        "items": comuni,
    })


@api_v1_react.get("/clienti/<id_cliente>/cartella")
@_richiedi_auth
def cliente_cartella_react(id_cliente: str):
    try:
        return jsonify(build_react_cliente_cartella_payload(
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
            get_agenda=get_agenda,
            get_messaggi=_messaggi_manager,
            get_scadenziario=get_scadenziario,
            get_preventivi=get_preventivi_readonly,
            get_fatturazione=get_fatturazione,
            id_cliente=id_cliente,
        ))
    except KeyError:
        return jsonify({"errore": "Cliente non trovato.", "codice": 404}), 404


@api_v1_react.get("/clienti/<id_cliente>/modifica")
@_richiedi_auth
def cliente_modifica_react(id_cliente: str):
    try:
        return jsonify(build_react_cliente_modifica_payload(
            get_clienti=get_clienti,
            get_soggetti=get_soggetti,
            id_cliente=id_cliente,
            query=request.args,
        ))
    except KeyError:
        return jsonify({"errore": "Cliente non trovato.", "codice": 404}), 404


@api_v1_react.get("/soggetti")
@_richiedi_auth
def soggetti_react_list():
    return jsonify(build_react_soggetti_payload(
        get_soggetti=get_soggetti,
        get_clienti=get_clienti,
    ))


def _soggetti_public_register_db(kind: str) -> Path:
    if kind == "registro_ppaa":
        configured_path = (
            current_app.config.get("REGISTRO_PPAA_CACHE_DB")
            or os.environ.get("IUSENTRA_REGISTRO_PPAA_CACHE_DB")
            or ""
        )
        return Path(configured_path) if str(configured_path).strip() else default_registro_ppaa_cache_db_path()
    configured_path = (
        current_app.config.get("REGINDE_CACHE_DB")
        or os.environ.get("IUSENTRA_REGINDE_CACHE_DB")
        or ""
    )
    return Path(configured_path) if str(configured_path).strip() else default_reginde_cache_db_path()


def _split_register_person_name(item: Mapping[str, Any]) -> tuple[str, str]:
    nome = str(item.get("nomeAnagrafico") or "").strip()
    cognome = str(item.get("cognomeAnagrafico") or "").strip()
    if nome or cognome:
        return nome, cognome
    label = str(item.get("nome") or item.get("label") or "").strip()
    parts = [part for part in label.split() if part]
    if len(parts) >= 2:
        return parts[0].title(), " ".join(parts[1:]).title()
    return label.title(), ""


def _soggetti_register_result(item: Mapping[str, Any]) -> dict[str, Any]:
    source = str(item.get("fontePecSuggerita") or "").strip()
    role = str(item.get("ruolo") or "").strip().casefold()
    label = str(item.get("nome") or item.get("label") or item.get("pec") or "").strip()
    identity = str(item.get("codiceFiscalePiva") or "").strip().upper()
    is_pa = source == "registro_ppaa" or role == "pa" or "avvocatura" in label.casefold()
    tipo = "PUBBLICA_AMMINISTRAZIONE" if is_pa else "PROFESSIONISTA"
    nome, cognome = _split_register_person_name(item)
    subject_patch = {
        "tipo": tipo,
        "nome": "" if is_pa else nome,
        "cognome": "" if is_pa else cognome,
        "ragione_sociale": label if is_pa else "",
        "codice_fiscale": identity,
        "partita_iva": identity if is_pa and identity.isdigit() and len(identity) == 11 else "",
        "qualifica": "CONTROPARTE" if is_pa else "DIFENSORE_CONTROPARTE",
        "pec": str(item.get("pec") or "").strip().lower(),
        "email": "",
        "telefono": "",
        "ordine": "ReGIndE" if source == "reginde" and not is_pa else "",
        "note": f"Importato da {'Registro PP.AA.' if source == 'registro_ppaa' else 'ReGIndE'} locale certificato.",
        "tag": "registro-ppaa" if source == "registro_ppaa" else "reginde",
    }
    return {
        "id": str(item.get("id") or ""),
        "label": label,
        "registry": source,
        "registryLabel": "Registro PP.AA." if source == "registro_ppaa" else "ReGIndE",
        "taxCode": identity,
        "pec": str(item.get("pec") or "").strip().lower(),
        "role": str(item.get("ruolo") or ""),
        "updatedAt": str(item.get("aggiornatoIl") or ""),
        "cacheSource": str(item.get("cacheSource") or ""),
        "subjectPatch": subject_patch,
    }


@api_v1_react.get("/soggetti/registri-pubblici")
@_richiedi_auth
def soggetti_registri_pubblici_cache():
    query = str(request.args.get("q") or request.args.get("query") or "").strip()
    selected_registry = str(request.args.get("registro") or request.args.get("registry") or "tutti").strip().lower().replace("-", "_")
    if selected_registry in {"ppaa", "pa", "registro_pa", "registro_paa", "registro_pubbliche_amministrazioni", "ipa"}:
        selected_registry = "registro_ppaa"
    if selected_registry not in {"reginde", "registro_ppaa"}:
        selected_registry = "tutti"
    try:
        limit = int(request.args.get("limit") or 12)
    except (TypeError, ValueError):
        limit = 12
    safe_limit = max(1, min(limit, 20))
    reginde = search_reginde_cache(_soggetti_public_register_db("reginde"), query, limit=safe_limit)
    ppaa = search_registro_ppaa_cache(_soggetti_public_register_db("registro_ppaa"), query, limit=safe_limit)
    payloads_by_registry = {"reginde": reginde, "registro_ppaa": ppaa}
    selected_payloads = [payloads_by_registry[selected_registry]] if selected_registry != "tutti" else [reginde, ppaa]
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in selected_payloads:
        for item in payload.get("results") or []:
            row = _soggetti_register_result(item)
            key = "|".join([row["registry"], row["taxCode"], row["pec"], row["label"]]).casefold()
            if key in seen:
                continue
            seen.add(key)
            results.append(row)
            if len(results) >= safe_limit:
                break
        if len(results) >= safe_limit:
            break
    scope_label = {
        "reginde": "ReGIndE",
        "registro_ppaa": "Registro PP.AA.",
    }.get(selected_registry, "ReGIndE e Registro PP.AA.")
    message = ""
    if len(query) < 3:
        message = f"Digita almeno 3 caratteri per cercare in {scope_label}."
    elif not results:
        message = f"Nessun soggetto trovato nella cache locale {scope_label}."
    return jsonify({
        "ok": True,
        "source": "registri_pubblici_cache_locale",
        "available": any(bool(payload.get("available")) for payload in selected_payloads),
        "complete": all(bool(payload.get("complete")) for payload in selected_payloads),
        "selectedRegistry": selected_registry,
        "message": message,
        "registries": [
            {
                "id": "reginde",
                "label": "ReGIndE",
                "available": bool(reginde.get("available")),
                "complete": bool(reginde.get("complete")),
                "records": int(reginde.get("records") or 0),
                "updatedAt": str(reginde.get("updatedAt") or ""),
            },
            {
                "id": "registro_ppaa",
                "label": "Registro PP.AA.",
                "available": bool(ppaa.get("available")),
                "complete": bool(ppaa.get("complete")),
                "records": int(ppaa.get("records") or 0),
                "updatedAt": str(ppaa.get("updatedAt") or ""),
            },
        ],
        "results": results,
    })


@api_v1_react.post("/soggetti/delete")
@_richiedi_auth
def soggetti_react_delete():
    payload, error = _request_json_object()
    if error:
        return error
    ids = [str(item or "").strip() for item in list(payload.get("ids") or []) if str(item or "").strip()]
    if not ids:
        return _json_validation_error("Seleziona almeno un soggetto da eliminare.", {"ids": "Nessun soggetto selezionato."}, status=400)
    soggetti_repo = get_soggetti()
    deleted: list[str] = []
    missing: list[str] = []
    for soggetto_id in ids:
        try:
            soggetto = soggetti_repo.get(soggetto_id)
            nome = str(getattr(soggetto, "nome_completo", "") or "").strip()
            soggetti_repo.elimina(soggetto_id)
            _audit_event("soggetti.elimina", "soggetto", soggetto_id, nome)
            deleted.append(soggetto_id)
        except KeyError:
            missing.append(soggetto_id)
    if not deleted:
        return jsonify({"ok": False, "message": "Nessun soggetto eliminato.", "deleted": [], "missing": missing}), 404
    if len(deleted) == 1:
        message = "Soggetto eliminato."
    else:
        message = f"{len(deleted)} soggetti eliminati."
    return jsonify({"ok": True, "message": message, "deleted": deleted, "missing": missing})


@api_v1_react.get("/soggetti/<id_soggetto>/modifica")
@_richiedi_auth
def soggetto_modifica_react(id_soggetto: str):
    try:
        return jsonify(build_react_soggetto_modifica_payload(
            get_clienti=get_clienti,
            get_soggetti=get_soggetti,
            id_soggetto=id_soggetto,
            query=request.args,
        ))
    except KeyError:
        return jsonify({"errore": "Soggetto non trovato.", "codice": 404}), 404


@api_v1_react.get("/email")
@_richiedi_auth
def email_react_list():
    response = jsonify(build_react_email_payload(
        db_path=_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"),
        messaggi_db=_tenant_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
        base_path="/email",
        compose_path="/email/scrivi",
        settings_path="/impostazioni?tab=pec",
        sync_path="/email/sincronizza",
        auto_esiti_path="/email/auto-esiti",
        local_test_path="/impostazioni?tab=pec",
        lex_context="email-pec",
        include_telematic=True,
        folder=request.args.get("cartella", "INBOX"),
        query=request.args.get("q", "").strip(),
        stato=request.args.get("stato", "").strip().upper(),
        solo_pst=request.args.get("pst") == "1",
        con_allegati=request.args.get("con_allegati") == "1",
        stato_pct=request.args.get("stato_pct", "").strip().upper(),
        origine=request.args.get("origine", "").strip().upper(),
        data_da=request.args.get("data_da", "").strip(),
        data_a=request.args.get("data_a", "").strip(),
        tenant_id=_tenant_runtime_label(),
    ))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@api_v1_react.get("/email/messaggio/<id_email>")
@_richiedi_auth
def email_react_detail(id_email: str):
    payload = build_react_email_detail_payload(
        db_path=_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"),
        id_email=id_email,
        base_path="/email",
        compose_path="/email/scrivi",
        settings_path="/impostazioni?tab=pec",
        include_telematic=True,
        tenant_id=_tenant_runtime_label(),
    )
    if payload is None:
        return jsonify({"errore": "Messaggio non trovato."}), 404
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _email_bulk_action(
    *,
    db_key: str,
    default_db_path: str,
    resource_prefix: str,
) -> Any:
    payload, error = _request_json_object()
    if error:
        return error
    ids = [str(item or "").strip() for item in list(payload.get("ids") or []) if str(item or "").strip()]
    if not ids:
        return _json_validation_error("Seleziona almeno un messaggio.", {"ids": "Nessun messaggio selezionato."}, status=400)
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"trash", "delete"}:
        return _json_validation_error("Azione multipla non valida.", {"action": "Azione non riconosciuta."}, status=400)

    gestore = GestioneEmailRicevute(db_path=_tenant_cfg_value(db_key, default_db_path))
    if action == "trash":
        result = gestore.sposta_cestino_multipla(ids)
    else:
        result = gestore.elimina_definitivamente_multipla(ids)

    updated = list(result.get("updated") or [])
    missing = list(result.get("missing") or [])
    skipped = list(result.get("skipped") or [])

    if not updated:
        if action == "trash" and skipped and not missing:
            return jsonify({
                "ok": False,
                "message": "I messaggi selezionati sono già nel cestino.",
                "updated": [],
                "missing": missing,
                "skipped": skipped,
            }), 409
        return jsonify({
            "ok": False,
            "message": "Nessun messaggio aggiornato.",
            "updated": [],
            "missing": missing,
            "skipped": skipped,
        }), 404

    if action == "delete":
        base_message = "Messaggio eliminato definitivamente." if len(updated) == 1 else f"{len(updated)} messaggi eliminati definitivamente."
        audit_action = f"{resource_prefix}.elimina.bulk"
    else:
        base_message = "Messaggio spostato nel cestino." if len(updated) == 1 else f"{len(updated)} messaggi spostati nel cestino."
        audit_action = f"{resource_prefix}.cestino.bulk"
    _audit_event(
        audit_action,
        "email",
        "bulk",
        f"{len(updated)} messaggi; {len(missing)} non trovati; {len(skipped)} già nel cestino",
    )
    if skipped:
        base_message = f"{base_message} {len(skipped)} già presenti nel cestino."
    if missing:
        base_message = f"{base_message} {len(missing)} non trovati."
    return jsonify({
        "ok": True,
        "message": base_message,
        "updated": updated,
        "missing": missing,
        "skipped": skipped,
    })


@api_v1_react.post("/email/bulk-action")
@_richiedi_auth
def email_react_bulk_action():
    return _email_bulk_action(
        db_key="EMAIL_CASELLA_DB",
        default_db_path="./email/casella.json",
        resource_prefix="email",
    )


@api_v1_react.get("/email-ordinaria")
@_richiedi_auth
def email_ordinaria_react_list():
    response = jsonify(build_react_email_payload(
        db_path=_tenant_cfg_value("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"),
        messaggi_db=_tenant_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
        base_path="/email-ordinaria",
        compose_path="/email-ordinaria/scrivi",
        settings_path="/impostazioni?tab=smtp",
        sync_path="/email-ordinaria/sincronizza",
        auto_esiti_path="",
        local_test_path="/impostazioni?tab=smtp",
        lex_context="email-ordinaria",
        include_telematic=False,
        folder=request.args.get("cartella", "INBOX"),
        query=request.args.get("q", "").strip(),
        stato=request.args.get("stato", "").strip().upper(),
        solo_pst=False,
        con_allegati=request.args.get("con_allegati") == "1",
        stato_pct="",
        origine=request.args.get("origine", "").strip().upper(),
        data_da=request.args.get("data_da", "").strip(),
        data_a=request.args.get("data_a", "").strip(),
    ))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@api_v1_react.get("/email-ordinaria/messaggio/<id_email>")
@_richiedi_auth
def email_ordinaria_react_detail(id_email: str):
    payload = build_react_email_detail_payload(
        db_path=_tenant_cfg_value("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"),
        id_email=id_email,
        base_path="/email-ordinaria",
        compose_path="/email-ordinaria/scrivi",
        settings_path="/impostazioni?tab=smtp",
        include_telematic=False,
    )
    if payload is None:
        return jsonify({"errore": "Messaggio non trovato."}), 404
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@api_v1_react.post("/email-ordinaria/bulk-action")
@_richiedi_auth
def email_ordinaria_react_bulk_action():
    return _email_bulk_action(
        db_key="EMAIL_ORDINARIA_DB",
        default_db_path="./email/ordinaria.json",
        resource_prefix="email_ordinaria",
    )


def _notifiche_legali_result_response(result: Any, *, success_message: str):
    payload = sanitize_react_notifiche_legali_payload(result.to_dict())
    payload["message"] = success_message if result.ok else "Controlla i punti bloccanti prima di proseguire."
    if result.ok:
        _audit_event("notifiche_legali.preview", "notifica_legale", "", success_message)
    return jsonify(payload), 200 if result.ok else 400


_NOTIFICHE_MODEL_LABEL_MAX = 120
_NOTIFICHE_MODEL_DESCRIPTION_MAX = 500
_NOTIFICHE_MODEL_BODY_MAX = 24000
_NOTIFICHE_DRAFT_BODY_MAX = 30000
_NOTIFICHE_CLIENT_BODY_MAX = 20000
_NOTIFICHE_SIGNED_RELATA_MAX_BYTES = 20 * 1024 * 1024
_NOTIFICHE_MANUAL_RECIPIENT_TAG = "notifiche-legali-manuale"
_NOTIFICHE_LOCAL_PEC_MAX_TOTAL_BYTES = 100 * 1024 * 1024
_NOTIFICHE_LOCAL_PEC_ENDPOINT = f"{LOCAL_SIGNER_BASE_URL}/pec/send"


class _NotificheLocalPecError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        blockers: Iterable[Any] | None = None,
        status: int = 400,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.blockers = [
            _notifiche_text(item)
            for item in (blockers or [message])
            if _notifiche_text(item)
        ] or [message]
        self.status = status
        self.payload = dict(payload or {})


def _json_payload_or_error() -> tuple[dict[str, Any] | None, Any | None]:
    payload, error = _request_json_object()
    return payload, error


def _notifiche_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _notifiche_pec(value: Any) -> str:
    return _notifiche_text(value).lower()


def _notifiche_manual_source(value: Any) -> str:
    source = normalise_public_register(value or "ini_pec")
    if source == "ipa":
        source = "registro_ppaa"
    return source if source in PUBLIC_PEC_REGISTERS else "ini_pec"


def _notifiche_manual_role(value: Any, source: str) -> str:
    raw = _notifiche_text(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "pubblica_amministrazione": "pa",
        "p_a": "pa",
        "difensore_avversario": "difensore",
        "difensore_controparte": "difensore",
    }
    role = aliases.get(raw, raw)
    if role in LEGAL_RECIPIENT_ROLES:
        return role
    if source == "registro_ppaa":
        return "pa"
    if source == "reginde":
        return "difensore"
    return "controparte"


def _notifiche_subject_type(role: str, source: str, identity: str, label: str) -> TipoSoggetto:
    normalized_label = normalizza_nome_anagrafico(label)
    if role == "pa" or source == "registro_ppaa":
        return TipoSoggetto.PUBBLICA_AMMINISTRAZIONE
    if role in {"difensore", "professionista"}:
        return TipoSoggetto.PROFESSIONISTA
    if role == "impresa" or (identity.isdigit() and len(identity) == 11):
        return TipoSoggetto.PERSONA_GIURIDICA
    if any(token in normalized_label for token in ("srl", "spa", "societa", "ministero", "comune", "agenzia", "ufficio")):
        return TipoSoggetto.PERSONA_GIURIDICA
    if len(identity) == 16:
        return TipoSoggetto.PERSONA_FISICA
    return TipoSoggetto.PERSONA_GIURIDICA


def _notifiche_subject_qualifica(role: str) -> str:
    return {
        "pa": RuoloSoggetto.CONTROPARTE.value,
        "controparte": RuoloSoggetto.CONTROPARTE.value,
        "difensore": RuoloSoggetto.DIFENSORE_CONTROPARTE.value,
        "impresa": RuoloSoggetto.CONTROPARTE.value,
        "professionista": RuoloSoggetto.ALTRO.value,
        "terzo": RuoloSoggetto.ALTRO.value,
    }.get(role, RuoloSoggetto.ALTRO.value)


def _notifiche_party_role(role: str) -> RuoloSoggetto:
    if role == "difensore":
        return RuoloSoggetto.DIFENSORE_CONTROPARTE
    if role in {"controparte", "impresa", "pa"}:
        return RuoloSoggetto.CONTROPARTE
    return RuoloSoggetto.ALTRO


def _notifiche_person_fields(label: str) -> dict[str, str]:
    parts = [part for part in _notifiche_text(label).split(" ") if part]
    if len(parts) >= 2:
        return {"cognome": parts[0], "nome": " ".join(parts[1:])}
    return {"cognome": "", "nome": label}


def _notifiche_subject_payload_fields(
    *,
    tipo: TipoSoggetto,
    label: str,
    identity: str,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "codice_fiscale": identity,
        "partita_iva": identity if identity.isdigit() and len(identity) == 11 else "",
    }
    if tipo in {
        TipoSoggetto.PERSONA_GIURIDICA,
        TipoSoggetto.PUBBLICA_AMMINISTRAZIONE,
        TipoSoggetto.ENTE,
        TipoSoggetto.CONDOMINIO,
        TipoSoggetto.ASSOCIAZIONE,
    }:
        fields["ragione_sociale"] = label
        return fields
    fields.update(_notifiche_person_fields(label))
    return fields


def _notifiche_subject_name_missing(soggetto: Any) -> bool:
    current = _notifiche_text(getattr(soggetto, "nome_completo", ""))
    normalized = current.replace("-", "").replace("—", "").strip()
    return not normalized


def _notifiche_manual_tags(source: str) -> list[str]:
    return [
        _NOTIFICHE_MANUAL_RECIPIENT_TAG,
        "notifiche-legali",
        f"pubblico-elenco:{source}",
    ]


def _notifiche_merge_tags(existing: Iterable[Any], source: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in list(existing or []) + _notifiche_manual_tags(source):
        text_value = _notifiche_text(value)
        if not text_value or text_value.casefold() in seen:
            continue
        if text_value.casefold().startswith("pubblico-elenco:") and text_value != f"pubblico-elenco:{source}":
            continue
        seen.add(text_value.casefold())
        tags.append(text_value)
    return tags


def _notifiche_manual_note(*, source: str, represented: str) -> str:
    source_label = PUBLIC_PEC_REGISTERS.get(source, source)
    note = f"Inserito manualmente da Notifiche legali. Fonte PEC dichiarata: {source_label}."
    if represented:
        note += f" Parte rappresentata: {represented}."
    return note


def _notifiche_find_manual_subject(repo: Any, *, pec: str, identity: str, label: str) -> Any | None:
    subjects = list(_safe("soggetti", lambda: repo.tutti(), []))
    for soggetto in subjects:
        current_pec = _notifiche_pec(getattr(getattr(soggetto, "recapiti", None), "pec", ""))
        if current_pec and current_pec == pec:
            return soggetto
    if identity:
        for soggetto in subjects:
            current_pec = _notifiche_pec(getattr(getattr(soggetto, "recapiti", None), "pec", ""))
            if current_pec and current_pec != pec:
                continue
            values = {
                normalizza_identificativo_anagrafico(getattr(soggetto, "codice_fiscale", "")),
                normalizza_identificativo_anagrafico(getattr(soggetto, "partita_iva", "")),
                normalizza_identificativo_anagrafico(getattr(soggetto, "identificativo", "")),
            }
            if identity in values:
                return soggetto
    label_key = normalizza_nome_anagrafico(label)
    if label_key:
        for soggetto in subjects:
            current_pec = _notifiche_pec(getattr(getattr(soggetto, "recapiti", None), "pec", ""))
            if current_pec:
                continue
            if normalizza_nome_anagrafico(getattr(soggetto, "nome_completo", "")) == label_key:
                return soggetto
    return None


def _notifiche_update_manual_subject(
    repo: Any,
    soggetto: Any,
    *,
    label: str,
    pec: str,
    identity: str,
    role: str,
    source: str,
    represented: str,
) -> Any:
    tipo = getattr(soggetto, "tipo", None) or _notifiche_subject_type(role, source, identity, label)
    recapiti = getattr(soggetto, "recapiti", None) or Recapiti()
    recapiti.pec = pec
    fields: dict[str, Any] = {
        "recapiti": recapiti,
        "tag": _notifiche_merge_tags(getattr(soggetto, "tag", []) or [], source),
    }
    if not _notifiche_text(getattr(soggetto, "qualifica", "")):
        fields["qualifica"] = _notifiche_subject_qualifica(role)
    if identity and not _notifiche_text(getattr(soggetto, "codice_fiscale", "")) and not _notifiche_text(getattr(soggetto, "partita_iva", "")):
        if identity.isdigit() and len(identity) == 11 and tipo != TipoSoggetto.PERSONA_FISICA:
            fields["partita_iva"] = identity
        else:
            fields["codice_fiscale"] = identity
    if _notifiche_subject_name_missing(soggetto):
        fields.update(_notifiche_subject_payload_fields(tipo=tipo, label=label, identity=identity))
    note = _notifiche_manual_note(source=source, represented=represented)
    current_note = _notifiche_text(getattr(soggetto, "note", ""))
    if note not in current_note:
        fields["note"] = "\n".join(part for part in (current_note, note) if part)
    return repo.aggiorna(getattr(soggetto, "id", ""), **fields)


def _notifiche_create_manual_subject(
    repo: Any,
    *,
    label: str,
    pec: str,
    identity: str,
    role: str,
    source: str,
    represented: str,
) -> Any:
    tipo = _notifiche_subject_type(role, source, identity, label)
    return repo.crea(
        tipo,
        **_notifiche_subject_payload_fields(tipo=tipo, label=label, identity=identity),
        qualifica=_notifiche_subject_qualifica(role),
        indirizzo=Indirizzo(),
        recapiti=Recapiti(pec=pec),
        id_cliente="",
        note=_notifiche_manual_note(source=source, represented=represented),
        tag=_notifiche_manual_tags(source),
    )


def _notifiche_recipient_from_subject(
    soggetto: Any,
    *,
    role: str,
    source: str,
    represented: str,
) -> dict[str, Any]:
    recapiti = getattr(soggetto, "recapiti", None)
    label = _notifiche_text(getattr(soggetto, "nome_completo", "")) or _notifiche_text(getattr(soggetto, "ragione_sociale", ""))
    return {
        "id": _notifiche_text(getattr(soggetto, "id", "")),
        "label": label,
        "nome": label,
        "codiceFiscalePiva": _notifiche_text(getattr(soggetto, "identificativo", "")),
        "pec": _notifiche_pec(getattr(recapiti, "pec", "")),
        "ruolo": role,
        "ruoloPratica": "Inserito manualmente",
        "fontePecSuggerita": source,
        "parteRappresentata": represented,
        "verificaRichiesta": True,
    }


def _normalise_relata_text_for_comparison(value: str) -> str:
    normalised = unicodedata.normalize("NFKC", str(value or ""))
    normalised = normalised.replace("’", "'").replace("‘", "'").replace("\u00ad", "")
    return re.sub(r"\s+", " ", normalised).strip()


_NOTIFICHE_RELATA_SOURCE_SESSION_KEY = "notifiche_relata_sources"
_NOTIFICHE_RELATA_SOURCE_TTL_SECONDS = 15 * 60
_NOTIFICHE_RELATA_SOURCE_MAX_ROWS = 5


def _notifiche_relata_payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8", errors="ignore")
    return hashlib.sha256(encoded).hexdigest()


def _remember_notifiche_relata_source(payload: Mapping[str, Any], source_sha256: str) -> None:
    source_sha256 = str(source_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        return
    now = time.time()
    raw_rows = session.get(_NOTIFICHE_RELATA_SOURCE_SESSION_KEY)
    rows = raw_rows if isinstance(raw_rows, dict) else {}
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in rows.items():
        if not isinstance(value, Mapping):
            continue
        try:
            created_at = float(value.get("createdAt") or 0)
        except (TypeError, ValueError):
            continue
        if now - created_at <= _NOTIFICHE_RELATA_SOURCE_TTL_SECONDS:
            cleaned[str(key)] = {
                "payloadSha256": str(value.get("payloadSha256") or ""),
                "createdAt": created_at,
            }
    cleaned[source_sha256] = {
        "payloadSha256": _notifiche_relata_payload_digest(payload),
        "createdAt": now,
    }
    kept = dict(
        sorted(cleaned.items(), key=lambda item: float(item[1].get("createdAt") or 0), reverse=True)[
            :_NOTIFICHE_RELATA_SOURCE_MAX_ROWS
        ]
    )
    session[_NOTIFICHE_RELATA_SOURCE_SESSION_KEY] = kept
    session.modified = True


def _notifiche_relata_source_matches_session(payload: Mapping[str, Any], source_sha256: str) -> bool:
    source_sha256 = str(source_sha256 or "").strip().lower()
    rows = session.get(_NOTIFICHE_RELATA_SOURCE_SESSION_KEY)
    if not isinstance(rows, Mapping):
        return False
    row = rows.get(source_sha256)
    if not isinstance(row, Mapping):
        return False
    try:
        created_at = float(row.get("createdAt") or 0)
    except (TypeError, ValueError):
        return False
    if time.time() - created_at > _NOTIFICHE_RELATA_SOURCE_TTL_SECONDS:
        return False
    return True


def _notifiche_expected_source_sha_from_form() -> str:
    source_sha256 = str(request.form.get("expectedSourceSha256") or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        return source_sha256
    return ""


def _extract_pdf_text_for_relata(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _signed_relata_payload_from_form() -> tuple[dict[str, Any] | None, Any | None]:
    raw = str(request.form.get("payload") or "")
    if not raw or len(raw) > 200_000:
        return None, (jsonify({"ok": False, "message": "Dati della relata mancanti o non validi."}), 400)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, (jsonify({"ok": False, "message": "Dati della relata non leggibili."}), 400)
    if not isinstance(payload, dict):
        return None, (jsonify({"ok": False, "message": "Dati della relata non validi."}), 400)
    return payload, None


def _notifiche_custom_templates_path() -> Path:
    log_path = Path(tenant_data_path(
        "NOTIFICHE_LOG",
        current_app.config.get("NOTIFICHE_LOG", "./notifiche/log.json"),
        require_tenant=True,
    ))
    return log_path.parent / "modelli_relata_personalizzati.json"


def _notifiche_relata_drafts_path() -> Path:
    log_path = Path(tenant_data_path(
        "NOTIFICHE_LOG",
        current_app.config.get("NOTIFICHE_LOG", "./notifiche/log.json"),
        require_tenant=True,
    ))
    return log_path.parent / "bozze_relata.json"


def _notifiche_attestation_drafts_path() -> Path:
    log_path = Path(tenant_data_path(
        "NOTIFICHE_LOG",
        current_app.config.get("NOTIFICHE_LOG", "./notifiche/log.json"),
        require_tenant=True,
    ))
    return log_path.parent / "bozze_attestazione.json"


def _load_custom_relata_templates() -> list[dict[str, Any]]:
    path = _notifiche_custom_templates_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("templates") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [
        normalise_custom_template(row)
        for row in rows
        if isinstance(row, dict) and row.get("custom_body")
    ]


def _write_custom_relata_templates(templates: list[dict[str, Any]]) -> None:
    path = _notifiche_custom_templates_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "templates": templates,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_relata_drafts() -> list[dict[str, Any]]:
    path = _notifiche_relata_drafts_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("drafts") if isinstance(payload, dict) else []
    return [item for item in rows if isinstance(item, dict)]


def _write_relata_drafts(drafts: list[dict[str, Any]]) -> None:
    path = _notifiche_relata_drafts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "drafts": drafts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_attestation_drafts() -> list[dict[str, Any]]:
    path = _notifiche_attestation_drafts_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("drafts") if isinstance(payload, dict) else []
    return [item for item in rows if isinstance(item, dict)]


def _write_attestation_drafts(drafts: list[dict[str, Any]]) -> None:
    path = _notifiche_attestation_drafts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "drafts": drafts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _custom_relata_template_option(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": template.get("id", ""),
        "code": template.get("code", "PERS"),
        "label": template.get("label", ""),
        "description": template.get("description", ""),
        "requiresProceeding": bool(template.get("requires_proceeding")),
        "privacyDescription": bool(template.get("privacy_description")),
        "custom": True,
        "previewText": template_preview_text(template),
        "fields": template.get("fields", []),
    }


def _slug_relata_template(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:48] or "modello"


def _augment_custom_relata_payload(payload: dict[str, Any]) -> dict[str, Any]:
    template_id = str(payload.get("template_id") or payload.get("modello_relata") or "").strip()
    if not template_id:
        return payload
    for template in _load_custom_relata_templates():
        if template.get("id") == template_id:
            return {**payload, "template_personalizzato": template}
    return payload


def _local_rome_datetime_seconds() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")


def _stamp_notifica_pec_times(payload: dict[str, Any]) -> dict[str, Any]:
    operation = str(payload.get("operazione") or "").strip()
    if operation not in {"notifica_pec_l53", "invio_pec_l53"}:
        return payload
    stamped = dict(payload)
    now = _local_rome_datetime_seconds()
    if operation == "invio_pec_l53":
        stamped["data_ora_invio_pec"] = now
    return stamped


def _notifiche_error_response(error: _NotificheLocalPecError):
    payload = {
        "ok": False,
        "message": error.message,
        "blockers": error.blockers,
        "warnings": [],
        **error.payload,
    }
    return jsonify(payload), error.status


def _notifiche_payload_draft_guard(payload: Mapping[str, Any]) -> None:
    override_text = str(payload.get("relata_override_text") or "").strip()
    if len(override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        raise _NotificheLocalPecError(
            "La bozza relata modificata è troppo lunga.",
            blockers=["La bozza relata modificata è troppo lunga."],
        )
    attestation_override_text = str(
        payload.get("attestazione_override_text") or payload.get("attestation_override_text") or ""
    ).strip()
    if len(attestation_override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        raise _NotificheLocalPecError(
            "L'attestazione di conformità modificata è troppo lunga.",
            blockers=["L'attestazione di conformità modificata è troppo lunga."],
        )


def _notifiche_rome_now_iso() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).isoformat()


def _notifiche_rome_timestamp(value: Any) -> str:
    text = _notifiche_text(value)
    if not text:
        return _notifiche_rome_now_iso()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        current_app.logger.warning("Timestamp notifica PEC non valido: %s", text)
        return _notifiche_rome_now_iso()
    rome = ZoneInfo("Europe/Rome")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=rome)
    return parsed.astimezone(rome).replace(microsecond=0).isoformat()


def _notifiche_safe_filename(value: Any, fallback: str = "allegato.bin") -> str:
    filename = Path(str(value or fallback or "allegato.bin")).name.strip()
    return filename or fallback


def _notifiche_fascicolo_id(payload: Mapping[str, Any]) -> str:
    return _notifiche_text(
        payload.get("fascicolo_id")
        or payload.get("practice_id")
        or payload.get("practiceId")
        or payload.get("id_fascicolo")
    )


def _notifiche_document_id(raw: Mapping[str, Any]) -> str:
    return _notifiche_text(
        raw.get("document_id")
        or raw.get("documentId")
        or raw.get("id_documento")
        or raw.get("fascicolo_document_id")
    )


def _notifiche_payload_documents(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_items = payload.get("documenti") or payload.get("documents") or []
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, Mapping)]


def _notifiche_find_fascicolo_document(fascicolo: Any, document_id: str) -> Any | None:
    clean_id = _notifiche_text(document_id)
    if not clean_id:
        return None
    for doc in getattr(fascicolo, "documenti", []) or []:
        if _notifiche_text(getattr(doc, "id", "")) == clean_id:
            return doc
    return None


def _notifiche_document_display_name(doc: Any, fallback: str = "allegato.bin") -> str:
    return _notifiche_safe_filename(
        getattr(doc, "nome_originale", "")
        or getattr(doc, "nome", "")
        or getattr(doc, "nome_portale", "")
        or fallback,
        fallback,
    )


def _notifiche_fascicolo_label(fascicolo: Any, payload: Mapping[str, Any]) -> str:
    if fascicolo is None:
        return _notifiche_text(payload.get("quickorganizer_pratica") or payload.get("pratica_codice") or "")
    return _notifiche_text(
        getattr(fascicolo, "numero_pratica", "")
        or getattr(fascicolo, "numero", "")
        or getattr(fascicolo, "titolo", "")
        or getattr(fascicolo, "title", "")
        or getattr(fascicolo, "id", "")
    )


def _notifiche_read_fascicolo_attachment(
    *,
    gestore: Any,
    fascicolo: Any,
    fascicolo_id: str,
    document_id: str,
    attachment_id: str,
    label: str,
    role: str,
    include_content: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    doc = _notifiche_find_fascicolo_document(fascicolo, document_id)
    if doc is None:
        raise _NotificheLocalPecError(
            f"Documento non appartenente al fascicolo: {document_id}.",
            blockers=[f"Documento non appartenente al fascicolo: {document_id}."],
        )
    try:
        content = _pat_read_document_bytes(gestore, fascicolo_id, document_id)
    except FileNotFoundError as exc:
        raise _NotificheLocalPecError(
            f"File documento non trovato nel fascicolo: {document_id}.",
            blockers=[f"File documento non trovato nel fascicolo: {document_id}."],
        ) from exc
    filename = _notifiche_document_display_name(doc, fallback=label or "allegato.bin")
    actual_sha256 = hashlib.sha256(content).hexdigest()
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    attachment = {
        "id": attachment_id,
        "label": label,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(content),
        "sha256": actual_sha256,
        "documentId": document_id,
        "role": role,
        "studioTelematicoArchiveRole": "relata_notifica" if role == "relata" else "originale_notificato",
        "studioTelematicoDisplayName": (
            filename
            if role == "relata"
            else f"{Path(filename).stem} (originale notificato){Path(filename).suffix}"
        ),
    }
    if include_content:
        attachment["content_base64"] = base64.b64encode(content).decode("ascii")
    evidence = {
        "document_role": role,
        "fascicolo_document_id": document_id,
        "content_sha256": actual_sha256,
        "outer_sha256": actual_sha256,
        "original_filename": filename,
        "document_version": "1",
        "authoritative": True,
        "studio_telematico_archive_role": "relata_notifica" if role == "relata" else "originale_notificato",
        "studio_telematico_display_name": (
            filename
            if role == "relata"
            else f"{Path(filename).stem} (originale notificato){Path(filename).suffix}"
        ),
    }
    return attachment, evidence


def _notifiche_relata_document_id(payload: Mapping[str, Any]) -> str:
    direct = _notifiche_text(
        payload.get("relata_firmata_document_id")
        or payload.get("relataFirmataDocumentId")
        or payload.get("signedRelataDocumentId")
    )
    if direct:
        return direct
    raw = payload.get("relata_firmata")
    return _notifiche_text(raw.get("documentId") or raw.get("document_id") or raw.get("id")) if isinstance(raw, Mapping) else ""


def _notifiche_current_signed_relata_document_id(fascicolo: Any, payload: Mapping[str, Any]) -> str:
    fallback_id = ""
    try:
        source_sha256 = hashlib.sha256(generate_relata_pdf_bytes(dict(payload))).hexdigest()
    except Exception:
        source_sha256 = ""
    evidence_tag = f"relata-source-sha256:{source_sha256}" if source_sha256 else ""
    for document in reversed(list(getattr(fascicolo, "documenti", []) or [])):
        tags = {_notifiche_text(tag) for tag in (getattr(document, "tags", []) or [])}
        if (
            "relata-notifica" in tags
            and "firma-verificata" in tags
            and bool(getattr(document, "firmato_digitalmente", False))
        ):
            document_id = _notifiche_text(getattr(document, "id", ""))
            if evidence_tag and evidence_tag in tags:
                return document_id
            if not fallback_id:
                fallback_id = document_id
    return fallback_id


def _notifiche_attestation_document_id(payload: Mapping[str, Any]) -> str:
    direct = _notifiche_text(
        payload.get("attestazione_conformita_document_id")
        or payload.get("attestationDocumentId")
        or payload.get("attestazioneDocumentId")
    )
    if direct:
        return direct
    raw = payload.get("attestazione_conformita")
    return _notifiche_text(raw.get("documentId") or raw.get("document_id") or raw.get("id")) if isinstance(raw, Mapping) else ""


def _notifiche_procura_document_id(payload: Mapping[str, Any]) -> str:
    return _notifiche_text(payload.get("procura_document_id") or payload.get("procuraDocumentId"))


def _notifiche_delivery_requires_attachment(delivery_plan: Mapping[str, Any], attachment_id: str) -> bool:
    raw = delivery_plan.get("attachments") or []
    if not isinstance(raw, list):
        return False
    return any(
        isinstance(item, Mapping)
        and _notifiche_text(item.get("id")) == attachment_id
        and bool(item.get("required", True))
        for item in raw
    )


def _notifiche_pec_settings() -> dict[str, Any]:
    try:
        manager = _studio_config_manager()
        config = getattr(manager, "config", manager)
        pec_cfg = getattr(config, "pec", None)
    except Exception as exc:
        raise _NotificheLocalPecError(
            "Configurazione PEC dello studio non disponibile.",
            blockers=["Configurazione PEC dello studio non disponibile."],
        ) from exc
    indirizzo = _notifiche_text(getattr(pec_cfg, "indirizzo", "") if pec_cfg is not None else "")
    smtp_host = _notifiche_text(getattr(pec_cfg, "smtp_host", "") if pec_cfg is not None else "")
    if not indirizzo or not smtp_host:
        raise _NotificheLocalPecError(
            "Configura la PEC dello studio prima dell'invio reale.",
            blockers=["Configura indirizzo PEC e server SMTP in Impostazioni > PEC prima dell'invio reale."],
            payload={"settingsHref": "/impostazioni?tab=pec"},
        )
    username = _notifiche_text(
        getattr(pec_cfg, "username", "")
        or getattr(pec_cfg, "smtp_username", "")
        or getattr(pec_cfg, "pec_username", "")
        or indirizzo
    )
    try:
        smtp_port = int(getattr(pec_cfg, "smtp_port", 465) or 465)
    except (TypeError, ValueError):
        smtp_port = 465
    raw_use_ssl = getattr(pec_cfg, "use_ssl", None)
    use_ssl = bool(raw_use_ssl) if raw_use_ssl is not None else smtp_port == 465
    raw_use_tls = getattr(pec_cfg, "use_tls", None)
    use_tls = bool(raw_use_tls) if raw_use_tls is not None else not use_ssl
    return {
        "indirizzo": indirizzo,
        "username": username,
        "from": indirizzo,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "use_ssl": use_ssl,
        "use_tls": use_tls,
    }


def _notifiche_delivery_reference(delivery_plan: Mapping[str, Any]) -> str:
    reference = _notifiche_text(delivery_plan.get("quickOrganizerReference"))
    notification_id = _notifiche_text(delivery_plan.get("notificationId"))
    if notification_id and f"[Notifica_ID:{notification_id}]" not in reference:
        reference = f"{reference} [Notifica_ID:{notification_id}]".strip()
    return reference


def _notifiche_delivery_body(
    *,
    result_payload: Mapping[str, Any],
    delivery_plan: Mapping[str, Any],
    payload: Mapping[str, Any],
    fascicolo_label: str,
) -> str:
    body = str(
        delivery_plan.get("body")
        or result_payload.get("body")
        or payload.get("corpo_pec")
        or payload.get("body")
        or ""
    ).strip()
    if not body:
        body = "Si trasmettono in allegato gli atti notificati ai sensi della L. 53/1994."
    reference = _notifiche_delivery_reference(delivery_plan)
    if reference and "Riferimento da citare nella risposta:" not in body:
        body = "\n".join([
            body,
            "",
            "--------------------------",
            f"Riferimento da citare nella risposta: {reference}",
            f"Pratica: {fascicolo_label or _notifiche_text(payload.get('pratica_codice')) or 'non indicata'}",
        ]).strip()
    return body


def _notifiche_result_messages(delivery_plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = delivery_plan.get("messages") or []
    if isinstance(raw, list):
        messages = [item for item in raw if isinstance(item, Mapping)]
        if messages:
            return messages
    recipients = delivery_plan.get("recipients") or []
    if not isinstance(recipients, list):
        return []
    subject = _notifiche_text(delivery_plan.get("subject") or delivery_plan.get("studioTelematicoSubject"))
    notification_id = _notifiche_text(delivery_plan.get("notificationId"))
    clean_recipients = [item for item in recipients if isinstance(item, Mapping)]
    return [{
        "messageId": f"{notification_id}-pec-1",
        "notificationId": notification_id,
        "recipientIds": [_notifiche_text(recipient.get("recipientId")) for recipient in clean_recipients],
        "recipientIdentityKeys": [_notifiche_text(recipient.get("recipientIdentityKey")) for recipient in clean_recipients],
        "to": _notifiche_text(delivery_plan.get("studioTelematicoTo")),
        "recipients": clean_recipients,
        "recipient": clean_recipients[0] if clean_recipients else {},
        "subject": subject,
    }]


def _notifiche_prepare_local_pec_context(raw_payload: Mapping[str, Any], *, include_content: bool = True) -> dict[str, Any]:
    _notifiche_payload_draft_guard(raw_payload)
    payload = {
        **dict(raw_payload),
        "operazione": LEGAL_NOTIFICATION_SEND_OPERATION,
        "conferma_invio_pec": True,
        "invio_finale": True,
    }
    payload = _stamp_notifica_pec_times(payload)
    payload = _augment_custom_relata_payload(payload)
    fascicolo_id = _notifiche_fascicolo_id(payload)
    if not fascicolo_id:
        raise _NotificheLocalPecError(
            "Seleziona il fascicolo prima dell'invio PEC reale.",
            blockers=["Seleziona il fascicolo prima dell'invio PEC reale."],
        )
    gestore = get_fascicoli()
    fascicolo = gestore.get(fascicolo_id)
    if fascicolo is None:
        raise _NotificheLocalPecError(
            "Fascicolo non trovato: la PEC non viene inviata senza allegati reali.",
            blockers=["Fascicolo non trovato: la PEC non viene inviata senza allegati reali."],
        )

    if not _notifiche_relata_document_id(payload):
        recovered_relata_id = _notifiche_current_signed_relata_document_id(fascicolo, payload)
        if recovered_relata_id:
            payload["relata_firmata"] = True
            payload["relata_firmata_document_id"] = recovered_relata_id

    result = validate_legal_notification(payload, require_signed_relata=True)
    result_payload = sanitize_react_notifiche_legali_payload(result.to_dict())
    output_plan = dict(result_payload.get("outputPlan") or {})
    delivery_plan = dict(output_plan.get("deliveryPlan") or {})
    if not result.ok:
        raise _NotificheLocalPecError(
            "Completa i dati indicati prima dell'invio PEC reale.",
            blockers=result_payload.get("blockers") or result.blockers,
            payload=result_payload,
        )

    attachments: list[dict[str, Any]] = []
    document_evidence: list[dict[str, Any]] = []
    for index, raw in enumerate(_notifiche_payload_documents(payload), start=1):
        document_id = _notifiche_document_id(raw)
        if not document_id:
            label = _notifiche_safe_filename(raw.get("nome_file") or raw.get("file_originale"), f"documento_{index}.pdf")
            raise _NotificheLocalPecError(
                f"Documento {label} selezionato ma non salvato nel fascicolo.",
                blockers=[f"Documento {label} selezionato ma non salvato nel fascicolo: salvalo o collegalo prima dell'invio reale."],
            )
        attachment, evidence = _notifiche_read_fascicolo_attachment(
            gestore=gestore,
            fascicolo=fascicolo,
            fascicolo_id=fascicolo_id,
            document_id=document_id,
            attachment_id=f"documento_{index}",
            label=_notifiche_text(raw.get("descrizione")) or "Documento da notificare",
            role="notified_act",
            include_content=include_content,
        )
        attachments.append(attachment)
        document_evidence.append(evidence)

    if not attachments:
        raise _NotificheLocalPecError(
            "Seleziona almeno un documento reale del fascicolo da notificare.",
            blockers=["Seleziona almeno un documento reale del fascicolo da notificare."],
        )

    if _notifiche_delivery_requires_attachment(delivery_plan, "attestazione_conformita"):
        attestation_id = _notifiche_attestation_document_id(payload)
        if not attestation_id:
            raise _NotificheLocalPecError(
                "Attestazione di conformità richiesta ma non salvata nel fascicolo.",
                blockers=["Attestazione di conformità richiesta ma non salvata nel fascicolo."],
            )
        attachment, evidence = _notifiche_read_fascicolo_attachment(
            gestore=gestore,
            fascicolo=fascicolo,
            fascicolo_id=fascicolo_id,
            document_id=attestation_id,
            attachment_id="attestazione_conformita",
            label="Attestazione di conformità",
            role="attestation",
            include_content=include_content,
        )
        attachments.append(attachment)
        document_evidence.append(evidence)

    if _notifiche_delivery_requires_attachment(delivery_plan, "procura"):
        procura_id = _notifiche_procura_document_id(payload)
        if not procura_id:
            raise _NotificheLocalPecError(
                "Procura richiesta ma non salvata nel fascicolo.",
                blockers=["Procura richiesta ma non salvata nel fascicolo."],
            )
        attachment, evidence = _notifiche_read_fascicolo_attachment(
            gestore=gestore,
            fascicolo=fascicolo,
            fascicolo_id=fascicolo_id,
            document_id=procura_id,
            attachment_id="procura",
            label="Procura alle liti",
            role="notified_act",
            include_content=include_content,
        )
        attachments.append(attachment)
        document_evidence.append(evidence)

    relata_id = _notifiche_relata_document_id(payload) or _notifiche_current_signed_relata_document_id(fascicolo, payload)
    if not relata_id:
        raise _NotificheLocalPecError(
            "Relata firmata mancante: firma la relata prima dell'invio PEC reale.",
            blockers=["Relata firmata mancante: firma la relata prima dell'invio PEC reale."],
        )
    attachment, evidence = _notifiche_read_fascicolo_attachment(
        gestore=gestore,
        fascicolo=fascicolo,
        fascicolo_id=fascicolo_id,
        document_id=relata_id,
        attachment_id="relata_firmata",
        label="Relata firmata digitalmente",
        role="relata",
        include_content=include_content,
    )
    attachments.append(attachment)
    document_evidence.append(evidence)

    total_size = sum(int(item.get("size_bytes") or 0) for item in attachments)
    if total_size > _NOTIFICHE_LOCAL_PEC_MAX_TOTAL_BYTES:
        raise _NotificheLocalPecError(
            "Gli allegati della notifica superano il limite operativo locale di 100 MB.",
            blockers=["Gli allegati della notifica superano il limite operativo locale di 100 MB."],
            status=413,
        )

    pec_settings = _notifiche_pec_settings()
    fascicolo_label = _notifiche_fascicolo_label(fascicolo, payload)
    body = _notifiche_delivery_body(
        result_payload=result_payload,
        delivery_plan=delivery_plan,
        payload=payload,
        fascicolo_label=fascicolo_label,
    )
    public_attachments = [{key: value for key, value in item.items() if key != "content_base64"} for item in attachments]
    delivery_plan.update({
        "body": body,
        "attachments": public_attachments,
        "localSendOnly": True,
        "localPecReady": True,
        "presidioPecAutomation": {
            "enabled": True,
            "phase": "post_message_id_locale",
            "correlationField": "Notifica_ID",
            "archiveTargets": ["fascicolo", "presidi_notifiche", "agenda", "scadenziario", "topbar", "web_push"],
            "localSendOnly": True,
        },
    })
    output_plan["deliveryPlan"] = delivery_plan
    result_payload["outputPlan"] = output_plan

    local_messages: list[dict[str, Any]] = []
    for index, message in enumerate(_notifiche_result_messages(delivery_plan), start=1):
        recipient = message.get("recipient") if isinstance(message.get("recipient"), Mapping) else {}
        message_recipients = [
            item
            for item in (message.get("recipients") if isinstance(message.get("recipients"), list) else [])
            if isinstance(item, Mapping)
        ]
        to_address = _notifiche_text(message.get("to") or delivery_plan.get("studioTelematicoTo") or (recipient or {}).get("pec"))
        if not to_address:
            raise _NotificheLocalPecError(
                "Destinatario PEC mancante nel piano di invio.",
                blockers=["Destinatario PEC mancante nel piano di invio."],
            )
        local_id = _notifiche_text(message.get("messageId")) or f"{delivery_plan.get('notificationId')}-pec-{index}"
        local_messages.append({
            "id": local_id,
            "messageId": local_id,
            "notificationId": _notifiche_text(delivery_plan.get("notificationId")),
            "endpoint": _NOTIFICHE_LOCAL_PEC_ENDPOINT,
            "requiresPassword": True,
            "requires_password": True,
            "channel": "local_signer",
            "recipient": recipient,
            "recipients": message_recipients,
            "payload": {
                **pec_settings,
                "to": to_address,
                "cc": [],
                "bcc": [],
                "subject": _notifiche_text(message.get("subject") or delivery_plan.get("subject") or delivery_plan.get("studioTelematicoSubject")),
                "body": body,
                "attachments": attachments,
            },
        })

    if not local_messages:
        raise _NotificheLocalPecError(
            "Nessun destinatario PEC nel piano di invio.",
            blockers=["Nessun destinatario PEC nel piano di invio."],
        )
    result_payload.update({
        "ok": True,
        "message": "Invio PEC pronto sul PC locale con tutti i destinatari selezionati.",
        "requiresLocalPec": True,
        "localPecMessages": local_messages,
        "notificationId": _notifiche_text(delivery_plan.get("notificationId")),
    })
    return {
        "payload": payload,
        "resultPayload": result_payload,
        "deliveryPlan": delivery_plan,
        "localMessages": local_messages,
        "attachments": public_attachments,
        "documents": document_evidence,
        "fascicoloId": fascicolo_id,
        "fascicoloLabel": fascicolo_label,
    }


def _notifiche_public_recipient(recipient: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "recipient_identity_key": _notifiche_text(recipient.get("recipientIdentityKey") or recipient.get("recipient_identity_key")),
        "name": _notifiche_text(recipient.get("name") or recipient.get("nome")),
        "fiscal_id": _notifiche_text(
            recipient.get("fiscalId")
            or recipient.get("fiscal_id")
            or recipient.get("codice_fiscale_piva")
            or recipient.get("codiceFiscalePiva")
        ),
        "role": _notifiche_text(recipient.get("role") or recipient.get("ruolo") or recipient.get("tipo")),
        "pec_address": _notifiche_pec(recipient.get("pec") or recipient.get("pec_address")),
        "public_register": _notifiche_text(recipient.get("sourceLabel") or recipient.get("source") or recipient.get("fonte_pec") or recipient.get("public_register")),
        "public_register_verified_at": _notifiche_text(recipient.get("verifiedAt") or recipient.get("verified_at")),
        "required": True,
    }


def _notifiche_confirmation_message_id(row: Mapping[str, Any]) -> str:
    return _notifiche_text(
        row.get("message_id")
        or row.get("messageId")
        or row.get("pecMessageId")
        or row.get("sentMessageId")
    )


def _notifiche_confirmation_local_id(row: Mapping[str, Any]) -> str:
    return _notifiche_text(row.get("localMessageId") or row.get("local_message_id") or row.get("localId") or row.get("messageLocalId"))


def _notifiche_result_rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _notifiche_tenant_ids_for_presidio() -> tuple[str, str]:
    paths = getattr(g, "data_paths", {}) or {}
    tenant = g.get("tenant")
    tenant_object_id = _notifiche_text(getattr(tenant, "id", "") if tenant is not None else "")
    notification_id = _notifiche_text(paths.get("_TENANT_NOTIFICATION_ID") or tenant_object_id or _tenant_runtime_label() or "default")
    presidio_id = _notifiche_text(paths.get("_TENANT_PRESIDIO_ID") or notification_id or tenant_object_id or "default")
    return notification_id or "default", presidio_id or "default"


def _notifiche_runtime_paths_for_presidio() -> dict[str, Any]:
    paths: dict[str, Any] = {
        key: value
        for key, value in current_app.config.items()
        if isinstance(value, (str, int, float, bool))
    }
    paths.update(getattr(g, "data_paths", {}) or {})
    paths.setdefault("PEC_AUDIT_DB", str(_pec_audit_db_path_for_request()))
    if not _notifiche_text(paths.get("NOTIFICATIONS_DB")):
        email_db = Path(str(paths.get("EMAIL_CASELLA_DB") or _tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json")))
        paths["NOTIFICATIONS_DB"] = str(email_db.parent.parent / "notifications" / "notifications.db")
    return paths


def _notifiche_create_presidio_from_confirmation(
    context: Mapping[str, Any],
    sent_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    from pct.pec_notification_presidio import (
        NotificationPresidioRepository,
        NotificationPresidioService,
        NotificationReceiptEnvelope,
        PecNotificationReconciler,
        ReceiptKind,
    )
    from web.services.notifications_runtime import materialize_selected_advanced_notification_presidia_for_paths

    paths = _notifiche_runtime_paths_for_presidio()
    tenant_notification_id, tenant_presidio_id = _notifiche_tenant_ids_for_presidio()
    db_path = Path(str(paths.get("PEC_AUDIT_DB") or _pec_audit_db_path_for_request()))
    repo = NotificationPresidioRepository(db_path, tenant_id=tenant_presidio_id)
    try:
        delivery_plan = context["deliveryPlan"]
        recipients = [
            _notifiche_public_recipient(item)
            for item in (delivery_plan.get("recipients") or [])
            if isinstance(item, Mapping)
        ]
        if not recipients:
            raise _NotificheLocalPecError(
                "Destinatari non disponibili per il presidio notifiche.",
                blockers=["Destinatari non disponibili per il presidio notifiche."],
            )
        first_message_id = sent_rows[0]["messageId"]
        now_iso = _notifiche_rome_now_iso()
        first_sent_at = _notifiche_rome_timestamp(sent_rows[0].get("sentAt") or now_iso)
        documents = [
            {
                **dict(item),
                "source_message_id": first_message_id,
            }
            for item in (context.get("documents") or [])
            if isinstance(item, Mapping)
        ]
        candidate = NotificationPresidioService(repo).create_candidate({
            "fascicolo_id": context.get("fascicoloId"),
            "source_message_id": first_message_id,
            "source_effective_at": first_sent_at,
            "event_or_order_at": first_sent_at,
            "source_order_or_event_id": _notifiche_text(delivery_plan.get("notificationId")),
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "notification_case": "notifica_l53",
            "rulepack_version": "studio-telematico-l53-local-send-v1",
            "priority": "P1",
            "confidence": 1.0,
            "detection_reason": "Invio PEC L. 53 confermato dal Local Signer con Message-ID reale.",
            "notification_instance_document_key": _notifiche_text(delivery_plan.get("notificationId")),
            "live_pec_operational_event": True,
            "channel": "pec",
            "actor": _actor_label(),
            "documents": documents,
            "recipients": recipients,
            "evidence_summary": {
                "source": "local_signer_pec_send",
                "notification_id": _notifiche_text(delivery_plan.get("notificationId")),
                "message_ids": [item["messageId"] for item in sent_rows],
            },
        })
        presidio_id = _notifiche_text(candidate.get("id"))
        reconciler = PecNotificationReconciler(repo)
        reconciliations = []
        recipient_by_pec = {
            _notifiche_pec(item.get("pec_address")): item
            for item in recipients
            if _notifiche_pec(item.get("pec_address"))
        }
        for row in sent_rows:
            row_sent_at = _notifiche_rome_timestamp(row.get("sentAt") or now_iso)
            row_recipients = [
                _notifiche_public_recipient(item)
                for item in (row.get("recipients") or [])
                if isinstance(item, Mapping)
            ] or [
                item
                for pec, item in recipient_by_pec.items()
                if pec and pec in _notifiche_text(row.get("to")).casefold()
            ] or recipients
            for recipient in row_recipients:
                reconciliations.append(reconciler.process(
                    NotificationReceiptEnvelope(
                        kind=ReceiptKind.SENT,
                        message_id=row["messageId"],
                        presidio_id=presidio_id,
                        recipient_address=_notifiche_pec(recipient.get("pec_address")),
                        recipient_name=_notifiche_text(recipient.get("name")),
                        recipient_fiscal_id=_notifiche_text(recipient.get("fiscal_id")),
                        occurred_at=row_sent_at,
                        metadata={
                            "notification_id": _notifiche_text(delivery_plan.get("notificationId")),
                            "local_message_id": _notifiche_text(row.get("localMessageId")),
                            "subject": _notifiche_text(row.get("subject") or delivery_plan.get("subject")),
                            "studio_telematico_to": _notifiche_text(row.get("to")),
                        },
                    ),
                    actor=_actor_label(),
                ))
        publication = materialize_selected_advanced_notification_presidia_for_paths(
            paths,
            tenant_label=_tenant_runtime_label(),
            tenant_id=tenant_notification_id,
            presidio_tenant_id=tenant_presidio_id,
            presidio_ids=[presidio_id],
            database=paths.get("_TENANT_DATABASE_CONFIG"),
        )
        clear_dashboard_payload_cache()
        return {
            "presidioId": presidio_id,
            "created": bool(candidate.get("created")),
            "status": _notifiche_text(reconciliations[-1].get("status") if reconciliations else candidate.get("status")),
            "reconciliations": reconciliations,
            "publication": publication,
            "tenantNotificationId": tenant_notification_id,
            "tenantPresidioId": tenant_presidio_id,
        }
    finally:
        close = getattr(repo, "close", None)
        if callable(close):
            close()


@api_v1_react.get("/notifiche-legali")
@_richiedi_auth
def notifiche_legali_payload():
    config_loader = _core_runtime_func("get_config_studio")
    config_studio = config_loader() if callable(config_loader) else None
    return jsonify(build_react_notifiche_legali_payload(
        config_studio=config_studio,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_soggetti=get_soggetti,
        custom_templates=_load_custom_relata_templates(),
    ))


@api_v1_react.get("/notifiche-legali/pratiche/<id_fascicolo>/documenti")
@_richiedi_auth
def notifiche_legali_pratica_documenti(id_fascicolo: str):
    selected_document_ids: list[str] = []
    for key in ("documenti", "documenti_ids", "id_documento", "id_documenti", "documento"):
        for value in request.args.getlist(key):
            selected_document_ids.extend([part.strip() for part in str(value).split(",") if part.strip()])
    return jsonify(build_react_notifiche_legali_practice_documents_payload(
        id_fascicolo,
        selected_document_ids=selected_document_ids,
        get_fascicoli=get_fascicoli,
    ))


@api_v1_react.get("/notifiche-legali/pratiche/<id_fascicolo>")
@_richiedi_auth
def notifiche_legali_pratica(id_fascicolo: str):
    return jsonify(build_react_notifiche_legali_practice_payload(
        id_fascicolo,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_soggetti=get_soggetti,
    ))


@api_v1_react.get("/notifiche-legali/reginde")
@_richiedi_auth
def notifiche_legali_reginde_cache():
    query = str(request.args.get("q") or request.args.get("query") or "").strip()
    try:
        limit = int(request.args.get("limit") or 25)
    except (TypeError, ValueError):
        limit = 25
    configured_path = (
        current_app.config.get("REGINDE_CACHE_DB")
        or os.environ.get("IUSENTRA_REGINDE_CACHE_DB")
        or ""
    )
    db_path = Path(configured_path) if str(configured_path).strip() else default_reginde_cache_db_path()
    payload = search_reginde_cache(db_path, query, limit=limit)
    return jsonify({
        "ok": True,
        "source": "reginde_cache_locale",
        "available": payload["available"],
        "complete": payload["complete"],
        "records": payload["records"],
        "nextStart": payload["nextStart"],
        "updatedAt": payload.get("updatedAt", ""),
        "message": payload["message"],
        "results": payload["results"],
    })


@api_v1_react.get("/notifiche-legali/registro-ppaa")
@_richiedi_auth
def notifiche_legali_registro_ppaa_cache():
    query = str(request.args.get("q") or request.args.get("query") or "").strip()
    try:
        limit = int(request.args.get("limit") or 25)
    except (TypeError, ValueError):
        limit = 25
    configured_path = (
        current_app.config.get("REGISTRO_PPAA_CACHE_DB")
        or os.environ.get("IUSENTRA_REGISTRO_PPAA_CACHE_DB")
        or ""
    )
    db_path = Path(configured_path) if str(configured_path).strip() else default_registro_ppaa_cache_db_path()
    payload = search_registro_ppaa_cache(db_path, query, limit=limit)
    return jsonify({
        "ok": True,
        "source": "registro_ppaa_cache_locale",
        "available": payload["available"],
        "complete": payload["complete"],
        "records": payload["records"],
        "nextStart": payload["nextStart"],
        "updatedAt": payload.get("updatedAt", ""),
        "message": payload["message"],
        "results": payload["results"],
    })


@api_v1_react.post("/notifiche-legali/verifica-pec-consultata")
@_richiedi_auth
def notifiche_legali_verifica_pec_consultata():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    fascicolo_id = str(payload.get("fascicolo_id") or payload.get("practice_id") or "").strip()
    if not fascicolo_id:
        return jsonify({"ok": False, "message": "Seleziona la pratica prima di verificare l'indirizzo PEC."}), 400
    gestione_fascicoli = get_fascicoli()
    fascicolo = gestione_fascicoli.get(fascicolo_id)
    if fascicolo is None:
        return jsonify({"ok": False, "message": "La pratica selezionata non è disponibile nello studio corrente."}), 404
    actor = _actor_label()
    try:
        evidence = build_public_register_confirmation_evidence(payload, confirmed_by=actor)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    source_snapshot = dict(getattr(fascicolo, "source_snapshot", {}) or {})
    existing_rows = source_snapshot.get("legal_notification_public_register_evidence")
    rows = [dict(item) for item in existing_rows if isinstance(item, dict)] if isinstance(existing_rows, list) else []
    evidence_record = {
        key: evidence[key]
        for key in (
            "source",
            "pec",
            "codice_fiscale",
            "nome",
            "consulted_at",
            "confirmed_at",
            "confirmed_by",
            "official_url",
            "verification_method",
            "evidence_sha256",
            "evidence_body_b64",
        )
    }
    rows = [item for item in rows if item.get("evidence_sha256") != evidence_record["evidence_sha256"]]
    rows.append(evidence_record)
    source_snapshot["legal_notification_public_register_evidence"] = rows[-100:]
    gestione_fascicoli.aggiorna(fascicolo_id, source_snapshot=source_snapshot)
    clear_react_fascicoli_base_cache()
    _sync_event("modifica", "fascicoli", fascicolo_id)
    _audit_event(
        "notifiche_legali.verifica_pec_pubblico_elenco",
        "fascicolo",
        fascicolo_id,
        f"Consultazione {evidence['source']} registrata con soggetto, data, ora e prova verificabile.",
    )
    return jsonify({**evidence, "fascicolo_id": fascicolo_id, "saved_in_practice": True})


@api_v1_react.post("/notifiche-legali/destinatari-manuali")
@_richiedi_auth
def notifiche_legali_salva_destinatario_manuale():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None

    pec = _notifiche_pec(payload.get("pec") or payload.get("destinatario_pec"))
    if not pec or not is_plausible_pec_address(pec):
        return jsonify({"ok": False, "message": "Inserisci un indirizzo PEC valido per salvare il destinatario."}), 400

    label = _notifiche_text(
        payload.get("nome")
        or payload.get("label")
        or payload.get("destinatario_nome")
        or pec
    )
    source = _notifiche_manual_source(payload.get("fontePecSuggerita") or payload.get("fonte_pec") or payload.get("fontePec"))
    role = _notifiche_manual_role(payload.get("ruolo"), source)
    identity = normalizza_identificativo_anagrafico(
        payload.get("codiceFiscalePiva")
        or payload.get("codice_fiscale")
        or payload.get("partita_iva")
    )
    represented = _notifiche_text(payload.get("parteRappresentata") or payload.get("parte_rappresentata"))
    practice_id = _notifiche_text(payload.get("practiceId") or payload.get("practice_id") or payload.get("fascicolo_id"))

    soggetti_repo = get_soggetti()
    existing = _notifiche_find_manual_subject(
        soggetti_repo,
        pec=pec,
        identity=identity,
        label=label,
    )
    if existing is not None:
        soggetto = _notifiche_update_manual_subject(
            soggetti_repo,
            existing,
            label=label,
            pec=pec,
            identity=identity,
            role=role,
            source=source,
            represented=represented,
        )
        created = False
    else:
        soggetto = _notifiche_create_manual_subject(
            soggetti_repo,
            label=label,
            pec=pec,
            identity=identity,
            role=role,
            source=source,
            represented=represented,
        )
        created = True

    linked_to_practice = False
    if practice_id:
        fascicolo = _safe("fascicolo", lambda: get_fascicoli().get(practice_id), None)
        fascicolo_id = (_notifiche_text(getattr(fascicolo, "id", "")) or practice_id) if fascicolo is not None else ""
        if fascicolo_id:
            try:
                soggetti_repo.aggiungi_parte(
                    fascicolo_id,
                    _notifiche_text(getattr(soggetto, "id", "")),
                    _notifiche_party_role(role),
                    represented or label,
                )
                linked_to_practice = True
                _sync_event("modifica", "fascicoli", fascicolo_id)
            except Exception:
                current_app.logger.exception("Destinatario manuale salvato ma non collegato alla pratica %s.", fascicolo_id)

    subject_id = _notifiche_text(getattr(soggetto, "id", ""))
    _sync_event("modifica", "soggetti", subject_id)
    _audit_event(
        "notifiche_legali.destinatario_manuale",
        "soggetto",
        subject_id,
        f"Destinatario PEC manuale {'creato' if created else 'aggiornato'} da Notifiche legali.",
    )
    message = (
        "Destinatario salvato nel database dello studio e aggiunto alla pratica."
        if linked_to_practice
        else "Destinatario salvato nel database dello studio e disponibile nelle prossime notifiche."
    )
    return jsonify({
        "ok": True,
        "message": message,
        "created": created,
        "updated": not created,
        "linkedToPractice": linked_to_practice,
        "subjectId": subject_id,
        "recipient": _notifiche_recipient_from_subject(
            soggetto,
            role=role,
            source=source,
            represented=represented,
        ),
    }), 201 if created else 200


@api_v1_react.post("/notifiche-legali/modelli-relata")
@_richiedi_auth
def notifiche_legali_salva_modello_relata():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    label = str(payload.get("label") or payload.get("nome") or "").strip()
    body = str(payload.get("body") or payload.get("testo") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    description = str(payload.get("description") or payload.get("descrizione") or "").strip()
    if not label:
        return jsonify({"ok": False, "message": "Indica un nome per il modello relata."}), 400
    if len(label) > _NOTIFICHE_MODEL_LABEL_MAX:
        return jsonify({"ok": False, "message": "Il nome del modello relata e' troppo lungo."}), 400
    if len(description) > _NOTIFICHE_MODEL_DESCRIPTION_MAX:
        return jsonify({"ok": False, "message": "La descrizione del modello relata e' troppo lunga."}), 400
    if len(body) < 80:
        return jsonify({"ok": False, "message": "Inserisci il testo del modello con i campi automatici necessari."}), 400
    if len(body) > _NOTIFICHE_MODEL_BODY_MAX:
        return jsonify({"ok": False, "message": "Il testo del modello relata e' troppo lungo."}), 400
    template_blockers = validate_custom_template_body(body)
    if template_blockers:
        return jsonify({"ok": False, "message": "Correggi i campi automatici del modello relata.", "blockers": template_blockers}), 400

    existing = _load_custom_relata_templates()
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    base_slug = _slug_relata_template(label)
    template_id = str(payload.get("id") or "").strip()
    if not template_id:
        template_id = f"relata_personalizzata_{base_slug}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    template = normalise_custom_template({
        "id": template_id,
        "code": "PERS",
        "label": label,
        "description": description or "Modello relata personalizzato dallo studio.",
        "custom_body": body,
        "requires_proceeding": bool(payload.get("requiresProceeding") or payload.get("requires_proceeding")),
        "privacy_description": bool(payload.get("privacyDescription") or payload.get("privacy_description")),
        "created_at": created_at,
        "created_by": _actor_label(),
    })
    merged = [item for item in existing if item.get("id") != template_id]
    merged.append(template)
    _write_custom_relata_templates(merged)
    _audit_event("notifiche_legali.modello_relata", "modello_relata", template_id, f"Salvato modello relata {label}.")
    return jsonify({"ok": True, "message": "Modello relata salvato.", "template": _custom_relata_template_option(template)})


@api_v1_react.post("/notifiche-legali/anteprima-relata")
@_richiedi_auth
def notifiche_legali_anteprima_relata():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    result = preview_legal_relata(_augment_custom_relata_payload(payload))
    if result.get("ok"):
        _audit_event("notifiche_legali.anteprima_relata", "notifica_legale", "", "Anteprima relata compilata generata.")
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/notifiche-legali/attestazione-conformita")
@_richiedi_auth
def notifiche_legali_attestazione_conformita():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    override_text = str(payload.get("attestazione_override_text") or payload.get("attestation_override_text") or "").strip()
    if len(override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({
            "ok": False,
            "message": "L'attestazione di conformità modificata è troppo lunga.",
            "missingFields": [],
        }), 400
    payload = _augment_custom_relata_payload(payload)
    model = build_attestazione_conformita_payload(payload)
    if not model.get("ok"):
        return jsonify({
            "ok": False,
            "message": "Completa i dati indicati prima di scaricare l'attestazione.",
            "missingFields": model.get("missing_fields") or [],
        }), 400

    content = generate_attestazione_conformita_pdf_bytes(payload)

    proceeding = model.get("campi_database", {}).get("procedimento", {})
    rg = re.sub(r"[^0-9]+", "", str(proceeding.get("numero_rg") or ""))
    year = re.sub(r"[^0-9]+", "", str(proceeding.get("anno_rg") or ""))
    suffix = f"_{rg}_{year}" if rg and year else ""
    filename = f"Attestazione_di_conformita{suffix}.pdf"
    _audit_event(
        "notifiche_legali.attestazione_conformita",
        "notifica_legale",
        str(payload.get("pratica_codice") or payload.get("practice_id") or ""),
        "Attestazione di conformità PDF compilata sul modello dello studio.",
    )
    return send_file(
        io.BytesIO(content),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


@api_v1_react.post("/notifiche-legali/attestazione-conformita-fascicolo")
@_richiedi_auth
def notifiche_legali_attestazione_conformita_fascicolo():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    override_text = str(payload.get("attestazione_override_text") or payload.get("attestation_override_text") or "").strip()
    if len(override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({"ok": False, "message": "L'attestazione di conformità modificata è troppo lunga."}), 400
    fascicolo_id = str(payload.get("fascicolo_id") or payload.get("practice_id") or "").strip()
    if not fascicolo_id:
        return jsonify({"ok": False, "message": "Seleziona la pratica prima di salvare l'attestazione."}), 400
    fascicolo = get_fascicoli().get(fascicolo_id)
    if fascicolo is None:
        return jsonify({"ok": False, "message": "La pratica selezionata non è disponibile nello studio corrente."}), 404

    payload = _augment_custom_relata_payload(payload)
    model = build_attestazione_conformita_payload(payload)
    if not model.get("ok"):
        return jsonify({
            "ok": False,
            "message": "Completa i dati indicati prima di salvare l'attestazione.",
            "missingFields": model.get("missing_fields") or [],
        }), 400
    content = generate_attestazione_conformita_pdf_bytes(payload)
    text_hash = hashlib.sha256(str(model.get("text") or "").encode("utf-8")).hexdigest()
    evidence_tag = f"attestazione-conformita-text-sha256:{text_hash}"
    existing = next(
        (
            document
            for document in list(getattr(fascicolo, "documenti", []) or [])
            if evidence_tag in list(getattr(document, "tags", []) or [])
        ),
        None,
    )
    if existing is not None:
        return jsonify({
            "ok": True,
            "message": "Attestazione di conformità già salvata nel fascicolo.",
            "documentId": str(getattr(existing, "id", "")),
            "fileName": str(getattr(existing, "nome", "")),
            "sha256": str(getattr(existing, "hash_contenuto_sha256", "") or getattr(existing, "hash_sha256", "")),
            "previewUrl": f"/fascicoli/{fascicolo_id}/documenti/{getattr(existing, 'id', '')}/visualizza",
            "downloadUrl": f"/fascicoli/{fascicolo_id}/documenti/{getattr(existing, 'id', '')}/scarica",
        })

    proceeding = model.get("campi_database", {}).get("procedimento", {})
    rg = re.sub(r"[^0-9]+", "", str(proceeding.get("numero_rg") or ""))
    year = re.sub(r"[^0-9]+", "", str(proceeding.get("anno_rg") or ""))
    suffix = f"_{rg}_{year}" if rg and year else ""
    filename = f"Attestazione_di_conformita{suffix}.pdf"
    save_document = _fascicoli_runtime_func("salva_documento_fascicolo")
    document = save_document(
        gf=get_fascicoli(),
        id_fasc=fascicolo_id,
        nome_file=filename,
        raw=content,
        tipo_doc=TipoDocumento.NOTIFICA,
        note="Attestazione di conformità generata per la notifica e allegata alla PEC.",
        tags=["attestazione-conformita", "notifica-legale", evidence_tag],
        data_documento=str(payload.get("data_relata") or date.today().isoformat()),
        firmato=False,
        caricato_da=_actor_label(),
        fonte_documento="NOTIFICA_LEGALE",
        nome_originale=filename,
    )
    document_id = str(getattr(document, "id", ""))
    sha256 = str(getattr(document, "hash_contenuto_sha256", "") or hashlib.sha256(content).hexdigest())
    clear_react_fascicoli_base_cache()
    _sync_event("modifica", "fascicoli", fascicolo_id)
    _audit_event(
        "notifiche_legali.attestazione_conformita_fascicolo",
        "fascicolo",
        fascicolo_id,
        f"Attestazione di conformità salvata come documento {document_id}.",
    )
    return jsonify({
        "ok": True,
        "message": "Attestazione di conformità salvata nel fascicolo e pronta come allegato PEC.",
        "documentId": document_id,
        "fileName": str(getattr(document, "nome", filename)),
        "sha256": sha256,
        "previewUrl": f"/fascicoli/{fascicolo_id}/documenti/{document_id}/visualizza",
        "downloadUrl": f"/fascicoli/{fascicolo_id}/documenti/{document_id}/scarica",
    })


@api_v1_react.post("/notifiche-legali/relata-pdf")
@_richiedi_auth
def notifiche_legali_relata_pdf():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    payload = _augment_custom_relata_payload(payload)
    result = validate_legal_notification(payload, require_signed_relata=False)
    if not result.ok:
        return _notifiche_legali_result_response(
            result,
            success_message="Relata pronta per la firma.",
        )
    content = generate_relata_pdf_bytes(payload)
    source_sha256 = hashlib.sha256(content).hexdigest()
    _remember_notifiche_relata_source(payload, source_sha256)
    date_token = re.sub(r"[^0-9]", "", str(payload.get("data_relata") or date.today().isoformat()))[:8]
    filename = f"Relata_di_notificazione_{date_token or date.today().strftime('%Y%m%d')}.pdf"
    _audit_event(
        "notifiche_legali.relata_generata",
        "notifica_legale",
        str(payload.get("fascicolo_id") or payload.get("practice_id") or ""),
        "Relata PDF generata per la firma locale.",
    )
    response = send_file(
        io.BytesIO(content),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )
    response.headers["X-IUSENTRA-Document-SHA256"] = source_sha256
    response.headers["Cache-Control"] = "no-store"
    return response


@api_v1_react.post("/notifiche-legali/relata-firmata")
@_richiedi_auth
def notifiche_legali_relata_firmata():
    payload, error = _signed_relata_payload_from_form()
    if error is not None:
        return error
    assert payload is not None
    payload = _augment_custom_relata_payload(payload)
    fascicolo_id = str(payload.get("fascicolo_id") or payload.get("practice_id") or "").strip()
    if not fascicolo_id:
        return jsonify({"ok": False, "message": "Seleziona la pratica prima di firmare la relata."}), 400
    fascicolo = get_fascicoli().get(fascicolo_id)
    if fascicolo is None:
        return jsonify({"ok": False, "message": "La pratica selezionata non e' disponibile nello studio corrente."}), 404

    result = validate_legal_notification(payload, require_signed_relata=False)
    if not result.ok:
        public = sanitize_react_notifiche_legali_payload(result.to_dict())
        public["message"] = "Completa i dati indicati prima di firmare la relata."
        return jsonify(public), 400

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"ok": False, "message": "File della relata firmata mancante."}), 400
    signed_data = uploaded.read(_NOTIFICHE_SIGNED_RELATA_MAX_BYTES + 1)
    if not signed_data or len(signed_data) > _NOTIFICHE_SIGNED_RELATA_MAX_BYTES:
        return jsonify({"ok": False, "message": "File della relata firmata vuoto o troppo grande."}), 400
    if not str(uploaded.filename).lower().endswith(".p7m"):
        return jsonify({"ok": False, "message": "La firma della relata deve produrre un file CAdES .p7m."}), 400

    from pct.firma import analizza_firma_documento
    from pct.firme_cades import inspect_signed_document_bytes

    inspected = inspect_signed_document_bytes(
        source_name=Path(uploaded.filename).name,
        data=signed_data,
    )
    if not inspected.status.signature_verified or not inspected.payload_bytes:
        return jsonify({"ok": False, "message": "Firma digitale non verificabile: la relata non e' stata salvata."}), 400
    source_pdf = inspected.payload_bytes
    if not source_pdf.startswith(b"%PDF"):
        return jsonify({"ok": False, "message": "Il file firmato non contiene la relata PDF generata da IUSENTRA."}), 400
    source_sha256 = hashlib.sha256(source_pdf).hexdigest()

    signatures = analizza_firma_documento(signed_data, Path(uploaded.filename).name)
    if not signatures or any(bool(item.get("scaduto")) for item in signatures):
        return jsonify({"ok": False, "message": "Il certificato di firma della relata non e' valido alla data del controllo."}), 400

    evidence_tag = f"relata-source-sha256:{source_sha256}"
    existing = next(
        (
            document
            for document in list(getattr(fascicolo, "documenti", []) or [])
            if evidence_tag in list(getattr(document, "tags", []) or [])
            and bool(getattr(document, "firmato_digitalmente", False))
        ),
        None,
    )
    if existing is not None:
        return jsonify({
            "ok": True,
            "message": "Relata gia' firmata e salvata nel fascicolo.",
            "documentId": str(getattr(existing, "id", "")),
            "fileName": str(getattr(existing, "nome", "")),
            "sha256": str(getattr(existing, "hash_contenuto_sha256", "") or getattr(existing, "hash_sha256", "")),
            "sourceSha256": source_sha256,
            "previewUrl": f"/fascicoli/{fascicolo_id}/documenti/{getattr(existing, 'id', '')}/visualizza",
            "downloadUrl": f"/fascicoli/{fascicolo_id}/documenti/{getattr(existing, 'id', '')}/scarica",
            "signatures": signatures,
        })

    recipient = re.sub(r"[^A-Za-z0-9]+", "_", str(payload.get("destinatario_nome") or "destinatario")).strip("_")
    date_token = re.sub(r"[^0-9]", "", str(payload.get("data_relata") or date.today().isoformat()))[:8]
    filename = f"Relata_di_notificazione_{recipient or 'destinatario'}_{date_token or date.today().strftime('%Y%m%d')}.pdf.p7m"
    save_document = _fascicoli_runtime_func("salva_documento_fascicolo")
    document = save_document(
        gf=get_fascicoli(),
        id_fasc=fascicolo_id,
        nome_file=filename,
        raw=signed_data,
        tipo_doc=TipoDocumento.NOTIFICA,
        note="Relata di notificazione firmata digitalmente e verificata.",
        tags=["relata-notifica", "firma-verificata", evidence_tag],
        data_documento=str(payload.get("data_relata") or date.today().isoformat()),
        firmato=True,
        caricato_da=_actor_label(),
        fonte_documento="NOTIFICA_LEGALE",
        nome_originale=filename,
    )
    document_id = str(getattr(document, "id", ""))
    clear_react_fascicoli_base_cache()
    _sync_event("modifica", "fascicoli", fascicolo_id)
    _audit_event(
        "notifiche_legali.relata_firmata",
        "fascicolo",
        fascicolo_id,
        f"Relata firmata verificata e salvata come documento {document_id}.",
    )
    return jsonify({
        "ok": True,
        "message": "Relata firmata e salvata nel fascicolo.",
        "documentId": document_id,
        "fileName": str(getattr(document, "nome", filename)),
        "sha256": hashlib.sha256(signed_data).hexdigest(),
        "sourceSha256": source_sha256,
        "previewUrl": f"/fascicoli/{fascicolo_id}/documenti/{document_id}/visualizza",
        "downloadUrl": f"/fascicoli/{fascicolo_id}/documenti/{document_id}/scarica",
        "signatures": signatures,
    })


@api_v1_react.post("/notifiche-legali/bozze-relata")
@_richiedi_auth
def notifiche_legali_salva_bozza_relata():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    relata_text = str(payload.get("relataText") or payload.get("relata_text") or payload.get("testo") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    template_id = str(payload.get("templateId") or payload.get("template_id") or "").strip()
    practice_id = str(payload.get("practiceId") or payload.get("practice_id") or "").strip()
    payload_hash = str(payload.get("payloadHash") or payload.get("payload_hash") or "").strip()
    if not relata_text:
        return jsonify({"ok": False, "message": "La bozza relata non puo' essere vuota."}), 400
    if len(relata_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({"ok": False, "message": "La bozza relata e' troppo lunga."}), 400
    if not template_id:
        return jsonify({"ok": False, "message": "Seleziona il modello di riferimento della bozza."}), 400
    saved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not payload_hash:
        payload_hash = hashlib.sha256(
            json.dumps(
                {"practiceId": practice_id, "templateId": template_id, "relataText": relata_text},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    draft_id = f"bozza_relata_{saved_at.replace(':', '').replace('-', '')}_{payload_hash[:10]}"
    draft = {
        "id": draft_id,
        "practiceId": practice_id,
        "templateId": template_id,
        "relataText": relata_text,
        "payloadHash": payload_hash,
        "savedAt": saved_at,
        "savedBy": _actor_label(),
    }
    drafts = [item for item in _load_relata_drafts() if item.get("id") != draft_id]
    drafts.append(draft)
    _write_relata_drafts(drafts[-100:])
    _audit_event("notifiche_legali.bozza_relata", "bozza_relata", draft_id, "Bozza relata salvata per la notifica corrente.")
    return jsonify({"ok": True, "message": "Bozza relata salvata per questa notifica.", "draftId": draft_id, "savedAt": saved_at})


@api_v1_react.post("/notifiche-legali/bozze-attestazione")
@_richiedi_auth
def notifiche_legali_salva_bozza_attestazione():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    attestation_text = str(
        payload.get("attestationText")
        or payload.get("attestazioneText")
        or payload.get("attestazione_text")
        or payload.get("testo")
        or ""
    ).replace("\r\n", "\n").replace("\r", "\n").strip()
    template_id = str(payload.get("templateId") or payload.get("template_id") or "").strip()
    practice_id = str(payload.get("practiceId") or payload.get("practice_id") or "").strip()
    payload_hash = str(payload.get("payloadHash") or payload.get("payload_hash") or "").strip()
    if not attestation_text:
        return jsonify({"ok": False, "message": "L'attestazione di conformità non può essere vuota."}), 400
    if len(attestation_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({"ok": False, "message": "L'attestazione di conformità è troppo lunga."}), 400
    if not template_id:
        return jsonify({"ok": False, "message": "Seleziona il modello di riferimento dell'attestazione."}), 400
    saved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not payload_hash:
        payload_hash = hashlib.sha256(
            json.dumps(
                {"practiceId": practice_id, "templateId": template_id, "attestationText": attestation_text},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    draft_id = f"bozza_attestazione_{saved_at.replace(':', '').replace('-', '')}_{payload_hash[:10]}"
    draft = {
        "id": draft_id,
        "practiceId": practice_id,
        "templateId": template_id,
        "attestationText": attestation_text,
        "payloadHash": payload_hash,
        "savedAt": saved_at,
        "savedBy": _actor_label(),
    }
    drafts = [item for item in _load_attestation_drafts() if item.get("id") != draft_id]
    drafts.append(draft)
    _write_attestation_drafts(drafts[-100:])
    _audit_event(
        "notifiche_legali.bozza_attestazione",
        "bozza_attestazione",
        draft_id,
        "Bozza attestazione di conformità salvata per la notifica corrente.",
    )
    return jsonify({
        "ok": True,
        "message": "Attestazione di conformità salvata per questa notifica.",
        "draftId": draft_id,
        "savedAt": saved_at,
    })


@api_v1_react.post("/notifiche-legali/notifica")
@_richiedi_auth
def notifiche_legali_preview():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    override_text = str(payload.get("relata_override_text") or "").strip()
    if len(override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({"ok": False, "message": "La bozza relata modificata e' troppo lunga.", "blockers": ["La bozza relata modificata e' troppo lunga."]}), 400
    attestation_override_text = str(payload.get("attestazione_override_text") or payload.get("attestation_override_text") or "").strip()
    if len(attestation_override_text) > _NOTIFICHE_DRAFT_BODY_MAX:
        return jsonify({
            "ok": False,
            "message": "L'attestazione di conformità modificata è troppo lunga.",
            "blockers": ["L'attestazione di conformità modificata è troppo lunga."],
        }), 400
    payload = _stamp_notifica_pec_times(payload)
    is_send = str(payload.get("operazione") or "").strip() == "invio_pec_l53"
    result = validate_legal_notification(
        _augment_custom_relata_payload(payload),
        require_signed_relata=False,
    )
    return _notifiche_legali_result_response(
        result,
        success_message=(
            "Piano PEC preparato dal PC locale per la notifica corrente."
            if is_send
            else "Relata e controlli L. 53/1994 pronti per la revisione dell'avvocato."
        ),
    )


@api_v1_react.post("/notifiche-legali/invio-pec-locale")
@_richiedi_auth
def notifiche_legali_invio_pec_locale():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    try:
        context = _notifiche_prepare_local_pec_context(payload, include_content=True)
    except _NotificheLocalPecError as exc:
        return _notifiche_error_response(exc)
    result_payload = dict(context["resultPayload"])
    _audit_event(
        "notifiche_legali.invio_pec_locale.preparato",
        "notifica_legale",
        _notifiche_text(result_payload.get("notificationId")),
        "Piano PEC L. 53 preparato per invio dal PC locale.",
    )
    return jsonify(result_payload), 200


@api_v1_react.post("/notifiche-legali/invio-pec-locale/conferma")
@_richiedi_auth
def notifiche_legali_invio_pec_locale_conferma():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    source_payload = payload.get("payload") if isinstance(payload.get("payload"), Mapping) else payload
    if not isinstance(source_payload, Mapping):
        return jsonify({
            "ok": False,
            "message": "Payload notifica mancante per la conferma dell'invio PEC.",
            "blockers": ["Payload notifica mancante per la conferma dell'invio PEC."],
            "warnings": [],
        }), 400
    try:
        context = _notifiche_prepare_local_pec_context(source_payload, include_content=False)
    except _NotificheLocalPecError as exc:
        return _notifiche_error_response(exc)

    delivery_plan = context["deliveryPlan"]
    expected_notification_id = _notifiche_text(delivery_plan.get("notificationId"))
    received_notification_id = _notifiche_text(payload.get("notificationId") or payload.get("notification_id"))
    if received_notification_id and received_notification_id != expected_notification_id:
        return jsonify({
            "ok": False,
            "message": "Notifica_ID non coerente con il piano PEC preparato.",
            "blockers": ["Notifica_ID non coerente con il piano PEC preparato."],
            "warnings": [],
        }), 400

    raw_results = _notifiche_result_rows(payload.get("results") or payload.get("sent") or payload.get("esiti"))
    if not raw_results:
        return jsonify({
            "ok": False,
            "message": "Nessun esito Local Signer ricevuto: la PEC non viene registrata come inviata.",
            "blockers": ["Nessun esito Local Signer ricevuto: la PEC non viene registrata come inviata."],
            "warnings": [],
        }), 400

    results_by_local_id = {
        _notifiche_confirmation_local_id(row): row
        for row in raw_results
        if _notifiche_confirmation_local_id(row)
    }
    sent_rows: list[dict[str, Any]] = []
    seen_message_ids: set[str] = set()
    for index, local_message in enumerate(context["localMessages"]):
        local_id = _notifiche_text(local_message.get("id") or local_message.get("messageId"))
        row = results_by_local_id.get(local_id)
        if row is None and index < len(raw_results):
            row = raw_results[index]
        if row is None:
            return jsonify({
                "ok": False,
                "message": "Manca la conferma Local Signer per un destinatario PEC.",
                "blockers": [f"Manca la conferma Local Signer per il messaggio {local_id}."],
                "warnings": [],
            }), 400
        message_id = _notifiche_confirmation_message_id(row)
        if not message_id:
            return jsonify({
                "ok": False,
                "message": "Message-ID mancante: la PEC non viene registrata come inviata.",
                "blockers": ["Message-ID mancante: la PEC non viene registrata come inviata."],
                "warnings": [],
            }), 400
        if message_id in seen_message_ids:
            return jsonify({
                "ok": False,
                "message": "Message-ID duplicato nella conferma Local Signer.",
                "blockers": ["Message-ID duplicato nella conferma Local Signer."],
                "warnings": [],
            }), 400
        seen_message_ids.add(message_id)
        local_payload = local_message.get("payload") if isinstance(local_message.get("payload"), Mapping) else {}
        sent_at = _notifiche_rome_timestamp(row.get("sentAt") or row.get("sent_at") or row.get("timestamp"))
        sent_rows.append({
            "localMessageId": local_id,
            "messageId": message_id,
            "to": _notifiche_pec(local_payload.get("to")),
            "subject": _notifiche_text(local_payload.get("subject")),
            "sentAt": sent_at,
        })

    try:
        registration = _notifiche_create_presidio_from_confirmation(context, sent_rows)
    except _NotificheLocalPecError as exc:
        return _notifiche_error_response(exc)
    publication = registration.get("publication") if isinstance(registration.get("publication"), Mapping) else {}
    warnings: list[str] = []
    if publication and publication.get("ok") is False:
        warnings.append(
            "PEC inviata e presidio registrato, ma la pubblicazione su Agenda, Scadenziario, top bar o Web Push non è stata completata."
        )
    delivery_recipients = delivery_plan.get("recipients") if isinstance(delivery_plan.get("recipients"), list) else []
    recipient_count = len(delivery_recipients) or len(sent_rows)
    _audit_event(
        "notifiche_legali.invio_pec_locale.confermato",
        "notifica_legale",
        expected_notification_id,
        f"PEC L. 53 confermata dal PC locale con {len(sent_rows)} Message-ID per {recipient_count} destinatari.",
    )
    _sync_event("update", "notifiche_legali", expected_notification_id)
    return jsonify({
        "ok": True,
        "message": (
            f"PEC inviata dal PC locale a {recipient_count} "
            f"{'destinatario' if recipient_count == 1 else 'destinatari'}. "
            "Presidio notifiche aggiornato e pubblicato su Agenda, Scadenziario, top bar e Web Push quando attivo."
        ),
        "blockers": [],
        "warnings": warnings,
        "notificationId": expected_notification_id,
        "presidioId": registration.get("presidioId"),
        "status": registration.get("status"),
        "sent": sent_rows,
        "publication": publication,
        "outputPlan": {
            "deliveryPlan": {
                **dict(delivery_plan),
                "confirmedMessageIds": [item["messageId"] for item in sent_rows],
                "presidioId": registration.get("presidioId"),
                "presidioStatus": registration.get("status"),
            },
            "presidio": registration,
        },
    }), 200


@api_v1_react.post("/notifiche-legali/comunicazione-cliente")
@_richiedi_auth
def notifiche_legali_comunicazione_cliente():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    body_text = str(payload.get("body_override") or payload.get("corpo") or payload.get("body") or "")
    if len(body_text) > _NOTIFICHE_CLIENT_BODY_MAX:
        return jsonify({"ok": False, "message": "Il testo della comunicazione cliente e' troppo lungo.", "blockers": ["Il testo della comunicazione cliente e' troppo lungo."]}), 400
    result = build_client_communication(payload)
    return _notifiche_legali_result_response(
        result,
        success_message="Comunicazione cliente preparata senza relata.",
    )


@api_v1_react.post("/notifiche-legali/unep")
@_richiedi_auth
def notifiche_legali_unep():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    result = validate_unep_notification_request(payload)
    return _notifiche_legali_result_response(
        result,
        success_message="Richiesta UNEP pronta sul canale dedicato.",
    )


@api_v1_react.post("/notifiche-legali/non-pec")
@_richiedi_auth
def notifiche_legali_non_pec():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    result = validate_non_pec_notification_tracking(payload)
    return _notifiche_legali_result_response(
        result,
        success_message="Notifica non PEC tracciata con prova documentale.",
    )


@api_v1_react.post("/notifiche-legali/area-web-pst")
@_richiedi_auth
def notifiche_legali_area_web_pst():
    payload, error = _json_payload_or_error()
    if error is not None:
        return error
    assert payload is not None
    result = prepare_pst_failed_notification_workflow(payload)
    return _notifiche_legali_result_response(
        result,
        success_message="Workflow area web PST preparato per revisione manuale.",
    )


@api_v1_react.get("/messaggi")
@_richiedi_auth
def messaggi_react_list():
    return jsonify(build_react_messaggi_payload(
        get_messaggi=_messaggi_manager,
        get_clienti=get_clienti,
        query=request.args,
        config=current_app.config,
    ))


@api_v1_react.get("/messaggi/nuovo")
@_richiedi_auth
def messaggi_react_nuovo():
    return jsonify(build_react_messaggi_nuovo_payload(
        get_clienti=get_clienti,
        query=request.args,
        config=current_app.config,
    ))


@api_v1_react.get("/scadenziario")
@_richiedi_auth
def scadenziario_react_list():
    email_db_path = Path(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))
    include_calculator = str(request.args.get("calcolatore", request.args.get("include_calculator", "1")) or "1").strip() != "0"
    return jsonify(build_react_scadenziario_payload(
        gestione_scadenziario=get_scadenziario(),
        gestione_fascicoli=get_fascicoli(),
        gestione_utenti=get_utenti(carica_audit=False),
        gestione_agenda=get_agenda(),
        query_args=request.args,
        termini_processuali_db=str(_termini_processuali_repository().path) if include_calculator else "",
        pec_audit_db=str(email_db_path.parent / "pec_audit.sqlite"),
        tenant_id=_tenant_runtime_label(),
    ))


@api_v1_react.get("/scadenziario/nuova")
@_richiedi_auth
def scadenziario_react_nuova():
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    config_loader = core_runtime.get("get_config_studio")
    return jsonify(build_react_scadenziario_nuova_payload(
        fascicoli_loader=get_fascicoli,
        utenti_loader=get_utenti,
        config_loader=config_loader if callable(config_loader) else None,
        scadenziario_loader=get_scadenziario,
        id_scadenza=request.args.get("id_scadenza", "").strip(),
    ))


def _termini_processuali_repository() -> DeadlinePracticeRepository:
    anchor = Path(_cfg_value("SCADENZIARIO_DB", "./scadenziario/scadenze.json"))
    repo = DeadlinePracticeRepository.json(anchor.with_name("termini_processuali.json"))
    _ensure_guida_pratica_terms_repository(repo)
    return repo


_GUIDA_PRATICA_TERMINI_BOOTSTRAPPED: set[str] = set()


def _ensure_guida_pratica_terms_repository(repo: DeadlinePracticeRepository) -> None:
    if repo.backend != "json":
        return
    repo_key = str(repo.path.resolve())
    if repo_key in _GUIDA_PRATICA_TERMINI_BOOTSTRAPPED:
        return
    try:
        from scripts.import_guida_pratica_termini_processuali import bootstrap_guida_pratica_terms_repository

        bootstrap_guida_pratica_terms_repository(repo.path)
    except Exception:
        current_app.logger.warning(
            "Bootstrap termini Guida Pratica non completato",
            exc_info=True,
        )
    finally:
        _GUIDA_PRATICA_TERMINI_BOOTSTRAPPED.add(repo_key)


def _current_user_id() -> str:
    utente = g.get("utente_corrente") or {}
    if isinstance(utente, dict):
        return str(utente.get("id") or utente.get("username") or "").strip()
    return str(getattr(utente, "id", "") or getattr(utente, "username", "") or "").strip()


def _json_body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


def _scadenziario_can_write() -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("scadenziario.scrivi"))


def _positive_int(value: Any, *, default: int = 0, maximum: int = 10000) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 0:
        parsed = 0
    return min(parsed, maximum)


@api_v1_react.get("/scadenziario/pdf-scadenze/anteprima")
@_richiedi_auth
def scadenziario_pdf_scadenze_anteprima():
    id_fascicolo = str(request.args.get("id_fascicolo") or request.args.get("fascicoloId") or "").strip()
    max_documents = _positive_int(request.args.get("max_documents") or request.args.get("maxDocuments"), default=0)
    try:
        preview = preview_pdf_deadlines(
            gestione_fascicoli=get_fascicoli(),
            gestione_scadenziario=get_scadenziario(),
            id_fascicolo=id_fascicolo,
            max_documents=max_documents,
        )
        return jsonify(preview.to_dict())
    except Exception as exc:
        current_app.logger.exception("Anteprima scadenze PDF non riuscita: %s", exc)
        return jsonify({"ok": False, "errore": "Scansione PDF non completata.", "message": "Scansione PDF non completata."}), 400


@api_v1_react.post("/scadenziario/pdf-scadenze/importa")
@_richiedi_auth
def scadenziario_pdf_scadenze_importa():
    if not _scadenziario_can_write():
        return jsonify({"ok": False, "errore": "Permesso insufficiente.", "message": "Permesso insufficiente."}), 403
    payload = _json_body()
    selected_ids = payload.get("selectedIds") or payload.get("ids") or []
    if not isinstance(selected_ids, list):
        selected_ids = []
    id_fascicolo = str(payload.get("id_fascicolo") or payload.get("fascicoloId") or "").strip()
    max_documents = _positive_int(payload.get("max_documents") or payload.get("maxDocuments"), default=0)
    try:
        result = import_pdf_deadlines(
            gestione_fascicoli=get_fascicoli(),
            gestione_scadenziario=get_scadenziario(),
            gestione_agenda=get_agenda(),
            selected_ids=[str(item) for item in selected_ids],
            id_fascicolo=id_fascicolo,
            max_documents=max_documents,
            user_id=_current_user_id(),
        )
        if result.get("ok"):
            _audit_event("scadenziario.importa_pdf", "scadenza", "", str(result.get("message") or ""))
            _sync_event("crea", "scadenze", "pdf-import")
        return _jsonify_public_payload(_pdf_import_public_result(result), 200 if result.get("ok") else 400)
    except Exception as exc:
        current_app.logger.exception("Import scadenze PDF non riuscito: %s", exc)
        return jsonify({"ok": False, "errore": "Importazione PDF non completata.", "message": "Importazione PDF non completata."}), 400


@api_v1_react.get("/scadenziario/termini/templates")
@_richiedi_auth
def scadenziario_termini_templates():
    repo = _termini_processuali_repository()
    raw_templates = repo.list_templates()
    codice_guida = str(request.args.get("guida_pratica") or request.args.get("codice_guida") or "").strip()
    visible_templates = calculator_templates_for_guide(raw_templates, codice_guida) if codice_guida else dedupe_calculator_templates(raw_templates)
    return jsonify({
        "templates": visible_templates,
        "templatesRawCount": len(raw_templates),
        "templatesVisibleCount": len(visible_templates),
        "legalSources": list(LEGAL_SOURCES),
        "endpoints": {
            "calculate": "/api/v1/ui/scadenziario/termini/calculate",
            "explain": "/api/v1/ui/scadenziario/termini/explain",
            "validate": "/api/v1/ui/scadenziario/termini/validate",
            "audit": "/api/v1/ui/scadenziario/termini/audit",
            "override": "/api/v1/ui/scadenziario/termini/override",
            "createDeadline": "/api/v1/ui/scadenziario/termini/crea-scadenza",
        },
    })


@api_v1_react.post("/scadenziario/termini/calculate")
@_richiedi_auth
def scadenziario_termini_calculate():
    try:
        result = calculate_and_audit(
            _json_body(),
            repository=_termini_processuali_repository(),
            user_id=_current_user_id(),
        )
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Calcolo termine processuale non riuscito: %s", exc)
        return jsonify({"ok": False, "errore": "Calcolo termine non completato."}), 400


@api_v1_react.post("/scadenziario/termini/explain")
@_richiedi_auth
def scadenziario_termini_explain():
    return scadenziario_termini_calculate()


@api_v1_react.post("/scadenziario/termini/validate")
@_richiedi_auth
def scadenziario_termini_validate():
    payload = _json_body()
    warnings: list[str] = []
    if not str(payload.get("input_date") or payload.get("inputDate") or "").strip():
        warnings.append("Inserire la data evento generatore.")
    if str(payload.get("ferial_suspension_policy") or "").strip() in {"partial", "manual_review"}:
        warnings.append("La sospensione feriale richiede verifica professionale.")
    if str(payload.get("direction") or "").strip() == "backward":
        warnings.append("Il calcolo a ritroso richiede conferma dell'atto o dell'udienza di riferimento.")
    if bool(payload.get("urgent")):
        warnings.append("Materia urgente: verificare la deroga settoriale prima del deposito.")
    return jsonify({
        "ok": not warnings,
        "warnings": warnings,
        "requiresLegalReview": bool(warnings),
    })


@api_v1_react.get("/scadenziario/termini/audit")
@_richiedi_auth
def scadenziario_termini_audit():
    limit = max(1, min(int(request.args.get("limit", 20) or 20), 100))
    return jsonify({"items": _termini_processuali_repository().list_audit(limit=limit)})


def _parse_italian_deadline_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Rome")).date()
    except Exception:
        try:
            return date.fromisoformat(text[:10])
        except Exception:
            return None


def _deadline_today_rome() -> date:
    return datetime.now(ZoneInfo("Europe/Rome")).date()


def _calculated_deadline_marker(result: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    template = result.get("template") if isinstance(result.get("template"), Mapping) else {}
    digest = hashlib.sha256(
        json.dumps(
            {
                "template": template.get("code") or payload.get("template_code") or payload.get("templateCode"),
                "input_date": result.get("inputDate") or payload.get("input_date") or payload.get("inputDate"),
                "deadline": result.get("deadline"),
                "case": result.get("caseReference") or payload.get("case_reference") or payload.get("caseReference"),
                "fascicolo": payload.get("id_fascicolo") or payload.get("fascicoloId"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"TERMINE_PROCESSUALE:{digest}"


def _sync_calculated_deadline_to_agenda(
    *,
    marker: str,
    title: str,
    deadline_date: str,
    description: str,
    id_fascicolo: str,
) -> dict[str, Any]:
    try:
        from pct.agenda import TipoAppuntamento
        from pct.ical_import import EventoImportato

        event = EventoImportato(
            uid=f"{marker}:agenda",
            titolo=title,
            data_ora=f"{deadline_date}T09:00:00",
            durata_minuti=30,
            tutto_giorno=False,
            descrizione=description,
        )
        report = get_agenda().upsert_da_evento_importato(
            event,
            provider="termini_processuali",
            default_tipo=TipoAppuntamento.SCADENZA,
            reminder_minuti=1440,
        )
        appuntamento = report.get("appuntamento")
        agenda_id = str(getattr(appuntamento, "id", "") or "")
        if agenda_id and id_fascicolo:
            appuntamento = get_agenda().modifica(agenda_id, procedimento=id_fascicolo)
        return {
            "ok": bool(agenda_id),
            "agendaId": agenda_id,
            "agendaHref": f"/agenda/{agenda_id}" if agenda_id else "/agenda",
            "outcome": str(report.get("outcome") or ""),
            "message": "Termine collegato anche all'agenda." if agenda_id else str(report.get("message") or ""),
        }
    except Exception as exc:
        current_app.logger.warning("Agenda non aggiornata per termine processuale: %s", exc)
        return {
            "ok": False,
            "agendaId": "",
            "agendaHref": "/agenda",
            "outcome": "unavailable",
            "message": "Scadenza creata, ma agenda non aggiornata.",
        }


def _validate_current_tenant_fascicolo_id(id_fascicolo: str) -> tuple[bool, dict[str, str] | None]:
    """Blocca riferimenti a fascicoli non presenti nello studio corrente."""

    value = str(id_fascicolo or "").strip()
    if not value:
        return True, None
    try:
        fascicolo = get_fascicoli().get(value)
    except Exception:
        current_app.logger.warning("Validazione fascicolo scadenziario non disponibile.", exc_info=True)
        return False, {
            "ok": False,
            "errore": "Fascicolo non verificabile nello studio corrente.",
            "messaggio": "Fascicolo non verificabile nello studio corrente.",
        }
    if fascicolo:
        return True, None
    return False, {
        "ok": False,
        "errore": "Fascicolo non trovato nello studio corrente.",
        "messaggio": "Fascicolo non trovato nello studio corrente.",
    }


@api_v1_react.post("/scadenziario/termini/override")
@_richiedi_auth
def scadenziario_termini_override():
    payload = _json_body()
    reason = str(payload.get("override_reason") or payload.get("overrideReason") or "").strip()
    if not reason:
        return jsonify({"ok": False, "errore": "Motivazione override obbligatoria."}), 400
    try:
        result = calculate_and_audit(
            payload,
            repository=_termini_processuali_repository(),
            user_id=_current_user_id(),
            is_override=True,
            override_reason=reason,
        )
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Override termine processuale non riuscito: %s", exc)
        return jsonify({"ok": False, "errore": "Override termine non completato."}), 400


@api_v1_react.post("/scadenziario/termini/crea-scadenza")
@_richiedi_auth
def scadenziario_termini_crea_scadenza():
    payload = _json_body()
    try:
        repo = _termini_processuali_repository()
        user_id = _current_user_id()
        result = calculate_and_audit(
            payload,
            repository=repo,
            user_id=user_id,
        )
        template = result["template"]
        title = str(payload.get("title") or payload.get("titolo") or template["name"]).strip()
        due_date = str(result["deadline"])
        id_fascicolo = str(payload.get("id_fascicolo") or payload.get("fascicoloId") or "").strip()
        valid_fascicolo, fascicolo_error = _validate_current_tenant_fascicolo_id(id_fascicolo)
        if not valid_fascicolo:
            return jsonify({**(fascicolo_error or {}), "crossTenantBlocked": True}), 404
        parsed_due_date = _parse_italian_deadline_date(due_date)
        if parsed_due_date and parsed_due_date < _deadline_today_rome():
            return jsonify({
                "ok": False,
                "expired": True,
                "messaggio": "Termine già superato: non riportato in scadenziario o agenda.",
                "deadline": due_date,
                "audit": result["audit"],
            }), 409
        marker = _calculated_deadline_marker(result, payload)
        manager = get_scadenziario()
        existing = next(
            (item for item in manager.tutte(solo_aperte=False) if marker in str(getattr(item, "note", "") or "")),
            None,
        )
        description = str(payload.get("description") or result["explanation"] or "")
        if existing:
            agenda = _sync_calculated_deadline_to_agenda(
                marker=marker,
                title=title,
                deadline_date=due_date,
                description=description,
                id_fascicolo=id_fascicolo,
            )
            agenda_id = str(agenda.get("agendaId") or "")
            if agenda_id and not str(getattr(existing, "id_appuntamento", "") or ""):
                existing = manager.aggiorna(str(getattr(existing, "id", "")), id_appuntamento=agenda_id)
            return jsonify({
                "ok": True,
                "alreadyExists": True,
                "messaggio": "Scadenza processuale già presente: agenda verificata.",
                "id": existing.id,
                "href": f"/scadenziario/{existing.id}",
                "agenda": agenda,
                "audit": result["audit"],
                "notificationsPlanned": 0,
            })
        scadenza = manager.nuova(
            titolo=title,
            tipo=TipoTermine.TERMINE_PERENTORIO,
            data_scadenza=due_date,
            id_fascicolo=id_fascicolo,
            descrizione=description,
            data_decorrenza=str(result["inputDate"]),
            perentorio=True,
            id_utente_responsabile=user_id,
            note=(
                f"{marker}\nCalcolo termini processuali audit "
                + result["audit"]["immutableHash"]
            ),
            source_event_type=str(template.get("metadata", {}).get("source_event") or "evento"),
            source_event_at=str(result["inputDate"]),
            deadline_profile_code=str(template["code"]),
            raw_due_at=str(result["rawDeadline"]),
            legal_due_at=str(result["deadline"]),
            trace_json=json.dumps([step["label"] for step in result["steps"]], ensure_ascii=False),
            giorni_preavviso=[30, 15, 7, 1, 0],
        )
        agenda = _sync_calculated_deadline_to_agenda(
            marker=marker,
            title=title,
            deadline_date=due_date,
            description=description,
            id_fascicolo=id_fascicolo,
        )
        agenda_id = str(agenda.get("agendaId") or "")
        if agenda_id:
            scadenza = manager.aggiorna(scadenza.id, id_appuntamento=agenda_id)
        notifications = repo.save_notification_plan(
            deadline_id=scadenza.id,
            case_reference=str(result.get("caseReference") or payload.get("case_reference") or ""),
            user_id=user_id,
            notification_plan=result.get("notificationPlan") or [],
        )
        return jsonify({
            "ok": True,
            "messaggio": "Scadenza processuale creata con audit del calcolo.",
            "id": scadenza.id,
            "href": f"/scadenziario/{scadenza.id}",
            "agenda": agenda,
            "audit": result["audit"],
            "notificationsPlanned": notifications,
        })
    except Exception as exc:
        current_app.logger.exception("Creazione scadenza da calcolo non riuscita: %s", exc)
        return jsonify({"ok": False, "errore": "Scadenza processuale non creata."}), 400


@api_v1_react.get("/wizard-pro")
@_richiedi_auth
def wizard_pro_react_dashboard():
    return jsonify(build_react_wizard_pro_payload(
        selected_fascicolo_id=request.args.get("id_fascicolo", "").strip(),
    ))


@api_v1_react.get("/wizard-pro/session/<id_sessione>/step/<int:n>")
@_richiedi_auth
def wizard_pro_react_step(id_sessione: str, n: int):
    payload = build_react_wizard_pro_step_payload(id_sessione, n)
    if payload is None:
        return jsonify({
            "errore": "Preparazione udienza non trovata.",
            "codice": 404,
            "contracts": {
                "mock_fallback": False,
                "writes": "operational_routes",
                "route_owner": "react_shell",
            },
        }), 404
    return jsonify(payload)


@api_v1_react.get("/wizard-pro/session/<id_sessione>/completo")
@_richiedi_auth
def wizard_pro_react_complete(id_sessione: str):
    payload = build_react_wizard_pro_complete_payload(id_sessione)
    if payload is None:
        return jsonify({
            "errore": "Preparazione udienza non trovata.",
            "codice": 404,
            "contracts": {
                "mock_fallback": False,
                "writes": "operational_routes",
                "route_owner": "react_shell",
            },
        }), 404
    return jsonify(payload)


@api_v1_react.get("/timesheet")
@_richiedi_auth
def timesheet_react_payload():
    return jsonify(build_react_timesheet_payload(
        get_timesheet=get_timesheet,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        query=dict(request.args),
    ))


@api_v1_react.get("/cartelle-condivise")
@_richiedi_auth
def cartelle_condivise_react_payload():
    get_condivisioni = _core_runtime_func("get_condivisioni")
    if not callable(get_condivisioni):
        return jsonify({
            "source": "errore_controllato",
            "generatedAt": _iso_now(),
            "contracts": {
                "mock_fallback": False,
                "writes": "operational_routes",
                "route_owner": "react_shell",
            },
            "errore": "Runtime condivisioni non disponibile.",
        }), 503
    return jsonify(build_react_condivisioni_payload(
        get_condivisioni=get_condivisioni,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        current_user=g.get("utente_corrente"),
    ))


@api_v1_react.get("/telematico")
@_richiedi_auth
def telematico_react_dashboard():
    return jsonify(
        build_react_telematico_payload(
            get_telematico=_telematico_loader(),
            get_fascicoli=get_fascicoli,
            build_access_status_payload=_telematico_runtime_func("build_access_status_payload"),
            prepare_dashboard=_telematico_runtime_func("backfill_telematico_from_existing_fascicoli"),
            dashboard_warning_message=_telematico_runtime_func("telematico_dashboard_warning_message"),
            logger=current_app.logger,
        )
    )


@api_v1_react.get("/telematico/surface/<surface>")
@_richiedi_auth
def telematico_react_surface(surface: str):
    normalized = (surface or "").strip().lower()
    if normalized in {"tribunali", "tribunali-pec"}:
        return jsonify(build_react_tribunali_payload())
    return jsonify(
        build_react_telematico_surface_payload(
            surface=surface,
            get_telematico=_telematico_loader(),
            get_fascicoli=get_fascicoli,
            build_access_status_payload=_telematico_runtime_func("build_access_status_payload"),
            logger=current_app.logger,
        )
    )


_PST_REACT_SCHEMA_BY_SERVICE: dict[str, dict[str, str]] = {
    "JPW_SICID": {
        "schema": "civile",
        "materia": "Civile contenzioso",
        "registro": "RGN",
        "tipo_registro": "RGN",
        "quick_filter": "civile",
        "tabella_ministeriale": "SICID_CONTENZIOSO_CIVILE",
        "servizio_pst_preferito": "JPW_SICID",
        "registro_portale": "JPW_SICID",
    },
    "JPW_SIL_DISTR": {
        "schema": "lavoro",
        "materia": "Lavoro e previdenza",
        "registro": "LAV",
        "tipo_registro": "LAV",
        "quick_filter": "lavoro",
        "tabella_ministeriale": "SICID_LAVORO",
        "servizio_pst_preferito": "JPW_SIL_DISTR",
        "registro_portale": "JPW_SIL",
    },
    "JPW_SIL": {
        "schema": "lavoro",
        "materia": "Lavoro e previdenza",
        "registro": "LAV",
        "tipo_registro": "LAV",
        "quick_filter": "lavoro",
        "tabella_ministeriale": "SICID_LAVORO",
        "servizio_pst_preferito": "JPW_SIL_DISTR",
        "registro_portale": "JPW_SIL",
    },
    "JPW_SILP_DISTR": {
        "schema": "lavoro",
        "materia": "Lavoro e previdenza",
        "registro": "LAV",
        "tipo_registro": "LAV",
        "quick_filter": "lavoro",
        "tabella_ministeriale": "SICID_LAVORO",
        "servizio_pst_preferito": "JPW_SILP_DISTR",
        "registro_portale": "JPW_SIL",
    },
    "JPW_SILP": {
        "schema": "lavoro",
        "materia": "Lavoro e previdenza",
        "registro": "LAV",
        "tipo_registro": "LAV",
        "quick_filter": "lavoro",
        "tabella_ministeriale": "SICID_LAVORO",
        "servizio_pst_preferito": "JPW_SILP_DISTR",
        "registro_portale": "JPW_SIL",
    },
    "JPW_SIVG": {
        "schema": "volontaria",
        "materia": "Volontaria giurisdizione",
        "registro": "VG",
        "tipo_registro": "VG",
        "quick_filter": "volontaria",
        "tabella_ministeriale": "SICID_VOLONTARIA_GIURISDIZIONE",
        "servizio_pst_preferito": "JPW_SIVG",
        "registro_portale": "JPW_SIVG",
    },
    "JPW_MIN": {
        "schema": "minori",
        "materia": "Minori",
        "registro": "MIN",
        "tipo_registro": "MIN",
        "quick_filter": "minori",
        "tabella_ministeriale": "SICID_MINORI",
        "servizio_pst_preferito": "JPW_MIN",
        "registro_portale": "JPW_MIN",
    },
    "JPW_SIMIN": {
        "schema": "minori",
        "materia": "Minori",
        "registro": "MIN",
        "tipo_registro": "MIN",
        "quick_filter": "minori",
        "tabella_ministeriale": "SICID_SIMIN",
        "servizio_pst_preferito": "JPW_SIMIN",
        "registro_portale": "JPW_SIMIN",
    },
    "JPW_SIECIC": {
        "schema": "esecuzioni",
        "materia": "Esecuzioni e concorsuali",
        "registro": "SIECIC",
        "tipo_registro": "SIECIC",
        "quick_filter": "esecuzioni",
        "tabella_ministeriale": "SIECIC_ESECUZIONI_CONCORSUALI",
        "servizio_pst_preferito": "JPW_SIECIC",
        "registro_portale": "JPW_SIECIC",
    },
    "JPW_SIGP": {
        "schema": "giudice di pace",
        "materia": "Giudice di pace",
        "registro": "GDP",
        "tipo_registro": "GDP",
        "quick_filter": "giudice di pace",
        "tabella_ministeriale": "SIGP_GIUDICE_DI_PACE",
        "servizio_pst_preferito": "JPW_SIGP",
        "registro_portale": "JPW_SIGP",
    },
    "JPW_CASSCI": {
        "schema": "cassazione civile",
        "materia": "Cassazione civile",
        "registro": "CASSCI",
        "tipo_registro": "CASSCI",
        "quick_filter": "cassazione civile",
        "tabella_ministeriale": "JPW_CASSCI",
        "servizio_pst_preferito": "JPW_CASSCI",
        "registro_portale": "JPW_CASSCI",
    },
    "JPW_CASSPE": {
        "schema": "cassazione penale",
        "materia": "Cassazione penale",
        "registro": "CASSPE",
        "tipo_registro": "CASSPE",
        "quick_filter": "cassazione penale",
        "tabella_ministeriale": "JPW_CASSPE",
        "servizio_pst_preferito": "JPW_CASSPE",
        "registro_portale": "JPW_CASSPE",
    },
}


def _pst_react_norm(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", raw.upper())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text).strip()


def _pst_react_service_from_text(*values: Any) -> tuple[str, str]:
    text = " ".join(_pst_react_norm(value) for value in values if str(value or "").strip())
    if not text:
        return "", ""
    checks: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
        ("JPW_CASSPE", (("CASS", "PENAL"), ("JPW", "CASSPE"))),
        ("JPW_CASSCI", (("CASS", "CIVIL"), ("JPW", "CASSCI"))),
        ("JPW_SIECIC", (("SIECIC",), ("ESECUZ",), ("CONCORS",), ("FALLIMENT",), ("PIGNOR",))),
        ("JPW_SIVG", (("VOLONTARI",), ("SIVG",))),
        ("JPW_SIMIN", (("SIMIN",),)),
        ("JPW_MIN", (("MINORE",), ("MINORI",), ("MINORENN",), ("JPW", "MIN"))),
        ("JPW_SIGP", (("SIGP",), ("GDP",), ("GIUDICE", "PACE"))),
        ("JPW_SILP_DISTR", (("SILP",),)),
        ("JPW_SIL_DISTR", (("LAVOR",), ("PREVIDENZ",), ("ASSISTENZ",), ("PCT", "LAVORO"), ("SICID", "LAVORO"))),
        ("JPW_SICID", (("SICID",), ("CIVILE",), ("RGN",), ("CONTENZIOSO",))),
    )
    for service, groups in checks:
        if any(all(marker in text for marker in group) for group in groups):
            return service, text
    return "", text


def _pst_react_apply_siecic_schema(hint: dict[str, Any], source: Any) -> dict[str, Any]:
    text = _pst_react_norm(source)
    if not text:
        return hint
    if "IMMOBIL" in text or "PIGNOR" in text:
        hint.update({
            "schema": "esecuzioni immobiliari",
            "materia": "Esecuzioni immobiliari",
            "registro": "ESIM",
            "tipo_registro": "ESIM",
            "quick_filter": "esecuzioni immobiliari",
            "tabella_ministeriale": "SIECIC_ESECUZIONI_IMMOBILIARI",
            "registro_portale": "ESIM",
        })
    elif "FALL" in text or "CONCORS" in text:
        hint.update({
            "schema": "procedure concorsuali",
            "materia": "Procedure concorsuali",
            "registro": "FALL",
            "tipo_registro": "FALL",
            "quick_filter": "procedure concorsuali",
            "tabella_ministeriale": "SIECIC_PROCEDURE_CONCORSUALI",
            "registro_portale": "FALL",
        })
    elif "MOBIL" in text or "ESECUZ" in text:
        hint.update({
            "schema": "esecuzioni mobiliari",
            "materia": "Esecuzioni mobiliari",
            "registro": "ESM",
            "tipo_registro": "ESM",
            "quick_filter": "esecuzioni mobiliari",
            "tabella_ministeriale": "SIECIC_ESECUZIONI_MOBILIARI",
            "registro_portale": "ESM",
        })
    return hint


def _pst_react_service_from_fascicolo(fascicolo: Any) -> tuple[str, str]:
    profile = getattr(fascicolo, "profilo_deposito", None)
    if not isinstance(profile, Mapping):
        profile = {}
    pratica = profile.get("pratica") if isinstance(profile.get("pratica"), Mapping) else {}
    canale = profile.get("canale") if isinstance(profile.get("canale"), Mapping) else {}
    ufficio = profile.get("ufficio") if isinstance(profile.get("ufficio"), Mapping) else {}

    explicit_sources = (
        getattr(fascicolo, "registro_operativo", ""),
        getattr(fascicolo, "canale_operativo", ""),
        getattr(fascicolo, "procedura_operativa_codice", ""),
        getattr(fascicolo, "tipo_procedimento", ""),
        getattr(fascicolo, "codice_guida_pratica", ""),
        pratica.get("registro_operativo"),
        pratica.get("procedura_operativa_codice"),
        pratica.get("tipo_procedimento"),
    )
    service, source = _pst_react_service_from_text(*explicit_sources)
    if service:
        return service, source

    descriptive_sources = (
        getattr(fascicolo, "tipo", ""),
        getattr(fascicolo, "area_pratica", ""),
        getattr(fascicolo, "titolo", ""),
        getattr(fascicolo, "oggetto", ""),
        getattr(fascicolo, "codice_oggetto_pst", ""),
    )
    service, source = _pst_react_service_from_text(*descriptive_sources)
    if service:
        return service, source

    office_service, office_source = _pst_react_service_from_text(
        getattr(fascicolo, "tribunale", ""),
        ufficio.get("nome"),
        ufficio.get("tipo"),
    )
    if office_service == "JPW_SIGP":
        return office_service, office_source

    return _pst_react_service_from_text(canale.get("codice"))


def _pst_react_schema_hint_from_fascicolo(fascicolo: Any) -> dict[str, Any]:
    service, source = _pst_react_service_from_fascicolo(fascicolo)
    if not service:
        return {}
    hint = dict(_PST_REACT_SCHEMA_BY_SERVICE.get(service, {}))
    if not hint:
        return {}
    if service == "JPW_SIECIC":
        hint = _pst_react_apply_siecic_schema(hint, source)
    hint.update({
        "source": "fascicolo_locale",
        "service_source": source,
        "confidence": "alta",
        "reason": (
            "Tabella ministeriale applicata automaticamente dal profilo del fascicolo locale "
            "prima della ricerca PST."
        ),
    })
    return hint


def _pst_react_rg_matches(left: Any, right: Any) -> bool:
    a = re.sub(r"\s+", "", str(left or "")).lstrip("0")
    b = re.sub(r"\s+", "", str(right or "")).lstrip("0")
    return bool(a and b and a == b)


def _pst_react_year_matches(left: Any, right: Any) -> bool:
    try:
        return int(left or 0) == int(right or 0) and int(left or 0) > 0
    except (TypeError, ValueError):
        return False


def _pst_react_office_codes(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    codes = {raw}
    try:
        resolved = risolvi_ufficio(raw)
    except Exception:
        resolved = None
    if isinstance(resolved, Mapping):
        for key in ("codice", "codice_ministero", "codice_gl", "codice_pst"):
            code = str(resolved.get(key) or "").strip()
            if code:
                codes.add(code)
    return codes


def _pst_react_office_matches(fascicolo: Any, ufficio: str, ufficio_codice: str) -> bool:
    requested_text = _pst_react_norm(ufficio)
    fascicolo_text = _pst_react_norm(getattr(fascicolo, "tribunale", ""))
    requested_codes = _pst_react_office_codes(ufficio_codice or ufficio)
    fascicolo_codes = _pst_react_office_codes(getattr(fascicolo, "tribunale", ""))
    if requested_codes and fascicolo_codes and requested_codes.intersection(fascicolo_codes):
        return True
    if requested_text and fascicolo_text:
        return requested_text == fascicolo_text or requested_text in fascicolo_text or fascicolo_text in requested_text
    return not (requested_text or requested_codes)


@api_v1_react.get("/telematico/pst/schema-hint")
@_richiedi_auth
def telematico_pst_schema_hint():
    try:
        numero = str(request.args.get("numero") or request.args.get("numero_rg") or "").strip()
        anno = str(request.args.get("anno") or request.args.get("anno_rg") or "").strip()
        ufficio = str(request.args.get("ufficio") or "").strip()
        ufficio_codice = str(request.args.get("ufficio_codice") or request.args.get("codice_ufficio") or "").strip()
        fascicolo_id = str(request.args.get("id_fasc") or request.args.get("fascicolo_id") or "").strip()
        fascicoli = list(get_fascicoli().tutti(archiviati=True))
        matched = None
        for fascicolo in fascicoli:
            if fascicolo_id and str(getattr(fascicolo, "id", "") or "") != fascicolo_id:
                continue
            if not fascicolo_id and not (
                _pst_react_rg_matches(getattr(fascicolo, "numero_rg", ""), numero)
                and _pst_react_year_matches(getattr(fascicolo, "anno_rg", 0), anno)
            ):
                continue
            if not _pst_react_office_matches(fascicolo, ufficio, ufficio_codice):
                continue
            matched = fascicolo
            break
        hint = _pst_react_schema_hint_from_fascicolo(matched) if matched is not None else {}
        return jsonify({
            "ok": True,
            "matched": matched is not None,
            "hint": hint,
            "fascicolo": {
                "id": str(getattr(matched, "id", "") or "") if matched is not None else "",
                "titolo": str(getattr(matched, "titolo", "") or "") if matched is not None else "",
                "tribunale": str(getattr(matched, "tribunale", "") or "") if matched is not None else "",
                "numero_rg": str(getattr(matched, "numero_rg", "") or "") if matched is not None else "",
                "anno_rg": getattr(matched, "anno_rg", "") if matched is not None else "",
            },
        })
    except Exception as exc:
        current_app.logger.exception("Errore deduzione tabella PST: %s", exc)
        return jsonify({
            "ok": False,
            "matched": False,
            "hint": {},
            "errore": "Tabella ministeriale non dedotta dal fascicolo locale.",
        }), 200


def _pat_module_prefill_text(value: Any, fallback: str = "") -> str:
    return re.sub(r"\s+", " ", str(value or fallback).strip())


def _pat_enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _pat_cliente_label(cliente: Any) -> str:
    if cliente is None:
        return ""
    return _pat_module_prefill_text(
        getattr(cliente, "nome_completo", "")
        or getattr(cliente, "ragione_sociale", "")
        or " ".join(
            item
            for item in (
                str(getattr(cliente, "cognome", "") or "").strip(),
                str(getattr(cliente, "nome", "") or "").strip(),
            )
            if item
        )
    )


def _pat_cliente_identificativo(cliente: Any) -> str:
    if cliente is None:
        return ""
    return _pat_module_prefill_text(
        getattr(cliente, "identificativo_fiscale", "")
        or getattr(cliente, "codice_fiscale", "")
        or getattr(cliente, "partita_iva", "")
    )


def _pat_cliente_pec(cliente: Any) -> str:
    recapiti = getattr(cliente, "recapiti", None)
    return _pat_module_prefill_text(getattr(recapiti, "pec", "") or getattr(recapiti, "email", ""))


def _pat_tipo_ricorso_from_fascicolo(fascicolo: Any) -> str:
    haystack = " ".join(
        _pat_module_prefill_text(getattr(fascicolo, field, ""))
        for field in ("oggetto", "titolo", "tipo_procedimento", "procedura_operativa_nome", "area_pratica")
    ).lower()
    if any(token in haystack for token in ("appalt", "cig", "pnrr")):
        return "Appalti"
    if "accesso" in haystack:
        return "Accesso"
    if "silenzio" in haystack:
        return "Silenzio"
    if "ottemperanza" in haystack:
        return "Ottemperanza"
    if "sportiv" in haystack:
        return "Rito sportivo"
    return "Ordinario"


def _pat_contributo_unificato_from_fascicolo(fascicolo: Any) -> str:
    pagamenti = getattr(fascicolo, "pagamenti", {}) or {}
    if not isinstance(pagamenti, Mapping):
        return ""
    raw = pagamenti.get("contributo_unificato") or pagamenti.get("contributo") or pagamenti.get("cu") or {}
    text = ""
    if isinstance(raw, Mapping):
        text = " ".join(str(raw.get(key) or "") for key in ("stato", "status", "esito", "note"))
    else:
        text = str(raw or "")
    normalized = text.lower()
    if "esent" in normalized:
        return "Esente"
    if "prenot" in normalized:
        return "Prenotato a debito"
    if "pag" in normalized or "iuv" in normalized or "f24" in normalized:
        return "Pagato"
    return ""


def _pat_dati_pagamento_from_fascicolo(fascicolo: Any) -> str:
    pagamenti = getattr(fascicolo, "pagamenti", {}) or {}
    if not isinstance(pagamenti, Mapping):
        return ""
    raw = pagamenti.get("contributo_unificato") or pagamenti.get("contributo") or pagamenti.get("cu") or {}
    if isinstance(raw, Mapping):
        values = [
            raw.get("iuv"),
            raw.get("numero"),
            raw.get("data"),
            raw.get("importo"),
            raw.get("stato") or raw.get("status"),
        ]
        return _pat_module_prefill_text(" - ".join(str(value) for value in values if value))
    return _pat_module_prefill_text(raw)


def _pat_parti_fascicolo(id_fascicolo: str) -> list[tuple[Any, Any]]:
    if not id_fascicolo:
        return []
    try:
        return list(get_soggetti().parti_fascicolo(id_fascicolo))
    except Exception:
        current_app.logger.exception("PAT prefill: parti fascicolo non disponibili per %s", id_fascicolo)
        return []


def _pat_soggetto_label(soggetto: Any) -> str:
    return _pat_module_prefill_text(
        getattr(soggetto, "nome_completo", "")
        or getattr(soggetto, "ragione_sociale", "")
        or " ".join(
            item
            for item in (
                str(getattr(soggetto, "cognome", "") or "").strip(),
                str(getattr(soggetto, "nome", "") or "").strip(),
            )
            if item
        )
    )


def _pat_document_size_label(size: Any) -> str:
    try:
        value = int(size or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "dimensione non indicata"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB".replace(".", ",")
    return f"{value / (1024 * 1024):.1f} MB".replace(".", ",")


def _pat_document_role(doc: Any) -> str:
    tipo = _pat_enum_text(getattr(doc, "tipo", "")).casefold()
    searchable = " ".join(
        str(item or "")
        for item in (
            getattr(doc, "nome", ""),
            getattr(doc, "nome_originale", ""),
            getattr(doc, "nome_portale", ""),
            getattr(doc, "note", ""),
            " ".join(str(tag) for tag in (getattr(doc, "tags", []) or [])),
            tipo,
        )
    )
    normalized = re.sub(r"[^a-z0-9àèéìòù]+", " ", searchable.casefold()).strip()
    if "procura" in normalized:
        return "procura"
    if "notifica" in normalized or "relata" in normalized:
        return "notifica"
    if "ricevuta" in normalized or "contributo" in normalized or "pagopa" in normalized or "iuv" in normalized:
        return "ricevuta_pagamento"
    if re.search(r"\b(ricorso|atto introduttivo|atto di appello|appello cautelare|motivi aggiunti)\b", normalized):
        return "atto_principale"
    if tipo == "ricorso":
        return "atto_principale"
    if re.search(r"\b(decreto|ordinanza|sentenza|verbale|perizia|ctu|ctp|comunicazione|minuta|liquidazione|note?|memoria conclusiva)\b", normalized):
        return "allegato"
    return "allegato"


def _pat_document_payload(fascicolo_id: str, doc: Any) -> dict[str, Any]:
    doc_id = _pat_module_prefill_text(getattr(doc, "id", ""))
    name = _pat_module_prefill_text(
        getattr(doc, "nome", "")
        or getattr(doc, "nome_originale", "")
        or getattr(doc, "nome_portale", "")
        or "Documento"
    )
    try:
        preview_url = url_for("visualizza_documento", id_fasc=fascicolo_id, id_doc=doc_id)
        download_url = url_for("scarica_documento", id_fasc=fascicolo_id, id_doc=doc_id)
    except Exception:
        preview_url = f"/fascicoli/{fascicolo_id}/documenti/{doc_id}/visualizza" if fascicolo_id and doc_id else ""
        download_url = f"/fascicoli/{fascicolo_id}/documenti/{doc_id}/scarica" if fascicolo_id and doc_id else ""
    size = int(getattr(doc, "dimensione_bytes", 0) or 0)
    return {
        "id": doc_id,
        "name": name,
        "type": _pat_enum_text(getattr(doc, "tipo", "")) or "Documento",
        "sizeBytes": size,
        "sizeLabel": _pat_document_size_label(size),
        "signed": bool(getattr(doc, "firmato_digitalmente", False) or getattr(doc, "firmato", False)),
        "suggestedRole": _pat_document_role(doc),
        "uploadedAt": _pat_module_prefill_text(getattr(doc, "data_caricamento", "")),
        "documentDate": _pat_module_prefill_text(getattr(doc, "data_documento", "")),
        "source": _pat_module_prefill_text(getattr(doc, "fonte_documento", "")),
        "previewUrl": preview_url,
        "downloadUrl": download_url,
    }


def _pat_read_document_bytes(gestore: Any, fascicolo_id: str, document_id: str) -> bytes:
    path = gestore.percorso_documento_lettura(fascicolo_id, document_id)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File documento non trovato: {document_id}")
    from web.services.document_crypto import decrypt_doc

    return decrypt_doc(path.read_bytes())


def _pat_selected_documents_from_payload(gestore: Any, fascicolo: Any, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_items = payload.get("documents") or payload.get("documenti") or []
    if not isinstance(raw_items, list):
        raw_items = []
    by_id = {
        _pat_module_prefill_text(getattr(doc, "id", "")): doc
        for doc in (getattr(fascicolo, "documenti", []) or [])
        if _pat_module_prefill_text(getattr(doc, "id", ""))
    }
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        doc_id = _pat_module_prefill_text(raw.get("id") or raw.get("documentId"))
        if not doc_id or doc_id in seen:
            continue
        doc = by_id.get(doc_id)
        if doc is None:
            raise ValueError(f"Documento non appartenente al fascicolo: {doc_id}")
        item = _pat_document_payload(_pat_module_prefill_text(getattr(fascicolo, "id", "")), doc)
        role = _pat_module_prefill_text(raw.get("role") or raw.get("ruolo") or item.get("suggestedRole")) or "allegato"
        item["role"] = role
        item["requiresSignature"] = bool(raw.get("requiresSignature") or raw.get("firmaRichiesta"))
        item["contentBytes"] = _pat_read_document_bytes(gestore, _pat_module_prefill_text(getattr(fascicolo, "id", "")), doc_id)
        selected.append(item)
        seen.add(doc_id)

    total_size = sum(len(item.get("contentBytes") or b"") for item in selected)
    if len(selected) > 50:
        raise ValueError("Il Formweb PAT consente al massimo 50 file per deposito.")
    if any(len(item.get("contentBytes") or b"") > 300 * 1024 * 1024 for item in selected):
        raise ValueError("Un allegato supera il limite Formweb di 300 MB per singolo file.")
    if total_size > 300 * 1024 * 1024:
        raise ValueError("Gli allegati selezionati superano il limite Formweb di 300 MB complessivi.")
    return selected


def _pat_first_party_by_roles(parti: Iterable[tuple[Any, Any]], roles: set[str]) -> str:
    for parte, soggetto in parti:
        role = _pat_enum_text(getattr(parte, "ruolo", "")).upper()
        if role in roles:
            return _pat_soggetto_label(soggetto)
    return ""


def _pat_prefill_item_from_fascicolo(fascicolo: Any) -> dict[str, Any]:
    fascicolo_id = _pat_module_prefill_text(getattr(fascicolo, "id", ""))
    cliente = None
    cliente_id = _pat_module_prefill_text(getattr(fascicolo, "id_cliente", ""))
    if cliente_id:
        try:
            cliente = get_clienti().get(cliente_id)
        except Exception:
            current_app.logger.exception("PAT prefill: cliente non disponibile per fascicolo %s", fascicolo_id)
    cliente_label = _pat_cliente_label(cliente) or _pat_module_prefill_text(getattr(fascicolo, "nome_cliente", ""))
    parti = _pat_parti_fascicolo(fascicolo_id)
    controparte = (
        _pat_first_party_by_roles(parti, {"CONTROPARTE", "PUBBLICA_AMMINISTRAZIONE", "ENTE"})
        or _pat_module_prefill_text(getattr(fascicolo, "controparte", ""))
    )
    rg = _pat_module_prefill_text(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", ""))
    anno_rg = _pat_module_prefill_text(getattr(fascicolo, "anno_rg", ""))
    numero_rg = _pat_module_prefill_text(getattr(fascicolo, "numero_rg", ""))
    oggetto = _pat_module_prefill_text(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", ""))
    documenti = list(getattr(fascicolo, "documenti", []) or [])
    document_payloads = [_pat_document_payload(fascicolo_id, doc) for doc in documenti]
    documenti_descrizione = ", ".join(_pat_module_prefill_text(getattr(doc, "nome", "")) for doc in documenti if getattr(doc, "nome", ""))
    fields = {
        "sede": _pat_module_prefill_text(getattr(fascicolo, "tribunale", "")),
        "parte_depositante": cliente_label,
        "codice_fiscale": _pat_cliente_identificativo(cliente) or _pat_module_prefill_text(getattr(fascicolo, "cf_controparte", "")),
        "oggetto": oggetto,
        "nrg": numero_rg,
        "anno_rg": anno_rg,
        "riferimento_fascicolo": rg or _pat_module_prefill_text(getattr(fascicolo, "numero", "")),
        "tipo_ricorso": _pat_tipo_ricorso_from_fascicolo(fascicolo),
        "ricorrente": cliente_label or _pat_first_party_by_roles(parti, {"ASSISTITO"}),
        "resistente": controparte,
        "amministrazione_resistente": controparte,
        "istante": cliente_label,
        "richiedente": cliente_label,
        "contributo_unificato": _pat_contributo_unificato_from_fascicolo(fascicolo),
        "dati_pagamento": _pat_dati_pagamento_from_fascicolo(fascicolo),
        "tipologia_atto": _pat_module_prefill_text(getattr(fascicolo, "tipo_procedimento", "")),
        "descrizione_allegati": documenti_descrizione,
        "qualifica_depositante": "CTU" if _pat_module_prefill_text(getattr(fascicolo, "ctu", "")) else "",
        "descrizione_deposito": oggetto,
        "nome_parte": cliente_label,
        "pec": _pat_cliente_pec(cliente),
        "note": _pat_module_prefill_text(getattr(fascicolo, "note", "")),
    }
    fields = {key: value for key, value in fields.items() if value}
    warnings = []
    if not fields.get("sede"):
        warnings.append("Sede TAR/CDS/CGARS assente nel fascicolo.")
    if not fields.get("nrg"):
        warnings.append("Numero RG non presente nel fascicolo.")
    if not cliente_label:
        warnings.append("Cliente o parte depositante da completare.")
    if not controparte:
        warnings.append("Controparte o amministrazione resistente da completare.")
    return {
        "id": fascicolo_id,
        "title": _pat_module_prefill_text(getattr(fascicolo, "titolo", "") or getattr(fascicolo, "oggetto", "") or "Fascicolo"),
        "subtitle": _pat_module_prefill_text(getattr(fascicolo, "numero", "") or rg or "Fascicolo IUSENTRA"),
        "rg": rg,
        "office": fields.get("sede", ""),
        "client": cliente_label,
        "counterparty": controparte,
        "source": "repository_fascicoli_clienti_soggetti",
        "fields": fields,
        "documents": document_payloads,
        "documentsSummary": f"{len(document_payloads)} documenti disponibili nel fascicolo",
        "warnings": warnings,
    }


@api_v1_react.get("/pat/moduli/prefill")
@_richiedi_auth
def pat_moduli_prefill():
    try:
        fascicoli = get_fascicoli().tutti(archiviati=False)[:30]
        matters = [_pat_prefill_item_from_fascicolo(fascicolo) for fascicolo in fascicoli]
        return jsonify({
            "ok": True,
            "source": "repository_reali",
            "generatedAt": _iso_now(),
            "matters": matters,
        })
    except Exception as exc:
        current_app.logger.exception("PAT prefill: repository non disponibile: %s", exc)
        return jsonify({
            "ok": False,
            "errore": "Dati IUSENTRA non disponibili per la precompilazione PAT.",
            "matters": [],
        }), 500


def _pat_pdf_text(value: Any, fallback: str = "") -> str:
    text = str(value or fallback).strip()
    return re.sub(r"\s+", " ", text)


@api_v1_react.post("/pat/moduli/compila")
@_richiedi_auth
def pat_moduli_compila_pdf():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "errore": "Payload modulo non valido."}), 400

    from pct.pat_moduli import PAT_MODULES

    module_id = _pat_pdf_text(payload.get("module_id") or payload.get("moduleId"))
    module = next((item for item in PAT_MODULES if item.id == module_id), None)
    if module is None:
        return jsonify({"ok": False, "errore": "Modulo PAT non riconosciuto."}), 404

    fascicolo_id = _pat_pdf_text(payload.get("fascicolo_id") or payload.get("fascicoloId"))
    selected_documents: list[dict[str, Any]] = []
    prefill_fields: dict[str, str] = {}
    prefill_meta: dict[str, Any] = {}
    if fascicolo_id:
        gestore_fascicoli = get_fascicoli()
        fascicolo = gestore_fascicoli.get(fascicolo_id)
        if fascicolo is None:
            return jsonify({"ok": False, "errore": "Fascicolo IUSENTRA non trovato per la precompilazione."}), 404
        prefill_meta = _pat_prefill_item_from_fascicolo(fascicolo)
        prefill_fields = {
            str(key): _pat_pdf_text(value)
            for key, value in (prefill_meta.get("fields") or {}).items()
            if _pat_pdf_text(value)
        }
        try:
            selected_documents = _pat_selected_documents_from_payload(gestore_fascicoli, fascicolo, payload)
        except ValueError as exc:
            current_app.logger.info("PAT compila: selezione allegati non valida per %s: %s", fascicolo_id, exc)
            return jsonify({"ok": False, "errore": "Selezione documenti non valida."}), 422
        except Exception as exc:
            current_app.logger.exception("PAT compila: lettura allegati fascicolo %s fallita: %s", fascicolo_id, exc)
            return jsonify({"ok": False, "errore": "Impossibile leggere uno o più documenti del fascicolo selezionato."}), 500

    fields_payload = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
    fields = dict(prefill_fields)
    for key, value in fields_payload.items():
        if key in {"xfa_values", "xfaValues"}:
            continue
        cleaned = _pat_pdf_text(value)
        if cleaned:
            fields[str(key)] = cleaned
    xfa_values_payload = payload.get("xfa_values") or payload.get("xfaValues")
    if isinstance(xfa_values_payload, dict):
        xfa_values: dict[str, str] = {}
        for key, value in xfa_values_payload.items():
            cleaned = _pat_pdf_text(value)
            if cleaned:
                xfa_values[str(key)] = cleaned
        if xfa_values:
            fields["xfa_values"] = xfa_values
    if fields.get("parte") and not fields.get("parte_depositante"):
        fields["parte_depositante"] = fields["parte"]
    resistente_alias = fields.get("amministrazione") or fields.get("controparte") or fields.get("resistente")
    if resistente_alias and not fields.get("amministrazione_resistente"):
        fields["amministrazione_resistente"] = resistente_alias
    if resistente_alias and not fields.get("resistente"):
        fields["resistente"] = resistente_alias
    missing = [field.label for field in module.fillable_fields if field.required and not fields.get(field.id)]
    if missing:
        return jsonify({
            "ok": False,
            "errore": "Compilare i campi obbligatori prima di produrre il PDF.",
            "missing": missing,
        }), 422

    from pct.pat_pdf_templates import build_pat_official_pdf

    try:
        pdf, download_name = build_pat_official_pdf(module.id, fields, selected_documents)
    except Exception as exc:
        current_app.logger.exception("PAT compila: modulo ufficiale %s non generato: %s", module.id, exc)
        return jsonify({"ok": False, "errore": "Modulo ufficiale PAT non generato. Verifica template ministeriale e dati compilati."}), 500
    pdf_bytes = pdf.getvalue()
    if request.headers.get("X-IUSENTRA-PAT-Preview") == "1" or payload.get("previewSession") is True:
        preview = _pat_store_preview_pdf(pdf_bytes, download_name)
        return jsonify(
            {
                "ok": True,
                "filename": download_name,
                "sizeBytes": len(pdf_bytes),
                "documentCount": len(selected_documents),
                "previewUrl": url_for("api_v1_react.pat_moduli_preview_pdf", token=preview["token"]),
                "downloadUrl": url_for(
                    "api_v1_react.pat_moduli_preview_pdf",
                    token=preview["token"],
                    download="1",
                ),
            }
        )
    pdf.seek(0)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=download_name,
    )


_PAT_PREVIEW_SESSION_KEY = "pat_pdf_previews"
_PAT_PREVIEW_MAX_AGE_SECONDS = 2 * 60 * 60
_PAT_PREVIEW_MAX_ITEMS = 8


def _pat_preview_tenant_slug() -> str:
    tenant = getattr(g, "tenant", None)
    candidates = [
        getattr(tenant, "slug", ""),
        getattr(g, "tenant_context_slug", ""),
        session.get("tenant_slug", ""),
        getattr(g.get("utente_corrente") if hasattr(g, "get") else None, "tenant_slug", ""),
        "single-studio",
    ]
    for candidate in candidates:
        value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(candidate or "").strip()).strip(".-")
        if value:
            return value[:80]
    return "single-studio"


def _pat_preview_root() -> Path:
    root = Path(tempfile.gettempdir()) / "iusentra-pat-previews" / _pat_preview_tenant_slug()
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _pat_safe_preview_filename(filename: str) -> str:
    name = Path(str(filename or "modulo-pat-compilato.pdf")).name.strip() or "modulo-pat-compilato.pdf"
    name = re.sub(r"[\r\n\t]+", " ", name)
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:180]


def _pat_cleanup_preview_session(root: Path) -> dict[str, dict[str, Any]]:
    now = datetime.now(timezone.utc).timestamp()
    raw = session.get(_PAT_PREVIEW_SESSION_KEY) or {}
    previews: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for token, meta_raw in raw.items():
            token_text = str(token or "").strip()
            meta = meta_raw if isinstance(meta_raw, dict) else {}
            created_at = float(meta.get("created_at") or 0)
            path = Path(str(meta.get("path") or ""))
            expired = not created_at or now - created_at > _PAT_PREVIEW_MAX_AGE_SECONDS
            try:
                resolved = path.resolve()
                inside_root = root in resolved.parents or resolved == root
            except Exception:
                inside_root = False
            if expired or not inside_root or not path.exists():
                try:
                    if inside_root and path.exists():
                        path.unlink()
                except Exception:
                    pass
                continue
            previews[token_text] = {
                "path": str(path),
                "filename": _pat_safe_preview_filename(str(meta.get("filename") or "")),
                "created_at": created_at,
            }
    ordered = sorted(previews.items(), key=lambda item: float(item[1].get("created_at") or 0), reverse=True)
    kept = dict(ordered[:_PAT_PREVIEW_MAX_ITEMS])
    for _token, meta in ordered[_PAT_PREVIEW_MAX_ITEMS:]:
        try:
            Path(str(meta.get("path") or "")).unlink(missing_ok=True)
        except Exception:
            pass
    session[_PAT_PREVIEW_SESSION_KEY] = kept
    return kept


def _pat_store_preview_pdf(pdf_bytes: bytes, filename: str) -> dict[str, str]:
    root = _pat_preview_root()
    previews = _pat_cleanup_preview_session(root)
    token = secrets.token_urlsafe(18)
    path = root / f"{token}.pdf"
    path.write_bytes(pdf_bytes)
    previews[token] = {
        "path": str(path),
        "filename": _pat_safe_preview_filename(filename),
        "created_at": datetime.now(timezone.utc).timestamp(),
    }
    session[_PAT_PREVIEW_SESSION_KEY] = previews
    return {"token": token, "path": str(path)}


def _pat_preview_from_session(token: str) -> tuple[Path, str] | None:
    token_text = str(token or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", token_text):
        return None
    root = _pat_preview_root()
    previews = _pat_cleanup_preview_session(root)
    meta = previews.get(token_text)
    if not isinstance(meta, dict):
        return None
    path = Path(str(meta.get("path") or ""))
    try:
        resolved = path.resolve()
        if not (root in resolved.parents or resolved == root) or not resolved.exists():
            return None
    except Exception:
        return None
    return resolved, _pat_safe_preview_filename(str(meta.get("filename") or ""))


@api_v1_react.get("/pat/moduli/preview/<token>")
@_richiedi_auth
def pat_moduli_preview_pdf(token: str):
    preview = _pat_preview_from_session(token)
    if preview is None:
        return jsonify({"ok": False, "errore": "Anteprima modulo PAT non disponibile. Rigenera il modulo."}), 404
    path, filename = preview
    response = send_file(
        path,
        mimetype="application/pdf",
        as_attachment=request.args.get("download") == "1",
        download_name=filename,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@api_v1_react.route("/pst/pagopa-proxy/", defaults={"pst_path": ""}, methods=["GET", "POST"])
@api_v1_react.route("/pst/pagopa-proxy/<path:pst_path>", methods=["GET", "POST"])
@_richiedi_auth
def pst_pagopa_proxy(pst_path: str):
    target_url = _pst_pagopa_target_url(pst_path)
    if not target_url:
        return Response("Percorso PagoPA PST non consentito.", status=400, mimetype="text/plain; charset=utf-8")

    fascicolo_id = _pst_pagopa_fascicolo_id()
    cookies = dict(session.get("pst_pagopa_cookies") or {})
    headers = {
        "User-Agent": request.headers.get("User-Agent") or "IUSENTRA PagoPA PST bridge",
        "Accept": request.headers.get("Accept") or "*/*",
        "Accept-Language": request.headers.get("Accept-Language") or "it-IT,it;q=0.9",
        "Referer": _pst_pagopa_upstream_referer(target_url),
    }
    if request.method == "POST":
        content_type = request.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type
        elif "/dwr/call/" in urlparse(target_url).path:
            headers["Content-Type"] = "text/plain"
        headers["Origin"] = f"https://{PST_PAGOPA_HOST}"
    upstream_data = None
    if request.method == "POST":
        upstream_data = request.get_data()
        if "/dwr/call/" in urlparse(target_url).path:
            upstream_data = _pst_pagopa_rewrite_dwr_body(upstream_data, cookies)

    try:
        upstream = requests.request(
            request.method,
            target_url,
            headers=headers,
            data=upstream_data,
            cookies=cookies,
            timeout=PST_PAGOPA_TIMEOUT_SECONDS,
            verify=_pst_pagopa_verify_bundle(),
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        current_app.logger.warning("Bridge PagoPA PST non raggiungibile: %s", exc)
        return Response(
            "Portale PagoPA PST momentaneamente non raggiungibile. Riprova dalla modale del fascicolo.",
            status=502,
            mimetype="text/plain; charset=utf-8",
        )

    updated_cookies = dict(cookies)
    updated_cookies.update(upstream.cookies.get_dict())
    if updated_cookies:
        session["pst_pagopa_cookies"] = updated_cookies
        session.modified = True

    if 300 <= upstream.status_code < 400 and upstream.headers.get("Location"):
        location = _pst_pagopa_proxy_href(upstream.headers["Location"], base_url=target_url, fascicolo_id=fascicolo_id)
        return Response(status=upstream.status_code, headers={"Location": location})

    content_type = upstream.headers.get("Content-Type") or "application/octet-stream"
    body = upstream.content
    response_headers: dict[str, str] = {
        "Cache-Control": "no-store",
        "Content-Security-Policy": PST_PAGOPA_PROXY_CSP,
        "X-IUSENTRA-PagoPA-Bridge": "pst",
    }
    disposition = upstream.headers.get("Content-Disposition")
    if disposition:
        response_headers["Content-Disposition"] = disposition

    lower_content_type = content_type.lower()
    target_path_lower = urlparse(target_url).path.lower()
    is_pdf = "application/pdf" in lower_content_type or ".pdf" in str(disposition or "").lower()
    if is_pdf:
        filename = _pst_pagopa_filename(upstream, target_url)
        document_id = _pst_pagopa_capture_pdf(fascicolo_id, body, filename=filename, target_url=target_url)
        if document_id:
            response_headers["X-IUSENTRA-Fascicolo-Documento"] = document_id
            response_headers["X-IUSENTRA-Fascicolo"] = fascicolo_id
        if "Content-Disposition" not in response_headers:
            response_headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return Response(body, status=upstream.status_code, headers=response_headers, content_type="application/pdf")

    if target_path_lower.endswith("/resources/static/css/print.css") and "text/css" not in lower_content_type:
        return Response(
            "/* Foglio di stampa PST non disponibile nel bridge PagoPA IUSENTRA. */\n",
            status=200,
            headers=response_headers,
            content_type="text/css; charset=utf-8",
        )

    if any(marker in lower_content_type for marker in PST_PAGOPA_TEXT_TYPES):
        encoding = upstream.encoding or "utf-8"
        text = upstream.content.decode(encoding, errors="replace")
        is_javascript = "javascript" in lower_content_type or target_path_lower.endswith(".js")
        if is_javascript and "/pst/dwr/" in target_path_lower:
            text = _pst_pagopa_rewrite_dwr_javascript(text)
        elif not is_javascript:
            text = _pst_pagopa_rewrite_text(text, base_url=target_url, fascicolo_id=fascicolo_id)
            if "text/html" in lower_content_type:
                text = _pst_pagopa_inject_runtime_bridge(text, base_url=target_url, fascicolo_id=fascicolo_id)
        if "/dwr/call/" in target_path_lower:
            response_content_type = "text/plain; charset=utf-8"
        else:
            response_content_type = "text/html; charset=utf-8" if "application/xhtml+xml" in lower_content_type else content_type
        response_body = text.encode("utf-8")
        return _pst_pagopa_inline_text_response(
            response_body,
            status_code=upstream.status_code,
            response_headers=response_headers,
            content_type=response_content_type,
        )

    return Response(body, status=upstream.status_code, headers=response_headers, content_type=content_type)


@api_v1_react.post("/local-signer/diagnostics")
@_richiedi_auth
def local_signer_diagnostics_capture():
    payload, error = _request_json_object()
    if error:
        return error
    assert payload is not None
    now = _iso_now()
    context = _sanitize_local_signer_diagnostic(payload.get("context") or {})
    entry_seed = json.dumps(
        {"created_at": now, "context": context, "source": payload.get("source")},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    entry_id = hashlib.sha256(entry_seed.encode("utf-8")).hexdigest()[:16]
    entry = {
        "id": entry_id,
        "created_at": now,
        "actor": _actor_label(),
        "studio_context": _tenant_runtime_label(),
        "source": _diagnostic_text(payload.get("source") or "browser-local-signer"),
        "context": context,
        "local_signer": _sanitize_local_signer_diagnostic(payload.get("local_signer") or {}),
        "local_logs": _sanitize_local_signer_diagnostic(payload.get("local_logs") or {}),
        "result": _sanitize_local_signer_diagnostic(payload.get("result") or {}),
    }
    path = _local_signer_diagnostics_path()
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    _audit_event(
        "local_signer.diagnostica_salvata",
        "local_signer",
        entry_id,
        f"Diagnosi Local Signer salvata per {entry['source']}.",
    )
    return jsonify({
        "ok": True,
        "id": entry_id,
        "message": "Diagnosi Local Signer salvata sul server dello studio.",
    })


@api_v1_react.get("/local-signer/diagnostics/latest")
@_richiedi_auth
def local_signer_diagnostics_latest():
    try:
        limit = max(1, min(int(request.args.get("limit", "20")), 100))
    except ValueError:
        limit = 20
    return jsonify({"ok": True, "items": _read_local_signer_diagnostics(limit)})


@api_v1_react.get("/studio-modules/<module_id>")
@_richiedi_auth
def studio_module_react_payload(module_id: str):
    get_trattamenti = _core_runtime_func("get_trattamenti")
    return jsonify(build_react_studio_module_payload(
        module_id=module_id,
        config=current_app.config,
        get_utenti=get_utenti,
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_preventivi=get_preventivi_readonly,
        get_timesheet=get_timesheet,
        get_config_studio=_core_runtime_func("get_config_studio"),
        get_trattamenti=get_trattamenti,
        query=dict(request.args),
    ))


@api_v1_react.get("/editor-professionale")
@_richiedi_auth
def editor_professionale_react_payload():
    try:
        payload = build_react_document_archive_payload(
            get_fascicoli=_fascicoli_loader(),
            query=dict(request.args),
        )
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception("Archivio documentale React non disponibile: %s", exc)
        return jsonify(
            {
                "source": "errore_controllato",
                "contracts": {"mockFallback": False, "readOnly": False},
                "message": "Archivio documentale momentaneamente non disponibile. Riprova tra pochi secondi.",
                "summary": {"active": 0, "trash": 0, "matters": 0, "formats": 0},
                "facets": {"types": [], "formats": [], "matters": []},
                "pagination": {"page": 1, "perPage": 50, "pages": 1, "total": 0, "from": 0, "to": 0},
                "items": [],
                "actions": {
                    "newDocument": "/template-atti/editor",
                    "openMatters": "/fascicoli",
                    "searchStudio": "/global-search?tipo=documenti",
                },
            }
        ), 200


def _gestore_strumenti_legali_react() -> GestioneStrumentiLegali:
    return GestioneStrumentiLegali(
        normative_db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
    )


def _payload_bool(payload: Any, name: str, default: bool = False) -> bool:
    raw = payload.get(name, default) if hasattr(payload, "get") else default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else default
    return str(raw).strip().lower() in {"1", "true", "si", "sì", "yes", "on"}


def _payload_list(payload: Any, name: str) -> list[str]:
    if not hasattr(payload, "get"):
        return []
    if hasattr(payload, "getlist"):
        raw: Any = payload.getlist(name)
    else:
        raw = payload.get(name, [])
    values = raw if isinstance(raw, (list, tuple, set)) else str(raw or "").split(",")
    return [str(value).strip() for value in values if str(value).strip()]


def _uffici_competenti_result(payload: Any, schema: Mapping[str, Any]) -> dict[str, Any]:
    comune_codice = str(payload.get("comune_istat", "") if hasattr(payload, "get") else "").strip()
    comune_nome = str(payload.get("comune", "") if hasattr(payload, "get") else "").strip()
    comune_db = get_comune(codice_istat=comune_codice) if comune_codice else None
    comune_query = comune_db.giustizia_map_value if comune_db else comune_nome
    result = ricerca_uffici_competenti(
        comune_query,
        includi_speciali=_payload_bool(payload, "includi_speciali"),
        tipi_ufficio=_payload_list(payload, "tipo_ufficio"),
        solo_pec=_payload_bool(payload, "solo_pec"),
    )
    if comune_db:
        result["comune"] = comune_db.label
        result["comuneRecord"] = comune_db.to_dict()
    offices = list(result.get("offices") or [])
    table_rows = [
        [
            str(office.get("typeLabel") or ""),
            str(office.get("name") or ""),
            " - ".join(part for part in [str(office.get("address") or ""), str(office.get("city") or "")] if part),
            str(office.get("phone") or office.get("email") or office.get("pec") or ""),
        ]
        for office in offices[:12]
    ]
    return {
        "ok": True,
        "message": "Ricerca completata.",
        "toolId": "uffici_competenti",
        "title": schema.get("title", "Uffici competenti per Comune"),
        "metrics": [
            {"label": "Comune", "value": result.get("comune", ""), "note": "ricerca ministeriale"},
            {"label": "Uffici mostrati", "value": str(result.get("totalVisible", 0)), "note": "schede operative"},
            {"label": "Uffici fonte", "value": str(result.get("totalOfficial", 0)), "note": "risultati complessivi"},
        ],
        "tables": [
            {
                "title": "Riepilogo uffici",
                "headers": ["Tipo", "Ufficio", "Sede", "Recapito"],
                "rows": table_rows,
            }
        ] if table_rows else [],
        "previewText": "",
        "notes": list(result.get("notes") or []),
        "warnings": list(result.get("warnings") or []),
        "sources": [dict(result.get("source") or {})],
        "comuneRecord": result.get("comuneRecord"),
        "offices": offices,
    }


@api_v1_react.post("/strumenti-legali/<tool_id>")
@_richiedi_auth
def strumenti_legali_react_calcola(tool_id: str):
    schema = TOOL_SCHEMAS.get((tool_id or "").strip())
    if not schema:
        return jsonify({
            "ok": False,
            "message": "Strumento non disponibile.",
            "warnings": ["Seleziona una funzione presente nel catalogo strumenti."],
            "metrics": [],
            "tables": [],
            "previewText": "",
            "notes": [],
            "sources": [],
        }), 404
    payload = request.get_json(silent=True) if request.is_json else request.form
    method_name = str(schema.get("method") or "")
    try:
        if tool_id == "uffici_competenti":
            return jsonify(_uffici_competenti_result(payload, schema))
        result = getattr(_gestore_strumenti_legali_react(), method_name)(payload)
        normalised = build_tool_result(tool_id, result)
        return jsonify({
            "ok": True,
            "message": "Calcolo completato.",
            "toolId": tool_id,
            "title": schema.get("title", "Strumento forense"),
            "metrics": normalised["metrics"],
            "tables": normalised["tables"],
            "previewText": normalised["preview_text"],
            "notes": list(result.get("notes") or []),
            "warnings": list(result.get("warnings") or []),
            "sources": list(result.get("sources") or []),
        })
    except ValueError:
        message = "Verifica i dati inseriti e riprova."
        return jsonify({
            "ok": False,
            "message": message,
            "toolId": tool_id,
            "title": schema.get("title", "Strumento forense"),
            "metrics": [],
            "tables": [],
            "previewText": "",
            "notes": [],
            "warnings": [message],
            "sources": [],
        }), 200
    except Exception as exc:
        current_app.logger.exception("Errore strumenti legali React %s: %s", tool_id, exc)
        return jsonify({
            "ok": False,
            "message": "Non ho potuto completare il calcolo. Controlla i campi richiesti e riprova.",
            "toolId": tool_id,
            "title": schema.get("title", "Strumento forense"),
            "metrics": [],
            "tables": [],
            "previewText": "",
            "notes": [],
            "warnings": ["Il calcolo non è stato completato. Verifica i dati inseriti."],
            "sources": [],
        }), 200


@api_v1_react.get("/privacy/registro")
@_richiedi_auth
def privacy_registro_react_payload():
    get_trattamenti = _core_runtime_func("get_trattamenti")
    if not callable(get_trattamenti):
        return jsonify({
            "source": "errore_controllato",
            "generatedAt": _iso_now(),
            "summary": {
                "total": 0,
                "active": 0,
                "inactive": 0,
                "extraEu": 0,
                "missingSecurity": 0,
                "missingRetention": 0,
                "warnings": 0,
            },
            "treatments": [],
            "actions": {
                "create": "/privacy/registro/nuovo",
                "list": "/privacy/registro",
                "audit": "/audit",
                "exportAuditCsv": "/audit/esporta.csv",
                "clienti": "/clienti",
                "settings": "/impostazioni",
                "lex": "#lex",
            },
            "contracts": {
                "mock_fallback": False,
                "writes": "operational_routes",
                "route_owner": "react_shell",
            },
            "warning": "Repository privacy non disponibile nel runtime corrente.",
        })
    return jsonify(build_react_privacy_registro_payload(
        get_trattamenti,
        path=request.args.get("path", "/privacy/registro"),
    ))


@api_v1_react.get("/admin/database")
@_richiedi_auth
def admin_database_react_payload():
    if not _puo_leggere_admin_database():
        return jsonify({"errore": "Accesso riservato agli amministratori.", "codice": 403}), 403

    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    get_database = core_runtime.get("get_database")
    latest_sqlite_snapshot_path = core_runtime.get("latest_sqlite_snapshot_path")
    if not callable(get_database) or not callable(latest_sqlite_snapshot_path):
        return jsonify(build_react_admin_database_error_payload("Runtime database non disponibile.")), 200

    try:
        admin_anchor = _cfg_value("CLIENTI_DB", "")
        storage_runtime = get_request_storage_runtime(admin_anchor).to_dict() if admin_anchor else {}
        return jsonify(build_react_admin_database_payload(
            get_database,
            latest_sqlite_snapshot_path,
            backup_dir=_cfg_value("BACKUP_DIR", "./backup"),
            studio_db_path=str(storage_runtime.get("studio_db_path") or _cfg_value("STUDIO_DB", "")),
            storage_runtime=storage_runtime,
            path=request.args.get("path", "/admin/database"),
        ))
    except Exception as exc:
        current_app.logger.exception("Bridge React database non disponibile: %s", exc)
        return jsonify(build_react_admin_database_error_payload("Database non disponibile dal runtime corrente.")), 200


@api_v1_react.get("/import/quickorganizer")
@_richiedi_auth
def studio_telematico_import_react_payload():
    return jsonify(_studio_telematico_import_page(request.args.get("path", "/import/quickorganizer")))


@api_v1_react.post("/import/quickorganizer/preparazione")
@_richiedi_auth
def studio_telematico_auto_prepare_start():
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    try:
        session_payload = begin_auto_prepare_session(
            _studio_telematico_prepare_root(),
            _studio_telematico_staging_root(),
        )
        token = str(session_payload.pop("token"))
        session_id = str(session_payload.get("sessionId") or "")
        session_payload["downloadUrl"] = url_for(
            "api_v1_react.studio_telematico_auto_prepare_launcher",
            session_id=session_id,
            token=token,
            _external=True,
        )
        session_payload["statusUrl"] = url_for(
            "api_v1_react.studio_telematico_auto_prepare_status",
            session_id=session_id,
            _external=True,
        )
        session_payload["canAutoUpload"] = True
        _audit_event(
            "studio_telematico.preparazione_avviata",
            "import_pratiche",
            session_id,
            "Avviata preparazione assistita pacchetto pratiche.",
        )
        return jsonify(session_payload)
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "preparazione_non_avviata"}), 400


@api_v1_react.get("/import/quickorganizer/preparazione/<session_id>")
@_richiedi_auth
def studio_telematico_auto_prepare_status(session_id: str):
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    try:
        return jsonify(auto_prepare_status(_studio_telematico_prepare_root(), session_id))
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "preparazione_non_trovata"}), 404


@api_v1_react.get("/import/quickorganizer/preparazione/<session_id>/avviatore.cmd")
@_richiedi_auth
def studio_telematico_auto_prepare_launcher(session_id: str):
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    token = _studio_telematico_public_token()
    try:
        update_auto_prepare_status(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            status="pending",
            progress=0,
            detail="Avviatore scaricato: apri il file per preparare e caricare il pacchetto.",
        )
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "preparazione_non_autorizzata"}), 403

    base_url = url_for(
        "api_v1_react.studio_telematico_auto_prepare_public_status",
        session_id=session_id,
        _external=True,
    ).rsplit("/stato", 1)[0]
    helper_url = f"{request.url_root.rstrip('/')}/static/tools/PreparaPacchettoPratiche.exe"
    script = "\r\n".join(
        [
            "@echo off",
            "setlocal",
            f"set \"SCRIPT_URL={helper_url}\"",
            f"set \"SESSION_ID={session_id}\"",
            f"set \"BASE_URL={base_url}\"",
            f"set \"TOKEN={token}\"",
            "set \"TARGET=%TEMP%\\iusentra-prepara-import-pratiche-%SESSION_ID%.exe\"",
            (
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
                "\"Invoke-WebRequest -Uri '%SCRIPT_URL%' -OutFile '%TARGET%' -UseBasicParsing\""
            ),
            "if errorlevel 1 exit /b %ERRORLEVEL%",
            (
                "\"%TARGET%\" "
                "-AutoUploadBaseUrl \"%BASE_URL%\" -AutoUploadToken \"%TOKEN%\" -AutoSessionId \"%SESSION_ID%\""
            ),
            "exit /b %ERRORLEVEL%",
            "",
        ]
    )
    response = current_app.response_class(script, mimetype="text/plain; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="AvviaImportPratiche.cmd"'
    return response


@api_v1_react.post("/import/quickorganizer/preparazione/<session_id>/stato")
@_richiedi_auth_studio_telematico_token
def studio_telematico_auto_prepare_public_status(session_id: str):
    body = getattr(g, "studio_telematico_auto_prepare_body", {}) or {}
    token = str(getattr(g, "studio_telematico_auto_prepare_token", ""))
    try:
        return jsonify(update_auto_prepare_status(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            status=str(body.get("status") or body.get("stato") or ""),
            progress=body.get("progress") or body.get("percentuale"),
            detail=str(body.get("detail") or body.get("dettaglio") or ""),
            errore=str(body.get("errore") or body.get("error") or ""),
        ))
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "preparazione_non_autorizzata"}), 403


@api_v1_react.post("/import/quickorganizer/preparazione/<session_id>/upload-session")
@_richiedi_auth_studio_telematico_token
def studio_telematico_auto_prepare_upload_session(session_id: str):
    body = getattr(g, "studio_telematico_auto_prepare_body", {}) or {}
    token = str(getattr(g, "studio_telematico_auto_prepare_token", ""))
    try:
        upload = start_auto_prepare_upload(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            filename=str(body.get("filename") or body.get("name") or "pacchetto.zip"),
            total_size=int(body.get("totalSize") or body.get("size") or 0),
            chunk_size=_STUDIO_TELEMATICO_CHUNK_SIZE_BYTES,
            max_size=max_chunked_upload_bytes(),
        )
        return jsonify(upload)
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "upload_non_valido"}), 400
    except ValueError:
        return jsonify({"ok": False, "errore": "Dimensione pacchetto non valida.", "codice": "upload_non_valido"}), 400


@api_v1_react.post("/import/quickorganizer/preparazione/<session_id>/upload-session/<upload_id>/chunk")
@_richiedi_auth_studio_telematico_token
def studio_telematico_auto_prepare_upload_chunk(session_id: str, upload_id: str):
    token = str(getattr(g, "studio_telematico_auto_prepare_token", ""))
    uploaded = request.files.get("chunk") or request.files.get("file") or _RequestBodyStorage(request.stream)
    try:
        index = int(request.form.get("index") or request.args.get("index") or 0)
        total_chunks = int(request.form.get("totalChunks") or request.args.get("totalChunks") or 0)
        return jsonify(receive_auto_prepare_chunk(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            upload_id,
            index,
            total_chunks,
            uploaded,
        ))
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "upload_non_valido"}), 400
    except ValueError:
        return jsonify({"ok": False, "errore": "Indice del blocco non valido.", "codice": "upload_non_valido"}), 400


@api_v1_react.post("/import/quickorganizer/preparazione/<session_id>/upload-session/<upload_id>/completa")
@_richiedi_auth_studio_telematico_token
def studio_telematico_auto_prepare_upload_complete(session_id: str, upload_id: str):
    body = getattr(g, "studio_telematico_auto_prepare_body", {}) or {}
    token = str(getattr(g, "studio_telematico_auto_prepare_token", ""))
    try:
        total_chunks = body.get("totalChunks") or request.args.get("totalChunks")
        stage = complete_auto_prepare_upload(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            upload_id,
            total_chunks=int(total_chunks) if total_chunks not in (None, "") else None,
        )
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "import_non_valido"}), 400
    except Exception as exc:  # noqa: BLE001 - archivi cliente possono contenere dati non coerenti
        current_app.logger.exception("Completamento preparazione import pratiche non riuscito: %s", exc)
        update_auto_prepare_status(
            _studio_telematico_prepare_root(),
            session_id,
            token,
            status="error",
            progress=100,
            detail="Il pacchetto non è leggibile. Verifica di aver incluso pratiche e documenti collegati.",
            errore="Il pacchetto non è leggibile. Verifica di aver incluso pratiche e documenti collegati.",
        )
        return jsonify({"ok": False, "errore": "Il pacchetto non è leggibile. Verifica di aver incluso pratiche e documenti collegati."}), 400

    summary = stage.get("analysis", {}).get("summary", {}) if isinstance(stage.get("analysis"), dict) else {}
    _audit_event(
        "studio_telematico.import_anteprima",
        "import_pratiche",
        str(stage.get("importId") or ""),
        f"Controllate {summary.get('matters', 0)} pratiche dal pacchetto import.",
    )
    return jsonify(stage)


@api_v1_react.post("/import/quickorganizer/upload-session")
@_richiedi_auth
def studio_telematico_import_upload_session():
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    body = _request_payload()
    filename = str(body.get("filename") or body.get("name") or "pacchetto.zip")
    total_size = int(body.get("totalSize") or body.get("size") or 0)
    try:
        session = begin_chunked_upload(
            filename,
            total_size,
            _studio_telematico_staging_root(),
            chunk_size=_STUDIO_TELEMATICO_CHUNK_SIZE_BYTES,
            max_size=max_chunked_upload_bytes(),
        )
        return jsonify({"ok": True, **session})
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "upload_non_valido"}), 400


@api_v1_react.post("/import/quickorganizer/upload-session/<upload_id>/chunk")
@_richiedi_auth
def studio_telematico_import_upload_chunk(upload_id: str):
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    uploaded = request.files.get("chunk") or request.files.get("file")
    if not uploaded:
        return jsonify({"ok": False, "errore": "Blocco del pacchetto non ricevuto.", "codice": "upload_non_valido"}), 400
    try:
        index = int(request.form.get("index") or request.args.get("index") or 0)
        total_chunks = int(request.form.get("totalChunks") or request.args.get("totalChunks") or 0)
        result = receive_chunked_upload(
            _studio_telematico_staging_root(),
            upload_id,
            index,
            total_chunks,
            uploaded,
        )
        return jsonify(result)
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "upload_non_valido"}), 400
    except ValueError:
        return jsonify({"ok": False, "errore": "Indice del blocco non valido.", "codice": "upload_non_valido"}), 400


@api_v1_react.post("/import/quickorganizer/upload-session/<upload_id>/completa")
@_richiedi_auth
def studio_telematico_import_upload_complete(upload_id: str):
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403
    body = _request_payload()
    try:
        total_chunks = body.get("totalChunks")
        stage = complete_chunked_upload(
            _studio_telematico_staging_root(),
            upload_id,
            total_chunks=int(total_chunks) if total_chunks not in (None, "") else None,
        )
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "import_non_valido"}), 400
    except Exception as exc:  # noqa: BLE001 - archivi cliente possono contenere dati non coerenti
        current_app.logger.exception("Completamento upload import pratiche non riuscito: %s", exc)
        return jsonify({"ok": False, "errore": "Il pacchetto non è leggibile. Verifica di aver incluso pratiche e documenti collegati."}), 400

    summary = stage.get("analysis", {}).get("summary", {}) if isinstance(stage.get("analysis"), dict) else {}
    _audit_event(
        "studio_telematico.import_anteprima",
        "import_pratiche",
        str(stage.get("importId") or ""),
        f"Controllate {summary.get('matters', 0)} pratiche dal pacchetto import.",
    )
    return jsonify({"ok": True, **stage})


@api_v1_react.post("/import/quickorganizer/anteprima")
@_richiedi_auth
def studio_telematico_import_preview():
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403

    uploaded = request.files.get("pacchetto") or request.files.get("package")
    body = _request_payload() if not uploaded else {}
    source_path = str(body.get("sourcePath") or body.get("source_path") or "").strip()
    if (not uploaded or not str(getattr(uploaded, "filename", "") or "").strip()) and not source_path:
        return jsonify({"ok": False, "errore": "Seleziona il pacchetto pratiche da controllare."}), 400

    if source_path:
        if not _studio_telematico_local_path_enabled():
            return jsonify({
                "ok": False,
                "errore": "Il controllo tramite percorso locale è disponibile solo dall'app installata su questo PC.",
                "codice": "percorso_locale_non_disponibile",
            }), 400
        try:
            stage = stage_referenced_package(source_path, _studio_telematico_staging_root())
        except QuickOrganizerImportError as exc:
            return jsonify({"ok": False, "errore": exc.public_message, "codice": "import_non_valido"}), 400
        except Exception as exc:  # noqa: BLE001 - risposta controllata per import da archivi esterni
            current_app.logger.exception("Anteprima import pratiche da percorso locale non riuscita: %s", exc)
            return jsonify({"ok": False, "errore": "Il pacchetto indicato non è leggibile. Verifica percorso, pratiche e documenti collegati."}), 400

        summary = stage.get("analysis", {}).get("summary", {}) if isinstance(stage.get("analysis"), dict) else {}
        _audit_event(
            "studio_telematico.import_anteprima",
            "import_pratiche",
            str(stage.get("importId") or ""),
        f"Controllate {summary.get('matters', 0)} pratiche dal pacchetto import.",
        )
        public_stage = dict(stage)
        public_stage.pop("sourcePath", None)
        return jsonify({"ok": True, **public_stage})

    temp_path = save_upload_to_temp(uploaded)
    try:
        stage = stage_uploaded_package(temp_path, _studio_telematico_staging_root())
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "import_non_valido"}), 400
    except Exception as exc:  # noqa: BLE001 - risposta controllata per import da archivi esterni
        current_app.logger.exception("Anteprima import pratiche non riuscita: %s", exc)
        return jsonify({"ok": False, "errore": "Il pacchetto non è leggibile. Verifica di aver incluso pratiche e documenti collegati."}), 400
    finally:
        cleanup_upload_temp(temp_path)

    summary = stage.get("analysis", {}).get("summary", {}) if isinstance(stage.get("analysis"), dict) else {}
    _audit_event(
        "studio_telematico.import_anteprima",
        "import_pratiche",
        str(stage.get("importId") or ""),
        f"Controllate {summary.get('matters', 0)} pratiche dal pacchetto import.",
    )
    return jsonify({"ok": True, **stage})


@api_v1_react.post("/import/quickorganizer/esegui")
@_richiedi_auth
def studio_telematico_import_run():
    if not _puo_importare_studio_telematico():
        return jsonify({"ok": False, "errore": "Profilo non autorizzato all'importazione pratiche.", "codice": 403}), 403

    body = _request_payload()
    import_id = str(body.get("importId") or body.get("import_id") or "").strip()
    allow_partial = bool(body.get("allowPartial") or body.get("importaParziale") or body.get("allow_partial"))
    if not import_id:
        return jsonify({"ok": False, "errore": "Anteprima non trovata. Carica di nuovo il pacchetto."}), 400

    try:
        storage_guard = _studio_telematico_storage_guard()
        package, stage = load_staged_package(_studio_telematico_staging_root(), import_id)
        result = import_quickorganizer_package(
            package,
            fascicoli=_fascicoli_loader()(),
            clienti=get_clienti(),
            soggetti=get_soggetti(),
            agenda_repo=get_agenda(),
            actor=_actor_label(),
            allow_partial=allow_partial,
        )
    except QuickOrganizerImportError as exc:
        return jsonify({"ok": False, "errore": exc.public_message, "codice": "import_non_completato"}), 400
    except Exception as exc:  # noqa: BLE001 - archivi cliente possono contenere dati non coerenti
        current_app.logger.exception("Import pratiche non riuscito: %s", exc)
        return jsonify({"ok": False, "errore": "Import non completato. Nessun passaggio successivo è stato avviato automaticamente."}), 400

    clear_dashboard_payload_cache()
    _clear_fascicoli_list_payload_cache()
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    _audit_event(
        "studio_telematico.import_esegui",
        "import_pratiche",
        import_id,
        (
            f"Importate {summary.get('mattersCreated', 0)} nuove pratiche e aggiornate "
            f"{summary.get('mattersUpdated', 0)} pratiche già presenti."
        ),
    )
    return jsonify({
        "ok": True,
        "importId": import_id,
        "sourceName": stage.get("sourceName", ""),
        "storage": storage_guard,
        **result,
    })


# IUSENTRA_REACT_FASCICOLI_ROUTES_START
_FASCICOLI_LIST_PAYLOAD_CACHE = ReactPayloadTTLCache(
    ttl_seconds=float(os.getenv("IUSENTRA_REACT_FASCICOLI_LIST_TTL_SECONDS") or 90),
    max_entries=int(os.getenv("IUSENTRA_REACT_FASCICOLI_LIST_MAX_ENTRIES") or 256),
)


def _clear_fascicoli_list_payload_cache() -> None:
    _FASCICOLI_LIST_PAYLOAD_CACHE.clear()
    clear_react_fascicoli_base_cache()


def clear_react_fascicoli_list_payload_cache() -> None:
    """Svuota la cache della lista fascicoli dopo modifiche a fascicoli o documenti."""

    _clear_fascicoli_list_payload_cache()


_FASCICOLI_FILTER_PREFERENCES_SECTION = "fascicoli_filtri"
_FASCICOLI_FILTER_SORTS = {
    "recenti", "rg", "cliente", "scadenza", "documenti", "titolo", "ufficio", "apertura",
    "stato", "gruppo", "responsabile", "valore",
}
_FASCICOLI_FILTER_STATUSES = {"tutti", "aperto", "in_corso", "definito", "da_archiviare", "archiviato", "sospeso"}
_FASCICOLI_FILTER_TYPES = {
    "tutti",
    "civile",
    "penale",
    "amministrativo",
    "tributario",
    "stragiudiziale",
    "consulenza",
    "lavoro",
    "famiglia",
    "successioni",
    "altro",
}
_FASCICOLI_FILTER_PAYMENT_STATUSES = {"tutti", "non_previsto", "da_registrare", "pagato", "parziale", "da_emettere"}
_FASCICOLI_FILTER_VIEWS = {"operativa", "economica"}
_FASCICOLI_DISPLAY_MODES = {"tabella", "compatta", "schede"}
_FASCICOLI_GROUP_MODES = {"nessuno", "gruppo", "stato", "tipo", "ufficio", "anno", "responsabile"}
_FASCICOLI_ROW_DENSITIES = {"compatta", "adattiva"}
_FASCICOLI_TABLE_COLUMNS = {
    "ref", "internal_ref", "title", "object", "type", "client", "court", "procedure_type",
    "register", "section", "section_role", "judge", "opposing_lawyer", "holder", "responsible",
    "counterparty", "claimant", "clerk", "ctu", "ctp", "notes", "operational_status", "custom_1",
    "custom_2", "group", "case_value", "rg", "rg_number", "rg_year", "next_deadline", "status",
    "documents", "unread_communications", "alerts", "opened_at", "closed_at", "updated_at",
}
_FASCICOLI_DEFAULT_TABLE_COLUMNS = [
    "ref", "title", "type", "client", "rg", "next_deadline", "status", "documents",
]
_FASCICOLI_FIELD_FILTER_ARGS: dict[str, tuple[str, ...]] = {
    "register": ("f_register",),
    "value": ("f_value",),
    "holder": ("f_holder",),
    "responsible": ("f_responsible",),
    "object": ("f_object",),
    "denomination": ("f_denomination",),
    "internal_ref": ("f_internal_ref",),
    "rg_year": ("f_rg_year",),
    "opened_year": ("f_opened_year",),
    "archived_year": ("f_archived_year",),
    "court": ("f_court",),
    "rg": ("f_rg",),
    "section": ("f_section",),
    "section_role": ("f_section_role",),
    "judge": ("f_judge",),
    "opposing_lawyer": ("f_opposing_lawyer",),
    "notes": ("f_notes",),
    "clerk": ("f_clerk",),
    "ctu": ("f_ctu",),
    "ctp": ("f_ctp",),
    "operational_status": ("f_operational_status",),
    "claimant": ("f_claimant",),
    "respondent": ("f_respondent",),
    "custom_1": ("f_custom_1",),
    "custom_2": ("f_custom_2",),
    "group": ("f_group",),
}


def _fascicoli_request_field_filters() -> dict[str, str]:
    return {
        field: next(
            (request.args.get(name, "").strip()[:160] for name in names if request.args.get(name, "").strip()),
            "",
        )
        for field, names in _FASCICOLI_FIELD_FILTER_ARGS.items()
    }


def _fascicoli_filter_preferences_defaults() -> dict[str, Any]:
    return {
        "type": "tutti",
        "status": "tutti",
        "sort": "rg",
        "secondarySort": "",
        "view": "operativa",
        "displayMode": "tabella",
        "groupBy": "nessuno",
        "visibleColumns": list(_FASCICOLI_DEFAULT_TABLE_COLUMNS),
        "rowDensity": "compatta",
        "court": "",
        "fieldFilters": {},
        "alertsOnly": False,
        "paymentsOnly": False,
        "missingRgOnly": False,
        "duplicatesOnly": False,
        "cu": "tutti",
        "liquidazione": "tutti",
        "parcella": "tutti",
        "pageSize": 25,
    }


def _fascicoli_filter_choice(value: Any, allowed: set[str], default: str) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in allowed else default


def _fascicoli_filter_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "si", "sì", "yes", "on"}


def _fascicoli_filter_preferences_payload(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(raw or {})
    defaults = _fascicoli_filter_preferences_defaults()
    try:
        page_size = int(source.get("pageSize") or source.get("page_size") or defaults["pageSize"])
    except (TypeError, ValueError):
        page_size = defaults["pageSize"]
    raw_field_filters = source.get("fieldFilters") if isinstance(source.get("fieldFilters"), Mapping) else source.get("field_filters")
    field_filters = {
        field: str((raw_field_filters or {}).get(field) or "").strip()[:160]
        for field in _FASCICOLI_FIELD_FILTER_ARGS
        if str((raw_field_filters or {}).get(field) or "").strip()
    }
    raw_visible_columns = source.get("visibleColumns") if isinstance(source.get("visibleColumns"), list) else source.get("visible_columns")
    visible_columns = []
    for value in raw_visible_columns if isinstance(raw_visible_columns, list) else []:
        column = str(value or "").strip().lower()
        if column in _FASCICOLI_TABLE_COLUMNS and column not in visible_columns:
            visible_columns.append(column)
    for required_column in ("ref", "title"):
        if required_column not in visible_columns:
            visible_columns.insert(0 if required_column == "ref" else 1, required_column)
    if len(visible_columns) <= 2 and not raw_visible_columns:
        visible_columns = list(defaults["visibleColumns"])
    return {
        "type": _fascicoli_filter_choice(source.get("type"), _FASCICOLI_FILTER_TYPES, defaults["type"]),
        "status": _fascicoli_filter_choice(source.get("status"), _FASCICOLI_FILTER_STATUSES, defaults["status"]),
        "sort": _fascicoli_filter_choice(source.get("sort"), _FASCICOLI_FILTER_SORTS, defaults["sort"]),
        "secondarySort": _fascicoli_filter_choice(
            source.get("secondarySort") or source.get("secondary_sort"),
            _FASCICOLI_FILTER_SORTS | {""},
            defaults["secondarySort"],
        ),
        "view": _fascicoli_filter_choice(source.get("view"), _FASCICOLI_FILTER_VIEWS, defaults["view"]),
        "displayMode": _fascicoli_filter_choice(
            source.get("displayMode") or source.get("display_mode"),
            _FASCICOLI_DISPLAY_MODES,
            defaults["displayMode"],
        ),
        "groupBy": _fascicoli_filter_choice(
            source.get("groupBy") or source.get("group_by"),
            _FASCICOLI_GROUP_MODES,
            defaults["groupBy"],
        ),
        "visibleColumns": visible_columns,
        "rowDensity": _fascicoli_filter_choice(
            source.get("rowDensity") or source.get("row_density"),
            _FASCICOLI_ROW_DENSITIES,
            defaults["rowDensity"],
        ),
        "court": str(source.get("court") or "").strip()[:120],
        "fieldFilters": field_filters,
        "alertsOnly": _fascicoli_filter_bool(source.get("alertsOnly") if "alertsOnly" in source else source.get("alerts_only")),
        "paymentsOnly": _fascicoli_filter_bool(source.get("paymentsOnly") if "paymentsOnly" in source else source.get("payments_only")),
        "missingRgOnly": _fascicoli_filter_bool(source.get("missingRgOnly") if "missingRgOnly" in source else source.get("missing_rg_only")),
        "duplicatesOnly": _fascicoli_filter_bool(source.get("duplicatesOnly") if "duplicatesOnly" in source else source.get("duplicates_only")),
        "cu": _fascicoli_filter_choice(source.get("cu"), _FASCICOLI_FILTER_PAYMENT_STATUSES, defaults["cu"]),
        "liquidazione": _fascicoli_filter_choice(source.get("liquidazione"), _FASCICOLI_FILTER_PAYMENT_STATUSES, defaults["liquidazione"]),
        "parcella": _fascicoli_filter_choice(source.get("parcella"), _FASCICOLI_FILTER_PAYMENT_STATUSES, defaults["parcella"]),
        "pageSize": max(5, min(100, page_size)),
    }


def _fascicoli_filter_preferences_studio_db():
    anchor = tenant_data_path("FASCICOLI_DB", "./fascicoli/fascicoli.json", require_tenant=True)
    return get_request_studio_db(anchor)


def _fascicoli_filter_preferences_sqlite_path() -> Path:
    anchor = Path(tenant_data_path("FASCICOLI_DB", "./fascicoli/fascicoli.json", require_tenant=True)).resolve()
    return anchor.parent / "ui_preferences.db"


def _fascicoli_filter_preferences_sqlite_load() -> dict[str, Any]:
    db_path = _fascicoli_filter_preferences_sqlite_path()
    if not db_path.exists():
        return {}
    with sqlite3.connect(str(db_path), timeout=2.0) as conn:
        conn.execute("PRAGMA busy_timeout=2000")
        row = conn.execute(
            """
            SELECT updated_at, dati_json
            FROM ui_preferences
            WHERE scope = ?
            """,
            (_FASCICOLI_FILTER_PREFERENCES_SECTION,),
        ).fetchone()
    if not row:
        return {}
    try:
        stored = json.loads(row[1] or "{}")
    except json.JSONDecodeError:
        stored = {}
    if not isinstance(stored, dict):
        return {}
    if "updatedAt" not in stored:
        stored["updatedAt"] = row[0]
    return stored


def _fascicoli_filter_preferences_sqlite_save(stored: Mapping[str, Any], updated_at: str) -> None:
    db_path = _fascicoli_filter_preferences_sqlite_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ui_preferences (
                scope TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'react_fascicoli',
                dati_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_ui_preferences_updated ON ui_preferences(updated_at);
            """
        )
        conn.execute(
            """
            INSERT INTO ui_preferences
            (scope, updated_at, source, dati_json)
            VALUES (?,?,?,?)
            ON CONFLICT(scope) DO UPDATE SET
                updated_at = excluded.updated_at,
                source = excluded.source,
                dati_json = excluded.dati_json
            """,
            (
                _FASCICOLI_FILTER_PREFERENCES_SECTION,
                updated_at,
                "react_fascicoli",
                json.dumps(dict(stored), ensure_ascii=False, separators=(",", ":")),
            ),
        )


def _load_fascicoli_filter_preferences() -> dict[str, Any]:
    from pct.impostazioni_config_repository import load_settings_config_section

    stored_sqlite = _fascicoli_filter_preferences_sqlite_load()
    if stored_sqlite:
        preferences = _fascicoli_filter_preferences_payload(
            stored_sqlite.get("preferences") if isinstance(stored_sqlite.get("preferences"), dict) else stored_sqlite
        )
        return {
            "ok": True,
            "configured": True,
            "updatedAt": str(stored_sqlite.get("updatedAt") or stored_sqlite.get("updated_at") or ""),
            "preferences": preferences,
        }

    studio_db = _fascicoli_filter_preferences_studio_db()
    try:
        stored = load_settings_config_section(studio_db, _FASCICOLI_FILTER_PREFERENCES_SECTION)
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc).lower():
            raise
        stored = {}
    preferences = _fascicoli_filter_preferences_payload(stored.get("preferences") if isinstance(stored.get("preferences"), dict) else stored)
    return {
        "ok": True,
        "configured": bool(stored),
        "updatedAt": str(stored.get("updatedAt") or stored.get("updated_at") or ""),
        "preferences": preferences,
    }


def _save_fascicoli_filter_preferences(payload: Mapping[str, Any]) -> dict[str, Any]:
    from pct.impostazioni_config_repository import ensure_settings_config_schema

    studio_db = _fascicoli_filter_preferences_studio_db()
    if studio_db is None:
        return {
            "ok": False,
            "message": "Preferenze filtri non salvate: archivio strutturato dello studio non disponibile.",
        }
    preferences = _fascicoli_filter_preferences_payload(payload)
    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    stored = {
        "preferences": preferences,
        "updatedAt": updated_at,
    }
    row = {
        "section": _FASCICOLI_FILTER_PREFERENCES_SECTION,
        "updated_at": updated_at,
        "source": "react_fascicoli",
        "secret_fields_json": "[]",
        "dati_json": json.dumps(stored, ensure_ascii=False, separators=(",", ":")),
    }

    if str(getattr(studio_db, "backend_kind", "")).lower() != "postgresql":
        _fascicoli_filter_preferences_sqlite_save(stored, updated_at)
        return {
            "ok": True,
            "configured": True,
            "updatedAt": updated_at,
            "preferences": preferences,
            "message": "Vista fascicoli salvata per questo studio.",
        }

    ensure_settings_config_schema(studio_db)

    def _insert(conn: Any, item: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO settings_config
            (section, updated_at, source, secret_fields_json, dati_json)
            VALUES (?,?,?,?,?)
            ON CONFLICT(section) DO UPDATE SET
                updated_at = excluded.updated_at,
                source = excluded.source,
                secret_fields_json = excluded.secret_fields_json,
                dati_json = excluded.dati_json
            """,
            (
                item["section"],
                item["updated_at"],
                item["source"],
                item["secret_fields_json"],
                item["dati_json"],
            ),
        )

    studio_db.salva_tabella("settings_config", [row], _insert, delete_all=False)
    return {
        "ok": True,
        "configured": True,
        "updatedAt": updated_at,
        "preferences": preferences,
        "message": "Vista fascicoli salvata per questo studio.",
    }


@api_v1_react.get("/fascicoli/preferenze-filtri")
@_richiedi_auth
def fascicoli_react_filter_preferences():
    try:
        return jsonify(_load_fascicoli_filter_preferences())
    except TenantDataPathError as exc:
        return _tenant_data_path_error(exc)


@api_v1_react.post("/fascicoli/preferenze-filtri")
@_richiedi_auth
def fascicoli_react_save_filter_preferences():
    payload, error = _request_json_object()
    if error:
        return error
    try:
        result = _save_fascicoli_filter_preferences(payload)
    except TenantDataPathError as exc:
        return _tenant_data_path_error(exc)
    status_code = 200 if result.get("ok") else 409
    if result.get("ok"):
        _audit_event(
            "fascicoli.preferenze_filtri_salvate",
            "fascicoli",
            "preferenze-filtri",
            "Preferenze filtri fascicoli aggiornate.",
        )
    return jsonify(result), status_code


def _fascicoli_list_cache_key() -> tuple | None:
    if not _FASCICOLI_LIST_PAYLOAD_CACHE.enabled:
        return None
    tenant = getattr(g, "tenant", None)
    tenant_slug = str(
        getattr(tenant, "slug", "") or getattr(g, "tenant_context_slug", "") or ""
    ).strip().lower()
    if not tenant_slug:
        for config_key in ("DATA_ROOT", "FASCICOLI_DB", "CLIENTI_DB"):
            value = current_app.config.get(config_key)
            if value:
                tenant_slug = str(value).strip().lower()
                break
    user = getattr(g, "user", None) or getattr(g, "utente_corrente", None)
    user_key = str(
        getattr(user, "id", "")
        or getattr(user, "username", "")
        or getattr(user, "email", "")
        or "api"
    ).strip().lower()
    args = (
        ("page", str(_request_int("page", default=1))),
        ("page_size", str(_request_int("page_size", "pageSize", default=5))),
        ("q", request.args.get("q", "").strip()),
        ("client", request.args.get("client", "").strip()),
        ("rg", request.args.get("rg", "").strip()),
        ("type", request.args.get("type", "").strip()),
        ("status", request.args.get("status", "").strip()),
        ("court", request.args.get("court", "").strip()),
        ("sort", request.args.get("sort", "rg").strip() or "rg"),
        ("secondary_sort", request.args.get("secondary_sort", "").strip()),
        ("group_by", request.args.get("group_by", "").strip()),
        ("view", (request.args.get("view", "") or request.args.get("vista", "")).strip()),
        ("alerts_only", "1" if (_request_bool("alerts_only") or _request_bool("alertsOnly")) else "0"),
        ("payments_only", "1" if (_request_bool("payments_only") or _request_bool("paymentsOnly")) else "0"),
        ("missing_rg_only", "1" if (_request_bool("missing_rg_only") or _request_bool("missingRgOnly")) else "0"),
        ("duplicates_only", "1" if (_request_bool("duplicates_only") or _request_bool("duplicatesOnly")) else "0"),
        ("cu", (request.args.get("cu", "") or request.args.get("contributo_unificato", "")).strip()),
        ("fondo_spese", (request.args.get("fondo_spese", "") or request.args.get("fondoSpese", "")).strip()),
        ("liquidazione", (request.args.get("liquidazione", "") or request.args.get("liquidazione_giudice", "")).strip()),
        ("parcella", request.args.get("parcella", "").strip()),
        *(('field_' + field, value) for field, value in sorted(_fascicoli_request_field_filters().items())),
    )
    return ("fascicoli-list", tenant_slug, user_key, args)


@api_v1_react.get("/fascicoli")
@_richiedi_auth
def fascicoli_react_list():
    cache_key = _fascicoli_list_cache_key()
    if cache_key is not None:
        cached = _FASCICOLI_LIST_PAYLOAD_CACHE.get(cache_key)
        if cached is not None:
            return current_app.response_class(cached, mimetype="application/json")
    response = jsonify(build_react_fascicoli_payload(
        get_fascicoli=_fascicoli_loader(),
        get_scadenziario=get_scadenziario,
        get_fatturazione=get_fatturazione,
        page=_request_int("page", default=1),
        page_size=_request_int("page_size", "pageSize", default=5),
        query=request.args.get("q", ""),
        client_filter=request.args.get("client", ""),
        rg_filter=request.args.get("rg", ""),
        type_filter=request.args.get("type", ""),
        status_filter=request.args.get("status", ""),
        court=request.args.get("court", ""),
        sort=request.args.get("sort", "rg"),
        secondary_sort=request.args.get("secondary_sort", ""),
        group_by=request.args.get("group_by", ""),
        view=request.args.get("view", "") or request.args.get("vista", ""),
        alerts_only=_request_bool("alerts_only") or _request_bool("alertsOnly"),
        payments_only=_request_bool("payments_only") or _request_bool("paymentsOnly"),
        missing_rg_only=_request_bool("missing_rg_only") or _request_bool("missingRgOnly"),
        duplicates_only=_request_bool("duplicates_only") or _request_bool("duplicatesOnly"),
        payment_filters={
            "contributo_unificato": request.args.get("cu", "") or request.args.get("contributo_unificato", ""),
            "fondo_spese": request.args.get("fondo_spese", "") or request.args.get("fondoSpese", ""),
            "liquidazione_giudice": request.args.get("liquidazione", "") or request.args.get("liquidazione_giudice", ""),
            "parcella": request.args.get("parcella", ""),
        },
        field_filters=_fascicoli_request_field_filters(),
    ))
    if cache_key is not None and response.status_code == 200:
        _FASCICOLI_LIST_PAYLOAD_CACHE.set(cache_key, response.get_data())
    return response


@api_v1_react.post("/fascicoli/presidio-economico/proforme")
@_richiedi_auth
def fascicoli_react_presidio_economico_proforme():
    payload, error = _request_json_object()
    if error:
        return error
    raw_limit = payload.get("limit") if isinstance(payload, dict) else None
    try:
        limit = int(raw_limit or 500)
    except (TypeError, ValueError):
        limit = 500
    current_user = getattr(g, "user", None)
    actor = str(getattr(current_user, "nome", "") or getattr(current_user, "username", "") or "IUSENTRA").strip()
    result = run_react_fascicoli_economic_presidio(
        get_fascicoli=_fascicoli_loader(),
        get_fatturazione=get_fatturazione,
        actor=actor,
        limit=max(1, min(1000, limit)),
    )
    if (
        int(result.get("createdCount") or 0)
        or int(result.get("contributiUpdatedCount") or 0)
        or int(result.get("documentAnalysisUpdatedCount") or 0)
    ):
        clear_dashboard_payload_cache()
        _clear_fascicoli_list_payload_cache()
        _audit_event(
            "fascicoli.presidio_economico.proforme",
            "fascicoli",
            "presidio-economico",
            result.get("message", "Bozze proforma generate automaticamente."),
        )
    return jsonify(result)


@api_v1_react.get("/fascicoli/archivio")
@_richiedi_auth
def fascicoli_react_archivio():
    return jsonify(build_react_archivio_payload(
        get_fascicoli=_fascicoli_loader(),
        get_scadenziario=get_scadenziario,
        query=request.args.get("q", ""),
    ))


@api_v1_react.get("/fascicoli/export")
@_richiedi_auth
def fascicoli_react_export():
    return jsonify(build_react_fascicoli_export_payload(
        get_fascicoli=_fascicoli_loader(),
        get_scadenziario=get_scadenziario,
    ))


@api_v1_react.post("/fascicoli/<id_fasc>/stato")
@_richiedi_auth
def fascicolo_react_stato(id_fasc: str):
    if not (_api_key_valida() or _session_user_can("fascicoli.scrivi")):
        return jsonify({"ok": False, "message": "Operazione non autorizzata.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    result, status = update_react_fascicolo_status(
        get_fascicoli=_fascicoli_loader(),
        id_fasc=id_fasc,
        payload=_request_payload(),
        actor=_actor_label(),
    )
    if result.get("ok"):
        _clear_fascicoli_list_payload_cache()
        _audit_event(
            "fascicoli.stato_aggiornato",
            "fascicolo",
            id_fasc,
            str(result.get("message") or "Stato fascicolo aggiornato."),
        )
    return jsonify(result), status


@api_v1_react.post("/fascicoli/<id_fasc>/pagamenti/<kind>")
@_richiedi_auth
def fascicolo_react_pagamento(id_fasc: str, kind: str):
    if not (_api_key_valida() or _session_user_can("fascicoli.scrivi") or _session_user_can("fatturazione.scrivi")):
        return jsonify({"ok": False, "message": "Operazione non autorizzata.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    result, status = update_react_fascicolo_payment(
        get_fascicoli=_fascicoli_loader(),
        get_fatturazione=get_fatturazione,
        id_fasc=id_fasc,
        kind=kind,
        payload=_request_payload(),
        actor=_actor_label(),
    )
    if result.get("ok"):
        _clear_fascicoli_list_payload_cache()
        _audit_event(
            "fascicoli.pagamento_aggiornato",
            "fascicolo",
            id_fasc,
            str(result.get("message") or "Controllo economico aggiornato."),
        )
    return redacted_json_response(result, status)


@api_v1_react.post("/fascicoli/<id_fasc>/proforma/genera")
@_richiedi_auth
def fascicolo_react_genera_proforma(id_fasc: str):
    utente = g.get("utente_corrente")
    if not utente or not (_api_key_valida() or _session_user_can("fatturazione.scrivi")):
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
        }), 403
    result, status = generate_react_fascicolo_proforma(
        get_fascicoli=_fascicoli_loader(),
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        get_utenti=get_utenti,
        get_preventivi=get_preventivi,
        current_user=utente,
        id_fasc=id_fasc,
        payload=_request_payload(),
        config=_fatturazione_runtime_config(),
        actor=_actor_label(),
        ip_address=request.remote_addr or "",
    )
    if result.get("ok"):
        clear_dashboard_payload_cache()
        _clear_fascicoli_list_payload_cache()
        _audit_event(
            "fascicoli.proforma_generata",
            "fascicolo",
            id_fasc,
            str(result.get("message") or "Proforma collegata al fascicolo."),
        )
    return redacted_json_response(result, status)


@api_v1_react.post("/fascicoli/<id_fasc>/deposito/valore-causa")
@_richiedi_auth
def fascicolo_react_deposito_valore_causa(id_fasc: str):
    if not (_api_key_valida() or _session_user_can("fascicoli.scrivi")):
        return jsonify({"ok": False, "message": "Operazione non autorizzata.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    result, status = update_react_fascicolo_deposit_value(
        get_fascicoli=_fascicoli_loader(),
        id_fasc=id_fasc,
        payload=_request_payload(),
        actor=_actor_label(),
    )
    if result.get("ok"):
        _clear_fascicoli_list_payload_cache()
        _audit_event(
            "fascicoli.deposito.valore_causa_aggiornato",
            "fascicolo",
            id_fasc,
            str(result.get("message") or "Valore della causa aggiornato."),
        )
    return redacted_json_response(result, status)


@api_v1_react.get("/fascicoli/nuovo")
@_richiedi_auth
def fascicolo_react_nuovo():
    return jsonify(build_react_fascicolo_form_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        id_fasc=None,
        query=dict(request.args),
        correction_context={"active": False, "title": "", "help": "", "highlight": ""},
        studio_avvocato_titolare=_studio_avvocato_titolare(),
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/modifica")
@_richiedi_auth
def fascicolo_react_modifica(id_fasc: str):
    get_fascicoli_loader = _fascicoli_loader()
    fascicoli = get_fascicoli_loader()
    if not fascicoli.get(id_fasc):
        return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
    return jsonify(build_react_fascicolo_form_payload(
        get_fascicoli=get_fascicoli_loader,
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        id_fasc=id_fasc,
        query=dict(request.args),
        correction_context={"active": False, "title": "", "help": "", "highlight": ""},
        studio_avvocato_titolare=_studio_avvocato_titolare(),
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/documenti/<id_doc>/editor")
@_richiedi_auth
def fascicolo_react_documento_editor(id_fasc: str, id_doc: str):
    return jsonify(build_react_document_editor_payload(
        get_fascicoli=_fascicoli_loader(),
        id_fasc=id_fasc,
        id_doc=id_doc,
    ))


@api_v1_react.get("/telematico/depositi/catalogo")
@_richiedi_auth
def telematico_depositi_catalogo():
    try:
        key = str(request.args.get("key") or "").strip()
        if key:
            entry = resolve_deposit_type_payload(key)
            if not entry:
                return jsonify({"ok": False, "mock_fallback": False, "errore": "Tipo deposito non trovato."}), 404
            return jsonify({"ok": True, "mock_fallback": False, "entry": entry})
        return jsonify({"ok": True, "mock_fallback": False, "catalog": build_deposit_catalog_payload(include_entries=True)})
    except Exception as exc:
        current_app.logger.exception("Catalogo depositi telematici non disponibile: %s", exc)
        return jsonify({"ok": False, "mock_fallback": False, "errore": "Catalogo depositi telematici non disponibile."}), 500


@api_v1_react.get("/fascicoli/<id_fasc>")
@_richiedi_auth
def fascicolo_react_dettaglio(id_fasc: str):
    include_sections = _detail_include_sections(default=set())
    missing_status = 200 if "all" in include_sections else 404
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections=include_sections,
    ), missing_status=missing_status)


@api_v1_react.get("/fascicoli/<id_fasc>/documenti")
@_richiedi_auth
def fascicolo_react_documenti(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"documenti"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/attivita")
@_richiedi_auth
def fascicolo_react_attivita(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"attivita"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/scadenze")
@_richiedi_auth
def fascicolo_react_scadenze(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"scadenze"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/depositi")
@_richiedi_auth
def fascicolo_react_depositi(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"depositi"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/relata")
@_richiedi_auth
def fascicolo_react_relata(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"relata"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/audit")
@_richiedi_auth
def fascicolo_react_audit(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"audit"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/lex")
@_richiedi_auth
def fascicolo_react_lex(id_fasc: str):
    return _jsonify_domain_payload(build_react_fascicolo_detail_payload(
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"lex"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/regia")
@_richiedi_auth
def fascicolo_regia_operativa(id_fasc: str):
    return _jsonify_public_payload(build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_practice_engine=get_practice_engine,
        actor=_actor_label(),
    ))


@api_v1_react.post("/fascicoli/<id_fasc>/regia/applica-profilo")
@_richiedi_auth
def fascicolo_regia_applica_profilo(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    payload = _request_payload()
    code = str(payload.get("profile_code") or payload.get("code") or payload.get("procedura_operativa_codice") or "").strip()
    profile = get_profile(code)
    if not profile:
        return jsonify({"errore": "Profilo pratica non trovato.", "codice": 404, "mock_fallback": False}), 404
    reason = str(payload.get("reason") or payload.get("motivo") or "Applicazione manuale profilo Regia Operativa.").strip()
    ctx["repo"].apply_profile(id_fasc, profile, actor=_actor_label(), reason=reason, reset=True)
    result = build_regia_payload(
        ctx["repo"],
        fascicolo=ctx["fascicolo"],
        cliente=ctx["cliente"],
        preventivi=ctx["preventivi"],
        conferimenti=ctx["conferimenti"],
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
        actor=_actor_label(),
    )
    return _jsonify_public_payload({"ok": True, "mock_fallback": False, "message": "Profilo pratica applicato e checklist rigenerata.", "regia": result})


@api_v1_react.post("/fascicoli/<id_fasc>/regia/ricalcola")
@_richiedi_auth
def fascicolo_regia_ricalcola(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    if not ctx["profile"]:
        return jsonify({"errore": "Profilo pratica da confermare prima del ricalcolo.", "mock_fallback": False}), 409
    ctx["repo"].audit(id_fasc, "REGIA_RECALCULATED", actor=_actor_label(), message="Regia Operativa ricalcolata.")
    result = build_regia_payload(
        ctx["repo"],
        fascicolo=ctx["fascicolo"],
        cliente=ctx["cliente"],
        preventivi=ctx["preventivi"],
        conferimenti=ctx["conferimenti"],
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
        actor=_actor_label(),
    )
    return _jsonify_public_payload({"ok": True, "mock_fallback": False, "regia": result})


@api_v1_react.get("/fascicoli/<id_fasc>/checklist")
@_richiedi_auth
def fascicolo_regia_checklist(id_fasc: str):
    payload = build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_practice_engine=get_practice_engine,
        actor=_actor_label(),
    )
    return _jsonify_public_payload({"source": "repository reale", "mock_fallback": False, "checklist": payload.get("checklist", [])})


_DEPOSIT_DOCUMENT_ROLE_TO_TYPE = {
    "atto_principale": TipoDocumento.ATTO_GIUDIZIARIO,
    "procura": TipoDocumento.PROCURA,
    "allegato": TipoDocumento.ALLEGATO,
    "allegato_prova": TipoDocumento.ALLEGATO,
    "prova_notifica": TipoDocumento.NOTIFICA,
}


def _deposit_document_role(value: Any) -> str:
    role = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    aliases = {
        "atto": "atto_principale",
        "atto_principale": "atto_principale",
        "ricorso": "atto_principale",
        "procura": "procura",
        "procura_alle_liti": "procura",
        "prova": "allegato",
        "documento_prova": "allegato",
        "allegato_prova": "allegato",
        "prova_notifica": "prova_notifica",
        "notifica": "prova_notifica",
        "allegato": "allegato",
        "fuori_busta": "fuori_busta",
        "escludi": "fuori_busta",
    }
    return aliases.get(role, "allegato")


def _documento_contenitore_firma(doc: Any) -> bool:
    for attr in ("nome", "nome_originale", "nome_archivio", "percorso"):
        value = str(getattr(doc, attr, "") or "").strip().lower().split("?", 1)[0]
        if value.endswith((".p7m", ".sig", ".pkcs7")):
            return True
    return False


def _deposit_datiatto_extra(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError("I dati specifici del deposito non sono validi.")
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("I dati specifici del deposito non sono leggibili.") from exc
    if len(encoded.encode("utf-8")) > 64 * 1024:
        raise ValueError("I dati specifici del deposito superano la dimensione consentita.")
    return json.loads(encoded)


def _deposit_slot_key_for_role(role: str, slots: Iterable[Any], used: set[str]) -> str:
    role = _deposit_document_role(role)
    if role == "atto_principale":
        return "ATTO_PRINCIPALE"
    if role == "procura":
        return "PROCURA"
    if role in {"allegato", "prova_notifica"}:
        candidates = [
            slot
            for slot in slots
            if str(getattr(slot, "slot_key", "") or "").strip().upper() not in used
            and (
                str(getattr(slot, "type", "") or "").strip().upper() == "DOCUMENTO_PROVA"
                or str(getattr(slot, "type", "") or "").strip().upper() == "DOCUMENTO"
                or "PROVA" in str(getattr(slot, "slot_key", "") or "").upper()
                or "DOCUMENT" in str(getattr(slot, "slot_key", "") or "").upper()
            )
        ]
        if candidates:
            return str(getattr(candidates[0], "slot_key", "") or "").strip().upper()
    return ""


@api_v1_react.get("/fascicoli/<id_fasc>/document-slots")
@_richiedi_auth
def fascicolo_regia_document_slots(id_fasc: str):
    payload = build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=_fascicoli_loader(),
        get_clienti=get_clienti,
        get_preventivi=get_preventivi_readonly,
        get_fatturazione=get_fatturazione,
        get_practice_engine=get_practice_engine,
        actor=_actor_label(),
    )
    return _jsonify_public_payload({"source": "repository reale", "mock_fallback": False, "documentSlots": payload.get("documentSlots", [])})


@api_v1_react.post("/fascicoli/<id_fasc>/document-slots/<slot_key>/link")
@_richiedi_auth
def fascicolo_regia_link_slot(id_fasc: str, slot_key: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    payload = _request_payload()
    document_id = str(payload.get("document_id") or payload.get("documentId") or "").strip()
    if not document_id:
        return jsonify({"errore": "Documento non indicato.", "mock_fallback": False}), 400
    if not any(getattr(doc, "id", "") == document_id for doc in getattr(ctx["fascicolo"], "documenti", []) or []):
        return jsonify({"errore": "Documento reale non trovato nel fascicolo.", "mock_fallback": False}), 404
    slot = ctx["repo"].link_slot(id_fasc, slot_key, document_id, actor=_actor_label())
    return _jsonify_public_payload({"ok": True, "mock_fallback": False, "slot": slot.__dict__, "message": "Documento collegato allo slot."})


@api_v1_react.post("/fascicoli/<id_fasc>/deposito/classifica-documenti")
@_richiedi_auth
def fascicolo_deposito_classifica_documenti(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    payload = _request_payload()
    rows = payload.get("documents") if isinstance(payload.get("documents"), list) else []
    if not rows:
        return jsonify({"errore": "Nessun documento indicato.", "mock_fallback": False}), 400
    try:
        datiatto_extra = _deposit_datiatto_extra(payload.get("datiatto_extra"))
    except ValueError as exc:
        return jsonify({"errore": str(exc), "mock_fallback": False}), 400
    tipo_deposito_key = str(payload.get("tipo_deposito_telematico_key") or "").strip()
    raw_professionista_ruolo = str(datiatto_extra.get("professionista_ruolo") or "").strip()
    if raw_professionista_ruolo:
        professionista_ruolo = normalize_deposito_professionista_role(
            raw_professionista_ruolo,
            tipo_deposito_key,
        )
        if not professionista_ruolo:
            return jsonify(
                {
                    "errore": "La qualifica del professionista non è valida per il tipo di deposito selezionato.",
                    "mock_fallback": False,
                }
            ), 400
        datiatto_extra["professionista_ruolo"] = professionista_ruolo

    documents_by_id = {str(getattr(doc, "id", "") or ""): doc for doc in getattr(ctx["fascicolo"], "documenti", []) or []}
    slots = ctx["repo"].ensure_slots(id_fasc, ctx["profile"]) if ctx["profile"] is not None else []
    linked_slots: list[str] = []
    updated_documents: list[dict[str, Any]] = []
    document_deposit_updates: list[dict[str, Any]] = []
    selected_count = 0
    used_slots: set[str] = set()

    for raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        document_id = str(raw_row.get("document_id") or raw_row.get("documentId") or "").strip()
        if not document_id:
            continue
        doc = documents_by_id.get(document_id)
        if not doc:
            return jsonify({"errore": "Documento reale non trovato nel fascicolo.", "mock_fallback": False}), 404
        selected = bool(raw_row.get("selected"))
        role = _deposit_document_role(raw_row.get("role"))
        catalog = classify_fascicolo_document(doc)
        if catalog.role == "atto_principale":
            role = "atto_principale"
        elif role == "atto_principale" and catalog.confidence >= 70 and catalog.role not in {"atto_principale", "atto_difensivo"}:
            if catalog.deposit_role in {"procura", "prova_notifica", "fuori_busta"}:
                role = catalog.deposit_role
            else:
                role = "allegato"
        signed_container = _documento_contenitore_firma(doc)
        already_signed = bool(raw_row.get("already_signed") or raw_row.get("alreadySigned") or signed_container)
        requires_signature = bool(
            raw_row.get("requires_signature")
            if "requires_signature" in raw_row
            else raw_row.get("requiresSignature")
        ) and not signed_container
        studio_document_type = re.sub(
            r"[^A-Za-z0-9_]+",
            "",
            str(raw_row.get("studio_document_type") or raw_row.get("studioDocumentType") or "").strip(),
        )
        if selected and role != "fuori_busta":
            selected_count += 1
            doc_type = _DEPOSIT_DOCUMENT_ROLE_TO_TYPE.get(role)
            current_doc_type = str(getattr(getattr(doc, "tipo", ""), "value", getattr(doc, "tipo", "")) or "").upper()
            if doc_type and (role in {"atto_principale", "procura", "prova_notifica"} or current_doc_type == TipoDocumento.ALTRO.value):
                document_deposit_updates.append({"id_doc": document_id, "tipo": doc_type})
            slot_key = _deposit_slot_key_for_role(role, slots, used_slots)
            if slot_key and ctx["repo"].get_slot(id_fasc, slot_key):
                ctx["repo"].link_slot(id_fasc, slot_key, document_id, actor=_actor_label())
                linked_slots.append(slot_key)
                used_slots.add(slot_key)
        updated_documents.append({
            "documentId": document_id,
            "selected": selected,
            "role": role,
            "studioDocumentType": studio_document_type,
            "alreadySigned": already_signed,
            "requiresSignature": requires_signature,
        })

    deposit_profile = dict(getattr(ctx["fascicolo"], "profilo_deposito", {}) or {})
    deposit_profile["preparazione_busta"] = {
        "tipo_deposito_telematico_key": str(payload.get("tipo_deposito_telematico_key") or "").strip(),
        "tipo_deposito_telematico_label": str(payload.get("tipo_deposito_telematico_label") or "").strip(),
        "tipo_deposito_telematico_policy": str(payload.get("tipo_deposito_telematico_policy") or "").strip(),
        "datiatto_extra": datiatto_extra,
        "documents": updated_documents,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "updated_by": _actor_label(),
    }
    ctx["fascicolo"] = ctx["gf"].aggiorna_preparazione_deposito(
        id_fasc,
        document_updates=document_deposit_updates,
        profilo_deposito=deposit_profile,
    )
    if raw_professionista_ruolo:
        persist_react_deposito_telematico_role(datiatto_extra["professionista_ruolo"])

    if ctx["profile"] is not None:
        run_predeposit_check(
            ctx["repo"],
            fascicolo=ctx["fascicolo"],
            cliente=ctx["cliente"],
            preventivo=ctx["preventivi"][0] if ctx["preventivi"] else None,
            conferimento=ctx["conferimenti"][0] if ctx["conferimenti"] else None,
            parcelle=ctx["parcelle"],
            fascicoli_manager=ctx["gf"],
            profile=ctx["profile"],
        )
    regia = build_regia_payload(
        ctx["repo"],
        fascicolo=ctx["fascicolo"],
        cliente=ctx["cliente"],
        preventivi=ctx["preventivi"],
        conferimenti=ctx["conferimenti"],
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
        actor=_actor_label(),
    )
    return _jsonify_public_payload({
        "ok": True,
        "mock_fallback": False,
        "message": f"Classificazione deposito salvata: {selected_count} documenti pronti per la busta.",
        "selectedCount": selected_count,
        "linkedSlots": linked_slots,
        "documents": updated_documents,
        "updatedDocuments": updated_documents,
        "regia": regia,
    })


@api_v1_react.post("/fascicoli/<id_fasc>/document-slots/<slot_key>/validate")
@_richiedi_auth
def fascicolo_regia_validate_slot(id_fasc: str, slot_key: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    slot = ctx["repo"].get_slot(id_fasc, slot_key)
    if not slot:
        return jsonify({"errore": "Slot documentale non trovato.", "mock_fallback": False}), 404
    validation_ctx = ValidationContext(
        fascicolo=ctx["fascicolo"],
        cliente=ctx["cliente"],
        preventivo=ctx["preventivi"][0] if ctx["preventivi"] else None,
        conferimento=ctx["conferimenti"][0] if ctx["conferimenti"] else None,
        parcelle=ctx["parcelle"],
        slots=ctx["repo"].list_slots(id_fasc),
        fascicoli_manager=ctx["gf"],
        profile=ctx["profile"],
        audit_events=ctx["repo"].list_audit(id_fasc),
    )
    updated, results = validate_slot(slot, validation_ctx)
    ctx["repo"].upsert_slot(updated)
    ctx["repo"].save_validation_results(id_fasc, results, scope="slot", slot_key=slot_key)
    return _jsonify_public_payload({"ok": True, "mock_fallback": False, "slot": updated.__dict__, "results": [item.__dict__ for item in results]})


@api_v1_react.post("/fascicoli/<id_fasc>/predeposito/check")
@_richiedi_auth
def fascicolo_regia_predeposito(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    if not ctx["profile"]:
        return jsonify({"errore": "Profilo pratica da confermare prima del predeposito.", "mock_fallback": False}), 409
    readiness = run_predeposit_check(
        ctx["repo"],
        fascicolo=ctx["fascicolo"],
        profile=ctx["profile"],
        cliente=ctx["cliente"],
        preventivo=ctx["preventivi"][0] if ctx["preventivi"] else None,
        conferimento=ctx["conferimenti"][0] if ctx["conferimenti"] else None,
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
    )
    ctx["repo"].audit(id_fasc, "PREDEPOSIT_CHECK", actor=_actor_label(), message="Check predeposito eseguito.", payload={"status": readiness["status"]})
    return _jsonify_public_payload({
        "ok": True,
        "mock_fallback": False,
        "status": readiness["status"],
        "ready": readiness["ready"],
        "blockers": [item.__dict__ for item in readiness["blockers"]],
        "warnings": [item.__dict__ for item in readiness["warnings"]],
        "results": [item.__dict__ for item in readiness["results"]],
    })


@api_v1_react.post("/fascicoli/<id_fasc>/depositi/prepara")
@_richiedi_auth
def fascicolo_regia_deposito_prepara(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    if not ctx["profile"]:
        return jsonify({"errore": "Profilo pratica da confermare prima del deposito.", "mock_fallback": False}), 409
    result = prepare_deposit(
        ctx["repo"],
        fascicolo=ctx["fascicolo"],
        profile=ctx["profile"],
        cliente=ctx["cliente"],
        preventivo=ctx["preventivi"][0] if ctx["preventivi"] else None,
        conferimento=ctx["conferimenti"][0] if ctx["conferimenti"] else None,
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
    )
    return jsonify({"ok": True, "mock_fallback": False, "session": result["session"].__dict__, "ready": result["readiness"]["ready"]})


@api_v1_react.post("/fascicoli/<id_fasc>/depositi/invia")
@_richiedi_auth
def fascicolo_regia_deposito_invia(id_fasc: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    payload = _request_payload()
    session_id = str(payload.get("deposito_id") or payload.get("depositoId") or payload.get("session_id") or "").strip()
    if not session_id:
        sessions = ctx["repo"].list_deposit_sessions(id_fasc)
        session_id = sessions[0].id if sessions else ""
    if not session_id:
        return jsonify({"errore": "Sessione deposito non preparata.", "mock_fallback": False}), 409
    result = send_deposit(
        ctx["repo"],
        session_id=session_id,
        fascicolo=ctx["fascicolo"],
        profile=ctx["profile"],
        cliente=ctx["cliente"],
        preventivo=ctx["preventivi"][0] if ctx["preventivi"] else None,
        conferimento=ctx["conferimenti"][0] if ctx["conferimenti"] else None,
        parcelle=ctx["parcelle"],
        fascicoli_manager=ctx["gf"],
        adapter=None,
        accept_warnings=bool(payload.get("accept_warnings") or payload.get("accetta_warning")),
    )
    status = 200 if result["sent"] else 409
    return jsonify({"ok": result["sent"], "mock_fallback": False, "session": result["session"].__dict__, "message": result["message"]}), status


@api_v1_react.get("/fascicoli/<id_fasc>/depositi/<deposito_id>/timeline")
@_richiedi_auth
def fascicolo_regia_deposito_timeline(id_fasc: str, deposito_id: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    events = ctx["repo"].list_timeline(deposito_id)
    return jsonify({"source": "repository reale", "mock_fallback": False, "timeline": [event.__dict__ for event in events]})


@api_v1_react.post("/fascicoli/<id_fasc>/depositi/<deposito_id>/importa-ricevuta")
@_richiedi_auth
def fascicolo_regia_importa_ricevuta(id_fasc: str, deposito_id: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    payload = _request_payload()
    original_bytes = None
    original_name = "ricevuta.json"
    if request.files:
        uploaded = next(iter(request.files.values()))
        original_name = uploaded.filename or "ricevuta.bin"
        original_bytes = uploaded.read()
    result = import_receipt(
        ctx["repo"],
        deposito_id=deposito_id,
        fascicolo_id=id_fasc,
        channel=getattr(ctx["profile"], "channel", ""),
        payload=payload,
        original_bytes=original_bytes,
        original_name=original_name,
        source="import_guidato_api",
    )
    return jsonify({"ok": True, "mock_fallback": False, "receipt": result["receipt"].__dict__, "session": result["session"].__dict__ if result["session"] else None})


@api_v1_react.get("/fascicoli/<id_fasc>/depositi/<deposito_id>/evidence-pack")
@_richiedi_auth
def fascicolo_regia_evidence_pack(id_fasc: str, deposito_id: str):
    ctx = _regia_context(id_fasc)
    if "error" in ctx:
        return ctx["error"], ctx["status"]
    existing = ctx["repo"].get_evidence_pack(deposito_id)
    if not existing:
        existing = ensure_evidence_pack(ctx["repo"], fascicolo=ctx["fascicolo"], profile=ctx["profile"], deposito_id=deposito_id)
    path = Path(existing.path)
    if not path.exists():
        return jsonify({"errore": "Evidence pack non disponibile.", "mock_fallback": False}), 404
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="application/zip")


@api_v1_react.post("/preventivi/<preventivo_id>/apri-fascicolo")
@_richiedi_auth
def regia_apri_fascicolo_da_preventivo(preventivo_id: str):
    gp = get_preventivi()
    preventivo = gp.get_preventivo(preventivo_id)
    if not preventivo:
        return jsonify({"errore": "Preventivo non trovato.", "mock_fallback": False}), 404
    cliente = get_clienti().get(getattr(preventivo, "id_cliente", ""))
    conferimento = gp.get_conferimento_principale_preventivo(preventivo_id)
    payload = _request_payload()
    parcelle = [item for item in get_fatturazione().tutte() if getattr(item, "id_preventivo", "") == preventivo_id]
    has_payment = any(_enum_value(getattr(item, "stato", "")).upper() in {"PAGATA", "SALDATA"} or getattr(item, "data_pagamento", "") for item in parcelle)
    if not has_payment and not str(payload.get("override_reason") or payload.get("motivo_override") or "").strip():
        return jsonify({"errore": "Impossibile aprire il fascicolo: manca pagamento o acconto. Registra l'incasso oppure inserisci un override motivato.", "mock_fallback": False}), 409
    result = apri_fascicolo_automatico(
        gp=gp,
        gf=_fascicoli_loader()(),
        gs=get_scadenziario(),
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        avvocato=_actor_label(),
    )
    fascicolo = result["fascicolo"]
    if not has_payment:
        get_practice_engine().audit(
            getattr(fascicolo, "id", ""),
            "ECONOMIC_OVERRIDE",
            actor=_actor_label(),
            message="Apertura fascicolo autorizzata con override economico.",
            reason=str(payload.get("override_reason") or payload.get("motivo_override") or ""),
        )
    return _jsonify_redacted(
        {
            "ok": True,
            "mock_fallback": False,
            "created": result["created"],
            "fascicolo_id": getattr(fascicolo, "id", ""),
            "practice_engine_profile": result.get("practice_engine_profile", ""),
        }
    )


@api_v1_react.post("/conferimenti/<conferimento_id>/apri-fascicolo")
@_richiedi_auth
def regia_apri_fascicolo_da_conferimento(conferimento_id: str):
    gp = get_preventivi()
    conferimento = gp.get_conferimento(conferimento_id)
    if not conferimento:
        return jsonify({"errore": "Conferimento non trovato.", "mock_fallback": False}), 404
    preventivo = gp.get_preventivo(getattr(conferimento, "id_preventivo", ""))
    cliente = get_clienti().get(getattr(conferimento, "id_cliente", "") or getattr(preventivo, "id_cliente", ""))
    payload = _request_payload()
    parcelle = [item for item in get_fatturazione().tutte() if getattr(item, "id_preventivo", "") == getattr(conferimento, "id_preventivo", "")]
    has_payment = any(_enum_value(getattr(item, "stato", "")).upper() in {"PAGATA", "SALDATA"} or getattr(item, "data_pagamento", "") for item in parcelle)
    if not has_payment and not str(payload.get("override_reason") or payload.get("motivo_override") or "").strip():
        return jsonify({"errore": "Impossibile aprire il fascicolo: manca pagamento o acconto. Registra l'incasso oppure inserisci un override motivato.", "mock_fallback": False}), 409
    result = apri_fascicolo_automatico(
        gp=gp,
        gf=_fascicoli_loader()(),
        gs=get_scadenziario(),
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        avvocato=_actor_label(),
    )
    fascicolo = result["fascicolo"]
    if not has_payment:
        get_practice_engine().audit(
            getattr(fascicolo, "id", ""),
            "ECONOMIC_OVERRIDE",
            actor=_actor_label(),
            message="Apertura fascicolo autorizzata con override economico.",
            reason=str(payload.get("override_reason") or payload.get("motivo_override") or ""),
        )
    return _jsonify_redacted(
        {
            "ok": True,
            "mock_fallback": False,
            "created": result["created"],
            "fascicolo_id": getattr(fascicolo, "id", ""),
            "practice_engine_profile": result.get("practice_engine_profile", ""),
        }
    )
# IUSENTRA_REACT_FASCICOLI_ROUTES_END


def _dashboard_cache_key() -> str:
    utente = g.get("utente_corrente")
    user_id = str(getattr(utente, "id", "") or getattr(utente, "username", "") or "api-key")
    tenant = str(g.get("tenant_slug", "") or g.get("auth_tenant_slug", "") or "studio")
    data_paths = getattr(g, "data_paths", {}) or {}
    email_db = str(data_paths.get("EMAIL_CASELLA_DB") or current_app.config.get("EMAIL_CASELLA_DB", ""))
    ordinary_email_db = str(data_paths.get("EMAIL_ORDINARIA_DB") or current_app.config.get("EMAIL_ORDINARIA_DB", ""))
    email_stamp = ""
    if email_db:
        try:
            stat = Path(email_db).stat()
            email_stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            email_stamp = "missing"
    ordinary_email_stamp = ""
    if ordinary_email_db:
        try:
            stat = Path(ordinary_email_db).stat()
            ordinary_email_stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            ordinary_email_stamp = "missing"
    return "|".join([APP_VERSION, tenant, user_id, email_db, email_stamp, ordinary_email_db, ordinary_email_stamp])


def _build_dashboard_payload() -> dict[str, Any]:
    """Payload della Panoramica con dichiarazione esplicita delle sorgenti cadute."""

    with traccia_sorgenti_panoramica() as sorgenti_degradate:
        payload = _collect_dashboard_payload()
    if sorgenti_degradate:
        payload["status"] = "parziale"
        payload["degraded_sources"] = etichette_sorgenti(sorgenti_degradate)
        payload["warning"] = messaggio_sorgenti_degradate(sorgenti_degradate)
    return payload


def _collect_dashboard_payload() -> dict[str, Any]:
    overview = _safe("workspace_intelligente", _workspace_overview, {})
    summary = dict(overview.get("summary") or {})

    pec_rows, email_rows, pec_unread = _email_rows()
    message_rows, client_messages_count = _client_message_rows()
    agenda_rows = _agenda_rows()
    operations = _today_operations(overview)
    completion = _incomplete_registry()
    engagement_rows, missing_engagements_count = _missing_engagements()
    matter_rows = _high_priority_matters()

    urgent_actions = len(operations)
    expiring_quotes = _expiring_quotes_count()
    deadline_distribution = _deadline_distribution()
    worklist = _safe(
        "scadenziario",
        lambda: build_regia_worklist(
            oggi=oggi_rome(),
            scadenze=get_scadenziario().tutte(solo_aperte=True),
            parse_date=_parse_date,
            enum_value=_enum_value,
            short_text=_short_text,
            priorita_urgenti={PrioritaTermine.CRITICA.value, PrioritaTermine.ALTA.value},
            agenda_rows=agenda_rows,
            pec_rows=pec_rows,
            engagement_rows=engagement_rows,
            operations=operations,
        ),
        [],
    )
    economic = _economic_rows()
    lex = _lex_suggestions(
        urgent_actions=urgent_actions,
        incomplete_registry=completion,
        missing_engagements_count=missing_engagements_count,
        high_priority_matters=matter_rows,
    )

    stats = {
        "todayAppointments": _count_agenda_oggi(),
        "urgentDeadlines": int(summary.get("scadenze_urgenti") or 0),
        "openMatters": _count_fascicoli_attivi(),
        "unpaidAmount": _euro(_parcelle_da_incassare()),
        "documentsToReview": int(summary.get("notifiche_scadenze") or 0),
        "urgentActions": urgent_actions,
        "pecUnread": pec_unread,
        "clientMessages": client_messages_count,
        "expiringQuotes": expiring_quotes,
        "missingAssignments": missing_engagements_count,
    }
    return {
        "source": "repository_reali",
        "status": "ok",
        "degraded_sources": [],
        "generated_at": overview.get("generated_at") or _iso_now(),
        # Timestamp gia' nel fuso dell'utente: la Panoramica mostra l'ora di
        # aggiornamento senza dover indovinare il fuso di un dato persistito.
        "generated_at_rome": adesso_rome().replace(microsecond=0).isoformat(),
        "stats": stats,
        "metrics": _metrics(
            urgent_actions=urgent_actions,
            pec_unread=pec_unread,
            client_messages=client_messages_count,
            expiring_quotes=expiring_quotes,
            missing_engagements_count=missing_engagements_count,
        ),
        "actions": list(overview.get("actions") or []),
        "fascicoli": _fascicoli_preview(),
        "pec": pec_rows,
        "emails": email_rows,
        "client_messages": message_rows,
        "agenda": agenda_rows,
        "today_operations": operations,
        "worklist": worklist,
        "incomplete_registry": completion,
        "missing_engagements": engagement_rows,
        "high_priority_matters": matter_rows,
        "deadline_distribution": deadline_distribution,
        "economic": economic,
        "lex_suggestions": lex,
        "contracts": {
            "empty_sections_are_real_empty_state": True,
            "mock_fallback": False,
            "ordinary_email_recent_enabled": True,
            "pec_and_ordinary_email_separated": True,
        },
    }


def _dashboard_error_payload() -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "status": "errore",
        "degraded_sources": [],
        "generated_at": _iso_now(),
        "generated_at_rome": adesso_rome().replace(microsecond=0).isoformat(),
        "stats": {
            "todayAppointments": 0,
            "urgentDeadlines": 0,
            "openMatters": 0,
            "unpaidAmount": _euro(0),
            "documentsToReview": 0,
            "urgentActions": 0,
            "pecUnread": 0,
            "clientMessages": 0,
            "expiringQuotes": 0,
            "missingAssignments": 0,
        },
        "metrics": _metrics(
            urgent_actions=0,
            pec_unread=0,
            client_messages=0,
            expiring_quotes=0,
            missing_engagements_count=0,
        ),
        "actions": [],
        "fascicoli": [],
        "pec": [],
        "emails": [],
        "client_messages": [],
        "agenda": [],
        "today_operations": [],
        "worklist": [],
        "incomplete_registry": {"percent": 100, "totalMissing": 0, "items": []},
        "missing_engagements": [],
        "high_priority_matters": [],
        "deadline_distribution": [],
        "economic": [],
        "lex_suggestions": [],
        "contracts": {
            "empty_sections_are_real_empty_state": True,
            "mock_fallback": False,
            "ordinary_email_recent_enabled": True,
            "pec_and_ordinary_email_separated": True,
        },
        "warning": "Dati non disponibili. Resta disponibile il modulo operativo originale.",
    }


@api_v1_react.get("/strumenti-legali")
@_richiedi_auth
def strumenti_legali_react():
    """Catalogo e schema dei moduli della suite Strumenti Forensi."""

    from pct.strumenti_legali import GestioneStrumentiLegali
    from web.services.react_strumenti_legali_bridge import (
        build_react_strumenti_legali_payload,
        sorgenti_opzioni,
    )

    try:
        gestore = GestioneStrumentiLegali(
            normative_db_path=current_app.config.get(
                "NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json"
            )
        )
        payload = build_react_strumenti_legali_payload(
            catalogo=gestore.catalogo_moduli(),
            form_state=gestore.build_form_state({}),
            tool_richiesto=request.args.get("tool", ""),
            opzioni=sorgenti_opzioni(gestore),
        )
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception as exc:
        current_app.logger.exception("Errore strumenti legali React bridge: %s", exc)
        return jsonify(
            {
                "strumenti": [],
                "categorie": [],
                "tool_attivo": "",
                "totale": 0,
                "totale_in_react": 0,
                "endpoint_calcolo": "/api/v1/ui/strumenti-legali/calcola",
                "warning": "Catalogo strumenti momentaneamente non disponibile. Riprova.",
            }
        ), 200


@api_v1_react.post("/strumenti-legali/calcola")
@_richiedi_auth
def strumenti_legali_calcola_react():
    """Esegue un calcolo della suite riusando i metodi già in produzione."""

    from pct.calcolatori.schema import schema_calcolatore
    from pct.strumenti_legali import GestioneStrumentiLegali
    from web.blueprints.strumenti_legali import TOOL_METHODS

    payload = request.get_json(silent=True) or {}
    tool = str(payload.get("tool") or "").strip()
    if not schema_calcolatore(tool) or tool not in TOOL_METHODS:
        return jsonify({"ok": False, "errore": "Strumento non disponibile in questa vista."}), 200

    dati = payload.get("dati") if isinstance(payload.get("dati"), dict) else {}
    try:
        gestore = GestioneStrumentiLegali(
            normative_db_path=current_app.config.get(
                "NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json"
            )
        )
        risultato = getattr(gestore, TOOL_METHODS[tool])(dati)
        return jsonify({"ok": True, "tool": tool, "result": risultato})
    except ValueError as exc:
        return jsonify({"ok": False, "errore": str(exc)}), 200
    except Exception as exc:
        current_app.logger.exception("Errore calcolo strumenti legali %s: %s", tool, exc)
        return jsonify({"ok": False, "errore": "Calcolo non riuscito. Controlla i dati e riprova."}), 200


@api_v1_react.get("/dashboard")
@_richiedi_auth
def dashboard():
    try:
        refresh = str(request.args.get("refresh", "") or "").lower() in {"1", "true", "si", "yes"}
        payload, cache_hit = get_dashboard_payload_cached(
            _dashboard_cache_key(),
            _build_dashboard_payload,
            refresh=refresh,
        )
        payload = dict(payload)
        payload["cache"] = {
            "hit": bool(cache_hit),
            "ttl_seconds": int(DASHBOARD_CACHE_TTL_SECONDS),
        }
        response = jsonify(payload)
        response.headers["X-IUSENTRA-Cache"] = "HIT" if cache_hit else "MISS"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response
    except Exception as exc:
        current_app.logger.exception("Errore dashboard React bridge: %s", exc)
        response = jsonify(_dashboard_error_payload())
        response.headers["X-IUSENTRA-Cache"] = "BYPASS"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response, 200


@api_v1_react.post("/dashboard/sync-mailboxes")
@_richiedi_auth
def dashboard_sync_mailboxes():
    payload = _request_payload()
    force = str(payload.get("force") or request.args.get("force") or "").strip().lower() in {"1", "true", "si", "yes", "on"}
    try:
        result = sync_mailboxes_for_current_context(force=force)
        result["ok"] = bool(result.get("ok", True))
        return _jsonify_redacted(result)
    finally:
        clear_dashboard_payload_cache()


@api_v1_react.get("/statistiche")
@_richiedi_auth
def statistiche_page():
    try:
        return jsonify(
            build_react_statistiche_payload(
                get_agenda=get_agenda,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                get_fatturazione=get_fatturazione,
                get_scadenziario=get_scadenziario,
                get_email=_email_manager,
                get_email_ordinaria=_ordinary_email_manager,
                get_messaggi=_messaggi_manager,
                get_preventivi=get_preventivi_readonly,
                get_timesheet=get_timesheet,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore statistiche React bridge: %s", exc)
        return jsonify(build_react_statistiche_error_payload("Statistiche non disponibili dal runtime corrente.")), 200


@api_v1_react.get("/audit")
@_richiedi_auth
def audit_page():
    if not _puo_leggere_audit():
        return jsonify(build_react_audit_error_payload("Permesso audit.leggi richiesto.", route="/audit")), 403
    try:
        return jsonify(build_react_audit_payload(get_utenti=get_utenti, query=request.args, route="/audit"))
    except Exception as exc:
        current_app.logger.exception("Errore audit React bridge: %s", exc)
        return jsonify(build_react_audit_error_payload("Registro audit non disponibile dal runtime corrente.", route="/audit")), 200


@api_v1_react.get("/registro-attivita")
@_richiedi_auth
def registro_attivita_page():
    if not _puo_leggere_audit():
        return jsonify(
            build_react_audit_error_payload("Permesso audit.leggi richiesto.", route="/registro-attivita")
        ), 403
    try:
        return jsonify(build_react_audit_payload(get_utenti=get_utenti, query=request.args, route="/registro-attivita"))
    except Exception as exc:
        current_app.logger.exception("Errore registro attivita React bridge: %s", exc)
        return jsonify(
            build_react_audit_error_payload(
                "Registro attivita non disponibile dal runtime corrente.",
                route="/registro-attivita",
            )
        ), 200


@api_v1_react.get("/audit/<id_evento>")
@_richiedi_auth
def audit_event_detail_page(id_evento: str):
    if not _puo_leggere_audit():
        return jsonify({"ok": False, "message": "Permesso audit.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    try:
        result, status = build_react_audit_detail_payload(get_utenti=get_utenti, id_evento=id_evento)
        return jsonify(result), status
    except Exception as exc:
        current_app.logger.exception("Errore dettaglio audit React bridge: %s", exc)
        return jsonify({"ok": False, "message": "Dettaglio audit non disponibile.", "errors": {"_form": "Errore server controllato."}, "item": None}), 500


@api_v1_react.get("/utenti")
@_richiedi_auth
def utenti_page():
    if not _puo_leggere_utenti():
        return jsonify(build_react_utenti_error_payload("Permesso utenti.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_utenti_payload(
                get_utenti=get_utenti,
                current_user=g.get("utente_corrente"),
                query=request.args,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore utenti React bridge: %s", exc)
        return jsonify(build_react_utenti_error_payload("Gestione utenti non disponibile dal runtime corrente.")), 200


@api_v1_react.post("/utenti/nuovo")
@_richiedi_auth
def utenti_nuovo_crea():
    utente = g.get("utente_corrente")
    if not _puo_scrivere_utenti():
        return _json_validation_error(
            "Permesso utenti.scrivi richiesto.",
            {"_form": "Non hai i permessi necessari per creare utenti."},
            status=403,
        )
    if current_app.config.get("MULTI_TENANT") and getattr(utente, "is_superadmin", False):
        return _json_validation_error(
            "Il ruolo SUPERADMIN si gestisce solo dal pannello piattaforma dedicato.",
            {"ruolo": "SUPERADMIN non è assegnabile agli utenti di studio."},
            status=403,
        )

    payload = _request_payload()
    errors: dict[str, str] = {}
    username = str(payload.get("username") or "").strip().lower()
    password = str(payload.get("password") or "")
    ruolo_raw = str(payload.get("ruolo") or "").strip()
    nome_completo = str(payload.get("nome_completo") or "").strip()
    email = str(payload.get("email") or "").strip()

    if not username:
        errors["username"] = "Inserisci lo username."
    if len(password) < 8:
        errors["password"] = "La password temporanea deve avere almeno 8 caratteri."
    try:
        ruolo = RuoloUtente(ruolo_raw)
        if ruolo == RuoloUtente.SUPERADMIN:
            errors["ruolo"] = "Il ruolo SUPERADMIN si gestisce solo dal pannello piattaforma."
    except ValueError:
        ruolo = None
        errors["ruolo"] = "Seleziona un ruolo valido."

    if errors:
        return _json_validation_error("Controlla i campi evidenziati.", errors)

    manager = get_utenti()
    try:
        nuovo = manager.crea(
            username=username,
            password=password,
            ruolo=ruolo,
            email=email,
            nome_completo=nome_completo,
        )
    except ValueError:
        message = "Utente non creato. Controlla i dati inseriti."
        field = "username" if "username" in message.lower() else "_form"
        return _json_validation_error(message, {field: message})
    except Exception as exc:
        current_app.logger.exception("Errore creazione utente React JSON: %s", exc)
        return _json_validation_error(
            "Creazione utente non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il fallback tecnico."},
            status=500,
        )

    actor_id = str(getattr(utente, "id", "") or "")
    actor_username = str(getattr(utente, "username", "") or "")
    try:
        manager.registra_evento(
            "utenti.crea",
            id_utente=actor_id,
            username=actor_username,
            risorsa_tipo="utente",
            risorsa_id=nuovo.id,
            dettagli=f"username={nuovo.username}",
            ip=request.remote_addr or "",
        )
    except Exception as exc:
        current_app.logger.warning("Audit creazione utente React non registrato: %s", exc)

    role_value = str(getattr(getattr(nuovo, "ruolo", ""), "value", getattr(nuovo, "ruolo", "")) or "")
    return jsonify(
        {
            "ok": True,
            "message": f"Utente '{nuovo.username}' creato. Al primo accesso dovra' cambiare la credenziale temporanea.",
            "errors": {},
            "item": {
                "id": nuovo.id,
                "username": nuovo.username,
                "name": getattr(nuovo, "nome_completo", ""),
                "email": getattr(nuovo, "email", ""),
                "role": role_value,
                "roleLabel": role_value.replace("_", " ").title(),
                "active": bool(getattr(nuovo, "attivo", False)),
            },
        }
    )


def _utenti_permission_response():
    return jsonify(
        {
            "ok": False,
            "message": "Permesso utenti.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "user": None,
        }
    ), 403


def _utenti_result_status(result: dict[str, Any]) -> int:
    if result.get("ok"):
        return 200
    errors = result.get("errors") if isinstance(result.get("errors"), dict) else {}
    return 403 if "permission" in errors else 400


@api_v1_react.post("/utenti/<id_utente>/stato")
@_richiedi_auth
def utenti_aggiorna_stato(id_utente: str):
    if not _puo_scrivere_utenti():
        return _utenti_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_utente_status(
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            user_id=id_utente,
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _utenti_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore modifica stato utente React JSON: %s", exc)
        return _json_validation_error(
            "Modifica stato utente non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.post("/utenti/<id_utente>/ruolo")
@_richiedi_auth
def utenti_aggiorna_ruolo(id_utente: str):
    if not _puo_scrivere_utenti():
        return _utenti_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_utente_role(
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            user_id=id_utente,
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _utenti_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore modifica ruolo utente React JSON: %s", exc)
        return _json_validation_error(
            "Modifica ruolo utente non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.post("/utenti/<id_utente>/reset-password")
@_richiedi_auth
def utenti_reset_password(id_utente: str):
    if not _puo_scrivere_utenti():
        return _utenti_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = reset_react_utente_password(
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            user_id=id_utente,
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _utenti_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore reset credenziale utente React JSON: %s", exc)
        return _json_validation_error(
            "Reset credenziale utente non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.post("/utenti/<id_utente>/profilo")
@_richiedi_auth
def utenti_aggiorna_profilo(id_utente: str):
    if not _puo_scrivere_utenti():
        return _utenti_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_utente_profile(
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            user_id=id_utente,
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _utenti_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore modifica profilo utente React JSON: %s", exc)
        return _json_validation_error(
            "Modifica profilo utente non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.get("/profili")
@_richiedi_auth
def profili_page():
    if not _puo_leggere_utenti():
        return jsonify(build_react_profili_error_payload("Permesso utenti.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_profili_payload(
                get_utenti=get_utenti,
                current_user=g.get("utente_corrente"),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore profili React bridge: %s", exc)
        return jsonify(build_react_profili_error_payload("Profili non disponibili dal runtime corrente.")), 200


@api_v1_react.post("/profili")
@_richiedi_auth
def profili_page_update():
    if not _puo_scrivere_utenti():
        return jsonify(
            {
                "ok": False,
                "message": "Permesso utenti.scrivi richiesto.",
                "errors": {"permission": "Operazione non autorizzata."},
                "updated": None,
            }
        ), 403
    if not request.is_json:
        return _json_validation_error(
            "Payload JSON richiesto.",
            {"payload": "Invia Content-Type application/json."},
            status=400,
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_validation_error(
            "Payload JSON non valido.",
            {"payload": "Il corpo della richiesta deve essere un oggetto JSON."},
            status=400,
        )
    try:
        result = update_react_profili_payload(
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            payload=payload,
            ip=request.remote_addr or "",
        )
        return jsonify(result), 200 if result.get("ok") else 400
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio profili React JSON: %s", exc)
        return _json_validation_error(
            "Salvataggio profili non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.get("/backup")
@_richiedi_auth
def backup_page():
    if not _puo_leggere_backup():
        return jsonify(build_react_backup_error_payload("Permesso backup.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_backup_payload(
                get_backup=_backup_loader(),
                current_user=g.get("utente_corrente"),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore backup React bridge: %s", exc)
        return jsonify(build_react_backup_error_payload("Backup non disponibile dal runtime corrente.")), 200


def _backup_permission_response():
    return jsonify(
        {
            "ok": False,
            "message": "Permesso backup.esegui richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "backup": None,
            "integrity": None,
        }
    ), 403


def _backup_result_status(result: dict[str, Any]) -> int:
    if result.get("ok"):
        return 200
    errors = result.get("errors") if isinstance(result.get("errors"), dict) else {}
    return 403 if "permission" in errors else 400


@api_v1_react.post("/backup/crea")
@_richiedi_auth
def backup_crea():
    if not _puo_eseguire_backup():
        return _backup_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = create_react_backup(
            get_backup=_backup_loader(),
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _backup_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore creazione backup React JSON: %s", exc)
        return _json_validation_error(
            "Creazione backup non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.post("/backup/verifica")
@_richiedi_auth
def backup_verifica():
    if not _puo_eseguire_backup():
        return _backup_permission_response()
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = verify_react_backup_integrity(
            get_backup=_backup_loader(),
            get_utenti=get_utenti,
            current_user=g.get("utente_corrente"),
            payload=payload or {},
            ip=request.remote_addr or "",
        )
        return _jsonify_redacted(result), _backup_result_status(result)
    except Exception as exc:
        current_app.logger.exception("Errore verifica backup React JSON: %s", exc)
        return _json_validation_error(
            "Verifica backup non disponibile dal runtime corrente.",
            {"_form": "Errore server controllato. Riprova o usa il rollback tecnico."},
            status=500,
        )


@api_v1_react.get("/sito-studio")
@_richiedi_auth
def sito_studio_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(
            build_react_sito_studio_payload(
                current_user=g.get("utente_corrente"),
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_error_payload("Sito Studio non disponibile dal runtime corrente.")), 200


@api_v1_react.get("/sito-studio/builder")
@_richiedi_auth
def sito_studio_builder_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(build_react_sito_studio_builder_payload(page_id=request.args.get("page_id", type=int)))
    except Exception as exc:
        current_app.logger.exception("Errore Builder Sito Studio React bridge: %s", exc)
        return jsonify(builder_error_payload("Builder Sito Studio non disponibile dal runtime corrente.")), 200


@api_v1_react.post("/sito-studio/builder/template")
@_richiedi_auth
def sito_studio_builder_template():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = apply_react_builder_template(payload or {})
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/design")
@_richiedi_auth
def sito_studio_builder_design():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = save_react_builder_design(payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio design Builder React: %s", exc)
        result = {"ok": False, "message": "Salvataggio parametri grafici non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/genera")
@_richiedi_auth
def sito_studio_builder_genera():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = generate_react_builder_site(payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore generazione Builder React: %s", exc)
        result = {"ok": False, "message": "Generazione guidata non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/valida")
@_richiedi_auth
def sito_studio_builder_valida():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = validate_react_builder()
    except Exception as exc:
        current_app.logger.exception("Errore validazione Builder React: %s", exc)
        result = {"ok": False, "message": "Controlli professionali non completati."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/site")
@_richiedi_auth
def sito_studio_builder_site_update():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_builder_site(payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio dati sito Builder React: %s", exc)
        result = {"ok": False, "message": "Salvataggio dati sito non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/pages")
@_richiedi_auth
def sito_studio_builder_create_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = create_react_builder_page(payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore creazione pagina Builder React: %s", exc)
        result = {"ok": False, "message": "Creazione pagina non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/pages/<int:page_id>/settings")
@_richiedi_auth
def sito_studio_builder_page_settings(page_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_builder_page(page_id, payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio pagina Builder React: %s", exc)
        result = {"ok": False, "message": "Salvataggio pagina non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/pages/<int:page_id>/duplicate")
@_richiedi_auth
def sito_studio_builder_page_duplicate(page_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = duplicate_react_builder_page(page_id)
    except Exception as exc:
        current_app.logger.exception("Errore duplicazione pagina Builder React: %s", exc)
        result = {"ok": False, "message": "Duplicazione pagina non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.delete("/sito-studio/builder/pages/<int:page_id>")
@_richiedi_auth
def sito_studio_builder_delete_page(page_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = delete_react_builder_page(page_id)
    except Exception as exc:
        current_app.logger.exception("Errore rimozione pagina Builder React: %s", exc)
        result = {"ok": False, "message": "Rimozione pagina non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/pages/<int:page_id>/blocks")
@_richiedi_auth
def sito_studio_builder_blocks(page_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = save_react_builder_blocks(page_id, payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio blocchi Builder React: %s", exc)
        result = {"ok": False, "message": "Salvataggio bozza non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/pages/<int:page_id>/publish")
@_richiedi_auth
def sito_studio_builder_publish(page_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = publish_react_builder_blocks(page_id, payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore pubblicazione Builder React: %s", exc)
        result = {"ok": False, "message": "Pubblicazione modifiche non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/revisions/<int:revision_id>/restore")
@_richiedi_auth
def sito_studio_builder_restore(revision_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = restore_react_builder_revision(revision_id)
    except Exception as exc:
        current_app.logger.exception("Errore ripristino revisione Builder React: %s", exc)
        result = {"ok": False, "message": "Ripristino revisione non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/builder/assets/upload")
@_richiedi_auth
def sito_studio_builder_asset_upload():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = upload_react_builder_asset(request.files.get("file"), request.form.to_dict())
    except Exception as exc:
        current_app.logger.exception("Errore caricamento immagine Builder React: %s", exc)
        result = {"ok": False, "message": "Caricamento immagine non riuscito."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.delete("/sito-studio/builder/assets/<int:asset_id>")
@_richiedi_auth
def sito_studio_builder_asset_delete(asset_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = delete_react_builder_asset(asset_id)
    except Exception as exc:
        current_app.logger.exception("Errore rimozione immagine Builder React: %s", exc)
        result = {"ok": False, "message": "Rimozione immagine non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/sito-studio/redazione-ai")
@_richiedi_auth
def sito_studio_redazione_ai_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(build_react_sito_studio_ai_payload())
    except Exception as exc:
        current_app.logger.exception("Errore Redazione AI Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_ai_error_payload("Redazione AI non disponibile dal runtime corrente.")), 200


@api_v1_react.post("/sito-studio/redazione-ai/articolo/genera")
@_richiedi_auth
def sito_studio_redazione_ai_genera():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = generate_react_sito_studio_ai_article(payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore generazione articolo Redazione AI React: %s", exc)
        result = {"ok": False, "message": "Generazione bozza non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/redazione-ai/jobs/<int:job_id>/crea-bozza")
@_richiedi_auth
def sito_studio_redazione_ai_crea_bozza(job_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = create_react_sito_studio_ai_draft(job_id)
    except Exception as exc:
        current_app.logger.exception("Errore creazione bozza Redazione AI React: %s", exc)
        result = {"ok": False, "message": "Creazione bozza non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/redazione-ai/articoli/<int:article_id>/genera-immagine")
@_richiedi_auth
def sito_studio_redazione_ai_genera_immagine(article_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = generate_react_sito_studio_ai_image(article_id)
    except Exception as exc:
        current_app.logger.exception("Errore immagine Redazione AI React: %s", exc)
        result = {"ok": False, "message": "Generazione immagine non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/redazione-ai/articoli/<int:article_id>/pubblica")
@_richiedi_auth
def sito_studio_redazione_ai_pubblica(article_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        result = publish_react_sito_studio_ai_article(article_id)
    except Exception as exc:
        current_app.logger.exception("Errore pubblicazione Redazione AI React: %s", exc)
        result = {"ok": False, "message": "Pubblicazione articolo non riuscita."}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/sito-studio/articoli/<int:article_id>/modifica")
@_richiedi_auth
def sito_studio_articolo_modifica_page(article_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        payload = build_react_sito_articolo_modifica_payload(article_id)
    except Exception as exc:
        current_app.logger.exception("Errore modifica articolo Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_error_payload("Articolo Sito Studio non disponibile dal runtime corrente.")), 200
    return _jsonify_domain_payload(payload)


@api_v1_react.post("/sito-studio/articoli/<int:article_id>/modifica")
@_richiedi_auth
def sito_studio_articolo_modifica_salva(article_id: int):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = update_react_sito_articolo(article_id, payload or {})
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio articolo Sito Studio React: %s", exc)
        result = {"ok": False, "message": "Salvataggio articolo non riuscito.", "errors": {"form": "Riprova tra poco."}}
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.get("/sito-studio/contatti")
@_richiedi_auth
def sito_studio_contatti_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(
            build_react_sito_contatti_payload(
                current_user=g.get("utente_corrente"),
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore contatti Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_error_payload("Contatti Sito Studio non disponibili dal runtime corrente.")), 200


@api_v1_react.post("/sito-studio/contatti/<id_contatto>/collega")
@_richiedi_auth
def sito_studio_contatto_collega(id_contatto: str):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = link_react_sito_contatto(id_contatto, payload or {}, get_clienti=get_clienti)
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/sito-studio/prenotazioni/<id_prenotazione>/stato")
@_richiedi_auth
def sito_studio_prenotazione_stato(id_prenotazione: str):
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = update_react_sito_booking_status(id_prenotazione, payload or {})
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.get("/studio")
@_richiedi_auth
def studio_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_studio_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_studio_payload(
                current_user=utente,
                studio_label=studio_nome(),
                get_utenti=get_utenti,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                get_scadenziario=get_scadenziario,
                get_backup=_backup_loader(),
                get_fatturazione=get_fatturazione,
                get_preventivi=get_preventivi_readonly,
                get_pagamenti=get_pagamenti,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Studio React bridge: %s", exc)
        return jsonify(build_react_studio_error_payload("Studio non disponibile dal runtime corrente.")), 200


@api_v1_react.get("/impostazioni")
@api_v1_react.get("/impostazioni-studio")
@_richiedi_auth
def impostazioni_page():
    if not g.get("utente_corrente") and not _api_key_valida():
        return jsonify(build_react_impostazioni_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(build_react_impostazioni_payload())
    except Exception as exc:
        current_app.logger.exception("Errore Impostazioni React bridge: %s", exc)
        return jsonify(build_react_impostazioni_error_payload("Impostazioni non disponibili dal runtime corrente.")), 200


@api_v1_react.post("/impostazioni/<section>")
@_richiedi_auth
def impostazioni_page_update(section: str):
    if request.is_json:
        payload, error_response = _request_json_object()
        if error_response is not None:
            return error_response
        result = update_react_impostazioni_section(section, payload or {})
    else:
        result = update_react_impostazioni_section(section, dict(request.form), files=request.files)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/firma/certificato")
@_richiedi_auth
def impostazioni_firma_certificato_update():
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = update_react_impostazioni_firma_certificato(payload or {})
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/fatturazione/applica-proforme")
@_richiedi_auth
def impostazioni_fatturazione_applica_proforme():
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = apply_react_impostazioni_fatturazione_to_proformas(payload or {})
    return jsonify(result), status


@api_v1_react.post("/impostazioni/test/<test_id>")
@_richiedi_auth
def impostazioni_page_test(test_id: str):
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = run_react_impostazioni_test(test_id, payload or {})
    status_code = 200 if result.get("ok") or result.get("local_signer_required") else 400
    return _jsonify_redacted(result), status_code


@api_v1_react.get("/impostazioni/ai/status")
@_richiedi_auth
def impostazioni_page_ai_status():
    result = build_react_impostazioni_ai_status()
    return jsonify(result), 200 if result.get("ok") else 200


@api_v1_react.get("/impostazioni/ai/lex-dataset")
@_richiedi_auth
def impostazioni_page_ai_lex_dataset():
    result = build_lex_dataset_training_status()
    return jsonify(result), 200 if result.get("ok") else 200


@api_v1_react.get("/impostazioni/ai/lex-dataset/review")
@_richiedi_auth
def impostazioni_page_ai_lex_dataset_review():
    result = load_lex_dataset_review_queue()
    return jsonify(result), 200 if result.get("ok") else 200


@api_v1_react.post("/impostazioni/ai/lex-dataset/review/<qa_id>")
@_richiedi_auth
def impostazioni_page_ai_lex_dataset_review_update(qa_id: str):
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    payload = payload or {}
    result = update_lex_dataset_review_item(
        qa_id,
        action=str(payload.get("action") or ""),
        question=str(payload.get("question") or ""),
        answer=str(payload.get("answer") or ""),
        note=str(payload.get("note") or ""),
        reviewer_id=_current_user_id(),
    )
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/ai/bootstrap")
@_richiedi_auth
def impostazioni_page_ai_bootstrap():
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = bootstrap_react_impostazioni_ai(force=bool((payload or {}).get("force")))
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/notifiche/link")
@_richiedi_auth
def impostazioni_notifiche_link():
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = prepare_notifica_link(payload or {})
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/notifiche/invia")
@_richiedi_auth
def impostazioni_notifiche_invia():
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = send_notifica(payload or {})
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/notifiche/promemoria-domani")
@_richiedi_auth
def impostazioni_notifiche_promemoria_domani():
    result = send_promemoria_domani()
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/calendari/profili")
@_richiedi_auth
def impostazioni_calendari_crea_profilo():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result = create_calendar_profile(payload=payload or {}, get_calendar_sync=get_calendar_sync)
    except Exception as exc:
        current_app.logger.exception("Errore creazione profilo calendario React: %s", exc)
        result = {"ok": False, "message": "Calendario non aggiunto.", "errors": {"_form": "Operazione non completata."}}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/calendari/profili/<profile_id>/sincronizza")
@_richiedi_auth
def impostazioni_calendari_sincronizza(profile_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = sync_calendar_profile(profile_id=profile_id, get_calendar_sync=get_calendar_sync, get_agenda=get_agenda)
    return _jsonify_redacted(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/calendari/profili/<profile_id>/stato")
@_richiedi_auth
def impostazioni_calendari_stato(profile_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = toggle_calendar_profile(profile_id=profile_id, get_calendar_sync=get_calendar_sync)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/calendari/profili/<profile_id>/elimina")
@_richiedi_auth
def impostazioni_calendari_elimina(profile_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    try:
        result = delete_calendar_profile(profile_id=profile_id, get_calendar_sync=get_calendar_sync)
    except Exception:
        result = {"ok": False, "message": "Calendario non eliminato.", "errors": {"profile": "Non trovato."}}
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/impostazioni/calendari/rigenera-link")
@_richiedi_auth
def impostazioni_calendari_rigenera_link():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = regenerate_calendar_token()
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/calendari/accounts")
@_richiedi_auth
def calendari_accounts():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = list_calendar_accounts_payload()
    return jsonify(result), 200


@api_v1_react.post("/calendari/demo/connect")
@_richiedi_auth
def calendari_demo_connect():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = connect_demo_calendar_account(payload or {})
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/google/connect")
@_richiedi_auth
def calendari_google_connect():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = calendar_oauth_connect("google")
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/calendari/google/callback")
@_richiedi_auth
def calendari_google_callback():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = calendar_oauth_callback("google", request.args)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/microsoft/connect")
@_richiedi_auth
def calendari_microsoft_connect():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = calendar_oauth_connect("microsoft")
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/calendari/microsoft/callback")
@_richiedi_auth
def calendari_microsoft_callback():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = calendar_oauth_callback("microsoft", request.args)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/apple/connect")
@_richiedi_auth
def calendari_apple_connect():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = connect_apple_calendar_account(payload or {})
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/webcal/connect")
@_richiedi_auth
def calendari_webcal_connect():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = connect_webcal_calendar_account(payload=payload or {}, get_calendar_sync=get_calendar_sync)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/accounts/<account_id>/sync")
@_richiedi_auth
def calendari_account_sync(account_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = sync_calendar_account(account_id)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/accounts/<account_id>/disconnect")
@_richiedi_auth
def calendari_account_disconnect(account_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = disconnect_calendar_account(account_id)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.post("/calendari/calendars/<calendar_id>/toggle")
@_richiedi_auth
def calendari_calendar_toggle(calendar_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = toggle_linked_calendar(calendar_id)
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/calendari/conflicts")
@_richiedi_auth
def calendari_conflicts():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    result = list_calendar_conflicts_payload()
    return jsonify(result), 200


@api_v1_react.post("/calendari/conflicts/<conflict_id>/resolve")
@_richiedi_auth
def calendari_conflict_resolve(conflict_id: str):
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "message": "Permesso impostazioni richiesto.", "errors": {"permission": "Permesso insufficiente."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result = resolve_calendar_conflict(conflict_id, str((payload or {}).get("strategy") or "ignore"))
    return jsonify(result), 200 if result.get("ok") else 400


@api_v1_react.get("/amministrazione")
@_richiedi_auth
def amministrazione_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_amministrazione_error_payload("Sessione utente richiesta.")), 403
    if not _session_user_can("utenti.leggi"):
        return jsonify(build_react_amministrazione_error_payload("Permesso utenti.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_amministrazione_payload(
                get_utenti=get_utenti,
                current_user=utente,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Amministrazione React bridge: %s", exc)
        return jsonify(
            build_react_amministrazione_error_payload(
                "Amministrazione non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/fatturazione")
@_richiedi_auth
def fatturazione_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_fatturazione_error_payload("Sessione utente richiesta.", route="/fatturazione")), 403
    if not _puo_leggere_fatturazione():
        return jsonify(build_react_fatturazione_error_payload("Permesso fatturazione.leggi richiesto.", route="/fatturazione")), 403
    try:
        return jsonify(
            build_react_fatturazione_payload(
                get_fatturazione=get_fatturazione,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                get_preventivi=get_preventivi_readonly,
                current_user=utente,
                query=dict(request.args),
                route="/fatturazione",
                config=_fatturazione_runtime_config(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Fatturazione React bridge: %s", exc)
        return jsonify(
            build_react_fatturazione_error_payload(
                "Fatturazione non disponibile dal runtime corrente.",
                route="/fatturazione",
            )
        ), 200


@api_v1_react.get("/fatturazione/nuova")
@_richiedi_auth
def fatturazione_nuova_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_fatturazione_error_payload("Sessione utente richiesta.", route="/fatturazione/nuova")), 403
    if not _puo_leggere_fatturazione():
        return jsonify(build_react_fatturazione_error_payload("Permesso fatturazione.leggi richiesto.", route="/fatturazione/nuova")), 403
    try:
        return jsonify(
            build_react_fatturazione_payload(
                get_fatturazione=get_fatturazione,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                get_preventivi=get_preventivi_readonly,
                current_user=utente,
                query=dict(request.args),
                route="/fatturazione/nuova",
                config=_fatturazione_runtime_config(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Nuova Fatturazione React bridge: %s", exc)
        return jsonify(
            build_react_fatturazione_error_payload(
                "Form parcella non disponibile dal runtime corrente.",
                route="/fatturazione/nuova",
            )
        ), 200


@api_v1_react.post("/fatturazione/nuova")
@_richiedi_auth
def fatturazione_nuova_crea():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({
            "ok": False,
            "message": "Sessione utente richiesta.",
            "errors": {"session": "Accedi per creare una parcella."},
            "item": None,
        }), 403
    if not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403

    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response

    try:
        result, status = create_react_fattura(
            get_fatturazione=get_fatturazione,
            get_clienti=get_clienti,
            get_fascicoli=get_fascicoli,
            get_utenti=get_utenti,
            get_preventivi=get_preventivi,
            current_user=utente,
            payload=payload,
            config=_fatturazione_runtime_config(),
            ip_address=request.remote_addr or "",
        )
        return _jsonify_redacted(result), status
    except Exception as exc:
        current_app.logger.exception("Errore creazione parcella React JSON: %s", exc)
        return jsonify({
            "ok": False,
            "message": "Creazione parcella non disponibile dal runtime corrente.",
            "errors": {"server": "Errore applicativo controllato."},
            "item": None,
        }), 500


@api_v1_react.post("/fatturazione/numerazione")
@_richiedi_auth
def fatturazione_configura_numerazione():
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "numbering": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_fatturazione_numbering(
        get_fatturazione=get_fatturazione,
        current_user=utente,
        payload=payload,
    )
    return _jsonify_redacted(result), status


@api_v1_react.get("/fatturazione/<id_documento>")
@_richiedi_auth
def fatturazione_detail_page(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({
            "ok": False,
            "message": "Sessione utente richiesta.",
            "errors": {"session": "Accedi per consultare la fatturazione."},
            "item": None,
        }), 403
    if not _puo_leggere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.leggi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    result, status = build_react_fatturazione_detail_payload(
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        id_documento=id_documento,
        sdi_cfg=getattr(_studio_config_runtime(), "sdi", None),
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/dettaglio")
@_richiedi_auth
def fatturazione_aggiorna_dettaglio(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_fatturazione_detail(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        studio_config=_fatturazione_runtime_config(),
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/xml/prepara-firma")
@_richiedi_auth
def fatturazione_prepara_firma_xml(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    result, status = prepare_react_fatturazione_xml_signature(
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        current_user=utente,
        id_documento=id_documento,
        config=_fatturazione_runtime_config(),
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/xml/firmato")
@_richiedi_auth
def fatturazione_conferma_xml_firmato(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "workflow": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = confirm_react_fatturazione_xml_signed(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        storage_root=_fatturazione_document_storage_root(),
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/sdi/pec/prepara")
@_richiedi_auth
def fatturazione_prepara_pec_sdi(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    cfg = _studio_config_runtime()
    result, status = prepare_react_fatturazione_sdi_pec(
        get_fatturazione=get_fatturazione,
        current_user=utente,
        id_documento=id_documento,
        storage_root=_fatturazione_document_storage_root(),
        pec_cfg=getattr(cfg, "pec", None),
        sdi_cfg=getattr(cfg, "sdi", None),
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/sdi/pec/conferma")
@_richiedi_auth
def fatturazione_conferma_pec_sdi(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = confirm_react_fatturazione_sdi_sent(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/sdi/esito")
@_richiedi_auth
def fatturazione_registra_esito_sdi(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = record_react_fatturazione_sdi_outcome(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/commercialista/prepara")
@_richiedi_auth
def fatturazione_prepara_commercialista(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    cfg = _studio_config_runtime()
    result, status = prepare_react_fatturazione_commercialista(
        get_fatturazione=get_fatturazione,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        storage_root=_fatturazione_document_storage_root(),
        pec_cfg=getattr(cfg, "pec", None),
        sdi_cfg=getattr(cfg, "sdi", None),
        config=_fatturazione_runtime_config(),
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/commercialista/email/invia")
@_richiedi_auth
def fatturazione_invia_email_commercialista(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    cfg = _studio_config_runtime()
    result, status = send_react_fatturazione_commercialista_email(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        attachment_root=_fatturazione_document_storage_root(),
        smtp_cfg=getattr(cfg, "smtp", None),
        studio_name=getattr(getattr(cfg, "studio", None), "nome", "") or "Studio Legale",
        messages_db_path=_messaggi_runtime_path(),
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/commercialista/pec/conferma")
@_richiedi_auth
def fatturazione_conferma_pec_commercialista(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = confirm_react_fatturazione_commercialista_pec(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/stato")
@_richiedi_auth
def fatturazione_aggiorna_stato(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_fatturazione_status(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/annulla")
@_richiedi_auth
def fatturazione_annulla(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = cancel_react_fatturazione_document(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.post("/fatturazione/<id_documento>/segna-pagata")
@_richiedi_auth
def fatturazione_segna_pagata(id_documento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = mark_react_fatturazione_paid(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        id_documento=id_documento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.get("/incassi-pagamenti")
@_richiedi_auth
def incassi_pagamenti_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_incassi_pagamenti_error_payload("Sessione utente richiesta.")), 403
    if not _puo_leggere_fatturazione():
        return jsonify(build_react_incassi_pagamenti_error_payload("Permesso fatturazione.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_incassi_pagamenti_payload(
                get_fatturazione=get_fatturazione,
                get_pagamenti=get_pagamenti,
                get_clienti=get_clienti,
                current_user=utente,
                query=dict(request.args),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Incassi Pagamenti React bridge: %s", exc)
        return jsonify(
            build_react_incassi_pagamenti_error_payload(
                "Incassi e pagamenti non disponibili dal runtime corrente."
            )
        ), 200


@api_v1_react.post("/incassi-pagamenti/incasso")
@_richiedi_auth
def incassi_pagamenti_registra_incasso():
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = register_react_incasso(
        get_fatturazione=get_fatturazione,
        get_pagamenti=get_pagamenti,
        get_utenti=get_utenti,
        current_user=utente,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/stato")
@_richiedi_auth
def incassi_pagamenti_aggiorna_stato(id_pagamento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_pagamento_status(
        get_pagamenti=get_pagamenti,
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        payment_id=id_pagamento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/collega")
@_richiedi_auth
def incassi_pagamenti_collega(id_pagamento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = link_react_pagamento_invoice(payment_id=id_pagamento, payload=payload)
    return jsonify(result), status


@api_v1_react.post("/incassi-pagamenti/<id_pagamento>/link-pagamento")
@_richiedi_auth
def incassi_pagamenti_link_pagamento(id_pagamento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.scrivi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = build_or_get_react_payment_link(
        get_pagamenti=get_pagamenti,
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=utente,
        payment_id=id_pagamento,
        payload=payload,
        host_url=request.host_url,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.get("/compensi-forensi")
@_richiedi_auth
def compensi_forensi_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_compensi_forensi_error_payload("Sessione utente richiesta.")), 403
    if not _puo_leggere_fatturazione():
        return jsonify(build_react_compensi_forensi_error_payload("Permesso fatturazione.leggi richiesto.")), 403
    try:
        return jsonify(
            build_react_compensi_forensi_payload(
                get_normative_tables=get_normative_tables,
                get_preventivi=get_preventivi_readonly,
                current_user=utente,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Compensi Forensi React bridge: %s", exc)
        return jsonify(
            build_react_compensi_forensi_error_payload(
                "Compensi forensi non disponibili dal runtime corrente."
            )
        ), 200


@api_v1_react.post("/compensi-forensi/calcola")
@_richiedi_auth
def compensi_forensi_calcola():
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "result": None, "warnings": []}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = calculate_react_compensi_forensi(
        get_normative_tables=get_normative_tables,
        get_utenti=get_utenti,
        current_user=utente,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.get("/tariffario")
@_richiedi_auth
def tariffario_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_tariffario_error_payload("Sessione utente richiesta.")), 403
    if not _puo_leggere_fatturazione():
        return jsonify(build_react_tariffario_error_payload("Permesso fatturazione.leggi richiesto.")), 403
    try:
        return redacted_json_response(
            build_react_tariffario_payload(
                get_normative_tables=get_normative_tables,
                query=dict(request.args),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Tariffario React bridge: %s", exc)
        return jsonify(
            build_react_tariffario_error_payload(
                "Tariffario non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/tariffario/<id_voce>")
@_richiedi_auth
def tariffario_detail_page(id_voce: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "item": None}), 403
    result, status = build_react_tariffario_detail_payload(get_normative_tables=get_normative_tables, id_voce=id_voce)
    return _jsonify_redacted(result), status


@api_v1_react.post("/tariffario/calcola")
@_richiedi_auth
def tariffario_calcola_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_tariffario_error_payload("Sessione utente richiesta.")), 403
    if not _puo_leggere_fatturazione():
        return jsonify({"ok": False, "message": "Permesso fatturazione.leggi richiesto.", "errors": {"permission": "Operazione non autorizzata."}, "result": None, "warnings": []}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    try:
        result, status = calculate_react_tariffario(get_normative_tables=get_normative_tables, payload=payload)
        return _jsonify_redacted(result), status
    except Exception as exc:
        current_app.logger.exception("Errore calcolo Tariffario React bridge: %s", exc)
        return jsonify(
            {
                "ok": False,
                "warnings": [
                    {
                        "code": "tariffario_calcolo_errore",
                        "message": "Calcolo non disponibile dal runtime corrente.",
                    }
                ],
            }
        ), 200


@api_v1_react.get("/template-atti")
@_richiedi_auth
def template_atti_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_template_atti_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_template_atti_payload(
                get_template_manager=_template_atti_loader,
                page="dashboard",
                studio_timbro=_studio_timbro_payload(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Template Atti React bridge: %s", exc)
        return jsonify(
            build_react_template_atti_error_payload(
                "Template atti non disponibili dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/template-atti/catalogo")
@_richiedi_auth
def template_atti_catalogo_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_template_atti_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_template_atti_payload(
                get_template_manager=_template_atti_loader,
                page="catalogo",
                studio_timbro=_studio_timbro_payload(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Catalogo Template Atti React bridge: %s", exc)
        return jsonify(
            build_react_template_atti_error_payload(
                "Catalogo template atti non disponibile dal runtime corrente."
            )
        ), 200


def _react_template_attr(obj: Any, *names: str) -> str:
    for name in names:
        value = getattr(obj, name, "") if obj is not None else ""
        if callable(value):
            try:
                value = value()
            except Exception:
                value = ""
        value = str(value or "").strip()
        if value:
            return value
    return ""


def _react_template_choice(value: Any, label: Any, **extra: Any) -> dict[str, Any]:
    item = {
        "value": str(value or "").strip(),
        "label": str(label or "").strip(),
    }
    item.update({key: val for key, val in extra.items() if val not in {None, ""}})
    return item


def _react_template_matter_value(value: Any, label: Any = "") -> str:
    visible = str(label or "").strip() or str(value or "").strip()
    known = {
        "STRAGIUDIZIALE": "Stragiudiziale",
        "CIVILE": "Civile",
        "PENALE": "Penale",
        "AMMINISTRATIVO": "Amministrativo",
        "TRIBUTARIO": "Tributario",
        "LAVORO": "Lavoro",
        "PRIVACY": "Privacy",
        "ALTRO": "Altro",
    }
    return known.get(visible.upper(), visible)


def _react_template_field_note(prefill: dict[str, Any]) -> dict[str, str] | None:
    value = prefill.get("value")
    if value not in (None, "", [], {}):
        source = str(prefill.get("source_label") or "dati disponibili").strip()
        return {"tone": "found", "text": f"Precompilato da {source}."}
    missing_reason = str(prefill.get("missing_reason") or "").strip()
    if missing_reason:
        return {"tone": "missing", "text": missing_reason}
    return None


def _react_template_office_options(
    field: dict[str, Any],
    *,
    selected_fascicolo: Any = None,
    current_value: str = "",
) -> list[dict[str, str]]:
    name = str(field.get("name") or "").casefold()
    label = str(field.get("label") or "").casefold()
    text = f"{name} {label}"
    if not any(token in text for token in ("court", "tribunale", "ufficio", "giudice", "autorita", "authority")):
        return []

    fascicolo_office = _react_template_attr(selected_fascicolo, "tribunale", "ufficio_giudiziario")
    context = f"{text} {fascicolo_office}".casefold()
    if "minorenni" in context or "minori" in context or "family" in context:
        allowed_types = {"TM"}
    elif "giudice di pace" in context or "gdp" in context or "sigp" in context:
        allowed_types = {"GP"}
    elif "corte d'appello" in context or "appello" in context:
        allowed_types = {"CA"}
    elif "procura" in context:
        allowed_types = {"PC", "PG"}
    else:
        allowed_types = {"OR", "GP", "TM", "CA"}

    try:
        data_path = Path(__file__).resolve().parents[2] / "pct" / "data" / "uffici_ministero.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    def _office_label(row: dict[str, Any]) -> str:
        return str(row.get("descrizione_ministero") or row.get("nome") or "").strip()

    current = str(current_value or fascicolo_office or "").strip()
    current_key = current.casefold()
    rows: list[tuple[int, str, str]] = []
    for codice, row in (data.get("uffici") or {}).items():
        if not isinstance(row, dict):
            continue
        if str(row.get("tipo_ministero") or "").strip().upper() not in allowed_types:
            continue
        label_value = _office_label(row)
        if not label_value:
            continue
        comune = str(row.get("comune_ministero") or "").strip()
        distretto = str(row.get("distretto_ministero") or row.get("distretto_gl") or "").strip()
        full_label = label_value
        if distretto and distretto.casefold() not in full_label.casefold():
            full_label = f"{full_label} ({distretto})"
        priority = 0
        haystack = f"{label_value} {comune} {distretto}".casefold()
        if current_key and (current_key in haystack or haystack in current_key):
            priority = -100
        rows.append((priority, full_label, str(codice or label_value).strip()))
    rows.sort(key=lambda item: (item[0], item[1].casefold()))

    options: list[dict[str, str]] = []
    seen: set[str] = set()
    if current:
        options.append(_react_template_choice(current, f"{current} - dal fascicolo"))
        seen.add(current.casefold())
    for _, label_value, value in rows:
        key = label_value.casefold()
        if key in seen:
            continue
        seen.add(key)
        options.append(_react_template_choice(label_value, label_value, codiceUfficio=value))
        if len(options) >= 80:
            break
    return options


def _react_template_field_payload(
    field: dict[str, Any],
    *,
    form_values: dict[str, Any],
    field_options: dict[str, list[Any]],
    errors: dict[str, str],
    prefill_fields: dict[str, dict[str, Any]],
    selected_fascicolo: Any = None,
) -> dict[str, Any]:
    name = str(field.get("name") or "").strip()
    options = []
    for option in field_options.get(name, []) or []:
        if isinstance(option, (list, tuple)) and len(option) >= 2:
            option_value = _react_template_matter_value(option[0], option[1]) if name == "matter" else option[0]
            options.append(_react_template_choice(option_value, option[1]))
        elif isinstance(option, dict):
            option_value = (
                _react_template_matter_value(option.get("value"), option.get("label") or option.get("text"))
                if name == "matter"
                else option.get("value")
            )
            options.append(_react_template_choice(option_value, option.get("label") or option.get("text")))
    prefill = prefill_fields.get(name) if isinstance(prefill_fields.get(name), dict) else {}
    raw_value = form_values.get(name, "")
    if not str(raw_value or "").strip() and prefill:
        raw_value = prefill.get("value", "")
    if isinstance(raw_value, (list, tuple, set)):
        value = "\n".join(str(item) for item in raw_value if str(item or "").strip())
    else:
        value = str(raw_value or "")
    if name == "matter":
        value = _react_template_matter_value(value)
    office_options = _react_template_office_options(field, selected_fascicolo=selected_fascicolo, current_value=value)
    if office_options and not options:
        options = office_options
    field_type = str(field.get("type") or "text").strip()
    if office_options:
        field_type = "select"
    return {
        "name": name,
        "label": str(field.get("label") or name.replace("_", " ").title()).strip(),
        "type": field_type,
        "placeholder": str(
            field.get("placeholder")
            or ("Seleziona dal catalogo uffici giudiziari" if office_options else "")
        ).strip(),
        "required": bool(field.get("required")),
        "value": value,
        "options": options,
        "error": str(errors.get(name) or "").strip(),
        "note": _react_template_field_note(prefill),
        "warnings": [str(item) for item in (prefill.get("warnings") or []) if str(item or "").strip()],
        "source": str(prefill.get("source") or "").strip(),
        "sourceLabel": str(prefill.get("source_label") or "").strip(),
        "confidence": str(prefill.get("confidence") or "").strip(),
    }


def _react_template_context_fields_payload(
    *,
    prefill_fields: dict[str, dict[str, Any]],
    existing_names: set[str],
    form_values: dict[str, Any],
) -> list[dict[str, Any]]:
    preferred_order = [
        "recipient_or_court",
        "destinatario_ufficio_giudiziario",
        "client_or_sender",
        "cliente_mittente",
        "counterparty_or_recipient",
        "controparte",
        "case_id",
        "pratica_collegata",
        "practice_reference",
        "practice_number",
        "practice_subject",
        "practice_data",
        "matter",
        "subject",
        "oggetto",
        "court_name",
        "competent_court",
        "lawyer",
        "difensore",
        "autore",
        "author_user_id",
        "pec_studio",
        "_lawyer_pec",
        "_studio_address",
    ]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in preferred_order:
        if name in existing_names or name in seen:
            continue
        prefill = prefill_fields.get(name)
        if not isinstance(prefill, dict):
            continue
        value = prefill.get("value")
        if isinstance(value, (list, tuple, set)):
            rendered_value = "\n".join(str(item) for item in value if str(item or "").strip())
        else:
            rendered_value = str(value or "").strip()
        if not rendered_value and name not in {"matter", "practice_reference", "practice_subject", "practice_data"}:
            continue
        rows.append(
            _react_template_field_payload(
                {
                    "name": name,
                    "label": str(prefill.get("label") or name.replace("_", " ").title()),
                    "type": "textarea" if "\n" in rendered_value or name in {"practice_data"} else "text",
                    "placeholder": str(prefill.get("missing_reason") or ""),
                    "required": False,
                },
                form_values=form_values,
                field_options={},
                errors={},
                prefill_fields=prefill_fields,
            )
        )
        seen.add(name)
    return rows


def _react_template_compliance_payload(
    *,
    model_code: str,
    prefill_resolution: dict[str, Any],
    form_values: dict[str, Any],
    validation_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    model_name = ""
    model_area = ""
    try:
        from pct.compilatore_atti import get_modello

        model = get_modello(model_code)
        if model:
            if isinstance(model, dict):
                model_name = str(model.get("nome") or model.get("titolo") or model.get("name") or "")
                model_area = str(model.get("categoria") or model.get("area") or model.get("materia") or "")
            else:
                model_name = str(getattr(model, "nome", "") or getattr(model, "titolo", "") or "")
                model_area = str(getattr(model, "categoria", "") or getattr(model, "area", "") or "")
    except Exception:
        model_name = ""
        model_area = ""
    try:
        from pct.template_atti_unified_catalog import get_unified_template_item

        catalog_item = get_unified_template_item(model_code) or {}
        model_name = model_name or str(catalog_item.get("titolo") or catalog_item.get("nome") or "")
        model_area = " ".join(
            str(catalog_item.get(key) or "")
            for key in (
                "area",
                "materia",
                "macro_area",
                "canale_deposito",
                "processo_area",
                "cartabia_profile",
            )
        ).strip() or model_area
    except Exception:
        pass

    try:
        from pct.template_atti_legal_sources import template_atti_sources_for_model

        official_template_sources = template_atti_sources_for_model(
            model_code=model_code,
            model_name=model_name,
            area=model_area,
        )
    except Exception:
        official_template_sources = []

    def _evidence_count(*groups: Any) -> int:
        seen: set[str] = set()
        for group in groups:
            for item in group or []:
                if isinstance(item, dict):
                    key = str(item.get("id") or item.get("source_id") or item.get("title") or "").strip()
                else:
                    key = str(getattr(item, "id", "") or getattr(item, "source_id", "") or getattr(item, "title", "") or item or "").strip()
                if key:
                    seen.add(key.casefold())
        return len(seen)

    def _with_template_sources(references: Any) -> list[Any]:
        rows = list(references or [])
        seen = {
            str((item or {}).get("id") if isinstance(item, dict) else item).casefold()
            for item in rows
            if str((item or {}).get("id") if isinstance(item, dict) else item).strip()
        }
        for source in official_template_sources:
            key = str(source.get("id") or "").casefold()
            if key and key not in seen:
                rows.append(source)
                seen.add(key)
        return rows

    def _rule_text(item: Any) -> str:
        if isinstance(item, dict):
            title = str(
                item.get("source_title")
                or item.get("norma_o_documento")
                or item.get("fonte")
                or item.get("titolo")
                or item.get("documento")
                or ""
            ).strip()
            details = []
            if item.get("articolo_o_sezione"):
                details.append(str(item.get("articolo_o_sezione")).strip())
            if item.get("versione"):
                details.append(f"versione {str(item.get('versione')).strip()}")
            if item.get("data_documento") or item.get("data_ultimo_aggiornamento"):
                details.append(f"aggiornato {str(item.get('data_documento') or item.get('data_ultimo_aggiornamento')).strip()}")
            return " - ".join([part for part in [title, ", ".join(part for part in details if part)] if part])
        return str(item or "").strip()

    def _rule_list(values: Any, *, replace_underscore: bool = False) -> list[str]:
        result = []
        seen: set[str] = set()
        for item in values or []:
            text_value = _rule_text(item)
            if replace_underscore:
                text_value = text_value.replace("_", " ")
            key = text_value.casefold()
            if text_value and key not in seen:
                seen.add(key)
                result.append(text_value)
        return result

    try:
        from pct.template_normative_compliance import analyze_template_compliance

        compliance = analyze_template_compliance(
            model_code,
            form_values,
            studio_timbro_payload=form_values.get("_studio_timbro") if isinstance(form_values, dict) else None,
        )
        payload = compliance.to_dict()
        return {
            "available": True,
            "state": compliance.overall_state,
            "overallState": compliance.overall_state,
            "ready": compliance.can_generate_final_draft,
            "requiresReview": compliance.overall_state != "ok",
            "canGenerateFinalDraft": compliance.can_generate_final_draft,
            "canGenerateWorkingDraft": compliance.can_generate_working_draft,
            "canOpenEditor": compliance.can_open_editor,
            "processArea": compliance.area,
            "profile": f"{compliance.rito} - {compliance.fase}".strip(" -"),
            "rulesetVersion": compliance.ruleset_version,
            "sourceLabel": "Fonti ufficiali applicabili",
            "evidenceCount": _evidence_count(
                [item.to_dict() for item in compliance.source_pack],
                official_template_sources,
            ),
            "missingFields": [item.label for item in compliance.missing_fields],
            "missingFieldRows": [item.to_dict() for item in compliance.missing_fields],
            "missingDocuments": [item.to_dict() for item in compliance.missing_documents],
            "blocking": [check.message for check in compliance.checks if check.state == "block"],
            "recommended": [check.message for check in compliance.checks if check.state == "warning"],
            "normativeReferences": _with_template_sources([item.to_dict() for item in compliance.normative_references]),
            "sources": [item.to_dict() for item in compliance.source_pack] + official_template_sources,
            "officialTemplateSources": official_template_sources,
            "layoutProfile": payload.get("layout_compliance") or {},
            "stampPolicy": payload.get("page_stamp_compliance") or {},
            "reliabilityScore": payload.get("reliability_score") or {},
            "nextActions": list(compliance.next_actions),
            "reasonedExplanation": compliance.reasoned_compliance_explanation,
            "procedibility": [],
            "deadlines": [],
            "cartabiaControls": [item.title for item in compliance.contextual_rules_applied],
            "editorialControls": [check.title for check in compliance.checks],
            "depositControls": [check.title for check in compliance.checks if "PCT" in compliance.channel],
            "validationRules": [
                str(rule.get("message") or rule.get("field") or "").strip()
                for rule in validation_rules
                if isinstance(rule, dict) and str(rule.get("message") or rule.get("field") or "").strip()
            ],
            "warnings": list(compliance.risk_flags),
            "raw": payload,
        }
    except Exception:
        current_app.logger.debug("Compliance contestuale React non disponibile per %s", model_code, exc_info=True)

    try:
        from pct.template_atti_unified_catalog import get_unified_template_item
        from pct.template_cartabia_rules import ensure_cartabia_metadata, verifica_cartabia_template

        item = get_unified_template_item(model_code) or {"codice": model_code, "link_compilatore_code": model_code}
        enriched = ensure_cartabia_metadata(item)
        verification = verifica_cartabia_template(
            enriched,
            prefill_resolution=prefill_resolution,
            payload=form_values,
            strict_data_check=True,
        )
        return {
            "available": True,
            "state": str(verification.get("stato_conformita") or enriched.get("stato_conformita") or ""),
            "ready": bool(verification.get("ok")),
            "requiresReview": bool(verification.get("richiede_verifica_avvocato")),
            "processArea": str(verification.get("processo_area") or enriched.get("processo_area") or ""),
            "profile": str(verification.get("cartabia_profile") or enriched.get("cartabia_profile") or ""),
            "rulesetVersion": str(verification.get("ruleset_version") or enriched.get("versione_regole") or ""),
            "sourceLabel": str(verification.get("fonte_regole") or enriched.get("fonte_regole") or ""),
            "evidenceCount": _evidence_count(
                [{"id": item} for item in (verification.get("source_evidence_ids") or enriched.get("source_evidence_ids") or [])],
                official_template_sources,
            ),
            "missingFields": [str(item) for item in (verification.get("missing_fields") or []) if str(item or "").strip()],
            "blocking": [
                str((item or {}).get("label") or (item or {}).get("codice") or "").strip()
                for item in (verification.get("controlli_bloccanti") or [])
                if isinstance(item, dict)
            ],
            "recommended": [
                str((item or {}).get("label") or (item or {}).get("codice") or "").strip()
                for item in (verification.get("controlli_consigliati") or [])
                if isinstance(item, dict)
            ],
            "normativeReferences": _with_template_sources(_rule_list(enriched.get("normativa_riferimento"))),
            "sources": official_template_sources,
            "officialTemplateSources": official_template_sources,
            "procedibility": _rule_list(enriched.get("condizioni_procedibilita")),
            "deadlines": _rule_list(enriched.get("termini_processuali_rilevanti")),
            "cartabiaControls": _rule_list(enriched.get("controlli_cartabia"), replace_underscore=True),
            "editorialControls": _rule_list(enriched.get("controlli_redazionali"), replace_underscore=True),
            "depositControls": _rule_list(enriched.get("controlli_deposito"), replace_underscore=True),
            "validationRules": [
                str(rule.get("message") or rule.get("field") or "").strip()
                for rule in validation_rules
                if isinstance(rule, dict) and str(rule.get("message") or rule.get("field") or "").strip()
            ],
            "warnings": [
                str(item).strip()
                for item in (enriched.get("avvisi_redazionali") or [])
                if str(item or "").strip()
            ],
        }
    except Exception:
        current_app.logger.debug("Compliance Cartabia React non disponibile per %s", model_code, exc_info=True)
        return {
            "available": False,
            "state": "needs_review",
            "ready": False,
            "requiresReview": True,
            "processArea": "",
            "profile": "",
            "rulesetVersion": "",
            "sourceLabel": "Fonte normativa da verificare",
            "evidenceCount": _evidence_count(official_template_sources),
            "missingFields": [],
            "blocking": ["Controlli Cartabia non disponibili per il modello."],
            "recommended": [],
            "normativeReferences": _with_template_sources([]),
            "sources": official_template_sources,
            "officialTemplateSources": official_template_sources,
            "procedibility": [],
            "deadlines": [],
            "cartabiaControls": [],
            "editorialControls": [],
            "depositControls": [],
            "validationRules": [],
            "warnings": [],
        }


def _react_template_editor_workflow_payload() -> list[dict[str, Any]]:
    labels = [
        "Template selezionato",
        "Autocompilazione dati studio/cliente/fascicolo",
        "Editor documento",
        "Lex Correttore",
        "Lex Revisore stile legale",
        "Lex Revisore placeholder",
        "Lex Revisore normativa/privacy",
        "Controllo finale",
        "Versione finale",
        "Esporta DOCX / PDF / RTF",
    ]
    return [
        {
            "id": f"step_{index:02d}",
            "label": label,
            "state": "active" if index == 3 else "done" if index < 3 else "pending",
        }
        for index, label in enumerate(labels, start=1)
    ]


def _react_template_lex_revision_payload(
    *,
    fields: list[dict[str, Any]],
    compliance: dict[str, Any],
    assistant_analysis: dict[str, Any],
) -> dict[str, Any]:
    missing = [field for field in fields if not str(field.get("value") or "").strip()]
    privacy_warnings = [
        str(item)
        for item in (compliance.get("warnings") or [])
        if "privacy" in str(item).casefold() or "dati personali" in str(item).casefold()
    ]
    normative_warnings = [
        str(item)
        for item in (compliance.get("blocking") or []) + (compliance.get("recommended") or [])
        if str(item or "").strip()
    ][:4]
    seed_proposals: list[dict[str, Any]] = []
    if missing:
        first = missing[0]
        field_name = str(first.get("name") or "").upper()
        seed_proposals.append(
            {
                "id": f"placeholder_{field_name.lower()}",
                "mode": "Revisore Placeholder",
                "title": "Campo da completare prima della versione finale",
                "original": f"[{field_name}]",
                "proposed": str(first.get("label") or field_name),
                "reason": "Il campo resta evidenziato e richiede conferma dell'avvocato.",
                "risk": "warning",
                "status": "pending",
            }
        )
    if normative_warnings:
        seed_proposals.append(
            {
                "id": "controllo_normativo",
                "mode": "Revisore Normativo",
                "title": "Verifica normativa richiesta",
                "original": normative_warnings[0],
                "proposed": "Verifica la fonte applicabile e integra il riferimento solo dopo controllo professionale.",
                "reason": "La proposta non modifica il testo: segnala il punto da confermare.",
                "risk": "warning",
                "status": "pending",
            }
        )
    if privacy_warnings:
        seed_proposals.append(
            {
                "id": "controllo_privacy",
                "mode": "Revisore Privacy",
                "title": "Controllo privacy e dati personali",
                "original": privacy_warnings[0],
                "proposed": "Riduci i dati personali non necessari e conserva solo quanto serve alla pratica.",
                "reason": "Controllo locale, senza invio a servizi esterni.",
                "risk": "warning",
                "status": "pending",
            }
        )
    return {
        "title": "Revisione testo",
        "assistantTitle": "Assistente redazionale Lex",
        "privacyPolicy": {
            "localOnly": True,
            "externalAllowed": False,
            "message": "Analisi locale nello studio; nessun invio a servizi esterni senza policy privacy esplicita.",
        },
        "auditPolicy": {
            "proposalVersioning": True,
            "acceptRejectRequired": True,
            "automaticApply": False,
            "tenantIsolated": True,
        },
        "modes": [
            "Correttore",
            "Redattore",
            "Revisore Normativo",
            "Revisore Privacy",
            "Revisore Placeholder",
            "Template Builder",
            "Final Check",
        ],
        "actions": [
            {"id": "correggi_refusi", "label": "Correggi refusi", "mode": "Correttore"},
            {"id": "migliora_tono", "label": "Migliora tono professionale", "mode": "Redattore"},
            {"id": "rendi_formale", "label": "Rendi più formale", "mode": "Redattore"},
            {"id": "rendi_chiaro_cliente", "label": "Rendi più chiaro per il cliente", "mode": "Redattore"},
            {"id": "rendi_incisivo", "label": "Rendi più incisivo", "mode": "Redattore"},
            {"id": "controlla_placeholder", "label": "Controlla placeholder", "mode": "Revisore Placeholder"},
            {"id": "controlla_normativa", "label": "Controlla normativa", "mode": "Revisore Normativo"},
            {"id": "controlla_privacy", "label": "Controlla privacy", "mode": "Revisore Privacy"},
            {"id": "genera_clausola", "label": "Genera clausola", "mode": "Template Builder"},
            {"id": "espandi_premesse", "label": "Espandi premesse", "mode": "Template Builder"},
            {"id": "versione_finale", "label": "Prepara versione finale", "mode": "Final Check"},
        ],
        "seedProposals": seed_proposals,
        "analysisSummary": str((assistant_analysis or {}).get("summary") or "").strip(),
    }


def _react_template_examples_payload(model_code: str, model_name: str) -> list[dict[str, Any]]:
    def professional_description(raw: str, title: str, row: Any) -> str:
        text = str(raw or "").strip()
        text = re.sub(r"\bTemplate\s+built-in\b", "Modello integrato", text, flags=re.IGNORECASE)
        text = re.sub(r"\bbozza\s+built-in\b", "bozza integrata", text, flags=re.IGNORECASE)
        text = re.sub(r"\bbuilt-in\b", "integrato", text, flags=re.IGNORECASE)
        text = re.sub(
            r"\s*:?\s*template del catalogo master\s*[\w.\- ]*\s*per\s*",
            ": ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\btemplate del catalogo master\s*[\w.\- ]*",
            "modello operativo dello studio",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\bcanale\s+(PST|PCT|PEC)\b", r"canale telematico \1", text, flags=re.IGNORECASE)
        text = re.sub(r"\s{2,}", " ", text).strip(" .")
        if text and text.casefold() != str(title or "").casefold():
            return f"{text}."
        area = _react_template_attr(row, "area", "categoria") or "atto"
        rito = _react_template_attr(row, "rito", "fase") or "pratica"
        return f"Modello operativo per {area}, pronto per la compilazione dalla pratica {rito}."

    examples: list[dict[str, Any]] = []
    try:
        manager = _template_atti_loader()
        rows = list(manager.tutti()) if hasattr(manager, "tutti") else []
    except Exception:
        rows = []
    try:
        from pct.compilatore_atti import (
            BASE_REQUIRED_FIELDS,
            HIDDEN_BASE_FIELDS,
            catalogo_compilatore,
            get_modello as get_compiler_model,
        )
    except Exception:
        BASE_REQUIRED_FIELDS = []
        HIDDEN_BASE_FIELDS = set()
        catalogo_compilatore = None
        get_compiler_model = None
    seen_example_codes: set[str] = set()
    for row in rows:
        code = (
            _react_template_attr(row, "link_compilatore_code")
            or _react_template_attr(row, "codice")
            or _react_template_attr(row, "id")
            or model_code
        )
        if code in seen_example_codes:
            continue
        if callable(get_compiler_model) and not get_compiler_model(code):
            continue
        seen_example_codes.add(code)
        title = _react_template_attr(row, "titolo", "title") or model_name or code
        description = _react_template_attr(row, "descrizione", "description", "note")
        category = _react_template_attr(row, "categoria", "area", "collezione") or "Atti"
        tags = [
            tag
            for tag in (
                _react_template_attr(row, "area"),
                _react_template_attr(row, "fase"),
                _react_template_attr(row, "rito"),
            )
            if tag
        ]
        examples.append(
            {
                "id": _react_template_attr(row, "id") or code,
                "code": code,
                "title": title,
                "description": professional_description(description, title, row),
                "category": category,
                "tags": tags,
                "fieldsCount": len(getattr(row, "campi_guidati", []) or []),
                "href": url_for("template_atti.compila", model_code=code),
                "selected": code == model_code or _react_template_attr(row, "id") == model_code,
            }
        )
    visible_base_count = len([
        name
        for name in BASE_REQUIRED_FIELDS
        if str(name or "").strip() and str(name or "").strip() not in set(HIDDEN_BASE_FIELDS)
    ])

    def compiler_category(model: dict[str, Any]) -> str:
        text = " ".join(
            str(model.get(key) or "")
            for key in ("code", "name", "description", "area", "act_type")
        ).lower()
        if any(token in text for token in ("diffid", "mora", "sollecito", "stragiudizial")):
            return "Diffide"
        if any(token in text for token in ("deleg", "procura", "mandato", "rappresentanza")):
            return "Deleghe"
        if any(token in text for token in ("parere", "responsabilit", "consulenz", "valutazion")):
            return "Pareri"
        if any(token in text for token in ("contratt", "accordo", "locazion", "comodato", "incarico", "privacy", "gdpr")):
            return "Contratti"
        return "Atti"

    if callable(catalogo_compilatore):
        try:
            compiler_rows = list((catalogo_compilatore() or {}).get("models") or [])
        except Exception:
            compiler_rows = []
        for model in compiler_rows:
            code = str((model or {}).get("code") or "").strip()
            if not code or code in seen_example_codes:
                continue
            required_extra = (model or {}).get("required_extra_fields") or []
            title = str((model or {}).get("name") or code).strip()
            description = str((model or {}).get("description") or "").strip()
            examples.append(
                {
                    "id": code,
                    "code": code,
                    "title": title,
                    "description": professional_description(description, title, model),
                    "category": compiler_category(model),
                    "tags": [
                        str(value).strip()
                        for value in ((model or {}).get("areas") or [(model or {}).get("area") or ""])
                        if str(value or "").strip()
                    ],
                    "fieldsCount": visible_base_count + len(required_extra),
                    "href": url_for("template_atti.compila", model_code=code),
                    "selected": code == model_code,
                }
            )
            seen_example_codes.add(code)
            if len(examples) >= 28:
                break
    if not examples:
        examples.append(
            {
                "id": model_code,
                "code": model_code,
                "title": model_name or model_code,
                "description": "Modello corrente collegato alla pratica.",
                "category": "Atti",
                "tags": [],
                "fieldsCount": 0,
                "href": url_for("template_atti.compila", model_code=model_code),
                "selected": True,
            }
        )
    examples.sort(key=lambda item: (not item.get("selected"), str(item.get("title") or "").casefold()))
    return examples[:28]


def _react_template_guide_preview_payload(
    *,
    model_code: str,
    model_name: str,
    selected_fascicolo: Any,
    selected_cliente: Any,
    guidance: dict[str, Any],
    stamp: dict[str, Any],
    initial_text: str = "",
) -> dict[str, Any]:
    guide_code = str(request.args.get("guida_pratica") or request.args.get("codice_guida") or "").strip()
    origin = str(request.args.get("origine") or request.args.get("source") or "").strip().lower()
    enabled = bool(guide_code or origin == "guida_pratica")
    if not enabled:
        return {
            "enabled": False,
            "importEndpoint": url_for("template_atti.api_importa_documento"),
            "previewPdfHref": url_for("template_atti.compila_pdf", model_code=model_code),
            "wordHref": url_for("template_atti.compila_word", model_code=model_code),
            "rtfHref": url_for("template_atti.compila_rtf", model_code=model_code),
            "saveEndpoint": url_for("template_atti.compila_guida_pratica_salva", model_code=model_code),
            "renderEndpoint": url_for("template_atti.compila_guida_pratica_anteprima", model_code=model_code),
            "importLabel": "Importa documento",
            "previewLabel": "Anteprima PDF",
            "saveLabel": "Salva nel fascicolo",
            "import": {
                "enabled": True,
                "formats": "PDF/DOCX/RTF/TXT",
                "note": "Importa nell'editor professionale; il testo resta modificabile prima dell'esportazione.",
            },
            "layoutChecks": [
                {"label": "Timbro studio", "value": "spostabile, dati da Impostazioni Studio", "tone": "success" if (stamp.get("lines") or []) else "warning"},
                {"label": "Corpo atto", "value": "impaginazione coerente al template", "tone": "success"},
            ],
            "editorLayout": {
                "fontSize": 12,
                "lineHeight": 1.9,
                "pageScale": 100,
                "fontFamily": "merriweather",
                "headingFontFamily": "merriweather",
                "uiFontFamily": "inter",
                "placeholderFontFamily": "ibm_plex_mono",
                "fallbackFontFamily": "times_new_roman",
                "stylePreset": "giudiziario_civile",
                "headingSize": 16,
                "textAlign": "justify",
                "pageOrientation": "verticale",
                "marginTop": 25,
                "marginRight": 22,
                "marginBottom": 25,
                "marginLeft": 32,
                "paragraphSpacing": 8,
                "signatureSpacing": 42,
                "stampPosition": "top-center",
                "stampOffsetY": 0,
                "stampFontFamily": "ibm_plex_mono",
                "stampFontSize": 8,
                "stampLineHeight": 1.16,
                "printCleanPlaceholders": False,
            },
        }
    fascicolo_id = _react_template_attr(selected_fascicolo, "id")
    guide_title = str(guidance.get("title") or guidance.get("summary") or "").strip()
    canonical_model_code = _guide_selected_model_code(
        model_code=model_code,
        guide_code=guide_code,
        selected_fascicolo=selected_fascicolo,
    )
    canonical_model_code = str(canonical_model_code or model_code or "").strip()
    model_label = str(model_name or model_code or "Template atto").strip()
    selected_case_label = _react_template_attr(selected_fascicolo, "titolo", "oggetto")
    selected_client_label = _react_template_attr(selected_cliente, "nome_completo", "ragione_sociale", "nome")
    subtitle = (
        "La guida carica il template già filtrato sulla pratica; l'avvocato può cambiarlo o "
        "importare un proprio PDF, DOCX, RTF o TXT senza chiudere il fascicolo."
    )
    if selected_case_label or selected_client_label:
        subtitle = f"{subtitle} Contesto: {' - '.join(part for part in [selected_case_label, selected_client_label] if part)}."
    return {
        "enabled": True,
        "eyebrow": "Anteprima modifica",
        "title": "Editor documento con impaginazione modello",
        "subtitle": subtitle,
        "badge": "template filtrato dalla guida",
        "guideCode": guide_code,
        "guideTitle": guide_title,
        "fascicoloHref": url_for("dettaglio_fascicolo", id_fasc=fascicolo_id) if fascicolo_id else "",
        "uploadEndpoint": url_for("carica_documento", id_fasc=fascicolo_id) if fascicolo_id else "",
        "importEndpoint": url_for("template_atti.api_importa_documento"),
        "previewPdfHref": url_for("template_atti.compila_pdf", model_code=model_code),
        "wordHref": url_for("template_atti.compila_word", model_code=model_code),
        "rtfHref": url_for("template_atti.compila_rtf", model_code=model_code),
        "saveEndpoint": url_for("template_atti.compila_guida_pratica_salva", model_code=model_code),
        "renderEndpoint": url_for("template_atti.compila_guida_pratica_anteprima", model_code=model_code),
        "importLabel": "Importa documento",
        "previewLabel": "Anteprima PDF",
        "saveLabel": "Salva nel fascicolo",
        "initialText": initial_text,
        "reason": "atto principale suggerito per questo passaggio operativo",
        "steps": [
            {"id": "apertura", "label": "1 Apertura", "state": "done"},
            {"id": "guida-nascosta", "label": "2 Guida nascosta", "state": "done"},
            {"id": "guida-ora", "label": "3 Guida ora", "state": "done"},
            {"id": "contesto-termini", "label": "4 Contesto e termini", "state": "done"},
            {"id": "anteprima-modifica", "label": "5 Anteprima modifica", "state": "active"},
            {"id": "rientro", "label": "6 Rientro completato", "state": "pending"},
        ],
        "template": {
            "code": canonical_model_code,
            "name": model_label,
            "reason": "filtrato da codice, rito, fase, ufficio e oggetto pratica",
            "autoLoad": True,
        },
        "import": {
            "enabled": True,
            "formats": "PDF/DOCX/RTF/TXT",
            "note": "Importa nell'anteprima: modifica se editabile, altrimenti salva l'originale collegato.",
        },
        "layoutChecks": [
            {"label": "Timbro studio", "value": "spostabile, dati da Impostazioni Studio", "tone": "success" if (stamp.get("lines") or []) else "warning"},
            {"label": "Corpo atto", "value": "impaginazione coerente al template", "tone": "success"},
        ],
        "editorLayout": {
            "fontSize": 12,
            "lineHeight": 1.9,
            "pageScale": 100,
            "fontFamily": "merriweather",
            "headingFontFamily": "merriweather",
            "uiFontFamily": "inter",
            "placeholderFontFamily": "ibm_plex_mono",
            "fallbackFontFamily": "times_new_roman",
            "stylePreset": "giudiziario_civile",
            "headingSize": 16,
            "textAlign": "justify",
            "pageOrientation": "verticale",
            "marginTop": 25,
            "marginRight": 22,
            "marginBottom": 25,
            "marginLeft": 32,
            "paragraphSpacing": 8,
            "signatureSpacing": 42,
            "stampPosition": "top-center",
            "stampOffsetY": 0,
            "stampFontFamily": "ibm_plex_mono",
            "stampFontSize": 8,
            "stampLineHeight": 1.16,
            "printCleanPlaceholders": False,
        },
    }


def _guide_selected_model_code(*, model_code: str, guide_code: str, selected_fascicolo: Any) -> str:
    try:
        from web.services.react_guida_pratica_bridge import build_document_plan_for_guida, fascicolo_guida_context
        from pct.guida_pratica import get_guida_pratica_service

        if not guide_code or not selected_fascicolo:
            return str(model_code or "").strip()
        fascicolo_context = fascicolo_guida_context(selected_fascicolo)
        guida = get_guida_pratica_service().get_guidance(guide_code, fascicolo=fascicolo_context)
        plan = build_document_plan_for_guida(guida, fascicolo_context)
        recommended = ((plan.get("template") or {}).get("recommended") or {}) if isinstance(plan, dict) else {}
        requested = str(model_code or "").strip()
        options = [recommended]
        alternatives = ((plan.get("template") or {}).get("alternatives") or []) if isinstance(plan, dict) else []
        if isinstance(alternatives, list):
            options.extend(item for item in alternatives if isinstance(item, dict))
        for option in options:
            option_codes = {
                str(option.get("id") or "").strip(),
                str(option.get("compilerCode") or "").strip(),
                str(option.get("link_compilatore_code") or "").strip(),
            }
            if requested and requested in option_codes:
                return requested
        return str(recommended.get("id") or recommended.get("compilerCode") or model_code or "").strip()
    except Exception:
        current_app.logger.debug("Template filtrato guida non risolto per %s", model_code, exc_info=True)
        return str(model_code or "").strip()


def _guide_template_target_code(*, model_code: str, guide_code: str, selected_fascicolo: Any) -> str:
    resolved = _guide_selected_model_code(
        model_code=model_code,
        guide_code=guide_code,
        selected_fascicolo=selected_fascicolo,
    )
    if not resolved:
        return ""
    target = resolved
    try:
        from pct.compilatore_atti import get_modello

        if not get_modello(target):
            from pct.template_catalog_service import build_template_catalog_items

            row = next((item for item in build_template_catalog_items() if str(item.get("codice") or "").strip() == target), None)
            target = str((row or {}).get("link_compilatore_code") or target).strip()
    except Exception:
        return ""
    return target


def _redirect_target_for_guide_template(*, model_code: str, guide_code: str, selected_fascicolo: Any) -> str:
    target = _guide_template_target_code(
        model_code=model_code,
        guide_code=guide_code,
        selected_fascicolo=selected_fascicolo,
    )
    if target and target != model_code:
        params = request.args.to_dict(flat=True)
        params["guida_pratica"] = guide_code
        params["origine"] = "guida_pratica"
        href = url_for("template_atti.compila", model_code=target)
        return f"{href}?{urlencode(params)}"
    return ""


@api_v1_react.get("/template-atti/compila/<model_code>")
@_richiedi_auth
def template_atti_compila_page(model_code: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "message": "Sessione utente richiesta.", "fields": []}), 403
    try:
        from web.blueprints.template_atti import (
            _build_assistant_analysis,
            _contesto_compilatore,
            _get_gp,
            _resolve_compiler_context,
        )

        requested_model_code = str(model_code or "").strip()
        guide_code = str(request.args.get("guida_pratica") or request.args.get("codice_guida") or "").strip()
        origin = str(request.args.get("origine") or request.args.get("source") or "").strip().lower()
        free_editor = str(request.args.get("editor_libero") or "").strip().lower() in {"1", "true", "si", "yes"}
        selected_fascicolo = None
        selected_fascicolo_id = str(
            request.args.get("id_fascicolo")
            or request.args.get("case_id")
            or request.form.get("id_fascicolo")
            or request.form.get("case_id")
            or ""
        ).strip()
        if selected_fascicolo_id:
            try:
                selected_fascicolo = get_fascicoli().get(selected_fascicolo_id)
            except Exception:
                selected_fascicolo = None
        if guide_code or origin == "guida_pratica":
            guide_target = _guide_template_target_code(
                model_code=model_code,
                guide_code=guide_code,
                selected_fascicolo=selected_fascicolo,
            )
            if guide_target and guide_target != model_code:
                model_code = guide_target

        resolved = _resolve_compiler_context(model_code)
        assistant_analysis = _build_assistant_analysis(
            model_code,
            payload=resolved["payload"],
            selected_cliente=resolved["selected_cliente"],
            selected_fascicolo=resolved["selected_fascicolo"],
        )
        ctx = _contesto_compilatore(
            model_code,
            payload=resolved["payload"],
            selected_cliente=resolved["selected_cliente"],
            selected_fascicolo=resolved["selected_fascicolo"],
            assistant_analysis=assistant_analysis,
            correction_context=resolved["correction_context"],
        )
        model = ctx["model"]
        form_values = ctx.get("form_values") or {}
        errors = ctx.get("errors") or {}
        prefill_resolution = ctx.get("prefill_resolution") if isinstance(ctx.get("prefill_resolution"), dict) else {}
        prefill_fields = prefill_resolution.get("fields") if isinstance(prefill_resolution.get("fields"), dict) else {}
        selected_cliente = ctx.get("selected_cliente")
        selected_fascicolo = ctx.get("selected_fascicolo")
        base_fields = [
            _react_template_field_payload(
                field,
                form_values=form_values,
                field_options=ctx.get("field_options") or {},
                errors=errors,
                prefill_fields=prefill_fields,
                selected_fascicolo=selected_fascicolo,
            )
            for field in ctx.get("base_fields", [])
        ]
        extra_fields = [
            _react_template_field_payload(
                field,
                form_values=form_values,
                field_options=ctx.get("field_options") or {},
                errors=errors,
                prefill_fields=prefill_fields,
                selected_fascicolo=selected_fascicolo,
            )
            for field in ctx.get("extra_fields", [])
        ]
        existing_field_names = {
            str(field.get("name") or "").strip()
            for field in [*base_fields, *extra_fields]
            if str(field.get("name") or "").strip()
        }
        context_fields = _react_template_context_fields_payload(
            prefill_fields=prefill_fields,
            existing_names=existing_field_names,
            form_values=form_values,
        )
        hidden_names = ["model_code", "area", "act_type", "case_id", "author_user_id", "version", "status"]
        clienti = [
            _react_template_choice(
                _react_template_attr(cliente, "id"),
                _react_template_attr(cliente, "nome_completo", "ragione_sociale", "nome"),
            )
            for cliente in ctx.get("clienti", [])
        ]
        fascicoli = []
        for fascicolo in ctx.get("fascicoli", []):
            title = _react_template_attr(fascicolo, "titolo", "oggetto") or "Pratica"
            rg = _react_template_attr(fascicolo, "rg_completo", "numero_rg")
            fascicoli.append(
                _react_template_choice(
                    _react_template_attr(fascicolo, "id"),
                    f"{title} - {rg}" if rg else title,
                    clienteId=_react_template_attr(fascicolo, "id_cliente"),
                )
            )
        issues = assistant_analysis.get("issues", []) if isinstance(assistant_analysis, dict) else []
        blocking_issues = [
            str((issue or {}).get("title") or (issue or {}).get("message") or "").strip()
            for issue in issues
            if isinstance(issue, dict) and str(issue.get("level") or "").upper() == "BLOCK"
        ]
        recommended_issues = [
            str((issue or {}).get("title") or (issue or {}).get("message") or "").strip()
            for issue in issues
            if isinstance(issue, dict) and str(issue.get("level") or "").upper() != "BLOCK"
        ]
        stamp = ctx.get("studio_timbro_preview") or {}
        guidance = ctx.get("guidance") if isinstance(ctx.get("guidance"), dict) else {}
        initial_text = ""
        if guide_code or origin == "guida_pratica":
            try:
                from pct.compilatore_atti import render_compiled_act

                initial_text = render_compiled_act(
                    model_code,
                    ctx.get("payload") if isinstance(ctx.get("payload"), dict) else form_values,
                    include_timbro=False,
                )
            except Exception:
                current_app.logger.debug("Anteprima testo template non generata per %s", model_code, exc_info=True)
        compliance_payload = _react_template_compliance_payload(
            model_code=model_code,
            prefill_resolution=prefill_resolution,
            form_values=ctx.get("payload") if isinstance(ctx.get("payload"), dict) else form_values,
            validation_rules=ctx.get("validation_rules") or [],
        )
        all_fields = base_fields + extra_fields + context_fields
        try:
            from pct.template_atti import template_font_registry_payload

            font_registry = template_font_registry_payload()
        except Exception:
            current_app.logger.debug("Registro font template atti non disponibile per %s", model_code, exc_info=True)
            font_registry = {}
        try:
            editor_layout = _get_gp().carica()
        except Exception:
            editor_layout = {}
        model_name = "Documento libero" if free_editor else str(model.get("name") or model_code)
        return jsonify(
            {
                "ok": True,
                "model": {
                    "code": str(model.get("code") or model_code),
                    "name": model_name,
                    "area": str(model.get("area") or ""),
                },
                "summary": "Editor libero per scrivere un atto o un documento senza partire da un modello già compilato." if free_editor else str(guidance.get("summary") or "Compilazione guidata con dati IUSENTRA."),
                "formAction": url_for("template_atti.compila", model_code=model_code),
                "catalogHref": url_for("template_atti.catalogo"),
                "submitLabel": "Salva bozza libera" if free_editor else "Crea bozza e apri editor" if selected_fascicolo else "Crea bozza dell'atto",
                "selectors": {
                    "clienti": clienti,
                    "fascicoli": fascicoli,
                    "selectedClienteId": _react_template_attr(selected_cliente, "id"),
                    "selectedFascicoloId": _react_template_attr(selected_fascicolo, "id"),
                    "selectedClienteLabel": _react_template_attr(selected_cliente, "nome_completo", "ragione_sociale", "nome"),
                    "selectedFascicoloLabel": _react_template_attr(selected_fascicolo, "titolo", "oggetto"),
                },
                "hidden": {
                    name: str(form_values.get(name, "") or "")
                    for name in hidden_names
                },
                "requestedModelCode": requested_model_code,
                "baseFields": base_fields,
                "extraFields": extra_fields,
                "contextFields": context_fields,
                "templateExamples": _react_template_examples_payload(model_code, model_name),
                "officialTemplateSources": compliance_payload.get("officialTemplateSources") or compliance_payload.get("sources") or [],
                "fontRegistry": font_registry,
                "editorLayout": editor_layout,
                "editorWorkflow": _react_template_editor_workflow_payload(),
                "lexRevision": _react_template_lex_revision_payload(
                    fields=all_fields,
                    compliance=compliance_payload,
                    assistant_analysis=assistant_analysis,
                ),
                "stamp": {
                    "lines": stamp.get("lines") or [],
                    "text": str(stamp.get("text") or ""),
                },
                "compliance": compliance_payload,
                "checks": {
                    "blocking": [item for item in blocking_issues if item],
                    "recommended": [item for item in recommended_issues if item],
                },
                "attachments": [str(item) for item in (ctx.get("suggested_attachments") or []) if str(item or "").strip()],
                "sections": [
                    {
                        "label": str(section.get("label") or section.get("title") or "").strip(),
                        "state": str(section.get("state") or "").strip(),
                    }
                    for section in (assistant_analysis.get("sections", []) if isinstance(assistant_analysis, dict) else [])
                    if isinstance(section, dict)
                ],
                "guidePreview": _react_template_guide_preview_payload(
                    model_code=model_code,
                    model_name=model_name,
                    selected_fascicolo=selected_fascicolo,
                    selected_cliente=selected_cliente,
                    guidance=guidance,
                    stamp=stamp,
                    initial_text=initial_text,
                ),
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore compilatore Template Atti React bridge: %s", exc)
        return jsonify(
            {
                "ok": False,
                "message": "Compilazione template atti non disponibile dal runtime corrente.",
                "model": {"code": model_code, "name": model_code, "area": ""},
                "baseFields": [],
                "extraFields": [],
            }
        ), 200


@api_v1_react.get("/studio/timbro")
@_richiedi_auth
def studio_timbro_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errors": {"sessione": "Sessione utente richiesta."}}), 403
    try:
        payload = _studio_timbro_payload()
        return jsonify({"ok": True, "timbro": payload["payload"], "preview": payload}), 200
    except Exception as exc:
        current_app.logger.exception("Errore lettura Timbro Studio React: %s", exc)
        return jsonify({"ok": False, "message": "Timbro studio non disponibile."}), 200


@api_v1_react.get("/studio/timbro/preview")
@_richiedi_auth
def studio_timbro_preview_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errors": {"sessione": "Sessione utente richiesta."}}), 403
    try:
        payload = _studio_timbro_payload()
        return jsonify({"ok": True, "preview": payload, "timbro": payload["payload"]}), 200
    except Exception as exc:
        current_app.logger.exception("Errore anteprima Timbro Studio React: %s", exc)
        return jsonify({"ok": False, "message": "Anteprima timbro studio non disponibile."}), 200


@api_v1_react.post("/studio/timbro")
@_richiedi_auth
def studio_timbro_save():
    if not _puo_configurare_impostazioni():
        return jsonify({"ok": False, "errors": {"permessi": "Permesso di configurazione richiesto."}}), 403
    payload, error = _request_json_object()
    if error is not None:
        return error
    from pct.studio_timbro import save_studio_timbro, StudioTimbro

    try:
        raw_timbro = payload.get("timbro", payload) if isinstance(payload, dict) else {}
        try:
            config_studio = getattr(_studio_config_manager(), "config", None)
        except Exception:
            config_studio = None
        saved = save_studio_timbro(
            raw_timbro,
            db_path=_cfg_value("STUDIO_TIMBRO_DB", "./config/studio_timbro.db"),
            config_studio=config_studio,
            app_config=current_app.config,
        )
        timbro = StudioTimbro.from_payload(saved)
        _audit_event("studio.timbro.salva", "studio_timbro", "default", "Timbro studio aggiornato.")
        return jsonify(
            {
                "ok": True,
                "message": "Timbro studio salvato.",
                "timbro": saved,
                "preview": {
                    "payload": saved,
                    "lines": timbro.to_lines(),
                    "html": timbro.to_html(),
                    "text": timbro.to_text(),
                    "scope": timbro.scope_payload(),
                },
            }
        ), 200
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio Timbro Studio React: %s", exc)
        return jsonify({"ok": False, "message": "Salvataggio timbro studio non riuscito."}), 200


@api_v1_react.get("/redazione-atti")
@_richiedi_auth
def redazione_atti_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_redazione_atti_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_redazione_atti_payload(
                get_template_manager=_template_atti_loader,
                get_fascicoli=get_fascicoli,
                get_preventivi=get_preventivi_readonly,
                config=_studio_prefill_config(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Redazione Atti React bridge: %s", exc)
        return jsonify(
            build_react_redazione_atti_error_payload(
                "Redazione atti non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.post("/redazione-atti/produci")
@_richiedi_auth
def redazione_atti_produci():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errors": {"sessione": "Sessione utente richiesta."}, "warnings": []}), 403
    payload = request.get_json(silent=True) or {}
    result, status = produce_react_redazione_atti(payload, config=_studio_prefill_config())
    return _jsonify_redacted(result), status


def _redazione_normativa_db_path() -> str:
    return _cfg_value("REDAZIONE_NORMATIVA_DB", "./template_atti/riferimenti_normativi.json")


def _redazione_carica_fascicolo_cliente(id_fascicolo: str, id_cliente: str = ""):
    """Carica fascicolo e cliente verificando l'associazione dichiarata."""
    from web.services.react_redazione_guidata_bridge import verifica_fascicolo_del_cliente

    fascicolo = get_fascicoli().get(str(id_fascicolo or "").strip()) if id_fascicolo else None
    if fascicolo is None:
        return None, None, "Fascicolo non trovato."
    if id_cliente and not verifica_fascicolo_del_cliente(fascicolo, id_cliente):
        return None, None, "Il fascicolo non appartiene al cliente selezionato."
    cliente = None
    cliente_id = str(id_cliente or getattr(fascicolo, "id_cliente", "") or "").strip()
    if cliente_id:
        cliente = get_clienti().get(cliente_id)
    return fascicolo, cliente, ""


@api_v1_react.get("/redazione-atti/clienti")
@_richiedi_auth
def redazione_atti_clienti():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta.", "clienti": []}), 403
    try:
        from web.services.react_redazione_guidata_bridge import build_redazione_clienti_payload

        return _jsonify_redacted(
            build_redazione_clienti_payload(get_clienti=get_clienti, get_fascicoli=get_fascicoli)
        )
    except Exception as exc:
        current_app.logger.exception("Errore elenco clienti redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Clienti non disponibili dal runtime corrente.", "clienti": []}), 200


@api_v1_react.get("/redazione-atti/clienti/<id_cliente>/fascicoli")
@_richiedi_auth
def redazione_atti_fascicoli_cliente(id_cliente: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta.", "fascicoli": []}), 403
    try:
        from web.services.react_redazione_guidata_bridge import build_redazione_fascicoli_payload

        return _jsonify_redacted(
            build_redazione_fascicoli_payload(get_fascicoli=get_fascicoli, cliente_id=id_cliente)
        )
    except Exception as exc:
        current_app.logger.exception("Errore fascicoli cliente redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Fascicoli non disponibili dal runtime corrente.", "fascicoli": []}), 200


@api_v1_react.get("/redazione-atti/fascicoli/<id_fascicolo>/contesto")
@_richiedi_auth
def redazione_atti_contesto_fascicolo(id_fascicolo: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403
    try:
        from web.blueprints.template_atti import _build_parti_template_context
        from web.services.react_redazione_guidata_bridge import build_redazione_contesto_payload

        id_cliente = str(request.args.get("id_cliente") or "").strip()
        fascicolo, cliente, errore = _redazione_carica_fascicolo_cliente(id_fascicolo, id_cliente)
        if errore:
            return jsonify({"ok": False, "errore": errore}), 200
        _, parti = _build_parti_template_context(str(getattr(fascicolo, "id", "") or ""))
        return _jsonify_redacted(
            build_redazione_contesto_payload(
                fascicolo=fascicolo,
                cliente=cliente,
                parti=parti,
                config=_studio_prefill_config(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore contesto fascicolo redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Contesto fascicolo non disponibile dal runtime corrente."}), 200


@api_v1_react.get("/redazione-atti/anteprima/<model_code>")
@_richiedi_auth
def redazione_atti_anteprima(model_code: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403
    try:
        from web.blueprints.template_atti import _build_parti_template_context, _get_studio_timbro
        from web.services.react_redazione_guidata_bridge import build_redazione_anteprima_payload

        id_fascicolo = str(request.args.get("id_fascicolo") or "").strip()
        id_cliente = str(request.args.get("id_cliente") or "").strip()
        if not id_fascicolo:
            return jsonify({"ok": False, "errore": "Seleziona prima il fascicolo."}), 200
        fascicolo, cliente, errore = _redazione_carica_fascicolo_cliente(id_fascicolo, id_cliente)
        if errore:
            return jsonify({"ok": False, "errore": errore}), 200
        _, parti = _build_parti_template_context(id_fascicolo)
        return _jsonify_redacted(
            build_redazione_anteprima_payload(
                model_code=model_code,
                fascicolo=fascicolo,
                cliente=cliente,
                parti=parti,
                utente=utente,
                config=_studio_prefill_config(),
                studio_timbro=_get_studio_timbro(),
                normativa_db_path=_redazione_normativa_db_path(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore anteprima redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Anteprima non disponibile dal runtime corrente."}), 200


@api_v1_react.post("/redazione-atti/genera")
@_richiedi_auth
def redazione_atti_genera():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403
    try:
        from pct.compilatore_atti import get_modello, render_compiled_act
        from web.blueprints.template_atti import (
            _build_contextual_compliance,
            _build_parti_template_context,
            _get_studio_timbro,
            _importa_compilazione_editor_professionale,
            _sanitize_editor_html,
            _to_editor_html,
        )
        from web.services.react_redazione_guidata_bridge import (
            evidenzia_dati_mancanti_html,
            prepara_payload_generazione,
        )

        dati = request.get_json(silent=True) or {}
        model_code = str(dati.get("modelCode") or dati.get("model_code") or "").strip()
        id_fascicolo = str(dati.get("idFascicolo") or dati.get("id_fascicolo") or "").strip()
        id_cliente = str(dati.get("idCliente") or dati.get("id_cliente") or "").strip()
        valori = dati.get("valori") if isinstance(dati.get("valori"), dict) else {}
        riferimenti = dati.get("riferimenti") if isinstance(dati.get("riferimenti"), list) else []
        conferma_bozza = bool(dati.get("confermaBozza"))
        conferma_avvisi = bool(dati.get("confermaAvvisi"))

        modello = get_modello(model_code)
        if not modello:
            return jsonify({"ok": False, "errore": "Modello atto non riconosciuto."}), 200
        if not id_fascicolo:
            return jsonify({"ok": False, "errore": "Seleziona il fascicolo: l'atto deve restare collegato alla pratica reale."}), 200
        fascicolo, cliente, errore = _redazione_carica_fascicolo_cliente(id_fascicolo, id_cliente)
        if errore:
            return jsonify({"ok": False, "errore": errore}), 200
        _, parti = _build_parti_template_context(id_fascicolo)

        preparazione = prepara_payload_generazione(
            model_code=model_code,
            fascicolo=fascicolo,
            cliente=cliente,
            parti=parti,
            utente=utente,
            config=_studio_prefill_config(),
            studio_timbro=_get_studio_timbro(),
            valori_utente=valori,
            riferimenti_selezionati=riferimenti,
            conferma_bozza=conferma_bozza,
        )
        if not preparazione["ok"]:
            return jsonify(
                {
                    "ok": False,
                    "errore": "Campi obbligatori mancanti: completali o conferma la creazione di una bozza da revisionare.",
                    "errors": preparazione["errors"],
                    "campiMancanti": preparazione["mancanti"],
                    "richiedeConfermaBozza": True,
                }
            ), 200

        payload = preparazione["payload"]
        marcati = preparazione["marcati"]
        compliance_result = _build_contextual_compliance(
            model_code,
            payload=payload,
            selected_cliente=cliente,
            selected_fascicolo=fascicolo,
        )
        if compliance_result.overall_state == "block":
            return jsonify(
                {
                    "ok": False,
                    "errore": "La generazione e' bloccata dai controlli normativi applicabili.",
                    "compliance": compliance_result.to_dict(),
                }
            ), 200
        if compliance_result.overall_state == "warning" and not (conferma_avvisi or conferma_bozza):
            return jsonify(
                {
                    "ok": False,
                    "errore": "I controlli normativi richiedono conferma: posso creare una bozza di lavoro da revisionare.",
                    "richiedeConfermaAvvisi": True,
                    "compliance": compliance_result.to_dict(),
                }
            ), 200
        requested_draft = "working_draft" if (marcati or compliance_result.overall_state == "warning") else "final_draft"

        testo_generato = render_compiled_act(model_code, payload)
        editor_import = _importa_compilazione_editor_professionale(
            model_code=model_code,
            model=modello,
            payload=payload,
            testo_generato=testo_generato,
            selected_fascicolo=fascicolo,
            compliance_result=compliance_result,
            requested_draft=requested_draft,
            confirmed_warning=True if requested_draft == "working_draft" else conferma_avvisi,
            editor_html_builder=lambda text: _sanitize_editor_html(
                evidenzia_dati_mancanti_html(_to_editor_html(text))
            ),
        )
        if not editor_import:
            return jsonify({"ok": False, "errore": "Generazione non riuscita: fascicolo non collegato."}), 200
        return jsonify(
            {
                "ok": True,
                "messaggio": "Atto generato con i dati reali del fascicolo e aperto nell'editor.",
                "documentId": editor_import["document_id"],
                "editorUrl": editor_import["editor_url"],
                "signatureUrl": editor_import.get("signature_url", ""),
                "createdAs": editor_import.get("created_as") or requested_draft,
                "complianceState": editor_import.get("compliance_state") or compliance_result.overall_state,
                "campiMarcati": marcati,
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore generazione redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Generazione non disponibile dal runtime corrente."}), 200


@api_v1_react.get("/redazione-atti/normativa/<model_code>")
@_richiedi_auth
def redazione_atti_normativa(model_code: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403
    try:
        from pct.redazione_contesto import condizioni_dal_fascicolo
        from pct.redazione_normativa import riferimenti_per_modello

        id_fascicolo = str(request.args.get("id_fascicolo") or "").strip()
        condizioni: dict[str, bool] = {}
        materia = ""
        if id_fascicolo:
            fascicolo = get_fascicoli().get(id_fascicolo)
            if fascicolo is not None:
                condizioni = condizioni_dal_fascicolo(fascicolo)
                tipo = getattr(fascicolo, "tipo", "")
                materia = getattr(tipo, "value", str(tipo or ""))
        return _jsonify_redacted(
            {
                "ok": True,
                "normativa": riferimenti_per_modello(
                    model_code,
                    materia=materia,
                    condizioni=condizioni,
                    db_path=_redazione_normativa_db_path(),
                ),
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore normativa redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Riferimenti normativi non disponibili."}), 200


@api_v1_react.post("/redazione-atti/normativa")
@_richiedi_auth
def redazione_atti_normativa_salva():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403
    try:
        from pct.redazione_normativa import disattiva_riferimento, riattiva_riferimento, salva_riferimento

        dati = request.get_json(silent=True) or {}
        azione = str(dati.get("azione") or "salva").strip().lower()
        db_path = _redazione_normativa_db_path()
        if azione == "disattiva":
            esito = disattiva_riferimento(str(dati.get("id") or ""), db_path=db_path)
            if esito:
                _audit_event("redazione.normativa.disattiva", "riferimento_normativo", str(dati.get("id") or ""), "Riferimento normativo disattivato dallo studio.")
            return jsonify({"ok": esito})
        if azione == "riattiva":
            esito = riattiva_riferimento(str(dati.get("id") or ""), db_path=db_path)
            if esito:
                _audit_event("redazione.normativa.riattiva", "riferimento_normativo", str(dati.get("id") or ""), "Riferimento normativo riattivato dallo studio.")
            return jsonify({"ok": esito})
        riferimento = salva_riferimento(dati.get("riferimento") if isinstance(dati.get("riferimento"), dict) else dati, db_path=db_path)
        _audit_event("redazione.normativa.salva", "riferimento_normativo", riferimento.id, f"Riferimento {riferimento.riferimento_breve()} aggiornato dallo studio.")
        return jsonify({"ok": True, "riferimento": riferimento.to_dict()})
    except ValueError as exc:
        current_app.logger.warning("Riferimento normativo non valido: %s", exc)
        return jsonify({"ok": False, "errore": "Riferimento normativo non valido."}), 200
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio normativa redazione atti: %s", exc)
        return jsonify({"ok": False, "errore": "Salvataggio riferimento non riuscito."}), 200


def _procedure_completion_guard(permesso: str):
    """Verifica flag + permesso RBAC; restituisce (service, context, errore_eventuale)."""
    from web.services.react_procedure_completion_bridge import (
        build_service,
        engine_enabled,
        error_payload,
        request_context,
    )

    utente = g.get("utente_corrente")
    if not utente:
        return None, None, (jsonify({"ok": False, "errore": "Sessione utente richiesta."}), 403)
    if not engine_enabled():
        payload, status = error_payload("Procedure Completion Engine non attivo per questo studio.", status=403)
        return None, None, (jsonify(payload), status)
    if not getattr(utente, "ha_permesso", lambda _p: False)(permesso):
        payload, status = error_payload(f"Permesso mancante: {permesso}.", status=403)
        return None, None, (jsonify(payload), status)
    return build_service(), request_context(), None


def _procedure_completion_public_error(message: str, exc: Exception, *, status: int = 200):
    current_app.logger.warning("Errore governato Procedure Completion: %s", exc)
    return jsonify({"ok": False, "errore": message}), status


@api_v1_react.get("/procedure-completion")
@_richiedi_auth
def procedure_completion_dashboard():
    try:
        from web.services.react_procedure_completion_bridge import build_dashboard_payload

        service, context, errore = _procedure_completion_guard("procedure_completion.leggi")
        if errore is not None:
            return errore
        return _jsonify_redacted(build_dashboard_payload(service, context))
    except Exception as exc:
        current_app.logger.exception("Errore dashboard procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Dashboard non disponibile dal runtime corrente."}), 200


@api_v1_react.post("/procedure-completion/preview")
@_richiedi_auth
def procedure_completion_preview():
    try:
        from pct.procedure_completion.service import ProcedureCompletionError
        from web.services.react_procedure_completion_bridge import validate_client_payload

        service, context, errore = _procedure_completion_guard("procedure_completion.esegui")
        if errore is not None:
            return errore
        payload = request.get_json(silent=True) or {}
        violazione = validate_client_payload(payload)
        if violazione:
            return jsonify({"ok": False, "errore": violazione, "code": "backend_security_control_param"}), 400
        try:
            esito = service.preview_completion(payload, context)
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Anteprima non disponibile per questa richiesta.", exc)
        return _jsonify_redacted(esito)
    except Exception as exc:
        current_app.logger.exception("Errore preview procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Anteprima non disponibile dal runtime corrente."}), 200


@api_v1_react.get("/procedure-completion/cards/<card_id>")
@_richiedi_auth
def procedure_completion_card_detail(card_id: str):
    try:
        from pct.procedure_completion.service import ProcedureCompletionError
        from pct.procedure_completion.validator import validate_card
        from web.services.react_procedure_completion_bridge import card_detail_payload

        service, context, errore = _procedure_completion_guard("procedure_completion.leggi")
        if errore is not None:
            return errore
        try:
            card = service.get_card(card_id, context)
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Scheda non disponibile.", exc, status=404)
        return _jsonify_redacted(card_detail_payload(card, validate_card(card).to_dict()))
    except Exception as exc:
        current_app.logger.exception("Errore dettaglio scheda procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Scheda non disponibile dal runtime corrente."}), 200


@api_v1_react.post("/procedure-completion/cards/<card_id>/submit-review")
@_richiedi_auth
def procedure_completion_submit_review(card_id: str):
    try:
        from pct.procedure_completion.service import ProcedureCompletionError
        from web.services.react_procedure_completion_bridge import validate_client_payload

        service, context, errore = _procedure_completion_guard("procedure_completion.esegui")
        if errore is not None:
            return errore
        payload = request.get_json(silent=True) or {}
        violazione = validate_client_payload(payload)
        if violazione:
            return jsonify({"ok": False, "errore": violazione, "code": "backend_security_control_param"}), 400
        try:
            esito = service.submit_for_review(card_id, context, reason=str(payload.get("reason") or ""))
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Invio in revisione non disponibile.", exc)
        return _jsonify_redacted(esito)
    except Exception as exc:
        current_app.logger.exception("Errore submit review procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Invio in revisione non disponibile."}), 200


@api_v1_react.post("/procedure-completion/cards/<card_id>/approve")
@_richiedi_auth
def procedure_completion_approve(card_id: str):
    try:
        from pct.procedure_completion.service import ProcedureCompletionError
        from web.services.react_procedure_completion_bridge import validate_client_payload

        service, context, errore = _procedure_completion_guard("procedure_completion.approva")
        if errore is not None:
            return errore
        payload = request.get_json(silent=True) or {}
        violazione = validate_client_payload(payload)
        if violazione:
            return jsonify({"ok": False, "errore": violazione, "code": "backend_security_control_param"}), 400
        try:
            esito = service.approve_completion(
                card_id,
                reviewer=context.get("user_id") or "",
                reason=str(payload.get("reason") or ""),
                context=context,
            )
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Approvazione non disponibile.", exc)
        return _jsonify_redacted(esito)
    except Exception as exc:
        current_app.logger.exception("Errore approvazione procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Approvazione non disponibile."}), 200


@api_v1_react.post("/procedure-completion/cards/<card_id>/publish")
@_richiedi_auth
def procedure_completion_publish(card_id: str):
    try:
        from pct.procedure_completion.service import ProcedureCompletionError

        service, context, errore = _procedure_completion_guard("procedure_completion.pubblica")
        if errore is not None:
            return errore
        try:
            esito = service.publish_completion(card_id, context)
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Pubblicazione non disponibile.", exc)
        return _jsonify_redacted(esito)
    except Exception as exc:
        current_app.logger.exception("Errore pubblicazione procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Pubblicazione non disponibile."}), 200


@api_v1_react.get("/procedure-completion/gaps")
@_richiedi_auth
def procedure_completion_gaps():
    try:
        from pct.procedure_completion.service import ProcedureCompletionError

        service, context, errore = _procedure_completion_guard("procedure_completion.leggi")
        if errore is not None:
            return errore
        try:
            gaps = service.list_gaps(
                severita=str(request.args.get("severita") or ""),
                card_id=str(request.args.get("card_id") or ""),
                context=context,
            )
        except ProcedureCompletionError as exc:
            return _procedure_completion_public_error("Elenco dati mancanti non disponibile.", exc)
        return _jsonify_redacted({"ok": True, "gaps": gaps, "totale": len(gaps)})
    except Exception as exc:
        current_app.logger.exception("Errore gap queue procedure completion: %s", exc)
        return jsonify({"ok": False, "errore": "Gap queue non disponibile."}), 200


@api_v1_react.get("/giurisprudenza")
@_richiedi_auth
def giurisprudenza_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_giurisprudenza_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_giurisprudenza_payload(
                get_giurisprudenza=get_giurisprudenza,
                query=dict(request.args),
                config=dict(current_app.config),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Giurisprudenza React bridge: %s", exc)
        return jsonify(
            build_react_giurisprudenza_error_payload(
                "Archivio giurisprudenza non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/giurisprudenza/nuova")
@_richiedi_auth
def giurisprudenza_nuova_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_giurisprudenza_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_giurisprudenza_new_payload(
                get_giurisprudenza=get_giurisprudenza,
                query=dict(request.args),
                config=dict(current_app.config),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Giurisprudenza nuova React bridge: %s", exc)
        return jsonify(
            build_react_giurisprudenza_error_payload(
                "Inserimento giurisprudenza non disponibile nell'ambiente corrente."
            )
        ), 200


@api_v1_react.post("/giurisprudenza/nuova")
@_richiedi_auth
def giurisprudenza_nuova_salva():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "errors": {"sessione": "Sessione utente richiesta."}, "warnings": []}), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = create_react_giurisprudenza_record(
        get_giurisprudenza=get_giurisprudenza,
        payload=payload or {},
    )
    if result.get("ok") and isinstance(result.get("record"), dict):
        record_id = str(result["record"].get("id") or "")
        _audit_event(
            "giurisprudenza.scheda.salva",
            "giurisprudenza",
            record_id,
            "Scheda giurisprudenza salvata da superficie React.",
        )
    return _jsonify_redacted(result), status


_LEGAL_PAYLOAD_CACHE = ReactPayloadTTLCache(
    ttl_seconds=float(os.getenv("IUSENTRA_REACT_LEGAL_PAYLOAD_TTL_SECONDS") or 120),
    max_entries=8,
)


def _legal_intelligence_cache_key(page: str) -> tuple | None:
    # Cache solo per le viste senza parametri: con una query la ricerca deve
    # restare live. Il payload dipende dal tenant (conteggi studio), quindi il
    # tenant entra nella chiave per non condividere dati tra studi.
    if request.args or not _LEGAL_PAYLOAD_CACHE.enabled:
        return None
    tenant = getattr(g, "tenant", None)
    tenant_slug = str(
        getattr(tenant, "slug", "") or getattr(g, "tenant_context_slug", "") or ""
    ).strip().lower()
    return (page, tenant_slug)


def _legal_intelligence_ui_payload(page: str, legacy_contract: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(
            build_react_legal_intelligence_error_payload(
                "Sessione utente richiesta.",
                legacy_contract=legacy_contract,
            )
        ), 403
    cache_key = _legal_intelligence_cache_key(page)
    if cache_key is not None:
        cached = _LEGAL_PAYLOAD_CACHE.get(cache_key)
        if cached is not None:
            return current_app.response_class(cached, mimetype="application/json")
    try:
        response = redacted_json_response(
            build_react_legal_intelligence_payload(
                get_legal_intelligence=get_legal_intelligence,
                get_legal_update_pipeline=get_legal_update_pipeline,
                get_fascicoli=get_fascicoli,
                get_clienti=get_clienti,
                get_agenda=get_agenda,
                get_scadenziario=get_scadenziario,
                page=page,
                query=dict(request.args),
                config=dict(current_app.config),
            )
        )
        if cache_key is not None and response.status_code == 200:
            _LEGAL_PAYLOAD_CACHE.set(cache_key, response.get_data())
        return response
    except Exception as exc:
        current_app.logger.exception("Errore Legal Intelligence React bridge: %s", exc)
        return jsonify(
            build_react_legal_intelligence_error_payload(
                "Legal Intelligence non disponibile dal runtime corrente.",
                legacy_contract=legacy_contract,
            )
        ), 200


@api_v1_react.get("/legal-intelligence")
@_richiedi_auth
def legal_intelligence_page():
    # Alias storico (v2.242.0+): la home canonica è /ricerca-legale.
    return _legal_intelligence_ui_payload(
        "dashboard",
        "artifacts/react-migration/legacy-contracts/legal-intelligence.json",
    )


@api_v1_react.get("/legal-intelligence/news")
@_richiedi_auth
def legal_intelligence_news_page():
    return _legal_intelligence_ui_payload(
        "news",
        "artifacts/react-migration/legacy-contracts/legal-intelligence__news.json",
    )


@api_v1_react.get("/legal-intelligence/mediazione")
@_richiedi_auth
def legal_intelligence_mediazione_page():
    return _legal_intelligence_ui_payload(
        "mediazione",
        "artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json",
    )


@api_v1_react.get("/ricerca-legale")
@_richiedi_auth
def ricerca_legale_page():
    # Path canonico: la pagina principale deve essere la ricerca operativa.
    return _legal_intelligence_ui_payload(
        "ricerca-legale",
        "artifacts/react-migration/legacy-contracts/ricerca-legale.json",
    )


@api_v1_react.get("/ricerca-legale/news")
@_richiedi_auth
def ricerca_legale_news_page():
    return _legal_intelligence_ui_payload(
        "news",
        "artifacts/react-migration/legacy-contracts/legal-intelligence__news.json",
    )


@api_v1_react.get("/ricerca-legale/mediazione")
@_richiedi_auth
def ricerca_legale_mediazione_page():
    return _legal_intelligence_ui_payload(
        "mediazione",
        "artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json",
    )


@api_v1_react.get("/ricerca-legale/ricerca")
@_richiedi_auth
def ricerca_legale_search_page():
    return _legal_intelligence_ui_payload(
        "ricerca-legale",
        "artifacts/react-migration/legacy-contracts/ricerca-legale.json",
    )


def _preventivi_ui_payload(route: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_preventivi_error_payload("Sessione utente richiesta.", route=route)), 403
    if not _puo_leggere_preventivi():
        return jsonify(build_react_preventivi_error_payload("Permesso fatturazione.leggi richiesto.", route=route)), 403
    try:
        return jsonify(
            build_react_preventivi_payload(
                get_preventivi=get_preventivi_readonly,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                current_user=utente,
                query=dict(request.args),
                route=route,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Preventivi React bridge: %s", exc)
        return jsonify(
            build_react_preventivi_error_payload(
                "Preventivi e conferimenti non disponibili dal runtime corrente.",
                route=route,
            )
        ), 200


@api_v1_react.get("/preventivi")
@_richiedi_auth
def preventivi_page():
    return _preventivi_ui_payload("/preventivi")


@api_v1_react.get("/preventivi/nuovo")
@_richiedi_auth
def preventivi_nuovo_page():
    return _preventivi_ui_payload("/preventivi/nuovo")


@api_v1_react.post("/preventivi/nuovo")
@_richiedi_auth
def preventivi_nuovo_crea():
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = create_react_preventivo(
        get_preventivi=get_preventivi,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        current_user=utente,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.get("/preventivi/conferimento/nuovo")
@_richiedi_auth
def preventivi_conferimento_nuovo_page():
    return _preventivi_ui_payload("/preventivi/conferimento/nuovo")


@api_v1_react.post("/preventivi/conferimento/nuovo")
@_richiedi_auth
def preventivi_conferimento_nuovo_crea():
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = create_react_conferimento(
        get_preventivi=get_preventivi,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        get_utenti=get_utenti,
        current_user=utente,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return _jsonify_redacted(result), status


@api_v1_react.get("/preventivi/<id_preventivo>")
@_richiedi_auth
def preventivi_detail_page(id_preventivo: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.leggi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    result, status = build_react_preventivo_detail_payload(
        get_preventivi=get_preventivi_readonly,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        id_preventivo=id_preventivo,
    )
    return jsonify(result), status


@api_v1_react.get("/preventivi/conferimento/<id_conferimento>")
@_richiedi_auth
def preventivi_conferimento_detail_page(id_conferimento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_leggere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.leggi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    result, status = build_react_conferimento_detail_payload(
        get_preventivi=get_preventivi_readonly,
        get_clienti=get_clienti,
        get_fascicoli=get_fascicoli,
        id_conferimento=id_conferimento,
    )
    return jsonify(result), status


@api_v1_react.post("/preventivi/<id_preventivo>/stato")
@_richiedi_auth
def preventivi_aggiorna_stato(id_preventivo: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_preventivo_status(
        get_preventivi=get_preventivi,
        get_utenti=get_utenti,
        current_user=utente,
        id_preventivo=id_preventivo,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.post("/preventivi/conferimento/<id_conferimento>/stato")
@_richiedi_auth
def preventivi_conferimento_aggiorna_stato(id_conferimento: str):
    utente = g.get("utente_corrente")
    if not utente or not _puo_scrivere_preventivi():
        return jsonify({
            "ok": False,
            "message": "Permesso fatturazione.scrivi richiesto.",
            "errors": {"permission": "Operazione non autorizzata."},
            "item": None,
        }), 403
    payload, error_response = _request_json_object()
    if error_response is not None:
        return error_response
    result, status = update_react_conferimento_status(
        get_preventivi=get_preventivi,
        get_utenti=get_utenti,
        current_user=utente,
        id_conferimento=id_conferimento,
        payload=payload,
        ip_address=request.remote_addr or "",
    )
    return jsonify(result), status


@api_v1_react.get("/preventivi/wizard")
@_richiedi_auth
def preventivi_wizard_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_preventivo_wizard_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_preventivo_wizard_payload(
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                get_normative_tables=get_normative_tables,
                query=dict(request.args),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore wizard preventivi React bridge: %s", exc)
        return jsonify(
            build_react_preventivo_wizard_error_payload(
                "Preventivo guidato non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/preventivi/wizard/bootstrap")
@_richiedi_auth
def preventivi_wizard_bootstrap_page():
    return preventivi_wizard_page()


@api_v1_react.post("/preventivi/wizard/calculate")
@_richiedi_auth
def preventivi_wizard_calculate_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_preventivo_wizard_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(build_react_preventivo_wizard_calculation_payload(_request_payload()))
    except Exception as exc:
        current_app.logger.exception("Errore calcolo wizard preventivi React bridge: %s", exc)
        return jsonify(
            {
                "ok": False,
                "warnings": [
                    {
                        "code": "preventivo_wizard_calcolo_errore",
                        "message": "Calcolo non disponibile dal runtime corrente.",
                    }
                ],
            }
        ), 200


def _wizard_codice_oggetto(payload: dict[str, Any], profile: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, str] | None]:
    profile = profile or {}
    explicit = str(payload.get("codice_oggetto_pst") or "").strip()
    profile_code = str(profile.get("codice_oggetto_pst") or "").strip()
    oggetto = str(payload.get("oggetto") or "").strip()
    candidate = explicit or profile_code or (oggetto if looks_like_codice_oggetto_pst(oggetto) else "")
    resolved = resolve_codice_oggetto_pst_payload(candidate)
    return resolved, codice_oggetto_pst_entry(resolved["codice_oggetto_pst"])


def _wizard_react_form_payload(payload: dict[str, Any], calculation: dict[str, Any] | None = None) -> dict[str, Any]:
    calculation = calculation or {}
    profile = calculation.get("profile") if isinstance(calculation.get("profile"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else calculation.get("rows")
    rows = rows if isinstance(rows, list) else []
    taxable_rows = [
        row for row in rows
        if isinstance(row, dict)
        and str(row.get("fiscale") or "imponibile").strip() != "anticipazione_art15"
    ]
    economic = calculation.get("economic") if isinstance(calculation.get("economic"), dict) else {}
    clause = payload.get("clausola") if isinstance(payload.get("clausola"), dict) else {}
    final = payload.get("opzioni_finali") if isinstance(payload.get("opzioni_finali"), dict) else {}
    preventivo_accettato = bool(final.get("preventivo_accettato"))
    conferimento_richiesto = bool(final.get("genera_conferimento"))
    conferimento_autorizzato = bool(preventivo_accettato and conferimento_richiesto)
    quick = payload.get("cliente_rapido") if isinstance(payload.get("cliente_rapido"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    classifications = payload.get("classificazioni_tassonomiche")
    sources = payload.get("fonti_tassonomia")
    if not isinstance(classifications, list):
        classifications = []
    if not isinstance(sources, list):
        sources = profile.get("tassonomia_sources") if isinstance(profile.get("tassonomia_sources"), list) else []
    codice_payload, codice_entry = _wizard_codice_oggetto(payload, profile)
    oggetto_form = str(payload.get("oggetto") or "").strip()
    if codice_entry and oggetto_form == codice_payload["codice_oggetto_pst"]:
        oggetto_form = str(codice_entry.get("descrizione", "") or "").strip() or oggetto_form
    return {
        **payload,
        "id_cliente": str(payload.get("id_cliente") or payload.get("customerId") or "").strip(),
        "id_fascicolo": str(payload.get("id_fascicolo") or payload.get("caseId") or "").strip(),
        "cliente_rapido_attivo": "1" if bool(payload.get("cliente_rapido_attivo")) else "",
        "cliente_rapido_tipo": str(quick.get("tipo") or "PERSONA_FISICA").strip(),
        "cliente_rapido_nome": str(quick.get("nome") or "").strip(),
        "cliente_rapido_cognome": str(quick.get("cognome") or "").strip(),
        "cliente_rapido_ragione_sociale": str(quick.get("ragione_sociale") or "").strip(),
        "cliente_rapido_codice_fiscale": str(quick.get("codice_fiscale") or "").strip(),
        "cliente_rapido_codice_fiscale_pg": str(quick.get("codice_fiscale") or "").strip(),
        "cliente_rapido_partita_iva": str(quick.get("partita_iva") or "").strip(),
        "oggetto": oggetto_form,
        "data_emissione": str(payload.get("data_emissione") or date.today().isoformat()).strip(),
        "data_scadenza": str(payload.get("data_scadenza") or "").strip(),
        "id_pratica": str(payload.get("id_pratica") or profile.get("id") or "").strip(),
        "area_pratica": str(payload.get("area_pratica") or profile.get("area") or "").strip(),
        "area_tassonomica": str(payload.get("area_tassonomica") or profile.get("area_tassonomica") or "").strip(),
        "macro_area_tassonomica": str(payload.get("macro_area_tassonomica") or profile.get("macro_area_tassonomica") or "").strip(),
        "sottobranca_tassonomica": str(payload.get("sottobranca_tassonomica") or profile.get("sottobranca_tassonomica") or "").strip(),
        "tassonomia_codice": str(payload.get("tassonomia_codice") or profile.get("tassonomia_codice") or "").strip(),
        "procedura_operativa_codice": str(payload.get("procedura_operativa_codice") or profile.get("procedura_operativa_codice") or "").strip(),
        "procedura_operativa_nome": str(payload.get("procedura_operativa_nome") or profile.get("procedura_operativa_nome") or "").strip(),
        "subbranch_operativa_codice": str(payload.get("subbranch_operativa_codice") or profile.get("subbranch_operativa_codice") or "").strip(),
        "workflow_operativo_codice": str(payload.get("workflow_operativo_codice") or profile.get("workflow_operativo_codice") or "").strip(),
        "copertura_operativa": str(payload.get("copertura_operativa") or profile.get("copertura_operativa") or "").strip(),
        "canale_operativo": str(payload.get("canale_operativo") or profile.get("canale_operativo") or "").strip(),
        "registro_operativo": str(payload.get("registro_operativo") or profile.get("registro_operativo") or "").strip(),
        "tipo_compenso": str(payload.get("tipo_compenso") or profile.get("tipo_compenso_default") or "").strip(),
        "tipo_procedimento": str(payload.get("tipo_procedimento") or profile.get("label") or "").strip(),
        "codice_oggetto_pst": codice_payload["codice_oggetto_pst"],
        "fonte_codice_oggetto": str(payload.get("fonte_codice_oggetto") or codice_payload["fonte_codice_oggetto"]).strip(),
        "file_fonte_codice_oggetto": str(payload.get("file_fonte_codice_oggetto") or codice_payload["file_fonte_codice_oggetto"]).strip(),
        "grado_sede": str(payload.get("grado") or profile.get("grado_default") or "").strip(),
        "regola_tariffaria": str(payload.get("regola_tariffaria") or profile.get("regola_tariffaria_default") or "").strip(),
        "complessita": str(payload.get("complessita") or "media").strip(),
        "valore_controversia": str(payload.get("valore") or payload.get("valore_controversia") or "0").strip(),
        "tariffa_oraria": str(payload.get("tariffa_oraria") or "0").strip(),
        "ore_stimate": str(payload.get("ore_stimate") or "0").strip(),
        "anticipazioni_art15": str(payload.get("anticipazioni") or "0").strip(),
        "anticipazioni_art15_totali": str(economic.get("anticipazioni_art15") or payload.get("anticipazioni_art15_totali") or "0").strip(),
        "applica_cassa": "1" if bool(payload.get("applica_cpa", True)) else "0",
        "applica_iva": "1" if bool(payload.get("applica_iva", True)) else "0",
        "bonus_telematico": "1" if bool(payload.get("bonus_telematico")) else "0",
        "spese_generali": "1" if bool(payload.get("spese_generali", True)) else "0",
        "perc_spese_generali": str(payload.get("perc_spese_generali") or "15").strip(),
        "voce_descr": [str(row.get("descrizione") or "").strip() for row in taxable_rows],
        "voce_importo": [str(row.get("importo") or "0").strip() for row in taxable_rows],
        "voce_tipo": [str(row.get("tipo") or "Onorario").strip() for row in taxable_rows],
        "note": str(payload.get("note") or calculation.get("note") or "").strip(),
        "log_calcolo": str((calculation.get("audit") or {}).get("log_calcolo") or payload.get("log_calcolo") or "").strip(),
        "fonti_tassonomia_json": json.dumps(sources, ensure_ascii=False),
        "classificazioni_tassonomiche_json": json.dumps(classifications, ensure_ascii=False),
        "preventivo_accettato": "1" if preventivo_accettato else "",
        "genera_conferimento": "1" if conferimento_autorizzato else "",
        "apri_fascicolo_guidato": "1" if bool(final.get("apri_fascicolo_guidato") and conferimento_autorizzato) else "",
        "conferimento_richiesto_senza_accettazione": "1" if conferimento_richiesto and not preventivo_accettato else "",
        "informativa_art13_resa": "1" if bool(final.get("informativa_art13_resa", True)) else "",
        "clausola_adr_resa": "1" if bool(clause.get("attiva")) else "",
        "clausola_controversie_attiva": "1" if bool(clause.get("attiva")) else "",
        "clausola_controversie_modello": str(clause.get("modello") or default_clause_payload()["model"]).strip(),
        "clausola_controversie_testo": str(clause.get("testo") or "").strip(),
        "clausola_controversie_trattativa_individuale": "1" if bool(clause.get("trattativa_individuale")) else "",
        "clausola_controversie_fonte": str(clause.get("fonte") or "").strip(),
        "avvocato_referente": str(payload.get("avvocato_referente") or metadata.get("avvocato_referente") or "").strip(),
        "from_page": str(payload.get("from_page") or "wizard").strip(),
    }


@api_v1_react.post("/preventivi/wizard/create")
@_richiedi_auth
def preventivi_wizard_create_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify({"ok": False, "warnings": [_warning("auth", "Sessione utente richiesta.")]}), 403
    try:
        from pct.preventivi import TipoVoce, VocePreventivo
        from web.blueprints.preventivi import (
            _aggiungi_voce_compenso_a_tempo,
            _arricchisci_log_cliente_anagrafico,
            _campi_cliente_mancanti,
            _cliente_da_completare,
            _compenso_a_tempo_da_form,
            _contesto_log_wizard_da_form,
            _crea_cliente_rapido_da_wizard,
            _flag_from_form,
            _parse_intero,
            _parse_numero,
            _url_completa_cliente,
            _url_onboarding_fascicolo,
        )

        payload = _request_payload()
        codice_oggetto = str(payload.get("codice_oggetto_pst") or "").strip()
        oggetto_candidate = str(payload.get("oggetto") or "").strip()
        codice_oggetto_non_valido = (
            bool(codice_oggetto) and not codice_oggetto_pst_entry(codice_oggetto)
        ) or (
            not codice_oggetto
            and looks_like_codice_oggetto_pst(oggetto_candidate)
            and not codice_oggetto_pst_entry(oggetto_candidate)
        )
        if codice_oggetto_non_valido:
            return jsonify(
                {
                    "ok": False,
                    "warnings": [
                        _warning("codice_oggetto_pst_non_valido", "Seleziona il codice oggetto dal catalogo ufficiale PST.")
                    ],
                }
            ), 200
        calculation = build_react_preventivo_wizard_calculation_payload(payload)
        if not calculation.get("ok"):
            return jsonify({"ok": False, "warnings": calculation.get("warnings") or []}), 200
        form_payload = _wizard_react_form_payload(payload, calculation)
        form = WizardPayloadForm(form_payload)
        gp = get_preventivi()
        id_cliente = form.get("id_cliente", "").strip()
        messages: list[dict[str, str]] = []
        response_warnings: list[dict[str, str]] = [
            warning
            for warning in (calculation.get("warnings") or [])
            if isinstance(warning, dict)
        ]
        if _flag_from_form(form, "conferimento_richiesto_senza_accettazione"):
            response_warnings.append(
                _warning(
                    "conferimento_dopo_accettazione",
                    "Il conferimento incarico non viene generato finché il preventivo non risulta accettato dal cliente.",
                )
            )
        if not id_cliente:
            if _flag_from_form(form, "cliente_rapido_attivo"):
                id_cliente, msg_cliente = _crea_cliente_rapido_da_wizard(form)
                form_payload["id_cliente"] = id_cliente
                form = WizardPayloadForm(form_payload)
                messages.append({"tone": "success", "message": msg_cliente})
            else:
                return jsonify(
                    {
                        "ok": False,
                        "warnings": [
                            _warning("cliente_richiesto", "Seleziona un cliente oppure inseriscine uno rapido.")
                        ],
                    }
                ), 200
        oggetto = form.get("oggetto", "").strip()
        if not oggetto:
            return jsonify({"ok": False, "warnings": [_warning("oggetto_richiesto", "Inserisci l'oggetto del preventivo.")]}), 200

        voci = []
        for desc, amount, kind in zip(form.getlist("voce_descr[]"), form.getlist("voce_importo[]"), form.getlist("voce_tipo[]")):
            desc = desc.strip()
            if not desc:
                continue
            try:
                tipo_voce = TipoVoce(kind) if kind else TipoVoce.ONORARIO
            except ValueError:
                tipo_voce = TipoVoce.ONORARIO
            try:
                voci.append(
                    VocePreventivo(
                        descrizione=desc,
                        importo=_parse_numero(amount, 0.0),
                        tipo=tipo_voce,
                    )
                )
            except (TypeError, ValueError):
                continue
        tipo_compenso, compenso_a_tempo = _compenso_a_tempo_da_form(form)
        if compenso_a_tempo.get("errors"):
            return jsonify({"ok": False, "warnings": [_warning("compenso_a_tempo", " ".join(compenso_a_tempo["errors"]))]}), 200
        _aggiungi_voce_compenso_a_tempo(voci, compenso_a_tempo)
        if not voci:
            return jsonify({"ok": False, "warnings": [_warning("voci_richieste", "Aggiungi almeno una voce al preventivo.")]}), 200
        motore_rows = [
            row for row in (calculation.get("rows") or [])
            if isinstance(row, dict) and str(row.get("source") or "") == "motore"
        ]
        if motore_rows and sum(float(getattr(voce, "importo", 0.0) or 0.0) for voce in voci) <= 0:
            return jsonify(
                {
                    "ok": False,
                    "warnings": [
                        _warning(
                            "calcolo_tabellare_zero",
                            "La regola tariffaria selezionata richiede un compenso tabellare positivo: il preventivo non viene creato a zero. Usa una voce manuale solo se è dichiarata come non tabellare.",
                        )
                    ],
                }
            ), 200

        cfg = current_app.config
        log_calcolo = _contesto_log_wizard_da_form(form, compenso_a_tempo)
        log_calcolo = _arricchisci_log_cliente_anagrafico(log_calcolo, get_clienti().get(id_cliente))
        try:
            fonti_tassonomia = json.loads(form.get("fonti_tassonomia_json", "") or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            fonti_tassonomia = []
        try:
            classificazioni = json.loads(form.get("classificazioni_tassonomiche_json", "") or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            classificazioni = []
        p = gp.crea_preventivo(
            id_cliente=id_cliente,
            oggetto=oggetto,
            voci=voci,
            creato_da=getattr(utente, "username", ""),
            id_fascicolo=form.get("id_fascicolo", "").strip() or None,
            data_emissione=form.get("data_emissione") or date.today().isoformat(),
            data_scadenza=form.get("data_scadenza", "").strip() or None,
            applica_cassa=_flag_from_form(form, "applica_cassa", default=True),
            applica_iva=_flag_from_form(form, "applica_iva", default=True),
            anticipazioni_art15=_parse_numero(form.get("anticipazioni_art15_totali"), 0.0),
            note=form.get("note", "").strip(),
            id_pratica=form.get("id_pratica", "").strip(),
            area_pratica=form.get("area_pratica", "").strip(),
            area_tassonomica=form.get("area_tassonomica", "").strip(),
            macro_area_tassonomica=form.get("macro_area_tassonomica", "").strip(),
            sottobranca_tassonomica=form.get("sottobranca_tassonomica", "").strip(),
            tassonomia_codice=form.get("tassonomia_codice", "").strip(),
            procedura_operativa_codice=form.get("procedura_operativa_codice", "").strip(),
            fonti_tassonomia=fonti_tassonomia if isinstance(fonti_tassonomia, list) else [],
            classificazioni_tassonomiche=classificazioni if isinstance(classificazioni, list) else [],
            tipo_compenso=tipo_compenso,
            tipo_procedimento=form.get("tipo_procedimento", "").strip(),
            codice_oggetto_pst=form.get("codice_oggetto_pst", "").strip(),
            fonte_codice_oggetto=form.get("fonte_codice_oggetto", "").strip(),
            file_fonte_codice_oggetto=form.get("file_fonte_codice_oggetto", "").strip(),
            valore_controversia=_parse_numero(form.get("valore_controversia"), 0.0),
            tariffa_oraria=_parse_numero(form.get("tariffa_oraria"), 0.0),
            ore_stimate=_parse_numero(form.get("ore_stimate"), 0.0),
            criterio_arrotondamento_orario=form.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
            minuti_stimati=_parse_intero(form.get("minuti_stimati"), 0),
            ore_fatturabili_calcolate=float(compenso_a_tempo.get("ore_fatturabili") or 0.0),
            compenso_orario_base=float(compenso_a_tempo.get("compenso_base") or 0.0),
            massimale_ore=_parse_numero(form.get("massimale_ore"), 0.0),
            soglia_preapprovazione_ore=_parse_numero(form.get("soglia_preapprovazione_ore"), 0.0),
            richiede_consenso_superamento_soglia=True,
            attivita_orarie_incluse=form.get("attivita_orarie_incluse", "").strip(),
            attivita_orarie_escluse=form.get("attivita_orarie_escluse", "").strip(),
            warning_compenso_orario=list(compenso_a_tempo.get("warnings") or []),
            complessita=form.get("complessita", "").strip(),
            log_calcolo=log_calcolo,
            studio_piva=cfg.get("STUDIO_PIVA", ""),
            studio_cf=cfg.get("STUDIO_CF", ""),
            studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
            clausola_controversie_attiva=_flag_from_form(form, "clausola_controversie_attiva"),
            clausola_controversie_modello=form.get("clausola_controversie_modello", "").strip(),
            clausola_controversie_testo=form.get("clausola_controversie_testo", "").strip(),
            clausola_controversie_trattativa_individuale=_flag_from_form(form, "clausola_controversie_trattativa_individuale"),
            clausola_controversie_fonte=form.get("clausola_controversie_fonte", "").strip(),
        )

        conferimento_id = ""
        fascicolo_id = ""
        redirect_url = detail_url_for_preventivo(p.id)
        if _flag_from_form(form, "preventivo_accettato"):
            p, _ = gp.registra_accettazione_preventivo(
                p.id,
                workflow_channel="STUDIO",
                via="STUDIO",
                ip=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", ""),
                creato_da=getattr(utente, "username", ""),
                auto_crea_conferimento=False,
            )
            messages.append({"tone": "success", "message": "Accettazione cliente registrata prima del conferimento."})
        if _flag_from_form(form, "genera_conferimento"):
            cliente_corrente = get_clienti().get(id_cliente)
            if _cliente_da_completare(cliente_corrente):
                missing = ", ".join(_campi_cliente_mancanti(cliente_corrente))
                return jsonify(
                    {
                        "ok": True,
                        "id_preventivo": p.id,
                        "redirect_url": _url_completa_cliente(
                            id_cliente,
                            next_url=url_for(
                                "preventivi.nuovo_conferimento",
                                id_cliente=id_cliente,
                                id_preventivo=p.id,
                                from_page="preventivo",
                            ),
                        ),
                        "warnings": response_warnings + [
                            _warning("cliente_da_completare", f"Preventivo creato. Completa l'anagrafica cliente prima del conferimento: {missing}.")
                        ],
                        "messages": messages,
                    }
                ), 200
            avvocato = form.get("avvocato_referente", "").strip() or cfg.get("STUDIO_NOME", "Studio Legale")
            conferimento = gp.crea_conferimento(
                id_cliente=id_cliente,
                oggetto=oggetto,
                avvocato_referente=avvocato,
                creato_da=getattr(utente, "username", ""),
                id_preventivo=p.id,
                id_fascicolo=form.get("id_fascicolo", "").strip() or None,
                compenso_pattuito=_parse_numero(form.get("compenso_pattuito"), p.totale),
                id_pratica=form.get("id_pratica", "").strip(),
                area_pratica=form.get("area_pratica", "").strip(),
                area_tassonomica=form.get("area_tassonomica", "").strip(),
                macro_area_tassonomica=form.get("macro_area_tassonomica", "").strip(),
                sottobranca_tassonomica=form.get("sottobranca_tassonomica", "").strip(),
                tassonomia_codice=form.get("tassonomia_codice", "").strip(),
                procedura_operativa_codice=form.get("procedura_operativa_codice", "").strip(),
                fonti_tassonomia=fonti_tassonomia if isinstance(fonti_tassonomia, list) else [],
                classificazioni_tassonomiche=classificazioni if isinstance(classificazioni, list) else [],
                tipo_compenso=tipo_compenso,
                tipo_procedimento=form.get("tipo_procedimento", "").strip(),
                codice_oggetto_pst=form.get("codice_oggetto_pst", "").strip(),
                fonte_codice_oggetto=form.get("fonte_codice_oggetto", "").strip(),
                file_fonte_codice_oggetto=form.get("file_fonte_codice_oggetto", "").strip(),
                tariffa_oraria=_parse_numero(form.get("tariffa_oraria"), 0.0),
                criterio_arrotondamento_orario=form.get("criterio_arrotondamento_orario", "").strip() or "ora_frazione_oltre_30",
                massimale_ore=_parse_numero(form.get("massimale_ore"), 0.0),
                soglia_preapprovazione_ore=_parse_numero(form.get("soglia_preapprovazione_ore"), 0.0),
                richiede_consenso_superamento_soglia=True,
                attivita_orarie_incluse=form.get("attivita_orarie_incluse", "").strip(),
                attivita_orarie_escluse=form.get("attivita_orarie_escluse", "").strip(),
                warning_compenso_orario=list(compenso_a_tempo.get("warnings") or []),
                informativa_art13_resa=_flag_from_form(form, "informativa_art13_resa"),
                clausola_adr_resa=_flag_from_form(form, "clausola_adr_resa"),
                clausola_controversie_attiva=_flag_from_form(form, "clausola_controversie_attiva"),
                clausola_controversie_modello=form.get("clausola_controversie_modello", "").strip(),
                clausola_controversie_testo=form.get("clausola_controversie_testo", "").strip(),
                clausola_controversie_trattativa_individuale=_flag_from_form(form, "clausola_controversie_trattativa_individuale"),
                studio_piva=cfg.get("STUDIO_PIVA", ""),
                studio_cf=cfg.get("STUDIO_CF", ""),
                studio_indirizzo=cfg.get("STUDIO_INDIRIZZO", ""),
            )
            gp.aggiorna_preventivo(p.id, stato=StatoPreventivo.CONVERTITO)
            conferimento_id = getattr(conferimento, "id", "")
            if _flag_from_form(form, "apri_fascicolo_guidato") and not p.id_fascicolo:
                redirect_url = _url_onboarding_fascicolo(
                    id_cliente,
                    id_preventivo=p.id,
                    id_conferimento=conferimento_id,
                    from_page=form.get("from_page", "").strip() or "wizard",
                )
        return jsonify(
            {
                "ok": True,
                "id_preventivo": p.id,
                "id_conferimento": conferimento_id,
                "id_fascicolo": fascicolo_id,
                "detail_url": detail_url_for_preventivo(p.id),
                "redirect_url": redirect_url,
                "messages": messages + [{"tone": "success", "message": f"Preventivo {p.numero} creato."}],
                "warnings": response_warnings,
            }
        ), 200
    except Exception as exc:
        current_app.logger.exception("Errore creazione wizard preventivi React bridge: %s", exc)
        return jsonify(
            {
                "ok": False,
                "warnings": [
                    {
                        "code": "preventivo_wizard_creazione_errore",
                        "message": "Creazione non disponibile dal runtime corrente.",
                    }
                ],
            }
        ), 200


@api_v1_react.get("/agenda")
@_richiedi_auth
def agenda():
    email_db_path = Path(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))
    payload = build_react_agenda_payload(
        get_agenda,
        get_scadenziario,
        get_fascicoli,
        from_value=request.args.get("from", ""),
        to_value=request.args.get("to", ""),
        selected_id=request.args.get("selected_id", "").strip(),
        pec_audit_db=str(email_db_path.parent / "pec_audit.sqlite"),
        tenant_id=_tenant_runtime_label(),
    )
    return jsonify(payload)


def _email_source_preview_cache_dir() -> Path:
    anchor = Path(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json")).resolve()
    root = anchor.parent / ".preview-cache" / "pec-source"
    root.mkdir(parents=True, exist_ok=True)
    return root


_EMAIL_SOURCE_PREVIEW_CACHE_VERSION = "v3"
_EMAIL_SOURCE_PREVIEW_CACHE_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
_EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRIES = 256
_EMAIL_SOURCE_PREVIEW_CACHE_MAX_BYTES = 384 * 1024 * 1024
_EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES = 64 * 1024 * 1024
_EMAIL_SOURCE_PREVIEW_CACHE_MAX_METADATA_BYTES = 64 * 1024
_EMAIL_SOURCE_PREVIEW_CACHE_CLEANUP_INTERVAL_SECONDS = 300
_EMAIL_SOURCE_PREVIEW_CACHE_LAST_CLEANUP: dict[str, float] = {}


def _email_source_cache_key(
    *,
    tenant_id: str,
    message_id: str,
    requested_name: str,
    source_sha256: str,
) -> str:
    basis = "\n".join(
        [
            str(tenant_id or "default").strip(),
            str(message_id or "").strip(),
            str(requested_name or "").strip().casefold(),
            str(source_sha256 or "").strip().casefold(),
            _EMAIL_SOURCE_PREVIEW_CACHE_VERSION,
        ]
    )
    return hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()


def _safe_cache_download_name(name: str) -> str:
    clean = Path(str(name or "anteprima").replace("\\", "/")).name.strip().strip(".") or "anteprima"
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", clean)[:180] or "anteprima"


def _read_email_source_preview_cache(cache_key: str) -> tuple[bytes, str, str, str] | None:
    cache_dir = _email_source_preview_cache_dir()
    meta_path = cache_dir / f"{cache_key}.json"
    data_path = cache_dir / f"{cache_key}.bin"
    if not meta_path.is_file() or not data_path.is_file():
        return None
    try:
        if (
            meta_path.stat().st_size > _EMAIL_SOURCE_PREVIEW_CACHE_MAX_METADATA_BYTES
            or data_path.stat().st_size > _EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES
        ):
            for oversized_path in (meta_path, data_path):
                oversized_path.unlink(missing_ok=True)
            return None
        with meta_path.open("r", encoding="utf-8") as meta_file:
            meta_raw = meta_file.read(_EMAIL_SOURCE_PREVIEW_CACHE_MAX_METADATA_BYTES + 1)
        if len(meta_raw.encode("utf-8")) > _EMAIL_SOURCE_PREVIEW_CACHE_MAX_METADATA_BYTES:
            return None
        meta = json.loads(meta_raw)
        mimetype = str(meta.get("mimetype") or "").strip()
        download_name = _safe_cache_download_name(str(meta.get("download_name") or "anteprima"))
        original_name = _safe_cache_download_name(str(meta.get("original_name") or download_name))
        if not mimetype:
            return None
        with data_path.open("rb") as data_file:
            cached_data = data_file.read(_EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES + 1)
        if len(cached_data) > _EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES:
            for oversized_path in (meta_path, data_path):
                oversized_path.unlink(missing_ok=True)
            return None
        return cached_data, mimetype, download_name, original_name
    except (OSError, json.JSONDecodeError):
        return None


def _cleanup_email_source_preview_cache(cache_dir: Path, *, force: bool = False) -> None:
    """Mantiene la cache tenant-aware entro limiti conservativi.

    La scansione avviene soltanto dopo una scrittura ed è ulteriormente
    limitata nel tempo: nessun GET a cache calda paga una pulizia completa.
    """

    cache_key = str(cache_dir.resolve())
    now_monotonic = time.monotonic()
    if not force:
        last_cleanup = _EMAIL_SOURCE_PREVIEW_CACHE_LAST_CLEANUP.get(cache_key, 0.0)
        if now_monotonic - last_cleanup < _EMAIL_SOURCE_PREVIEW_CACHE_CLEANUP_INTERVAL_SECONDS:
            return
    _EMAIL_SOURCE_PREVIEW_CACHE_LAST_CLEANUP[cache_key] = now_monotonic
    cutoff = time.time() - _EMAIL_SOURCE_PREVIEW_CACHE_MAX_AGE_SECONDS
    entries: list[tuple[float, int, Path, Path, bool]] = []
    known_data_paths: set[Path] = set()
    try:
        meta_paths = list(cache_dir.glob("*.json"))
    except OSError:
        return
    for meta_path in meta_paths:
        data_path = cache_dir / f"{meta_path.stem}.bin"
        known_data_paths.add(data_path)
        try:
            meta_stat = meta_path.stat()
            data_stat = data_path.stat()
        except OSError:
            for orphan in (meta_path, data_path):
                try:
                    orphan.unlink(missing_ok=True)
                except OSError:
                    pass
            continue
        newest_mtime = max(meta_stat.st_mtime, data_stat.st_mtime)
        if newest_mtime < cutoff:
            for stale_path in (meta_path, data_path):
                try:
                    stale_path.unlink(missing_ok=True)
                except OSError:
                    pass
            continue
        entries.append(
            (
                newest_mtime,
                int(meta_stat.st_size + data_stat.st_size),
                meta_path,
                data_path,
                (
                    data_stat.st_size <= _EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES
                    and meta_stat.st_size <= _EMAIL_SOURCE_PREVIEW_CACHE_MAX_METADATA_BYTES
                ),
            )
        )

    try:
        orphan_data_paths = [path for path in cache_dir.glob("*.bin") if path not in known_data_paths]
    except OSError:
        orphan_data_paths = []
    for orphan in orphan_data_paths:
        try:
            orphan.unlink(missing_ok=True)
        except OSError:
            pass

    retained_bytes = 0
    for index, (_mtime, entry_size, meta_path, data_path, within_entry_budget) in enumerate(
        sorted(entries, key=lambda item: item[0], reverse=True)
    ):
        keep = (
            index < _EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRIES
            and within_entry_budget
            and retained_bytes + entry_size <= _EMAIL_SOURCE_PREVIEW_CACHE_MAX_BYTES
        )
        if keep:
            retained_bytes += entry_size
            continue
        for stale_path in (meta_path, data_path):
            try:
                stale_path.unlink(missing_ok=True)
            except OSError:
                pass


def _write_email_source_preview_cache(
    cache_key: str,
    *,
    data: bytes,
    mimetype: str,
    download_name: str,
    original_name: str,
) -> None:
    if len(data) > _EMAIL_SOURCE_PREVIEW_CACHE_MAX_ENTRY_BYTES:
        return
    cache_dir = _email_source_preview_cache_dir()
    data_path = cache_dir / f"{cache_key}.bin"
    meta_path = cache_dir / f"{cache_key}.json"
    write_token = secrets.token_hex(8)
    tmp_data = cache_dir / f".{cache_key}.{write_token}.bin.tmp"
    tmp_meta = cache_dir / f".{cache_key}.{write_token}.json.tmp"
    try:
        tmp_data.write_bytes(data)
        tmp_meta.write_text(
            json.dumps(
                {
                    "mimetype": str(mimetype or "application/octet-stream"),
                    "download_name": _safe_cache_download_name(download_name),
                    "original_name": _safe_cache_download_name(original_name),
                    "generated_at": datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp_data, data_path)
        os.replace(tmp_meta, meta_path)
    finally:
        for temporary_path in (tmp_data, tmp_meta):
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    _cleanup_email_source_preview_cache(cache_dir)


def _source_pdf_viewer_requested() -> bool:
    return str(request.args.get("viewer") or "").strip().casefold() in {"mobile", "pages", "reader"}


_PEC_SOURCE_READ_RETRY_DELAYS = (0.0, 0.12, 0.25, 0.5, 1.0)


def _sqlite_busy_error(exc: BaseException) -> bool:
    message = str(exc or "").casefold()
    return (
        "database is locked" in message
        or "database table is locked" in message
        or "database is busy" in message
    )


def _pec_audit_db_path_for_request() -> Path:
    paths = getattr(g, "data_paths", {}) or {}
    explicit_path = str(paths.get("PEC_AUDIT_DB") or "").strip()
    if explicit_path:
        return Path(explicit_path).resolve()
    email_db = Path(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json")).resolve()
    return email_db.parent / "pec_audit.sqlite"


def _read_pec_source_message_row(message_id: str, *, include_mime: bool) -> dict[str, bytes | int | str] | None:
    """Legge una riga PEC tenant-aware, separando metadati e BLOB MIME."""

    clean_message_id = str(message_id or "").strip()
    if not clean_message_id:
        return None
    db_path = _pec_audit_db_path_for_request()
    if not db_path.exists():
        return None
    tenant_id = _tenant_runtime_label()
    last_busy: sqlite3.OperationalError | None = None
    for delay in _PEC_SOURCE_READ_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            with sqlite3.connect(
                f"file:{db_path.as_posix()}?mode=ro",
                timeout=1.0,
                uri=True,
            ) as connection:
                connection.row_factory = sqlite3.Row
                try:
                    connection.execute("PRAGMA query_only=ON")
                    connection.execute("PRAGMA busy_timeout=1000")
                except sqlite3.Error:
                    pass
                columns = "original_mime" if include_mime else "mime_sha256, mime_size"
                row = connection.execute(
                    f"SELECT {columns} FROM pec_messages WHERE tenant_id=? AND id=?",
                    (tenant_id, clean_message_id),
                ).fetchone()
                if row is None:
                    return None
                if include_mime:
                    return {"original_mime": bytes(row["original_mime"] or b"")}
                return {
                    "mime_sha256": str(row["mime_sha256"] or ""),
                    "mime_size": int(row["mime_size"] or 0),
                }
        except sqlite3.OperationalError as exc:
            if not _sqlite_busy_error(exc):
                raise
            last_busy = exc
    if last_busy is not None:
        raise last_busy
    return None


def _read_pec_source_message_metadata(message_id: str) -> dict[str, int | str] | None:
    row = _read_pec_source_message_row(message_id, include_mime=False)
    return row if row is None else {"mime_sha256": str(row.get("mime_sha256") or ""), "mime_size": int(row.get("mime_size") or 0)}


def _read_pec_source_message_blob(message_id: str) -> bytes | None:
    row = _read_pec_source_message_row(message_id, include_mime=True)
    if row is None:
        return None
    return bytes(row.get("original_mime") or b"")


def _serve_email_source_preview(
    preview_data: bytes,
    preview_mimetype: str,
    preview_name: str,
    *,
    message_id: str,
    original_name: str,
):
    mime = str(preview_mimetype or "").split(";", 1)[0].strip().lower()
    if mime == "application/pdf" and _source_pdf_viewer_requested():
        download_url = url_for(
            "api_v1_react.email_source_attachment",
            message_id=message_id,
            name=original_name,
            download=1,
        )
        page_value = str(request.args.get("page") or "").strip()
        if page_value:
            try:
                page_number = int(page_value)
                png_payload = render_pdf_page_png(preview_data, page_number)
            except Exception as exc:
                current_app.logger.warning(
                    "Anteprima pagina fonte PEC non disponibile message_id=%s file=%s page=%s: %s",
                    message_id,
                    original_name,
                    page_value,
                    exc,
                )
                return preview_error_html(download_url)
            response = send_file(
                io.BytesIO(png_payload),
                mimetype="image/png",
                as_attachment=False,
                download_name=f"{Path(preview_name).stem}-pagina-{page_number}.png",
                conditional=False,
            )
            response.headers["Cache-Control"] = "private, max-age=3600"
            return response
        try:
            total_pages = pdf_page_count(preview_data)
            page_urls = [
                url_for(
                    "api_v1_react.email_source_attachment",
                    message_id=message_id,
                    name=original_name,
                    viewer="mobile",
                    page=page,
                )
                for page in range(1, total_pages + 1)
            ]
        except Exception as exc:
            current_app.logger.warning(
                "Lettore PDF fonte PEC non disponibile message_id=%s file=%s: %s",
                message_id,
                original_name,
                exc,
            )
            return preview_error_html(download_url)
        return pdf_mobile_preview_html(
            nome_documento=preview_name or original_name,
            page_urls=page_urls,
            scarica_url=download_url,
        )
    return send_file(
        io.BytesIO(preview_data),
        mimetype=preview_mimetype,
        as_attachment=False,
        download_name=preview_name,
        conditional=False,
    )


def _serve_cached_email_source_preview(cache_key: str, *, message_id: str):
    cached_preview = _read_email_source_preview_cache(cache_key)
    if not cached_preview:
        return None
    preview_data, preview_mimetype, preview_name, original_name = cached_preview
    response = _serve_email_source_preview(
        preview_data,
        preview_mimetype,
        preview_name,
        message_id=message_id,
        original_name=original_name,
    )
    if hasattr(response, "headers"):
        response.headers["Cache-Control"] = "private, max-age=3600"
        response.headers["X-IUSENTRA-Source-Preview-Cache"] = "hit"
    return response


@api_v1_react.get("/email/source/<message_id>")
@_richiedi_auth
def email_source_attachment(message_id: str):
    """Apre la fonte documentale di una PEC senza duplicare l'allegato originale."""

    requested_name = Path(str(request.args.get("name", "") or "").replace("\\", "/")).name.rstrip(" .").casefold()

    def matching_indices(names: list[str]) -> list[int]:
        normalized = [Path(name.replace("\\", "/")).name.rstrip(" .").casefold() for name in names]
        matches = [index for index, name in enumerate(normalized) if name == requested_name]
        if not matches and requested_name:
            matches = [index for index, name in enumerate(normalized) if requested_name in name]
        if not requested_name and len(normalized) == 1:
            matches = [0]
        return matches

    raw_data: bytes | None = None
    original_name = ""
    original_mime = ""
    tenant_id = _tenant_runtime_label()
    source_sha256 = ""
    cache_key = ""
    try:
        audit_metadata = _read_pec_source_message_metadata(str(message_id or "").strip())
    except sqlite3.OperationalError as exc:
        if not _sqlite_busy_error(exc):
            raise
        current_app.logger.warning(
            "Archivio PEC temporaneamente occupato durante apertura fonte message_id=%s file=%s: %s",
            message_id,
            requested_name,
            exc,
        )
        return Response(
            "Archivio PEC in aggiornamento. Riprova tra pochi secondi.",
            status=503,
            mimetype="text/plain",
        )

    if audit_metadata is not None:
        source_sha256 = str(audit_metadata.get("mime_sha256") or "")
        if source_sha256 and request.args.get("download") != "1":
            cache_key = _email_source_cache_key(
                tenant_id=tenant_id,
                message_id=message_id,
                requested_name=requested_name,
                source_sha256=source_sha256,
            )
            cached_response = _serve_cached_email_source_preview(cache_key, message_id=message_id)
            if cached_response is not None:
                return cached_response
        try:
            raw_mime_bytes = _read_pec_source_message_blob(str(message_id or "").strip())
        except sqlite3.OperationalError as exc:
            if not _sqlite_busy_error(exc):
                raise
            return Response(
                "Archivio PEC in aggiornamento. Riprova tra pochi secondi.",
                status=503,
                mimetype="text/plain",
            )
        if raw_mime_bytes is None:
            return Response("La PEC collegata non è disponibile nello storico dello studio.", status=404, mimetype="text/plain")
        source_sha256 = source_sha256 or hashlib.sha256(raw_mime_bytes).hexdigest()
        _, _, audit_attachments = extract_message_parts(message_from_bytes(raw_mime_bytes))
        names = [attachment.filename for attachment in audit_attachments]
        matching = matching_indices(names)
        if len(matching) != 1:
            return Response("L'allegato indicato non è stato trovato in modo univoco nella PEC.", status=404, mimetype="text/plain")
        audit_attachment = audit_attachments[matching[0]]
        raw_data = audit_attachment.data
        original_name = audit_attachment.filename
        original_mime = attachment_mimetype(original_name, audit_attachment.content_type)
    else:
        gestore = GestioneEmailRicevute(_tenant_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))
        email_item = gestore.get(message_id)
        if email_item is None:
            wanted_id = str(message_id or "").strip().strip("<>").casefold()
            email_item = next(
                (
                    item
                    for item in gestore.tutte()
                    if wanted_id in {
                        str(getattr(item, "id", "") or "").strip().strip("<>").casefold(),
                        str(getattr(item, "message_id", "") or "").strip().strip("<>").casefold(),
                    }
                ),
                None,
            )
        if email_item is None:
            return Response("La PEC collegata non è disponibile nello storico dello studio.", status=404, mimetype="text/plain")
        attachments = list(getattr(email_item, "allegati", []) or [])
        names = [
            str((info or {}).get("nome") or (info or {}).get("nome_file") or "allegato").strip()
            for info in attachments
        ]
        matching = matching_indices(names)
        if len(matching) != 1:
            return Response("L'allegato indicato non è stato trovato in modo univoco nella PEC.", status=404, mimetype="text/plain")
        attachment_index = matching[0]
        info = attachments[attachment_index] or {}
        original_name = names[attachment_index]
        original_mime = attachment_mimetype(original_name, str(info.get("mime") or ""))
        source_sha256 = str(info.get("sha256") or "").strip().casefold()
        if source_sha256 and request.args.get("download") != "1":
            cache_key = _email_source_cache_key(
                tenant_id=tenant_id,
                message_id=message_id,
                requested_name=requested_name,
                source_sha256=source_sha256,
            )
            cached_response = _serve_cached_email_source_preview(cache_key, message_id=message_id)
            if cached_response is not None:
                return cached_response
        raw_data = gestore.leggi_allegato(email_item, attachment_index)
        if raw_data is None:
            return Response("L'allegato non è disponibile nello storico locale. Sincronizza nuovamente la PEC.", status=409, mimetype="text/plain")
        source_sha256 = source_sha256 or hashlib.sha256(raw_data).hexdigest()

    if raw_data is None:
        return Response("L'allegato non è disponibile nello storico dello studio.", status=409, mimetype="text/plain")
    if request.args.get("download") == "1":
        return send_file(
            io.BytesIO(raw_data),
            mimetype=original_mime,
            as_attachment=True,
            download_name=original_name,
            conditional=False,
        )

    def serve_preview(preview_data: bytes, preview_mimetype: str, preview_name: str):
        mime = str(preview_mimetype or "").split(";", 1)[0].strip().lower()
        if mime == "application/pdf" and _source_pdf_viewer_requested():
            download_url = url_for(
                "api_v1_react.email_source_attachment",
                message_id=message_id,
                name=original_name,
                download=1,
            )
            page_value = str(request.args.get("page") or "").strip()
            if page_value:
                try:
                    page_number = int(page_value)
                    png_payload = render_pdf_page_png(preview_data, page_number)
                except Exception as exc:
                    current_app.logger.warning(
                        "Anteprima pagina fonte PEC non disponibile message_id=%s file=%s page=%s: %s",
                        message_id,
                        original_name,
                        page_value,
                        exc,
                    )
                    return preview_error_html(download_url)
                response = send_file(
                    io.BytesIO(png_payload),
                    mimetype="image/png",
                    as_attachment=False,
                    download_name=f"{Path(preview_name).stem}-pagina-{page_number}.png",
                    conditional=False,
                )
                response.headers["Cache-Control"] = "private, max-age=3600"
                return response
            try:
                total_pages = pdf_page_count(preview_data)
                page_urls = [
                    url_for(
                        "api_v1_react.email_source_attachment",
                        message_id=message_id,
                        name=original_name,
                        viewer="mobile",
                        page=page,
                    )
                    for page in range(1, total_pages + 1)
                ]
            except Exception as exc:
                current_app.logger.warning(
                    "Lettore PDF fonte PEC non disponibile message_id=%s file=%s: %s",
                    message_id,
                    original_name,
                    exc,
                )
                return preview_error_html(download_url)
            return pdf_mobile_preview_html(
                nome_documento=preview_name or original_name,
                page_urls=page_urls,
                scarica_url=download_url,
            )
        return send_file(
            io.BytesIO(preview_data),
            mimetype=preview_mimetype,
            as_attachment=False,
            download_name=preview_name,
            conditional=False,
        )

    if not cache_key:
        cache_key = _email_source_cache_key(
            tenant_id=tenant_id,
            message_id=message_id,
            requested_name=requested_name,
            source_sha256=source_sha256 or hashlib.sha256(raw_data).hexdigest(),
        )
        cached_response = _serve_cached_email_source_preview(cache_key, message_id=message_id)
        if cached_response is not None:
            return cached_response

    preview = build_attachment_preview_payload(
        nome_file=original_name,
        data=raw_data,
        mime_salvato=original_mime,
    )
    if preview.unavailable_reason:
        download_url = url_for(
            "api_v1_react.email_source_attachment",
            message_id=message_id,
            name=original_name,
            download=1,
        )
        return preview_unavailable_html(original_name, download_url)
    try:
        _write_email_source_preview_cache(
            cache_key,
            data=preview.data,
            mimetype=preview.mimetype,
            download_name=preview.download_name,
            original_name=original_name,
        )
    except OSError:
        current_app.logger.exception("Cache anteprima fonte PEC non scritta")
    return serve_preview(preview.data, preview.mimetype, preview.download_name)


@api_v1_react.get("/agenda/importa")
@_richiedi_auth
def agenda_importa_defaults():
    return jsonify(
        {
            "ok": True,
            "source": "api",
            "modalita": [
                {"id": "file", "label": "File ICS"},
                {"id": "url", "label": "URL calendario"},
            ],
            "sorgenti": [
                {"id": "generico", "label": "Calendario esterno"},
                {"id": "google", "label": "Google Calendar"},
                {"id": "outlook", "label": "Outlook / Microsoft 365"},
                {"id": "apple", "label": "Apple Calendar"},
                {"id": "webcal", "label": "Webcal"},
            ],
            "tipi": [
                {"id": "UDIENZA", "label": "Udienza"},
                {"id": "CONSULTAZIONE", "label": "Consultazione"},
                {"id": "RIUNIONE", "label": "Riunione"},
                {"id": "DEPOSITO", "label": "Deposito"},
                {"id": "SCADENZA", "label": "Scadenza"},
                {"id": "ALTRO", "label": "Altro"},
            ],
            "promemoria": [
                {"id": "15", "label": "15 minuti prima"},
                {"id": "30", "label": "30 minuti prima"},
                {"id": "60", "label": "1 ora prima"},
                {"id": "1440", "label": "1 giorno prima"},
            ],
        }
    )


@api_v1_react.get("/agenda/nuovo/defaults")
@_richiedi_auth
def agenda_nuovo_defaults():
    utente = g.get("utente_corrente")
    nome = str(getattr(utente, "nome_completo", "") or "").strip()
    username = str(getattr(utente, "username", "") or "").strip()
    return jsonify(
        {
            "ok": True,
            "avvocato": nome or username,
        }
    )
