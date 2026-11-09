"""Buste sintetiche di firma e di marca per i test del lettore (nessun dato reale)."""

from __future__ import annotations

import base64

from asn1crypto import algos, cms, core



def _pdf_di_prova() -> bytes:
    """PDF vero di una pagina, apribile dal motore di rendering del lettore."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (60, 80), "white").save(buffer, format="PDF")
    return buffer.getvalue()


PDF_PROVA = _pdf_di_prova()


def busta_p7m(payload: bytes) -> bytes:
    """Busta CAdES SignedData con contenuto incorporato e senza firmatari."""
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data", "content": payload},
            "signer_infos": [],
        }
    )
    return cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()


def busta_p7m_annidata(payload: bytes, livelli: int) -> bytes:
    data = payload
    for _ in range(livelli):
        data = busta_p7m(data)
    return data


class _MetaData(core.Sequence):
    _fields = [
        ("hash_protected", core.Boolean),
        ("file_name", core.UTF8String, {"optional": True}),
        ("media_type", core.IA5String, {"optional": True}),
    ]


class _TimeStampedData(core.Sequence):
    _fields = [
        ("version", core.Integer),
        ("data_uri", core.IA5String, {"optional": True}),
        ("meta_data", _MetaData, {"optional": True}),
        ("content", core.OctetString, {"optional": True}),
        # Evidenza fittizia [0]: il lettore non verifica la marca.
        ("temporal_evidence", core.Integer, {"explicit": 0}),
    ]


class _ContentInfoTsd(core.Sequence):
    _fields = [
        ("content_type", core.ObjectIdentifier),
        ("content", _TimeStampedData, {"explicit": 0}),
    ]


def marca_tsd(payload: bytes, nome: str = "atto.pdf.p7m") -> bytes:
    """TimeStampedData RFC 5544 con il documento incorporato e un'evidenza fittizia."""
    tsd = _TimeStampedData(
        {
            "version": 1,
            "meta_data": {"hash_protected": False, "file_name": nome},
            "content": payload,
            "temporal_evidence": 1,
        }
    )
    return _ContentInfoTsd(
        {"content_type": "1.2.840.113549.1.9.16.1.31", "content": tsd}
    ).dump()


def busta_m7m(p7m: bytes, nome: str = "atto.pdf.p7m") -> bytes:
    """Busta MIME .m7m: parte pkcs7-mime con il .p7m e parte con la marca."""
    def _b64(data: bytes) -> bytes:
        testo = base64.b64encode(data)
        return b"\r\n".join(testo[i : i + 76] for i in range(0, len(testo), 76))

    confine = b"----=_m7m_prova"
    return (
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/mixed; boundary="' + confine + b'"\r\n\r\n'
        b"--" + confine + b"\r\n"
        b'Content-Type: application/pkcs7-mime; smime-type=signed-data; name="' + nome.encode() + b'"\r\n'
        b"Content-Transfer-Encoding: base64\r\n\r\n" + _b64(p7m) + b"\r\n"
        b"--" + confine + b"\r\n"
        b"Content-Type: application/timestamp-reply\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n" + _b64(b"\x30\x03\x02\x01\x00") + b"\r\n"
        b"--" + confine + b"--\r\n"
    )
