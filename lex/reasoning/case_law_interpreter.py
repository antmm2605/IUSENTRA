"""Interprete strutturato delle evidenze giurisprudenziali per Lex."""

from __future__ import annotations

import re
from typing import Any


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", "\n").split()).strip()


def first_non_empty(*values: Any) -> str:
    for value in values:
        clean = clean_text(value)
        if clean:
            return clean
    return ""


def _as_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item.get("metadata") or {})
    return dict(getattr(item, "metadata", {}) or {})


def _get_value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _metadata_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata.get(key) not in (None, ""):
            return metadata.get(key)
    return ""


def _list_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return ", ".join(clean_text(item) for item in value if clean_text(item))
    return clean_text(value)


def _infer_from_title(title: str) -> dict[str, str]:
    inferred = {"numero": "", "anno": "", "organo": ""}
    match = re.search(r"(?:sentenza|sent\.)\s*n\.?\s*(\d+)\s*/\s*(\d{4})", title, flags=re.I)
    if match:
        inferred["numero"] = match.group(1)
        inferred["anno"] = match.group(2)
    lowered = title.lower()
    if "corte costituzionale" in lowered:
        inferred["organo"] = "Corte costituzionale"
    elif "cassazione" in lowered:
        inferred["organo"] = "Corte di cassazione"
    elif "consiglio di stato" in lowered:
        inferred["organo"] = "Consiglio di Stato"
    elif "tar" in lowered:
        inferred["organo"] = "TAR"
    return inferred


def normalize_case_law_item(item: Any) -> dict[str, Any]:
    metadata = _as_metadata(item)
    title = first_non_empty(
        _get_value(item, "title"),
        _get_value(item, "titolo"),
        _metadata_value(metadata, "title", "titolo", "citation"),
        "Pronuncia giurisprudenziale",
    )
    inferred = _infer_from_title(title)
    content = first_non_empty(
        _get_value(item, "content"),
        _get_value(item, "excerpt"),
        _get_value(item, "text"),
        _metadata_value(metadata, "content", "excerpt", "text", "sintesi"),
    )
    official_url = first_non_empty(
        _get_value(item, "official_url"),
        _get_value(item, "url"),
        _metadata_value(metadata, "official_url", "url", "url_pagina_ufficiale"),
    )
    pdf_url = first_non_empty(
        _metadata_value(metadata, "url_pdf_ufficiale", "pdf_url", "url_pdf"),
        _get_value(item, "url_pdf_ufficiale"),
    )
    dispositivo = first_non_empty(
        _metadata_value(metadata, "dispositivo"),
        _get_value(item, "dispositivo"),
    )
    principio = first_non_empty(
        _metadata_value(metadata, "principio", "principio_sintetico", "massima_ufficiale"),
        _get_value(item, "principio"),
        _get_value(item, "principio_sintetico"),
        _get_value(item, "massima_ufficiale"),
    )
    row = {
        "title": title,
        "content": content,
        "source_id": first_non_empty(_get_value(item, "source_id"), _get_value(item, "id"), _metadata_value(metadata, "source_id")),
        "organo": first_non_empty(_metadata_value(metadata, "organo", "court", "grado"), inferred["organo"]),
        "numero": first_non_empty(_metadata_value(metadata, "numero", "numero_sentenza"), inferred["numero"]),
        "anno": first_non_empty(_metadata_value(metadata, "anno"), inferred["anno"]),
        "sezione": first_non_empty(_metadata_value(metadata, "sezione")),
        "data_deposito": first_non_empty(
            _metadata_value(metadata, "data_deposito", "published_at"),
            _get_value(item, "published_at"),
        ),
        "data_decisione": first_non_empty(_metadata_value(metadata, "data_decisione")),
        "norme_citate": _list_text(_metadata_value(metadata, "norme_citate", "riferimenti_normativi")),
        "questione": first_non_empty(_metadata_value(metadata, "questione", "questione_giuridica")),
        "dispositivo": dispositivo,
        "principio": principio,
        "massima_ufficiale": first_non_empty(_metadata_value(metadata, "massima_ufficiale")),
        "official_url": official_url,
        "url_pagina_ufficiale": first_non_empty(_metadata_value(metadata, "url_pagina_ufficiale"), official_url),
        "url_pdf_ufficiale": pdf_url,
        "verified_reference": bool(
            _get_value(item, "verified_reference", False)
            or metadata.get("verified_reference")
        ),
        "metadata": metadata,
    }
    if not row["questione"]:
        row["questione"] = _infer_question(row)
    return row


def _infer_question(row: dict[str, Any]) -> str:
    haystack = " ".join([clean_text(row.get("title")), clean_text(row.get("content")), clean_text(row.get("principio"))])
    if "578-bis" in haystack or "578 bis" in haystack:
        return "Questione relativa all'art. 578-bis c.p.p."
    return ""


def build_case_law_context(evidence_items: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in list(evidence_items or []):
        row = normalize_case_law_item(item)
        if not row["title"] and not row["content"]:
            continue
        key = "|".join(
            [
                clean_text(row.get("source_id")).lower(),
                clean_text(row.get("title")).lower(),
                clean_text(row.get("numero")),
                clean_text(row.get("anno")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def detect_case_law_completeness(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = list(case_rows or [])
    has_integral_text = any(len(clean_text(row.get("content"))) > 1800 for row in rows)
    has_dispositivo = any(clean_text(row.get("dispositivo")) for row in rows)
    has_principio = any(clean_text(row.get("principio")) or clean_text(row.get("massima_ufficiale")) for row in rows)
    has_official_url = any(clean_text(row.get("official_url")) or clean_text(row.get("url_pagina_ufficiale")) for row in rows)
    missing: list[str] = []
    if not has_integral_text:
        missing.append("testo integrale o motivazione completa")
    if not has_dispositivo:
        missing.append("dispositivo")
    if not has_principio:
        missing.append("principio o massima")
    if not has_official_url:
        missing.append("URL ufficiale")
    return {
        "rows": len(rows),
        "has_integral_text": has_integral_text,
        "has_dispositivo": has_dispositivo,
        "has_principio": has_principio,
        "has_official_url": has_official_url,
        "missing": missing,
        "complete": bool(rows and has_dispositivo and has_principio and has_official_url),
    }


def build_case_law_prompt_block(case_rows: list[Any]) -> str:
    rows = build_case_law_context(case_rows)
    if not rows:
        return ""
    lines = ["=== SENTENZE DA ANALIZZARE ==="]
    for idx, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"Sentenza {idx}:",
                f"- Titolo: {clean_text(row.get('title'))}",
                f"- Organo: {clean_text(row.get('organo'))}",
                f"- Numero: {clean_text(row.get('numero'))}",
                f"- Anno: {clean_text(row.get('anno'))}",
                f"- Sezione: {clean_text(row.get('sezione'))}",
                f"- Data deposito: {clean_text(row.get('data_deposito'))}",
                f"- Norma/e citate: {clean_text(row.get('norme_citate'))}",
                f"- Questione: {clean_text(row.get('questione'))}",
                f"- Dispositivo: {clean_text(row.get('dispositivo'))}",
                f"- Principio: {clean_text(row.get('principio'))}",
                f"- Estratto: {clean_text(row.get('content'))[:1800]}",
                f"- Fonte ufficiale: {clean_text(row.get('url_pagina_ufficiale') or row.get('official_url'))}",
                f"- PDF ufficiale: {clean_text(row.get('url_pdf_ufficiale'))}",
                "",
            ]
        )
    completeness = detect_case_law_completeness(rows)
    if completeness["missing"]:
        lines.append("Dati da dichiarare come non completi: " + ", ".join(completeness["missing"]) + ".")
    return "\n".join(lines).strip()


def build_deterministic_case_law_answer(case_rows: list[Any], confidence_label: str = "media") -> str:
    rows = build_case_law_context(case_rows)
    if not rows:
        return (
            "Pronuncia individuata\n"
            "Non ho una pronuncia verificabile nelle evidenze disponibili.\n\n"
            "Oggetto della decisione\n"
            "Non determinabile senza una fonte giurisprudenziale agganciata.\n\n"
            "Decisione / dispositivo\n"
            "Non determinabile dalle evidenze disponibili.\n\n"
            "Principio ricavabile\n"
            "Non ricavabile senza testo, massima o estratto verificato.\n\n"
            "Limiti\n"
            "Prima dell'uso in atto o parere serve acquisire il testo ufficiale.\n\n"
            "Fonti considerate\n"
            "- Nessuna fonte giurisprudenziale strutturata disponibile."
        )
    first = rows[0]
    completeness = detect_case_law_completeness(rows)
    title = clean_text(first.get("title")) or "Pronuncia giurisprudenziale"
    organo = clean_text(first.get("organo")) or "Organo non indicato nelle evidenze"
    oggetto = first_non_empty(first.get("questione"), first.get("principio"), first.get("content"))
    dispositivo = clean_text(first.get("dispositivo")) or "Il dispositivo non risulta disponibile nelle evidenze agganciate."
    principio = clean_text(first.get("principio")) or "Il principio non risulta espresso in modo autonomo nelle evidenze agganciate."
    norme = clean_text(first.get("norme_citate")) or "Norme non indicate nelle evidenze strutturate."
    fonte_lines = []
    for row in rows:
        fonte = first_non_empty(row.get("url_pagina_ufficiale"), row.get("official_url"), row.get("url_pdf_ufficiale"), row.get("source_id"))
        label = clean_text(row.get("title")) or "Fonte giurisprudenziale"
        suffix = f" - {fonte}" if fonte else ""
        fonte_lines.append(f"- {label}{suffix}")
    if not fonte_lines:
        fonte_lines.append("- Fonte non indicata.")
    limited = ""
    if completeness["missing"]:
        limited = " Mancano nelle evidenze: " + ", ".join(completeness["missing"]) + "."
    return (
        "Pronuncia individuata\n"
        f"Ho trovato: {title}.\n\n"
        "Organo giudicante\n"
        f"{organo}.\n\n"
        "Oggetto della decisione\n"
        f"{clean_text(oggetto) or 'Oggetto non determinabile dalle evidenze disponibili.'}\n\n"
        "Norma/e coinvolte\n"
        f"{norme}\n\n"
        "Decisione / dispositivo\n"
        f"Dalle evidenze risulta: {dispositivo}\n\n"
        "Principio ricavabile\n"
        f"Il principio ricavabile, nei limiti dell'estratto disponibile, e': {principio}\n\n"
        "Impatto pratico per lo studio\n"
        "La pronuncia va usata come base di verifica giurisprudenziale, distinguendo il dato certo "
        "contenuto nella fonte da eventuali inferenze operative da validare prima di atto o parere.\n\n"
        "Limiti\n"
        f"Affidabilita stimata: {confidence_label}. La risposta e' costruita sulle fonti agganciate da Lex.{limited} "
        "Prima di uso in atto o parere, verificare il testo integrale ufficiale.\n\n"
        "Fonti considerate\n"
        + "\n".join(fonte_lines)
    )
