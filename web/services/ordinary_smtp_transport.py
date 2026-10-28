"""Scelta del trasporto SMTP ordinario; Gmail conserva il canale esistente."""
from __future__ import annotations


def ordinary_smtp_uses_local_signer(host: str) -> bool:
    return str(host or "").strip().lower().rstrip(".") not in {"smtp.gmail.com", "smtp.googlemail.com"}
