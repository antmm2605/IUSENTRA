"""Avvisi operativi per la scadenza del certificato di firma digitale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from flask import current_app


@dataclass(frozen=True)
class SignatureCertificateAlert:
    category: str
    message: str
    days: int
    expiry_it: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: Any) -> date | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _format_it(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def build_signature_certificate_login_warning(config: Any, *, today: date | None = None) -> SignatureCertificateAlert | None:
    firma = getattr(config, "firma", None)
    if firma is None:
        return None
    expiry = _parse_date(getattr(firma, "certificato_scadenza", "") or getattr(firma, "certificato_scadenza_it", ""))
    if expiry is None:
        return None
    warning_days = int(getattr(firma, "certificato_giorni_preavviso", 20) or 20)
    warning_days = max(1, min(365, warning_days))
    remaining = (expiry - (today or date.today())).days
    expiry_it = _text(getattr(firma, "certificato_scadenza_it", "")) or _format_it(expiry)
    if remaining < 0:
        return SignatureCertificateAlert(
            category="danger",
            message=(
                f"Il certificato di firma digitale è scaduto il {expiry_it}. "
                "Rinnova il certificato prima di firmare o depositare atti."
            ),
            days=remaining,
            expiry_it=expiry_it,
        )
    if remaining <= warning_days:
        label = "giorno" if remaining == 1 else "giorni"
        return SignatureCertificateAlert(
            category="warning",
            message=(
                f"Il certificato di firma digitale scade il {expiry_it}: mancano {remaining} {label}. "
                "Programma il rinnovo prima dei prossimi depositi."
            ),
            days=remaining,
            expiry_it=expiry_it,
        )
    return None


def current_signature_certificate_login_warning() -> SignatureCertificateAlert | None:
    try:
        from web.blueprints.impostazioni import _get_gestore

        return build_signature_certificate_login_warning(_get_gestore().config)
    except Exception as exc:  # pragma: no cover - difesa runtime, non deve bloccare il login
        current_app.logger.warning("Avviso scadenza certificato firma non disponibile: %s", exc)
        return None
