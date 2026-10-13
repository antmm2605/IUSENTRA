from __future__ import annotations

from types import SimpleNamespace

from pct.economic_dashboard import build_fascicolo_economic_dashboard
from pct.sentenza_economic_dashboard import (
    build_sentenza_economic_context_block,
    build_sentenze_economiche_summary,
)


_AUDITS = [
    {"safe_to_attach": True, "human_review_required": False, "status": "verified"},
    {"safe_to_attach": False, "human_review_required": True, "status": "to_review"},
]
_EVENTS = [
    {"event_type": "apri_credito_avvocato_antistatario", "amount": 4200.0, "status": "to_review"},
    {"event_type": "apri_credito_cliente", "amount": 1500.0, "status": "confirmed"},
    {"event_type": "verifica_contributo_unificato", "amount": None, "status": "to_review"},
    {"event_type": "apri_credito_cliente", "amount": 999.0, "status": "rejected"},
]


def test_summary_somma_solo_eventi_confermati():
    summary = build_sentenze_economiche_summary(_AUDITS, _EVENTS)
    totals = summary["totals"]
    assert totals["sentenze_lette"] == 2
    assert totals["sentenze_verificate"] == 1
    assert totals["da_verificare"] == 1
    assert totals["crediti_avvocato_antistatario"] == 0.0
    assert totals["crediti_cliente"] == 1500.0  # 'rejected' escluso
    assert totals["spese_liquidate_totale"] == 1500.0
    assert totals["contributo_unificato_alert"] == 1
    labels = [item["label"] for item in summary["worklist"]]
    assert "Importo da provvedimento da verificare" in labels
    assert "Spese distratte in favore dell'avvocato" not in labels


def test_dashboard_merge_additivo_non_rompe_base():
    fascicolo = SimpleNamespace(
        id="F1", numero="2025/001", titolo="Pratica", stato=SimpleNamespace(value="APERTO"),
        compenso_pattuito=0.0, valore_preventivato=0.0, valore_causa=0.0,
    )
    base = build_fascicolo_economic_dashboard(fascicolo=fascicolo, parcelle=[], timesheet_entries=[])
    assert "sentenze_economiche" not in base["totals"]
    base_kpi = len(base["kpis"])

    summary = build_sentenze_economiche_summary(_AUDITS, _EVENTS)
    merged = build_fascicolo_economic_dashboard(
        fascicolo=fascicolo, parcelle=[], timesheet_entries=[], sentenze=summary
    )
    assert len(merged["kpis"]) == base_kpi + 1
    assert merged["kpis"][-1]["label"] == "Spese da sentenza"
    assert merged["totals"]["sentenze_economiche"]["spese_liquidate_totale"] == 1500.0
    assert any(item["label"] == "Sentenze da verificare" for item in merged["worklist"])


def test_letture_ripetute_e_discordanti_non_creano_un_totale_certo():
    events = [
        {"id": "E1", "source_id": "A1", "event_type": "apri_credito_cliente", "amount": 1100.0, "status": "to_review"},
        {"id": "E2", "source_id": "A2", "event_type": "apri_credito_cliente", "amount": 1100.0, "status": "to_review"},
        {"id": "E3", "source_id": "A3", "event_type": "apri_credito_cliente", "amount": 1200.0, "status": "to_review"},
    ]
    original = [dict(event) for event in events]
    first = build_sentenze_economiche_summary(_AUDITS, events)
    second = build_sentenze_economiche_summary(_AUDITS, events)
    assert first == second
    assert first["totals"]["crediti_cliente"] == 0.0
    assert first["totals"]["spese_liquidate_totale"] == 0.0
    assert first["kpi"]["value"] == "Da verificare"
    evidence = [row for row in first["worklist"] if row["label"] == "Importo da provvedimento da verificare"]
    assert [row["value"] for row in evidence] == ["€ 1.100,00", "€ 1.100,00", "€ 1.200,00"]
    assert events == original


def test_context_block_pass_through():
    audit = {
        "documento_id": "DOC1",
        "document_hash_sha256": "abc123",
        "fonte": "PEC",
        "safe_to_attach": True,
        "match": {"overall_score": 0.93},
        "sentenza": {"spese_liquidate": {"beneficiario_credito": "avvocato"}},
        "contributo_unificato": {"status": "pagato"},
        "azioni": [{"type": "apri_credito_avvocato_antistatario"}],
    }
    block = build_sentenza_economic_context_block(audit)
    assert block["source"] == "sentenza_economic_audit"
    assert block["documento_origine"]["hash_sha256"] == "abc123"
    assert block["sentenza_economic_audit"]["match_score"] == 0.93
    assert block["sentenza_economic_audit"]["safe_to_attach"] is True
