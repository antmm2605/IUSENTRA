"""Lato della parte oltre esecuzione e sfratto: lavoro, condominio, sinistri, garanzia del consumatore, canone oltre quello
registrato (lex/harness/lato.py, lex/harness/fattispecie/difese.py).

Racconti nuovi in prima persona, scritti per questo controllo (24/11/2026), dalla parte di chi subisce; non vengono dalla
batteria, dai casi dell'avvocato né da banchi di misura.
"""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.lato import ATTIVO, PASSIVO, lato_della_parte
from lex.harness.norme import ISTANTANEA

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

OGGI = "\n\nOggi è il 24/11/2026."


def _r(testo: str):
    return rispondi(testo + OGGI, oggi=date(2026, 11, 24))


SUBISCE = [
    ("difesa_datore_lavoro",
     "Sono il titolare di una pizzeria a Salerno: un ex cameriere mi ha notificato un ricorso al giudice del lavoro per "
     "licenziamento illegittimo, con udienza fissata al 20/01/2027. Come mi difendo?",
     ("art. 416 c.p.c.", "10/01/2027")),
    ("difesa_datore_lavoro",
     "Ho una piccola ditta edile; un mio ex operaio mi ha mandato una lettera con cui impugna il licenziamento del "
     "15/10/2026. Cosa rischio e cosa devo fare?",
     ("centottanta giorni", "art. 6 d.lgs. 23/2015")),
    ("difesa_condominio",
     "Sono l'amministratore di un condominio a Rimini: un condomino ha impugnato la delibera del 10/10/2026 e mi è arrivata "
     "la domanda di mediazione. Come mi devo comportare?",
     ("art. 1131 c.c.", "notizia all'assemblea")),
    ("sinistro_responsabile",
     "Ho tamponato un'auto al semaforo il 03/11/2026 e ora il conducente mi chiede 4.000 euro di danni con una lettera del "
     "suo avvocato. Cosa devo fare?",
     ("art. 1913 c.c.", "tre giorni", "art. 1917 c.c.")),
    ("garanzia_venditore",
     "Ho un negozio di elettrodomestici a Siena: un cliente pretende la sostituzione di un frigorifero venduto il "
     "10/02/2026 che ora non raffredda. Devo sostituirlo? E posso rivalermi sul fornitore?",
     ("art. 134 d.lgs. 206/2005", "regresso")),
    ("locatore_canone_nero",
     "Sono il proprietario di un bilocale a Bologna: l'ex inquilino, che ha riconsegnato le chiavi il 31/01/2026, ora mi "
     "chiede indietro i soldi pagati in nero oltre il canone registrato. Devo restituirli?",
     ("31/07/2026", "art. 2969 c.c.", "scaduto")),
    ("opposizione_convalida",
     "Sono inquilina di un appartamento a Lecce: il proprietario mi ha intimato licenza per finita locazione con udienza il "
     "15/01/2027, ma il contratto si è rinnovato. Come mi difendo?",
     ("art. 663 c.p.c.",)),
]


@pytest.mark.parametrize("regola,testo,attesi", SUBISCE, ids=[f"{r}-{i}" for i, (r, _, _) in enumerate(SUBISCE)])
def test_chi_subisce_riceve_lo_strumento_del_suo_lato(regola, testo, attesi):
    r = _r(testo)
    assert r is not None and r.regola == regola, (r.regola if r else None)
    assert not r.affermazioni_tolte, r.affermazioni_tolte
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate
    for x in attesi:
        assert x in r.testo, x


AGISCE = [
    ("impugnazione_licenziamento", "Sono stato licenziato il 03/11/2026 dalla ditta per cui lavoravo a Ferrara. Come lo impugno?"),
    ("sinistro_stradale", "Mi hanno tamponato a Rovigo il 01/11/2026, l'altro conducente era assicurato con Gamma "
                          "Assicurazioni; ho danni per 2.000 euro. Come chiedo il risarcimento?"),
    ("garanzia_conformita", "Ho comprato un televisore da 900 euro, consegnato il 01/04/2026, che si è rotto il 10/11/2026. "
                            "Il venditore non risponde. Cosa posso fare?"),
    ("impugnazione_delibera", "Sono condomina di uno stabile a Varese: ho votato contro la delibera del 12/11/2026 che "
                              "approva lavori non necessari. Entro quando la impugno?"),
]


@pytest.mark.parametrize("regola,testo", AGISCE, ids=[r for r, _ in AGISCE])
def test_chi_agisce_resta_allo_strumento_di_chi_agisce(regola, testo):
    r = _r(testo)
    assert r is not None and r.regola == regola, (r.regola if r else None)


AMBIGUI = [
    ("Licenziamento per giusta causa comunicato il 10/11/2026 a un cameriere di un bar di Pisa. Cosa possiamo fare?",
     ("impugnazione_licenziamento", "difesa_datore_lavoro")),
    ("Incidente stradale a Prato il 02/11/2026: tamponamento fra due auto, entrambe assicurate, con danni per 3.500 euro. "
     "Come procediamo?", ("sinistro_stradale", "sinistro_responsabile")),
    ("Lavatrice venduta in un negozio di Lucca il 05/03/2026, consegnata il 10/03/2026, che ora perde acqua: il negozio non "
     "vuole ripararla. Cosa fare?", ("garanzia_conformita", "garanzia_venditore")),
]


@pytest.mark.parametrize("testo,regole", AMBIGUI, ids=["lavoro", "sinistro", "garanzia"])
def test_lato_ignoto_lex_chiede_con_due_opzioni_che_portano_alle_due_regole(testo, regole):
    r = _r(testo)
    assert r.regola == "chiarimento_lato"
    scelte = r.registro["scelte"]
    assert len(scelte) == 2
    assert [_r(s).regola for s in scelte] == list(regole)


def test_lettera_di_licenziamento_ricevuta_e_il_lavoratore_non_chi_subisce_la_causa():
    assert lato_della_parte("Ho ricevuto la lettera di licenziamento il 02/11/2026: sono stata licenziata.", "lavoro") == ATTIVO
    assert lato_della_parte("Un mio ex dipendente mi ha notificato il ricorso.", "lavoro") == PASSIVO


def test_datore_che_impugna_la_sentenza_resta_all_appello():
    r = _r("Sono il titolare di un bar: il giudice del lavoro ha accolto il ricorso del mio ex dipendente con sentenza "
           "notificata il 05/11/2026. Entro quando l'appello?")
    assert r.regola in {"appello_lavoro", "lav_appello"}, r.regola
