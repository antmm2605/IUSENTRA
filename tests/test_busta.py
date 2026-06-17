"""Test per la creazione della busta telematica."""

import os
import tempfile
import pytest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from pct.busta import BustaTelematica, DatiBusta, Allegato, ATTO_MSG_FILENAME


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
    return {
        Path(part.get_filename() or "").name: part.get_payload(decode=True) or b""
        for part in message.iter_attachments()
        if part.get_filename()
    }


def test_busta_contiene_xml(dati_busta, tmp_path):
    """Verifica che la busta contenga il file DatiAtto.xml."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    assert "DatiAtto.xml" in attachments
    assert "IndiceDocumentiDepositati.PDF" in attachments


def test_datiatto_contiene_indice_documenti_generato(dati_busta, tmp_path):
    """Verifica che l'indice generato sia richiamato nei metadati della busta."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    xml_bytes = attachments["DatiAtto.xml"]
    indice_bytes = attachments["IndiceDocumentiDepositati.PDF"]

    root = etree.fromstring(xml_bytes)
    ns = {"p": "http://www.giustizia.it/processo_telematico"}
    indice_node = root.find(".//p:Documenti/p:Allegato[p:NomeFile='IndiceDocumentiDepositati.PDF']", ns)
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
    assert "IndiceDocumentiDepositati.PDF" in risultato["documenti"]


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
    assert audit["indice_busta_filename"] == "IndiceDocumentiDepositati.PDF"
    assert any("Atto.enc" in action and "AES256" in action for action in audit["guided_next_actions"])
    assert audit["formal_checks"]["T002"]["status"] == "warning"
    issue = next(issue for issue in audit["issues"] if issue["code"] == "ATTO-ENC-MISSING")
    assert "Atto.msg" in issue["detail"]
    assert "AES256" in issue["detail"]


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
