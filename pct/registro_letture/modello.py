"""Gli oggetti del registro: oggetto da leggere, lettura, anomalia, stato."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

TIPI = ("documento", "pec", "allegato_pec")
STATI_LETTURA = ("letto", "in_corso", "errore", "non_leggibile")
STATI_ANOMALIA = ("aperta", "confermata", "corretta", "ignorata")
GRAVITA = ("alta", "media", "bassa")


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


@dataclass(slots=True)
class Oggetto:
    """Un oggetto del fascicolo che i lettori leggono: documento, PEC o allegato PEC."""

    tipo: str
    oggetto_id: str
    nome: str = ""
    sha256: str = ""            # impronta del contenuto in chiaro (quando nota)
    sha256_archivio: str = ""   # impronta del file conservato (cifrato)
    dimensione: int = 0
    origine: str = ""
    data_oggetto: str = ""
    cliente: str = ""
    numero_rg: str = ""
    anno_rg: str = ""
    presente: bool = True

    @property
    def impronta(self) -> str:
        """L'impronta con cui il registro riconosce il contenuto."""
        return impronta_oggetto(self)

    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["impronta"] = self.impronta
        return dati


def impronta_oggetto(oggetto: Oggetto | dict[str, Any]) -> str:
    """Contenuto in chiaro se noto, altrimenti file conservato, altrimenti dimensione."""
    if isinstance(oggetto, dict):
        sha = _testo(oggetto.get("sha256")).lower()
        archivio = _testo(oggetto.get("sha256_archivio")).lower()
        dimensione = int(oggetto.get("dimensione") or 0)
    else:
        sha = _testo(oggetto.sha256).lower()
        archivio = _testo(oggetto.sha256_archivio).lower()
        dimensione = int(oggetto.dimensione or 0)
    if sha:
        return sha
    if archivio:
        return f"archivio:{archivio}"
    return f"dimensione:{max(0, dimensione)}"


def impronta_inventario(oggetti: Iterable[Oggetto | dict[str, Any]]) -> str:
    """L'impronta del fascicolo intero: cambia se un oggetto è nuovo, cambiato o rimosso."""
    righe: list[tuple[str, str, str]] = []
    for oggetto in oggetti:
        if isinstance(oggetto, dict):
            if not oggetto.get("presente", True):
                continue
            righe.append((_testo(oggetto.get("tipo")), _testo(oggetto.get("oggetto_id")), impronta_oggetto(oggetto)))
        else:
            if not oggetto.presente:
                continue
            righe.append((oggetto.tipo, oggetto.oggetto_id, oggetto.impronta))
    righe.sort()
    return hashlib.sha256(json.dumps(righe, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Lettura:
    tipo: str
    oggetto_id: str
    sha256: str
    lettore: str
    versione_lettore: str
    stato: str
    esito: dict[str, Any] = field(default_factory=dict)
    durata_ms: int = 0
    letto_il: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Anomalia:
    id: str
    tipo: str
    oggetto_id: str
    sha256: str
    lettore: str
    campo: str
    valore_letto: str
    valore_proposto: str
    contesto: str
    motivo: str
    codice: str
    gravita: str
    stato: str = "aperta"
    valore_confermato: str = ""
    creata_il: str = ""
    risolta_il: str = ""
    risolta_da: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StatoLettore:
    lettore: str
    etichetta: str
    versione: str
    letti: int
    da_leggere: int
    errori: int
    ultima_lettura: str
    completa: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StatoFascicolo:
    fascicolo_id: str
    impronta: str
    oggetti: int
    lettori: list[StatoLettore]
    per_oggetto: list[dict[str, Any]]
    anomalie_aperte: int
    tutto_letto: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "fascicolo_id": self.fascicolo_id,
            "impronta": self.impronta,
            "oggetti": self.oggetti,
            "lettori": [voce.to_dict() for voce in self.lettori],
            "per_oggetto": list(self.per_oggetto),
            "anomalie_aperte": self.anomalie_aperte,
            "tutto_letto": self.tutto_letto,
        }


__all__ = [
    "GRAVITA",
    "STATI_ANOMALIA",
    "STATI_LETTURA",
    "TIPI",
    "Anomalia",
    "Lettura",
    "Oggetto",
    "StatoFascicolo",
    "StatoLettore",
    "impronta_inventario",
    "impronta_oggetto",
]
