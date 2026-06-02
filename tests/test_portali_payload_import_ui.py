from __future__ import annotations

from pathlib import Path
import base64
import hashlib

import pytest

from pct.auth import GestioneUtenti, RuoloUtente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.fascicolo_workspace import build_fascicolo_workspace
from pct.pat import ClientPAT
from pct.pdp import ClientPDP
from pct.portal_direct_guard import UnverifiedDirectPortalError
from pct.sigit import ClientSIGIT
from pct.pst_servizi_catalogo import SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA
from web.services.portal_integration_policy import (
    MODE_DIRECT_INTERNAL,
    MODE_DIRECT_VERIFIED,
    MODE_OFFICIAL_PORTAL_ASSISTED,
    get_portal_integration_policy,
)
from web.app import create_app


def _cfg_web(tmp_path: Path) -> dict:
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "API_KEY": "react-test-key",
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
        "EMAIL_CASELLA_DB": str(tmp_path / "email" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(tmp_path / "email" / "ordinaria.json"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "PORTALE_IMPORT_LOG_DB": str(tmp_path / "portale" / "import_log.json"),
        "PRACTICE_ENGINE_DB": str(tmp_path / "practice_engine" / "practice_engine.json"),
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


def _direct_manifest(**overrides) -> dict:
    manifest = {
        "allow_direct": True,
        "status": "verified",
        "official_source_url": "https://example.gov.it/canale-ufficiale",
        "evidence_sha256": "a" * 64,
        "verified_at": "2026-05-13T10:00:00Z",
        "expires_at": "2030-01-01T00:00:00Z",
        "integration_tests_passed": True,
        "channel_kind": "official_api",
        "verified_by": "Responsabile integrazioni",
    }
    manifest.update(overrides)
    return manifest


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
    app.config["API_KEY"] = "react-test-key"

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
            ("pdp", "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp"),
            ("pat", "https://pe.prod.cloud.giustizia-amministrativa.it"),
            ("ptt", "https://sigit.giustiziatributaria.gov.it/Sigit/index.do"),
        ):
            page = client.get(f"/portali/{portale}/acquisizione?_legacy=1", follow_redirects=True)
            html = page.get_data(as_text=True)

            assert page.status_code == 200
            assert expected in html
            assert ".json" in html
            assert "payload JSON autorizzato" in html
            assert "/acquisizione/importa-payload" in html


def test_pst_e_direct_internal():
    policy = get_portal_integration_policy("pst")

    assert policy.mode == MODE_DIRECT_INTERNAL
    assert policy.direct_allowed is True
    assert policy.assistant_required is False


@pytest.mark.parametrize("portale", ["ptt", "pat", "pdp"])
def test_ptt_pat_pdp_e_assistito_senza_manifest(portale: str):
    policy = get_portal_integration_policy(portale, config={})

    assert policy.mode == MODE_OFFICIAL_PORTAL_ASSISTED
    assert policy.direct_allowed is False
    assert policy.assistant_required is True


def test_ptt_e_assistito_senza_manifest():
    assert get_portal_integration_policy("ptt", config={}).mode == MODE_OFFICIAL_PORTAL_ASSISTED


def test_pat_e_assistito_senza_manifest():
    assert get_portal_integration_policy("pat", config={}).mode == MODE_OFFICIAL_PORTAL_ASSISTED


def test_pdp_e_assistito_senza_manifest():
    assert get_portal_integration_policy("pdp", config={}).mode == MODE_OFFICIAL_PORTAL_ASSISTED


@pytest.mark.parametrize("portale", ["ptt", "pat", "pdp"])
def test_ptt_pat_pdp_fail_closed_se_manifest_incompleto(portale: str):
    policy = get_portal_integration_policy(
        portale,
        config={"PORTAL_DIRECT_CHANNELS": {portale: _direct_manifest(evidence_sha256="abc")}},
    )

    assert policy.mode == MODE_OFFICIAL_PORTAL_ASSISTED
    assert policy.direct_allowed is False
    assert "evidence_sha256" in policy.validation_errors


def test_pdp_diventa_direct_verified_solo_con_manifest_completo():
    policy = get_portal_integration_policy(
        "pdp",
        config={"PORTAL_DIRECT_CHANNELS": {"pdp": _direct_manifest()}},
    )

    assert policy.mode == MODE_DIRECT_VERIFIED
    assert policy.direct_allowed is True
    assert policy.assistant_required is False


def test_guard_blocca_client_diretto_ptt_senza_manifest():
    with pytest.raises(UnverifiedDirectPortalError):
        ClientSIGIT(codice_fiscale_avvocato="RSSMRA80A01H501U").ricerca_fascicoli("PTT_RC")


def test_guard_blocca_client_diretto_pat_senza_manifest():
    with pytest.raises(UnverifiedDirectPortalError):
        ClientPAT(codice_fiscale_avvocato="RSSMRA80A01H501U").consulta_documenti("PAT_RC", "77", 2026)


def test_guard_blocca_client_diretto_pdp_senza_manifest():
    with pytest.raises(UnverifiedDirectPortalError):
        ClientPDP(codice_fiscale_avvocato="RSSMRA80A01H501U").deposita_atto("PDP_PA", "Memoria", "missing.pdf")


def test_assistant_start_rifiuta_pst(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post("/api/portali/pst/assistant/start", json={})

    data = response.get_json()
    assert response.status_code == 400
    assert data["ok"] is False
    assert "PST usa il canale diretto interno" in data["errore"]


@pytest.mark.parametrize("portale", ["ptt", "pat", "pdp"])
def test_assistant_start_accetta_ptt_pat_pdp(tmp_path: Path, portale: str):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post(f"/api/portali/{portale}/assistant/start", json={"fascicolo_id": ""})

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["portale"] == portale
    assert data["mode"] == MODE_OFFICIAL_PORTAL_ASSISTED
    assert data["session_id"]
    assert data["official_url"].startswith("https://")


def test_deposito_non_finalizza_senza_ricevuta_ufficiale(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post("/api/portali/ptt/deposito/finalizza", json={"fascicolo_id": "F1"})

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is False
    assert data["status"] == "anomalia_da_verificare"
    assert "senza ricevuta" in data["message"]


def _seed_fascicolo(cfg: dict, tipo: TipoFascicolo = TipoFascicolo.TRIBUTARIO):
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    return gf.nuovo(titolo="Studio c/ Agenzia", tipo=tipo)


@pytest.mark.parametrize(
    ("portale", "tipo"),
    [
        ("pdp", TipoFascicolo.PENALE),
        ("pat", TipoFascicolo.AMMINISTRATIVO),
        ("ptt", TipoFascicolo.TRIBUTARIO),
    ],
)
def test_api_importa_file_assistiti_smista_nel_fascicolo_interno(tmp_path: Path, portale: str, tipo: TipoFascicolo):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    fascicolo = _seed_fascicolo(cfg, tipo)
    app = create_app(cfg)
    atto = f"Atto ufficiale {portale.upper()}".encode("utf-8")
    ricevuta = f"Ricevuta accettazione {portale.upper()}".encode("utf-8")

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post(
            f"/api/portali/{portale}/acquisizione/importa-file",
            json={
                "fascicolo_id": fascicolo.id,
                "downloaded_files": [
                    {
                        "nome": f"{portale}_provvedimento.txt",
                        "contenuto_b64": base64.b64encode(atto).decode("ascii"),
                        "tipo_atto": "Provvedimento",
                        "id_documento_portale": f"{portale}-DOC-1",
                        "id_deposito_esterno": f"{portale}-DEP-1",
                    },
                    {
                        "nome": "ricevuta_accettazione.eml",
                        "contenuto_b64": base64.b64encode(ricevuta).decode("ascii"),
                        "sha256": hashlib.sha256(ricevuta).hexdigest(),
                        "oggetto": "Ricevuta accettazione deposito",
                        "data_ufficiale": "2026-05-13",
                        "id_deposito_ufficiale": f"{portale}-DEP-RCPT",
                    },
                ],
                "mapping": {"mode": "update_existing", "target_fascicolo_id": fascicolo.id},
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["id_fascicolo"] == fascicolo.id
    assert data["summary"]["documenti"] >= 2
    assert data["summary"]["ricevute"] == 1
    assert data["summary"]["fascicolo_url"].endswith(f"/fascicoli/{fascicolo.id}")

    reloaded = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert reloaded is not None
    assert reloaded.source == portale.upper()
    assert any(doc.nome == f"{portale}_provvedimento.txt" for doc in reloaded.documenti)
    assert any(doc.nome == "ricevuta_accettazione.eml" for doc in reloaded.documenti)
    assert any(dep.servizio_portale == SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA for dep in reloaded.depositi_pct)


def test_import_ricevuta_deposito_crea_comunicazione_cancelleria(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    fascicolo = _seed_fascicolo(cfg)
    app = create_app(cfg)
    payload = b"Ricevuta ufficiale deposito PTT"
    sha = hashlib.sha256(payload).hexdigest()

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post(
            "/api/portali/ptt/deposito/importa-ricevute",
            json={
                "fascicolo_id": fascicolo.id,
                "receipts": [
                    {
                        "filename": "ricevuta_accettazione.eml",
                        "content_base64": base64.b64encode(payload).decode("ascii"),
                        "sha256": sha,
                        "oggetto": "Ricevuta accettazione deposito",
                        "mittente": "segreteria@giustiziatributaria.gov.it",
                        "destinatario": "studio@example.com",
                        "data_ufficiale": "2026-05-13",
                        "message_id": "<ptt-acc@example.gov>",
                        "id_deposito_ufficiale": "PTT-DEP-1",
                    }
                ],
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["imported"][0]["classificazione"] == "ricevuta_accettazione_deposito"

    reloaded = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert reloaded is not None
    assert any(dep.servizio_portale == SERVIZIO_PST_COMUNICAZIONE_CANCELLERIA for dep in reloaded.depositi_pct)
    assert any("sha256=" + sha in dep.note for dep in reloaded.depositi_pct)


def test_import_ricevuta_deposito_collega_timeline_evidence_pack(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    fascicolo = _seed_fascicolo(cfg, TipoFascicolo.AMMINISTRATIVO)
    app = create_app(cfg)
    payload = b"Esito ufficiale PAT"
    sha = hashlib.sha256(payload).hexdigest()

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post(
            "/api/portali/pat/deposito/importa-ricevute",
            json={
                "fascicolo_id": fascicolo.id,
                "receipts": [
                    {
                        "filename": "esito_cancelleria.pdf",
                        "content_base64": base64.b64encode(payload).decode("ascii"),
                        "sha256": sha,
                        "oggetto": "Esito segreteria cancelleria",
                        "data_ufficiale": "2026-05-13",
                    }
                ],
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["deposito_id"]
    assert data["evidence_pack"]["hash_sha256"]

    practice_engine = Path(cfg["PRACTICE_ENGINE_DB"])
    raw = practice_engine.read_text(encoding="utf-8")
    assert "OFFICIAL_PORTAL_RECEIPTS_IMPORTED" in raw
    assert "official_portal_assisted" in raw


def test_wizard_ptt_mostra_portale_ufficiale_assistito(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        page = client.get("/portali/ptt/acquisizione?_legacy=1", follow_redirects=True)

    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Portale ufficiale assistito" in html
    assert "Fascicolo tributario interno con PTT / SIGIT assistito" in html
    assert "Avvia sessione assistita" in html
    assert "Apri portale ufficiale assistito" in html
    assert "Raccogli file scaricati" in html
    assert "Importa nel fascicolo interno" in html
    assert "Chiudi sessione assistita" in html
    assert "Apri link esterno" not in html


def test_wizard_pst_non_mostra_portale_ufficiale_assistito_come_flusso_principale(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        page = client.get("/portali/pst/acquisizione?_legacy=1", follow_redirects=True)

    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'id="awAssistantStart"' not in html
    assert "Fascicolo tributario interno con PTT / SIGIT assistito" not in html


def test_pst_preview_fonde_catalogo_master_detail_e_scarta_righe_non_scaricabili(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _seed_user(cfg)
    app = create_app(cfg)

    doc_principale = {
        "id_documento": "28139218",
        "id_cat": "28139218",
        "nome": "Citazione_28139218.pdf",
        "tipo_atto": "Citazione",
        "data_deposito": "2024-09-05",
        "mittente": "MONTAGNESE ROBERTO",
    }
    allegato = {
        "id_documento": "ALLEGATO-1",
        "id_cat": "ALLEGATO-1",
        "id_documento_padre": "28139218",
        "parent_nome": "Citazione_28139218.pdf",
        "nome": "PROCURA.PDF",
        "tipo_atto": "Documento",
        "data_deposito": "2024-09-05",
        "is_allegato": True,
    }
    doc_principale_da_gruppo = {
        **doc_principale,
        "id_documento": "28139218-GRUPPO",
        "id_cat": "28139218-GRUPPO",
        "id_deposito": "__2024-09-05__MONTAGNESE ROBERTO",
    }
    riga_testo_non_documento = {
        "nome": "ROBERTO",
        "tipo_atto": "Documento",
        "data_deposito": "",
    }
    snapshot = {
        "fascicolo": {"numero": "1025", "anno": "2024"},
        "documenti": [doc_principale],
        "catalogo": [doc_principale, allegato, doc_principale_da_gruppo, riga_testo_non_documento],
    }

    with app.test_client() as client:
        client.post("/login", data={"username": "admin-portali", "password": "Admin1234!"})
        response = client.post(
            "/api/portali/pst/acquisizione/preview",
            json={
                "selection": {
                    "numero": "1025",
                    "anno": "2024",
                    "ufficio_nome": "Tribunale di Palmi",
                    "ufficio_codice": "0910011",
                    "parti": ["MONTAGNESE ROBERTO"],
                    "snapshot": snapshot,
                },
                "snapshot": snapshot,
                "documenti": [doc_principale],
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    documenti = data["preview"]["documenti"]
    nomi = {item["nome"] for item in documenti}
    assert data["preview"]["counts"]["documenti"] == 2
    assert "Citazione_28139218.pdf" in nomi
    assert "PROCURA.PDF" in nomi
    assert "ROBERTO" not in nomi
