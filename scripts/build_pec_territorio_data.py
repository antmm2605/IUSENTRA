from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.territorio_italia import normalize_comune_key


PEC_TERRITORIO_URL = "https://www.giustizia.it/resources/cms/documents/PEC_territorio.pdf"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "pct" / "data" / "pec_territorio.json"
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def _download_pdf(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA PEC territorio/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - fonte ministeriale esplicita.
        return response.read()


def _lines_from_pdf(content: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(content))
    lines: list[str] = []
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = re.sub(r"\s+", " ", raw).strip()
            if line:
                lines.append(line)
    return lines


def _kind_from_entry(email: str, label: str) -> str:
    text = f"{email} {label}".casefold()
    if "assiseappello" in text or "assise appello" in text:
        return "assise_appello"
    if "assise" in text:
        return "assise"
    if "unep" in text:
        return "unep"
    if "procura generale" in text or ".pg." in text:
        return "procura_generale"
    if "procura per i minorenni" in text or "procmin" in text:
        return "procura_minorenni"
    if "tribunale per i minorenni" in text or "tribmin" in text:
        return "tribunale_minorenni"
    if "corte d'appello" in text or ".ca." in text:
        return "corte_appello"
    if "giudice di pace" in text or "gdp." in text:
        return "giudice_pace"
    if "procura" in text:
        return "procura"
    if "tribunale" in text:
        return "tribunale"
    return ""


def _city_from_entry(kind: str, label: str) -> str:
    city = label.casefold()
    replacements = [
        "procura generale",
        "procura per i minorenni",
        "tribunale per i minorenni",
        "corte d'appello",
        "giudice di pace",
        "tribunale",
        "procura",
        "unep",
    ]
    for replacement in replacements:
        city = city.replace(replacement, " ")
    city = re.sub(r"\s+", " ", city).strip()
    return normalize_comune_key(city) if city else ""


def build_data(output: Path, *, url: str = PEC_TERRITORIO_URL) -> dict[str, Any]:
    content = _download_pdf(url)
    lines = _lines_from_pdf(content)
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = EMAIL_RE.search(line)
        if not match:
            index += 1
            continue
        email = match.group(0).lower()
        label = (line[: match.start()] + " " + line[match.end() :]).strip()
        if not label:
            probe = index + 1
            while probe < len(lines) and EMAIL_RE.search(lines[probe]):
                probe += 1
            if probe < len(lines):
                label = lines[probe]
        kind = _kind_from_entry(email, label)
        city_key = _city_from_entry(kind, label)
        entries.append(
            {
                "email": email,
                "label": label,
                "kind": kind,
                "cityKey": city_key,
            }
        )
        index += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": {
            "title": "Ministero della Giustizia - Posta certificata strutture giustizia",
            "url": url,
            "downloadedAt": datetime.now(timezone.utc).isoformat(),
        },
        "entries": sorted(entries, key=lambda item: (item["kind"], item["cityKey"], item["email"])),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "output": str(output), "entries": len(entries)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera il catalogo PEC territoriale del Ministero della Giustizia.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    result = build_data(Path(args.output))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
