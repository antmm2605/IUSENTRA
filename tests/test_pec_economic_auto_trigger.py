from __future__ import annotations

from types import SimpleNamespace

import web.services.pec_pipeline_runtime as rt
from pct.sentenza_economic_repository import SentenzaEconomicRepository


SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda di Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
con distrazione in favore del procuratore antistatario avv. Bianchi."""


class _FakeFascManager:
    def get(self, fid):
        if fid != "F1":
            return None
        return SimpleNamespace(id="F1", numero_rg="1234", anno_rg=2025, nome_cliente="Mario Rossi",
                               tribunale="Tribunale di Milano", controparte="Beta S.r.l.", valore_causa=3000.0)


class _FakePecRepo:
    def __init__(self, detail):
        self._detail = detail

    def get_message_detail(self, message_id):
        return self._detail

    def _fascicoli_manager(self):
        return _FakeFascManager()


def _link_jobs():
    return [{"job_type": "link", "message_id": "M1", "result": {"fascicolo_id": "F1"}}]


def _detail(event_type):
    return {
        "parsed": {"legal_workflow": {"event_type": event_type}},
        "attachments": [{"content_type": "application/pdf", "filename": "sentenza.pdf",
                         "classification": "atto", "ocr_text": SENT_DISTRAZIONE, "sha256": "hh"}],
    }


def test_auto_trigger_su_deposito_sentenza(monkeypatch, tmp_path):
    monkeypatch.setattr(rt, "_economic_control_enabled", lambda: True)
    paths = {"SENTENZA_ECONOMIC_DB": str(tmp_path / "se.db")}
    report = rt.trigger_economic_audits_for_paths(
        paths, tenant_label="Studio-A", jobs=_link_jobs(), pec_repo=_FakePecRepo(_detail("deposito_sentenza")),
    )
    assert report["triggered"] == 1
    # audit persistito in ANTEPRIMA per lo slug minuscolo (coincide con la lettura UI)
    se_repo = SentenzaEconomicRepository(tmp_path / "se.db")
    audits = se_repo.list_sentenza_audits("studio-a", fascicolo_id="F1")
    assert len(audits) == 1
    assert audits[0]["audit"]["fonte"] == "PEC"
    assert audits[0]["status"] in {"to_review", "verified"}
    # e c'è l'evento credito avvocato antistatario (4200) leggibile dalla UI
    eventi = se_repo.list_economic_events("studio-a", fascicolo_id="F1")
    assert any(e["event_type"] == "apri_credito_avvocato_antistatario" and e["amount"] == 4200.0 for e in eventi)


def test_skip_se_non_deposito_sentenza(monkeypatch, tmp_path):
    monkeypatch.setattr(rt, "_economic_control_enabled", lambda: True)
    report = rt.trigger_economic_audits_for_paths(
        {"SENTENZA_ECONOMIC_DB": str(tmp_path / "se.db")},
        tenant_label="studio-a", jobs=_link_jobs(), pec_repo=_FakePecRepo(_detail("udienza_fissata")),
    )
    assert report["triggered"] == 0
    assert report["skipped"] == 1


def test_skip_totale_se_flag_spento(monkeypatch, tmp_path):
    monkeypatch.setattr(rt, "_economic_control_enabled", lambda: False)
    report = rt.trigger_economic_audits_for_paths(
        {"SENTENZA_ECONOMIC_DB": str(tmp_path / "se.db")},
        tenant_label="studio-a", jobs=_link_jobs(), pec_repo=_FakePecRepo(_detail("deposito_sentenza")),
    )
    assert report == {"triggered": 0, "skipped": 0, "errors": 0}
