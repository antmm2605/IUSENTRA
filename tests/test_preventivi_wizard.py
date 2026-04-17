from pathlib import Path

from werkzeug.datastructures import MultiDict

from pct.economico_context import carica_log_calcolo
from pct.fascicoli import Fascicolo, TipoFascicolo
from pct.motore_preventivo import catalogo_wizard
from web.blueprints.preventivi import (
    _area_pratica_da_fascicolo,
    _contesto_fascicolo_wizard,
    _contesto_log_wizard_da_form,
)


def _mk_fascicolo(tipo: TipoFascicolo, **overrides) -> Fascicolo:
    data = {
        "id": "fasc-001",
        "numero": "2026/001",
        "titolo": "Vendita di cose immobili",
        "tipo": tipo,
        "id_cliente": "cli-001",
    }
    data.update(overrides)
    return Fascicolo(**data)


def test_area_pratica_da_fascicolo_mappa_tipo_su_macro_area_wizard():
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.CIVILE)) == "Civile"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.LAVORO)) == "Civile"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.STRAGIUDIZIALE)) == "Stragiudiziale"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.PENALE)) == "Penale"


def test_contesto_fascicolo_wizard_espone_rg_label_e_area_proposta():
    fascicolo = _mk_fascicolo(
        TipoFascicolo.CIVILE,
        oggetto="Vendita di cose immobili",
        numero_rg="1025",
        anno_rg=2024,
        tribunale="Tribunale di Torino",
    )

    context = _contesto_fascicolo_wizard(fascicolo)

    assert context["rg_label"] == "RG 1025/2024"
    assert context["context_label"] == "RG 1025/2024 — Vendita di cose immobili"
    assert context["display_label"] == "RG 1025/2024 — Vendita di cose immobili"
    assert context["area_pratica"] == "Civile"
    assert context["tribunale"] == "Tribunale di Torino"


def test_contesto_fascicolo_wizard_usa_titolo_quando_oggetto_manca():
    fascicolo = _mk_fascicolo(TipoFascicolo.TRIBUTARIO, titolo="Avviso di accertamento IMU")

    context = _contesto_fascicolo_wizard(fascicolo)

    assert context["context_label"] == "Avviso di accertamento IMU"
    assert context["area_pratica"] == "Tributario"


def test_contesto_log_wizard_da_form_conserva_tassonomia_e_fonti():
    form = MultiDict(
        {
            "oggetto": "Licenziamento disciplinare",
            "id_pratica": "licenziamento",
            "area_pratica": "Civile",
            "area_tassonomica": "Giudiziale",
            "macro_area_tassonomica": "Diritto del Lavoro",
            "sottobranca_tassonomica": "Lavoro subordinato, licenziamenti e differenze retributive",
            "tassonomia_codice": "GIU_LAV_LAVORO",
            "procedura_operativa_codice": "PROC_LIC_IMP_001",
            "procedura_operativa_nome": "Impugnazione licenziamento individuale",
            "subbranch_operativa_codice": "SB_LAVORO_LICENZIAMENTI",
            "workflow_operativo_codice": "WF_CONTENZIOSO_LAVORO",
            "copertura_operativa": "FULL",
            "canale_operativo": "TRIBUNALE",
            "registro_operativo": "LAVORO",
            "tipo_compenso": "Per fasi processuali (D.M. 55/2014)",
            "tipo_procedimento": "Rito lavoro",
            "grado_sede": "Tribunale",
            "regola_tariffaria": "lavoro_subordinato",
            "complessita": "media",
            "valore_controversia": "15000",
            "perc_spese_generali": "15",
            "anticipazioni_art15": "43,50",
            "fonti_tassonomia_json": (
                '[{"title":"Codice di procedura civile","article":"rito lavoro","url":"https://www.normattiva.it/"},'
                '{"title":"Ministero del Lavoro","article":"licenziamenti","url":"https://www.lavoro.gov.it/"}]'
            ),
        }
    )

    payload = carica_log_calcolo(_contesto_log_wizard_da_form(form))

    assert payload["area_tassonomica"] == "Giudiziale"
    assert payload["macro_area_tassonomica"] == "Diritto del Lavoro"
    assert payload["sottobranca_tassonomica"] == "Lavoro subordinato, licenziamenti e differenze retributive"
    assert payload["tassonomia_codice"] == "GIU_LAV_LAVORO"
    assert payload["procedura_operativa_codice"] == "PROC_LIC_IMP_001"
    assert payload["procedura_operativa_nome"] == "Impugnazione del licenziamento individuale"
    assert payload["workflow_operativo_codice"].startswith("WF_")
    assert payload["copertura_operativa"]
    assert payload["canale_operativo"]
    assert payload["registro_operativo"]
    assert payload["riferimenti_tassonomia"] == [
        "Codice di procedura civile — rito lavoro",
        "Ministero del Lavoro — licenziamenti",
    ]


def test_catalogo_wizard_espone_inquadramento_operativo_per_le_tipologie_mappate():
    rows = [
        item
        for items in catalogo_wizard().values()
        for item in items
        if item.get("procedura_operativa_codice")
    ]

    assert rows, "Il catalogo del wizard deve esporre almeno una procedura operativa mappata"
    sample = rows[0]
    assert sample["procedura_operativa_nome"]
    assert sample["workflow_operativo_codice"]
    assert sample["canale_operativo"]
    assert sample["registro_operativo"]


def test_template_dettaglio_preventivo_espone_classificazione_tassonomica_e_fonti():
    template = Path("web/templates/preventivi/dettaglio_preventivo.html").read_text(encoding="utf-8")

    assert "Classificazione tassonomica" in template
    assert "Inquadramento operativo" in template
    assert "Procedura operativa" in template
    assert "Agganci di prodotto" in template
    assert "p.area_tassonomica" in template
    assert "p.macro_area_tassonomica" in template
    assert "p.sottobranca_tassonomica" in template
    assert "p.fonti_tassonomia" in template


def test_template_wizard_espone_classificazione_operativa_visibile():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "procedura_operativa_codice" in template
    assert "Classificazione operativa" in template
    assert "Procedura / servizio" in template
    assert "Tassonomia tecnica di supporto" in template
    assert "Inquadramento operativo" in template
    assert "Agganci di prodotto" in template
    assert "workflow_operativo_codice" in template
