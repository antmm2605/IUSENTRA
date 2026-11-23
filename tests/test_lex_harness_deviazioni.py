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


PUBBLICO = [
    ("Assisto una docente di ruolo dell'istituto scolastico di Matera, addetta alla sede di Pisticci: il Ministero non le ha "
     "pagato gli scatti di anzianità. Quale tribunale è competente?", "ricorso_dipendente_pubblico"),
    ("Un dipendente del Comune di Enna lamenta il demansionamento: TAR o giudice del lavoro?", "ricorso_dipendente_pubblico"),
    ("All'assistito l'INPS ha respinto la domanda di NASpI con provvedimento del 03/11/2026: come la contestiamo?",
     "ricorso_amministrativo_inps"),
    ("L'ASL non paga le somme liquidate dalla sentenza del tribunale notificata il 10/09/2026: quando possiamo notificare il "
     "precetto?", "esecuzione_contro_pa"),
    ("La Direzione territoriale del lavoro ha notificato il 04/11/2026 un'ordinanza-ingiunzione da 3.000 euro alla ditta del "
     "cliente: come la impugniamo?", "ordinanza_ingiunzione"),
]


@pytest.mark.parametrize("frase,regola", PUBBLICO)
def test_pubblico_impiego_previdenza_e_sanzioni_alla_regola_giusta(frase, regola):
    assert _regola(frase) == regola


def test_foro_del_dipendente_pubblico_e_quello_dell_ufficio():
    r = rispondi(PUBBLICO[0][0], oggi=OGGI)
    assert "ufficio al quale il dipendente" in r.testo or "l'ufficio al quale il dipendente è" in r.testo
    assert "cpc:413" in r.norme_verificate and "dlgs165:63" in r.norme_verificate and not r.affermazioni_tolte


def test_previdenza_non_al_tar_e_improcedibilita():
    r = rispondi(PUBBLICO[2][0], oggi=OGGI)
    assert "non è il TAR" in r.testo and "centottanta giorni" in r.testo


def test_esecuzione_contro_la_pa_centoventi_giorni():
    r = rispondi(PUBBLICO[3][0], oggi=OGGI)
    assert "08/01/2027" in r.testo                    # 120 giorni dal 10/09/2026
    assert "dl669:14" in r.norme_verificate


def test_ordinanza_ingiunzione_trenta_giorni_non_decreto_ingiuntivo():
    r = rispondi(PUBBLICO[4][0], oggi=OGGI)
    assert r.regola == "ordinanza_ingiunzione" and "trenta giorni" in r.testo and "04/12/2026" in r.testo
    assert "641" not in r.testo and "645" not in r.testo


def test_verbale_cds_indica_anche_il_prefetto():
    r = rispondi("Al cliente è stato notificato il 12/11/2026 un verbale per eccesso di velocità a Prato: meglio il prefetto o il "
                 "giudice di pace?", oggi=OGGI)
    assert r.regola == "opposizione_verbale_cds" and "prefetto" in r.testo and "sessanta giorni" in r.testo


CIVILE_ESECUZIONE_FAMIGLIA_LOCAZIONE = [
    ("Ricevuto un precetto da 4.200 euro, ma la cliente aveva già saldato tutto con bonifico a marzo: come reagiamo?",
     "opposizione_precetto"),
    ("Nel precetto notificato al cliente manca la sottoscrizione del difensore: come lo contestiamo?",
     "opposizione_atti_esecutivi"),
    ("Abbiamo un decreto ingiuntivo esecutivo contro un debitore che lavora in un'azienda di Rovigo: possiamo pignorargli lo "
     "stipendio?", "pignoramento_terzi"),
    ("Non sappiamo quali conti abbia il debitore: possiamo far cercare i beni nelle banche dati con l'ufficiale giudiziario?",
     "ricerca_beni"),
    ("L'ex marito della cliente ha perso il lavoro e chiede di ridurre l'assegno di mantenimento fissato nel divorzio: come "
     "procediamo?", "modifica_condizioni"),
    ("I coniugi vogliono separarsi con l'accordo degli avvocati senza andare in tribunale, hanno un figlio di sei anni: si può "
     "fare la negoziazione assistita?", "negoziazione_familiare"),
    ("La compagna convivente del cliente subisce violenze domestiche: possiamo chiedere l'allontanamento di lui dalla casa "
     "familiare?", "ordini_protezione"),
    ("Il contratto di locazione dell'appartamento di Pavia è scaduto a settembre e l'inquilino non vuole lasciare la casa: "
     "come procediamo?", "sfratto_finita_locazione"),
    ("Il giudice ha convalidato lo sfratto ma il conduttore è ancora nell'immobile: come lo facciamo uscire?", "rilascio"),
    ("Rappresento Lia Conti, inquilina: il proprietario le ha intimato sfratto ma i canoni non erano dovuti per i vizi della casa. "
     "Come ci difendiamo?", "opposizione_convalida"),
    ("Per l'affitto dell'appartamento di Siena il proprietario non restituisce il deposito cauzionale di 1.400 euro: quale "
     "giudice?", "causa_locazione"),
    ("Nel preliminare abbiamo pattuito una caparra penitenziale di 5.000 euro: il cliente vuole recedere, cosa perde?",
     "recesso_contratto"),
    ("L'impresa non consegna i mobili ordinati: mandiamo una diffida ad adempiere per risolvere il contratto?", "diffida_1454"),
]


@pytest.mark.parametrize("frase,regola", CIVILE_ESECUZIONE_FAMIGLIA_LOCAZIONE)
def test_civile_esecuzione_famiglia_locazione_alla_regola_giusta(frase, regola):
    assert _regola(frase) == regola


def test_ordini_di_protezione_nel_codice_di_procedura():
    r = rispondi(CIVILE_ESECUZIONE_FAMIGLIA_LOCAZIONE[6][0], oggi=OGGI)
    assert "cpc:473bis69" in r.norme_verificate and "342-bis" in r.testo and not r.affermazioni_tolte


def test_negoziazione_familiare_con_figli_minori_serve_l_autorizzazione():
    r = rispondi(CIVILE_ESECUZIONE_FAMIGLIA_LOCAZIONE[5][0], oggi=OGGI)
    assert "dieci giorni" in r.testo and "autorizz" in r.testo and "dl132:6" in r.norme_verificate


def test_pignoramento_dello_stipendio_un_quinto():
    r = rispondi(CIVILE_ESECUZIONE_FAMIGLIA_LOCAZIONE[2][0], oggi=OGGI)
    assert "un quinto" in r.testo and "cpc:545" in r.norme_verificate


def test_cauzione_della_locazione_non_va_alla_competenza_per_valore():
    assert _regola("Causa per la cauzione dell'affitto di 900 euro: chi decide?") != "competenza_pagamento"
