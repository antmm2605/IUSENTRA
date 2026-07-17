from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_document_catalog import document_ai_texts_for_catalog
from pct.pec_pipeline import _date_from_iso_or_it, _procedural_date_kind, extract_procedural_dates
from pct.scadenziario import GestioneScadenziario
from pct.storage import StudioDB
from pct.tenant import GestioneTenant


_CLOSED_STATUSES = {"ARCHIVIATO", "DEFINITO"}


def _text(value: Any, default: str = "") -> str:
    rendered = str(value if value is not None else "").strip()
    return rendered or default


def _enum_upper(value: Any) -> str:
    return _text(getattr(value, "value", value)).upper()


def _studio_db_path(paths: dict[str, Any]) -> Path:
    fascicoli_path = Path(_text(paths.get("FASCICOLI_DB"))).resolve()
    return fascicoli_path.parent.parent / "studio.db"


def _future_day(value: Any, *, today: date) -> str:
    parsed = _date_from_iso_or_it(_text(value)[:10])
    return parsed.isoformat() if parsed is not None and parsed >= today else ""


def _rg(fascicolo: Any) -> str:
    complete = _text(getattr(fascicolo, "rg_completo", ""))
    if complete:
        return complete
    number = _text(getattr(fascicolo, "numero_rg", ""))
    year = _text(getattr(fascicolo, "anno_rg", ""))
    return f"RG {number}/{year}" if number and year else "n.d."


def _document_future_dates(
    *,
    slug: str,
    paths: dict[str, Any],
    studio_db: StudioDB,
    fascicolo: Any,
    today: date,
) -> tuple[list[dict[str, Any]], int]:
    documents = list(getattr(fascicolo, "documenti", []) or [])
    if not documents:
        return [], 0
    storage_root = _text(paths.get("DOCUMENTI_AI_DIR")) or str(
        Path(_text(paths.get("FASCICOLI_DOCS"))).parent / "documenti_ai"
    )
    texts = document_ai_texts_for_catalog(
        tenant_ids=[slug, "default", "single-studio"],
        fascicolo_id=_text(getattr(fascicolo, "id", "")),
        documents=documents,
        fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
        structured_db=studio_db,
        storage_root=storage_root,
    )
    metadata = {
        _text(getattr(document, "id", "")): _text(getattr(document, "nome", ""), "Documento fascicolo")
        for document in documents
    }
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for document_id, text in texts.items():
        filename = metadata.get(_text(document_id), _text(document_id, "Documento fascicolo"))
        for item in extract_procedural_dates({filename: _text(text)}):
            kind = _procedural_date_kind(item)
            parsed = _date_from_iso_or_it(_text(item.get("date")))
            if kind not in {"udienza", "termine"} or parsed is None or parsed < today:
                continue
            key = (parsed.isoformat(), kind, _text(document_id))
            candidates[key] = {
                "date": parsed.isoformat(),
                "kind": kind,
                "document_id": _text(document_id),
                "document": filename,
                "label": _text(item.get("label"), "Data processuale"),
            }
    return sorted(candidates.values(), key=lambda row: (row["date"], row["kind"], row["document"])), len(texts)


def _structured_future_dates(value: Any, *, today: date, path: str = "source_snapshot") -> list[dict[str, str]]:
    found: dict[tuple[str, str], dict[str, str]] = {}

    def visit(current: Any, current_path: str) -> None:
        if isinstance(current, dict):
            for key, nested in current.items():
                visit(nested, f"{current_path}.{_text(key)}")
            return
        if isinstance(current, (list, tuple)):
            for index, nested in enumerate(current):
                visit(nested, f"{current_path}[{index}]")
            return
        raw = _text(current)
        if not raw:
            return
        for match in re.findall(r"\b(?:20\d{2}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]20\d{2})\b", raw):
            parsed = _date_from_iso_or_it(match)
            if parsed is None or parsed < today:
                continue
            found[(parsed.isoformat(), current_path)] = {
                "date": parsed.isoformat(),
                "path": current_path,
                "value": raw[:240],
            }

    visit(value, path)
    return sorted(found.values(), key=lambda row: (row["date"], row["path"]))


def audit_tenant(*, slug: str, paths: dict[str, Any], inspect_documents: bool) -> dict[str, Any]:
    studio_db_path = _studio_db_path(paths)
    if not studio_db_path.exists():
        return {
            "ok": False,
            "tenant": slug,
            "source_of_truth": "missing",
            "failures": [{"code": "studio_db_mancante", "path": str(studio_db_path)}],
        }
    studio_db = StudioDB.get(str(studio_db_path))
    fascicoli = GestioneFascicoli(
        _text(paths.get("FASCICOLI_DB")),
        documents_dir=_text(paths.get("FASCICOLI_DOCS")),
        archive_dir=_text(paths.get("FASCICOLI_ARCH")),
        studio_db=studio_db,
    ).tutti(archiviati=False)
    scadenze = GestioneScadenziario(
        _text(paths.get("SCADENZIARIO_DB")),
        studio_db=studio_db,
    ).tutte(solo_aperte=True)
    today = date.today()
    deadlines_by_fascicolo: dict[str, list[str]] = defaultdict(list)
    for item in scadenze:
        target = _future_day(
            getattr(item, "data_scadenza", "") or getattr(item, "data", ""),
            today=today,
        )
        if target:
            deadlines_by_fascicolo[_text(getattr(item, "id_fascicolo", ""))].append(target)

    covered = 0
    missing: list[dict[str, Any]] = []
    for fascicolo in fascicoli:
        status = _enum_upper(getattr(fascicolo, "stato", ""))
        if status in _CLOSED_STATUSES:
            continue
        fid = _text(getattr(fascicolo, "id", ""))
        future_dates = set(deadlines_by_fascicolo.get(fid, []))
        persisted = _future_day(getattr(fascicolo, "data_prossima_udienza", ""), today=today)
        if persisted:
            future_dates.add(persisted)
        direct = getattr(fascicolo, "prossima_scadenza", None)
        direct_date = _future_day(
            getattr(direct, "data_scadenza", "") or getattr(direct, "data", "") if direct else "",
            today=today,
        )
        if direct_date:
            future_dates.add(direct_date)
        if future_dates:
            covered += 1
            continue
        document_candidates: list[dict[str, Any]] = []
        indexed_documents = 0
        structured_candidates = _structured_future_dates(
            getattr(fascicolo, "source_snapshot", {}) or {},
            today=today,
        )
        if inspect_documents:
            document_candidates, indexed_documents = _document_future_dates(
                slug=slug,
                paths=paths,
                studio_db=studio_db,
                fascicolo=fascicolo,
                today=today,
            )
        missing.append(
            {
                "id": fid,
                "rg": _rg(fascicolo),
                "numero": _text(getattr(fascicolo, "numero", "")),
                "titolo": _text(getattr(fascicolo, "titolo", "")),
                "cliente": _text(getattr(fascicolo, "cliente_principale", "")),
                "stato": status,
                "documenti": len(getattr(fascicolo, "documenti", []) or []),
                "documenti_indicizzati": indexed_documents,
                "date_documentali_recuperabili": document_candidates,
                "date_strutturate_recuperabili": structured_candidates,
                "esito": (
                    "data_documentale_da_consolidare"
                    if document_candidates
                    else "data_strutturata_da_consolidare"
                    if structured_candidates
                    else "nessuna_data_futura_individuata"
                ),
            }
        )
    active = covered + len(missing)
    return {
        "ok": not missing,
        "tenant": slug,
        "source_of_truth": "sqlite",
        "today": today.isoformat(),
        "stats": {
            "fascicoli_attivi": active,
            "fascicoli_con_prossima_scadenza": covered,
            "fascicoli_senza_prossima_scadenza": len(missing),
            "copertura_percentuale": round((covered / active) * 100, 2) if active else 100.0,
        },
        "missing": missing,
    }


def run_audit(*, registry: Path, tenant: str, inspect_documents: bool) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if not tenant or studio.slug.casefold() == tenant.casefold()]
    reports = [
        audit_tenant(
            slug=studio.slug,
            paths=manager.percorsi_dati(studio.slug, reconcile_aliases=False, ensure_baseline=False),
            inspect_documents=inspect_documents,
        )
        for studio in studios
    ]
    if tenant and not studios:
        return {"ok": False, "source_of_truth": "missing", "errors": [f"Studio non trovato: {tenant}"]}
    return {
        "ok": bool(reports) and all(report.get("ok") for report in reports),
        "registry": str(registry),
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "tenants": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit read-only della copertura delle prossime scadenze dei fascicoli.")
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", default="")
    parser.add_argument("--inspect-documents", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = run_audit(
        registry=Path(args.registry),
        tenant=_text(args.tenant),
        inspect_documents=bool(args.inspect_documents),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
