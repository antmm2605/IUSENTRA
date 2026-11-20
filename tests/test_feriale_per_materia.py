"""Sospensione feriale per materia: art. 3 L. 742/1969 e art. 92 R.D. 12/1941 (testo vigente, Normattiva, 19/11/2026).

Per ogni materia esclusa un termine di 30 giorni a cavallo di agosto: dal 20/07/2026 scade il 19/08/2026 senza
sospensione; con la sospensione (art. 1 L. 742/1969) i giorni di agosto non si contano e la scadenza va al 19/09/2026,
sabato, prorogata a lunedì 21/09/2026 (art. 155 c.p.c.). Le materie non escluse (opposizione agli atti esecutivi,
revocatoria fallimentare, contratti) restano sospese.
"""

from __future__ import annotations

from datetime import date

import pytest

from pct.ragionamento.regole.calcolo import in_avanti
from pct.ragionamento.rito import determina_rito

BASE, OGGI = date(2026, 7, 20), date(2026, 7, 21)
SENZA, CON = "2026-08-19", "2026-09-21"


def _termine(codice: str, etichette=()):
    rito = determina_rito({"codice_oggetto_pst": codice}, list(etichette))
    termine = in_avanti(BASE, 30, rito=rito, oggi=OGGI, perentorio=True, evento="comunicazione", norma="art. 155 c.p.c.")
    return rito, termine


@pytest.mark.parametrize("codice, materia", [
    ("222099", "lavoro"),                                   # pubblico impiego (art. 409 c.p.c.)
    ("230001", "previdenza"),                               # previdenza obbligatoria (art. 442 c.p.c.)
    ("011001", "procedimento cautelare"),                   # sequestro conservativo (art. 671 c.p.c.)
    ("019999", "procedimento cautelare"),                   # altri cautelari (art. 700 c.p.c.)
    ("016011", "alimenti"),                                 # assegno provvisorio per alimenti (art. 446 c.c.)
    ("030001", "sfratto"),                                  # intimazione di sfratto (art. 657 c.p.c.)
    ("100012", "opposizione all'esecuzione"),               # art. 615, secondo comma, c.p.c.
    ("413061", "amministrazione di sostegno"),              # artt. 404 ss. c.c.
    ("110001", "interdizione"),
    ("111601", "abusi familiari"),                          # art. 473-bis.71 c.p.c.
    ("171401", "fallimento"),                               # dichiarazione di fallimento
])
def test_materie_escluse_senza_sospensione_di_agosto(codice, materia):
    rito, termine = _termine(codice)
    assert not rito.sospensione_feriale and materia in rito.motivo_feriale
    assert "art. 3 L. 742/1969" in rito.motivo_feriale
    assert termine.scadenza == SENZA and termine.sospensione_feriale.startswith("non si applica")


@pytest.mark.parametrize("codice", ["100021", "530021", "171105", "140999"])
def test_materie_non_escluse_restano_sospese(codice):
    rito, termine = _termine(codice)
    assert rito.sospensione_feriale and not rito.motivo_feriale
    assert termine.scadenza == CON and termine.sospensione_feriale.startswith("si applica")


def test_senza_codice_oggetto_decide_l_atto_introduttivo_non_un_documento_di_prova():
    rito, termine = _termine("", ["Ricorso ex art. 700 c.p.c.", "Procura alle liti"])
    assert not rito.sospensione_feriale and termine.scadenza == SENZA
    rito, termine = _termine("", ["Atto di citazione", "Contratto di lavoro", "Verbale di sequestro"])
    assert rito.sospensione_feriale and termine.scadenza == CON
    rito, _ = _termine("", ["Ricorso in opposizione agli atti esecutivi (art. 617 c.p.c.)"])
    assert rito.sospensione_feriale


def test_termine_breve_dalla_notifica_della_sentenza_segue_la_materia():
    from pct.sentenza_notificata import termini_dalla_notifica

    breve = lambda **k: next(c for c in termini_dalla_notifica("2026-07-20", contro_pa=False, condanna=False, **k)
                             if c["codice"] == "termine_breve_impugnazione")
    assert breve(lavoro=False)["deadline"] == CON
    escluso = breve(lavoro=False, esclusione_feriale="opposizione all'esecuzione (art. 3 L. 742/1969 e art. 92 R.D. 12/1941)")
    assert escluso["deadline"] == SENZA and "senza sospensione feriale (opposizione all'esecuzione" in escluso["formula"]


def test_preset_di_nuova_scadenza_usano_la_stessa_esclusione_per_materia():
    from types import SimpleNamespace

    from pct.termini_materia import NOTA_LAVORO, esclusione_feriale_fascicolo, nota_esclusione, profilo_della_richiesta

    sfratto = SimpleNamespace(tipo="CIVILE", sezione="", codice_oggetto_pst="030001")
    lavoro = SimpleNamespace(tipo="LAVORO", sezione="", codice_oggetto_pst="")
    contratti = SimpleNamespace(tipo="CIVILE", sezione="", codice_oggetto_pst="140999")
    fascicoli = {"S": sfratto, "L": lavoro, "C": contratti}
    assert "procedimento di sfratto" in esclusione_feriale_fascicolo(sfratto)
    assert esclusione_feriale_fascicolo(contratti) == "" and esclusione_feriale_fascicolo(None) == ""
    profilo, materia_lavoro, motivo = profilo_della_richiesta("appello_breve", "", {"id_fascicolo": "S"}, fascicoli.get)
    assert not profilo.apply_ferial_suspension and not materia_lavoro and "art. 92 R.D. 12/1941" in motivo
    assert nota_esclusione(motivo).startswith("Sospensione feriale non applicata: procedimento di sfratto")
    profilo, materia_lavoro, motivo = profilo_della_richiesta("appello_breve", "", {"id_fascicolo": "L"}, fascicoli.get)
    assert not profilo.apply_ferial_suspension and materia_lavoro and nota_esclusione(motivo) == NOTA_LAVORO
    profilo, _, motivo = profilo_della_richiesta("appello_breve", "", {"id_fascicolo": "C"}, fascicoli.get)
    assert profilo.apply_ferial_suspension and motivo == ""
    # «materia_lavoro» esplicito e falso: non è lavoro, ma lo sfratto resta escluso
    _, _, motivo = profilo_della_richiesta("appello_breve", "", {"id_fascicolo": "S", "materia_lavoro": "0"}, fascicoli.get)
    assert "sfratto" in motivo
