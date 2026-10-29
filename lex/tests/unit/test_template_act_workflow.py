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
    # Art. 166 c.p.c.: data prudenziale a giorni liberi, con la scadenza di legge a giorni pieni accanto.
    assert "28/01/2027" in payload["answer"]
    scadenza = payload["calculated_deadlines"]["scadenze"][0]
    assert scadenza["valore"] == "28/01/2027"
    assert "29/01/2027" in scadenza["spiegazione"]
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


def test_richieste_cortesi_usano_il_catalogo_prima_del_percorso_generale(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    for question in ["Vorrei preparare un ricorso per decreto ingiuntivo", "Puoi preparare una procura alle liti", "Potresti aiutarmi a compilare un atto di citazione"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) == {"ok": True}
        assert calls[-1]["studio_context"]["request_profile"]["source_mode"] == "internal"
    count = len(calls)
    for question in ["Come si prepara un ricorso per decreto ingiuntivo?", "Quali sono i termini per redigere una citazione?"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) is None
    assert len(calls) == count


def test_varianti_linguistiche_di_redazione_e_catalogo_reale(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    forms = ["scrivi {}", "scrivimi {}", "redigi {}", "preparami {}", "compila {}", "crea {}", "fammi una bozza {}", "vorrei scrivere {}", "voglio redigere {}", "puoi preparare {}", "potresti aiutarmi a compilare {}", "per favore scrivi {}"]
    acts = ["ricorso decreto ingiuntivo", "procura alle liti", "atto di citazione", "comparsa conclusionale", "ricorso tributario"]
    for form in forms:
        for act in acts:
            question = form.format(act)
            assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) == {"ok": True}, question
    assert len(calls) == 60
    for question in ["Come si scrive un ricorso?", "Quali termini ha il decreto ingiuntivo?", "Non scrivere un ricorso decreto ingiuntivo", "Scrivi una spiegazione del decreto ingiuntivo", "Puoi spiegarmi come preparare una citazione?", "Scrivi una poesia sul mare"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) is None, question
    assert len(calls) == 60


def test_richiesta_generica_non_sceglie_fascicoli_per_la_parola_ricorso():
    context = _base_context()
    context["fascicoli"] += [{"id": "altro-1", "titolo": "Alfa II ricorso contro Ente Beta", "oggetto": "decreto ingiuntivo"}, {"id": "altro-2", "titolo": "Gamma II ricorso contro Ente Beta"}]
    payload = run_template_act_workflow(_request("Vorrei preparare un ricorso per decreto ingiuntivo"), context, {"items": []})
    assert payload["act_context"]["client_id"] == ""
    assert payload["act_context"]["fascicolo_id"] == ""
    assert payload["act_context"]["parti"] == []
    assert "Alfa II" not in payload["answer"] and "Gamma II" not in payload["answer"]
    assert "Bianchi" not in str(payload["message_blocks"])


def test_soggetti_globali_non_entrano_nel_fascicolo_selezionato(monkeypatch):
    from pct import template_atti_lex_service as service

    monkeypatch.setattr(service, "_parti_collegate", lambda _: [])
    context = _base_context()
    context["parti"] += [{"id": "non-collegata", "nome_completo": "Ente Estraneo", "tipo": "TipoSoggetto.PERSONA_GIURIDICA"}]
    payload = service.run_template_act_workflow(_request("prepara procura alle liti", metadata={"active_context": {"client_id": "cli-rossi", "case_id": "fas-rossi"}}), context, {"items": []})
    assert "Ente Estraneo" not in str(payload["act_context"]["parti"])


def test_sinonimi_operativi_e_refusi_non_cambiano_i_fatti(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload
    from pct.template_atti_lex_service import search_template_models

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    forms = ["devo produrre {}", "devo predisporre {}", "vorrei stendere {}", "predisponi {}", "stendi {}", "genera {}", "produci {}", "mi serve {}", "mi occorre {}", "ho bisogno di {}", "scrvi {}", "redgi {}"]
    for form in forms:
        for act in ["ricorso decreto ingiuntivo", "procura alle liti", "atto di citazione", "comparsa conclusionale", "ricorso tributario"]:
            question = form.format(act)
            assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) == {"ok": True}, question
            assert calls[-1]["current_user_message"] == question
    for question in ["scrvi ricrso decrto ingiuntvo", "redgi atto di citazone"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) == {"ok": True}, question
    assert search_template_models("ricrso decrto ingiuntvo")[0].model_code == search_template_models("ricorso decreto ingiuntivo")[0].model_code
    for question in ["mi serve sapere il termine per il ricorso", "devo capire come si scrive una citazione", "non predisporre una procura"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) is None


def test_tipo_soggetto_collegato_mostrato_con_etichetta_leggibile(monkeypatch):
    from pct import template_atti_lex_service as service

    monkeypatch.setattr(service, "_parti_collegate", lambda _: [{"nome_completo": "Ente Collegato", "tipo": "TipoSoggetto.PERSONA_GIURIDICA"}])
    payload = service.run_template_act_workflow(_request("prepara procura alle liti", metadata={"active_context": {"client_id": "cli-rossi", "case_id": "fas-rossi"}}), _base_context(), {"items": []})
    card = next(b for b in payload["message_blocks"] if b.get("title") == "Ente Collegato")
    assert card["subtitle"] == "Persona giuridica"


def test_riferimento_rg_non_seleziona_tutte_le_pratiche_dello_stesso_anno():
    from pct.template_atti_lex_service import _matches_query

    assert _matches_query({"titolo": "Alfa", "rg_completo": "123/2026"}, "prepara ricorso per RG 123/2026")
    assert not _matches_query({"titolo": "Beta", "rg_completo": "999/2026"}, "prepara ricorso per RG 123/2026")
    assert not _matches_query({"titolo": "Alfa", "rg_completo": "123/2025"}, "prepara ricorso per RG 123/2026")


def test_nome_completo_prevale_su_indizi_generici_e_non_inverte_atto_richiesto():
    from pct.template_atti_lex_service import resolve_template_for_query

    for name, code in [
        ("Riscontro a Diffida", "STR_RISDIFF_001"),
        ("Revoca del mandato difensivo", "CIV_PROC_008"),
        ("Diffida ad adempiere", "STR_BLT_004"),
    ]:
        match = resolve_template_for_query("prepara " + name)
        assert match.model_code == code, (name, match.to_dict())
        assert not match.ambiguous, name


def test_due_atti_distinti_richiedono_scelta_e_il_codice_esplicito_resta_vincolante():
    from pct.template_atti_lex_service import resolve_template_for_query

    question = "prepara diffida ad adempiere e riscontro a diffida"
    match = resolve_template_for_query(question)
    assert match.ambiguous
    assert {"STR_RISDIFF_001", "STR_BLT_004"} <= {row["model_code"] for row in match.options}
    selected = resolve_template_for_query(question, {"model_code": "STR_BLT_004"})
    assert selected.model_code == "STR_BLT_004"
    assert not selected.ambiguous


def test_nome_identico_in_aree_diverse_mostra_entrambe_le_scelte():
    from pct.template_atti_lex_service import resolve_template_for_query, _azioni_varianti

    match = resolve_template_for_query("prepara istanza di rinvio")
    assert match.ambiguous
    actions = _azioni_varianti(match)
    by_code = {row["href"].rsplit("/", 1)[-1]: row["label"] for row in actions}
    assert "Civile" in by_code["CIV_SUC_005"]
    assert "Penale" in by_code["PEN_RINV_001"]


def test_nome_identico_di_un_alias_non_nasconde_il_modello_canonico():
    from pct.template_atti_lex_service import resolve_template_for_query, _azioni_varianti

    match = resolve_template_for_query("prepara lista testi")
    assert match.model_code == "PEN_LISTATESTI_001"
    assert not match.ambiguous
    assert any(row["href"].endswith("/PEN_BLT_008") for row in _azioni_varianti(match))
    assert resolve_template_for_query("prepara lista testi", {"model_code": "PEN_BLT_008"}).model_code == "PEN_BLT_008"


def test_articoli_e_preposizioni_non_invertono_il_significato_dell_atto():
    from pct.template_atti_lex_service import resolve_template_for_query

    for question, code in [
        ("scrivi riscontro diffida", "STR_RISDIFF_001"),
        ("prepara revoca mandato difensivo", "CIV_PROC_008"),
        ("prepara diffida adempiere", "STR_BLT_004"),
        ("crea una diffida e messa in mora", "STR_DIFF_001"),
        ("redigi opposizione decreto ingiuntivo", "CIV_OPPDI_001"),
    ]:
        match = resolve_template_for_query(question)
        assert match.model_code == code, (question, match.to_dict())
        assert not match.ambiguous, question


def test_parere_con_titolo_del_catalogo_non_e_confuso_con_domanda_informativa(monkeypatch):
    from lex import http_bounded_bridge
    from lex.http_template_bridge import template_http_payload

    calls = []
    monkeypatch.setattr(http_bounded_bridge, "build_bounded_http_payload", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    question = "prepara un parere su operazione straordinaria"
    assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) == {"ok": True}
    assert calls[-1]["current_user_message"] == question
    for question in ["mi serve sapere del parere su operazione straordinaria", "scrivi una spiegazione del parere su operazione straordinaria", "prepara un parere su un argomento non censito"]:
        assert template_http_payload(user=object(), studio=object(), data={}, question=question, attachments=[]) is None
    assert len(calls) == 1


def test_ricerca_include_varianti_compilabili_del_catalogo_esteso():
    from pct.template_atti_lex_service import resolve_template_for_query, _azioni_varianti
    from pct.compilatore_atti import get_modello

    for name, code in [
        ("Ricorso monitorio per fatture commerciali", "MON_003"),
        ("Atto di citazione con chiamata del terzo", "CIV_ORD_002"),
        ("Ricorso ex art. 700 c.p.c.", "CAU_001"),
    ]:
        match = resolve_template_for_query("prepara " + name)
        assert match.model_code == code or any(row["href"].endswith("/" + code) for row in _azioni_varianti(match))
        assert get_modello(code) is not None
    assert resolve_template_for_query("scrivi risposta alla diffida").model_code == "STR_RISDIFF_001"
    assert resolve_template_for_query("prepara replica a diffida").model_code == "STR_RISDIFF_001"


def test_istanza_specifica_non_propone_varianti_di_altre_istanze():
    payload = run_template_act_workflow(_request("prepara istanza di ricerca telematica dei beni"), {}, {"items": []})
    block = next(row for row in payload["message_blocks"] if row.get("title") == "Scegli il modello da produrre")
    assert len(block["items"]) == 1
    assert block["items"][0]["href"].endswith("/ESE_013")
    assert "rinvio" not in str(block).lower()
    assert "anticipazione" not in str(block).lower()
    assert payload["created_document"] == {}
    assert payload["explicit_create"] is False
