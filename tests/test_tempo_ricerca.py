"""Tempo massimo delle ricerche: nessuna query delle fonti tiene un thread per minuti."""
import sqlite3
import time

import pytest

from lex import tempo_ricerca

_LUNGA = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT count(*) FROM n"


def test_il_timer_interrompe_anche_senza_gestore_di_avanzamento(monkeypatch):
    monkeypatch.setattr(tempo_ricerca, "_PASSO", 10**9)  # solo il timer può fermarla
    inizio = time.monotonic()
    with tempo_ricerca.scadenza(0.2):
        connessione = tempo_ricerca.applica(sqlite3.connect(":memory:"))
        with pytest.raises(tempo_ricerca.RicercaTroppoLunga):
            with tempo_ricerca.traduci_interruzione():
                connessione.execute(_LUNGA).fetchone()
    assert time.monotonic() - inizio < 3

    # Il timer che scatta quando la connessione è già chiusa non deve sollevare
    # errori nel suo thread (prima lo copriva solo una ricerca lenta per caso).
    import threading

    errori = []
    monkeypatch.setattr(threading, "excepthook", errori.append)
    with tempo_ricerca.scadenza(0.05):
        chiusa = tempo_ricerca.applica(sqlite3.connect(":memory:"))
        chiusa.close()
        timer = tempo_ricerca._timer_attivi()[-1]
        timer.join(2)
    assert not timer.is_alive()
    assert errori == []


def test_senza_scadenza_nessun_limite():
    connessione = tempo_ricerca.applica(sqlite3.connect(":memory:"))
    assert connessione.execute("SELECT 1").fetchone() == (1,)
    assert tempo_ricerca.scadenza_attiva() is None


def test_scadenza_annidata_vale_la_piu_stretta():
    with tempo_ricerca.scadenza(100):
        esterna = tempo_ricerca.scadenza_attiva()
        with tempo_ricerca.scadenza(1):
            assert tempo_ricerca.scadenza_attiva() < esterna
        assert tempo_ricerca.scadenza_attiva() == esterna


def test_errore_chiaro_e_non_confuso_con_archivio_mancante():
    errore = tempo_ricerca.RicercaTroppoLunga(20)
    assert not isinstance(errore, OSError)
    assert "20 secondi" in str(errore)


def test_richiesta_http_risponde_503_con_messaggio(monkeypatch):
    from flask import Flask, jsonify

    from web.blueprints import api_v1_ricerca_legale as modulo

    app = Flask(__name__)

    @app.get("/lenta")
    def lenta():
        tempo_ricerca.apri_per_richiesta(0.0001)
        time.sleep(0.01)
        try:
            tempo_ricerca.controlla()
        except tempo_ricerca.RicercaTroppoLunga as exc:
            return modulo._ricerca_troppo_lunga(exc)
        return jsonify(ok=True)

    with app.test_client() as client:
        risposta = client.get("/lenta")
    tempo_ricerca.chiudi_per_richiesta()
    assert risposta.status_code == 503
    assert risposta.get_json()["code"] == "tempo_massimo"


def test_esecutore_limitato_libera_posto_e_connessione_alla_scadenza(tmp_path):
    from pct.giurisprudenza_corpus import connessione_sola_lettura

    db = tmp_path / "archivio.sqlite"
    sqlite3.connect(db).execute("CREATE TABLE t(x)").connection.commit()
    esecutore = tempo_ricerca.EsecutoreLimitato("prova", posti=1, per_utente=1)
    connessioni = []

    def lavoro_lungo():
        conn = connessione_sola_lettura(str(db))  # collegata al tempo massimo del worker
        connessioni.append(conn)
        try:
            return conn.execute(_LUNGA).fetchone()
        finally:
            conn.close()

    inizio = time.monotonic()
    with pytest.raises(tempo_ricerca.RicercaTroppoLunga):
        esecutore.esegui(lavoro_lungo, secondi=0.3, utente="a")
    assert time.monotonic() - inizio < 3
    fine = time.monotonic() + 3
    while esecutore.occupati() and time.monotonic() < fine:
        time.sleep(0.05)
    assert esecutore.occupati() == 0  # SQLite interrotto nel worker: posto libero
    with pytest.raises(sqlite3.ProgrammingError):
        connessioni[0].execute("SELECT 1")  # connessione chiusa
    assert esecutore.esegui(lambda: 42, secondi=1, utente="a") == 42


def test_esecutore_limitato_senza_posto_non_accoda():
    import threading

    esecutore = tempo_ricerca.EsecutoreLimitato("prova2", posti=1, per_utente=1)
    fermo = threading.Event()
    futuro = esecutore.avvia(fermo.wait, 2, secondi=2, utente="a")
    with pytest.raises(tempo_ricerca.PostoNonDisponibile):
        esecutore.avvia(lambda: 1, secondi=1, utente="b")
    fermo.set()
    futuro.result(timeout=3)
