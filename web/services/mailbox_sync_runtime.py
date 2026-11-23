"""Runtime condiviso per sincronizzazione PEC ed email ordinaria."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, RLock, Thread
from time import monotonic
from typing import Any, Callable, Mapping

from flask import current_app, g, has_app_context

from web.services.tenant_paths import CROSS_STUDIO_DATA_MESSAGE, TenantDataPathError
from web.services.email_storage_runtime import create_email_mailbox


DEFAULT_MAILBOX_SYNC_COOLDOWN_SECONDS = 180.0
# Decisione del 19/11/2026: una casella che non si collega non blocca mai gli altri lavori.
# - tempo massimo per casella: oltre, il giro torna subito e la sincronizzazione finisce da sola in sfondo;
# - dopo un errore si riprova con attesa crescente (5, 10, 20... minuti, fino a 2 ore);
# - lo stesso errore si segnala una volta sola, non a ogni giro.
DEFAULT_MAILBOX_SYNC_TIMEOUT_SECONDS = 240.0
ATTESA_DOPO_ERRORE_SECONDI = 300.0
ATTESA_DOPO_ERRORE_MASSIMA = 2 * 3600.0
_FALLIMENTI: dict[str, dict[str, Any]] = {}

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
        _FALLIMENTI.clear()
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


    if kind == "ordinary":
        default = os.environ.get("PCT_EMAIL_ORDINARIA_DB", "./email/ordinaria.json")
        return create_email_mailbox(db_path=_cfg_path(ctx, "EMAIL_ORDINARIA_DB", default, require_tenant=True))
    return create_email_mailbox(
        db_path=_cfg_path(ctx, "EMAIL_CASELLA_DB", os.environ.get("PCT_EMAIL_DB", "./email/casella.json"), require_tenant=True)
    )


def _pec_state_path(ctx: MailboxRuntimeContext) -> str:
    fascicoli_db = _cfg_path(ctx, "FASCICOLI_DB", "./fascicoli/fascicoli.json")
    return os.path.join(os.path.dirname(os.path.abspath(fascicoli_db)), "pec_cancelleria_state.json")


def _fascicoli_manager(ctx: MailboxRuntimeContext, mailbox):
    if not ctx.data_paths and has_app_context():
        from web.helpers import get_fascicoli

        return get_fascicoli()
    from pct.email_sql_client import GestioneEmailSQL
    from pct.fascicoli import GestioneFascicoli

    fascicoli_db = _cfg_path(ctx, "FASCICOLI_DB", "./fascicoli/fascicoli.json")
    studio_db = None
    if isinstance(mailbox, GestioneEmailSQL):
        root = Path(mailbox.db_path).resolve().parent.parent
        if not Path(fascicoli_db).resolve().is_relative_to(root):
            raise TenantDataPathError(CROSS_STUDIO_DATA_MESSAGE)
        studio_db = mailbox.repository.db
    return GestioneFascicoli(
        db_path=fascicoli_db,
        documents_dir=_cfg_path(ctx, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        archive_dir=_cfg_path(ctx, "FASCICOLI_ARCH", "./fascicoli/archivio"),
        studio_db=studio_db,
        carica_tutto=studio_db is None,
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
        tempi: dict[str, float] = {}
        if pec_cfg and getattr(pec_cfg, "imap_host", "") and getattr(pec_cfg, "indirizzo", ""):
            from pct.email_client import sincronizza_pec_e_fascicoli

            workflow = sincronizza_pec_e_fascicoli(
                gestione_email=gestore,
                gestione_fascicoli=_fascicoli_manager(runtime, gestore),
                config_pec=pec_cfg,
                state_path=_pec_state_path(runtime),
                limite=limite,
                incremental_only=incremental_only,
            )
            report = workflow.get("sync", {}) or {}
            log_esiti = workflow.get("auto_esiti", []) or []
            auto_summary = _auto_summary(gestore, log_esiti)
            poll_report = workflow.get("poll", {}) or poll_report
            tempi = dict(workflow.get("tempi", {}) or {})
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
                log_esiti = aggiorna_esiti_da_email(gestore, _fascicoli_manager(runtime, gestore))
                auto_summary = _auto_summary(gestore, log_esiti)

        inizio_inviati = monotonic()
        _sync_inviati(runtime, gestore)
        tempi["inviati"] = round(monotonic() - inizio_inviati, 2)
        errore = str(report.get("errore", "") or "").strip()
        _audit(runtime, "email.sincronizzata", f"Nuove: {report.get('nuove', 0)}, PST: {report.get('pst_trovate', 0)}")
        _log_tempi_sincronizzazione(tempi, report)
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
            "tempi": tempi,
            "riparazioni_rinviate": int(report.get("riparazioni_rinviate", 0) or 0),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


def _log_tempi_sincronizzazione(tempi: Mapping[str, float], report: Mapping[str, Any]) -> None:
    try:
        current_app.logger.info(
            "Sincronizzazione PEC: %s s in tutto (%s); nuove %s, riparazioni rinviate %s.",
            round(sum(tempi.values()), 2),
            ", ".join(f"{nome} {secondi}s" for nome, secondi in tempi.items()),
            report.get("nuove", 0),
            report.get("riparazioni_rinviate", 0),
        )
    except Exception:
        return


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
        fallimento = _FALLIMENTI.get(key) or {}
        if not force and fallimento and now < float(fallimento.get("riprova_dopo") or 0):
            return {"ok": True, "skipped": True, "reason": "attesa_dopo_errore", "result": {},
                    "errore_noto": str(fallimento.get("errore") or ""), "tentativi": int(fallimento.get("tentativi") or 0),
                    "riprova_tra_secondi": int(float(fallimento["riprova_dopo"]) - now)}
        acquired = lock.acquire(blocking=False)
    if not acquired:
        return {"ok": True, "skipped": True, "reason": "already_running", "result": {}}
    kwargs: dict[str, Any] = {}
    if limite is not None:
        kwargs["limite"] = max(1, int(limite))
    if incremental_only:
        kwargs["incremental_only"] = True
    esito: dict[str, Any] = {}
    app = current_app._get_current_object() if has_app_context() else None

    def esegui() -> None:
        try:
            if app is not None:
                with app.app_context():
                    esito["result"] = runner(runtime, **kwargs)
            else:
                esito["result"] = runner(runtime, **kwargs)
        except Exception as exc:  # pragma: no cover - i runner restituiscono già l'errore
            esito["result"] = {"ok": False, "errore": str(exc)}
        finally:
            with _STATE_LOCK:
                _LAST_ATTEMPT[key] = monotonic()
            lock.release()

    limite_tempo = _tempo_massimo_casella(runtime)
    lavoro = Thread(target=esegui, name=f"casella-{kind}-{runtime.tenant_label}", daemon=True)
    lavoro.start()
    lavoro.join(limite_tempo)
    if lavoro.is_alive():
        # La casella non risponde entro il tempo massimo: il giro prosegue; la sincronizzazione resta in sfondo
        # e tiene il proprio blocco, così il giro successivo la trova «già in corso» e non ne apre un'altra.
        result = {"ok": False, "in_sfondo": True,
                  "errore": f"Casella non sincronizzata entro {int(limite_tempo)} secondi: si riprova più tardi."}
    else:
        result = esito.get("result") or {"ok": False, "errore": "Sincronizzazione senza riscontro."}
    return {"ok": bool(result.get("ok", False)), "skipped": False, "reason": "", "result": _annota_fallimento(key, result)}


def _tempo_massimo_casella(ctx: MailboxRuntimeContext) -> float:
    valore = (ctx.config or {}).get("IUSENTRA_MAILBOX_SYNC_TIMEOUT_S") or os.getenv("IUSENTRA_MAILBOX_SYNC_TIMEOUT_S")
    try:
        return max(5.0, float(valore)) if valore else DEFAULT_MAILBOX_SYNC_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        return DEFAULT_MAILBOX_SYNC_TIMEOUT_SECONDS


def _errore_casella(result: Mapping[str, Any]) -> str:
    errore = str(result.get("errore") or result.get("sync_errore") or "").strip()
    if not errore and result.get("ok") is False:
        errore = "Sincronizzazione non riuscita."
    return errore


def _annota_fallimento(key: str, result: dict[str, Any]) -> dict[str, Any]:
    """Attesa crescente dopo gli errori; lo stesso errore ripetuto è marcato «già segnalato»."""
    errore = _errore_casella(result)
    with _STATE_LOCK:
        precedente = _FALLIMENTI.get(key) or {}
        if not errore:
            _FALLIMENTI.pop(key, None)
            return result
        tentativi = int(precedente.get("tentativi") or 0) + 1
        attesa = min(ATTESA_DOPO_ERRORE_MASSIMA, ATTESA_DOPO_ERRORE_SECONDI * (2 ** (tentativi - 1)))
        _FALLIMENTI[key] = {"errore": errore, "tentativi": tentativi, "riprova_dopo": monotonic() + attesa}
    annotato = dict(result)
    annotato["tentativi"] = tentativi
    annotato["riprova_tra_secondi"] = int(attesa)
    if precedente and str(precedente.get("errore") or "") == errore:
        annotato["gia_segnalato"] = True
    return annotato


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
