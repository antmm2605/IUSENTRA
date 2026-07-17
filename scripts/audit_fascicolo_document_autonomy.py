from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.document_intelligence.sources import collect_fascicolo_document_sources
from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_document_catalog import document_ai_texts_for_catalog
from pct.fascicolo_sentenza_economica import (
    analyze_sentenza_tribunale_text,
    extract_contributo_unificato_document_evidence,
    validate_sentenza_fascicolo_context,
)
from pct.pec_pipeline import (
    DOCUMENT_PRESIDIO_PARSER_VERSION,
    PecAuditRepository,
    _date_from_iso_or_it,
    _document_presidio_ai_signal_rank,
    _document_presidio_checked_resource_id,
    _document_presidio_fascicolo_fingerprint,
    _document_presidio_source_priority,
    _procedural_date_kind,
    build_remote_hearing_profile,
    extract_procedural_dates,
)
from pct.scadenziario import GestioneScadenziario
from pct.storage import StudioDB
from pct.tenant import GestioneTenant


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _studio_db_path(paths: dict[str, Any]) -> Path:
    fascicoli_path = Path(_text(paths.get("FASCICOLI_DB"))).resolve()
    return fascicoli_path.parent.parent / "studio.db"


def _pec_audit_path(paths: dict[str, Any]) -> Path:
    configured = _text(paths.get("PEC_AUDIT_DB"))
    if configured:
        return Path(configured)
    email_path = Path(_text(paths.get("EMAIL_CASELLA_DB"))).resolve()
    return email_path.parent / "pec_audit.sqlite"


def _amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payment(fascicolo: Any, kind: str) -> dict[str, Any]:
    payments = getattr(fascicolo, "pagamenti", {}) or {}
    if not isinstance(payments, dict):
        return {}
    aliases = {
        "contributo_unificato": {"contributo_unificato", "contributo", "cu"},
        "liquidazione_giudice": {"liquidazione_giudice", "liquidazione", "liquidazione giudice"},
    }
    for key, value in payments.items():
        normalized = _text(key).casefold().replace("-", "_").replace(" ", "_")
        if normalized in {item.replace(" ", "_") for item in aliases.get(kind, {kind})} and isinstance(value, dict):
            return dict(value)
    return {}


def _payment_status(value: dict[str, Any]) -> str:
    status = _text(value.get("status") or value.get("stato")).casefold().replace(" ", "_")
    if not status and value.get("pagato") is True:
        return "pagato"
    return status


def _best_contributo_evidence(
    rows: list[tuple[dict[str, Any], Any | None]],
) -> tuple[dict[str, Any], Any | None]:
    if not rows:
        return {}, None
    return sorted(
        rows,
        key=lambda row: (
            0
            if _text(row[0].get("status")) == "pagato" and _amount(row[0].get("importo")) is not None
            else 1,
            0
            if row[0].get("esente") is True
            or _text(row[0].get("natura")) == "esenzione_contributo_unificato"
            else 1,
            0 if _amount(row[0].get("importo")) is not None else 1,
            _text(row[0].get("filename") or row[0].get("document_id")),
        ),
    )[0]


def _failure(
    failures: list[dict[str, Any]],
    *,
    code: str,
    fascicolo: Any,
    document: Any | None = None,
    source: Any | None = None,
    text_available: bool | None = None,
    expected: Any = "",
    actual: Any = "",
) -> None:
    fingerprint = _text(getattr(source, "sha256", "")) if source is not None else ""
    if not fingerprint and document is not None:
        for attr in ("sha256", "hash_sha256", "file_hash", "checksum"):
            fingerprint = _text(getattr(document, attr, ""))
            if fingerprint:
                break
    failures.append(
        {
            "code": code,
            "reason": code,
            "fascicolo_id": _text(getattr(fascicolo, "id", "")),
            "rg": _text(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", "")),
            "document_id": _text(getattr(document, "id", "")) if document is not None else "",
            "documento": _text(getattr(document, "nome", "")) if document is not None else "",
            "fingerprint": fingerprint,
            "text_available": text_available,
            "expected_field": expected,
            "parser_version": DOCUMENT_PRESIDIO_PARSER_VERSION,
            "expected": expected,
            "actual": actual,
        }
    )


def _document_by_id(fascicolo: Any) -> dict[str, Any]:
    return {
        _text(getattr(document, "id", "")): document
        for document in list(getattr(fascicolo, "documenti", []) or [])
        if _text(getattr(document, "id", ""))
    }


def _source_availability_issue(source: Any) -> str:
    if not bool(getattr(source, "supported", False)):
        return "formato non supportato"
    content = getattr(source, "content_bytes", None)
    if content is not None:
        return "" if len(content) > 0 else "file vuoto"
    path = getattr(source, "content_path", None)
    if path is None:
        return "percorso fisico mancante"
    try:
        if not path.is_file():
            return "file fisico non disponibile"
        if path.stat().st_size <= 0:
            return "file vuoto"
    except OSError as exc:
        return f"file fisico non accessibile: {type(exc).__name__}"
    return ""


def audit_tenant(
    *,
    slug: str,
    paths: dict[str, Any],
    max_failures: int,
) -> dict[str, Any]:
    studio_db_path = _studio_db_path(paths)
    if not studio_db_path.exists():
        return {
            "ok": False,
            "tenant": slug,
            "source_of_truth": "missing",
            "failures": [{"code": "studio_db_mancante", "path": str(studio_db_path)}],
        }

    studio_db = StudioDB.get(str(studio_db_path))
    fascicoli = GestioneFascicoli(
        _text(paths.get("FASCICOLI_DB")),
        documents_dir=_text(paths.get("FASCICOLI_DOCS")),
        archive_dir=_text(paths.get("FASCICOLI_ARCH")),
        studio_db=studio_db,
    ).tutti(archiviati=False)
    scadenze = GestioneScadenziario(
        _text(paths.get("SCADENZIARIO_DB")),
        studio_db=studio_db,
    ).tutte(solo_aperte=False)
    scadenze_by_fascicolo: dict[str, list[Any]] = defaultdict(list)
    for item in scadenze:
        scadenze_by_fascicolo[_text(getattr(item, "id_fascicolo", ""))].append(item)

    pec_repo = PecAuditRepository(
        _pec_audit_path(paths),
        tenant_id=slug,
        fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
        fascicoli_docs_path=_text(paths.get("FASCICOLI_DOCS")),
        scadenziario_db_path=_text(paths.get("SCADENZIARIO_DB")),
        agenda_db_path=_text(paths.get("AGENDA_DB")),
    )
    checked_resources = pec_repo._document_presidio_checked_resource_ids()
    latest_states = pec_repo._document_presidio_latest_fascicolo_states()

    failures: list[dict[str, Any]] = []
    stats = {
        "fascicoli": len(fascicoli),
        "documenti": 0,
        "documenti_sorgente_disponibile": 0,
        "documenti_sorgente_non_disponibile": 0,
        "documenti_indicizzati": 0,
        "documenti_senza_testo": 0,
        "documenti_da_processare": 0,
        "documenti_operativi": 0,
        "documenti_operativi_indicizzati": 0,
        "documenti_operativi_da_processare": 0,
        "date_future_estratte": 0,
        "date_future_presidiate": 0,
        "modalita_udienza_estratte": 0,
        "contributi_estratti": 0,
        "contributi_consolidati": 0,
        "liquidazioni_estratte": 0,
        "liquidazioni_consolidate": 0,
        "fascicoli_stato_incrementale_corrente": 0,
    }
    today = date.today()
    documents_root = _text(paths.get("FASCICOLI_DOCS"))
    storage_root = _text(paths.get("DOCUMENTI_AI_DIR")) or str(Path(documents_root).parent / "documenti_ai")

    for fascicolo in fascicoli:
        fid = _text(getattr(fascicolo, "id", ""))
        documents = list(getattr(fascicolo, "documenti", []) or [])
        stats["documenti"] += len(documents)
        document_map = _document_by_id(fascicolo)
        sources = collect_fascicolo_document_sources(
            tenant_id=slug,
            fascicolo_id=fid,
            fascicolo=fascicolo,
            documents_root=documents_root,
        )
        sources_by_id = {
            _text(source.source_id): source
            for source in sources
            if _text(source.source_id)
        }
        for document_id, document in document_map.items():
            if document_id in sources_by_id:
                continue
            stats["documenti_sorgente_non_disponibile"] += 1
            _failure(
                failures,
                code="sorgente_documento_non_risolta",
                fascicolo=fascicolo,
                document=document,
                expected="sorgente fisica tenant-aware",
                actual="documento non convertito in sorgente",
            )

        state = latest_states.get(fid) or {}
        current_fingerprint = _document_presidio_fascicolo_fingerprint(fascicolo)
        if (
            _text(state.get("parser_version")) == DOCUMENT_PRESIDIO_PARSER_VERSION
            and _text(state.get("fascicolo_fingerprint")) == current_fingerprint
            and _text(state.get("status")) == "complete"
        ):
            stats["fascicoli_stato_incrementale_corrente"] += 1

        texts = document_ai_texts_for_catalog(
            tenant_ids=[slug, "default", "single-studio"],
            fascicolo_id=fid,
            documents=documents,
            fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
            structured_db=studio_db,
            storage_root=storage_root,
        )
        cu_evidences: list[tuple[dict[str, Any], Any | None]] = []
        for source in sources:
            document_id = _text(source.source_id)
            document = document_map.get(document_id)
            source_issue = _source_availability_issue(source)
            if source_issue:
                stats["documenti_sorgente_non_disponibile"] += 1
                _failure(
                    failures,
                    code="sorgente_documento_non_disponibile",
                    fascicolo=fascicolo,
                    document=document,
                    source=source,
                    text_available=False,
                    expected="file fisico leggibile",
                    actual=source_issue,
                )
            else:
                stats["documenti_sorgente_disponibile"] += 1
            source_priority = _document_presidio_source_priority(source)[0]
            if source_priority < 2:
                stats["documenti_operativi"] += 1
            resource_id = _document_presidio_checked_resource_id(
                fascicolo_id=fid,
                document_id=document_id or source.filename,
                sha256=_text(source.sha256),
            )
            if resource_id not in checked_resources:
                stats["documenti_da_processare"] += 1
                if source_priority < 2:
                    stats["documenti_operativi_da_processare"] += 1
                _failure(
                    failures,
                    code="documento_non_presidiato",
                    fascicolo=fascicolo,
                    document=document,
                    source=source,
                    expected="stato incrementale persistito",
                    actual="mancante",
                )
            text = _text(texts.get(document_id))
            if not text:
                stats["documenti_senza_testo"] += 1
                _failure(
                    failures,
                    code="testo_documento_non_indicizzato",
                    fascicolo=fascicolo,
                    document=document,
                    source=source,
                    text_available=False,
                    expected="testo indicizzato",
                    actual="mancante",
                )
                continue
            stats["documenti_indicizzati"] += 1
            if source_priority < 2:
                stats["documenti_operativi_indicizzati"] += 1

            future_candidates: dict[tuple[str, str], dict[str, Any]] = {}
            analyze_procedural_dates = (
                source_priority < 2
                or _document_presidio_ai_signal_rank(source.filename, text) < 9
            )
            for candidate in extract_procedural_dates({source.filename: text}) if analyze_procedural_dates else []:
                kind = _procedural_date_kind(candidate)
                parsed_day = _date_from_iso_or_it(_text(candidate.get("date")))
                if kind not in {"udienza", "termine"} or parsed_day is None or parsed_day < today:
                    continue
                future_candidates[(kind, parsed_day.isoformat())] = candidate
            for (kind, target_date), candidate in future_candidates.items():
                stats["date_future_estratte"] += 1
                matching = [
                    item
                    for item in scadenze_by_fascicolo.get(fid, [])
                    if _text(getattr(item, "data_scadenza", ""))[:10] == target_date
                ]
                if not matching:
                    _failure(
                        failures,
                        code="data_futura_non_presidiata",
                        fascicolo=fascicolo,
                        document=document,
                        source=source,
                        text_available=True,
                        expected={"kind": kind, "date": target_date},
                        actual="nessuna scadenza",
                    )
                    continue
                stats["date_future_presidiate"] += 1
                if kind != "udienza":
                    continue
                profile = build_remote_hearing_profile(
                    {
                        "headers": {"subject": source.filename},
                        "body": {"text": "", "html_text": "", "href_urls": []},
                        "procedural_profile": {},
                    },
                    [
                        {
                            "filename": source.filename,
                            "content_type": source.mime_type or "",
                            "classification": "atto",
                            "ocr_text": text,
                        }
                    ],
                )
                mode = _text(profile.get("mode_unified"))
                if not mode:
                    continue
                stats["modalita_udienza_estratte"] += 1
                if not any(_text(getattr(item, "hearing_mode", "")) == mode for item in matching):
                    _failure(
                        failures,
                        code="modalita_udienza_non_persistita",
                        fascicolo=fascicolo,
                        document=document,
                        source=source,
                        text_available=True,
                        expected=mode,
                        actual=[_text(getattr(item, "hearing_mode", "")) for item in matching],
                    )

            cu = extract_contributo_unificato_document_evidence(
                text,
                {**dict(source.metadata), "filename": source.filename, "document_id": document_id, "sha256": source.sha256},
            )
            if cu:
                stats["contributi_estratti"] += 1
                cu_evidences.append((dict(cu), document))

            extraction = analyze_sentenza_tribunale_text(
                text,
                {**dict(source.metadata), "filename": source.filename, "document_id": document_id},
            )
            if not extraction.found or extraction.liquidazione_importo is None:
                continue
            context = validate_sentenza_fascicolo_context(
                text=text,
                extraction=extraction,
                fascicolo=fascicolo,
                metadata={**dict(source.metadata), "filename": source.filename, "document_id": document_id},
                fascicolo_id=fid,
            )
            if not context.ok:
                continue
            stats["liquidazioni_estratte"] += 1
            saved_liquidazione = _payment(fascicolo, "liquidazione_giudice")
            actual_liquidazione = _amount(
                saved_liquidazione.get("importo")
                if "importo" in saved_liquidazione
                else saved_liquidazione.get("amount")
            )
            if actual_liquidazione is not None and abs(extraction.liquidazione_importo - actual_liquidazione) < 0.01:
                stats["liquidazioni_consolidate"] += 1
            else:
                _failure(
                    failures,
                    code="liquidazione_non_consolidata",
                    fascicolo=fascicolo,
                    document=document,
                    expected=extraction.liquidazione_importo,
                    actual=actual_liquidazione,
                )

        if cu_evidences:
            best_cu, best_document = _best_contributo_evidence(cu_evidences)
            saved_cu = _payment(fascicolo, "contributo_unificato")
            expected_amount = _amount(best_cu.get("importo"))
            actual_amount = _amount(saved_cu.get("importo") if "importo" in saved_cu else saved_cu.get("amount"))
            expected_status = _text(best_cu.get("status")) or (
                "non_previsto"
                if best_cu.get("esente") is True
                or _text(best_cu.get("natura")) == "esenzione_contributo_unificato"
                else ""
            )
            amount_ok = expected_amount is None or (
                actual_amount is not None and abs(expected_amount - actual_amount) < 0.01
            )
            status_ok = not expected_status or _payment_status(saved_cu) == expected_status
            if amount_ok and status_ok:
                stats["contributi_consolidati"] += len(cu_evidences)
            else:
                _failure(
                    failures,
                    code="contributo_non_consolidato",
                    fascicolo=fascicolo,
                    document=best_document,
                    expected={"status": expected_status, "importo": expected_amount},
                    actual={"status": _payment_status(saved_cu), "importo": actual_amount},
                )

    failure_counts: dict[str, int] = defaultdict(int)
    for item in failures:
        failure_counts[_text(item.get("code"))] += 1
    return {
        "ok": not failures,
        "tenant": slug,
        "source_of_truth": "sqlite",
        "studio_db": str(studio_db_path),
        "parser_version": DOCUMENT_PRESIDIO_PARSER_VERSION,
        "stats": stats,
        "failure_counts": dict(sorted(failure_counts.items())),
        "failures": failures[: max(1, max_failures)],
        "diagnostic_queue": failures[: max(1, max_failures)],
        "rule_governance": {
            "official_sources_only": True,
            "generic_web_auto_activation": False,
            "required_evidence": [
                "fonte ufficiale identificata",
                "versione della regola",
                "test sul corpus storico",
                "controllo anti-regressione",
            ],
        },
        "failure_total": len(failures),
    }


def run_audit(*, registry: Path, tenant: str, max_failures: int) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if not tenant or studio.slug.casefold() == tenant.casefold()]
    reports = []
    for studio in studios:
        paths = manager.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False)
        reports.append(audit_tenant(slug=studio.slug, paths=paths, max_failures=max_failures))
    if tenant and not studios:
        return {"ok": False, "source_of_truth": "missing", "errors": [f"Studio non trovato: {tenant}"]}
    return {
        "ok": bool(reports) and all(report.get("ok") for report in reports),
        "registry": str(registry),
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "tenants": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit read-only del presidio autonomo documenti, scadenze ed economia fascicolo."
    )
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", default="")
    parser.add_argument("--max-failures", type=int, default=100)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = run_audit(
        registry=Path(args.registry),
        tenant=_text(args.tenant),
        max_failures=max(1, int(args.max_failures or 100)),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
