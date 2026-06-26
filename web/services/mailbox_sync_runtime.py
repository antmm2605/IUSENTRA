"""Runtime condiviso per sincronizzazione PEC ed email ordinaria."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock
from time import monotonic
from typing import Any, Callable, Mapping

from flask import current_app, g, has_app_context

from web.services.tenant_paths import CROSS_STUDIO_DATA_MESSAGE, TenantDataPathError


DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS = 180.0

_STATE_LOCK = RLock()
_RUN_LOCKS: dict[str, Lock] = {}
_LAST_ATTEMPT: dict[str, float] = {}
_MAILBOX_TENANT_SENSITIVE_KEYS = frozenset(
    {
        "EMAIL_CASELLA_DB",
        "EMAIL_ORDINARIA_DB",
        "MESSAGGI_DB",
        "STUDIO_CONFIG",
        "CONFIG_STUDIO_DB",
        "FASCICOLI_DB",
        "FASCICOLI_DOCS",
        "FASCICOLI_ARCH",
        "AUTH_DB",
        "AUDIT_DB",
    }
)


@dataclass(frozen=True)
class MailboxRuntimeContext:
    tenant_label: str
    data_paths: Mapping[str, Any]
    config: Mapping[str, Any]
    actor_id: str = ""
    actor_username: str = ""


def _app_config() -> Mapping[str, Any]:
    return current_app.config if has_app_context() else {}


def _current_data_paths() -> Mapping[str, Any]:
    if has_app_context():
        return getattr(g, "data_paths", {}) or {}
    return {}


def _current_actor() -> tuple[str, str]:
    if not has_app_context():
        return "", ""
    utente = g.get("utente_corrente")
    return (
        str(getattr(utente, "id", "") or ""),
        str(getattr(utente, "username", "") or getattr(utente, "nome", "") or ""),
    )


def mailbox_context_for_current_request() -> MailboxRuntimeContext:
    actor_id, actor_username = _current_actor()
    tenant = ""
    if has_app_context():
        tenant = str(g.get("tenant_slug", "") or g.get("auth_tenant_slug", "") or "")
    return MailboxRuntimeContext(
        tenant_label=tenant or "default",
        data_paths=_current_data_paths(),
        config=_app_config(),
        actor_id=actor_id,
        actor_username=actor_username,
    )


def mailbox_context_from_paths(
    data_paths: Mapping[str, Any],
    *,
    tenant_label: str = "default",
    actor_id: str = "scheduler",
    actor_username: str = "scheduler",
) -> MailboxRuntimeContext:
    return MailboxRuntimeContext(
        tenant_label=str(tenant_label or "default"),
        data_paths=data_paths,
        config=_app_config(),
        actor_id=actor_id,
        actor_username=actor_username,
    )


def clear_mailbox_sync_runtime_state() -> None:
    """Resetta lock/cooldown in test o dopo riconfigurazioni esplicite."""
    with _STATE_LOCK:
        _RUN_LOCKS.clear()
        _LAST_ATTEMPT.clear()


def _context_multi_tenant(ctx: MailboxRuntimeContext) -> bool:
    return bool(ctx.config.get("MULTI_TENANT"))


def _tenant_root_from_context(ctx: MailboxRuntimeContext) -> Path:
    studio_db = str(ctx.data_paths.get("STUDIO_DB") or "").strip()
    if not studio_db:
        raise TenantDataPathError(CROSS_STUDIO_DATA_MESSAGE)
    return Path(studio_db).expanduser().resolve().parent


def _assert_runtime_path_in_tenant(ctx: MailboxRuntimeContext, key: str, value: str) -> str:
    resolved = Path(value).expanduser().resolve()
    if not _context_multi_tenant(ctx) or key not in _MAILBOX_TENANT_SENSITIVE_KEYS:
        return str(resolved)
    tenant_root = _tenant_root_from_context(ctx)
    try:
        resolved.relative_to(tenant_root)
    except ValueError as exc:
        raise TenantDataPathError(CROSS_STUDIO_DATA_MESSAGE) from exc
    return str(resolved)


def _cfg_path(
    ctx: MailboxRuntimeContext,
    key: str,
    default: str = "",
    *aliases: str,
    require_tenant: bool = False,
) -> str:
    for candidate in (key, *aliases):
        value = ctx.data_paths.get(candidate)
        if value:
            return _assert_runtime_path_in_tenant(ctx, candidate, str(value))
    if _context_multi_tenant(ctx) and (require_tenant or key in _MAILBOX_TENANT_SENSITIVE_KEYS):
        raise TenantDataPathError(CROSS_STUDIO_DATA_MESSAGE)
    for candidate in (key, *aliases):
        value = ctx.config.get(candidate)
        if value:
            return str(Path(str(value)).expanduser().resolve())
    return str(default or "")


def _studio_config_path(ctx: MailboxRuntimeContext) -> str:
    return _cfg_path(ctx, "STUDIO_CONFIG", "./config/studio.json", "CONFIG_STUDIO_DB")


def _load_studio_config(ctx: MailboxRuntimeContext) -> Any:
    from pct.config_studio import GestioneConfigStudio

    return GestioneConfigStudio(config_path=_studio_config_path(ctx)).config


def _get_config_pec(ctx: MailboxRuntimeContext) -> Any:
    try:
        cfg = _load_studio_config(ctx)
        return cfg.pec if cfg and hasattr(cfg, "pec") else None
    except Exception:
        return None


def _get_config_smtp(ctx: MailboxRuntimeContext) -> Any:
    try:
        cfg = _load_studio_config(ctx)
        return cfg.smtp if cfg and hasattr(cfg, "smtp") else None
    except Exception:
        return None


def _email_manager(ctx: MailboxRuntimeContext, kind: str):
    from pct.email_client import GestioneEmailRicevute

    if kind == "ordinary":
        default = os.environ.get("PCT_EMAIL_ORDINARIA_DB", "./email/ordinaria.json")
        return GestioneEmailRicevute(db_path=_cfg_path(ctx, "EMAIL_ORDINARIA_DB", default, require_tenant=True))
    return GestioneEmailRicevute(
        db_path=_cfg_path(ctx, "EMAIL_CASELLA_DB", os.environ.get("PCT_EMAIL_DB", "./email/casella.json"), require_tenant=True)
    )


def _pec_state_path(ctx: MailboxRuntimeContext) -> str:
    fascicoli_db = _cfg_path(ctx, "FASCICOLI_DB", "./fascicoli/fascicoli.json")
    return os.path.join(os.path.dirname(os.path.abspath(fascicoli_db)), "pec_cancelleria_state.json")


def _fascicoli_manager(ctx: MailboxRuntimeContext):
    if not ctx.data_paths and has_app_context():
        from web.helpers import get_fascicoli

        return get_fascicoli()
    from pct.fascicoli import GestioneFascicoli

    return GestioneFascicoli(
        db_path=_cfg_path(ctx, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        documents_dir=_cfg_path(ctx, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        archive_dir=_cfg_path(ctx, "FASCICOLI_ARCH", "./fascicoli/archivio"),
    )


def _audit(ctx: MailboxRuntimeContext, azione: str, dettagli: str = "") -> None:
    try:
        from pct.auth import GestioneUtenti

        gestore = GestioneUtenti(
            db_path=_cfg_path(ctx, "AUTH_DB", "./auth/utenti.json"),
            audit_path=_cfg_path(ctx, "AUDIT_DB", "./auth/audit.json"),
            secret_key=str(ctx.config.get("SECRET_KEY", "")),
            crea_admin_se_vuoto=False,
        )
        if hasattr(gestore, "registra_audit"):
            gestore.registra_audit(ctx.actor_id, azione, dettagli=dettagli)
        else:
            gestore.registra_evento(
                azione,
                id_utente=ctx.actor_id,
                username=ctx.actor_username,
                dettagli=dettagli,
            )
    except Exception:
        return


def _sync_inviati(ctx: MailboxRuntimeContext, gestore: Any) -> None:
    try:
        from pct.messaggi import CanaleMsggio, GestioneMessaggi

        manager = GestioneMessaggi(config=None, db_path=_cfg_path(ctx, "MESSAGGI_DB", "./messaggi/storico.json"))
        inviati = [
            msg
            for msg in manager.tutti(canale=CanaleMsggio.EMAIL)
            if getattr(getattr(msg, "stato", ""), "value", getattr(msg, "stato", ""))
            in {"INVIATO", "CONSEGNATO", "LETTO"}
        ]
        if inviati:
            gestore.sincronizza_inviati(inviati)
    except Exception:
        return


def _auto_summary(gestore: Any, log: list[str]) -> dict[str, int]:
    try:
        from pct.email_client import riassunto_auto_esiti

        summary = riassunto_auto_esiti(log)
    except Exception:
        summary = {"aggiornati": 0, "non_abbinati": 0, "errori": 0, "totale": len(log or [])}
    try:
        pending = [e for e in gestore._carica().values() if getattr(e, "e_pst", False) and not getattr(e, "auto_registrata", False)]  # noqa: SLF001
        summary["pst_in_attesa"] = len(pending)
    except Exception:
        summary["pst_in_attesa"] = 0
    return summary


def run_pec_mailbox_sync(
    ctx: MailboxRuntimeContext | None = None,
    *,
    limite: int = 500,
    incremental_only: bool = True,
) -> dict[str, Any]:
    """Esegue la sincronizzazione PEC ordinaria sul solo nuovo non gia' acquisito."""
    runtime = ctx or mailbox_context_for_current_request()
    gestore = _email_manager(runtime, "pec")
    pec_cfg = _get_config_pec(runtime)
    smtp_cfg = _get_config_smtp(runtime)

    imap_host = imap_port = username = password = use_ssl = None
    if pec_cfg and getattr(pec_cfg, "imap_host", "") and getattr(pec_cfg, "indirizzo", ""):
        imap_host = pec_cfg.imap_host
        imap_port = getattr(pec_cfg, "imap_port", 993)
        username = pec_cfg.indirizzo
        password = pec_cfg.password
        use_ssl = getattr(pec_cfg, "use_ssl", True)
    elif smtp_cfg and getattr(smtp_cfg, "imap_host", ""):
        imap_host = smtp_cfg.imap_host
        imap_port = getattr(smtp_cfg, "imap_port", 993)
        username = smtp_cfg.username
        password = smtp_cfg.password
        use_ssl = getattr(smtp_cfg, "imap_use_ssl", True)

    if not imap_host or not username:
        return {
            "ok": False,
            "errore": "IMAP non configurato. Configura le credenziali in Impostazioni -> Email.",
        }

    try:
        poll_report = {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}
        log_esiti: list[str] = []
        auto_summary = {"aggiornati": 0, "non_abbinati": 0, "errori": 0, "totale": 0, "pst_in_attesa": 0}
        if pec_cfg and getattr(pec_cfg, "imap_host", "") and getattr(pec_cfg, "indirizzo", ""):
            from pct.email_client import sincronizza_pec_e_fascicoli

            workflow = sincronizza_pec_e_fascicoli(
                gestione_email=gestore,
                gestione_fascicoli=_fascicoli_manager(runtime),
                config_pec=pec_cfg,
                state_path=_pec_state_path(runtime),
                limite=limite,
                incremental_only=incremental_only,
            )
            report = workflow.get("sync", {}) or {}
            log_esiti = workflow.get("auto_esiti", []) or []
            auto_summary = _auto_summary(gestore, log_esiti)
            poll_report = workflow.get("poll", {}) or poll_report
        else:
            from pct.email_client import aggiorna_esiti_da_email, cartelle_imap_standard

            report = gestore.sincronizza_imap(
                imap_host=str(imap_host),
                imap_port=int(imap_port or 993),
                username=str(username),
                password=str(password or ""),
                use_ssl=bool(use_ssl),
                cartelle_imap=cartelle_imap_standard(),
                limite=limite,
                timeout_seconds=15,
                incremental_only=incremental_only,
            )
            if report.get("pst_trovate", 0) > 0:
                log_esiti = aggiorna_esiti_da_email(gestore, _fascicoli_manager(runtime))
                auto_summary = _auto_summary(gestore, log_esiti)

        _sync_inviati(runtime, gestore)
        errore = str(report.get("errore", "") or "").strip()
        _audit(runtime, "email.sincronizzata", f"Nuove: {report.get('nuove', 0)}, PST: {report.get('pst_trovate', 0)}")
        return {
            "ok": True,
            "warning": bool(errore),
            "messaggio": "Sincronizzazione completata con avvisi. Sincronizzazione IMAP non completata." if errore else "Sincronizzazione completata.",
            "nuove": report.get("nuove", 0),
            "pst_trovate": report.get("pst_trovate", 0),
            "allegati_salvati": report.get("allegati_salvati", 0),
            "esiti_aggiornati": auto_summary["aggiornati"],
            "non_abbinati": auto_summary["non_abbinati"],
            "pst_in_attesa": auto_summary["pst_in_attesa"],
            "comunicazioni_cancelleria": poll_report.get("associati", 0),
            "report": poll_report,
            "errore": errore,
            "sync_errore": errore,
            "stats": gestore.statistiche(),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


def run_ordinary_mailbox_sync(
    ctx: MailboxRuntimeContext | None = None,
    *,
    limite: int = 500,
    incremental_only: bool = True,
) -> dict[str, Any]:
    """Esegue la sincronizzazione ordinaria leggendo solo il nuovo non acquisito."""
    runtime = ctx or mailbox_context_for_current_request()
    gestore = _email_manager(runtime, "ordinary")
    cfg = _get_config_smtp(runtime)
    if not cfg or not getattr(cfg, "imap_host", "") or not getattr(cfg, "username", ""):
        return {
            "ok": False,
            "errore": (
                "IMAP email ordinaria non configurato. Apri Impostazioni -> Email SMTP "
                "e compila server IMAP, username e password."
            ),
        }
    try:
        from pct.email_client import cartelle_imap_standard

        report = gestore.sincronizza_imap(
            imap_host=getattr(cfg, "imap_host", ""),
            imap_port=int(getattr(cfg, "imap_port", 993) or 993),
            username=getattr(cfg, "username", ""),
            password=getattr(cfg, "password", ""),
            use_ssl=bool(getattr(cfg, "imap_use_ssl", True)),
            cartelle_imap=cartelle_imap_standard(),
            limite=limite,
            timeout_seconds=15,
            incremental_only=incremental_only,
        )
        _sync_inviati(runtime, gestore)
        errore = str(report.get("errore", "") or "").strip()
        _audit(runtime, "email_ordinaria.sincronizzata", f"Nuove: {report.get('nuove', 0)}")
        return {
            "ok": True,
            "warning": bool(errore),
            "messaggio": "Sincronizzazione email ordinaria completata con avvisi." if errore else "Sincronizzazione email ordinaria completata.",
            "nuove": report.get("nuove", 0),
            "allegati_salvati": report.get("allegati_salvati", 0),
            "errore": errore,
            "sync_errore": errore,
            "stats": gestore.statistiche(),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


def _lock_key(ctx: MailboxRuntimeContext, kind: str) -> str:
    db_key = "EMAIL_ORDINARIA_DB" if kind == "ordinary" else "EMAIL_CASELLA_DB"
    db_path = _cfg_path(ctx, db_key, "")
    config_path = _studio_config_path(ctx)
    return "|".join([kind, ctx.tenant_label, db_path, config_path])


def _sync_with_runtime_guard(
    kind: str,
    runner: Callable[..., dict[str, Any]],
    *,
    ctx: MailboxRuntimeContext | None = None,
    force: bool = False,
    cooldown_seconds: float = DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS,
    limite: int | None = None,
    incremental_only: bool = True,
) -> dict[str, Any]:
    runtime = ctx or mailbox_context_for_current_request()
    key = _lock_key(runtime, kind)
    now = monotonic()
    with _STATE_LOCK:
        lock = _RUN_LOCKS.setdefault(key, Lock())
        last = _LAST_ATTEMPT.get(key, 0.0)
        if not force and last and now - last < max(0.0, float(cooldown_seconds)):
            return {"ok": True, "skipped": True, "reason": "cooldown", "result": {}, "cooldown_seconds": int(cooldown_seconds)}
        acquired = lock.acquire(blocking=False)
    if not acquired:
        return {"ok": True, "skipped": True, "reason": "already_running", "result": {}}
    try:
        kwargs: dict[str, Any] = {}
        if limite is not None:
            kwargs["limite"] = max(1, int(limite))
        if incremental_only:
            kwargs["incremental_only"] = True
        result = runner(runtime, **kwargs)
        return {"ok": bool(result.get("ok", False)), "skipped": False, "reason": "", "result": result}
    finally:
        with _STATE_LOCK:
            _LAST_ATTEMPT[key] = monotonic()
        lock.release()


def sync_pec_for_current_context(
    *,
    force: bool = False,
    cooldown_seconds: float = DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS,
    limite: int | None = None,
    incremental_only: bool = True,
) -> dict[str, Any]:
    return _sync_with_runtime_guard(
        "pec",
        run_pec_mailbox_sync,
        force=force,
        cooldown_seconds=cooldown_seconds,
        limite=limite,
        incremental_only=incremental_only,
    )


def sync_ordinary_for_current_context(
    *,
    force: bool = False,
    cooldown_seconds: float = DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS,
    limite: int | None = None,
    incremental_only: bool = True,
) -> dict[str, Any]:
    return _sync_with_runtime_guard(
        "ordinary",
        run_ordinary_mailbox_sync,
        force=force,
        cooldown_seconds=cooldown_seconds,
        limite=limite,
        incremental_only=incremental_only,
    )


def sync_mailboxes_for_current_context(
    *,
    force: bool = False,
    cooldown_seconds: float = DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS,
    limite: int | None = None,
    incremental_only: bool = True,
) -> dict[str, Any]:
    return {
        "ok": True,
        "pec": sync_pec_for_current_context(
            force=force,
            cooldown_seconds=cooldown_seconds,
            limite=limite,
            incremental_only=incremental_only,
        ),
        "ordinary": sync_ordinary_for_current_context(
            force=force,
            cooldown_seconds=cooldown_seconds,
            limite=limite,
            incremental_only=incremental_only,
        ),
    }


def sync_mailboxes_for_paths(
    data_paths: Mapping[str, Any],
    *,
    tenant_label: str = "default",
    force: bool = False,
    cooldown_seconds: float = DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS,
    limite: int | None = None,
    incremental_only: bool = True,
) -> dict[str, Any]:
    ctx = mailbox_context_from_paths(data_paths, tenant_label=tenant_label)
    return {
        "ok": True,
        "pec": _sync_with_runtime_guard(
            "pec",
            run_pec_mailbox_sync,
            ctx=ctx,
            force=force,
            cooldown_seconds=cooldown_seconds,
            limite=limite,
            incremental_only=incremental_only,
        ),
        "ordinary": _sync_with_runtime_guard(
            "ordinary",
            run_ordinary_mailbox_sync,
            ctx=ctx,
            force=force,
            cooldown_seconds=cooldown_seconds,
            limite=limite,
            incremental_only=incremental_only,
        ),
    }
