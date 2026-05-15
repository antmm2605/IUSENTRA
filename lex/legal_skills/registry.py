"""Registry read-only dei Legal Skills pack."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

from .exceptions import FeatureDisabledError, SkillNotFoundError
from .models import LegalSkill, LegalSkillPack
from .seed_loader import load_builtin_seed_packs


FeatureFlagReader = Callable[[str], bool]


class LegalSkillRegistry:
    def __init__(
        self,
        *,
        feature_enabled: FeatureFlagReader | None = None,
        custom_enabled: FeatureFlagReader | None = None,
    ) -> None:
        self._feature_enabled = feature_enabled
        self._custom_enabled = custom_enabled
        self._lock = RLock()
        self._packs: dict[str, LegalSkillPack] | None = None

    def invalidate(self) -> None:
        with self._lock:
            self._packs = None

    def _assert_enabled(self) -> None:
        if self._feature_enabled is not None and not self._feature_enabled("lex.legalSkills.enabled"):
            raise FeatureDisabledError("Legal Skills non attivo per questo studio.")

    def _load(self) -> dict[str, LegalSkillPack]:
        with self._lock:
            if self._packs is None:
                self._packs = {pack.pack_id: pack for pack in load_builtin_seed_packs()}
            return self._packs

    def list_packs(self) -> list[LegalSkillPack]:
        self._assert_enabled()
        return list(self._load().values())

    def get_pack(self, pack_id: str) -> LegalSkillPack:
        self._assert_enabled()
        try:
            return self._load()[pack_id]
        except KeyError as exc:
            raise SkillNotFoundError("Pack Legal Skills non trovato.") from exc

    def list_skills(self, pack_id: str) -> list[LegalSkill]:
        return list(self.get_pack(pack_id).skills)

    def get_skill(self, pack_id: str, skill_id: str) -> LegalSkill:
        pack = self.get_pack(pack_id)
        for skill in pack.skills:
            if skill.skill_id == skill_id:
                return skill
        raise SkillNotFoundError("Skill Legal Skills non trovata.")

    def can_use_custom_skills(self) -> bool:
        return bool(self._custom_enabled and self._custom_enabled("lex.legalSkills.customSkills"))

    def search(self, query: str = "", area: str = "") -> list[LegalSkill]:
        text = " ".join(str(query or "").lower().split())
        area_filter = str(area or "").lower().strip()
        results: list[LegalSkill] = []
        for pack in self.list_packs():
            for skill in pack.skills:
                if area_filter and area_filter not in {pack.area.lower(), skill.area.lower()}:
                    continue
                haystack = f"{skill.name} {skill.description} {skill.skill_id}".lower()
                if not text or text in haystack:
                    results.append(skill)
        return results

    def to_public_payload(self) -> dict[str, Any]:
        return {"ok": True, "packs": [pack.to_public_dict(include_skills=False) for pack in self.list_packs()]}


__all__ = ["LegalSkillRegistry"]
