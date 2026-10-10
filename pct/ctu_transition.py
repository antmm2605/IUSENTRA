"""Barriera CTU verso SQL, riusando il coordinamento sorgente già governato.

Il marker è separato per percorso sorgente. La procedura di migrazione deve
verificare backup e SQL prima di confermarlo; il runtime non lo crea.
"""
from contextlib import contextmanager

from pct.prima_nota_transition import (
    assert_json_source_active,
    commit_transition_locked,
    prepare_transition_locked,
    prima_nota_source_lock,
    read_transition,
)


@contextmanager
def source_lock(path):
    with prima_nota_source_lock(path):
        yield


def assert_legacy_active(path):
    try:
        assert_json_source_active(path)
    except RuntimeError as exc:
        raise RuntimeError("Incarichi CTU in transizione SQL: accesso all'archivio storico sospeso.") from exc


def read_marker(path):
    try:
        return read_transition(path)
    except RuntimeError as exc:
        raise RuntimeError("Transizione CTU non verificata: recupero necessario, senza ritorno al JSON.") from exc


def prepare_locked(path, *, tenant, source_sha256):
    return prepare_transition_locked(path, tenant=tenant, source_sha256=source_sha256)


def commit_locked(path, *, tenant, source_sha256):
    return commit_transition_locked(path, tenant=tenant, source_sha256=source_sha256)
