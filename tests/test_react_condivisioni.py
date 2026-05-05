from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.condivisione import RuoloCondivisione
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_react_shell import _app
from web.services.react_condivisioni_bridge import build_react_condivisioni_payload


class _Collaboratore:
    id = "collab-1"
    username = "collab"
    nome_completo = "Collaboratore Test"

    def ha_permesso(self, _permission: str) -> bool:
        return False


def _seed_condivisioni(app):
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Giulia", cognome="Verdi")
    fascicoli = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        "Opposizione a decreto ingiuntivo",
        TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        tribunale="Tribunale di Roma",
    )
    with app.app_context():
        condivisioni = app.extensions["core_runtime"]["get_condivisioni"]()
        condivisioni.condividi(
            id_cliente=cliente.id,
            id_utente="collab-1",
            username="collab",
            nome_completo="Collaboratore Test",
            ruolo=RuoloCondivisione.SCRITTURA,
            condiviso_da="operatore",
            note="Accesso istruttoria",
            data_scadenza=(date.today() + timedelta(days=5)).isoformat(),
            tags=["istruttoria"],
        )
        condivisioni.condividi_fascicolo(
            id_fascicolo=fascicolo.id,
            id_cliente=cliente.id,
            id_utente="collab-1",
            username="collab",
            nome_completo="Collaboratore Test",
            ruolo=RuoloCondivisione.LETTURA,
            condiviso_da="operatore",
        )
        _token, _link = condivisioni.crea_link_temporaneo(
            id_cliente=cliente.id,
            creato_da="operatore",
            ruolo=RuoloCondivisione.LETTURA,
            ore_validita=24,
            descrizione="Consultazione temporanea",
        )
    return cliente, fascicolo


def test_cartelle_condivise_react_api_permessi_e_api_esistenti(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_condivisioni(app)

    with app.test_client() as client:
        _login(client)
        response = client.get("/cartelle-condivise")
        classic = client.get("/cartelle-condivise?_legacy=1")
        api = client.get("/api/v1/ui/cartelle-condivise")
        api_cliente = client.get(f"/api/v1/clienti/{cliente.id}/condivisioni")
        api_stats = client.get("/api/v1/condivisioni/statistiche")
        cleanup = client.post("/api/v1/condivisioni/pulizia-scaduti")

    assert response.status_code == 200
    assert '<html lang="it" class="react-shell-document">' in response.get_data(as_text=True)
    assert classic.status_code == 200
    assert 'id="root"' not in classic.get_data(as_text=True)
    assert api.status_code == 200
    payload = api.get_json()
    assert payload["contracts"]["mock_fallback"] is False
    assert payload["contracts"]["writes"] == "operational_routes"
    assert payload["mode"] == "gestore"
    assert payload["stats"]["sharedFolders"] >= 1
    assert payload["stats"]["activeTemporaryLinks"] >= 1
    assert payload["managedFolders"][0]["client"]["id"] == cliente.id
    assert "token" not in str(payload["managedFolders"][0]["activeLinks"]).lower()
    assert api_cliente.status_code == 200
    assert api_cliente.get_json()["id_cliente"] == cliente.id
    assert api_stats.status_code == 200
    assert cleanup.status_code == 200

    with app.app_context():
        condivisioni = app.extensions["core_runtime"]["get_condivisioni"]()
        collaborator_payload = build_react_condivisioni_payload(
            get_condivisioni=lambda: condivisioni,
            get_clienti=lambda: GestioneClienti(db_path=app.config["CLIENTI_DB"]),
            get_fascicoli=lambda: GestioneFascicoli(
                db_path=app.config["FASCICOLI_DB"],
                documents_dir=app.config["FASCICOLI_DOCS"],
                archive_dir=app.config["FASCICOLI_ARCH"],
            ),
            current_user=_Collaboratore(),
        )
    assert collaborator_payload["mode"] == "collaboratore"
    assert collaborator_payload["receivedFolders"][0]["client"]["id"] == cliente.id
    assert collaborator_payload["receivedMatters"][0]["id"] == fascicolo.id
