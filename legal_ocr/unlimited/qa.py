from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from legal_ocr.ner_legal import extract_legal_entities


@dataclass(frozen=True, slots=True)
class LexOcrQuestion:
    id: str
    question: str
    patterns: tuple[str, ...]


DEFAULT_QUESTIONS = (
    LexOcrQuestion(
        "numero_ruolo",
        "Qual è il numero di ruolo o R.G. del documento?",
        (r"\b(?:proc\.?\s*n\.?\s*)?(?:R\.?\s*G\.?\s*A\.?\s*C\.?|RGAC|R\.?\s*G\.?).{0,40}\d{1,7}\s*/\s*\d{2,4}",),
    ),
    LexOcrQuestion(
        "ufficio",
        "Quale ufficio giudiziario emerge dal documento?",
        (
            r"\bTribunale\s+(?:di|per i Minorenni di|di Sorveglianza di)\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' ]{2,80}",
            r"\bCorte\s+d['’]Appello\s+di\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' ]{2,80}",
            r"\b(?:Ufficio\s+del\s+)?Giudice\s+di\s+Pace\s+di\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' ]{2,80}",
            r"\bProcura\s+(?:della\s+Repubblica|Generale)\s+di\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' ]{2,80}",
            r"\bTAR\s+[A-ZÀ-Ù][A-Za-zÀ-ÿ' ]{2,80}",
            r"\bConsiglio\s+di\s+Stato\b.{0,80}",
        ),
    ),
    LexOcrQuestion(
        "parti",
        "Quali parti o soggetti principali sono citati?",
        (
            r".{0,80}\b(?:contro| c/ | vs\.? )\b.{0,100}",
            r"\bparti\s*:\s*[^\n]{6,220}",
        ),
    ),
    LexOcrQuestion("date", "Quali date o scadenze processuali sono presenti?", (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b")),
    LexOcrQuestion("norme", "Quali articoli o riferimenti normativi sono richiamati?", (r"\b(?:art\.?|artt\.?|articolo)\s+\d+[^.;\n]{0,80}", r"\b(?:D\.Lgs\.?|D\.L\.?|L\.|DPR|D\.P\.R\.?|DM|D\.M\.?)\s*n\.?\s*\d+/\d{4}")),
    LexOcrQuestion("pec", "Sono presenti indirizzi PEC o riferimenti di comunicazione?", (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",)),
    LexOcrQuestion("importi", "Sono presenti importi economici rilevanti?", (r"(?:€|EUR|euro)\s*[\.,]?\s*\d[\d\.\s]*(?:,\d{2})?", r"\b\d[\d\.\s]*(?:,\d{2})\s*(?:€|euro|EUR)\b")),
)


def default_legal_questions() -> list[dict[str, str]]:
    return [{"id": item.id, "question": item.question} for item in DEFAULT_QUESTIONS]


def answer_questions_from_text(text: str, questions: list[str] | None = None) -> dict[str, Any]:
    normalized = _normalize(text)
    entities = extract_legal_entities(normalized)
    selected = _custom_questions(questions) if questions else list(DEFAULT_QUESTIONS)
    answers = [_answer_one(normalized, question, entities) for question in selected]
    answered = sum(1 for item in answers if item["status"] == "answered")
    return {
        "ok": bool(normalized),
        "text_chars": len(normalized),
        "answered": answered,
        "total": len(answers),
        "coverage_pct": round((answered / len(answers) * 100), 2) if answers else 0.0,
        "entities_counts": entities.get("counts") or {},
        "answers": answers,
    }


def _answer_one(text: str, question: LexOcrQuestion, entities: dict[str, Any]) -> dict[str, Any]:
    snippets: list[str] = []
    values: list[str] = []
    for pattern in question.patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = match.group(0).strip()
            if value and value not in values:
                values.append(value)
            snippets.append(_window(text, match.start(), match.end()))
            if len(snippets) >= 3:
                break
        if len(snippets) >= 3:
            break
    entity_answer = _entity_answer(question.id, entities)
    if entity_answer and entity_answer not in snippets:
        snippets.insert(0, entity_answer)
    status = "answered" if snippets else "missing_evidence"
    if status == "answered":
        answer = _compose_answer(question.id, snippets, values=values)
    else:
        answer = "Nel testo OCR non c'è evidenza sufficiente per rispondere senza inventare."
    return {
        "id": question.id,
        "question": question.question,
        "status": status,
        "answer": answer,
        "citations": snippets[:3],
    }


def _custom_questions(values: list[str]) -> list[LexOcrQuestion]:
    out: list[LexOcrQuestion] = []
    for index, raw in enumerate(values, start=1):
        question = str(raw or "").strip()
        if not question:
            continue
        keywords = [re.escape(token) for token in re.findall(r"\w{4,}", question.lower())[:4]]
        pattern = r".{0,100}(?:" + "|".join(keywords or [re.escape(question[:20])]) + r").{0,120}"
        out.append(LexOcrQuestion(f"custom_{index}", question, (pattern,)))
    return out


def _entity_answer(question_id: str, entities: dict[str, Any]) -> str:
    if question_id == "numero_ruolo" and entities.get("numero_ruolo"):
        item = entities["numero_ruolo"][0]
        return str(item.get("testo") or f"R.G. {item.get('numero')}/{item.get('anno')}").strip()
    if question_id == "ufficio" and entities.get("uffici"):
        return "; ".join(str(item) for item in entities["uffici"][:3])
    if question_id == "parti" and entities.get("parti"):
        item = entities["parti"][0]
        return f"{item.get('attore', '').strip()} contro {item.get('convenuto', '').strip()}".strip()
    if question_id == "date" and entities.get("date"):
        return "; ".join(str(item) for item in entities["date"][:5])
    if question_id == "norme" and entities.get("riferimenti"):
        return "; ".join(str(item) for item in entities["riferimenti"][:5])
    if question_id == "importi" and entities.get("importi"):
        return "; ".join(str(item) for item in entities["importi"][:5])
    return ""


def _compose_answer(question_id: str, snippets: list[str], *, values: list[str] | None = None) -> str:
    first = "; ".join(list(values or [])[:5]).strip() or snippets[0].strip()
    labels = {
        "numero_ruolo": "Il numero di ruolo emerge così",
        "ufficio": "L'ufficio indicato dal documento emerge così",
        "parti": "Le parti o i soggetti principali emergono così",
        "date": "Le date o scadenze rilevate sono",
        "norme": "I riferimenti normativi rilevati sono",
        "pec": "I riferimenti PEC/comunicazione rilevati sono",
        "importi": "Gli importi rilevati sono",
    }
    return f"{labels.get(question_id, 'Risposta fondata sul testo OCR')}: {first}"


def _window(text: str, start: int, end: int, *, radius: int = 140) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def _normalize(value: str) -> str:
    text = str(value or "").replace("\ufeff", "").replace("\r", "").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
