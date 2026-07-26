#!/usr/bin/env python
"""Populate the local Registro PP.AA. SQL cache from certified PST data.

The operational cache is SQLite under ``data/local/registro_ppaa`` by default.
Imported JSON/JSONL/XML files are treated as runtime evidence or controlled
exports and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reginde_sync_cache import (
    DEFAULT_PREFER_CF,
    CacheWriter,
    PageResult,
    import_local_signer,
    normalize_cf,
    normalize_pec,
    now_rome,
    parse_page,
    record_key,
    unique,
)

DEFAULT_OUTPUT_DIR = Path("data/local/registro_ppaa")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _first_mapping_value(row: dict[str, Any], *names: str) -> Any:
    lower = {str(key).strip().lower().replace("-", "_"): value for key, value in row.items()}
    for name in names:
        key = name.strip().lower().replace("-", "_")
        value = lower.get(key)
        if value is not None and _text(value):
            return value
    return ""


def record_from_mapping(row: dict[str, Any], *, index: int, response_sha256: str) -> dict[str, Any]:
    pec = unique(
        normalize_pec(value)
        for value in (
            _list_values(_first_mapping_value(row, "pec", "indirizzo_pec", "indirizzoPec", "mail", "email"))
            + _list_values(_first_mapping_value(row, "pecs", "indirizzi_pec", "indirizziAbilitati"))
        )
        if "@" in normalize_pec(value)
    )
    codici_fiscali = unique(
        normalize_cf(value)
        for value in _list_values(_first_mapping_value(row, "codice_fiscale", "codiceFiscale", "cf"))
        if normalize_cf(value)
    )
    partite_iva = unique(
        normalize_cf(value)
        for value in _list_values(_first_mapping_value(row, "partita_iva", "partitaIVA", "piva"))
        if normalize_cf(value)
    )
    ids = unique(
        _text(value)
        for value in _list_values(_first_mapping_value(row, "id", "codice", "codice_ente", "codiceEnte"))
        if _text(value)
    )
    denominazione = _text(
        _first_mapping_value(row, "denominazione", "descrizione", "nome", "ragione_sociale", "ragioneSociale")
    )
    values = {
        "denominazione": [denominazione] if denominazione else [],
        "codicefiscale": codici_fiscali,
        "partitaiva": partite_iva,
        "pec": pec,
    }
    record = {
        "record_key": "",
        "source": "registro_ppaa",
        "page_start": index,
        "response_sha256": response_sha256,
        "ids": ids,
        "codici_fiscali": codici_fiscali,
        "partite_iva": partite_iva,
        "pec": pec,
        "nome": "",
        "cognome": "",
        "nome_completo": "",
        "denominazione": denominazione,
        "ruolo": _text(_first_mapping_value(row, "ruolo", "tipo", "tipologia")) or "PPAA",
        "stato": _text(_first_mapping_value(row, "stato", "status")) or "ATTIVO",
        "visibile": str(_first_mapping_value(row, "visibile", "visible") or "true").strip().lower() not in {"0", "false", "no"},
        "values": values,
    }
    record["record_key"] = record_key(record)
    return record


def records_from_json_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("records", "results", "enti", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def load_import_records(paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        suffix = path.suffix.lower()
        if suffix == ".xml":
            parsed, _ = parse_page(data, page_start=len(records) + 1)
            for record in parsed:
                record["source"] = "registro_ppaa"
            records.extend(parsed)
            continue
        if suffix == ".jsonl":
            for line in data.decode("utf-8-sig").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict) and {"record_key", "pec"}.issubset(payload):
                    payload = {**payload, "source": "registro_ppaa"}
                    records.append(payload)
                elif isinstance(payload, dict):
                    records.append(record_from_mapping(payload, index=len(records) + 1, response_sha256=digest))
            continue
        payload = json.loads(data.decode("utf-8-sig"))
        for row in records_from_json_payload(payload):
            if {"record_key", "pec"}.issubset(row):
                records.append({**row, "source": "registro_ppaa"})
            else:
                records.append(record_from_mapping(row, index=len(records) + 1, response_sha256=digest))
    return [record for record in records if record.get("pec")]


@dataclass
class RegistroPpaaClient:
    repo_root: Path
    cert_thumbprint: str
    prefer_cf: str
    pin: str

    def __post_init__(self) -> None:
        self.module = import_local_signer(self.repo_root)
        self.certificate = self.module._reginde_cert_thumbprint(self.cert_thumbprint, self.prefer_cf)

    def fetch_queries(self, queries: list[str], *, max_time: int) -> list[PageResult]:
        requests = [
            {
                "url": self.module._REGINDE_INTERROGAZIONE_ENTE_URL,
                "soap_body": self.module._reginde_soap_body_for_entity(query, "", ""),
                "soap_action": self.module._REGINDE_INTERROGAZIONE_NS,
                "max_time": max_time,
                "connect_timeout": 12,
            }
            for query in queries
        ]
        t0 = time.perf_counter()
        responses = self.module._reginde_windows_native_batch(
            requests,
            cert_thumbprint=self.certificate,
            pin=self.pin,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000 / max(1, len(queries)))
        results: list[PageResult] = []
        for index, (query, response) in enumerate(zip(queries, responses), start=1):
            body_bytes = response.get("body_bytes") or b""
            error = _text(response.get("error"))
            status_code = int(response.get("status_code") or 0)
            if error:
                results.append(PageResult(index, 1, status_code, elapsed_ms, [], "", len(body_bytes), error))
                continue
            records, response_sha256 = parse_page(body_bytes, page_start=index)
            for record in records:
                record["source"] = "registro_ppaa"
            results.append(PageResult(index, 1, status_code, elapsed_ms, records, response_sha256, len(body_bytes)))
        return results


def read_pin(args: argparse.Namespace) -> str:
    if args.status or not args.query:
        return ""
    if args.pin_stdin:
        return sys.stdin.readline().strip()
    if args.pin_env:
        return os.getenv(args.pin_env, "").strip()
    env_pin = os.getenv("IUSENTRA_REGISTRO_PPAA_PIN", "").strip()
    if env_pin:
        return env_pin
    import getpass

    return getpass.getpass("PIN certificato Registro PP.AA.: ").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alimenta la cache SQL locale del Registro PP.AA.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Cartella cache locale ignorata da Git.")
    parser.add_argument("--query", action="append", default=[], help="Denominazione ente da cercare via servizio PST certificato.")
    parser.add_argument("--import-file", action="append", default=[], help="File JSON, JSONL o XML da importare nella cache SQL locale.")
    parser.add_argument("--reset", action="store_true", help="Riparte da una cache vuota.")
    parser.add_argument("--status", action="store_true", help="Mostra lo stato locale senza contattare il PST.")
    parser.add_argument("--request-timeout", type=int, default=90)
    parser.add_argument("--cert-thumbprint", default="", help="Thumbprint certificato Windows; vuoto = scelta automatica.")
    parser.add_argument("--prefer-cf", default=os.getenv("IUSENTRA_REGISTRO_PPAA_CERT_CF", DEFAULT_PREFER_CF))
    parser.add_argument("--pin-env", default="", help="Nome variabile ambiente da cui leggere il PIN.")
    parser.add_argument("--pin-stdin", action="store_true", help="Legge il PIN dalla prima riga di stdin.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    if args.reset and output_dir.exists():
        import shutil

        shutil.rmtree(output_dir)
    cache = CacheWriter(
        output_dir,
        source="registro_ppaa",
        operation="ricercaEnteEx",
        db_filename="registro_ppaa_cache.sqlite",
        page_prefix="registro-ppaa-query",
    )
    try:
        if args.status:
            state = cache.load_state()
            state.setdefault("stats", cache.stats())
            return state

        imported_records = load_import_records(args.import_file)
        seen_at = now_rome()
        imported_count = cache.upsert_records(imported_records, page_start=0, seen_at=seen_at) if imported_records else 0

        query_pages: list[PageResult] = []
        query_records = 0
        if args.query:
            pin = read_pin(args)
            if not pin:
                raise SystemExit("PIN mancante: usa --pin-stdin, --pin-env o IUSENTRA_REGISTRO_PPAA_PIN.")
            client = RegistroPpaaClient(
                repo_root,
                cert_thumbprint=args.cert_thumbprint,
                prefer_cf=args.prefer_cf,
                pin=pin,
            )
            pin = ""
            query_pages = client.fetch_queries([_text(item) for item in args.query if _text(item)], max_time=args.request_timeout)
            for page in query_pages:
                if page.error:
                    print(json.dumps({"query_index": page.start, "error": page.error}, ensure_ascii=False), flush=True)
                    continue
                cache.write_page(page)
                query_records += cache.upsert_records(page.records, page_start=page.start, seen_at=now_rome())
                print(json.dumps({"query_index": page.start, "records": len(page.records)}, ensure_ascii=False), flush=True)

        state = {
            "source": "registro_ppaa",
            "operation": "ricercaEnteEx",
            "output_dir": str(output_dir),
            "updated_at_europe_rome": now_rome(),
            "complete": False,
            "records_seen_total": imported_count + query_records,
            "queries": len(args.query or []),
            "imports": len(args.import_file or []),
            "last_errors": [page.error for page in query_pages if page.error],
            "stats": cache.stats(),
            "privacy": "Cache locale: non committare SQLite, pagine o manifest contenenti dati Registro PP.AA.",
        }
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
