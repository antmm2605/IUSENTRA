"""Contributo unificato nei preventivi calcolato con l'art. 13 D.P.R. 115/2002, non a importi fissi."""

from __future__ import annotations

import pytest

from pct.contributo_preventivo import contributo_per_preventivo, grado_dal_testo, parametri_contributo
from pct.strumenti_legali import GestioneStrumentiLegali


@pytest.fixture(scope="module")
def calcolatore():
    return GestioneStrumentiLegali()


@pytest.mark.parametrize("tipologia, valore, grado, atteso", [
    ("atto_citazione", 30000, "Tribunale", 518.0),           # scaglione 26.000-52.000
    ("atto_citazione", 30000, "Corte d'Appello", 777.0),     # +50% impugnazione
    ("decreto_ingiuntivo", 30000, "", 259.0),                # metà (comma 3)
    ("appello_civile", 1000, "", 64.5),                      # 43 × 1,5
    ("cassazione_civile", 30000, "", 1036.0),                # doppio
    ("responsabilita_organi_sociali", 30000, "", 1036.0),    # sezione impresa: doppio
    ("controversia_lavoro", 30000, "", 259.0),
    ("appello_lavoro", 30000, "", 388.5),
    ("opposizione_atti_esecutivi", 0, "", 168.0),
    ("ricorso_tributario", 30000, "", 250.0),
    ("appello_cds", 0, "", 975.0),                           # 650 × 1,5, non 1.300
    ("silenzio_inadempimento", 0, "", 300.0),                # comma 6-bis lett. a, non 325
    ("appalti_contratti_pubblici", 30000, "", 2000.0),
])
def test_contributo_dal_calcolatore(calcolatore, tipologia, valore, grado, atteso):
    assert contributo_per_preventivo(calcolatore, tipologia, valore=valore, grado_scelto=grado) == atteso


def test_tipologie_non_mappate_e_grado():
    assert parametri_contributo("procedimenti_famiglia", valore=1000) is None
    assert contributo_per_preventivo(object(), "procedimenti_famiglia", valore=1000) is None
    assert parametri_contributo("atto_citazione", valore=0)["cu_valore_tipo"] == "indeterminabile"
    assert grado_dal_testo("Corte di Cassazione") == "cassazione"
    assert grado_dal_testo("Consiglio di Stato") == "appello"
    assert grado_dal_testo("") == "primo_grado"


def test_opposizione_decreto_ingiuntivo_dimezzata(calcolatore):
    """Art. 13, comma 3, D.P.R. 115/2002: metà «compreso il giudizio di opposizione a decreto ingiuntivo»."""
    assert contributo_per_preventivo(calcolatore, "opposizione_di", valore=10000) == 118.5
    assert contributo_per_preventivo(calcolatore, "opposizione_di", valore=10000, grado_scelto="Corte d'Appello") == 177.75


def test_indeterminabile_giudice_di_pace_e_473bis47(calcolatore):
    """Art. 13, comma 1, lett. b-d, D.P.R. 115/2002."""
    base = {"cu_categoria": "civile_ordinario", "cu_valore_tipo": "indeterminabile"}
    assert calcolatore.calcola_contributo_unificato(base)["base"] == 518.0
    assert calcolatore.calcola_contributo_unificato({**base, "cu_giudice_pace": True})["base"] == 237.0
    famiglia = {"cu_categoria": "famiglia_473bis47"}
    assert calcolatore.calcola_contributo_unificato(famiglia)["base"] == 98.0
    assert calcolatore.calcola_contributo_unificato({**famiglia, "cu_grado": "appello"})["base"] == 147.0


def test_redazione_legge_grado_e_ufficio_dal_fascicolo(calcolatore):
    from types import SimpleNamespace
    from pct.redazione_contesto import contributo_unificato_da_fascicolo

    def fascicolo(**campi):
        dati = {"tipo": "CIVILE", "titolo": "Causa", "oggetto": "", "note": "", "valore_causa": 30000,
                "tribunale": "Tribunale di Roma", "tipo_procedimento": "", "documenti": []}
        dati.update(campi)
        return SimpleNamespace(**dati)

    def atteso(**parametri):
        return calcolatore.calcola_contributo_unificato({"cu_valore": 30000, "cu_valore_tipo": "determinato", **parametri})["totale"]

    assert contributo_unificato_da_fascicolo(fascicolo())["totale"] == atteso(cu_categoria="civile_ordinario")
    appello = contributo_unificato_da_fascicolo(fascicolo(tribunale="Corte d'Appello di Roma"))
    assert appello["totale"] == atteso(cu_categoria="civile_ordinario", cu_grado="appello")
    assert "Appello" in appello["descrizione"]
    famiglia = contributo_unificato_da_fascicolo(fascicolo(valore_causa=0, titolo="Separazione giudiziale"))
    assert famiglia["categoria"] == "famiglia_473bis47"
    assert famiglia["totale"] == calcolatore.calcola_contributo_unificato({"cu_categoria": "famiglia_473bis47"})["totale"]
