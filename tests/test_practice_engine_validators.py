from types import SimpleNamespace

from pct.fascicoli import TipoDocumento
from pct.practice_engine.deposit_readiness import run_predeposit_check
from pct.practice_engine.models import SlotType, ValidatorStatus
from pct.practice_engine.profiles import get_profile
from pct.practice_engine.validators import ValidationContext, run_validator

from tests.regia_test_utils import encrypted_pdf_bytes, link_required_documents, make_simple_fascicolo, pdfa_bytes


def _ctx(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    cliente = SimpleNamespace(codice_fiscale="RSSMRA80A01H501U", email="cliente@example.test")
    return gf, repo, fascicolo, profile, cliente


def test_anagrafici_ed_economici_bloccano_quando_mancano(tmp_path):
    gf, repo, fascicolo, profile, _cliente = _ctx(tmp_path)
    ctx = ValidationContext(fascicolo=fascicolo, cliente=None, profile=profile, slots=repo.list_slots(fascicolo.id), fascicoli_manager=gf)
    assert run_validator("cliente_presente", ctx).status == ValidatorStatus.OK.value
    ctx.cliente = SimpleNamespace(codice_fiscale="ERRATO", email="")
    assert run_validator("cliente_cf_valido", ctx).status == ValidatorStatus.BLOCK.value
    assert run_validator("conferimento_firmato", ctx).status == ValidatorStatus.BLOCK.value
    assert run_validator("pagamento_acconto_registrato", ctx).status == ValidatorStatus.BLOCK.value
    repo.audit(fascicolo.id, "ECONOMIC_OVERRIDE", reason="urgenza cautelare")
    ctx.audit_events = repo.list_audit(fascicolo.id)
    assert run_validator("pagamento_acconto_registrato", ctx).status == ValidatorStatus.WARNING.value


def test_documenti_obbligatori_pdfa_firma_e_dimensione(tmp_path):
    gf, repo, fascicolo, profile, cliente = _ctx(tmp_path)
    ctx = ValidationContext(fascicolo=fascicolo, cliente=cliente, profile=profile, slots=repo.list_slots(fascicolo.id), fascicoli_manager=gf)
    assert run_validator("atto_principale_presente", ctx).status == ValidatorStatus.BLOCK.value
    assert run_validator("procura_presente", ctx).status == ValidatorStatus.BLOCK.value
    link_required_documents(gf, repo, fascicolo, procura=False, signed=False)
    fascicolo = gf.get(fascicolo.id)
    ctx = ValidationContext(fascicolo=fascicolo, cliente=cliente, profile=profile, slots=repo.list_slots(fascicolo.id), fascicoli_manager=gf)
    assert run_validator("firma_digitale_presente", ctx).status == ValidatorStatus.BLOCK.value
    assert run_validator("pdfa_valido", ctx).status == ValidatorStatus.OK.value
    bad = gf.aggiungi_documento(fascicolo.id, "atto_cifrato.pdf", TipoDocumento.ATTO_GIUDIZIARIO, encrypted_pdf_bytes(), firmato=True)
    repo.link_slot(fascicolo.id, "ATTO_PRINCIPALE", bad.id)
    fascicolo = gf.get(fascicolo.id)
    ctx = ValidationContext(fascicolo=fascicolo, cliente=cliente, profile=profile, slots=repo.list_slots(fascicolo.id), fascicoli_manager=gf)
    assert run_validator("pdf_non_cifrato", ctx).status == ValidatorStatus.BLOCK.value


def test_predeposito_restituisce_blocchi_warning_e_not_applicable(tmp_path):
    gf, repo, fascicolo, profile, cliente = _ctx(tmp_path)
    readiness = run_predeposit_check(repo, fascicolo=fascicolo, profile=profile, cliente=cliente, fascicoli_manager=gf)
    assert readiness["ready"] is False
    assert any(item.status == ValidatorStatus.BLOCK.value for item in readiness["blockers"])
    ctx = ValidationContext(fascicolo=fascicolo, cliente=cliente, profile=profile, slots=repo.list_slots(fascicolo.id), fascicoli_manager=gf)
    assert run_validator("marca_bollo_se_dovuta", ctx).status == ValidatorStatus.NOT_APPLICABLE.value


def test_predeposito_collega_documenti_solo_se_classificazione_certa(tmp_path):
    gf, repo, fascicolo, profile, cliente = _ctx(tmp_path)
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "Ricorso.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fascicolo.id,
        "Procura.PDF",
        TipoDocumento.PROCURA,
        pdfa_bytes(),
        firmato=True,
    )

    readiness = run_predeposit_check(repo, fascicolo=gf.get(fascicolo.id), profile=profile, cliente=cliente, fascicoli_manager=gf)
    slots = {slot.slot_key: slot for slot in readiness["slots"]}

    assert slots["ATTO_PRINCIPALE"].document_id == atto.id
    assert slots["PROCURA"].document_id == procura.id
    assert any(event.event_type == "DOCUMENT_SLOT_AUTO_LINKED" for event in repo.list_audit(fascicolo.id))


def test_predeposito_non_collega_documento_richiesto_come_ricorso_se_non_certo(tmp_path):
    gf, repo, fascicolo, profile, cliente = _ctx(tmp_path)
    gf.aggiungi_documento(
        fascicolo.id,
        "Documento richiesto - prova interesse ad agire Istanza GPS corretta.PDF",
        TipoDocumento.ALLEGATO,
        pdfa_bytes(),
        firmato=True,
    )

    readiness = run_predeposit_check(repo, fascicolo=gf.get(fascicolo.id), profile=profile, cliente=cliente, fascicoli_manager=gf)
    slots = {slot.slot_key: slot for slot in readiness["slots"]}

    assert slots["ATTO_PRINCIPALE"].document_id == ""
    assert any(item.status == ValidatorStatus.BLOCK.value for item in readiness["blockers"])


def test_profilo_deposito_non_scambia_contratto_per_atto_principale():
    profile = get_profile("PROC_LIC_IMP_001")
    assert profile is not None

    slots = {slot["slot_key"]: slot for slot in profile.required_slots}
    assert slots["ATTO_PRINCIPALE"]["label"] == "Atto principale"
    assert slots["ATTO_PRINCIPALE"]["type"] == SlotType.ATTO_PRINCIPALE.value
    assert slots["ATTO_PRINCIPALE"]["required"] is True
    assert slots["ATTO_PRINCIPALE"]["blocking"] is True

    contract_slots = [slot for slot in profile.required_slots if "Contratto di lavoro" in slot["label"]]
    assert contract_slots
    assert contract_slots[0]["type"] == SlotType.DOCUMENTO_PROVA.value
    assert contract_slots[0]["slot_key"] != "ATTO_PRINCIPALE"
