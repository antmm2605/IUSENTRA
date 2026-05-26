from __future__ import annotations

import pytest

from pct.uffici_competenti import GIUSTIZIA_MAP_VIEW_URL, _find_comune_option, ricerca_uffici_competenti


_SOURCE_I_GRAVE = "\u0117"

GIUSTIZIA_MAP_HTML = f"""
<html><body>
<span class="testo_xml" id="blocco_xml">
&lt;uffici&gt;
  &lt;ufficio nomeufficio="Tribunale di PALMI"&gt;
    &lt;indirizzo&gt;Via Roma&lt;/indirizzo&gt;
    &lt;comune&gt;PALMI&lt;/comune&gt;
    &lt;cap&gt;89015&lt;/cap&gt;
    &lt;telefono&gt;0966 - 4169&lt;/telefono&gt;
    &lt;email&gt;tribunale.palmi@giustizia.it&lt;/email&gt;
    &lt;pec&gt;tribunale.palmi@giustiziacert.it&lt;/pec&gt;
    &lt;assistenza_pct&gt;
      &lt;telefono&gt;0966/416238&lt;/telefono&gt;
      &lt;orari&gt;dal luned{_SOURCE_I_GRAVE} al venerd{_SOURCE_I_GRAVE} dalle 12.30 alle 14.00&lt;/orari&gt;
    &lt;/assistenza_pct&gt;
  &lt;/ufficio&gt;
  &lt;ufficio&gt;
    &lt;nome&gt;Giudice di Pace di PALMI&lt;/nome&gt;
    &lt;indirizzo&gt;Via Oberdan, 26&lt;/indirizzo&gt;
    &lt;comune&gt;PALMI&lt;/comune&gt;
    &lt;telefono&gt;0966 - 248557&lt;/telefono&gt;
    &lt;email&gt;gdp.palmi@giustizia.it&lt;/email&gt;
    &lt;pec&gt;gdp.palmi@giustiziacert.it&lt;/pec&gt;
  &lt;/ufficio&gt;
  &lt;ufficio&gt;
    &lt;nome&gt;Unep presso il Tribunale di PALMI&lt;/nome&gt;
    &lt;indirizzo&gt;Via Sauro, snc&lt;/indirizzo&gt;
    &lt;comune&gt;PALMI&lt;/comune&gt;
    &lt;pec&gt;unep.tribunale.palmi@giustiziacert.it&lt;/pec&gt;
  &lt;/ufficio&gt;
  &lt;ufficio&gt;
    &lt;nome&gt;Procura della Repubblica presso il Tribunale per i Minorenni di REGGIO CALABRIA&lt;/nome&gt;
    &lt;indirizzo&gt;Via minorenni&lt;/indirizzo&gt;
    &lt;comune&gt;REGGIO CALABRIA&lt;/comune&gt;
    &lt;pec&gt;procmin.reggiocalabria@giustiziacert.it&lt;/pec&gt;
  &lt;/ufficio&gt;
  &lt;ufficio&gt;
    &lt;nome&gt;Corte Suprema di Cassazione di ROMA&lt;/nome&gt;
    &lt;indirizzo&gt;Piazza Cavour&lt;/indirizzo&gt;
    &lt;comune&gt;ROMA&lt;/comune&gt;
  &lt;/ufficio&gt;
&lt;/uffici&gt;
</span>
</body></html>
"""


def test_ricerca_uffici_competenti_parse_ministero_senza_cache():
    payload = ricerca_uffici_competenti(
        "Taurianova",
        fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML,
    )

    assert payload["comune"] == "Taurianova"
    assert payload["source"]["url"] == GIUSTIZIA_MAP_VIEW_URL
    assert payload["totalOfficial"] == 5
    assert payload["totalVisible"] == 4
    assert [office["name"] for office in payload["offices"]] == [
        "Giudice di Pace di PALMI",
        "Tribunale di PALMI",
        "Unep presso il Tribunale di PALMI",
        "Procura della Repubblica presso il Tribunale per i Minorenni di REGGIO CALABRIA",
    ]
    tribunale = next(office for office in payload["offices"] if office["kind"] == "tribunale")
    assert tribunale["assistenzaPct"]["orari"] == "dal lunedì al venerdì dalle 12.30 alle 14.00"
    assert any(action["label"] == "Usa nel fascicolo" for action in tribunale["actions"])
    assert payload["warnings"]
    assert "fonte ministeriale" in payload["notes"][0]


def test_ricerca_uffici_competenti_visualizza_uffici_speciali_su_richiesta():
    payload = ricerca_uffici_competenti(
        "Taurianova",
        includi_speciali=True,
        fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML,
    )

    assert payload["totalVisible"] == 5
    assert payload["offices"][-1]["name"] == "Corte Suprema di Cassazione di ROMA"


def test_ricerca_uffici_competenti_filtra_tipologia_e_solo_pec():
    payload = ricerca_uffici_competenti(
        "Taurianova",
        includi_speciali=True,
        tipi_ufficio=["procura_minorenni"],
        solo_pec=True,
        fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML,
    )

    assert payload["totalVisible"] == 1
    assert payload["offices"][0]["kind"] == "procura_minorenni"
    assert payload["offices"][0]["pec"] == "procmin.reggiocalabria@giustiziacert.it"


def test_ricerca_uffici_competenti_arricchisce_pec_da_catalogo_ministeriale():
    html = """
    <root>
      <ufficio nomeufficio="Tribunale di PALMI">
        <indirizzo>Via Roma</indirizzo>
        <comune>PALMI</comune>
        <pec/>
      </ufficio>
      <ufficio>
        <nome>Giudice di Pace di PALMI</nome>
        <comune>PALMI</comune>
        <pec/>
      </ufficio>
    </root>
    """

    payload = ricerca_uffici_competenti(
        "Palmi",
        includi_speciali=True,
        tipi_ufficio=["tribunale", "giudice_pace"],
        solo_pec=True,
        fetcher=lambda _comune, _timeout: html,
    )

    assert [office["kind"] for office in payload["offices"]] == ["giudice_pace", "tribunale"]
    assert payload["offices"][0]["pec"] == "gdp.palmi@civile.ptel.giustiziacert.it"
    assert payload["offices"][1]["pec"] == "tribunale.palmi@civile.ptel.giustiziacert.it"


def test_ricerca_uffici_competenti_seleziona_comune_esatto_da_lista_ministeriale():
    html = """
    <select name="comune" class="cerca_for" id="comune">
      <option value="">Scegli...</option>
      <option value="18080057#Palmi">Palmi (RC)</option>
      <option value="11044056#Palmiano">Palmiano (AP)</option>
    </select>
    """

    assert _find_comune_option(html, "Palmi") == "18080057#Palmi"


@pytest.mark.parametrize("comune", ["", "A", "\x01Palmi"])
def test_ricerca_uffici_competenti_valida_comune(comune: str):
    with pytest.raises(ValueError):
        ricerca_uffici_competenti(comune, fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML)
