"""Bridge JSON operativo per la pagina React Impostazioni."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g, request

from web.services.react_impostazioni_backup import build_backup_settings_payload
from web.services.react_impostazioni_calendar import build_calendario_payload
from web.services.react_impostazioni_notifications import build_notifiche_payload
from web.services.react_impostazioni_payments import build_pagamenti_payload, update_pagamenti_settings


ALLOWED_SECTIONS = {
    "studio",
    "pec",
    "firma",
    "smtp",
    "whatsapp",
    "scheduler",
    "ai",
    "pagamenti",
    "notifiche",
    "backup",
    "calendari",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "si", "yes", "on"}


def _int(value: Any, default: int, *, minimum: int = 0, maximum: int = 65535) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _hhmm(value: Any, default: str) -> str:
    raw = _text(value, default)
    parts = raw.split(":")
    if len(parts) != 2:
        return default
    hour = _int(parts[0], 0, minimum=0, maximum=23)
    minute = _int(parts[1], 0, minimum=0, maximum=59)
    return f"{hour:02d}:{minute:02d}"


def _secret_state(value: str) -> dict[str, Any]:
    return {
        "present": bool(value),
        "label": "salvata" if value else "non salvata",
        "placeholder": "Lascia vuoto per mantenere il valore salvato" if value else "Inserisci valore riservato",
    }


def _runtime_loader(name: str) -> Any:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    loader = core_runtime.get(name)
    return loader if callable(loader) else None


def _missing_backup() -> Any:
    raise RuntimeError("Backup non disponibile in questo momento.")


def _file_label(value: str) -> str:
    return Path(value).name if value else ""


def _can(permission: str) -> bool:
    if _api_key_valida():
        return True
    user = g.get("utente_corrente")
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def _api_key_valida() -> bool:
    api_key = str(current_app.config.get("API_KEY", "") or "")
    return bool(api_key and request.headers.get("X-API-Key") == api_key)


def _gestore_config():
    from web.blueprints.impostazioni import _get_gestore

    return _get_gestore()


def _local_signer_payload() -> dict[str, Any]:
    from web.blueprints.impostazioni import _local_signer_meta

    meta = _local_signer_meta()
    return {
        **meta,
        "base_url": "http://127.0.0.1:27272",
        "restart_protocol": "iusentra-local-signer://restart",
        "downloads": {
            "windows": "/polisWeb/local-signer/setup/windows",
            "macos": "/polisWeb/local-signer/setup/macos",
            "linux": "/polisWeb/local-signer/setup/linux",
        },
    }


def _contracts(can_update: bool) -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "secrets_exposed": False,
        "sensitive_settings": "redacted_secret_values",
        "can_update": can_update,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/impostazioni.json",
    }


def _status(label: str, configured: bool, note: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "status": "configurata" if configured else "da completare",
        "tone": "success" if configured else "warning",
        "note": note,
    }


def _section_status(
    cfg: Any,
    pagamenti: dict[str, Any],
    notifiche: dict[str, Any],
    backup: dict[str, Any],
    calendari: dict[str, Any],
) -> list[dict[str, Any]]:
    backup_status = backup.get("status") or {}
    return [
        _status("Dati Studio", bool(cfg.studio.nome), "Anagrafica usata in atti, parcelle e depositi."),
        _status("PEC", bool(cfg.pec.indirizzo and cfg.pec.smtp_host and cfg.pec.imap_host), "Canale PCT e notifiche."),
        _status("Firma Digitale", cfg.firma.backend_firma_operativo_safe != "nessuno", "Local Signer gestisce la firma dal PC."),
        _status("Email SMTP", bool(cfg.smtp.host and cfg.smtp.username), "Posta ordinaria separata dalla PEC."),
        _status("WhatsApp", bool(cfg.whatsapp.twilio_sid or cfg.whatsapp.callmebot_key), "Promemoria e comunicazioni cliente."),
        _status("Scheduler", bool(cfg.scheduler.backup_abilitato or cfg.scheduler.wa_reminder_abilitato), "Backup e promemoria automatici."),
        _status("AI Locale", bool(cfg.ai.enabled), "Assistente attivo sul PC dello studio."),
        _status("Pagamenti", bool((pagamenti or {}).get("provider_attivi")), "Canali, bonifico e link parcella."),
        _status("Notifiche", bool((notifiche or {}).get("clienti_con_numero")), "Messaggi WhatsApp e promemoria."),
        _status("Backup", bool(backup_status.get("completed")), "Copie, verifica e scaricamento protetto."),
        _status("Calendari", bool((calendari or {}).get("profile_count") or (calendari or {}).get("feeds")), "Link, calendari collegati e sincronizzazione."),
    ]


def _payload_from_config(cfg: Any, *, can_update: bool) -> dict[str, Any]:
    from web.helpers import get_agenda as helper_get_agenda
    from web.helpers import get_calendar_sync as helper_get_calendar_sync
    from web.helpers import get_scadenziario as helper_get_scadenziario

    firma = cfg.firma
    get_agenda = _runtime_loader("get_agenda") or helper_get_agenda
    get_backup = _runtime_loader("get_backup") or _missing_backup
    get_calendar_sync = _runtime_loader("get_calendar_sync") or helper_get_calendar_sync
    get_scadenziario = _runtime_loader("get_scadenziario") or helper_get_scadenziario
    pagamenti = build_pagamenti_payload(_secret_state)
    notifiche = build_notifiche_payload(cfg)
    backup = build_backup_settings_payload(get_backup)
    calendari = build_calendario_payload(
        get_calendar_sync=get_calendar_sync,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
    )
    return {
        "ok": True,
        "source": "config_studio",
        "generated_at": _iso_now(),
        "contracts": _contracts(can_update),
        "permissions": {
            "can_read": True,
            "can_update": can_update,
            "can_test_connections": can_update,
            "can_configure_ai": _can("ai.configura") or can_update,
            "can_send_notifications": _can("messaggi.scrivi") or can_update,
            "can_manage_backup": _can("backup.esegui") or can_update,
            "can_manage_calendar": can_update,
        },
        "sections": _section_status(cfg, pagamenti, notifiche, backup, calendari),
        "local_signer": _local_signer_payload(),
        "studio": {
            "nome": cfg.studio.nome,
            "avvocato": cfg.studio.avvocato,
            "numero_iscrizione_albo": cfg.studio.numero_iscrizione_albo,
            "ordine_avvocati": cfg.studio.ordine_avvocati,
            "piva": cfg.studio.piva,
            "cf": cfg.studio.cf,
            "indirizzo": cfg.studio.indirizzo,
            "city": cfg.studio.city,
            "province": cfg.studio.province,
            "patron_name": cfg.studio.patron_name,
            "patron_day": cfg.studio.patron_day,
            "patron_month": cfg.studio.patron_month,
            "telefono": cfg.studio.telefono,
            "email": cfg.studio.email,
            "sito_web": cfg.studio.sito_web,
            "iban": cfg.studio.iban,
            "banca": cfg.studio.banca,
            "codice_fiscale_avvocato": cfg.studio.codice_fiscale_avvocato,
        },
        "pec": {
            "indirizzo": cfg.pec.indirizzo,
            "smtp_host": cfg.pec.smtp_host,
            "smtp_port": cfg.pec.smtp_port,
            "imap_host": cfg.pec.imap_host,
            "imap_port": cfg.pec.imap_port,
            "use_ssl": cfg.pec.use_ssl,
            "password": _secret_state(cfg.pec.password),
        },
        "firma": {
            "p12_path": firma.p12_path,
            "p12_label": _file_label(firma.p12_path),
            "cert_pem_path": firma.cert_pem_path,
            "cert_pem_label": _file_label(firma.cert_pem_path),
            "key_pem_path": firma.key_pem_path,
            "key_pem_label": _file_label(firma.key_pem_path),
            "pkcs11_library": firma.pkcs11_library,
            "pkcs11_slot": firma.pkcs11_slot,
            "pkcs11_label": firma.pkcs11_label,
            "cf_avvocato": firma.cf_avvocato,
            "backend_preferito": firma.backend_preferito_normalizzato,
            "backend_operativo": firma.backend_firma_operativo_safe,
            "pkcs11_canale_locale": firma.pkcs11_canale_locale,
            "visible_signature_mode": firma.visible_signature_mode,
            "password": _secret_state(firma.password),
            "key_pem_password": _secret_state(firma.key_pem_password),
        },
        "smtp": {
            "host": cfg.smtp.host,
            "port": cfg.smtp.port,
            "imap_host": cfg.smtp.imap_host,
            "imap_port": cfg.smtp.imap_port,
            "imap_use_ssl": cfg.smtp.imap_use_ssl,
            "username": cfg.smtp.username,
            "from_address": cfg.smtp.from_address,
            "from_name": cfg.smtp.from_name,
            "use_tls": cfg.smtp.use_tls,
            "password": _secret_state(cfg.smtp.password),
        },
        "whatsapp": {
            "twilio_sid": cfg.whatsapp.twilio_sid,
            "twilio_numero": cfg.whatsapp.twilio_numero,
            "twilio_token": _secret_state(cfg.whatsapp.twilio_token),
            "callmebot_key": _secret_state(cfg.whatsapp.callmebot_key),
        },
        "scheduler": {
            "backup_ora": cfg.scheduler.backup_ora,
            "wa_reminder_ora": cfg.scheduler.wa_reminder_ora,
            "backup_abilitato": cfg.scheduler.backup_abilitato,
            "wa_reminder_abilitato": cfg.scheduler.wa_reminder_abilitato,
        },
        "ai": {
            "enabled": cfg.ai.enabled,
            "base_url": cfg.ai.base_url,
            "auto_bootstrap": cfg.ai.auto_bootstrap,
            "chat_model": cfg.ai.chat_model or "__auto__",
            "embed_model": cfg.ai.embed_model or "__auto__",
            "keep_alive": cfg.ai.keep_alive,
            "auto_index_documents": cfg.ai.auto_index_documents,
        },
        "pagamenti": pagamenti,
        "notifiche": notifiche,
        "backup": backup,
        "calendari": calendari,
        "warnings": [],
    }


def build_react_impostazioni_payload() -> dict[str, Any]:
    cfg = _gestore_config().config
    return _payload_from_config(cfg, can_update=_can("admin.configura"))


def build_react_impostazioni_error_payload(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(False),
        "permissions": {"can_read": False, "can_update": False, "can_test_connections": False},
        "sections": [],
        "warnings": [{"code": "impostazioni_errore", "message": message}],
    }


def _audit(section: str) -> None:
    try:
        from web.helpers import get_utenti

        user = g.get("utente_corrente")
        get_utenti().registra_evento(
            f"impostazioni.{section}.aggiorna",
            id_utente=_text(getattr(user, "id", "")),
            username=_text(getattr(user, "username", "")),
            risorsa_tipo="config_studio",
            risorsa_id=section,
            dettagli=f"Sezione {section} aggiornata da pagina React.",
            ip=request.remote_addr or "",
        )
    except Exception as exc:
        current_app.logger.warning("Audit impostazioni React non registrato: %s", exc)


def _upload_path(files: Any, name: str, prefix: str, allowed: set[str], current: str) -> str:
    storage = files.get(name) if files is not None else None
    if storage and getattr(storage, "filename", ""):
        from web.blueprints.impostazioni import _salva_upload_firma

        return _salva_upload_firma(storage, prefix, allowed)
    return current


def update_react_impostazioni_section(section: str, payload: dict[str, Any], *, files: Any = None) -> dict[str, Any]:
    section = _text(section).lower()
    if section not in ALLOWED_SECTIONS:
        return {"ok": False, "message": "Sezione impostazioni non valida.", "errors": {"section": "Sezione non supportata."}}
    if not _can("admin.configura"):
        return {"ok": False, "message": "Permesso admin.configura richiesto.", "errors": {"permission": "Permesso insufficiente."}}

    from pct.config_studio import (
        ConfigDatiStudio,
        ConfigFirma,
        ConfigLocalAI,
        ConfigPEC,
        ConfigSMTP,
        ConfigScheduler,
        ConfigWhatsApp,
    )
    from visible_signature import normalize_visible_signature_mode
    from web.blueprints.impostazioni import _applica_ad_app

    manager = _gestore_config()
    cfg = manager.config
    data = payload or {}

    if section == "studio":
        cfg.studio = ConfigDatiStudio(
            nome=_text(data.get("nome")),
            avvocato=_text(data.get("avvocato")),
            numero_iscrizione_albo=_text(data.get("numero_iscrizione_albo")),
            ordine_avvocati=_text(data.get("ordine_avvocati")),
            piva=_text(data.get("piva")),
            cf=_text(data.get("cf")),
            indirizzo=_text(data.get("indirizzo")),
            city=_text(data.get("city")),
            province=_text(data.get("province")).upper()[:2],
            patron_name=_text(data.get("patron_name")),
            patron_day=_int(data.get("patron_day"), 0, minimum=0, maximum=31),
            patron_month=_int(data.get("patron_month"), 0, minimum=0, maximum=12),
            telefono=_text(data.get("telefono")),
            email=_text(data.get("email")),
            sito_web=_text(data.get("sito_web")),
            iban=_text(data.get("iban")),
            banca=_text(data.get("banca")),
            codice_fiscale_avvocato=_text(data.get("codice_fiscale_avvocato")).upper(),
        )
    elif section == "pec":
        password = _text(data.get("pec_password") or data.get("password"))
        cfg.pec = ConfigPEC(
            indirizzo=_text(data.get("indirizzo")),
            password=password or cfg.pec.password,
            smtp_host=_text(data.get("smtp_host"), cfg.pec.smtp_host),
            smtp_port=_int(data.get("smtp_port"), cfg.pec.smtp_port, minimum=1),
            imap_host=_text(data.get("imap_host"), cfg.pec.imap_host),
            imap_port=_int(data.get("imap_port"), cfg.pec.imap_port, minimum=1),
            use_ssl=_bool(data.get("use_ssl"), cfg.pec.use_ssl),
        )
    elif section == "firma":
        backend = _text(data.get("backend_preferito") or data.get("firma_formato") or "auto").lower()
        if backend not in {"auto", "pkcs11", "p12", "pem"}:
            backend = "auto"
        password = _text(data.get("password") or data.get("firma_password"))
        key_password = _text(data.get("key_pem_password") or data.get("firma_key_pem_password"))
        cfg.firma = ConfigFirma(
            p12_path=_upload_path(files, "firma_p12_file", "firma", {".p12", ".pfx"}, _text(data.get("p12_path"), cfg.firma.p12_path)),
            password=password or cfg.firma.password,
            cert_pem_path=_upload_path(files, "firma_cert_pem_file", "firma_cert", {".crt", ".cer", ".pem"}, _text(data.get("cert_pem_path"), cfg.firma.cert_pem_path)),
            key_pem_path=_upload_path(files, "firma_key_pem_file", "firma_key", {".key", ".pem"}, _text(data.get("key_pem_path"), cfg.firma.key_pem_path)),
            key_pem_password=key_password or cfg.firma.key_pem_password,
            pkcs11_library=_text(data.get("pkcs11_library")),
            pkcs11_slot=_text(data.get("pkcs11_slot")),
            pkcs11_label=_text(data.get("pkcs11_label")),
            cf_avvocato=_text(data.get("cf_avvocato") or data.get("firma_cf_avvocato")).upper(),
            backend_preferito=backend,
            visible_signature_mode=normalize_visible_signature_mode(_text(data.get("visible_signature_mode"), cfg.firma.visible_signature_mode)),
        )
    elif section == "smtp":
        password = _text(data.get("smtp_password") or data.get("password"))
        cfg.smtp = ConfigSMTP(
            host=_text(data.get("host")),
            port=_int(data.get("port"), cfg.smtp.port, minimum=1),
            imap_host=_text(data.get("imap_host")),
            imap_port=_int(data.get("imap_port"), cfg.smtp.imap_port, minimum=1),
            imap_use_ssl=_bool(data.get("imap_use_ssl"), cfg.smtp.imap_use_ssl),
            username=_text(data.get("username")),
            password=password or cfg.smtp.password,
            from_address=_text(data.get("from_address")),
            from_name=_text(data.get("from_name")),
            use_tls=_bool(data.get("use_tls"), cfg.smtp.use_tls),
        )
    elif section == "whatsapp":
        token = _text(data.get("twilio_token"))
        callmebot_key = _text(data.get("callmebot_key"))
        cfg.whatsapp = ConfigWhatsApp(
            twilio_sid=_text(data.get("twilio_sid")),
            twilio_token=token or cfg.whatsapp.twilio_token,
            twilio_numero=_text(data.get("twilio_numero")),
            callmebot_key=callmebot_key or cfg.whatsapp.callmebot_key,
        )
    elif section == "scheduler":
        cfg.scheduler = ConfigScheduler(
            backup_ora=_hhmm(data.get("backup_ora"), cfg.scheduler.backup_ora),
            wa_reminder_ora=_hhmm(data.get("wa_reminder_ora"), cfg.scheduler.wa_reminder_ora),
            backup_abilitato=_bool(data.get("backup_abilitato"), False),
            wa_reminder_abilitato=_bool(data.get("wa_reminder_abilitato"), False),
        )
    elif section == "ai":
        cfg.ai = ConfigLocalAI(
            enabled=_bool(data.get("enabled"), False),
            base_url=_text(data.get("base_url"), "http://127.0.0.1:11434/api/version"),
            auto_bootstrap=_bool(data.get("auto_bootstrap"), False),
            chat_model="" if _text(data.get("chat_model")) == "__auto__" else _text(data.get("chat_model")),
            embed_model="" if _text(data.get("embed_model")) == "__auto__" else _text(data.get("embed_model")),
            keep_alive=_text(data.get("keep_alive"), "10m") or "10m",
            auto_index_documents=_bool(data.get("auto_index_documents"), False),
        )
    elif section == "pagamenti":
        update_pagamenti_settings(data)
        _audit(section)
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Impostazioni pagamenti salvate.", "updated_section": section})
        return response
    elif section == "notifiche":
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Notifiche aggiornate.", "updated_section": section})
        return response
    elif section == "backup":
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Backup aggiornato.", "updated_section": section})
        return response
    elif section == "calendari":
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Calendari aggiornati.", "updated_section": section})
        return response

    manager.aggiorna(cfg)
    _applica_ad_app(cfg)
    _audit(section)
    response = _payload_from_config(cfg, can_update=True)
    response.update({"message": "Impostazioni salvate.", "updated_section": section})
    return response


def run_react_impostazioni_test(test_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("admin.configura"):
        return {"ok": False, "message": "Permesso admin.configura richiesto."}

    from pct.config_studio import (
        ConfigPEC,
        ConfigSMTP,
        ConfigWhatsApp,
        test_pec_imap,
        test_pec_smtp,
        test_smtp_email,
        test_smtp_imap,
        test_whatsapp,
    )

    cfg = _gestore_config().config
    data = payload or {}
    test_id = _text(test_id).lower()
    if test_id == "pec-smtp":
        result = test_pec_smtp(ConfigPEC(
            indirizzo=_text(data.get("indirizzo"), cfg.pec.indirizzo),
            password=_text(data.get("password"), cfg.pec.password) or cfg.pec.password,
            smtp_host=_text(data.get("smtp_host"), cfg.pec.smtp_host),
            smtp_port=_int(data.get("smtp_port"), cfg.pec.smtp_port, minimum=1),
            imap_host=cfg.pec.imap_host,
            imap_port=cfg.pec.imap_port,
            use_ssl=_bool(data.get("use_ssl"), cfg.pec.use_ssl),
        ))
    elif test_id == "pec-imap":
        result = test_pec_imap(ConfigPEC(
            indirizzo=_text(data.get("indirizzo"), cfg.pec.indirizzo),
            password=_text(data.get("password"), cfg.pec.password) or cfg.pec.password,
            smtp_host=cfg.pec.smtp_host,
            smtp_port=cfg.pec.smtp_port,
            imap_host=_text(data.get("imap_host"), cfg.pec.imap_host),
            imap_port=_int(data.get("imap_port"), cfg.pec.imap_port, minimum=1),
            use_ssl=_bool(data.get("use_ssl"), cfg.pec.use_ssl),
        ))
    elif test_id == "smtp":
        result = test_smtp_email(ConfigSMTP(
            host=_text(data.get("host"), cfg.smtp.host),
            port=_int(data.get("port"), cfg.smtp.port, minimum=1),
            username=_text(data.get("username"), cfg.smtp.username),
            password=_text(data.get("password"), cfg.smtp.password) or cfg.smtp.password,
            from_address=cfg.smtp.from_address,
            from_name=cfg.smtp.from_name,
            use_tls=_bool(data.get("use_tls"), cfg.smtp.use_tls),
        ))
    elif test_id == "smtp-imap":
        result = test_smtp_imap(ConfigSMTP(
            host=cfg.smtp.host,
            port=cfg.smtp.port,
            imap_host=_text(data.get("imap_host"), cfg.smtp.imap_host),
            imap_port=_int(data.get("imap_port"), cfg.smtp.imap_port, minimum=1),
            imap_use_ssl=_bool(data.get("imap_use_ssl"), cfg.smtp.imap_use_ssl),
            username=_text(data.get("username"), cfg.smtp.username),
            password=_text(data.get("password"), cfg.smtp.password) or cfg.smtp.password,
            from_address=cfg.smtp.from_address,
            from_name=cfg.smtp.from_name,
            use_tls=cfg.smtp.use_tls,
        ))
    elif test_id == "whatsapp":
        result = test_whatsapp(ConfigWhatsApp(
            twilio_sid=_text(data.get("twilio_sid"), cfg.whatsapp.twilio_sid),
            twilio_token=_text(data.get("twilio_token"), cfg.whatsapp.twilio_token) or cfg.whatsapp.twilio_token,
            twilio_numero=_text(data.get("twilio_numero"), cfg.whatsapp.twilio_numero),
            callmebot_key=_text(data.get("callmebot_key"), cfg.whatsapp.callmebot_key) or cfg.whatsapp.callmebot_key,
        ))
    else:
        return {"ok": False, "message": "Test non supportato."}
    return {"ok": bool(result.get("ok")), "message": _text(result.get("messaggio"), "Test completato.")}


def build_react_impostazioni_ai_status() -> dict[str, Any]:
    try:
        from lex.providers.local_ai_service import get_local_ai_service

        return {"ok": True, "status_payload": get_local_ai_service().health_snapshot()}
    except Exception as exc:
        current_app.logger.exception("Errore stato AI locale React: %s", exc)
        return {"ok": False, "message": "AI locale non disponibile.", "status_payload": {"runtime": {"status": "error"}}}


def bootstrap_react_impostazioni_ai(force: bool = False) -> dict[str, Any]:
    if not (_can("ai.configura") or _can("admin.configura")):
        return {"ok": False, "message": "Permesso ai.configura richiesto."}
    try:
        from lex.providers.local_ai_service import get_local_ai_service
        from lex.providers.ollama_runtime import refresh_live_ollama_runtime

        service = get_local_ai_service()
        result = service.bootstrap_runtime(force=force)
        refresh_live_ollama_runtime()
        return {"ok": True, "result": result, "status_payload": service.health_snapshot()}
    except Exception as exc:
        current_app.logger.exception("Errore bootstrap AI locale React: %s", exc)
        return {"ok": False, "message": "Preparazione AI locale non completata.", "status_payload": {"runtime": {"status": "error"}}}
