"""Motore deterministico e governato per eseguire Legal Skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from lex.research.request_profile import classify_request
from lex.research.source_policy import allowed_domains, infer_area_with_confidence

from .exceptions import SkillNotFoundError, StorageError
from .guardrails import (
    build_reviewer_note,
    classify_output_risk,
    enforce_jurisdiction_policy,
    enforce_privilege_destination_policy,
    sanitize_untrusted_document_text,
)
from .models import (
    LegalSkill,
    LegalSkillCitation,
    LegalSkillFinding,
    LegalSkillProfile,
    SkillRunRequest,
    SkillRunResult,
    utc_now_iso,
)
from .output_contracts import contract_for_skill
from .profile_store import LegalSkillProfileStore
from .registry import LegalSkillRegistry


AuditCallback = Callable[[str, str, str, str], Any]


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


class SkillRunStorage:
    def __init__(self, runs_path: str | Path) -> None:
        self.runs_path = Path(runs_path)

    def _load_all(self) -> list[dict[str, Any]]:
        if not self.runs_path.exists():
            return []
        try:
            raw = json.loads(self.runs_path.read_text(encoding="utf-8") or "[]")
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("Registro Legal Skills non leggibile.") from exc
        return raw if isinstance(raw, list) else []

    def save(self, result: SkillRunResult) -> SkillRunResult:
        rows = [row for row in self._load_all() if row.get("run_id") != result.run_id]
        rows.append(result.to_public_dict())
        try:
            _atomic_write_json(self.runs_path, rows[-500:])
        except OSError as exc:
            raise StorageError("Registro Legal Skills non salvabile.") from exc
        return result

    def get(self, run_id: str) -> dict[str, Any]:
        for row in self._load_all():
            if str(row.get("run_id") or "") == run_id:
                return row
        raise SkillNotFoundError("Risultato Legal Skills non trovato.")

    def update(self, run_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        rows = self._load_all()
        updated: dict[str, Any] | None = None
        for row in rows:
            if str(row.get("run_id") or "") == run_id:
                row.update(dict(updates))
                updated = row
                break
        if updated is None:
            raise SkillNotFoundError("Risultato Legal Skills non trovato.")
        _atomic_write_json(self.runs_path, rows[-500:])
        return updated


class LegalSkillWorkflowEngine:
    def __init__(
        self,
        *,
        registry: LegalSkillRegistry,
        profile_store: LegalSkillProfileStore,
        storage: SkillRunStorage,
        audit: AuditCallback | None = None,
    ) -> None:
        self.registry = registry
        self.profile_store = profile_store
        self.storage = storage
        self.audit = audit

    def _audit(self, action: str, entity_id: str, details: str) -> None:
        if callable(self.audit):
            self.audit(action, "legal_skills", entity_id, details)

    def _run_id(self, request: SkillRunRequest) -> str:
        raw = f"{utc_now_iso()}:{request.pack_id}:{request.skill_id}:{request.question}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _document_citations(self, documents: list[dict[str, Any]]) -> tuple[list[LegalSkillCitation], list[str], str]:
        citations: list[LegalSkillCitation] = []
        warnings: list[str] = []
        combined: list[str] = []
        for index, doc in enumerate(documents[:12], start=1):
            title = str(doc.get("title") or doc.get("name") or f"Documento {index}").strip()[:120]
            text, doc_warnings = sanitize_untrusted_document_text(str(doc.get("text") or doc.get("content") or ""))
            warnings.extend(doc_warnings)
            if text.strip():
                combined.append(text)
                citations.append(
                    LegalSkillCitation(
                        label=title,
                        source_type="internal",
                        reference=f"Documento interno {index}",
                        reliability="high",
                        excerpt=" ".join(text.split())[:260],
                    )
                )
        return citations, warnings, "\n\n".join(combined)

    def _policy_citations(self, profile: LegalSkillProfile, question: str, source_mode: str) -> list[LegalSkillCitation]:
        inferred = infer_area_with_confidence(question) or {"area": profile.practice_areas[0] if profile.practice_areas else "default"}
        area = str(inferred.get("area") or "default")
        domains = allowed_domains(area, source_mode)[:4]
        citations: list[LegalSkillCitation] = []
        for domain in domains:
            source_type = "official" if any(token in domain for token in ("normattiva", "gazzettaufficiale", "garanteprivacy", "giustizia")) else "verified"
            citations.append(
                LegalSkillCitation(
                    label=domain,
                    source_type=source_type,
                    reference=f"Policy fonti Lex: {area}",
                    reliability="high" if source_type == "official" else "medium",
                    url=f"https://{domain.strip('*')}" if "." in domain and "*" not in domain else "",
                )
            )
        return citations

    def _build_findings(self, *, skill_id: str, context_text: str, schema: dict[str, Any]) -> list[LegalSkillFinding]:
        columns = schema.get("finding_columns") or ["tema", "stato", "azione", "fonte"]
        snippets = [line.strip() for line in context_text.splitlines() if line.strip()][:4]
        if not snippets:
            return [
                LegalSkillFinding(
                    title="Base informativa insufficiente",
                    status="da completare",
                    severity="high",
                    summary="Aggiungi documenti, dati fascicolo o fonti prima di usare il risultato.",
                    recommendation="Integra il contesto e rilancia la skill.",
                )
            ]
        findings: list[LegalSkillFinding] = []
        for index, snippet in enumerate(snippets[:4], start=1):
            findings.append(
                LegalSkillFinding(
                    title=f"{columns[0].capitalize()} {index}",
                    status="da verificare",
                    severity="medium",
                    summary=snippet[:260],
                    recommendation="Verificare il punto nel documento e decidere la prossima azione di studio.",
                )
            )
        if skill_id in {"renewal_watch", "chronology_builder"}:
            findings.insert(
                0,
                LegalSkillFinding(
                    title="Sequenza temporale",
                    status="da verificare",
                    severity="medium",
                    summary="Il motore ha raccolto gli elementi ordinabili, ma le date vanno confermate sul fascicolo.",
                    recommendation="Confrontare contratto, PEC e agenda prima di approvare.",
                ),
            )
        return findings[:6]

    def run(
        self,
        request: SkillRunRequest,
        *,
        actor: str = "",
        user_roles: list[str] | None = None,
        skill: LegalSkill | None = None,
    ) -> SkillRunResult:
        # `skill` pre-risolta: usata dalla libreria prompt per eseguire una
        # skill sintetica read-only senza passare dal registry dei pack.
        profile = self.profile_store.require_ready()
        skill = skill or self.registry.get_skill(request.pack_id, request.skill_id)
        requested_mode = request.requested_source_mode or skill.source_mode or profile.preferred_source_mode
        request_profile = classify_request(request.question or skill.description, requested_mode=requested_mode)
        source_mode = request_profile.source_mode or requested_mode or "balanced"
        schema = contract_for_skill(skill.skill_id)
        document_citations, doc_warnings, context_text = self._document_citations(request.documents)
        citations = [*document_citations, *self._policy_citations(profile, request.question or skill.description, source_mode)]
        warnings = [
            *doc_warnings,
            *enforce_jurisdiction_policy(profile.jurisdictions),
            *enforce_privilege_destination_policy(request.context),
        ]
        findings = self._build_findings(skill_id=skill.skill_id, context_text=context_text, schema=schema)
        if not document_citations and source_mode == "strict":
            answer = "Base documentale insufficiente: completa il contesto o collega fonti interne prima di usare questa bozza."
            status = "degraded"
            warnings.append("Risultato limitato per assenza di documenti interni verificati.")
        else:
            sections = schema.get("sections") or ["Sintesi", "Punti di attenzione", "Fonti"]
            answer = (
                f"{sections[0]}: analisi preliminare per {skill.name}. "
                "Usa i punti sotto come griglia di revisione, non come parere finale. "
                "Le fonti e i documenti indicati devono essere controllati prima dell'approvazione."
            )
            status = "completed"
        risk = classify_output_risk(answer, request_risk=request_profile.risk_level)
        reviewer_note = build_reviewer_note(risk_level=risk, source_mode=source_mode, citations=citations, warnings=warnings)
        result = SkillRunResult(
            run_id=self._run_id(request),
            pack_id=skill.pack_id,
            skill_id=skill.skill_id,
            status=status,
            question=request.question or skill.description,
            answer=answer,
            findings=findings,
            citations=citations,
            reviewer_note=reviewer_note,
            confidence="low" if status == "degraded" else ("medium" if risk != "low" else "high"),
            source_mode=source_mode,
            needs_review=True,
            disable_exports=reviewer_note.blocks_export,
            metadata={
                "request_profile": request_profile.to_dict(),
                "schema": schema,
                "warnings": warnings,
                "actor": actor,
                "roles": user_roles or [],
            },
        )
        self.storage.save(result)
        self._audit("legal_skills_run_completed", result.run_id, f"Eseguita skill {skill.pack_id}/{skill.skill_id}.")
        return result


__all__ = ["LegalSkillWorkflowEngine", "SkillRunStorage"]
