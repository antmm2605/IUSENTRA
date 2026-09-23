"""Estrae il catalogo beni mobili dal PDF ufficiale PST ACC705.

Il PDF resta la fonte documentale immutabile. Il JSON prodotto e' il mirror
runtime usato dal deposito: conserva anche gli eventuali codici duplicati
pubblicati dal Ministero, senza correggerli o reinterpretarli.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs" / "specs" / "ministero" / "Codifiche_Beni_Mobili.pdf"
DEFAULT_OUTPUT = ROOT / "pct" / "data" / "cataloghi" / "codifiche_beni_mobili_pst.json"
SOURCE_PAGE = "https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC705"
SOURCE_DOCUMENT = "https://pst.giustizia.it/PST/resources/cms/documents/Codifiche_Beni_Mobili.pdf"
EXPECTED_SOURCE_SHA256 = "C081D674CCA3F965DF54B38A564F44A66E8DC5552A92454BF6C1129C6C834DC5"

_ROW = re.compile(r"^(?P<code>[0-9]+(?:\.[0-9A-Z]+)*)\s+(?P<label>.+?)\s*$")
_SECTION_HEADERS = {
    "Beni mobiliari esecuzioni individuali": "esecuzioni_individuali",
    "Beni mobiliari procedure concorsuali": "procedure_concorsuali",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def extract_entries(source: Path) -> list[dict[str, str]]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - script di manutenzione
        raise RuntimeError("pdfplumber e' necessario per estrarre il PDF PST.") from exc

    source_hash = _sha256(source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "Il PDF PST non coincide con la fonte acquisita il 23/09/2026: "
            f"atteso {EXPECTED_SOURCE_SHA256}, trovato {source_hash}."
        )

    entries: list[dict[str, str]] = []
    section = ""
    with pdfplumber.open(source) as document:
        for page in document.pages:
            for raw_line in (page.extract_text() or "").splitlines():
                line = raw_line.strip()
                if line in _SECTION_HEADERS:
                    section = _SECTION_HEADERS[line]
                    continue
                match = _ROW.match(line)
                if not match:
                    continue
                if not section:
                    raise RuntimeError(f"Riga catalogo priva di sezione: {line}")
                entries.append(
                    {
                        "code": match.group("code"),
                        "label": match.group("label"),
                        "scope": section,
                    }
                )

    individual = [item for item in entries if item["scope"] == "esecuzioni_individuali"]
    if [item["code"] for item in individual] != [str(value) for value in range(27)]:
        raise RuntimeError("La sezione esecuzioni individuali non contiene esattamente i codici 0-26.")
    if not any(item["scope"] == "procedure_concorsuali" for item in entries):
        raise RuntimeError("La sezione procedure concorsuali non e' stata estratta.")
    return entries


def build_payload(source: Path) -> dict[str, Any]:
    entries = extract_entries(source)
    return {
        "version": "PST-ACC705-2026-09-23",
        "title": "Codifica beni mobili",
        "sourcePage": SOURCE_PAGE,
        "sourceDocument": SOURCE_DOCUMENT,
        "sourceFile": "docs/specs/ministero/Codifiche_Beni_Mobili.pdf",
        "sourceSha256": _sha256(source),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build_payload(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(payload['entries'])} codifiche salvate in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
