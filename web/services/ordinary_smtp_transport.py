"""Scelta del trasporto SMTP ordinario; Gmail conserva il canale esistente."""
from __future__ import annotations


def ordinary_smtp_uses_local_signer(host: str) -> bool:
    return str(host or "").strip().lower().rstrip(".") not in {"smtp.gmail.com", "smtp.googlemail.com"}


def ordinary_smtp_tls_options(port: int, use_tls: bool) -> dict[str, bool]:
    """La porta submission 465 negozia TLS prima del saluto SMTP."""
    implicit = int(port) == 465 or not use_tls
    return {"use_ssl": implicit, "use_tls": not implicit}
