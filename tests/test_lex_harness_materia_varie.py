"""Regole di famiglia, locazioni, consumatori, tributario, immigrazione e stragiudiziale: frasi libere per regola."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla

CASI = [
    ("Non eravamo sposati e ci siamo lasciati: come regoliamo l'affidamento della bambina?", "fam_affidamento_figli"),
    ("La madre vuole trasferirsi a Torino con il figlio: il padre può chiedere il collocamento presso di sé?", "fam_affidamento_figli"),
    ("Prepara il ricorso per l'affidamento esclusivo del minore al padre.", "fam_affidamento_figli"),
    ("La madre impedisce al padre di vedere i figli da mesi: cosa facciamo?", "fam_affidamento_figli"),
    ("Quale tribunale decide sull'affidamento se il bambino vive a Palmi con la nonna?", "fam_affidamento_figli"),
    ("L'inquilino deve trasferirsi per lavoro: può recedere dal contratto 4+4 prima della scadenza?", "loc_recesso_conduttore"),
    ("Recesso del conduttore dal contratto di locazione commerciale per gravi motivi: quanto preavviso?", "loc_recesso_conduttore"),
    ("Prepara la lettera di recesso dell'inquilino dalla locazione abitativa.", "loc_recesso_conduttore"),
    ("Il conduttore vuole lasciare la casa dopo un anno: deve pagare i canoni fino alla fine?", "loc_recesso_conduttore"),
    ("Il contratto di affitto prevede il recesso libero del conduttore con tre mesi di preavviso: è valido?", "loc_recesso_conduttore"),
    ("Il locatore chiede l'aggiornamento ISTAT del canone per gli ultimi tre anni: è dovuto?", "loc_aggiornamento_istat"),
    ("L'adeguamento del canone del negozio può superare il 75% dell'ISTAT?", "loc_aggiornamento_istat"),
    ("Prepara la richiesta di aggiornamento del canone di locazione.", "loc_aggiornamento_istat"),
    ("Con la cedolare secca si può chiedere la rivalutazione del canone?", "loc_aggiornamento_istat"),
    ("Aggiornamento del canone: è automatico o va chiesto ogni anno?", "loc_aggiornamento_istat"),
    ("Ho comprato un divano online e voglio restituirlo: entro quanti giorni posso recedere?", "cons_recesso"),
    ("Contratto firmato a casa con un venditore porta a porta: il consumatore può ripensarci?", "cons_recesso"),
    ("Prepara la comunicazione di recesso dal contratto concluso a distanza.", "cons_recesso"),
    ("Il sito non mi ha informato del diritto di recesso: quanto tempo ho per recedere?", "cons_recesso"),
    ("Abbonamento firmato fuori dai locali commerciali: si può recedere senza penali?", "cons_recesso"),
    ("La compagnia telefonica mi ha attivato servizi non richiesti: è una pratica commerciale scorretta?", "cons_pratiche_scorrette"),
    ("Pubblicità ingannevole sul prezzo dell'auto: possiamo segnalarla all'AGCM?", "cons_pratiche_scorrette"),
    ("Prepara una segnalazione all'Antitrust per pratica aggressiva.", "cons_pratiche_scorrette"),
    ("Il venditore ha usato pressioni insistenti: pratica commerciale aggressiva?", "cons_pratiche_scorrette"),
    ("Cosa si intende per pratica commerciale ingannevole verso il consumatore?", "cons_pratiche_scorrette"),
    ("Bolletta della luce contestata: devo fare la conciliazione ARERA prima del giudice?", "cons_adr"),
    ("Per una lite con l'operatore telefonico serve il Corecom?", "cons_adr"),
    ("Prepara la domanda di conciliazione paritetica con il gestore del gas.", "cons_adr"),
    ("Quali procedure ADR esistono per le controversie di consumo?", "cons_adr"),
    ("La conciliazione per la bolletta del telefono è obbligatoria?", "cons_adr"),
    ("L'Agenzia delle Entrate ha sbagliato il calcolo dell'imposta: chiediamo l'autotutela?", "trib_autotutela"),
    ("Autotutela obbligatoria: in quali casi l'ufficio deve annullare l'atto?", "trib_autotutela"),
    ("Prepara l'istanza di autotutela per la cartella già pagata.", "trib_autotutela"),
    ("L'istanza di autotutela sospende il termine per impugnare l'avviso?", "trib_autotutela"),
    ("Il Comune ha richiesto l'IMU per un immobile venduto: autotutela?", "trib_autotutela"),
    ("Possiamo fare accertamento con adesione sull'avviso IRPEF notificato ieri?", "trib_adesione"),
    ("L'istanza di adesione sospende il termine per il ricorso?", "trib_adesione"),
    ("Prepara l'istanza di accertamento con adesione all'Agenzia delle entrate.", "trib_adesione"),
    ("Vorremmo trattare con l'Agenzia delle entrate per ridurre l'accertamento: come?", "trib_adesione"),
    ("Adesione dopo il contraddittorio preventivo: è ancora possibile?", "trib_adesione"),
    ("Il cliente ha cartelle per 60.000 euro: in quante rate può pagarle?", "trib_rateizzazione"),
    ("Rateizzazione delle cartelle: cosa succede se salto qualche rata?", "trib_rateizzazione"),
    ("Prepara la richiesta di dilazione all'Agenzia delle entrate-Riscossione.", "trib_rateizzazione"),
    ("Debito con la riscossione di 200.000 euro: si può avere la rateazione?", "trib_rateizzazione"),
    ("La dilazione dei ruoli nel 2027 quante rate prevede?", "trib_rateizzazione"),
    ("La Commissione territoriale ha negato l'asilo al mio assistito: entro quando ricorriamo?", "imm_protezione_internazionale"),
    ("Riconosciuta solo la protezione sussidiaria e non lo status di rifugiato: possiamo impugnare?", "imm_protezione_internazionale"),
    ("Prepara il ricorso contro il diniego della protezione internazionale.", "imm_protezione_internazionale"),
    ("Protezione speciale negata dalla Commissione: a quale giudice?", "imm_protezione_internazionale"),
    ("Il richiedente asilo è all'estero: il termine per il ricorso è più lungo?", "imm_protezione_internazionale"),
    ("Vogliamo chiudere la causa con un accordo transattivo: cosa deve contenere?", "str_transazione"),
    ("La transazione firmata si può annullare se scopriamo nuovi documenti?", "str_transazione"),
    ("Prepara un accordo transattivo per il pagamento a rate di 8.000 euro.", "str_transazione"),
    ("Si può fare una transazione su diritti indisponibili?", "str_transazione"),
    ("Reciproche concessioni per chiudere la lite con il fornitore: come scriviamo la transazione?", "str_transazione"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_varie(frase, regola):
    controlla(frase, regola)
