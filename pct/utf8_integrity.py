"""Servizio di integrita' UTF-8 per dati e risposte IUSENTRA.

Il servizio corregge i casi recuperabili di mojibake e caratteri sostitutivi
nei testi operativi. Non crea backup: e' pensato per manutenzione notturna su
file tenant-aware e per sanitizzare le risposte Lex prima della UI.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Sequence


TEXT_SUFFIXES = {
    ".csv",
    ".eml",
    ".html",
    ".ics",
    ".json",
    ".md",
    ".txt",
    ".xml",
}
DEFAULT_MAX_FILES = 20000
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
SCHEMA_VERSION = "iusentra.utf8_integrity.v1"

_TARGET_CHARS = "àèéìòùÀÈÉÌÒÙ—–€’‘“”…•"
_COMMON_BAD_TO_GOOD: dict[str, str] = {}
for _target in _TARGET_CHARS:
    raw = _target.encode("utf-8")
    for _encoding in ("cp1252", "cp1250", "latin-1"):
        try:
            bad = raw.decode(_encoding)
        except UnicodeError:
            continue
        if bad and "\ufffd" not in bad and bad != _target:
            _COMMON_BAD_TO_GOOD[bad] = _target

_COMMON_BAD_TO_GOOD.update(
    {
        "â€“": "–",
        "â€”": "—",
        "â€˜": "‘",
        "â€™": "’",
        "â€œ": "“",
        "â€�": "”",
        "â€\ufffd": "”",
        "â€¦": "…",
        "â€¢": "•",
        "â‚¬": "€",
    }
)

_MOJIBAKE_RE = re.compile(
    r"\u00c3[\u0080-\u00bf]"
    r"|\u00c2[\u0080-\u00bf]"
    r"|\u00e2[\u0080-\u00bf\u201a\u20ac\u0192\u201e\u2026\u2020\u2021\u02c6\u2030\u0160\u2039\u0152\u017d\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\u017e\u0178]"
    r"|\u0102[\u0080-\u02ff]"
)

_REPLACEMENT_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpossibilit\ufffd(?=\W|$)", re.IGNORECASE), "possibilità"),
    (re.compile(r"\battivit\ufffd(?=\W|$)", re.IGNORECASE), "attività"),
    (re.compile(r"\bqualit\ufffd(?=\W|$)", re.IGNORECASE), "qualità"),
    (re.compile(r"\bpriorit\ufffd(?=\W|$)", re.IGNORECASE), "priorità"),
    (re.compile(r"\bmodalit\ufffd(?=\W|$)", re.IGNORECASE), "modalità"),
    (re.compile(r"\bresponsabilit\ufffd(?=\W|$)", re.IGNORECASE), "responsabilità"),
    (re.compile(r"\bsociet\ufffd(?=\W|$)", re.IGNORECASE), "società"),
    (re.compile(r"\bcitt\ufffd(?=\W|$)", re.IGNORECASE), "città"),
    (re.compile(r"\bperch\ufffd(?=\W|$)", re.IGNORECASE), "perché"),
    (re.compile(r"\bpoich\ufffd(?=\W|$)", re.IGNORECASE), "poiché"),
    (re.compile(r"\bfinch\ufffd(?=\W|$)", re.IGNORECASE), "finché"),
    (re.compile(r"\bnonch\ufffd(?=\W|$)", re.IGNORECASE), "nonché"),
    (re.compile(r"\bpi\ufffd(?=\W|$)", re.IGNORECASE), "più"),
    (re.compile(r"\bpu\ufffd(?=\W|$)", re.IGNORECASE), "può"),
    (re.compile(r"\bcos\ufffd(?=\W|$)", re.IGNORECASE), "così"),
    (re.compile(r"\bgi\ufffd(?=\W|$)", re.IGNORECASE), "già"),
    (re.compile(r"\bsar\ufffd(?=\W|$)", re.IGNORECASE), "sarà"),
    (re.compile(r"\bavr\ufffd(?=\W|$)", re.IGNORECASE), "avrà"),
    (re.compile(r"\bdovr\ufffd(?=\W|$)", re.IGNORECASE), "dovrà"),
    (re.compile(r"\bpotr\ufffd(?=\W|$)", re.IGNORECASE), "potrà"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def encoding_artifact_score(text: str) -> int:
    sample = str(text or "")
    control_chars = sum(1 for char in sample if ord(char) < 32 and char not in "\r\n\t")
    return (
        sample.count("\ufffd") * 100
        + len(_MOJIBAKE_RE.findall(sample)) * 20
        + control_chars * 10
    )


def contains_encoding_artifacts(text: str) -> bool:
    sample = str(text or "")
    return "\ufffd" in sample or bool(_MOJIBAKE_RE.search(sample))


def _transcode_candidates(text: str) -> list[str]:
    candidates = [text]
    for encoding in ("cp1252", "cp1250", "latin-1"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _repair_common_sequences(text: str) -> str:
    repaired = str(text or "")
    for _ in range(3):
        previous = repaired
        for bad, good in _COMMON_BAD_TO_GOOD.items():
            repaired = repaired.replace(bad, good)
        if repaired == previous:
            break
    return repaired


def _repair_replacement_chars(text: str, *, drop_unresolved: bool) -> str:
    repaired = str(text or "")
    for pattern, replacement in _REPLACEMENT_WORDS:
        repaired = pattern.sub(
            lambda match, repl=replacement: repl[:1].upper() + repl[1:] if match.group(0)[:1].isupper() else repl,
            repaired,
        )
    if drop_unresolved:
        repaired = repaired.replace("\ufffd", "")
    return repaired


def repair_text_encoding(text: str, *, drop_unresolved: bool = False) -> str:
    """Restituisce il miglior testo UTF-8 recuperabile.

    Corregge sia sequenze tipo ``piÃ¹``/``perchĂ©`` sia casi frequenti con
    carattere sostitutivo. Quando ``drop_unresolved`` e' vero, eventuali
    sostitutivi non recuperabili vengono rimossi per non arrivare in UI.
    """

    original = str(text or "")
    candidates: list[str] = []
    for candidate in _transcode_candidates(original):
        repaired = _repair_common_sequences(candidate)
        repaired = _repair_replacement_chars(repaired, drop_unresolved=drop_unresolved)
        candidates.append(repaired)
    best = min(candidates or [original], key=encoding_artifact_score)
    if encoding_artifact_score(best) <= encoding_artifact_score(original):
        return best
    repaired = _repair_common_sequences(original)
    return _repair_replacement_chars(repaired, drop_unresolved=drop_unresolved)


def _decode_best(raw: bytes) -> tuple[str, str, bool]:
    candidates: list[tuple[int, str, str, bool]] = []
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "cp1250", "latin-1"):
        try:
            decoded = raw.decode(encoding)
            had_decode_error = False
        except UnicodeError:
            decoded = raw.decode(encoding, errors="replace")
            had_decode_error = True
        candidates.append((encoding_artifact_score(decoded), encoding, decoded, had_decode_error))
    _, encoding, decoded, had_decode_error = min(candidates, key=lambda item: item[0])
    return decoded, encoding, had_decode_error


def _repair_json_value(value: Any) -> tuple[Any, int]:
    changed = 0
    if isinstance(value, str):
        repaired = repair_text_encoding(value, drop_unresolved=False)
        return repaired, int(repaired != value)
    if isinstance(value, list):
        rows = []
        for item in value:
            repaired, item_changed = _repair_json_value(item)
            rows.append(repaired)
            changed += item_changed
        return rows, changed
    if isinstance(value, dict):
        repaired_dict: dict[str, Any] = {}
        for key, item in value.items():
            repaired_key = repair_text_encoding(str(key), drop_unresolved=False)
            repaired_item, item_changed = _repair_json_value(item)
            repaired_dict[repaired_key] = repaired_item
            changed += item_changed + int(repaired_key != str(key))
        return repaired_dict, changed
    return value, 0


def _repair_file_text(path: Path, raw: bytes) -> tuple[str, dict[str, Any]]:
    decoded, encoding_used, had_decode_error = _decode_best(raw)
    before_score = encoding_artifact_score(decoded)
    repaired_text = repair_text_encoding(decoded, drop_unresolved=False)
    json_strings_repaired = 0
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(repaired_text)
            repaired_json, json_strings_repaired = _repair_json_value(parsed)
            if json_strings_repaired:
                repaired_text = json.dumps(repaired_json, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        except (TypeError, ValueError):
            pass
    return repaired_text, {
        "encoding_used": encoding_used,
        "had_decode_error": had_decode_error,
        "before_score": before_score,
        "after_score": encoding_artifact_score(repaired_text),
        "json_strings_repaired": json_strings_repaired,
        "replacement_chars_before": decoded.count("\ufffd"),
        "replacement_chars_after": repaired_text.count("\ufffd"),
    }


def _is_within_roots(path: Path, roots: Sequence[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots)


def _iter_text_files(roots: Sequence[Path], *, max_files: int) -> Iterable[Path]:
    seen: set[Path] = set()
    count = 0
    for root in roots:
        if not root.exists():
            continue
        iterator = [root] if root.is_file() else root.rglob("*")
        for path in iterator:
            if count >= max_files:
                return
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            count += 1
            yield path


def _default_report_path(config: dict[str, Any]) -> Path:
    explicit = config.get("IUSENTRA_UTF8_INTEGRITY_REPORT") or os.getenv("IUSENTRA_UTF8_INTEGRITY_REPORT")
    if explicit:
        return Path(str(explicit))
    legal_db = config.get("LEGAL_INTELLIGENCE_DB") or os.getenv("PCT_LEGAL_INTELLIGENCE_DB")
    if legal_db:
        return Path(str(legal_db)).expanduser().resolve().parent / "utf8_integrity_report.json"
    if Path("/data").exists():
        return Path("/data/intelligence/utf8_integrity_report.json")
    return Path("intelligence/utf8_integrity_report.json")


def roots_from_config(config: dict[str, Any] | None = None) -> list[Path]:
    cfg = dict(config or {})
    explicit = _clean(cfg.get("IUSENTRA_UTF8_ROOTS") or os.getenv("IUSENTRA_UTF8_ROOTS"))
    if explicit:
        return [Path(part) for part in re.split(r"[;|]", explicit) if _clean(part)]
    roots: list[Path] = []
    data_root = _clean(cfg.get("PCT_DATA_ROOT") or cfg.get("DATA_ROOT") or os.getenv("PCT_DATA_ROOT"))
    if data_root:
        roots.append(Path(data_root))
    elif Path("/data").exists():
        roots.append(Path("/data"))
    elif Path("data").exists():
        roots.append(Path("data"))
    for key in (
        "TENANTS_REGISTRY",
        "CLIENTI_DB",
        "SOGGETTI_DB",
        "SOGGETTI_PARTI_DB",
        "AGENDA_DB",
        "SCADENZIARIO_DB",
        "FASCICOLI_DB",
        "EMAIL_CASELLA_DB",
        "EMAIL_ORDINARIA_DB",
        "MESSAGGI_DB",
        "PREVENTIVI_DB",
        "FATTURAZIONE_DB",
        "STUDIO_CONFIG",
        "LEGAL_INTELLIGENCE_DB",
        "GIURISPRUDENZA_DB",
        "NORMATIVE_TABLES_DB",
    ):
        raw = cfg.get(key)
        if raw:
            roots.append(Path(str(raw)).expanduser().resolve().parent)
    unique: list[Path] = []
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


@dataclass(slots=True)
class Utf8FileResult:
    path: str
    status: str
    changed: bool
    encoding_used: str = ""
    before_score: int = 0
    after_score: int = 0
    replacement_chars_before: int = 0
    replacement_chars_after: int = 0
    message: str = ""


def scan_utf8_integrity(
    roots: Sequence[str | Path],
    *,
    repair: bool = True,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    safe_roots = [Path(root).expanduser().resolve() for root in roots if _clean(root)]
    started_at = _now_iso()
    files: list[Utf8FileResult] = []
    checked = repaired_count = artifact_count = skipped_large = errors = unresolved = 0
    for path in _iter_text_files(safe_roots, max_files=max_files):
        checked += 1
        try:
            size = path.stat().st_size
            if size > max_file_bytes:
                skipped_large += 1
                files.append(Utf8FileResult(str(path), "saltato_file_grande", False, message=f"{size} byte"))
                continue
            if not _is_within_roots(path, safe_roots):
                files.append(Utf8FileResult(str(path), "fuori_perimetro", False))
                continue
            raw = path.read_bytes()
            repaired_text, meta = _repair_file_text(path, raw)
            original_text, _, _ = _decode_best(raw)
            changed = repaired_text != original_text or meta["had_decode_error"]
            has_artifacts = meta["before_score"] > 0 or meta["replacement_chars_before"] > 0 or meta["had_decode_error"]
            if has_artifacts:
                artifact_count += 1
            if meta["replacement_chars_after"]:
                unresolved += 1
            if changed and repair:
                path.write_text(repaired_text, encoding="utf-8")
                repaired_count += 1
            status = "riparato" if changed and repair else ("da_riparare" if changed else "ok")
            files.append(
                Utf8FileResult(
                    path=str(path),
                    status=status,
                    changed=changed,
                    encoding_used=str(meta["encoding_used"]),
                    before_score=int(meta["before_score"]),
                    after_score=int(meta["after_score"]),
                    replacement_chars_before=int(meta["replacement_chars_before"]),
                    replacement_chars_after=int(meta["replacement_chars_after"]),
                )
            )
        except Exception as exc:
            errors += 1
            files.append(Utf8FileResult(str(path), "errore", False, message=str(exc)))
    report = {
        "schema_version": SCHEMA_VERSION,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "ok": errors == 0 and unresolved == 0,
        "repair_enabled": bool(repair),
        "no_backup_created": True,
        "roots": [str(root) for root in safe_roots],
        "checked_files": checked,
        "files_with_artifacts": artifact_count,
        "repaired_files": repaired_count,
        "skipped_large_files": skipped_large,
        "error_files": errors,
        "unresolved_replacement_files": unresolved,
        "files": [asdict(row) for row in files if row.status != "ok"][:500],
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = str(target)
    return report


def run_utf8_integrity_service(
    config: dict[str, Any] | None = None,
    *,
    repair: bool = True,
    roots: Sequence[str | Path] | None = None,
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    cfg = dict(config or {})
    selected_roots = [Path(root) for root in roots] if roots else roots_from_config(cfg)
    selected_report = report_path or _default_report_path(cfg)
    return scan_utf8_integrity(
        selected_roots,
        repair=repair,
        max_files=int(max_files or os.getenv("IUSENTRA_UTF8_MAX_FILES") or DEFAULT_MAX_FILES),
        max_file_bytes=int(max_file_bytes or os.getenv("IUSENTRA_UTF8_MAX_FILE_BYTES") or DEFAULT_MAX_FILE_BYTES),
        report_path=selected_report,
    )


__all__ = [
    "SCHEMA_VERSION",
    "contains_encoding_artifacts",
    "encoding_artifact_score",
    "repair_text_encoding",
    "roots_from_config",
    "run_utf8_integrity_service",
    "scan_utf8_integrity",
]
