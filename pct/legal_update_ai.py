from __future__ import annotations

import json
import re
from typing import Any

from pct.local_ai import OllamaHttpClient


CLASSIFICATION_TYPES = {
    "NORMATIVA_NUOVA",
    "NORMATIVA_AGGIORNAMENTO",
    "GIURISPRUDENZA",
    "PRASSI",
    "NEWS",
    "COMMENTO",
    "DUPLICATO",
    "INCERTO",
}

PROPOSED_ACTIONS = {
    "NEWS_ONLY",
    "NEW_NORMATIVE",
    "UPDATE_NORMATIVE",
    "NEW_CASE_LAW",
    "NEW_PRASSI",
    "DUPLICATE",
    "OUT_OF_SCOPE",
    "NEEDS_REVIEW",
}

MATTER_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("diritto_lavoro", ("licenziamento", "lavoro", "inps", "contratto collettivo", "sicurezza sul lavoro", "tfr", "mobbing")),
    ("diritto_tributario", ("agenzia delle entrate", "tribut", "iva", "accertamento", "riscossione", "credito d'imposta", "fisco", "imposta")),
    ("diritto_amministrativo", ("tar", "consiglio di stato", "appalto", "pubblica amministrazione", "procedimento amministrativo", "codice processo amministrativo")),
    ("diritto_penale", ("reato", "penale", "cassazione penale", "esecuzione penale", "procura", "codice penale", "procedura penale")),
    ("diritto_civile", ("contratto", "responsabilita", "responsabilità", "risarcimento", "locazione", "condominio", "successione", "codice civile", "danno", "nullita", "nullità")),
    ("privacy_protezione_dati", ("privacy", "gdpr", "data breach", "protezione dati", "garante")),
    ("appalti_contratti_pubblici", ("appalti", "contratti pubblici", "gara", "sotto soglia", "sopra soglia")),
    ("diritto_ue", ("regolamento ue", "direttiva", "eur-lex", "unione europea", "commissione europea")),
    ("previdenza_assistenza", ("previdenza", "assistenza", "cassa forense", "assegno", "contributo")),
    ("consumatori", ("consumatore", "consumatori", "clausola vessatoria", "codice del consumo")),
    ("ambiente_energia", ("ambiente", "energia", "impianto", "autorizzazione ambientale")),
    ("sanita", ("sanita", "medico", "servizio sanitario", "struttura sanitaria")),
    ("edilizia_urbanistica", ("urbanistica", "edilizia", "permesso di costruire", "abuso edilizio")),
    ("pubblico_impiego", ("pubblico impiego", "concorso pubblico", "dipendente pubblico")),
)

SUBMATTER_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("diritto_civile", "contratti", ("contratto", "clausola", "inadempimento")),
    ("diritto_civile", "responsabilita_civile", ("responsabilita", "risarcimento", "danno")),
    ("diritto_immobiliare", "locazioni", ("locazione", "locazioni", "canone")),
    ("diritto_lavoro", "licenziamenti", ("licenziamento", "reintegra", "giusta causa")),
    ("diritto_lavoro", "sicurezza_sul_lavoro", ("sicurezza sul lavoro", "infortunio", "dvr")),
    ("diritto_tributario", "iva", ("iva", "aliquota", "detrazione")),
    ("diritto_tributario", "accertamento", ("accertamento", "avviso", "adesione")),
    ("diritto_tributario", "riscossione", ("riscossione", "cartella", "agenzia entrate-riscossione")),
    ("diritto_amministrativo", "processo_amministrativo", ("tar", "consiglio di stato", "processo amministrativo")),
    ("privacy_protezione_dati", "gdpr", ("gdpr", "regolamento ue 2016/679")),
    ("privacy_protezione_dati", "data_breach", ("data breach", "violazione dei dati")),
    ("appalti_contratti_pubblici", "appalti_sotto_soglia", ("sotto soglia", "affidamento diretto")),
    ("appalti_contratti_pubblici", "appalti_sopra_soglia", ("sopra soglia", "bando europeo")),
    ("diritto_fallimentare_crisi_impresa", "concordato", ("concordato",)),
    ("diritto_fallimentare_crisi_impresa", "composizione_negoziata", ("composizione negoziata",)),
    ("diritto_penale", "esecuzione_penale", ("esecuzione penale", "misura alternativa")),
    ("diritto_civile", "procedura_civile", ("procedura civile", "processo civile", "codice di procedura civile", "c.p.c.")),
    ("diritto_penale", "procedura_penale", ("procedura penale", "processo penale", "codice di procedura penale", "c.p.p.")),
    ("diritto_civile", "giurisprudenza_merito", ("giurisprudenza di merito", "tribunale", "corte d'appello")),
    ("diritto_civile", "avvocati_professione_forense", ("avvocato", "avvocati", "professionale forense", "deontologia")),
    ("diritto_civile", "notifiche_pec", ("pec", "notifica", "notifiche", "domicilio digitale")),
    ("diritto_civile", "onere_della_prova", ("onere della prova", "prova", "art. 2697", "2697 c.c.")),
    ("diritto_civile", "nullita", ("nullita", "nullità", "annullabilita", "annullabilità")),
    ("diritto_civile", "termini_processuali", ("termine processuale", "termini processuali", "decadenza", "rimessione in termini")),
    ("diritto_famiglia", "separazione_divorzio", ("separazione", "divorzio", "assegno divorzile")),
    ("diritto_famiglia", "figli_mantenimento", ("figli", "mantenimento", "assegno mantenimento", "minori")),
    ("diritto_civile", "decreto_ingiuntivo_opposizione", ("decreto ingiuntivo", "opposizione a decreto ingiuntivo", "opposizione istat")),
    ("diritto_civile", "circolazione_stradale", ("codice della strada", "circolazione stradale", "sinistro stradale", "rc auto")),
    ("diritto_civile", "compensi_avvocato", ("compenso avvocato", "compensi forensi", "parcella", "d.m. 55")),
)

NORM_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("decreto_legge", re.compile(r"\bdecreto[\s-]legge\b", re.IGNORECASE)),
    ("decreto_legislativo", re.compile(r"\bdecreto legislativo\b", re.IGNORECASE)),
    ("decreto_ministeriale", re.compile(r"\bdecreto ministeriale\b", re.IGNORECASE)),
    ("regolamento", re.compile(r"\bregolamento\b", re.IGNORECASE)),
    ("direttiva", re.compile(r"\bdirettiva\b", re.IGNORECASE)),
    ("decisione", re.compile(r"\bdecisione\b", re.IGNORECASE)),
    ("legge", re.compile(r"\blegge\b", re.IGNORECASE)),
    ("circolare", re.compile(r"\bcircolare\b", re.IGNORECASE)),
    ("risoluzione", re.compile(r"\brisoluzione\b", re.IGNORECASE)),
    ("interpello", re.compile(r"\binterpello\b", re.IGNORECASE)),
    ("provvedimento", re.compile(r"\bprovvedimento\b", re.IGNORECASE)),
)

NORM_NUMBER_RE = re.compile(r"(?:n\.|numero)\s*([0-9]{1,4})(?:/([0-9]{4}))?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20[0-9]{2}|19[0-9]{2})\b")
DECISION_RE = re.compile(
    r"(?:sentenza|ordinanza|decisione)\s*(?:n\.|numero)?\s*([0-9]{1,5})(?:/([0-9]{4}))?",
    re.IGNORECASE,
)

COURT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Corte costituzionale", re.compile(r"corte costituzionale", re.IGNORECASE)),
    ("Corte di Cassazione", re.compile(r"cassazione", re.IGNORECASE)),
    ("Consiglio di Stato", re.compile(r"consiglio di stato", re.IGNORECASE)),
    ("TAR", re.compile(r"\btar\b", re.IGNORECASE)),
    ("Corte di giustizia UE", re.compile(r"corte di giustizia", re.IGNORECASE)),
)

UPDATE_MARKERS = (
    "modifica",
    "aggiorna",
    "sostituisce",
    "integra",
    "abroga",
    "conversione",
    "proroga",
    "sospende",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalized_text(*parts: Any) -> str:
    return _clean_spaces(" ".join(_clean_spaces(part) for part in parts if part)).lower()


def _extract_norm_type(text: str) -> str:
    for label, pattern in NORM_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def _extract_norm_number_year(text: str) -> tuple[str, str]:
    match = NORM_NUMBER_RE.search(text)
    if not match:
        return "", ""
    number = _clean_spaces(match.group(1))
    year = _clean_spaces(match.group(2))
    if not year:
        year_match = YEAR_RE.search(text[match.start() : match.end() + 20])
        if not year_match:
            year_match = YEAR_RE.search(text)
        if year_match:
            year = _clean_spaces(year_match.group(1))
    return number, year


def _extract_decision_data(text: str) -> tuple[str, str, str]:
    court_name = ""
    for label, pattern in COURT_PATTERNS:
        if pattern.search(text):
            court_name = label
            break
    match = DECISION_RE.search(text)
    if not match:
        return court_name, "", ""
    number = _clean_spaces(match.group(1))
    year = _clean_spaces(match.group(2))
    if not year:
        year_match = YEAR_RE.search(text[match.start() : match.end() + 20])
        if not year_match:
            year_match = YEAR_RE.search(text)
        if year_match:
            year = _clean_spaces(year_match.group(1))
    return court_name, number, year


def infer_matter(title: str, body_text: str, *, source_category: str = "", issuer: str = "") -> str:
    text = _normalized_text(title, body_text, source_category, issuer)
    for slug, keywords in MATTER_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return slug
    if "ue" in _normalized_text(source_category) or "eur-lex" in text:
        return "diritto_ue"
    if "lavoro" in text:
        return "diritto_lavoro"
    if "tribut" in text:
        return "diritto_tributario"
    if "amministrativ" in text:
        return "diritto_amministrativo"
    if "penal" in text:
        return "diritto_penale"
    return "diritto_civile"


def infer_submatter(matter_slug: str, title: str, body_text: str) -> str:
    text = _normalized_text(title, body_text)
    for matter, submatter, keywords in SUBMATTER_KEYWORDS:
        if matter == matter_slug and any(keyword in text for keyword in keywords):
            return submatter
    return ""


def _sanitize_json_text(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _query_ollama(base_url: str, model: str, prompt: str, *, timeout: int = 60) -> dict[str, Any]:
    payload = OllamaHttpClient(base_url, timeout=timeout).generate_completion(
        model,
        prompt,
        response_format="json",
        timeout=timeout,
    )
    content = _sanitize_json_text(payload.get("response") or "")
    return json.loads(content)


def _build_llm_prompt(document: dict[str, Any], heuristic: dict[str, Any], source: dict[str, Any]) -> str:
    return (
        "Sei il classificatore documentale del motore di aggiornamento giuridico di IUSENTRA.\n"
        "Restituisci solo JSON valido.\n"
        "Classifica il documento in una sola categoria tra: "
        "NORMATIVA_NUOVA, NORMATIVA_AGGIORNAMENTO, GIURISPRUDENZA, PRASSI, NEWS, COMMENTO, DUPLICATO, INCERTO.\n"
        "Mantieni prudenza: se i dati strutturali non sono chiari, non inventare.\n"
        f"Fonte: {json.dumps(source, ensure_ascii=False)}\n"
        f"Documento: {json.dumps(document, ensure_ascii=False)}\n"
        f"Analisi euristica: {json.dumps(heuristic, ensure_ascii=False)}\n"
        "Output richiesto: classification_type, matter_slug, submatter_slug, summary_short, summary_long, "
        "what_changes, confidence_score, impact_level, issuer, norm_type, norm_number, norm_year, "
        "decision_number, decision_year, court_name, effective_date."
    )


def _merge_llm_payload(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in (
        "classification_type",
        "matter_slug",
        "submatter_slug",
        "summary_short",
        "summary_long",
        "what_changes",
        "impact_level",
        "issuer",
        "norm_type",
        "norm_number",
        "norm_year",
        "decision_number",
        "decision_year",
        "court_name",
        "effective_date",
    ):
        value = candidate.get(key)
        if value not in (None, ""):
            merged[key] = value
    if candidate.get("confidence_score") not in (None, ""):
        try:
            merged["confidence_score"] = max(float(base.get("confidence_score") or 0), float(candidate["confidence_score"]))
        except (TypeError, ValueError):
            pass
    if str(merged.get("classification_type") or "").upper() not in CLASSIFICATION_TYPES:
        merged["classification_type"] = base.get("classification_type") or "INCERTO"
    return merged


def analyze_document(
    document: dict[str, Any],
    source: dict[str, Any],
    *,
    ai_base_url: str = "",
    ai_model: str = "",
) -> dict[str, Any]:
    title = _clean_spaces(document.get("title"))
    body_text = str(document.get("body_text") or "")
    body_short = _clean_spaces(document.get("body_short") or body_text[:240])
    issuer = _clean_spaces(document.get("issuer") or source.get("name") or "")
    source_category = _clean_spaces(source.get("category"))
    combined = _normalized_text(title, body_text, issuer, source_category)

    norm_type = _extract_norm_type(combined)
    norm_number, norm_year = _extract_norm_number_year(combined)
    court_name, decision_number, decision_year = _extract_decision_data(combined)

    classification_type = "INCERTO"
    if source_category in {"normativa", "ue"} or norm_type:
        classification_type = "NORMATIVA_AGGIORNAMENTO" if any(marker in combined for marker in UPDATE_MARKERS) else "NORMATIVA_NUOVA"
    elif source_category == "giurisprudenza" or decision_number or court_name:
        classification_type = "GIURISPRUDENZA"
    elif source_category == "prassi" or any(token in combined for token in ("circolare", "risoluzione", "interpello", "provvedimento")):
        classification_type = "PRASSI"
    elif bool(source.get("is_official")):
        classification_type = "NEWS"
    else:
        classification_type = "COMMENTO"

    matter_slug = infer_matter(title, body_text, source_category=source_category, issuer=issuer)
    submatter_slug = infer_submatter(matter_slug, title, body_text)

    confidence = 0.52
    if bool(source.get("is_official")):
        confidence += 0.15
    if classification_type in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"} and norm_type and norm_number and norm_year:
        confidence += 0.18
    if classification_type == "GIURISPRUDENZA" and court_name and decision_number and decision_year:
        confidence += 0.18
    if classification_type == "PRASSI" and norm_number and norm_year:
        confidence += 0.12
    if len(body_text) > 400:
        confidence += 0.05
    if classification_type == "COMMENTO":
        confidence -= 0.12
    confidence = max(0.1, min(0.99, confidence))

    impact_level = "medio"
    if classification_type in {"NORMATIVA_AGGIORNAMENTO", "GIURISPRUDENZA"}:
        impact_level = "alto"
    elif classification_type in {"NEWS", "COMMENTO"}:
        impact_level = "basso"

    summary_short = body_short or title or "Aggiornamento giuridico in acquisizione."
    summary_long = body_text[:1400] if body_text else title
    what_changes = {
        "NORMATIVA_NUOVA": "Introduce un nuovo atto o un nuovo riferimento normativo da censire in archivio.",
        "NORMATIVA_AGGIORNAMENTO": "Aggiorna un atto esistente e richiede controllo di versionamento e relazioni.",
        "GIURISPRUDENZA": "Introduce un nuovo orientamento o un deposito da collegare a norme e materie.",
        "PRASSI": "Fornisce istruzioni applicative o chiarimenti operativi dell'ente emittente.",
        "NEWS": "Segnala un aggiornamento informativo collegabile a fonti ufficiali.",
        "COMMENTO": "Contenuto editoriale o commento, utile solo come supporto informativo.",
    }.get(classification_type, "Richiede revisione amministrativa per essere classificato correttamente.")

    analysis = {
        "classification_type": classification_type,
        "confidence_score": round(confidence, 2),
        "impact_level": impact_level,
        "issuer": issuer,
        "norm_type": norm_type,
        "norm_number": norm_number,
        "norm_year": norm_year,
        "decision_number": decision_number,
        "decision_year": decision_year,
        "court_name": court_name,
        "effective_date": _clean_spaces(document.get("document_date")),
        "matter_slug": matter_slug,
        "submatter_slug": submatter_slug,
        "summary_short": summary_short[:220],
        "summary_long": summary_long[:2000],
        "what_changes": what_changes[:1200],
        "extracted_entities_json": {
            "references": [item for item in (norm_type, norm_number, norm_year, decision_number, decision_year, court_name) if item],
            "source_category": source_category,
            "source_code": source.get("code"),
        },
    }

    if ai_base_url and ai_model:
        try:
            llm_payload = _query_ollama(ai_base_url, ai_model, _build_llm_prompt(document, analysis, source))
            if isinstance(llm_payload, dict):
                analysis = _merge_llm_payload(analysis, llm_payload)
        except Exception:
            pass

    return analysis
