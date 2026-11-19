"""La fase reale della guida arriva da un endpoint separato: la guida si apre subito."""

import web.services.guida_fase_runtime as runtime


def test_fase_per_la_guida_dalla_lettura(monkeypatch):
    lettura = {"fase": {"codice": "decisa", "descrizione": "causa decisa: Sentenza del 07/10/2026", "prove": []},
               "percorso": {"strada": "realizzazione", "passi": [{"passo": "Notificare la sentenza alla controparte", "norme": []}]}}
    monkeypatch.setattr(runtime, "lettura_pronta", lambda _fid: lettura)
    risposta = runtime._calcola_fase("9DC39668")
    assert risposta["ok"] and risposta["fase"] == "decisa"
    assert risposta["nota_fase"].startswith("Causa decisa: Sentenza del 07/10/2026.")
    assert risposta["prima_cosa_da_fare"] == "Notificare la sentenza alla controparte"


def test_senza_lettura_nessuna_fase(monkeypatch):
    monkeypatch.setattr(runtime, "lettura_pronta", lambda _fid: None)
    risposta = runtime._calcola_fase("X")
    assert risposta["nota_fase"] == "" and risposta["percorso"] is None


def test_guida_consultiva_riusa_la_fase_precedente(monkeypatch):
    from web.services import riscontri_processuali_runtime as riscontri

    monkeypatch.setattr(runtime, "lettura_pronta", lambda _fid: None)
    monkeypatch.setattr(riscontri, "lettura_precedente", lambda _fid: {
        "fase": {"codice": "chiusa", "descrizione": "pratica definita"},
        "aggiornamento_pendente": True,
    })
    assert runtime.fase_per_la_guida("F1")["in_preparazione"]
    consultiva = runtime.fase_per_la_guida("F1", consultiva=True)
    assert consultiva["fase"] == "chiusa"
    assert consultiva["aggiornamento_pendente"] is True
