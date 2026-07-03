from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

LEGAL_REGEX_PACK_VERSION = "2026.05.24-legal-ocr-v1"

_CF_RE = re.compile(r"\b([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])\b", re.I)
_PEC_RE = re.compile(r"\b[A-Z0-9._%+\-']+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
_DATE_RE = re.compile(r"\b((?:0?[1-9]|[12][0-9]|3[01])[\-/\.](?:0?[1-9]|1[0-2])[\-/\.](?:18|19|20|21|22|23|24|25|26|27|28|29)[0-9]{2}|(?:18|19|20|21|22|23|24|25|26|27|28|29)[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b")
_PEC_DOMAINS = ("giustiziacert.it", "giustizia.it", "postacert.it")
_CF_CHECK = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ODD = dict(zip("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))
_EVEN = {str(i): i for i in range(10)} | {chr(ord("A") + i): i for i in range(26)}


@dataclass(frozen=True, slots=True)
class RegexFieldResult:
    id: str
    status: str
    value: str = ""
    values: tuple[str, ...] = ()
    tries: int = 1
    reason: str = ""
    rule_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {"id": self.id, "status": self.status, "tries": self.tries, "rule_id": self.rule_id, "reason": self.reason}
        if self.value:
            out["value"] = self.value
        if self.values:
            out["values"] = list(self.values)
        return out


def validate_codice_fiscale_persona_fisica(value: str) -> bool:
    cf = _remove_spaces(value).upper()
    if not re.fullmatch(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]", cf):
        return False
    total = sum((_ODD if idx % 2 else _EVEN).get(char, 0) for idx, char in enumerate(cf[:15], start=1))
    return _CF_CHECK[total % 26] == cf[-1]


def _remove_spaces(value: str) -> str:
    return "".join(str(value or "").split())


def _digits_only(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def validate_regex_pack(text: str, *, attempts: int = 1, now: date | None = None) -> dict[str, Any]:
    source = str(text or "")
    today = now or datetime.now(timezone.utc).date()
    cf_all = tuple(dict.fromkeys(m.group(1).upper() for m in _CF_RE.finditer(source)))
    cf_valid = tuple(v for v in cf_all if validate_codice_fiscale_persona_fisica(v))
    rg = tuple(dict.fromkeys(_extract_rg(source)))
    pec = tuple(dict.fromkeys(m.group(0).lower() for m in _PEC_RE.finditer(source) if _valid_pec(m.group(0))))
    dates, invalid_dates = _dates(source, today)
    amounts = tuple(dict.fromkeys(_extract_amounts(source)))
    fields = [
        _field("cf_avvocato", cf_valid, attempts, "cf.it.persona_fisica.v1", "Codice fiscale persona fisica valido non trovato."),
        _field("n_rg", rg, attempts, "procedimento.rg.v1", "Numero RG non trovato."),
        _field("pec", pec, attempts, "pec.rfc5322.justice.v1", "Indirizzo PEC valido non trovato."),
        _field("date", dates, attempts, "date.it.iso.plausibility.v1", "Date valide non trovate."),
        _field("importi", amounts, attempts, "amount.it.v1", "Importi in formato italiano non trovati."),
    ]
    if invalid_dates:
        fields.append(RegexFieldResult("date_plausibility", "fail", values=tuple(invalid_dates), tries=attempts, reason="Sono presenti date atto future o non plausibili.", rule_id="date.atto.not_future.v1"))
    return {"pack_version": LEGAL_REGEX_PACK_VERSION, "mandatory_fields": [f.to_dict() for f in fields], "matches": {"cf": list(cf_all), "cf_validi": list(cf_valid), "n_rg": list(rg), "pec": list(pec), "date": list(dates), "importi": list(amounts)}}


def _field(field_id: str, values: tuple[str, ...], attempts: int, rule_id: str, fail: str) -> RegexFieldResult:
    return RegexFieldResult(field_id, "ok" if values else "fail", values[0] if values else "", values, max(1, attempts), "Campo validato." if values else fail, rule_id)


def _extract_rg(source: str) -> list[str]:
    values: list[str] = []
    for start, end, n, y in _iter_rg_num_anno(source):
        prefix = source[max(0, start - 90) : start]
        if not _has_rg_context(prefix):
            continue
        if n and y:
            values.append(f"{n}/{y}")
    return values


def _iter_rg_num_anno(source: str):
    text = str(source or "")
    length = len(text)
    index = 0
    while index < length:
        if not text[index].isdigit() or (index > 0 and text[index - 1].isdigit()):
            index += 1
            continue
        num_start = index
        while index < length and text[index].isdigit() and index - num_start < 7:
            index += 1
        numero = text[num_start:index]
        if index < length and text[index].isdigit():
            continue
        cursor = _skip_spaces(text, index)
        if cursor >= length or text[cursor] != "/":
            continue
        cursor = _skip_spaces(text, cursor + 1)
        year_start = cursor
        while cursor < length and text[cursor].isdigit() and cursor - year_start < 4:
            cursor += 1
        anno = text[year_start:cursor]
        if len(anno) != 4 or anno[0] not in {"1", "2"}:
            continue
        if cursor < length and text[cursor].isdigit():
            continue
        yield num_start, cursor, numero, anno


def _skip_spaces(text: str, index: int) -> int:
    length = len(text)
    while index < length and text[index] in {" ", "\t"}:
        index += 1
    return index


def _has_rg_context(prefix: str) -> bool:
    normalized = " ".join(str(prefix or "").split()).lower()
    compact = "".join(ch for ch in normalized if ch.isalnum())
    if any(term in normalized for term in ("r.g", "r g", "ruolo generale", "reg gen", "reg. gen")):
        return True
    if any(marker in compact for marker in ("nrg", "rgn", "rgac", "rgciv", "rgtrib", "reggen", "ruologenerale")):
        return True
    return normalized.rstrip().endswith(("rg", "r.g", "r g"))


def _extract_amounts(source: str) -> list[str]:
    values: list[str] = []
    previous_was_currency = False
    for raw in str(source or "").replace("\n", " ").split():
        token = raw.strip(" \t\r\n.,;:()[]{}<>")
        lower = token.lower()
        if lower in {"eur", "euro", "€"}:
            previous_was_currency = True
            continue
        if _is_amount_token(token):
            values.append(_remove_spaces(token))
            previous_was_currency = False
            continue
        if previous_was_currency and _is_amount_token(token.lstrip("€")):
            values.append(_remove_spaces(token.lstrip("€")))
        previous_was_currency = False
    return values


def _is_amount_token(token: str) -> bool:
    value = _remove_spaces(token).lstrip("€")
    integer, sep, cents = value.partition(",")
    if sep != "," or len(cents) != 2 or not cents.isdigit() or not integer:
        return False
    if "." not in integer:
        return integer.isdigit()
    groups = integer.split(".")
    return (
        1 <= len(groups[0]) <= 3
        and groups[0].isdigit()
        and all(len(group) == 3 and group.isdigit() for group in groups[1:])
    )


def _valid_pec(value: str) -> bool:
    domain = str(value or "").lower().strip(".").rsplit("@", 1)[-1]
    return ".." not in value and re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) is not None and (domain.endswith(".pec.it") or "pec" in domain or any(domain == d or domain.endswith("." + d) for d in _PEC_DOMAINS))


def _dates(source: str, today: date) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ok: list[str] = []
    bad: list[str] = []
    for match in _DATE_RE.finditer(source):
        raw = match.group(1)
        parsed = _parse_date(raw)
        if not parsed or ("data atto" in source[max(0, match.start() - 30) : match.start()].lower() and parsed > today):
            bad.append(raw)
        else:
            ok.append(parsed.isoformat())
    return tuple(dict.fromkeys(ok)), tuple(dict.fromkeys(bad))


def _parse_date(value: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None
