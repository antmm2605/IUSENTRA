from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


CODE_ARTICLE_RE = re.compile(
    r"\b(?P<code>cod\.?\s+proc\.?\s+pen\.?|cod\.?\s+proc\.?\s+civ\.?|cod\.?\s+pen\.?|cod\.?\s+civ\.?|"
    r"codice\s+di\s+procedura\s+penale|codice\s+di\s+procedura\s+civile|codice\s+penale|codice\s+civile|"
    r"codice\s+della\s+strada|c\.p\.p\.|c\.p\.c\.|c\.p\.|c\.c\.|c\.d\.s\.)\s+"
    r"(?P<article>artt?\.?\s+[0-9][A-Za-z0-9_.-]*(?:\s*(?:,|e)\s*[0-9][A-Za-z0-9_.-]*)?)",
    re.IGNORECASE,
)
ARTICLE_RE = re.compile(
    r"\b(?:artt?\.?|articoli?)\s+[0-9][A-Za-z0-9_.-]*"
    r"(?:\s*(?:,|e)\s*[0-9][A-Za-z0-9_.-]*)?"
    r"(?:\s*,?\s*(?:comma|commi)\s+(?:[0-9]+|primo|secondo|terzo|quarto|quinto|sesto|settimo|ottavo|nono|decimo)"
    r"(?:\s*(?:,|e)\s*(?:[0-9]+|primo|secondo|terzo|quarto|quinto|sesto|settimo|ottavo|nono|decimo))?)?"
    r"(?:\s*(?:c\.p\.p\.|c\.p\.c\.|c\.p\.|c\.c\.|c\.d\.s\.|cod\.?\s+proc\.?\s+pen\.?|cod\.?\s+proc\.?\s+civ\.?|"
    r"cod\.?\s+pen\.?|cod\.?\s+civ\.?|codice\s+di\s+procedura\s+penale|codice\s+di\s+procedura\s+civile|"
    r"codice\s+penale|codice\s+civile|codice\s+della\s+strada))?",
    re.IGNORECASE,
)
ACT_RE = re.compile(
    r"\b(?:D\.?\s*Lgs\.?|Decreto\s+legislativo|D\.?\s*L\.?|Decreto-?legge|D\.?\s*P\.?\s*R\.?|"
    r"D\.?\s*M\.?|Legge|L\.)\s*(?:\d{1,2}\s+[A-Za-zàèéìòù]+\s+\d{4},?\s*)?"
    r"(?:n\.?\s*)?[0-9]{1,6}(?:/[0-9]{2,4})?",
    re.IGNORECASE,
)
EU_ACT_RE = re.compile(
    r"\b(?:Regolamento|Direttiva)\s+\(?UE\)?\s+[0-9]{4}/[0-9]{1,6}",
    re.IGNORECASE,
)
DECISION_RE = re.compile(
    r"\b(?:sentenza|ordinanza|decreto|delibera|decisione|parere)\s+(?:n\.?\s*)?[0-9]{1,6}(?:/[0-9]{2,4})?"
    r"(?:\s+del\s+\d{1,2}(?:/\d{1,2}/\d{2,4}|\s+[A-Za-zàèéìòù]+\s+\d{4}))?",
    re.IGNORECASE,
)
COURT_RE = re.compile(
    r"\b(?:Corte\s+Suprema\s+di\s+Cassazione|Corte\s+di\s+Cassazione|Cassazione|Corte\s+costituzionale|"
    r"Consiglio\s+di\s+Stato|TAR(?:\s+[A-Za-zàèéìòù]+)?|CGUE|Corte\s+di\s+giustizia\s+UE|CEDU|Corte\s+EDU)\b",
    re.IGNORECASE,
)
RG_RE = re.compile(
    r"\b(?:R\.?\s*G\.?|RG|ricorso\s+n\.?|ricorso\s+nr\.?)\s*(?:n\.?\s*)?[0-9]{1,6}\s*/\s*[0-9]{2,4}\b",
    re.IGNORECASE,
)
CONTENT_ID_RE = re.compile(r"\bcontentId=[A-Za-z0-9_-]+\b", re.IGNORECASE)

LAW_FIRM_CONTEXT_TERMS: tuple[str, ...] = (
    "norma",
    "decreto",
    "regolamento",
    "sentenza",
    "ordinanza",
    "questione",
    "massima",
    "circolare",
    "interpello",
    "messaggio",
    "provvedimento",
    "sanzione",
    "controversia",
    "ricorso",
    "appalto",
    "lavoro",
    "previdenza",
    "privacy",
    "tribut",
    "penale",
    "civile",
    "amministrativo",
    "famiglia",
    "locazione",
    "responsabilità",
)


def clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def extract_legal_references(
    text: Any,
    *,
    source_document: str = "",
    document_part: str = "",
    limit: int = 48,
) -> list[dict[str, Any]]:
    """Estrae riferimenti deterministici senza risolvere link non verificati."""

    source = clean_spaces(text)
    if not source:
        return []
    refs: list[dict[str, Any]] = []
    _collect_code_articles(refs, source, source_document=source_document, document_part=document_part)
    for pattern, ref_type, confidence in (
        (ARTICLE_RE, "article", 0.9),
        (ACT_RE, "act", 0.88),
        (EU_ACT_RE, "eu_act", 0.88),
        (DECISION_RE, "decision", 0.86),
        (COURT_RE, "court", 0.76),
        (RG_RE, "rg", 0.9),
        (CONTENT_ID_RE, "content_id", 0.88),
    ):
        for match in pattern.finditer(source):
            _append_reference(
                refs,
                source,
                match.start(),
                match.end(),
                ref_type=ref_type,
                source_document=source_document,
                document_part=document_part,
                confidence=confidence,
            )
    return _dedupe_references(refs, limit=limit)


def legal_reference_labels(
    references: Iterable[dict[str, Any]],
    *,
    allowed_types: Iterable[str] | None = None,
    limit: int = 20,
) -> list[str]:
    allowed = {str(item) for item in allowed_types or ()}
    labels: list[str] = []
    seen: set[str] = set()
    for row in references:
        if allowed and str(row.get("type") or "") not in allowed:
            continue
        label = clean_spaces(row.get("normalized_text") or row.get("text"))
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def build_contextual_question_matrix(
    *,
    title: Any,
    context_text: Any = "",
    has_attachment: bool = False,
    norm_references: Iterable[Any] = (),
    rg_references: Iterable[Any] = (),
    source_code: Any = "",
    category: Any = "",
    matter: Any = "",
    has_rg_discrepancy: bool = False,
    limit: int = 18,
) -> list[dict[str, str]]:
    subject = clean_spaces(title) or "questa fonte"
    context = clean_spaces(context_text)
    haystack = f"{subject} {context} {source_code} {category} {matter}".casefold()
    rg_values = [clean_spaces(value) for value in rg_references if clean_spaces(value)]
    norm_values = [clean_spaces(value) for value in norm_references if clean_spaces(value)]
    primary_rg = rg_values[0] if rg_values else ""
    reference = f" R.G. {primary_rg}" if primary_rg and "r.g." not in subject.casefold() else ""

    rows: list[tuple[str, str]] = [
        ("sintesi", f"Mi puoi sintetizzare {subject}{reference}?"),
        ("natura_atto", "È una sentenza definitiva, un'ordinanza, una questione pendente o un altro atto?"),
        ("oggetto", "Qual è l'oggetto della questione o della decisione?"),
        ("stato", "Qual è lo stato del procedimento o dell'atto?"),
        ("punto_diritto", "Qual è il punto di diritto o il principio in discussione?"),
        ("motivi", "Quali sono i motivi, le censure o i passaggi rilevanti indicati nel testo?"),
        ("norme", "Quali norme sono richiamate e perché contano?"),
        ("effetto_pratico", "Qual è l'effetto pratico per un avvocato che deve usare questa fonte?"),
        ("esito", "Risulta già un esito finale oppure la questione è ancora pendente?"),
    ]
    if "cassazione" in haystack:
        rows.append(("principio_operativo", f"Qual è il principio operativo della Cassazione su {subject}?"))
    if "agcom" in haystack:
        rows.append(("agcom_perimetro", "Questo provvedimento AGCOM riguarda sanzione, controversia utente, Corecom, diritto d'autore o una consultazione non operativa?"))
    if "inps" in haystack:
        rows.append(("inps_impatto", "Questa fonte INPS incide su termini, contributi o contenzioso previdenziale?"))
    if "openga" in haystack or "giustizia amministrativa" in haystack:
        rows.append(("open_data_destinazione", "Il dato amministrativo contiene un documento giuridico concreto o resta solo evidenza RAG?"))
    if has_attachment:
        rows.append(("pdf_allegato", "Quale PDF o allegato ufficiale è collegato e il link è cliccabile?"))
    if has_rg_discrepancy:
        rows.append(("discrepanza_rg", "Ci sono discrepanze tra il numero R.G. della scheda e quello del PDF?"))
    if norm_values:
        rows.append(("articoli", "Puoi spiegare gli articoli richiamati senza limitarti a citarli?"))
    if any(term in haystack for term in LAW_FIRM_CONTEXT_TERMS):
        rows.append(("uso_in_atto", "Questa fonte è utilizzabile per redigere un atto o serve solo come monitoraggio?"))
    rows.append(("qualita_testo", "Il testo è leggibile oppure ci sono parti OCR da non riportare come certe?"))
    return [{"check": key, "question": question} for key, question in _dedupe_rows(rows)[: max(1, int(limit or 1))]]


def _collect_code_articles(
    refs: list[dict[str, Any]],
    text: str,
    *,
    source_document: str,
    document_part: str,
) -> None:
    for match in CODE_ARTICLE_RE.finditer(text):
        value = f"{clean_spaces(match.group('article'))} {clean_spaces(match.group('code'))}"
        _append_reference(
            refs,
            text,
            match.start(),
            match.end(),
            ref_type="article",
            source_document=source_document,
            document_part=document_part,
            confidence=0.92,
            override_text=value,
        )


def _append_reference(
    refs: list[dict[str, Any]],
    source: str,
    start: int,
    end: int,
    *,
    ref_type: str,
    source_document: str,
    document_part: str,
    confidence: float,
    override_text: str = "",
) -> None:
    raw = clean_spaces(override_text or source[start:end])
    raw = raw.strip(" ,.;:")
    if not raw:
        return
    refs.append(
        {
            "text": raw,
            "normalized_text": _normalize_reference(raw),
            "type": ref_type,
            "context_snippet": _snippet(source, start, end),
            "source_document": clean_spaces(source_document),
            "document_part": clean_spaces(document_part),
            "confidence": round(float(confidence), 2),
            "official_url": "",
        }
    )


def _normalize_reference(value: str) -> str:
    text = clean_spaces(value)
    text = re.sub(r"\barticoli\b", "artt.", text, flags=re.IGNORECASE)
    text = re.sub(r"\barticolo\b", "art.", text, flags=re.IGNORECASE)
    text = re.sub(r"\bartt?\b(?!\.)", lambda m: "artt." if m.group(0).lower().startswith("artt") else "art.", text)
    fixes = {
        r"\bcod\.?\s+proc\.?\s+pen\.?\b": "c.p.p.",
        r"\bcodice\s+di\s+procedura\s+penale\b": "c.p.p.",
        r"\bcod\.?\s+proc\.?\s+civ\.?\b": "c.p.c.",
        r"\bcodice\s+di\s+procedura\s+civile\b": "c.p.c.",
        r"\bcod\.?\s+pen\.?\b": "c.p.",
        r"\bcodice\s+penale\b": "c.p.",
        r"\bcod\.?\s+civ\.?\b": "c.c.",
        r"\bcodice\s+civile\b": "c.c.",
        r"\bcodice\s+della\s+strada\b": "c.d.s.",
    }
    for pattern, replacement in fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    for pattern, replacement in {
        r"(?<!\w)c\.p\.p\.?(?!\w)": "c.p.p.",
        r"(?<!\w)c\.p\.c\.?(?!\w)": "c.p.c.",
        r"(?<!\w)c\.p\.?(?!\.?[pc])(?!\w)": "c.p.",
        r"(?<!\w)c\.c\.?(?!\w)": "c.c.",
        r"(?<!\w)c\.d\.s\.?(?!\w)": "c.d.s.",
    }.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return clean_spaces(text)


def _snippet(source: str, start: int, end: int, *, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(source), end + radius)
    return clean_spaces(source[left:right]).strip(" ,.;:")


def _dedupe_references(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("type") or ""), clean_spaces(row.get("normalized_text")).casefold())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _dedupe_rows(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, question in rows:
        if key in seen:
            continue
        seen.add(key)
        result.append((key, question))
    return result
