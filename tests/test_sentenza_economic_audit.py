from __future__ import annotations

from types import SimpleNamespace

from pct.sentenza_economic_audit import (
    assess_contributo_unificato,
    build_audit,
    extract_economics,
    load_ruleset,
)


CU_TIERS = [(1100.0, 43.0), (5200.0, 98.0), (26000.0, 237.0)]


def _fasc(**kw):
    base = dict(
        id="F1",
        numero_rg="1234",
        anno_rg=2025,
        nome_cliente="Mario Rossi",
        tribunale="Tribunale di Milano",
        controparte="Beta S.r.l.",
    )
    base.update(kw)
    return SimpleNamespace(**base)


SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO
Sezione Prima Civile - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda proposta da Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
oltre spese generali, con distrazione in favore del procuratore antistatario avv. Bianchi."""

SENT_CLIENTE = """TRIBUNALE ORDINARIO DI MILANO
Sezione Prima Civile - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda proposta da Mario Rossi contro Beta S.r.l.;
condanna Beta S.r.l. alla rifusione delle spese di lite, che liquida in complessivi euro 1.500,00 oltre accessori di legge."""

SENT_COMPENSATE = """TRIBUNALE ORDINARIO DI MILANO - R.G. 1234/2025
definitivamente pronunciando, accoglie parzialmente la domanda di Mario Rossi contro Beta S.r.l.;
compensa integralmente le spese di lite tra le parti."""


def test_match_rg_e_distrazione_credito_avvocato():
    audit = build_audit(fascicolo=_fasc(), testo=SENT_DISTRAZIONE, cu_tiers=CU_TIERS)
    assert audit.match.rg_match is True
    assert audit.safe_to_attach is True
    assert audit.sentenza.spese_liquidate.beneficiario_credito == "avvocato"
    assert audit.sentenza.spese_liquidate.distrazione_spese is True
    assert audit.sentenza.spese_liquidate.totale_stimato == 4200.0
    tipi = [a.type for a in audit.azioni]
    assert "apri_credito_avvocato_antistatario" in tipi
    # regola #4: ogni azione richiede conferma avvocato
    assert all(a.requires_confirmation for a in audit.azioni)


def test_rg_mismatch_blocca_alimentazione_economica():
    audit = build_audit(fascicolo=_fasc(numero_rg="9999"), testo=SENT_DISTRAZIONE, cu_tiers=CU_TIERS)
    assert audit.match.rg_match is False
    assert audit.safe_to_attach is False
    assert audit.human_review_required is True
    # regola #1: nessuna azione economica, solo riconciliazione
    assert [a.type for a in audit.azioni] == ["verifica_riconciliazione"]
    assert audit.status == "needs_reconciliation"
    assert audit.match.issues  # motivo esplicitato


def test_condanna_senza_distrazione_credito_cliente():
    # regola #2: mai credito avvocato senza distrazione
    audit = build_audit(fascicolo=_fasc(), testo=SENT_CLIENTE)
    spese = audit.sentenza.spese_liquidate
    assert spese.condanna_spese is True
    assert spese.distrazione_spese is False
    assert spese.beneficiario_credito == "cliente"
    assert spese.totale_stimato == 1500.0
    assert "apri_credito_cliente" in [a.type for a in audit.azioni]


def test_compensazione_nessun_credito():
    ext = extract_economics(SENT_COMPENSATE)
    assert ext.spese_liquidate.spese_compensate is True
    assert ext.spese_liquidate.beneficiario_credito == "incerto"


def test_contributo_unificato_stati():
    rules = load_ruleset()
    esente = assess_contributo_unificato("Il ricorrente e' esente dal contributo unificato.", ruleset=rules)
    assert esente.status == "esente"
    assert esente.human_review_required is False

    invito = assess_contributo_unificato("Si trasmette invito al pagamento ex art. 248 D.P.R. 115/2002.", ruleset=rules)
    assert invito.status == "da_integrare"
    assert invito.invito_pagamento_rilevato is True

    # regola #5: "pagato" mai senza prova (importo + IUV/data)
    incerto = assess_contributo_unificato("contributo unificato versato", ruleset=rules)
    assert incerto.status == "incerto"
    pagato = assess_contributo_unificato(
        "contributo unificato versato",
        evidence={"importo_pagato": 98.0, "iuv": "RF00", "fonte_prova": "ricevuta_pagamento"},
        ruleset=rules,
    )
    assert pagato.status == "pagato"


def test_contributo_atteso_da_scaglioni_normativi():
    cu = assess_contributo_unificato("contributo unificato", valore_causa=3000.0, cu_tiers=CU_TIERS)
    # regola #6: importo atteso dai soli scaglioni versionati
    assert cu.importo_atteso == 98.0


def test_ruleset_versionato_ha_fonti_normative():
    rules = load_ruleset()
    assert rules["ambito"] == "civile"
    assert "art. 93" in rules["fonti"]["distrazione"]
    assert "D.P.R. 115/2002" in rules["fonti"]["contributo_unificato"]
