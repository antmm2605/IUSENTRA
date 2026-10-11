"""Barriera dell'archivio termini, tramite il coordinamento sorgente nativo."""
from pct.prima_nota_transition import (
    assert_json_source_active,
    commit_transition_locked,
    prepare_transition_locked,
    prima_nota_source_lock,
    read_transition,
)

source_lock = prima_nota_source_lock
prepare_locked = prepare_transition_locked
commit_locked = commit_transition_locked


def assert_legacy_active(path):
    try:
        assert_json_source_active(path)
    except RuntimeError as exc:
        raise RuntimeError("Archivio dei termini in transizione SQL: accesso storico sospeso.") from exc


def read_marker(path):
    try:
        return read_transition(path)
    except RuntimeError as exc:
        raise RuntimeError("Transizione dei termini non verificata: recupero necessario.") from exc
