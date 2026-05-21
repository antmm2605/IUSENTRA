from __future__ import annotations

from typing import Any

_DRAFT_TERMS = ("diffida", "messa in mora", "lettera", "pec", "sollecito", "contestazione")
_APPENDIX_MARKERS = ("Fonti consultate", "Dato certo", "Qualita della risposta", "Qualità della risposta")
_SECTION_BREAKS = (
    ("Spett.le", "\n\n**Spett.le**\n"),
    ("Oggetto:", "\n\n**Oggetto:** "),
    ("Con la presente,", "\n\nCon la presente,"),
    ("Fatto", "\n\n**Fatto**\n\n"),
    ("Diritto", "\n\n**Diritto**\n\n"),
    ("Richiesta formale", "\n\n**Richiesta formale**\n\n"),
    ("Si diffida", "\n\nSi diffida"),
    ("Avvertenza", "\n\n**Avvertenza**\n\n"),
    ("Con osservanza,", "\n\n---\n\nCon osservanza,"),
)


def looks_like_legal_draft(value: Any) -> bool:
    text = str(value or "").replace("\r", "").strip()
    lowered = text.casefold()
    if not lowered:
        return False
    if "diffida e messa in mora" in lowered or "dati da completare prima dell'invio" in lowered:
        return True
    if "dati da completare prima dell'invio" in lowered.replace("\u2019", "'"):
        return True
    bozza_at = lowered.find("bozza")
    return bozza_at >= 0 and any(term in lowered[bozza_at : bozza_at + 220] for term in _DRAFT_TERMS)


def strip_draft_source_appendix(value: Any) -> str:
    clean = str(value or "").replace("\r", "").strip()
    if not looks_like_legal_draft(clean):
        return clean
    return _cut_at_first_marker(clean, _APPENDIX_MARKERS).strip()


def normalize_legal_draft_layout(value: Any) -> str:
    """Impagina una bozza legale Lex anche quando il modello la restituisce piatta."""

    clean = strip_draft_source_appendix(value)
    if not looks_like_legal_draft(clean):
        return clean

    clean = _remove_prefix(clean, "Sintesi operativa")
    clean = _remove_prefix(clean, "Risposta:")
    clean = "\n\n---\n\n".join(part.strip() for part in clean.split("---"))
    clean = _normalize_title(clean)

    clean = _normalize_checklist(clean)
    clean = _split_flat_draft_sections(clean)
    clean = _normalize_checklist(clean)
    clean = _collapse_blank_lines(clean)
    clean = clean.replace("**Dati da completare prima dell'invio**\n- ", "**Dati da completare prima dell'invio**\n\n- ")
    clean = "\n".join(line.rstrip(" \t") for line in clean.split("\n"))
    return clean.strip()


def _normalize_checklist(value: str) -> str:
    clean = value
    clean = _replace_casefold(clean, "> **Dati da completare prima dell'invio:**", "\n\n**Dati da completare prima dell'invio**")
    clean = _replace_casefold(clean, "> **Dati da completare prima dell\u2019invio:**", "\n\n**Dati da completare prima dell'invio**")
    clean = _replace_casefold(clean, "Dati da completare prima dell'invio:", "\n\n**Dati da completare prima dell'invio**\n\n")
    clean = _replace_casefold(clean, "Dati da completare prima dell\u2019invio:", "\n\n**Dati da completare prima dell'invio**\n\n")
    clean = clean.replace("\n> - ", "\n- ").replace(" > - ", "\n- ")
    return clean


def _split_flat_draft_sections(value: str) -> str:
    clean = value
    clean = _break_before_date_followed_by_spett_le(clean)
    for token, replacement in _SECTION_BREAKS:
        clean = _replace_section_token(clean, token, replacement)
    clean = _break_before_numbered_items(clean)
    clean = _split_spett_le_address(clean)
    clean = _replace_casefold(clean, "Con osservanza, Avv.", "Con osservanza,\n\nAvv.")
    return clean


def _cut_at_first_marker(value: str, markers: tuple[str, ...]) -> str:
    lowered = value.casefold()
    positions = [lowered.find(marker.casefold()) for marker in markers]
    valid = [position for position in positions if position >= 0]
    return value[: min(valid)] if valid else value


def _remove_prefix(value: str, prefix: str) -> str:
    clean = value.lstrip()
    return clean[len(prefix):].lstrip() if clean.casefold().startswith(prefix.casefold()) else value


def _replace_casefold(value: str, needle: str, replacement: str) -> str:
    if not needle:
        return value
    result = value
    lowered_needle = needle.casefold()
    while True:
        lowered = result.casefold()
        index = lowered.find(lowered_needle)
        if index < 0:
            return result
        result = f"{result[:index]}{replacement}{result[index + len(needle):]}"


def _replace_section_token(value: str, token: str, replacement: str) -> str:
    result = value
    lowered_token = token.casefold()
    search_from = 0
    while search_from < len(result):
        lowered = result.casefold()
        index = lowered.find(lowered_token, search_from)
        if index < 0:
            return result
        end = index + len(token)
        before_ok = index == 0 or result[index - 1].isspace()
        after_ok = end >= len(result) or result[end].isspace()
        if before_ok and after_ok:
            left = result[:index].rstrip()
            right = result[end:].lstrip()
            result = f"{left}{replacement}{right}"
            search_from = len(left) + len(replacement) + 1
            continue
        search_from = end
    return result


def _normalize_title(value: str) -> str:
    clean = value.lstrip()
    first, separator, rest = clean.partition("\n")
    title = first.strip().strip("*").strip()
    lowered = title.casefold()
    if not lowered.startswith("bozza") or not any(term in lowered for term in _DRAFT_TERMS):
        return value
    remainder = rest.lstrip("-\n ")
    return f"**{title}**\n\n---\n\n{remainder}" if separator else f"**{title}**\n\n---"


def _collapse_blank_lines(value: str) -> str:
    lines: list[str] = []
    blank = 0
    for line in value.split("\n"):
        if line.strip():
            blank = 0
            lines.append(line)
            continue
        blank += 1
        if blank <= 1:
            lines.append("")
    return "\n".join(lines)


def _break_before_date_followed_by_spett_le(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        parsed = _parse_italian_date_at(value, index)
        if parsed is None:
            out.append(value[index])
            index += 1
            continue
        date_text, end_index = parsed
        lookahead = end_index
        while lookahead < len(value) and value[lookahead].isspace():
            lookahead += 1
        if value[lookahead : lookahead + len("Spett.le")].casefold() == "spett.le":
            if out and not "".join(out[-2:]).endswith("\n\n"):
                out.append("\n\n")
            out.append(date_text)
            out.append("\n\n")
            index = end_index
            continue
        out.append(value[index])
        index += 1
    return "".join(out)


def _break_before_numbered_items(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        if (
            value[index].isspace()
            and index + 3 < len(value)
            and value[index + 1].isdigit()
            and value[index + 1] != "0"
            and value[index + 2] in {".", ")"}
            and value[index + 3].isspace()
        ):
            out.append("\n")
            index += 1
            continue
        out.append(value[index])
        index += 1
    return "".join(out)


def _parse_italian_date_at(value: str, index: int) -> tuple[str, int] | None:
    if index > 0 and not value[index - 1].isspace():
        return None
    start = index
    for size in (1, 2):
        day_end = start + size
        if day_end >= len(value) or not value[start:day_end].isdigit() or value[day_end] != "/":
            continue
        month_start = day_end + 1
        for month_size in (1, 2):
            month_end = month_start + month_size
            year_start = month_end + 1
            year_end = year_start + 4
            if (
                month_end < len(value)
                and value[month_start:month_end].isdigit()
                and value[month_end] == "/"
                and year_end <= len(value)
                and value[year_start:year_end].isdigit()
                and (year_end == len(value) or value[year_end].isspace())
            ):
                return value[start:year_end], year_end
    return None


def _split_spett_le_address(value: str) -> str:
    marker = "**Spett.le**\n"
    address_start = value.find("[Indirizzo")
    if marker not in value or address_start < 0:
        address_start = value.find("[indirizzo")
    if marker in value and address_start >= 0 and "\n" not in value[value.find(marker) + len(marker) : address_start]:
        return f"{value[:address_start].rstrip()}\n{value[address_start:]}"
    return value
