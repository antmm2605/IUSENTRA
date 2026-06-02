"""Crash test operativo, repair loop e backup blindato del prodotto."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic
import traceback
from typing import Any, Callable

from click.testing import CliRunner

from pct.backup import GestioneBackup, StatoBackup, TipoBackup


OPERATIONAL_CRASH_SCHEDULES: tuple[dict[str, str], ...] = (
    {"code": "morning", "label": "Autotest mattina", "time": "07:00"},
    {"code": "midday", "label": "Autotest meta' giornata", "time": "13:30"},
    {"code": "evening", "label": "Autotest sera", "time": "19:30"},
)

OPERATIONAL_BACKUP_SCHEDULE: dict[str, str] = {
    "code": "nightly",
    "label": "Backup blindato notturno",
    "time": "23:50",
}


@dataclass(frozen=True)
class CrashPhase:
    phase_id: str
    label: str
    description: str
    selectors: tuple[str, ...] = ()
    phase_type: str = "pytest"
    fallback_check_id: str = ""


CRASH_PHASES: tuple[CrashPhase, ...] = (
    CrashPhase(
        phase_id="setup_runtime",
        label="Fase 1 - Avvio e setup studio",
        description="Login, tenant, DB, AI e worker devono risultare spiegabili e pronti.",
        phase_type="health",
    ),
    CrashPhase(
        phase_id="dirty_data",
        label="Fase 2 - Cliente e fascicolo con dati sporchi",
        description="Duplicati, CF errato e campi obbligatori mancanti devono essere bloccati.",
        selectors=("tests/e2e/test_operational_crash_day.py", "-k", "dirty_data"),
        fallback_check_id="dirty_data",
    ),
    CrashPhase(
        phase_id="business_flow",
        label="Fase 3 - Attivita', parcella e incasso",
        description="Il dominio economico deve restare coerente dopo salvataggi e modifiche.",
        selectors=("tests/e2e/test_studio_reale_flow.py",),
        fallback_check_id="business_flow",
    ),
    CrashPhase(
        phase_id="ai_pipeline",
        label="Fase 4 - Pipeline AI e review",
        description="Draft, review, diff umano e publish SQL devono restare auditabili.",
        selectors=("tests/e2e/test_ai_pipeline_full.py",),
        fallback_check_id="ai_pipeline",
    ),
    CrashPhase(
        phase_id="publish_safety",
        label="Fase 5 - Publish sicuro",
        description="Un errore a meta' publish non deve corrompere ne' draft ne' database.",
        selectors=("tests/e2e/test_operational_crash_day.py", "-k", "publish_failure"),
        fallback_check_id="publish_safety",
    ),
    CrashPhase(
        phase_id="migration_rollback",
        label="Fase 6 - Migrazione tenant e rollback",
        description="Snapshot, diff e rollback devono funzionare davvero anche su tenant sporchi.",
        selectors=("tests/e2e/test_tenant_migration_full.py",),
        fallback_check_id="migration_rollback",
    ),
    CrashPhase(
        phase_id="observability_operator",
        label="Fase 7 - Observability e remediation",
        description="Gli errori devono essere spiegati in modo operativo, non come semplice 500.",
        selectors=("tests/e2e/test_operational_crash_day.py", "-k", "observability"),
        fallback_check_id="observability_operator",
    ),
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _stamp_now() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


_SENSITIVE_REPORT_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "private_key",
    "master_key",
    "signing_key",
    "pin",
)


def _redact_report_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_REPORT_KEY_PARTS):
                redacted[str(key)] = "[redatto]" if item not in (None, "", []) else item
            else:
                redacted[str(key)] = _redact_report_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [_redact_report_sensitive_values(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_report_sensitive_values(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        _redact_report_sensitive_values(payload),
        ensure_ascii=False,
        indent=2,
    )
    # codeql[py/clear-text-storage-sensitive-data]
    path.write_text(encoded, encoding="utf-8")
    return str(path)


def _phase_excerpt(output: str, *, max_lines: int = 18) -> str:
    lines = [str(line).rstrip() for line in str(output or "").splitlines() if str(line).strip()]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[:max_lines] + ["..."])


def _assert_runtime(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _pytest_available() -> bool:
    try:
        return importlib.util.find_spec("pytest") is not None
    except Exception:
        return False


def _write_runtime_studio_config(target_path: Path, source_path: str = "") -> None:
    source = Path(str(source_path or "").strip())
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        shutil.copy2(source, target_path)
        return
    payload = {
        "studio": {
            "nome": "Studio Crash Test",
            "avvocato": "Avv. Crash Test",
            "email": "studio.crash@example.it",
        },
        "pec": {
            "indirizzo": "studio.crash@pec.example.it",
            "smtp_host": "smtp.pec.example.it",
        },
        "smtp": {
            "host": "smtp.office365.com",
        },
        "ai": {
            "enabled": True,
            "base_url": "http://127.0.0.1:11434/api",
            "chat_model": "gemma3:1b",
            "embed_model": "embeddinggemma:300m",
        },
    }
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_isolated_app_config(base_config: dict[str, Any] | None, temp_root: Path) -> dict[str, Any]:
    base = dict(base_config or {})
    cfg = {
        "TESTING": True,
        "SECRET_KEY": str(base.get("SECRET_KEY") or "operational-crash-secret"),
        "BOOTSTRAP_ADMIN_PASSWORD": "admin",
        "BOOTSTRAP_ADMIN_CREDENTIALS_PATH": str(temp_root / "auth" / "bootstrap_admin.json"),
        "AUTH_DB": str(temp_root / "auth" / "utenti.json"),
        "AUDIT_DB": str(temp_root / "auth" / "audit.json"),
        "CLIENTI_DB": str(temp_root / "clienti" / "anagrafica.json"),
        "CONDIVISIONI_DB": str(temp_root / "clienti" / "condivisioni.json"),
        "FASCICOLI_DB": str(temp_root / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(temp_root / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(temp_root / "fascicoli" / "archivio"),
        "AGENDA_DB": str(temp_root / "agenda" / "appuntamenti.json"),
        "CALENDAR_SYNC_DB": str(temp_root / "agenda" / "calendar_sync.json"),
        "SCADENZIARIO_DB": str(temp_root / "scadenziario" / "scadenze.json"),
        "MESSAGGI_DB": str(temp_root / "messaggi" / "storico.json"),
        "EMAIL_CASELLA_DB": str(temp_root / "email" / "casella.json"),
        "SEARCH_INDEX": str(temp_root / "search" / "index.db"),
        "SOGGETTI_DB": str(temp_root / "soggetti" / "anagrafica.json"),
        "SOGGETTI_PARTI_DB": str(temp_root / "soggetti" / "parti.json"),
        "PST_IMPORT_DIR": str(temp_root / "import_pst"),
        "VALIDATION_RUNS_DB": str(temp_root / "intelligence" / "validation_runs.json"),
        "LEGAL_INTELLIGENCE_DB": str(temp_root / "intelligence" / "motori.json"),
        "NORMATIVE_TABLES_DB": str(temp_root / "intelligence" / "tabelle_normative.json"),
        "GIURISPRUDENZA_DB": str(temp_root / "intelligence" / "giurisprudenza.json"),
        "WORKSPACE_INTELLIGENCE_DB": str(temp_root / "intelligence" / "workspace_intelligence.json"),
        "TEMPLATE_ATTI_DB": str(temp_root / "template_atti" / "templates.json"),
        "TEMPLATE_ATTI_PREFS_DB": str(temp_root / "template_atti" / "editor_layout.json"),
        "PREVENTIVI_DB": str(temp_root / "preventivi" / "preventivi.json"),
        "FATTURAZIONE_DB": str(temp_root / "fatturazione" / "parcelle.json"),
        "TIMESHEET_DB": str(temp_root / "timesheet" / "entries.json"),
        "PAGAMENTI_DIR": str(temp_root / "pagamenti"),
        "LOCAL_AI_DB": str(temp_root / "intelligence" / "local_ai.db"),
        "LOCAL_AI_MODELS_DIR": str(temp_root / "intelligence" / "models"),
        "LOCAL_AI_POLICY": str(base.get("LOCAL_AI_POLICY") or (Path.cwd() / "config" / "ai-policy.json")),
        "STUDIO_CONFIG": str(temp_root / "config" / "studio.json"),
        "PDP_PENALE_DB": str(temp_root / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(temp_root / "telematico" / "workflow.db"),
        "PORTALE_DB": str(temp_root / "portale" / "portali.json"),
        "PORTALE_UPLOADS": str(temp_root / "portale" / "uploads"),
        "TENANTS_REGISTRY": str(temp_root / "tenants.json"),
        "STUDIO_DB": str(temp_root / "studio.db"),
        "BACKUP_DIR": str(temp_root / "backup"),
    }
    _write_runtime_studio_config(
        Path(cfg["STUDIO_CONFIG"]),
        str(base.get("STUDIO_CONFIG") or ""),
    )
    return cfg


def _login_admin(app: Any) -> None:
    with app.test_client() as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        _assert_runtime(
            response.status_code == 302,
            f"Login admin non riuscito nello smoke isolato ({response.status_code}).",
        )


def _run_runtime_dirty_data_check(runtime_context: dict[str, Any] | None = None) -> str:
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo

    with TemporaryDirectory(prefix="iusentra-crash-dirty-") as tmp:
        root = Path(tmp)
        clienti = GestioneClienti(db_path=str(root / "clienti" / "anagrafica.json"))
        fascicoli = GestioneFascicoli(
            db_path=str(root / "fascicoli" / "fascicoli.json"),
            documents_dir=str(root / "fascicoli" / "documenti"),
            archive_dir=str(root / "fascicoli" / "archivio"),
        )

        cliente = clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Anna",
            cognome="Verdi",
            codice_fiscale="VRDNNA80A41H501Z",
            email="anna.verdi@example.it",
        )

        blocked: list[str] = []
        for label, payload in (
            (
                "duplicato_cf",
                {
                    "tipo": TipoCliente.PERSONA_FISICA,
                    "nome": "Anna",
                    "cognome": "Duplicata",
                    "codice_fiscale": "VRDNNA80A41H501Z",
                },
            ),
            (
                "cf_non_valido",
                {
                    "tipo": TipoCliente.PERSONA_FISICA,
                    "nome": "Mario",
                    "cognome": "Rossi",
                    "codice_fiscale": "ROSSIMARIO",
                },
            ),
        ):
            try:
                clienti.nuovo(payload.pop("tipo"), **payload)
            except ValueError:
                blocked.append(label)

        try:
            fascicoli.nuovo(
                titolo="   ",
                tipo=TipoFascicolo.CIVILE,
                id_cliente=cliente.id,
                nome_cliente=cliente.nome_completo,
            )
        except ValueError:
            blocked.append("fascicolo_incompleto")

        _assert_runtime(len(clienti.tutti()) == 1, "Sono entrati clienti sporchi non ammessi.")
        _assert_runtime(clienti.get(cliente.id) is not None, "Il cliente valido non e' rimasto persistito.")
        _assert_runtime(fascicoli.tutti(stato=None) == [], "E' stato creato un fascicolo incompleto.")
        _assert_runtime(
            set(blocked) == {"duplicato_cf", "cf_non_valido", "fascicolo_incompleto"},
            f"Validazioni sporche incomplete: {blocked}",
        )
        return "\n".join(
            [
                f"Cliente valido creato: {cliente.id}",
                "Duplicato CF bloccato",
                "Codice fiscale errato bloccato",
                "Fascicolo incompleto bloccato",
            ]
        )


def _run_runtime_business_flow_check(runtime_context: dict[str, Any] | None = None) -> str:
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.economic_pipeline import genera_parcella_da_timesheet
    from pct.fascicoli import GestioneFascicoli
    from pct.fatturazione import GestioneFatturazione, StatoParcella
    from pct.pagamenti import GestionePagamenti
    from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo
    from pct.scadenziario import GestioneScadenziario
    from pct.studio_demo import build_studio_demo_snapshot
    from pct.timesheet import GestioneTimesheet, StatoTimesheet
    from pct.workflow_commerciale import apri_fascicolo_automatico

    with TemporaryDirectory(prefix="iusentra-crash-business-") as tmp:
        root = Path(tmp)
        clienti = GestioneClienti(db_path=str(root / "clienti" / "anagrafica.json"))
        preventivi = GestionePreventivi(db_path=str(root / "preventivi" / "preventivi.json"))
        fascicoli = GestioneFascicoli(
            db_path=str(root / "fascicoli" / "fascicoli.json"),
            documents_dir=str(root / "fascicoli" / "documenti"),
            archive_dir=str(root / "fascicoli" / "archivio"),
        )
        scadenze = GestioneScadenziario(str(root / "scadenziario" / "scadenze.json"))
        timesheet = GestioneTimesheet(db_path=str(root / "timesheet" / "entries.json"))
        fatturazione = GestioneFatturazione(db_path=str(root / "fatturazione" / "parcelle.json"))
        pagamenti = GestionePagamenti(db_dir=str(root / "pagamenti"))

        cliente = clienti.nuovo(
            TipoCliente.PERSONA_FISICA,
            nome="Elena",
            cognome="Giovannella",
            codice_fiscale="GVNLNE80A41H224R",
            avvocato_referente="Avv. Demo",
        )
        clienti.aggiorna_indirizzo(
            cliente.id,
            "residenza",
            via="Via Roma 12",
            comune="Palmi",
            provincia="RC",
            cap="89015",
        )
        clienti.aggiorna_recapiti(
            cliente.id,
            email="elena.giovannella@example.it",
            cellulare="3331234567",
        )
        cliente = clienti.get(cliente.id)
        _assert_runtime(cliente is not None, "Il cliente non e' stato recuperato dopo il salvataggio.")
        _assert_runtime(
            bool(getattr(cliente, "profilo_completo_per_conferimento", False)),
            "Il profilo cliente non risulta completo per il conferimento.",
        )

        preventivo = preventivi.crea_preventivo(
            id_cliente=cliente.id,
            oggetto="Vendita immobili e attivita' preparatorie",
            voci=[
                VocePreventivo(
                    descrizione="Fase iniziale",
                    importo=850.0,
                    tipo=TipoVoce.ONORARIO,
                )
            ],
            creato_da="superadmin",
            id_pratica="vendita_immobili",
            area_pratica="Civile",
            tipo_compenso="Per fasi processuali (D.M. 55/2014)",
        )
        preventivo, conferimento = preventivi.registra_accettazione_preventivo(
            preventivo.id,
            workflow_channel="ONLINE",
            via="PORTALE_CLIENTE",
            auto_crea_conferimento=True,
            avvocato_referente="Avv. Demo",
        )
        _assert_runtime(conferimento is not None, "Il conferimento non e' stato creato automaticamente.")
        conferimento = preventivi.registra_firma_conferimento(
            conferimento.id,
            via="PORTALE_CLIENTE",
            workflow_channel="ONLINE",
        )
        apertura = apri_fascicolo_automatico(
            gp=preventivi,
            gf=fascicoli,
            gs=scadenze,
            cliente=cliente,
            preventivo=preventivi.get_preventivo(preventivo.id),
            conferimento=preventivi.get_conferimento(conferimento.id),
            avvocato="Avv. Demo",
        )
        fascicolo = apertura["fascicolo"]
        _assert_runtime(bool(apertura.get("created")), "Il fascicolo automatico non e' stato aperto.")
        _assert_runtime(fascicolo.id_cliente == cliente.id, "Il fascicolo non punta al cliente corretto.")

        voce = timesheet.crea(
            descrizione="Analisi atti e preparazione prima udienza",
            minuti=90,
            id_fascicolo=fascicolo.id,
            id_cliente=cliente.id,
            username="avv.demo",
            valore_unitario=180.0,
            fatturabile=True,
            stato=StatoTimesheet.APERTO,
            origine="runtime-crash",
        )
        timesheet.cambia_stato(voce.id, StatoTimesheet.VALIDATO)

        billing = genera_parcella_da_timesheet(
            timesheet=timesheet,
            fatturazione=fatturazione,
            creato_da="avv.demo",
            entry_ids=[voce.id],
            data_scadenza="2026-05-15",
        )
        parcella = billing["parcella"]
        _assert_runtime(parcella.id_fascicolo == fascicolo.id, "La parcella non e' collegata al fascicolo.")

        link = pagamenti.crea_link(
            id_parcella=parcella.id,
            id_cliente=cliente.id,
            importo=parcella.totale,
            descrizione="Saldo parcella fascicolo vendita immobili",
        )
        pagamenti.segna_pagato(link.id, provider="BONIFICO", tx_id="TRX-CRASH-001")
        fatturazione.cambia_stato(
            parcella.id,
            StatoParcella.PAGATA,
            data_pagamento="2026-04-19",
            metodo_pagamento="BONIFICO",
        )

        snapshot = build_studio_demo_snapshot(
            clienti=clienti.tutti(),
            preventivi=preventivi.tutti_preventivi(),
            conferimenti=preventivi.tutti_conferimenti(),
            fascicoli=fascicoli.tutti(stato=None),
            timesheet_entries=timesheet.tutte(),
            parcelle=fatturazione.tutte(),
            payment_links=pagamenti.tutti_link(),
        )
        _assert_runtime(bool(snapshot.get("ready")), "Lo snapshot studio non risulta pronto.")
        _assert_runtime(
            snapshot.get("ready_steps") == snapshot.get("steps_total"),
            "Lo snapshot studio ha passi incompleti.",
        )
        _assert_runtime(float(snapshot.get("saldo_aperto") or 0.0) == 0.0, "Il saldo aperto non e' a zero.")
        _assert_runtime(int(snapshot.get("link_incasso_attivi") or 0) == 0, "Restano link di incasso attivi.")
        return "\n".join(
            [
                f"Cliente creato: {cliente.id}",
                f"Preventivo accettato: {preventivo.id}",
                f"Conferimento firmato: {conferimento.id}",
                f"Fascicolo aperto: {fascicolo.id}",
                f"Parcella pagata: {parcella.id} -> {parcella.totale:.2f} EUR",
                "Workflow cliente -> incasso coerente e saldo aperto a zero",
            ]
        )


def _run_runtime_ai_pipeline_check(runtime_context: dict[str, Any] | None = None) -> str:
    from web.app import create_app
    from web.services.legal_coverage_surface import build_repository

    base_config = dict((runtime_context or {}).get("base_config") or {})
    with TemporaryDirectory(prefix="iusentra-crash-ai-") as tmp:
        root = Path(tmp)
        cfg = _build_isolated_app_config(base_config, root)
        app = create_app({**cfg, "STUDIO_DB": str(root / "studio.db")})

        with app.test_client() as client:
            response = client.post(
                "/login",
                data={"username": "admin", "password": "admin"},
                follow_redirects=False,
            )
            _assert_runtime(response.status_code == 302, "Login admin coverage non riuscito.")

            for action in ("audit", "gaps", "drafts"):
                action_response = client.post(
                    f"/admin/copertura-ai/esegui/{action}",
                    data={},
                    follow_redirects=True,
                )
                _assert_runtime(
                    action_response.status_code == 200,
                    f"L'azione coverage '{action}' non si e' chiusa correttamente ({action_response.status_code}).",
                )

            drafts_response = client.get("/admin/copertura-ai/api/drafts")
            _assert_runtime(drafts_response.status_code == 200, "La coda draft coverage non e' leggibile.")
            drafts = drafts_response.get_json() or []
            _assert_runtime(bool(drafts), "La pipeline coverage non ha prodotto bozze.")
            draft_id = int(drafts[0]["id"])

            detail_response = client.get(f"/admin/copertura-ai/api/drafts/{draft_id}")
            _assert_runtime(detail_response.status_code == 200, "Il dettaglio draft coverage non e' leggibile.")
            detail = detail_response.get_json() or {}
            _assert_runtime(detail.get("retrieval_examples_json") is not None, "Manca il retrieval del draft coverage.")
            _assert_runtime("autopublish_policy" in detail, "Manca la policy autopublish del draft.")
            _assert_runtime("ai_governance" in detail, "Manca la governance AI del draft.")

            approve_response = client.post(
                f"/admin/copertura-ai/api/drafts/{draft_id}/approve",
                json={
                    "reviewer": "review-runtime",
                    "review_reason": "Bozza validata e pronta per il catalogo SQL.",
                    "review_signature": "Avv. Runtime",
                },
            )
            approve_payload = approve_response.get_json() or {}
            _assert_runtime(
                approve_response.status_code == 200 and bool(approve_payload.get("ok")),
                "L'approvazione del draft coverage non e' riuscita.",
            )

            approved_detail = client.get(f"/admin/copertura-ai/api/drafts/{draft_id}")
            approved_payload = approved_detail.get_json() or {}
            _assert_runtime("summary" in (approved_payload.get("review_diff_json") or {}), "Manca il diff review del draft.")

            publish_response = client.post(
                f"/admin/copertura-ai/api/drafts/{draft_id}/publish",
                json={
                    "reviewer": "review-runtime",
                    "review_reason": "Publish confermato dopo controllo strutturato.",
                    "review_signature": "Avv. Runtime",
                },
            )
            publish_payload = publish_response.get_json() or {}
            _assert_runtime(
                publish_response.status_code == 200 and bool(publish_payload.get("ok")),
                "Il publish SQL coverage non e' riuscito.",
            )
            _assert_runtime(
                int(((publish_payload.get("result") or {}).get("published_total")) or 0) == 1,
                "Il publish SQL coverage non ha prodotto l'aggiornamento atteso.",
            )

        with app.app_context():
            repository = build_repository(app)
            draft = repository.get_draft(draft_id)
            history = repository.list_published_history(limit=10)
            review_history = repository.list_review_history(draft_id)

        _assert_runtime(draft is not None and draft.get("status") == "published", "Il draft coverage non risulta pubblicato.")
        _assert_runtime(str(draft.get("review_signature") or "") == "Avv. Runtime", "La firma review non e' persistita.")
        _assert_runtime(bool(history), "Lo storico publish coverage e' vuoto.")
        _assert_runtime(any(str(row.get("review_action") or "") == "published" for row in review_history), "Manca l'evento audit di publish.")

        conn = sqlite3.connect(str(root / "studio.db"))
        try:
            procedures = conn.execute("SELECT COUNT(*) FROM legal_procedures").fetchone()[0]
            published = conn.execute("SELECT COUNT(*) FROM published_procedure_history").fetchone()[0]
            audit_rows = conn.execute("SELECT COUNT(*) FROM coverage_review_audit_log").fetchone()[0]
        finally:
            conn.close()

        _assert_runtime(procedures >= 1, "Il catalogo SQL non e' stato aggiornato.")
        _assert_runtime(published >= 1, "Manca lo storico publish SQL.")
        _assert_runtime(audit_rows >= 2, "L'audit coverage non e' completo.")
        return "\n".join(
            [
                f"Draft coverage pubblicato: {draft_id}",
                f"Procedure SQL: {procedures}",
                f"Storico publish: {published}",
                f"Audit review: {audit_rows}",
                "Diff AI vs umano e policy autopublish presenti",
            ]
        )


def _run_runtime_publish_safety_check(runtime_context: dict[str, Any] | None = None) -> str:
    from pct.legal_coverage_pipeline import approve_draft, publish_single_draft
    from web.app import create_app
    from web.services.legal_coverage_surface import build_repository, run_action

    base_config = dict((runtime_context or {}).get("base_config") or {})
    with TemporaryDirectory(prefix="iusentra-crash-publish-") as tmp:
        root = Path(tmp)
        cfg = _build_isolated_app_config(base_config, root)
        app = create_app({**cfg, "STUDIO_DB": str(root / "studio.db")})

        with app.app_context():
            repository = build_repository(app)
            _assert_runtime(repository.ping() is True, "Il repository coverage non risponde.")
            run_action("audit")
            run_action("gaps")
            run_action("drafts", limit=5)

            drafts = repository.list_drafts()
            _assert_runtime(bool(drafts), "La pipeline coverage non ha generato draft per il test publish.")
            draft_id = int(drafts[0]["id"])
            approve_draft(
                repository,
                draft_id,
                reviewer="review-operativo",
                review_reason="Bozza approvata per test di failure controllata.",
                review_signature="Avv. Operativo",
            )

            original_apply = repository.apply_generated_sql

            def _broken_apply(sql_payload: Any) -> Any:
                raise RuntimeError("Database coverage non raggiungibile durante il publish di prova.")

            repository.apply_generated_sql = _broken_apply
            failure_message = ""
            try:
                try:
                    publish_single_draft(repository, draft_id, apply_to_db=True)
                except RuntimeError as exc:
                    failure_message = str(exc)
            finally:
                repository.apply_generated_sql = original_apply

            _assert_runtime(
                "Database coverage non raggiungibile" in failure_message,
                "Il failure mode del publish non e' stato intercettato.",
            )
            draft = repository.get_draft(draft_id)
            history = repository.list_published_history(limit=10)
            review_history = repository.list_review_history(draft_id)

        _assert_runtime(draft is not None and draft.get("status") == "approved", "Il draft e' stato corrotto dopo il failure publish.")
        _assert_runtime(history == [], "Lo storico publish e' stato popolato nonostante l'errore.")
        _assert_runtime(
            any(str(row.get("review_action") or "") == "approved" for row in review_history),
            "Lo storico review non contiene l'approvazione che precede il failure.",
        )
        return "\n".join(
            [
                f"Draft coverage preservato: {draft_id}",
                f"Messaggio di failure: {failure_message}",
                "Nessuna pubblicazione SQL parziale",
                "Draft rimasto in stato approved con audit integro",
            ]
        )


def _seed_migration_source(paths: dict[str, str]) -> None:
    from pct.agenda import Agenda, TipoAppuntamento
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo
    from pct.scadenziario import GestioneScadenziario, TipoTermine

    clienti = GestioneClienti(db_path=paths["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Lucia",
        cognome="Bianchi",
        codice_fiscale="BNCLCU85B42H501R",
        email="lucia.bianchi@example.it",
    )
    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        titolo="Migrazione pratica monitorata",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Milano",
        numero_rg="8765",
        anno_rg=2026,
        oggetto="Verifica cutover storage",
    )
    agenda = Agenda(db_path=paths["AGENDA_DB"])
    agenda.aggiungi(
        titolo="Udienza di prova",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=f"{date.today().isoformat()}T09:30:00",
        durata_minuti=30,
        cliente=cliente.nome_completo,
        id_cliente=cliente.id,
        procedimento=fascicolo.numero,
        tribunale="Tribunale di Milano",
    )
    GestioneScadenziario(paths["SCADENZIARIO_DB"]).nuova(
        titolo="Deposito memoria di prova",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza=date.today().isoformat(),
        id_fascicolo=fascicolo.id,
        perentorio=True,
    )


def _run_runtime_migration_rollback_check(runtime_context: dict[str, Any] | None = None) -> str:
    from pct.cli import cli
    from pct.tenant import GestioneTenant
    from web.app import create_app
    from web.services.migration_assistant import build_migration_assistant, execute_migration_assistant

    base_config = dict((runtime_context or {}).get("base_config") or {})
    with TemporaryDirectory(prefix="iusentra-crash-migration-") as tmp:
        root = Path(tmp)
        cfg = _build_isolated_app_config(base_config, root)
        manager = GestioneTenant(cfg["TENANTS_REGISTRY"])
        studio = manager.crea("Studio Migrazione Runtime", "studio-migrazione-runtime", db_config={"mode": "JSON"})
        paths = manager.percorsi_dati(studio.slug)
        _seed_migration_source(paths)
        app = create_app(cfg)

        with app.app_context():
            report = execute_migration_assistant(selected_slug=studio.slug, target="sqlite")
            payload = build_migration_assistant(selected_slug=studio.slug)

        _assert_runtime(str(report.get("target") or "") == "sqlite", "La migrazione non ha colpito il target SQLite.")
        _assert_runtime(bool(report.get("success")), "La migrazione tenant non si e' chiusa con successo.")
        _assert_runtime(Path(str(report.get("report_path") or "")).exists(), "Il report migrazione non esiste.")
        _assert_runtime(
            Path(str(report.get("pre_migration_snapshot_path") or "")).exists(),
            "Lo snapshot pre-migrazione non esiste.",
        )
        diff_domains = dict(((report.get("diff_summary") or {}).get("by_domain")) or {})
        _assert_runtime(
            int(((diff_domains.get("clienti") or {}).get("prima")) or 0) == 1,
            "Il diff migrazione non censisce correttamente i clienti prima del cutover.",
        )
        _assert_runtime(
            int(((diff_domains.get("clienti") or {}).get("dopo")) or 0) == 1,
            "Il diff migrazione non censisce correttamente i clienti dopo il cutover.",
        )
        _assert_runtime(
            bool(((payload.get("last_execution") or {}).get("rollback") or {}).get("command")),
            "La superficie migrazione non espone il comando di rollback.",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "migrate",
                "--rollback",
                f"--tenant={studio.slug}",
                f"--registry={cfg['TENANTS_REGISTRY']}",
            ],
        )
        _assert_runtime(result.exit_code == 0, f"Il rollback CLI non e' riuscito: {result.output}")

        rollback_payload = {}
        start = result.output.find("{")
        if start >= 0:
            rollback_payload = json.loads(result.output[start:])
        _assert_runtime(bool(rollback_payload.get("success")), "Il rollback non ha restituito un esito positivo.")
        _assert_runtime(Path(str(rollback_payload.get("report_path") or "")).exists(), "Il report rollback non esiste.")

        manager_after = GestioneTenant(cfg["TENANTS_REGISTRY"])
        studio_after = manager_after.get(studio.slug)
        _assert_runtime(studio_after is not None, "Lo studio migrato non e' piu' leggibile dopo il rollback.")
        _assert_runtime(
            str(studio_after.database.normalized_mode or "") == "JSON",
            "Il rollback non ha ripristinato il mode JSON.",
        )
        _assert_runtime(
            str(studio_after.database.effective_runtime_kind or "") == "json",
            "Il rollback non ha ripristinato il runtime JSON.",
        )
        return "\n".join(
            [
                f"Snapshot pre-migrazione: {report['pre_migration_snapshot_path']}",
                f"Report diff: {report['report_path']}",
                f"Rollback CLI: {rollback_payload.get('report_path')}",
                "Cutover e ritorno a JSON riusciti senza perdita dati",
            ]
        )


def _run_runtime_observability_check(runtime_context: dict[str, Any] | None = None) -> str:
    from web.app import create_app
    from web.services.system_health_surface import build_system_health_api_payload
    import web.services.system_health_surface as system_health_surface

    base_config = dict((runtime_context or {}).get("base_config") or {})
    with TemporaryDirectory(prefix="iusentra-crash-observability-") as tmp:
        root = Path(tmp)
        cfg = _build_isolated_app_config(base_config, root)
        app = create_app(cfg)

        original_builder = system_health_surface.build_observability_payload

        def _fake_payload(_app: Any) -> dict[str, Any]:
            return {
                "alerts": [
                    {
                        "code": "OCR_QUEUE_OVERFLOW",
                        "normalized_code": "OCR_QUEUE_OVERFLOW",
                        "title": "OCR rallentato",
                        "operator_message": "La coda OCR e' oltre soglia e l'operatore deve intervenire.",
                        "remediation": "Verifica worker OCR o risorse CPU prima di continuare.",
                        "severity": "warning",
                        "family": "OCR",
                        "component": "worker",
                    },
                    {
                        "code": "TENANT_DB_ERROR",
                        "normalized_code": "TENANT_DB_ERROR",
                        "title": "Database tenant non raggiungibile",
                        "operator_message": "Il backend strutturato dello studio non risponde.",
                        "remediation": "Blocca il publish e controlla la connessione SQL o PostgreSQL.",
                        "severity": "danger",
                        "family": "STORAGE",
                        "component": "database",
                    },
                ],
                "storage": {"default_mode": "SQLITE"},
                "scheduler_worker_mode": True,
                "ocr": {"in_coda": 512, "throughput_ultima_ora": 2},
                "providers": {"local_ai": {"runtime": {"status": "ok"}}},
                "error_taxonomy": {
                    "OCR": ["OCR_QUEUE_OVERFLOW"],
                    "STORAGE": ["TENANT_DB_ERROR"],
                },
            }

        system_health_surface.build_observability_payload = _fake_payload
        try:
            with app.app_context():
                payload = build_system_health_api_payload()
        finally:
            system_health_surface.build_observability_payload = original_builder

        _assert_runtime(str(payload.get("status") or "") == "error", "Lo stato health non segnala l'errore operativo.")
        _assert_runtime(str(payload.get("ocr") or "") == "degraded", "La degradazione OCR non e' stata rilevata.")
        _assert_runtime(str(payload.get("db") or "") == "error", "L'errore backend tenant non e' stato rilevato.")
        actions = list(payload.get("actions_required") or [])
        _assert_runtime(bool(actions), "Mancano azioni suggerite per l'operatore.")
        first_action = actions[0]
        _assert_runtime(bool(first_action.get("message")), "L'operatore non riceve il messaggio esplicativo.")
        _assert_runtime(bool(first_action.get("action")), "L'operatore non riceve la remediation.")
        taxonomy = dict(payload.get("error_taxonomy") or {})
        _assert_runtime("OCR" in taxonomy, "La tassonomia errori non include OCR.")
        return "\n".join(
            [
                f"Stato sistema: {payload.get('status')}",
                f"Primo alert: {first_action.get('code')} -> {first_action.get('message')}",
                f"Azione suggerita: {first_action.get('action')}",
                "Tassonomia errori e remediation operatore presenti",
            ]
        )


def _run_runtime_check(
    check_id: str,
    *,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handlers = {
        "dirty_data": _run_runtime_dirty_data_check,
        "business_flow": _run_runtime_business_flow_check,
        "ai_pipeline": _run_runtime_ai_pipeline_check,
        "publish_safety": _run_runtime_publish_safety_check,
        "migration_rollback": _run_runtime_migration_rollback_check,
        "observability_operator": _run_runtime_observability_check,
    }
    started = monotonic()
    handler = handlers.get(str(check_id or "").strip())
    if handler is None:
        return {
            "status": "failed",
            "return_code": 1,
            "duration_seconds": round(monotonic() - started, 2),
            "output_excerpt": _phase_excerpt(f"Nessun controllo runtime registrato per '{check_id}'."),
        }
    try:
        output = handler(runtime_context)
        return {
            "status": "passed",
            "return_code": 0,
            "duration_seconds": round(monotonic() - started, 2),
            "output_excerpt": _phase_excerpt(output),
        }
    except Exception:
        return {
            "status": "failed",
            "return_code": 1,
            "duration_seconds": round(monotonic() - started, 2),
            "output_excerpt": _phase_excerpt(traceback.format_exc()),
        }


def _run_pytest_phase(
    selectors: tuple[str, ...],
    *,
    cwd: str = "",
    python_executable: str = "",
    timeout_seconds: int = 900,
    fallback_check_id: str = "",
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback_notice = "Pytest non disponibile nel runtime, uso il controllo operativo interno equivalente."
    if fallback_check_id and not _pytest_available():
        outcome = _run_runtime_check(fallback_check_id, runtime_context=runtime_context)
        outcome["output_excerpt"] = _phase_excerpt(f"{fallback_notice}\n{outcome['output_excerpt']}")
        return outcome

    command = [
        str(python_executable or sys.executable),
        "-X",
        "utf8",
        "-m",
        "pytest",
        "-q",
        *selectors,
    ]
    started = monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(timeout_seconds),
            check=False,
        )
        output = "\n".join(
            part for part in [completed.stdout or "", completed.stderr or ""] if str(part).strip()
        )
        if (
            fallback_check_id
            and completed.returncode != 0
            and "No module named pytest" in output
        ):
            outcome = _run_runtime_check(fallback_check_id, runtime_context=runtime_context)
            outcome["output_excerpt"] = _phase_excerpt(f"{fallback_notice}\n{outcome['output_excerpt']}")
            return outcome
        ok = completed.returncode == 0
        return {
            "status": "passed" if ok else "failed",
            "return_code": int(completed.returncode),
            "duration_seconds": round(monotonic() - started, 2),
            "output_excerpt": _phase_excerpt(output),
        }
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part
            for part in [
                str(getattr(exc, "stdout", "") or ""),
                str(getattr(exc, "stderr", "") or ""),
                "Timeout operativo raggiunto durante il crash test.",
            ]
            if str(part).strip()
        )
        return {
            "status": "failed",
            "return_code": 124,
            "duration_seconds": round(monotonic() - started, 2),
            "output_excerpt": _phase_excerpt(output),
        }


def _evaluate_health_phase(health_payload: dict[str, Any]) -> dict[str, Any]:
    alerts = list(health_payload.get("actions_required") or [])
    db_status = str(health_payload.get("db") or "error")
    scheduler_status = str(health_payload.get("scheduler") or "error")
    ocr_status = str(health_payload.get("ocr") or "error")
    ai_status = str(health_payload.get("ai") or "error")
    ok = db_status != "error" and scheduler_status != "error"
    lines = [
        f"DB: {db_status}",
        f"Scheduler: {scheduler_status}",
        f"OCR: {ocr_status}",
        f"AI: {ai_status}",
    ]
    for alert in alerts[:4]:
        lines.append(
            f"- {str(alert.get('code') or '')}: {str(alert.get('message') or '')} -> {str(alert.get('action') or '')}"
        )
    return {
        "status": "passed" if ok else "failed",
        "return_code": 0 if ok else 1,
        "duration_seconds": 0.0,
        "output_excerpt": _phase_excerpt("\n".join(lines)),
    }


def _build_quick_checks(
    phase_results: list[dict[str, Any]],
    health_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    indexed = {row["phase_id"]: row for row in phase_results}

    def _passed(phase_id: str) -> bool:
        return str((indexed.get(phase_id) or {}).get("status") or "") == "passed"

    return [
        {
            "id": "db_no_damage",
            "question": "Posso rompere il DB e il sistema non fa danni?",
            "ok": bool(
                health_payload.get("db") != "error"
                and _passed("publish_safety")
                and _passed("migration_rollback")
            ),
        },
        {
            "id": "ai_traceability",
            "question": "Posso spiegare ogni decisione AI?",
            "ok": _passed("ai_pipeline"),
        },
        {
            "id": "operator_clarity",
            "question": "Un non tecnico capisce tutti gli errori?",
            "ok": _passed("setup_runtime") and _passed("observability_operator"),
        },
        {
            "id": "migration_rollback",
            "question": "Posso migrare e tornare indietro senza paura?",
            "ok": _passed("migration_rollback"),
        },
        {
            "id": "dirty_data_blocked",
            "question": "I dati sporchi NON entrano mai?",
            "ok": _passed("dirty_data"),
        },
    ]


def _phase_failure_to_ticket(phase: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "dirty_data": (
            "DIRTY_DATA_NOT_BLOCKED",
            "danger",
            "I dati sporchi non sono bloccati",
            "Rinforza le validazioni dominio su clienti e fascicoli prima di usare il prodotto in produzione.",
        ),
        "business_flow": (
            "BUSINESS_FLOW_BROKEN",
            "danger",
            "Il workflow cliente -> incasso non e' coerente",
            "Controlla preventivi, conferimenti, fascicoli, parcelle e pagamenti fino a chiusura verde del golden path.",
        ),
        "ai_pipeline": (
            "AI_REVIEW_NOT_DEFENDABLE",
            "danger",
            "La review AI non e' difendibile",
            "Verifica diff AI vs umano, audit reviewer, firma e policy di publish prima di riattivare il flusso.",
        ),
        "publish_safety": (
            "PUBLISH_SQL_UNSAFE",
            "danger",
            "Il publish SQL non e' transazionale o non blocca l'errore",
            "Blocca l'autopublish e correggi rollback o gestione eccezioni del publisher.",
        ),
        "migration_rollback": (
            "MIGRATION_ROLLBACK_FAILED",
            "danger",
            "Migrazione o rollback tenant non affidabili",
            "Usa il report di migrazione, correggi il failure mode e non fare cutover prima di diff e rollback verdi.",
        ),
        "observability_operator": (
            "OBSERVABILITY_NOT_ACTIONABLE",
            "warning",
            "L'operatore non riceve remediation chiare",
            "Completa tassonomia errori, messaggi operatore e azioni suggerite sulle superfici admin.",
        ),
        "setup_runtime": (
            "SETUP_RUNTIME_FAILED",
            "danger",
            "Lo startup operativo non e' chiaro o non e' pronto",
            "Riallinea salute sistema, backend strutturato, worker e fallback AI prima dell'uso quotidiano.",
        ),
    }
    action_code, severity, title, remediation = mapping.get(
        str(phase.get("phase_id") or ""),
        (
            "CRASH_TEST_PHASE_FAILED",
            "warning",
            "Una fase del crash test e' fallita",
            "Apri il report operativo e correggi la fase segnalata prima del prossimo run.",
        ),
    )
    return {
        "action_code": action_code,
        "severity": severity,
        "status": "open",
        "title": title,
        "remediation": remediation,
        "phase_id": str(phase.get("phase_id") or ""),
        "phase_label": str(phase.get("label") or ""),
        "output_excerpt": str(phase.get("output_excerpt") or ""),
    }


def _health_alert_tickets(health_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for alert in list(health_payload.get("actions_required") or []):
        code = str(alert.get("code") or "").strip() or "SYSTEM_ALERT"
        rows.append(
            {
                "action_code": code,
                "severity": "danger" if code in {"TENANT_DB_ERROR", "MIGRATION_FAILED"} else "warning",
                "status": "open",
                "title": str(alert.get("title") or "Alert operativo"),
                "remediation": str(alert.get("action") or ""),
                "message": str(alert.get("message") or ""),
            }
        )
    return rows


def _dedupe_tickets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("action_code") or "").strip()
        if not code or code in deduped:
            continue
        deduped[code] = row
    return list(deduped.values())


def build_backup_targets(
    *,
    tenant_slug: str,
    backup_dir: str,
    local_mirror_dir: str = "",
    secondary_mirror_dir: str = "",
    secondary_label: str = "",
) -> dict[str, Any]:
    backup_root = Path(str(backup_dir or "./backup"))
    tenant_code = str(tenant_slug or "single-studio").strip().lower() or "single-studio"
    local_target = Path(str(local_mirror_dir or backup_root / "mirror" / "cliente"))
    secondary_target = (
        Path(str(secondary_mirror_dir or "")).expanduser()
        if str(secondary_mirror_dir or "").strip()
        else None
    )
    return {
        "tenant_slug": tenant_code,
        "backup_root": str(backup_root),
        "local_target": str(local_target),
        "secondary_target": str(secondary_target) if secondary_target else "",
        "secondary_label": str(secondary_label or "Destinazione esterna da configurare"),
    }


def _copy_backup_artifact(source_path: str, target_root: str, *, tenant_slug: str, stamp: str) -> str:
    source = Path(str(source_path or ""))
    if not source.exists():
        return ""
    target_dir = Path(str(target_root or "")).expanduser() / str(tenant_slug or "single-studio") / stamp
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return str(target)


def run_operational_backup_plan(
    *,
    tenant_slug: str,
    backup_manager: GestioneBackup,
    backup_dir: str,
    repository: Any | None = None,
    trigger_source: str = "manual",
    schedule_code: str = "",
    local_mirror_dir: str = "",
    secondary_mirror_dir: str = "",
    secondary_label: str = "",
) -> dict[str, Any]:
    targets = build_backup_targets(
        tenant_slug=tenant_slug,
        backup_dir=backup_dir,
        local_mirror_dir=local_mirror_dir,
        secondary_mirror_dir=secondary_mirror_dir,
        secondary_label=secondary_label,
    )
    stamp = _stamp_now()
    backup_runs: list[dict[str, Any]] = []
    for backup_type in (TipoBackup.COMPLETO, TipoBackup.INCREMENTALE):
        note = f"Backup blindato {backup_type.value.lower()} {trigger_source}"
        record = backup_manager.esegui_backup(tipo=backup_type, nota=note)
        local_copy_path = ""
        secondary_copy_path = ""
        if record.stato == StatoBackup.OK:
            local_copy_path = _copy_backup_artifact(
                record.percorso_file,
                targets["local_target"],
                tenant_slug=targets["tenant_slug"],
                stamp=stamp,
            )
            if targets["secondary_target"]:
                secondary_copy_path = _copy_backup_artifact(
                    record.percorso_file,
                    targets["secondary_target"],
                    tenant_slug=targets["tenant_slug"],
                    stamp=stamp,
                )
        payload = {
            "tenant_slug": targets["tenant_slug"],
            "executed_at": _now_iso(),
            "backup_scope": "nightly",
            "backup_type": backup_type.value,
            "status": record.stato.value,
            "primary_record_id": record.id,
            "primary_path": record.percorso_file,
            "local_copy_path": local_copy_path,
            "secondary_copy_path": secondary_copy_path,
            "secondary_label": targets["secondary_label"],
            "trigger_source": trigger_source,
            "schedule_code": schedule_code,
            "error": record.errore,
            "num_file": int(record.num_file or 0),
            "dimensione_bytes": int(record.dimensione_bytes or 0),
        }
        backup_runs.append(payload)

    report = {
        "generated_at": _now_iso(),
        "tenant_slug": targets["tenant_slug"],
        "trigger_source": trigger_source,
        "schedule_code": schedule_code,
        "backup_targets": targets,
        "runs": backup_runs,
        "success": all(str(run.get("status") or "") == "OK" for run in backup_runs),
    }
    report_dir = Path(backup_dir) / "operational_backups"
    report["report_path"] = _write_json(
        report_dir / f"operational_backup_{targets['tenant_slug']}_{stamp}.json",
        report,
    )
    _write_json(report_dir / "operational_backup_latest.json", report)

    for payload in backup_runs:
        payload["report_path"] = report["report_path"]
        if repository is not None:
            repository.record_backup_run(targets["tenant_slug"], payload)

    _write_json(Path(report["report_path"]), report)
    return report


def run_operational_crash_test(
    *,
    tenant_slug: str,
    report_dir: str,
    repair_dir: str,
    repository: Any | None = None,
    health_snapshot_factory: Callable[[], dict[str, Any]] | None = None,
    backup_executor: Callable[[str], dict[str, Any]] | None = None,
    trigger_source: str = "manual",
    schedule_code: str = "",
    auto_repair: bool = True,
    max_attempts: int = 3,
    cwd: str = "",
    python_executable: str = "",
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started_at = _now_iso()
    attempts: list[dict[str, Any]] = []
    latest_tickets: list[dict[str, Any]] = []
    backup_reports: list[dict[str, Any]] = []
    phase_results: list[dict[str, Any]] = []
    last_health_snapshot = (health_snapshot_factory or (lambda: {}))()

    total_attempts = max(int(max_attempts or 1), 1)
    for attempt in range(1, total_attempts + 1):
        if attempt > 1 and backup_executor is not None:
            backup_reports.append(backup_executor(f"repair_attempt_{attempt}"))
        last_health_snapshot = (health_snapshot_factory or (lambda: {}))()
        phase_results = []
        for phase in CRASH_PHASES:
            if phase.phase_type == "health":
                outcome = _evaluate_health_phase(last_health_snapshot)
            else:
                outcome = _run_pytest_phase(
                    phase.selectors,
                    cwd=cwd,
                    python_executable=python_executable,
                    fallback_check_id=phase.fallback_check_id,
                    runtime_context=runtime_context,
                )
            phase_results.append(
                {
                    "phase_id": phase.phase_id,
                    "label": phase.label,
                    "description": phase.description,
                    "status": outcome["status"],
                    "duration_seconds": outcome["duration_seconds"],
                    "return_code": outcome["return_code"],
                    "output_excerpt": outcome["output_excerpt"],
                    "selectors": list(phase.selectors),
                }
            )

        failed_phases = [row for row in phase_results if row["status"] != "passed"]
        latest_tickets = _dedupe_tickets(
            [_phase_failure_to_ticket(row) for row in failed_phases]
            + _health_alert_tickets(last_health_snapshot)
        )
        attempts.append(
            {
                "attempt": attempt,
                "failed_total": len(failed_phases),
                "failed_phase_ids": [row["phase_id"] for row in failed_phases],
                "tickets_total": len(latest_tickets),
            }
        )
        if not failed_phases or not auto_repair or attempt >= total_attempts:
            break

    completed_at = _now_iso()
    quick_checks = _build_quick_checks(phase_results, last_health_snapshot)
    success = all(bool(row.get("ok")) for row in quick_checks)
    summary = {
        "status": "passed" if success else "failed",
        "phase_total": len(phase_results),
        "passed_phases": sum(1 for row in phase_results if row["status"] == "passed"),
        "failed_phases": sum(1 for row in phase_results if row["status"] != "passed"),
        "attempts": len(attempts),
    }
    report = {
        "generated_at": completed_at,
        "tenant_slug": str(tenant_slug or "").strip().lower(),
        "trigger_source": trigger_source,
        "schedule_code": schedule_code,
        "started_at": started_at,
        "completed_at": completed_at,
        "overall_ok": success,
        "status": summary["status"],
        "summary": summary,
        "quick_checks": quick_checks,
        "health_snapshot": last_health_snapshot,
        "phases": phase_results,
        "repair_tickets": latest_tickets,
        "attempt_log": attempts,
        "backup_reports": backup_reports,
    }

    report_root = Path(report_dir)
    tenant_code = str(tenant_slug or "single-studio").strip().lower() or "single-studio"
    report["report_path"] = _write_json(
        report_root / f"operational_crash_test_{tenant_code}_{_stamp_now()}.json",
        report,
    )
    _write_json(report_root / "operational_crash_test_latest.json", report)

    crash_run_id = 0
    if repository is not None:
        crash_run_id = repository.record_crash_run(
            {
                "tenant_slug": tenant_code,
                "trigger_source": trigger_source,
                "schedule_code": schedule_code,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": summary["status"],
                "overall_ok": success,
                "attempt_count": len(attempts),
                "total_phases": len(phase_results),
                "passed_phases": summary["passed_phases"],
                "report_path": report["report_path"],
                "summary": summary,
                "quick_checks": quick_checks,
                "phases": phase_results,
                "repair_tickets": latest_tickets,
            }
        )

    repair_root = Path(repair_dir)
    persisted_tickets: list[str] = []
    for index, ticket in enumerate(latest_tickets, start=1):
        ticket_payload = {
            **ticket,
            "tenant_slug": tenant_code,
            "crash_run_id": crash_run_id,
            "generated_at": completed_at,
        }
        ticket_path = repair_root / f"repair_ticket_{tenant_code}_{_stamp_now()}_{index:02d}.json"
        persisted_tickets.append(_write_json(ticket_path, ticket_payload))
        if repository is not None:
            repository.record_repair_ticket(crash_run_id, tenant_code, ticket_payload)
    report["repair_ticket_paths"] = persisted_tickets
    _write_json(Path(report["report_path"]), report)
    return report
