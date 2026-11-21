"""Lavori automatici di Lex, collaudo del 21/11/2026: motivo vero degli errori e coda senza anteprime superate."""
from __future__ import annotations

from lex.agents.executor import WorkflowAgentExecutor
from lex.agents.models import AgentPlan, AgentRun, AgentStep
from lex.agents.runtime import WorkflowAgentRuntime
from lex.agents.storage import WorkflowAgentStorage


class RegistroCheFallisce:
    def run_tool(self, tool_name, **kwargs):
        raise LookupError("Archivio dei modelli non leggibile.")


def _run(fascicolo_id: str = "", creato: str = "2026-07-10T19:34:15Z") -> AgentRun:
    lettura = AgentStep(step_key="contesto_fascicolo", title="Raccoglie contesto fascicolo senza inventare dati",
                        tool_name="collect_fascicolo_context", required_permissions=("fascicoli.leggi",),
                        input_json={"fascicolo_id": fascicolo_id})
    modelli = AgentStep(step_key="modelli", title="Seleziona template atti disponibili", tool_name="list_template_atti",
                        required_permissions=("fascicoli.leggi",), input_json={"tipo": "bozza atto"})
    bozza = AgentStep(step_key="bozza", title="Propone bozza documento in editor", tool_name="create_document_draft",
                      mutates_state=True, approval_required=True, required_permissions=("fascicoli.scrivi",),
                      input_json={"fascicolo_id": fascicolo_id})
    piano = AgentPlan(workflow_code="redazione_atto", title="Redazione atto", description="prova",
                      steps=[lettura, modelli, bozza], baseline_minutes=120, expected_review_minutes=18,
                      expected_correction_minutes=6)
    return AgentRun(workflow_code="redazione_atto", created_by="avvocato", tenant_scope="studio-a", plan=piano,
                    fascicolo_id=fascicolo_id, created_at=creato)


def test_senza_fascicolo_il_passo_dice_perche_non_parte():
    run = WorkflowAgentExecutor(RegistroCheFallisce()).preview(_run(), tenant_scope="studio-a",
                                                               user_permissions=["fascicoli.leggi", "fascicoli.scrivi"])
    contesto, modelli = run.plan.steps[0], run.plan.steps[1]
    assert contesto.status == "blocked" and "Nessun fascicolo scelto" in contesto.error_message
    # Un errore vero porta il suo motivo, non «Errore controllato».
    assert modelli.status == "failed" and modelli.error_message == "Lettura non riuscita: Archivio dei modelli non leggibile."


def test_proposte_vecchie_senza_fascicolo_chiuse_con_il_motivo(tmp_path):
    storage = WorkflowAgentStorage(runs_path=tmp_path / "runs.json", metrics_path=tmp_path / "metrics.json",
                                   tenant_scope="studio-a")
    runtime = WorkflowAgentRuntime(storage=storage)
    vecchia = WorkflowAgentExecutor(RegistroCheFallisce()).preview(_run(), tenant_scope="studio-a",
                                                                   user_permissions=["fascicoli.leggi"])
    recente = WorkflowAgentExecutor(RegistroCheFallisce()).preview(_run(creato="2026-11-20T08:00:00Z"),
                                                                   tenant_scope="studio-a", user_permissions=["fascicoli.leggi"])
    con_fascicolo = WorkflowAgentExecutor(RegistroCheFallisce()).preview(_run("F1"), tenant_scope="studio-a",
                                                                         user_permissions=["fascicoli.leggi"])
    for run in (vecchia, recente, con_fascicolo):
        storage.save_run(run)
    assert runtime.chiudi_proposte_superate(oggi="2026-11-21T09:00:00Z") == 1
    chiusa = storage.get_run(vecchia.id).proposals[0]
    assert chiusa.status == "rejected" and "senza fascicolo" in chiusa.reject_reason and "10/07/2026" in chiusa.reject_reason
    assert storage.get_run(recente.id).proposals[0].status == "pending"
    assert storage.get_run(con_fascicolo.id).proposals[0].status == "pending"
    # Idempotente: una seconda volta non chiude altro.
    assert runtime.chiudi_proposte_superate(oggi="2026-11-21T09:00:00Z") == 0
    giri = runtime.ultimi_giri_per_lavoro()
    assert giri["redazione_atto"]["data"] == "2026-11-20T08:00:00Z"
    assert any("Nessun fascicolo scelto" in p for p in giri["redazione_atto"]["problemi"])
