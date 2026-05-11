import os
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.deposito_guidato import OrchestratoreDepositoGuidato
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pst_catalog import PST_WEB_SERVICES_DOC_VERSION
from web.app import create_app


def _pdf_base(pdfa_part: str = "2", pdfa_conf: str = "B") -> bytes:
    xmp = (
        b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description xmlns:pdfaid='http://www.aiim.org/pdfa/ns/id/'>"
        b"<pdfaid:part>" + pdfa_part.encode() + b"</pdfaid:part>"
        b"<pdfaid:conformance>" + pdfa_conf.encode() + b"</pdfaid:conformance>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    return b"%PDF-1.4\n" + xmp + b"\n%%EOF"


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
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
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
    }


def _doc_payload(gf: GestioneFascicoli, fasc_id: str, doc) -> dict:
    return {
        "id": doc.id,
        "nome": doc.nome,
        "tipo": doc.tipo.value,
        "percorso": str(gf.percorso_documento(fasc_id, doc.id)),
        "dimensione_bytes": doc.dimensione_bytes,
        "firmato_digitalmente": doc.firmato_digitalmente,
    }


def test_orchestratore_blocca_comparsa_senza_procura(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Comparsa Rossi c. Banca Alfa",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Banca Alfa S.p.A.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "comparsa.pdf",
        TipoDocumento.COMPARSA,
        _pdf_base(),
        firmato=True,
    )

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "COMPARSA_RISPOSTA",
            "codice_registro": "RG",
            "oggetto": "Comparsa di costituzione e risposta",
            "codice_oggetto_pst": "014001",
            "numero_rg": "1025",
            "anno_rg": 2024,
            "atto_principale_id": atto.id,
            "allegati_ids": [],
            "operatore": "avv.rossi",
        },
        selected_documents=[
            {
                "id": atto.id,
                "nome": atto.nome,
                "tipo": atto.tipo.value,
                "percorso": str(gf.percorso_documento(fasc.id, atto.id)),
                "dimensione_bytes": atto.dimensione_bytes,
                "firmato_digitalmente": atto.firmato_digitalmente,
            }
        ],
        all_documents=[
            {
                "id": atto.id,
                "nome": atto.nome,
                "tipo": atto.tipo.value,
                "percorso": str(gf.percorso_documento(fasc.id, atto.id)),
                "dimensione_bytes": atto.dimensione_bytes,
                "firmato_digitalmente": atto.firmato_digitalmente,
            }
        ],
    )

    assert run.can_prepare_deposit is False
    assert run.semaforo["giuridico"] == "blocco"
    assert any(issue["code"] == "procura_mancante" for issue in run.issues)
    assert run.snapshot["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION
    assert run.resolver["pst_official_catalog"]["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION
    assert "pst_official_runtime" in run.resolver
    assert "getRegistriFromUfficio" in run.resolver["pst_official_runtime"]["methods"] or run.resolver["pst_official_runtime"]["methods"] == {}
    assert "effective_allowed_registries" in run.resolver
    assert run.snapshot["pst_busta_audit"]["transport_mode"] == "simulazione_zip_rinominato"
    assert run.snapshot["pst_busta_audit"]["formal_checks"]["T003"]["status"] == "ok"


def test_api_validazione_deposito_restituisce_semaforo_e_consente_con_warning(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
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
    fasc = gf.nuovo(
        titolo="Comparsa di risposta demo",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="204",
        anno_rg=2025,
        controparte="Alfa S.r.l.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "comparsa.pdf",
        TipoDocumento.COMPARSA,
        _pdf_base(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
        firmato=False,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/api/fascicoli/{fasc.id}/deposito/valida",
            data={
                "tipo_atto": "COMPARSA_RISPOSTA",
                "codice_registro": "RG",
                "oggetto": "Comparsa di costituzione e risposta",
                "codice_oggetto_pst": "014001",
                "numero_rg": "204",
                "anno_rg": "2025",
                "atto_principale_id": atto.id,
                "allegati_ids": [procura.id],
            },
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["validation"]["can_prepare_deposit"] is True
    assert data["validation"]["semaforo"]["tecnico_pst"] == "ok"
    assert data["validation"]["semaforo"]["documentale"] == "ok"
    assert data["validation"]["semaforo"]["giuridico"] == "warning"
    assert any(issue["code"] == "indice_non_rilevato" for issue in data["validation"]["issues"])
    assert data["validation"]["snapshot"]["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION
    assert data["validation"]["context"]["codice_oggetto_pst"] == "014001"
    assert data["validation"]["snapshot"]["pst_busta_audit"]["transport_mode"] == "simulazione_zip_rinominato"


def test_orchestratore_blocca_deposito_pct_senza_codice_oggetto_pst(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Comparsa senza codice oggetto",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="204",
        anno_rg=2025,
        controparte="Alfa S.r.l.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "comparsa.pdf",
        TipoDocumento.COMPARSA,
        _pdf_base(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
        firmato=False,
    )

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "COMPARSA_RISPOSTA",
            "codice_registro": "RG",
            "oggetto": "Comparsa di costituzione e risposta",
            "numero_rg": "204",
            "anno_rg": 2025,
            "atto_principale_id": atto.id,
            "allegati_ids": [procura.id],
            "operatore": "avv.rossi",
        },
        selected_documents=[
            _doc_payload(gf, fasc.id, atto),
            _doc_payload(gf, fasc.id, procura),
        ],
        all_documents=[
            _doc_payload(gf, fasc.id, atto),
            _doc_payload(gf, fasc.id, procura),
        ],
    )

    assert run.can_prepare_deposit is False
    codes = {issue["code"] for issue in run.issues}
    assert "codice_oggetto_pst_mancante" in codes
    assert "xml_codice_oggetto_mancante" in codes


def test_pagina_deposito_prepara_renderizza_anche_senza_correction_query(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
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
    fasc = gf.nuovo(
        titolo="Deposito introduttivo demo",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Alfa S.r.l.",
        id_cliente="cli-1",
    )
    gf.aggiungi_documento(
        fasc.id,
        "atto_principale.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        _pdf_base(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fasc.id}/deposito/prepara")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Deposito" in html
    assert "RG 1025/2024" in html
    assert f"Interno {fasc.numero}" in html
    assert 'const correctionContext = {"active": false' in html
    assert "_arrayBufferToBase64Safe" in html
    assert "_base64ToUint8ArraySafe" in html
    assert "String.fromCharCode(...new Uint8Array(buf))" not in html


def test_orchestratore_tributario_consente_prededeposito_con_nir(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Ricorso tributario demo",
        tipo=TipoFascicolo.TRIBUTARIO,
        tribunale="CPT Milano",
        numero_rg="321",
        anno_rg=2026,
        controparte="Agenzia delle Entrate",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "ricorso_tributario.pdf.p7m",
        TipoDocumento.RICORSO,
        _pdf_base(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura_alle_liti.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
    )
    notifica = gf.aggiungi_documento(
        fasc.id,
        "relata_notifica_ente.pdf",
        TipoDocumento.NOTIFICA,
        _pdf_base(),
    )
    contributo = gf.aggiungi_documento(
        fasc.id,
        "ricevuta_contributo_unificato.pdf",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
    )
    indice = gf.aggiungi_documento(
        fasc.id,
        "indice_documenti.pdf",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
    )
    nir = gf.aggiungi_documento(
        fasc.id,
        "NIR_nota_iscrizione_a_ruolo_firmata.pdf.p7m",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
        firmato=True,
    )
    docs = [
        _doc_payload(gf, fasc.id, atto),
        _doc_payload(gf, fasc.id, procura),
        _doc_payload(gf, fasc.id, notifica),
        _doc_payload(gf, fasc.id, contributo),
        _doc_payload(gf, fasc.id, indice),
        _doc_payload(gf, fasc.id, nir),
    ]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "PTT_RICORSI",
            "oggetto": "Ricorso tributario contro avviso di accertamento",
            "numero_rg": "",
            "anno_rg": "",
            "atto_principale_id": atto.id,
            "allegati_ids": [procura.id, notifica.id, contributo.id, indice.id, nir.id],
            "operatore": "avv.rossi",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    codes = {issue["code"] for issue in run.issues}
    assert run.channel == "PTT_TRIBUTARIO"
    assert run.profile_id == "ricorso_tributario"
    assert run.can_prepare_deposit is True
    assert run.semaforo["giuridico"] != "blocco"
    assert run.semaforo["tecnico_pst"] == "warning"
    assert "nir_tributaria_mancante" not in codes
    assert "canale_non_depositabile" not in codes
    assert "schema_non_pct" not in codes
    assert "schema_sigit_formweb" in codes


def test_orchestratore_tributario_blocca_ricorso_senza_nir(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Ricorso tributario senza NIR",
        tipo=TipoFascicolo.TRIBUTARIO,
        tribunale="CPT Milano",
        numero_rg="654",
        anno_rg=2026,
        controparte="Agenzia delle Entrate",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "ricorso_tributario.pdf.p7m",
        TipoDocumento.RICORSO,
        _pdf_base(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura_alle_liti.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
    )
    notifica = gf.aggiungi_documento(
        fasc.id,
        "relata_notifica_ente.pdf",
        TipoDocumento.NOTIFICA,
        _pdf_base(),
    )
    contributo = gf.aggiungi_documento(
        fasc.id,
        "ricevuta_contributo_unificato.pdf",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
    )
    docs = [
        _doc_payload(gf, fasc.id, atto),
        _doc_payload(gf, fasc.id, procura),
        _doc_payload(gf, fasc.id, notifica),
        _doc_payload(gf, fasc.id, contributo),
    ]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "PTT_RICORSI",
            "oggetto": "Ricorso tributario contro avviso di accertamento",
            "numero_rg": "",
            "anno_rg": "",
            "atto_principale_id": atto.id,
            "allegati_ids": [procura.id, notifica.id, contributo.id],
            "operatore": "avv.rossi",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    assert run.can_prepare_deposit is False
    assert run.semaforo["giuridico"] == "blocco"
    assert any(issue["code"] == "nir_tributaria_mancante" for issue in run.issues)
