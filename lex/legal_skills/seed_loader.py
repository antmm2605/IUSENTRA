"""Caricamento dei seed pack Legal Skills integrati."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import LegalSkillsError
from .models import LegalSkillPack
from .parser import parse_skill_markdown


SEED_PACKS_DIR = Path(__file__).resolve().parent / "seed_packs"


def _load_pack_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegalSkillsError("Seed pack non leggibile.", code="seed_pack_invalid", status_code=500) from exc
    if not isinstance(raw, dict):
        raise LegalSkillsError("Seed pack non valido.", code="seed_pack_invalid", status_code=500)
    return raw


def load_seed_pack(pack_dir: Path) -> LegalSkillPack:
    pack_config = _load_pack_json(pack_dir / "pack.json")
    pack_id = str(pack_config.get("pack_id") or pack_dir.name).strip()
    area = str(pack_config.get("area") or "default").strip()
    pack = LegalSkillPack(
        pack_id=pack_id,
        name=str(pack_config.get("name") or pack_id).strip(),
        description=str(pack_config.get("description") or "").strip(),
        area=area,
        jurisdiction=str(pack_config.get("jurisdiction") or "IT").strip(),
        source_mode=str(pack_config.get("source_mode") or "balanced").strip(),
        builtin=True,
        read_only=True,
        version=str(pack_config.get("version") or "1.0.0").strip(),
    )
    skills_dir = pack_dir / "skills"
    for skill_dir in sorted(skills_dir.iterdir() if skills_dir.exists() else []):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue
        raw = skill_md.read_text(encoding="utf-8")
        parsed = parse_skill_markdown(raw, pack_id=pack_id, skill_id=skill_dir.name, area=area, builtin=True)
        if parsed.skill.trust_status in {"material_concern", "refuse"}:
            raise LegalSkillsError(
                f"Seed skill non affidabile: {pack_id}/{skill_dir.name}",
                code="seed_skill_trust_failed",
                status_code=500,
            )
        pack.skills.append(parsed.skill)
    if not pack.skills:
        raise LegalSkillsError("Seed pack senza skill.", code="seed_pack_empty", status_code=500)
    return pack


def load_builtin_seed_packs(base_dir: Path | None = None) -> list[LegalSkillPack]:
    root = base_dir or SEED_PACKS_DIR
    packs: list[LegalSkillPack] = []
    for pack_dir in sorted(root.iterdir() if root.exists() else []):
        if pack_dir.is_dir():
            packs.append(load_seed_pack(pack_dir))
    if not packs:
        raise LegalSkillsError("Nessun seed pack Legal Skills disponibile.", code="seed_packs_missing", status_code=500)
    return packs


__all__ = ["SEED_PACKS_DIR", "load_builtin_seed_packs", "load_seed_pack"]
