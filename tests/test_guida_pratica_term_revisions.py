import json

from pct.guida_pratica.term_revisions import caution_term, family_term, revise_item, revise_payload
from pct.guida_pratica.service import GuidaPraticaService
from scripts.import_guida_pratica_termini_processuali import _template_from_term, collect_terms


def test_revised_family_rule_preserves_history_and_other_fields():
    original = {"codice": "411003", "campi": ["cliente"], "termini_processuali": [
        {"termine": "Appello generico", "giorni": 30, "norma": "art. 325 c.p.c."}]}
    result = revise_item(original)
    assert result["termini_processuali"] == [family_term()]
    assert result["term_rules_history"][0]["previous_terms"] == original["termini_processuali"]
    assert result["campi"] == original["campi"]
    assert original["termini_processuali"][0]["giorni"] == 30
    assert revise_item(result) == result


def test_unrelated_procedure_is_preserved_without_copying_whole_catalog():
    row = {"codice": "199090", "termini_processuali": [{"giorni": 30}]}
    result = revise_payload({"codici_materia": [row], "version": "test"})
    assert result["codici_materia"][0] is row
    assert result["version"] == "test"


def test_raw_import_and_guide_use_identical_revised_rules(tmp_path):
    source = tmp_path / "kb.json"
    source.write_text(json.dumps({"codici_materia": [
        {"codice": "411003", "denominazione": "Famiglia", "categoria": "procedimenti amministrativi e civili", "termini_processuali": [{"giorni": 30}]},
        {"codice": "014100", "denominazione": "Cautelare", "termini_processuali": [{"giorni": 15}]},
    ]}), encoding="utf-8")
    rows = collect_terms([source])
    assert len(rows) == 2
    by_code = {row["codice"]: _template_from_term(row) for row in rows}
    assert by_code["411003"]["base_value"] == family_term()["giorni"] == 10
    assert by_code["411003"]["ferial_suspension_policy"] == "manual_review"
    assert by_code["411003"]["matter_type"] == "civil"
    assert by_code["014100"]["matter_type"] == "civil"
    assert by_code["014100"]["base_value"] == caution_term()["giorni"] == 15
    assert by_code["014100"]["ferial_suspension_policy"] == "excluded"
    assert by_code["014100"]["suspend_august"] is False
    assert len(by_code["014100"]["metadata"]["source_event_options"]) == 3


def test_full_guide_merges_do_not_reintroduce_generic_appeal_deadlines():
    service = GuidaPraticaService()
    for code, expected in (("411003", family_term()), ("014100", caution_term())):
        guidance = service.get_guidance(code)
        assert guidance["termini_processuali"] == [expected]
        assert guidance["term_rules_history"]
        assert guidance["term_rules_revision"]["source"] == expected["fonte_verifica"]
