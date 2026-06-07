"""Audit della matrice pratica legale pubblicata in Ricerca Legale.

Il gate fallisce quando una materia dichiarata pronta non ha riferimenti
nominali, fonti ufficiali, atti da produrre, scadenze/task e domande Lex.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.legal_practice_research_matrix import (
    LEGAL_NOMINAL_REFERENCE_LIBRARY,
    LEGAL_PRACTICE_RESEARCH_MATRIX,
    LEGAL_PRACTICE_RESEARCH_MATRIX_VERSION,
    LEGAL_WEB_RESEARCH_VERIFIED_REFERENCES,
    PRODUCT_DESTINATIONS,
)


AUDIT_DATE = "2026-06-06"
DEFAULT_OUTPUT_DIR = Path("artifacts/legal-sources")

REQUIRED_CARD_FIELDS = (
    "id",
    "area",
    "title",
    "scope",
    "official_sources",
    "articles_and_codes",
    "decrees_and_rules",
    "case_law_and_hearings",
    "acts_to_prepare",
    "deadlines_tasks",
    "lex_questions",
    "research_queries",
)

REQUIRED_SOURCE_FIELDS = ("label", "authority", "source_code", "url")
REQUIRED_REFERENCE_FIELDS = (
    "id",
    "practice_ids",
    "label",
    "authority",
    "kind",
    "url",
    "articles",
    "use",
)
REQUIRED_WEB_RESEARCH_FIELDS = (
    "verified_on",
    "web_search_query",
    "practice_steps",
    "lex_questions",
)

OFFICIAL_URL_HINTS = (
    "normattiva.it",
    "gazzettaufficiale.it",
    "giustizia.it",
    "pst.giustizia.it",
    "giustizia-amministrativa.it",
    "openga.giustizia-amministrativa.it",
    "cortedicassazione.it",
    "cortecostituzionale.it",
    "curia.europa.eu",
    "eur-lex.europa.eu",
    "echr.coe.int",
    "hudoc.echr.coe.int",
    "agenziaentrate.gov.it",
    "giustiziatributaria.gov.it",
    "anticorruzione.it",
    "interno.gov.it",
    "mim.gov.it",
    "istruzione.it",
    "inpa.gov.it",
    "funzionepubblica.gov.it",
    "aranagenzia.it",
    "corteconti.it",
    "mase.gov.it",
    "mimit.gov.it",
    "registroimprese.it",
    "consob.it",
    "siae.it",
    "cultura.gov.it",
    "inps.it",
    "inail.it",
    "lavoro.gov.it",
    "bancaditalia.it",
    "arbitrobancariofinanziario.it",
    "agcm.it",
    "agcom.it",
    "garanteprivacy.it",
    "anac.it",
    "inipec.gov.it",
    "indicepa.gov.it",
    "domiciliodigitale.gov.it",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    if value:
        return [value]
    return []


def _has_text(value: Any) -> bool:
    return bool(_text(value))


def _official_url_score(url: str) -> int:
    lower = url.lower()
    return 1 if any(hint in lower for hint in OFFICIAL_URL_HINTS) else 0


def _missing_field_issues(prefix: str, row: Mapping[str, Any], fields: Iterable[str]) -> list[str]:
    issues: list[str] = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, (list, tuple)):
            if not any(_has_text(item) for item in value):
                issues.append(f"{prefix}: campo obbligatorio vuoto `{field}`")
        elif not _has_text(value):
            issues.append(f"{prefix}: campo obbligatorio vuoto `{field}`")
    return issues


def _audit_cards(reference_by_practice: Mapping[str, list[Mapping[str, Any]]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, card in enumerate(LEGAL_PRACTICE_RESEARCH_MATRIX, start=1):
        card_id = _text(card.get("id")) or f"card_{index}"
        prefix = f"scheda {card_id}"
        if card_id in seen_ids:
            issues.append(f"{prefix}: id duplicato")
        seen_ids.add(card_id)

        card_issues = _missing_field_issues(prefix, card, REQUIRED_CARD_FIELDS)
        official_sources = [source for source in _list(card.get("official_sources")) if isinstance(source, Mapping)]
        if not official_sources:
            card_issues.append(f"{prefix}: nessuna fonte ufficiale nominale collegata")
        for source_index, source in enumerate(official_sources, start=1):
            source_prefix = f"{prefix}, fonte {source_index}"
            card_issues.extend(_missing_field_issues(source_prefix, source, REQUIRED_SOURCE_FIELDS))
            url = _text(source.get("url"))
            if url and not _official_url_score(url):
                card_issues.append(f"{source_prefix}: URL non riconosciuto come fonte ufficiale `{url}`")

        references = reference_by_practice.get(card_id, [])
        if not references:
            card_issues.append(f"{prefix}: nessun riferimento nominale della libreria punta alla materia")

        rows.append(
            {
                "id": card_id,
                "area": _text(card.get("area")),
                "title": _text(card.get("title")),
                "official_sources": len(official_sources),
                "nominal_references": len(references),
                "articles_and_codes": len(_list(card.get("articles_and_codes"))),
                "decrees_and_rules": len(_list(card.get("decrees_and_rules"))),
                "case_law_and_hearings": len(_list(card.get("case_law_and_hearings"))),
                "acts_to_prepare": len(_list(card.get("acts_to_prepare"))),
                "deadlines_tasks": len(_list(card.get("deadlines_tasks"))),
                "lex_questions": len(_list(card.get("lex_questions"))),
                "research_queries": len(_list(card.get("research_queries"))),
                "covered": not card_issues,
                "issues": card_issues,
            }
        )
        issues.extend(card_issues)

    return rows, issues


def _audit_references(practice_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, reference in enumerate(LEGAL_NOMINAL_REFERENCE_LIBRARY, start=1):
        reference_id = _text(reference.get("id")) or f"reference_{index}"
        prefix = f"riferimento {reference_id}"
        reference_issues = _missing_field_issues(prefix, reference, REQUIRED_REFERENCE_FIELDS)
        if reference_id in seen_ids:
            reference_issues.append(f"{prefix}: id duplicato")
        seen_ids.add(reference_id)

        url = _text(reference.get("url"))
        if url and not _official_url_score(url):
            reference_issues.append(f"{prefix}: URL non riconosciuto come fonte ufficiale `{url}`")

        linked_practices = [_text(item) for item in _list(reference.get("practice_ids")) if _text(item)]
        unknown_practices = [item for item in linked_practices if item not in practice_ids]
        for practice_id in unknown_practices:
            reference_issues.append(f"{prefix}: pratica collegata inesistente `{practice_id}`")

        is_web_verified = bool(_text(reference.get("verified_on"))) or reference_id.startswith("web_")
        if is_web_verified:
            reference_issues.extend(_missing_field_issues(prefix, reference, REQUIRED_WEB_RESEARCH_FIELDS))

        rows.append(
            {
                "id": reference_id,
                "label": _text(reference.get("label")),
                "authority": _text(reference.get("authority")),
                "kind": _text(reference.get("kind")),
                "practice_ids": linked_practices,
                "url": url,
                "verified_on": _text(reference.get("verified_on")),
                "web_search_query": _text(reference.get("web_search_query")),
                "practice_steps": len(_list(reference.get("practice_steps"))),
                "lex_questions": len(_list(reference.get("lex_questions"))),
                "covered": not reference_issues,
                "issues": reference_issues,
            }
        )
        issues.extend(reference_issues)

    return rows, issues


def build_audit() -> dict[str, Any]:
    practice_ids = {_text(card.get("id")) for card in LEGAL_PRACTICE_RESEARCH_MATRIX if _text(card.get("id"))}
    reference_by_practice: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for reference in LEGAL_NOMINAL_REFERENCE_LIBRARY:
        if not isinstance(reference, Mapping):
            continue
        for practice_id in _list(reference.get("practice_ids")):
            practice_key = _text(practice_id)
            if practice_key:
                reference_by_practice[practice_key].append(reference)

    cards, card_issues = _audit_cards(reference_by_practice)
    references, reference_issues = _audit_references(practice_ids)
    issues = card_issues + reference_issues
    covered_cards = sum(1 for row in cards if row["covered"])
    covered_references = sum(1 for row in references if row["covered"])
    web_research_references = [row for row in references if _text(row.get("verified_on")) or row["id"].startswith("web_")]
    covered_web_research_references = sum(1 for row in web_research_references if row["covered"])
    total_units = len(cards) + len(references)
    covered_units = covered_cards + covered_references
    coverage_percent = round((covered_units / total_units) * 100, 2) if total_units else 0.0
    area_counter = Counter(row["area"] for row in cards if row["area"])
    authority_counter = Counter(row["authority"] for row in references if row["authority"])

    return {
        "audit_date": AUDIT_DATE,
        "matrix_version": LEGAL_PRACTICE_RESEARCH_MATRIX_VERSION,
        "product_destinations": list(PRODUCT_DESTINATIONS),
        "summary": {
            "cards": len(cards),
            "references": len(references),
            "covered_cards": covered_cards,
            "covered_references": covered_references,
            "web_research_verified_references": len(web_research_references),
            "web_research_registered_references": len(LEGAL_WEB_RESEARCH_VERIFIED_REFERENCES),
            "covered_web_research_verified_references": covered_web_research_references,
            "web_research_declared_status": "100%" if web_research_references and covered_web_research_references == len(web_research_references) else "non dichiarabile",
            "issues": len(issues),
            "coverage_percent": coverage_percent,
            "declared_coverage_status": "100%" if not issues else "non dichiarabile",
            "practice_areas": len(area_counter),
            "authorities": len(authority_counter),
        },
        "areas": dict(sorted(area_counter.items())),
        "authorities": dict(sorted(authority_counter.items())),
        "cards": cards,
        "references": references,
        "issues": issues,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Audit matrice pratica legale",
        "",
        f"Data audit: {payload['audit_date']}.",
        f"Versione matrice: {payload['matrix_version']}.",
        "",
        "## Esito",
        "",
        f"- Copertura dichiarabile: {summary['declared_coverage_status']}",
        f"- Schede materia: {summary['cards']}",
        f"- Riferimenti nominali: {summary['references']}",
        f"- Mancanze rilevate: {summary['issues']}",
        f"- Percentuale tecnica: {summary['coverage_percent']}%",
        "",
        "## Destinazioni prodotto",
        "",
    ]
    lines.extend(f"- {destination}" for destination in payload["product_destinations"])
    lines.extend(["", "## Materie coperte", ""])
    for card in payload["cards"]:
        status = "coperta" if card["covered"] else "da completare"
        lines.append(
            f"- `{card['id']}` - {card['title']} ({card['area']}): {status}; "
            f"fonti {card['official_sources']}, riferimenti {card['nominal_references']}, "
            f"norme {card['articles_and_codes']}, decreti/regole {card['decrees_and_rules']}, "
            f"sentenze/udienze/provvedimenti {card['case_law_and_hearings']}, "
            f"atti {card['acts_to_prepare']}, scadenze/task {card['deadlines_tasks']}, "
            f"domande Lex {card['lex_questions']}."
        )
    lines.extend(["", "## Riferimenti nominali", ""])
    for reference in payload["references"]:
        status = "coperto" if reference["covered"] else "da completare"
        practices = ", ".join(reference["practice_ids"][:4])
        lines.append(
            f"- `{reference['id']}` - {reference['label']} ({reference['authority']}): {status}; "
            f"tipo {reference['kind']}; pratiche {practices}."
        )
    lines.extend(["", "## Mancanze", ""])
    if payload["issues"]:
        lines.extend(f"- {issue}" for issue in payload["issues"])
    else:
        lines.append("Nessuna mancanza rilevata: tutte le schede e tutti i riferimenti nominali superano il gate.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit copertura matrice pratica legale.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-incomplete", action="store_true")
    args = parser.parse_args(argv)

    payload = build_audit()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"legal-practice-matrix-audit-{AUDIT_DATE}"
    _write_json(output_dir / f"{stem}.json", payload)
    _write_markdown(output_dir / f"{stem}.md", payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_incomplete and payload["summary"]["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
