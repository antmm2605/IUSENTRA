from __future__ import annotations

import base64
import io
import errno
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from pct.auth import GestioneUtenti, RuoloUtente
from pct.busta import DatiBusta
from pct.cli import cli
from pct.config_studio import ConfigFirma, ConfigStudio, ConfigPEC as StudioConfigPEC, GestioneConfigStudio
from pct.deposito import DepositoCivile
from pct.fascicoli import EsitoDepositoPCT, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.firma import FirmaDigitale, busta_cades_valida, crea_signer_da_config
from pct.pec import ConfigPEC
from pct.pst_cifratura import PSTCifraturaError
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


def _cades_signed_pdf() -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Firmatario")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    documento = _pdf_base()
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
        "SECRET_KEY": "test",
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


def _crea_fascicolo_tributario_pronto(gf: GestioneFascicoli):
    fascicolo = gf.nuovo(
        titolo="Ricorso tributario demo",
        tipo=TipoFascicolo.TRIBUTARIO,
        tribunale="CPT Milano",
        numero_rg="321",
        anno_rg=2026,
        controparte="Agenzia delle Entrate",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "ricorso_tributario.pdf.p7m",
        TipoDocumento.RICORSO,
        _cades_signed_pdf(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fascicolo.id,
        "procura_alle_liti.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
    )
    notifica = gf.aggiungi_documento(
        fascicolo.id,
        "relata_notifica_ente.pdf",
        TipoDocumento.NOTIFICA,
        _pdf_base(),
    )
    contributo = gf.aggiungi_documento(
        fascicolo.id,
        "ricevuta_contributo_unificato.pdf",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
    )
    indice = gf.aggiungi_documento(
        fascicolo.id,
        "indice_documenti.pdf",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
    )
    nir = gf.aggiungi_documento(
        fascicolo.id,
        "NIR_nota_iscrizione_a_ruolo_firmata.pdf.p7m",
        TipoDocumento.ALLEGATO,
        _cades_signed_pdf(),
        firmato=True,
    )
    return fascicolo, atto, procura, notifica, contributo, indice, nir


def test_salva_documento_firmato_pades_usa_i_bytes_passati(tmp_path):
    firma = object.__new__(FirmaDigitale)
    visto = {}

    def _fake_firma_pades(pdf_path: str, output_path: str) -> str:
        visto["input_path"] = pdf_path
        visto["input_bytes"] = Path(pdf_path).read_bytes()
        visto["output_path"] = output_path
        Path(output_path).write_bytes(b"%PDF-SIGNED%")
        return output_path

    firma.firma_pades = _fake_firma_pades

    output_path = tmp_path / "atto_firmato.pdf"
    result = FirmaDigitale.salva_documento_firmato(
        firma,
        b"%PDF-INPUT%",
        str(output_path),
        formato="pades",
    )

    assert result == str(output_path)
    assert visto["input_bytes"] == b"%PDF-INPUT%"
    assert visto["output_path"] == str(output_path)
    assert not Path(visto["input_path"]).exists()


def test_esito_deposito_pct_normalizza_legacy_e_alias_id():
    esito = EsitoDepositoPCT.from_dict(
        {
            "id_deposito": "DEP12345",
            "timestamp": "2026-04-04T10:00:00",
            "stato": "ACCETTATO",
            "tipo_atto": "MEMORIA",
            "pec_destinatario": "tribunale.milano@pec.it",
        }
    )

    assert esito.id == "DEP12345"
    assert esito.id_deposito == "DEP12345"
    assert esito.stato == "ACCETTATO_PEC"


def test_deposito_civile_risolve_codice_ufficio_prima_della_busta(tmp_path, monkeypatch):
    import pct.deposito as deposito_mod

    catture = {}

    class FakePEC:
        def __init__(self, cfg):
            self.cfg = cfg

        def invia_busta(self, destinatario_pec, busta_path, oggetto):
            catture["pec_destinatario"] = destinatario_pec
            catture["busta_path"] = busta_path
            catture["oggetto"] = oggetto
            return {"inviato": True}

        def attendi_ricevute(self):
            return {"accettazione": "ACC-PEC"}

    class FakeReGINde:
        def ottieni_ufficio(self, codice_ufficio):
            if codice_ufficio == "0580010":
                return SimpleNamespace(
                    codice="0580010",
                    nome="Tribunale di Milano",
                    distretto="Milano",
                    pec="tribunale.milano@pec.it",
                    tipo="TRIBUNALE",
                )
            return None

        def cerca_ufficio_giudiziario(self, nome):
            raise AssertionError("Con un codice ufficio valido non deve essere usato il fallback per nome.")

    class FakeBusta:
        def __init__(self, dati):
            catture["codice_ufficio_in_busta"] = dati.codice_ufficio
            self._dati = dati

        def crea_busta(self, output_dir):
            path = Path(output_dir)
            path.mkdir(parents=True, exist_ok=True)
            enc = path / "busta.enc"
            enc.write_bytes(b"ENC")
            return str(enc)

    monkeypatch.setattr(deposito_mod, "ClientPEC", FakePEC)
    monkeypatch.setattr(deposito_mod, "ClientReGINde", FakeReGINde)
    monkeypatch.setattr(deposito_mod, "BustaTelematica", FakeBusta)
    monkeypatch.setattr(
        deposito_mod,
        "valida_documento_deposito",
        lambda *args, **kwargs: {"ok": True, "errori": []},
    )

    atto = tmp_path / "atto.pdf"
    atto.write_bytes(b"%PDF-TEST%")

    deposito = DepositoCivile(
        ConfigPEC(
            indirizzo="studio@pec.it",
            password="secret",
            smtp_host="smtp.pec.it",
            imap_host="imap.pec.it",
        ),
        output_dir=str(tmp_path / "depositi"),
    )
    dati = DatiBusta(
        codice_ufficio="",
        codice_registro="CIVILE",
        oggetto="Deposito memoria",
        tipo_atto="MEMORIA",
        atto_principale=str(atto),
        allegati=[],
        numero_rg="1234",
        anno_rg=2026,
        operatore="Avv. Demo",
        cf_mittente="RSSMRA80A01H501U",
    )

    esito = deposito.deposita(dati, "0580010", attendi_ricevute=True)

    assert dati.codice_ufficio == "0580010"
    assert catture["codice_ufficio_in_busta"] == "0580010"
    assert esito.stato == "ACCETTATO_PEC"
    assert esito.id_deposito == esito.id
    assert esito.busta_path.endswith("busta.enc")


def test_cmd_deposita_risolve_ufficio_prima_di_costruire_la_busta(tmp_path, monkeypatch):
    import pct.cli as cli_mod

    atto = tmp_path / "atto.pdf"
    atto.write_text("PDF", encoding="utf-8")
    catture = {}

    monkeypatch.setattr(
        cli_mod,
        "carica_config",
        lambda: {
            "pec_indirizzo": "studio@pec.it",
            "pec_password": "secret",
            "pec_smtp_host": "smtp.pec.it",
            "pec_smtp_port": 465,
            "pec_imap_host": "imap.pec.it",
            "firma_p12": "",
            "firma_password": "",
            "cf_avvocato": "RSSMRA80A01H501U",
            "nome_avvocato": "Avv. Demo",
            "output_dir": str(tmp_path / "depositi"),
        },
    )

    class FakeReGINde:
        def ottieni_ufficio(self, codice_ufficio):
            if codice_ufficio == "0580010":
                return SimpleNamespace(
                    codice="0580010",
                    nome="Tribunale di Milano",
                    distretto="Milano",
                    pec="tribunale.milano@pec.it",
                    tipo="TRIBUNALE",
                )
            return None

        def cerca_ufficio_giudiziario(self, nome):
            return None

    class FakeDeposito:
        def __init__(self, config_pec, firma=None, output_dir="./depositi"):
            catture["output_dir"] = output_dir

        def deposita(self, dati, tribunale, attendi_ricevute=True, tsa_url=None):
            catture["codice_ufficio"] = dati.codice_ufficio
            catture["tribunale_arg"] = tribunale
            return EsitoDepositoPCT(
                id="DEP12345",
                timestamp="2026-04-04T10:00:00",
                stato="INVIATO",
                tipo_atto=dati.tipo_atto,
                pec_destinatario="tribunale.milano@pec.it",
                busta_path=str(tmp_path / "busta.enc"),
            )

        def salva_esito(self, esito):
            path = tmp_path / "esito.json"
            path.write_text("{}", encoding="utf-8")
            return str(path)

    monkeypatch.setattr(cli_mod, "ClientReGINde", FakeReGINde)
    monkeypatch.setattr(cli_mod, "DepositoCivile", FakeDeposito)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "deposita",
            "--atto",
            str(atto),
            "--tribunale",
            "0580010",
            "--oggetto",
            "Deposito memoria",
            "--tipo-atto",
            "MEMORIA",
            "--no-firma",
            "--no-ricevute",
        ],
    )

    assert result.exit_code == 0, result.output
    assert catture["codice_ufficio"] == "0580010"
    assert catture["tribunale_arg"] == "0580010"
    assert "Tribunale di Milano (0580010)" in result.output


def test_config_firma_pkcs11_consente_solo_cades(tmp_path):
    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    cfg = ConfigFirma(pkcs11_library=str(libreria))

    assert cfg.formato_attivo == "pkcs11"
    assert cfg.formati_firma_consentiti == ["cades"]
    assert cfg.valida_formato_firma("cades") == "cades"
    with pytest.raises(ValueError, match="solo CAdES"):
        cfg.valida_formato_firma("pades")


def test_config_firma_p12_consente_cades_e_pades(tmp_path):
    p12 = tmp_path / "firma.p12"
    p12.write_bytes(b"fake")
    cfg = ConfigFirma(p12_path=str(p12))

    assert cfg.formato_attivo == "p12"
    assert cfg.formati_firma_consentiti == ["cades", "pades"]
    assert cfg.valida_formato_firma("pades") == "pades"


def test_config_firma_backend_preferito_prevale_su_rilevazione_tecnica(tmp_path):
    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    p12 = tmp_path / "firma.p12"
    p12.write_bytes(b"fake")
    cfg = ConfigFirma(
        backend_preferito="p12",
        pkcs11_library=str(libreria),
        p12_path=str(p12),
    )

    assert cfg.formato_attivo == "pkcs11"
    assert cfg.backend_firma_effettivo == "p12"
    assert cfg.formati_firma_consentiti == ["cades", "pades"]


def test_config_firma_backend_preferito_non_fa_fallback_silenzioso(tmp_path):
    p12 = tmp_path / "firma.p12"
    p12.write_bytes(b"fake")
    cfg = ConfigFirma(
        backend_preferito="pkcs11",
        p12_path=str(p12),
    )

    with pytest.raises(FileNotFoundError, match="PKCS#11 selezionato"):
        _ = cfg.backend_firma_effettivo
    assert cfg.backend_firma_effettivo_safe == "nessuno"
    assert "PKCS#11 selezionato" in cfg.backend_firma_errore


def test_crea_signer_da_config_rispetta_backend_preferito_pkcs11(tmp_path, monkeypatch):
    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    cfg = ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria))
    catture = {}

    class _FakeSigner:
        pass

    def _fake_da_config(config, pin=None):
        catture["backend"] = config.backend_firma_effettivo
        catture["pin"] = pin
        return _FakeSigner()

    monkeypatch.setattr("pct.firma_pkcs11.FirmaPKCS11.da_config", _fake_da_config)

    signer = crea_signer_da_config(cfg, pin="123456")

    assert isinstance(signer, _FakeSigner)
    assert catture == {"backend": "pkcs11", "pin": "123456"}


def test_firma_documento_blocca_pdf_pades_con_backend_pkcs11(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(firma=ConfigFirma(pkcs11_library=str(libreria)))
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="deposito-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo test firma", tipo=TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "atto.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-ORIG%",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "deposito-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        with open(tmp_path / "signed.pdf", "wb") as fh:
            fh.write(b"%PDF-SIGNED%")
        with open(tmp_path / "signed.pdf", "rb") as fh:
            response = client.post(
                f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
                data={"file": (fh, "signed.pdf"), "note": "Upload PAdES"},
                content_type="multipart/form-data",
                follow_redirects=False,
            )

    assert response.status_code in {302, 303}
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("solo CAdES" in message for _, message in flashes)

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "atto.pdf"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is False


def test_firma_documento_get_apre_shell_react_senza_405(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(ConfigStudio(firma=ConfigFirma()))

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="firma-react-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo firma React", tipo=TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "atto.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-ORIG%",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "firma-react-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert b"Method Not Allowed" not in response.data
    assert b"IUSENTRA React Shell" in response.data or b'id="root"' in response.data


def test_firma_documento_blocca_rifirma_senza_conferma_esplicita(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(ConfigStudio(firma=ConfigFirma()))

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="firma-guard-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo guardia firma", tipo=TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "atto.pdf.p7m",
        TipoDocumento.ATTO_GIUDIZIARIO,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "firma-guard-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"note": "Tentativo rifirma"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        confirmed = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"note": "Rifirma confermata", "confirm_resign": "1"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["already_signed"] is True
    assert payload["requires_confirm_resign"] is True
    assert "documento già firmato" in payload["messaggio"]
    assert confirmed.status_code == 200
    assert confirmed.get_json()["ok"] is True


def test_api_pkcs11_firma_documento_blocca_pades(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(firma=ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria)))
    )
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pkcs11-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pkcs11-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/firma/pkcs11/firma-documento",
            json={
                "fascicolo_id": "FASC-1",
                "documento_id": "DOC-1",
                "pin": "12345678",
                "formato": "pades",
            },
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "solo CAdES" in payload["messaggio"]


def test_api_pkcs11_firma_documenti_batch_usa_una_sola_sessione(tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    import pct.firma_pkcs11 as firma_pkcs11

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(firma=ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria)))
    )
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pkcs11-batch-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo test firma batch", tipo=TipoFascicolo.CIVILE)
    doc1 = gf.aggiungi_documento(
        fascicolo.id,
        "atto-1.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-ORIG-1%",
    )
    doc2 = gf.aggiungi_documento(
        fascicolo.id,
        "atto-2.pdf",
        TipoDocumento.ALLEGATO,
        b"%PDF-ORIG-2%",
    )

    calls = {"pins": [], "salvati": []}
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Batch"),
    ])
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

    class _FakeSigner:
        intestatario = "Avv. Batch"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def verifica_scadenza(self):
            return {
                "scaduto": False,
                "scadenza": "2029-02-23",
                "avviso_imminente": False,
                "messaggio": "Certificato valido",
            }

        def salva_documento_firmato(self, contenuto, output_path, formato="cades"):
            calls["salvati"].append({"output_path": output_path, "formato": formato})
            digest = hashes.Hash(hashes.SHA256())
            digest.update(contenuto)
            signed_attrs_der = firma_pkcs11.FirmaPKCS11._build_signed_attrs(
                object.__new__(firma_pkcs11.FirmaPKCS11),
                digest.finalize(),
            )
            signature = key.sign(signed_attrs_der, padding.PKCS1v15(), hashes.SHA256())
            p7m = firma_pkcs11._build_cades_bes(
                documento=contenuto,
                signature_bytes=signature,
                cert_der=cert.public_bytes(serialization.Encoding.DER),
                signed_attrs_der=signed_attrs_der,
                detached=False,
            )
            Path(str(output_path) + ".p7m").write_bytes(p7m)
            return str(output_path) + ".p7m"

    def _fake_crea_signer(cfg_firma, pin=None):
        calls["pins"].append(pin)
        return _FakeSigner()

    monkeypatch.setattr("pct.firma.crea_signer_da_config", _fake_crea_signer)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pkcs11-batch-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/firma/pkcs11/firma-documenti-batch",
            json={
                "fascicolo_id": fascicolo.id,
                "documento_ids": [doc1.id, doc2.id],
                "pin": "12345678",
                "formato": "cades",
            },
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["firmati"] == 2
    assert payload["errori"] == 0
    assert calls["pins"] == ["12345678"]
    assert len(calls["salvati"]) == 2

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert all(doc.firmato_digitalmente for doc in fascicolo_reload.documenti[:2])
    assert fascicolo_reload.documenti[0].nome.endswith(".p7m")
    assert fascicolo_reload.documenti[1].nome.endswith(".p7m")

    path_doc1 = gf_reload.percorso_documento(fascicolo.id, doc1.id)
    assert path_doc1 is not None
    contenuto_doc1 = path_doc1.read_bytes()
    assert busta_cades_valida(contenuto_doc1) is True
    assert contenuto_doc1 != b"%PDF-ORIG-1%"


def test_firma_documento_ajax_rifiuta_p7m_non_valido(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(firma=ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria)))
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="upload-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo test upload firma", tipo=TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        b"%PDF-ORIG%",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "upload-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"file": (io.BytesIO(b"%PDF-rinominato%"), "procura.pdf.p7m")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "firma CAdES valida" in payload["messaggio"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "procura.pdf"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is False


def test_firma_documento_ajax_rifiuta_pdf_con_testo_firmato_ma_senza_pades(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(ConfigStudio(firma=ConfigFirma()))

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="upload-pades-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(titolo="Fascicolo PDF non PAdES", tipo=TipoFascicolo.CIVILE)
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "atto.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\nDocumento non firmato\n%%EOF",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "upload-pades-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"file": (io.BytesIO(b"%PDF-1.4\nFirmato digitalmente\n%%EOF"), "Atto Firmato digitale.PDF")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert "PAdES" in payload["messaggio"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "atto.pdf"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is False


def test_firma_documento_ajax_valido_non_fallisce_se_sync_realtime_ha_errori(tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    libreria = tmp_path / "bit4id.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(firma=ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria)))
    )

    class _FakeSyncBroken:
        n_connessi = 0

        def pubblica(self, *args, **kwargs):
            raise RuntimeError("sync down")

    monkeypatch.setattr("web.app.get_gestore", lambda: _FakeSyncBroken(), raising=False)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="upload-sync-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Procura firmata",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Milano",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        b"%PDF-1.4\nprocura valida",
        caricato_da="upload-sync-admin",
        firmato=False,
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Firmatario")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    documento = b"%PDF-1.4\nprocura valida"
    signed_attrs = local_signer_mod._build_signed_attrs_der_inline(documento)
    signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
    p7m_valido = _build_cades_bes(
        documento=documento,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs,
        detached=False,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "upload-sync-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"file": (io.BytesIO(p7m_valido), "procura.pdf.p7m")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["warning"] is True
    assert "sync" in payload["warning_codes"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "procura.pdf.p7m"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is True


def test_firma_documento_ajax_recupera_errore_spazio_con_fallback_compatto(tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="upload-storage-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Procura fallback storage",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Milano",
        numero_rg="124",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    doc = gf.aggiungi_documento(
        fascicolo.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        b"%PDF-1.4\nprocura valida",
        caricato_da="upload-storage-admin",
        firmato=False,
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Storage")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    documento = b"%PDF-1.4\nprocura valida"
    signed_attrs = local_signer_mod._build_signed_attrs_der_inline(documento)
    signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
    p7m_valido = _build_cades_bes(
        documento=documento,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs,
        detached=False,
    )

    original_sostituisci = GestioneFascicoli.sostituisci_documento
    calls: list[dict] = []

    def _fake_sostituisci(self, *args, **kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            raise OSError(errno.ENOSPC, "No space left on device")
        return original_sostituisci(self, *args, **kwargs)

    monkeypatch.setattr(GestioneFascicoli, "sostituisci_documento", _fake_sostituisci)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "upload-storage-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/firma",
            data={"file": (io.BytesIO(p7m_valido), "procura.pdf.p7m")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["warning"] is True
    assert "storage_compact" in payload["warning_codes"]
    assert len(calls) == 2
    assert calls[0].get("preserve_version_snapshot", True) is True
    assert calls[0].get("reuse_existing_path", False) is False
    assert calls[1]["preserve_version_snapshot"] is False
    assert calls[1]["reuse_existing_path"] is True

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "procura.pdf.p7m"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is True


def test_wizard_tributario_renderizza_prededeposito_sigit_demo(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="tributario-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo, *_ = _crea_fascicolo_tributario_pronto(gf)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "tributario-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.get(
            f"/fascicoli/{fascicolo.id}/wizard/ricorso_tributario/completa",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Pre-deposito PTT Tributario" in body
    assert "Verifica pre-deposito SIGIT" in body
    assert "Simula invio SIGIT" in body
    assert 'name="canale_deposito" value="PTT_TRIBUTARIO"' in body
    assert "PTT_RICORSI" in body


def test_deposito_invia_pec_tributario_demo_registra_esito(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="tributario-operatore",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo, atto, procura, notifica, contributo, indice, nir = _crea_fascicolo_tributario_pronto(gf)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "tributario-operatore", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "canale_deposito": "PTT_TRIBUTARIO",
                "codice_ufficio": "CPT030000",
                "tipo_atto": "RICORSO",
                "codice_registro": "PTT_RICORSI",
                "oggetto": "Ricorso tributario contro avviso di accertamento",
                "atto_principale_id": atto.id,
                "allegati_ids": [
                    procura.id,
                    notifica.id,
                    contributo.id,
                    indice.id,
                    nir.id,
                ],
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["demo"] is True
    assert payload["tipo_atto"] == "RICORSO"
    assert payload["validation"]["channel"] == "PTT_TRIBUTARIO"
    assert payload["validation"]["can_prepare_deposit"] is True
    assert payload["pec_dest"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.depositi_pct) == 1
    deposito = fascicolo_reload.depositi_pct[0]
    assert deposito.id == payload["id_deposito"]
    assert deposito.tipo_atto == "RICORSO"


def test_deposito_invia_pec_civile_usa_local_signer_se_server_send_disabilitato(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)

    def resolver_pst_non_disponibile(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            "Download PST non riuscito: https://servizipst.giustizia.it/PST/it/pst_2_4.wp"
        )

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_pst_non_disponibile,
    )
    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    libreria = tmp_path / "token-pkcs11.dll"
    libreria.write_bytes(b"fake")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=StudioConfigPEC(
                indirizzo="studio@example.pec.it",
                password="",
                smtp_host="smtp.example.pec.it",
                smtp_port=465,
                use_ssl=True,
            ),
            firma=ConfigFirma(backend_preferito="pkcs11", pkcs11_library=str(libreria)),
        )
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-locale-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    data = {
        "tipo_atto": "MEMORIA",
        "codice_registro": "RG",
        "codice_oggetto_pst": "014001",
        "oggetto": "Memoria civile",
        "numero_rg": "123",
        "anno_rg": "2026",
        "tribunale_nome": "Tribunale di Test",
        "tribunale_pec": "ufficio@example.pec.it",
        "atto_principale_id": atto.id,
        "demo_mode": "0",
    }
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-locale-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia",
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert response.status_code == 409
        raw_body = response.get_data(as_text=True)
        assert "Download PST non riuscito" not in raw_body
        assert "https://servizipst.giustizia.it" not in raw_body
        payload = response.get_json()
        assert payload["ok"] is False
        assert payload["requires_guided_completion"] is True
        assert payload["package_ready"] is True
        assert payload["pec_dest"] == "ufficio@example.pec.it"
        assert payload["busta_audit"]["blocks_direct_send"] is True
        assert payload["busta_audit"]["required_encryption_algorithm"] == "AES256"
        assert payload["busta_audit"]["atto_msg_generated"] is True
        assert payload["busta_audit"]["atto_enc_path"] == ""
        assert "https://" not in payload["busta_audit"]["certificate_error"]
        assert any("Atto.enc" in action and "AES256" in action for action in payload["next_actions"])
        assert any(".cer" in action for action in payload["next_actions"])

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []
    assert not fascicolo_reload.documenti[0].id_deposito_pct


def test_deposito_invia_pec_simula_invio_senza_spedire_quando_busta_conforme(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_da_nome",
        lambda nome: {"codice": "TEST001", "pec": "tribunale.test@civile.ptel.giustiziacert.it", "nome": nome},
    )
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-simulazione-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-simulazione-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "simula_invio_pec": "1",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["simulazione"] is True
    assert payload["requires_local_pec"] is False
    assert "message_id" not in payload
    assert "senza invio reale" in payload["messaggio"]
    assert "Il pacchetto locale" in payload["messaggio"]
    report = payload["compatibility_report"]
    assert report["percentuale"] == 100
    assert report["blockers"] == 0
    corpo_check = next(item for item in report["checks"] if item["code"] == "CORPO_PEC")
    assert corpo_check["status"] == "ok"
    local_payload = payload["local_pec"]["payload"]
    assert local_payload["attachments"][0]["filename"] == "Atto.enc"
    assert local_payload["attachments"][0]["content_base64"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.depositi_pct) == 1
    deposito = fascicolo_reload.depositi_pct[0]
    assert deposito.stato == "PROVA_SENZA_INVIO"
    assert "Payload Local Signer completo con Atto.enc" in deposito.messaggio
    assert "Nessun invio esterno eseguito" in deposito.messaggio
    assert "PROVA SENZA INVIO REALE" in deposito.note
    doc_reload = next(doc for doc in fascicolo_reload.documenti if doc.id == atto.id)
    assert not doc_reload.id_deposito_pct


def test_deposito_invia_pec_reale_payload_local_signer_base64_e_corpo_finale(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=StudioConfigPEC(
                indirizzo="studio@example.pec.it",
                password="secret",
                smtp_host="smtp.example.pec.it",
                smtp_port=465,
                use_ssl=True,
            )
        )
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-reale-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Ricorso civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "Ricorso.pdf.p7m",
        TipoDocumento.RICORSO,
        _cades_signed_pdf(),
        firmato=True,
    )
    allegato = gf.aggiungi_documento(
        fascicolo.id,
        "Autocertificazione ricorso_63ee.PDF",
        TipoDocumento.ALLEGATO,
        _pdf_base(),
        firmato=False,
    )
    procura = gf.aggiungi_documento(
        fascicolo.id,
        "Procura.PDF.p7m",
        TipoDocumento.PROCURA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    request_data = {
        "tipo_atto": "RICORSO",
        "codice_registro": "RG",
        "codice_oggetto_pst": "014001",
        "oggetto": "Ricorso civile",
        "numero_rg": "123",
        "anno_rg": "2026",
        "atto_principale_id": atto.id,
        "allegati_ids": [allegato.id, procura.id],
        "corpo_pec": (
            "Egregio sig. Cancelliere,\n\n"
            "Allego alla presente il file crittografato Atto.enc per il deposito telematico.\n\n"
            "Il file Atto.enc contiene i seguenti documenti:\n"
            "- Autocertificazione ricorso.PDF"
        ),
    }
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-reale-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        simulation_response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={**request_data, "simula_invio_pec": "1"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data=request_data,
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert simulation_response.status_code == 200, simulation_response.get_data(as_text=True)
    simulation_payload = simulation_response.get_json()
    assert simulation_payload["compatibility_report"]["percentuale"] == 100
    simulation_corpo_check = next(
        item for item in simulation_payload["compatibility_report"]["checks"] if item["code"] == "CORPO_PEC"
    )
    assert simulation_corpo_check["status"] == "ok"
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["requires_local_pec"] is True
    local_payload = payload["local_pec"]["payload"]
    attachment = local_payload["attachments"][0]
    assert attachment["filename"] == "Atto.enc"
    assert base64.b64decode(attachment["content_base64"], validate=True) == b"ATTO-ENC-CONFORME"
    assert "Ricorso.pdf.p7m" in payload["corpo_pec"]
    assert "Autocertificazione ricorso_63ee.PDF" in payload["corpo_pec"]
    assert "Procura.PDF.p7m" in payload["corpo_pec"]
    assert "Autocertificazione ricorso.PDF" not in payload["corpo_pec"]
    corpo_check = next(item for item in payload["compatibility_report"]["checks"] if item["code"] == "CORPO_PEC")
    assert corpo_check["status"] == "ok"


def test_deposito_invia_pec_simulazione_guidata_non_restituisce_conflitto_http(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def resolver_pst_non_disponibile(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError("Certificato PST non disponibile")

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_pst_non_disponibile,
    )

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-simulazione-guidata-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-simulazione-guidata-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "simula_invio_pec": "1",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["requires_guided_completion"] is True
    assert payload["package_ready"] is True
    assert payload["pec_dest"] == "tribunale.test@civile.ptel.giustiziacert.it"
    assert payload["local_pec"]["payload"]["to"] == "tribunale.test@civile.ptel.giustiziacert.it"
    assert payload["pec_sender_ready"] is False
    assert "Atto.enc" in payload["message"]
    assert any(".cer" in action or "Atto.enc" in action for action in payload["next_actions"])

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []


def test_deposito_invia_pec_prova_senza_invio_non_restituisce_conflitto_http(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=StudioConfigPEC(
                indirizzo="studio@example.pec.it",
                password="secret",
                smtp_host="smtp.example.pec.it",
                smtp_port=465,
                use_ssl=True,
            )
        )
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-prova-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-prova-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "prova_senza_invio": "1",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["requires_local_pec"] is True
    assert payload["package_ready"] is True
    assert payload["pec_dest"] == "ufficio@example.pec.it"
    assert payload["local_pec"]["payload"]["smtp_host"] == "smtp.example.pec.it"
    assert "Nessun invio PEC reale" in payload["messaggio"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []


def test_deposito_invia_pec_reale_richiede_sempre_local_signer_anche_con_smtp_server_abilitato(tmp_path, monkeypatch):
    monkeypatch.setenv("PEC_SEND_ENABLED", "1")
    monkeypatch.setenv("PCT_PEC_SERVER_SEND_ENABLED", "1")
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    class ExplodingClientPEC:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Il deposito reale deve passare dal Local Signer locale, non dallo SMTP server.")

    monkeypatch.setattr("pct.pec.ClientPEC", ExplodingClientPEC)

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=StudioConfigPEC(
                indirizzo="studio@example.pec.it",
                password="secret",
                smtp_host="smtp.example.pec.it",
                smtp_port=465,
                use_ssl=True,
            )
        )
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-local-signer-only-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )
    corpo_pec = "Corpo PEC controllato dall'avvocato prima dell'invio locale."

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-local-signer-only-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "corpo_pec": corpo_pec,
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["requires_local_pec"] is True
    assert payload["package_ready"] is True
    assert payload["pec_dest"] == "ufficio@example.pec.it"
    assert payload["corpo_pec"] == corpo_pec
    assert payload["local_pec"]["channel"] == "local_signer"
    assert payload["local_pec"]["endpoint"] == "http://127.0.0.1:27272/pec/send"
    assert payload["local_pec"]["payload"]["smtp_host"] == "smtp.example.pec.it"
    assert payload["local_pec"]["payload"]["to"] == "ufficio@example.pec.it"

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []


def test_deposito_legacy_invia_richiede_sempre_local_signer_anche_con_smtp_server_abilitato(tmp_path, monkeypatch):
    monkeypatch.setenv("PEC_SEND_ENABLED", "1")
    monkeypatch.setenv("PCT_PEC_SERVER_SEND_ENABLED", "1")
    monkeypatch.setattr(
        "web.bootstrap.deposito_legacy_send_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")
    GestioneConfigStudio(cfg["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=StudioConfigPEC(
                indirizzo="studio@example.pec.it",
                password="secret",
                smtp_host="smtp.example.pec.it",
                smtp_port=465,
                use_ssl=True,
            )
        )
    )

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-legacy-local-only-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-legacy-local-only-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "demo_mode": "0",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["requires_local_pec"] is True
    assert payload["local_pec"]["channel"] == "local_signer"
    assert payload["local_pec"]["payload"]["smtp_host"] == "smtp.example.pec.it"
    assert payload["local_pec"]["payload"]["to"] == "ufficio@example.pec.it"

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []


def test_deposito_invia_pec_prova_senza_invio_mostra_preview_anche_senza_pec_mittente(tmp_path, monkeypatch):
    monkeypatch.delenv("PEC_SEND_ENABLED", raising=False)
    monkeypatch.delenv("PCT_PEC_SERVER_SEND_ENABLED", raising=False)
    monkeypatch.setattr(
        "web.bootstrap.deposito_routes._ufficio_deposito_destinatario",
        lambda fascicolo: {
            "codice_ufficio": "TEST001",
            "pec_dest": "tribunale.test@civile.ptel.giustiziacert.it",
            "nome": "Tribunale di Test",
        },
    )

    def fake_crea_busta(self, output_dir):
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        enc = path / "Atto.enc"
        enc.write_bytes(b"ATTO-ENC-CONFORME")
        self._last_transport_audit = {
            "transport_mode": "atto_enc_aes256",
            "required_encryption_algorithm": "AES256",
            "uses_real_encryption": True,
            "atto_msg_generated": True,
            "atto_enc_path": str(enc),
            "guided_next_actions": [],
        }
        return str(enc)

    monkeypatch.setattr("pct.busta.BustaTelematica.crea_busta", fake_crea_busta)

    cfg = _cfg_web(tmp_path)
    cfg["STUDIO_CONFIG"] = str(tmp_path / "studio.json")

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="pec-preview-admin",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="admin@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Memoria civile",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Test",
        numero_rg="123",
        anno_rg=2026,
        controparte="Controparte",
        id_cliente="cliente-1",
    )
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf.p7m",
        TipoDocumento.MEMORIA,
        _cades_signed_pdf(),
        firmato=True,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "pec-preview-admin", "password": "Admin1234!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/deposito/invia-pec",
            data={
                "tipo_atto": "MEMORIA",
                "codice_registro": "RG",
                "codice_oggetto_pst": "014001",
                "oggetto": "Memoria civile",
                "numero_rg": "123",
                "anno_rg": "2026",
                "atto_principale_id": atto.id,
                "prova_senza_invio": "1",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert payload["requires_local_pec"] is True
    assert payload["package_ready"] is True
    assert payload["pec_dest"] == "tribunale.test@civile.ptel.giustiziacert.it"
    assert payload["local_pec"]["payload"]["to"] == "tribunale.test@civile.ptel.giustiziacert.it"
    assert payload["local_pec"]["payload"]["smtp_host"] == ""
    assert payload["pec_sender_ready"] is False
    assert any("PEC mittente dello studio non configurata" in item for item in payload["next_actions"])
    assert "Nessun invio PEC reale" in payload["messaggio"]

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.depositi_pct == []
