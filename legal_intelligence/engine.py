"""Orchestratore del controllo giornaliero fonti ufficiali."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .applier import apply_update_record
from .detector import build_diff, content_hash, has_changed
from .fetcher import FetchResult, OfficialSourceFetcher
from .impact_analyzer import analyze_impact
from .normalizer import normalize_text
from .sources import DEFAULT_LEGAL_SOURCES, LegalSource
from .store import LegalIntelligenceStore, now_iso


FetchCallable = Callable[[LegalSource, dict[str, str]], FetchResult]


class LegalIntelligenceDailyEngine:
    def __init__(
        self,
        db_path: str | Path,
        *,
        sources: Iterable[LegalSource] | None = None,
        fetcher: FetchCallable | None = None,
    ):
        self.store = LegalIntelligenceStore(db_path)
        self.sources = list(sources or DEFAULT_LEGAL_SOURCES)
        self.fetcher = fetcher
        for source in self.sources:
            self.store.upsert_source(source)

    def _fetch(self, source: LegalSource, headers: dict[str, str]) -> FetchResult:
        if self.fetcher:
            return self.fetcher(source, headers)
        return OfficialSourceFetcher().fetch(source, previous_headers=headers)

    def run_daily_sync(self, *, source_ids: list[str] | None = None) -> dict:
        wanted = {item for item in (source_ids or []) if item}
        selected = [source for source in self.sources if source.enabled and (not wanted or source.id in wanted)]
        run_id = self.store.create_run()
        summary = {
            "run_id": run_id,
            "status": "completed",
            "sources_checked": 0,
            "updates_detected": 0,
            "updates_applied": 0,
            "pending_review": 0,
            "errors_count": 0,
            "log": [],
        }
        for source in selected:
            self.store.upsert_source(source)
            summary["sources_checked"] += 1
            headers = self.store.source_headers(source.id)
            result = self._fetch(source, headers)
            if not result.ok:
                self.store.mark_source_error(source.id, result.error or f"HTTP {result.status_code}")
                summary["errors_count"] += 1
                summary["log"].append({"source_id": source.id, "status": "errore", "error": result.error})
                continue
            if result.status_code == 304:
                self.store.mark_source_not_modified(source.id)
                summary["log"].append({"source_id": source.id, "status": "invariata"})
                continue
            content_type = result.headers.get("content-type", "") if result.headers else ""
            normalized = normalize_text(result.content, content_type)
            new_hash = content_hash(normalized)
            previous = self.store.latest_snapshot(source.id)
            previous_hash = previous.get("content_sha256") if previous else ""
            previous_text = previous.get("normalized_text") if previous else ""
            self.store.add_snapshot(source.id, result=result, content_sha256=new_hash, normalized_text=normalized)
            if has_changed(previous_hash, new_hash):
                analysis = analyze_impact(source, normalized)
                update = {
                    "source_id": source.id,
                    "detected_at": now_iso(),
                    "title": analysis.title,
                    "summary": analysis.summary,
                    "old_sha256": previous_hash or "",
                    "new_sha256": new_hash,
                    "diff_text": build_diff(previous_text or "", normalized),
                    "impact_areas": analysis.impact_areas,
                    "apply_mode": analysis.apply_mode,
                    "status": "pending_review",
                    "severity": analysis.severity,
                    "metadata": {"source_url": result.url, "official": source.official},
                }
                applied = apply_update_record(update)
                update_id = self.store.create_update(applied)
                summary["updates_detected"] += 1
                if applied["status"] == "applied":
                    summary["updates_applied"] += 1
                else:
                    summary["pending_review"] += 1
                summary["log"].append({"source_id": source.id, "status": applied["status"], "update_id": update_id})
            else:
                summary["log"].append({"source_id": source.id, "status": "invariata"})
        if summary["errors_count"]:
            summary["status"] = "completed_with_errors"
        self.store.finish_run(run_id, summary)
        return summary

    def dashboard_snapshot(self) -> dict:
        return self.store.dashboard()

    def approve_update(self, update_id: int) -> None:
        self.store.update_status(
            update_id,
            status="applied",
            note="Aggiornamento approvato manualmente dallo studio.",
        )

    def get_update(self, update_id: int) -> dict | None:
        return self.store.get_update(update_id)
