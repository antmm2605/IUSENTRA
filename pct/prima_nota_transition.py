"""Coordinamento puntuale della fonte Prima nota, tramite il lock nativo.

Il codice condiviso firma/PEC rimane invariato. Questo adattatore recupera
le risorse del lock quando l'acquisizione o il rilascio falliscono.
Non è da solo una barriera contro produttori non ancora aggiornati.
"""
from __future__ import annotations

import os
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pct.sync import FileLock


def transition_path(path):
    return Path(str(Path(path).resolve()) + '.sql-transition')


def assert_json_source_active(path):
    """Qualsiasi fence presente, anche incompleto, vieta il ritorno al JSON."""
    try:
        transition_path(path).read_bytes()
    except FileNotFoundError:
        return
    raise RuntimeError('Prima nota in transizione SQL: accesso al registro storico sospeso.')


def read_transition(path):
    try:
        content = transition_path(path).read_bytes()
    except FileNotFoundError:
        return None
    try:
        value = json.loads(content.decode('utf-8'))
        if not isinstance(value, dict) or set(value) != {'version', 'tenant', 'source_sha256', 'phase'}:
            raise ValueError('Struttura non valida')
        if type(value['version']) is not int or value['version'] != 1 or value['phase'] not in {'prepared', 'committed'}:
            raise ValueError('Versione o fase non valida')
        if not isinstance(value['tenant'], str) or not value['tenant'].strip():
            raise ValueError('Tenant non valido')
        sha = value['source_sha256']
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Impronta non valida')
    except (ValueError, TypeError) as exc:
        raise RuntimeError('Transizione Prima nota incoerente: recupero necessario, senza ritorno al JSON.') from exc
    return value


def prepare_transition_locked(path, *, tenant, source_sha256):
    """Il chiamante mantiene prima_nota_source_lock e ha già il backup.

    Non rimuovere il fence se SQL fallisce: il recupero esplicito deve
    verificare il marker SQL e la fonte prima di riprendere l'adozione.
    """
    value = {'version': 1, 'tenant': str(tenant).strip(), 'source_sha256': source_sha256, 'phase': 'prepared'}
    if not value['tenant'] or not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in '0123456789abcdef' for c in source_sha256):
        raise ValueError('Tenant e impronta necessari per la transizione Prima nota.')
    previous = read_transition(path)
    if previous is not None:
        if previous['tenant'] != value['tenant'] or previous['source_sha256'] != source_sha256:
            raise RuntimeError('Transizione già presente con altra fonte o tenant: recupero necessario.')
        return previous
    # Esclusivo: un'interruzione lascia un fence visibile e fail-closed.
    with transition_path(path).open('xb') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())
    return value


def commit_transition_locked(path, *, tenant, source_sha256):
    """Solo dopo riscontro del commit SQL, sotto il medesimo lock sorgente."""
    previous = read_transition(path)
    if previous is None or previous['tenant'] != tenant or previous['source_sha256'] != source_sha256:
        raise RuntimeError('Transizione Prima nota non preparata sulla stessa fonte e tenant.')
    if previous['phase'] == 'committed':
        return previous
    value = {**previous, 'phase': 'committed'}
    target = transition_path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.prima-nota-transition-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8'))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return value


@contextmanager
def prima_nota_source_lock(path):
    """Stesso lock fra migrazione e futuri scrittori, path assoluto canonico."""
    canonical = os.path.normcase(str(Path(path).resolve()))
    lock = FileLock(canonical)
    # FileLock acquisisce il thread lock prima di aprire il descriptor.
    # Il suo __enter__ non recupera le risorse se open/lock OS fallisce.
    try:
        lock.__enter__()
    except BaseException:
        try:
            if lock._fd is not None:
                lock._fd.close()
                lock._fd = None
        finally:
            lock._get_thread_lock().release()
        raise
    try:
        yield
    finally:
        try:
            lock.__exit__(None, None, None)
        except BaseException:
            # __exit__ nativo interrompe la pulizia se l'unlock OS fallisce.
            if lock._fd is not None:
                try:
                    lock._fd.close()
                    lock._fd = None
                finally:
                    lock._get_thread_lock().release()
            raise
