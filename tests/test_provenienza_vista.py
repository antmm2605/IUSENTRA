"""La vista «Provenienza» del fascicolo e l'invio delle uscite AI nella catena probatoria."""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, g

from audit.integrations import emit_ai_output_recorded, emit_ai_output_reviewed
from audit.schemas import AuditKind
from pct.provenienza_ai import Provenienza, cancello_ancoraggio
from tests.audit_test_utils import make_service


def _provenienza(**campi) -> dict:
    esito = cancello_ancoraggio({"etichetta": "Decreto ingiuntivo"}, "DECRETO INGIUNTIVO N. 12/2026")
    base = dict(azione="catalogo.seconda_lettura", modello="maternion/spark-x2.5:4b", versione_regole="v", sha256_input="a" * 64,
                citazione="DECRETO INGIUNTIVO N. 12/2026", parametri={"etichetta": "Decreto ingiuntivo"}, cancello=esito.to_dict())
    base.update(campi)
    return Provenienza(**base).to_dict()


def test_nuovi_tipi_di_evento_probatorio():
    assert AuditKind("AI_OUTPUT_RECORDED") is AuditKind.AI_OUTPUT_RECORDED
    assert AuditKind("AI_OUTPUT_REVIEWED") is AuditKind.AI_OUTPUT_REVIEWED


def test_uscita_e_revisione_entrano_nella_catena_una_volta(tmp_path):
    service, _public = make_service()
    app = Flask(__name__)
    app.config.update(AUDIT_ENABLED=True, AUDIT_ENV="development")
    app.extensions["legal_audit_service"] = service
    provenienza = _provenienza()
    with app.test_request_context("/"):
        g.tenant = SimpleNamespace(slug="studio-a")
        g.utente_corrente = SimpleNamespace(id="u1", nome_completo="Avv. Rossi")
        emit_ai_output_recorded(fascicolo_id="F1", provenienza=provenienza, oggetto="DOC-1")
        emit_ai_output_recorded(fascicolo_id="F1", provenienza=provenienza, oggetto="DOC-1")
        emit_ai_output_reviewed(fascicolo_id="F1", sigillo=provenienza["sigillo"], esito="confermata", oggetto="DOC-1", riferimento="t1")
    righe = service.repository.list_events(tenant_id="studio-a", fascicolo_id="F1")
    assert [r["kind"] for r in righe] == ["AI_OUTPUT_RECORDED", "AI_OUTPUT_REVIEWED"]
    assert righe[0]["idempotency_key"] == f"AI_OUTPUT_RECORDED:{provenienza['sigillo']}"
    assert service.verify_chain("studio-a", "F1").ok


def test_payload_probatorio_senza_testo_letto():
    from audit.integrations import _payload_provenienza

    payload = _payload_provenienza(_provenienza())
    assert "citazione" not in payload and "parametri" not in payload
    assert payload["cancello_ammesso"] is True and payload["sigillo"]


def test_vista_elenca_catalogo_ed_editor(monkeypatch):
    from web.services import provenienza_runtime as runtime

    confermata = _provenienza()
    da_approvare = _provenienza(creato_il="2026-09-27T08:00:00+00:00", sha256_input="b" * 64)
    manomessa = {**_provenienza(creato_il="2026-09-25T08:00:00+00:00"), "modello": "altro"}
    assegnazioni = [
        SimpleNamespace(document_id="D1", document_label="Decreto ingiuntivo", status="confirmed",
                        metadata={"filename": "di.pdf", "lex_lettura": {"etichetta": "Decreto ingiuntivo", "esito": "scelta", "provenienza": confermata}}),
        SimpleNamespace(document_id="D2", document_label="Procura alle liti", status="review_required",
                        metadata={"lex_lettura": {"etichetta": "Procura alle liti", "esito": "scelta", "provenienza": da_approvare}}),
        SimpleNamespace(document_id="D3", document_label="Memoria", status="confirmed",
                        metadata={"lex_lettura": {"etichetta": "Ricorso", "esito": "scelta", "provenienza": manomessa}}),
        SimpleNamespace(document_id="D4", document_label="Sentenza", status="proposed", metadata={}),
    ]

    class Repo:
        def list_catalog_assignments(self, tenant, fid):
            assert fid == "F1"
            return assegnazioni

    monkeypatch.setattr("web.services.document_intelligence_runtime.build_document_ai_service", lambda: SimpleNamespace(repository=Repo()))
    monkeypatch.setattr("web.services.document_intelligence_runtime.document_ai_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_dall_editor", lambda tenant, fid: [])
    fascicolo = SimpleNamespace(id="F1", documenti=[SimpleNamespace(id="D1", nome="Decreto ingiuntivo.pdf"), SimpleNamespace(id="D2", nome="procura.pdf")])
    app = Flask(__name__)
    with app.app_context():
        vista = runtime.provenienze_fascicolo(fascicolo)
    voci = vista["voci"]
    assert [v["oggettoId"] for v in voci] == ["D2", "D1", "D3"]  # dalla più recente
    per_id = {v["oggettoId"]: v for v in voci}
    assert per_id["D1"]["approvazione"] == "confermata" and per_id["D1"]["oggetto"] == "Decreto ingiuntivo.pdf"
    assert per_id["D2"]["approvazione"] == "da_approvare"
    assert per_id["D3"]["approvazione"] == "corretta" and per_id["D3"]["integro"] is False
    assert per_id["D1"]["cancello"]["stato"] == "ammesso" and per_id["D1"]["modelloEtichetta"] == "spark-x2.5:4b"
    assert vista["riepilogo"] == {"totale": 3, "daApprovare": 1, "bloccate": 0, "nonIntegre": 1, "modelli": ["altro", "spark-x2.5:4b"]}
    assert vista["catena"]["attiva"] is False


def test_eventi_dell_editor_per_la_vista(tmp_path):
    from pct.editor_ai.audit import record_editor_ai_event
    from pct.editor_ai.repository import EditorAIRepository

    repository = EditorAIRepository.from_fascicoli_db(str(tmp_path / "fascicoli.json"))
    provenienza = Provenienza("editor.bozza", "ollama:qwen3:4b", "tpl", "c" * 64).to_dict()
    record_editor_ai_event(repository, "editor_ai.generation.completed", tenant_id="t", fascicolo_id="F1", user_context={"user_id": "u"},
                           atto_ai_id="A1", payload={"provenienza": provenienza})
    record_editor_ai_event(repository, "editor_ai.readback.completed", tenant_id="t", fascicolo_id="F1", user_context={"user_id": "u"}, atto_ai_id="A1")
    eventi = repository.list_audit_events("t", "F1", event_types=("editor_ai.generation.completed",))
    assert len(eventi) == 1 and eventi[0]["payload"]["provenienza"]["sigillo"] == provenienza["sigillo"]
