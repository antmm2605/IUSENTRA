"""Redazione: ricorso del rito semplificato al posto del 702-bis abrogato; ricorso di lavoro anche per il pubblico impiego.

Testi vigenti letti l'08/11/2026 nell'archivio Normattiva del software: artt. 281-decies e 281-undecies c.p.c. (D.Lgs.
149/2022, art. 35: procedimenti instaurati dopo il 28/02/2023); art. 63 D.Lgs. 165/2001; artt. 413, quinto comma, e
417-bis c.p.c.; art. 11 R.D. 1611/1933.
"""

from types import SimpleNamespace

from pct.compilatore_atti import MODEL_INDEX
from pct.redazione_contesto import condizioni_dal_fascicolo
from pct.redazione_normativa import RIFERIMENTI_BASE
from pct.schede_compilazione import campi_da_chiedere, scheda_per_template
from pct.template_atti_compiler_bindings import compiler_alias_specs


def test_ricorso_semplificato_non_usa_il_compilatore_della_citazione():
    binding = next(b for b in compiler_alias_specs() if b["compiler_code"] == "CIV_INT_001")
    assert binding["base_code"] == "CIV_INT_001"  # modello proprio, non piu alias della citazione (CIV_CIT_001)
    assert "702-bis" not in binding["title"] and "281-undecies" in binding["title"]
    modello = MODEL_INDEX["CIV_INT_001"]
    assert "alias_of" not in modello and modello["name"].startswith("Ricorso nel procedimento semplificato")
    assert "hearing_date" not in modello["required_extra_fields"]  # l'udienza la fissa il giudice con decreto


def test_catalogo_senza_ricorso_ex_702_bis():
    from pct.template_atti_catalogo import build_builtin_templates

    modelli = build_builtin_templates()
    assert not [t for t in modelli if "702-bis" in str(t.get("titolo") or "")]
    semplificato = next(t for t in modelli if t.get("id") == "TMP-CIV-002" or t.get("codice") == "TMP-CIV-002")
    assert "procedimento semplificato di cognizione" in semplificato["titolo"]
    assert "702-bis" not in str(semplificato)


def test_norme_del_rito_semplificato_collegate_al_modello():
    articoli = {r.articolo for r in RIFERIMENTI_BASE if "CIV_INT_001" in r.modelli}
    assert {"281-decies", "281-undecies"} <= articoli


def test_ricorso_di_lavoro_non_chiede_la_dimensione_del_datore_se_non_serve():
    scheda = scheda_per_template("LAV_001")
    dimensione = next(c for c in scheda["campi"] if c["campo"] == "dimensione_datore")
    assert dimensione["obbligatorio"] is False
    domande = {d["campo"] for d in campi_da_chiedere(scheda, {})}
    assert "dimensione_datore" not in domande


def test_ricorso_di_lavoro_con_elementi_del_pubblico_impiego():
    scheda = scheda_per_template("LAV_001")
    campi = {c["campo"]: c for c in scheda["campi"]}
    assert {"pubblico_impiego", "ufficio_di_servizio", "notifica_amministrazione"} <= set(campi)
    assert "1611/1933" in campi["notifica_amministrazione"]["fonte"]["regola"]
    assert ("165/2001", "63") in {(n["atto"], n["articolo"]) for n in scheda["base_normativa"]}
    assert ("codice_procedura_civile", "417bis") in {(n["atto"], n["articolo"]) for n in scheda["base_normativa"]}


def test_norme_del_pubblico_impiego_solo_se_il_datore_e_pubblico():
    pubbliche = {r.id: r for r in RIFERIMENTI_BASE if r.condizione == "pubblico_impiego"}
    assert {"dlgs165_63", "cpc_413_pa", "cpc_417bis", "rd1611_11"} <= set(pubbliche)
    assert all("LAV_RIC_001" in r.modelli and r.url_fonte for r in pubbliche.values())
    docente = SimpleNamespace(tipo="LAVORO", titolo="Carta del docente", oggetto="", note="", controparte="Ministero dell'Istruzione e del Merito")
    privato = SimpleNamespace(tipo="LAVORO", titolo="Differenze retributive", oggetto="", note="", controparte="Alfa srl")
    assert condizioni_dal_fascicolo(docente)["pubblico_impiego"] is True
    assert condizioni_dal_fascicolo(privato)["pubblico_impiego"] is False
