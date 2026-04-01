from pct.motore_preventivo import (
    catalogo_wizard,
    get_tipo_pratica,
    redattore_preventivo_iniziale,
)


def test_atto_citazione_ha_metadata_professionali_e_riferimenti():
    tp = get_tipo_pratica("atto_citazione")
    assert tp is not None
    assert tp.summary
    assert tp.when_to_use
    assert tp.motore_label == "Motore parametrico giudiziale civile"
    assert tp.redattore_label == "Redattore preventivo giudiziale civile"
    assert tp.esborsi_tipici
    titles = {ref["title"] for ref in tp.normative_references}
    assert "L. 31 dicembre 2012, n. 247" in titles
    assert "D.M. 10 marzo 2014, n. 55" in titles
    assert any("art. 163 c.p.c." in (ref.get("article") or "") for ref in tp.normative_references)


def test_catalogo_wizard_espone_fasi_e_checklist_serializzabili():
    catalogo = catalogo_wizard()
    assert "Stragiudiziale" in catalogo
    mediazione = next(item for item in catalogo["Stragiudiziale"] if item["id"] == "mediazione")
    assert mediazione["fasi_default_keys"] == ["attivazione", "rivitalizzazione", "conciliazione"]
    assert mediazione["checklist_iniziale"]
    assert any(ref["title"] == "D.Lgs. 4 marzo 2010, n. 28" for ref in mediazione["normative_references"])


def test_redattore_preventivo_iniziale_restituisce_scheda_pronta_per_wizard():
    scheda = redattore_preventivo_iniziale("negoziazione_assistita")
    assert scheda["id"] == "negoziazione_assistita"
    assert scheda["oggetto_template"].startswith("Preventivo professionale")
    assert "Informativa resa ai sensi dell'art. 13" in scheda["note_template"]
    assert any(ref["title"] == "D.L. 12 settembre 2014, n. 132" for ref in scheda["normative_references"])


def test_mediazione_riporta_anche_il_regolamento_spese_post_cartabia():
    scheda = redattore_preventivo_iniziale("mediazione")
    titles = {ref["title"] for ref in scheda["normative_references"]}
    assert "D.M. 24 ottobre 2023, n. 150" in titles


def test_catalogo_include_tipologie_civili_e_stragiudiziali_aggiunte():
    catalogo = catalogo_wizard()
    civile_ids = {item["id"] for item in catalogo["Civile"]}
    stragiud_ids = {item["id"] for item in catalogo["Stragiudiziale"]}
    assert "sfratto_morosita" in civile_ids
    assert "risarcimento_danni" in civile_ids
    assert "sinistro_stradale_stragiudiziale" in stragiud_ids
