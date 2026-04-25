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

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert 'id="docBulkDeleteForm"' in body
    assert 'id="modalConfermaAzioneFascicolo"' in body
    assert "_prepareFascicoloDeleteForms" in body
    assert 'data-bs-target="#collapse-sezione-cabina-fascicolo"' in body
    assert 'class="collapse show" id="collapse-sezione-cabina-fascicolo"' in body
    assert 'data-bs-target="#modalDettaglioAttivita' in body
    assert "elimina_attivita_fascicolo" not in body
    assert "/attivita/" in body and "/elimina" in body


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

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Nessun documento caricato" in body
    assert "Non sono file salvati nel fascicolo" in body
    assert "Catalogo portale 1" in body
    assert "1 metadato" in body
    assert "Metadati portale 1" in body
    assert "0/1 file acquisiti" in body
    assert "2 metadati" not in body
