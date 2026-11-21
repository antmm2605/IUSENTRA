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
