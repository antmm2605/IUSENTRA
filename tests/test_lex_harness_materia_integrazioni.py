"""Regole aggiunte dopo la valutazione indipendente e risposte completate: frasi nuove, con refusi, racconti e chi subisce."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla, risposta

CASI = [
    ("Mio padre è morto a marzo lasciando solo debiti con le banche: io e mia sorella non vogliamo l'eredita, come si fa?", "suc_rinuncia_eredita"),
    ("Buongiorno avvocato, mia madre è mancata e ho saputo che aveva un sacco di debiti. Posso rinunciare all'eredità? E i miei figli?", "suc_rinuncia_eredita"),
    ("rinuncia eredita: dal notaio o in tribunale?", "suc_rinuncia_eredita"),
    ("Ho rinunciato all'eredità dello zio ma ora so che c'era una casa: posso tornare indietro?", "suc_rinuncia_eredita"),
    ("La cliente non vuole accettare l'eredità del marito perché ci sono cartelle esattoriali enormi.", "suc_rinuncia_eredita"),
    ("Il cliente è stato tamponato a giugno, la compagnia non paga: prima di fare causa serve l'invito alla negoziazione?", "rc_negoziazione_sinistri"),
    ("sinistro stradale con lesioni lievi, l'assicurazione tace da 4 mesi: possiamo andare direttamente dal giudice?", "rc_negoziazione_sinistri"),
    ("Incidente in moto, abbiamo mandato la richiesta danni all'assicurazione: quando possiamo invitarla alla negoziazione assistita?", "rc_negoziazione_sinistri"),
    ("La negoziazione assistita per un incidente stradale da 80.000 euro è comunque obbligatoria?", "rc_negoziazione_sinistri"),
    ("Mi hanno investito e l'avvocato della compagnia dice che prima della causa serve la procedura con gli avvocati: è vero?", "rc_negoziazione_sinistri"),
    ("Sono un cameriere, il ristorante non mi paga da tre mesi ma ho le buste paga firmate: posso avere un decreto ingiuntivo?", "lav_decreto_ingiuntivo"),
    ("Decreto ingiuntivo per la tredicesima non pagata dal datore: davanti a quale giudice?", "lav_decreto_ingiuntivo"),
    ("La lavoratrice ha le busta paga di ottobre e novembre ma non ha ricevuto lo stipendio: come otteniamo subito un'ingiunzione?", "lav_decreto_ingiuntivo"),
    ("Il datore deve all'operaio le ferie non godute e il tfr: facciamo un ricorso monitorio?", "lav_decreto_ingiuntivo"),
    ("Ingiunzione di pagamento per le mensilità arretrate di un dipendente di una pizzeria.", "lav_decreto_ingiuntivo"),
    ("Il cliente ha cartelle INPS e IRPEF dal 2015 al 2021: può ancora fare la rottamazione?", "trib_definizione_agevolata"),
    ("C'è una definizione agevolata delle cartelle quest'anno? Come funziona con le rate?", "trib_definizione_agevolata"),
    ("Vorrei la pace fiscale per i debiti con l'agenzia riscossione di mio padre.", "trib_definizione_agevolata"),
    ("Con la rottamazione delle multe stradali si risparmiano anche le sanzioni?", "trib_definizione_agevolata"),
    ("Ho aderito alla rottamazione ma ho saltato due rate: cosa succede?", "trib_definizione_agevolata"),
    ("Il collega era ricoverato in ospedale e il termine per la memoria è scaduto: possiamo chiedere la rimessione in termini?", "civ_rimessione_termini"),
    ("La PEC della cancelleria non è mai arrivata e siamo decaduti dalla prova: rimedio?", "civ_rimessione_termini"),
    ("Rimessione in termini nel processo civile: cosa bisogna dimostrare?", "civ_rimessione_termini"),
    ("Per un guasto del sistema non abbiamo potuto depositare e il termine è scaduto ieri.", "civ_rimessione_termini"),
    ("Siamo decaduti dal termine per causa non imputabile: come si chiede al giudice di rimetterci?", "civ_rimessione_termini"),
    ("Mio marito è stato condannato definitivamente a 18 anni: posso divorziare subito senza separazione?", "fam_divorzio_immediato"),
    ("Il coniuge è stato condannato per maltrattamenti in famiglia contro di me due volte: divorzio immediato?", "fam_divorzio_immediato"),
    ("Lui ha tentato di uccidermi ed è stato condannato: devo prima separarmi per divorziare?", "fam_divorzio_immediato"),
    ("Mia moglie è in carcere con l'ergastolo, come chiedo il divorzio?", "fam_divorzio_immediato"),
    ("Divorzio diretto per condanna penale del coniuge: quali reati contano?", "fam_divorzio_immediato"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_integrate(frase, regola):
    from tests.lex_materie_casi import EQUIVALENTI

    # La regola principale del sinistro (lex-regole) tratta anche la negoziazione obbligatoria: risposta equivalente.
    EQUIVALENTI.setdefault("rc_negoziazione_sinistri", set()).add("sinistro_stradale")
    controlla(frase, regola)


def test_appello_lavoro_anche_termine_lungo():
    r = risposta("Prepara l'appello del lavoratore contro la sentenza del giudice del lavoro che gli ha negato gli straordinari.")
    assert "sei mesi dalla pubblicazione" in r.testo and "trenta giorni dalla notificazione" in r.testo


def test_istat_solo_dalla_richiesta_scritta():
    r = risposta("Il padrone di casa vuole gli aumenti ISTAT degli ultimi quattro anni mai chiesti: deve pagarli l'inquilino?")
    assert "dalla richiesta scritta" in r.testo


def test_citazione_segnala_negoziazione_fino_a_50000():
    r = risposta("Devo fare causa al cliente che non mi paga 12.000 euro di lavori: come preparo l'atto di citazione?")
    assert "50.000 euro" in r.testo


def test_2932_trascrizione_della_domanda():
    r = risposta("Il promittente venditore non si presenta dal notaio: voglio la sentenza che trasferisca la casa.")
    assert "va trascritta" in r.testo


def test_ogni_regola_ha_lato_sinonimi_situazioni():
    from lex.harness.fattispecie.materie import SCHEDE

    for s in SCHEDE:
        assert s.lato in {"attivo", "passivo", "entrambi"}, s.regola
        assert len(s.sinonimi) >= 2 and len(s.situazioni) >= 3, s.regola
