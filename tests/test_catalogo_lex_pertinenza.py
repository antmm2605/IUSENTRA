"""La citazione deve dimostrare la natura proposta, non soltanto esistere."""
import pytest
from tests.test_fascicoli_rinomina_sql_mirata import rename_case as rename_case
from tests.test_catalogo_lex import _risposta
from pct.document_intelligence.catalog_lex import leggi_con_lex


def test_testo_tecnico_non_diventa_accertamento_con_adesione():
    testo = (
        "Collaudo tecnico delle impronte SQL documentali.\n"
        "Fonte sintetica senza dati personali: acquisizione e consultazione restano distinte.\n"
        "Il lettore deve conservare il testo originale e la sua impronta."
    )
    esito = leggi_con_lex(testo, genera=_risposta(
        "Accertamento con adesione", "Collaudo tecnico delle impronte SQL documentali",
        "atto di verifica e adesione",
    ))
    assert esito.stato == "non_verificata"


def test_atto_tributario_reale_conserva_la_proposta_pertinente():
    testo = (
        "ISTANZA DI ACCERTAMENTO CON ADESIONE\n"
        "All'Agenzia delle Entrate. Il contribuente chiede il contraddittorio "
        "sull'imposta oggetto dell'avviso."
    )
    esito = leggi_con_lex(testo, genera=_risposta(
        "Accertamento con adesione", "Il contribuente chiede il contraddittorio",
    ))
    assert esito.stato == "scelta"


@pytest.mark.parametrize("concurrent", ["none", "manual", "source", "catalog"])
def test_la_lettura_lenta_non_sovrascrive_la_conferma_manuale(rename_case, tmp_path, monkeypatch, concurrent):
    from dataclasses import replace
    from types import SimpleNamespace
    from pct.document_intelligence import DocumentAIRepository
    from tests.test_catalogo_lex import NOTE, _assegnazione
    import web.helpers
    import web.services.document_intelligence_runtime as runtime
    from web.services.catalogo_lex_runtime import seconda_lettura_studio_corrente

    _, backend, _, _ = rename_case
    from tests.test_fascicoli_rinomina_sql_mirata import commit
    backend.conn.execute("CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)")
    commit(backend)
    repo = DocumentAIRepository.from_fascicoli_db(tmp_path / "studio.db", structured_db=backend)
    assignment = replace(_assegnazione(repo, tmp_path, NOTE), status="review_required", confidence=60)
    repo.save_catalog_assignment(assignment)
    monkeypatch.setattr(runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=repo))
    monkeypatch.setattr(runtime, "document_ai_tenant_id", lambda: "studio-test")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: {"FASC-LEX": SimpleNamespace(id="FASC-LEX")})
    def genera(domanda, schema):
        corrente = repo.get_catalog_assignment("studio-test", "FASC-LEX", "DOC-LEX")
        if concurrent == "manual":
            repo.save_catalog_assignment(replace(corrente, status="confirmed", source_state="manual_override",
                                                updated_at="2030-01-01T00:00:00Z", updated_by="avvocato"))
        elif concurrent == "catalog":
            repo.save_catalog_assignment(replace(corrente, document_label="Decreto di fissazione udienza",
                                                status="proposed", confidence=96, reason="Nuova decisione nello stesso secondo"))
        elif concurrent == "source":
            repo.mark_status("studio-test", "FASC-LEX", assignment.document_ai_id, "processing")
        return _risposta("Note scritte ex art. 127-ter c.p.c.", "Il ricorrente rassegna le seguenti conclusioni")(domanda, schema)
    seconda_lettura_studio_corrente(genera=genera, modello="qwen3:4b")
    salvata = repo.get_catalog_assignment("studio-test", "FASC-LEX", "DOC-LEX")
    if concurrent == "manual":
        assert salvata.status == "confirmed"
        assert salvata.source_state == "manual_override"
        assert salvata.updated_by == "avvocato"
    elif concurrent == "catalog":
        assert salvata.document_label == "Decreto di fissazione udienza"
        assert salvata.confidence == 96
        assert salvata.updated_at == assignment.updated_at
    elif concurrent == "source":
        assert salvata.status == "review_required" and salvata.confidence == 60
        assert repo.get_document("studio-test", "FASC-LEX", assignment.document_ai_id).status == "processing"
    else:
        assert salvata.status == "proposed" and salvata.confidence == 80
    eventi = backend.conn.execute("SELECT event_type FROM fascicolo_documenti_ai_audit WHERE tenant_id = ? AND fascicolo_id = ?", ("studio-test", "FASC-LEX")).fetchall()
    atteso = "document_catalog.lex_second_reading" if concurrent == "none" else "document_catalog.lex_discarded_concurrent"
    assert any(event["event_type"] == atteso for event in eventi)


def test_ripresa_puntuale_legge_solo_il_documento_scelto(rename_case, tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    from dataclasses import replace
    from pct.document_intelligence import DocumentAIRepository
    from pct.registro_letture import Oggetto
    from tests.test_catalogo_lex import NOTE, _assegnazione
    from tests.test_fascicoli_rinomina_sql_mirata import commit
    from tests.test_fascicolo_document_catalog_pipeline import _ready_source
    from web.services.catalogo_archivio_runtime import prepara_catalogo

    _, backend, _, _ = rename_case
    backend.conn.execute("CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)")
    commit(backend)
    repo = DocumentAIRepository.from_fascicoli_db(tmp_path / "studio.db", structured_db=backend)
    assignment = _assegnazione(repo, tmp_path, NOTE)
    _ready_source(repo, tenant_id="studio-test", fascicolo_id="FASC-LEX", document_id="ALTRO",
                  filename="altro.pdf", sha256="8" * 64, text="Non deve essere letto")
    fascicolo = NS(id="FASC-LEX", documenti=[NS(id="DOC-LEX", nome="documento.pdf"), NS(id="ALTRO", nome="altro.pdf")])
    oggetti = [Oggetto(tipo="documento", oggetto_id=doc, presente=True, sha256=sha)
               for doc, sha in [("DOC-LEX", "7" * 64), ("ALTRO", "8" * 64)]]
    calls = []
    original = repo.get_extracted_text
    def leggi(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(repo, "get_extracted_text", leggi)
    sources, texts, report = prepara_catalogo(fascicolo, oggetti, repo, "studio-test",
                                            document_ids={"DOC-LEX"}, retry=True)
    assert [s.source_id for s in sources] == ["DOC-LEX"]
    assert texts == {"DOC-LEX": NOTE}
    assert len(calls) == 1
    assert report["file_reads"] == 0
    repo.save_catalog_assignment(replace(assignment, status="confirmed", source_state="manual_override"))
    calls.clear()
    sources, texts, report = prepara_catalogo(fascicolo, oggetti, repo, "studio-test",
                                            document_ids={"DOC-LEX"}, retry=True)
    assert sources == [] and texts == {} and calls == []
    assert report["manual_or_confirmed_preserved"] == 1


def test_api_ripresa_puntuale_non_riattiva_indice_o_ocr(monkeypatch):
    from flask import Flask, g
    from types import SimpleNamespace as NS
    from web.blueprints import api_v1_documenti_ai as api
    import web.helpers
    import web.services.document_intelligence_runtime as runtime
    import web.services.catalogo_archivio_runtime as archivio
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(api.api_v1_documenti_ai)
    @app.before_request
    def auth():
        g.utente_corrente = NS(id='avvocato-test', ha_permesso=lambda permesso: permesso == 'fascicoli.scrivi')
    monkeypatch.setattr(runtime, 'assert_document_ai_fascicolo_current_tenant', lambda fid: None)
    monkeypatch.setattr(web.helpers, 'get_fascicoli', lambda: {'F1': NS(id='F1', documenti=[NS(id='D1')])})
    calls = []
    def riprendi(fascicolo, **kwargs):
        calls.append((fascicolo.id, kwargs))
        return {'run': {'processed': 1, 'errors': []}}
    monkeypatch.setattr(archivio, 'aggiorna_catalogo_da_archivio', riprendi)
    def vietato(*args, **kwargs):
        raise AssertionError('Il comando sulla categoria non deve avviare indicizzazione od OCR')
    monkeypatch.setattr(api, 'build_lex_indexing_summary_payload', vietato)
    def catalog(fid, **kwargs):
        assert fid == 'F1' and kwargs == {'process': False}
        return {'documents': [], 'run': {'processed': 0}}
    monkeypatch.setattr(api, 'build_document_catalog_payload', catalog)
    with app.test_client() as client:
        response = client.post('/api/v1/ui/fascicoli/F1/catalogazione-documentale/aggiorna',
                               json={'documento_id': 'D1'})
        assert response.status_code == 200
        assert response.json['run']['processed'] == 1
        assert calls == [('F1', {'document_ids': {'D1'}, 'retry': True, 'actor': 'avvocato-test'})]
        calls.clear()
        response = client.post('/api/v1/ui/fascicoli/F1/catalogazione-documentale/aggiorna',
                               json={'documento_id': 'ALTRO'})
        assert response.status_code == 404 and calls == []
        monkeypatch.setattr(api, '_user_context', lambda: {'user': NS(ha_permesso=lambda permesso: False)})
        response = client.post('/api/v1/ui/fascicoli/F1/catalogazione-documentale/aggiorna',
                               json={'documento_id': 'D1'})
        assert response.status_code == 403 and calls == []
        monkeypatch.setattr(api, '_user_context', lambda: {'user': NS(ha_permesso=lambda permesso: True)})
        for motivo, codice in [('waiting_for_text', 'catalog_source_not_ready'),
                              ('manual_or_confirmed_preserved', 'catalog_decision_preserved')]:
            monkeypatch.setattr(archivio, 'aggiorna_catalogo_da_archivio', lambda *args, **kwargs: {motivo: 1})
            response = client.post('/api/v1/ui/fascicoli/F1/catalogazione-documentale/aggiorna',
                                   json={'documento_id': 'D1'})
            assert response.status_code == 409 and response.json['code'] == codice



def test_ripresa_conserva_la_proposta_precedente_nellaudit(rename_case, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace as NS
    from pct.document_intelligence import DocumentAIRepository
    from pct.document_intelligence.catalog_lex import EsitoLex, applica_esito
    from pct.registro_letture import Oggetto
    from tests.test_catalogo_lex import _assegnazione, _voce
    from tests.test_fascicoli_rinomina_sql_mirata import commit
    import web.services.document_intelligence_runtime as runtime
    import web.services.registro_letture_runtime as registro_runtime
    from web.services.catalogo_archivio_runtime import aggiorna_catalogo_da_archivio
    _, backend, _, _ = rename_case
    backend.conn.execute("CREATE TABLE _meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)")
    commit(backend)
    repo = DocumentAIRepository.from_fascicoli_db(tmp_path / "studio.db", structured_db=backend)
    testo = "Collaudo tecnico delle impronte SQL documentali. Fonte sintetica senza dati personali."
    assignment = _assegnazione(repo, tmp_path, testo)
    errata = EsitoLex("scelta", "Accertamento con adesione", "Collaudo tecnico delle impronte SQL documentali",
                     "proposta storica priva dei riscontri", _voce("Accertamento con adesione"))
    prima, candidati, evidenze = applica_esito(assignment, [], [], errata, modello="qwen3:4b")
    repo.save_catalog_assignment(prima, candidates=candidati, evidence=evidenze)
    case = NS(id="FASC-LEX", documenti=[NS(id="DOC-LEX", nome="documento.pdf")])
    oggetto = Oggetto(tipo="documento", oggetto_id="DOC-LEX", presente=True, sha256="7" * 64)
    registro = NS(oggetti=lambda *args: [oggetto])
    monkeypatch.setattr(runtime, "build_document_ai_service", lambda: NS(repository=repo))
    monkeypatch.setattr(runtime, "document_ai_tenant_id", lambda: "studio-test")
    monkeypatch.setattr(runtime, "_registra_catalogo", lambda *args: None)
    monkeypatch.setattr(registro_runtime, "tenant_corrente", lambda: "studio-test")
    report = aggiorna_catalogo_da_archivio(case, registro, document_ids={"DOC-LEX"}, retry=True, actor="avvocato-test")
    assert report["run"]["processed"] == 1 and not report["run"]["errors"]
    dopo = repo.get_catalog_assignment("studio-test", "FASC-LEX", "DOC-LEX")
    assert dopo.document_label == "Contenuto da verificare"
    assert repo.get_extracted_text("studio-test", "FASC-LEX", assignment.document_ai_id, assignment.document_version_id).text == testo
    row = backend.conn.execute("SELECT payload_json FROM fascicolo_documenti_ai_audit WHERE tenant_id = ? AND event_type = ?",
                               ("studio-test", "document_catalog.reclassified_from_archive")).fetchone()
    raw = row["payload_json"]
    payload = json.loads(raw) if isinstance(raw, str) else raw
    precedente = payload["payload"]["precedente"]
    assert precedente["etichetta"] == "Accertamento con adesione"
    assert precedente["lex_lettura"]["citazione"] == errata.citazione
