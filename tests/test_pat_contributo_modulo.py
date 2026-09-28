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


def test_tipo_atto_impugnato_salvato_con_la_voce_e_il_codice_del_modulo():
    # La tendina ha un solo elenco di voci (ALTRO, DPR, … ORDINANZA MINISTERIALE): «ALTRO» non diventa
    # «DELIBERA»; il codice lo calcola lo script del modulo (DELIBERA → 05).
    from pct.pat_anteprima import anteprima
    from pct.pat_xfa_schema import build_pat_xfa_schema_payload

    campo = next(f for s in build_pat_xfa_schema_payload("deposito_ricorso")["sections"] for f in s["fields"]
                 if f["name"] == "listTipoAtto")
    assert all(o["value"] == o["label"] for o in campo["options"]) and len(campo["options"]) == 10
    base = "template/ricorso/subform/tableAttiImpugnati/rigaAttoImpugnato/"
    pdf = build_pat_official_pdf("deposito_ricorso", {**BASE, "xfa_values": {
        base + "textFieldAutorita": "Comune di Venezia", base + "listTipoAtto": "DELIBERA",
        base + "numeroAtto": "12", base + "annoAtto": "2026"}})[0].getvalue()
    righe = {r["etichetta"]: r["valore"] for s in anteprima("deposito_ricorso", pdf)["sezioni"] for r in s["righe"]}
    assert righe["Atto Impugnato · Tipo provvedimento"] == "DELIBERA"
    radice = read_compiled_template(pdf)
    codici = [valore(c) for c in radice.iter() if isinstance(c.tag, str) and c.get("name") == "codiceAttoImpugnato"]
    assert codici == ["05"]


def test_voce_di_tendina_sconosciuta_non_si_scrive():
    from pct.pat_anteprima import anteprima

    pdf = build_pat_official_pdf("deposito_ricorso", {**BASE, "tipo_ricorso": "PNRR"})[0].getvalue()
    righe = {r["etichetta"]: r["valore"] for s in anteprima("deposito_ricorso", pdf)["sezioni"] for r in s["righe"]}
    assert "Tipologia di ricorso" not in righe or righe["Tipologia di ricorso"] != "PNRR"


def test_anteprima_modello_intatto_per_tutti_i_moduli():
    from pct.pat_anteprima import anteprima
    from pct.pat_pdf_templates import PAT_PDF_TEMPLATES

    for modulo in PAT_PDF_TEMPLATES:
        esito = anteprima(modulo, build_pat_official_pdf(modulo, BASE)[0].getvalue())
        assert esito["modelloIntatto"] is True and esito["versione"] in {"4.02", "4.03"}
