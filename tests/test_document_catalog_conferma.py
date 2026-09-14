"""Conferma massiva delle proposte di catalogazione: servizio ed endpoint."""

from __future__ import annotations

from types import SimpleNamespace

from tests.test_react_shell import _app
from web.services import document_catalog_conferma as servizio

HEADERS = {"X-API-Key": "react-test-key", "Content-Type": "application/json"}


class _Repository:
    def __init__(self, assegnazioni, prove):
        self._assegnazioni = assegnazioni
        self._prove = prove

    def list_catalog_assignments(self, tenant_id, fascicolo_id):
        return self._assegnazioni

    def list_catalog_evidence(self, assignment_id):
        return self._prove.get(assignment_id, [])


def test_conferma_solo_le_proposte_con_prova_e_lascia_le_altre(monkeypatch):
    assegnazioni = [
        SimpleNamespace(id="A1", document_id="D1", document_label="Atto di citazione", status="proposed"),
        SimpleNamespace(id="A2", document_id="D2", document_label="Procura", status="proposed"),
        SimpleNamespace(id="A3", document_id="D3", document_label="Sentenza", status="confirmed"),
        SimpleNamespace(id="A4", document_id="D4", document_label="Documento", status="review_required"),
        SimpleNamespace(id="A5", document_id="D5", document_label="Ricevuta", status="proposed"),
    ]
    repository = _Repository(assegnazioni, {"A1": ["prova"], "A5": ["prova"]})
    confermate: list[tuple] = []

    def finto_resolve(fascicolo_id, document_id, *, status, note, evidence_acknowledged, user_context=None):
        if document_id == "D5":
            raise RuntimeError("catalogo bloccato")
        confermate.append((fascicolo_id, document_id, status, note, evidence_acknowledged))
        return {"document_id": document_id, "status": status}

    monkeypatch.setattr(servizio, "assert_document_ai_fascicolo_current_tenant", lambda fascicolo_id: None)
    monkeypatch.setattr(servizio, "build_document_ai_service", lambda: SimpleNamespace(repository=repository))
    monkeypatch.setattr(servizio, "document_ai_tenant_id", lambda: "tenant")
    monkeypatch.setattr(servizio, "resolve_document_catalog_assignment", finto_resolve)

    esito = servizio.conferma_proposte_catalogo("F1", user_context={"user_id": "avv"})

    assert confermate == [("F1", "D1", "confirmed", servizio.NOTA_CONFERMA_MASSIVA, True)]
    assert [voce["document_id"] for voce in esito["confermate"]] == ["D1"]
    assert [voce["document_id"] for voce in esito["senza_prova"]] == ["D2"]
    assert [voce["document_id"] for voce in esito["errori"]] == ["D5"]
    assert esito["message"] == "1 proposta confermata; 1 senza prova letta dal contenuto (restano proposte: correggile o aggiorna l'indice); 1 non confermate per errore."


def test_messaggio_quando_non_ci_sono_proposte(monkeypatch):
    monkeypatch.setattr(servizio, "assert_document_ai_fascicolo_current_tenant", lambda fascicolo_id: None)
    monkeypatch.setattr(servizio, "build_document_ai_service", lambda: SimpleNamespace(repository=_Repository([], {})))
    monkeypatch.setattr(servizio, "document_ai_tenant_id", lambda: "tenant")
    assert servizio.conferma_proposte_catalogo("F1")["message"].startswith("Nessuna proposta da confermare")


def test_endpoint_conferma_proposte_restituisce_esito_e_catalogo(tmp_path, monkeypatch):
    from web.blueprints import api_v1_documenti_ai as modulo

    monkeypatch.setattr(servizio, "conferma_proposte_catalogo", lambda fascicolo_id, user_context=None: {"confermate": [{"document_id": "D1", "document_label": "Atto"}], "senza_prova": [], "errori": [], "message": "1 proposta confermata."})
    monkeypatch.setattr(modulo, "build_document_catalog_payload", lambda fascicolo_id, process=False, **_kwargs: {"documents": [], "summary": {"total": 1, "confirmed": 1, "proposed": 0}, "run": {"errors": []}})
    app = _app(tmp_path)
    with app.test_client() as client:
        risposta = client.post("/api/v1/ui/fascicoli/F1/catalogazione-documentale/conferma-proposte", headers=HEADERS, data="{}")
    assert risposta.status_code == 200, risposta.get_data(as_text=True)
    payload = risposta.get_json()
    assert payload["message"] == "1 proposta confermata."
    assert payload["confermate"][0]["document_id"] == "D1"
    assert payload["summary"]["confirmed"] == 1
