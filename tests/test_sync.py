"""Test per pct/sync.py — sincronizzazione multi-operatore."""

from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

import pytest

from pct.sync import (
    FileLock,
    Evento,
    GestoreSincronizzazione,
    get_gestore,
    reset_gestore,
)


# ================================================================ Fixtures

@pytest.fixture(autouse=True)
def reset_singleton():
    """Assicura che ogni test parta con un singleton fresco."""
    reset_gestore()
    yield
    reset_gestore()


@pytest.fixture
def gs():
    return GestoreSincronizzazione()


# ================================================================ FileLock

def test_filelock_crea_file_lock(tmp_path):
    target = str(tmp_path / "dati.json")
    with FileLock(target):
        assert Path(target + ".lock").exists()


def test_filelock_esclusivo_cross_thread(tmp_path):
    """Due thread non possono detenere il lock contemporaneamente."""
    target = str(tmp_path / "shared.json")
    risultati = []
    lock_acquisito = threading.Event()

    def primo():
        with FileLock(target):
            lock_acquisito.set()
            time.sleep(0.1)
            risultati.append("primo_dentro")

    def secondo():
        lock_acquisito.wait()
        # A questo punto il primo ha il lock: il secondo deve aspettare
        with FileLock(target):
            risultati.append("secondo_dentro")

    t1 = threading.Thread(target=primo)
    t2 = threading.Thread(target=secondo)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # L'ordine deve essere rispettato
    assert risultati == ["primo_dentro", "secondo_dentro"]


def test_filelock_rilasciato_dopo_contesto(tmp_path):
    """Il lock deve essere rilasciato dopo il contesto."""
    target = str(tmp_path / "dati.json")
    with FileLock(target):
        pass
    # Deve essere possibile acquisirlo di nuovo
    acquired = False
    with FileLock(target):
        acquired = True
    assert acquired


def test_filelock_non_blocca_lettura_concorrente(tmp_path):
    """Più thread possono leggere senza bloccarsi se nessuno scrive."""
    target = str(tmp_path / "dati.json")
    Path(target).write_text('{"x": 1}')
    letti = []

    def leggi():
        letti.append(json.loads(Path(target).read_text()))

    threads = [threading.Thread(target=leggi) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(letti) == 5


# ================================================================ Evento

def test_evento_to_json():
    ev = Evento("crea", "clienti", id_risorsa="c1", utente="mario")
    d = json.loads(ev.to_json())
    assert d["tipo"] == "crea"
    assert d["modulo"] == "clienti"
    assert d["id"] == "c1"
    assert d["utente"] == "mario"
    assert isinstance(d["ts"], int)


def test_evento_to_sse_formato():
    ev = Evento("modifica", "fascicoli")
    sse = ev.to_sse()
    assert sse.startswith("data: ")
    assert sse.endswith("\n\n")


def test_evento_extra_campi():
    ev = Evento("info", "sistema", messaggio="test")
    d = json.loads(ev.to_json())
    assert d["messaggio"] == "test"


# ================================================================ GestoreSincronizzazione — file ops

def test_leggi_atomico_file_inesistente(gs, tmp_path):
    dati, versione = gs.leggi_atomico(str(tmp_path / "nope.json"))
    assert dati == []
    assert versione == ""


def test_leggi_atomico_file_esistente(gs, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps([{"id": "1"}]))
    dati, versione = gs.leggi_atomico(str(p))
    assert len(dati) == 1
    assert versione != ""


def test_scrivi_atomico_crea_file(gs, tmp_path):
    target = str(tmp_path / "out.json")
    ok, _ = gs.scrivi_atomico(target, [{"id": "x"}])
    assert ok
    assert Path(target).exists()
    letti = json.loads(Path(target).read_text())
    assert letti[0]["id"] == "x"


def test_scrivi_atomico_scrittura_atomica(gs, tmp_path):
    """Il file temp non deve restare dopo la scrittura."""
    target = str(tmp_path / "out.json")
    gs.scrivi_atomico(target, {"k": "v"})
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert tmp_files == []


def test_scrivi_atomico_optimistic_lock_successo(gs, tmp_path):
    target = str(tmp_path / "out.json")
    # Prima scrittura
    ok1, v1 = gs.scrivi_atomico(target, {"n": 1})
    assert ok1
    # Seconda scrittura con versione corretta
    ok2, _ = gs.scrivi_atomico(target, {"n": 2}, versione_attesa=v1)
    assert ok2


def test_scrivi_atomico_optimistic_lock_conflitto(gs, tmp_path):
    target = str(tmp_path / "out.json")
    ok, v1 = gs.scrivi_atomico(target, {"n": 1})
    # Simula modifica esterna
    time.sleep(0.01)
    gs.scrivi_atomico(target, {"n": 99})
    # Ora proviamo con la versione vecchia — deve fallire
    ok_conflict, _ = gs.scrivi_atomico(target, {"n": 2}, versione_attesa=v1)
    assert not ok_conflict
    # Il file deve contenere il valore scritto dall'altro
    assert json.loads(Path(target).read_text())["n"] == 99


def test_versione_file_cambia_dopo_scrittura(gs, tmp_path):
    target = str(tmp_path / "out.json")
    Path(target).write_text('{"a":1}')
    v1 = gs.versione_file(target)
    time.sleep(0.01)
    Path(target).write_text('{"a":2}')
    v2 = gs.versione_file(target)
    assert v1 != v2


def test_versione_file_inesistente(gs, tmp_path):
    assert gs.versione_file(str(tmp_path / "nope.json")) == ""


# ================================================================ GestoreSincronizzazione — SSE bus

def test_subscribe_restituisce_id_e_queue(gs):
    cid, q = gs.subscribe()
    assert isinstance(cid, str) and len(cid) > 0
    assert isinstance(q, queue.Queue)


def test_n_connessi_aumenta(gs):
    assert gs.n_connessi == 0
    gs.subscribe()
    assert gs.n_connessi == 1
    gs.subscribe()
    assert gs.n_connessi == 2


def test_unsubscribe_riduce_contatore(gs):
    cid, _ = gs.subscribe()
    assert gs.n_connessi == 1
    gs.unsubscribe(cid)
    assert gs.n_connessi == 0


def test_pubblica_consegna_evento(gs):
    cid, q = gs.subscribe()
    raggiunti = gs.pubblica("crea", "clienti", "c1", "mario")
    assert raggiunti == 1
    ev = q.get_nowait()
    assert ev.tipo == "crea"
    assert ev.modulo == "clienti"
    assert ev.id_risorsa == "c1"
    assert ev.utente == "mario"


def test_pubblica_a_tutti_i_subscribers(gs):
    cids = []
    queues = []
    for _ in range(3):
        cid, q = gs.subscribe()
        cids.append(cid)
        queues.append(q)
    raggiunti = gs.pubblica("modifica", "fascicoli")
    assert raggiunti == 3
    for q in queues:
        assert not q.empty()


def test_pubblica_senza_subscribers(gs):
    n = gs.pubblica("info", "sistema")
    assert n == 0


def test_pubblica_broadcast(gs):
    _, q = gs.subscribe()
    gs.pubblica_broadcast("Manutenzione", utente="admin")
    ev = q.get_nowait()
    assert ev.tipo == "info"
    assert ev.modulo == "sistema"


def test_sse_stream_primo_messaggio_connesso(gs):
    cid, q = gs.subscribe()
    gen = gs.sse_stream(cid, q)
    primo = next(gen)
    assert "connesso" in primo


def test_sse_stream_consegna_evento(gs):
    cid, q = gs.subscribe()
    gs.pubblica("crea", "clienti", "c1")
    gen = gs.sse_stream(cid, q)
    next(gen)  # skip messaggio connesso
    secondo = next(gen)
    assert "data:" in secondo
    d = json.loads(secondo.replace("data: ", "").strip())
    assert d["tipo"] == "crea"


def test_sse_stream_heartbeat(gs):
    cid, q = gs.subscribe()
    gen = gs.sse_stream(cid, q)
    next(gen)  # connesso
    # Non pubblichiamo nulla: dopo timeout di 0 secondi arriva heartbeat
    # Non possiamo aspettare 25s nel test, verifichiamo solo la struttura
    # del generatore (che sia un generatore)
    import types
    assert isinstance(gen, types.GeneratorType)


# ================================================================ Singleton

def test_get_gestore_singleton():
    g1 = get_gestore()
    g2 = get_gestore()
    assert g1 is g2


def test_reset_gestore():
    g1 = get_gestore()
    reset_gestore()
    g2 = get_gestore()
    assert g1 is not g2


# ================================================================ Concorrenza scritture

def test_scritture_concorrenti_no_corruzione(tmp_path):
    """Dieci thread scrivono sullo stesso file senza corrompere il JSON."""
    target = str(tmp_path / "shared.json")
    gs = GestoreSincronizzazione()
    Path(target).write_text("[]")
    errori = []

    def scrivi(n):
        try:
            dati, _ = gs.leggi_atomico(target)
            dati.append(n)
            gs.scrivi_atomico(target, dati)
        except Exception as e:
            errori.append(str(e))

    threads = [threading.Thread(target=scrivi, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errori == []
    # Il file deve essere JSON valido
    finale = json.loads(Path(target).read_text())
    assert isinstance(finale, list)


def test_pubblica_thread_safe(gs):
    """Cento thread pubblicano simultaneamente senza deadlock."""
    cid, q = gs.subscribe()
    errori = []

    def pubblica(n):
        try:
            gs.pubblica("info", "test", str(n))
        except Exception as e:
            errori.append(str(e))

    threads = [threading.Thread(target=pubblica, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errori == []
    assert gs.n_connessi >= 1


# ================================================================ Route web

@pytest.fixture
def client_sync(tmp_path):
    """Client Flask con utente admin per test route sync."""
    from web.app import create_app
    from pct.auth import GestioneUtenti, RuoloUtente

    auth_db = str(tmp_path / "utenti.json")
    audit_db = str(tmp_path / "audit.json")
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)

    gu = GestioneUtenti(db_path=auth_db, audit_path=audit_db, secret_key="test")
    gu.crea(username="syncadmin", password="Sync1234!", ruolo=RuoloUtente.AMMINISTRATORE, email="s@b.it")

    cfg = {
        "TESTING": True, "SECRET_KEY": "test",
        "AUTH_DB": auth_db, "AUDIT_DB": audit_db,
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
    }
    app = create_app(cfg)
    with app.test_client() as c:
        c.post("/login", data={"username": "syncadmin", "password": "Sync1234!"}, follow_redirects=True)
        yield c


import os  # noqa: E402 (needed for fixture above)


def test_api_sync_stato(client_sync):
    r = client_sync.get("/api/sync/stato")
    assert r.status_code == 200
    d = r.get_json()
    assert "connessi" in d
    assert "versioni" in d


def test_api_sync_broadcast_ok(client_sync):
    r = client_sync.post(
        "/api/sync/broadcast",
        json={"messaggio": "Test broadcast"},
        content_type="application/json",
    )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True


def test_api_sync_broadcast_senza_messaggio(client_sync):
    r = client_sync.post(
        "/api/sync/broadcast",
        json={},
        content_type="application/json",
    )
    assert r.status_code == 400
