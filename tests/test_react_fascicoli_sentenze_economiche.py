from __future__ import annotations

from types import SimpleNamespace

import web.services.react_fascicoli_bridge as bridge
import web.services.sentenza_economic_runtime as runtime
from pct.sentenza_economic_repository import SentenzaEconomicRepository


SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda di Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
con distrazione in favore del procuratore antistatario avv. Bianchi."""


def _fasc():
    return SimpleNamespace(id="F1", numero_rg="1234", anno_rg=2025, nome_cliente="Mario Rossi",
                           tribunale="Tribunale di Milano", controparte="Beta S.r.l.", valore_causa=3000.0)


def _sentenza_doc():
    return SimpleNamespace(id="D1", nome="sentenza-tribunale.pdf", tipo="SENTENZA", hash_sha256="hash-sentenza")


def test_bridge_helper_espone_gli_importi_liquidati(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True,
        "summary": {
            "kpi": {"label": "Spese da sentenza", "value": "€ 4.200,00", "tone": "primary"},
            "worklist": [{"label": "Spese distratte in favore dell'avvocato", "hint": "Credito diretto ex art. 93 c.p.c.", "value": "€ 4.200,00", "tone": "info"}],
            "totals": {"sentenze_lette": 1, "sentenze_verificate": 1, "da_verificare": 0,
                       "crediti_cliente": 0.0, "crediti_avvocato_antistatario": 4200.0,
                       "spese_liquidate_totale": 4200.0, "contributo_unificato_alert": 0},
        },
    })
    block = bridge._sentenze_economiche("F1")
    assert block is not None
    assert block["totals"]["spese_liquidate_totale"] == 4200.0
    assert block["totals"]["crediti_avvocato_antistatario"] == 4200.0
    assert any("art. 93" in item["hint"] for item in block["worklist"])


def test_bridge_helper_none_se_flag_spento(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {"ok": False, "code": "feature_disabled"})
    assert bridge._sentenze_economiche("F1") is None


def test_bridge_helper_none_se_nessuna_sentenza(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True, "summary": {"kpi": {}, "worklist": [], "totals": {"sentenze_lette": 0}},
    })
    assert bridge._sentenze_economiche("F1") is None


def test_bridge_helper_non_mostra_id_documento_numerico():
    assert bridge._readable_document_source("20260317101453130") == "Documento indicizzato del fascicolo"
    assert bridge._readable_document_source("20260317101453130.PDF") == "Documento indicizzato del fascicolo"


def test_payment_item_non_espone_id_documento_numerico():
    item = bridge._payment_item(
        "contributo_unificato",
        {
            "status": "pagato",
            "importo": 49.0,
            "documento_fonte": "20260317101453130.PDF",
        },
        "F1",
    )

    assert item["documentoFonte"] == "Ricevuta pagoPA"
    assert item["documentoFonteRaw"] == "20260317101453130.PDF"


def test_bridge_helper_sanitizza_fonte_sentenza_runtime(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True,
        "summary": {
            "kpi": {"label": "Evidenze economiche lette", "value": "€ 258,00", "tone": "success"},
            "worklist": [{
                "label": "Liquidazione letta",
                "value": "€ 258,00",
                "hint": "Pagato - Fonte: sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "success",
            }],
            "totals": {"sentenze_lette": 1, "sentenze_verificate": 0, "da_verificare": 0,
                       "crediti_cliente": 0.0, "crediti_avvocato_antistatario": 0.0,
                       "spese_liquidate_totale": 258.0, "contributo_unificato_alert": 0},
        },
    })

    block = bridge._sentenze_economiche("F1")

    assert block is not None
    assert "sentenza_key" not in block["worklist"][0]["hint"]
    assert "Sentenza del 15/06/2026" in block["worklist"][0]["hint"]


def test_bridge_helper_mostra_evidenze_economiche_gia_lette_se_audit_vuoto(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True, "summary": {"kpi": {}, "worklist": [], "totals": {"sentenze_lette": 0}},
    })
    block = bridge._sentenze_economiche("F1", payment_summary={
        "items": {
            "liquidazione_giudice": {
                "status": "pagato",
                "statusLabel": "Pagato",
                "importo": 258.0,
                "documentoFonte": "sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "success",
            },
            "parcella": {
                "status": "da_emettere",
                "statusLabel": "Da emettere",
                "importo": 376.46,
                "documentoFonte": "sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "warning",
            },
        },
    })

    assert block is not None
    assert block["totals"]["sentenze_lette"] == 1
    assert block["totals"]["spese_liquidate_totale"] == 258.0
    assert block["kpi"]["value"] == "€ 258,00"
    assert any(item["label"] == "Liquidazione letta" and item["value"] == "€ 258,00" for item in block["worklist"])
    assert all("sentenza_key" not in item["hint"] for item in block["worklist"])
    assert any("Sentenza del 15/06/2026" in item["hint"] for item in block["worklist"])


def test_prova_reale_gli_importi_arrivano_dal_repository(monkeypatch, tmp_path):
    # Semina un audit reale (distrazione -> credito avvocato 4200) nel repo tenant.
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    runtime.run_analysis(
        fascicolo=_fasc(), testo=SENT_DISTRAZIONE, repo=repo,
        cu_tiers=[(1100.0, 43.0), (5200.0, 98.0)], tenant_id="studio-a",
        actor_id="avv", documento_id="D1", document_hash_sha256="hh",
    )
    # Il runtime (percorso vivo del payload) legge quel repo per il tenant/fascicolo.
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)

    payload = runtime.build_sentenza_economic_payload("F1")
    assert payload["ok"] is True
    totals = payload["summary"]["totals"]
    assert totals["sentenze_lette"] == 1
    assert totals["crediti_avvocato_antistatario"] == 4200.0
    assert totals["spese_liquidate_totale"] == 4200.0
    # E il bridge lo trasforma nel blocco che il frontend renderizza.
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": payload)
    block = bridge._sentenze_economiche("F1")
    assert block["totals"]["spese_liquidate_totale"] == 4200.0


def test_payload_auto_analizza_documenti_sentenza_non_ancora_letti(monkeypatch, tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    fascicolo = _fasc()
    fascicolo.documenti = [_sentenza_doc()]
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)
    monkeypatch.setattr(runtime, "_resolve_fascicolo", lambda fid: fascicolo if fid == "F1" else None)
    monkeypatch.setattr(runtime, "_document_texts_for_fascicolo", lambda _fascicolo, _tenant_id: {"D1": SENT_DISTRAZIONE})

    payload = runtime.build_sentenza_economic_payload("F1")
    assert payload["ok"] is True
    assert payload["autoAnalysis"]["analyzed"] == 1
    assert payload["summary"]["totals"]["sentenze_lette"] == 1

    second = runtime.build_sentenza_economic_payload("F1")
    assert second["autoAnalysis"]["analyzed"] == 0
    assert second["autoAnalysis"]["skipped"] == 1
    assert second["summary"]["totals"]["sentenze_lette"] == 1


def test_payload_auto_analizza_tutte_le_sentenze_candidate_senza_limite_fisso(monkeypatch, tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    fascicolo = _fasc()
    fascicolo.documenti = [
        SimpleNamespace(id=f"D{index}", nome=f"sentenza-{index}.pdf", tipo="SENTENZA", hash_sha256=f"hash-{index}")
        for index in range(10)
    ]
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)
    monkeypatch.setattr(runtime, "_resolve_fascicolo", lambda fid: fascicolo if fid == "F1" else None)
    monkeypatch.setattr(
        runtime,
        "_document_texts_for_fascicolo",
        lambda _fascicolo, _tenant_id: {f"D{index}": SENT_DISTRAZIONE for index in range(10)},
    )

    payload = runtime.build_sentenza_economic_payload("F1")

    assert payload["ok"] is True
    assert payload["autoAnalysis"]["candidates"] == 10
    assert payload["autoAnalysis"]["analyzed"] == 10
    assert payload["summary"]["totals"]["sentenze_lette"] == 10
