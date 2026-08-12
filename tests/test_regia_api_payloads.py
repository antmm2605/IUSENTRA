from pathlib import Path

from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
from pct.config_studio import GestioneConfigStudio
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.storage import StudioDB
from tests.regia_test_utils import pdfa_bytes
from tests.test_web_bootstrap import _cfg_web
from web.app import create_app
from web.services.storage_runtime import resolve_storage_runtime


def _cades_signed_payload(documento: bytes) -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes, FirmaPKCS11

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CAdES")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    digest = hashes.Hash(hashes.SHA256())
    digest.update(documento)
    signed_attrs_der = FirmaPKCS11._build_signed_attrs(
        object.__new__(FirmaPKCS11),
        digest.finalize(),
    )
    signature = key.sign(signed_attrs_der, padding.PKCS1v15(), hashes.SHA256())
    return _build_cades_bes(
        documento=documento,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs_der,
        detached=False,
    )


def _app_with_fascicolo(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "regia-test-key"
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Cliente",
        cognome="Regia",
        codice_fiscale="RSSMRA80A01H501U",
    )
    cliente = clienti.aggiorna(
        cliente.id,
        recapiti=Recapiti(email="cliente.regia@example.test"),
        indirizzo_residenza=Indirizzo(via="Via Regia", civico="1", comune="Palmi", provincia="RC"),
    )
    gf = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Regia API",
        tipo=TipoFascicolo.LAVORO,
        id_cliente=cliente.id,
        nome_cliente="Cliente Regia",
        oggetto="Impugnazione licenziamento",
        tribunale="Tribunale di Palmi",
        avvocato="Avv. Regia",
        codice_fiscale_cliente="RSSMRA80A01H501U",
        procedura_operativa_codice="PROC_LIC_IMP_001",
    )
    return app, gf, fascicolo


def test_api_regia_payload_completo_e_mock_false(tmp_path):
    app, _gf, fascicolo = _app_with_fascicolo(tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/regia", headers={"X-API-Key": "regia-test-key"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["source"] == "repository reale"
    assert payload["header"]["title"] == "Regia API"
    assert payload["checklist"]
    assert payload["documentSlots"]
    assert payload["validation"]["blockers"]
    delivery = payload["deposit"]["deliveryPolicy"]
    assert delivery["mode"] == "direct_pec"
    assert delivery["allowsDirectPec"] is True
    assert delivery["directPecReady"] is False
    assert delivery["requiresManualFinalUpload"] is False
    assert delivery["requiresGuidedCompletion"] is True
    assert delivery["packageKind"] == "pct_busta_enc"
    assert delivery["sendButtonLabel"] == "Completa trasporto"
    assert delivery["prepareButtonLabel"] == "Prepara controllo busta"
    assert delivery["immediateBatchSigning"] is True
    assert delivery["documentIndexGeneratedBySoftware"] is True
    assert "Atto.enc" in delivery["missingOperationalStep"]
    assert "AES256" in delivery["missingOperationalStep"]
    assert any("Atto.enc" in action and "AES256" in action for action in delivery["guidedNextActions"])


def test_api_regia_economia_espone_link_operativi(tmp_path):
    app, _gf, fascicolo = _app_with_fascicolo(tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/regia", headers={"X-API-Key": "regia-test-key"})
    assert response.status_code == 200
    economics = response.get_json()["economics"]
    assert economics["preventivoHref"].startswith("/preventivi/nuovo?")
    assert f"id_fascicolo={fascicolo.id}" in economics["preventivoHref"]
    assert economics["conferimentoHref"].startswith("/preventivi/conferimento/nuovo?")
    assert f"id_fascicolo={fascicolo.id}" in economics["conferimentoHref"]
    assert economics["proformaHref"].startswith("/fatturazione/nuova?")
    assert f"id_fascicolo={fascicolo.id}" in economics["proformaHref"]
    assert economics["paymentHref"] == economics["proformaHref"]


def test_api_slot_predeposito_deposito_ricevuta_evidence_pack(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    doc = gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, pdfa_bytes(), firmato=True)
    procura = gf.aggiungi_documento(fascicolo.id, "procura.pdf", TipoDocumento.PROCURA, pdfa_bytes(), firmato=True)
    client = app.test_client()
    headers = {"X-API-Key": "regia-test-key"}

    link = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/ATTO_PRINCIPALE/link",
        json={"document_id": doc.id},
        headers=headers,
    )
    assert link.status_code == 200
    assert link.get_json()["mock_fallback"] is False
    client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/PROCURA/link", json={"document_id": procura.id}, headers=headers)
    validate = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/ATTO_PRINCIPALE/validate", headers=headers)
    assert validate.status_code == 200
    check = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/predeposito/check", headers=headers)
    assert check.status_code == 200
    prepare = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/prepara", headers=headers)
    assert prepare.status_code == 200
    deposito_id = prepare.get_json()["session"]["id"]
    send = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/invia", json={"deposito_id": deposito_id}, headers=headers)
    assert send.status_code == 409
    assert send.get_json()["mock_fallback"] is False
    receipt = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/importa-ricevuta",
        json={"receipt_type": "ESITO_CANCELLERIA", "status": "accettato", "positive": True, "message": "Esito cancelleria positivo"},
        headers=headers,
    )
    assert receipt.status_code == 200
    assert receipt.get_json()["session"]["status"] == "ACQUISITO"
    timeline = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/timeline", headers=headers)
    assert timeline.status_code == 200
    assert timeline.get_json()["timeline"]
    evidence = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/evidence-pack", headers=headers)
    assert evidence.status_code == 200
    assert evidence.mimetype == "application/zip"


def test_api_deposito_classifica_documenti_collega_slot_e_metadati(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    atto = gf.aggiungi_documento(fascicolo.id, "ricorso lavoro.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    procura = gf.aggiungi_documento(fascicolo.id, "procura.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    prova = gf.aggiungi_documento(fascicolo.id, "contratto 24-25.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    fuori = gf.aggiungi_documento(fascicolo.id, "comunicazione cancelleria.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    client = app.test_client()
    headers = {"X-API-Key": "regia-test-key"}

    response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/deposito/classifica-documenti",
        json={
            "documents": [
                {"document_id": atto.id, "selected": True, "role": "atto_principale", "already_signed": False},
                {"document_id": procura.id, "selected": True, "role": "procura", "already_signed": True},
                {"document_id": prova.id, "selected": True, "role": "allegato_prova", "already_signed": False},
                {"document_id": fuori.id, "selected": False, "role": "fuori_busta", "already_signed": False},
            ]
        },
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["selectedCount"] == 3
    assert "ATTO_PRINCIPALE" in payload["linkedSlots"]
    assert "PROCURA" in payload["linkedSlots"]
    assert any(slot for slot in payload["linkedSlots"] if slot not in {"ATTO_PRINCIPALE", "PROCURA"})
    assert any(row["role"] == "allegato" for row in payload["updatedDocuments"] if row["documentId"] == prova.id)
    assert payload["regia"]["documentSlots"]

    with app.app_context():
        storage = resolve_storage_runtime(anchor_path=app.config["FASCICOLI_DB"])
        studio_db = StudioDB.get(storage.studio_db_path) if storage.uses_sqlite else None
    aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
        studio_db=studio_db,
    )._get_o_errore(fascicolo.id)
    docs = {doc.id: doc for doc in aggiornato.documenti}
    assert docs[atto.id].tipo == TipoDocumento.ATTO_GIUDIZIARIO
    assert docs[procura.id].tipo == TipoDocumento.PROCURA
    assert docs[prova.id].tipo == TipoDocumento.ALLEGATO
    assert docs[procura.id].firmato_digitalmente is False
    assert docs[fuori.id].tipo == TipoDocumento.ALTRO


def test_api_deposito_salva_qualifica_professionista_nel_fascicolo_e_nello_studio(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    atto = gf.aggiungi_documento(fascicolo.id, "ricorso.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    client = app.test_client()

    response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/deposito/classifica-documenti",
        json={
            "tipo_deposito_telematico_key": "Introduttivi_SICID::Ricorso",
            "datiatto_extra": {"professionista_ruolo": "AVV."},
            "documents": [{"document_id": atto.id, "selected": True, "role": "atto_principale"}],
        },
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 200
    aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )._get_o_errore(fascicolo.id)
    preparazione = aggiornato.profilo_deposito["preparazione_busta"]
    assert preparazione["datiatto_extra"]["professionista_ruolo"] == "AVV."
    assert GestioneConfigStudio(app.config["STUDIO_CONFIG"]).config.studio.deposito_telematico_role == "AVV."


def test_api_deposito_rifiuta_qualifica_non_prevista_dal_decompilato(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    atto = gf.aggiungi_documento(fascicolo.id, "ricorso.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    response = app.test_client().post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/deposito/classifica-documenti",
        json={
            "tipo_deposito_telematico_key": "Introduttivi_SICID::Ricorso",
            "datiatto_extra": {"professionista_ruolo": "RUOLO_INVENTATO"},
            "documents": [{"document_id": atto.id, "selected": True, "role": "atto_principale"}],
        },
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 400
    assert response.get_json()["errore"] == "La qualifica del professionista non è valida per il tipo di deposito selezionato."


def test_preparazione_deposito_salva_una_sola_riga_in_unica_transazione(tmp_path, monkeypatch):
    studio_db = StudioDB.get(str(tmp_path / "studio.db"))
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )
    fascicolo = gf.nuovo(titolo="Deposito atomico", tipo=TipoFascicolo.LAVORO)
    documento = gf.aggiungi_documento(
        fascicolo.id,
        "ricorso.pdf",
        TipoDocumento.ALTRO,
        pdfa_bytes(),
        firmato=False,
    )
    calls: list[tuple[str, int, bool]] = []
    original_salva_tabella = studio_db.salva_tabella

    def _record_salva_tabella(table, rows, inserter, delete_all=True):
        calls.append((table, len(rows), bool(delete_all)))
        return original_salva_tabella(table, rows, inserter, delete_all=delete_all)

    monkeypatch.setattr(studio_db, "salva_tabella", _record_salva_tabella)

    aggiornato = gf.aggiorna_preparazione_deposito(
        fascicolo.id,
        document_updates=[{"id_doc": documento.id, "tipo": TipoDocumento.ATTO_GIUDIZIARIO.value}],
        profilo_deposito={"preparazione_busta": {"tipo_deposito_telematico_key": "OpposizioneDILavoro"}},
    )

    assert calls == [("fascicoli", 1, False)]
    assert aggiornato.documenti[0].tipo == TipoDocumento.ATTO_GIUDIZIARIO
    assert aggiornato.profilo_deposito["preparazione_busta"]["tipo_deposito_telematico_key"] == "OpposizioneDILavoro"
    ricaricato = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
        studio_db=studio_db,
    )._get_o_errore(fascicolo.id)
    assert ricaricato.documenti[0].tipo == TipoDocumento.ATTO_GIUDIZIARIO
    assert ricaricato.profilo_deposito == aggiornato.profilo_deposito


def test_api_deposito_classifica_documenti_non_richiede_firma_su_contenitore_p7m(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    p7m = gf.aggiungi_documento(fascicolo.id, "Procura.PDF.p7m", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)
    client = app.test_client()

    response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/deposito/classifica-documenti",
        json={
            "documents": [
                {
                    "document_id": p7m.id,
                    "selected": True,
                    "role": "procura",
                    "already_signed": False,
                    "requires_signature": True,
                }
            ]
        },
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    row = next(item for item in payload["updatedDocuments"] if item["documentId"] == p7m.id)
    assert row["alreadySigned"] is True
    assert row["requiresSignature"] is False

    aggiornato = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )._get_o_errore(fascicolo.id)
    doc = next(item for item in aggiornato.documenti if item.id == p7m.id)
    assert doc.firmato_digitalmente is False

def test_api_deposito_classifica_documenti_non_cade_se_profilo_da_confermare(tmp_path, monkeypatch):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    atto = gf.aggiungi_documento(fascicolo.id, "atto da confermare.pdf", TipoDocumento.ALTRO, pdfa_bytes(), firmato=False)

    resolver_payload = {
        "profile": None,
        "confidence": 0.0,
        "reason": "profilo non determinabile automaticamente",
        "alternatives": [],
        "needs_manual_confirmation": True,
    }

    def _no_profile(*_args, **_kwargs):
        return None, resolver_payload

    monkeypatch.setattr("web.blueprints.api_v1_react.ensure_profile_for_fascicolo", _no_profile)
    monkeypatch.setattr("pct.practice_engine.evaluator.ensure_profile_for_fascicolo", _no_profile)

    client = app.test_client()
    response = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/deposito/classifica-documenti",
        json={"documents": [{"document_id": atto.id, "selected": True, "role": "atto_principale"}]},
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["selectedCount"] == 1
    assert payload["linkedSlots"] == []
    assert payload["regia"]["page_state"] == "profilo_da_confermare"
    assert "Classificazione deposito salvata" in payload["message"]


def test_api_fascicolo_mostra_p7m_solo_con_firma_reale(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    firmato = gf.aggiungi_documento(
        fascicolo.id,
        "Memoria.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=False,
        nome_originale="Memoria.pdf.p7m",
        nome_archivio="Memoria.pdf.p7m",
    )
    flag_storico = gf.aggiungi_documento(
        fascicolo.id,
        "Autocertificazione ricorso.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=True,
    )
    nome_ingannevole = gf.aggiungi_documento(
        fascicolo.id,
        "Ricorso Firmato digitale.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=True,
    )
    metadato_generico = gf.aggiungi_documento(
        fascicolo.id,
        "Comparsa con signed true.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=True,
    )
    metadato_generico.signature_metadata = {"signed": True}
    pades = gf.aggiungi_documento(
        fascicolo.id,
        "Memoria autorizzata.PDF",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=True,
    )
    gf.segna_firmato(
        fascicolo.id,
        pades.id,
        signature_metadata={"signature_format": "PAdES", "signature_verified": True, "pades_verified": True},
    )
    gf._salva()
    client = app.test_client()

    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}?include=all",
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 200
    documents = {doc["id"]: doc for doc in response.get_json()["documents"]}
    assert documents[firmato.id]["name"] == "Memoria.pdf.p7m"
    assert documents[firmato.id]["signed"] is False
    assert documents[firmato.id]["statusLabel"] == "Da firmare"
    assert documents[flag_storico.id]["name"] == "Autocertificazione ricorso.PDF"
    assert documents[flag_storico.id]["signed"] is False
    assert documents[flag_storico.id]["statusLabel"] == "Da firmare"
    assert documents[nome_ingannevole.id]["name"] == "Ricorso Firmato digitale.PDF"
    assert documents[nome_ingannevole.id]["signed"] is False
    assert documents[nome_ingannevole.id]["statusLabel"] == "Da firmare"
    assert documents[metadato_generico.id]["signed"] is False
    assert documents[metadato_generico.id]["statusLabel"] == "Da firmare"
    assert documents[pades.id]["name"] == "Memoria autorizzata.PDF"
    assert documents[pades.id]["signed"] is True
    assert documents[pades.id]["statusLabel"] == "Firmato"


def test_api_fascicolo_verifica_p7m_cifrato_a_riposo(tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_DOC_KEY", "regia-encrypted-cades-test")
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    signed_payload = _cades_signed_payload(pdfa_bytes())
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "Ricorso.pdf.p7m",
        TipoDocumento.ATTO_GIUDIZIARIO,
        signed_payload,
        firmato=True,
    )
    from web.services.document_crypto import encrypt_doc

    encrypted_payload = encrypt_doc(signed_payload)
    path = gf.percorso_documento(fascicolo.id, doc.id)
    path.write_bytes(encrypted_payload)
    doc.dimensione_bytes = len(encrypted_payload)
    gf._salva()

    client = app.test_client()
    response = client.get(
        f"/api/v1/ui/fascicoli/{fascicolo.id}?include=all",
        headers={"X-API-Key": "regia-test-key"},
    )

    assert response.status_code == 200
    documents = {item["id"]: item for item in response.get_json()["documents"]}
    assert documents[doc.id]["signed"] is True
    assert documents[doc.id]["statusLabel"] == "Firmato"
