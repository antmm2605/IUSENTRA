"""Validazione dei record di staging del Migration Center.

Regole minime per evitare di importare dati incompleti o errati: campi
obbligatori per tipo, codice fiscale verificato, date e importi parsabili.
I record con errori restano "invalid" e non vengono mai committati.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .base import RecordKind, RecordStatus, StagedRecord, ValidationIssue

_REQUIRED: dict[RecordKind, tuple[str, ...]] = {
    RecordKind.CLIENTE: ("nome",),
    RecordKind.SOGGETTO: ("nome",),
    RecordKind.FASCICOLO: ("titolo",),
    RecordKind.SCADENZA: ("descrizione", "data"),
    RecordKind.FATTURA: ("numero", "importo"),
    RecordKind.DOCUMENTO: ("filename",),
}

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")


def _is_date(value: str) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


def _is_importo(value: Any) -> bool:
    text = str(value if value is not None else "").strip().replace("€", "").replace(" ", "")
    if not text:
        return False
    # Accetta formati IT (1.234,56) e tecnici (1234.56).
    text = text.replace(".", "").replace(",", ".") if re.search(r",\d{1,2}$", text) else text.replace(",", "")
    try:
        float(text)
        return True
    except ValueError:
        return False


def _cf_valido(cf: str) -> bool:
    cf = str(cf or "").strip().upper()
    if not cf:
        return True  # CF assente: non è un errore bloccante (solo warning altrove)
    try:
        from pct.codice_fiscale import decodifica

        return decodifica(cf) is not None
    except Exception:
        return bool(re.fullmatch(r"[A-Z0-9]{16}", cf))


def validate_record(record: StagedRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    data = record.data or {}
    for required in _REQUIRED.get(record.kind, ()):  # campi obbligatori per tipo
        if not str(data.get(required) or "").strip():
            issues.append(ValidationIssue(required, f"Campo obbligatorio mancante: {required}.", "error"))

    cf = data.get("codice_fiscale") or data.get("cf")
    if cf and not _cf_valido(str(cf)):
        issues.append(ValidationIssue("codice_fiscale", "Codice fiscale non valido.", "error"))

    if record.kind == RecordKind.SCADENZA and data.get("data") and not _is_date(str(data.get("data"))):
        issues.append(ValidationIssue("data", "Data scadenza non in formato riconosciuto.", "error"))

    if record.kind == RecordKind.FATTURA and data.get("importo") and not _is_importo(data.get("importo")):
        issues.append(ValidationIssue("importo", "Importo fattura non numerico.", "error"))

    return issues


def apply_validation(records: list[StagedRecord]) -> None:
    """Valuta ogni record e ne aggiorna issues/status (in-place)."""

    for record in records:
        record.issues = validate_record(record)
        if record.has_errors:
            record.status = RecordStatus.INVALID
        elif record.status != RecordStatus.DUPLICATE:
            record.status = RecordStatus.VALID


__all__ = ["validate_record", "apply_validation"]
