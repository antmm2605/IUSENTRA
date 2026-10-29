"""Controllo del registro delle fonti ufficiali (``pct/legal_rules/source_registry.yml``).

Uno stato «verified_snapshot» dichiara che esiste una fotografia verificata del testo: senza l'impronta
SHA-256 di quella fotografia (``source_hash``) la dichiarazione non e' riscontrabile e la fonte va trattata
come non verificata. Le impronte non si inventano: si declassa lo stato e si segnala.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REGISTRO = Path(__file__).resolve().parents[2] / "pct" / "legal_rules" / "source_registry.yml"
STATI_CON_IMPRONTA = {"verified_snapshot"}
STATO_DECLASSATO = "snapshot_senza_impronta"
_SHA256 = re.compile(r"[0-9a-f]{64}")


def impronta_valida(valore: Any) -> bool:
    return isinstance(valore, str) and _SHA256.fullmatch(valore.strip().lower()) is not None


def stato_verifica_effettivo(fonte: dict) -> str:
    """Stato dichiarato, declassato a «snapshot_senza_impronta» se «verified_snapshot» manca di hash valido."""
    stato = str((fonte or {}).get("verification_status") or "pending_live_verification").strip()
    if stato in STATI_CON_IMPRONTA and not impronta_valida((fonte or {}).get("source_hash")):
        return STATO_DECLASSATO
    return stato


def valida_registro(payload: dict) -> list[str]:
    """Problemi del registro: lista vuota = nessuna fonte dichiarata verificata senza impronta."""
    problemi = []
    for fonte in (payload or {}).get("sources") or []:
        if not isinstance(fonte, dict):
            problemi.append("voce del registro non strutturata")
            continue
        if stato_verifica_effettivo(fonte) == STATO_DECLASSATO:
            problemi.append(f"{fonte.get('id') or '?'}: verified_snapshot senza source_hash SHA-256")
    return problemi


def carica_registro(percorso: Path = REGISTRO) -> dict:
    """Registro con gli stati gia' declassati dove l'impronta manca (``verification_status_dichiarato`` conserva l'originale)."""
    payload = json.loads(Path(percorso).read_text(encoding="utf-8"))
    for fonte in payload.get("sources") or []:
        if isinstance(fonte, dict):
            effettivo = stato_verifica_effettivo(fonte)
            if effettivo != fonte.get("verification_status"):
                fonte["verification_status_dichiarato"] = fonte.get("verification_status")
                fonte["verification_status"] = effettivo
    return payload


__all__ = ["carica_registro", "impronta_valida", "stato_verifica_effettivo", "valida_registro"]
