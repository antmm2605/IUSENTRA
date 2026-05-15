"""Controlled local population for the Legal Source Engine.

This module makes the first native engine operational without crawling. It
materializes the already-reviewed registry, manuscripts and scorecards into
ignored runtime folders, then builds a small local JSONL index of source cards.
Those cards are not a legal corpus: they let Lex discover, cite and rank
official source adapters until source-specific ingestion is implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import LegalCitation, RetrievedLegalPassage
from .registry import LegalSourceRegistry, create_default_registry
from .reports import dogfood_report, scorecard_report, source_manuscript_report, source_registry_report
from .settings import LegalSourceEngineSettings, save_runtime_config


INDEX_FILENAME = "passages.jsonl"
MANIFEST_FILENAME = "manifest.json"
POPULATE_REPORT_FILENAME = "auto_populate_report.json"


@dataclass(slots=True)
class AutoPopulateResult:
    ok: bool
    activated: bool = False
    populated: bool = False
    network_used: bool = False
    sources_total: int = 0
    sources_enabled: int = 0
    passages_written: int = 0
    index_path: str = ""
    manifest_path: str = ""
    report_path: str = ""
    runtime_config_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def activate_local_engine(
    *,
    source_ids: list[str] | tuple[str, ...] | None = None,
    settings: LegalSourceEngineSettings | None = None,
    populate: bool = True,
    force: bool = False,
) -> AutoPopulateResult:
    base_settings = settings or LegalSourceEngineSettings.from_env(include_runtime_config=False)
    registry = create_default_registry(settings=base_settings)
    selected_ids = list(source_ids or registry.source_ids())
    active_settings = base_settings.with_activation(selected_ids)
    runtime_path = save_runtime_config(active_settings)

    result = AutoPopulateResult(
        ok=True,
        activated=True,
        sources_total=len(registry.all_sources()),
        sources_enabled=len(selected_ids),
        runtime_config_path=str(runtime_path),
    )
    if populate:
        populated = populate_local_engine(settings=active_settings, force=force)
        result.populated = populated.populated
        result.network_used = populated.network_used
        result.passages_written = populated.passages_written
        result.index_path = populated.index_path
        result.manifest_path = populated.manifest_path
        result.report_path = populated.report_path
        result.warnings.extend(populated.warnings)
        result.ok = result.ok and populated.ok
    return result


def ensure_operational_index(
    *,
    settings: LegalSourceEngineSettings | None = None,
    registry: LegalSourceRegistry | None = None,
    force: bool = False,
) -> AutoPopulateResult:
    active_settings = settings or LegalSourceEngineSettings.from_env()
    active_registry = registry or create_default_registry(settings=active_settings)
    index_path = active_settings.index_dir / INDEX_FILENAME
    if not active_settings.enabled and not force:
        return AutoPopulateResult(
            ok=True,
            sources_total=len(active_registry.all_sources()),
            sources_enabled=len(active_registry.enabled_sources()),
            index_path=str(index_path),
            warnings=["Legal Source Engine non abilitato: popolamento automatico saltato."],
        )
    if not active_settings.auto_populate and not force:
        return AutoPopulateResult(
            ok=True,
            sources_total=len(active_registry.all_sources()),
            sources_enabled=len(active_registry.enabled_sources()),
            index_path=str(index_path),
            warnings=["Auto-populate non abilitato: indice locale non modificato."],
        )
    if index_path.exists() and not force:
        return AutoPopulateResult(
            ok=True,
            populated=False,
            sources_total=len(active_registry.all_sources()),
            sources_enabled=len(active_registry.enabled_sources()),
            index_path=str(index_path),
            warnings=["Indice locale gia presente: usare force per rigenerarlo."],
        )
    return populate_local_engine(settings=active_settings, registry=active_registry, force=force)


def populate_local_engine(
    *,
    settings: LegalSourceEngineSettings | None = None,
    registry: LegalSourceRegistry | None = None,
    force: bool = False,
) -> AutoPopulateResult:
    active_settings = settings or LegalSourceEngineSettings.from_env()
    active_registry = registry or create_default_registry(settings=active_settings)
    source_rows = active_registry.enabled_sources() if active_registry.enabled_sources() else active_registry.all_sources()
    passages = build_seed_passages(active_registry, source_ids=[source.source_id for source in source_rows])

    active_settings.data_dir.mkdir(parents=True, exist_ok=True)
    active_settings.index_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = active_settings.artifact_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    index_path = active_settings.index_dir / INDEX_FILENAME
    manifest_path = active_settings.index_dir / MANIFEST_FILENAME
    report_path = reports_dir / POPULATE_REPORT_FILENAME

    if index_path.exists() and not force:
        return AutoPopulateResult(
            ok=True,
            populated=False,
            sources_total=len(active_registry.all_sources()),
            sources_enabled=len(active_registry.enabled_sources()),
            passages_written=0,
            index_path=str(index_path),
            manifest_path=str(manifest_path),
            report_path=str(report_path),
            warnings=["Indice locale gia presente: nessuna riscrittura eseguita."],
        )

    _write_json(active_settings.data_dir / "registry.json", source_registry_report(active_registry))
    _write_json(active_settings.data_dir / "manuscripts.json", source_manuscript_report(active_registry))
    _write_json(active_settings.data_dir / "scorecards.json", scorecard_report(active_registry))
    _write_passages(index_path, passages)

    manifest = _build_manifest(active_registry, passages, settings=active_settings)
    _write_json(manifest_path, manifest)
    report = {
        "ok": True,
        "mode": "controlled_local_auto_populate",
        "network_used": False,
        "customer_data_used": False,
        "corpus_downloaded": False,
        "generated_at": manifest["generated_at"],
        "settings": {
            "enabled": active_settings.enabled,
            "allow_network": active_settings.allow_network,
            "auto_populate": active_settings.auto_populate,
            "populate_on_startup": active_settings.populate_on_startup,
            "require_citations": active_settings.require_citations,
            "data_dir": str(active_settings.data_dir),
            "index_dir": str(active_settings.index_dir),
            "artifact_dir": str(active_settings.artifact_dir),
        },
        "registry": source_registry_report(active_registry),
        "dogfood": dogfood_report(),
        "manifest": manifest,
    }
    _write_json(report_path, report)

    return AutoPopulateResult(
        ok=True,
        populated=True,
        network_used=False,
        sources_total=len(active_registry.all_sources()),
        sources_enabled=len(active_registry.enabled_sources()),
        passages_written=len(passages),
        index_path=str(index_path),
        manifest_path=str(manifest_path),
        report_path=str(report_path),
    )


def build_seed_passages(
    registry: LegalSourceRegistry,
    *,
    source_ids: list[str] | tuple[str, ...] | None = None,
    retrieved_at: str | None = None,
) -> list[RetrievedLegalPassage]:
    timestamp = retrieved_at or _now_iso()
    selected = set(source_ids or registry.source_ids())
    passages: list[RetrievedLegalPassage] = []
    for source in registry.all_sources():
        if source.source_id not in selected:
            continue
        manuscript = source.manuscript
        metadata = source.metadata
        citation = LegalCitation(
            source_id=metadata.source_id,
            source_name=metadata.display_name,
            source_category=metadata.category,
            jurisdiction=metadata.jurisdiction,
            document_type="source_research_manuscript",
            authority=metadata.display_name,
            title=f"Manoscritto fonte - {metadata.display_name}",
            url=metadata.base_url,
            retrieved_at=timestamp,
        )
        text = " ".join(
            [
                f"Fonte ufficiale registrata: {metadata.display_name}.",
                f"Categoria: {metadata.category}.",
                f"Giurisdizione: {metadata.jurisdiction}.",
                f"URL ufficiale: {metadata.base_url or 'da configurare per la fonte specifica'}.",
                "Modalita di accesso documentate: " + ", ".join(manuscript.access_modes or ["non definite"]) + ".",
                "Identificativi supportati: " + ", ".join(manuscript.identifiers_supported or ["non definiti"]) + ".",
                "Strategia di ingestione: " + "; ".join(manuscript.ingestion_strategy or ["solo revisione manuale"]) + ".",
                "Limiti noti: " + "; ".join(manuscript.limitations or ["da completare"]) + ".",
                "Comportamenti vietati: " + "; ".join(manuscript.forbidden_behaviors or ["crawling non autorizzato"]) + ".",
            ]
        )
        passages.append(
            RetrievedLegalPassage(
                text=text,
                citation=citation,
                score=0.45,
                retrieval_method="auto_seed_source_registry",
                source_priority=metadata.priority,
                metadata={
                    "document_id": f"source:{metadata.source_id}",
                    "stable_identifier": f"source:{metadata.source_id}",
                    "record_type": "source_research_manuscript",
                    "official": metadata.official,
                    "supports_open_data": metadata.supports_open_data,
                    "supports_search": metadata.supports_search,
                    "supports_fetch_by_id": metadata.supports_fetch_by_id,
                    "supports_versions": metadata.supports_versions,
                    "requires_auth": metadata.requires_auth,
                    "versioning_supported": manuscript.versioning_supported,
                    "identifiers_supported": list(manuscript.identifiers_supported),
                    "citation_requirements": list(manuscript.citation_requirements),
                },
            )
        )
    passages.sort(key=lambda passage: (passage.source_priority, passage.citation.source_name))
    return passages


def _build_manifest(
    registry: LegalSourceRegistry,
    passages: list[RetrievedLegalPassage],
    *,
    settings: LegalSourceEngineSettings,
) -> dict[str, Any]:
    payload = [passage.to_dict() for passage in passages]
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "generated_at": _now_iso(),
        "engine": "iusentra_legal_source_engine",
        "mode": "controlled_local_auto_populate",
        "network_used": False,
        "customer_data_used": False,
        "passages": len(passages),
        "sources_total": len(registry.all_sources()),
        "sources_enabled": len(registry.enabled_sources()),
        "source_ids": [passage.citation.source_id for passage in passages],
        "checksum_sha256": digest,
        "index_path": str(settings.index_dir / INDEX_FILENAME),
    }


def _write_passages(path: Path, passages: list[RetrievedLegalPassage]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for passage in passages:
            handle.write(json.dumps(passage.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IUSENTRA Legal Source Engine local populator")
    parser.add_argument("--activate", action="store_true", help="write ignored runtime config enabling local source cards")
    parser.add_argument("--populate", action="store_true", help="materialize registry and local JSONL index")
    parser.add_argument("--force", action="store_true", help="regenerate existing local index")
    parser.add_argument("--json", action="store_true", help="print JSON result")
    args = parser.parse_args(argv)

    if args.activate:
        result = activate_local_engine(populate=args.populate or not args.activate, force=args.force)
    else:
        result = ensure_operational_index(force=args.force) if args.populate else ensure_operational_index()

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "Legal Source Engine: "
            f"ok={result.ok} activated={result.activated} populated={result.populated} "
            f"passages={result.passages_written} network_used={result.network_used}"
        )
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())


__all__ = [
    "AutoPopulateResult",
    "INDEX_FILENAME",
    "MANIFEST_FILENAME",
    "activate_local_engine",
    "build_seed_passages",
    "ensure_operational_index",
    "main",
    "populate_local_engine",
]
