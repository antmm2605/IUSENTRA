"""Standardizza date e orari visibili in italiano e Europe/Rome.

Lo script agisce solo su sorgenti/template, non su dati runtime, payload tecnici,
XML/EML originali, timestamp RFC 3161 o bundle React compilati.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_PARTS = {
    ".git",
    "data",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}
EXCLUDED_PREFIXES = {
    Path("tests"),
    Path("scripts"),
    Path("docs/specs"),
    Path("lex/tests"),
    Path("pct/data"),
    Path("tests/fixtures"),
    Path("web/static/react/assets"),
    Path("web/static/react/.vite"),
}

SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".html"}


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def is_excluded(path: Path) -> bool:
    relative = rel(path)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in EXCLUDED_PREFIXES)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def replace_file(path: Path, transform) -> bool:
    original = read(path)
    updated = transform(original)
    if updated == original:
        return False
    write(path, updated)
    return True


def ensure_import(text: str, import_line: str, anchor: str | None = None) -> str:
    if import_line in text:
        return text
    if anchor and anchor in text:
        return text.replace(anchor, anchor + "\n" + import_line, 1)
    match = re.search(r"(^from __future__ import annotations\s*\n)", text, flags=re.MULTILINE)
    if match:
        idx = match.end()
        return text[:idx] + "\n" + import_line + "\n" + text[idx:]
    return import_line + "\n" + text


def normalize_fatturazione_pdf(text: str) -> str:
    if "from pct.formatting import format_date_it, format_datetime_it, format_euro_it" not in text:
        if "from pct.formatting import format_datetime_it, format_euro_it" in text:
            text = text.replace(
                "from pct.formatting import format_datetime_it, format_euro_it",
                "from pct.formatting import format_date_it, format_datetime_it, format_euro_it",
            )
        elif "from pct.formatting import format_euro_it" in text:
            text = text.replace(
                "from pct.formatting import format_euro_it",
                "from pct.formatting import format_date_it, format_datetime_it, format_euro_it",
            )
        else:
            text = ensure_import(text, "from pct.formatting import format_date_it, format_datetime_it, format_euro_it")
    return text.replace(
        '        story.append(Paragraph(f"<b>Data UTC:</b> {audit_proof.get(\'event_ts_utc\', \'\')}", style_small))',
        "        story.append(Paragraph(\n"
        "            f\"<b>Data e ora italiana:</b> {format_datetime_it(audit_proof.get('event_ts_utc', ''), include_timezone=True)}\",\n"
        "            style_small,\n"
        "        ))",
    )


def normalize_email_bridge(text: str) -> str:
    text = ensure_import(
        text,
        "from pct.formatting import DISPLAY_TIMEZONE, parse_datetime_rome",
        anchor="from pct.email_client import CartellaEmail, GestioneEmailRicevute, StatoEmail",
    )
    text = re.sub(
        r"def _parse_datetime\(value: Any\) -> datetime \| None:\n"
        r"(?:    .+\n){1,18}?    return None\n",
        "def _parse_datetime(value: Any) -> datetime | None:\n"
        "    parsed = parse_datetime_rome(value)\n"
        "    if parsed is None:\n"
        "        return None\n"
        "    return parsed.astimezone(DISPLAY_TIMEZONE).replace(tzinfo=None)\n",
        text,
    )
    text = text.replace("    today = date.today()\n", "    today = datetime.now(DISPLAY_TIMEZONE).date()\n")
    return text


def _find_matching_brace(text: str, start: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _insert_timezone_in_options(text: str, marker: str) -> str:
    offset = 0
    while True:
        idx = text.find(marker, offset)
        if idx == -1:
            return text
        brace = text.find("{", idx + len(marker) - 1)
        if brace == -1:
            offset = idx + len(marker)
            continue
        end = _find_matching_brace(text, brace)
        if end == -1:
            offset = idx + len(marker)
            continue
        block = text[brace : end + 1]
        if "timeZone" in block:
            offset = end + 1
            continue
        if "\n" in block:
            line_start = text.rfind("\n", 0, brace) + 1
            base_indent = re.match(r"\s*", text[line_start:brace]).group(0)
            insertion = "\n" + base_indent + "  timeZone: 'Europe/Rome',"
            text = text[: brace + 1] + insertion + text[brace + 1 :]
            offset = end + len(insertion) + 1
        else:
            text = text[: brace + 1] + " timeZone: 'Europe/Rome'," + text[brace + 1 :]
            offset = end + len(" timeZone: 'Europe/Rome',") + 1


def normalize_frontend_datetime_options(text: str) -> str:
    markers = [
        "new Intl.DateTimeFormat('it-IT', {",
        'new Intl.DateTimeFormat("it-IT", {',
        ".toLocaleDateString('it-IT', {",
        '.toLocaleDateString("it-IT", {',
        ".toLocaleTimeString('it-IT', {",
        '.toLocaleTimeString("it-IT", {',
    ]
    for marker in markers:
        text = _insert_timezone_in_options(text, marker)
    return text


def audit_visible_datetime_residuals() -> list[str]:
    findings: list[str] = []
    markers = [
        "new Intl.DateTimeFormat('it-IT', {",
        'new Intl.DateTimeFormat("it-IT", {',
        ".toLocaleDateString('it-IT', {",
        '.toLocaleDateString("it-IT", {',
        ".toLocaleTimeString('it-IT', {",
        '.toLocaleTimeString("it-IT", {',
    ]
    visible_iso_literal = re.compile(r"\b20\d{2}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)?\b")
    visible_raw_dynamic = re.compile(
        r"(Data|Scadenza|Valido fino|pagamento entro|arrivo|inviat|consegn|ricevut|audit|modified_at|label)"
        r".*\{[^}]*\b(data_|timestamp|event_ts|created_at|updated_at|sent_at|received_at|delivered_at)[^}]*\}",
        re.IGNORECASE,
    )
    visible_context = re.compile(
        r"(Data|Scadenza|Valido fino|pagamento entro|arrivo|inviat|consegn|ricevut|audit|backup|modificat|label)",
        re.IGNORECASE,
    )
    technical_line = re.compile(
        r"(https?://|urn:nir:|codiceRedazionale|dataPubblicazioneGazzetta|decreto\.legislativo:|"
        r"decreto\.legge:|decreto\.del\.presidente\.della\.repubblica:|presidente\.repubblica:|legge:|<postacert>|SCHEMA_VERSION|schema_version|"
        r"source_code|effective_from|published_at|checked_on|LAST_VERIFIED_AT|VERIFIED_ON|"
        r"input type=\"date\"|type=\"date\"|type=\"hidden\"|data-label=|data-date=|data-time=|data-val|"
        r"data-pst-key=|placeholder=|"
        r"Date\.UTC|datetime\.now\(UTC\)|datetime\.now\(tz=UTC\)|"
        r"format_date_it|format_datetime_it|formatDateIt|formatDateTimeIt|formatDateLabel|formatDocumentAIDate|"
        r"awFormatDate|_format_italian_date|italian_date\(|_italian_date\(|strftime\('%d/%m/%Y|strftime\(\"%d/%m/%Y|"
        r"\|data_it\b|\|dataora_it\b|\|fmt_data\b|_label\b|data_oggi|\[\d+:\d+\]|"
        r"_fmt\b|created_at_fmt|sent_at|data_doc|metadata=\{|fieldConfidence\(|setNotifica\(|"
        r"destinatario\.data_verifica_pec|context\['destinatario'\]\['data_verifica_pec'\]|"
        r"isoformat\(|fromisoformat|data_ora = f\"|help=|# ISO|ISO 8601|template field|\"token\":|"
        r"\"start\":|\"end\":|data_scadenza=|data_pagamento=|data_emissione=|data_pubblicazione=|data_atto|file_markers|key =)",
        re.IGNORECASE,
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_excluded(path) or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative = rel(path)
        if relative == Path("scripts/standardizza_date_italiane.py") or relative == Path("tests/test_pdf_style.py"):
            continue
        try:
            text = read(path)
        except UnicodeDecodeError:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if technical_line.search(stripped):
                continue
            if "Data UTC:" in stripped:
                findings.append(f"{relative.as_posix()}:{idx}: {stripped}")
            if visible_raw_dynamic.search(stripped):
                findings.append(f"{relative.as_posix()}:{idx}: data dinamica visibile senza helper italiano: {stripped}")
            if visible_context.search(stripped) and visible_iso_literal.search(stripped):
                findings.append(f"{relative.as_posix()}:{idx}: data ISO visibile: {stripped}")
        for marker in markers:
            offset = 0
            while True:
                idx = text.find(marker, offset)
                if idx == -1:
                    break
                brace = text.find("{", idx + len(marker) - 1)
                end = _find_matching_brace(text, brace) if brace != -1 else -1
                block = text[brace : end + 1] if end != -1 else ""
                if "timeZone" not in block:
                    line_no = text.count("\n", 0, idx) + 1
                    findings.append(f"{relative.as_posix()}:{line_no}: formatter data senza Europe/Rome")
                offset = (end + 1) if end != -1 else idx + len(marker)
    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    changed: list[str] = []

    targeted = {
        Path("web/blueprints/fatturazione.py"): normalize_fatturazione_pdf,
        Path("web/services/react_email_bridge.py"): normalize_email_bridge,
    }
    for relative, transform in targeted.items():
        path = ROOT / relative
        if path.exists() and replace_file(path, transform):
            changed.append(relative.as_posix())

    for base in (ROOT / "frontend" / "src", ROOT / "web" / "static" / "js"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and not is_excluded(path) and path.suffix.lower() in {".ts", ".tsx", ".js"}:
                if replace_file(path, normalize_frontend_datetime_options):
                    changed.append(rel(path).as_posix())

    findings = audit_visible_datetime_residuals()
    print("standardizza_date_italiane")
    print(f"modified_files={len(changed)}")
    for item in changed:
        print(f"  modified: {item}")
    print(f"visible_datetime_findings={len(findings)}")
    for item in findings[:80]:
        print(f"  finding: {item}")
    if len(findings) > 80:
        print(f"  ... altri {len(findings) - 80} finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
