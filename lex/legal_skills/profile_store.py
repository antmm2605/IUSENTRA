"""Storage tenant-aware del profilo Legal Skills."""

from __future__ import annotations

import json
from pathlib import Path
import uuid
from typing import Any, Callable, Mapping

from .exceptions import ProfileIncompleteError, StorageError
from .models import LegalSkillProfile, utc_now_iso


AuditCallback = Callable[[str, str, str, str], Any]


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


class LegalSkillProfileStore:
    def __init__(self, profile_path: str | Path, *, audit: AuditCallback | None = None) -> None:
        self.profile_path = Path(profile_path)
        self.snapshots_dir = self.profile_path.parent / "snapshots"
        self.audit = audit

    def _audit(self, action: str, entity_id: str, details: str) -> None:
        if callable(self.audit):
            self.audit(action, "legal_skills_profile", entity_id, details)

    def load(self) -> LegalSkillProfile:
        if not self.profile_path.exists():
            return LegalSkillProfile(updated_at="", updated_by="").refresh_status()
        try:
            raw = json.loads(self.profile_path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("Profilo Legal Skills non leggibile.") from exc
        if not isinstance(raw, Mapping):
            raw = {}
        profile = LegalSkillProfile(
            profile_id=str(raw.get("profile_id") or "studio"),
            status=str(raw.get("status") or "incomplete"),
            firm_name=str(raw.get("firm_name") or ""),
            jurisdictions=[str(item) for item in raw.get("jurisdictions") or ["IT"] if str(item).strip()],
            practice_areas=[str(item) for item in raw.get("practice_areas") or [] if str(item).strip()],
            preferred_source_mode=str(raw.get("preferred_source_mode") or "strict"),
            matter_context=dict(raw.get("matter_context") or {}) if isinstance(raw.get("matter_context"), Mapping) else {},
            verified_fields=[str(item) for item in raw.get("verified_fields") or []],
            missing_fields=[str(item) for item in raw.get("missing_fields") or []],
            updated_at=str(raw.get("updated_at") or ""),
            updated_by=str(raw.get("updated_by") or ""),
        )
        return profile.refresh_status()

    def save(self, profile: LegalSkillProfile, *, actor: str = "") -> LegalSkillProfile:
        profile.updated_at = utc_now_iso()
        profile.updated_by = actor or profile.updated_by
        profile.refresh_status()
        try:
            current = self.load()
            snapshot = current.to_public_dict()
            if current.updated_at:
                snapshot_name = f"{utc_now_iso().replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}.json"
                _atomic_write_json(self.snapshots_dir / snapshot_name, snapshot)
            _atomic_write_json(self.profile_path, profile.to_public_dict())
        except OSError as exc:
            raise StorageError("Profilo Legal Skills non salvabile.") from exc
        self._audit("legal_skills_profile_saved", profile.profile_id, "Profilo Legal Skills aggiornato.")
        return profile

    def cold_start(self, payload: Mapping[str, Any], *, actor: str = "") -> LegalSkillProfile:
        current = self.load()
        profile = LegalSkillProfile(
            profile_id="studio",
            firm_name=str(payload.get("firm_name") or current.firm_name or "").strip(),
            jurisdictions=[str(item).strip() for item in payload.get("jurisdictions") or current.jurisdictions or ["IT"] if str(item).strip()],
            practice_areas=[str(item).strip() for item in payload.get("practice_areas") or current.practice_areas or [] if str(item).strip()],
            preferred_source_mode=str(payload.get("preferred_source_mode") or current.preferred_source_mode or "strict").strip(),
            matter_context=dict(payload.get("matter_context") or current.matter_context or {})
            if isinstance(payload.get("matter_context") or current.matter_context, Mapping)
            else {},
            verified_fields=[str(item) for item in payload.get("verified_fields") or []],
            updated_by=actor,
        ).refresh_status()
        return self.save(profile, actor=actor)

    def require_ready(self) -> LegalSkillProfile:
        profile = self.load().refresh_status()
        if profile.status != "ready":
            raise ProfileIncompleteError("Completa il profilo Legal Skills prima di generare risultati sostanziali.")
        return profile

    def placeholder_report(self) -> dict[str, Any]:
        profile = self.load().refresh_status()
        placeholders = [field for field in ("firm_name", "practice_areas") if field in profile.missing_fields]
        return {
            "ok": True,
            "status": profile.status,
            "profile": profile.to_public_dict(),
            "placeholders": placeholders,
        }


__all__ = ["LegalSkillProfileStore"]
