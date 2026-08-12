#!/usr/bin/env python
"""Harvest pubblico del Registro PP.AA. dal Portale Servizi Telematici.

Base normativa: art. 16, comma 12, D.L. 179/2012 (registro degli indirizzi
elettronici delle pubbliche amministrazioni presso il Ministero della
giustizia) e D.M. 44/2011. La fonte e' il form pubblico ``Ricerca Pubblica
Amministrazione`` del PST (``https://servizipst.giustizia.it/PST/it/pst_2_8_2.wp``,
azione ufficiale ``/ExtStr2/do/pubbamm/searchPA.action``): il tool usa
esclusivamente l'export Displaytag della stessa ricerca pubblica, senza
credenziali, e salva gli esiti come evidenza runtime locale esclusa da Git.

Copertura: la ricerca e' a sottostringa, quindi le query ``codFiscale=0..9``
coprono ogni ente con codice fiscale/partita IVA numerici e le query
``denominazione=a,e,i,o,u`` coprono gli eventuali enti senza codice fiscale.
I duplicati tra query vengono deduplicati prima dell'import nella cache SQL
di ``tools/registro_ppaa_sync_cache.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

PST_FORM_URL = "https://servizipst.giustizia.it/PST/it/pst_2_8_2.wp"
PST_ACTION_PATH = "/ExtStr2/do/pubbamm/searchPA.action"
EXPORT_TABLE_PARAM = "d-4001731-e=3"
DEFAULT_OUTPUT_DIR = Path("data/local/registro_ppaa")
USER_AGENT = "IUSENTRA-RegistroPPAA-Harvest (consultazione pubblica registro PP.AA. art. 16 c.12 D.L. 179/2012)"

_ROW_RE = re.compile(r"<row>(.*?)</row>", re.DOTALL)
_COLUMN_RE = re.compile(r"<column>(.*?)</column>", re.DOTALL)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_query_plan() -> list[dict[str, str]]:
    plan = [{"label": f"cf-{digit}", "codFiscale": digit, "denominazione": ""} for digit in "0123456789"]
    plan.extend({"label": f"den-{vowel}", "codFiscale": "", "denominazione": vowel} for vowel in "aeiou")
    return plan


def export_url(query: dict[str, str]) -> str:
    from urllib.parse import quote

    return (
        f"{PST_FORM_URL}?{EXPORT_TABLE_PARAM}"
        f"&pec=&codFiscale={quote(query.get('codFiscale', ''))}"
        f"&actionPath={quote(PST_ACTION_PATH, safe='')}"
        f"&currentFrame=0&denominazione={quote(query.get('denominazione', ''))}"
    )


def build_opener() -> urllib.request.OpenerDirector:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", USER_AGENT)]
    return opener


def fetch_export(opener: urllib.request.OpenerDirector, query: dict[str, str], *, timeout: int) -> bytes:
    with opener.open(export_url(query), timeout=timeout) as response:
        return response.read()


def parse_export_rows(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8", errors="replace")
    rows: list[dict[str, str]] = []
    for row_match in _ROW_RE.finditer(text):
        columns = [_text(html.unescape(col)) for col in _COLUMN_RE.findall(row_match.group(1))]
        if len(columns) < 5:
            continue
        rows.append(
            {
                "denominazione": columns[0],
                "codice_fiscale": columns[1],
                "codice_ente": columns[2],
                "tipo": columns[3],
                "pec": columns[4].lower(),
            }
        )
    return rows


def dedup_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    unique_rows: list[dict[str, str]] = []
    for row in rows:
        key = (row["denominazione"].lower(), row["codice_fiscale"], row["pec"])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def harvest(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    plan = build_query_plan()
    if args.only:
        wanted = {label.strip() for label in args.only.split(",") if label.strip()}
        plan = [query for query in plan if query["label"] in wanted]

    opener = build_opener() if not args.skip_fetch else None
    if opener is not None:
        # Warm-up: apre il form pubblico per ottenere la sessione anonima PST.
        with opener.open(PST_FORM_URL, timeout=args.timeout) as response:
            response.read()

    all_rows: list[dict[str, str]] = []
    fetches: list[dict[str, Any]] = []
    for query in plan:
        page_path = pages_dir / f"harvest-{query['label']}.html"
        if opener is not None:
            payload = fetch_export(opener, query, timeout=args.timeout)
            page_path.write_bytes(payload)
            time.sleep(max(0.0, args.delay))
        elif page_path.exists():
            payload = page_path.read_bytes()
        else:
            fetches.append({"query": query["label"], "rows": 0, "error": "pagina locale assente"})
            continue
        rows = parse_export_rows(payload)
        all_rows.extend(rows)
        fetches.append(
            {
                "query": query["label"],
                "rows": len(rows),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    unique_rows = dedup_rows(all_rows)
    jsonl_path = Path(args.jsonl) if args.jsonl else output_dir / "harvest-registro-ppaa.jsonl"
    if not jsonl_path.is_absolute():
        jsonl_path = repo_root / jsonl_path
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in unique_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary: dict[str, Any] = {
        "source": "registro_ppaa_public",
        "form_url": PST_FORM_URL,
        "action_path": PST_ACTION_PATH,
        "queries": fetches,
        "rows_seen_total": len(all_rows),
        "rows_distinct": len(unique_rows),
        "rows_with_pec": sum(1 for row in unique_rows if "@" in row["pec"]),
        "jsonl": str(jsonl_path),
        "privacy": "Evidenza runtime locale: pagine e JSONL non vanno committati.",
    }

    if args.import_cache:
        import registro_ppaa_sync_cache as sync_module

        sync_args = argparse.Namespace(
            output_dir=str(output_dir),
            query=[],
            import_file=[str(jsonl_path)],
            reset=False,
            status=False,
            request_timeout=90,
            cert_thumbprint="",
            prefer_cf="",
            pin_env="",
            pin_stdin=False,
        )
        summary["cache_state"] = sync_module.run(sync_args)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest pubblico del Registro PP.AA. dal PST (export Displaytag).")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Cartella cache locale ignorata da Git.")
    parser.add_argument("--jsonl", default="", help="Percorso JSONL di uscita; vuoto = dentro output-dir.")
    parser.add_argument("--delay", type=float, default=3.0, help="Pausa in secondi tra le richieste al PST.")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--only", default="", help="Sottoinsieme di query, es. 'cf-0,den-a'.")
    parser.add_argument("--skip-fetch", action="store_true", help="Non contatta il PST: riparsa le pagine gia' scaricate.")
    parser.add_argument("--import-cache", action="store_true", help="Importa subito il JSONL nella cache SQL locale.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = harvest(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
