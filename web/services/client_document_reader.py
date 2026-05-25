"""Lettura documento in memoria per la nuova anagrafica cliente."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage

from core.security.upload_validator import validate_upload

ALLOWED_CLIENT_DOCUMENT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")
ALLOWED_CLIENT_DOCUMENT_MIME_TYPES = ("application/pdf", "image/png", "image/jpeg")
MAX_CLIENT_DOCUMENT_MB = 12

FIELD_LABELS: dict[str, str] = {
    "codice_fiscale": "codice fiscale",
    "cognome": "cognome",
    "nome": "nome",
    "sesso": "sesso",
    "data_nascita": "data di nascita",
    "luogo_nascita": "luogo di nascita",
    "provincia_nascita": "provincia di nascita",
    "nazionalita": "nazionalità",
    "doc_tipo": "tipo documento",
    "doc_numero": "numero documento",
    "doc_rilasciato_da": "rilasciato da",
    "doc_data_rilascio": "data rilascio",
    "doc_data_scadenza": "data scadenza",
    "via": "via",
    "civico": "civico",
    "cap": "CAP",
    "comune": "comune",
    "provincia": "provincia",
    "nazione": "nazione",
    "telefono": "telefono",
    "cellulare": "cellulare",
    "email": "email",
    "pec": "PEC",
}

EXPECTED_FIELDS = (
    "nome",
    "cognome",
    "codice_fiscale",
    "data_nascita",
    "luogo_nascita",
    "provincia_nascita",
    "doc_numero",
    "doc_data_scadenza",
)


class ClientDocumentReaderError(ValueError):
    """Errore recuperabile nella lettura del documento cliente."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def read_client_document_upload(upload: FileStorage | None) -> dict[str, Any]:
    if upload is None or not getattr(upload, "filename", ""):
        raise ClientDocumentReaderError("Seleziona un PDF o un'immagine del documento.")
    filename = str(upload.filename or "documento")
    content = upload.read()
    validation = validate_upload(
        filename,
        content,
        allowed_extensions=ALLOWED_CLIENT_DOCUMENT_EXTENSIONS,
        allowed_mime_types=ALLOWED_CLIENT_DOCUMENT_MIME_TYPES,
        max_size_mb=MAX_CLIENT_DOCUMENT_MB,
    )
    if not validation.ok:
        raise ClientDocumentReaderError(validation.error or "Documento non leggibile.")
    return read_client_document_bytes(
        content,
        validation.safe_filename or Path(filename).name,
        mime_type=validation.mime_type,
    )


def read_client_document_bytes(content: bytes, filename: str, *, mime_type: str = "") -> dict[str, Any]:
    text, warning = _extract_text(content, filename)
    return parse_client_document_text(
        text,
        filename=filename,
        mime_type=mime_type,
        warnings=[warning] if warning else [],
    )


def parse_client_document_text(
    text: str,
    *,
    filename: str = "documento",
    mime_type: str = "",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    clean_text = _normalize_text(text)
    fields: dict[str, dict[str, Any]] = {}
    mrz = _parse_mrz_from_text(clean_text)
    for field, value in (mrz.get("patch") or {}).items():
        _remember_field(fields, field, value, 0.97, "zona MRZ")
    for field, value, confidence in _extract_visible_fields(clean_text):
        _remember_field(fields, field, value, confidence, "testo documento")

    patch = {
        key: str(row["value"])
        for key, row in fields.items()
        if str(row.get("value") or "").strip() and float(row.get("confidence") or 0) >= 0.78
    }
    missing = [FIELD_LABELS[key] for key in EXPECTED_FIELDS if key not in patch]
    field_rows = [
        {
            "name": key,
            "label": FIELD_LABELS.get(key, key),
            "value": row["value"],
            "confidence": row["confidence"],
            "source": row["source"],
            "status": "affidabile" if float(row.get("confidence") or 0) >= 0.78 else "da verificare",
        }
        for key, row in sorted(fields.items(), key=lambda item: FIELD_LABELS.get(item[0], item[0]))
    ]
    all_warnings = list(warnings or [])
    if not clean_text:
        all_warnings.append("Il testo non è stato estratto dal documento. Verifica qualità della scansione o lingua OCR installata.")
    if not patch:
        message = "Non ho trovato dati anagrafici affidabili nel documento."
    elif missing:
        message = "Dati documento letti. Alcuni campi non risultano presenti o abbastanza chiari."
    else:
        message = "Dati documento letti e pronti per la compilazione."
    return {
        "ok": bool(patch),
        "message": message,
        "source": "lettore_documento_cliente",
        "filename": Path(filename).name,
        "mime_type": mime_type,
        "patch": patch,
        "fields": field_rows,
        "missing": missing,
        "warnings": all_warnings,
        "mrz": {"detected": bool(mrz.get("detected")), "type": mrz.get("type") or ""},
    }


def _extract_text(content: bytes, filename: str) -> tuple[str, str]:
    try:
        from pct.ocr import estrai_testo

        return str(estrai_testo(content, filename, lang="ita") or ""), ""
    except Exception:  # pragma: no cover
        return "", "Lettura automatica non completata. Verifica il formato del file o la qualità della scansione."


def _normalize_text(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _remember_field(fields: dict[str, dict[str, Any]], field: str, value: Any, confidence: float, source: str) -> None:
    clean = _clean_value(field, str(value or ""))
    if not clean:
        return
    previous = fields.get(field)
    if previous and float(previous.get("confidence") or 0) >= confidence:
        return
    fields[field] = {"value": clean, "confidence": round(float(confidence), 2), "source": source}


def _clean_value(field: str, value: str) -> str:
    clean = re.sub(r"\s+", " ", str(value or "").replace("<", " ")).strip(" :-")
    if not clean:
        return ""
    if field in {"codice_fiscale", "provincia_nascita", "provincia"}:
        limit = 16 if field == "codice_fiscale" else 2
        return re.sub(r"[^A-Z0-9]", "", clean.upper())[:limit]
    if field in {"nome", "cognome", "luogo_nascita", "comune"}:
        return _title_case(clean)
    if field == "sesso":
        return _normalize_sex(clean)
    if field == "nazionalita":
        return _normalize_nationality(clean)
    if field == "doc_tipo":
        return _normalize_document_type(clean)
    if field in {"data_nascita", "doc_data_rilascio", "doc_data_scadenza"}:
        purpose = "birth" if field == "data_nascita" else "expiry" if field == "doc_data_scadenza" else "generic"
        return _parse_date(clean, purpose)
    if field in {"email", "pec"}:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", clean, flags=re.I)
        return match.group(0).lower() if match else ""
    return clean.strip()


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "").lower().split())


def _normalize_key(value: str) -> str:
    replacements = str.maketrans("àèéìòù", "aeeiou")
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower().translate(replacements))


def _normalize_sex(value: str) -> str:
    raw = _normalize_key(value)
    if raw in {"m", "male", "maschio", "maschile"}:
        return "M"
    if raw in {"f", "female", "femmina", "femminile"}:
        return "F"
    return ""


def _normalize_nationality(value: str) -> str:
    raw = _normalize_key(value)
    if raw in {"ita", "italia", "italiana", "italiano", "italian"}:
        return "Italiana"
    return _title_case(value)


def _normalize_document_type(value: str) -> str:
    raw = _normalize_key(value)
    if "pass" in raw:
        return "PASSAPORTO"
    if "patente" in raw:
        return "PATENTE"
    if "soggiorno" in raw:
        return "PERMESSO_SOGGIORNO"
    if "ident" in raw or raw.startswith("i"):
        return "CARTA_IDENTITA"
    return value.upper()


def _parse_date(value: str, purpose: str = "generic") -> str:
    raw = str(value or "").strip()
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", raw)
    if iso:
        return _valid_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    italian = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})\b", raw)
    if italian:
        year = int(italian.group(3))
        if year < 100:
            year = _two_digit_year(year, purpose)
        return _valid_date(year, int(italian.group(2)), int(italian.group(1)))
    if re.fullmatch(r"\d{6}", raw):
        return _valid_date(_two_digit_year(int(raw[:2]), purpose), int(raw[2:4]), int(raw[4:6]))
    compact = re.search(r"\b(\d{4})(\d{2})(\d{2})\b", raw)
    if compact:
        return _valid_date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))
    return ""


def _two_digit_year(year: int, purpose: str) -> int:
    current = date.today().year
    century = current // 100 * 100
    full = century + year
    if purpose == "birth":
        return full - 100 if full > current else full
    if purpose == "expiry":
        return full + 100 if full < current - 30 else full
    return full - 100 if full > current + 30 else full


def _valid_date(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _parse_mrz_from_text(text: str) -> dict[str, Any]:
    lines = [_clean_mrz_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and "<" in line and len(line) >= 24]
    for index in range(len(lines) - 1):
        first, second = lines[index], lines[index + 1]
        if first.startswith("P") and len(first) >= 40 and len(second) >= 40:
            return {"detected": True, "type": "PASSAPORTO", "patch": _parse_td3(first[:44], second[:44])}
        if first[:1] in {"I", "A", "C"} and len(first) >= 34 and len(second) >= 34:
            return {"detected": True, "type": "DOCUMENTO", "patch": _parse_td2(first[:36], second[:36])}
    for index in range(len(lines) - 2):
        first, second, third = lines[index], lines[index + 1], lines[index + 2]
        if first[:1] in {"I", "A", "C"} and len(first) >= 28 and len(second) >= 28 and len(third) >= 24:
            return {"detected": True, "type": "CARTA_IDENTITA", "patch": _parse_td1(first[:30], second[:30], third[:30])}
    return {"detected": False, "type": "", "patch": {}}


def _clean_mrz_line(line: str) -> str:
    return re.sub(r"[^A-Z0-9<]", "", str(line or "").upper())


def _parse_td3(line1: str, line2: str) -> dict[str, str]:
    patch = _parse_mrz_names(line1[5:])
    patch.update({
        "doc_tipo": "PASSAPORTO",
        "doc_numero": line2[:9].replace("<", ""),
        "nazionalita": line2[10:13],
        "data_nascita": line2[13:19],
        "sesso": line2[20:21],
        "doc_data_scadenza": line2[21:27],
    })
    return patch


def _parse_td2(line1: str, line2: str) -> dict[str, str]:
    patch = _parse_mrz_names(line1[5:])
    patch.update({
        "doc_tipo": "CARTA_IDENTITA",
        "doc_numero": line2[:9].replace("<", ""),
        "nazionalita": line2[10:13],
        "data_nascita": line2[13:19],
        "sesso": line2[20:21],
        "doc_data_scadenza": line2[21:27],
    })
    cf = _find_cf(f"{line1} {line2}")
    if cf:
        patch["codice_fiscale"] = cf
    return patch


def _parse_td1(line1: str, line2: str, line3: str) -> dict[str, str]:
    patch = _parse_mrz_names(line3)
    patch.update({
        "doc_tipo": "CARTA_IDENTITA",
        "doc_numero": line1[5:14].replace("<", ""),
        "data_nascita": line2[:6],
        "sesso": line2[7:8],
        "doc_data_scadenza": line2[8:14],
        "nazionalita": line2[15:18],
    })
    cf = _find_cf(f"{line1} {line2}")
    if cf:
        patch["codice_fiscale"] = cf
    return patch


def _parse_mrz_names(segment: str) -> dict[str, str]:
    surname, _, names = str(segment or "").partition("<<")
    return {"cognome": surname.replace("<", " "), "nome": names.replace("<", " ")}


def _extract_visible_fields(text: str) -> list[tuple[str, str, float]]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    flattened = "\n".join(lines)
    upper = flattened.upper()
    found: list[tuple[str, str, float]] = []

    cf = _find_cf(upper)
    if cf:
        found.append(("codice_fiscale", cf, 0.96))
    if re.search(r"CARTA\s+D[’']?IDENT|IDENTITY\s+CARD", upper):
        found.append(("doc_tipo", "CARTA_IDENTITA", 0.9))
    elif re.search(r"\bPASSAPORT", upper):
        found.append(("doc_tipo", "PASSAPORTO", 0.9))
    elif re.search(r"\bPATENTE\b", upper):
        found.append(("doc_tipo", "PATENTE", 0.86))

    for field, labels, confidence in (
        ("cognome", ("COGNOME", "SURNAME"), 0.88),
        ("nome", ("NOME", "GIVEN NAME", "GIVEN NAMES"), 0.88),
        ("sesso", ("SESSO", "SEX"), 0.86),
        ("nazionalita", ("NAZIONALITA", "NAZIONALITÀ", "CITTADINANZA", "NATIONALITY"), 0.84),
        ("doc_numero", ("NUMERO DOCUMENTO", "DOCUMENTO N", "N DOCUMENTO", "DOCUMENT NUMBER"), 0.82),
        ("doc_rilasciato_da", ("RILASCIATO DA", "AUTORITA", "AUTORITÀ", "ISSUED BY"), 0.8),
    ):
        value = _line_value(lines, labels)
        if value:
            found.append((field, value, confidence))

    found.extend(_birth_from_text(flattened))
    for field, labels, purpose, confidence in (
        ("data_nascita", ("DATA DI NASCITA", "NATO IL", "NATA IL", "DATE OF BIRTH"), "birth", 0.9),
        ("doc_data_rilascio", ("DATA RILASCIO", "RILASCIATO IL", "ISSUED ON"), "generic", 0.82),
        ("doc_data_scadenza", ("DATA SCADENZA", "SCADENZA", "VALIDA FINO AL", "VALIDO FINO AL", "EXPIRY", "EXPIRES"), "expiry", 0.9),
    ):
        value = _date_after_labels(flattened, labels, purpose)
        if value:
            found.append((field, value, confidence))

    found.extend(_address_from_text(lines))
    email = _find_email(flattened)
    if email:
        found.append(("email", email, 0.82))
    pec = _find_labelled_email(flattened, ("PEC", "POSTA CERTIFICATA"))
    if pec:
        found.append(("pec", pec, 0.84))
    phone = _line_value(lines, ("TELEFONO", "TEL", "PHONE"))
    if phone:
        found.append(("telefono", phone, 0.8))
    mobile = _line_value(lines, ("CELLULARE", "MOBILE"))
    if mobile:
        found.append(("cellulare", mobile, 0.8))
    return found


def _line_value(lines: list[str], labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    for index, line in enumerate(lines):
        match = re.search(rf"\b(?:{label_pattern})\b\s*(?:[:\-\.]|N[.°])?\s*(.+)$", line, flags=re.I)
        if match:
            value = _trim_value(match.group(1))
            if value and _normalize_key(value) not in {_normalize_key(label) for label in labels}:
                return value
        if re.fullmatch(rf"\s*(?:{label_pattern})\s*", line, flags=re.I) and index + 1 < len(lines):
            return _trim_value(lines[index + 1])
    return ""


def _trim_value(value: str) -> str:
    clean = re.split(
        r"\b(?:NOME|COGNOME|SESSO|SEX|DATA|NATO|NATA|LUOGO|SCADENZA|RILASCIO|RESIDENZA|INDIRIZZO|NAZIONALIT[ÀA])\b",
        str(value or "").strip(" :-"),
        maxsplit=1,
        flags=re.I,
    )[0]
    return clean.strip(" :-")


def _birth_from_text(text: str) -> list[tuple[str, str, float]]:
    found: list[tuple[str, str, float]] = []
    match = re.search(
        r"\bNAT[OA]\s+A\s+([A-ZÀ-Ü' -]{2,60}?)(?:\s*\(([A-Z]{2})\)|\s+([A-Z]{2}))?\s+(?:IL\s+)?(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        text,
        flags=re.I,
    )
    if match:
        found.append(("luogo_nascita", match.group(1), 0.88))
        province = match.group(2) or match.group(3)
        if province:
            found.append(("provincia_nascita", province, 0.9))
        found.append(("data_nascita", match.group(4), 0.9))
    place = re.search(r"\bLUOGO\s+DI\s+NASCITA\s*[:\-]?\s*([A-ZÀ-Ü' -]{2,60}?)(?:\s*\(([A-Z]{2})\)|\s+([A-Z]{2})\b)", text, flags=re.I)
    if place:
        found.append(("luogo_nascita", place.group(1), 0.86))
        province = place.group(2) or place.group(3)
        if province:
            found.append(("provincia_nascita", province, 0.88))
    return found


def _date_after_labels(text: str, labels: tuple[str, ...], purpose: str) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:\-]?\s*(\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})", text, flags=re.I)
    return _parse_date(match.group(1), purpose) if match else ""


def _address_from_text(lines: list[str]) -> list[tuple[str, str, float]]:
    for line in lines:
        if not re.search(r"\b(?:RESIDENZA|INDIRIZZO|ADDRESS)\b", line, flags=re.I):
            continue
        value = re.sub(r"^.*?\b(?:RESIDENZA|INDIRIZZO|ADDRESS)\b\s*[:\-]?", "", line, flags=re.I).strip()
        match = re.search(r"(.+?)\s+(\d+[A-Z]?)\s*,?\s*(\d{5})\s+(.+?)\s+\(?([A-Z]{2})\)?$", value, flags=re.I)
        if not match:
            continue
        return [
            ("via", match.group(1), 0.8),
            ("civico", match.group(2), 0.8),
            ("cap", match.group(3), 0.82),
            ("comune", match.group(4), 0.78),
            ("provincia", match.group(5), 0.82),
            ("nazione", "Italia", 0.8),
        ]
    return []


def _find_cf(text: str) -> str:
    match = re.search(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", str(text or "").upper())
    return match.group(0) if match else ""


def _find_email(text: str) -> str:
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", str(text or ""), flags=re.I)
    return match.group(0).lower() if match else ""


def _find_labelled_email(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"\b(?:{label_pattern})\b\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{{2,}})", text, flags=re.I)
    return match.group(1).lower() if match else ""
