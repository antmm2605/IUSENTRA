"""Un fascicolo con la sola area deve poter arrivare a un profilo.

Il catalogo ministeriale non sostituisce quello che l'avvocato ha scritto —
e' giusto cosi'. Ma "compilato" deve voler dire completo. Finche' bastava un
campo su tre per fermare l'arricchimento, un fascicolo con la sola area
restava senza profilo: e' la forma normale, perche' `area_pratica` sta sul
fascicolo mentre branca e sottofamiglia stanno solo nel profilo di deposito,
che quasi nessun fascicolo ha.

La conseguenza si vedeva a valle: la catalogazione girava, leggeva e
riconosceva ogni documento, e poi li lasciava tutti e sessantadue "da
verificare" con lo stesso motivo — «mancano area, branca e sottofamiglia» —
mentre il fascicolo portava il codice oggetto ministeriale 222050 che lo
identificava.
"""

from __future__ import annotations

import pytest

from pct.document_intelligence.catalog_context import enrich_official_context
from pct.document_intelligence.catalog_resolver import resolve_profile

#: Il fascicolo reale da cui e' partita la segnalazione: lavoro, retribuzione.
OGGETTO_MINISTERIALE = {
    "codice_oggetto_pst": "222050",
    "oggetto": "retribuzione",
    "canale": "",
    "tipo_fascicolo": "",
}


def _contesto(**campi):
    return enrich_official_context({**OGGETTO_MINISTERIALE, "area": "", "branca": "", "sottobranca": "", **campi})


def test_con_la_sola_area_il_profilo_si_risolve():
    contesto = _contesto(area="Lavoro e previdenza")

    profilo, motivo = resolve_profile(contesto)

    assert profilo == "LAV"
    assert "222050" in motivo


def test_con_la_sola_area_le_caselle_vuote_si_completano():
    contesto = _contesto(area="Lavoro e previdenza")

    assert contesto["area"] == "Lavoro e previdenza"
    assert contesto["branca"] == "Pubblico impiego"
    assert contesto["sottobranca"] == "retribuzione"


def test_un_profilo_completo_dell_avvocato_non_viene_toccato():
    """Quello che ha scritto l'avvocato resta, e non si dichiara un profilo ufficiale."""

    contesto = _contesto(area="Mia area", branca="Mia branca", sottobranca="Mia sottofamiglia")

    assert (contesto["area"], contesto["branca"], contesto["sottobranca"]) == (
        "Mia area",
        "Mia branca",
        "Mia sottofamiglia",
    )
    assert contesto.get("_official_profile_id") is None


@pytest.mark.parametrize(
    "scritto",
    [
        {"area": "Area scritta a mano"},
        {"branca": "Branca scritta a mano"},
        {"sottobranca": "Sottofamiglia scritta a mano"},
    ],
)
def test_il_valore_scritto_a_mano_non_viene_mai_sovrascritto(scritto):
    contesto = _contesto(**scritto)

    campo, valore = next(iter(scritto.items()))
    assert contesto[campo] == valore


def test_senza_voce_ministeriale_non_si_inventa_un_profilo():
    contesto = enrich_official_context(
        {
            "codice_oggetto_pst": "",
            "oggetto": "una materia che non sta a catalogo",
            "area": "Lavoro e previdenza",
            "branca": "",
            "sottobranca": "",
            "canale": "",
            "tipo_fascicolo": "",
        }
    )

    assert contesto["branca"] == ""
    assert contesto.get("_official_profile_id") is None
    assert resolve_profile(contesto)[0] is None


def test_i_canali_non_civili_restano_fuori_dal_catalogo():
    """Il catalogo usato qui e' quello civile: penale e amministrativo no."""

    for canale in ("pat", "siga", "ptt", "sigit", "pdp", "penale"):
        contesto = _contesto(canale=canale)

        assert contesto.get("_official_profile_id") is None, canale
