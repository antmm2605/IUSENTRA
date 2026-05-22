from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.termini_processuali import DeadlinePracticeRepository

DEFAULT_DB = ROOT / "data" / "scadenziario" / "termini_processuali.json"
DEFAULT_REPORT = ROOT / "artifacts" / "guida-pratica" / "termini-processuali-import-report.json"
DEFAULT_CSV = ROOT / "artifacts" / "guida-pratica" / "termini-processuali-kb-audit.csv"

PHASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("impugnazione", re.compile(r"impugn|appello|cassazione|reclamo|opposizione", re.I)),
    ("notifica", re.compile(r"notific|ricezione|comunicazione|pec", re.I)),
    ("deposito", re.compile(r"deposit|iscrizione|ricorso|memoria", re.I)),
    ("costituzione", re.compile(r"costituz|comparire|comparizione", re.I)),
    ("udienza", re.compile(r"udienza|rinvio", re.I)),
    ("prescrizione_decadenza", re.compile(r"prescr|decadenz|imprescritt", re.I)),
    ("presupposto_temporale", re.compile(r"presupposto|decorso|separazione|durata", re.I)),
    ("adempimento_amministrativo", re.compile(r"annotazione|comune|registro|amministr", re.I)),
    ("procedimentale", re.compile(r"durata|massima|procediment|mediazione|atp", re.I)),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _stable_code(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12].upper()


def _default_sources() -> list[Path]:
    module_dir = ROOT / "pct" / "data" / "legal_knowledge_base_modules"
    sources = [
        ROOT / "pct" / "data" / "legal_knowledge_base.full.json",
        ROOT / "pct" / "data" / "legal_knowledge_base.json",
    ]
    if module_dir.exists():
        sources.extend(sorted(module_dir.glob("*.json")))
    return [path for path in sources if path.exists()]


def _iter_json_sources(paths: Iterable[Path]) -> Iterable[tuple[Path, Any]]:
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue


def infer_phase(term: Mapping[str, Any]) -> str:
    haystack = " ".join(_text(term.get(key)) for key in ("termine", "decorrenza", "natura", "norma", "tipo"))
    for phase, pattern in PHASE_PATTERNS:
        if pattern.search(haystack):
            return phase
    return "generico_da_classificare"


def infer_matter_type(container: Mapping[str, Any]) -> str:
    haystack = " ".join(
        _text(container.get(key))
        for key in ("categoria", "sottocategoria", "rito", "denominazione", "titolo")
    ).lower()
    if any(word in haystack for word in ("lavoro", "previdenza", "licenziamento")):
        return "labor"
    if any(word in haystack for word in ("tribut", "fisc")):
        return "tax"
    if any(word in haystack for word in ("amministrativ", "tar", "consiglio di stato")):
        return "admin"
    if any(word in haystack for word in ("penal", "reat")):
        return "penal"
    return "civil"


def classify(term: Mapping[str, Any]) -> tuple[str, bool, str]:
    label = _text(term.get("termine") or term.get("tipo") or term.get("label"))
    natura = _text(term.get("natura"))
    decorrenza = _text(term.get("decorrenza") or term.get("trigger"))
    norma = _text(term.get("norma"))
    haystack = " ".join([label, natura, decorrenza, norma]).lower()
    has_numeric_unit = any(_int(term.get(key)) is not None for key in ("giorni", "giorno", "mesi", "mese", "anni", "anno"))
    if term.get("manual_review") is True or (term.get("richiede_verifica_avvocato") is True and not has_numeric_unit):
        return "manual_review", False, "Richiede verifica professionale prima di calcolo automatico."
    if "imprescrittibile" in haystack:
        return "informativo_non_calcolabile", False, "Termine imprescrittibile o senza scadenza calcolabile."
    if "da verificare" in haystack or "secondo rito" in haystack:
        return "manual_review", False, "Richiede verifica professionale prima di calcolo automatico."
    if _int(term.get("giorni") or term.get("giorno")) is not None:
        return "calcolabile_giorni", True, "Importabile come template giorni se evento generatore e' valorizzato."
    if _int(term.get("mesi") or term.get("mese")) is not None:
        return "calcolabile_mesi", True, "Importabile come template mesi se evento generatore e' valorizzato."
    if _int(term.get("anni") or term.get("anno")) is not None:
        if any(word in haystack for word in ("prescr", "patto", "sospensione", "riduzione")):
            return "termine_lungo_o_prescrizione", False, "Da registrare come regola/profilo, non come calcolo processuale ordinario."
        return "calcolabile_anni_da_verificare", False, "Anni da convertire in mesi solo dopo verifica professionale."
    return "informativo_non_calcolabile", False, "Manca unita' numerica o decorrenza calcolabile."


def infer_direction(term: Mapping[str, Any]) -> str:
    label = _text(term.get("termine") or term.get("tipo") or term.get("label")).lower()
    decorrenza = _text(term.get("decorrenza") or term.get("trigger")).lower()
    if "prima udienza" in decorrenza and any(word in label for word in ("costituzione", "memoria", "difensiva")):
        return "backward"
    if "prima udienza" in label and any(word in label for word in ("prima", "ante")):
        return "backward"
    return "forward"


def _walk_terms(obj: Any, source: Path, container: Mapping[str, Any] | None = None) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        current = dict(container or {})
        if any(key in obj for key in ("codice", "code", "id", "denominazione", "titolo", "rito", "categoria", "sottocategoria")):
            current.update(obj)
        terms = obj.get("termini_processuali")
        if isinstance(terms, list):
            code = _text(obj.get("codice") or obj.get("code") or obj.get("id") or current.get("codice") or current.get("code") or current.get("id"))
            title = _text(obj.get("denominazione") or obj.get("titolo") or obj.get("title") or current.get("denominazione") or current.get("titolo") or current.get("title"))
            for index, raw_term in enumerate(terms, 1):
                term = raw_term if isinstance(raw_term, dict) else {"termine": str(raw_term)}
                classification, calculable, note = classify(term)
                row = {
                    "source": str(source.relative_to(ROOT) if source.is_relative_to(ROOT) else source),
                    "codice": code,
                    "denominazione": title,
                    "categoria": _text(obj.get("categoria") or current.get("categoria")),
                    "sottocategoria": _text(obj.get("sottocategoria") or current.get("sottocategoria")),
                    "rito": _text(obj.get("rito") or current.get("rito")),
                    "fase_processuale": infer_phase(term),
                    "termine": _text(term.get("termine") or term.get("tipo") or term.get("label")),
                    "giorni": _text(term.get("giorni")),
                    "mesi": _text(term.get("mesi")),
                    "anni": _text(term.get("anni")),
                    "decorrenza": _text(term.get("decorrenza") or term.get("trigger")),
                    "natura": _text(term.get("natura")),
                    "norma": _text(term.get("norma")),
                    "criticita": _text(term.get("criticita")),
                    "classificazione_import": classification,
                    "calcolabile_automaticamente": calculable,
                    "nota_import": note,
                    "matter_type": infer_matter_type(current),
                    "direction": infer_direction(term),
                    "ordinal": index,
                }
                row["term_rule_code"] = "GP_TERM_" + _stable_code(row["codice"], row["termine"], row["decorrenza"], row["norma"])
                yield row
        for value in obj.values():
            yield from _walk_terms(value, source, current)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_terms(value, source, container)


def collect_terms(sources: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for source, payload in _iter_json_sources(sources):
        for row in _walk_terms(payload, source):
            key = (row["codice"], row["termine"].lower(), row["decorrenza"].lower(), row["norma"].lower())
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def _template_from_term(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not row.get("calcolabile_automaticamente"):
        return None
    period_type = "days"
    base_value = _int(row.get("giorni"))
    if base_value is None:
        base_value = _int(row.get("mesi"))
        period_type = "months"
    if base_value is None:
        return None
    return {
        "code": "GP_" + _stable_code(_text(row.get("codice")), _text(row.get("termine")), _text(row.get("decorrenza")), _text(row.get("norma"))),
        "name": _text(row.get("termine"))[:180] or "Termine Guida Pratica",
        "matter_type": _text(row.get("matter_type")) or "civil",
        "base_value": int(base_value),
        "period_type": period_type,
        "direction": _text(row.get("direction")) or "forward",
        "suspend_august": True,
        "ferial_suspension_policy": "manual_review" if row.get("classificazione_import") == "manual_review" else "applies",
        "free_term": bool(row.get("direction") == "backward"),
        "urgent": "urgente" in _text(row.get("termine")).lower(),
        "extend_saturday": True,
        "extend_holiday": True,
        "reference_law": _text(row.get("norma")),
        "cartabia_compliant": True,
        "metadata": {
            "source": "guida_pratica",
            "source_file": _text(row.get("source")),
            "codice_guida": _text(row.get("codice")),
            "denominazione_guida": _text(row.get("denominazione")),
            "fase_processuale": _text(row.get("fase_processuale")),
            "decorrenza": _text(row.get("decorrenza")),
            "natura": _text(row.get("natura")),
            "criticita": _text(row.get("criticita")),
            "requires_professional_review": True,
        },
        "version": 1,
    }


def import_terms(rows: list[dict[str, Any]], db_path: Path) -> dict[str, Any]:
    repo = DeadlinePracticeRepository.json(db_path)
    payload = repo._read_json()
    payload["guida_pratica_terms"] = rows
    templates = {str(item.get("code")): dict(item) for item in payload.get("templates", []) if isinstance(item, dict)}
    imported_templates = 0
    for row in rows:
        template = _template_from_term(row)
        if not template:
            continue
        templates[template["code"]] = template
        imported_templates += 1
    payload["templates"] = sorted(templates.values(), key=lambda item: (str(item.get("matter_type")), str(item.get("name"))))
    payload["guida_pratica_terms_import"] = {
        "imported_at": _utc_now(),
        "records": len(rows),
        "templates_upserted": imported_templates,
        "by_phase": dict(Counter(str(row.get("fase_processuale")) for row in rows).most_common()),
        "by_classification": dict(Counter(str(row.get("classificazione_import")) for row in rows).most_common()),
    }
    repo._write_json(payload)
    return dict(payload["guida_pratica_terms_import"])


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "source",
        "codice",
        "denominazione",
        "categoria",
        "sottocategoria",
        "rito",
        "fase_processuale",
        "termine",
        "giorni",
        "mesi",
        "anni",
        "decorrenza",
        "natura",
        "norma",
        "criticita",
        "classificazione_import",
        "calcolabile_automaticamente",
        "direction",
        "matter_type",
        "term_rule_code",
        "nota_import",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa i termini processuali della Guida Pratica nel repository termini.")
    parser.add_argument("--source", action="append", default=[], help="File JSON sorgente. Ripetibile. Se omesso usa la KB locale.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Repository JSON termini processuali.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Report JSON di import.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="CSV audit termini.")
    parser.add_argument("--dry-run", action="store_true", help="Produce solo report e CSV, senza aggiornare il repository termini.")
    args = parser.parse_args()

    sources = [Path(item) for item in args.source] if args.source else _default_sources()
    rows = collect_terms(sources)
    write_csv(rows, Path(args.csv))
    import_summary = None if args.dry_run else import_terms(rows, Path(args.db))
    report = {
        "generated_at": _utc_now(),
        "dry_run": bool(args.dry_run),
        "sources": [str(path) for path in sources],
        "records": len(rows),
        "by_phase": dict(Counter(str(row.get("fase_processuale")) for row in rows).most_common()),
        "by_classification": dict(Counter(str(row.get("classificazione_import")) for row in rows).most_common()),
        "calculable_templates": sum(1 for row in rows if row.get("calcolabile_automaticamente")),
        "csv": str(Path(args.csv)),
        "db": str(Path(args.db)),
        "import": import_summary,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
