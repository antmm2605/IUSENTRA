from __future__ import annotations

from typing import Any


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


def generate_context_questions(
    *,
    source_code: Any = "",
    title: Any,
    body: Any = "",
    pdf_text: Any = "",
    references: list[Any] | tuple[Any, ...] = (),
    classification: Any = "",
    matter: Any = "",
    source_url: Any = "",
    attachment_url: Any = "",
    has_rg_discrepancy: bool = False,
    limit: int = 18,
) -> list[dict[str, str]]:
    subject = clean_spaces(title) or "questa fonte"
    context = clean_spaces(f"{body} {pdf_text}")
    source = clean_spaces(source_code).casefold()
    classification_text = clean_spaces(classification).casefold()
    matter_text = clean_spaces(matter).casefold()
    haystack = f"{subject} {context} {source} {classification_text} {matter_text}".casefold()
    norm_labels = _reference_labels(references, types={"article", "act", "eu_act"})
    rg_labels = _reference_labels(references, types={"rg"})
    if not rg_labels:
        rg_labels = _extract_rg_labels(context)
    primary_rg = rg_labels[0] if rg_labels else ""
    rg_suffix = f" R.G. {primary_rg}" if primary_rg and "r.g." not in subject.casefold() else ""

    rows: list[tuple[str, str, str, str]] = [
        ("sintesi", f"Mi puoi sintetizzare {subject}{rg_suffix}?", "capire subito il contenuto operativo", "titolo"),
        ("natura_atto", "È una sentenza definitiva, un'ordinanza, una questione pendente o un altro atto?", "distinguere esito, stato e valore d'uso", "titolo fonte"),
        ("oggetto", "Qual è l'oggetto della questione o della decisione?", "identificare il tema utile per lo studio", "corpo"),
        ("stato", "Qual è lo stato del procedimento o dell'atto?", "evitare di trattare una pendenza come decisione definitiva", "corpo"),
        ("punto_diritto", "Qual è il punto di diritto o il principio in discussione?", "ricavare il principio operativo", "testo"),
        ("motivi", "Quali sono i motivi, le censure o i passaggi rilevanti indicati nel testo?", "preparare uso in atto o memoria", "testo"),
        ("norme", "Quali norme sono richiamate e perché contano?", "collegare articoli e impatto pratico", "riferimenti"),
        ("effetto_pratico", "Qual è l'effetto pratico per un avvocato che deve usare questa fonte?", "tradurre il contenuto in azione di studio", "classificazione"),
        ("esito", "Qual è l'esito o il prossimo passaggio operativo da verificare?", "non confondere decisione, pendenza e monitoraggio", "corpo"),
        ("destinazione", "Questa fonte aggiorna normativa, prassi, giurisprudenza o resta RAG-only?", "decidere pubblicazione e consultazione", "policy fonte"),
    ]
    if "cassazione" in haystack:
        rows.append(("principio_operativo", f"Qual è il principio operativo della Cassazione su {subject}?", "presidiare massime, sentenze e questioni", "fonte Cassazione"))
    if "agcom" in haystack:
        rows.append(("agcom_perimetro", "Il provvedimento AGCOM riguarda sanzione, controversia, Corecom, tutela utenti, diritto d'autore o consultazione?", "evitare contributi/consultazioni non operative", "fonte AGCOM"))
    if "inps" in haystack:
        rows.append(("inps_impatto", "La circolare o il messaggio INPS incide su termini, contributi o contenzioso previdenziale?", "selezionare impatto previdenziale", "fonte INPS"))
    if "openga" in haystack or "giustizia amministrativa" in haystack:
        rows.append(("open_data_destinazione", "Il dato amministrativo contiene un documento giuridico concreto o resta solo evidenza RAG?", "non pubblicare cataloghi come news", "OpenGA"))
    if attachment_url or pdf_text:
        rows.append(("pdf_allegato", "Quale PDF o allegato ufficiale contiene il testo e il link è cliccabile?", "rendere verificabile il testo ufficiale", "allegato"))
        rows.append(("articoli_pdf", "Quali articoli sono richiamati nel PDF o nell'allegato OCR?", "usare gli articoli estratti dal documento", "PDF/OCR"))
        if any(marker in haystack for marker in ("c.p.p.", "cod. proc. pen", "codice di procedura penale")):
            rows.append(("articoli_cpp_pdf", "Quali articoli del c.p.p. sono richiamati nel PDF?", "isolare i riferimenti processuali penali dell'allegato", "PDF/OCR"))
    if has_rg_discrepancy:
        rows.append(("discrepanza_rg", "Ci sono discrepanze tra il numero R.G. della scheda e quello del PDF?", "separare dati scheda e dati allegato", "R.G."))
    if norm_labels:
        rows.append(("articoli", "Puoi spiegare gli articoli richiamati senza limitarti a citarli?", "trasformare i riferimenti in ragionamento operativo", "riferimenti"))
    if any(term in haystack for term in LAW_FIRM_CONTEXT_TERMS):
        rows.append(("uso_in_atto", "Questa fonte è utilizzabile per redigere un atto o serve solo come monitoraggio?", "decidere l'uso professionale", "materia"))
    rows.append(("qualita_testo", "Il testo è leggibile oppure ci sono parti OCR da non riportare come certe?", "segnalare limiti reali della fonte", "qualità testo"))

    return [
        {"type": key, "question": question, "reason": reason, "source": data_source}
        for key, question, reason, data_source in _dedupe(rows)[: max(1, int(limit or 1))]
    ]


def compat_question_matrix(
    *,
    title: Any,
    context_text: Any = "",
    has_attachment: bool = False,
    norm_references: list[Any] | tuple[Any, ...] = (),
    rg_references: list[Any] | tuple[Any, ...] = (),
    source_code: Any = "",
    category: Any = "",
    matter: Any = "",
    has_rg_discrepancy: bool = False,
    limit: int = 18,
) -> list[dict[str, str]]:
    references = [
        {"reference_type": "article", "normalized_text": clean_spaces(item)}
        for item in norm_references
        if clean_spaces(item)
    ] + [
        {"reference_type": "rg", "normalized_text": clean_spaces(item)}
        for item in rg_references
        if clean_spaces(item)
    ]
    rows = generate_context_questions(
        source_code=source_code,
        title=title,
        body=context_text,
        pdf_text=context_text if has_attachment else "",
        references=references,
        classification=category,
        matter=matter,
        attachment_url="allegato" if has_attachment else "",
        has_rg_discrepancy=has_rg_discrepancy,
        limit=limit,
    )
    return [{"check": row["type"], "question": row["question"], "reason": row["reason"], "source": row["source"]} for row in rows]


def _reference_labels(references: list[Any] | tuple[Any, ...], *, types: set[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in references:
        row = item if isinstance(item, dict) else {}
        row_type = clean_spaces(row.get("reference_type") or row.get("type"))
        if row_type not in types:
            continue
        label = clean_spaces(row.get("normalized_text") or row.get("raw_text") or row.get("text"))
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def _extract_rg_labels(text: str) -> list[str]:
    import re

    labels: list[str] = []
    for match in re.finditer(r"\b(?:R\.?\s*G\.?|RG)\s*(?:n\.?\s*)?([0-9]{1,6}\s*/\s*[0-9]{2,4})", text, re.IGNORECASE):
        label = clean_spaces(match.group(1).replace(" ", ""))
        if label and label not in labels:
            labels.append(label)
    return labels


def _dedupe(rows: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    seen: set[str] = set()
    output: list[tuple[str, str, str, str]] = []
    for row in rows:
        key = row[0]
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output
