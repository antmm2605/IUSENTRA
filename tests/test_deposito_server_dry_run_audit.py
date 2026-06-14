from email.message import EmailMessage
from pathlib import Path

from pct.busta import Allegato, BustaTelematica, DatiBusta, INDICE_DOCUMENTI_FILENAME
from scripts.audit_deposito_server_dry_run import audit_deposito_package, main
from scripts.server_deposito_dry_run_http import build_deposito_form


def _pdf(path: Path, body: bytes = b"test") -> Path:
    path.write_bytes(b"%PDF-1.4\n" + body + b"\n%%EOF")
    return path


def _eml_with_attachments(path: Path, attachments: dict[str, bytes]) -> Path:
    message = EmailMessage()
    message["Subject"] = "COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO"
    message["From"] = "studio@example.invalid"
    message["To"] = "audit@example.invalid"
    message.set_content("Campione deposito reale sanificato.")
    for name, payload in attachments.items():
        maintype, subtype = ("application", "pdf")
        if name.lower().endswith(".xml.p7m"):
            subtype = "pkcs7-mime"
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=name)
    path.write_bytes(message.as_bytes())
    return path


def test_audit_dry_run_confronta_busta_con_copia_non_crittografata_e_blocca_invio_reale(tmp_path):
    atto = _pdf(tmp_path / "Ricorso.PDF", b"atto principale")
    allegato = _pdf(tmp_path / "Procura.PDF", b"procura")
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="RG",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(atto),
        allegati=[Allegato(percorso=str(allegato), descrizione="Procura", tipo="PROCURA")],
        numero_rg="1754",
        anno_rg=2026,
        operatore="Avv. Test",
    )
    package = Path(BustaTelematica(dati).crea_busta(str(tmp_path / "out")))
    evidence_copy = _eml_with_attachments(
        tmp_path / "copia-non-crittografata.eml",
        {
            "DatiAtto.xml.p7m": b"firmato",
            "Ricorso.PDF": b"atto",
            "Procura.PDF": b"procura",
            INDICE_DOCUMENTI_FILENAME: b"%PDF-1.4\nindice\n%%EOF",
        },
    )
    evidence_send = _eml_with_attachments(tmp_path / "invio-reale.eml", {"Atto.enc": b"encrypted"})

    report = audit_deposito_package(package, [evidence_copy, evidence_send])

    assert report["ok_control_package"] is True
    assert report["ok_real_transport"] is False
    assert report["must_not_send_real_pec"] is True
    assert report["generated"]["has_dati_atto_xml"] is True
    assert report["generated"]["has_indice_documenti"] is True
    assert report["evidence"]["has_real_atto_enc"] is True
    codes = {item["code"] for item in report["comparison"]["differences"]}
    assert {"DATI_ATTO_UNSIGNED", "ATTO_ENC_AES256_MISSING"} <= codes


def test_cli_audit_dry_run_strict_real_transport_esce_con_blocco(tmp_path, capsys):
    atto = _pdf(tmp_path / "Atto.PDF")
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="RG",
        oggetto="014001",
        tipo_atto="MEMORIA",
        atto_principale=str(atto),
    )
    package = Path(BustaTelematica(dati).crea_busta(str(tmp_path / "out")))
    evidence_copy = _eml_with_attachments(
        tmp_path / "copia.eml",
        {
            "DatiAtto.xml.p7m": b"firmato",
            INDICE_DOCUMENTI_FILENAME: b"%PDF-1.4\nindice\n%%EOF",
        },
    )

    rc = main(
        [
            "--package",
            str(package),
            "--evidence",
            str(evidence_copy),
            "--strict-real-transport",
        ]
    )

    assert rc == 2
    assert "ATTO_ENC_AES256_MISSING" in capsys.readouterr().out


def test_runner_server_dry_run_usa_proposta_react_e_prove_notifica():
    payload = {
        "fascicolo": {
            "id": "EFBE9117",
            "ref": "RG 1754/2026",
            "title": "Vinci Rosa Maria",
            "client": "Vinci Rosa Maria",
            "codiceOggettoPst": "222050 - Retribuzione",
            "rgNumber": "1754",
            "rgYear": "2026",
            "type": "Lavoro",
        },
        "regia": {
            "profile": {"procedureCode": "PROC_LAV_RETRIB_001"},
            "documentSlots": [
                {"slotKey": "ATTO_PRINCIPALE", "documentId": "doc-atto"},
                {"slotKey": "PROCURA", "documentId": "doc-procura"},
            ],
        },
        "documents": [
            {"id": "doc-atto", "name": "Ricorso originale notificato.PDF", "type": "Atto giudiziario", "signed": True, "tags": []},
            {"id": "doc-procura", "name": "Procura.PDF", "type": "Procura", "signed": True, "tags": []},
            {"id": "doc-rac", "name": "ACCETTAZIONE_ Notificazione ai sensi della legge n. 53.eml", "type": "Comunicazione", "signed": False, "tags": []},
            {"id": "doc-rdac", "name": "CONSEGNA_ Notificazione ai sensi della legge n. 53.eml", "type": "Comunicazione", "signed": False, "tags": []},
            {"id": "doc-pec-ufficio", "name": "POSTA CERTIFICATA: comunicazione cancelleria 274-2026.eml", "type": "Comunicazione", "signed": False, "tags": []},
            {"id": "doc-decreto", "name": "Decreto fissazione udienza (originale notificato).pdf", "type": "Documento portale", "signed": False, "portalClass": "documento", "tags": []},
        ],
    }

    form, summary = build_deposito_form(payload)

    assert form["atto_principale_id"] == "doc-atto"
    assert form["codice_oggetto_pst"] == "222050 - Retribuzione"
    assert form["codice_registro"] == "RGL"
    assert form["documenti_selezionati_ids"] == ["doc-atto", "doc-procura", "doc-rac", "doc-rdac", "doc-decreto"]
    assert "doc-pec-ufficio" not in form["documenti_selezionati_ids"]
    assert summary["totalSelected"] == 5
