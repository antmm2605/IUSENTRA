from email.message import EmailMessage
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

from pct.busta import Allegato, BustaTelematica, DatiBusta, INDICE_BUSTA_FILENAME, INDICE_DOCUMENTI_FILENAME
from web.services.deposito_route_helpers import guided_transport_completion_response
from web.services.local_pec_runtime import deposito_pec_body
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


def _anagrafica_ministeriale_minima() -> bytes:
    return b'<AnagraficaProcedimento xmlns="http://schemi.processotelematico.giustizia.it/tipi/atti/v6"/>'


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
    evidence_send = _eml_with_attachments(tmp_path / "invio-reale.eml", {"Atto.enc": package.read_bytes()})

    report = audit_deposito_package(package, [evidence_copy, evidence_send])

    assert report["ok_control_package"] is True
    assert report["ok_real_transport"] is True
    assert report["must_not_send_real_pec"] is True
    assert report["generated"]["has_dati_atto_xml"] is True
    assert report["generated"]["has_indice_documenti"] is True
    assert report["evidence"]["has_real_atto_enc"] is True
    codes = {item["code"] for item in report["comparison"]["differences"]}
    assert "DATI_ATTO_UNSIGNED" in codes
    assert "ATTO_ENC_AES256_MISSING" not in codes


def test_audit_dry_run_richiede_indice_busta_xml_esterno(tmp_path):
    atto = _pdf(tmp_path / "Ricorso.pdf", b"atto principale")
    allegato = _pdf(tmp_path / "Documento.pdf", b"allegato")
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="RG",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(atto),
        allegati=[Allegato(percorso=str(allegato), descrizione="Documento", tipo="ALLEGATO")],
        anagrafica_procedimento_xml=_anagrafica_ministeriale_minima(),
    )
    package = Path(BustaTelematica(dati).crea_busta(str(tmp_path / "out")))
    evidence_copy = _eml_with_attachments(
        tmp_path / "copia-non-crittografata.eml",
        {
            "DatiAtto.xml": b"<DatiAtto/>",
            INDICE_DOCUMENTI_FILENAME: b"%PDF-1.4\nindice\n%%EOF",
        },
    )

    report = audit_deposito_package(package, [evidence_copy])

    assert report["ok_control_package"] is True
    assert report["generated"]["has_indice_busta_xml"] is True
    assert report["generated"]["indice_busta_mode"] == "indice_busta_xml"
    assert report["generated"]["has_indice_busta_internal"] is False
    codes = {item["code"] for item in report["comparison"]["differences"]}
    assert "INDICE_BUSTA_MISSING" not in codes
    assert "INDICE_BUSTA_AMBIGUOUS" not in codes
    assert "INDICE_BUSTA_TIPI" not in codes


def test_audit_dry_run_blocca_ricevuta_telematica_senza_tipo_rt(tmp_path):
    atto = _pdf(tmp_path / "Ricorso.pdf", b"atto principale")
    ricevuta = _pdf(tmp_path / "Ricevuta telematica pagamento PagoPA.pdf", b"rt")
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="RG",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(atto),
        allegati=[Allegato(percorso=str(ricevuta), descrizione="Ricevuta telematica pagamento", tipo="ALLEGATO")],
    )
    package = Path(BustaTelematica(dati).crea_busta(str(tmp_path / "out")))
    atto_msg = package.with_name("Atto.msg")
    parts = _eml_with_attachments(
        tmp_path / "copia-non-crittografata.eml",
        {
            "DatiAtto.xml": b"<DatiAtto/>",
            INDICE_DOCUMENTI_FILENAME: b"%PDF-1.4\nindice\n%%EOF",
        },
    )

    # Corrompe solo l'indice di controllo: il nome della ricevuta resta presente, ma non e' marcato RT.
    from email import policy
    from email.parser import BytesParser

    message = BytesParser(policy=policy.default).parsebytes(atto_msg.read_bytes())
    corrupted = EmailMessage()
    corrupted["Subject"] = message["Subject"] or "Atto"
    corrupted.make_related()
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename() or part.get_param("name", header="Content-Type") or ""
        payload = part.get_payload(decode=True) or b""
        maintype, _, subtype = part.get_content_type().partition("/")
        if Path(filename).name == INDICE_BUSTA_FILENAME:
            root = ET.fromstring(payload)
            node = next(item for item in root.findall("Allegato") if item.attrib.get("Nome") == ricevuta.name)
            node.set("Tipo", "SM")
            payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        corrupted.add_attachment(payload, maintype=maintype, subtype=subtype or "octet-stream", filename=filename)
    atto_msg.write_bytes(corrupted.as_bytes(policy=policy.default))

    report = audit_deposito_package(package, [parts])

    assert report["ok_control_package"] is False
    assert report["generated"]["indice_busta_tipi_ok"] is False
    codes = {item["code"]: item["level"] for item in report["comparison"]["differences"]}
    assert codes["INDICE_BUSTA_TIPI"] == "block_control"


def test_audit_dry_run_blocca_indice_interno_con_xml_esterno(tmp_path):
    package = tmp_path / "busta.zip"
    dati_atto = b"""<?xml version="1.0" encoding="UTF-8"?>
<Ricorso xmlns="http://schemi.processotelematico.giustizia.it/tipi/introduzione/v2">
  <IndiceBusta xmlns="http://schemi.processotelematico.giustizia.it/tipi/atti/v6"/>
</Ricorso>
"""
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("DatiAtto.xml", dati_atto)
        zf.writestr("IndiceBusta.xml", b"<IndiceBusta/>")
        zf.writestr(INDICE_DOCUMENTI_FILENAME, b"%PDF-1.4\nindice\n%%EOF")
    evidence_copy = _eml_with_attachments(
        tmp_path / "copia.eml",
        {
            "DatiAtto.xml": dati_atto,
            INDICE_DOCUMENTI_FILENAME: b"%PDF-1.4\nindice\n%%EOF",
        },
    )

    report = audit_deposito_package(package, [evidence_copy])
    assert report["ok_control_package"] is False
    assert report["generated"]["indice_busta_mode"] == "ambiguo_indice_interno_e_xml"
    codes = {item["code"]: item["level"] for item in report["comparison"]["differences"]}
    assert codes["INDICE_BUSTA_AMBIGUOUS"] == "block_control"

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


def test_prova_guidata_espone_destinatario_pec_testo_e_documenti(tmp_path):
    atto = _pdf(tmp_path / "Ricorso.PDF", b"atto principale")
    allegato = _pdf(tmp_path / "Procura.PDF", b"procura")
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="RG",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(atto),
        allegati=[Allegato(percorso=str(allegato), descrizione="Procura", tipo="PROCURA")],
        numero_rg="330",
        anno_rg=2026,
        operatore="Avv. Test",
    )
    busta = BustaTelematica(dati)
    package = str(tmp_path / "Atto.enc")
    Path(package).write_bytes(b"non-generato")
    documenti = ["DatiAtto.xml", "Ricorso.PDF", "Procura.PDF", INDICE_DOCUMENTI_FILENAME]
    corpo = deposito_pec_body(documenti)

    response = guided_transport_completion_response(
        busta=busta,
        id_deposito="TEST330",
        timestamp="2026-06-16T20:30:00",
        pec_dest="tribunale.vicenza@civile.ptel.giustiziacert.it",
        tipo_atto="RICORSO",
        oggetto_pec="DEPOSITO TELEMATICO: Ricorso RG 330/2026",
        corpo_pec=corpo,
        documenti_busta=documenti,
        attachment_path=package,
        validation={"ok": True},
    )

    assert response is not None
    assert response["ok"] is False
    assert response["package_ready"] is True
    assert response["requires_guided_completion"] is True
    assert response["pec_dest"] == "tribunale.vicenza@civile.ptel.giustiziacert.it"
    assert "DEPOSITO TELEMATICO: Ricorso" in response["oggetto_pec"]
    assert "Egregio sig. Cancelliere" in response["corpo_pec"]
    assert "Atto.enc" in response["corpo_pec"]
    assert "IUSENTRA Local Signer" not in response["corpo_pec"]
    assert response["documenti_busta"] == documenti
    assert INDICE_DOCUMENTI_FILENAME in response["documenti_busta"]
    assert response["busta_audit"]["blocks_direct_send"] is True
