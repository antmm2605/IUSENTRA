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
