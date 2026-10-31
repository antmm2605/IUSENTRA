"""Notifiche ricevute dalla controparte: atto, perfezionamento per il destinatario e termini (31/10/2026)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from pct.notifiche_ricevute import (
    atto_notificato,
    direzione_notifica,
    oggetto_di_notifica_l53,
    perfezionamento_destinatario,
    termini_da_notifica_ricevuta,
)

CONSEGNA = datetime(2026, 7, 10, 10, 0)


def test_oggetto_della_notifica_in_proprio():
    assert oggetto_di_notifica_l53("Notificazione ai sensi della legge n. 53 del 1994 - Rossi c. Bianchi")
    assert not oggetto_di_notifica_l53("Trasmissione documenti")


@pytest.mark.parametrize(
    ("casella", "mittente", "cartella", "attesa"),
    [
        ("studio@pec.it", "Avv. Rossi <rossi@pec.it>", "INBOX", "ricevuta"),
        ("studio@pec.it", "STUDIO@pec.it", "INBOX", "inviata"),
        ("studio@pec.it", "altro@pec.it", "Posta inviata", "inviata"),
        ("", "rossi@pec.it", "INBOX", ""),
    ],
)
def test_direzione_della_notifica(casella, mittente, cartella, attesa):
    assert direzione_notifica(casella=casella, mittente=mittente, cartella=cartella) == attesa


@pytest.mark.parametrize(
    ("consegna", "attesa"),
    [
        (datetime(2026, 7, 31, 22, 10), date(2026, 8, 1)),  # dopo le 21: il giorno dopo alle 7
        (datetime(2026, 7, 31, 6, 30), date(2026, 7, 31)),  # prima delle 7: stesso giorno alle 7
        (datetime(2026, 7, 31, 20, 59), date(2026, 7, 31)),
        (datetime(2026, 7, 31, 19, 30, tzinfo=timezone.utc), date(2026, 7, 31)),  # 21:30 a Roma
    ],
)
def test_perfezionamento_per_il_destinatario_art_147(consegna, attesa):
    if consegna.tzinfo is not None:
        attesa = date(2026, 8, 1)
    assert perfezionamento_destinatario(consegna) == attesa


@pytest.mark.parametrize(
    ("testo", "allegati", "codici"),
    [
        ("In forza del decreto ingiuntivo n. 123/2026", [], ["opposizione_decreto_ingiuntivo"]),
        ("ATTO DI PRECETTO", [], ["termine_adempimento_precetto", "opposizione_atti_esecutivi_precetto"]),
        ("RICORSO PER CASSAZIONE", [], ["controricorso"]),
        ("", ["Sentenza_Tribunale_Bari.pdf"], ["appello_breve"]),
        ("", ["Sentenza_Corte_d_Appello.pdf"], ["ricorso_cassazione_breve"]),
        ("ATTO DI APPELLO avverso la sentenza n. 45/2026; udienza del 15/12/2026", [], ["costituzione_appellato"]),
        ("ATTO DI CITAZIONE: cita a comparire all'udienza del 10/12/2026", [], ["costituzione_convenuto"]),
    ],
)
def test_ogni_atto_notificato_apre_il_suo_termine(testo, allegati, codici):
    proposte = termini_da_notifica_ricevuta(testo, consegna=CONSEGNA, nomi_allegati=allegati)
    assert [p["codice_termine"] for p in proposte] == codici
    assert all(p["create_in_scadenziario"] and p["human_review_required"] and p["peremptory"] for p in proposte)


def test_il_termine_decorre_dal_perfezionamento_e_quello_a_ritroso_dall_udienza():
    decreto = termini_da_notifica_ricevuta("decreto ingiuntivo", consegna=datetime(2026, 7, 31, 22, 10))[0]
    assert decreto["dies_a_quo_date"] == "2026-08-01" and decreto["duration_value"] == 40
    citazione = termini_da_notifica_ricevuta("atto di citazione, udienza del 10/12/2026", consegna=CONSEGNA)[0]
    assert citazione["dies_a_quo_date"] == "2026-12-10" and citazione["direction"] == "backward"


def test_senza_udienza_o_con_data_impossibile_il_termine_a_ritroso_non_si_propone():
    assert termini_da_notifica_ricevuta("atto di citazione", consegna=CONSEGNA) == []
    assert termini_da_notifica_ricevuta("atto di citazione, udienza del 31/02/2027", consegna=CONSEGNA) == []


def test_un_atto_non_riconosciuto_non_apre_termini():
    assert atto_notificato("Trasmissione documenti") is None
    assert termini_da_notifica_ricevuta("Trasmissione documenti", consegna=CONSEGNA) == []
