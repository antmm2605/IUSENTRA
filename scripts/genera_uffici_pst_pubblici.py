"""Genera il catalogo pubblico uffici PST civile e penale dai link ufficiali."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path


URL_CIVILI = (
    "https://servizipst.giustizia.it/PST/it/pst_2_4.wp"
    "?ufficioSelect=giudiziari&distretto=&localita=&tipoUfficio=&action%3Asearch=ricerca"
)
URL_PENALI = (
    "https://servizipst.giustizia.it/PST/it/pst_2_4.wp"
    "?ufficioSelect=penali&distretto=&localita=&tipoUfficio=&action%3Asearch=ricerca"
)


_NON_OPERATIVO_RE = re.compile(
    r"(?i)\b(non\s+attiv[oa]?|ex\s+giud|ex\s+sd|ante\s+\d{2}-\d{2}-\d{4}|model office|formazione)\b"
)


def _fetch(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA audit uffici PST"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _estrai_uffici(html_text: str, sezione: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(
        r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>",
        html_text,
        flags=re.I,
    ):
        href = match.group(1).replace("&amp;", "&")
        if "viewUfficio.action" not in href:
            continue
        code_match = re.search(r"codiceUfficio=([^&]+)", href)
        if not code_match:
            continue
        descrizione = html.unescape(re.sub(r"<[^>]+>", " ", match.group(2))).strip()
        codice = code_match.group(1).strip()
        if not codice or not descrizione:
            continue
        non_operativo = bool(_NON_OPERATIVO_RE.search(descrizione)) or codice.startswith("987654321")
        key = (codice, descrizione)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "codice_ufficio": codice,
                "descrizione": descrizione,
                "sezione": sezione,
                "stato_prudenziale": "storico_o_non_operativo" if non_operativo else "pst_visibile",
                "deposito_prudenziale": not non_operativo,
                "href": href,
            }
        )
    return rows


def genera(output: Path, timeout: int = 120) -> dict:
    html_civile = _fetch(URL_CIVILI, timeout)
    html_penale = _fetch(URL_PENALI, timeout)
    civili = _estrai_uffici(html_civile, "giudiziari")
    penali = _estrai_uffici(html_penale, "penali")
    payload = {
        "fonte": {
            "civili": URL_CIVILI,
            "penali": URL_PENALI,
        },
        "generato_il": datetime.now().isoformat(timespec="seconds"),
        "criterio": "Catalogo pubblico PST estratto dagli URL Uffici giudiziari civili e penali.",
        "conteggi": {
            "civili": len(civili),
            "penali": len(penali),
            "civili_deposito_prudenziale": sum(1 for row in civili if row["deposito_prudenziale"]),
            "penali_deposito_prudenziale": sum(1 for row in penali if row["deposito_prudenziale"]),
            "civili_storici_o_non_operativi": sum(1 for row in civili if not row["deposito_prudenziale"]),
            "penali_storici_o_non_operativi": sum(1 for row in penali if not row["deposito_prudenziale"]),
        },
        "uffici": {
            "civili": civili,
            "penali": penali,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="pct/data/uffici_pst_pubblici.json")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    payload = genera(Path(args.output), timeout=args.timeout)
    print(json.dumps({"ok": True, **payload["conteggi"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
