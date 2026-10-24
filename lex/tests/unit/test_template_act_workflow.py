from __future__ import annotations

from lex.contracts import LexRequest
from pct.studio_timbro import StudioTimbro
from pct.template_atti_lex_service import create_editor_draft, run_template_act_workflow


def _stamp_payload():
    return StudioTimbro.from_payload({"studio_nome": "Studio Verdi", "professionista_nome": "Avv. Verdi"}).to_payload()


def _base_context():
    cliente = {
        "id": "cli-rossi",
        "nome_completo": "Mario Rossi",
        "codice_fiscale": "RSSMRA80A01H501U",
        "email": "mario.rossi@example.test",
    }
    fascicolo = {
        "id": "fas-rossi",
        "titolo": "Rossi contro Bianchi",
        "id_cliente": "cli-rossi",
        "controparte": "Bianchi",
        "tribunale": "Tribunale di Roma",
        "oggetto": "Recupero credito",
        "note": "Inadempimento contrattuale documentato.",
        "documenti": [{"id": "doc-1", "nome": "contratto.pdf"}],
    }
    return {
        "clienti": [cliente],
        "fascicoli": [fascicolo],
        "parti": [{"id": "parte-1", "nome_completo": "Bianchi", "ruolo": "controparte"}],
        "utenti": [{"id": "avv-1", "username": "avv.verdi", "nome_completo": "Avv. Verdi"}],
        "config": {
            "STUDIO_AVVOCATO": "Avv. Verdi",
            "STUDIO_NOME": "Studio Verdi",
            "PCT_STUDIO_PEC": "studio.verdi@pec.test",
            "STUDIO_CF": "VRDPLA70A01H501X",
        },
    }


def _request(query: str, *, metadata: dict | None = None, intent: str = "template_act_prefill") -> LexRequest:
    return LexRequest(
        tenant_id="tenant-1",
        user_id="utente-1",
        session_id="sessione-1",
        query=query,
        intent=intent,
        metadata=metadata or {},
    )


def test_template_workflow_precompila_cliente_e_controparte_da_fascicolo():
    payload = run_template_act_workflow(
        _request("crea atto di citazione per Mario Rossi contro Bianchi"),
        _base_context(),
        {"items": []},
    )

    assert payload["template"]["model_code"] == "CIV_CIT_001"
    assert payload["act_context"]["client_id"] == "cli-rossi"
    assert payload["act_context"]["fascicolo_id"] == "fas-rossi"
    assert "Mario Rossi" in payload["prefill"]["payload"]["client_or_sender"]
    assert "Bianchi" in payload["prefill"]["payload"]["counterparty_or_recipient"]
    assert payload["lex_actions"]


def test_template_workflow_segnala_dati_mancanti_senza_inventare():
    payload = run_template_act_workflow(
        _request("usa il template diffida per il fascicolo Rossi"),
        _base_context(),
        {"items": []},
    )

    assert payload["template"]["model_code"] == "STR_DIFF_001"
    assert payload["missing_fields"]
    assert payload["created_document"] == {}
    assert "Nessuna bozza" in payload["answer"]


def test_template_workflow_riporta_scadenza_del_calcolatore_senza_creare_atto(monkeypatch):
    from pct.registro_letture.fatti_repository import Fatto
    from web.services import archivio_letture_runtime

    calls = []

    def fatti(fascicolo):
        calls.append(fascicolo.id)
        return [Fatto(categoria="data", campo="udienza", valore="2027-04-09", verifica="verificata")]

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", fatti)
    payload = run_template_act_workflow(
        _request("Prepara la comparsa di costituzione", metadata={
            "active_context": {"model_code": "CIV_COM_001", "case_id": "fas-rossi"},
        }), _base_context(), {"items": []},
    )
    assert calls == ["fas-rossi"]
    assert "29/01/2027" in payload["answer"]
    assert payload["calculated_deadlines"]["scadenze"][0]["valore"] == "29/01/2027"
    assert payload["created_document"] == {}


def test_template_workflow_permesso_negato_non_legge_scadenze(monkeypatch):
    from web.services import archivio_letture_runtime

    def forbidden(*args, **kwargs):
        raise AssertionError("La richiesta non autorizzata non deve leggere fatti")

    monkeypatch.setattr(archivio_letture_runtime, "fatti_fascicolo", forbidden)
    payload = run_template_act_workflow(
        _request("Prepara la comparsa", metadata={"active_context": {
            "model_code": "CIV_COM_001", "case_id": "fas-rossi", "permissions_scope": ["nessun_accesso"],
        }}), _base_context(), {"items": []},
    )
    assert payload["act_context"]["forbidden"]
    assert payload["calculated_deadlines"] == {}


def test_template_payload_json_non_espone_configurazione_interna():
    import json
    from datetime import timedelta

    context = _base_context()
    context["config"].update(SECRET_KEY="valore-riservato", PERMANENT_SESSION_LIFETIME=timedelta(days=1))
    payload = run_template_act_workflow(_request("usa template diffida"), context, {"items": []})
    encoded = json.dumps(payload)
    assert "valore-riservato" not in encoded and "PERMANENT_SESSION_LIFETIME" not in encoded
    assert payload["act_context"]["config"]["STUDIO_NOME"] == "Studio Verdi"


def test_template_workflow_non_crea_documento_senza_conferma():
    metadata = {
        "template_payload": {
            "sender": "Mario Rossi",
            "recipient": "Bianchi",
            "breach_description": "Inadempimento contrattuale documentato.",
            "specific_request": "Pagamento delle somme dovute.",
            "deadline_assigned": "2026-05-30",
            "final_warning": "In difetto si agirà senza ulteriore avviso.",
            "_studio_timbro": _stamp_payload(),
        }
    }
    payload = run_template_act_workflow(
        _request("crea diffida per Mario Rossi contro Bianchi", metadata=metadata),
        _base_context(),
        {"items": []},
    )

    create_actions = [action for action in payload["lex_actions"] if action["id"] in {"create_final_draft", "create_working_draft"}]
    assert create_actions
    assert create_actions[0]["requires_confirmation"] is True
    assert payload["created_document"] == {}


def test_create_editor_draft_crea_documento_quando_confermato_con_payload_valido():
    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {
            "ok": True,
            "document_id": "doc-editor-1",
            "open_url": "/fascicoli/fas-rossi/documenti/doc-editor-1/editor",
            "filename": "atto.html",
        }

    result = create_editor_draft(
        "STR_DIFF_001",
        {
            "case_id": "fas-rossi",
            "title": "Diffida",
            "sender": "Mario Rossi",
            "recipient": "Bianchi",
            "breach_description": "Inadempimento contrattuale documentato.",
            "specific_request": "Pagamento delle somme dovute.",
            "deadline_assigned": "2026-05-30",
            "final_warning": "In difetto si agirà senza ulteriore avviso.",
            "attachments_list": "Contratto e solleciti.",
            "_studio_timbro": _stamp_payload(),
        },
        "fas-rossi",
        "utente-1",
        rendered_text="Testo della diffida.",
        document_writer=writer,
    )

    assert result.ok is True
    assert result.document_id == "doc-editor-1"
    assert written["model_code"] == "STR_DIFF_001"


def test_template_workflow_crea_documento_editor_quando_confermato():
    written = {}

    def writer(**kwargs):
        written.update(kwargs)
        return {
            "ok": True,
            "document_id": "doc-editor-2",
            "open_url": "/fascicoli/fas-rossi/documenti/doc-editor-2/editor",
            "filename": "diffida.html",
        }

    metadata = {
        "active_context": {"model_code": "STR_DIFF_001", "case_id": "fas-rossi", "client_id": "cli-rossi"},
        "template_payload": {
            "facts": "Inadempimento contrattuale documentato.",
            "requests_or_conclusions": "Pagamento delle somme dovute.",
            "place": "Roma",
            "attachments_list": "Contratto e solleciti.",
            "breach_description": "Mancato pagamento nei termini concordati.",
            "specific_request": "Pagamento entro il termine assegnato.",
            "deadline_assigned": "2026-05-30",
            "_studio_timbro": _stamp_payload(),
            "final_warning": "In difetto si procederà senza ulteriore avviso.",
        },
    }

    context = _base_context()
    context["template_act_document_writer"] = writer
    payload = run_template_act_workflow(
        _request("crea ora la bozza nell'editor", metadata=metadata, intent="template_act_create"),
        context,
        {"items": []},
    )

    assert payload["explicit_create"] is True
    assert payload["created_document"]["document_id"] == "doc-editor-2"
    assert payload["created_document"]["editor_url"].endswith("/editor")
    assert written["model_code"] == "STR_DIFF_001"


def test_template_workflow_permesso_mancante_non_espone_fascicolo():
    metadata = {"active_context": {"permissions_scope": ["clienti.leggi"]}}
    payload = run_template_act_workflow(
        _request("crea atto di citazione per Mario Rossi contro Bianchi", metadata=metadata),
        _base_context(),
        {"items": []},
    )

    assert payload["act_context"]["forbidden"] is True
    assert payload["act_context"]["fascicolo"] == {}
    assert payload["created_document"] == {}


def test_template_workflow_cliente_ambiguo_propone_opzioni():
    context = _base_context()
    context["clienti"] = [
        {"id": "cli-1", "nome_completo": "Mario Rossi"},
        {"id": "cli-2", "nome_completo": "Marco Rossi"},
    ]
    context["fascicoli"] = []

    payload = run_template_act_workflow(
        _request("crea diffida per Rossi"),
        context,
        {"items": []},
    )

    assert payload["act_context"]["client_options"]
    assert payload["created_document"] == {}
    assert "non scelgo" in payload["answer"]


def test_template_lookup_decreto_ingiuntivo_non_crea_bozza():
    payload = run_template_act_workflow(
        _request("quali atti posso creare per decreto ingiuntivo?"),
        _base_context(),
        {"items": []},
    )

    assert payload["lookup_only"] is True
    assert "CIV_RDI_001" in payload["answer"]
    assert payload["created_document"] == {}


def test_template_http_command_preserva_contesto_e_confini(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    base = dict(user=object(), studio=object(), question="Prepara una diffida", attachments=[])
    data = {"active_context": {"model_code": "STR_DIFF_001", "case_id": "controlled"}}
    assert template_http_payload(**base, data=data) == {"ok": True}
    assert calls[0]["studio_context"]["active_context"] == data["active_context"]
    assert calls[0]["attachments"] == []
    assert len(calls) == 1
    assert template_http_payload(**(base | {"attachments": ["controlled"]}), data=data) is None
    assert template_http_payload(**(base | {"question": "Quali norme regolano una diffida?"}), data=data) is None
    assert template_http_payload(**(base | {"question": "Prepara il caffè"}), data={}) is None
    assert len(calls) == 1


def test_procura_senza_contesto_chiede_cliente_prima_di_valutare_una_bozza(monkeypatch):
    from pct import template_atti_lex_service as service
    from pct import template_normative_compliance
    def forbidden(*args, **kwargs):
        raise AssertionError("Una bozza inesistente non deve essere precompilata o certificata")
    monkeypatch.setattr(service,"build_prefill",forbidden)
    monkeypatch.setattr(template_normative_compliance,"analyze_template_compliance",forbidden)
    payload=service.run_template_act_workflow(_request("procura alle liti"),{}, {"items":[]})
    assert "Per quale cliente" in payload["answer"]
    assert "case_id" not in payload["answer"] and "affidabilità" not in payload["answer"]
    assert payload["prefill"]=={} and payload["compliance"]=={} and payload["created_document"]=={}
    assert payload["lex_actions"][0]["id"]=="select_drafting_context"
    assert not any(action["kind"]=="mutation" for action in payload["lex_actions"])


def test_filtri_catalogo_privilegiano_identita_su_allegati_comuni():
    from pct.template_atti_lex_service import search_template_models
    for richiesta, expected in [("Procura alle liti","CIV_PROC_001"),("Atto di citazione","CIV_CIT_001"),("Diffida e messa in mora","STR_DIFF_001")]:
        risultati=search_template_models(richiesta)
        assert risultati and risultati[0].model_code==expected
    procure=search_template_models("procura alle liti",limit=20)
    assert not any(r.model_code.startswith("AMM_") for r in procure)
    assert search_template_models("procura alle liti Modello catalogo atti: Procura alle liti. Campi richiesti: facts, area.")[0].model_code=="CIV_PROC_001"
    assert search_template_models("procura alle liti",model_code="CIV_PROC_003")[0].model_code=="CIV_PROC_003"


def test_varianti_selezionabili_riusano_modelli_reali_e_non_creano_documenti():
    payload=run_template_act_workflow(_request("procura alle liti"),{}, {"items":[]})
    scelta=next(b for b in payload["message_blocks"] if b.get("title")=="Scegli il modello da produrre")
    assert len(scelta["items"])>=3
    assert any(a["label"]=="Procura generale alle liti" for a in scelta["items"])
    assert all(a["kind"]=="open" and a["href"].startswith("/template-atti/compila/CIV_PROC_") for a in scelta["items"])
    assert payload["created_document"]=={} and payload["compliance"]=={}


def test_evidenza_generica_non_sostituisce_modello_scelto():
    from lex.contracts import EvidenceItem
    item=EvidenceItem(source_type="template_atto",source_id="CIV_PROCBASE_001",title="Generico",content="Procura",score=0.9,metadata={"model_code":"CIV_PROCBASE_001"})
    payload=run_template_act_workflow(_request("procura alle liti",metadata={"model_code":"CIV_PROC_003"}),{}, {"items":[item]})
    assert payload["template"]["model_code"]=="CIV_PROC_003"


def test_catalogo_non_mostra_pec_o_altre_citazioni_non_usate_come_fonti():
    from types import SimpleNamespace
    from lex.contracts import Citation, ProviderDraft
    from lex.formatting.answer_builder import AnswerBuilder
    request=_request("procura alle liti")
    payload=run_template_act_workflow(request,{}, {"items":[]})
    draft=ProviderDraft(text=payload["answer"],metadata={"template_act":payload,"provider":"deterministic"})
    evidence={"items":[],"citations":[Citation(source_type="anagrafica",source_id="smtp-config",title="PEC e canali email",excerpt="smtp.example:465")]}
    response=AnswerBuilder()._build_template_act_response(request=request,draft=draft,verdict=SimpleNamespace(warnings=[],risk_level="medium"),evidence=evidence,confidence=0.5)
    assert response.citations==[]
    assert all("PEC" not in row["title"] for row in response.metadata["source_rows"])
    assert "smtp.example" not in response.answer


def test_nome_esatto_rispettato_in_tutte_le_aree_del_catalogo():
    from pct.compilatore_atti import elenco_modelli
    from pct.template_atti_lex_service import search_template_models, normalize_text
    campione={}
    for model in elenco_modelli():
        if model.get("name") and model.get("area"):
            campione.setdefault(model["area"],model["name"])
    assert len(campione)>=5
    for area,title in campione.items():
        risultati=search_template_models(title)
        assert risultati and normalize_text(risultati[0].name)==normalize_text(title), (area,title,[m.name for m in risultati[:3]])


def test_modello_ambiguo_non_viene_precompilato_prima_della_scelta(monkeypatch):
    from pct import template_atti_lex_service as service
    original=service.resolve_template_for_query
    def ambiguous(query,context):
        match=original("atto di citazione",context)
        match.ambiguous=True
        match.options=[{"model_code":"CIV_CIT_001","name":"Atto di citazione"},{"model_code":"CIV_RDI_001","name":"Ricorso per decreto ingiuntivo"}]
        return match
    monkeypatch.setattr(service,"resolve_template_for_query",ambiguous)
    def forbidden(*args,**kwargs):raise AssertionError("La scelta del modello spetta all’avvocato")
    monkeypatch.setattr(service,"build_prefill",forbidden)
    payload=service.run_template_act_workflow(_request("prepara un atto per Mario Rossi"),_base_context(),{"items":[]})
    assert "Scegli" in payload["answer"] and payload["prefill"]=={}
    assert not any(a["kind"]=="mutation" for a in payload["lex_actions"])
