from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from pct.auth import GestioneUtenti, RuoloUtente
from pct.busta import DatiBusta
from pct.cli import cli
from pct.config_studio import ConfigFirma, ConfigStudio, GestioneConfigStudio
from pct.deposito import DepositoCivile
from pct.fascicoli import EsitoDepositoPCT, GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.firma import FirmaDigitale
from pct.pec import ConfigPEC
from web.app import create_app


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
                follow_redirects=True,
            )

    assert response.status_code == 200
    assert b"solo CAdES" in response.data

    gf_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gf_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.documenti[0].nome == "atto.pdf"
    assert fascicolo_reload.documenti[0].firmato_digitalmente is False


def test_api_pkcs11_firma_documento_blocca_pades(tmp_path):
    cfg = _cfg_web(tmp_path)
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
