from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.document_intelligence.sources import collect_fascicolo_document_sources
from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_document_catalog import document_ai_texts_for_catalog
from pct.pec_pipeline import (
    DOCUMENT_PRESIDIO_EVENT_TYPE,
    PecAuditRepository,
    _date_from_iso_or_it,
    _document_presidio_activity_description,
    _document_presidio_deadline_proposal,
    _document_presidio_message_id,
    _document_presidio_profile,
    _document_presidio_source_priority,
    _fascicolo_rg_display,
    _procedural_date_kind,
    _remote_hearing_deadline_extra,
    _remote_hearing_for_procedural_candidate,
    _remote_hearing_note_lines,
    _remote_hearing_updates_for_existing,
    build_remote_hearing_profile,
    extract_procedural_dates,
    iso_now,
)
from pct.storage import StudioDB
from pct.tenant import GestioneTenant


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _paths(manager: GestioneTenant, slug: str) -> dict[str, Any]:
    return manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False)


def _studio_db_path(paths: dict[str, Any]) -> Path:
    return Path(_text(paths.get("FASCICOLI_DB"))).resolve().parent.parent / "studio.db"


def _pec_audit_path(paths: dict[str, Any]) -> Path:
    email_path = Path(_text(paths.get("EMAIL_CASELLA_DB"))).resolve()
    return Path(_text(paths.get("PEC_AUDIT_DB"))) if _text(paths.get("PEC_AUDIT_DB")) else email_path.parent / "pec_audit.sqlite"


def _report_payload(*, fascicolo: Any, source: Any, text: str, candidate: dict[str, Any], kind: str) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    document_name = _text(source.filename) or "Documento fascicolo"
    document_id = _text(source.source_id)
    profile = _document_presidio_profile(fascicolo, document_name=document_name, candidate=candidate)
    attachment = {
        "filename": document_name,
        "content_type": source.mime_type or "",
        "classification": "atto",
        "ocr_text": text,
    }
    parsed = {
        "headers": {"subject": document_name, "date": iso_now()},
        "body": {"text": "", "html": ""},
        "fields": {},
        "rg_candidates": [_fascicolo_rg_display(fascicolo)] if _fascicolo_rg_display(fascicolo) else [],
        "procedural_dates": [candidate],
        "procedural_profile": profile,
        "attachments": [attachment],
    }
    remote_parsed = dict(parsed)
    remote_parsed["procedural_profile"] = {}
    remote = build_remote_hearing_profile(remote_parsed, [attachment])
    active_remote = _remote_hearing_for_procedural_candidate(remote, candidate, kind=kind)
    if active_remote:
        profile["remote_hearing"] = active_remote
    proposal = _document_presidio_deadline_proposal(
        parsed,
        candidate,
        kind=kind,
        document_name=document_name,
        document_id=document_id,
    )
    payload = {
        "event_type": DOCUMENT_PRESIDIO_EVENT_TYPE,
        "blocking": False,
        "issues": [],
        "procedural_profile": profile,
        "remote_hearing": active_remote,
        "deadline_proposal": proposal,
        "document_presidio": {
            "source": "document_cache_backfill",
            "document_id": document_id,
            "filename": document_name,
            "sha256": _text(source.sha256),
            "retrieval_metadata": dict(source.metadata),
        },
    }
    message_id = _document_presidio_message_id(
        fascicolo_id=_text(getattr(fascicolo, "id", "")),
        document_id=document_id or document_name,
        kind=kind,
        date_value=_text(candidate.get("date")),
    )
    return message_id, parsed, proposal, payload


def backfill_tenant(*, slug: str, paths: dict[str, Any], apply: bool) -> dict[str, Any]:
    studio_db_path = _studio_db_path(paths)
    if not studio_db_path.exists():
        return {"ok": False, "tenant": slug, "errors": [f"Database studio mancante: {studio_db_path}"]}
    studio_db = StudioDB.get(str(studio_db_path))
    fascicoli_manager = GestioneFascicoli(
        _text(paths.get("FASCICOLI_DB")),
        documents_dir=_text(paths.get("FASCICOLI_DOCS")),
        archive_dir=_text(paths.get("FASCICOLI_ARCH")),
        studio_db=studio_db,
    )
    repo = PecAuditRepository(
        _pec_audit_path(paths),
        tenant_id=slug,
        fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
        fascicoli_docs_path=_text(paths.get("FASCICOLI_DOCS")),
        scadenziario_db_path=_text(paths.get("SCADENZIARIO_DB")),
        agenda_db_path=_text(paths.get("AGENDA_DB")),
    )
    storage_root = _text(paths.get("DOCUMENTI_AI_DIR")) or str(Path(_text(paths.get("FASCICOLI_DOCS"))).parent / "documenti_ai")
    result: dict[str, Any] = {
        "ok": True,
        "tenant": slug,
        "source_of_truth": "sqlite",
        "apply": bool(apply),
        "cached_documents": 0,
        "future_candidates": 0,
        "existing_deadlines": 0,
        "would_enrich": 0,
        "existing_enriched": 0,
        "deadlines_created": 0,
        "activities_updated": 0,
        "errors": [],
        "items": [],
    }
    today = date.today()
    seen: set[tuple[str, str, str, str]] = set()

    for fascicolo in fascicoli_manager.tutti(archiviati=False):
        fid = _text(getattr(fascicolo, "id", ""))
        documents = list(getattr(fascicolo, "documenti", []) or [])
        sources = [
            source
            for source in collect_fascicolo_document_sources(
                tenant_id=slug,
                fascicolo_id=fid,
                fascicolo=fascicolo,
                documents_root=_text(paths.get("FASCICOLI_DOCS")),
            )
            if _document_presidio_source_priority(source)[0] < 2
        ]
        if not sources:
            continue
        texts = document_ai_texts_for_catalog(
            tenant_ids=[slug, "default", "single-studio"],
            fascicolo_id=fid,
            documents=documents,
            fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
            structured_db=studio_db,
            storage_root=storage_root,
        )
        for source in sources:
            text = _text(texts.get(_text(source.source_id)))
            if not text:
                continue
            result["cached_documents"] += 1
            for candidate in extract_procedural_dates({source.filename: text}):
                kind = _procedural_date_kind(candidate)
                target_date = _text(candidate.get("date"))
                parsed_day = _date_from_iso_or_it(target_date)
                if kind not in {"udienza", "termine"} or parsed_day is None or parsed_day < today:
                    continue
                key = (fid, _text(source.source_id), kind, target_date)
                if key in seen:
                    continue
                seen.add(key)
                result["future_candidates"] += 1
                message_id, parsed, proposal, report_payload = _report_payload(
                    fascicolo=fascicolo,
                    source=source,
                    text=text,
                    candidate=candidate,
                    kind=kind,
                )
                existing = repo._document_presidio_existing_deadline(
                    fascicolo_id=fid,
                    target_date=target_date,
                    kind=kind,
                )
                item = {
                    "fascicolo_id": fid,
                    "document_id": _text(source.source_id),
                    "documento": source.filename,
                    "kind": kind,
                    "date": target_date,
                    "mode": _text((report_payload.get("remote_hearing") or {}).get("mode_unified")),
                }
                if existing:
                    result["existing_deadlines"] += 1
                    try:
                        current_deadline = repo._scadenziario_manager().get(_text(existing.get("deadline_id")))
                    except Exception:
                        current_deadline = None
                    pending_updates = (
                        _remote_hearing_updates_for_existing(
                            current_deadline,
                            _remote_hearing_deadline_extra(report_payload, proposal),
                            _remote_hearing_note_lines(report_payload, proposal),
                        )
                        if current_deadline is not None
                        else {}
                    )
                    if pending_updates:
                        result["would_enrich"] += 1
                        item["update_fields"] = sorted(pending_updates)
                    if apply:
                        enriched = repo._document_presidio_enrich_existing_deadline(
                            existing_deadline=existing,
                            message_id=message_id,
                            fascicolo_id=fid,
                            proposal=proposal,
                            report_payload=report_payload,
                            actor="Backfill cache documentale",
                        )
                        if enriched.get("enriched"):
                            result["existing_enriched"] += 1
                        agenda_id = _text(enriched.get("agenda_id"))
                        activity = repo._upsert_document_presidio_activity(
                            fascicoli_manager,
                            fascicolo_id=fid,
                            document_id=_text(source.source_id),
                            message_id=message_id,
                            kind=kind,
                            target_date=target_date,
                            title=_text(proposal.get("title")),
                            description=_document_presidio_activity_description(proposal, report_payload),
                            agenda_id=agenda_id,
                        )
                        if activity.get("ok"):
                            result["activities_updated"] += 1
                    item["status"] = "existing"
                else:
                    if apply:
                        deadline = repo.schedule_deadline_from_payload(
                            message_id,
                            parsed=parsed,
                            report=report_payload,
                            message={"linked_fascicolo_id": fid},
                            actor="Backfill cache documentale",
                            due_date=target_date,
                        )
                        if deadline.get("ok"):
                            result["deadlines_created"] += 1
                            activity = repo._upsert_document_presidio_activity(
                                fascicoli_manager,
                                fascicolo_id=fid,
                                document_id=_text(source.source_id),
                                message_id=message_id,
                                kind=kind,
                                target_date=target_date,
                                title=_text(proposal.get("title")),
                                description=_document_presidio_activity_description(proposal, report_payload),
                                agenda_id=_text((deadline.get("agenda") or {}).get("agenda_id")),
                            )
                            if activity.get("ok"):
                                result["activities_updated"] += 1
                        else:
                            result["errors"].append({**item, "message": _text(deadline.get("message"))})
                    item["status"] = "missing"
                if len(result["items"]) < 100:
                    result["items"].append(item)
    result["ok"] = not result["errors"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill idempotente di modalità udienza e scadenze dalla cache documentale.")
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manager = GestioneTenant(str(Path(args.registry)))
    studios = [studio for studio in manager.lista() if studio.slug.casefold() == args.tenant.casefold()]
    if not studios:
        print(json.dumps({"ok": False, "errors": [f"Studio non trovato: {args.tenant}"]}, ensure_ascii=False, indent=2))
        return 1
    report = backfill_tenant(slug=studios[0].slug, paths=_paths(manager, studios[0].slug), apply=bool(args.apply))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
