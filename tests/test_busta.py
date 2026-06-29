"""Test per la creazione della busta telematica."""

import os
import tempfile
import pytest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from pct.busta import (
    BustaTelematica,
    DatiBusta,
    Allegato,
    ATTO_MSG_FILENAME,
    DATI_ATTO_FILENAME,
    DATI_ATTO_FIRMATO_FILENAME,
    INDICE_BUSTA_FILENAME,
    INDICE_DOCUMENTI_FILENAME,
)
from pct.firma import estrai_contenuto_cades
from pct.pst_cifratura import PSTCifraturaError


@pytest.fixture
def tmp_pdf(tmp_path):
    """Crea un PDF di test."""
    pdf = tmp_path / "atto.pdf"
    # PDF minimo valido
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
    )
    return str(pdf)


@pytest.fixture
def dati_busta(tmp_pdf):
    """Dati di test per la busta."""
    return DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Memoria difensiva - RG 1234/2024",
        tipo_atto="MEMORIA",
        atto_principale=tmp_pdf,
        allegati=[],
        numero_rg="1234",
        anno_rg=2024,
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
    )


def test_crea_busta(dati_busta, tmp_path):
    """Verifica che la busta venga creata correttamente."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    assert Path(busta_path).exists()
    assert busta_path.endswith(".enc")


def _atto_msg_attachments(busta_path: str | Path) -> dict[str, bytes]:
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
    attachments = {}
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name
        if filename:
            attachments[filename] = part.get_payload(decode=True) or b""
    return attachments


def _cades_signed_payload(payload: bytes) -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Firma DatiAtto")]
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
    signed_attrs = local_signer_mod._build_signed_attrs_der_inline(payload)
    signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
    return _build_cades_bes(
        documento=payload,
        signature_bytes=signature,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs,
        detached=False,
    )


def test_busta_contiene_xml(dati_busta, tmp_path):
    """Verifica che la busta contenga il file DatiAtto.xml."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    assert DATI_ATTO_FILENAME in attachments
    assert INDICE_BUSTA_FILENAME in attachments
    assert INDICE_DOCUMENTI_FILENAME in attachments


def test_busta_contiene_indice_busta_ministeriale(dati_busta, tmp_path):
    """Verifica che Atto.msg contenga IndiceBusta.xml, distinto dal PDF indice."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    root = etree.fromstring(attachments[INDICE_BUSTA_FILENAME])
    assert root.tag == "IndiceBusta"
    atto = root.find("Atto")
    assert atto is not None
    assert atto.get("Nome") == "atto.pdf"
    dati = [node for node in root.findall("Allegato") if node.get("Tipo") == "DA"]
    assert dati
    assert dati[0].get("Nome") == DATI_ATTO_FILENAME


def test_atto_msg_usa_mime_file_parts_compatibili_con_parser_pst(dati_busta, tmp_path):
    """IndiceBusta.xml deve essere una parte MIME nominata, senza corpo testo extra."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())

    assert message.get_content_type() == "multipart/related"
    leaf_parts = [part for part in message.walk() if not part.is_multipart()]
    assert leaf_parts
    assert all(part.get_filename() or part.get_param("name", header="Content-Type") for part in leaf_parts)
    assert "text/plain" not in {part.get_content_type() for part in leaf_parts}

    indice_part = next(
        part
        for part in leaf_parts
        if Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name
        == INDICE_BUSTA_FILENAME
    )
    assert indice_part.get_content_type() == "text/xml"
    assert indice_part.get_param("name", header="Content-Type") == INDICE_BUSTA_FILENAME
    assert indice_part.get_content_disposition() == "inline"
    assert indice_part.get("Content-ID") == f"<{INDICE_BUSTA_FILENAME}>"
    assert indice_part.get("Content-Transfer-Encoding", "").lower() != "base64"
    assert etree.fromstring(indice_part.get_payload(decode=True)).tag == "IndiceBusta"


def test_busta_reale_usa_dati_atto_firmato_nell_indice_busta(dati_busta, tmp_path):
    """Quando DatiAtto.xml è firmato, Atto.msg usa il .p7m e l'indice ministeriale lo richiama."""
    from lxml import etree

    busta = BustaTelematica(
        dati_busta,
        id_busta="D78E4A75-B17D-428B-9DE7-DCFFD20959CD",
        timestamp="2026-06-23T09:10:00",
    )
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()
    dati_atto_firmato = _cades_signed_payload(dati_atto_xml)
    busta_path = busta.crea_busta(
        str(tmp_path),
        dati_atto_firmato=dati_atto_firmato,
        require_dati_atto_firmato=True,
    )

    attachments = _atto_msg_attachments(busta_path)
    assert DATI_ATTO_FIRMATO_FILENAME in attachments
    assert DATI_ATTO_FILENAME not in attachments
    assert estrai_contenuto_cades(attachments[DATI_ATTO_FIRMATO_FILENAME]) == dati_atto_xml
    root = etree.fromstring(attachments[INDICE_BUSTA_FILENAME])
    dati = [node for node in root.findall("Allegato") if node.get("Tipo") == "DA"]
    assert dati[0].get("Nome") == DATI_ATTO_FIRMATO_FILENAME
    audit = busta.audit_conformita_pst()
    assert audit["dati_atto_signed"] is True
    assert not any(issue["code"] == "DATI-ATTO-SIGNATURE-MISSING" for issue in audit["issues"])
    assert audit["atto_msg_indice_busta_valid"] is True
    assert audit["busta_verifica_valida"] is True
    assert audit["atto_enc_cms_valid"] is True
    assert audit["atto_enc_sha256"]
    assert audit["indice_busta_atto_filename"] == "atto.pdf"
    assert audit["indice_busta_dati_atto_filename"] == DATI_ATTO_FIRMATO_FILENAME
    assert audit["formal_checks"]["T002"]["status"] == "ok"


def test_dati_atto_per_firma_e_deterministico_con_stessa_busta(dati_busta):
    id_busta = "D78E4A75-B17D-428B-9DE7-DCFFD20959CD"
    timestamp = "2026-06-23T09:10:00"
    busta_a = BustaTelematica(dati_busta, id_busta=id_busta, timestamp=timestamp)
    busta_b = BustaTelematica(dati_busta, id_busta=id_busta, timestamp=timestamp)

    assert busta_a.crea_dati_atto_xml_per_firma() == busta_b.crea_dati_atto_xml_per_firma()


def test_datiatto_contiene_indice_documenti_generato(dati_busta, tmp_path):
    """Verifica che l'indice generato sia richiamato nei metadati della busta."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    xml_bytes = attachments[DATI_ATTO_FILENAME]
    indice_bytes = attachments[INDICE_DOCUMENTI_FILENAME]

    root = etree.fromstring(xml_bytes)
    ns = {"p": "http://www.giustizia.it/processo_telematico"}
    indice_node = root.find(f".//p:Documenti/p:Allegato[p:NomeFile='{INDICE_DOCUMENTI_FILENAME}']", ns)
    assert indice_node is not None
    assert indice_node.findtext("p:Tipo", namespaces=ns) == "INDICE_DOCUMENTI"
    assert indice_node.findtext("p:Hash", namespaces=ns) == BustaTelematica._hash_bytes(indice_bytes)


def test_indice_documenti_pdf_disponibile_per_anteprima(dati_busta):
    """Verifica che l'indice documenti possa essere mostrato prima dell'invio."""
    busta = BustaTelematica(dati_busta)
    indice_pdf = busta.crea_indice_documenti_pdf()

    assert indice_pdf.startswith(b"%PDF")
    assert b"%%EOF" in indice_pdf
    assert len(indice_pdf) > 250


def test_busta_contiene_atto(dati_busta, tmp_path):
    """Verifica che la busta contenga l'atto principale."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    assert "atto.pdf" in attachments


def test_verifica_busta_valida(dati_busta, tmp_path):
    """Verifica che la verifica della busta funzioni."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))
    risultato = busta.verifica_busta(busta_path)

    assert risultato["valida"] is True
    assert risultato["id_busta"] is not None
    assert risultato["audit_tecnico"]["transport_mode"] == "atto_enc_da_atto_msg_cifrato_aes256"
    assert risultato["audit_tecnico"]["uses_real_encryption"] is True
    assert risultato["audit_tecnico"]["formal_checks"]["T001"]["status"] == "ok"
    assert risultato["audit_tecnico"]["indice_busta_generated"] is True
    assert risultato["audit_tecnico"]["atto_msg_indice_busta_valid"] is True
    assert risultato["audit_tecnico"]["busta_verifica_valida"] is True
    assert risultato["audit_tecnico"]["atto_enc_sha256"]
    assert INDICE_BUSTA_FILENAME in _atto_msg_attachments(busta_path)
    assert INDICE_DOCUMENTI_FILENAME in risultato["documenti"]


def test_busta_blocca_indice_busta_non_coerente_con_atto_msg(dati_busta, tmp_path, monkeypatch):
    """La busta non deve arrivare ad Atto.enc se IndiceBusta.xml richiama file assenti."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)

    def indice_corrotto(*, dati_atto_filename=DATI_ATTO_FILENAME):
        root = etree.Element("IndiceBusta")
        etree.SubElement(root, "Atto", Nome="atto_sbagliato.pdf", ID="ATTO_1")
        etree.SubElement(root, "Allegato", Nome=dati_atto_filename, ID="DATI_1", Tipo="DA")
        etree.SubElement(root, "Allegato", Nome=INDICE_DOCUMENTI_FILENAME, ID="INDICE_1", Tipo="SM")
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    monkeypatch.setattr(busta, "_crea_indice_busta_xml", indice_corrotto)

    with pytest.raises(ValueError, match="IndiceBusta.xml"):
        busta.crea_busta(str(tmp_path))


def test_audit_busta_blocca_prima_della_generazione_reale(dati_busta):
    busta = BustaTelematica(dati_busta)
    audit = busta.audit_conformita_pst()

    assert audit["uses_real_encryption"] is False
    assert audit["atto_msg_generated"] is False
    assert audit["required_encryption_algorithm"] == "AES256"
    assert audit["expected_transport_mode"] == "atto_enc_da_atto_msg_cifrato_aes256"
    assert audit["blocks_direct_send"] is True
    assert audit["guided_completion_required"] is True
    assert audit["indice_busta_generated"] is True
    assert audit["indice_busta_filename"] == INDICE_BUSTA_FILENAME
    assert audit["dati_atto_signed"] is False
    assert any(issue["code"] == "DATI-ATTO-SIGNATURE-MISSING" for issue in audit["issues"])
    assert any("Atto.enc" in action and "AES256" in action for action in audit["guided_next_actions"])
    assert audit["formal_checks"]["T002"]["status"] == "warning"
    issue = next(issue for issue in audit["issues"] if issue["code"] == "ATTO-ENC-MISSING")
    assert "Atto.msg" in issue["detail"]
    assert "AES256" in issue["detail"]


def test_busta_con_certificato_pst_non_disponibile_conserva_atto_msg(dati_busta, tmp_path, monkeypatch):
    def resolver_non_disponibile(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            "Download PST non riuscito: https://servizipst.giustizia.it/PST/it/pst_2_4.wp"
        )

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_non_disponibile,
    )
    busta = BustaTelematica(dati_busta)

    with pytest.raises(PSTCifraturaError):
        busta.crea_busta(str(tmp_path))

    audit = busta.audit_conformita_pst()
    assert audit["uses_real_encryption"] is False
    assert audit["transport_mode"] == "atto_msg_generato_cifratura_pst_non_completata"
    assert audit["atto_msg_generated"] is True
    assert audit["atto_enc_path"] == ""
    assert Path(audit["atto_msg_path"]).name == ATTO_MSG_FILENAME
    assert Path(audit["atto_msg_path"]).exists()
    assert audit["blocks_direct_send"] is True
    assert audit["guided_completion_required"] is True
    assert ".cer" in audit["certificate_error"]
    assert "https://" not in audit["certificate_error"]
    assert any(".cer" in action for action in audit["guided_next_actions"])
    assert any("Atto.enc" in action and "AES256" in action for action in audit["guided_next_actions"])
    assert not any("https://" in action for action in audit["guided_next_actions"])


def test_busta_con_certificato_pst_non_pubblicato_spiega_blocco(dati_busta, tmp_path, monkeypatch):
    def resolver_non_pubblicato(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            f"Certificato di cifratura PST non trovato per l'ufficio {codice_ufficio}."
        )

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_non_pubblicato,
    )
    busta = BustaTelematica(dati_busta)

    with pytest.raises(PSTCifraturaError):
        busta.crea_busta(str(tmp_path))

    audit = busta.audit_conformita_pst()
    assert audit["certificate_error_code"] == "certificato_cifratura_non_pubblicato"
    assert "non pubblica" in audit["certificate_error"]
    assert "PST" in audit["certificate_error"]
    assert "Atto.enc" in " ".join(audit["guided_next_actions"])
    assert "diverso ufficio/canale ufficiale" in " ".join(audit["guided_next_actions"])


def test_busta_con_allegati(tmp_path, tmp_pdf):
    """Verifica che gli allegati vengano inclusi nella busta."""
    allegato_path = tmp_path / "allegato.pdf"
    allegato_path.write_bytes(b"%PDF-1.4\n%%EOF")

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Test con allegati",
        tipo_atto="RICORSO",
        atto_principale=tmp_pdf,
        allegati=[
            Allegato(
                percorso=str(allegato_path),
                descrizione="Documento allegato",
                tipo="ALLEGATO",
            )
        ],
    )

    busta = BustaTelematica(dati)
    busta_path = busta.crea_busta(str(tmp_path / "output"))

    attachments = _atto_msg_attachments(busta_path)
    assert "allegato.pdf" in attachments


def test_id_busta_univoco(dati_busta, tmp_path):
    """Verifica che ogni busta abbia un ID univoco."""
    busta1 = BustaTelematica(dati_busta)
    busta2 = BustaTelematica(dati_busta)
    assert busta1.id_busta != busta2.id_busta


def test_hash_file(dati_busta):
    """Verifica che l'hash del file sia calcolato correttamente."""
    busta = BustaTelematica(dati_busta)
    hash_val = busta._hash_file(dati_busta.atto_principale)
    assert len(hash_val) == 64  # SHA-256 hex = 64 caratteri
    assert hash_val == hash_val.upper()
