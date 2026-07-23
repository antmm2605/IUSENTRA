"""Avanzamento dei percorsi guidati per fascicolo.

Store JSON tenant-aware (stesso pattern di profilo e runs Legal Skills):
per ogni coppia percorso/fascicolo registra i passi completati con data e
operatore, così la UI può proporre il passo successivo. Scrittura atomica,
nessun dato oltre l'identificativo del fascicolo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..exceptions import StorageError

_MAX_RIGHE = 2000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _chiave(percorso_id: str, fascicolo_id: str) -> str:
    return f"{percorso_id}::{fascicolo_id}"


class PathwayProgressStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("Avanzamento percorsi non leggibile.") from exc
        return raw if isinstance(raw, dict) else {}

    def _save(self, dati: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            righe = dict(list(dati.items())[-_MAX_RIGHE:])
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(righe, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError as exc:
            raise StorageError("Avanzamento percorsi non salvabile.") from exc

    def stato(self, percorso_id: str, fascicolo_id: str) -> dict[str, Any]:
        """Mappa passo_id → {completato_il, operatore} per il fascicolo."""
        voce = self._load().get(_chiave(percorso_id, fascicolo_id)) or {}
        passi = voce.get("passi") if isinstance(voce, dict) else {}
        return passi if isinstance(passi, dict) else {}

    def segna(
        self, percorso_id: str, fascicolo_id: str, passo_id: str, *, completato: bool, actor: str = ""
    ) -> dict[str, Any]:
        """Marca (o riapre) un passo e restituisce lo stato aggiornato."""
        dati = self._load()
        chiave = _chiave(percorso_id, fascicolo_id)
        voce = dati.get(chiave)
        if not isinstance(voce, dict):
            voce = {"percorso_id": percorso_id, "fascicolo_id": fascicolo_id, "passi": {}}
        passi = voce.get("passi")
        if not isinstance(passi, dict):
            passi = {}
        if completato:
            passi[passo_id] = {"completato_il": _utc_now(), "operatore": str(actor or "")[:120]}
        else:
            passi.pop(passo_id, None)
        voce["passi"] = passi
        voce["aggiornato_il"] = _utc_now()
        dati[chiave] = voce
        self._save(dati)
        return passi


__all__ = ["PathwayProgressStore"]
