"""Time tracking passivo: sessioni dal segnale audit → proposte → timesheet.

Fail-closed: operazioni isolate non generano proposte, l'unita' minima vale
solo con almeno 2 operazioni, niente doppioni per finestra, e nessun minuto
diventa fatturabile senza conferma dell'avvocato.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct.time_tracking_passivo import (
    DURATA_EVENTO_SINGOLO_MINUTI,
    GestioneTrackingPassivo,
    StatoProposta,
    sessioni_da_eventi,
)


def _ev(ts: str, azione: str = "fascicoli.apri", fascicolo: str = "F1", utente: str = "U1", esito: str = "OK"):
    return SimpleNamespace(
        timestamp=ts, azione=azione, risorsa_tipo="fascicolo", risorsa_id=fascicolo,
        id_utente=utente, username="avv.rossi", esito=esito,
    )


# --- Sessioni --------------------------------------------------------------------


def test_eventi_ravvicinati_formano_una_sessione():
    eventi = [
        _ev("2026-08-13T09:00:00"),
        _ev("2026-08-13T09:05:00", azione="documenti.visualizza"),
        _ev("2026-08-13T09:20:00", azione="editor.salva"),
    ]
    sessioni = sessioni_da_eventi(eventi)
    assert len(sessioni) == 1
    sessione = sessioni[0]
    assert sessione.durata_minuti == 20
    assert sessione.eventi == 3
    assert "consultazione fascicolo" in sessione.categorie
    assert "redazione atti" in sessione.categorie


def test_gap_oltre_soglia_divide_le_sessioni():
    eventi = [
        _ev("2026-08-13T09:00:00"),
        _ev("2026-08-13T09:04:00"),
        _ev("2026-08-13T11:00:00"),  # >15 min dopo → nuova sessione
        _ev("2026-08-13T11:10:00"),
    ]
    sessioni = sessioni_da_eventi(eventi)
    assert len(sessioni) == 2


def test_operazione_isolata_non_propone():
    assert sessioni_da_eventi([_ev("2026-08-13T09:00:00")]) == []


def test_due_operazioni_ravvicinate_valgono_unita_minima():
    eventi = [_ev("2026-08-13T09:00:00"), _ev("2026-08-13T09:01:00")]
    sessioni = sessioni_da_eventi(eventi)
    assert len(sessioni) == 1
    assert sessioni[0].durata_minuti == DURATA_EVENTO_SINGOLO_MINUTI


def test_eventi_non_rilevanti_o_falliti_ignorati():
    eventi = [
        _ev("2026-08-13T09:00:00", azione="auth.login"),  # non e' lavoro sul fascicolo
        _ev("2026-08-13T09:01:00", esito="NEGATO"),
        _ev("2026-08-13T09:02:00", azione="fascicoli.apri"),
    ]
    assert sessioni_da_eventi(eventi) == []  # resta 1 solo evento valido → nessuna proposta


def test_utenti_e_fascicoli_separati():
    eventi = [
        _ev("2026-08-13T09:00:00", utente="U1"),
        _ev("2026-08-13T09:02:00", utente="U1"),
        _ev("2026-08-13T09:00:00", utente="U2", fascicolo="F2"),
        _ev("2026-08-13T09:03:00", utente="U2", fascicolo="F2"),
    ]
    sessioni = sessioni_da_eventi(eventi)
    assert len(sessioni) == 2
    assert {(s.utente_id, s.fascicolo_id) for s in sessioni} == {("U1", "F1"), ("U2", "F2")}


# --- Proposte --------------------------------------------------------------------


@pytest.fixture
def gestione(tmp_path):
    return GestioneTrackingPassivo(db_path=str(tmp_path / "tracking.json"))


def _eventi_sessione():
    return [
        _ev("2026-08-13T09:00:00"),
        _ev("2026-08-13T09:10:00", azione="documenti.visualizza"),
        _ev("2026-08-13T09:25:00", azione="editor.salva"),
    ]


def test_genera_idempotente(gestione):
    prime = gestione.genera_da_eventi(_eventi_sessione())
    seconde = gestione.genera_da_eventi(_eventi_sessione())
    assert len(prime) == 1
    assert seconde == []
    assert len(gestione.bozze()) == 1
    assert prime[0]["minuti"] == 25
    assert "operazioni" in prime[0]["descrizione"]


def test_conferma_crea_voce_timesheet(gestione):
    proposta = gestione.genera_da_eventi(_eventi_sessione())[0]
    creati = []

    def crea_voce(payload):
        creati.append(payload)
        return {"id": "VT-1"}

    esito = gestione.conferma(proposta["id"], crea_voce_timesheet=crea_voce, minuti=30)
    assert esito["stato"] == StatoProposta.CONFERMATA
    assert esito["minuti"] == 30  # l'avvocato ha corretto la durata
    assert esito["voce_timesheet_id"] == "VT-1"
    assert creati[0]["origine"] == "tracking_passivo"
    assert creati[0]["id_fascicolo"] == "F1"
    assert gestione.bozze() == []


def test_scartata_non_si_ripresenta(gestione):
    proposta = gestione.genera_da_eventi(_eventi_sessione())[0]
    gestione.scarta(proposta["id"], motivo="Attivita' non fatturabile")
    assert gestione.bozze() == []
    assert gestione.genera_da_eventi(_eventi_sessione()) == []  # chiave gia' nota


def test_conferma_richiede_minuti_positivi(gestione):
    proposta = gestione.genera_da_eventi(_eventi_sessione())[0]
    with pytest.raises(ValueError, match="durata positiva"):
        gestione.conferma(proposta["id"], crea_voce_timesheet=lambda p: {"id": "X"}, minuti=0)


def test_persistenza_round_trip(tmp_path):
    percorso = str(tmp_path / "tracking.json")
    primo = GestioneTrackingPassivo(db_path=percorso)
    primo.genera_da_eventi(_eventi_sessione())
    secondo = GestioneTrackingPassivo(db_path=percorso)
    assert len(secondo.bozze()) == 1
