"""Contesto fascicolo per la precompilazione dei prompt LegalSkills Italia.

Dataclass pura e serializzabile: il web layer la costruisce dai dati reali
del gestionale (fascicolo, documenti, scadenze) e il compositore la usa per
sostituire i segnaposto. Nessun dato viene inventato: i campi assenti
restano segnaposto da completare con l'avvocato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


@dataclass
class ContestoFascicolo:
    """Fotografia minima del fascicolo utile alla redazione di un prompt."""

    fascicolo_id: str
    numero: str = ""
    titolo: str = ""
    cliente: str = ""
    controparte: str = ""
    ufficio: str = ""
    numero_rg: str = ""
    anno_rg: str = ""
    giudice: str = ""
    sezione: str = ""
    oggetto: str = ""
    valore_causa: str = ""
    tipo_procedimento: str = ""
    documenti: list[str] = field(default_factory=list)
    scadenze: list[str] = field(default_factory=list)

    def etichetta_rg(self) -> str:
        if self.numero_rg and self.anno_rg:
            return f"RG {self.numero_rg}/{self.anno_rg}"
        if self.numero_rg:
            return f"RG {self.numero_rg}"
        return ""

    def etichetta_parti(self) -> str:
        if self.cliente and self.controparte:
            return f"assistito {self.cliente} contro {self.controparte}"
        if self.cliente:
            return f"assistito {self.cliente}"
        return ""

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "fascicolo_id": self.fascicolo_id,
            "numero": self.numero,
            "titolo": self.titolo,
            "cliente": self.cliente,
            "controparte": self.controparte,
            "ufficio": self.ufficio,
            "rg": self.etichetta_rg(),
            "oggetto": self.oggetto,
            "documenti": list(self.documenti),
            "scadenze": list(self.scadenze),
        }

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "ContestoFascicolo":
        return cls(
            fascicolo_id=_clean(raw.get("fascicolo_id")),
            numero=_clean(raw.get("numero")),
            titolo=_clean(raw.get("titolo")),
            cliente=_clean(raw.get("cliente")),
            controparte=_clean(raw.get("controparte")),
            ufficio=_clean(raw.get("ufficio")),
            numero_rg=_clean(raw.get("numero_rg")),
            anno_rg=_clean(raw.get("anno_rg")),
            giudice=_clean(raw.get("giudice")),
            sezione=_clean(raw.get("sezione")),
            oggetto=_clean(raw.get("oggetto")),
            valore_causa=_clean(raw.get("valore_causa")),
            tipo_procedimento=_clean(raw.get("tipo_procedimento")),
            documenti=[_clean(item) for item in raw.get("documenti", []) if _clean(item)],
            scadenze=[_clean(item) for item in raw.get("scadenze", []) if _clean(item)],
        )


__all__ = ["ContestoFascicolo"]
