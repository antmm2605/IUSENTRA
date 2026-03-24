"""
pct/cal_token.py — Gestione token segreto per subscription WebCal.

Il token è un UUID casuale (secrets.token_urlsafe) che funge da
"chiave" nell'URL del feed iCal:

    /cal/<token>/agenda.ics
    /cal/<token>/scadenze.ics
    /cal/<token>/completo.ics

Rigenerare il token revoca tutti i link precedentemente condivisi.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path


def _path(token_dir: str) -> Path:
    return Path(token_dir) / "cal_token.json"


def get_token(token_dir: str) -> dict:
    """Restituisce il token esistente; ne crea uno nuovo se assente."""
    p = _path(token_dir)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _genera(token_dir)


def rigenera_token(token_dir: str) -> dict:
    """Genera un nuovo token (revoca il precedente)."""
    return _genera(token_dir)


def _genera(token_dir: str) -> dict:
    data = {
        "token": secrets.token_urlsafe(32),
        "creato_il": datetime.now().isoformat(),
    }
    p = _path(token_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
