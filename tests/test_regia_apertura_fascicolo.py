from pct.workflow_commerciale import apri_fascicolo_automatico

from tests.regia_test_utils import make_context_objects


def test_apertura_fascicolo_da_pratica_commerciale_genera_regia(tmp_path):
    ctx = make_context_objects(tmp_path, paid=True)
    result = apri_fascicolo_automatico(
        gp=ctx.preventivi,
        gf=ctx.fascicoli,
        gs=ctx.scadenziario,
        cliente=ctx.cliente,
        preventivo=ctx.preventivo,
        conferimento=ctx.conferimento,
        avvocato="Avv. Regia",
    )
    fascicolo = result["fascicolo"]
    assert result["created"] is True
    assert fascicolo.id_cliente == ctx.cliente.id
    assert "licenziamento" in fascicolo.oggetto.lower()
    assert fascicolo.procedura_operativa_codice == "PROC_LIC_IMP_001"
    assert fascicolo.canale_operativo
    assert fascicolo.registro_operativo
    assert ctx.preventivi.get_preventivo(ctx.preventivo.id).id_fascicolo == fascicolo.id
    assert ctx.preventivi.get_conferimento(ctx.conferimento.id).id_fascicolo == fascicolo.id

    pe_repo = ctx.repo.from_fascicoli_db(str(ctx.fascicoli.db_path), studio_db=getattr(ctx.fascicoli, "_studio_db", None))
    assert result["practice_engine_profile"] == "PROC_LIC_IMP_001"
    assert pe_repo.get_profile_snapshot(fascicolo.id) is None
    assert pe_repo.list_checklist(fascicolo.id) == []
    assert pe_repo.list_slots(fascicolo.id) == []
    assert pe_repo.latest_state(fascicolo.id) == "PRE_FASCICOLO"
    assert any(event.event_type == "FASCICOLO_OPENED_FROM_COMMERCIAL_WORKFLOW" for event in pe_repo.list_audit(fascicolo.id))


def test_override_economico_deve_essere_auditato(tmp_path):
    ctx = make_context_objects(tmp_path, paid=False)
    result = apri_fascicolo_automatico(
        gp=ctx.preventivi,
        gf=ctx.fascicoli,
        gs=ctx.scadenziario,
        cliente=ctx.cliente,
        preventivo=ctx.preventivo,
        conferimento=ctx.conferimento,
        avvocato="Avv. Regia",
    )
    fascicolo = result["fascicolo"]
    pe_repo = ctx.repo.from_fascicoli_db(str(ctx.fascicoli.db_path), studio_db=getattr(ctx.fascicoli, "_studio_db", None))
    pe_repo.audit(fascicolo.id, "ECONOMIC_OVERRIDE", reason="Urgenza deposito cautelare", actor="Avv. Regia")
    assert any(event.event_type == "ECONOMIC_OVERRIDE" and event.reason for event in pe_repo.list_audit(fascicolo.id))
