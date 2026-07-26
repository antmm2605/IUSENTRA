#!/usr/bin/env python
"""Synchronize ReGIndE subjects through the certified Local Signer channel.

The registry payload is personal/professional data. This tool deliberately keeps
the downloaded cache under ``data/local/reginde`` by default, which is local
runtime data and must not be committed.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
REGINDE_NS = "http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt"
DEFAULT_OUTPUT_DIR = Path("data/local/reginde")
DEFAULT_PREFER_CF = "MNTGPP94L01G791A"


def now_rome() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
    except Exception:
        return datetime.now().astimezone().isoformat(timespec="seconds")


def local_name(tag: Any) -> str:
    raw = str(tag or "")
    return raw.rsplit("}", 1)[-1].split(":", 1)[-1]


def normalize_key_name(value: Any) -> str:
    return "".join(ch for ch in local_name(value).lower() if ch.isalnum())


def normalize_cf(value: Any) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def normalize_pec(value: Any) -> str:
    return str(value or "").strip().lower()


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip()
        marker = value.lower()
        if value and marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def node_values(node: ET.Element) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}

    def add(name: Any, value: Any) -> None:
        key = normalize_key_name(name)
        text_value = str(value or "").strip()
        if key and text_value:
            values.setdefault(key, []).append(text_value)

    for element in node.iter():
        add(element.tag, element.text)
        for attr_name, attr_value in element.attrib.items():
            add(attr_name, attr_value)
    return values


def first(values: dict[str, list[str]], *names: str) -> str:
    for name in names:
        candidates = values.get(normalize_key_name(name)) or []
        if candidates:
            return str(candidates[0] or "").strip()
    return ""


def record_key(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("ids", "codici_fiscali", "partite_iva", "pec"):
        parts.extend(str(item).strip().lower() for item in record.get(field, []) if str(item).strip())
    if not parts:
        parts.append(str(record.get("denominazione") or record.get("nome_completo") or "").strip().lower())
    return hashlib.sha256("|".join(sorted(set(parts))).encode("utf-8")).hexdigest()


def parse_record(node: ET.Element, *, page_start: int, response_sha256: str) -> dict[str, Any]:
    values = node_values(node)
    cf_fields = ("codicefiscale", "codfisc", "cf", "codicefiscalepg", "codicefiscalepf")
    primary_pec_fields = (
        "postaelettronicacertificata",
        "indirizzopec",
        "emailpec",
        "indirizzodigitale",
        "pec",
    )
    fallback_pec_fields = (
        "email",
        "mail",
    )
    id_fields = ("id", "idsoggetto", "idcard", "codice")
    piva_fields = ("partitaiva", "ivacode", "piva")

    direct_cf = unique(
        normalize_cf(value)
        for value in values.get("codfisc", [])
        if normalize_cf(value)
    )
    codici_fiscali = direct_cf or unique(
        normalize_cf(value)
        for key in cf_fields
        for value in values.get(key, [])
        if normalize_cf(value)
    )
    pec = unique(
        normalize_pec(value)
        for key in primary_pec_fields
        for value in values.get(key, [])
        if "@" in normalize_pec(value)
    )
    if not pec:
        pec = unique(
            normalize_pec(value)
            for key in fallback_pec_fields
            for value in values.get(key, [])
            if "@" in normalize_pec(value)
        )
    ids = unique(str(value).strip() for key in id_fields for value in values.get(key, []) if str(value).strip())
    partite_iva = unique(
        normalize_cf(value)
        for key in piva_fields
        for value in values.get(key, [])
        if normalize_cf(value)
    )

    nome = first(values, "nome")
    cognome = first(values, "cognome")
    nome_completo = " ".join(part for part in (nome, cognome) if part).strip()
    denominazione = first(values, "nomeCompagnia", "denominazione", "ragioneSociale", "descrizione")
    visibile_raw = (first(values, "visibile", "visible") or "true").strip().lower()

    record = {
        "record_key": "",
        "source": "reginde",
        "page_start": page_start,
        "response_sha256": response_sha256,
        "ids": ids,
        "codici_fiscali": codici_fiscali,
        "partite_iva": partite_iva,
        "pec": pec,
        "nome": nome,
        "cognome": cognome,
        "nome_completo": nome_completo,
        "denominazione": denominazione or nome_completo,
        "ruolo": first(values, "ruolo", "tipoSoggetto", "qualifica", "tipologia"),
        "stato": first(values, "status", "stato"),
        "visibile": visibile_raw not in {"0", "false", "no"},
        "values": values,
    }
    record["record_key"] = record_key(record)
    return record


def parse_page(xml_bytes: bytes, *, page_start: int) -> tuple[list[dict[str, Any]], str]:
    response_sha256 = hashlib.sha256(xml_bytes).hexdigest()
    root = ET.fromstring(xml_bytes)
    fault = ""
    for node in root.iter():
        if local_name(node.tag).lower() == "faultstring":
            fault = (node.text or "").strip()
            break
    if fault:
        raise RuntimeError(f"SOAP Fault ReGIndE: {fault}")
    returns = [node for node in root.iter() if local_name(node.tag).lower() == "return"]
    records = [parse_record(node, page_start=page_start, response_sha256=response_sha256) for node in returns]
    return records, response_sha256


def search_text_for_record(record: dict[str, Any]) -> str:
    values = [
        record.get("denominazione", ""),
        record.get("nome_completo", ""),
        record.get("ruolo", ""),
        record.get("stato", ""),
        " ".join(record.get("codici_fiscali") or []),
        " ".join(record.get("partite_iva") or []),
        " ".join(record.get("pec") or []),
    ]
    return " ".join(str(item or "").strip() for item in values if str(item or "").strip())


def soap_body_for_page(start: int, count: int) -> str:
    ET.register_namespace("soapenv", SOAP_NS)
    ET.register_namespace("int", REGINDE_NS)
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    ET.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    operation = ET.SubElement(body, f"{{{REGINDE_NS}}}elencoPaginatoSoggetti")
    ET.SubElement(operation, "da").text = str(start)
    ET.SubElement(operation, "count").text = str(count)
    return ET.tostring(envelope, encoding="unicode", xml_declaration=True)


def import_local_signer(repo_root: Path) -> Any:
    module_path = repo_root / "tools" / "local_signer.py"
    spec = importlib.util.spec_from_file_location("iusentra_local_signer_for_reginde_sync", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Local Signer non importabile da {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class PageResult:
    start: int
    count_requested: int
    status_code: int
    elapsed_ms: int
    records: list[dict[str, Any]]
    response_sha256: str
    body_bytes: int
    error: str = ""


class RegindeClient:
    def __init__(self, repo_root: Path, *, cert_thumbprint: str, prefer_cf: str, pin: str) -> None:
        self.module = import_local_signer(repo_root)
        self.cert_thumbprint = cert_thumbprint
        self.prefer_cf = prefer_cf
        self.pin = pin
        self.certificate = self.module._reginde_cert_thumbprint(cert_thumbprint, prefer_cf)

    def fetch_pages(self, starts: list[int], *, page_size: int, max_time: int) -> list[PageResult]:
        requests = [
            {
                "url": self.module._REGINDE_INTERROGAZIONE_URL,
                "soap_body": soap_body_for_page(start, page_size),
                "soap_action": self.module._REGINDE_INTERROGAZIONE_NS,
                "max_time": max_time,
                "connect_timeout": 12,
            }
            for start in starts
        ]
        t0 = time.perf_counter()
        responses = self.module._reginde_windows_native_batch(
            requests,
            cert_thumbprint=self.certificate,
            pin=self.pin,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        per_page_elapsed = round(elapsed_ms / max(1, len(starts)))
        results: list[PageResult] = []
        for start, response in zip(starts, responses):
            body_bytes = response.get("body_bytes") or b""
            error = str(response.get("error") or "").strip()
            status_code = int(response.get("status_code") or 0)
            if error:
                results.append(
                    PageResult(
                        start=start,
                        count_requested=page_size,
                        status_code=status_code,
                        elapsed_ms=per_page_elapsed,
                        records=[],
                        response_sha256="",
                        body_bytes=len(body_bytes),
                        error=error,
                    )
                )
                continue
            records, response_sha256 = parse_page(body_bytes, page_start=start)
            results.append(
                PageResult(
                    start=start,
                    count_requested=page_size,
                    status_code=status_code,
                    elapsed_ms=per_page_elapsed,
                    records=records,
                    response_sha256=response_sha256,
                    body_bytes=len(body_bytes),
                )
            )
        return results


class CacheWriter:
    def __init__(
        self,
        output_dir: Path,
        *,
        source: str = "reginde",
        operation: str = "elencoPaginatoSoggetti",
        db_filename: str = "reginde_cache.sqlite",
        page_prefix: str = "reginde-page",
    ) -> None:
        self.output_dir = output_dir
        self.pages_dir = output_dir / "pages"
        self.state_path = output_dir / "state.json"
        self.manifest_path = output_dir / "manifest.json"
        self.source = source
        self.operation = operation
        self.page_prefix = page_prefix
        self.db_path = output_dir / db_filename
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_key TEXT PRIMARY KEY,
                denominazione TEXT,
                nome_completo TEXT,
                codici_fiscali_json TEXT NOT NULL,
                partite_iva_json TEXT NOT NULL,
                pec_json TEXT NOT NULL,
                ruolo TEXT,
                stato TEXT,
                visibile INTEGER NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                first_page_start INTEGER NOT NULL,
                last_page_start INTEGER NOT NULL,
                response_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_reginde_denominazione ON records(denominazione)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_reginde_nome ON records(nome_completo)")
        self.fts_available = self._ensure_fts()
        self.conn.commit()
        if self.fts_available:
            self._rebuild_fts_if_empty()

    def _ensure_fts(self) -> bool:
        try:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS records_fts
                USING fts5(record_key UNINDEXED, search_text, tokenize='unicode61 remove_diacritics 2')
                """
            )
            return True
        except sqlite3.Error:
            return False

    def _rebuild_fts_if_empty(self) -> None:
        try:
            fts_count = int(self.conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()[0])
            record_count = int(self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])
        except sqlite3.Error:
            return
        if fts_count or not record_count:
            return
        rows = self.conn.execute("SELECT record_key, record_json FROM records").fetchall()
        for record_key, raw_payload in rows:
            try:
                payload = json.loads(raw_payload)
            except Exception:
                payload = {}
            self.conn.execute(
                "INSERT INTO records_fts(record_key, search_text) VALUES (?, ?)",
                (record_key, search_text_for_record(payload if isinstance(payload, dict) else {})),
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    def load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def save_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    def write_page(self, page: PageResult) -> Path:
        end = page.start + max(0, len(page.records)) - 1
        path = self.pages_dir / f"{self.page_prefix}-{page.start:09d}-{end:09d}.jsonl"
        tmp = path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for record in page.records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(path)
        meta = {
            "source": self.source,
            "operation": self.operation,
            "start": page.start,
            "count_requested": page.count_requested,
            "record_count": len(page.records),
            "status_code": page.status_code,
            "elapsed_ms": page.elapsed_ms,
            "response_sha256": page.response_sha256,
            "body_bytes": page.body_bytes,
            "written_at_europe_rome": now_rome(),
        }
        self.save_json_atomic(path.with_suffix(".meta.json"), meta)
        return path

    def upsert_records(self, records: list[dict[str, Any]], *, page_start: int, seen_at: str) -> int:
        count = 0
        for record in records:
            payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
            self.conn.execute(
                """
                INSERT INTO records (
                    record_key, denominazione, nome_completo, codici_fiscali_json,
                    partite_iva_json, pec_json, ruolo, stato, visibile, first_seen_at,
                    last_seen_at, first_page_start, last_page_start, response_sha256,
                    record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_key) DO UPDATE SET
                    denominazione=excluded.denominazione,
                    nome_completo=excluded.nome_completo,
                    codici_fiscali_json=excluded.codici_fiscali_json,
                    partite_iva_json=excluded.partite_iva_json,
                    pec_json=excluded.pec_json,
                    ruolo=excluded.ruolo,
                    stato=excluded.stato,
                    visibile=excluded.visibile,
                    last_seen_at=excluded.last_seen_at,
                    last_page_start=excluded.last_page_start,
                    response_sha256=excluded.response_sha256,
                    record_json=excluded.record_json
                """,
                (
                    record["record_key"],
                    record.get("denominazione", ""),
                    record.get("nome_completo", ""),
                    json.dumps(record.get("codici_fiscali", []), ensure_ascii=False),
                    json.dumps(record.get("partite_iva", []), ensure_ascii=False),
                    json.dumps(record.get("pec", []), ensure_ascii=False),
                    record.get("ruolo", ""),
                    record.get("stato", ""),
                    1 if record.get("visibile") else 0,
                    seen_at,
                    seen_at,
                    page_start,
                    page_start,
                    record.get("response_sha256", ""),
                    payload,
                ),
            )
            if self.fts_available:
                self.conn.execute("DELETE FROM records_fts WHERE record_key = ?", (record["record_key"],))
                self.conn.execute(
                    "INSERT INTO records_fts(record_key, search_text) VALUES (?, ?)",
                    (record["record_key"], search_text_for_record(record)),
                )
            count += 1
        self.conn.commit()
        return count

    def stats(self) -> dict[str, Any]:
        row = self.conn.execute("SELECT COUNT(*) FROM records").fetchone()
        pages = sorted(self.pages_dir.glob("reginde-page-*.jsonl"))
        return {
            "db_path": str(self.db_path),
            "records_distinct": int(row[0] if row else 0),
            "page_files": len(pages),
            "bytes_pages": sum(path.stat().st_size for path in pages),
        }

    def save_state(self, state: dict[str, Any]) -> None:
        state["updated_at_europe_rome"] = now_rome()
        state["stats"] = self.stats()
        self.save_json_atomic(self.state_path, state)
        self.save_json_atomic(self.manifest_path, state)


def read_pin(args: argparse.Namespace) -> str:
    if args.status:
        return ""
    if args.pin_stdin:
        return sys.stdin.readline().strip()
    if args.pin_env:
        return os.getenv(args.pin_env, "").strip()
    env_pin = os.getenv("IUSENTRA_REGINDE_PIN", "").strip()
    if env_pin:
        return env_pin
    return getpass.getpass("PIN certificato ReGIndE: ").strip()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("deve essere maggiore di zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sincronizza ReGIndE in cache locale con paginazione certificata.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Cartella cache locale ignorata da Git.")
    parser.add_argument("--page-size", type=positive_int, default=50)
    parser.add_argument("--pages-per-batch", type=positive_int, default=3)
    parser.add_argument("--start", type=positive_int, help="Indice ReGIndE iniziale; se assente riprende dallo stato.")
    parser.add_argument("--max-pages", type=positive_int, help="Numero massimo di pagine per questa tranche.")
    parser.add_argument("--max-records", type=positive_int, help="Numero massimo di record per questa tranche.")
    parser.add_argument("--max-minutes", type=float, help="Durata massima della tranche.")
    parser.add_argument("--full", action="store_true", help="Continua fino alla prima pagina vuota.")
    parser.add_argument("--reset", action="store_true", help="Ignora il checkpoint e riparte da --start o 1.")
    parser.add_argument("--status", action="store_true", help="Mostra lo stato locale senza contattare ReGIndE.")
    parser.add_argument("--delay", type=float, default=1.5, help="Pausa in secondi tra batch.")
    parser.add_argument("--request-timeout", type=positive_int, default=120)
    parser.add_argument("--cert-thumbprint", default="", help="Thumbprint certificato Windows; vuoto = scelta automatica.")
    parser.add_argument("--prefer-cf", default=os.getenv("IUSENTRA_REGINDE_CERT_CF", DEFAULT_PREFER_CF))
    parser.add_argument("--pin-env", default="", help="Nome variabile ambiente da cui leggere il PIN.")
    parser.add_argument("--pin-stdin", action="store_true", help="Legge il PIN dalla prima riga di stdin.")
    return parser


def ensure_bounded(args: argparse.Namespace) -> None:
    if args.status:
        return
    if args.full or args.max_pages or args.max_records or args.max_minutes:
        return
    raise SystemExit("Indica --full oppure un limite (--max-pages, --max-records o --max-minutes).")


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    cache = CacheWriter(output_dir)
    try:
        if args.status:
            state = cache.load_state()
            state.setdefault("stats", cache.stats())
            return state

        ensure_bounded(args)
        pin = read_pin(args)
        if not pin:
            raise SystemExit("PIN mancante: usa --pin-stdin, --pin-env o IUSENTRA_REGINDE_PIN.")

        previous = {} if args.reset else cache.load_state()
        next_start = int(args.start or previous.get("next_start") or 1)
        state = {
            "source": "reginde",
            "operation": "elencoPaginatoSoggetti",
            "output_dir": str(output_dir),
            "page_size": args.page_size,
            "pages_per_batch": args.pages_per_batch,
            "started_at_europe_rome": previous.get("started_at_europe_rome") or now_rome(),
            "last_run_started_at_europe_rome": now_rome(),
            "next_start": next_start,
            "pages_ok": int(previous.get("pages_ok") or 0),
            "records_seen_total": int(previous.get("records_seen_total") or 0),
            "last_error": "",
            "complete": bool(previous.get("complete") or False),
            "privacy": "Cache locale: non committare pagine JSONL, SQLite o manifest contenenti dati ReGIndE.",
        }
        if state["complete"] and not args.reset:
            return state

        client = RegindeClient(
            repo_root,
            cert_thumbprint=args.cert_thumbprint,
            prefer_cf=args.prefer_cf,
            pin=pin,
        )
        pin = ""
        run_started = time.monotonic()
        pages_done = 0
        records_done = 0
        stop = False
        while not stop:
            if args.max_pages and pages_done >= args.max_pages:
                break
            if args.max_records and records_done >= args.max_records:
                break
            if args.max_minutes and (time.monotonic() - run_started) >= args.max_minutes * 60:
                break

            remaining_pages = args.pages_per_batch
            if args.max_pages:
                remaining_pages = min(remaining_pages, args.max_pages - pages_done)
            starts = [next_start + offset * args.page_size for offset in range(remaining_pages)]
            pages = client.fetch_pages(starts, page_size=args.page_size, max_time=args.request_timeout)
            for page in pages:
                if page.error:
                    state["last_error"] = page.error
                    stop = True
                    break
                seen_at = now_rome()
                if not page.records:
                    state["complete"] = True
                    state["next_start"] = page.start
                    stop = True
                    break
                cache.write_page(page)
                inserted = cache.upsert_records(page.records, page_start=page.start, seen_at=seen_at)
                pages_done += 1
                records_done += inserted
                state["pages_ok"] += 1
                state["records_seen_total"] += len(page.records)
                next_start = page.start + args.page_size
                state["next_start"] = next_start
                state["last_page"] = {
                    "start": page.start,
                    "record_count": len(page.records),
                    "status_code": page.status_code,
                    "elapsed_ms": page.elapsed_ms,
                    "response_sha256": page.response_sha256,
                    "body_bytes": page.body_bytes,
                    "written_at_europe_rome": seen_at,
                }
                cache.save_state(state)
                print(
                    json.dumps(
                        {
                            "page_start": page.start,
                            "records": len(page.records),
                            "next_start": next_start,
                            "distinct": cache.stats()["records_distinct"],
                            "elapsed_ms": page.elapsed_ms,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if args.max_records and records_done >= args.max_records:
                    stop = True
                    break
                if args.max_pages and pages_done >= args.max_pages:
                    stop = True
                    break
                if args.max_minutes and (time.monotonic() - run_started) >= args.max_minutes * 60:
                    stop = True
                    break
            if stop:
                break
            if args.delay > 0:
                time.sleep(args.delay)
            if not args.full and not (args.max_pages or args.max_records or args.max_minutes):
                break

        state["last_run_finished_at_europe_rome"] = now_rome()
        state["last_run_pages"] = pages_done
        state["last_run_records"] = records_done
        cache.save_state(state)
        return state
    finally:
        cache.close()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
