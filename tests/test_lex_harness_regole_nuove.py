"""Tre regole nuove dell'harness (23/11/2026): sequestro conservativo ante causam, garanzia nella vendita al consumatore,
locazione con morosità e condizioni di procedibilità chieste con parole libere.

Le frasi sono nuove: diverse dai 22 casi dell'avvocato, dalla batteria da 47, dai 100 casi indipendenti e dal dataset
sintetico. Ogni risposta deve passare il controllo delle norme sul testo vigente senza affermazioni tolte."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi

OGGI = "\n\nOggi è il 23/11/2026."

SEQUESTRO = [
    "Il mio cliente Bruno Gatti vanta un credito di 48.000 euro verso Carlo Mele, residente a Verona, per un prestito "
    "documentato. Mele sta vendendo i suoi due appartamenti. Possiamo chiedere il sequestro prima di fare causa?",
    "Assisto Delta Costruzioni s.r.l.: la Omega Impianti s.r.l., con sede a Parma, ci deve 120.000 euro di fatture e sta "
    "svuotando i conti correnti. Come blocchiamo i suoi beni prima della causa?",
    "Una cliente ha prestato 9.000 euro all'ex compagno, residente a Lecce, che ora si sta trasferendo all'estero e ha messo "
    "in vendita l'auto. Prepara il ricorso per sequestro conservativo.",
]
GARANZIA = [
    "La mia cliente Laura Neri ha comprato il 10/03/2025 in un negozio di Firenze una lavatrice da 780 euro, consegnata il "
    "15/03/2025. Dal 02/11/2026 non funziona più e il venditore la rimanda al produttore. Che diritti ha?",
    "Un consumatore ha acquistato online uno smartphone da 1.100 euro, ricevuto il 20/09/2026; dopo un mese si spegne da solo. "
    "Può pretendere la sostituzione o la restituzione dei soldi?",
    "Assisto Paolo Riva: ha comprato da un concessionario di Bergamo un'auto usata a 8.500 euro, consegnata il 05/05/2026; il "
    "cambio si è rotto il 30/10/2026. Il venditore rifiuta la riparazione. Come ci muoviamo?",
]
LOCAZIONE = [
    "Il mio cliente affitta un appartamento a Torino a 700 euro al mese; l'inquilino non paga da cinque mesi. Prima di "
    "agire dobbiamo fare la mediazione?",
    "Locatrice di un negozio a Bari, canone 1.500 euro: il conduttore è moroso da marzo. Ci sono condizioni di procedibilità "
    "da rispettare prima dello sfratto?",
    "Per la morosità del conduttore di un bilocale a Genova (quattro canoni non pagati da 550 euro) serve il tentativo "
    "obbligatorio di conciliazione davanti a un organismo prima di andare dal giudice?",
]


@pytest.mark.parametrize("domanda,regola", [(d, "sequestro_ante_causam") for d in SEQUESTRO]
                         + [(d, "garanzia_conformita") for d in GARANZIA]
                         + [(d, "procedibilita_locazione") for d in LOCAZIONE])
def test_frasi_libere_trovano_la_regola_e_passano_il_controllo(domanda, regola):
    r = rispondi(domanda + OGGI, oggi=date(2026, 11, 23))
    assert r is not None and r.regola == regola
    assert not r.affermazioni_tolte, r.affermazioni_tolte
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate


def test_sequestro_competenza_termini_e_requisiti():
    r = rispondi(SEQUESTRO[0] + OGGI, oggi=date(2026, 11, 23))
    t = r.testo
    assert "fondato timore di perdere la garanzia" in t or "fondato timore" in t
    assert "Tribunale di Verona" in t
    assert "sessanta giorni" in t and "trenta giorni" in t
    assert {"cpc:671", "cpc:669ter", "cpc:669octies", "cpc:675"} <= set(r.norme_verificate)


def test_sequestro_merito_del_giudice_di_pace_va_al_tribunale():
    r = rispondi(SEQUESTRO[2] + OGGI, oggi=date(2026, 11, 23))
    assert "va comunque al tribunale" in r.testo
    assert r.bozza and "sequestro conservativo" in r.bozza.lower()


def test_sequestro_gia_ottenuto_resta_alla_regola_esistente():
    r = rispondi("Abbiamo ottenuto il sequestro conservativo con ordinanza di accoglimento del 10/11/2026, pronunciata fuori "
                 "udienza, per un prestito di 30.000 euro. Entro quando va eseguito?" + OGGI, oggi=date(2026, 11, 23))
    assert r.regola == "sequestro_conservativo"


def test_garanzia_termini_calcolati_dalla_consegna():
    r = rispondi(GARANZIA[0] + OGGI, oggi=date(2026, 11, 23))
    t = r.testo
    assert "15/03/2027" in t                     # due anni dalla consegna del 15/03/2025
    assert "15/05/2027" in t                     # ventisei mesi dalla consegna
    assert "riparazione" in t and "sostituzione" in t and "riduzione" in t and "risoluzione" in t
    assert "decadenza" in t                      # niente termine di denuncia nel testo vigente
    assert {"dlgs206:133", "dlgs206:135bis", "dlgs206:135"} <= set(r.norme_verificate)


def test_garanzia_bene_usato_e_presunzione_di_un_anno():
    r = rispondi(GARANZIA[2] + OGGI, oggi=date(2026, 11, 23))
    assert "non meno di un anno" in r.testo or "fino a un anno" in r.testo
    assert "un anno" in r.testo


def test_garanzia_non_scatta_fra_imprese_o_negli_appalti():
    r = rispondi("La Rossi s.r.l. ha acquistato per la sua azienda un compressore da 6.000 euro, difettoso dopo due mesi. "
                 "Cosa facciamo?" + OGGI, oggi=date(2026, 11, 23))
    assert r is None or r.regola != "garanzia_conformita"


def test_locazione_mediazione_esclusa_per_la_convalida():
    r = rispondi(LOCAZIONE[0] + OGGI, oggi=date(2026, 11, 23))
    t = r.testo
    assert "mutamento del rito" in t
    assert "improcedibil" in t
    assert "negoziazione assistita non è condizione" in t
    assert "dlgs28:5" in r.norme_verificate


def test_negoziazione_in_locazione_resta_alla_regola_esistente():
    r = rispondi("Il conduttore di un appartamento a Roma è moroso da tre mesi: mandiamo l'invito alla negoziazione "
                 "assistita?" + OGGI, oggi=date(2026, 11, 23))
    assert r.regola == "negoziazione_locazione_inadatta"
