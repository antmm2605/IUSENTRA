from types import SimpleNamespace

from pct.fascicoli import TipoDocumento
from pct.practice_engine.deposit_readiness import run_predeposit_check
from pct.practice_engine.models import ValidatorStatus
from pct.practice_engine.validators import ValidationContext, run_validator

from tests.regia_test_utils import encrypted_pdf_bytes, link_required_documents, make_simple_fascicolo


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
