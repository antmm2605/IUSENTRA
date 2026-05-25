from __future__ import annotations

import pytest

from pct.uffici_competenti import GIUSTIZIA_MAP_VIEW_URL, ricerca_uffici_competenti


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
  &lt;/ufficio&gt;
  &lt;ufficio&gt;
    &lt;nome&gt;Unep presso il Tribunale di PALMI&lt;/nome&gt;
    &lt;indirizzo&gt;Via Sauro, snc&lt;/indirizzo&gt;
    &lt;comune&gt;PALMI&lt;/comune&gt;
    &lt;pec&gt;unep.tribunale.palmi@giustiziacert.it&lt;/pec&gt;
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
    assert payload["totalOfficial"] == 4
    assert payload["totalVisible"] == 3
    assert [office["name"] for office in payload["offices"]] == [
        "Giudice di Pace di PALMI",
        "Tribunale di PALMI",
        "Unep presso il Tribunale di PALMI",
    ]
    tribunale = next(office for office in payload["offices"] if office["kind"] == "tribunale")
    assert tribunale["assistenzaPct"]["orari"] == "dal lunedì al venerdì dalle 12.30 alle 14.00"
    assert any(action["label"] == "Usa nel fascicolo" for action in tribunale["actions"])
    assert payload["warnings"]
    assert "senza salvare copie locali" in payload["notes"][0]


def test_ricerca_uffici_competenti_visualizza_uffici_speciali_su_richiesta():
    payload = ricerca_uffici_competenti(
        "Taurianova",
        includi_speciali=True,
        fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML,
    )

    assert payload["totalVisible"] == 4
    assert payload["offices"][-1]["name"] == "Corte Suprema di Cassazione di ROMA"


@pytest.mark.parametrize("comune", ["", "A", "\x01Palmi"])
def test_ricerca_uffici_competenti_valida_comune(comune: str):
    with pytest.raises(ValueError):
        ricerca_uffici_competenti(comune, fetcher=lambda _comune, _timeout: GIUSTIZIA_MAP_HTML)
