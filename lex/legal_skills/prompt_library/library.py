"""Servizio read-only della libreria prompt "LegalSkills Italia".

Carica il catalogo versionato (26 aree del diritto) da
``prompt_library/catalog/`` e compone i prompt nelle varie forme.
Il catalogo è bloccante e fail-closed: file mancanti o non validi
sollevano ``LegalSkillsError`` invece di degradare in silenzio.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from ..exceptions import LegalSkillsError
from .case_context import ContestoFascicolo
from .composer import FORME, componi_testo, forme_public, titolo_prompt
from .models import AreaPrompt, VocePrompt

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"


def _load_area_file(path: Path) -> AreaPrompt:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegalSkillsError(
            f"Catalogo prompt non leggibile: {path.name}", code="prompt_catalog_invalid", status_code=500
        ) from exc
    if not isinstance(raw, dict):
        raise LegalSkillsError(
            f"Catalogo prompt non valido: {path.name}", code="prompt_catalog_invalid", status_code=500
        )
    area = AreaPrompt.from_dict(raw)
    if not area.area_id or not area.voci:
        raise LegalSkillsError(
            f"Catalogo prompt incompleto: {path.name}", code="prompt_catalog_invalid", status_code=500
        )
    for voce in area.voci:
        if not voce.voce_id or not voce.nome or not voce.riferimenti:
            raise LegalSkillsError(
                f"Voce prompt senza riferimenti normativi: {area.area_id}/{voce.voce_id or '?'}",
                code="prompt_catalog_invalid",
                status_code=500,
            )
        sconosciute = [forma for forma in voce.forme if forma not in FORME]
        if sconosciute or not voce.forme:
            raise LegalSkillsError(
                f"Forme prompt non valide per {area.area_id}/{voce.voce_id}: {sconosciute}",
                code="prompt_catalog_invalid",
                status_code=500,
            )
    return area


class LegalPromptLibrary:
    """Libreria prompt read-only, con ricerca su tutto il catalogo."""

    def __init__(self, catalog_dir: Path | None = None) -> None:
        self._catalog_dir = catalog_dir or CATALOG_DIR
        self._lock = RLock()
        self._aree: dict[str, AreaPrompt] | None = None

    def invalidate(self) -> None:
        with self._lock:
            self._aree = None

    def _load(self) -> dict[str, AreaPrompt]:
        with self._lock:
            if self._aree is None:
                aree: dict[str, AreaPrompt] = {}
                files = sorted(self._catalog_dir.glob("*.json")) if self._catalog_dir.exists() else []
                for path in files:
                    area = _load_area_file(path)
                    if area.area_id in aree:
                        raise LegalSkillsError(
                            f"Area prompt duplicata: {area.area_id}", code="prompt_catalog_invalid", status_code=500
                        )
                    aree[area.area_id] = area
                if not aree:
                    raise LegalSkillsError(
                        "Catalogo prompt LegalSkills Italia non disponibile.",
                        code="prompt_catalog_missing",
                        status_code=500,
                    )
                self._aree = aree
            return self._aree

    def aree(self) -> list[AreaPrompt]:
        return sorted(self._load().values(), key=lambda area: area.nome.lower())

    def get_area(self, area_id: str) -> AreaPrompt:
        try:
            return self._load()[str(area_id or "").strip()]
        except KeyError as exc:
            raise LegalSkillsError("Area prompt non trovata.", code="prompt_area_not_found", status_code=404) from exc

    def totale_prompt(self) -> int:
        return sum(area.numero_prompt for area in self._load().values())

    def forme(self) -> list[dict[str, Any]]:
        return forme_public()

    def _entry(self, area: AreaPrompt, voce: VocePrompt, forma: str) -> dict[str, Any]:
        return {
            "prompt_id": f"{area.area_id}.{voce.voce_id}.{forma}",
            "titolo": titolo_prompt(voce, forma),
            "area_id": area.area_id,
            "area_nome": area.nome,
            "voce_id": voce.voce_id,
            "forma": forma,
            "forma_label": FORME[forma]["label"],
            "descrizione": voce.descrizione,
            "riferimenti": list(voce.riferimenti),
            "tags": list(voce.tags),
        }

    def search(self, query: str = "", area: str = "", forma: str = "", limit: int = 0) -> list[dict[str, Any]]:
        """Ricerca su tutto il catalogo; query vuota restituisce tutti i prompt."""
        testo = " ".join(str(query or "").lower().split())
        filtro_area = str(area or "").lower().strip()
        filtro_forma = str(forma or "").lower().strip()
        risultati: list[dict[str, Any]] = []
        for area_obj in self.aree():
            if filtro_area and filtro_area != area_obj.area_id.lower():
                continue
            for voce in area_obj.voci:
                haystack = " ".join(
                    [voce.nome, voce.descrizione, voce.voce_id, area_obj.nome, *voce.riferimenti, *voce.tags]
                ).lower()
                if testo and testo not in haystack:
                    continue
                for forma_id in voce.forme:
                    if filtro_forma and filtro_forma != forma_id:
                        continue
                    risultati.append(self._entry(area_obj, voce, forma_id))
                    if limit and len(risultati) >= limit:
                        return risultati
        return risultati

    def get_prompt(self, prompt_id: str, contesto: ContestoFascicolo | None = None) -> dict[str, Any]:
        """Restituisce il prompt completo, precompilato se c'è un contesto fascicolo."""
        parti = str(prompt_id or "").strip().split(".")
        if len(parti) != 3:
            raise LegalSkillsError("Identificativo prompt non valido.", code="prompt_not_found", status_code=404)
        area_id, voce_id, forma = parti
        area = self.get_area(area_id)
        voce = next((item for item in area.voci if item.voce_id == voce_id), None)
        if voce is None or forma not in voce.forme:
            raise LegalSkillsError("Prompt non trovato nel catalogo.", code="prompt_not_found", status_code=404)
        entry = self._entry(area, voce, forma)
        entry["testo"] = componi_testo(area, voce, forma, contesto=contesto)
        entry["forma_descrizione"] = FORME[forma]["descrizione"]
        if contesto is not None:
            entry["contesto_fascicolo"] = contesto.to_public_dict()
        return entry


_LIBRARY_LOCK = RLock()
_LIBRARY: LegalPromptLibrary | None = None


def get_prompt_library() -> LegalPromptLibrary:
    """Singleton di processo della libreria prompt."""
    global _LIBRARY
    with _LIBRARY_LOCK:
        if _LIBRARY is None:
            _LIBRARY = LegalPromptLibrary()
        return _LIBRARY


__all__ = ["CATALOG_DIR", "LegalPromptLibrary", "get_prompt_library"]
