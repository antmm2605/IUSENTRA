"""Fusione dei layer nella scheda operativa."""
from __future__ import annotations

from pct.procedure_completion.extractor import extract_normative_references, summarize_passage
from pct.procedure_completion.fusion import AVVERTIMENTO_BOZZA, fuse_card
from pct.procedure_completion.schema import normalize_request
from pct.procedure_completion.source_plan import build_source_plan


def _plan_reale():
    request = normalize_request({"codice": "010003", "denominazione": "Procedimento di ingiunzione ante causam"})
    return request, build_source_plan(request)


def test_estrattore_riconosce_entrambi_gli_ordini_di_citazione():
    citazioni = extract_normative_references(
        "Ai sensi dell'art. 633 c.p.c. e del D.Lgs. 14/2019, artt. 57-64, nonche' Codice di procedura civile - art. 644.",
        source_id="src1",
        url="https://www.normattiva.it",
    )
    riferimenti = {cit.riferimento for cit in citazioni}
    assert "art. 633 c.p.c." in riferimenti
    assert "art. 644 c.p.c." in riferimenti
    assert any("D.Lgs. 14/2019" in rif and "57" in rif for rif in riferimenti)
    assert all(cit.verificabile for cit in citazioni)


def test_summarize_e_troncamento_non_riscrittura():
    testo = "parola " * 200
    sintesi = summarize_passage(testo, max_chars=80)
    assert len(sintesi) <= 80
    assert sintesi.rstrip(".").split()[0] == "parola"


def test_fusione_da_catalogo_reale_compila_telematico_e_avvertimenti():
    from pct.procedure_lifecycle_templates import build_lifecycle_steps_for_xsd

    request, plan = _plan_reale()
    card = fuse_card(request, plan, lifecycle_steps=build_lifecycle_steps_for_xsd(plan.xsd_object))
    assert card.fonte_catalogo["codice"] == "010003"
    assert card.deposito_telematico["canale"].startswith("PCT")
    assert "D.M. 44/2011" in str(card.firma_digitale.get("base_normativa"))
    assert "Ricevuta di accettazione PEC (RdAC)" in card.ricevute_attese
    assert AVVERTIMENTO_BOZZA in card.avvertimenti_obbligatori
    assert card.articoli_rilevanti, "le citazioni derivano dalle fonti della famiglia XSD"
    assert card.lifecycle_steps, "passi del ciclo di vita dal layer procedurale"


def test_template_mancante_genera_gap_e_needs_review():
    request, plan = _plan_reale()
    card = fuse_card(request, plan, template_result={})
    assert card.atto_principale["stato"] == "needs_review"
    assert any(gap["codice_gap"] == "template_mancante" for gap in card.gap_evidenza)
    assert card.status == "needs_review"


def test_template_selezionato_collega_atto_principale():
    request, plan = _plan_reale()
    template_result = {
        "best_template": {"id": "TPL_RIC_MON", "titolo": "Ricorso per decreto ingiuntivo", "match_score": 88, "match_reasons": ["titolo"]},
        "alternatives": [{"id": "TPL_ALT", "titolo": "Atto alternativo", "match_score": 40}],
    }
    card = fuse_card(request, plan, template_result=template_result)
    assert card.template_selected["template_id"] == "TPL_RIC_MON"
    assert card.atto_principale["stato"] == "collegato_a_template"
    assert len(card.template_candidates) == 2
    assert not any(gap["codice_gap"] == "template_mancante" for gap in card.gap_evidenza)


def test_codice_sconosciuto_needs_review_senza_flusso_pct_presunto():
    request = normalize_request({"codice": "512075", "denominazione": "Accordo di ristrutturazione dei debiti"})
    plan = build_source_plan(request)
    card = fuse_card(request, plan)
    assert card.status == "needs_review"
    assert card.risk_level == "high"
    assert not card.deposito_telematico, "nessun flusso telematico presunto per codice non censito"
    assert not card.ricevute_attese


def test_knowledge_card_popola_guida_e_condizioni():
    request, plan = _plan_reale()
    knowledge = {
        "card_json": {
            "presupposti": ["Credito certo, liquido ed esigibile", "Prova scritta idonea"],
            "condizioni_procedibilita": [{"condizione": "Nessuna per il monitorio", "fonte_id": "src9"}],
            "rischi": ["Opposizione del debitore"],
        }
    }
    card = fuse_card(request, plan, knowledge_card=knowledge)
    assert "Credito certo, liquido ed esigibile" in card.guida_pratica
    assert card.condizioni_procedibilita[0]["fonte_id"] == "src9"
    assert "Opposizione del debitore" in card.rischi_operativi
    assert not any(gap["codice_gap"] == "guida_pratica_mancante" for gap in card.gap_evidenza)
