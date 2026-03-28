"""
Test conformità PST — validazione PDF/A e timestamp RFC 3161.

Copre:
  - pct.validazione: verifica_pdfa, verifica_dimensione, valida_documento_deposito
  - pct.rfc3161: costruzione richiesta ASN.1, client TSA (mock HTTP)
"""

import hashlib
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
#  Helper: crea byte PDF minimi
# ---------------------------------------------------------------------------

def _pdf_base(pdfa_part: str = "", pdfa_conf: str = "", cifrato: bool = False) -> bytes:
    """Genera un flusso PDF minimale con/senza marcatori XMP pdfaid."""
    xmp = b""
    if pdfa_part:
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
    enc = b"\n/Encrypt 1 0 R" if cifrato else b""
    return b"%PDF-1.4\n" + xmp + enc + b"\n%%EOF"


def _crea_pdf(tmpdir: str, nome: str = "atto.pdf", **kwargs) -> str:
    """Scrive un PDF di test e restituisce il percorso."""
    path = os.path.join(tmpdir, nome)
    Path(path).write_bytes(_pdf_base(**kwargs))
    return path


# ===========================================================================
#  VALIDAZIONE PDF/A
# ===========================================================================

class TestVerificaPDFA(unittest.TestCase):

    def test_pdfa2b_rilevato(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="2", pdfa_conf="B")
            r = verifica_pdfa(p)
        self.assertTrue(r["conforme"])
        self.assertEqual(r["parte"], "2")
        self.assertEqual(r["livello"], "B")
        self.assertEqual(r["versione"], "PDF/A-2B")
        self.assertFalse(r["cifrato"])

    def test_pdfa1a_rilevato(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="1", pdfa_conf="A")
            r = verifica_pdfa(p)
        self.assertTrue(r["conforme"])
        self.assertEqual(r["versione"], "PDF/A-1A")

    def test_non_pdfa(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d)  # nessun marcatore XMP
            r = verifica_pdfa(p)
        self.assertFalse(r["conforme"])
        self.assertEqual(r["versione"], "")
        self.assertTrue(len(r["avvisi"]) > 0)

    def test_cifrato_non_conforme(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="2", pdfa_conf="B", cifrato=True)
            r = verifica_pdfa(p)
        self.assertFalse(r["conforme"])
        self.assertTrue(r["cifrato"])

    def test_file_non_trovato(self):
        from pct.validazione import verifica_pdfa
        r = verifica_pdfa("/tmp/__nonexistent_test_file.pdf")
        self.assertFalse(r["conforme"])
        self.assertIn("non trovato", r["messaggio"].lower())

    def test_p7m_skip_validazione(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "atto.pdf.p7m")
            # .p7m contiene dati arbitrari (non PDF)
            Path(p).write_bytes(b"\x30\x82\x01\x00" + b"\x00" * 50)
            r = verifica_pdfa(p)
        # conforme=None significa "non verificabile" (wrapper firma)
        self.assertIsNone(r["conforme"])

    def test_estensione_non_pdf(self):
        from pct.validazione import verifica_pdfa
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "doc.docx")
            Path(p).write_bytes(b"PK\x03\x04somezipdata")
            r = verifica_pdfa(p)
        self.assertFalse(r["conforme"])
        self.assertIn("non PDF", r["messaggio"])


# ===========================================================================
#  VERIFICA DIMENSIONE
# ===========================================================================

class TestVerificaDimensione(unittest.TestCase):

    def test_entro_limite(self):
        from pct.validazione import verifica_dimensione
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d)
            r = verifica_dimensione(p, max_bytes=1024 * 1024)
        self.assertTrue(r["ok"])
        self.assertGreater(r["bytes"], 0)

    def test_sopra_limite(self):
        from pct.validazione import verifica_dimensione
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "grande.pdf")
            Path(p).write_bytes(b"X" * 100)
            r = verifica_dimensione(p, max_bytes=50)
        self.assertFalse(r["ok"])
        self.assertIn("troppo grande", r["messaggio"].lower())

    def test_file_non_trovato(self):
        from pct.validazione import verifica_dimensione
        r = verifica_dimensione("/tmp/__nonexistent_dim.pdf")
        self.assertFalse(r["ok"])


# ===========================================================================
#  VALIDA_DOCUMENTO_DEPOSITO
# ===========================================================================

class TestValidaDocumentoDeposito(unittest.TestCase):

    def test_pdfa_ok_atto_principale(self):
        from pct.validazione import valida_documento_deposito
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="2", pdfa_conf="B")
            r = valida_documento_deposito(p, atto_principale=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["errori"], [])

    def test_non_pdfa_atto_principale_bloccante(self):
        from pct.validazione import valida_documento_deposito
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d)  # nessun marcatore
            r = valida_documento_deposito(p, atto_principale=True)
        self.assertFalse(r["ok"])
        self.assertTrue(len(r["errori"]) > 0)

    def test_non_pdfa_allegato_solo_avviso(self):
        from pct.validazione import valida_documento_deposito
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d)  # nessun marcatore
            r = valida_documento_deposito(p, atto_principale=False)
        # Per gli allegati non è bloccante — solo avviso
        self.assertTrue(r["ok"])
        self.assertEqual(r["errori"], [])
        self.assertTrue(len(r["avvisi"]) > 0)

    def test_cifrato_sempre_bloccante(self):
        from pct.validazione import valida_documento_deposito
        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="2", pdfa_conf="B", cifrato=True)
            r = valida_documento_deposito(p, atto_principale=False)
        self.assertFalse(r["ok"])
        self.assertTrue(any("cifrat" in e.lower() for e in r["errori"]))


# ===========================================================================
#  RFC 3161 — Costruzione richiesta ASN.1
# ===========================================================================

class TestRFC3161ASN1(unittest.TestCase):

    def test_build_timestamp_request_bytes(self):
        from pct.rfc3161 import _build_timestamp_request
        data = b"test_atto_principale"
        req = _build_timestamp_request(data, nonce=12345)
        # Deve iniziare con SEQUENCE (0x30)
        self.assertEqual(req[0], 0x30)
        # Deve essere almeno 50 byte
        self.assertGreater(len(req), 50)

    def test_richiesta_contiene_sha256_digest(self):
        from pct.rfc3161 import _build_timestamp_request
        data = b"documento_da_marcare"
        req = _build_timestamp_request(data, nonce=99999)
        digest = hashlib.sha256(data).digest()
        # Il digest SHA-256 deve essere presente nel payload DER
        self.assertIn(digest, req)

    def test_nonce_casuale_richieste_diverse(self):
        from pct.rfc3161 import _build_timestamp_request
        data = b"stesso_documento"
        r1 = _build_timestamp_request(data)
        r2 = _build_timestamp_request(data)
        # Due richieste senza nonce fisso devono essere diverse (nonce random)
        self.assertNotEqual(r1, r2)

    def test_asn1_int_zero(self):
        from pct.rfc3161 import _asn1_int
        enc = _asn1_int(0)
        self.assertEqual(enc, b"\x02\x01\x00")

    def test_asn1_int_large(self):
        from pct.rfc3161 import _asn1_int
        # 256 = 0x100 → big-endian 2 byte, con leading zero per bit di segno → [0x00, 0x01, 0x00]
        enc = _asn1_int(256)
        self.assertEqual(enc[0], 0x02)  # tag INTEGER

    def test_asn1_oid_sha256(self):
        from pct.rfc3161 import _asn1_oid, _OID_SHA256
        enc = _asn1_oid(_OID_SHA256)
        self.assertEqual(enc[0], 0x06)  # OID tag
        self.assertGreater(len(enc), 5)


# ===========================================================================
#  RFC 3161 — Client TSA (mock HTTP)
# ===========================================================================

class TestRFC3161Client(unittest.TestCase):

    def _fake_tsr(self) -> bytes:
        """Costruisce una risposta TSA minimale (PKIStatusInfo + INTEGER seriale)."""
        # SEQUENCE { INTEGER(0), INTEGER(serial) }  (semplificato)
        ser = b"\x02\x04\x00\x01\x02\x03"  # INTEGER 0x00010203
        status = b"\x02\x01\x00"            # INTEGER 0 (granted)
        return b"\x30" + bytes([len(status + ser)]) + status + ser

    def test_timestamp_ok(self):
        from pct.rfc3161 import richiedi_timestamp
        fake_resp = MagicMock()
        fake_resp.content = self._fake_tsr()
        fake_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=fake_resp) as mock_post:
            r = richiedi_timestamp(b"dati_atto", tsa_url="https://tsa.example.com/tsr")

        self.assertTrue(r["ok"])
        self.assertEqual(r["token"], self._fake_tsr())
        self.assertEqual(r["tsa_url"], "https://tsa.example.com/tsr")
        self.assertEqual(r["errore"], "")
        mock_post.assert_called_once()

    def test_content_type_header(self):
        from pct.rfc3161 import richiedi_timestamp
        fake_resp = MagicMock()
        fake_resp.content = self._fake_tsr()
        fake_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=fake_resp) as mock_post:
            richiedi_timestamp(b"dati", tsa_url="https://tsa.example.com/tsr")

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["headers"]["Content-Type"],
            "application/timestamp-query",
        )

    def test_timestamp_errore_rete(self):
        from pct.rfc3161 import richiedi_timestamp
        import requests as _req
        with patch("requests.post", side_effect=_req.ConnectionError("timeout")):
            r = richiedi_timestamp(b"dati", tsa_url="https://tsa.example.com/tsr")

        self.assertFalse(r["ok"])
        self.assertEqual(r["token"], b"")
        self.assertIn("Errore contatto TSA", r["messaggio"])

    def test_salva_token(self):
        from pct.rfc3161 import salva_token
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "atto.pdf.p7m")
            token = b"\x30\x82\x00\x10" + b"\xAB" * 16
            tsr_path = salva_token(token, base)
            self.assertTrue(Path(tsr_path).exists())
            self.assertEqual(Path(tsr_path).read_bytes(), token)
            self.assertTrue(tsr_path.endswith(".tsr"))


# ===========================================================================
#  INTEGRAZIONE — deposito.py usa validazione pre-firma
# ===========================================================================

class TestDepositoCivileValidazionePDFALogica(unittest.TestCase):
    """
    Verifica la logica di blocco PDF/A in deposito.py senza importare cryptography.

    Testa direttamente valida_documento_deposito + il pattern usato in deposito.py
    (la classe DepositoCivile non è istanziabile nell'ambiente di test per via di
    pyo3/cffi, ma la logica di validazione è testata in TestValidaDocumentoDeposito).
    """

    def test_valida_documento_blocca_non_pdfa(self):
        """Simula la logica del check PDF/A che deposita() esegue."""
        from pct.validazione import valida_documento_deposito

        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d)  # non PDF/A
            esito_pdfa = valida_documento_deposito(p, atto_principale=True)

        # La logica in deposito.py: if not esito_pdfa["ok"] → return EsitoDeposito(stato="ERRORE")
        self.assertFalse(esito_pdfa["ok"])
        self.assertTrue(len(esito_pdfa["errori"]) > 0)

    def test_valida_documento_prosegue_con_pdfa(self):
        """Con PDF/A conforme, esito['ok'] è True → il deposito prosegue."""
        from pct.validazione import valida_documento_deposito

        with tempfile.TemporaryDirectory() as d:
            p = _crea_pdf(d, pdfa_part="2", pdfa_conf="B")
            esito_pdfa = valida_documento_deposito(p, atto_principale=True)

        self.assertTrue(esito_pdfa["ok"])
        self.assertEqual(esito_pdfa["errori"], [])


if __name__ == "__main__":
    unittest.main()
