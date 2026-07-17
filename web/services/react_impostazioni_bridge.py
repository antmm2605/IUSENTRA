"""Bridge JSON operativo per la pagina React Impostazioni."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g, request
from web.services.tenant_api_auth import api_key_valid_for_request

from web.services.react_impostazioni_backup import build_backup_settings_payload
from web.services.react_impostazioni_calendar import build_calendario_payload
from web.services.react_impostazioni_notifications import build_notifiche_payload
from web.services.react_impostazioni_payments import build_pagamenti_payload, update_pagamenti_settings
from web.services.lex_dataset_training_status import build_lex_dataset_training_status


ALLOWED_SECTIONS = {
    "studio",
    "fatturazione",
    "pec",
    "firma",
    "smtp",
    "whatsapp",
    "scheduler",
    "ai",
    "sdi",
    "pagamenti",
    "notifiche",
    "backup",
    "calendari",
}

_FATTURAZIONE_REGIMI = {"RF01", "RF02", "RF19"}
_FATTURAZIONE_METODI = {"Bonifico", "Contanti", "Assegno", "Carta di credito", "PayPal"}
_FATTURAZIONE_ALIQUOTE_IVA = {4.0, 5.0, 10.0, 22.0}


SDI_OFFICIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "id": "fatturapa_specifiche_formato",
        "label": "Specifiche tecniche formato FatturaPA 1.3.1",
        "url": "https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.3.1/Specifiche_tecniche_del_formato_FatturaPA_V1.3.1.pdf",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/fatturapa-specifiche-formato-v1-3-1.pdf",
        "scope": "Formato XML e regole tecniche della fattura elettronica.",
    },
    {
        "id": "agenzia_entrate_guida_fatturazione_elettronica",
        "label": "Agenzia Entrate - guida fatturazione elettronica",
        "url": "https://www.agenziaentrate.gov.it/portale/guida-fatturazione-elettronica",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/agenzia-entrate-guida-fatturazione-elettronica.html",
        "scope": "Invio tramite SdI, ricevute, scarto e monitoraggio dei file trasmessi.",
    },
    {
        "id": "fatturapa_sdicoop_trasmissione",
        "label": "FatturaPA - SDICoop trasmissione",
        "url": "https://www.fatturapa.gov.it/export/fatturazione/sdi/ws/trasmissione/v1.1/SDICoop_trasmissione_v1.1.pdf",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/fatturapa-sdicoop-trasmissione-v1-1.pdf",
        "scope": "Trasmissione tramite canale accreditato.",
    },
    {
        "id": "fatturapa_sdiftp_trasmissione",
        "label": "FatturaPA - SdIFtp trasmissione",
        "url": "https://www.fatturapa.gov.it/export/documenti/sdi/Specifiche_tecniche_SdIFtp_v4.2.pdf",
        "localPath": "docs/specs/ministero/fonti_ufficiali/2026-06-02/fatturapa-sdiftp-specifiche-v4-2.pdf",
        "scope": "Trasmissione tramite servizio FTP accreditato.",
    },
)


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


def _float(value: Any, default: float, *, minimum: float = 0.0, maximum: float = 100.0) -> float:
    try:
        parsed = float(str(value).strip().replace(",", "."))
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


def _parse_iso_date(value: Any) -> date | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _format_date_it(value: Any) -> str:
    parsed = _parse_iso_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def _days_until(value: Any, *, today: date | None = None) -> int | None:
    parsed = _parse_iso_date(value)
    if not parsed:
        return None
    return (parsed - (today or date.today())).days


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
    return api_key_valid_for_request()


def _gestore_config():
    from web.blueprints.impostazioni import _get_gestore

    return _get_gestore()


def resolve_react_fatturazione_defaults(cfg: Any) -> dict[str, Any]:
    """Risolve i default fiscali dal backend SQL tenant e usa il JSON solo come mirror."""

    source = getattr(cfg, "fatturazione", None)
    fallback = {
        "regime_fiscale": _text(getattr(source, "regime_fiscale", "RF01"), "RF01").upper(),
        "applica_iva": bool(getattr(source, "applica_iva", True)),
        "applica_cassa": bool(getattr(source, "applica_cassa", True)),
        "applica_ritenuta": bool(getattr(source, "applica_ritenuta", False)),
        "applica_bollo": bool(getattr(source, "applica_bollo", False)),
        "aliquota_iva": float(getattr(source, "aliquota_iva", 22.0) or 22.0),
        "percentuale_spese_generali": float(getattr(source, "percentuale_spese_generali", 15.0) or 0.0),
        "metodo_pagamento": _text(getattr(source, "metodo_pagamento", "Bonifico"), "Bonifico"),
        "giorni_scadenza": int(getattr(source, "giorni_scadenza", 30) or 0),
    }
    try:
        from pct.impostazioni_config_repository import load_settings_config_section
        from web.blueprints.impostazioni import _studio_config_path
        from web.services.storage_runtime import get_request_studio_db

        studio_db = get_request_studio_db(_studio_config_path())
        stored = load_settings_config_section(studio_db, "fatturazione")
    except Exception:
        stored = {}
    raw = {**fallback, **stored}
    regime = _text(raw.get("regime_fiscale"), "RF01").upper()
    if regime not in _FATTURAZIONE_REGIMI:
        regime = "RF01"
    metodo = _text(raw.get("metodo_pagamento"), "Bonifico")
    if metodo not in _FATTURAZIONE_METODI:
        metodo = "Bonifico"
    applica_iva = _bool(raw.get("applica_iva"), True) and regime not in {"RF02", "RF19"}
    aliquota_iva = _float(raw.get("aliquota_iva"), 22.0)
    if aliquota_iva not in _FATTURAZIONE_ALIQUOTE_IVA:
        aliquota_iva = 22.0
    return {
        "regime_fiscale": regime,
        "applica_iva": applica_iva,
        "applica_cassa": _bool(raw.get("applica_cassa"), True),
        "applica_ritenuta": _bool(raw.get("applica_ritenuta"), False),
        "applica_bollo": _bool(raw.get("applica_bollo"), False),
        "aliquota_iva": aliquota_iva,
        "percentuale_spese_generali": _float(raw.get("percentuale_spese_generali"), 15.0),
        "metodo_pagamento": metodo,
        "giorni_scadenza": _int(raw.get("giorni_scadenza"), 30, minimum=0, maximum=365),
    }


def _fatturazione_proforma_summary() -> dict[str, int]:
    try:
        from web.helpers import get_fatturazione as helper_get_fatturazione

        loader = _runtime_loader("get_fatturazione") or helper_get_fatturazione
        records = list(loader().tutte())
    except Exception:
        return {"totali": 0, "aggiornabili": 0, "escluse": 0}

    totali = 0
    aggiornabili = 0
    for record in records:
        personalized = getattr(record, "dati_personalizzati", {}) or {}
        document = personalized.get("document") if isinstance(personalized, dict) else {}
        if not isinstance(document, dict) or _text(document.get("documento_operativo")).upper() != "PROFORMA":
            continue
        totali += 1
        stato = _text(getattr(getattr(record, "stato", ""), "value", getattr(record, "stato", ""))).upper()
        if stato != "ANNULLATA" and not _text(getattr(record, "sdi_data_invio", "")):
            aggiornabili += 1
    return {"totali": totali, "aggiornabili": aggiornabili, "escluse": totali - aggiornabili}


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
        _status("Fatturazione", True, "Regole fiscali predefinite per proforme e fatture."),
        _status("PEC", bool(cfg.pec.indirizzo and cfg.pec.smtp_host and cfg.pec.imap_host), "Canale PCT e notifiche."),
        _status("Firma Digitale", cfg.firma.backend_firma_operativo_safe != "nessuno", "Local Signer gestisce la firma dal PC."),
        _status("Email SMTP", bool(cfg.smtp.host and cfg.smtp.username), "Posta ordinaria separata dalla PEC."),
        _status("WhatsApp", bool(cfg.whatsapp.twilio_sid or cfg.whatsapp.callmebot_key), "Promemoria e comunicazioni cliente."),
        _status("Scheduler", bool(cfg.scheduler.backup_abilitato or cfg.scheduler.wa_reminder_abilitato), "Backup e promemoria automatici."),
        _status("AI Locale", bool(cfg.ai.enabled), "Assistente attivo sul PC dello studio."),
        _status("Canali SdI", bool(getattr(cfg.sdi, "canale_configurato", False)), "FatturaPA tramite portale, intermediario o canale accreditato."),
        _status("Pagamenti", bool((pagamenti or {}).get("provider_attivi")), "Canali, bonifico e link parcella."),
        _status("Notifiche", bool((notifiche or {}).get("clienti_con_numero")), "Messaggi WhatsApp e promemoria."),
        _status("Backup", bool(backup_status.get("completed")), "Copie, verifica e scaricamento protetto."),
        _status("Calendari", bool((calendari or {}).get("profile_count") or (calendari or {}).get("feeds")), "Link, calendari collegati e sincronizzazione."),
    ]


def _sdi_warnings(cfg: Any) -> list[dict[str, str]]:
    sdi = getattr(cfg, "sdi", None)
    if sdi is None:
        return []
    if not bool(getattr(sdi, "abilitato", False)):
        return []
    if bool(getattr(sdi, "auto_invio_abilitato", False)) and not bool(getattr(sdi, "canale_configurato", False)):
        return [
            {
                "code": "sdi_auto_senza_canale",
                "message": (
                    "Invio automatico SdI non attivo: configura prima intermediario o canale accreditato. "
                    "IUSENTRA può preparare XML e registrare identificativo/esiti, ma non inventa un canale accreditato."
                ),
            }
        ]
    if getattr(sdi, "modalita_normalizzata", "manuale") == "manuale":
        return [
            {
                "code": "sdi_modalita_manuale",
                "message": (
                    "Canale SdI in modalità manuale: la trasmissione resta su portale o intermediario esterno; "
                    "qui si registrano XML, identificativo e ricevute."
                ),
            }
        ]
    return []


def _operational_settings_payloads(cfg: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    from web.helpers import get_agenda as helper_get_agenda
    from web.helpers import get_calendar_sync as helper_get_calendar_sync
    from web.helpers import get_scadenziario as helper_get_scadenziario

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
    return pagamenti, notifiche, backup, calendari


def _extra_settings_sections(
    pagamenti: dict[str, Any],
    notifiche: dict[str, Any],
    backup: dict[str, Any],
    calendari: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pagamenti": pagamenti,
        "notifiche": notifiche,
        "backup": backup,
        "calendari": calendari,
    }


def _sync_settings_config_snapshot(cfg: Any, extra_sections: dict[str, Any] | None = None) -> int:
    from web.blueprints.impostazioni import _salva_snapshot_sql_impostazioni

    return _salva_snapshot_sql_impostazioni(cfg, extra_sections=extra_sections)


def _payload_from_config(cfg: Any, *, can_update: bool) -> dict[str, Any]:
    firma = cfg.firma
    certificato_scadenza = _text(getattr(firma, "certificato_scadenza", ""))
    certificato_scadenza_it = _text(getattr(firma, "certificato_scadenza_it", "")) or _format_date_it(certificato_scadenza)
    certificato_giorni = _days_until(certificato_scadenza)
    certificato_preavviso = _int(
        getattr(firma, "certificato_giorni_preavviso", 20),
        20,
        minimum=1,
        maximum=365,
    )
    pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
    fatturazione = resolve_react_fatturazione_defaults(cfg)
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
            "qualifica_professionale": getattr(cfg.studio, "qualifica_professionale", ""),
            "numero_iscrizione_albo": cfg.studio.numero_iscrizione_albo,
            "ordine_avvocati": cfg.studio.ordine_avvocati,
            "piva": cfg.studio.piva,
            "cf": cfg.studio.cf,
            "indirizzo": cfg.studio.indirizzo,
            "cap": getattr(cfg.studio, "cap", ""),
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
            "bic_swift": getattr(cfg.studio, "bic_swift", "") or getattr(cfg.fatturazione, "bic_swift", ""),
            "codice_fiscale_avvocato": cfg.studio.codice_fiscale_avvocato,
        },
        "fatturazione": fatturazione,
        "fatturazione_stats": _fatturazione_proforma_summary(),
        "pec": {
            "indirizzo": cfg.pec.indirizzo,
            "username": getattr(cfg.pec, "username", ""),
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
            "certificato_thumbprint": _text(getattr(firma, "certificato_thumbprint", "")),
            "certificato_soggetto": _text(getattr(firma, "certificato_soggetto", "")),
            "certificato_codice_fiscale": _text(getattr(firma, "certificato_codice_fiscale", "")),
            "certificato_emittente": _text(getattr(firma, "certificato_emittente", "")),
            "certificato_scadenza": certificato_scadenza,
            "certificato_scadenza_it": certificato_scadenza_it,
            "certificato_ultimo_controllo": _text(getattr(firma, "certificato_ultimo_controllo", "")),
            "certificato_giorni_preavviso": certificato_preavviso,
            "certificato_giorni_scadenza": certificato_giorni if certificato_giorni is not None else "",
            "certificato_avviso_login": bool(
                certificato_giorni is not None and certificato_giorni <= certificato_preavviso
            ),
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
            "lex_dataset_status": build_lex_dataset_training_status(
                ai_enabled=cfg.ai.enabled,
                auto_index_documents=cfg.ai.auto_index_documents,
            ),
        },
        "sdi": {
            "abilitato": cfg.sdi.abilitato,
            "modalita": cfg.sdi.modalita_normalizzata,
            "nome_intermediario": cfg.sdi.nome_intermediario,
            "codice_canale": cfg.sdi.codice_canale,
            "indirizzo_servizio": cfg.sdi.endpoint_trasmissione,
            "endpoint_trasmissione": cfg.sdi.endpoint_trasmissione,
            "username": cfg.sdi.username,
            "password": _secret_state(cfg.sdi.password),
            "pec_notifiche": cfg.sdi.pec_notifiche,
            "email_commercialista": getattr(cfg.sdi, "email_commercialista", ""),
            "pec_commercialista": getattr(cfg.sdi, "pec_commercialista", ""),
            "nome_commercialista": getattr(cfg.sdi, "nome_commercialista", ""),
            "auto_invio_abilitato": cfg.sdi.auto_invio_abilitato,
            "note": cfg.sdi.note,
            "canale_configurato": cfg.sdi.canale_configurato,
            "fonti": list(SDI_OFFICIAL_SOURCES),
            "presidio": (
                "Invio automatico disponibile solo con canale/intermediario reale configurato."
                if cfg.sdi.canale_configurato
                else "IUSENTRA prepara XML FatturaPA e registra identificativo/esiti; la trasmissione resta esterna finché manca un canale reale."
            ),
        },
        "pagamenti": pagamenti,
        "notifiche": notifiche,
        "backup": backup,
        "calendari": calendari,
        "warnings": _sdi_warnings(cfg),
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


def update_react_impostazioni_firma_certificato(payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("admin.configura"):
        return {"ok": False, "message": "Permesso admin.configura richiesto.", "errors": {"permission": "Permesso insufficiente."}}

    data = payload or {}
    parsed = _parse_iso_date(
        data.get("scadenza")
        or data.get("certificato_scadenza")
        or data.get("expiry")
        or data.get("expires_at")
    )
    if not parsed:
        return {
            "ok": False,
            "message": "Scadenza certificato non leggibile. Ripeti la verifica dal Local Signer.",
            "errors": {"certificato_scadenza": "Data scadenza mancante o non valida."},
        }

    from pct.config_studio import ConfigFirma
    from web.blueprints.impostazioni import _applica_ad_app

    manager = _gestore_config()
    cfg = manager.config
    old = cfg.firma
    certificato_cf = _text(data.get("codice_fiscale") or data.get("certificato_codice_fiscale")).upper()
    cfg.firma = ConfigFirma(
        p12_path=old.p12_path,
        password=old.password,
        cert_pem_path=old.cert_pem_path,
        key_pem_path=old.key_pem_path,
        key_pem_password=old.key_pem_password,
        pkcs11_library=old.pkcs11_library,
        pkcs11_slot=old.pkcs11_slot,
        pkcs11_label=old.pkcs11_label,
        cf_avvocato=old.cf_avvocato or certificato_cf,
        backend_preferito=old.backend_preferito,
        visible_signature_mode=old.visible_signature_mode,
        certificato_thumbprint=_text(data.get("thumbprint") or data.get("certificato_thumbprint")),
        certificato_soggetto=_text(data.get("soggetto") or data.get("subject") or data.get("certificato_soggetto")),
        certificato_codice_fiscale=certificato_cf,
        certificato_emittente=_text(data.get("emittente") or data.get("issuer") or data.get("certificato_emittente")),
        certificato_scadenza=parsed.isoformat(),
        certificato_scadenza_it=_format_date_it(parsed.isoformat()),
        certificato_ultimo_controllo=_iso_now(),
        certificato_giorni_preavviso=_int(
            data.get("giorni_preavviso") or data.get("certificato_giorni_preavviso") or getattr(old, "certificato_giorni_preavviso", 20),
            20,
            minimum=1,
            maximum=365,
        ),
    )

    manager.aggiorna(cfg)
    _applica_ad_app(cfg)
    pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
    _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
    _audit("firma_certificato")
    response = _payload_from_config(cfg, can_update=True)
    response.update({"message": "Scadenza certificato firma salvata.", "updated_section": "firma"})
    return response


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
        ConfigFatturazione,
        ConfigFirma,
        ConfigLocalAI,
        ConfigPEC,
        ConfigSDI,
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
        from pct.studio_address import normalize_bic_swift, normalize_studio_location

        location = normalize_studio_location(
            indirizzo=data.get("indirizzo"),
            cap=data.get("cap"),
            city=data.get("city"),
            province=data.get("province"),
        )
        bic_swift = normalize_bic_swift(data.get("bic_swift"))
        errors: dict[str, str] = {}
        if _text(data.get("cap")) and len(location["cap"]) != 5:
            errors["cap"] = "Inserisci un CAP italiano di 5 cifre."
        if bic_swift and len(bic_swift) not in {8, 11}:
            errors["bic_swift"] = "Inserisci un BIC/SWIFT di 8 o 11 caratteri."
        if errors:
            return {"ok": False, "message": "Controlla i dati dello studio.", "errors": errors}
        cfg.studio = ConfigDatiStudio(
            nome=_text(data.get("nome")),
            avvocato=_text(data.get("avvocato")),
            qualifica_professionale=_text(data.get("qualifica_professionale")),
            numero_iscrizione_albo=_text(data.get("numero_iscrizione_albo")),
            ordine_avvocati=_text(data.get("ordine_avvocati")),
            piva=_text(data.get("piva")),
            cf=_text(data.get("cf")),
            indirizzo=location["indirizzo"],
            cap=location["cap"],
            city=location["city"],
            province=location["province"],
            patron_name=_text(data.get("patron_name")),
            patron_day=_int(data.get("patron_day"), 0, minimum=0, maximum=31),
            patron_month=_int(data.get("patron_month"), 0, minimum=0, maximum=12),
            telefono=_text(data.get("telefono")),
            email=_text(data.get("email")),
            sito_web=_text(data.get("sito_web")),
            iban=_text(data.get("iban")),
            banca=_text(data.get("banca")),
            bic_swift=bic_swift,
            codice_fiscale_avvocato=_text(data.get("codice_fiscale_avvocato")).upper(),
        )
    elif section == "fatturazione":
        regime = _text(data.get("regime_fiscale"), "RF01").upper()
        metodo = _text(data.get("metodo_pagamento"), "Bonifico")
        errors: dict[str, str] = {}
        if regime not in _FATTURAZIONE_REGIMI:
            errors["regime_fiscale"] = "Seleziona un regime fiscale valido."
        if metodo not in _FATTURAZIONE_METODI:
            errors["metodo_pagamento"] = "Seleziona una modalità di pagamento valida."
        raw_percentuale = _text(data.get("percentuale_spese_generali"), "15").replace(",", ".")
        try:
            percentuale = float(raw_percentuale)
        except ValueError:
            errors["percentuale_spese_generali"] = "Inserisci una percentuale valida."
            percentuale = 15.0
        if not 0 <= percentuale <= 100:
            errors["percentuale_spese_generali"] = "Inserisci una percentuale compresa tra 0 e 100."
        raw_giorni = _text(data.get("giorni_scadenza"), "30")
        try:
            giorni_scadenza = int(raw_giorni)
        except ValueError:
            errors["giorni_scadenza"] = "Inserisci un numero intero di giorni."
            giorni_scadenza = 30
        if not 0 <= giorni_scadenza <= 365:
            errors["giorni_scadenza"] = "Inserisci un valore compreso tra 0 e 365 giorni."
        raw_aliquota = _text(data.get("aliquota_iva"), "22").replace(",", ".")
        try:
            aliquota_iva = float(raw_aliquota)
        except ValueError:
            aliquota_iva = 22.0
            errors["aliquota_iva"] = "Seleziona un’aliquota IVA valida."
        if aliquota_iva not in _FATTURAZIONE_ALIQUOTE_IVA:
            errors["aliquota_iva"] = "Seleziona un’aliquota IVA tra 4%, 5%, 10% e 22%."
        if errors:
            return {"ok": False, "message": "Controlla le impostazioni di fatturazione.", "errors": errors}
        cfg.fatturazione = ConfigFatturazione(
            regime_fiscale=regime,
            applica_iva=_bool(data.get("applica_iva"), True),
            applica_cassa=_bool(data.get("applica_cassa"), True),
            applica_ritenuta=_bool(data.get("applica_ritenuta"), False),
            applica_bollo=_bool(data.get("applica_bollo"), False),
            aliquota_iva=aliquota_iva,
            percentuale_spese_generali=percentuale,
            metodo_pagamento=metodo,
            giorni_scadenza=giorni_scadenza,
        )
    elif section == "pec":
        password = _text(data.get("pec_password") or data.get("password"))
        cfg.pec = ConfigPEC(
            indirizzo=_text(data.get("indirizzo")),
            username=_text(data.get("username")),
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
            certificato_thumbprint=_text(getattr(cfg.firma, "certificato_thumbprint", "")),
            certificato_soggetto=_text(getattr(cfg.firma, "certificato_soggetto", "")),
            certificato_codice_fiscale=_text(getattr(cfg.firma, "certificato_codice_fiscale", "")),
            certificato_emittente=_text(getattr(cfg.firma, "certificato_emittente", "")),
            certificato_scadenza=_text(getattr(cfg.firma, "certificato_scadenza", "")),
            certificato_scadenza_it=_text(getattr(cfg.firma, "certificato_scadenza_it", "")),
            certificato_ultimo_controllo=_text(getattr(cfg.firma, "certificato_ultimo_controllo", "")),
            certificato_giorni_preavviso=_int(getattr(cfg.firma, "certificato_giorni_preavviso", 20), 20, minimum=1, maximum=365),
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
    elif section == "sdi":
        modalita_sdi = _text(data.get("modalita"), cfg.sdi.modalita).lower()
        if modalita_sdi not in {"manuale", "intermediario", "canale_accreditato"}:
            modalita_sdi = "manuale"
        password = _text(data.get("sdi_password") or data.get("password"))
        cfg.sdi = ConfigSDI(
            abilitato=_bool(data.get("abilitato"), cfg.sdi.abilitato),
            modalita=modalita_sdi,
            nome_intermediario=_text(data.get("nome_intermediario")),
            codice_canale=_text(data.get("codice_canale")),
            endpoint_trasmissione=_text(
                data.get("indirizzo_servizio") or data.get("endpoint_trasmissione"),
                cfg.sdi.endpoint_trasmissione,
            ),
            username=_text(data.get("username")),
            password=password or cfg.sdi.password,
            pec_notifiche=_text(data.get("pec_notifiche")),
            email_commercialista=_text(data.get("email_commercialista")),
            pec_commercialista=_text(data.get("pec_commercialista")),
            nome_commercialista=_text(data.get("nome_commercialista")),
            auto_invio_abilitato=_bool(data.get("auto_invio_abilitato"), cfg.sdi.auto_invio_abilitato),
            note=_text(data.get("note")),
        )
    elif section == "pagamenti":
        update_pagamenti_settings(data)
        pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
        _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
        _audit(section)
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Impostazioni pagamenti salvate.", "updated_section": section})
        return response
    elif section == "notifiche":
        pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
        _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Notifiche aggiornate.", "updated_section": section})
        return response
    elif section == "backup":
        pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
        _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Backup aggiornato.", "updated_section": section})
        return response
    elif section == "calendari":
        pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
        _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
        response = _payload_from_config(cfg, can_update=True)
        response.update({"message": "Calendari aggiornati.", "updated_section": section})
        return response

    manager.aggiorna(cfg)
    _applica_ad_app(cfg)
    pagamenti, notifiche, backup, calendari = _operational_settings_payloads(cfg)
    _sync_settings_config_snapshot(cfg, _extra_settings_sections(pagamenti, notifiche, backup, calendari))
    _audit(section)
    response = _payload_from_config(cfg, can_update=True)
    message = "Impostazioni di fatturazione salvate." if section == "fatturazione" else "Impostazioni salvate."
    response.update({"message": message, "updated_section": section})
    return response


def apply_react_impostazioni_fatturazione_to_proformas(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    from web.helpers import get_fatturazione as helper_get_fatturazione
    from web.helpers import get_pagamenti as helper_get_pagamenti
    from web.helpers import get_utenti
    from web.services.react_fatturazione_archive_actions import apply_react_fatturazione_defaults_to_proformas
    from web.services.react_fatturazione_bridge import build_fatturazione_runtime_config

    cfg = _gestore_config().config
    defaults = resolve_react_fatturazione_defaults(cfg)
    get_fatturazione = _runtime_loader("get_fatturazione") or helper_get_fatturazione
    get_pagamenti = _runtime_loader("get_pagamenti") or helper_get_pagamenti
    try:
        pagamenti_config = getattr(get_pagamenti(), "config", None)
    except Exception:
        pagamenti_config = None
    studio_config = build_fatturazione_runtime_config(
        cfg,
        pagamenti_config,
        fatturazione_defaults=defaults,
    )
    return apply_react_fatturazione_defaults_to_proformas(
        get_fatturazione=get_fatturazione,
        get_utenti=get_utenti,
        current_user=g.get("utente_corrente"),
        defaults=defaults,
        studio_config=studio_config,
        confirm=(payload or {}).get("confirm") is True,
        ip_address=request.remote_addr or "",
    )


def run_react_impostazioni_test(test_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not _can("admin.configura"):
        return {"ok": False, "message": "Permesso admin.configura richiesto."}

    from pct.config_studio import (
        ConfigPEC,
        ConfigSMTP,
        ConfigWhatsApp,
        test_pec_imap,
        test_smtp_email,
        test_smtp_imap,
        test_whatsapp,
    )

    cfg = _gestore_config().config
    data = payload or {}
    test_id = _text(test_id).lower()
    if test_id == "pec-smtp":
        return {
            "ok": False,
            "local_signer_required": True,
            "message": (
                "La verifica invio PEC si esegue dal PC in uso tramite "
                "IUSENTRA Local Signer. Apri Impostazioni sul computer dello studio "
                "e premi Verifica invio PEC."
            ),
        }
    elif test_id == "pec-imap":
        result = test_pec_imap(ConfigPEC(
            indirizzo=_text(data.get("indirizzo"), cfg.pec.indirizzo),
            username=_text(data.get("username"), getattr(cfg.pec, "username", "")),
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
