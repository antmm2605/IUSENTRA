"""Backfill tenant-aware della matrice Sentenza Tribunale su documenti AI esistenti."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    ORIGIN,
    SENTENZA_VECTOR_SCHEMA_VERSION,
    SentenzaAutomationOutcome,
    SentenzaEconomicaExtraction,
    analyze_sentenza_tribunale_text,
    apply_sentenza_tribunale_automation,
    sentenza_vector_relevant_excerpt,
)
from pct.fatturazione import GestioneFatturazione
from pct.local_ai import LocalAIService
from pct.storage import StudioDB


ROME = ZoneInfo("Europe/Rome")


@dataclass(slots=True)
class TenantBackfillTarget:
    tenant: str
    storage_key: str
    root: Path


@dataclass(slots=True)
class BackfillDocumentResult:
    tenant: str
    fascicolo_id: str
    document_id: str
    path: str
    found: bool
    fascicolo_found: bool
    sentenza_key: str = ""
    applied: bool = False
    message: str = ""
    proforma_id: str = ""
    proforma_number: str = ""
    vector_index: dict[str, Any] = field(default_factory=dict)
    extraction: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BackfillCandidate:
    path: Path
    text: str
    metadata: dict[str, Any]
    extraction: SentenzaEconomicaExtraction
    result: BackfillDocumentResult
    sentenza_key: str
    fascicolo_key: str
    score: int


def _now_rome() -> str:
    return datetime.now(ROME).replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_tenants(registry: Path, data_root: Path, selected: set[str]) -> list[TenantBackfillTarget]:
    raw = _load_json(registry) if registry.exists() else {}
    targets: list[TenantBackfillTarget] = []
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((str(item.get("slug") or item.get("storage_key") or ""), item) for item in raw if isinstance(item, dict))
    else:
        items = []
    for slug, item in items:
        if not isinstance(item, dict):
            continue
        storage_key = _text(item.get("storage_key")) or _text(item.get("slug")) or _text(slug)
        tenant = _text(item.get("slug")) or storage_key
        if not storage_key:
            continue
        if selected and storage_key not in selected and tenant not in selected and _text(slug) not in selected:
            continue
        root = data_root / "tenants" / storage_key
        if root.exists():
            targets.append(TenantBackfillTarget(tenant=tenant, storage_key=storage_key, root=root))
    if targets or selected:
        return targets
    tenants_root = data_root / "tenants"
    if not tenants_root.exists():
        return []
    return [
        TenantBackfillTarget(tenant=item.name, storage_key=item.name, root=item)
        for item in sorted(tenants_root.iterdir())
        if item.is_dir()
    ]


def _document_id_from_path(path: Path) -> str:
    parts = list(path.parts)
    if len(parts) >= 3 and parts[-1] == "extracted_text.json":
        return parts[-3]
    return ""


def _fascicolo_id_from_path(path: Path) -> str:
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part == "fascicoli" and index + 1 < len(parts):
            candidate = parts[index + 1]
            if candidate != "documenti_ai":
                return candidate
    return ""


def _iter_extracted_texts(tenant_root: Path) -> list[Path]:
    base = tenant_root / "fascicoli" / "documenti_ai"
    if not base.exists():
        return []
    return sorted(base.rglob("extracted_text.json"))


def _document_key(metadata: dict[str, Any]) -> str:
    for key in ("sentenza_key", "document_id", "documento_id", "source_id", "sha256", "filename"):
        value = _text(metadata.get(key))
        if value:
            return f"{key}:{value}"
    return ""


def _candidate_score(extraction: SentenzaEconomicaExtraction, text: str) -> int:
    score = 0
    if extraction.liquidazione_importo is not None:
        score += 100
    if extraction.contributo_unificato_importo is not None:
        score += 40
    if extraction.fondo_spese_importo is not None:
        score += 30
    if extraction.spese_generali:
        score += 10
    if extraction.antistatario:
        score += 5
    score += min(20, len(str(text or "")) // 5000)
    return score


def _rg_label(extraction: SentenzaEconomicaExtraction) -> str:
    if extraction.rg_number and extraction.rg_year:
        return f"{extraction.rg_number}/{extraction.rg_year}"
    return ""


def _sentenza_key(tenant: TenantBackfillTarget, metadata: dict[str, Any], extraction: SentenzaEconomicaExtraction) -> str:
    parts = [
        tenant.storage_key,
        _text(metadata.get("fascicolo_id")),
        _text(extraction.sentence_date),
        _text(extraction.sentence_number),
        _text(extraction.sentence_year),
        _text(extraction.rg_number),
        _text(extraction.rg_year),
    ]
    return "|".join(parts)


def _vector_title(extraction: SentenzaEconomicaExtraction, fascicolo: Any) -> str:
    title = "Sentenza Tribunale"
    if extraction.sentence_number and extraction.sentence_year:
        title = f"Sentenza Tribunale n. {extraction.sentence_number}/{extraction.sentence_year}"
    rg = _rg_label(extraction)
    if rg:
        title = f"{title} - RG {rg}"
    fascicolo_title = _text(getattr(fascicolo, "titolo", ""))
    return f"{title} - {fascicolo_title}" if fascicolo_title else title


def _vector_relevant_excerpt(text: str, *, max_chars: int = 12000) -> str:
    return sentenza_vector_relevant_excerpt(text, max_chars=max_chars) or "n.d."


def _vector_text(
    *,
    extraction: SentenzaEconomicaExtraction,
    fascicolo: Any,
    metadata: dict[str, Any],
    outcome: SentenzaAutomationOutcome,
    text: str,
) -> str:
    rows = [
        "Scheda conoscenza Lex AI - Sentenza Tribunale",
        f"Fascicolo: {_text(getattr(fascicolo, 'titolo', '')) or _text(getattr(fascicolo, 'numero_rg', '')) or metadata.get('fascicolo_id', '')}",
        f"RG: {_rg_label(extraction) or metadata.get('numero_rg', '')}",
        f"Data sentenza: {extraction.sentence_date}",
        f"Liquidazione giudice: {extraction.liquidazione_importo if extraction.liquidazione_importo is not None else 'n.d.'}",
        f"Contributo unificato: {extraction.contributo_unificato_importo if extraction.contributo_unificato_importo is not None else 'n.d.'}",
        f"Fondo spese: {extraction.fondo_spese_importo if extraction.fondo_spese_importo is not None else 'n.d.'}",
        f"Proforma collegata: {outcome.proforma_id or 'n.d.'}",
        f"Documento fonte: {metadata.get('filename') or metadata.get('document_id') or 'n.d.'}",
        "",
        "Estratto liquidazione:",
        extraction.liquidazione_titolo or "n.d.",
        "",
        "Estratto sentenza rilevante:",
        _vector_relevant_excerpt(text),
    ]
    return "\n".join(str(row) for row in rows)


def _local_ai_service(tenant_root: Path, repo_root: Path) -> LocalAIService:
    intelligence = tenant_root / "intelligence"
    return LocalAIService(
        db_path=str(intelligence / "local_ai.db"),
        policy_path=str(repo_root / "config" / "ai-policy.json"),
        config_path=str(tenant_root / "config" / "studio.json"),
        app_root=str(repo_root),
        models_path=str(intelligence / "models"),
    )


def _existing_vector_result(fascicolo: Any, document_key: str) -> dict[str, Any]:
    payments = getattr(fascicolo, "pagamenti", {}) or {}
    automation = payments.get(AUTOMATION_KEY) if isinstance(payments, dict) else {}
    if not isinstance(automation, dict):
        return {}
    vector_indexes = automation.get("vector_indexes")
    if not isinstance(vector_indexes, dict):
        return {}
    result = vector_indexes.get(document_key)
    return dict(result) if isinstance(result, dict) else {}


def _vector_result_current(result: dict[str, Any]) -> bool:
    if not (result.get("ok") and result.get("document_id")):
        return False
    if result.get("schema_version") != SENTENZA_VECTOR_SCHEMA_VERSION:
        return False
    embedding = result.get("embedding") if isinstance(result.get("embedding"), dict) else {}
    return int(embedding.get("pending_remaining") or 0) <= 0


def _record_vector_result(fascicoli: GestioneFascicoli, fascicolo_id: str, document_key: str, result: dict[str, Any]) -> None:
    if not document_key:
        return
    fascicolo = fascicoli.get(fascicolo_id)
    if not fascicolo:
        return
    payments = dict(getattr(fascicolo, "pagamenti", {}) or {})
    automation = dict(payments.get(AUTOMATION_KEY) or {})
    vector_indexes = automation.get("vector_indexes") if isinstance(automation.get("vector_indexes"), dict) else {}
    vector_indexes[document_key] = dict(result or {})
    automation["vector_indexes"] = vector_indexes
    payments[AUTOMATION_KEY] = automation
    fascicoli.aggiorna(fascicolo_id, pagamenti=payments)


def _feed_vector_index(
    *,
    tenant: TenantBackfillTarget,
    repo_root: Path,
    fascicoli: GestioneFascicoli,
    fascicolo_id: str,
    text: str,
    metadata: dict[str, Any],
    outcome: SentenzaAutomationOutcome,
    embed_batch_size: int = 64,
    embed_max_batches: int = 3,
) -> dict[str, Any]:
    document_key = _document_key(metadata)
    fascicolo = fascicoli.get(fascicolo_id)
    if not fascicolo:
        return {"ok": False, "status": "skipped", "error": "Fascicolo non trovato"}
    existing = _existing_vector_result(fascicolo, document_key)
    if _vector_result_current(existing):
        return existing
    try:
        service = _local_ai_service(tenant.root, repo_root)
        extraction = outcome.extraction
        source_id = f"{tenant.storage_key}:{fascicolo_id}:{document_key or metadata.get('sha256') or metadata.get('document_id')}"
        indexed = service.index_text_document(
            source_type="lex_sentenza_tribunale",
            source_id=source_id,
            practice_id=fascicolo_id,
            title=_vector_title(extraction, fascicolo),
            text=_vector_text(extraction=extraction, fascicolo=fascicolo, metadata=metadata, outcome=outcome, text=text),
            metadata={
                "tenant_id": tenant.storage_key,
                "tenant_slug": tenant.tenant,
                "fascicolo_id": fascicolo_id,
                "document_id": _text(metadata.get("document_id")),
                "document_key": document_key,
                "sha256": _text(metadata.get("sha256")),
                "tipo_documento": "sentenza_tribunale",
                "data_sentenza": extraction.sentence_date,
                "rg": _rg_label(extraction),
                "cliente": _text(getattr(fascicolo, "nome_cliente", "")),
                "importo_liquidazione": extraction.liquidazione_importo,
                "contributo_unificato": extraction.contributo_unificato_importo,
                "fondo_spese": extraction.fondo_spese_importo,
                "proforma_id": outcome.proforma_id,
                "origin": ORIGIN,
                "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
            },
        )
        embedding: dict[str, Any] = {}
        document_id = _text(indexed.get("document_id"))
        if document_id:
            try:
                embedding = service.embed_all_pending_chunks(
                    document_id=document_id,
                    batch_size=max(1, embed_batch_size),
                    max_batches=max(1, embed_max_batches),
                )
            except Exception as exc:
                embedding = {"status": "error", "error": str(exc)}
        result = {
            "ok": True,
            "schema_version": SENTENZA_VECTOR_SCHEMA_VERSION,
            "status": indexed.get("status"),
            "document_id": document_id,
            "chunk_count": indexed.get("chunk_count"),
            "embedding": embedding,
        }
    except Exception as exc:
        result = {"ok": False, "status": "error", "error": str(exc)}
    _record_vector_result(fascicoli, fascicolo_id, document_key, result)
    return result


def _build_repositories(tenant: TenantBackfillTarget) -> tuple[GestioneFascicoli, GestioneFatturazione]:
    studio_db = StudioDB.get(str(tenant.root / "studio.db")) if (tenant.root / "studio.db").exists() else None
    fascicoli = GestioneFascicoli(
        db_path=str(tenant.root / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tenant.root / "fascicoli" / "documenti"),
        archive_dir=str(tenant.root / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    fatturazione = GestioneFatturazione(
        db_path=str(tenant.root / "fatturazione" / "parcelle.json"),
        studio_db=studio_db,
    )
    return fascicoli, fatturazione


def _metadata_for_text(payload: dict[str, Any], path: Path, tenant: TenantBackfillTarget) -> dict[str, Any]:
    document_id = _text(payload.get("document_id")) or _document_id_from_path(path)
    fascicolo_id = _text(payload.get("fascicolo_id")) or _fascicolo_id_from_path(path)
    return {
        "tenant_id": tenant.storage_key,
        "tenant_slug": tenant.tenant,
        "source_tenant_id": _text(payload.get("tenant_id")),
        "fascicolo_id": fascicolo_id,
        "document_id": document_id,
        "documento_id": document_id,
        "filename": _text(payload.get("filename") or payload.get("original_filename") or path.parent.parent.name),
        "sha256": _text(payload.get("sha256")),
        "extracted_text_path": str(path),
        "tipo_documento": _text(payload.get("tipo_documento") or payload.get("classification") or "Sentenza Tribunale"),
    }


def run_backfill(
    *,
    data_root: Path,
    registry: Path,
    repo_root: Path,
    tenants: set[str] | None = None,
    apply: bool = False,
    skip_lex: bool = False,
    limit: int = 0,
    lex_embed_batch_size: int = 64,
    lex_embed_max_batches: int = 3,
) -> dict[str, Any]:
    selected = tenants or set()
    unique_sentenze: set[str] = set()
    unique_fascicoli_found: set[str] = set()
    unique_fascicoli_applied: set[str] = set()
    unique_fascicoli_confirmed: set[str] = set()
    unique_missing_fascicoli: set[str] = set()
    report: dict[str, Any] = {
        "ok": True,
        "source_of_truth": "sqlite/postgresql runtime repositories",
        "mode": "apply" if apply else "dry_run",
        "started_at": _now_rome(),
        "data_root": str(data_root),
        "registry": str(registry),
        "tenants": [],
        "totals": {
            "documents_seen": 0,
            "sentenze_found": 0,
            "fascicoli_found": 0,
            "applied": 0,
            "matrix_confirmed": 0,
            "vector_indexed": 0,
            "vector_embedding_errors": 0,
            "skipped_missing_fascicolo": 0,
            "duplicates_skipped": 0,
            "unique_sentenze": 0,
            "unique_fascicoli_found": 0,
            "unique_fascicoli_applied": 0,
            "unique_fascicoli_confirmed": 0,
            "unique_missing_fascicoli": 0,
            "errors": 0,
        },
    }
    for tenant in _load_tenants(registry, data_root, selected):
        tenant_unique_sentenze: set[str] = set()
        tenant_unique_fascicoli_found: set[str] = set()
        tenant_unique_fascicoli_applied: set[str] = set()
        tenant_unique_fascicoli_confirmed: set[str] = set()
        tenant_unique_missing_fascicoli: set[str] = set()
        tenant_duplicates_skipped = 0
        tenant_matrix_confirmed = 0
        tenant_report: dict[str, Any] = {
            "tenant": tenant.tenant,
            "storage_key": tenant.storage_key,
            "root": str(tenant.root),
            "documents": [],
            "summary": {},
        }
        fascicoli, fatturazione = _build_repositories(tenant)
        paths = _iter_extracted_texts(tenant.root)
        candidates: list[BackfillCandidate] = []
        best_by_sentenza_key: dict[str, BackfillCandidate] = {}
        for path in paths:
            if limit and report["totals"]["documents_seen"] >= limit:
                break
            report["totals"]["documents_seen"] += 1
            try:
                payload = _load_json(path)
                if not isinstance(payload, dict):
                    continue
                text = _text(payload.get("text") or payload.get("testo"))
                metadata = _metadata_for_text(payload, path, tenant)
                extraction = analyze_sentenza_tribunale_text(text, metadata)
                if not extraction.found:
                    continue
                report["totals"]["sentenze_found"] += 1
                fascicolo_id = _text(metadata.get("fascicolo_id"))
                fascicolo = fascicoli.get(fascicolo_id)
                sentenza_key = _sentenza_key(tenant, metadata, extraction)
                fascicolo_key = f"{tenant.storage_key}:{fascicolo_id}"
                unique_sentenze.add(sentenza_key)
                tenant_unique_sentenze.add(sentenza_key)
                metadata["sentenza_key"] = sentenza_key
                result = BackfillDocumentResult(
                    tenant=tenant.storage_key,
                    fascicolo_id=fascicolo_id,
                    document_id=_text(metadata.get("document_id")),
                    path=str(path),
                    found=True,
                    fascicolo_found=fascicolo is not None,
                    sentenza_key=sentenza_key,
                    extraction=extraction.to_dict(),
                    warnings=list(extraction.warnings or []),
                )
                if fascicolo is None:
                    result.message = "Fascicolo non trovato nel repository tenant corrente."
                    report["totals"]["skipped_missing_fascicolo"] += 1
                    unique_missing_fascicoli.add(fascicolo_key)
                    tenant_unique_missing_fascicoli.add(fascicolo_key)
                    tenant_report["documents"].append(result.to_dict())
                    continue
                report["totals"]["fascicoli_found"] += 1
                unique_fascicoli_found.add(fascicolo_key)
                tenant_unique_fascicoli_found.add(fascicolo_key)
                candidate = BackfillCandidate(
                    path=path,
                    text=text,
                    metadata=metadata,
                    extraction=extraction,
                    result=result,
                    sentenza_key=sentenza_key,
                    fascicolo_key=fascicolo_key,
                    score=_candidate_score(extraction, text),
                )
                candidates.append(candidate)
                current_best = best_by_sentenza_key.get(sentenza_key)
                if current_best is None or candidate.score > current_best.score:
                    best_by_sentenza_key[sentenza_key] = candidate
            except Exception as exc:
                report["ok"] = False
                report["totals"]["errors"] += 1
                tenant_report["documents"].append(
                    {
                        "tenant": tenant.storage_key,
                        "path": str(path),
                        "found": False,
                        "fascicolo_found": False,
                        "applied": False,
                        "message": f"Errore backfill: {type(exc).__name__}: {exc}",
                    }
                )
        for candidate in candidates:
            result = candidate.result
            if best_by_sentenza_key.get(candidate.sentenza_key) is not candidate:
                result.message = "Duplicato della stessa sentenza: matrice già contabilizzata sul documento migliore."
                result.warnings.append("duplicato_sentenza_saltato")
                report["totals"]["duplicates_skipped"] += 1
                tenant_duplicates_skipped += 1
                tenant_report["documents"].append(result.to_dict())
                continue
            if apply:
                outcome = apply_sentenza_tribunale_automation(
                    fascicoli_repository=fascicoli,
                    fatturazione_repository=fatturazione,
                    fascicolo_id=candidate.result.fascicolo_id,
                    text=candidate.text,
                    document_metadata=candidate.metadata,
                    actor="Lex AI backfill",
                )
                result.applied = bool(outcome.applied)
                result.message = outcome.message
                result.proforma_id = outcome.proforma_id
                result.proforma_number = outcome.proforma_number
                result.extraction = outcome.extraction.to_dict()
                report["totals"]["matrix_confirmed"] += 1
                tenant_matrix_confirmed += 1
                unique_fascicoli_confirmed.add(candidate.fascicolo_key)
                tenant_unique_fascicoli_confirmed.add(candidate.fascicolo_key)
                if outcome.applied:
                    report["totals"]["applied"] += 1
                    unique_fascicoli_applied.add(candidate.fascicolo_key)
                    tenant_unique_fascicoli_applied.add(candidate.fascicolo_key)
                if not skip_lex and outcome.extraction.found:
                    result.vector_index = _feed_vector_index(
                        tenant=tenant,
                        repo_root=repo_root,
                        fascicoli=fascicoli,
                        fascicolo_id=candidate.result.fascicolo_id,
                        text=candidate.text,
                        metadata=candidate.metadata,
                        outcome=outcome,
                        embed_batch_size=lex_embed_batch_size,
                        embed_max_batches=lex_embed_max_batches,
                    )
                    if result.vector_index.get("ok"):
                        report["totals"]["vector_indexed"] += 1
                    if str((result.vector_index.get("embedding") or {}).get("status") or "") == "error":
                        report["totals"]["vector_embedding_errors"] += 1
            else:
                result.message = "Dry-run: sentenza riconosciuta, matrice applicabile."
            tenant_report["documents"].append(result.to_dict())
        tenant_report["summary"] = {
            "documents_reported": len(tenant_report["documents"]),
            "sentenze_found": sum(1 for item in tenant_report["documents"] if item.get("found")),
            "applied": sum(1 for item in tenant_report["documents"] if item.get("applied")),
            "matrix_confirmed": tenant_matrix_confirmed,
            "missing_fascicolo": sum(1 for item in tenant_report["documents"] if item.get("found") and not item.get("fascicolo_found")),
            "duplicates_skipped": tenant_duplicates_skipped,
            "unique_sentenze": len(tenant_unique_sentenze),
            "unique_fascicoli_found": len(tenant_unique_fascicoli_found),
            "unique_fascicoli_applied": len(tenant_unique_fascicoli_applied),
            "unique_fascicoli_confirmed": len(tenant_unique_fascicoli_confirmed),
            "unique_missing_fascicoli": len(tenant_unique_missing_fascicoli),
        }
        report["tenants"].append(tenant_report)
    report["totals"]["unique_sentenze"] = len(unique_sentenze)
    report["totals"]["unique_fascicoli_found"] = len(unique_fascicoli_found)
    report["totals"]["unique_fascicoli_applied"] = len(unique_fascicoli_applied)
    report["totals"]["unique_fascicoli_confirmed"] = len(unique_fascicoli_confirmed)
    report["totals"]["unique_missing_fascicoli"] = len(unique_missing_fascicoli)
    report["finished_at"] = _now_rome()
    return report


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill della matrice Sentenza Tribunale sui documenti AI tenant-aware.")
    parser.add_argument("--data-root", default="data", help="Radice dati IUSENTRA.")
    parser.add_argument("--registry", default="data/tenants.json", help="Registro tenant.")
    parser.add_argument("--tenant", action="append", default=[], help="Tenant/storage_key da processare; ripetibile.")
    parser.add_argument("--apply", action="store_true", help="Applica realmente la matrice. Senza questo flag esegue solo dry-run.")
    parser.add_argument("--skip-lex", action="store_true", help="Non alimenta il DB vettoriale Lex AI durante --apply.")
    parser.add_argument("--lex-embed-batch-size", type=int, default=64, help="Chunk Lex AI per batch embedding durante --apply.")
    parser.add_argument("--lex-embed-max-batches", type=int, default=3, help="Numero massimo batch embedding per sentenza durante --apply.")
    parser.add_argument("--limit", type=int, default=0, help="Limite globale documenti letti, utile per diagnosi mirate.")
    parser.add_argument("--report", default="", help="Percorso file JSON report.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    data_root = Path(args.data_root).resolve()
    registry = Path(args.registry).resolve()
    report = run_backfill(
        data_root=data_root,
        registry=registry,
        repo_root=repo_root,
        tenants=set(args.tenant or []),
        apply=bool(args.apply),
        skip_lex=bool(args.skip_lex),
        limit=max(0, int(args.limit or 0)),
        lex_embed_batch_size=max(1, int(args.lex_embed_batch_size or 64)),
        lex_embed_max_batches=max(1, int(args.lex_embed_max_batches or 3)),
    )
    if args.report:
        _write_report(Path(args.report), report)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
