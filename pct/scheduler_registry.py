"""Registro persistente per pianificazioni e agenti delegati IUSENTRA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from uuid import uuid4

from pct.legal_update_autofetch import (
    LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
    LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
    is_legal_update_progressive_step1_source,
    legal_update_progressive_exclusion_reason,
)


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_DB_NAME = "scheduler_registry.sqlite"
EXCLUSIVE_MANUAL_MAINTENANCE_JOB_IDS = frozenset(
    {
        "utf8_integrity_nightly",
        "operational_crash_morning",
        "operational_crash_midday",
        "operational_crash_evening",
        "operational_backup_nightly",
    }
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).strftime(ISO_FMT)


def _parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in (ISO_FMT, "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = _parse_dt(started_at)
    finish = _parse_dt(finished_at)
    if not start or not finish:
        return 0
    return max(0, int((finish - start).total_seconds() * 1000))


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload if payload is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_loads(payload: Any, default: Any = None) -> Any:
    if not payload:
        return {} if default is None else default
    try:
        return json.loads(str(payload))
    except (TypeError, ValueError):
        return {} if default is None else default


def _slug(value: str, fallback: str = "job") -> str:
    raw = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", raw).strip("_")
    return cleaned or fallback


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "si", "attivo"}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_minute(value: Any, default: str = "0") -> str:
    raw = str(value if value is not None else default).strip()
    if not raw:
        return default
    if re.fullmatch(r"\*/([1-9]\d?)", raw):
        interval = int(raw[2:])
        return raw if 1 <= interval <= 59 else default
    if re.fullmatch(r"\d{1,2}(,\d{1,2})*", raw):
        parts = [int(part) for part in raw.split(",")]
        return raw if all(0 <= part <= 59 for part in parts) else default
    return default


def _safe_hour(value: Any, default: str = "") -> str:
    raw = str(value if value is not None else default).strip()
    if not raw:
        return default
    if re.fullmatch(r"\*/([1-9]\d?)", raw):
        interval = int(raw[2:])
        return raw if 1 <= interval <= 23 else default
    if re.fullmatch(r"\d{1,2}(,\d{1,2})*", raw):
        parts = [int(part) for part in raw.split(",")]
        return raw if all(0 <= part <= 23 for part in parts) else default
    return default


def _hhmm(value: object, default: str) -> tuple[str, str]:
    raw = str(value or default).strip()
    try:
        hour, minute = raw.split(":", 1)
        return _safe_hour(hour, default.split(":", 1)[0]), _safe_minute(minute, default.split(":", 1)[1])
    except (TypeError, ValueError):
        return default.split(":", 1)[0], default.split(":", 1)[1]


def _runtime_registry_db_path(config: dict[str, Any] | None = None) -> Path:
    cfg = config or {}
    explicit = (
        cfg.get("SCHEDULER_REGISTRY_DB")
        or cfg.get("IUSENTRA_SCHEDULER_REGISTRY_DB")
        or os.getenv("IUSENTRA_SCHEDULER_REGISTRY_DB")
    )
    if explicit:
        return Path(str(explicit))
    legal_db = cfg.get("LEGAL_INTELLIGENCE_DB") or os.getenv("LEGAL_INTELLIGENCE_DB")
    if legal_db:
        return Path(str(legal_db)).expanduser().resolve().parent / DEFAULT_DB_NAME
    if Path("/data").exists():
        return Path("/data/intelligence") / DEFAULT_DB_NAME
    return Path("intelligence") / DEFAULT_DB_NAME


@dataclass(frozen=True)
class SchedulerTemplate:
    key: str
    name: str
    family: str
    description: str
    trigger_kind: str = "cron"
    hour: str = ""
    minute: str = "0"
    interval_minutes: int = 0
    day_of_week: str = ""
    enabled: bool = True
    built_in: bool = False
    editable: bool = True
    args: dict[str, Any] | None = None
    criteria: tuple[str, ...] = ()


DELEGATED_AGENT_TEMPLATES: tuple[SchedulerTemplate, ...] = (
    SchedulerTemplate(
        "agent_clienti_soggetti",
        "Agente clienti e soggetti",
        "Agenti delegati",
        "Controlla anagrafiche, soggetti, parti e dati minimi utili ai fascicoli.",
        enabled=False,
        criteria=(
            "Verifica presenza archivi clienti e soggetti.",
            "Evidenzia dati mancanti senza inventare valori.",
            "Propone una correzione operativa o spiega il blocco.",
        ),
        args={"paths": ["CLIENTI_DB", "SOGGETTI_DB", "SOGGETTI_PARTI_DB"]},
    ),
    SchedulerTemplate(
        "agent_scadenze_agenda",
        "Agente scadenziario e agenda",
        "Agenti delegati",
        "Controlla appuntamenti, termini, sincronizzazioni calendario e scadenze urgenti.",
        enabled=False,
        criteria=(
            "Legge agenda e scadenziario tenant-aware.",
            "Segnala scadenze senza fascicolo o data non valida.",
            "Conferma esito dell'autoverifica.",
        ),
        args={"paths": ["AGENDA_DB", "SCADENZIARIO_DB", "CALENDAR_SYNC_DB"]},
    ),
    SchedulerTemplate(
        "agent_preventivi_parcelle",
        "Agente preventivi e parcelle",
        "Agenti delegati",
        "Controlla preventivi, conferimenti, parcelle e pagamenti collegati.",
        enabled=False,
        criteria=(
            "Verifica archivi economici principali.",
            "Controlla presenza di collegamenti cliente/fascicolo quando disponibili.",
            "Traccia le anomalie invece di sovrascrivere dati.",
        ),
        args={"paths": ["PREVENTIVI_DB", "FATTURAZIONE_DB", "PAGAMENTI_DIR", "TIMESHEET_DB"]},
    ),
    SchedulerTemplate(
        "agent_email_pec",
        "Agente email PEC",
        "Agenti delegati",
        "Controlla caselle PEC, allegati compressi e collegamento ai fascicoli.",
        enabled=False,
        criteria=(
            "Usa solo archivi tenant-aware.",
            "Verifica compatibilita' con lettore allegati compresso.",
            "Segnala doppie copie o archivi mancanti.",
        ),
        args={"paths": ["EMAIL_CASELLA_DB", "FASCICOLI_DB", "AUDIT_DB"]},
    ),
    SchedulerTemplate(
        "agent_email_ordinaria",
        "Agente email ordinaria",
        "Agenti delegati",
        "Controlla posta ordinaria, allegati e duplicazioni tra tenant e area condivisa.",
        enabled=False,
        criteria=(
            "Verifica archivio ordinario corretto.",
            "Segnala se la posta sembra puntare a path globali legacy.",
            "Non scarica nuovamente messaggi gia' presenti.",
        ),
        args={"paths": ["EMAIL_ORDINARIA_DB", "MESSAGGI_DB", "FASCICOLI_DB"]},
    ),
    SchedulerTemplate(
        "agent_fascicoli_documenti",
        "Agente fascicoli e documenti",
        "Agenti delegati",
        "Controlla fascicoli, documenti, archivio e indici di lavoro.",
        enabled=False,
        criteria=(
            "Verifica archivi fascicoli e cartelle documentali.",
            "Segnala documenti non collegati.",
            "Conserva isolamento studio.",
        ),
        args={"paths": ["FASCICOLI_DB", "FASCICOLI_DOCS", "FASCICOLI_ARCH", "SEARCH_INDEX"]},
    ),
    SchedulerTemplate(
        "agent_aggiornamenti_legali",
        "Agente aggiornamenti legali",
        "Agenti delegati",
        "Controlla fonti ufficiali, archivi Normattiva/Gazzetta e coda revisioni.",
        enabled=False,
        criteria=(
            "Verifica archivi ufficiali locali.",
            "Controlla coda e fonti senza riscaricare duplicati.",
            "Richiede ricerca web completa quando manca conferma.",
        ),
        args={"paths": ["LEGAL_INTELLIGENCE_DB", "GIURISPRUDENZA_DB", "NORMATTIVA_DB", "LEX_OFFICIAL_DB"]},
    ),
    SchedulerTemplate(
        "agent_backup_storage",
        "Agente backup e spazio",
        "Agenti delegati",
        "Controlla retention backup, cache rigenerabili e spazio storage.",
        enabled=False,
        criteria=(
            "Rispetta massimo tre backup operativi.",
            "Distingue dati studio da cache rigenerabile.",
            "Non elimina dati applicativi.",
        ),
        args={"paths": ["BACKUP_DIR", "PCT_DATA_ROOT"]},
    ),
    SchedulerTemplate(
        "agent_telematico_depositi",
        "Agente depositi telematici",
        "Agenti delegati",
        "Controlla workflow deposito, esiti PEC e pratiche telematiche pendenti.",
        enabled=False,
        criteria=(
            "Non salva credenziali o sessioni portale.",
            "Verifica solo archivi e stati interni.",
            "Segnala pratiche pendenti o non associate.",
        ),
        args={"paths": ["TELEMATICO_DB", "PDP_PENALE_DB", "EMAIL_CASELLA_DB"]},
    ),
    SchedulerTemplate(
        "agent_sito_studio",
        "Agente sito studio",
        "Agenti delegati",
        "Controlla richieste contatto, prenotazioni e pubblicazione sito studio.",
        enabled=False,
        criteria=(
            "Verifica ingressi pubblici reali.",
            "Mantiene stati vuoti specifici.",
            "Non mostra dati dimostrativi.",
        ),
        args={"paths": ["STUDIO_CONFIG", "PORTALE_DB"]},
    ),
    SchedulerTemplate(
        "agent_pagamenti_notifiche",
        "Agente pagamenti e notifiche",
        "Agenti delegati",
        "Controlla link pagamento, messaggi, WhatsApp e notifiche operative.",
        enabled=False,
        criteria=(
            "Verifica archivi pagamenti e messaggi.",
            "Non invia comunicazioni senza trigger esplicito.",
            "Segnala configurazioni mancanti.",
        ),
        args={"paths": ["PAGAMENTI_DIR", "MESSAGGI_DB", "STUDIO_CONFIG"]},
    ),
    SchedulerTemplate(
        "agent_privacy_gdpr",
        "Agente privacy e GDPR",
        "Agenti delegati",
        "Controlla registro attivita', audit e tracciamenti essenziali.",
        enabled=False,
        criteria=(
            "Verifica audit trail e registri.",
            "Segnala archivi assenti.",
            "Non esporta dati personali.",
        ),
        args={"paths": ["AUDIT_DB", "AUTH_DB"]},
    ),
    SchedulerTemplate(
        "agent_redazione_atti_editor",
        "Agente redazione atti ed editor",
        "Agenti delegati",
        "Controlla template, fascicoli, documenti indicizzati e Copilota Lex negli editor.",
        enabled=False,
        criteria=(
            "Verifica che editor normale e professionale possano leggere il documento reale.",
            "Controlla template, bozza AI, proposte pending e fonti citabili.",
            "Mantiene Da verificare se mancano fascicolo, template o documenti indicizzati.",
        ),
        args={"paths": ["FASCICOLI_DB", "FASCICOLI_DOCS", "TEMPLATE_ATTI_DB", "LOCAL_AI_DB"]},
    ),
    SchedulerTemplate(
        "agent_giurisprudenza_cassazione",
        "Agente Cassazione e citazioni",
        "Agenti delegati",
        "Controlla corpus Cassazione, fonti ufficiali e citazioni verificabili per Lex.",
        enabled=False,
        criteria=(
            "Usa solo corpus verificato o fonte ufficiale per massime e citazioni.",
            "Non pubblica citazioni senza numero, data, sezione o testo verificabile.",
            "Richiede ricerca web completa quando manca una conferma ufficiale.",
        ),
        args={"paths": ["GIURISPRUDENZA_DB", "LEGAL_INTELLIGENCE_DB", "NORMATTIVA_DB", "LEX_OFFICIAL_DB"]},
    ),
    SchedulerTemplate(
        "agent_ai_locale_rag",
        "Agente AI locale e RAG",
        "Agenti delegati",
        "Controlla Ollama, indicizzazione locale, embedding, LLM Wiki e OCR documentale.",
        enabled=False,
        criteria=(
            "Verifica stato AI locale senza usare fascicoli per training esterno.",
            "Segnala mismatch embedding o reindicizzazione necessaria.",
            "Mantiene Da verificare per MTP, LLM Wiki, GLM-OCR o Gemini non pronti.",
        ),
        args={"paths": ["LOCAL_AI_DB", "WORKSPACE_INTELLIGENCE_DB", "FASCICOLI_DOCS", "LOCAL_AI_MODELS_DIR"]},
    ),
    SchedulerTemplate(
        "agent_integrazioni_native",
        "Agente integrazioni native",
        "Agenti delegati",
        "Controlla Google, Microsoft, SDI, firma digitale, provider email e webhooks.",
        enabled=False,
        criteria=(
            "Verifica solo configurazioni e stato, senza mostrare segreti.",
            "Distingue integrazione censita, configurata e realmente operativa.",
            "Segnala provider firma o SDI ancora da collegare.",
        ),
        args={"paths": ["CONFIG_STUDIO_DB", "STUDIO_CONFIG", "CALENDAR_SYNC_DB", "FATTURAZIONE_DB", "PAGAMENTI_DIR"]},
    ),
)


_DELEGATED_TEMPLATE_AGENT_IDS: dict[str, str] = {
    "agent_clienti_soggetti": "cliente_soggetti",
    "agent_scadenze_agenda": "scadenziario_agenda",
    "agent_preventivi_parcelle": "preventivi_parcelle_tariffario",
    "agent_email_pec": "email_pec",
    "agent_email_ordinaria": "email_ordinaria",
    "agent_fascicoli_documenti": "fascicoli_documenti_timeline",
    "agent_aggiornamenti_legali": "fonti_legal_update",
    "agent_backup_storage": "backup_storage_database",
    "agent_telematico_depositi": "pct_depositi_telematici",
    "agent_sito_studio": "sito_studio_portale",
    "agent_pagamenti_notifiche": "fatturazione_pagamenti_sdi",
    "agent_privacy_gdpr": "portal_compliance_security",
    "agent_redazione_atti_editor": "redazione_atti_editor",
    "agent_giurisprudenza_cassazione": "giurisprudenza_cassazione",
    "agent_ai_locale_rag": "ai_locale_rag_runtime",
    "agent_integrazioni_native": "integrazioni_native",
}


def delegated_operational_agent_specs(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the internal Lex micro-agents driven by scheduler templates."""

    specs: list[dict[str, Any]] = []
    for template in DELEGATED_AGENT_TEMPLATES:
        agent_id = _DELEGATED_TEMPLATE_AGENT_IDS.get(template.key)
        if not agent_id:
            continue
        args = dict(template.args or {})
        specs.append(
            {
                "template_key": template.key,
                "agent_id": agent_id,
                "name": template.name,
                "family": template.family,
                "paths": list(args.get("paths") or []),
                "criteria": list(template.criteria),
                "enabled": bool(template.enabled),
            }
        )
    return specs


LEGAL_SOURCE_TEMPLATE_PREFIX = "legal_source_scan__"


def _legal_source_job_id(source_code: str) -> str:
    return _slug(f"legal_source_{source_code}", fallback="legal_source")


def default_scheduler_templates(config: dict[str, Any] | None = None) -> tuple[SchedulerTemplate, ...]:
    cfg = config or {}
    backup_h, backup_m = _hhmm(cfg.get("BACKUP_ORA") or os.getenv("PCT_BACKUP_ORA"), "02:00")
    wa_h, wa_m = _hhmm(cfg.get("WA_REMINDER_ORA") or os.getenv("PCT_WA_REMINDER_ORA"), "18:00")
    uffici_h, uffici_m = _hhmm(cfg.get("UFFICI_SYNC_ORA") or os.getenv("PCT_UFFICI_SYNC_ORA"), "03:30")
    pst_cert_h, pst_cert_m = _hhmm(
        cfg.get("PST_CERTIFICATI_CIFRATURA_SYNC_ORA")
        or os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_SYNC_ORA"),
        "03:45",
    )
    pst_cert_day = str(
        cfg.get("PST_CERTIFICATI_CIFRATURA_SYNC_GIORNO")
        or os.getenv("PCT_PST_CERTIFICATI_CIFRATURA_SYNC_GIORNO")
        or "sun"
    ).strip() or "sun"
    builtins = (
        SchedulerTemplate("backup_giornaliero", "Backup giornaliero", "Manutenzione", "Copia operativa giornaliera.", "cron", backup_h, backup_m, built_in=True),
        SchedulerTemplate("aggiorna_scadute", "Scadenze scadute", "Agenda e scadenze", "Aggiorna stati delle scadenze scadute.", "cron", "0", "5", built_in=True),
        SchedulerTemplate("wa_reminder", "Promemoria WhatsApp", "Comunicazioni", "Invia promemoria appuntamenti del giorno successivo.", "cron", wa_h, wa_m, built_in=True),
        SchedulerTemplate("aggiorna_parcelle_scadute", "Parcelle scadute", "Economia", "Aggiorna stati delle parcelle scadute.", "cron", "1", "0", built_in=True),
        SchedulerTemplate("sync_uffici", "Uffici giudiziari", "Fonti e tabelle", "Sincronizza uffici giudiziari da fonti ufficiali.", "cron", uffici_h, uffici_m, built_in=True),
        SchedulerTemplate("pst_certificati_cifratura_weekly", "Certificati PST cifratura", "Depositi telematici", "Controlla e aggiorna ogni settimana i certificati .cer degli uffici giudiziari per Atto.enc.", "cron", pst_cert_h, pst_cert_m, 0, pst_cert_day, built_in=True),
        SchedulerTemplate("legal_official_archives_daily", "Archivi Normattiva e Gazzetta", "Aggiornamenti legali", "Aggiorna archivi ufficiali locali senza duplicare pacchetti invariati.", "cron", "23", "0", built_in=True),
        SchedulerTemplate("legal_monitor_daily", "Monitor legale giornaliero", "Aggiornamenti legali", "Presidia le fonti legali principali.", "cron", "5", "45", built_in=True),
        SchedulerTemplate("legal_monitor_pst", "Monitor PST", "Aggiornamenti legali", "Controlla aggiornamenti PST durante la giornata.", "cron", "6,12,18", "15", built_in=True),
        SchedulerTemplate(
            "legal_updates_batch",
            "Aggiornamenti legali fonti verdi",
            "Aggiornamenti legali",
            "Esegue solo le fonti verdi della fase 9 con budget controllato e pubblicazione governata.",
            "cron",
            "23",
            "15",
            built_in=True,
        ),
        SchedulerTemplate("sync_tabelle_normative_daily", "Tabelle normative", "Fonti e tabelle", "Aggiorna tassi, indici e tabelle normative.", "cron", "4", "30", built_in=True),
        SchedulerTemplate("calendar_sync_hourly", "Sincronizzazione calendari", "Agenda e scadenze", "Sincronizza calendari configurati ogni ora.", "cron", "", "12", built_in=True),
        SchedulerTemplate("calendar_sync_engine_polling", "Calendari collegati", "Agenda e scadenze", "Controlla calendari collegati.", "cron", "", "*/10", built_in=True),
        SchedulerTemplate("calendar_sync_engine_webcal", "Calendari WebCal", "Agenda e scadenze", "Aggiorna calendari WebCal e ICS.", "cron", "", "42", built_in=True),
        SchedulerTemplate("calendar_sync_engine_retry", "Riprova calendari", "Agenda e scadenze", "Riprende sincronizzazioni calendario in sospeso.", "cron", "", "*/5", built_in=True),
        SchedulerTemplate("mailbox_sync_runtime", "Sincronizzazione caselle", "Comunicazioni", "Sincronizza PEC e posta ordinaria tenant-aware.", "cron", "", "*/15", built_in=True),
        SchedulerTemplate("pec_audit_pipeline_workers", "Presidio PEC automatico", "Comunicazioni", "Acquisisce le PEC archiviate nel presidio e lavora classificazione, scadenze automatiche e collegamento fascicoli.", "cron", "", "*/5", built_in=True),
        SchedulerTemplate("pec_audit_digest_daily", "Digest PEC giornaliero", "Comunicazioni", "Prepara il riepilogo giornaliero del presidio PEC con nuovi messaggi e anomalie.", "cron", "8", "0", built_in=True),
        SchedulerTemplate("workspace_intelligence_snapshot", "Quadro studio", "Lex AI", "Aggiorna inventario operativo dei fascicoli.", "cron", "", "*/20", built_in=True),
        SchedulerTemplate("local_ai_maintenance", "AI locale", "Lex AI", "Mantiene indicizzazione locale e modelli.", "cron", "", "*/30", built_in=True),
        SchedulerTemplate("lex_sentenza_economia_auto", "Sentenze Lex ed economia", "Lex AI", "Applica automaticamente la matrice economica solo alle Sentenze Tribunale con RG e cliente coincidenti col fascicolo.", "cron", "", "7-57/10", built_in=True),
        SchedulerTemplate("lex_dataset_nightly", "Dataset Lex notturno", "Lex AI", "Prepara dataset locali di revisione da Documenti AI senza avviare addestramento automatico.", "cron", "1", "45", built_in=True),
        SchedulerTemplate("lex_operational_agents_nightly", "Agenti Lex notturni", "Lex AI", "Aggiorna inventario operativo completo di studio per Lex.", "cron", "1", "20", built_in=True),
        SchedulerTemplate("utf8_integrity_nightly", "Integrità testo UTF-8", "Manutenzione", "Verifica e ripara mojibake, accenti italiani e caratteri sostitutivi nei dati testuali.", "cron", "0", "35", built_in=True),
        SchedulerTemplate("operational_crash_morning", "Controllo operativo mattina", "Manutenzione", "Esegue controllo operativo con riparazione assistita.", "cron", "7", "0", built_in=True),
        SchedulerTemplate("operational_crash_midday", "Controllo operativo pranzo", "Manutenzione", "Esegue controllo operativo intermedio.", "cron", "13", "30", built_in=True),
        SchedulerTemplate("operational_crash_evening", "Controllo operativo sera", "Manutenzione", "Esegue controllo operativo serale.", "cron", "19", "30", built_in=True),
        SchedulerTemplate("operational_backup_nightly", "Backup blindato notturno", "Manutenzione", "Esegue backup blindato notturno.", "cron", "23", "50", built_in=True),
        SchedulerTemplate("polling_esiti_deposito", "Esiti deposito", "Depositi telematici", "Controlla esiti deposito e PEC cancelleria.", "cron", "", "*/15", built_in=True),
        SchedulerTemplate("poll_pec_cancelleria", "PEC cancelleria", "Depositi telematici", "Associa comunicazioni PEC ai fascicoli.", "cron", "", "*/30", built_in=True),
        SchedulerTemplate("scheduler_registry_reload", "Console pianificazioni", "Manutenzione", "Applica modifiche pianificazioni e richieste manuali.", "cron", "", "*/1", built_in=True, editable=False),
    )
    return builtins


def legal_source_scheduler_templates(config: dict[str, Any] | None = None) -> tuple[SchedulerTemplate, ...]:
    cfg = config or {}
    rows: list[dict[str, Any]] = []
    try:
        from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
        from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository

        rows = [dict(row) for row in DEFAULT_SOURCE_ROWS]
        intelligence_db = str(cfg.get("LEGAL_INTELLIGENCE_DB") or os.getenv("PCT_LEGAL_INTELLIGENCE_DB") or "").strip()
        if intelligence_db:
            repo_cfg = LegalUpdateDbConfig.from_anchor(intelligence_db)
            repository = LegalUpdateRepository(repo_cfg.db_path, json_path=repo_cfg.json_path)
            repository.upsert_sources(rows)
            rows = repository.list_sources(enabled_only=False)
    except Exception:
        rows = rows or []
    templates: list[SchedulerTemplate] = []
    for row in rows:
        code = _slug(str(row.get("code") or ""), fallback="")
        if not code:
            continue
        name = " ".join(str(row.get("name") or code).split()).strip()
        category = " ".join(str(row.get("category") or "fonte").replace("_", " ").split()).strip()
        templates.append(
            SchedulerTemplate(
                f"{LEGAL_SOURCE_TEMPLATE_PREFIX}{code}",
                f"Fonte legale: {name}",
                "Agenti fonte legale",
                f"Controlla {name}, registra esito, timeout e documenti letti.",
                trigger_kind="manual",
                hour="",
                minute="0",
                enabled=bool(row.get("enabled", True)) and is_legal_update_progressive_step1_source(code),
                built_in=False,
                editable=True,
                args={
                    "kind": "legal_update_source_scan",
                    "source_code": code,
                    "source_name": name,
                    "category": category,
                    "auto_publish": True,
                },
                criteria=(
                    "Esegue una sola fonte con timeout governato.",
                    "La fase 9 abilita solo fonti verdi o canali RAG governati.",
                    "Registra documenti trovati, lavorati e invariati.",
                    "Non accetta comandi liberi o sorgenti non censite.",
                ),
            )
        )
    return tuple(templates)


def template_catalog(config: dict[str, Any] | None = None) -> tuple[SchedulerTemplate, ...]:
    return default_scheduler_templates(config) + DELEGATED_AGENT_TEMPLATES + legal_source_scheduler_templates(config)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si", "attivo"}


class SchedulerRegistryRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    family TEXT NOT NULL,
                    description TEXT NOT NULL,
                    template_key TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    hour TEXT NOT NULL DEFAULT '',
                    minute TEXT NOT NULL DEFAULT '0',
                    interval_minutes INTEGER NOT NULL DEFAULT 0,
                    day_of_week TEXT NOT NULL DEFAULT '',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    built_in INTEGER NOT NULL DEFAULT 0,
                    editable INTEGER NOT NULL DEFAULT 1,
                    args_json TEXT NOT NULL DEFAULT '{}',
                    last_applied_signature TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS scheduled_job_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    template_key TEXT NOT NULL DEFAULT '',
                    origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_message TEXT NOT NULL DEFAULT '',
                    requested_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_job_runs_job_id
                    ON scheduled_job_runs(job_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_scheduled_job_runs_status
                    ON scheduled_job_runs(status, id ASC);
                """
            )

    def upsert_default_jobs(self, config: dict[str, Any] | None = None) -> None:
        now = _iso()
        with self.connect() as conn:
            for template in default_scheduler_templates(config):
                conn.execute(
                    """
                    INSERT INTO scheduled_jobs (
                        job_id, name, family, description, template_key, trigger_kind,
                        hour, minute, interval_minutes, day_of_week, enabled, built_in,
                        editable, args_json, created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'system')
                    ON CONFLICT(job_id) DO UPDATE SET
                        name=excluded.name,
                        family=excluded.family,
                        description=excluded.description,
                        template_key=excluded.template_key,
                        built_in=1,
                        editable=excluded.editable
                    """,
                    (
                        template.key,
                        template.name,
                        template.family,
                        template.description,
                        template.key,
                        template.trigger_kind,
                        template.hour,
                        template.minute,
                        template.interval_minutes,
                        template.day_of_week,
                        1 if template.enabled else 0,
                        1,
                        1 if template.editable else 0,
                        _json_dumps(template.args or {}),
                        now,
                        now,
                    ),
                )
            for template in legal_source_scheduler_templates(config):
                source_code = str((template.args or {}).get("source_code") or "").strip()
                job_id = _legal_source_job_id(source_code)
                conn.execute(
                    """
                    INSERT INTO scheduled_jobs (
                        job_id, name, family, description, template_key, trigger_kind,
                        hour, minute, interval_minutes, day_of_week, enabled, built_in,
                        editable, args_json, created_at, updated_at, updated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'system')
                    ON CONFLICT(job_id) DO UPDATE SET
                        name=excluded.name,
                        family=excluded.family,
                        description=excluded.description,
                        template_key=excluded.template_key,
                        enabled=excluded.enabled,
                        args_json=excluded.args_json,
                        editable=excluded.editable
                    """,
                    (
                        job_id,
                        template.name,
                        template.family,
                        template.description,
                        template.key,
                        template.trigger_kind,
                        template.hour,
                        template.minute,
                        template.interval_minutes,
                        template.day_of_week,
                        1 if template.enabled else 0,
                        1 if template.editable else 0,
                        _json_dumps(template.args or {}),
                        now,
                        now,
                    ),
                )
            conn.execute(
                """
                UPDATE scheduled_jobs
                SET minute='7-57/10',
                    updated_at=?,
                    updated_by='system'
                WHERE job_id='lex_sentenza_economia_auto'
                  AND built_in=1
                  AND minute='*/10'
                """,
                (now,),
            )
            conn.execute(
                """
                UPDATE scheduled_jobs
                SET enabled=0,
                    description='Disattivato dalla fase 9: la Gazzetta resta negli archivi ufficiali locali, fuori dallo scheduler progressivo.',
                    updated_at=?,
                    updated_by='system'
                WHERE job_id='legal_updates_gazzetta' AND built_in=1
                """,
                (now,),
            )

    def list_jobs(self, include_disabled: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM scheduled_jobs"
        params: list[Any] = []
        if not include_disabled:
            sql += " WHERE enabled=1"
        sql += " ORDER BY built_in DESC, family, name"
        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
        return [self._normalize_job(row) for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM scheduled_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._normalize_job(dict(row)) if row else None

    def save_job(self, job_id: str, updates: dict[str, Any], *, updated_by: str = "") -> dict[str, Any]:
        current = self.get_job(job_id)
        if not current:
            raise ValueError("Pianificazione non trovata.")
        if not current.get("editable"):
            raise ValueError("Questa pianificazione e' protetta.")
        trigger_kind = str(updates.get("trigger_kind") or current["trigger_kind"]).strip().lower()
        if trigger_kind not in {"cron", "interval", "manual"}:
            raise ValueError("Tipo pianificazione non valido.")
        hour = _safe_hour(updates.get("hour"), str(current.get("hour") or ""))
        minute = _safe_minute(updates.get("minute"), str(current.get("minute") or "0"))
        interval_minutes = max(0, _coerce_int(updates.get("interval_minutes"), int(current.get("interval_minutes") or 0)))
        if trigger_kind == "interval" and interval_minutes < 1:
            interval_minutes = 60
        enabled = 1 if _coerce_bool(updates.get("enabled"), bool(current.get("enabled"))) else 0
        name = " ".join(str(updates.get("name") or current["name"]).split()).strip() or current["name"]
        description = " ".join(str(updates.get("description") or current["description"]).split()).strip()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_jobs
                SET name=?, description=?, trigger_kind=?, hour=?, minute=?,
                    interval_minutes=?, day_of_week=?, enabled=?, updated_at=?,
                    updated_by=?, last_applied_signature=''
                WHERE job_id=?
                """,
                (
                    name,
                    description,
                    trigger_kind,
                    hour,
                    minute,
                    interval_minutes,
                    str(updates.get("day_of_week") or current.get("day_of_week") or "").strip(),
                    enabled,
                    _iso(),
                    updated_by,
                    job_id,
                ),
            )
        updated = self.get_job(job_id)
        if updated is None:  # pragma: no cover
            raise ValueError("Pianificazione non trovata dopo il salvataggio.")
        return updated

    def create_job_from_template(
        self,
        template_key: str,
        *,
        name: str = "",
        hour: str = "",
        minute: str = "0",
        interval_minutes: int = 0,
        trigger_kind: str = "cron",
        enabled: bool = True,
        created_by: str = "",
    ) -> dict[str, Any]:
        templates = {tpl.key: tpl for tpl in DELEGATED_AGENT_TEMPLATES}
        template = templates.get(str(template_key or "").strip())
        if not template:
            raise ValueError("Template non autorizzato.")
        trigger_kind = str(trigger_kind or "cron").strip().lower()
        if trigger_kind not in {"cron", "interval", "manual"}:
            raise ValueError("Tipo pianificazione non valido.")
        base_name = " ".join(str(name or template.name).split()).strip() or template.name
        suffix = uuid4().hex[:8]
        job_id = _slug(f"{template.key}_{suffix}", fallback=f"agent_{suffix}")
        if trigger_kind == "interval":
            interval_minutes = max(1, _coerce_int(interval_minutes, 60))
        now = _iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_jobs (
                    job_id, name, family, description, template_key, trigger_kind,
                    hour, minute, interval_minutes, day_of_week, enabled, built_in,
                    editable, args_json, created_at, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, 0, 1, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    base_name,
                    template.family,
                    template.description,
                    template.key,
                    trigger_kind,
                    _safe_hour(hour, template.hour),
                    _safe_minute(minute, template.minute),
                    interval_minutes,
                    1 if enabled else 0,
                    _json_dumps(template.args or {}),
                    now,
                    now,
                    created_by,
                ),
            )
        created = self.get_job(job_id)
        if created is None:  # pragma: no cover
            raise ValueError("Pianificazione non creata.")
        return created

    def update_applied_signature(self, job_id: str, signature: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_jobs
                SET last_applied_signature=?,
                    updated_at=CASE WHEN last_applied_signature<>? THEN ? ELSE updated_at END
                WHERE job_id=?
                """,
                (signature, signature, _iso(), job_id),
            )

    def request_manual_run(self, job_id: str, *, requested_by: str = "") -> dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            raise ValueError("Pianificazione non trovata.")
        run_id = uuid4().hex
        now = _iso()
        if not job.get("enabled"):
            message = "Pianificazione disattivata: esecuzione non avviata."
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO scheduled_job_runs (
                        run_id, job_id, template_key, origin, status, scheduled_at,
                        started_at, finished_at, duration_ms, message, result_json,
                        error_message, requested_by, created_at
                    )
                    VALUES (?, ?, ?, 'manuale', 'completed', ?, ?, ?, 0, ?, ?, '', ?, ?)
                    """,
                    (
                        run_id,
                        job_id,
                        str(job.get("template_key") or ""),
                        now,
                        now,
                        now,
                        message,
                        _json_dumps(
                            {
                                "ok": True,
                                "summary": message,
                                "details": [{"job_id": job_id, "status": "disattivata"}],
                            }
                        ),
                        requested_by,
                        now,
                    ),
                )
            return {"run_id": run_id, "job_id": job_id, "status": "completed", "message": message}
        if job_id == "operational_backup_nightly":
            with self.connect() as conn:
                open_row = conn.execute(
                    """
                    SELECT job_id, status
                    FROM scheduled_job_runs
                    WHERE origin='manuale'
                      AND status IN ('requested', 'running')
                      AND job_id <> ?
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                if open_row:
                    blocked_by = str(open_row["job_id"] or "")
                    message = (
                        "Backup non avviato dentro un avvio massivo: sono già presenti "
                        "altre esecuzioni manuali in coda o in corso. "
                        "Rilancia il backup singolarmente quando la console è libera."
                    )
                    conn.execute(
                        """
                        INSERT INTO scheduled_job_runs (
                            run_id, job_id, template_key, origin, status, scheduled_at,
                            started_at, finished_at, duration_ms, message, result_json,
                            error_message, requested_by, created_at
                        )
                        VALUES (?, ?, ?, 'manuale', 'completed', ?, ?, ?, 0, ?, ?, '', ?, ?)
                        """,
                        (
                            run_id,
                            job_id,
                            str(job.get("template_key") or ""),
                            now,
                            now,
                            now,
                            message,
                            _json_dumps(
                                {
                                    "ok": True,
                                    "status": "backup_massivo_rinviato",
                                    "summary": message,
                                    "blocked_by": blocked_by,
                                    "details": [
                                        {
                                            "job_id": job_id,
                                            "status": "non_avviata",
                                            "blocked_by": blocked_by,
                                        }
                                    ],
                                }
                            ),
                            requested_by,
                            now,
                        ),
                    )
                    return {"run_id": run_id, "job_id": job_id, "status": "completed", "message": message}
        if job_id in EXCLUSIVE_MANUAL_MAINTENANCE_JOB_IDS:
            with self.connect() as conn:
                open_row = conn.execute(
                    """
                    SELECT job_id, status
                    FROM scheduled_job_runs
                    WHERE origin='manuale'
                      AND status IN ('requested', 'running')
                      AND job_id <> ?
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                if open_row:
                    blocked_by = str(open_row["job_id"] or "")
                    message = (
                        "Manutenzione pesante non avviata dentro un avvio massivo: "
                        "sono già presenti altre esecuzioni manuali in coda o in corso. "
                        "Rilancia la singola pianificazione quando la console è libera."
                    )
                    conn.execute(
                        """
                        INSERT INTO scheduled_job_runs (
                            run_id, job_id, template_key, origin, status, scheduled_at,
                            started_at, finished_at, duration_ms, message, result_json,
                            error_message, requested_by, created_at
                        )
                        VALUES (?, ?, ?, 'manuale', 'completed', ?, ?, ?, 0, ?, ?, '', ?, ?)
                        """,
                        (
                            run_id,
                            job_id,
                            str(job.get("template_key") or ""),
                            now,
                            now,
                            now,
                            message,
                            _json_dumps(
                                {
                                    "ok": True,
                                    "status": "manutenzione_massiva_rinviata",
                                    "summary": message,
                                    "blocked_by": blocked_by,
                                    "details": [
                                        {
                                            "job_id": job_id,
                                            "status": "non_avviata",
                                            "blocked_by": blocked_by,
                                        }
                                    ],
                                }
                            ),
                            requested_by,
                            now,
                        ),
                    )
                    return {"run_id": run_id, "job_id": job_id, "status": "completed", "message": message}
        if job_id in EXCLUSIVE_MANUAL_MAINTENANCE_JOB_IDS:
            placeholders = ",".join("?" for _ in EXCLUSIVE_MANUAL_MAINTENANCE_JOB_IDS)
            params = tuple(sorted(EXCLUSIVE_MANUAL_MAINTENANCE_JOB_IDS))
            with self.connect() as conn:
                open_row = conn.execute(
                    f"""
                    SELECT job_id, status
                    FROM scheduled_job_runs
                    WHERE status IN ('requested', 'running')
                      AND job_id IN ({placeholders})
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
                if open_row:
                    blocked_by = str(open_row["job_id"] or "")
                    message = (
                        "Manutenzione pesante già in corso: esecuzione non avviata "
                        "per proteggere spazio, database e reattività. "
                        "Rilancia la singola pianificazione quando termina."
                    )
                    conn.execute(
                        """
                        INSERT INTO scheduled_job_runs (
                            run_id, job_id, template_key, origin, status, scheduled_at,
                            started_at, finished_at, duration_ms, message, result_json,
                            error_message, requested_by, created_at
                        )
                        VALUES (?, ?, ?, 'manuale', 'completed', ?, ?, ?, 0, ?, ?, '', ?, ?)
                        """,
                        (
                            run_id,
                            job_id,
                            str(job.get("template_key") or ""),
                            now,
                            now,
                            now,
                            message,
                            _json_dumps(
                                {
                                    "ok": True,
                                    "status": "manutenzione_esclusiva_rinviata",
                                    "summary": message,
                                    "blocked_by": blocked_by,
                                    "details": [
                                        {
                                            "job_id": job_id,
                                            "status": "non_avviata",
                                            "blocked_by": blocked_by,
                                        }
                                    ],
                                }
                            ),
                            requested_by,
                            now,
                        ),
                    )
                    return {"run_id": run_id, "job_id": job_id, "status": "completed", "message": message}
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_job_runs (
                    run_id, job_id, template_key, origin, status, scheduled_at,
                    requested_by, created_at, message
                )
                VALUES (?, ?, ?, 'manuale', 'requested', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_id,
                    str(job.get("template_key") or ""),
                    now,
                    requested_by,
                    now,
                    "Esecuzione manuale richiesta dalla console.",
                ),
            )
        return {"run_id": run_id, "job_id": job_id, "status": "requested"}

    def list_requested_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scheduled_job_runs
                WHERE status='requested'
                ORDER BY id ASC
                LIMIT ?
                """,
                (max(1, int(limit or 20)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_run_running(self, run_id: str) -> None:
        now = _iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE scheduled_job_runs SET status='running', started_at=?, message=? WHERE run_id=?",
                (now, "Esecuzione in corso.", run_id),
            )

    def mark_run_finished(
        self,
        run_id: str,
        *,
        status: str,
        message: str = "",
        result: dict[str, Any] | None = None,
        error_message: str = "",
    ) -> None:
        now = _iso()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT started_at FROM scheduled_job_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            row_data = dict(row) if row else {}
            started_at = str(row_data.get("started_at") or now)
            conn.execute(
                """
                UPDATE scheduled_job_runs
                SET status=?, finished_at=?, duration_ms=?, message=?,
                    result_json=?, error_message=?
                WHERE run_id=?
                """,
                (
                    status,
                    now,
                    _duration_ms(started_at, now),
                    message,
                    _json_dumps(result or {}),
                    error_message,
                    run_id,
                ),
            )

    def cancel_open_runs(
        self,
        *,
        job_prefixes: tuple[str, ...] = (),
        job_ids: tuple[str, ...] = (),
        cancelled_by: str = "",
        reason: str = "",
    ) -> dict[str, int]:
        prefixes = tuple(str(prefix or "").strip() for prefix in job_prefixes if str(prefix or "").strip())
        exact_ids = tuple(str(job_id or "").strip() for job_id in job_ids if str(job_id or "").strip())
        if not prefixes and not exact_ids:
            return {"cancelled": 0, "running": 0, "requested": 0}
        where_parts = ["status IN ('requested', 'running')"]
        params: list[Any] = []
        job_clauses: list[str] = []
        for prefix in prefixes:
            job_clauses.append("job_id LIKE ?")
            params.append(f"{prefix}%")
        for job_id in exact_ids:
            job_clauses.append("job_id = ?")
            params.append(job_id)
        where_parts.append("(" + " OR ".join(job_clauses) + ")")
        where_sql = " AND ".join(where_parts)
        now = _iso()
        message = " ".join(str(reason or "").split()) or "Esecuzione annullata dalla console."
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT status, started_at FROM scheduled_job_runs WHERE {where_sql}",
                tuple(params),
            ).fetchall()
            running = sum(1 for row in rows if str(row["status"]) == "running")
            requested = sum(1 for row in rows if str(row["status"]) == "requested")
            conn.execute(
                f"""
                UPDATE scheduled_job_runs
                SET status='cancelled',
                    finished_at=?,
                    duration_ms=CASE
                        WHEN COALESCE(started_at, '') <> '' THEN duration_ms
                        ELSE 0
                    END,
                    message=?,
                    error_message=?,
                    result_json=?,
                    requested_by=CASE WHEN requested_by <> '' THEN requested_by ELSE ? END
                WHERE {where_sql}
                """,
                (
                    now,
                    message,
                    message,
                    _json_dumps({"cancelled_by": cancelled_by, "reason": message}),
                    cancelled_by,
                    *params,
                ),
            )
        return {"cancelled": len(rows), "running": running, "requested": requested}

    def cancel_manual_runs_started_before(self, cutoff_iso: str, *, reason: str = "") -> dict[str, int]:
        cutoff = str(cutoff_iso or "").strip()
        if not cutoff:
            return {"cancelled": 0}
        now = _iso()
        message = (
            " ".join(str(reason or "").split())
            or "Esecuzione interrotta dal riavvio del worker; rilanciare dalla console."
        )
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, started_at
                FROM scheduled_job_runs
                WHERE origin='manuale'
                  AND status='running'
                  AND COALESCE(started_at, created_at, '') < ?
                """,
                (cutoff,),
            ).fetchall()
            for row in rows:
                started_at = str(row["started_at"] or now)
                conn.execute(
                    """
                    UPDATE scheduled_job_runs
                    SET status='cancelled',
                        finished_at=?,
                        duration_ms=?,
                        message=?,
                        error_message='',
                        result_json=?
                    WHERE run_id=?
                    """,
                    (
                        now,
                        _duration_ms(started_at, now),
                        message,
                        _json_dumps(
                            {
                                "ok": False,
                                "status": "interrotta_riavvio_worker",
                                "summary": message,
                            }
                        ),
                        str(row["run_id"]),
                    ),
                )
        return {"cancelled": len(rows)}

    def record_scheduler_event(
        self,
        job_id: str,
        *,
        status: str,
        scheduled_at: str = "",
        message: str = "",
        result: dict[str, Any] | None = None,
        error_message: str = "",
    ) -> None:
        job = self.get_job(job_id)
        template_key = str((job or {}).get("template_key") or job_id)
        now = _iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_job_runs (
                    run_id, job_id, template_key, origin, status, scheduled_at,
                    started_at, finished_at, duration_ms, message, result_json,
                    error_message, created_at
                )
                VALUES (?, ?, ?, 'scheduler', ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    job_id,
                    template_key,
                    status,
                    scheduled_at,
                    now,
                    now,
                    message,
                    _json_dumps(result or {}),
                    error_message,
                    now,
                ),
            )

    def list_recent_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT runs.*, jobs.name AS job_name, jobs.family AS job_family
                FROM scheduled_job_runs AS runs
                LEFT JOIN scheduled_jobs AS jobs ON jobs.job_id = runs.job_id
                ORDER BY runs.id DESC
                LIMIT ?
                """,
                (max(1, int(limit or 50)),),
            ).fetchall()
        return [self._normalize_run(dict(row)) for row in rows]

    def latest_runs_by_job(self) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT r.*
                FROM scheduled_job_runs r
                JOIN (
                    SELECT job_id, MAX(id) AS max_id
                    FROM scheduled_job_runs
                    GROUP BY job_id
                ) latest ON latest.max_id = r.id
                """
            ).fetchall()
        return {str(row["job_id"]): self._normalize_run(dict(row)) for row in rows}

    def latest_completed_run(self, job_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM scheduled_job_runs
                WHERE job_id=? AND status='completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (str(job_id or ""),),
            ).fetchone()
        return self._normalize_run(dict(row)) if row else {}

    def totals(self) -> dict[str, int]:
        with self.connect() as conn:
            jobs = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN built_in=0 AND family <> 'Agenti fonte legale' THEN 1 ELSE 0 END) AS custom
                FROM scheduled_jobs
                """
            ).fetchone()
            runs = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status IN ('failed', 'error', 'missed') THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status='requested' THEN 1 ELSE 0 END) AS requested,
                    SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running,
                    SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled
                FROM scheduled_job_runs
                """
            ).fetchone()
        job_totals = dict(jobs or {})
        run_totals = dict(runs or {})
        return {
            "jobs_total": int(job_totals.get("total") or 0),
            "jobs_active": int(job_totals.get("active") or 0),
            "jobs_custom": int(job_totals.get("custom") or 0),
            "runs_total": int(run_totals.get("total") or 0),
            "runs_failed": int(run_totals.get("failed") or 0),
            "runs_requested": int(run_totals.get("requested") or 0),
            "runs_running": int(run_totals.get("running") or 0),
            "runs_cancelled": int(run_totals.get("cancelled") or 0),
        }

    def _normalize_job(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["enabled"] = bool(row.get("enabled"))
        row["built_in"] = bool(row.get("built_in"))
        row["editable"] = bool(row.get("editable"))
        row["interval_minutes"] = int(row.get("interval_minutes") or 0)
        row["args"] = _json_loads(row.get("args_json"), {})
        row["signature"] = job_signature(row)
        row["schedule_label"] = schedule_label(row)
        return row

    def _normalize_run(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["duration_ms"] = int(row.get("duration_ms") or 0)
        row["result"] = _json_loads(row.get("result_json"), {})
        row["status_label"] = run_status_label(row.get("status"))
        return row


def scheduler_registry_repository(config: dict[str, Any] | None = None) -> SchedulerRegistryRepository:
    return SchedulerRegistryRepository(_runtime_registry_db_path(config))


def job_signature(job: dict[str, Any]) -> str:
    return _json_dumps(
        {
            "trigger_kind": job.get("trigger_kind"),
            "hour": job.get("hour"),
            "minute": job.get("minute"),
            "interval_minutes": int(job.get("interval_minutes") or 0),
            "day_of_week": job.get("day_of_week"),
            "enabled": bool(job.get("enabled")),
            "template_key": job.get("template_key"),
        }
    )


def schedule_label(job: dict[str, Any]) -> str:
    kind = str(job.get("trigger_kind") or "cron").lower()
    if kind == "manual":
        return "Solo avvio manuale"
    if kind == "interval":
        minutes = int(job.get("interval_minutes") or 0)
        return f"Ogni {minutes} minuti" if minutes else "Intervallo non configurato"
    hour = str(job.get("hour") or "").strip()
    minute = str(job.get("minute") or "0").strip()
    if hour and "," in hour:
        return f"Alle ore {hour.replace(',', ', ')}:{minute.zfill(2) if minute.isdigit() else minute}"
    if hour:
        return f"Ogni giorno alle {hour.zfill(2) if hour.isdigit() else hour}:{minute.zfill(2) if minute.isdigit() else minute}"
    return f"Ogni ora al minuto {minute}"


def run_status_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return {
        "requested": "Richiesta",
        "running": "In corso",
        "completed": "Completata",
        "failed": "Non riuscita",
        "error": "Errore",
        "missed": "Saltata",
        "cancelled": "Annullata",
    }.get(key, key.capitalize() or "Non registrata")


def _job_trigger(job: dict[str, Any]):
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    kind = str(job.get("trigger_kind") or "cron").lower()
    if kind == "manual":
        return None
    if kind == "interval":
        return IntervalTrigger(minutes=max(1, int(job.get("interval_minutes") or 60)))
    kwargs: dict[str, Any] = {"minute": str(job.get("minute") or "0")}
    if str(job.get("hour") or "").strip():
        kwargs["hour"] = str(job.get("hour")).strip()
    if str(job.get("day_of_week") or "").strip():
        kwargs["day_of_week"] = str(job.get("day_of_week")).strip()
    return CronTrigger(**kwargs)


def _run_legal_source_agent(app, args: dict[str, Any]) -> dict[str, Any]:
    cfg = app.config if app is not None else {}
    source_code = _slug(str(args.get("source_code") or ""), fallback="")
    if not source_code:
        return {
            "ok": False,
            "summary": "Fonte legale non indicata.",
            "self_check": "Non superato: manca il codice fonte.",
            "supervisor_check": "Esecuzione bloccata prima della scansione.",
            "details": [],
        }
    try:
        from pct.legal_update_batch_runner import LegalUpdateJobConfig, run_legal_update_batch_with_timeouts
        from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
        from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository

        intelligence_db = str(
            cfg.get("LEGAL_INTELLIGENCE_DB")
            or os.getenv("PCT_LEGAL_INTELLIGENCE_DB")
            or "./intelligence/motori.json"
        )
        repo_cfg = LegalUpdateDbConfig.from_anchor(intelligence_db)
        repository = LegalUpdateRepository(repo_cfg.db_path, json_path=repo_cfg.json_path)
        repository.upsert_sources([dict(row) for row in DEFAULT_SOURCE_ROWS])
        source = repository.get_source_by_code(source_code)
        if not source:
            return {
                "ok": False,
                "summary": f"Fonte {source_code} non presente nel catalogo.",
                "self_check": "Non superato: la fonte richiesta non e' censita.",
                "supervisor_check": "Bloccato: non si eseguono fonti non autorizzate.",
                "details": [{"source_code": source_code, "status": "non_censita"}],
            }
        if not bool(source.get("enabled")):
            alternative = "canale ufficiale alternativo censito"
            if source_code in {"giustizia_amministrativa", "giustizia_amministrativa_decisioni_pareri"}:
                alternative = "OpenGA ufficiale (openga_giustizia_amministrativa e cartelle openga_*)"
            elif not bool(source.get("is_official")):
                alternative = "Normattiva e Gazzetta Ufficiale, con la fonte privata solo come confronto secondario"
            return {
                "ok": False,
                "summary": f"{source.get('name')}: fonte non avviata automaticamente; presidio spostato su {alternative}.",
                "self_check": "Da verificare: il canale non viene usato come fonte primaria automatica.",
                "supervisor_check": (
                    "Risoluzione applicata: non si insiste sul canale non governato come primario; "
                    f"il controllo automatico passa da {alternative}."
                ),
                "criteria": [
                    "Fonte censita nel catalogo aggiornamenti legali.",
                    "Canale diretto disattivato quando non e' stabile.",
                    "Presidio alternativo ufficiale mantenuto nel ciclo automatico.",
                ],
                "details": [
                    {
                        "source_code": source_code,
                        "source_name": source.get("name"),
                        "status": "in_osservazione",
                        "alternative": alternative,
                        "notes": source.get("notes") or "",
                    }
                ],
            }
        if not is_legal_update_progressive_step1_source(source_code):
            reason = legal_update_progressive_exclusion_reason(source_code)
            return {
                "ok": True,
                "summary": f"{source.get('name')}: presidio rinviato, fonte fuori dalla fase 9 progressiva.",
                "self_check": "Superato: la fonte non viene avviata perché fuori dal gruppo verde abilitato.",
                "supervisor_check": reason,
                "criteria": [
                    "Fonte censita nel catalogo aggiornamenti legali.",
                    "Scheduler progressivo limitato alle fonti verdi della fase 9.",
                    "Fonti fuori step bloccate fino a canary/report verde dedicato.",
                ],
                "details": [
                    {
                        "source_code": source_code,
                        "source_name": source.get("name"),
                        "status": "fuori_step_progressivo",
                        "reason": reason,
                    }
                ],
            }
        timeout_seconds = _coerce_int(
            cfg.get("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
            or os.getenv("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
            or os.getenv("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"),
            LEGAL_UPDATE_PROGRESSIVE_ITEM_TIMEOUT_SECONDS,
        )
        publish_max_items = _coerce_int(
            cfg.get("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
            or os.getenv("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
            or os.getenv("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"),
            LEGAL_UPDATE_PROGRESSIVE_PUBLISH_MAX_ITEMS,
        )
        report = run_legal_update_batch_with_timeouts(
            LegalUpdateJobConfig(
                intelligence_db=intelligence_db,
                giurisprudenza_db=str(cfg.get("GIURISPRUDENZA_DB") or os.getenv("PCT_GIURISPRUDENZA_DB") or ""),
                ai_base_url=str(cfg.get("LOCAL_AI_BASE_URL") or cfg.get("PCT_LOCAL_AI_BASE_URL") or ""),
                ai_model=str(cfg.get("LOCAL_AI_CHAT_MODEL") or cfg.get("OLLAMA_MODEL") or "mistral"),
                export_json_enabled=_truthy(cfg.get("LEGAL_UPDATES_EXPORT_JSON_ENABLED")),
                mirror_giurisprudenza_json_enabled=_truthy(cfg.get("LEGAL_UPDATES_MIRROR_GIURISPRUDENZA_JSON_ENABLED")),
            ),
            source_codes=[source_code],
            auto_publish=_truthy(args.get("auto_publish", True)),
            item_timeout_seconds=timeout_seconds,
            publish_max_items=publish_max_items,
            record_agent_runs=True,
        )
        source_report = (report.get("reports") or [{}])[0]
        payload = source_report.get("payload") or {}
        inner_report = payload.get("report") or {}
        inner_rows = inner_report.get("reports") or []
        documents_found = sum(int(row.get("documents_found") or 0) for row in inner_rows)
        processed = sum(int(row.get("processed") or 0) for row in inner_rows)
        skipped = sum(int(row.get("skipped_unchanged") or 0) for row in inner_rows)
        row_errors = [
            str(row.get("error") or "").strip()
            for row in inner_rows
            if str(row.get("error") or "").strip()
        ]
        payload_error = str(payload.get("error") or "").strip()
        if payload_error:
            row_errors.append(payload_error)
        source_timeout = bool(source_report.get("timeout"))
        source_completed = bool(source_report.get("ok")) and not row_errors and not source_timeout
        read_completed = not row_errors and not source_timeout and (documents_found > 0 or processed > 0 or skipped > 0)
        ok = source_completed or read_completed
        summary = (
            f"{source.get('name')}: {documents_found} documenti trovati, "
            f"{processed} lavorati, {skipped} invariati."
        )
        if not ok and source_timeout:
            summary = f"{source.get('name')}: timeout dopo {timeout_seconds} secondi."
        elif not ok:
            summary = f"{source.get('name')}: controllo non completato."
        return {
            "ok": ok,
            "summary": summary,
            "self_check": "Superato: fonte censita ed eseguita con timeout dedicato." if ok else "Da verificare: la fonte non ha completato il controllo.",
            "supervisor_check": "Esito registrato come agente fonte, senza comandi liberi.",
            "criteria": [
                "Fonte censita nel catalogo aggiornamenti legali.",
                "Esecuzione isolata con timeout per fonte.",
                "Esito registrato per controllo successivo.",
            ],
            "details": [
                {
                    "source_code": source_code,
                    "source_name": source.get("name"),
                    "documents_found": documents_found,
                    "processed": processed,
                    "skipped_unchanged": skipped,
                    "timeout_seconds": timeout_seconds,
                    "errors": row_errors,
                }
            ],
            "report": report,
        }
    except Exception as exc:
        return {
            "ok": False,
            "summary": f"Fonte {source_code}: controllo non completato.",
            "self_check": str(exc),
            "supervisor_check": "Errore registrato: serve verifica della fonte o della connettivita'.",
            "details": [{"source_code": source_code, "status": "errore"}],
        }


def run_delegated_agent_template(template_key: str, app, args: dict[str, Any] | None = None) -> dict[str, Any]:
    key = str(template_key or "").strip()
    if key.startswith(LEGAL_SOURCE_TEMPLATE_PREFIX):
        return _run_legal_source_agent(app, args or {})
    templates = {tpl.key: tpl for tpl in DELEGATED_AGENT_TEMPLATES}
    template = templates.get(key)
    if not template:
        return {
            "ok": False,
            "summary": "Template agente non autorizzato.",
            "self_check": "Non superato: template non presente nel catalogo autorizzato.",
            "supervisor_check": "Bloccato prima dell'esecuzione.",
            "details": [],
        }
    agent_id = _DELEGATED_TEMPLATE_AGENT_IDS.get(key, "")
    if agent_id:
        try:
            from lex.operational_knowledge.nightly_agents import run_operational_micro_agent

            template_args = dict(template.args or {})
            if args:
                template_args.update(args)
            return run_operational_micro_agent(
                agent_id=agent_id,
                app=app,
                required_path_keys=list(template_args.get("paths") or []),
                criteria=list(template.criteria),
            )
        except Exception as exc:
            return {
                "ok": False,
                "agent_id": agent_id,
                "status": "errore",
                "summary": f"{template.name}: agente non completato.",
                "self_check": f"Da verificare: {exc}",
                "supervisor_check": "Errore registrato: serve controllo della configurazione dell'agente.",
                "criteria": list(template.criteria),
                "details": [{"template_key": key, "agent_id": agent_id, "status": "errore"}],
                "missing_keys": [],
            }
    return {
        "ok": False,
        "summary": "Template agente non collegato a un micro-agente Lex.",
        "self_check": "Da verificare: manca il mapping operativo interno.",
        "supervisor_check": "Bloccato prima dell'esecuzione per evitare controlli fittizi.",
        "criteria": list(template.criteria),
        "details": [{"template_key": key, "status": "mapping_mancante"}],
        "missing_keys": [],
    }


def _run_dynamic_job(app, repository: SchedulerRegistryRepository, job: dict[str, Any], *, run_id: str = "") -> dict[str, Any]:
    if not job or not job.get("job_id"):
        if run_id:
            repository.mark_run_finished(
                run_id,
                status="failed",
                message="Pianificazione agente non trovata.",
            )
        return {"ok": False, "summary": "Pianificazione agente non trovata."}
    owned_run_id = run_id or uuid4().hex
    created_own_run = not run_id
    if created_own_run:
        now = _iso()
        with repository.connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_job_runs (
                    run_id, job_id, template_key, origin, status, scheduled_at,
                    started_at, requested_by, created_at, message
                )
                VALUES (?, ?, ?, 'scheduler', 'running', ?, ?, '', ?, ?)
                """,
                (
                    owned_run_id,
                    job["job_id"],
                    str(job.get("template_key") or ""),
                    now,
                    now,
                    now,
                    "Esecuzione agente in corso.",
                ),
            )
    else:
        repository.mark_run_running(owned_run_id)
    try:
        with app.app_context():
            result = run_delegated_agent_template(str(job.get("template_key") or ""), app, job.get("args") or {})
        status = "completed" if result.get("ok") else "failed"
        repository.mark_run_finished(
            owned_run_id,
            status=status,
            message=str(result.get("summary") or ""),
            result=result,
            error_message="" if result.get("ok") else str(result.get("self_check") or ""),
        )
        return result
    except Exception as exc:  # pragma: no cover - difesa runtime
        repository.mark_run_finished(
            owned_run_id,
            status="failed",
            message="Esecuzione agente non completata.",
            error_message=str(exc),
        )
        raise


def apply_scheduler_registry(scheduler, app, repository: SchedulerRegistryRepository | None = None) -> dict[str, int]:
    repo = repository or scheduler_registry_repository(app.config)
    repo.upsert_default_jobs(app.config)
    applied = 0
    removed = 0
    for job in repo.list_jobs():
        job_id = str(job.get("job_id") or "")
        if not job_id or job_id == "scheduler_registry_reload":
            continue
        existing = scheduler.get_job(job_id)
        signature = job_signature(job)
        trigger = _job_trigger(job)
        if job.get("built_in"):
            if not existing:
                continue
            if not job.get("enabled"):
                try:
                    scheduler.pause_job(job_id)
                except Exception:
                    pass
                repo.update_applied_signature(job_id, signature)
                applied += 1
                continue
            if trigger is not None:
                try:
                    scheduler.reschedule_job(job_id, trigger=trigger)
                    scheduler.resume_job(job_id)
                except Exception:
                    pass
            repo.update_applied_signature(job_id, signature)
            applied += 1
            continue
        if not job.get("enabled") or trigger is None:
            if existing:
                scheduler.remove_job(job_id)
                removed += 1
            repo.update_applied_signature(job_id, signature)
            continue
        if not existing or str(job.get("last_applied_signature") or "") != signature:
            if existing:
                scheduler.remove_job(job_id)
            scheduler.add_job(
                lambda job_id=job_id: _run_dynamic_job(app, repo, repo.get_job(job_id) or {}),
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            repo.update_applied_signature(job_id, signature)
            applied += 1
    return {"applied": applied, "removed": removed}


def dispatch_requested_manual_runs(scheduler, app, repository: SchedulerRegistryRepository | None = None) -> dict[str, int]:
    from apscheduler.triggers.date import DateTrigger

    repo = repository or scheduler_registry_repository(app.config)
    dispatched = 0
    failed = 0
    for request in repo.list_requested_runs(limit=20):
        run_id = str(request.get("run_id") or "")
        job_id = str(request.get("job_id") or "")
        job = repo.get_job(job_id)
        if not job:
            repo.mark_run_finished(run_id, status="failed", message="Pianificazione non trovata.")
            failed += 1
            continue
        existing = scheduler.get_job(job_id)
        manual_job_id = f"manual_{job_id}_{run_id[:8]}"
        try:
            if existing and job.get("built_in"):
                scheduler.add_job(
                    _run_existing_scheduler_job,
                    trigger=DateTrigger(run_date=datetime.now()),
                    args=[existing.func, list(existing.args or []), dict(existing.kwargs or {}), repo.db_path, run_id],
                    id=manual_job_id,
                    replace_existing=True,
                    max_instances=1,
                )
            else:
                scheduler.add_job(
                    lambda job=job, run_id=run_id: _run_dynamic_job(app, repo, job, run_id=run_id),
                    trigger=DateTrigger(run_date=datetime.now()),
                    id=manual_job_id,
                    replace_existing=True,
                    max_instances=1,
                )
            dispatched += 1
        except Exception as exc:
            repo.mark_run_finished(
                run_id,
                status="failed",
                message="Esecuzione manuale non avviata.",
                error_message=str(exc),
            )
            failed += 1
    return {"dispatched": dispatched, "failed": failed}


def _run_existing_scheduler_job(func, args: list[Any], kwargs: dict[str, Any], db_path: Path, run_id: str) -> None:
    repo = SchedulerRegistryRepository(db_path)
    repo.mark_run_running(run_id)
    started = time.monotonic()
    try:
        result = func(*(args or []), **(kwargs or {}))
        result_payload = result if isinstance(result, dict) else {"summary": "" if result is None else str(result)[:4000]}
        result_ok = result_payload.get("ok") if isinstance(result_payload, dict) else True
        repo.mark_run_finished(
            run_id,
            status="completed" if result_ok is not False else "failed",
            message=f"Esecuzione completata in {time.monotonic() - started:.1f}s.",
            result=result_payload,
            error_message=str(result_payload.get("error") or "") if result_ok is False else "",
        )
    except Exception as exc:
        repo.mark_run_finished(
            run_id,
            status="failed",
            message="Esecuzione non completata.",
            error_message=str(exc),
        )
        raise
