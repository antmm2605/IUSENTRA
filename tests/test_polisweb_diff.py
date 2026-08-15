"""Motore differenze registri: nuovo/spostato/rimosso/deposito, storico bounded.

Informativo e fail-closed: la prima lettura non genera rumore, le differenze
non toccano mai scadenze operative.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.polisweb_diff import (
    GestioneDiffRegistro,
    MAX_DIFFERENZE_PER_FASCICOLO,
    confronta_snapshot,
    snapshot_eventi,
)


def _ev(tipo="udienza", descrizione="Prima udienza di comparizione", data="2026-10-01"):
    return SimpleNamespace(tipo=tipo, descrizione=descrizione, data=data)


# --- Confronto puro --------------------------------------------------------------


def test_prima_lettura_senza_differenze():
    corrente = snapshot_eventi([_ev()])
    assert confronta_snapshot(None, corrente) == []


def test_nuovo_evento_rilevato():
    prima = snapshot_eventi([_ev()])
    dopo = snapshot_eventi([_ev(), _ev(tipo="scadenza", descrizione="Note conclusionali", data="2026-11-15")])
    differenze = confronta_snapshot(prima, dopo)
    assert len(differenze) == 1
    assert differenze[0].tipo == "nuovo_evento"
    assert "note conclusionali" in differenze[0].descrizione.casefold()
    assert differenze[0].descrizione.startswith("Scadenza")
    assert differenze[0].data_corrente == "2026-11-15"


def test_udienza_spostata_rilevata():
    prima = snapshot_eventi([_ev(data="2026-10-01")])
    dopo = snapshot_eventi([_ev(data="2026-10-22")])
    differenze = confronta_snapshot(prima, dopo)
    assert len(differenze) == 1
    assert differenze[0].tipo == "evento_spostato"
    assert differenze[0].data_precedente == "2026-10-01"
    assert differenze[0].data_corrente == "2026-10-22"
    assert "spostato dal 2026-10-01 al 2026-10-22" in differenze[0].messaggio()


def test_evento_rimosso_rilevato():
    prima = snapshot_eventi([_ev(), _ev(tipo="scadenza", descrizione="Deposito memorie", data="2026-09-30")])
    dopo = snapshot_eventi([_ev()])
    differenze = confronta_snapshot(prima, dopo)
    assert len(differenze) == 1
    assert differenze[0].tipo == "evento_rimosso"
    assert "non compare piu'" in differenze[0].messaggio()


def test_identita_case_insensitive_e_spazi():
    prima = snapshot_eventi([_ev(descrizione="Prima  Udienza di comparizione")])
    dopo = snapshot_eventi([_ev(descrizione="prima udienza di COMPARIZIONE")])
    assert confronta_snapshot(prima, dopo) == []  # stessa identita', nessun falso spostamento


def test_nessuna_differenza_se_uguali():
    prima = snapshot_eventi([_ev(), _ev(tipo="scadenza", descrizione="Note", data="2026-11-15")])
    assert confronta_snapshot(prima, dict(prima)) == []


# --- Repository ------------------------------------------------------------------


def test_registra_lettura_ciclo_completo(tmp_path):
    gestione = GestioneDiffRegistro(db_path=str(tmp_path / "diff.json"))
    prime = gestione.registra_lettura("F1", [_ev()])
    assert prime == []  # prima lettura: nessun rumore
    seconde = gestione.registra_lettura("F1", [_ev(data="2026-10-22")], depositi_importati=2)
    tipi = [d.tipo for d in seconde]
    assert "evento_spostato" in tipi
    assert "nuovo_deposito" in tipi
    storico = gestione.storico("F1")
    assert len(storico) == 2
    assert storico[0]["messaggio"]  # piu' recente in testa
    # Persistenza
    riletto = GestioneDiffRegistro(db_path=str(tmp_path / "diff.json"))
    assert riletto.ha_snapshot("F1")
    assert len(riletto.storico("F1")) == 2


def test_storico_limitato(tmp_path):
    gestione = GestioneDiffRegistro(db_path=str(tmp_path / "diff.json"))
    gestione.registra_lettura("F1", [])
    for indice in range(MAX_DIFFERENZE_PER_FASCICOLO + 10):
        gestione.registra_lettura("F1", [], depositi_importati=1)
    tutte = gestione._dati["differenze"]["F1"]
    assert len(tutte) == MAX_DIFFERENZE_PER_FASCICOLO


def test_fascicoli_separati(tmp_path):
    gestione = GestioneDiffRegistro(db_path=str(tmp_path / "diff.json"))
    gestione.registra_lettura("F1", [_ev()])
    gestione.registra_lettura("F2", [_ev()])
    gestione.registra_lettura("F1", [_ev(data="2026-10-22")])
    assert len(gestione.storico("F1")) == 1
    assert gestione.storico("F2") == []
