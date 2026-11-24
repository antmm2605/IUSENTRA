"""Preamboli estranei: le parole di contesto («lavoro», «condominio», «Tribunale di…») non decidono lo strumento quando la
frase della richiesta contiene il fatto che lo indica (lex/harness/richiesta.py).

Frasi nuove, scritte per questo controllo (24/11/2026): non vengono dalla batteria, dai casi dell'avvocato né da banchi
di misura.
"""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.fattispecie.schede import senza_importi
from lex.harness.norme import ISTANTANEA
from lex.harness.richiesta import separa

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

OGGI = "\n\nOggi è il 24/11/2026."

CASI = [
    ("termine_querela",
     "Lavoro da vent'anni come avvocato a Bergamo e seguo soprattutto pratiche di lavoro e di condominio per piccole "
     "imprese. Ieri un'amica mi ha raccontato che un ex collega ha scritto su Instagram che lei è una truffatrice; l'ha "
     "scoperto il 01/11/2026. Che termine ha per la querela?"),
    ("fam_mantenimento",
     "Davanti al Tribunale di Milano, sezione lavoro, ho una causa pendente per differenze retributive che va avanti da due "
     "anni. Oggi però devo capire un'altra cosa: il mio ex marito non versa l'assegno per i figli da sei mesi. Cosa posso "
     "fare per ottenere i soldi?"),
    ("sinistro_stradale",
     "Il Tribunale di Napoli è oberato di cause di lavoro e le udienze slittano di mesi, lo sanno tutti in studio. Detto "
     "questo: la mia cliente è stata tamponata il 05/11/2026 da un furgone assicurato con Beta Assicurazioni e ha danni per "
     "3.000 euro. Voglio chiedere il risarcimento all'assicurazione: come procedo?"),
    ("ricorso_tar",
     "Nel mio studio ci occupiamo di diritto del lavoro e di contratti collettivi da anni, con molti fascicoli aperti al "
     "Tribunale di Torino. Una cliente mi chiede aiuto per una questione diversa: il Comune di Torino le ha notificato il "
     "30/10/2026 il diniego del permesso di costruire. Posso fare ricorso al TAR ed entro quando?"),
    ("opposizione_verbale_cds",
     "In condominio abbiamo spesso liti per i rumori e per le infiltrazioni, e l'assemblea si riunisce ogni mese. A parte "
     "questo, al mio cliente è stato notificato il 03/11/2026 un verbale per divieto di sosta accertato il 20/10/2026 nel "
     "comune di Lodi, sanzione di 42 euro. Voglio fare opposizione al giudice di pace."),
    ("garanzia_conformita",
     "Il mio cliente lavora come operaio in una fabbrica di Brescia e ha un contratto a tempo indeterminato. Ha comprato una "
     "lavatrice da 600 euro in un negozio, consegnata il 10/06/2026, che dal 01/11/2026 non funziona più e il venditore non "
     "la ripara. Cosa può chiedere al venditore?"),
    ("opposizione_precetto",
     "Faccio l'amministratore di condominio da dieci anni a Como, gestisco quindici stabili e conosco bene le assemblee. Il "
     "mio problema però è personale: il 02/11/2026 mi hanno notificato un precetto per 7.000 euro già pagati. Voglio "
     "oppormi al precetto."),
    ("ricorso_tributario",
     "Sono socio di una cooperativa di lavoro e seguo anche la parte amministrativa del condominio dove vivo. Il 10/11/2026 "
     "ho ricevuto un avviso di accertamento IMU del 2019 che non ho mai visto prima. Posso impugnarlo ed entro quando?"),
    ("negoziazione_locazione_inadatta",
     "Il mio cliente affitta un appartamento a Padova; l'inquilino non paga da quattro mesi, 650 euro al mese. Voglio "
     "mandare l'invito alla negoziazione assistita prima dello sfratto: preparalo."),
    ("impugnazione_delibera",
     "Il mio cliente è condomino di un palazzo a Monza; l'assemblea del 05/11/2026, alla quale ha votato contro, ha "
     "approvato una spesa contraria al regolamento. Entro quando la impugna?"),
]


@pytest.mark.parametrize("regola,domanda", CASI, ids=[r for r, _ in CASI])
def test_preambolo_estraneo_non_decide_lo_strumento(regola, domanda):
    r = rispondi(domanda + OGGI, oggi=date(2026, 11, 24))
    assert r is not None and r.regola == regola, (r.regola if r else None)
    assert not r.affermazioni_tolte and not r.citazioni_non_verificate


def test_separa_richiesta_e_zona():
    richiesta, zona = separa("Lavoro da anni in un'azienda di Parma. Il problema però è un altro: mio padre è morto e ha "
                             "lasciato debiti. Posso rinunciare all'eredità?")
    assert richiesta == "Posso rinunciare all'eredità?"
    assert zona.startswith("Il problema però") and "Lavoro" not in zona


def test_senza_preambolo_non_si_separa_nulla():
    assert separa("L'inquilino non paga da tre mesi. Posso intimare lo sfratto?") == ("", "")
    assert separa("Posso fare opposizione al decreto ingiuntivo?") == ("", "")


def test_un_importo_non_e_un_articolo_nei_segnali():
    assert "650" not in senza_importi("canone di 650 euro al mese")
    assert "art. 650" in senza_importi("opposizione tardiva ex art. 650 c.p.c.")


def test_inizio_con_importi_e_racconto_non_preambolo():
    assert separa("Assisto Lia Corsi, creditrice di 12.000 euro verso Ugo Pace. Pace sta svuotando i conti. Possiamo "
                  "chiedere il sequestro prima della causa?") == ("", "")
