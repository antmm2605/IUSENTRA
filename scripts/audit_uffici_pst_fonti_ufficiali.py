"""Audit read-only delle fonti ufficiali PST per uffici giudiziari.

Il controllo confronta il catalogo pubblico PST generato in
``pct/data/uffici_pst_pubblici.json`` con le schede dettaglio pubbliche del
Portale Servizi Telematici. Non usa credenziali, PIN o sessioni private.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JSON = REPO_ROOT / "pct" / "data" / "uffici_pst_pubblici.json"
OUT_JSON = REPO_ROOT / "artifacts" / "audit" / "uffici-pst-fonti-ufficiali-20260602.json"
OUT_MD = REPO_ROOT / "artifacts" / "audit" / "uffici-pst-fonti-ufficiali-20260602.md"
PST_BASE = "https://servizipst.giustizia.it"
NON_OPERATIVO_RE = re.compile(
    r"(?i)\b(non\s+attiv[oa]?|ex\s+giud|ex\s+sd|ante\s+\d{2}-\d{2}-\d{4}|model office|formazione)\b"
)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _extract_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for table in re.findall(r"<table\b[^>]*class=[\"'][^\"']*serviziTable[^\"']*[\"'][^>]*>([\s\S]*?)</table>", text, flags=re.I):
        for row_html in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>", table, flags=re.I):
            cells = re.findall(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>", row_html, flags=re.I)
            clean = [_clean_text(cell) for cell in cells]
            if clean and not all(cell.lower() in {"tipo atto depositabile", "data avvio", "ufficio interno", "fonte normativa", "servizio", "data attivazione", "descrizione"} for cell in clean):
                rows.append(clean)
    return rows


def _detail_block(raw: str) -> str:
    h3_match = re.search(r"<h3[^>]*>[\s\S]*?</h3>", raw, flags=re.I)
    if not h3_match:
        return raw
    start = h3_match.start()
    end_candidates = []
    for marker in ("<!-- box centrale 1 -->", '<div id="main_bottom"', "<footer", '<div id="footer"'):
        pos = raw.find(marker, h3_match.end())
        if pos >= 0:
            end_candidates.append(pos)
    end = min(end_candidates) if end_candidates else len(raw)
    return raw[start:end]


def _detail_url(row: dict) -> str:
    href = str(row.get("href") or "").replace("¤tFrame", "&currentFrame")
    return urljoin(PST_BASE, href)


def _fetch_detail(row: dict, timeout: int) -> dict:
    url = _detail_url(row)
    request = urllib.request.Request(url, headers={"User-Agent": "IUSENTRA audit uffici PST"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(response.status)
        raw = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    block = _detail_block(raw)
    title_match = re.search(r"<h3[^>]*>([\s\S]*?)</h3>", block, flags=re.I)
    pec = sorted(set(re.findall(r"mailto:([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", block, flags=re.I)))
    table_rows = _extract_table_rows(block)
    detail_identity_text = " ".join(
        [
            str(row.get("descrizione") or ""),
            _clean_text(title_match.group(1)) if title_match else "",
        ]
    )
    return {
        "codice_ufficio": row.get("codice_ufficio"),
        "descrizione": row.get("descrizione"),
        "sezione": row.get("sezione"),
        "deposito_prudenziale_catalogo": bool(row.get("deposito_prudenziale")),
        "stato_prudenziale_catalogo": row.get("stato_prudenziale"),
        "url": url,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "titolo_dettaglio": _clean_text(title_match.group(1)) if title_match else "",
        "pec": pec,
        "righe_tabella_servizi": len(table_rows),
        "tabella_servizi_prime_righe": table_rows[:12],
        "marker_non_operativo_dettaglio": bool(NON_OPERATIVO_RE.search(detail_identity_text)),
    }


def _audit(workers: int, timeout: int, include_storici: bool) -> dict:
    public = json.loads(PUBLIC_JSON.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for section in ("civili", "penali"):
        for row in public.get("uffici", {}).get(section, []):
            if include_storici or row.get("deposito_prudenziale"):
                rows.append(row)

    details: list[dict] = []
    errors: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(_fetch_detail, row, timeout): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                details.append(future.result())
            except Exception as exc:
                errors.append({
                    "codice_ufficio": row.get("codice_ufficio"),
                    "descrizione": row.get("descrizione"),
                    "sezione": row.get("sezione"),
                    "errore": str(exc),
                    "url": _detail_url(row),
                })

    def _section(section: str) -> list[dict]:
        return [item for item in details if item.get("sezione") == section]

    summary = {
        "generato_il": datetime.now().isoformat(timespec="seconds"),
        "fonte_catalogo": public.get("fonte", {}),
        "catalogo_conteggi": public.get("conteggi", {}),
        "dettagli_controllati": len(details),
        "errori_dettaglio": len(errors),
        "civili_dettagli_controllati": len(_section("giudiziari")),
        "penali_dettagli_controllati": len(_section("penali")),
        "dettagli_senza_pec": sum(1 for item in details if not item.get("pec")),
        "penali_senza_pec": sum(1 for item in _section("penali") if not item.get("pec")),
        "penali_con_tabella_atti": sum(1 for item in _section("penali") if int(item.get("righe_tabella_servizi") or 0) > 0),
        "marker_non_operativo_dettaglio": sum(1 for item in details if item.get("marker_non_operativo_dettaglio")),
        "href_corrupt": sum(1 for item in details if "¤" in str(item.get("url") or "")),
    }
    return {"summary": summary, "errors": errors, "details": sorted(details, key=lambda x: (x.get("sezione") or "", x.get("descrizione") or ""))}


def _write_markdown(payload: dict, path: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# Audit fonti ufficiali PST - uffici giudiziari",
        "",
        f"Generato: {summary['generato_il']}",
        "",
        "Fonti ufficiali usate:",
        f"- Civili: {summary['fonte_catalogo'].get('civili', '')}",
        f"- Penali: {summary['fonte_catalogo'].get('penali', '')}",
        "- Schede dettaglio PST pubbliche collegate a ciascun ufficio prudenzialmente depositabile.",
        "",
        "Esito sintetico:",
        f"- Catalogo civili: {summary['catalogo_conteggi'].get('civili')} voci; depositabili prudenziali {summary['catalogo_conteggi'].get('civili_deposito_prudenziale')}; storiche/non operative {summary['catalogo_conteggi'].get('civili_storici_o_non_operativi')}.",
        f"- Catalogo penali: {summary['catalogo_conteggi'].get('penali')} voci; depositabili prudenziali {summary['catalogo_conteggi'].get('penali_deposito_prudenziale')}; storiche/non operative {summary['catalogo_conteggi'].get('penali_storici_o_non_operativi')}.",
        f"- Schede dettaglio controllate: {summary['dettagli_controllati']} (civili {summary['civili_dettagli_controllati']}, penali {summary['penali_dettagli_controllati']}).",
        f"- Errori dettaglio: {summary['errori_dettaglio']}.",
        f"- Link corrotti da entità HTML: {summary['href_corrupt']}.",
        f"- Penali con tabella atti depositabili valorizzata: {summary['penali_con_tabella_atti']}.",
        f"- Penali senza PEC in scheda dettaglio: {summary['penali_senza_pec']}.",
        "",
        "Limite accertato:",
        "la lista pubblica PST non espone un flag universale `attivo`; lo stato viene quindi trattato prudenzialmente: voci con diciture di ufficio storico/non operativo o Model Office non sono scelte automaticamente per deposito.",
        "",
    ]
    if payload["errors"]:
        lines.append("Errori:")
        for error in payload["errors"][:30]:
            lines.append(f"- {error.get('sezione')} {error.get('codice_ufficio')} {error.get('descrizione')}: {error.get('errore')}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--include-storici", action="store_true")
    parser.add_argument("--output-json", default=str(OUT_JSON))
    parser.add_argument("--output-md", default=str(OUT_MD))
    args = parser.parse_args()
    payload = _audit(args.workers, args.timeout, args.include_storici)
    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(payload, out_md)
    print(json.dumps({"ok": True, **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
