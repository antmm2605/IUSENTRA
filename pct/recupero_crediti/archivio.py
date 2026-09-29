"""Archivio delle posizioni di recupero crediti, per studio (file JSON accanto alla configurazione)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Iterable

from pct.recupero_crediti.modello import Posizione

_BLOCCO = threading.Lock()


class ArchivioRecupero:
    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso)

    @classmethod
    def accanto_a(cls, percorso_config: str | Path) -> "ArchivioRecupero":
        return cls(Path(percorso_config).with_name("recupero_crediti.json"))

    def _leggi(self) -> dict[str, dict]:
        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return dati.get("posizioni", {}) if isinstance(dati, dict) else {}

    def _scrivi(self, posizioni: dict[str, dict]) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        fd, temporaneo = tempfile.mkstemp(prefix=".recupero.", dir=str(self.percorso.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as uscita:
                json.dump({"versione": 1, "posizioni": posizioni}, uscita, ensure_ascii=False, indent=1)
            os.replace(temporaneo, self.percorso)
        except BaseException:
            Path(temporaneo).unlink(missing_ok=True)
            raise

    def tutte(self) -> list[Posizione]:
        return sorted((Posizione.from_dict(v) for v in self._leggi().values()), key=lambda p: (p.lotto, p.debitore.casefold()))

    def get(self, pid: str) -> Posizione | None:
        dati = self._leggi().get(str(pid))
        return Posizione.from_dict(dati) if dati else None

    def salva(self, posizioni: Iterable[Posizione]) -> None:
        with _BLOCCO:
            tutte = self._leggi()
            for p in posizioni:
                tutte[p.id] = {k: v for k, v in p.to_dict().items() if k not in {"capitale", "stato_etichetta"}}
            self._scrivi(tutte)


__all__ = ["ArchivioRecupero"]
