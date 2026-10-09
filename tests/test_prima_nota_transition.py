"""Prove della preparazione alla transizione, su soli file controllati."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from pct.prima_nota_transition import prima_nota_source_lock


@pytest.mark.parametrize('phase', ['prepared', 'committed', 'broken'])
def test_fence_impedisce_riapertura_e_salvataggio_da_manager_json_vecchio(tmp_path, phase):
    from pct.prima_nota import GestionePrimaNota
    from pct.prima_nota_transition import prepare_transition_locked, commit_transition_locked, transition_path
    path = tmp_path / 'controlled.json'
    old = GestionePrimaNota(str(path))
    old.registra(importo=260)
    original = path.read_bytes()
    with prima_nota_source_lock(path):
        prepare_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        if phase == 'committed':
            commit_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        elif phase == 'broken':
            transition_path(path).write_bytes(b'{"interrotto":')
    with pytest.raises(RuntimeError, match='transizione SQL'):
        old.registra(importo=500)
    assert old.saldi()['incassi'] == 260
    with pytest.raises(RuntimeError, match='transizione SQL'):
        GestionePrimaNota(str(path))
    assert path.read_bytes() == original


def test_fence_ripetuto_non_cambia_fonte_o_tenant_e_non_torna_prepared(tmp_path):
    from pct.prima_nota_transition import prepare_transition_locked, commit_transition_locked, transition_path
    path = tmp_path / 'controlled.json'
    with prima_nota_source_lock(path):
        prepare_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        commit_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        original = transition_path(path).read_bytes()
        assert prepare_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)['phase'] == 'committed'
        for tenant, sha in [('altro', 'a' * 64), ('studio-test', 'b' * 64)]:
            with pytest.raises(RuntimeError):
                prepare_transition_locked(path, tenant=tenant, source_sha256=sha)
            with pytest.raises(RuntimeError):
                commit_transition_locked(path, tenant=tenant, source_sha256=sha)
        assert transition_path(path).read_bytes() == original


def test_commit_fence_fallito_conserva_preparazione_e_originale(monkeypatch, tmp_path):
    import pct.prima_nota_transition as transition
    path = tmp_path / 'controlled.json'
    path.write_bytes(b'originale-controllato')
    with prima_nota_source_lock(path):
        transition.prepare_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        def fail(*args):
            raise OSError('Replace fence controllato fallito')
        monkeypatch.setattr(transition.os, 'replace', fail)
        with pytest.raises(OSError):
            transition.commit_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
        assert transition.read_transition(path)['phase'] == 'prepared'
    assert path.read_bytes() == b'originale-controllato'
    assert not list(tmp_path.glob('.prima-nota-transition-*'))


@pytest.mark.parametrize('raw', [b'', b'\xff', b'[]', b'{"version":true}', b'{"version":1,"tenant":"s","source_sha256":"a","phase":"prepared"}'])
def test_fence_incompleto_non_autorizza_recupero_silenzioso(tmp_path, raw):
    from pct.prima_nota_transition import read_transition, transition_path, prepare_transition_locked
    path = tmp_path / 'controlled.json'
    transition_path(path).write_bytes(raw)
    with pytest.raises(RuntimeError, match='recupero necessario'):
        read_transition(path)
    with prima_nota_source_lock(path):
        with pytest.raises(RuntimeError, match='recupero necessario'):
            prepare_transition_locked(path, tenant='studio-test', source_sha256='a' * 64)
    assert transition_path(path).read_bytes() == raw


def test_due_copie_non_sovrascrivono_un_movimento_confermato(tmp_path):
    from pct.prima_nota import GestionePrimaNota
    path = tmp_path / 'controlled.json'
    first, second = GestionePrimaNota(str(path)), GestionePrimaNota(str(path))
    first.registra(importo=260, causale='Primo movimento')
    confirmed = path.read_bytes()
    with pytest.raises(ValueError, match='altro processo'):
        second.registra(importo=500, causale='Secondo movimento')
    assert path.read_bytes() == confirmed
    assert second.saldi()['incassi'] == 260
    second.registra(importo=500, causale='Secondo movimento')
    assert GestionePrimaNota(str(path)).saldi()['incassi'] == 760


def test_replace_fallito_preserva_fonte_e_non_conferma_movimento(monkeypatch, tmp_path):
    import pct.prima_nota
    path = tmp_path / 'controlled.json'
    manager = pct.prima_nota.GestionePrimaNota(str(path))
    manager.registra(importo=260)
    confirmed = path.read_bytes()
    def fail(*args):
        raise OSError('Replace controllato fallito')
    monkeypatch.setattr(pct.prima_nota.os, 'replace', fail)
    with pytest.raises(OSError, match='Replace controllato'):
        manager.registra(importo=500)
    assert path.read_bytes() == confirmed
    assert manager.saldi()['incassi'] == 260
    assert not list(tmp_path.glob('.prima-nota-*'))


def test_rilascio_fallito_dopo_replace_non_cancella_la_scrittura(monkeypatch, tmp_path):
    import pct.sync
    from pct.prima_nota import GestionePrimaNota
    path = tmp_path / 'controlled.json'
    manager = GestionePrimaNota(str(path))
    def fail(fd):
        raise OSError('Rilascio controllato fallito dopo persistenza')
    monkeypatch.setattr(pct.sync, '_unlock_fd', fail)
    with pytest.raises(OSError, match='dopo persistenza'):
        manager.registra(importo=260)
    assert manager.saldi()['incassi'] == 260
    assert GestionePrimaNota(str(path)).saldi()['incassi'] == 260


def test_acquisizione_fallita_rilascia_descriptor_e_thread_lock(monkeypatch, tmp_path):
    import pct.sync
    path = tmp_path / 'controlled.json'
    descriptors = []
    native = pct.sync._lock_fd
    def fail(fd):
        descriptors.append(fd)
        raise OSError('Lock occupato controllato')
    monkeypatch.setattr(pct.sync, '_lock_fd', fail)
    with pytest.raises(OSError):
        with prima_nota_source_lock(path):
            pytest.fail('Non entrare senza acquisizione')
    assert len(descriptors) == 1 and descriptors[0].closed
    monkeypatch.setattr(pct.sync, '_lock_fd', native)
    # Un altro thread deve poter acquisire: RLock ricorsivo sullo stesso thread non prova il rilascio.
    def next_writer():
        with prima_nota_source_lock(path):
            return True
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(next_writer).result(timeout=5)


def test_alias_percorso_usa_lo_stesso_lock(tmp_path):
    source = tmp_path / 'controlled.json'
    holder_ready, release, waiting = Event(), Event(), Event()
    order = []
    def holder():
        with prima_nota_source_lock(source):
            holder_ready.set()
            assert release.wait(timeout=5)
            order.append('first')
    def other():
        assert holder_ready.wait(timeout=5)
        waiting.set()
        with prima_nota_source_lock(tmp_path / '.' / 'controlled.json'):
            order.append('second')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(holder), pool.submit(other)
        assert waiting.wait(timeout=5)
        assert not second.done()
        release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert order == ['first', 'second']


def test_rilascio_fallito_chiude_descriptor_e_non_blocca_il_successivo(monkeypatch, tmp_path):
    import pct.sync
    path = tmp_path / 'controlled.json'
    descriptors = []
    native = pct.sync._unlock_fd
    def fail(fd):
        descriptors.append(fd)
        raise OSError('Rilascio controllato fallito')
    monkeypatch.setattr(pct.sync, '_unlock_fd', fail)
    with pytest.raises(OSError):
        with prima_nota_source_lock(path):
            pass
    assert descriptors[0].closed
    monkeypatch.setattr(pct.sync, '_unlock_fd', native)
    def next_writer():
        with prima_nota_source_lock(path):
            return True
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(next_writer).result(timeout=5)


def test_errore_nel_blocco_non_modifica_fonte_e_rilascia(tmp_path):
    source = tmp_path / 'controlled.json'
    source.write_bytes(b'originale-controllato')
    with pytest.raises(ValueError):
        with prima_nota_source_lock(source):
            raise ValueError('Backup non confermato')
    with prima_nota_source_lock(source):
        assert source.read_bytes() == b'originale-controllato'


def test_lock_nativo_tra_processi_distinti(tmp_path):
    import subprocess
    import sys
    source = tmp_path / 'controlled.json'
    source.write_bytes(b'fonte-preservata')
    holder_code = """
import sys
from pct.prima_nota_transition import prima_nota_source_lock
with prima_nota_source_lock(sys.argv[1]):
    print('held',flush=True)
    sys.stdin.readline()
"""
    contender_code = """
import sys
from pct.prima_nota_transition import prima_nota_source_lock
try:
    with prima_nota_source_lock(sys.argv[1]):
        print('acquired',flush=True)
except OSError:
    print('busy',flush=True)
"""
    holder = subprocess.Popen([sys.executable, '-c', holder_code, str(source)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    contender = None
    try:
        assert holder.stdout.readline().strip() == 'held'
        contender = subprocess.Popen([sys.executable, '-c', contender_code, str(source)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = contender.communicate(timeout=0.5)
            assert contender.returncode == 0 and out.strip() == 'busy', err
            # Windows usa il rifiuto non bloccante nativo: non autorizza una scrittura.
            holder.communicate(input='release\n', timeout=5)
            resumed = subprocess.run([sys.executable, '-c', contender_code, str(source)],
                                     capture_output=True, text=True, timeout=5)
            assert resumed.returncode == 0 and resumed.stdout.strip() == 'acquired', resumed.stderr
        except subprocess.TimeoutExpired:
            # Linux aspetta il rilascio nativo; nessuna scrittura simultanea ammessa.
            holder.communicate(input='release\n', timeout=5)
            out, err = contender.communicate(timeout=5)
            assert contender.returncode == 0 and out.strip() == 'acquired', err
        assert source.read_bytes() == b'fonte-preservata'
    finally:
        if holder.poll() is None:
            holder.communicate(input='release\n', timeout=5)
        if contender is not None and contender.poll() is None:
            contender.kill()
            contender.communicate(timeout=5)
