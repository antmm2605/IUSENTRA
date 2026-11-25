"""Schemi di errore della rimisura indipendente (24/11/2026): negazioni, parole in più materie, strumento chiesto contro
materia nominata, generale contro speciale, racconti senza il nome dell'istituto. Frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness import rispondi
from lex.harness.normalizzazione import togli_negati

CASI = [
    # negazioni ed eccezioni
    ("Una collega ha scritto su un gruppo whatsapp che la mia cliente ruba in ufficio: vogliamo i danni senza querela",
     {"rc_diffamazione"}),
    # parole presenti in più materie
    ("Lavoro in banca, mia madre è morta e voglio rinunciare all'eredità", {"suc_rinuncia_eredita"}),
    ("Sul lavoro mi hanno tolto le mansioni e mi isolano dai colleghi da mesi", {"lav_mobbing_demansionamento"}),
    # lo strumento chiesto vince sulla materia nominata
    ("Per 12.000 euro di un prestito non restituito serve la negoziazione assistita prima della causa?",
     {"negoziazione_obbligatoria"}),
    # generale contro speciale
    ("Abbiamo firmato una transazione con il fornitore ma eravamo stati ingannati: si può annullare?", {"str_transazione"}),
    ("Il giudice del lavoro ha respinto il ricorso del dipendente: entro quando l'appello?", {"appello_lavoro", "lav_appello"}),
    # racconti senza il nome dell'istituto
    ("Hanno pubblicato su facebook che il mio cliente è un truffatore", {"rc_diffamazione"}),
    ("Mia nonna ha lasciato tutto alla badante con il testamento e a noi nipoti niente", {"suc_riduzione"}),
    ("Sono caduta per una buca sul marciapiede del comune e mi sono rotta il polso", {"rc_cose_in_custodia"}),
    ("L'ospedale ha sbagliato l'intervento e mio padre è peggiorato", {"rc_responsabilita_sanitaria"}),
]


@pytest.mark.parametrize("domanda,regole", CASI)
def test_schemi_di_errore(domanda, regole):
    r = rispondi(domanda)
    assert r is not None and r.regola in regole, r.regola if r else None


def test_la_parola_negata_non_resta():
    assert "querel" not in togli_negati("vogliamo i danni senza querela").replace("[istituto escluso]", "")
    assert "causa" not in togli_negati("non vogliamo fare causa").replace("[istituto escluso]", "")
