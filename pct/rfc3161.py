"""
Client RFC 3161 per marcatura temporale CAdES (timestamp).

Costruisce una richiesta TimeStampReq minimale in ASN.1 DER, la invia a una
TSA (Time Stamp Authority) via HTTP POST e restituisce il token grezzo.

Nessuna dipendenza aggiuntiva: usa solo `hashlib`, `os`, `struct` e
`requests` (già presente nel progetto).

Norma di riferimento:
  RFC 3161 — Internet X.509 PKI Time-Stamp Protocol (TSP)
  D.M. 44/2011 art. 12 — la marcatura temporale è opzionale (la ricevuta PEC
  ha valore legale equivalente); si raccomanda quando si vuole certificare
  l'ora esatta indipendentemente dall'infrastruttura PEC.

TSA pubbliche gratuite (non affiliazione con il progetto):
  - https://freetsa.org/tsr  (FreeTSA)
  - http://timestamp.sectigo.com
  - http://timestamp.comodoca.com
  - http://tsa.swisssign.net
"""

from __future__ import annotations

import hashlib
import os
import struct
from typing import Optional


# ---------------------------------------------------------------------------
#  Costruttori ASN.1 DER minimali
#  (solo i tag necessari per TimeStampReq RFC 3161 §2.4.1)
# ---------------------------------------------------------------------------

def _asn1_len(n: int) -> bytes:
    """Codifica la lunghezza in DER."""
    if n < 0x80:
        return bytes([n])
    enc = []
    while n:
        enc.append(n & 0xFF)
        n >>= 8
    enc.reverse()
    return bytes([0x80 | len(enc)] + enc)


def _asn1_wrap(tag: int, content: bytes) -> bytes:
    return bytes([tag]) + _asn1_len(len(content)) + content


def _asn1_seq(*items: bytes) -> bytes:
    return _asn1_wrap(0x30, b"".join(items))       # SEQUENCE


def _asn1_set(*items: bytes) -> bytes:
    return _asn1_wrap(0x31, b"".join(items))       # SET


def _asn1_int(value: int) -> bytes:
    # INTEGER — codifica minima big-endian con bit di segno
    n = value
    data = []
    while n:
        data.append(n & 0xFF)
        n >>= 8
    if not data:
        data = [0]
    data.reverse()
    if data[0] & 0x80:
        data = [0x00] + data
    return _asn1_wrap(0x02, bytes(data))            # INTEGER


def _asn1_bool(value: bool) -> bytes:
    return _asn1_wrap(0x01, b"\xff" if value else b"\x00")  # BOOLEAN


def _asn1_octet(data: bytes) -> bytes:
    return _asn1_wrap(0x04, data)                  # OCTET STRING


def _asn1_oid(dotted: str) -> bytes:
    """Codifica un OID in DER."""
    parts = [int(x) for x in dotted.split(".")]
    # primo byte = 40 * arc0 + arc1
    enc = [40 * parts[0] + parts[1]]
    for n in parts[2:]:
        if n == 0:
            enc.append(0)
        else:
            tmp = []
            while n:
                tmp.append(n & 0x7F)
                n >>= 7
            tmp.reverse()
            for i, b in enumerate(tmp):
                enc.append(b | (0x80 if i < len(tmp) - 1 else 0))
    return _asn1_wrap(0x06, bytes(enc))            # OID


# OID SHA-256
_OID_SHA256 = "2.16.840.1.101.3.4.2.1"


def _build_timestamp_request(data: bytes, nonce: Optional[int] = None) -> bytes:
    """
    Costruisce una TimeStampReq DER minimale.

    TimeStampReq ::= SEQUENCE {
       version          INTEGER,
       messageImprint   MessageImprint,
       reqPolicy        TSAPolicyId OPTIONAL,
       nonce            INTEGER OPTIONAL,
       certReq          BOOLEAN OPTIONAL,
       extensions       [0] IMPLICIT Extensions OPTIONAL
    }

    MessageImprint ::= SEQUENCE {
       hashAlgorithm    AlgorithmIdentifier,
       hashedMessage    OCTET STRING
    }
    """
    digest = hashlib.sha256(data).digest()

    # AlgorithmIdentifier = SEQUENCE { OID, NULL }
    alg_id = _asn1_seq(
        _asn1_oid(_OID_SHA256),
        _asn1_wrap(0x05, b""),   # NULL
    )

    # MessageImprint
    msg_imprint = _asn1_seq(alg_id, _asn1_octet(digest))

    # Nonce opzionale (8 byte casuali)
    if nonce is None:
        nonce = int.from_bytes(os.urandom(8), "big")
    nonce_field = _asn1_int(nonce)

    # certReq = TRUE (vogliamo il certificato TSA nella risposta)
    cert_req = _asn1_bool(True)

    # TimeStampReq
    return _asn1_seq(
        _asn1_int(1),        # version = 1
        msg_imprint,
        nonce_field,
        cert_req,
    )


# ---------------------------------------------------------------------------
#  Client TSA
# ---------------------------------------------------------------------------

# TSA pubblica di default (FreeTSA — nessun account richiesto)
TSA_URL_DEFAULT = "https://freetsa.org/tsr"


def richiedi_timestamp(
    data: bytes,
    tsa_url: str = TSA_URL_DEFAULT,
    timeout: int = 15,
) -> dict:
    """
    Richiede una marcatura temporale RFC 3161 per i dati forniti.

    Args:
        data:    Contenuto da marcare (es. il file .p7m firmato).
        tsa_url: URL HTTP/HTTPS della TSA.
        timeout: Timeout HTTP in secondi.

    Returns:
        dict con chiavi:
          ok          (bool)   — True se il timestamp è stato ottenuto
          token       (bytes)  — token grezzo TimeStampResp DER (o b"")
          serial      (str)    — numero seriale estratto (stringa hex o "")
          tsa_url     (str)    — URL TSA usata
          messaggio   (str)    — descrizione leggibile
          errore      (str)    — messaggio di errore (se not ok)
    """
    try:
        import requests as _req
    except ImportError:
        return {
            "ok": False,
            "token": b"",
            "serial": "",
            "tsa_url": tsa_url,
            "messaggio": "Modulo 'requests' non disponibile.",
            "errore": "ImportError: requests",
        }

    nonce = int.from_bytes(os.urandom(8), "big")
    try:
        req_der = _build_timestamp_request(data, nonce)
    except Exception as exc:
        return {
            "ok": False,
            "token": b"",
            "serial": "",
            "tsa_url": tsa_url,
            "messaggio": f"Errore costruzione richiesta TSA: {exc}",
            "errore": str(exc),
        }

    try:
        resp = _req.post(
            tsa_url,
            data=req_der,
            headers={"Content-Type": "application/timestamp-query"},
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as exc:
        return {
            "ok": False,
            "token": b"",
            "serial": "",
            "tsa_url": tsa_url,
            "messaggio": f"Errore contatto TSA ({tsa_url}): {exc}",
            "errore": str(exc),
        }

    token = resp.content

    # Estrai il numero seriale dalla risposta DER (posizione approssimativa)
    # Il seriale è tipicamente il primo INTEGER nel ContentInfo/SignedData/TSTInfo
    serial = _estrai_serial_approssimativo(token)

    return {
        "ok": True,
        "token": token,
        "serial": serial,
        "tsa_url": tsa_url,
        "messaggio": f"Marcatura temporale ottenuta (TSA: {tsa_url}, seriale: {serial}).",
        "errore": "",
    }


def _estrai_serial_approssimativo(token: bytes) -> str:
    """
    Estrae il numero seriale dalla risposta TSA in modo best-effort.

    Non esegue parsing DER completo: cerca il pattern tipico
    nelle prime strutture INTEGER della risposta.
    """
    # Cerca il primo INTEGER dopo i primi 30 byte (skip PKIStatusInfo)
    idx = 30
    count = 0
    while idx < min(len(token), 512):
        if token[idx] == 0x02:  # INTEGER tag
            if idx + 1 < len(token):
                ln = token[idx + 1]
                if ln < 0x80 and idx + 2 + ln <= len(token):
                    val = int.from_bytes(token[idx + 2: idx + 2 + ln], "big")
                    count += 1
                    if count >= 2:  # il secondo INTEGER tende ad essere il seriale
                        return hex(val)[2:].upper()
                idx += 2 + (ln if ln < 0x80 else 1)
            else:
                break
        else:
            idx += 1
    return ""


# ---------------------------------------------------------------------------
#  Salvataggio token
# ---------------------------------------------------------------------------

def salva_token(token: bytes, percorso_base: str) -> str:
    """
    Salva il token RFC 3161 su disco con estensione .tsr.

    Args:
        token:          Bytes del TimeStampResp.
        percorso_base:  Percorso del documento originale (es. /data/.../atto.pdf.p7m)

    Returns:
        Percorso del file .tsr salvato.
    """
    from pathlib import Path
    tsr_path = str(percorso_base) + ".tsr"
    Path(tsr_path).write_bytes(token)
    return tsr_path
