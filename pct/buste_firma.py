"""Apertura delle buste che avvolgono un documento firmato o marcato.

Il lettore deve mostrare all'avvocato il documento contenuto, non la busta:
qui si tolgono in sequenza gli involucri CAdES (``.p7m`` anche annidati più
volte), le marche temporali TimeStampedData (``.tsd``, RFC 5544) e le buste
MIME con marca (``.m7m``). La verifica della firma non serve per la lettura e
non viene fatta qui.
"""

from __future__ import annotations

from collections.abc import Callable
from email import policy
from email.parser import BytesParser

MAX_LIVELLI_BUSTA = 5
SUFFISSI_BUSTA = (".p7m", ".tsd", ".m7m")
OID_TIMESTAMPED_DATA = "1.2.840.113549.1.9.16.1.31"
MIME_PKCS7 = frozenset({"application/pkcs7-mime", "application/x-pkcs7-mime"})
MIME_MARCA_REPLY = frozenset({"application/timestamp-reply", "application/timestamp-response"})
_TESTA_MIME = (b"mime-version:", b"content-type:")


def nome_senza_buste(nome: str) -> str:
    """``atto.pdf.p7m.p7m.tsd`` -> ``atto.pdf``: toglie tutte le estensioni di busta."""
    testo = str(nome or "").strip()
    for _ in range(MAX_LIVELLI_BUSTA + 1):
        minuscolo = testo.casefold()
        suffisso = next((s for s in SUFFISSI_BUSTA if minuscolo.endswith(s)), "")
        if not suffisso or len(testo) == len(suffisso):
            break
        testo = testo[: -len(suffisso)]
    return testo


def _der(data: bytes) -> bytes:
    from pct.firme_cades import der_da_base64

    return der_da_base64(data)


def _tipo_content_info(data: bytes) -> str:
    """OID del ContentInfo in testa ai byte, senza decodificare il contenuto."""
    if not data or data[:1] != b"\x30":
        return ""
    try:
        from asn1crypto import core

        class _ContentInfoGenerico(core.Sequence):
            _fields = [
                ("content_type", core.ObjectIdentifier),
                ("content", core.Any, {"explicit": 0, "optional": True}),
            ]

        info = _ContentInfoGenerico.load(data)
        return str(info["content_type"].dotted)
    except Exception:
        return ""


def e_busta_cms(data: bytes) -> bool:
    """True se i byte sono una busta CMS SignedData (anche in Base64/PEM)."""
    return _tipo_content_info(_der(data)) == "1.2.840.113549.1.7.2"


def _contenuto_tsd(data: bytes) -> bytes | None:
    der = _der(data)
    if _tipo_content_info(der) != OID_TIMESTAMPED_DATA:
        return None
    try:
        from asn1crypto import core

        class _MetaData(core.Sequence):
            _fields = [
                ("hash_protected", core.Boolean),
                ("file_name", core.UTF8String, {"optional": True}),
                ("media_type", core.IA5String, {"optional": True}),
                ("other_meta_data", core.Any, {"optional": True}),
            ]

        class _TimeStampedData(core.Sequence):
            _fields = [
                ("version", core.Integer),
                ("data_uri", core.IA5String, {"optional": True}),
                ("meta_data", _MetaData, {"optional": True}),
                ("content", core.OctetString, {"optional": True}),
                ("temporal_evidence", core.Any),
            ]

        class _ContentInfoTsd(core.Sequence):
            _fields = [
                ("content_type", core.ObjectIdentifier),
                ("content", _TimeStampedData, {"explicit": 0}),
            ]

        contenuto = _ContentInfoTsd.load(der)["content"]["content"]
        valore = contenuto.native if contenuto is not None else None
    except Exception:
        return None
    return bytes(valore) if valore else None


def _e_mime(data: bytes) -> bool:
    testa = data[:2048].lstrip().lower()
    return testa.startswith(_TESTA_MIME) or b"\ncontent-type:" in testa


def _contenuto_m7m(data: bytes) -> bytes | None:
    """Busta .m7m: MIME con la parte ``application/pkcs7-mime`` e la marca.

    Si riconosce solo se c'è anche la parte ``application/timestamp-reply`` e
    l'intestazione non è quella di un messaggio di posta: una PEC salvata come
    .eml con un allegato .p7m non è una busta .m7m e non va «aperta».
    """
    if not data or not _e_mime(data):
        return None
    try:
        messaggio = BytesParser(policy=policy.compat32).parsebytes(data)
        if messaggio.get("from") or messaggio.get("subject") or not messaggio.is_multipart():
            return None
        busta: bytes | None = None
        marca = False
        for parte in messaggio.walk():
            if parte.is_multipart():
                continue
            tipo = parte.get_content_type().casefold()
            if tipo in MIME_MARCA_REPLY:
                marca = True
            elif tipo in MIME_PKCS7 and busta is None:
                payload = parte.get_payload(decode=True)
                busta = bytes(payload) if payload else None
    except Exception:
        return None
    return busta if marca else None


def contenuto_marca_temporale(data: bytes) -> bytes | None:
    """Contenuto di una marca ``.tsd`` o di una busta ``.m7m``; None se non lo è."""
    if not data:
        return None
    return _contenuto_tsd(data) or _contenuto_m7m(data)


def e_busta(data: bytes) -> bool:
    """True se i byte sono ancora una busta di firma o di marca da aprire."""
    return bool(data) and (e_busta_cms(data) or contenuto_marca_temporale(data) is not None)


def togli_buste(data: bytes, estrai_cms: Callable[[bytes], bytes | None]) -> bytes | None:
    """Toglie gli involucri in sequenza (al massimo ``MAX_LIVELLI_BUSTA``).

    Al primo livello si tenta comunque l'estrazione CMS, come prima; dal
    secondo si prosegue solo se il contenuto è ancora una busta. Restituisce
    None se nemmeno il primo involucro si apre.
    """
    corrente = data
    risultato: bytes | None = None
    for livello in range(MAX_LIVELLI_BUSTA):
        interno = contenuto_marca_temporale(corrente)
        if interno is None and (livello == 0 or e_busta_cms(corrente)):
            interno = estrai_cms(corrente)
        if not interno:
            break
        # Un ".p7m" salvato già estratto (XML in chiaro) torna com'è, come prima.
        risultato = interno
        if interno == corrente:
            break
        corrente = interno
    return risultato


__all__ = [
    "MAX_LIVELLI_BUSTA",
    "SUFFISSI_BUSTA",
    "contenuto_marca_temporale",
    "e_busta",
    "e_busta_cms",
    "nome_senza_buste",
    "togli_buste",
]
