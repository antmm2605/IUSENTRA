"""Modelli della libreria prompt "LegalSkills Italia".

Base normativa: ogni voce del catalogo dichiara i propri riferimenti
normativi (codici, leggi speciali, regolamenti UE) secondo il principio
delle fonti certe di IUSENTRA. I prompt sono ausili redazionali per il
professionista: ogni output prodotto con questi prompt resta una bozza
soggetta a revisione obbligatoria dell'avvocato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _clean_str(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_str_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    cleaned = [_clean_str(item) for item in values]
    return [item for item in cleaned if item]


@dataclass
class VocePrompt:
    """Istituto o attività forense da cui derivano i prompt di un'area."""

    voce_id: str
    nome: str
    descrizione: str
    riferimenti: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    forme: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "VocePrompt":
        return cls(
            voce_id=_clean_str(raw.get("voce_id")),
            nome=_clean_str(raw.get("nome")),
            descrizione=_clean_str(raw.get("descrizione")),
            riferimenti=_clean_str_list(raw.get("riferimenti")),
            tags=_clean_str_list(raw.get("tags")),
            forme=_clean_str_list(raw.get("forme")),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "voce_id": self.voce_id,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "riferimenti": list(self.riferimenti),
            "tags": list(self.tags),
            "forme": list(self.forme),
        }


@dataclass
class AreaPrompt:
    """Area del diritto del catalogo LegalSkills Italia."""

    area_id: str
    nome: str
    descrizione: str
    voci: list[VocePrompt] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AreaPrompt":
        voci = [VocePrompt.from_dict(item) for item in raw.get("voci", []) if isinstance(item, dict)]
        return cls(
            area_id=_clean_str(raw.get("area_id")),
            nome=_clean_str(raw.get("nome")),
            descrizione=_clean_str(raw.get("descrizione")),
            voci=voci,
        )

    @property
    def numero_prompt(self) -> int:
        return sum(len(voce.forme) for voce in self.voci)

    def to_public_dict(self, include_voci: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "area_id": self.area_id,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "numero_voci": len(self.voci),
            "numero_prompt": self.numero_prompt,
        }
        if include_voci:
            payload["voci"] = [voce.to_public_dict() for voce in self.voci]
        return payload


__all__ = ["AreaPrompt", "VocePrompt"]
