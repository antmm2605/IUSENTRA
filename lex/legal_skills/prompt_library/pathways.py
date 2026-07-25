"""Percorsi guidati per procedimento della libreria LegalSkills Italia.

Catalogo versionato di sequenze operative (es. recupero credito in via
monitoria, sfratto per morosità): ogni passo richiama un prompt reale del
catalogo e dichiara termini e riferimenti normativi (fonti certe). Il
caricamento è fail-closed: un passo che punta a un prompt inesistente
blocca l'avvio invece di degradare in silenzio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

from ..exceptions import LegalSkillsError
from .library import LegalPromptLibrary, get_prompt_library

PATHWAYS_DIR = Path(__file__).resolve().parent / "pathways_data"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return [item for item in (_clean(v) for v in values) if item]


@dataclass
class PassoPercorso:
    passo_id: str
    nome: str
    descrizione: str
    prompt_ref: str
    termini: list[str] = field(default_factory=list)
    riferimenti: list[str] = field(default_factory=list)
    template_refs: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "passo_id": self.passo_id,
            "nome": self.nome,
            "descrizione": self.descrizione,
            "prompt_ref": self.prompt_ref,
            "termini": list(self.termini),
            "riferimenti": list(self.riferimenti),
            "template_refs": list(self.template_refs),
        }


@dataclass
class Percorso:
    percorso_id: str
    nome: str
    area_id: str
    descrizione: str
    riferimenti: list[str] = field(default_factory=list)
    passi: list[PassoPercorso] = field(default_factory=list)

    def to_public_dict(self, include_passi: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "percorso_id": self.percorso_id,
            "nome": self.nome,
            "area_id": self.area_id,
            "descrizione": self.descrizione,
            "riferimenti": list(self.riferimenti),
            "numero_passi": len(self.passi),
        }
        if include_passi:
            payload["passi"] = [passo.to_public_dict() for passo in self.passi]
        return payload


def _load_percorso(path: Path, prompt_ids: set[str]) -> Percorso:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegalSkillsError(
            f"Percorso non leggibile: {path.name}", code="pathway_invalid", status_code=500
        ) from exc
    if not isinstance(raw, dict):
        raise LegalSkillsError(f"Percorso non valido: {path.name}", code="pathway_invalid", status_code=500)
    percorso = Percorso(
        percorso_id=_clean(raw.get("percorso_id")),
        nome=_clean(raw.get("nome")),
        area_id=_clean(raw.get("area_id")),
        descrizione=_clean(raw.get("descrizione")),
        riferimenti=_clean_list(raw.get("riferimenti")),
    )
    visti: set[str] = set()
    for voce in raw.get("passi", []):
        if not isinstance(voce, dict):
            continue
        passo = PassoPercorso(
            passo_id=_clean(voce.get("passo_id")),
            nome=_clean(voce.get("nome")),
            descrizione=_clean(voce.get("descrizione")),
            prompt_ref=_clean(voce.get("prompt_ref")),
            termini=_clean_list(voce.get("termini")),
            riferimenti=_clean_list(voce.get("riferimenti")),
            template_refs=_clean_list(voce.get("template_refs")),
        )
        if not passo.passo_id or passo.passo_id in visti:
            raise LegalSkillsError(
                f"Passo duplicato o senza id in {percorso.percorso_id}", code="pathway_invalid", status_code=500
            )
        if passo.prompt_ref not in prompt_ids:
            raise LegalSkillsError(
                f"Passo {percorso.percorso_id}/{passo.passo_id} punta a un prompt inesistente: {passo.prompt_ref}",
                code="pathway_invalid",
                status_code=500,
            )
        if not passo.riferimenti:
            raise LegalSkillsError(
                f"Passo senza base normativa: {percorso.percorso_id}/{passo.passo_id}",
                code="pathway_invalid",
                status_code=500,
            )
        visti.add(passo.passo_id)
        percorso.passi.append(passo)
    if not percorso.percorso_id or not percorso.passi or not percorso.riferimenti:
        raise LegalSkillsError(f"Percorso incompleto: {path.name}", code="pathway_invalid", status_code=500)
    return percorso


class PathwayCatalog:
    """Catalogo read-only dei percorsi per procedimento."""

    def __init__(self, pathways_dir: Path | None = None, library: LegalPromptLibrary | None = None) -> None:
        self._dir = pathways_dir or PATHWAYS_DIR
        self._library = library
        self._lock = RLock()
        self._percorsi: dict[str, Percorso] | None = None

    def invalidate(self) -> None:
        with self._lock:
            self._percorsi = None

    def _load(self) -> dict[str, Percorso]:
        with self._lock:
            if self._percorsi is None:
                library = self._library or get_prompt_library()
                prompt_ids = {entry["prompt_id"] for entry in library.search()}
                percorsi: dict[str, Percorso] = {}
                for path in sorted(self._dir.glob("*.json")) if self._dir.exists() else []:
                    percorso = _load_percorso(path, prompt_ids)
                    if percorso.percorso_id in percorsi:
                        raise LegalSkillsError(
                            f"Percorso duplicato: {percorso.percorso_id}", code="pathway_invalid", status_code=500
                        )
                    percorsi[percorso.percorso_id] = percorso
                if not percorsi:
                    raise LegalSkillsError(
                        "Nessun percorso guidato disponibile.", code="pathways_missing", status_code=500
                    )
                self._percorsi = percorsi
            return self._percorsi

    def percorsi(self) -> list[Percorso]:
        return sorted(self._load().values(), key=lambda percorso: percorso.nome.lower())

    def get(self, percorso_id: str) -> Percorso:
        try:
            return self._load()[str(percorso_id or "").strip()]
        except KeyError as exc:
            raise LegalSkillsError("Percorso non trovato.", code="pathway_not_found", status_code=404) from exc


_CATALOG_LOCK = RLock()
_CATALOG: PathwayCatalog | None = None


def get_pathway_catalog() -> PathwayCatalog:
    """Singleton di processo del catalogo percorsi."""
    global _CATALOG
    with _CATALOG_LOCK:
        if _CATALOG is None:
            _CATALOG = PathwayCatalog()
        return _CATALOG


__all__ = ["PATHWAYS_DIR", "PassoPercorso", "PathwayCatalog", "Percorso", "get_pathway_catalog"]
