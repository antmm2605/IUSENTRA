"""Browser P-256 proof of possession. No MAC-address identity or bearer token."""

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def public_key(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ValueError("Chiave del computer non valida.")
    try:
        raw = base64.b64decode(value, validate=True)
        key = serialization.load_der_public_key(raw)
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise TypeError()
    except (ValueError, TypeError) as exc:
        raise ValueError("Chiave del computer non valida.") from exc
    canonical = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(canonical).decode(), hashlib.sha256(canonical).hexdigest()


def verify(key, message, signature):
    try:
        raw = base64.b64decode(signature, validate=True)
        if len(raw) != 64:
            raise TypeError()
        der = utils.encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        serialization.load_der_public_key(base64.b64decode(key)).verify(
            der, message.encode(), ec.ECDSA(hashes.SHA256())
        )
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise PermissionError("Prova del computer non valida.") from exc
