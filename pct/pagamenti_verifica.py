"""Verifica presso il gestore di un pagamento annunciato da un webhook.

Un webhook è una richiesta HTTP che chiunque può inviare: PayPal, SumUp e
Satispay non firmano la notifica con un segreto condiviso come fa Stripe.
Prima di segnare pagata una parcella IUSENTRA chiede quindi al gestore lo
stato reale della transazione, con le credenziali dello studio, e confronta
il riferimento del link e l'importo. Se il gestore non conferma, nulla cambia.

Base normativa: art. 2220 c.c. e D.P.R. 633/1972 art. 6 (il pagamento
determina l'esigibilità dell'IVA per le prestazioni professionali): una
parcella non si registra incassata senza prova del pagamento.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

TIMEOUT = 10


def _importo_uguale(atteso: float, ricevuto: Any) -> bool:
    try:
        return abs(round(float(atteso), 2) - round(float(ricevuto), 2)) < 0.005
    except (TypeError, ValueError):
        return False


def paypal_pagamento_confermato(gp, capture_id: str, link) -> bool:
    """La cattura PayPal esiste, è COMPLETED e appartiene a questo link."""
    import requests

    if not capture_id:
        return False
    token = gp.paypal_token()
    if not token:
        return False
    cfg = gp.config.paypal
    try:
        r = requests.get(
            f"{cfg.base_url}/v2/payments/captures/{quote(capture_id, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        dati = r.json()
    except Exception:
        return False
    importo = (dati.get("amount") or {}).get("value")
    return (
        dati.get("status") == "COMPLETED"
        and str(dati.get("custom_id") or "") == link.id
        and _importo_uguale(link.importo, importo)
    )


def sumup_pagamento_confermato(gp, checkout_id: str, link) -> bool:
    """Il checkout SumUp esiste, è PAID e porta il riferimento di questo link."""
    import requests

    if not checkout_id:
        return False
    cfg = gp.config.sumup
    if not cfg.api_key:
        return False
    try:
        r = requests.get(
            f"https://api.sumup.com/v0.1/checkouts/{quote(checkout_id, safe='')}",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        dati = r.json()
    except Exception:
        return False
    return (
        dati.get("status") == "PAID"
        and str(dati.get("checkout_reference") or "") == link.id
        and _importo_uguale(link.importo, dati.get("amount"))
    )


def _firma_satispay(cfg, metodo: str, percorso: str, corpo: bytes) -> dict[str, str]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    digest = base64.b64encode(hashlib.sha256(corpo).digest()).decode()
    data = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    host = cfg.base_url.replace("https://", "")
    da_firmare = (
        f"(request-target): {metodo.lower()} {percorso}\n"
        f"host: {host}\n"
        f"date: {data}\n"
        f"digest: SHA-256={digest}"
    )
    chiave = serialization.load_pem_private_key(cfg.private_key_pem.encode(), password=None)
    firma = base64.b64encode(chiave.sign(da_firmare.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
    return {
        "Authorization": (
            f'Signature keyId="{cfg.key_id}",algorithm="rsa-sha256",'
            f'headers="(request-target) host date digest",signature="{firma}"'
        ),
        "Date": data,
        "Digest": f"SHA-256={digest}",
    }


def satispay_pagamento_confermato(gp, payment_id: str, link) -> bool:
    """Il pagamento Satispay esiste, è ACCEPTED e porta il riferimento di questo link."""
    import requests

    cfg = gp.config.satispay
    if not payment_id or not cfg.key_id or not cfg.private_key_pem:
        return False
    percorso = f"/g_business/v1/payments/{quote(payment_id, safe='')}"
    try:
        r = requests.get(
            f"{cfg.base_url}{percorso}",
            headers=_firma_satispay(cfg, "GET", percorso, b""),
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        dati = r.json()
    except Exception:
        return False
    metadati = dati.get("metadata") or {}
    importo: Optional[float] = None
    try:
        importo = int(dati.get("amount_unit")) / 100
    except (TypeError, ValueError):
        importo = None
    return (
        dati.get("status") == "ACCEPTED"
        and str(metadati.get("link_id") or "") == link.id
        and _importo_uguale(link.importo, importo)
    )


def paypal_ordine_del_link(gp, order_id: str, link) -> bool:
    """L'ordine PayPal da catturare è stato creato per questo link e per questo importo."""
    import requests

    if not order_id:
        return False
    token = gp.paypal_token()
    if not token:
        return False
    cfg = gp.config.paypal
    try:
        r = requests.get(
            f"{cfg.base_url}/v2/checkout/orders/{quote(order_id, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return False
        dati = r.json()
    except Exception:
        return False
    unita = (dati.get("purchase_units") or [{}])[0]
    return str(unita.get("custom_id") or "") == link.id and _importo_uguale(
        link.importo, (unita.get("amount") or {}).get("value")
    )


def stripe_sessione_del_link(sessione, link) -> bool:
    """La sessione Stripe pagata porta il riferimento di questo link e il suo importo."""
    try:
        metadati = dict(getattr(sessione, "metadata", None) or {})
    except Exception:
        metadati = {}
    totale = getattr(sessione, "amount_total", None)
    importo = (totale / 100) if isinstance(totale, (int, float)) else None
    return (
        getattr(sessione, "payment_status", "") == "paid"
        and str(metadati.get("link_id") or "") == link.id
        and _importo_uguale(link.importo, importo)
    )
