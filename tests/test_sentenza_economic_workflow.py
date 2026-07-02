from __future__ import annotations

from types import SimpleNamespace

from pct.sentenza_economic_repository import SentenzaEconomicRepository
from pct.sentenza_economic_workflow import genera_parcella_da_credito, should_trigger_economic_audit
from web.services.sentenza_economic_runtime import run_pec_economic_trigger


CU_TIERS = [(1100.0, 43.0), (5200.0, 98.0)]

SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda di Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
con distrazione in favore del procuratore antistatario avv. Bianchi."""


def _fasc(**kw):
    base = dict(id="F1", id_cliente="CLI1", numero_rg="1234", anno_rg=2025, nome_cliente="Mario Rossi",
                tribunale="Tribunale di Milano", controparte="Beta S.r.l.", valore_causa=3000.0)
    base.update(kw)
    return SimpleNamespace(**base)


class _FakeFatturazione:
    def __init__(self):
        self.created = None

    def crea(self, id_cliente, voci, **kwargs):
        self.created = {"id_cliente": id_cliente, "voci": voci, **kwargs}
        return SimpleNamespace(id="P1", origine=kwargs.get("origine"), voci=voci)


def test_should_trigger_solo_su_deposito_sentenza():
    assert should_trigger_economic_audit({"event_type": "deposito_sentenza"}) is True
    assert should_trigger_economic_audit({"event_type": "udienza_fissata"}) is False
    assert should_trigger_economic_audit({}) is False


def test_parcella_non_generata_se_non_confermato():
    evento = {"id": "E1", "event_type": "apri_credito_avvocato_antistatario", "amount": 4200.0, "status": "to_review", "beneficiary_type": "avvocato"}
    res = genera_parcella_da_credito(evento=evento, fascicolo=_fasc(), fatturazione=_FakeFatturazione())
    assert res["ok"] is False
    assert res["code"] == "not_confirmed"


def test_parcella_generata_da_credito_confermato_origine_sentenza():
    evento = {"id": "E1", "event_type": "apri_credito_avvocato_antistatario", "amount": 4200.0, "status": "confirmed", "beneficiary_type": "avvocato"}
    fatt = _FakeFatturazione()
    res = genera_parcella_da_credito(evento=evento, fascicolo=_fasc(), fatturazione=fatt, audit_id="A1")
    assert res["ok"] is True
    assert fatt.created["origine"] == "sentenza"
    assert fatt.created["voci"][0].prezzo_unitario == 4200.0
    assert fatt.created["dati_personalizzati"]["sentenza_economic_audit_id"] == "A1"


def test_evento_non_credito_rifiutato():
    evento = {"id": "E2", "event_type": "verifica_contributo_unificato", "status": "confirmed"}
    res = genera_parcella_da_credito(evento=evento, fascicolo=_fasc(), fatturazione=_FakeFatturazione())
    assert res["code"] == "not_a_credit"


def test_pec_trigger_solo_su_deposito_sentenza(tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    non_trig = run_pec_economic_trigger(
        classification={"event_type": "udienza_fissata"}, fascicolo=_fasc(), testo=SENT_DISTRAZIONE,
        repo=repo, cu_tiers=CU_TIERS, tenant_id="studio-a",
    )
    assert non_trig["code"] == "not_triggered"

    trig = run_pec_economic_trigger(
        classification={"event_type": "deposito_sentenza"}, fascicolo=_fasc(), testo=SENT_DISTRAZIONE,
        repo=repo, cu_tiers=CU_TIERS, tenant_id="studio-a", message_id="MSG1",
    )
    assert trig["ok"] is True
    # anteprima: audit persistito come to_review, nessuna scrittura definitiva
    audits = repo.list_sentenza_audits("studio-a", fascicolo_id="F1")
    assert len(audits) == 1
    assert audits[0]["audit"]["fonte"] == "PEC"
