"""Verifica prudente delle fonti ufficiali usate dal motore Template Atti."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any


RULES_DIR = Path(__file__).resolve().parents[1] / "legal_rules"
SOURCE_REGISTRY_FILE = RULES_DIR / "source_registry.yml"


def _load_registry() -> dict[str, Any]:
    try:
        return json.loads(SOURCE_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sources": []}


@dataclass(slots=True)
class VerifiedNormativeSource:
    id: str
    title: str
    official_url: str
    verification_status: str
    fetched_at: str
    http_status: int = 0
    content_hash: str = ""
    matched_patterns: list[str] = field(default_factory=list)
    missing_patterns: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_normative_source(source: dict[str, Any], *, timeout_seconds: float = 8.0, offline: bool = False) -> VerifiedNormativeSource:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_id = str(source.get("id") or "").strip()
    title = str(source.get("title") or source_id).strip()
    url = str(source.get("official_url") or "").strip()
    patterns = [str(item).strip() for item in source.get("matched_patterns") or [] if str(item).strip()]
    if offline:
        return VerifiedNormativeSource(
            id=source_id,
            title=title,
            official_url=url,
            verification_status=str(source.get("verification_status") or "pending_live_verification"),
            fetched_at=now,
            matched_patterns=[],
            missing_patterns=patterns,
            error="Verifica live non eseguita: modalità offline.",
        )
    if not url:
        return VerifiedNormativeSource(
            id=source_id,
            title=title,
            official_url=url,
            verification_status="missing_url",
            fetched_at=now,
            missing_patterns=patterns,
            error="URL ufficiale mancante.",
        )
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA legal source verifier"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(600000)
            status = int(getattr(response, "status", 0) or 0)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return VerifiedNormativeSource(
            id=source_id,
            title=title,
            official_url=url,
            verification_status="unreachable",
            fetched_at=now,
            missing_patterns=patterns,
            error=str(exc),
        )
    text = body.decode("utf-8", errors="ignore").casefold()
    matched = [pattern for pattern in patterns if pattern.casefold() in text]
    missing = [pattern for pattern in patterns if pattern not in matched]
    content_hash = hashlib.sha256(body).hexdigest()
    verification_status = "verified_online" if status < 400 and (not patterns or not missing) else "pattern_missing"
    return VerifiedNormativeSource(
        id=source_id,
        title=title,
        official_url=url,
        verification_status=verification_status,
        fetched_at=now,
        http_status=status,
        content_hash=content_hash,
        matched_patterns=matched,
        missing_patterns=missing,
    )


def verify_ruleset_sources(
    *,
    output_dir: str | Path = "data/legal_sources/snapshots",
    timeout_seconds: float = 8.0,
    offline: bool = False,
) -> list[VerifiedNormativeSource]:
    registry = _load_registry()
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    results: list[VerifiedNormativeSource] = []
    for source in registry.get("sources") or []:
        if not isinstance(source, dict):
            continue
        result = verify_normative_source(source, timeout_seconds=timeout_seconds, offline=offline)
        results.append(result)
        safe_id = result.id.replace("/", "_") or "source"
        (target / f"{safe_id}.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    summary = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "offline": offline,
        "total": len(results),
        "verified": sum(1 for item in results if item.verification_status == "verified_online"),
        "pending_or_failed": [
            item.to_dict()
            for item in results
            if item.verification_status not in {"verified_online", "verified_snapshot"}
        ],
    }
    (target / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return results
