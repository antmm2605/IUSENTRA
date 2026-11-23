"""Deviazioni pericolose trovate dalla mappa di copertura degli strumenti (23/11/2026): ogni frase deve arrivare alla regola
del suo strumento e non a una regola vicina che darebbe termini o giudice sbagliati.

Le frasi sono nuove: diverse da quelle del catalogo di copertura, dei banchi e dei casi indipendenti."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.comprensione import comprendi
from lex.harness.fatti import leggi_fatti
from lex.harness.fattispecie import scegli

OGGI = date(2026, 11, 23)

AMMINISTRATIVO_TRIBUTARIO = [
    ("Il Comune di Lecco ha comunicato il 02/11/2026 l'aggiudicazione dell'appalto del servizio mensa a un'altra ditta: entro "
     "quando impugniamo?", "appalti_120"),
    ("La stazione appaltante ci ha escluso dalla procedura per la fornitura di arredi: come reagiamo?", "appalti_120"),
    ("L'ASL non ha mai risposto alla nostra istanza di accesso ai documenti del concorso: cosa possiamo fare?", "accesso_atti"),
    ("Il Ministero tace da otto mesi sulla domanda di riconoscimento del titolo, il procedimento doveva chiudersi in novanta "
     "giorni: quale azione abbiamo?", "silenzio"),
    ("Pende il nostro ricorso al TAR contro il diniego e il Comune ha emesso un provvedimento connesso di conferma: possiamo "
     "impugnarlo nello stesso giudizio?", "motivi_aggiunti"),
    ("La Regione non dà esecuzione alla sentenza del TAR passata in giudicato che ci ha dato ragione: come la costringiamo?",
     "ottemperanza"),
    ("Al marito della cliente è stato negato il ricongiungimento familiare dalla Prefettura: a chi ci rivolgiamo?",
     "permesso_soggiorno"),
    ("La Corte di giustizia tributaria di primo grado di Bari ha rigettato il nostro ricorso sull'IRPEF, sentenza notificata il "
     "05/11/2026: entro quando appelliamo?", "appello_tributario"),
    ("Abbiamo impugnato l'avviso di accertamento IVA ma l'Agenzia delle Entrate Riscossione ha iscritto ipoteca: chiediamo la "
     "sospensione?", "sospensione_tributaria"),
    ("Per un avviso di accertamento di 9.000 euro dobbiamo ancora presentare il reclamo prima del ricorso tributario?",
     "reclamo_mediazione_tributaria"),
    ("Possiamo proporre ricorso straordinario al Capo dello Stato invece di andare al TAR contro l'esclusione dal concorso?",
     "ricorso_straordinario"),
]


def _regola(frase):
    c = comprendi(frase)
    assert c.per_harness, frase
    r = scegli(c, leggi_fatti(frase, oggi=OGGI))
    return r[0] if r else None


@pytest.mark.parametrize("frase,regola", AMMINISTRATIVO_TRIBUTARIO)
def test_amministrativo_e_tributario_alla_regola_giusta(frase, regola):
    assert _regola(frase) == regola


def test_appalti_trenta_giorni_non_sessanta():
    r = rispondi(AMMINISTRATIVO_TRIBUTARIO[0][0], oggi=OGGI)
    assert r.regola == "appalti_120" and "trenta giorni" in r.testo and "02/12/2026" in r.testo
    assert "cpa:120" in r.norme_verificate and not r.affermazioni_tolte


def test_unita_familiare_al_tribunale_ordinario_non_al_tar():
    r = rispondi(AMMINISTRATIVO_TRIBUTARIO[6][0], oggi=OGGI)
    assert "autorita' giudiziaria ordinaria" in r.testo or "autorità giudiziaria ordinaria" in r.testo
    assert "dlgs286:30" in r.norme_verificate


def test_appello_tributario_dalla_notifica_della_sentenza():
    r = rispondi(AMMINISTRATIVO_TRIBUTARIO[7][0], oggi=OGGI)
    assert "04/01/2027" in r.testo                   # sessanta giorni dal 05/11/2026
    assert "dlgs546:51" in r.norme_verificate and not r.affermazioni_tolte


def test_reclamo_mediazione_tributaria_abrogato():
    r = rispondi(AMMINISTRATIVO_TRIBUTARIO[9][0], oggi=OGGI)
    assert r.regola == "reclamo_mediazione_tributaria" and "abrogato" in r.testo


def test_straordinario_non_cade_sul_tar():
    r = rispondi(AMMINISTRATIVO_TRIBUTARIO[10][0], oggi=OGGI)
    assert r.regola == "ricorso_straordinario" and "centoventi giorni" in r.testo


def test_le_parole_accesso_e_silenzio_non_bastano():
    assert _regola_o_none("Prepara la domanda di accesso al fondo di garanzia per le PMI.") != "accesso_atti"


def _regola_o_none(frase):
    c = comprendi(frase)
    if not c.per_harness:
        return None
    r = scegli(c, leggi_fatti(frase, oggi=OGGI))
    return r[0] if r else None
