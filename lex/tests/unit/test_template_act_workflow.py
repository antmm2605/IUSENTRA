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
