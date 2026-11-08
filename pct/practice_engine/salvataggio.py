"""Una sola scrittura per più modifiche del presidio procedurale dello stesso fascicolo.

Il repository del presidio scrive tutte le tabelle dello studio a ogni modifica (cancella e reinserisce ogni
riga, poi riscrive il mirror JSON). Aprire il Presidio del fascicolo ne chiedeva sette di fila: misurato sulla
copia di prova dello studio l'08/11/2026, 40 dei 46 secondi della richiesta erano queste scritture.

Qui le modifiche di una stessa operazione si raccolgono e si scrivono una volta sola, e solo le righe del
fascicolo toccato quando le righe degli altri fascicoli sono rimaste le stesse; altrimenti si riscrive tutto come
prima. Il contenuto salvato è identico: cambia solo quante volte e quanto si scrive. Se l'operazione fallisce non
si scrive nulla, come in una transazione.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

# Tabella SQL per ogni raccolta in memoria del repository (tutte hanno la colonna fascicolo_id).
TABELLE = {
    "practice_profiles": "practice_profiles", "practice_requirements": "practice_requirements",
    "practice_document_slots": "practice_document_slots", "practice_checklist_items": "practice_checklist_items",
    "practice_validation_results": "practice_validation_results", "practice_state_history": "practice_state_history",
    "deposit_sessions": "deposit_sessions", "deposit_receipts": "deposit_receipts",
    "deposit_timeline_events": "deposit_timeline_events", "evidence_packs": "evidence_packs",
    "audit_events": "practice_audit_events",
}


def _righe_degli_altri(dati: dict[str, list[dict[str, Any]]], fascicolo_id: str) -> dict[str, tuple[int, ...]]:
    """L'identità delle righe degli altri fascicoli: se non cambia, quelle righe non vanno riscritte."""
    return {chiave: tuple(id(riga) for riga in dati.get(chiave) or [] if riga.get("fascicolo_id") != fascicolo_id)
            for chiave in TABELLE}


def scrivi_fascicolo(repository: Any, fascicolo_id: str) -> None:
    """Riscrive in una transazione solo le righe del fascicolo."""
    conn = repository.studio_db.conn
    solo = {chiave: [riga for riga in repository._data.get(chiave) or [] if riga.get("fascicolo_id") == fascicolo_id]
            for chiave in repository._data}
    try:
        conn.execute("BEGIN")
        for tabella in TABELLE.values():
            conn.execute(f"DELETE FROM {tabella} WHERE fascicolo_id = ?", (fascicolo_id,))
        repository._insert_all(conn, solo)
        repository._commit()
    except Exception:
        repository._rollback()
        raise


@contextmanager
def salvataggio_unico(repository: Any, fascicolo_id: str = "") -> Iterator[None]:
    if repository._suspend_persist:  # già dentro un'operazione: scrive chi l'ha aperta
        yield
        return
    fascicolo_id = str(fascicolo_id or "").strip()
    altri = _righe_degli_altri(repository._data, fascicolo_id) if fascicolo_id else None
    repository._suspend_persist = True
    repository._salvataggio_rinviato = False
    try:
        yield
    finally:
        repository._suspend_persist = False
    if not repository._salvataggio_rinviato:
        return
    repository._salvataggio_rinviato = False
    if altri is not None and altri == _righe_degli_altri(repository._data, fascicolo_id):
        try:
            scrivi_fascicolo(repository, fascicolo_id)
        except Exception:
            repository._persist_all()
        repository._write_legacy_mirror()
        return
    repository._save()


__all__ = ["TABELLE", "salvataggio_unico", "scrivi_fascicolo"]
