from types import SimpleNamespace

from pct.fatturazione import StatoParcella
from pct.workflow_pipeline import build_cliente_workflow_pipeline, build_fascicolo_workflow_pipeline


def test_cliente_workflow_identifica_step_incasso():
    cliente = SimpleNamespace(id="cli-1", nome_completo="Mario Rossi")
    preventivo = SimpleNamespace(stato=SimpleNamespace(value="ACCETTATO"))
    conferimento = SimpleNamespace(id="conf-1")
    fascicolo = SimpleNamespace(id="fas-1")
    timesheet = SimpleNamespace(ore=2.5)
    parcella = SimpleNamespace(totale=480.0, stato=StatoParcella.EMESSA)

    pipeline = build_cliente_workflow_pipeline(
        cliente=cliente,
        preventivi=[preventivo],
        conferimenti=[conferimento],
        fascicoli=[fascicolo],
        parcelle=[parcella],
        timesheet_entries=[timesheet],
    )

    assert pipeline["current_key"] == "incasso"
    assert pipeline["saldo_aperto"] == 480.0
    assert any(stage["key"] == "fattura" and stage["complete"] for stage in pipeline["stages"])


def test_fascicolo_workflow_chiede_prima_attivita():
    fascicolo = SimpleNamespace(id="fas-1", id_cliente="cli-1", attivita_count=0)

    pipeline = build_fascicolo_workflow_pipeline(
        fascicolo=fascicolo,
        cliente=SimpleNamespace(id="cli-1"),
        preventivo=None,
        conferimento=None,
        parcelle=[],
        timesheet_entries=[],
    )

    assert pipeline["next_action"] == "Registra le prime attivita' operative del fascicolo."
    assert pipeline["tone"] == "info"
    assert pipeline["stages"][2]["count"] == 0
