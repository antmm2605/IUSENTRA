from __future__ import annotations

from pathlib import Path

import pytest

from pct.auth import GestioneUtenti, RuoloUtente
from pct.fascicoli import GestioneFascicoli
from pct.fascicolo_workspace import build_fascicolo_workspace
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "MULTI_TENANT": False,
        "STORAGE_MODE_DEFAULT": "json",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "PORTALE_IMPORT_LOG_DB": str(tmp_path / "portale" / "import_log.json"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "PDP_PENALE_DB": str(tmp_path / "penale" / "pdp_penale.db"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


def _seed_user(cfg: dict) -> None:
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="admin-portali",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )


def _payload(portale: str) -> dict:
    if portale == "pdp":
        fascicolo = {
            "ufficio": "Procura della Repubblica di Palermo",
            "ufficio_codice": "PDP_PA",
            "registro": "RGNR",
            "numero": "12345",
            "anno": "2026",
            "fase": "DIBATTIMENTO",
            "reato": "Lesioni personali",
            "stato": "PENDENTE",
            "data_iscrizione": "2026-04-01",
            "data_udienza": "2026-05-20",
            "giudice": "Dott. Verdi",
        }
        parti = [
            {"ruolo": "Imputato", "denominazione": "Mario Rossi"},
            {"ruolo": "Parte offesa", "denominazione": "Luigi Bianchi"},
        ]
    elif portale == "pat":
        fascicolo = {
            "ufficio": "TAR Calabria",
            "ufficio_codice": "PAT_RC",
            "tipo": "RICORSO",
            "numero_ricorso": "77",
            "anno": "2026",
            "materia": "Appalti",
            "oggetto": "Impugnazione aggiudicazione",
            "stato": "PENDENTE",
            "data_deposito": "2026-04-02",
            "data_udienza": "2026-06-12",
            "giudice_relatore": "Cons. Neri",
        }
        parti = [
            {"ruolo": "Ricorrente", "denominazione": "Impresa Alfa SRL"},
            {"ruolo": "Resistente", "denominazione": "Comune di Reggio Calabria"},
        ]
    else:
        fascicolo = {
            "ufficio": "Corte di Giustizia Tributaria di primo grado di Reggio Calabria",
            "ufficio_codice": "PTT_RC",
            "tipo": "RICORSO",
            "numero_rgt": "902",
            "anno_rgt": "2026",
            "materia": "IMU",
            "oggetto_controversia": "Avviso di accertamento IMU",
            "stato": "PENDENTE",
            "data_deposito": "2026-04-03",
            "data_udienza": "2026-07-10",
            "giudice_relatore": "Dott.ssa Blu",
        }
        parti = [
            {"ruolo": "Ricorrente", "denominazione": "Paolo Verdi"},
            {"ruolo": "Resistente", "denominazione": "Agenzia Entrate"},
        ]

    return {
        "fascicolo": fascicolo,
        "parti": parti,
        "eventi": [
            {
                "evento_uid": f"{portale}-EVT-1",
                "tipo_evento": "Deposito",
                "descrizione": "Deposito atto introduttivo",
                "data_evento": "2026-04-04",
            }
        ],
        "udienze": [
            {
                "udienza_uid": f"{portale}-UD-1",
                "data_udienza": "2026-08-08",
                "ora": "09:30",
                "tipo": "Udienza pubblica",
                "descrizione": "Prima udienza importata dal payload",
            }
        ],
        "documenti": [
            {
                "documento_uid": f"{portale}-DOC-1",
                "nome_file": f"{portale}_atto_introduttivo.pdf",
                "sezione": "DocumentiFascicolo",
                "classificazione": "Atto introduttivo",
                "tipo_atto": "Ricorso",
                "data_deposito": "2026-04-04",
                "depositante": "Avv. Roberto Montagnese",
                "dimensione_bytes": 123456,
                "id_deposito": f"{portale}-DEP-DOC",
            }
        ],
        "comunicazioni": [
            {
                "comunicazione_uid": f"{portale}-COM-1",
                "tipo": "Cancelleria",
                "oggetto": "Comunicazione fissazione udienza",
                "data_comunicazione": "2026-04-05",
                "mittente": "Cancelleria",
            }
        ],
        "istanze": [
            {
                "evento_uid": f"{portale}-IST-1",
                "tipo_evento": "Istanza",
                "descrizione": "Istanza di accesso al fascicolo",
                "data_evento": "2026-04-06",
                "esito": "Depositata",
            }
        ],
        "depositi": [
            {
                "deposito_uid": f"{portale}-DEP-LOG",
                "tipo_atto": "Ricevuta deposito",
                "stato": "ACCETTATO",
                "data_invio": "2026-04-07",
                "messaggio_esito": "Esito importato dal payload autorizzato",
            }
        ],
    }


@pytest.mark.parametrize("portale", ["pdp", "pat", "ptt"])
def test_payload_autorizzato_portali_arriva_nella_ui_fascicolo(tmp_path: Path, portale: str):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin-portali", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.post(
            f"/api/portali/{portale}/acquisizione/importa-payload",
            json={
                "payload": _payload(portale),
                "options": {
                    "importa_documenti": True,
                    "importa_provvedimenti": True,
                    "importa_eventi": True,
                    "importa_udienze": True,
                    "importa_scadenze": True,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": True,
                },
                "mapping": {"mode": "create_new"},
            },
        )
        data = response.get_json()

        assert response.status_code == 200
        assert data["ok"] is True
        id_fasc = data["id_fascicolo"]

        detail = client.get(f"/fascicoli/{id_fasc}", follow_redirects=True)
        react_detail = client.get(
            f"/api/v1/ui/fascicoli/{id_fasc}",
            headers={"X-API-Key": "react-test-key"},
        )
        react_payload = react_detail.get_json()

    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = fascicoli.get(id_fasc)
    assert fasc is not None
    workspace = build_fascicolo_workspace(fasc)

    assert detail.status_code == 200
    assert react_detail.status_code == 200
    assert workspace["counts"]["documenti"] == 0
    assert workspace["counts"]["documenti_governati"] >= 1
    assert workspace["counts"]["documenti_catalogo_portale"] >= 1
    assert workspace["counts"]["attivita"] >= 1
    assert workspace["counts"]["udienze_scadenze"] >= 1
    assert workspace["counts"]["comunicazioni"] >= 1
    assert workspace["counts"]["istanze"] >= 1
    documents = react_payload["documents"]
    portal_document = next(item for item in documents if item["name"] == f"{portale}_atto_introduttivo.pdf")
    assert portal_document["statusLabel"] == "Da acquisire"
    assert portal_document["statusTone"] == "info"
    assert portal_document["portalDate"] == "04/04/2026"
    assert any(deposito["portalDocuments"] for deposito in react_payload["deposits"])
    assert any(item["label"] == "Documenti" and "elementi" in item["value"] for item in react_payload["quality"])


def test_wizard_portali_espone_upload_payload_json_e_portali_ufficiali(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "admin-portali", "password": "Admin1234!"},
            follow_redirects=True,
        )
        for portale, expected in (
            ("pdp", "https://appweb.giustizia.it/snt"),
            ("pat", "https://www.giustizia-amministrativa.it/portale-avvocato"),
            ("ptt", "https://sigit.giustiziatributaria.gov.it/Sigit/index.do"),
        ):
            page = client.get(f"/portali/{portale}/acquisizione", follow_redirects=True)
            html = page.get_data(as_text=True)

            assert page.status_code == 200
            assert expected in html
            assert ".json" in html
            assert "payload JSON autorizzato" in html
            assert "/acquisizione/importa-payload" in html
