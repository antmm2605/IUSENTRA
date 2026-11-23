"""Instradamento del testo libero: formulazioni dell'avvocato che prima cadevano fuori dalle regole (23/11/2026).

Frasi diverse da quelle dei banchi di misura e da quelle del dataset sintetico."""
from __future__ import annotations

import pytest

from lex.harness import rispondi

CASI = [
    ("Rappresento Gino Vela, inquilino di un bilocale a Pisa (canone 620 euro). Il proprietario gli ha intimato lo sfratto per "
     "morosità con atto notificato il 03/11/2026 e udienza il 01/12/2026. Che fare?\n\nOggi è il 18/11/2026.", "sanatoria_morosita"),
    ("La mia cliente Irene Sola ha commissionato alla ditta Fratelli Neri s.n.c. il rifacimento del tetto della sua casa a Cuneo, "
     "corrispettivo 14.000 euro, lavori consegnati il 02/02/2026; il 10/03/2026 compaiono infiltrazioni, contestate con PEC del "
     "20/03/2026. Come ci muoviamo?\n\nOggi è il 18/11/2026.", "vizi_appalto"),
    ("Assisto Pietro Lanza: gli è arrivato un verbale per semaforo rosso, accertamento del 15/07/2026 a Modena, notificato a "
     "Pietro Lanza il 30/10/2026. Scrivi il ricorso al giudice di pace.\n\nOggi è il 18/11/2026.", "opposizione_verbale_cds"),
    ("Il mio cliente Aldo Rizzi ha ricevuto il 25/10/2026 dalla Regione Umbria un provvedimento di revoca dell'autorizzazione "
     "all'esercizio. Entro quando possiamo fare ricorso?\n\nOggi è il 18/11/2026.", "ricorso_tar"),
    ("Assisto Sara Pinto, condomina dissenziente: l'assemblea del 28/10/2026 ha approvato una delibera sulla ripartizione delle "
     "spese di facciata. Come contestarla?\n\nOggi è il 18/11/2026.", "impugnazione_delibera"),
    ("Il mio cliente Luca Toni il 02/10/2026 ha avuto un incidente a Siena: è stato tamponato da un furgone assicurato; danni "
     "all'auto per 2.400 euro. Cosa possiamo fare con l'assicurazione?\n\nOggi è il 18/11/2026.", "sinistro_stradale"),
    ("Per conto di Beta Ricambi s.r.l., con sede a Brescia: la cliente Gamma Motori s.r.l. non ha pagato le fatture n. 7 del "
     "05/02/2026 di euro 2.900 e n. 15 del 06/03/2026 di euro 3.100, nonostante la diffida del 10/05/2026. Come ci muoviamo?"
     "\n\nOggi è il 18/11/2026.", "decreto_ingiuntivo"),
    ("Difendo Caffè Duomo s.r.l., conduttore di un locale ad uso commerciale a Trento, canone 1.800 euro: la locatrice ha "
     "intimato lo sfratto per morosità, udienza il 10/12/2026; nel locale ci sono infiltrazioni mai riparate. Come ci opponiamo?"
     "\n\nOggi è il 18/11/2026.", "opposizione_sfratto_commerciale"),
    ("La mia cliente Anna Ferri pagava per la casa a Rimini 450 euro di affitto registrato e altri 120 euro in nero, oltre al "
     "canone, dal 01/01/2025 al 30/09/2026. Può riavere le somme in nero?\n\nOggi è il 18/11/2026.",
     "restituzione_canone_non_registrato"),
    ("Assisto Marco Leone: il Ministero gli ha notificato il 10/10/2026 un decreto definitivo di esclusione da una graduatoria. "
     "Possiamo proporre ricorso straordinario al Presidente della Repubblica?\n\nOggi è il 18/11/2026.", "ricorso_straordinario"),
    ("Assisto Elena Riva, condomina a Udine: il vicino ha chiuso una parte del cortile comune con una recinzione abusiva. "
     "Come possiamo agire?\n\nOggi è il 18/11/2026.", "lite_condominio"),
]


@pytest.mark.parametrize("domanda,regola", CASI)
def test_formulazioni_libere_trovano_la_regola(domanda, regola):
    r = rispondi(domanda)
    assert r is not None and r.regola == regola


@pytest.mark.parametrize("domanda", ["cosa devo fare oggi?", "che udienze ho domani?", "mostrami le scadenze della settimana"])
def test_le_domande_operative_restano_operative(domanda):
    from lex.harness.comprensione import comprendi

    assert not comprendi(domanda).per_harness
