"""Deduplica dei record di staging: chiave naturale per tipo + hash contenuto.

Evita import doppi sia rispetto ai dati già presenti nello studio (existing_keys)
sia rispetto a duplicati interni allo stesso file sorgente.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .base import RecordKind, RecordStatus, StagedRecord


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def natural_key(kind: RecordKind, data: dict[str, Any]) -> str:
    """Chiave naturale stabile per la deduplica (vuota se non determinabile)."""

    if kind in (RecordKind.CLIENTE, RecordKind.SOGGETTO):
        cf = _norm(data.get("codice_fiscale") or data.get("cf"))
        if cf:
            return f"{kind.value}:cf:{cf}"
        piva = _norm(data.get("partita_iva") or data.get("piva"))
        if piva:
            return f"{kind.value}:piva:{piva}"
        nome = _norm(f"{data.get('nome', '')} {data.get('cognome', '')}")
        return f"{kind.value}:nome:{nome}" if nome.strip() else ""
    if kind == RecordKind.FASCICOLO:
        ruolo = _norm(data.get("numero_ruolo") or data.get("rg"))
        anno = _norm(data.get("anno"))
        if ruolo:
            return f"fascicolo:rg:{ruolo}/{anno}" if anno else f"fascicolo:rg:{ruolo}"
        return f"fascicolo:titolo:{_norm(data.get('titolo'))}" if _norm(data.get("titolo")) else ""
    if kind == RecordKind.FATTURA:
        numero = _norm(data.get("numero"))
        anno = _norm(data.get("anno"))
        return f"fattura:{numero}/{anno}" if numero else ""
    if kind == RecordKind.SCADENZA:
        return f"scadenza:{_norm(data.get('descrizione'))}:{_norm(data.get('data'))}"
    if kind == RecordKind.DOCUMENTO:
        return f"documento:{_norm(data.get('filename'))}"
    return ""


def assign_natural_keys(records: list[StagedRecord]) -> None:
    for record in records:
        if not record.natural_key:
            record.natural_key = natural_key(record.kind, record.data or {})


def mark_duplicates(records: list[StagedRecord], existing_keys: Iterable[str] = ()) -> None:
    """Marca come DUPLICATE i record già presenti o ripetuti nel batch.

    Non tocca i record già INVALID (la validazione ha priorità). Il primo
    record di una chiave resta valido, i successivi diventano duplicati.
    """

    assign_natural_keys(records)
    existing = {str(key) for key in existing_keys if str(key)}
    seen_keys: set[str] = set()
    seen_hashes: set[str] = set()
    for record in records:
        if record.status == RecordStatus.INVALID:
            continue
        key = record.natural_key
        is_dup = False
        if key and (key in existing or key in seen_keys):
            is_dup = True
        elif record.content_sha256 in seen_hashes:
            is_dup = True
        if is_dup:
            record.status = RecordStatus.DUPLICATE
        else:
            if key:
                seen_keys.add(key)
            seen_hashes.add(record.content_sha256)


__all__ = ["natural_key", "assign_natural_keys", "mark_duplicates"]
