"""Payload e salvataggio React per la scheda Pagamenti nelle impostazioni."""

from __future__ import annotations

from typing import Any, Callable

from flask import current_app


SecretStateBuilder = Callable[[str], dict[str, Any]]


def _text(value: Any, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "si", "yes", "on"}


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get_pagamenti():
    from web.helpers import get_pagamenti

    return get_pagamenti()


def _mode(value: Any, allowed: set[str], default: str) -> str:
    raw = _text(value, default).lower()
    return raw if raw in allowed else default


def _link_payload(link: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(link, "id", "")),
        "id_parcella": _text(getattr(link, "id_parcella", "")),
        "id_cliente": _text(getattr(link, "id_cliente", "")),
        "descrizione": _text(getattr(link, "descrizione", "")),
        "importo": _money(getattr(link, "importo", 0)),
        "valuta": _text(getattr(link, "valuta", "EUR"), "EUR"),
        "stato": _text(getattr(link, "stato", "")),
        "creato_il": _text(getattr(link, "creato_il", ""))[:10],
        "scade_il": _text(getattr(link, "scade_il", ""))[:10],
        "pagato_il": _text(getattr(link, "pagato_il", ""))[:10],
        "provider_usato": _text(getattr(link, "provider_usato", "")),
    }


def build_pagamenti_payload(secret_state: SecretStateBuilder) -> dict[str, Any]:
    try:
        gp = _get_pagamenti()
        cfg = gp.config
        stats = gp.statistiche()
        links = [_link_payload(link) for link in gp.tutti_link()[:12]]
    except Exception as exc:
        current_app.logger.exception("Pagamenti React non disponibili: %s", exc)
        return {
            "available": False,
            "provider_attivi": [],
            "statistiche": {},
            "link_recenti": [],
            "message": "Impostazioni pagamenti non disponibili.",
        }

    return {
        "available": True,
        "provider_attivi": cfg.provider_attivi(),
        "statistiche": {
            "totale_link": int(stats.get("totale_link", 0) or 0),
            "attesi": int(stats.get("attesi", 0) or 0),
            "pagati": int(stats.get("pagati", 0) or 0),
            "falliti": int(stats.get("falliti", 0) or 0),
            "scaduti": int(stats.get("scaduti", 0) or 0),
            "importo_atteso": _money(stats.get("importo_atteso", 0)),
            "importo_pagato": _money(stats.get("importo_pagato", 0)),
        },
        "link_recenti": links,
        "stripe_abilitato": bool(cfg.stripe.abilitato),
        "stripe_modo": cfg.stripe.modo or "test",
        "stripe_pk_test": cfg.stripe.pk_test,
        "stripe_sk_test": secret_state(cfg.stripe.sk_test),
        "stripe_pk_live": cfg.stripe.pk_live,
        "stripe_sk_live": secret_state(cfg.stripe.sk_live),
        "stripe_webhook_secret": secret_state(cfg.stripe.webhook_secret),
        "paypal_abilitato": bool(cfg.paypal.abilitato),
        "paypal_modo": cfg.paypal.modo or "sandbox",
        "paypal_client_id": cfg.paypal.client_id,
        "paypal_client_secret": secret_state(cfg.paypal.client_secret),
        "satispay_abilitato": bool(cfg.satispay.abilitato),
        "satispay_modo": cfg.satispay.modo or "sandbox",
        "satispay_key_id": cfg.satispay.key_id,
        "satispay_private_key": secret_state(cfg.satispay.private_key_pem),
        "sumup_abilitato": bool(cfg.sumup.abilitato),
        "sumup_api_key": secret_state(cfg.sumup.api_key),
        "sumup_merchant_code": cfg.sumup.merchant_code,
        "bonifico_abilitato": bool(cfg.bonifico.abilitato),
        "bonifico_iban": cfg.bonifico.iban,
        "bonifico_intestazione": cfg.bonifico.intestazione,
        "bonifico_banca": cfg.bonifico.banca,
        "bonifico_note": cfg.bonifico.note_aggiuntive,
    }


def update_pagamenti_settings(payload: dict[str, Any]) -> None:
    from pct.pagamenti import (
        BonificoConfig,
        ConfigPagamenti,
        PayPalConfig,
        SatispayConfig,
        StripeConfig,
        SumUpConfig,
    )

    gp = _get_pagamenti()
    current = gp.config
    data = payload or {}
    config = ConfigPagamenti(
        stripe=StripeConfig(
            abilitato=_bool(data.get("stripe_abilitato"), current.stripe.abilitato),
            modo=_mode(data.get("stripe_modo"), {"test", "live"}, current.stripe.modo or "test"),
            pk_test=_text(data.get("stripe_pk_test")),
            sk_test=_text(data.get("stripe_sk_test")) or current.stripe.sk_test,
            pk_live=_text(data.get("stripe_pk_live")),
            sk_live=_text(data.get("stripe_sk_live")) or current.stripe.sk_live,
            webhook_secret=_text(data.get("stripe_webhook_secret")) or current.stripe.webhook_secret,
        ),
        paypal=PayPalConfig(
            abilitato=_bool(data.get("paypal_abilitato"), current.paypal.abilitato),
            modo=_mode(data.get("paypal_modo"), {"sandbox", "live"}, current.paypal.modo or "sandbox"),
            client_id=_text(data.get("paypal_client_id")),
            client_secret=_text(data.get("paypal_client_secret")) or current.paypal.client_secret,
        ),
        satispay=SatispayConfig(
            abilitato=_bool(data.get("satispay_abilitato"), current.satispay.abilitato),
            modo=_mode(data.get("satispay_modo"), {"sandbox", "production"}, current.satispay.modo or "sandbox"),
            key_id=_text(data.get("satispay_key_id")),
            private_key_pem=_text(data.get("satispay_private_key")) or current.satispay.private_key_pem,
        ),
        sumup=SumUpConfig(
            abilitato=_bool(data.get("sumup_abilitato"), current.sumup.abilitato),
            api_key=_text(data.get("sumup_api_key")) or current.sumup.api_key,
            merchant_code=_text(data.get("sumup_merchant_code")),
        ),
        bonifico=BonificoConfig(
            abilitato=_bool(data.get("bonifico_abilitato"), current.bonifico.abilitato),
            iban=_text(data.get("bonifico_iban")),
            intestazione=_text(data.get("bonifico_intestazione")),
            banca=_text(data.get("bonifico_banca")),
            note_aggiuntive=_text(data.get("bonifico_note")),
        ),
    )
    gp.aggiorna_config(config)
