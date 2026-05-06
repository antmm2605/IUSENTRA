"""Endpoint ponte per la migrazione React progressiva.

Questi endpoint restano sottili: espongono dati normalizzati alla shell React
riusando i repository e i servizi esistenti, senza creare una seconda source of
truth frontend.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from pct import __version__ as APP_VERSION
from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail
from pct.fatturazione import StatoParcella
from pct.messaggi import CanaleMsggio, ConfigMessaggistica, GestioneMessaggi, Messaggio, StatoMessaggio
from pct.preventivi import StatoPreventivo
from pct.practice_engine.deposit_orchestrator import prepare_deposit, send_deposit
from pct.practice_engine.deposit_readiness import run_predeposit_check
from pct.practice_engine.evaluator import build_regia_payload, ensure_evidence_pack, ensure_profile_for_fascicolo
from pct.practice_engine.profiles import get_profile
from pct.practice_engine.receipt_tracker import import_receipt
from pct.practice_engine.validators import ValidationContext, validate_slot
from pct.scadenziario import PrioritaTermine, TipoTermine
from pct.termini_processuali import (
    DeadlinePracticeRepository,
    LEGAL_SOURCES,
    calculate_and_audit,
)
from pct.timesheet import StatoTimesheet
from pct.workspace_intelligente import WorkspaceIntelligenteService
from pct.workflow_commerciale import apri_fascicolo_automatico
from web.services.react_agenda_bridge import build_react_agenda_payload
from web.services.react_admin_database_bridge import (
    build_react_admin_database_error_payload,
    build_react_admin_database_payload,
)
from web.services.react_audit_bridge import build_react_audit_error_payload, build_react_audit_payload
from web.services.react_clienti_bridge import (
    build_react_cliente_cartella_payload,
    build_react_cliente_modifica_payload,
    build_react_clienti_nuovo_payload,
    build_react_clienti_payload,
    build_react_soggetto_modifica_payload,
)
from web.services.react_condivisioni_bridge import build_react_condivisioni_payload
from web.services.mailbox_sync_runtime import sync_mailboxes_for_current_context
from web.services.react_dashboard_cache import (
    DASHBOARD_CACHE_TTL_SECONDS,
    clear_dashboard_payload_cache,
    get_dashboard_payload_cached,
)
from web.services.react_document_editor_bridge import build_react_document_editor_payload
from web.services.react_email_bridge import build_react_email_payload
from web.services.react_fascicoli_bridge import (
    build_react_archivio_payload,
    build_react_fascicoli_export_payload,
    build_react_fascicoli_payload,
    build_react_fascicolo_detail_payload,
    build_react_fascicolo_form_payload,
)
from web.services.react_messaggi_bridge import build_react_messaggi_nuovo_payload, build_react_messaggi_payload
from web.services.react_practice_engine_bridge import build_react_practice_engine_payload
from web.services.react_privacy_bridge import build_react_privacy_registro_payload
from web.services.react_scadenziario_bridge import (
    build_react_scadenziario_nuova_payload,
    build_react_scadenziario_payload,
)
from web.services.react_soggetti_bridge import build_react_soggetti_payload
from web.services.react_statistiche_bridge import (
    build_react_statistiche_error_payload,
    build_react_statistiche_payload,
)
from web.services.react_utenti_bridge import build_react_utenti_error_payload, build_react_utenti_payload
from web.services.react_profili_bridge import build_react_profili_error_payload, build_react_profili_payload
from web.services.react_backup_bridge import build_react_backup_error_payload, build_react_backup_payload
from web.services.react_sito_studio_bridge import (
    build_react_sito_studio_error_payload,
    build_react_sito_studio_payload,
)
from web.services.react_studio_bridge import build_react_studio_error_payload, build_react_studio_payload
from web.services.react_amministrazione_bridge import (
    build_react_amministrazione_error_payload,
    build_react_amministrazione_payload,
)
from web.services.react_fatturazione_bridge import (
    build_react_fatturazione_error_payload,
    build_react_fatturazione_payload,
)
from web.services.react_compensi_forensi_bridge import (
    build_react_compensi_forensi_error_payload,
    build_react_compensi_forensi_payload,
)
from web.services.react_tariffario_bridge import (
    build_react_tariffario_error_payload,
    build_react_tariffario_payload,
    build_react_tariffario_run_payload,
)
from web.services.react_preventivi_bridge import (
    build_react_preventivi_error_payload,
    build_react_preventivi_payload,
)
from web.services.react_template_atti_bridge import (
    build_react_template_atti_error_payload,
    build_react_template_atti_payload,
)
from web.services.react_redazione_atti_bridge import (
    build_react_redazione_atti_error_payload,
    build_react_redazione_atti_payload,
)
from web.services.react_incassi_pagamenti_bridge import (
    build_react_incassi_pagamenti_error_payload,
    build_react_incassi_pagamenti_payload,
)
from web.services.react_studio_module_bridge import build_react_studio_module_payload
from web.services.react_telematico_bridge import (
    build_react_telematico_payload,
    build_react_telematico_surface_payload,
    build_react_tribunali_payload,
)
from web.services.react_timesheet_bridge import build_react_timesheet_payload
from web.services.react_wizard_pro_bridge import (
    build_react_wizard_pro_complete_payload,
    build_react_wizard_pro_payload,
    build_react_wizard_pro_step_payload,
)
from web.services.studio_site_runtime import site_admin_identity_or_403
from web.helpers import (
    get_agenda,
    get_calendar_sync,
    get_clienti,
    get_fascicoli,
    get_fatturazione,
    get_normative_tables,
    get_pagamenti,
    get_practice_engine,
    get_giurisprudenza,
    get_preventivi,
    get_scadenziario,
    get_soggetti,
    get_timesheet,
    get_utenti,
    studio_nome,
)

api_v1_react = Blueprint("api_v1_react", __name__, url_prefix="/api/v1/ui")

MONTHS_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _richiedi_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"errore": "Autenticazione richiesta.", "codice": 401}), 401

    return wrapper


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


def _session_user_can(permission: str) -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)(permission))


def _puo_leggere_backup() -> bool:
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)("backup.leggi"))


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
        db_path=str(current_app.config.get("TEMPLATE_ATTI_DB", "./template_atti/templates.json") or "./template_atti/templates.json")
    )


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


def _core_runtime_func(name: str) -> Callable[..., Any] | None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    func = core_runtime.get(name)
    return func if callable(func) else None


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
    gf = get_fascicoli()
    fascicolo = gf.get(id_fasc)
    if not fascicolo:
        return {"error": jsonify({"errore": "Fascicolo non trovato.", "codice": 404}), "status": 404}
    gp = get_preventivi()
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


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        current_app.logger.exception("Dashboard React: sorgente non disponibile (%s).", label)
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
    today = date.today()
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
    today = date.today()
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
    text = f"{float(value or 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {text}"


def _count_agenda_oggi() -> int:
    today = date.today()
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
    return GestioneEmailRicevute(_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"))


def _ordinary_email_manager() -> GestioneEmailRicevute:
    return GestioneEmailRicevute(_cfg_value("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"))


def _messaggi_manager() -> GestioneMessaggi:
    return GestioneMessaggi(
        ConfigMessaggistica(studio_nome=studio_nome()),
        db_path=_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
    )


def _messaggi_tutti() -> list[Messaggio]:
    try:
        return _messaggi_manager().tutti()
    except Exception:
        path = Path(_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"))
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
        row = _row(
            getattr(email, "id", ""),
            title,
            subtitle,
            time=_format_time(getattr(email, "timestamp", "")),
            unread=unread,
            href="/email/",
        )
        if len(pec_rows) < limit:
            pec_rows.append(row)
    for email in ordinary_emails:
        unread = getattr(email, "stato", "") == StatoEmail.NON_LETTA
        title = getattr(email, "mittente_nome", "") or getattr(email, "mittente", "") or "Mittente non indicato"
        subtitle = getattr(email, "oggetto", "") or getattr(email, "anteprima", "") or "Email senza oggetto"
        if len(mail_rows) >= limit:
            break
        mail_rows.append(
            _row(
                getattr(email, "id", ""),
                title,
                subtitle,
                time=_format_time(getattr(email, "timestamp", "") or getattr(email, "data", "")),
                unread=unread,
                href="/email-ordinaria/",
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
    week_ago = date.today() - timedelta(days=7)
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
            rows.append(
                _row(
                    getattr(message, "id", ""),
                    title,
                    subtitle,
                    time=_format_time(getattr(message, "creato_il", "")),
                    avatar=_initials(title),
                    badge=badge,
                    tone=tone,
                    href="/messaggi",
                )
            )
    return rows, recent_count


def _agenda_rows(limit: int = 6) -> list[dict[str, Any]]:
    today = date.today()
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
        rows.append(
            _row(
                getattr(item, "id", ""),
                getattr(item, "titolo", "") or "Appuntamento",
                subtitle,
                time=parsed.strftime("%H:%M"),
                badge=badge.upper(),
                tone="warning" if parsed.date() <= today + timedelta(days=1) else "primary",
                href="/agenda",
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
            rows.append(
                _row(
                    getattr(scadenza, "id", ""),
                    getattr(scadenza, "titolo", "") or "Scadenza urgente",
                    f"Scade {_format_date(getattr(scadenza, 'data_scadenza', ''))}",
                    badge="Apri",
                    tone="danger",
                    href="/scadenziario",
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
    preventivi = _safe("preventivi", lambda: get_preventivi(), None)
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
    today = date.today()
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
            rows.append(
                _row(
                    getattr(preventivo, "id", ""),
                    cliente_nome or "Cliente non collegato",
                    f"Pratica: {getattr(preventivo, 'oggetto', '') or getattr(preventivo, 'numero', '')}",
                    badge=badge,
                    tone=tone,
                    href="/preventivi",
                )
            )
    return rows, count


def _expiring_quotes_count() -> int:
    preventivi = _safe("preventivi", lambda: get_preventivi().tutti_preventivi(), [])
    today = date.today()
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
    anno = date.today().year
    month_prefix = f"{anno:04d}-{date.today().month:02d}"
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
                "replace_telematico": False,
                "replace_telematico_surfaces": False,
                "replace_tribunali_pec": False,
                "replace_checklist_deposito": False,
                "replace_guida_firma_digitale": False,
                "replace_preventivi": False,
                "replace_sito_studio": False,
                "replace_clienti": True,
                "replace_soggetti": True,
                "replace_email": True,
                "replace_messaggi": True,
            },
        }
    )


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


@api_v1_react.get("/clienti/nuovo")
@_richiedi_auth
def clienti_react_nuovo():
    return jsonify(build_react_clienti_nuovo_payload(
        get_clienti=get_clienti,
        get_soggetti=get_soggetti,
        query=request.args,
    ))


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
            get_preventivi=get_preventivi,
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
        db_path=_cfg_value("EMAIL_CASELLA_DB", "./email/casella.json"),
        messaggi_db=_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
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
    ))
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@api_v1_react.get("/email-ordinaria")
@_richiedi_auth
def email_ordinaria_react_list():
    response = jsonify(build_react_email_payload(
        db_path=_cfg_value("EMAIL_ORDINARIA_DB", "./email/ordinaria.json"),
        messaggi_db=_cfg_value("MESSAGGI_DB", "./messaggi/storico.json"),
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
    return jsonify(build_react_scadenziario_payload(
        gestione_scadenziario=get_scadenziario(),
        gestione_fascicoli=get_fascicoli(),
        gestione_utenti=get_utenti(),
        query_args=request.args,
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
    return DeadlinePracticeRepository.json(anchor.with_name("termini_processuali.json"))


def _current_user_id() -> str:
    utente = g.get("utente_corrente") or {}
    if isinstance(utente, dict):
        return str(utente.get("id") or utente.get("username") or "").strip()
    return str(getattr(utente, "id", "") or getattr(utente, "username", "") or "").strip()


def _json_body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


@api_v1_react.get("/scadenziario/termini/templates")
@_richiedi_auth
def scadenziario_termini_templates():
    repo = _termini_processuali_repository()
    return jsonify({
        "templates": repo.list_templates(),
        "legalSources": list(LEGAL_SOURCES),
        "endpoints": {
            "calculate": "/api/v1/ui/scadenziario/termini/calculate",
            "explain": "/api/v1/ui/scadenziario/termini/explain",
            "validate": "/api/v1/ui/scadenziario/termini/validate",
            "audit": "/api/v1/ui/scadenziario/termini/audit",
            "override": "/api/v1/ui/scadenziario/termini/override",
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
        return jsonify({"ok": False, "errore": str(exc)}), 400


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
        return jsonify({"ok": False, "errore": str(exc)}), 400


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
        scadenza = get_scadenziario().nuova(
            titolo=title,
            tipo=TipoTermine.TERMINE_PERENTORIO,
            data_scadenza=str(result["deadline"]),
            id_fascicolo=str(payload.get("id_fascicolo") or payload.get("fascicoloId") or ""),
            descrizione=str(payload.get("description") or result["explanation"] or ""),
            data_decorrenza=str(result["inputDate"]),
            perentorio=True,
            id_utente_responsabile=user_id,
            note=(
                "Calcolo termini processuali audit "
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
            "audit": result["audit"],
            "notificationsPlanned": notifications,
        })
    except Exception as exc:
        current_app.logger.exception("Creazione scadenza da calcolo non riuscita: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 400


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
        get_preventivi=get_preventivi,
        get_timesheet=get_timesheet,
        get_config_studio=_core_runtime_func("get_config_studio"),
        get_trattamenti=get_trattamenti,
        query=dict(request.args),
    ))


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
        return jsonify(build_react_admin_database_payload(
            get_database,
            latest_sqlite_snapshot_path,
            backup_dir=str(current_app.config.get("BACKUP_DIR", "./backup")),
            path=request.args.get("path", "/admin/database"),
        ))
    except Exception as exc:
        current_app.logger.exception("Bridge React database non disponibile: %s", exc)
        return jsonify(build_react_admin_database_error_payload(str(exc))), 200


# IUSENTRA_REACT_FASCICOLI_ROUTES_START
@api_v1_react.get("/fascicoli")
@_richiedi_auth
def fascicoli_react_list():
    return jsonify(build_react_fascicoli_payload(
        get_fascicoli=get_fascicoli,
        get_scadenziario=get_scadenziario,
        page=_request_int("page", default=1),
        page_size=_request_int("page_size", "pageSize", default=25),
        query=request.args.get("q", ""),
        type_filter=request.args.get("type", ""),
        status_filter=request.args.get("status", ""),
        court=request.args.get("court", ""),
        sort=request.args.get("sort", "recenti"),
        alerts_only=_request_bool("alerts_only") or _request_bool("alertsOnly"),
    ))


@api_v1_react.get("/fascicoli/archivio")
@_richiedi_auth
def fascicoli_react_archivio():
    return jsonify(build_react_archivio_payload(
        get_fascicoli=get_fascicoli,
        get_scadenziario=get_scadenziario,
        query=request.args.get("q", ""),
    ))


@api_v1_react.get("/fascicoli/export")
@_richiedi_auth
def fascicoli_react_export():
    return jsonify(build_react_fascicoli_export_payload(
        get_fascicoli=get_fascicoli,
        get_scadenziario=get_scadenziario,
    ))


@api_v1_react.get("/fascicoli/nuovo")
@_richiedi_auth
def fascicolo_react_nuovo():
    return jsonify(build_react_fascicolo_form_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        id_fasc=None,
        query=dict(request.args),
        correction_context={"active": False, "title": "", "help": "", "highlight": ""},
        studio_avvocato_titolare=_studio_avvocato_titolare(),
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/modifica")
@_richiedi_auth
def fascicolo_react_modifica(id_fasc: str):
    return jsonify(build_react_fascicolo_form_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
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


@api_v1_react.get("/fascicoli/<id_fasc>")
@_richiedi_auth
def fascicolo_react_dettaglio(id_fasc: str):
    return jsonify(build_react_fascicolo_detail_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections=_detail_include_sections(),
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/documenti")
@_richiedi_auth
def fascicolo_react_documenti(id_fasc: str):
    return jsonify(build_react_fascicolo_detail_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
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
    return jsonify(build_react_fascicolo_detail_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
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
    return jsonify(build_react_fascicolo_detail_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
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
    return jsonify(build_react_fascicolo_detail_payload(
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
        get_soggetti=get_soggetti,
        get_preventivi=get_preventivi,
        get_fatturazione=get_fatturazione,
        get_timesheet=get_timesheet,
        get_practice_engine=get_practice_engine,
        get_config_studio=_core_runtime_func("get_config_studio"),
        id_fasc=id_fasc,
        studio_avvocato_titolare=_studio_avvocato_titolare(),
        include_sections={"depositi"},
    ))


@api_v1_react.get("/fascicoli/<id_fasc>/regia")
@_richiedi_auth
def fascicolo_regia_operativa(id_fasc: str):
    return jsonify(build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_preventivi=get_preventivi,
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
    return jsonify({"ok": True, "mock_fallback": False, "message": "Profilo pratica applicato e checklist rigenerata.", "regia": result})


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
    return jsonify({"ok": True, "mock_fallback": False, "regia": result})


@api_v1_react.get("/fascicoli/<id_fasc>/checklist")
@_richiedi_auth
def fascicolo_regia_checklist(id_fasc: str):
    payload = build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_preventivi=get_preventivi,
        get_fatturazione=get_fatturazione,
        get_practice_engine=get_practice_engine,
        actor=_actor_label(),
    )
    return jsonify({"source": "repository reale", "mock_fallback": False, "checklist": payload.get("checklist", [])})


@api_v1_react.get("/fascicoli/<id_fasc>/document-slots")
@_richiedi_auth
def fascicolo_regia_document_slots(id_fasc: str):
    payload = build_react_practice_engine_payload(
        fascicolo_id=id_fasc,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_preventivi=get_preventivi,
        get_fatturazione=get_fatturazione,
        get_practice_engine=get_practice_engine,
        actor=_actor_label(),
    )
    return jsonify({"source": "repository reale", "mock_fallback": False, "documentSlots": payload.get("documentSlots", [])})


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
    return jsonify({"ok": True, "mock_fallback": False, "slot": slot.__dict__, "message": "Documento collegato allo slot."})


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
    return jsonify({"ok": True, "mock_fallback": False, "slot": updated.__dict__, "results": [item.__dict__ for item in results]})


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
    return jsonify({
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
        gf=get_fascicoli(),
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
    return jsonify({"ok": True, "mock_fallback": False, "created": result["created"], "fascicolo_id": getattr(fascicolo, "id", ""), "practice_engine_profile": result.get("practice_engine_profile", "")})


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
        gf=get_fascicoli(),
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
    return jsonify({"ok": True, "mock_fallback": False, "created": result["created"], "fascicolo_id": getattr(fascicolo, "id", ""), "practice_engine_profile": result.get("practice_engine_profile", "")})
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
        "generated_at": overview.get("generated_at") or _iso_now(),
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
        "generated_at": _iso_now(),
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
        return jsonify(result)
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


@api_v1_react.get("/sito-studio")
@_richiedi_auth
def sito_studio_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(build_react_sito_studio_payload())
    except Exception as exc:
        current_app.logger.exception("Errore Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_error_payload("Sito Studio non disponibile dal runtime corrente.")), 200


@api_v1_react.get("/sito-studio/contatti")
@_richiedi_auth
def sito_studio_contatti_page():
    denied = _richiedi_admin_sito_studio_api()
    if denied is not None:
        return denied
    try:
        return jsonify(build_react_sito_studio_payload(contacts_only=True))
    except Exception as exc:
        current_app.logger.exception("Errore contatti Sito Studio React bridge: %s", exc)
        return jsonify(build_react_sito_studio_error_payload("Contatti Sito Studio non disponibili dal runtime corrente.")), 200


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
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Studio React bridge: %s", exc)
        return jsonify(build_react_studio_error_payload("Studio non disponibile dal runtime corrente.")), 200


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
        return jsonify(build_react_fatturazione_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_fatturazione_payload(
                get_fatturazione=get_fatturazione,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                query=dict(request.args),
                route="/fatturazione",
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Fatturazione React bridge: %s", exc)
        return jsonify(
            build_react_fatturazione_error_payload(
                "Fatturazione non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/fatturazione/nuova")
@_richiedi_auth
def fatturazione_nuova_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_fatturazione_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_fatturazione_payload(
                get_fatturazione=get_fatturazione,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                query=dict(request.args),
                route="/fatturazione/nuova",
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Nuova Fatturazione React bridge: %s", exc)
        return jsonify(
            build_react_fatturazione_error_payload(
                "Form parcella non disponibile dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/incassi-pagamenti")
@_richiedi_auth
def incassi_pagamenti_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_incassi_pagamenti_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_incassi_pagamenti_payload(
                get_fatturazione=get_fatturazione,
                get_pagamenti=get_pagamenti,
                get_clienti=get_clienti,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Incassi Pagamenti React bridge: %s", exc)
        return jsonify(
            build_react_incassi_pagamenti_error_payload(
                "Incassi e pagamenti non disponibili dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/compensi-forensi")
@_richiedi_auth
def compensi_forensi_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_compensi_forensi_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_compensi_forensi_payload(
                get_normative_tables=get_normative_tables,
                get_preventivi=get_preventivi,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Compensi Forensi React bridge: %s", exc)
        return jsonify(
            build_react_compensi_forensi_error_payload(
                "Compensi forensi non disponibili dal runtime corrente."
            )
        ), 200


@api_v1_react.get("/tariffario")
@_richiedi_auth
def tariffario_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_tariffario_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
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


@api_v1_react.post("/tariffario/calcola")
@_richiedi_auth
def tariffario_calcola_page():
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_tariffario_error_payload("Sessione utente richiesta.")), 403
    try:
        payload = _request_payload()
        return jsonify(
            build_react_tariffario_run_payload(
                payload,
                get_normative_tables=get_normative_tables,
            )
        )
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
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Catalogo Template Atti React bridge: %s", exc)
        return jsonify(
            build_react_template_atti_error_payload(
                "Catalogo template atti non disponibile dal runtime corrente."
            )
        ), 200


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
                get_preventivi=get_preventivi,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Redazione Atti React bridge: %s", exc)
        return jsonify(
            build_react_redazione_atti_error_payload(
                "Redazione atti non disponibile dal runtime corrente."
            )
        ), 200


def _preventivi_ui_payload(route: str):
    utente = g.get("utente_corrente")
    if not utente:
        return jsonify(build_react_preventivi_error_payload("Sessione utente richiesta.")), 403
    try:
        return jsonify(
            build_react_preventivi_payload(
                get_preventivi=get_preventivi,
                get_clienti=get_clienti,
                get_fascicoli=get_fascicoli,
                query=dict(request.args),
                route=route,
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Preventivi React bridge: %s", exc)
        return jsonify(
            build_react_preventivi_error_payload(
                "Preventivi e conferimenti non disponibili dal runtime corrente."
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


@api_v1_react.get("/preventivi/conferimento/nuovo")
@_richiedi_auth
def preventivi_conferimento_nuovo_page():
    return _preventivi_ui_payload("/preventivi/conferimento/nuovo")


@api_v1_react.get("/agenda")
@_richiedi_auth
def agenda():
    payload = build_react_agenda_payload(
        get_agenda,
        get_scadenziario,
        from_value=request.args.get("from", ""),
        to_value=request.args.get("to", ""),
        selected_id=request.args.get("selected_id", "").strip(),
    )
    return jsonify(payload)
