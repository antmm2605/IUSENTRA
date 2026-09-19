"""Sorveglianza del decreto biennale che adegua la soglia del patrocinio.

Art. 77 D.P.R. 115/2002: l'importo dell'art. 76 si adegua ogni due anni con
decreto interministeriale pubblicato in Gazzetta. Il controllo non riscrive la
soglia: prepara la riga e la fa confermare, perche' una soglia di legge la
accetta una persona, sull'atto.
"""

from __future__ import annotations

from pct.patrocinio_adeguamento import (
    controlla_adeguamento,
    importo_dichiarato,
    proposta_di_aggiornamento,
    riguarda_il_patrocinio,
)


class _Norme:
    def rows(self, tabella: str, on_date=None):
        return [
            {"effective_from": "2023-06-06", "amount": 12838.01, "decreto": "D.M. 10 maggio 2023"},
            {"effective_from": "2025-07-11", "amount": 13659.64, "decreto": "D.M. 22 aprile 2025"},
        ]


ATTO_NUOVO = {
    "titolo": "Adeguamento dei limiti di reddito per l'ammissione al patrocinio a spese dello Stato",
    "testo": "L'importo di cui all'articolo 76, comma 1, e' adeguato in euro 14.523,18.",
    "data": "2027-07-09",
    "url": "https://www.gazzettaufficiale.it/eli/id/2027/07/09/27A00001/sg",
}
ATTO_ESTRANEO = {
    "titolo": "Adeguamento delle tariffe postali",
    "testo": "Importi rideterminati in euro 15.000,00.",
    "data": "2027-08-01",
    "url": "https://www.gazzettaufficiale.it/eli/id/2027/08/01/27A00002/sg",
}


def test_riconosce_solo_gli_atti_sul_patrocinio():
    assert riguarda_il_patrocinio(ATTO_NUOVO["titolo"], ATTO_NUOVO["testo"]) is True
    assert riguarda_il_patrocinio(ATTO_ESTRANEO["titolo"], ATTO_ESTRANEO["testo"]) is False


def test_legge_l_importo_dichiarato_dall_atto():
    assert str(importo_dichiarato(ATTO_NUOVO["testo"])) == "14523.18"
    assert importo_dichiarato("nessun importo qui") is None


def test_un_decreto_nuovo_diventa_una_riga_da_confermare():
    esito = proposta_di_aggiornamento([ATTO_NUOVO, ATTO_ESTRANEO], _Norme())

    assert esito["aggiornamento"] is True
    assert esito["riga_proposta"]["amount"] == 14523.18
    assert esito["riga_proposta"]["effective_from"] == "2027-07-09"
    # il parametro dell'art. 9 comma 1-bis e' il triplo, e si dice
    assert "43.569,54" in esito["messaggio"]
    assert "14.523,18" in esito["messaggio"]


def test_senza_decreti_nuovi_la_soglia_resta_quella():
    esito = proposta_di_aggiornamento([ATTO_ESTRANEO], _Norme())

    assert esito["aggiornamento"] is False
    assert "13.659,64" in esito["messaggio"]


def test_un_decreto_gia_in_tabella_non_si_ripropone():
    gia_noto = dict(ATTO_NUOVO, data="2025-07-11", testo="importo adeguato in euro 13.659,64")

    assert proposta_di_aggiornamento([gia_noto], _Norme())["aggiornamento"] is False


def test_un_atto_senza_importo_leggibile_chiede_di_aprirlo():
    senza_importo = dict(ATTO_NUOVO, testo="Adeguamento del limite di reddito per il patrocinio.")

    esito = proposta_di_aggiornamento([senza_importo], _Norme())

    assert esito["aggiornamento"] is True
    assert esito["riga_proposta"]["amount"] is None
    assert "non e' leggibile" in esito["messaggio"]


def test_se_la_gazzetta_non_risponde_non_si_inventa_nulla():
    def fonte_muta():
        raise RuntimeError("timeout")

    esito = controlla_adeguamento(_Norme(), fonte_muta)

    assert esito["aggiornamento"] is False
    assert "non raggiungibile" in esito["messaggio"]
