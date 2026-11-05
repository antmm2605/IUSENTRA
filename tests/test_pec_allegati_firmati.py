"""Lettura degli allegati firmati (.p7m) e degli zip annidati nelle PEC di cancelleria.

I provvedimenti del giudice arrivano spesso firmati CAdES («provvedimento.pdf.p7m») o dentro lo zip della
comunicazione: prima del 05/11/2026 il testo di un .p7m restava vuoto e il profilo processuale non poteva
leggerlo. Le buste di prova sono firmate con un certificato autogenerato (solo per il test).
"""

from __future__ import annotations

import datetime
import io
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pct.pec_pipeline import AttachmentPayload, extract_text_with_coverage

TESTO = "Il giudice assegna termine per note scritte in sostituzione dell'udienza del 23/11/2026 ore 14:00."


def _busta_cades(contenuto: bytes) -> bytes:
    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Prova firma")])
    adesso = datetime.datetime.now(datetime.timezone.utc)
    certificato = (
        x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chiave.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(adesso)
        .not_valid_after(adesso + datetime.timedelta(days=1)).sign(chiave, hashes.SHA256())
    )
    return (
        pkcs7.PKCS7SignatureBuilder().set_data(contenuto).add_signer(certificato, chiave, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )


def _zip(voci: dict[str, bytes]) -> bytes:
    uscita = io.BytesIO()
    with zipfile.ZipFile(uscita, "w") as archivio:
        for nome, dati in voci.items():
            archivio.writestr(nome, dati)
    return uscita.getvalue()


def _leggi(nome: str, dati: bytes, tipo: str = "application/octet-stream") -> str:
    testo, _copertura = extract_text_with_coverage(AttachmentPayload(index=1, filename=nome, content_type=tipo, data=dati))
    return testo


def test_allegato_firmato_p7m_si_legge_dal_contenuto():
    assert "note scritte" in _leggi("provvedimento.txt.p7m", _busta_cades(TESTO.encode()))


def test_doppia_firma_p7m_p7m_si_legge():
    assert "23/11/2026" in _leggi("provvedimento.txt.p7m.p7m", _busta_cades(_busta_cades(TESTO.encode())))


def test_p7m_dentro_lo_zip_della_comunicazione_si_legge():
    archivio = _zip({"2276942s.txt.p7m": _busta_cades(TESTO.encode())})
    testo = _leggi("2276942s.pdf.zip", archivio, "application/zip")
    assert "note scritte" in testo and "[2276942s.txt.p7m]" in testo


def test_zip_dentro_lo_zip_si_legge():
    interno = _zip({"decreto.txt": TESTO.encode()})
    testo = _leggi("comunicazione.zip", _zip({"allegati.zip": interno}), "application/zip")
    assert "note scritte" in testo


def test_p7m_non_valido_non_produce_spazzatura():
    assert _leggi("rotto.pdf.p7m", b"\x30\x82\x00\x10non una busta") == ""


def test_codice_di_accesso_e_id_riunione_dell_udienza_da_remoto():
    from pct.pec_pipeline import _remote_hearing_for_procedural_candidate as dettagli

    base = {"detected": True, "url": "https://teams.microsoft.com/l/meetup-join/x"}
    candidato = {"date": "2026-10-29", "time": "09:15"}
    campo_xml = dettagli(base, candidato, kind="udienza", document_text=(
        "Udienza del 29/10/2026 ore 09:15 da remoto. Codice di accesso FiscaleDestinatario AAABBB00A01H501Z"))
    assert not campo_xml.get("passcode")
    vero = dettagli(base, candidato, kind="udienza", document_text=(
        "Udienza del 29/10/2026 ore 09:15 da remoto. ID riunione: 123 456 789 Passcode: aB3cD4"))
    assert vero["passcode"] == "aB3cD4" and vero["meeting_id"] == "123 456 789"


def test_dettaglio_leggero_porta_solo_il_profilo_processuale():
    from pct.pec_pipeline import _solo_profilo_processuale

    assert _solo_profilo_processuale({"procedural_profile": {"ufficio": "Tribunale di Vicenza"}, "issues": [1]}) == {
        "procedural_profile": {"ufficio": "Tribunale di Vicenza"}}
    assert _solo_profilo_processuale({}) == {}
