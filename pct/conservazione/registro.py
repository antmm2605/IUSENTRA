"""Registro dei pacchetti di versamento dello studio (chi, quando, cosa, esito del conservatore).

Il pacchetto si conserva cifrato accanto al registro, così lo si può riscaricare identico
(stessa impronta) fino all'esito del versamento. L'esito lo dà il rapporto di versamento del
conservatore: qui se ne registrano gli estremi.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATI = {"preparato": "Pronto da versare", "versato": "Versato: rapporto di versamento ricevuto",
         "rifiutato": "Rifiutato dal conservatore"}


@dataclass
class Versamento:
    id: str = field(default_factory=lambda: "PDV-" + uuid.uuid4().hex[:10].upper())
    fascicolo_id: str = ""
    creato_il: str = ""
    creato_da: str = ""
    documenti: list[dict[str, str]] = field(default_factory=list)
    impronta_pacchetto: str = ""
    dimensione: int = 0
    anni_conservazione: int = 10
    stato: str = "preparato"
    conservatore: str = ""
    data_versamento: str = ""
    id_rapporto: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "stato_etichetta": STATI.get(self.stato, self.stato)}

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "Versamento":
        return cls(**{k: v for k, v in (dati or {}).items() if k in cls.__dataclass_fields__})


class RegistroVersamenti:
    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso)
        self.cartella_pacchetti = self.percorso.parent / "pacchetti"

    @classmethod
    def accanto_a(cls, percorso_config: str | Path) -> "RegistroVersamenti":
        return cls(Path(percorso_config).parent / "conservazione" / "versamenti.json")

    def _leggi(self) -> dict[str, dict[str, Any]]:
        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
            return dati if isinstance(dati, dict) else {}
        except (OSError, ValueError):
            return {}

    def _scrivi(self, dati: dict[str, dict[str, Any]]) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        fd, temporaneo = tempfile.mkstemp(dir=self.percorso.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(dati, file, ensure_ascii=False, indent=1)
        os.replace(temporaneo, self.percorso)

    def salva(self, versamento: Versamento, pacchetto_cifrato: bytes | None = None) -> None:
        if pacchetto_cifrato is not None:
            self.cartella_pacchetti.mkdir(parents=True, exist_ok=True)
            (self.cartella_pacchetti / f"{versamento.id}.zip.enc").write_bytes(pacchetto_cifrato)
        dati = self._leggi()
        dati[versamento.id] = asdict(versamento)
        self._scrivi(dati)

    def get(self, vid: str) -> Versamento | None:
        voce = self._leggi().get(str(vid))
        return Versamento.from_dict(voce) if voce else None

    def per_fascicolo(self, fascicolo_id: str) -> list[Versamento]:
        voci = [Versamento.from_dict(v) for v in self._leggi().values() if v.get("fascicolo_id") == fascicolo_id]
        return sorted(voci, key=lambda v: v.creato_il, reverse=True)

    def pacchetto(self, vid: str) -> bytes | None:
        percorso = self.cartella_pacchetti / f"{Path(str(vid)).name}.zip.enc"
        return percorso.read_bytes() if percorso.is_file() else None


__all__ = ["STATI", "RegistroVersamenti", "Versamento"]
