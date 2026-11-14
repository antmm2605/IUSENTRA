from pct.practice_engine.models import DepositReceipt, ValidationResult, ValidatorStatus
from pct.practice_engine.state_machine import can_transition, has_final_positive_receipt


def test_transizioni_valide_e_vietate():
    ok, _ = can_transition("FASCICOLO_APERTO", "DOCUMENTI_DA_COMPLETARE")
    assert ok is True
    ok, reason = can_transition("FASCICOLO_APERTO", "ACQUISITO", channel="PCT_CIVILE", receipts=[])
    assert ok is False
    assert "esito finale" in reason


def test_pronto_deposito_vietato_con_blocchi():
    result = ValidationResult("atto_principale_presente", ValidatorStatus.BLOCK.value, "BLOCK", "Manca atto")
    ok, reason = can_transition("VALIDAZIONE_IN_CORSO", "PRONTO_AL_DEPOSITO", validation_results=[result])
    assert ok is False
    assert "blocchi" in reason


def test_acquisito_richiede_ricevuta_finale_corretta():
    pec = DepositReceipt("r1", "d1", "f1", "ACCETTAZIONE_PEC", "ACCETTATO_PEC", positive=True)
    cancelleria = DepositReceipt("r2", "d1", "f1", "ESITO_CANCELLERIA", "ACQUISITO", positive=True)
    assert has_final_positive_receipt("PCT_CIVILE", [pec]) is False
    assert has_final_positive_receipt("PCT_CIVILE", [pec, cancelleria]) is True
    ok, _ = can_transition("ACCETTATO_DA_CANCELLERIA", "ACQUISITO", channel="PCT_CIVILE", receipts=[cancelleria])
    assert ok is True


def test_regia_distingue_bozza_documento_emesso_e_incasso():
    from types import SimpleNamespace

    from pct.practice_engine.riepilogo_economico import _economic_summary

    repo = SimpleNamespace(list_audit=lambda _: [])
    bozza = SimpleNamespace(id="bozza", stato="BOZZA")
    emessa = SimpleNamespace(id="emessa", stato="EMESSA")
    result = _economic_summary(None, None, [bozza], repo, "pratica")
    assert result["proformaDraft"] is True
    assert result["proformaIssued"] is False
    assert result["invoiceIssued"] is False
    assert result["paymentParcellaId"] == ""
    assert "id_documento=bozza" in result["proformaHref"]

    result = _economic_summary(None, None, [bozza, emessa], repo, "pratica")
    assert result["proformaIssued"] is True
    assert result["invoiceIssued"] is True
    assert result["paymentParcellaId"] == "emessa"
    assert "id_documento=emessa" in result["proformaHref"]
