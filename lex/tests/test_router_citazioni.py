"""Il router riconosce le pronunce citate con le abbreviazioni forensi (punti compresi), non i numeri di ruolo."""
import pytest

from lex.contracts import LexRequest
from lex.router import LexRouter


def _workflow(domanda: str) -> str:
    return LexRouter().resolve_workflow(LexRequest(tenant_id="t", user_id="u", session_id="s", query=domanda))


@pytest.mark.parametrize("domanda", [
    "Cass. civ. sez. III n. 9449/2016",
    "Cass. S.U. n. 5425/2021",
    "Corte cost. n. 75/2019",
    "C. cost. 75/2019",
    "Cons. St. sez. IV n. 1234/2021",
    "Consiglio di Stato n. 1234 del 2021",
    "C.d.S. n. 5678 del 2020",
    "TAR Lazio n. 3456/2019",
    "T.A.R. Lombardia, sez. II, n. 210 del 12/03/2022",
    "C.G.A.R.S. n. 88/2023",
])
def test_citazioni_con_punti(domanda):
    assert _workflow(domanda) == "giurisprudenza_specifica"


@pytest.mark.parametrize("domanda", [
    "ricorso al TAR Lazio nel fascicolo R.G. n. 1234/2025",
    "cosa dice la Cassazione sulla caparra confirmatoria",
    "termine per il ricorso al TAR",
])
def test_non_sono_citazioni(domanda):
    assert _workflow(domanda) != "giurisprudenza_specifica"
