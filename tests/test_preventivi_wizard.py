from pct.fascicoli import Fascicolo, TipoFascicolo
from web.blueprints.preventivi import _area_pratica_da_fascicolo, _contesto_fascicolo_wizard


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
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.LAVORO)) == "Lavoro e previdenza"
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
