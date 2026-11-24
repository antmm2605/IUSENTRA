"""Avvertenze delle regole dell'harness: ogni affermazione giuridica porta la sua norma, controllata sul testo vigente;
un consiglio pratico è dichiarato «Consiglio operativo».

Le frasi sono nuove, scritte per questo controllo (24/11/2026): non vengono dalla batteria, dai casi dell'avvocato né da
banchi di misura.
"""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.controllo import verifica_analisi
from lex.harness.modello import Analisi, Punto, Rif
from lex.harness.norme import ISTANTANEA

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

OGGI = "\n\nOggi è il 24/11/2026."

CASI = [
    ("caparra_confirmatoria",
     "Assisto Franco Bassi, promissario acquirente di una villetta a Lucca per 260.000 euro con preliminare del 03/02/2026 "
     "e caparra confirmatoria di 25.000 euro versata a Maria Conti, residente a Pisa. La venditrice non si è presentata dal "
     "notaio il 30/09/2026 e ha rimesso in vendita la casa. Prepara l'atto di citazione per il doppio della caparra."),
    ("diffida_commerciale",
     "La Fonderia Alpi s.r.l., mia cliente, ha emesso alla Meccanica Sud s.r.l. le fatture n. 14 del 10/05/2026 di euro "
     "8.400 e n. 19 del 12/06/2026 di euro 5.200, scadute e non pagate. Prepara una diffida con gli interessi moratori."),
    ("impugnazione_delibera",
     "Il mio cliente, condomino a Monza, ha votato contro la delibera assembleare del 05/11/2026 che approva una spesa "
     "contraria al regolamento: entro quando possiamo impugnare la delibera?"),
    ("negoziazione_locazione_inadatta",
     "Il mio cliente affitta un appartamento a Padova; l'inquilino è moroso da quattro mesi. Prepara l'invito alla "
     "negoziazione assistita per i canoni."),
    ("opposizione_sfratto_commerciale",
     "Assisto la conduttrice di un bar a Rimini: la locatrice le ha intimato sfratto per morosità, udienza di convalida "
     "fissata al 15/12/2026, canoni non pagati euro 6.000; il locale ha infiltrazioni segnalate con PEC. Lei vuole chiedere "
     "il termine di grazia di novanta giorni."),
    ("opposizione_verbale_cds",
     "Mi è stato notificato il 10/11/2026 a mezzo posta un verbale per eccesso di velocità accertato il 01/07/2026 nel "
     "territorio del comune di Arezzo, sanzione di euro 173. Voglio fare ricorso."),
    ("permesso_soggiorno",
     "Al mio cliente, cittadino albanese, la questura ha negato il permesso di soggiorno per motivi familiari per "
     "ricongiungimento con la moglie: vorrebbe fare ricorso al TAR."),
    ("procedibilita_locazione",
     "Il proprietario di un negozio a Cagliari mi chiede se, con il conduttore moroso da tre mesi, deve prima fare la "
     "mediazione o altro passaggio obbligatorio prima dello sfratto."),
    ("ricorso_tar",
     "Il Comune di Viterbo ha notificato il 20/10/2026 al mio cliente il diniego dell'autorizzazione per un dehors. Entro "
     "quando il ricorso al TAR?"),
    ("ricorso_tributario",
     "All'Agenzia delle entrate che ha notificato il 15/10/2026 un avviso di accertamento al mio cliente: entro quando il "
     "ricorso tributario?"),
    ("sinistro_stradale",
     "La mia cliente è stata tamponata a Lecco il 02/11/2026 da un'auto assicurata con Alfa Assicurazioni; ha danni all'auto "
     "per 2.300 euro e un colpo di frusta. Come chiediamo il risarcimento all'assicurazione?"),
    ("termine_querela",
     "Un ex collega ha diffamato la mia cliente con un post su Facebook; lei lo ha saputo il 10/11/2026. Entro quando "
     "presentare querela? Lei pensava di avere sei mesi."),
]


@pytest.mark.parametrize("regola,domanda", CASI, ids=[r for r, _ in CASI])
def test_ogni_avvertenza_ha_la_norma_o_e_un_consiglio_operativo(regola, domanda):
    r = rispondi(domanda + OGGI, oggi=date(2026, 11, 24))
    assert r is not None and r.regola == regola
    assert not r.affermazioni_tolte, r.affermazioni_tolte
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate
    avvertenze = r.registro["12_tranelli_e_avvertenze"]
    assert avvertenze, "la regola deve dare almeno un'avvertenza"
    for x in avvertenze:
        if isinstance(x, str):
            assert x.startswith("Consiglio operativo:"), x
        else:
            assert x["fonti"] and all(f["ancora"] for f in x["fonti"]), x
    assert "**Avvertenze**" in r.testo


def test_querela_non_attribuisce_al_cliente_parole_che_non_ha_detto():
    r = rispondi("Il mio vicino ha scritto su Instagram che la mia cliente è una truffatrice; lei lo ha scoperto il "
                 "01/11/2026. La querela entro quando va presentata?" + OGGI, oggi=date(2026, 11, 24))
    assert r.regola == "termine_querela"
    assert "sei mesi" not in r.testo and "febbraio" not in r.testo and "cancellare il post" not in r.testo
    assert "rinuncia tacita" in r.testo


def test_negoziazione_per_locale_commerciale_non_promette_il_termine_di_grazia():
    r = rispondi("Il mio cliente ha affittato un negozio a Verona; il conduttore è moroso da cinque mesi. Prepara l'invito "
                 "alla negoziazione assistita per i canoni." + OGGI, oggi=date(2026, 11, 24))
    assert r.regola == "negoziazione_locazione_inadatta"
    avv = r.testo.split("**Avvertenze**")[1].split("**")[0]
    assert "novanta giorni" not in avv and "art. 55" in avv


def test_avvertenza_con_ancora_assente_dal_testo_vigente_passa_ai_dubbi():
    a = Analisi("prova", "civile")
    a.avvertenze = [Punto("Affermazione inventata.", [Rif("cp:124", "parole che la norma non contiene affatto")]),
                    "Consiglio operativo: resta."]
    esito = verifica_analisi(a)
    assert a.avvertenze == ["Consiglio operativo: resta."]
    assert esito.affermazioni_tolte and any("Affermazione inventata" in d for d in a.dubbi)
