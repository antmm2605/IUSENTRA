"""Riquadro «Contributo unificato» del modulo PAT di deposito ricorso (art. 13 D.P.R. 115/2002).

«Non esente» contiene la parola «esente»: il modulo compilato deve comunque selezionare la voce giusta,
una sola, sia dal campo guidato sia dal valore XFA indicato per percorso.
"""

from __future__ import annotations

import pytest

from pct.pat_pdf_templates import build_pat_official_pdf, read_compiled_template
from pct.pat_xfa_dati import valore

BASE = {
    "sede": "Tribunale Amministrativo regionale del Veneto - Venezia",
    "ricorrente": "Rossi Mario",
    "resistente": "Comune di Venezia",
    "oggetto": "Annullamento del diniego di permesso di costruire",
    "tipo_ricorso": "ORDINARIO",
}
PERCORSO = "template/ricorso/subform/subFormContributo/rbContributo"


def _scelte(campi: dict) -> dict[str, str]:
    radice = read_compiled_template(build_pat_official_pdf("deposito_ricorso", campi)[0].getvalue())
    trovate: dict[str, str] = {}

    def visita(elemento, percorso):
        for figlio in elemento:
            nome = figlio.get("name")
            nuovo = percorso + ([nome] if nome else [])
            if isinstance(figlio.tag, str) and figlio.tag.endswith("field") and "rbContributo" in nuovo and valore(figlio):
                trovate[nome] = valore(figlio)
            visita(figlio, nuovo)

    visita(radice, [])
    return trovate


@pytest.mark.parametrize(
    ("scelta", "attesa"),
    [
        ("Non esente", {"nonEsente": "3"}),
        ("Da pagare", {"nonEsente": "3"}),
        ("Pagato", {"nonEsente": "3"}),
        ("Esente", {"esente": "2"}),
        ("Prenotato a debito", {"prenotazioneADebito": "1"}),
        ("Patrocinio a spese dello Stato", {"patrocinio": "4"}),
        ("Non dovuto", {"nonDovuto": "5"}),
    ],
)
def test_contributo_dal_campo_guidato(scelta, attesa):
    assert _scelte({**BASE, "contributo_unificato": scelta}) == attesa


@pytest.mark.parametrize(("scelta", "attesa"), [("Esente", {"esente": "2"}), ("Non esente", {"nonEsente": "3"})])
def test_contributo_dal_valore_xfa(scelta, attesa):
    assert _scelte({**BASE, "xfa_values": {PERCORSO: scelta}}) == attesa


def test_precompilazione_dal_fascicolo_non_confonde_non_esente():
    from types import SimpleNamespace

    from web.blueprints.api_v1_react import _pat_contributo_unificato_from_fascicolo as contributo

    def fascicolo(stato):
        return SimpleNamespace(pagamenti={"contributo_unificato": {"stato": stato}})

    assert contributo(fascicolo("Non esente")) == "Da pagare"
    assert contributo(fascicolo("Non esente - pagato con F24")) == "Pagato"
    assert contributo(fascicolo("Esente")) == "Esente"
    assert contributo(fascicolo("Prenotazione a debito")) == "Prenotato a debito"
