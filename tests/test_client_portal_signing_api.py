"""Test del workflow professionale di firma del Portale Cliente.

Copre i requisiti di sicurezza del flusso: flag default-off fail-closed,
token risolto lato server, evidence con hash e mai al cliente, conferimento
gate-ato dall'accettazione preventivo, consensi obbligatori, PDF originale
immutato, fallback upload firmato, documento identità con consenso.
"""

from __future__ import annotations

import base64
import io
import sqlite3
from pathlib import Path

from pct.clienti import GestioneClienti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.preventivi import GestionePreventivi, StatoPreventivo, TipoVoce, VocePreventivo
from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


SIGNING_FLAG = "routes.appV2.clientPortal.signingWorkflow"

ALL_SIGNING_CONSENTS = {
    "firma_lettura_documento": True,
    "firma_accettazione_contenuto": True,
    "firma_autorizzazione_applicazione": True,
    "firma_conferma_dati": True,
}

JPEG_1PX = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)


def _app(tmp_path: Path, *, signing_enabled: bool = True):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "client-portal-signing-key"
    if signing_enabled:
        app.config["FEATURE_FLAGS"] = {SIGNING_FLAG: True}
    return app


def _seed_cliente_fascicolo(app):
    with app.app_context():
        clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
        cliente = clienti.nuovo(
            tipo=TipoCliente.PERSONA_FISICA,
            nome="Mario",
            cognome="Rossi",
            codice_fiscale="RSSMRA80A01H501U",
        )
        clienti.aggiorna_recapiti(cliente.id, email="mario.rossi@example.it", cellulare="3331234567")
        fascicoli = GestioneFascicoli(
            db_path=app.config["FASCICOLI_DB"],
            documents_dir=app.config["FASCICOLI_DOCS"],
            archive_dir=app.config["FASCICOLI_ARCH"],
        )
        fascicolo = fascicoli.nuovo(
            "Recupero credito commerciale",
            TipoFascicolo.CIVILE,
            id_cliente=cliente.id,
            nome_cliente=cliente.nome_completo,
        )
    return cliente, fascicolo


def _seed_preventivo(app, cliente_id: str, *, stato=StatoPreventivo.INVIATO):
    with app.app_context():
        gp = GestionePreventivi(db_path=app.config["PREVENTIVI_DB"])
        preventivo = gp.crea_preventivo(
            id_cliente=cliente_id,
            oggetto="Assistenza recupero credito",
            voci=[VocePreventivo(descrizione="Fase stragiudiziale", importo=1200.0, tipo=TipoVoce.ONORARIO)],
        )
        gp.cambia_stato_preventivo(preventivo.id, stato)
    return preventivo


def _client_with_invite(app, cliente, fascicolo):
    client = app.test_client()
    _login(client)
    response = client.post(
        "/api/v1/ui/client-portal/studio/invites",
        json={"clientId": cliente.id, "matterId": fascicolo.id, "expiresDays": 7},
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    token = response.get_json()["inviteUrl"].rsplit("/", 1)[-1]
    accepted = client.post(f"/api/v1/ui/client-portal/public/invites/{token}/accept", json={})
    assert accepted.status_code == 200
    return client, token


def _headers(token: str) -> dict:
    return {"X-Client-Portal-Token": token}


def _accept_first_preventivo(client, token):
    overview = client.get("/api/v1/ui/client-portal/public/signing/overview", headers=_headers(token))
    payload = overview.get_json()
    assert overview.status_code == 200, payload
    preventivo = payload["preventivi"][0]
    accept = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{preventivo['id']}/accept",
        json={"accepted": True, "pdfSha256": preventivo["pdfSha256"]},
        headers=_headers(token),
    )
    assert accept.status_code == 200, accept.get_data(as_text=True)
    return accept.get_json()


def _portal_db_path(tmp_path: Path) -> Path:
    return tmp_path / "client_portal" / "client_portal.db"


def _gp_runtime(app):
    """Gestore preventivi visto dal runtime dell'app (JSON + studio.db)."""

    from web.helpers import get_preventivi

    with app.test_request_context():
        return get_preventivi()


# ---------------------------------------------------------------- flag off


def test_signing_flag_default_off_fail_closed(tmp_path: Path):
    app = _app(tmp_path, signing_enabled=False)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)

    with app.test_request_context():
        pass

    with app.test_client() as client:
        _login(client)
        for method, url in [
            ("GET", "/api/v1/ui/client-portal/public/signing/overview"),
            ("POST", "/api/v1/ui/client-portal/public/signing/preventivi/x/accept"),
            ("POST", "/api/v1/ui/client-portal/public/signing/preventivi/x/decline"),
            ("POST", "/api/v1/ui/client-portal/public/signing/conferimento/x/sign"),
            ("POST", "/api/v1/ui/client-portal/public/signing/conferimento/x/upload-signed"),
            ("POST", "/api/v1/ui/client-portal/public/signing/identity-document"),
            ("POST", "/api/v1/ui/client-portal/public/signing/otp/start"),
            ("POST", "/api/v1/ui/client-portal/public/signing/otp/verify"),
            ("GET", "/api/v1/ui/client-portal/public/signing/receipt"),
            ("POST", "/api/v1/ui/client-portal/studio/documents/x/review"),
        ]:
            response = client.open(url, method=method, json={})
            assert response.status_code == 403, (url, response.status_code)
            assert response.get_json()["code"] == "feature_disabled"


def test_signing_endpoint_blocca_tenant_id(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/api/v1/ui/client-portal/public/signing/preventivi/x/accept",
            json={"accepted": True, "tenant_id": "studio-b"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "backend_security_control_param"
    assert "studio-b" not in response.get_data(as_text=True)


# ---------------------------------------------------------------- overview


def test_overview_lista_preventivi_del_cliente_con_pdf_stabile(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    _seed_preventivo(app, "cliente-di-altri", stato=StatoPreventivo.INVIATO)

    with app.test_client() as client:
        _ = client  # test client separato per lo studio
    client, token = _client_with_invite(app.test_client().application and app or app, cliente, fascicolo)

    first = client.get("/api/v1/ui/client-portal/public/signing/overview", headers=_headers(token))
    second = client.get("/api/v1/ui/client-portal/public/signing/overview", headers=_headers(token))

    payload = first.get_json()
    assert first.status_code == 200
    assert len(payload["preventivi"]) == 1
    preventivo = payload["preventivi"][0]
    assert preventivo["oggetto"] == "Assistenza recupero credito"
    # Primo accesso dal portale: lo stato passa a APERTO.
    assert preventivo["stato"] in {"APERTO", "INVIATO"}
    assert len(preventivo["pdfSha256"]) == 64
    # Hash stabile fra due chiamate (PDF materializzato una sola volta).
    assert second.get_json()["preventivi"][0]["pdfSha256"] == preventivo["pdfSha256"]
    # Nessun campo interno esposto.
    raw = first.get_data(as_text=True)
    assert "stored_name" not in raw
    assert "evidence" not in raw
    assert "/uploads/" not in raw
    # Il PDF materializzato è scaricabile dal cliente.
    download = client.get(
        f"/api/v1/ui/client-portal/public/documents/{preventivo['documentId']}/download",
        headers=_headers(token),
    )
    assert download.status_code == 200
    assert download.data[:4] == b"%PDF"
    # Firma qualificata mai dichiarata disponibile.
    assert payload["qualifiedSignature"]["available"] is False


# ---------------------------------------------------------------- preventivo


def test_accettazione_preventivo_con_evidence(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    preventivo = _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)

    result = _accept_first_preventivo(client, token)
    assert result["ok"] is True
    step_map = {step["key"]: step["status"] for step in result["overview"]["steps"]}
    assert step_map["preventivo"] == "completato"
    # Conferimento creato automaticamente e disponibile (dati minimi presenti).
    assert result["overview"]["conferimento"]["available"] is True

    aggiornato = _gp_runtime(app).get_preventivo(preventivo.id)
    assert aggiornato.stato == StatoPreventivo.ACCETTATO
    assert aggiornato.accettato_via == "PORTALE_CLIENTE_APP"

    # Evidence lato studio: consenso con hash, mai nel payload cliente.
    with sqlite3.connect(_portal_db_path(tmp_path)) as conn:
        row = conn.execute(
            "SELECT payload_json FROM client_portal_consents WHERE consent_key = 'accettazione_preventivo'"
        ).fetchone()
    assert row is not None
    assert '"ipHash"' in row[0]
    assert '"tokenRef"' in row[0]
    assert '"payloadSha256"' in row[0]
    assert token not in row[0]
    audit = sqlite3.connect(_portal_db_path(tmp_path)).execute(
        "SELECT action FROM client_portal_audit_events WHERE action = 'client_portal.preventivo.accettato'"
    ).fetchone()
    assert audit is not None

    # Doppia accettazione → errore controllato.
    again = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{preventivo.id}/accept",
        json={"accepted": True},
        headers=_headers(token),
    )
    assert again.status_code == 422
    assert again.get_json()["message"] == "Preventivo già accettato."


def test_accettazione_rifiutata_su_sha_mismatch_e_consenso_mancante(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    preventivo = _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)

    no_consent = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{preventivo.id}/accept",
        json={"accepted": False},
        headers=_headers(token),
    )
    assert no_consent.status_code == 422

    mismatch = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{preventivo.id}/accept",
        json={"accepted": True, "pdfSha256": "0" * 64},
        headers=_headers(token),
    )
    assert mismatch.status_code == 422
    assert "ricarica la pagina" in mismatch.get_json()["message"]


def test_rifiuto_preventivo_con_motivo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    preventivo = _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)

    decline = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{preventivo.id}/decline",
        json={"reason": "Compenso troppo elevato"},
        headers=_headers(token),
    )
    assert decline.status_code == 200
    assert _gp_runtime(app).get_preventivo(preventivo.id).stato == StatoPreventivo.RIFIUTATO


def test_preventivo_di_altro_cliente_non_accettabile(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    estraneo = _seed_preventivo(app, "altro-cliente")
    client, token = _client_with_invite(app, cliente, fascicolo)

    response = client.post(
        f"/api/v1/ui/client-portal/public/signing/preventivi/{estraneo.id}/accept",
        json={"accepted": True},
        headers=_headers(token),
    )
    assert response.status_code == 422
    assert response.get_json()["message"] == "Preventivo non disponibile."


# ---------------------------------------------------------------- conferimento


def test_firma_conferimento_produce_pdf_firmato_immutando_originale(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    result = _accept_first_preventivo(client, token)
    conferimento = result["overview"]["conferimento"]
    assert conferimento["available"] is True
    original_sha = conferimento["pdfSha256"]

    data_url = "data:image/jpeg;base64," + base64.b64encode(JPEG_1PX).decode("ascii")
    sign = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento['id']}/sign",
        json={
            "mode": "canvas",
            "signatureImage": data_url,
            "consents": dict(ALL_SIGNING_CONSENTS),
            "position": {"pageIndex": -1, "xMm": 110, "yMm": 12, "widthMm": 85, "heightMm": 26},
            "pdfSha256": original_sha,
        },
        headers=_headers(token),
    )
    payload = sign.get_json()
    assert sign.status_code == 200, payload
    assert payload["signedDocumentId"]
    assert "evidence" not in str(payload)

    with sqlite3.connect(_portal_db_path(tmp_path)) as conn:
        rows = dict(
            conn.execute(
                "SELECT request_id, status FROM client_portal_documents WHERE request_id IN (?, ?)",
                ("documento-firmato", f"conferimento-pdf:{conferimento['id']}"),
            ).fetchall()
        )
        assert rows["documento-firmato"] == "firmato_definitivo"
        # Documento originale immutato (stesso hash registrato).
        original_row = conn.execute(
            "SELECT sha256 FROM client_portal_documents WHERE request_id = ?",
            (f"conferimento-pdf:{conferimento['id']}",),
        ).fetchone()
        assert original_row[0] == original_sha
        signed_sha = conn.execute(
            "SELECT sha256 FROM client_portal_documents WHERE request_id = 'documento-firmato'"
        ).fetchone()[0]
        assert signed_sha != original_sha
        evidence_json = conn.execute(
            "SELECT evidence_json FROM client_portal_signature_requests WHERE status = 'firmato'"
        ).fetchone()[0]
    for key in ("originalSha256", "signedSha256", "ipHash", "tokenRef", "payloadSha256", "signatureCoordinates"):
        assert key in evidence_json
    assert token not in evidence_json
    # Consensi registrati: conferimento + le 4 dichiarazioni di firma.
    with sqlite3.connect(_portal_db_path(tmp_path)) as conn:
        keys = {row[0] for row in conn.execute("SELECT consent_key FROM client_portal_consents WHERE accepted = 1")}
    assert "accettazione_conferimento" in keys
    assert set(ALL_SIGNING_CONSENTS) <= keys

    # Il PDF firmato scaricato è un PDF valido con hash coerente.
    download = client.get(
        f"/api/v1/ui/client-portal/public/documents/{payload['signedDocumentId']}/download",
        headers=_headers(token),
    )
    assert download.status_code == 200
    assert download.data[:4] == b"%PDF"
    import hashlib

    assert hashlib.sha256(download.data).hexdigest() == signed_sha

    # Ricevuta finale disponibile e senza dati interni.
    receipt = client.get("/api/v1/ui/client-portal/public/signing/receipt", headers=_headers(token))
    receipt_payload = receipt.get_json()
    assert receipt.status_code == 200
    assert receipt_payload["receipt"]["firma"]["eseguita"] is True
    assert "elettronica semplice" in receipt_payload["receipt"]["firma"]["tipo"]
    assert "evidence" not in str(receipt_payload)


def test_firma_rifiutata_senza_tutti_i_consensi(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    result = _accept_first_preventivo(client, token)
    conferimento_id = result["overview"]["conferimento"]["id"]

    for missing in ALL_SIGNING_CONSENTS:
        consents = dict(ALL_SIGNING_CONSENTS)
        consents[missing] = False
        response = client.post(
            f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento_id}/sign",
            json={"consents": consents, "typedName": "Mario Rossi"},
            headers=_headers(token),
        )
        assert response.status_code == 422, missing
        assert "consensi" in response.get_json()["message"].lower()


def test_conferimento_bloccato_senza_accettazione_preventivo(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    preventivo = _seed_preventivo(app, cliente.id)
    with app.test_request_context():
        from web.helpers import get_preventivi

        conferimento = get_preventivi().crea_conferimento_da_preventivo(preventivo.id)
    client, token = _client_with_invite(app, cliente, fascicolo)

    overview = client.get("/api/v1/ui/client-portal/public/signing/overview", headers=_headers(token))
    assert overview.get_json()["conferimento"]["available"] is False

    response = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento.id}/sign",
        json={"consents": dict(ALL_SIGNING_CONSENTS), "typedName": "Mario Rossi"},
        headers=_headers(token),
    )
    assert response.status_code == 422
    assert "accettazione del preventivo" in response.get_json()["message"]


def test_upload_firmato_fallback_va_in_revisione(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    result = _accept_first_preventivo(client, token)
    conferimento = result["overview"]["conferimento"]

    non_pdf = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento['id']}/upload-signed",
        data={
            "file": (io.BytesIO(b"testo"), "firmato.txt"),
            **{key: "true" for key in ALL_SIGNING_CONSENTS},
        },
        content_type="multipart/form-data",
        headers=_headers(token),
    )
    assert non_pdf.status_code == 422

    upload = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento['id']}/upload-signed",
        data={
            "file": (io.BytesIO(b"%PDF-1.4\nfirmato-a-mano"), "conferimento_firmato.pdf"),
            **{key: "true" for key in ALL_SIGNING_CONSENTS},
        },
        content_type="multipart/form-data",
        headers=_headers(token),
    )
    payload = upload.get_json()
    assert upload.status_code == 200, payload
    with sqlite3.connect(_portal_db_path(tmp_path)) as conn:
        status = conn.execute(
            "SELECT status FROM client_portal_documents WHERE id = ?",
            (payload["signedDocumentId"],),
        ).fetchone()[0]
    assert status == "in_revisione"

    # Revisione studio: approvazione con nota.
    review = client.post(
        f"/api/v1/ui/client-portal/studio/documents/{payload['signedDocumentId']}/review",
        json={"decision": "approvato", "note": "Firma verificata."},
    )
    assert review.status_code == 200
    assert review.get_json()["item"]["status"] == "approvato"


# ---------------------------------------------------------------- documento identità


def test_identita_richiede_consenso_poi_upload_e_review(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)

    def _upload():
        return client.post(
            "/api/v1/ui/client-portal/public/signing/identity-document",
            data={"file": (io.BytesIO(JPEG_1PX), "carta-identita.jpg")},
            content_type="multipart/form-data",
            headers=_headers(token),
        )

    senza_consenso = _upload()
    assert senza_consenso.status_code == 422
    assert "consenso" in senza_consenso.get_json()["message"].lower()

    consenso = client.post(
        "/api/v1/ui/client-portal/public/consents",
        json={"key": "acquisizione_documento_identita", "version": "2026-07", "accepted": True},
        headers=_headers(token),
    )
    assert consenso.status_code == 200

    primo = _upload()
    assert primo.status_code == 200
    assert primo.get_json()["item"]["status"] == "in_revisione"
    primo_id = primo.get_json()["item"]["id"]

    secondo = _upload()
    assert secondo.status_code == 200
    with sqlite3.connect(_portal_db_path(tmp_path)) as conn:
        status_primo = conn.execute(
            "SELECT status FROM client_portal_documents WHERE id = ?", (primo_id,)
        ).fetchone()[0]
    assert status_primo == "sostituito"

    formato = client.post(
        "/api/v1/ui/client-portal/public/signing/identity-document",
        data={"file": (io.BytesIO(b"GIF89a"), "carta.gif")},
        content_type="multipart/form-data",
        headers=_headers(token),
    )
    assert formato.status_code == 422

    # Review senza permessi (nessuna sessione studio su un client anonimo).
    anon = app.test_client()
    negato = anon.post(
        f"/api/v1/ui/client-portal/studio/documents/{primo_id}/review",
        json={"decision": "approvato"},
    )
    assert negato.status_code == 401


# ---------------------------------------------------------------- OTP step-up


def _enable_otp(client):
    response = client.post(
        "/api/v1/ui/client-portal/studio/settings",
        json={"signatures": {"otpStepUp": True}},
    )
    assert response.status_code == 200, response.get_data(as_text=True)


def test_otp_step_up_blocca_firma_senza_verifica(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    _enable_otp(client)
    result = _accept_first_preventivo(client, token)
    conferimento_id = result["overview"]["conferimento"]["id"]

    blocked = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento_id}/sign",
        json={"consents": dict(ALL_SIGNING_CONSENTS), "typedName": "Mario Rossi"},
        headers=_headers(token),
    )
    assert blocked.status_code == 422
    assert "codice" in blocked.get_json()["message"].lower()

    codes: list[str] = []

    def _fake_send(invite, repo, code):
        codes.append(code)
        return True, ""

    monkeypatch.setattr(
        "web.services.client_portal_signing_bridge._otp_send_email", _fake_send
    )
    start = client.post(
        "/api/v1/ui/client-portal/public/signing/otp/start", json={}, headers=_headers(token)
    )
    assert start.status_code == 200
    assert codes and codes[0] not in start.get_data(as_text=True)

    wrong = client.post(
        "/api/v1/ui/client-portal/public/signing/otp/verify",
        json={"code": "000000" if codes[0] != "000000" else "111111"},
        headers=_headers(token),
    )
    assert wrong.status_code == 422

    ok = client.post(
        "/api/v1/ui/client-portal/public/signing/otp/verify",
        json={"code": codes[0]},
        headers=_headers(token),
    )
    assert ok.status_code == 200

    signed = client.post(
        f"/api/v1/ui/client-portal/public/signing/conferimento/{conferimento_id}/sign",
        json={"consents": dict(ALL_SIGNING_CONSENTS), "typedName": "Mario Rossi"},
        headers=_headers(token),
    )
    assert signed.status_code == 200, signed.get_data(as_text=True)

    # Il codice non è mai salvato in chiaro nel DB del portale.
    raw_db = _portal_db_path(tmp_path).read_text(encoding="latin-1", errors="ignore")
    assert codes[0] not in raw_db


def test_otp_lockout_dopo_tentativi_errati(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    _enable_otp(client)

    codes: list[str] = []
    monkeypatch.setattr(
        "web.services.client_portal_signing_bridge._otp_send_email",
        lambda invite, repo, code: (codes.append(code) or (True, "")),
    )
    assert client.post("/api/v1/ui/client-portal/public/signing/otp/start", json={}, headers=_headers(token)).status_code == 200
    wrong_code = "999999" if codes[0] != "999999" else "888888"
    for _ in range(5):
        client.post(
            "/api/v1/ui/client-portal/public/signing/otp/verify",
            json={"code": wrong_code},
            headers=_headers(token),
        )
    # Anche il codice giusto ora è bloccato.
    locked = client.post(
        "/api/v1/ui/client-portal/public/signing/otp/verify",
        json={"code": codes[0]},
        headers=_headers(token),
    )
    assert locked.status_code == 422


def test_otp_start_fail_closed_se_email_non_disponibile(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    _crea_operatore(app)
    cliente, fascicolo = _seed_cliente_fascicolo(app)
    _seed_preventivo(app, cliente.id)
    client, token = _client_with_invite(app, cliente, fascicolo)
    _enable_otp(client)

    monkeypatch.setattr(
        "web.services.client_portal_signing_bridge._otp_send_email",
        lambda invite, repo, code: (False, "SMTP non configurato."),
    )
    start = client.post(
        "/api/v1/ui/client-portal/public/signing/otp/start", json={}, headers=_headers(token)
    )
    assert start.status_code == 422
    assert "Impossibile inviare il codice" in start.get_json()["message"]


# ---------------------------------------------------------------- token opachi


def test_token_non_valido_riceve_errore_opaco(tmp_path: Path):
    app = _app(tmp_path)

    with app.test_client() as client:
        response = client.get(
            "/api/v1/ui/client-portal/public/signing/overview",
            headers={"X-Client-Portal-Token": "cp1.token.finto.nonce"},
        )

    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert response.get_json()["code"] == "invalid_invite"
    assert "tenant" not in body.lower()
    assert "Traceback" not in body
