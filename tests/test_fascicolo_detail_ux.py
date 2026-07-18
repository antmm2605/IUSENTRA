from __future__ import annotations

import os
from pathlib import Path

import pytest

from pct.auth import GestioneUtenti, RuoloUtente
from pct.document_management import build_document_management_summary
from pct.fascicolo_workspace import build_fascicolo_workspace
from pct.fascicoli import GestioneFascicoli, TipoAttivita, TipoDocumento, TipoFascicolo


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
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
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


@pytest.fixture()
def fascicolo_ux(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )
    return cfg, fascicolo


def _login(client):
    client.post(
        "/login",
        data={"username": "avvocato", "password": "Avv12345!"},
        follow_redirects=True,
    )


def _signed_payload_p7m(payload: bytes) -> bytes:
    from asn1crypto import algos, cms

    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data", "content": payload},
            "signer_infos": [],
        }
    )
    return cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()


def test_dettaglio_fascicolo_espone_ux_documenti_e_cabina_collassabile(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, b"%PDF-1.4")
    gf.aggiungi_attivita(fascicolo.id, TipoAttivita.UDIENZA, "2026-05-10", "Udienza di trattazione")

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.get(f"/fascicoli/{fascicolo.id}")
        legacy_response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1")
        react_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}")
        react_documents_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti")

    body = response.data.decode("utf-8")
    legacy_body = legacy_response.data.decode("utf-8")
    react_payload = react_response.get_json()
    react_documents_payload = react_documents_response.get_json()
    assert response.status_code == 200
    assert legacy_response.status_code == 200
    assert react_response.status_code == 200
    assert react_documents_response.status_code == 200
    assert '<div id="root"></div>' in body
    assert 'id="docBulkDeleteForm"' in legacy_body
    assert 'id="modalConfermaAzioneFascicolo"' in legacy_body
    assert "_prepareFascicoloDeleteForms" in legacy_body
    assert 'data-bs-target="#collapse-sezione-cabina-fascicolo"' in legacy_body
    assert 'class="collapse show" id="collapse-sezione-cabina-fascicolo"' in legacy_body
    assert 'data-bs-target="#modalDettaglioAttivita' in legacy_body
    assert "elimina_attivita_fascicolo" not in legacy_body
    assert "/attivita/" in legacy_body and "/elimina" in legacy_body
    assert react_payload["fascicolo"]["title"] == "RG 1025/2024"
    assert react_payload["documents"] == []
    assert react_documents_payload["documents"][0]["name"] == "atto.pdf"
    assert react_payload["activities"] == []


def test_elimina_documento_resta_nella_sezione_documenti(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    doc = gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, b"%PDF-1.4")

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/elimina",
            data={"next_section": "sezione-documenti-fascicolo"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/fascicoli/{fascicolo.id}#sezione-documenti-fascicolo")
    assert not GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id).documenti


def test_rinomina_documento_da_react_action(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    doc = gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, b"%PDF-1.4")

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/rinomina",
            json={"nome_file": "Ricorso principale"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        detail = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti").get_json()

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["nome_file"] == "Ricorso principale.pdf"
    assert detail["documents"][0]["name"] == "Ricorso principale.pdf"
    assert detail["documents"][0]["actions"]["rename"].endswith(f"/documenti/{doc.id}/rinomina")


def test_rinomina_documento_portale_mostra_nome_scelto_e_conserva_originale(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "9732730s.pdf",
        TipoDocumento.SENTENZA,
        b"%PDF-1.4",
        nome_originale="9732730s.pdf",
        nome_portale="9732730s.pdf",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/rinomina",
            json={"nome_file": "Sentenza"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        detail = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti").get_json()

    assert response.status_code == 200
    assert detail["documents"][0]["name"] == "Sentenza.pdf"
    assert "Nome file originale: 9732730s.pdf" in detail["documents"][0]["tags"]
    assert all("iusentra:" not in tag for tag in detail["documents"][0]["tags"])


def test_documenti_xml_p7m_eml_e_txt_si_visualizzano_e_si_eliminano(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    eml = gf.aggiungi_documento(
        fascicolo.id,
        "pec_a29623d7158e1c9232ce3182.eml",
        TipoDocumento.COMUNICAZIONE,
        b"Subject: PEC prova\r\nFrom: cancelleria@example.test\r\n\r\nCorpo messaggio",
    )
    txt = gf.aggiungi_documento(
        fascicolo.id,
        "nota_lex.txt",
        TipoDocumento.ALLEGATO,
        "Promemoria leggibile da Lex".encode("utf-8"),
    )
    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?><DatiAtto><Oggetto>Deposito prova</Oggetto></DatiAtto>'
    xml = gf.aggiungi_documento(
        fascicolo.id,
        "DatiAtto.xml",
        TipoDocumento.ALLEGATO,
        xml_bytes,
    )
    xml_p7m = gf.aggiungi_documento(
        fascicolo.id,
        "DatiAtto.xml.p7m",
        TipoDocumento.ALLEGATO,
        _signed_payload_p7m(xml_bytes),
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        eml_preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/visualizza")
        txt_preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{txt.id}/visualizza")
        xml_preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{xml.id}/visualizza")
        xml_p7m_preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{xml_p7m.id}/visualizza")
        eml_delete = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/elimina",
            headers={"X-Requested-With": "XMLHttpRequest"},
            follow_redirects=False,
        )
        txt_delete = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{txt.id}/elimina",
            headers={"X-Requested-With": "XMLHttpRequest"},
            follow_redirects=False,
        )
        xml_delete = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{xml.id}/elimina",
            headers={"X-Requested-With": "XMLHttpRequest"},
            follow_redirects=False,
        )
        xml_p7m_delete = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{xml_p7m.id}/elimina",
            headers={"X-Requested-With": "XMLHttpRequest"},
            follow_redirects=False,
        )

    assert eml_preview.status_code == 200
    assert txt_preview.status_code == 200
    assert xml_preview.status_code == 200
    assert xml_p7m_preview.status_code == 200
    assert "Email PEC / EML" in eml_preview.data.decode("utf-8")
    assert "PEC prova" in eml_preview.data.decode("utf-8")
    assert "Documento di testo" in txt_preview.data.decode("utf-8")
    assert "Promemoria leggibile da Lex" in txt_preview.data.decode("utf-8")
    assert "Documento XML" in xml_preview.data.decode("utf-8")
    assert "Deposito prova" in xml_preview.data.decode("utf-8")
    assert "Documento XML firmato" in xml_p7m_preview.data.decode("utf-8")
    assert "Deposito prova" in xml_p7m_preview.data.decode("utf-8")
    assert eml_delete.status_code == 200
    assert txt_delete.status_code == 200
    assert xml_delete.status_code == 200
    assert xml_p7m_delete.status_code == 200
    assert eml_delete.get_json()["ok"] is True
    assert txt_delete.get_json()["ok"] is True
    assert xml_delete.get_json()["ok"] is True
    assert xml_p7m_delete.get_json()["ok"] is True
    assert not GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id).documenti


def test_eml_importato_con_titolo_senza_estensione_resta_visualizzabile(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    eml = gf.aggiungi_documento(
        fascicolo.id,
        "CONSEGNA_notifica.eml",
        TipoDocumento.COMUNICAZIONE,
        b"Subject: CONSEGNA notifica\r\nFrom: gestore@example.test\r\nTo: studio@example.test\r\n\r\nRicevuta completa",
        nome_originale="CONSEGNA_notifica.eml",
    )
    eml.nome = "CONSEGNA: Notificazione ai sensi della legge n. 53 del 1994"
    gf._salva()

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/visualizza")
        download = client.get(f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/scarica")

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert "Email PEC / EML" in preview.data.decode("utf-8")
    assert "Ricevuta completa" in preview.data.decode("utf-8")
    assert download.status_code == 200
    assert ".eml" in download.headers["Content-Disposition"].casefold()


def test_eml_storico_senza_estensione_nei_metadati_viene_riconosciuto_dal_contenuto(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    eml = gf.aggiungi_documento(
        fascicolo.id,
        "ricevuta_storica",
        TipoDocumento.COMUNICAZIONE,
        b"Subject: ACCETTAZIONE deposito\r\nFrom: gestore@example.test\r\nTo: studio@example.test\r\nDate: Sat, 18 Jul 2026 10:00:00 +0200\r\n\r\nMessaggio acquisito",
        nome_originale="ricevuta_storica",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        preview = client.get(f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/visualizza")
        download = client.get(f"/fascicoli/{fascicolo.id}/documenti/{eml.id}/scarica")

    assert preview.status_code == 200
    assert preview.mimetype == "text/html"
    assert "Email PEC / EML" in preview.data.decode("utf-8")
    assert "Messaggio acquisito" in preview.data.decode("utf-8")
    assert download.status_code == 200
    assert ".eml" in download.headers["Content-Disposition"].casefold()


def test_elimina_documenti_multipli_rimuove_senza_flash_ripetuti(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    doc1 = gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, b"%PDF-1.4")
    doc2 = gf.aggiungi_documento(fascicolo.id, "verbale.pdf", TipoDocumento.VERBALE, b"%PDF-1.4")

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/elimina-multipla",
            data={"documenti_ids": f"{doc1.id},{doc2.id}", "next_section": "sezione-documenti-fascicolo"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/fascicoli/{fascicolo.id}#sezione-documenti-fascicolo")
    assert not GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id).documenti


def test_elimina_attivita_resta_nella_sezione_operativa(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    att = gf.aggiungi_attivita(fascicolo.id, TipoAttivita.ALTRO, "2026-05-10", "Deposito note")

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.post(
            f"/fascicoli/{fascicolo.id}/attivita/{att.id}/elimina",
            data={"next_section": "sezione-attivita-processuali"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/fascicoli/{fascicolo.id}#sezione-attivita-processuali")
    assert not GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id).attivita


def test_catalogo_portale_non_viene_contato_come_documento_acquisito(fascicolo_ux):
    from web.app import create_app

    cfg, fascicolo = fascicolo_ux
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    documento_portale = {
        "id_documento": "32970605",
        "nome": "VerbaleUdienza_32970605.pdf",
        "tipo": "VerbaleUdienza",
        "data_deposito": "2026-04-25T16:55:42",
        "mittente": "Cancelleria",
        "dimensione_bytes": 104000,
    }
    gf.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="POLISWEB",
        id_deposito_esterno="pst:JPW_SICID:32970605-A",
        tipo_atto="VerbaleUdienza",
        data_deposito="2026-04-25T16:55:42",
        mittente="Cancelleria",
        servizio_portale="PST",
        documenti_portale=[documento_portale],
    )
    gf.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="POLISWEB",
        id_deposito_esterno="pst:JPW_SICID:32970605-B",
        tipo_atto="VerbaleUdienza",
        data_deposito="25/04/2026 16:55",
        mittente="Cancelleria",
        servizio_portale="PST",
        documenti_portale=[{**documento_portale, "data_deposito": "25/04/2026 16:55"}],
    )

    aggiornato = gf.get(fascicolo.id)
    workspace = build_fascicolo_workspace(aggiornato)
    document_management = build_document_management_summary(aggiornato)
    assert workspace["counts"]["documenti"] == 0
    assert workspace["counts"]["documenti_catalogo_portale"] == 1
    assert workspace["counts"]["documenti_governati"] == 1
    assert document_management["stats"]["catalogo_portale"] == 1
    assert document_management["stats"]["portale_classificati"] == 1
    assert "metadati del catalogo portale" in document_management["next_action"]

    app = create_app(cfg)
    with app.test_client() as client:
        _login(client)
        response = client.get(f"/fascicoli/{fascicolo.id}")
        legacy_response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1")
        react_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/documenti")

    body = response.data.decode("utf-8")
    legacy_body = legacy_response.data.decode("utf-8")
    react_payload = react_response.get_json()
    assert response.status_code == 200
    assert legacy_response.status_code == 200
    assert react_response.status_code == 200
    assert '<div id="root"></div>' in body
    assert "Nessun documento caricato" in legacy_body
    assert "Non sono file salvati nel fascicolo" in legacy_body
    assert "Catalogo portale 1" in legacy_body
    assert "1 metadato" in legacy_body
    assert "Metadati portale 1" in legacy_body
    assert "0/1 file acquisiti" in legacy_body
    assert "2 metadati" not in legacy_body
    assert len(react_payload["documents"]) == 1
    assert react_payload["documents"][0]["name"] == "VerbaleUdienza_32970605.pdf"
    assert react_payload["documents"][0]["statusLabel"] == "Da acquisire"
    assert react_payload["documents"][0]["portalDate"] == "25/04/2026"
