import os
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.deposito_guidato import OrchestratoreDepositoGuidato
from pct.deposito_simulazione import SIMULATED_DEPOSIT_NOTE_MARKER
from pct.fascicoli import EsitoDepositoPCT, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry
from pct.pst_catalog import (
    PST_SICI_XSD_20260611_NEW_ACT,
    PST_SICI_XSD_20260611_NEW_OBJECT_CODE,
    PST_SICI_XSD_20260611_STATUS,
    PST_WEB_SERVICES_DOC_VERSION,
    get_xsd_channels,
)
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


def _cades_signed_payload(documento: bytes) -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Deposito Guidato")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    signed_attrs = local_signer_mod._build_signed_attrs_der_inline(documento)
    signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
    return _build_cades_bes(
        documento=documento,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs,
        detached=False,
    )


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


def test_pst_xsd_sici_20260611_tracciato_come_anticipazione_non_in_esercizio():
    assert PST_SICI_XSD_20260611_STATUS == "anticipated_not_production"
    assert PST_SICI_XSD_20260611_NEW_ACT == "RichiestaVerbaleSINDACA"
    assert PST_SICI_XSD_20260611_NEW_OBJECT_CODE == "110046"
    assert codice_oggetto_pst_entry("110046") is None

    channels = {channel.key: channel for channel in get_xsd_channels()}
    preview = channels["SICI_20260611_PREVIEW"]
    assert preview.production_ready is False
    assert preview.status == "preview"
    assert "11/06/2026" in preview.changelog_name


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
        _cades_signed_payload(_pdf_base()),
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
    assert run.snapshot["pst_busta_audit"]["transport_mode"] == "atto_enc_non_generato"
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
        email="avvocato@example.invalid",
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
        _cades_signed_payload(_pdf_base()),
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
    assert data["validation"]["semaforo"]["documentale"] == "warning"
    assert data["validation"]["semaforo"]["giuridico"] == "warning"
    assert not any(issue["code"] == "indice_non_rilevato" for issue in data["validation"]["issues"])
    assert data["validation"]["snapshot"]["pst_webservices_doc_version"] == PST_WEB_SERVICES_DOC_VERSION
    assert data["validation"]["context"]["codice_oggetto_pst"] == "014001"
    assert data["validation"]["snapshot"]["pst_busta_audit"]["transport_mode"] == "atto_enc_non_generato"
    assert data["validation"]["snapshot"]["pst_busta_audit"]["indice_busta_generated"] is True
    assert data["validation"]["snapshot"]["pst_busta_audit"]["indice_busta_filename"] == "IndiceBusta.xml"
    assert data["validation"]["snapshot"]["pst_busta_audit"]["indice_documenti_filename"] == "IndiceDocumentiDepositati.PDF"


def test_generazione_busta_usa_codice_oggetto_pst_validato(tmp_path, monkeypatch):
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
        email="avvocato@example.invalid",
    )
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = gf.nuovo(
        titolo="Ricorso lavoro carta docente",
        tipo=TipoFascicolo.LAVORO,
        tribunale="Tribunale di Palmi",
        numero_rg="1754",
        anno_rg=2026,
        controparte="Ministero",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "Ricorso.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        _cades_signed_payload(_pdf_base()),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "Procura.PDF",
        TipoDocumento.PROCURA,
        _cades_signed_payload(_pdf_base()),
        firmato=True,
    )
    captured: dict[str, str] = {}

    def _fake_crea_busta(self, output_dir):
        captured["oggetto"] = self.dati.oggetto
        captured["allegati"] = ",".join(allegato.descrizione for allegato in self.dati.allegati)
        target = Path(output_dir) / "Atto.enc"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ENC")
        return str(target)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", _fake_crea_busta)
    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fasc.id}/deposito/genera-busta",
            data={
                "tipo_atto": "RICORSO",
                "codice_registro": "RGL",
                "oggetto": "Ricorso lavoro carta docente",
                "codice_oggetto_pst": "222050 - Retribuzione",
                "numero_rg": "1754",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "allegati_ids": [procura.id],
                "documenti_selezionati_ids": [atto.id, procura.id],
            },
        )

    assert response.status_code == 200
    assert captured["oggetto"] == "222050"
    assert captured["allegati"] == "Procura.PDF"


def test_generazione_busta_blocca_se_selezione_video_non_coincide_con_busta(tmp_path, monkeypatch):
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
        email="avvocato@example.invalid",
    )
    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = gf.nuovo(
        titolo="Ricorso lavoro carta docente",
        tipo=TipoFascicolo.LAVORO,
        tribunale="Tribunale di Palmi",
        numero_rg="1754",
        anno_rg=2026,
        controparte="Ministero",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "Ricorso.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        _cades_signed_payload(_pdf_base()),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "Procura.PDF",
        TipoDocumento.PROCURA,
        _cades_signed_payload(_pdf_base()),
        firmato=True,
    )
    ricevuta = gf.aggiungi_documento(
        fasc.id,
        "Ricevuta accettazione.eml",
        TipoDocumento.COMUNICAZIONE,
        b"Subject: ricevuta",
        firmato=False,
    )

    def _fake_crea_busta(self, output_dir):
        raise AssertionError("La busta non deve essere generata se la selezione visuale diverge")

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", _fake_crea_busta)
    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fasc.id}/deposito/genera-busta",
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
            data={
                "tipo_atto": "RICORSO",
                "codice_registro": "RGL",
                "oggetto": "Ricorso lavoro carta docente",
                "codice_oggetto_pst": "222050 - Retribuzione",
                "numero_rg": "1754",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "allegati_ids": [procura.id],
                "documenti_selezionati_ids": [atto.id, procura.id, ricevuta.id],
            },
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "selezione a video" in payload["errore"]
    assert ricevuta.id in payload["errore"]


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
        _cades_signed_payload(_pdf_base()),
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


def test_orchestratore_pct_contributo_mancante_usa_policy_pagopa_pst(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Ricorso civile senza ricevuta",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        controparte="Alfa S.r.l.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "ricorso.pdf",
        TipoDocumento.RICORSO,
        _cades_signed_payload(_pdf_base()),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
        firmato=False,
    )
    notifica = gf.aggiungi_documento(
        fasc.id,
        "relata_notifica.pdf",
        TipoDocumento.NOTIFICA,
        _pdf_base(),
        firmato=False,
    )
    docs = [
        _doc_payload(gf, fasc.id, atto),
        _doc_payload(gf, fasc.id, procura),
        _doc_payload(gf, fasc.id, notifica),
    ]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "RG",
            "oggetto": "Ricorso civile introduttivo",
            "codice_oggetto_pst": "011001",
            "atto_principale_id": atto.id,
            "allegati_ids": [procura.id, notifica.id],
            "operatore": "avv.rossi",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    issue = next(item for item in run.issues if item["code"] == "contributo_non_evidenziato")
    assert "pst.giustizia.it" in issue["source"]
    assert "RT.xml" in issue["detail"]
    assert "pagoPA" in issue["suggested_action"]
    assert "promemoria PDF non sostituisce la RT" in issue["suggested_action"]


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
        email="avvocato@example.invalid",
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
        _cades_signed_payload(_pdf_base()),
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
        legacy_response = client.get(f"/fascicoli/{fasc.id}/deposito/prepara?_legacy=1")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<html lang="it" class="react-shell-document">' in html
    assert 'id="root"' in html
    assert "Prepara deposito" not in html

    assert legacy_response.status_code == 200
    legacy_html = legacy_response.get_data(as_text=True)
    assert "Deposito" in legacy_html
    assert "RG 1025/2024" in legacy_html
    assert f"Interno {fasc.numero}" in legacy_html
    assert 'const correctionContext = {"active": false' in legacy_html
    assert "_arrayBufferToBase64Safe" in legacy_html
    assert "_base64ToUint8ArraySafe" in legacy_html
    assert "String.fromCharCode(...new Uint8Array(buf))" not in legacy_html


def test_deposito_prova_genera_ricevuta_accettazione_senza_invio_reale(tmp_path):
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
        titolo="Comparsa prova deposito",
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
        _cades_signed_payload(_pdf_base()),
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
            f"/fascicoli/{fasc.id}/deposito/invia",
            data={
                "demo_mode": "1",
                "tipo_atto": "COMPARSA_RISPOSTA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Comparsa di costituzione e risposta",
                "numero_rg": "204",
                "anno_rg": "2025",
                "tribunale_nome": "Tribunale di Palmi",
                "atto_principale_id": atto.id,
                "allegati_ids": [procura.id],
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc_reload = gf_reload.get(fasc.id)
    assert fasc_reload is not None
    assert len(fasc_reload.depositi_pct) == 1
    deposito = fasc_reload.depositi_pct[0]
    assert deposito.stato == "INVIATO"
    assert SIMULATED_DEPOSIT_NOTE_MARKER in deposito.note
    assert deposito.ricevuta_accettazione == ""

    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        receipt_response = client.post(
            f"/api/fascicoli/{fasc.id}/depositi/{deposito.id}/simula-ricevuta",
            data={"fase": "accettazione"},
        )
        consegna_response = client.post(
            f"/api/fascicoli/{fasc.id}/depositi/{deposito.id}/simula-ricevuta",
            data={"fase": "consegna"},
        )
        controlli_response = client.post(
            f"/api/fascicoli/{fasc.id}/depositi/{deposito.id}/simula-ricevuta",
            data={"fase": "controlli"},
        )
        conferma_response = client.post(
            f"/api/fascicoli/{fasc.id}/depositi/{deposito.id}/simula-ricevuta",
            data={"fase": "cancelleria"},
        )

    assert receipt_response.status_code == 200
    payload = receipt_response.get_json()
    assert payload["ok"] is True
    assert payload["simulazione"] is True
    assert payload["fase"] == "accettazione"
    assert payload["stato"] == "ACCETTATO_PEC"
    assert payload["ricevuta_accettazione"] is True
    assert payload["prossima_fase"] == "consegna"
    assert consegna_response.get_json()["stato"] == "CONSEGNATO"
    controlli_payload = controlli_response.get_json()
    assert controlli_payload["stato"] == "WARN_CONTROLLI"
    assert controlli_payload["ricevuta_controlli"] is True
    conferma_payload = conferma_response.get_json()
    assert conferma_payload["stato"] == "ACCETTATO_CANCELLERIA"
    assert conferma_payload["ricevuta_cancelleria"] is True
    assert conferma_payload["prossima_fase"] == "completo"

    gf_receipts = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc_after_receipt = gf_receipts.get(fasc.id)
    assert fasc_after_receipt is not None
    deposito_reload = fasc_after_receipt.depositi_pct[0]
    ricevuta = deposito_reload.ricevuta_accettazione
    assert "Messaggio di posta certificata" in ricevuta
    assert "daticert.xml" in ricevuta
    assert "EsitoAtto.xml" in ricevuta
    assert "postacert.eml" in ricevuta
    assert "smime.p7s" in ricevuta
    assert "studio-legale@pec.invalid" in ricevuta
    assert "@pec.it" not in ricevuta
    assert "ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO" in deposito_reload.ricevuta_controlli_automatici
    assert "<CodiceEsito>-1</CodiceEsito>" in deposito_reload.ricevuta_controlli_automatici
    assert "NOME FILE: documento_allegato.pdf" in deposito_reload.ricevuta_controlli_automatici
    assert deposito_reload.ricevuta_consegna
    assert deposito_reload.ricevuta_cancelleria
    assert deposito_reload.stato == "ACCETTATO_CANCELLERIA"


def test_ricevuta_prova_rifiuta_depositi_non_simulati(tmp_path):
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
        titolo="Deposito reale da proteggere",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="204",
        anno_rg=2025,
    )
    fasc.depositi_pct.append(
        EsitoDepositoPCT(
            id="DEP-REALE",
            timestamp="2026-05-27T08:00:00",
            stato="INVIATO",
            tipo_atto="RICORSO",
            pec_destinatario="ufficio@example.pec.it",
            messaggio="Deposito inviato via PEC.",
        )
    )
    gf._salva()

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/api/fascicoli/{fasc.id}/depositi/DEP-REALE/simula-ricevuta",
            data={"fase": "accettazione"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "solo per depositi senza invio reale" in payload["errore"]


def test_orchestratore_blocca_atto_principale_p7m_non_cades_senza_prova_tecnica(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Alessi Robertino c. Zurich",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Giudice di Pace - Palmi",
        numero_rg="466",
        anno_rg=2023,
        controparte="Zurich Ass.ni",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "attoACQ.pdf.p7m",
        TipoDocumento.RICORSO,
        _pdf_base(),
        firmato=False,
    )
    docs = [_doc_payload(gf, fasc.id, atto)]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "RG",
            "oggetto": "Ricorso",
            "codice_oggetto_pst": "222050",
            "numero_rg": "466",
            "anno_rg": 2023,
            "atto_principale_id": atto.id,
            "allegati_ids": [],
            "operatore": "admin",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    codes = {issue["code"] for issue in run.issues}
    assert "atto_principale_non_firmato" in codes
    assert run.semaforo["documentale"] == "blocco"


def test_orchestratore_non_blocca_atto_principale_cades_reale_senza_flag_storico(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Alessi Robertino c. Zurich",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Giudice di Pace - Palmi",
        numero_rg="466",
        anno_rg=2023,
        controparte="Zurich Ass.ni",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "attoACQ.pdf.p7m",
        TipoDocumento.RICORSO,
        _cades_signed_payload(_pdf_base()),
        firmato=False,
    )
    docs = [_doc_payload(gf, fasc.id, atto)]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "RG",
            "oggetto": "Ricorso",
            "codice_oggetto_pst": "222050",
            "numero_rg": "466",
            "anno_rg": 2023,
            "atto_principale_id": atto.id,
            "allegati_ids": [],
            "operatore": "admin",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    codes = {issue["code"] for issue in run.issues}
    assert "atto_principale_non_firmato" not in codes
    assert run.semaforo["documentale"] != "blocco"


def test_orchestratore_non_blocca_atto_principale_cades_cifrato_a_riposo(tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_DOC_KEY", "deposito-guidato-cades-encrypted-test")
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Marchetti c. MIM",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Vicenza",
        numero_rg="332",
        anno_rg=2026,
        controparte="MIM",
        id_cliente="cli-1",
    )
    signed_payload = _cades_signed_payload(_pdf_base())
    atto = gf.aggiungi_documento(
        fasc.id,
        "Ricorso.pdf.p7m",
        TipoDocumento.RICORSO,
        signed_payload,
        firmato=True,
    )
    from web.services.document_crypto import encrypt_doc

    encrypted_payload = encrypt_doc(signed_payload)
    path = gf.percorso_documento(fasc.id, atto.id)
    path.write_bytes(encrypted_payload)
    atto.dimensione_bytes = len(encrypted_payload)
    gf._salva()
    docs = [_doc_payload(gf, fasc.id, atto)]

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "RICORSO",
            "codice_registro": "RG",
            "oggetto": "Ricorso",
            "codice_oggetto_pst": "222050",
            "numero_rg": "332",
            "anno_rg": 2026,
            "atto_principale_id": atto.id,
            "allegati_ids": [],
            "operatore": "admin",
        },
        selected_documents=docs,
        all_documents=docs,
    )

    codes = {issue["code"] for issue in run.issues}
    assert "atto_principale_non_firmato" not in codes
    assert run.semaforo["documentale"] != "blocco"


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
        _cades_signed_payload(_pdf_base()),
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
        _cades_signed_payload(_pdf_base()),
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
        _cades_signed_payload(_pdf_base()),
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
