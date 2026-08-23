"""Golden journey P0 con fixture sintetiche, report e rollback sicuro.

Questo modulo e' intenzionalmente esterno al runtime web: prepara dati di
collaudo isolati ed esegue guardrail Pytest, senza interrogare provider reali
o modificare gli archivi di uno studio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from time import monotonic
from typing import Any
from uuid import uuid4
import zipfile

from pct.auth import GestioneUtenti, RuoloUtente
from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.storage import StudioDB
from pct.tenant import GestioneTenant


WORKSPACE_DIRNAME = "golden-journeys"
WORKSPACE_SCHEMA_VERSION = "2026.08.23.1"
WORKSPACE_MARKER = ".iusentra-golden-journeys.json"
RUN_ID_PATTERN = re.compile(r"^run-[a-z0-9][a-z0-9-]{2,79}$")
SYNTHETIC_PASSWORD = "FixtureSoloTest!2026"


@dataclass(frozen=True)
class GoldenJourney:
    """Contratto stabile di un percorso critico verificabile."""

    journey_id: str
    label: str
    business_outcome: str
    criticality: str
    capability_ids: tuple[str, ...]
    tenant_roles: tuple[str, ...]
    fixture_keys: tuple[str, ...]
    pytest_selectors: tuple[str, ...]
    browser_category: str
    provider_status: str
    rollback_scope: str


GOLDEN_JOURNEYS: tuple[GoldenJourney, ...] = (
    GoldenJourney("lead-conflitto-cliente", "Lead, conflitto e cliente", "Un lead controllato diventa cliente senza oltrepassare il confine tenant.", "critico", ("clienti_anagrafiche", "ricerca_studio"), ("amministratore", "operatore"), ("tenant_a", "tenant_b", "cliente"), ("tests/test_global_search.py", "tests/test_tenant_isolation_runtime.py"), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("cliente-preventivo-conferimento", "Cliente, preventivo e conferimento", "Il preventivo accettato genera il conferimento con audit del workflow.", "critico", ("preventivi_incarichi",), ("amministratore", "operatore"), ("tenant_a", "cliente", "fascicolo"), ("tests/test_preventivi_wizard.py", "tests/test_preventivi_conferimento_route.py"), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("conferimento-fascicolo-procedura", "Conferimento, fascicolo e procedura", "Il conferimento firmato apre il fascicolo e la procedura iniziale tenant-aware.", "critico", ("fascicoli", "preventivi_incarichi"), ("operatore",), ("tenant_a", "cliente", "fascicolo"), ("tests/e2e/test_studio_reale_flow.py",), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("pec-scadenza", "PEC, fascicolo e scadenza", "Una PEC controllata alimenta una proposta di scadenza senza invio esterno.", "critico", ("pec_email", "scadenze_termini", "fascicoli"), ("operatore",), ("tenant_a", "pec", "fascicolo"), ("tests/test_email_client.py", "tests/test_scadenza_proposta_agenda.py", "tests/test_pec_pipeline_tenant_isolation.py"), "browser_reale_richiesto", "dry_run", "run_sintetico"),
    GoldenJourney("atto-firma-predeposito", "Atto, firma e predeposito", "Il pacchetto di predeposito applica i controlli prima del canale locale di firma.", "critico", ("deposito_telematico", "fascicoli"), ("operatore",), ("tenant_a", "fascicolo", "documenti"), ("tests/test_deposito_guidato.py", "tests/test_deposito.py"), "browser_reale_richiesto", "local_signer_non_eseguito", "run_sintetico"),
    GoldenJourney("deposito-ricevute", "Deposito, ricevute e riconciliazione", "Gli esiti del deposito sono ricondotti al fascicolo senza invio PEC reale.", "critico", ("deposito_telematico", "pec_email"), ("operatore",), ("tenant_a", "fascicolo", "pec"), ("tests/test_regia_deposito_receipts.py", "tests/test_deposito_server_dry_run_audit.py"), "browser_reale_richiesto", "canary_non_eseguito", "run_sintetico"),
    GoldenJourney("notifica-relata", "Notifica L. 53 e relata", "Relata, prova e audit restano distinti dal deposito e dall'invio effettivo.", "critico", ("notifiche_legali", "fascicoli"), ("operatore",), ("tenant_a", "fascicolo", "documenti", "pec"), ("tests/test_notifiche_legali.py", "tests/test_notification_relata_materializer.py", "tests/test_notification_relata_fascicolo.py"), "browser_reale_richiesto", "canary_non_eseguito", "run_sintetico"),
    GoldenJourney("udienza-esito", "Udienza, esito e attività", "Un esito di udienza genera attività e termini successivi governati.", "alto", ("agenda", "scadenze_termini"), ("operatore",), ("tenant_a", "fascicolo"), ("tests/test_agenda.py", "tests/test_scadenziario.py"), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("timesheet-fattura-incasso", "Timesheet, fattura e incasso", "Il ciclo economico controllato mantiene saldo, permessi e tracciabilità.", "critico", ("timesheet", "fatturazione_pagamenti"), ("amministratore", "operatore"), ("tenant_a", "cliente", "fascicolo"), ("tests/e2e/test_studio_reale_flow.py", "tests/test_timesheet.py"), "browser_reale_richiesto", "pagamento_sdi_non_eseguiti", "run_sintetico"),
    GoldenJourney("documento-lex-export", "Documento, Lex ed export", "Documento e fonti passano per revisione prima dell'export controllato.", "alto", ("documenti", "lex_ai"), ("operatore",), ("tenant_a", "fascicolo", "documenti"), ("tests/test_legal_skills_engine.py",), "browser_reale_richiesto", "ai_locale_controllata", "run_sintetico"),
    GoldenJourney("portale-firma-pagamento", "Portale, firma e pagamento", "L'invito portale resta isolato dal tenant e non abilita provider reali.", "alto", ("portale_clienti", "documenti", "fatturazione_pagamenti"), ("operatore",), ("tenant_a", "tenant_b", "documenti"), ("tests/test_client_portal_api.py", "tests/test_client_portal_access.py", "tests/test_client_portal_repository.py"), "browser_reale_richiesto", "firma_pagamento_non_eseguiti", "run_sintetico"),
    GoldenJourney("migrazione-cutover-rollback", "Migrazione, cutover e rollback", "La migrazione sintetica confronta lo stato e torna indietro in modo auditabile.", "critico", ("migrazione_sql_postgresql",), ("amministratore",), ("tenant_migrazione",), ("tests/e2e/test_tenant_migration_full.py", "tests/test_storage_postgres_migration.py"), "non_ui", "non_applicabile", "run_sintetico"),
    GoldenJourney("backup-restore", "Backup e restore", "Il backup sintetico viene ripristinato e verificato senza toccare dati applicativi.", "critico", ("backup_ripristino",), ("amministratore",), ("tenant_backup",), ("tests/test_backup.py",), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("tenant-a-versus-b", "Tenant A contro tenant B", "Ogni tentativo di attraversare il confine A/B viene negato e tracciato.", "critico", ("tenant_isolation",), ("amministratore",), ("tenant_a", "tenant_b"), ("tests/test_tenant_isolation_runtime.py", "tests/test_pec_pipeline_tenant_isolation.py"), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
    GoldenJourney("readonly-write-denied", "Sola lettura contro modifica", "Il profilo in sola lettura non può modificare dati protetti e il diniego resta controllato.", "critico", ("ruoli_permessi", "tenant_isolation"), ("lettura",), ("tenant_a", "lettura"), ("tests/test_profili.py",), "browser_reale_richiesto", "non_applicabile", "run_sintetico"),
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _validate_workspace_dir(workspace_dir: str | Path) -> Path:
    root = Path(workspace_dir).resolve()
    if root.name != WORKSPACE_DIRNAME:
        raise ValueError(f"La root dei golden journey deve chiamarsi '{WORKSPACE_DIRNAME}'.")
    return root


def _validate_run_id(run_id: str) -> str:
    value = str(run_id or "").strip().lower()
    if not RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("Identificativo run non valido.")
    return value


def _marker_path(root: Path) -> Path:
    return root / WORKSPACE_MARKER


def _ensure_workspace_marker(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    marker = _marker_path(root)
    payload = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "purpose": "fixture sintetiche golden journey IUSENTRA",
        "created_at": _now_iso(),
    }
    if marker.exists():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("La root dei golden journey non ha un marker leggibile.") from exc
        if not isinstance(current, dict) or current.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
            raise ValueError("La root dei golden journey non appartiene a questo contratto di fixture.")
        return
    marker.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture_document_payloads(document_dir: Path) -> list[str]:
    document_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = document_dir / "atto-controllato.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% Fixture IUSENTRA controllata\n")
    xml_path = document_dir / "metadati-controllati.xml"
    xml_path.write_text("<?xml version=\"1.0\" encoding=\"UTF-8\"?><fixture tenant=\"synthetic\" />", encoding="utf-8")
    eml_path = document_dir / "pec-controllata.eml"
    eml_path.write_text("From: fixture@example.invalid\nSubject: PEC controllata\n\nContenuto sintetico.", encoding="utf-8")
    zip_path = document_dir / "busta-controllata.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(pdf_path, arcname=pdf_path.name)
        archive.write(xml_path, arcname=xml_path.name)
    return [path.name for path in (pdf_path, xml_path, eml_path, zip_path)]


def _seed_tenant(*, registry: GestioneTenant, slug: str, name: str, run_root: Path) -> dict[str, Any]:
    studio = registry.crea(name, slug, db_config={"mode": "SQLITE"})
    paths = registry.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=True)
    studio_db = StudioDB.get(paths["STUDIO_DB"])
    studio_db.ensure_schema()
    utenti_sql = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="golden-journey-fixture",
        crea_admin_se_vuoto=False,
        studio_db=studio_db,
        tenant_slug_context=studio.slug,
    )
    utenti_mirror = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="golden-journey-fixture",
        crea_admin_se_vuoto=False,
        tenant_slug_context=studio.slug,
    )
    roles = (
        ("amministratore", RuoloUtente.AMMINISTRATORE),
        ("operatore", RuoloUtente.AVVOCATO),
        ("lettura", RuoloUtente.PRATICANTE),
    )
    user_rows: list[dict[str, str]] = []
    for role_key, role in roles:
        username = f"{slug}-{role_key}"
        user = utenti_sql.crea(
            username=username,
            password=SYNTHETIC_PASSWORD,
            ruolo=role,
            tenant_slug=studio.slug,
            must_change_password=False,
        )
        if utenti_mirror.get_by_username(username) is None:
            utenti_mirror.importa_utente_esistente(user, tenant_slug=studio.slug, preserve_id=True)
        user_rows.append({"username": username, "role": role.value})

    clienti = GestioneClienti(db_path=paths["CLIENTI_DB"], studio_db=studio_db)
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Cliente",
        cognome=f"Sintetico {slug.upper()}",
        avvocato_referente="Avvocato sintetico",
    )
    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=studio_db,
    )
    fascicolo = fascicoli.nuovo(
        f"Fascicolo controllato {slug.upper()}",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=f"{cliente.nome} {cliente.cognome}".strip(),
        oggetto="Dati esclusivamente sintetici per golden journey",
    )
    document_names = _fixture_document_payloads(Path(paths["FASCICOLI_DOCS"]) / fascicolo.id)
    quick_check = studio_db.conn.execute("PRAGMA quick_check").fetchone()[0]
    if quick_check != "ok":
        raise RuntimeError(f"SQLite fixture non integra per {slug}: {quick_check}")
    return {
        "slug": studio.slug,
        "root": str(Path(paths["STUDIO_DB"]).parent),
        "studio_db": str(paths["STUDIO_DB"]),
        "client_id": cliente.id,
        "fascicolo_id": fascicolo.id,
        "users": user_rows,
        "document_names": document_names,
        "quick_check": quick_check,
        "run_root": str(run_root),
    }


def prepare_synthetic_workspace(*, workspace_dir: str | Path, run_id: str = "") -> dict[str, Any]:
    """Crea due tenant sintentici senza sovrascrivere fixture esistenti."""

    root = _validate_workspace_dir(workspace_dir)
    _ensure_workspace_marker(root)
    run_value = _validate_run_id(run_id or f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}")
    run_root = (root / "runs" / run_value).resolve()
    if run_root.exists():
        raise FileExistsError("La run sintetica esiste già: usa un identificativo nuovo o il rollback esplicito.")
    if root not in run_root.parents:
        raise ValueError("Il percorso della run esce dalla root dedicata.")
    run_root.mkdir(parents=True, exist_ok=False)
    registry = GestioneTenant(str(run_root / "tenants.json"))
    tenant_rows = [
        _seed_tenant(registry=registry, slug="tenant-a", name="Studio sintetico A", run_root=run_root),
        _seed_tenant(registry=registry, slug="tenant-b", name="Studio sintetico B", run_root=run_root),
    ]
    manifest = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "run_id": run_value,
        "created_at": _now_iso(),
        "source_of_truth": "sqlite",
        "json_authoritative": False,
        "provider_status": "non_eseguito",
        "synthetic_password_stored": False,
        "tenants": tenant_rows,
    }
    manifest_path = run_root / "fixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**manifest, "workspace_dir": str(root), "run_root": str(run_root), "manifest_path": str(manifest_path)}


def rollback_synthetic_workspace(*, workspace_dir: str | Path, run_id: str) -> dict[str, Any]:
    """Rimuove una sola run marcata, mai l'intera root o dati utente."""

    root = _validate_workspace_dir(workspace_dir)
    _ensure_workspace_marker(root)
    run_value = _validate_run_id(run_id)
    run_root = (root / "runs" / run_value).resolve()
    runs_root = (root / "runs").resolve()
    if runs_root not in run_root.parents or run_root.parent != runs_root:
        raise ValueError("Rollback fuori dalla directory delle run rifiutato.")
    manifest_path = run_root / "fixture-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("La run richiesta non contiene il manifest di fixture.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Il manifest della run non è leggibile.") from exc
    if manifest.get("schema_version") != WORKSPACE_SCHEMA_VERSION or manifest.get("run_id") != run_value:
        raise ValueError("Il manifest non corrisponde alla run richiesta.")
    for tenant in manifest.get("tenants") or []:
        if isinstance(tenant, dict) and tenant.get("studio_db"):
            StudioDB.invalidate(str(tenant["studio_db"]))
    for attempt in range(3):
        try:
            shutil.rmtree(run_root)
            break
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1 * (attempt + 1))
    return {"ok": True, "run_id": run_value, "removed_run_root": str(run_root), "workspace_dir": str(root)}


def _resolve_report_dir(workspace_dir: str | Path) -> Path:
    return _validate_workspace_dir(workspace_dir) / "reports"


def _latest_report(workspace_dir: str | Path) -> dict[str, Any] | None:
    latest = _resolve_report_dir(workspace_dir) / "golden_journeys_latest.json"
    if not latest.exists():
        return None
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _journey_row(journey: GoldenJourney) -> dict[str, Any]:
    return {
        **asdict(journey),
        "capability_ids": list(journey.capability_ids),
        "tenant_roles": list(journey.tenant_roles),
        "fixture_keys": list(journey.fixture_keys),
        "pytest_selectors": list(journey.pytest_selectors),
        "status": "not_run",
        "status_label": "Non eseguito",
        "duration_seconds": 0.0,
        "completed_at": "",
        "output_excerpt": "",
    }


def build_golden_journey_payload(*, workspace_dir: str | Path, report_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report_payload or _latest_report(workspace_dir) or {}
    rows_by_id = {journey.journey_id: _journey_row(journey) for journey in GOLDEN_JOURNEYS}
    for row in report.get("journeys") or []:
        journey_id = str((row or {}).get("journey_id") or "").strip()
        if journey_id in rows_by_id:
            rows_by_id[journey_id].update({key: value for key, value in dict(row).items() if key in rows_by_id[journey_id] or key == "return_code"})
    rows = [rows_by_id[journey.journey_id] for journey in GOLDEN_JOURNEYS]
    passed = sum(row["status"] == "passed" for row in rows)
    failed = sum(row["status"] == "failed" for row in rows)
    return {
        "summary": {
            "journeys_total": len(rows),
            "passed": passed,
            "failed": failed,
            "not_run": len(rows) - passed - failed,
            "status": "failed" if failed else "passed" if passed == len(rows) else "not_run",
            "provider_status": "non_eseguito",
            "source_of_truth": "sqlite",
        },
        "rows": rows,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Golden journey P0", "", f"- Generato: {report['generated_at']}", f"- Esito automatico: {'PASS' if report['success'] else 'FAIL'}", "- Provider reali: non eseguiti", "", "| Journey | Stato | Durata | Provider |", "| --- | --- | ---: | --- |"]
    for row in report["journeys"]:
        lines.append(f"| {row['label']} | {row['status_label']} | {row['duration_seconds']} s | {row['provider_status']} |")
    lines.extend(["", "La prova materiale con browser reale resta separata e obbligatoria per le superfici utente.", ""])
    return "\n".join(lines)


def run_golden_journeys(*, workspace_dir: str | Path, cwd: str = "", run_id: str = "") -> dict[str, Any]:
    """Prepara fixture e lancia tutti i journey, persistendo evidenze tecniche."""

    fixture = prepare_synthetic_workspace(workspace_dir=workspace_dir, run_id=run_id)
    working_dir = str(cwd or Path.cwd())
    rows: list[dict[str, Any]] = []
    environment = dict(os.environ)
    environment["IUSENTRA_GOLDEN_JOURNEY_WORKSPACE"] = fixture["run_root"]
    for journey in GOLDEN_JOURNEYS:
        started = monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *journey.pytest_selectors],
            cwd=working_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=environment,
        )
        excerpt = "\n".join(line for line in (str(result.stdout) + "\n" + str(result.stderr)).splitlines() if line.strip())
        rows.append({
            **_journey_row(journey),
            "status": "passed" if result.returncode == 0 else "failed",
            "status_label": "Pass" if result.returncode == 0 else "Fail",
            "return_code": int(result.returncode),
            "duration_seconds": round(monotonic() - started, 2),
            "completed_at": _now_iso(),
            "output_excerpt": "\n".join(excerpt.splitlines()[-12:]),
            "fixture_run_id": fixture["run_id"],
        })
    report = {"generated_at": _now_iso(), "cwd": working_dir, "success": all(row["status"] == "passed" for row in rows), "fixture": fixture, "journeys": rows}
    report_dir = _resolve_report_dir(workspace_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"golden_journeys_{stamp}.json"
    markdown_path = report_dir / f"golden_journeys_{stamp}.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    (report_dir / "golden_journeys_latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "golden_journeys_latest.md").write_text(_markdown_report(report), encoding="utf-8")
    return {**report, "report_path": str(report_path), "report_markdown_path": str(markdown_path)}
