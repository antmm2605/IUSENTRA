"""Compattazione deterministica dei contesti Lex prima del modello.

Il modulo è una reimplementazione pulita del pattern TokenJuice: riduce HTML,
OCR, PDF già estratti, log e JSON lunghi senza chiamare LLM e senza navigare il
web. La regola centrale è conservare ancoraggi legali verificabili: norme,
R.G., date, atti, fonte e passaggi con valore giuridico.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any


TOKENJUICE_SCHEMA = "iusentra.lex_tokenjuice.v1"


_NORM_RE = re.compile(
    r"\bart\.?\s*\d+(?:[- bisterquater]*\d*)?"
    r"(?:\s*,?\s*(?:co\.?|comma)\s*\d+)?"
    r"(?:\s+(?:c\.p\.p\.|c\.p\.|c\.p\.c\.|c\.c\.|cost\.|cod\. proc\. pen\.|cod\. pen\.|cod\. civ\.))?",
    re.I,
)
_RG_RE = re.compile(r"\b(?:R\.?\s*G\.?|ricorso)\s*(?:n\.?|num\.?)?\s*\d{1,8}\s*/\s*(?:19|20)\d{2}\b", re.I)
_DATE_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}\b|"
    r"\b\d{1,2}\s+"
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(?:19|20)\d{2}\b",
    re.I,
)
_LEGAL_KEYWORDS = (
    "cassazione",
    "corte",
    "sentenza",
    "ordinanza",
    "questione",
    "ricorso",
    "udienza",
    "deposito",
    "relatore",
    "pena",
    "motivo",
    "censura",
    "principio",
    "massima",
    "norma",
    "dispositivo",
)
_BLOCK_TAGS = {"article", "aside", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr"}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas"}


@dataclass(frozen=True, slots=True)
class LexTokenJuiceResult:
    schema: str
    rule_id: str
    source_type: str
    text: str
    original_chars: int
    compressed_chars: int
    reduction_ratio: float
    anchors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["anchors"] = list(self.anchors)
        payload["warnings"] = list(self.warnings)
        if not include_text:
            payload.pop("text", None)
        return _compact(payload)


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if name in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if name in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = str(data or "").strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return _normalise_text(" ".join(self.parts))


def compress_lex_context(
    value: Any,
    *,
    source_type: str = "",
    max_chars: int = 4000,
    min_chars: int = 400,
) -> LexTokenJuiceResult:
    """Compatta un contesto lungo preservando gli ancoraggi legali.

    `max_chars` è il tetto deterministico del testo restituito. Se il contenuto
    è già più piccolo, viene normalizzato ma non tagliato.
    """

    original = str(value or "")
    source = _normalise_source_type(source_type)
    rule_id = _choose_rule(original, source)
    prepared, warnings = _prepare_text(original, rule_id=rule_id)
    anchors = tuple(_extract_anchors(prepared))
    max_chars = max(240, int(max_chars or 4000))
    min_chars = max(80, min(int(min_chars or 400), max_chars))

    if len(prepared) <= max_chars:
        compressed = prepared
        applied_rule = f"{rule_id}:normalizzato"
    else:
        compressed = _compress_long_text(prepared, anchors=anchors, max_chars=max_chars, min_chars=min_chars)
        applied_rule = f"{rule_id}:compattato"

    ratio = 1.0
    if len(original) > 0:
        ratio = round(len(compressed) / len(original), 4)
    return LexTokenJuiceResult(
        schema=TOKENJUICE_SCHEMA,
        rule_id=applied_rule,
        source_type=source or rule_id,
        text=compressed,
        original_chars=len(original),
        compressed_chars=len(compressed),
        reduction_ratio=ratio,
        anchors=anchors[:40],
        warnings=tuple(warnings),
        metadata={
            "deterministic": True,
            "llm_used": False,
            "web_used": False,
            "max_chars": max_chars,
        },
    )


def tokenjuice_metadata(result: LexTokenJuiceResult, *, include_text_when_shorter: bool = True) -> dict[str, Any]:
    payload = result.to_dict(include_text=False)
    if include_text_when_shorter and result.compressed_chars < result.original_chars:
        payload["compressed_text"] = result.text
    return payload


def _prepare_text(original: str, *, rule_id: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    text = str(original or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    if rule_id == "html":
        parser = _HtmlTextExtractor()
        parser.feed(text)
        text = parser.text()
        warnings.append("html ripulito da script, stili e markup")
    elif rule_id == "json":
        text = _normalise_json(text)
    elif rule_id == "log":
        text = _normalise_log(text)
    else:
        text = _normalise_legal_text(text)
        if _looks_ocr_dirty(text):
            warnings.append("testo OCR potenzialmente sporco: usare sintesi prudente")
    return _dedupe_lines(text), warnings


def _compress_long_text(text: str, *, anchors: tuple[str, ...], max_chars: int, min_chars: int) -> str:
    lines = _ranked_lines(text)
    head_budget = max(min_chars, int(max_chars * 0.24))
    tail_budget = max(min_chars // 2, int(max_chars * 0.16))
    anchor_budget = max(min_chars, int(max_chars * 0.36))
    remaining_budget = max_chars - head_budget - tail_budget
    anchor_lines = _anchor_lines(text, anchors=anchors)
    if anchors or anchor_lines:
        anchor_source = "\n".join(_dedupe_sequence(list(anchors) + anchor_lines))
        anchor_block = _take_chars(anchor_source, anchor_budget)
        remaining_budget = max(0, max_chars - len(anchor_block) - head_budget - tail_budget)
    else:
        anchor_block = ""
    relevant_block = _take_chars("\n".join(lines), max(0, remaining_budget))
    head = _take_chars(text, head_budget)
    tail = _take_tail_chars(text, tail_budget)
    sections = [
        ("Inizio documento", head),
        ("Ancoraggi conservati", anchor_block),
        ("Passaggi rilevanti", relevant_block),
        ("Fine documento", tail),
    ]
    return _fit_sections(sections, max_chars=max_chars)


def _ranked_lines(text: str) -> list[str]:
    rows = []
    for index, line in enumerate(_lines(text)):
        score = _line_score(line)
        if score > 0:
            rows.append((score, index, line))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [line for _, _, line in rows[:60]]


def _anchor_lines(text: str, *, anchors: tuple[str, ...]) -> list[str]:
    if not anchors:
        return []
    lowered_anchors = [anchor.lower() for anchor in anchors]
    found: list[str] = []
    for line in _lines(text):
        lowered = line.lower()
        if any(anchor in lowered for anchor in lowered_anchors) and line not in found:
            found.append(line)
        if len(found) >= 32:
            break
    return found


def _line_score(line: str) -> int:
    lowered = line.lower()
    score = 0
    score += 8 * len(_extract_norms(line))
    score += 12 * len(_extract_rg_refs(line))
    score += 3 * len(_extract_dates(line))
    score += sum(3 for keyword in _LEGAL_KEYWORDS if keyword in lowered)
    if 80 <= len(line) <= 800:
        score += 2
    if _looks_ocr_dirty(line):
        score -= 3
    return score


def _fit_sections(sections: list[tuple[str, str]], *, max_chars: int) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for title, body in sections:
        value = _normalise_text(body)
        if not value or value in seen:
            continue
        seen.add(value)
        parts.append(f"{title}:\n{value}")
    payload = "\n\n".join(parts).strip()
    if len(payload) <= max_chars:
        return payload
    return payload[: max(0, max_chars - 1)].rstrip() + "…"


def _choose_rule(text: str, source_type: str) -> str:
    lowered = str(text or "")[:2000].lower()
    source = source_type.lower()
    if "html" in source or "<html" in lowered or "<body" in lowered or "</p>" in lowered:
        return "html"
    if "json" in source or _looks_like_json(text):
        return "json"
    if "log" in source or "traceback" in lowered or "error" in source:
        return "log"
    if "pdf" in source or "ocr" in source or _looks_ocr_dirty(text):
        return "legal_ocr"
    return "legal_text"


def _normalise_source_type(value: str) -> str:
    return " ".join(str(value or "").lower().replace(";", " ").split())


def _normalise_json(text: str) -> str:
    try:
        payload = json.loads(text)
    except Exception:
        return _normalise_text(text)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ": "))


def _normalise_log(text: str) -> str:
    lines = []
    for line in _lines(text):
        lowered = line.lower()
        if any(token in lowered for token in ("error", "warning", "traceback", "exception", "failed", "timeout")):
            lines.append(line)
    tail = _lines(text)[-40:]
    return "\n".join(_dedupe_sequence(lines + tail))


def _normalise_legal_text(text: str) -> str:
    value = re.sub(r"([A-Za-zÀ-ÿ])-\n([A-Za-zÀ-ÿ])", r"\1\2", text)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return _normalise_text(value)


def _normalise_text(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", text) if part.strip()]
    return "\n\n".join(paragraphs).strip()


def _dedupe_lines(text: str) -> str:
    return "\n".join(_dedupe_sequence(_lines(text)))


def _dedupe_sequence(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for line in lines:
        key = _normalise_text(line).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(line)
    return rows


def _lines(text: str) -> list[str]:
    rows: list[str] = []
    for paragraph in str(text or "").splitlines():
        value = " ".join(paragraph.split()).strip()
        if value:
            rows.append(value)
    if not rows:
        normalized = _normalise_text(text)
        return [normalized] if normalized else []
    return rows


def _extract_anchors(text: str) -> list[str]:
    anchors: list[str] = []
    for extractor in (_extract_norms, _extract_rg_refs, _extract_dates):
        for value in extractor(text):
            if value and value.lower() not in {anchor.lower() for anchor in anchors}:
                anchors.append(value)
    return anchors


def _extract_norms(text: str) -> list[str]:
    found: list[str] = []
    for match in _NORM_RE.finditer(str(text or "")):
        value = " ".join(match.group(0).replace("Art ", "art. ").split()).strip(" .;,")
        if value and value not in found:
            found.append(value)
    return found[:60]


def _extract_rg_refs(text: str) -> list[str]:
    found: list[str] = []
    for match in _RG_RE.finditer(str(text or "")):
        value = _normalise_rg(match.group(0))
        if value and value not in found:
            found.append(value)
    return found[:40]


def _extract_dates(text: str) -> list[str]:
    found: list[str] = []
    for match in _DATE_RE.finditer(str(text or "")):
        value = " ".join(match.group(0).split()).strip()
        if value and value not in found:
            found.append(value)
    return found[:40]


def _normalise_rg(value: str) -> str:
    match = re.search(r"(\d{1,8})\s*/\s*((?:19|20)\d{2})", str(value or ""))
    if not match:
        return " ".join(str(value or "").split()).strip()
    return f"R.G. {match.group(1)}/{match.group(2)}"


def _looks_like_json(text: str) -> bool:
    value = str(text or "").lstrip()
    return (value.startswith("{") and value.rstrip().endswith("}")) or (value.startswith("[") and value.rstrip().endswith("]"))


def _looks_ocr_dirty(text: str) -> bool:
    value = str(text or "")
    if value.count("|") >= 3:
        return True
    return bool(re.search(r"(?:\b[a-zA-Z]\s*\|\s*[a-zA-Z]\b|[^\w\s]{8,})", value[:5000]))


def _take_chars(text: str, max_chars: int) -> str:
    value = _normalise_text(text)
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)].rstrip() + "…"


def _take_tail_chars(text: str, max_chars: int) -> str:
    value = _normalise_text(text)
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return "…" + value[-max(0, max_chars - 1) :].lstrip()


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {}, ())}
