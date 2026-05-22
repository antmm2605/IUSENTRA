"""Motore contestuale di conformità normativa per Template Atti.

Il controllo non è una label grafica: risolve modello, contesto, profilo
normativo, fonti, riferimenti applicabili, layout, timbro e gate di
generazione prima di autorizzare una bozza finale.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pct.legal_layout_profiles import ActLayoutProfile, StudioStampPlacement, get_layout_profile


RULES_DIR = Path(__file__).with_name("legal_rules")
RULESET_VERSION = "2026.05.20.1"
VERIFIED_STATUSES = {"verified_online", "verified_snapshot"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: Any) -> str:
    return _clean(value).casefold()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, "", {}):
        return []
    return [value]


def _load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, "", [], {}):
            return payload.get(key)
    return ""


@dataclass(slots=True)
class NormativeSource:
    id: str
    title: str
    source_type: str
    official_url: str
    source_priority: str
    last_verified_at: str
    verification_status: str
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NormativeReference:
    id: str
    title: str
    source_id: str
    source_title: str
    article: str
    paragraph: str
    official_url: str
    reason_for_application: str
    applies_to: list[str] = field(default_factory=list)
    applies_when: dict[str, Any] = field(default_factory=dict)
    verification_status: str = "pending_live_verification"
    last_verified_at: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ComplianceCheck:
    id: str
    title: str
    state: str
    severity: str
    message: str
    required_fields: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)
    required_sections: list[str] = field(default_factory=list)
    reason: str = ""
    suggested_action: str = ""
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MissingField:
    name: str
    label: str
    severity: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MissingDocument:
    title: str
    severity: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AppliedRule:
    id: str
    title: str
    severity: str
    reason: str
    suggested_action: str
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MissingNormativeData:
    missing_fields: list[MissingField] = field(default_factory=list)
    missing_documents: list[MissingDocument] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_fields": [item.to_dict() for item in self.missing_fields],
            "missing_documents": [item.to_dict() for item in self.missing_documents],
            "missing_sections": list(self.missing_sections),
        }


@dataclass(slots=True)
class ReliabilityScore:
    value: float
    label: str
    caps_applied: list[str] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LayoutComplianceResult:
    ok: bool
    layout_profile_id: str
    title: str
    reason: str
    margin_top_mm: int
    margin_left_mm: int
    margin_right_mm: int
    margin_bottom_mm: int
    text_align: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageStampComplianceResult:
    ok: bool
    position: str
    repeat_on_each_page: bool
    align_within_box: str
    line_align: str
    reason: str
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateNormativeProfile:
    model_code: str
    template_name: str
    area: str
    matter: str
    rito: str
    fase: str
    grado: str
    channel: str
    office_type: str
    layout_profile_id: str
    source_ids: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)
    required_sections: list[str] = field(default_factory=list)
    warning_fields: list[str] = field(default_factory=list)
    stamp_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CartabiaComplianceResult:
    model_code: str
    template_name: str
    area: str
    matter: str
    rito: str
    fase: str
    grado: str
    channel: str
    office_type: str
    overall_state: str
    can_generate_working_draft: bool
    can_generate_final_draft: bool
    can_open_editor: bool
    normative_references: list[NormativeReference] = field(default_factory=list)
    contextual_rules_applied: list[AppliedRule] = field(default_factory=list)
    checks: list[ComplianceCheck] = field(default_factory=list)
    missing_fields: list[MissingField] = field(default_factory=list)
    missing_documents: list[MissingDocument] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    source_pack: list[NormativeSource] = field(default_factory=list)
    reliability_score: ReliabilityScore = field(default_factory=lambda: ReliabilityScore(0.0, "non verificato"))
    reasoned_compliance_explanation: str = ""
    next_actions: list[str] = field(default_factory=list)
    ruleset_version: str = RULESET_VERSION
    verified_at: str = ""
    template_profile: TemplateNormativeProfile | None = None
    layout_compliance: LayoutComplianceResult | None = None
    page_stamp_compliance: PageStampComplianceResult | None = None
    missing_normative_data: MissingNormativeData = field(default_factory=MissingNormativeData)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_code": self.model_code,
            "template_name": self.template_name,
            "area": self.area,
            "matter": self.matter,
            "rito": self.rito,
            "fase": self.fase,
            "grado": self.grado,
            "channel": self.channel,
            "office_type": self.office_type,
            "overall_state": self.overall_state,
            "state": self.overall_state,
            "can_generate_working_draft": self.can_generate_working_draft,
            "can_generate_final_draft": self.can_generate_final_draft,
            "can_open_editor": self.can_open_editor,
            "normative_references": [item.to_dict() for item in self.normative_references],
            "contextual_rules_applied": [item.to_dict() for item in self.contextual_rules_applied],
            "checks": [item.to_dict() for item in self.checks],
            "missing_fields": [item.to_dict() for item in self.missing_fields],
            "missing_documents": [item.to_dict() for item in self.missing_documents],
            "risk_flags": list(self.risk_flags),
            "source_pack": [item.to_dict() for item in self.source_pack],
            "reliability_score": self.reliability_score.to_dict(),
            "reasoned_compliance_explanation": self.reasoned_compliance_explanation,
            "next_actions": list(self.next_actions),
            "ruleset_version": self.ruleset_version,
            "verified_at": self.verified_at,
            "template_profile": self.template_profile.to_dict() if self.template_profile else {},
            "layout_compliance": self.layout_compliance.to_dict() if self.layout_compliance else {},
            "page_stamp_compliance": self.page_stamp_compliance.to_dict() if self.page_stamp_compliance else {},
            "missing_normative_data": self.missing_normative_data.to_dict(),
        }


class CartabiaContextualComplianceEngine:
    def __init__(self, *, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or RULES_DIR
        self._source_registry = self._load_sources()
        self._profiles = self._load_profiles()
        self._rules = self._load_rules()

    def analyze_template_context(
        self,
        *,
        model_code: str,
        payload: dict[str, Any] | None = None,
        template_name: str = "",
        fascicolo: Any = None,
        cliente: Any = None,
        documents: list[Any] | None = None,
        studio_timbro_payload: dict[str, Any] | None = None,
        strict_payload: bool = True,
    ) -> CartabiaComplianceResult:
        payload = dict(payload or {})
        code = _clean(model_code).upper()
        profile = self._profile_for(code)
        if template_name:
            profile.template_name = template_name
        layout_profile = get_layout_profile(profile.layout_profile_id)
        sources = self._sources_for(profile.source_ids)
        matching_rules = [rule for rule in self._rules if self._rule_applies(rule, code, profile)]
        missing_fields: list[MissingField] = []
        missing_documents: list[MissingDocument] = []
        missing_sections: list[str] = []
        checks: list[ComplianceCheck] = []
        applied: list[AppliedRule] = []
        references: list[NormativeReference] = []

        profile_missing = self._missing_fields(profile.required_fields, payload, severity="block", reason="Campo richiesto dal profilo del template.")
        missing_fields.extend(profile_missing)
        missing_documents.extend(self._missing_documents(profile.required_documents, payload, documents, severity="block", reason="Documento richiesto dal profilo del template."))
        missing_sections.extend(profile.required_sections)

        for rule in matching_rules:
            severity = _clean(rule.get("severity")) or "warning"
            source_ids = [str(item) for item in rule.get("source_ids") or []]
            applied.append(
                AppliedRule(
                    id=_clean(rule.get("id")),
                    title=_clean(rule.get("title")),
                    severity=severity,
                    reason=_clean(rule.get("reason")),
                    suggested_action=_clean(rule.get("suggested_action")),
                    source_ids=source_ids,
                )
            )
            rule_missing_fields = self._missing_fields(
                rule.get("required_fields") or [],
                payload,
                severity=severity,
                reason=_clean(rule.get("reason")) or "Campo richiesto dalla regola applicabile.",
            )
            warning_missing_fields = self._missing_fields(
                rule.get("warning_fields") or [],
                payload,
                severity="warning",
                reason=_clean(rule.get("reason")) or "Campo da confermare nel contesto dell'atto.",
            )
            rule_missing_docs = self._missing_documents(
                rule.get("required_documents") or [],
                payload,
                documents,
                severity=severity,
                reason=_clean(rule.get("reason")) or "Documento richiesto dalla regola applicabile.",
            )
            missing_fields.extend(rule_missing_fields)
            missing_fields.extend(warning_missing_fields)
            missing_documents.extend(rule_missing_docs)
            for section in rule.get("required_sections") or []:
                if _clean(section):
                    missing_sections.append(_clean(section))
            state = "ok"
            message = "Controllo superato."
            if any(item.severity == "block" for item in rule_missing_fields + rule_missing_docs):
                state = "block"
                message = _clean(rule.get("suggested_action")) or "Completa i dati bloccanti."
            elif warning_missing_fields or any(item.severity == "warning" for item in rule_missing_docs):
                state = "warning"
                message = _clean(rule.get("suggested_action")) or "Conferma il controllo prima della bozza di lavoro."
            checks.append(
                ComplianceCheck(
                    id=_clean(rule.get("id")),
                    title=_clean(rule.get("title")),
                    state=state,
                    severity=severity,
                    message=message,
                    required_fields=[_clean(item) for item in rule.get("required_fields") or [] if _clean(item)],
                    required_documents=[_clean(item) for item in rule.get("required_documents") or [] if _clean(item)],
                    required_sections=[_clean(item) for item in rule.get("required_sections") or [] if _clean(item)],
                    reason=_clean(rule.get("reason")),
                    suggested_action=_clean(rule.get("suggested_action")),
                    source_ids=source_ids,
                )
            )
            references.extend(self._references_for_rule(rule, profile))

        layout_result = self._layout_result(layout_profile, profile)
        stamp_result = self._stamp_result(layout_profile, studio_timbro_payload, profile.stamp_required)
        risk_flags: list[str] = []
        source_statuses = {source.verification_status for source in sources}
        unverified_sources = [source for source in sources if source.verification_status not in VERIFIED_STATUSES]
        if unverified_sources:
            risk_flags.append("fonti_primarie_non_verificate_online")
            checks.append(
                ComplianceCheck(
                    id="SOURCES_VERIFICATION",
                    title="Verifica fonti ufficiali",
                    state="warning",
                    severity="warning",
                    message="Una o più fonti ufficiali richiedono verifica live prima della conformità piena.",
                    reason="Le fonti non verificate non vengono usate come base per dichiarare conformità finale.",
                    suggested_action="Esegui la verifica fonti o conferma una bozza di lavoro da revisionare.",
                    source_ids=[source.id for source in unverified_sources],
                )
            )
        if not layout_result.ok:
            risk_flags.append("layout_profile_mancante_o_non_conforme")
        if not stamp_result.ok:
            risk_flags.append("timbro_non_conforme_su_ogni_pagina")
        if not _value(payload, "case_id", "id_fascicolo") and not fascicolo:
            risk_flags.append("fascicolo_non_collegato")
        if not _value(payload, "client_or_sender", "plaintiff", "claimant", "sender", "client", "id_cliente") and not cliente:
            risk_flags.append("cliente_non_collegato")

        missing_fields = self._dedupe_missing_fields(missing_fields)
        missing_documents = self._dedupe_missing_documents(missing_documents)
        has_block = (
            any(item.severity == "block" for item in missing_fields)
            or any(item.severity == "block" for item in missing_documents)
            or any(check.state == "block" for check in checks)
            or not layout_result.ok
            or not stamp_result.ok
        )
        has_warning = (
            any(item.severity == "warning" for item in missing_fields)
            or any(item.severity == "warning" for item in missing_documents)
            or any(check.state == "warning" for check in checks)
            or bool(unverified_sources)
            or bool({"fascicolo_non_collegato", "cliente_non_collegato"}.intersection(risk_flags))
        )
        if not strict_payload:
            has_block = has_block and any(check.state == "block" and check.id.startswith("SOURCES") for check in checks)
        state = "block" if has_block else "warning" if has_warning else "ok"
        reliability = self._reliability(
            state=state,
            missing_fields=missing_fields,
            missing_documents=missing_documents,
            source_statuses=source_statuses,
            layout_ok=layout_result.ok,
            stamp_ok=stamp_result.ok,
            risk_flags=risk_flags,
        )
        next_actions = self._next_actions(state, missing_fields, missing_documents, unverified_sources, layout_result, stamp_result)
        explanation = self._explanation(profile, state, reliability, sources, references)
        return CartabiaComplianceResult(
            model_code=code,
            template_name=profile.template_name,
            area=profile.area,
            matter=profile.matter,
            rito=profile.rito,
            fase=profile.fase,
            grado=profile.grado,
            channel=profile.channel,
            office_type=profile.office_type,
            overall_state=state,
            can_generate_working_draft=state in {"ok", "warning"},
            can_generate_final_draft=state == "ok",
            can_open_editor=state == "ok",
            normative_references=self._dedupe_references(references),
            contextual_rules_applied=applied,
            checks=checks,
            missing_fields=missing_fields,
            missing_documents=missing_documents,
            risk_flags=risk_flags,
            source_pack=sources,
            reliability_score=reliability,
            reasoned_compliance_explanation=explanation,
            next_actions=next_actions,
            ruleset_version=RULESET_VERSION,
            verified_at=_now(),
            template_profile=profile,
            layout_compliance=layout_result,
            page_stamp_compliance=stamp_result,
            missing_normative_data=MissingNormativeData(missing_fields, missing_documents, sorted(set(missing_sections))),
        )

    def _load_sources(self) -> dict[str, NormativeSource]:
        payload = _load_json_yaml(self.rules_dir / "source_registry.yml")
        result: dict[str, NormativeSource] = {}
        for row in payload.get("sources") or []:
            if not isinstance(row, dict):
                continue
            source = NormativeSource(
                id=_clean(row.get("id")),
                title=_clean(row.get("title")),
                source_type=_clean(row.get("source_type")),
                official_url=_clean(row.get("official_url")),
                source_priority=_clean(row.get("source_priority")) or "primary",
                last_verified_at=_clean(row.get("last_verified_at")),
                verification_status=_clean(row.get("verification_status")) or "pending_live_verification",
                source_hash=_clean(row.get("source_hash")),
            )
            if source.id:
                result[source.id] = source
        return result

    def _load_profiles(self) -> tuple[list[TemplateNormativeProfile], TemplateNormativeProfile]:
        payload = _load_json_yaml(self.rules_dir / "template_profiles.yml")
        profiles: list[TemplateNormativeProfile] = []
        for row in payload.get("profiles") or []:
            if isinstance(row, dict):
                profiles.append(self._profile_from_row(row))
        default = self._profile_from_row(payload.get("default_profile") if isinstance(payload.get("default_profile"), dict) else {})
        return profiles, default

    def _profile_from_row(self, row: dict[str, Any]) -> TemplateNormativeProfile:
        return TemplateNormativeProfile(
            model_code=_clean(row.get("model_code")) or "*",
            template_name=_clean(row.get("template_name")) or _clean(row.get("model_code")) or "Template atto",
            area=_clean(row.get("area")) or "GENERALE",
            matter=_clean(row.get("matter")),
            rito=_clean(row.get("rito")),
            fase=_clean(row.get("fase")),
            grado=_clean(row.get("grado")),
            channel=_clean(row.get("channel")),
            office_type=_clean(row.get("office_type")),
            layout_profile_id=_clean(row.get("layout_profile_id")) or "generic_internal_draft_layout",
            source_ids=[_clean(item) for item in row.get("source_ids") or [] if _clean(item)],
            required_fields=[_clean(item) for item in row.get("required_fields") or [] if _clean(item)],
            required_documents=[_clean(item) for item in row.get("required_documents") or [] if _clean(item)],
            required_sections=[_clean(item) for item in row.get("required_sections") or [] if _clean(item)],
            warning_fields=[_clean(item) for item in row.get("warning_fields") or [] if _clean(item)],
            stamp_required=bool(row.get("stamp_required", True)),
        )

    def _load_rules(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for filename in ("cartabia_civile.yml", "cartabia_penale.yml", "pct_rules.yml", "pat_rules.yml", "ptt_rules.yml", "pec_rules.yml"):
            payload = _load_json_yaml(self.rules_dir / filename)
            for rule in payload.get("rules") or []:
                if isinstance(rule, dict) and _clean(rule.get("id")):
                    rules.append(rule)
        return rules

    def _profile_for(self, model_code: str) -> TemplateNormativeProfile:
        profiles, default = self._profiles
        for profile in profiles:
            if profile.model_code == model_code:
                return self._profile_from_row(profile.to_dict())
        for profile in profiles:
            if profile.model_code.endswith("*") and model_code.startswith(profile.model_code[:-1]):
                clone = self._profile_from_row(profile.to_dict())
                clone.model_code = model_code
                return clone
        clone = self._profile_from_row(default.to_dict())
        clone.model_code = model_code
        try:
            from pct.compilatore_atti import get_modello

            model = get_modello(model_code) or {}
            clone.template_name = _clean(model.get("name")) or clone.template_name
            clone.area = _clean(model.get("area")) or clone.area
        except Exception:
            pass
        return clone

    def _sources_for(self, ids: list[str]) -> list[NormativeSource]:
        return [self._source_registry[source_id] for source_id in ids if source_id in self._source_registry]

    def _rule_applies(self, rule: dict[str, Any], model_code: str, profile: TemplateNormativeProfile) -> bool:
        applies = [_clean(item).upper() for item in rule.get("applies_to") or [] if _clean(item)]
        if applies:
            matched = False
            for item in applies:
                if item == model_code or (item.endswith("*") and model_code.startswith(item[:-1])):
                    matched = True
                    break
            if not matched:
                return False
        when = rule.get("applies_when") if isinstance(rule.get("applies_when"), dict) else {}
        for key, expected in when.items():
            actual = _norm(getattr(profile, key, ""))
            if expected and _norm(expected) and _norm(expected) not in actual and actual not in _norm(expected):
                return False
        return True

    def _missing_fields(self, fields: list[Any], payload: dict[str, Any], *, severity: str, reason: str) -> list[MissingField]:
        rows: list[MissingField] = []
        labels = self._field_labels()
        for field_name in [_clean(item) for item in fields if _clean(item)]:
            if _value(payload, field_name):
                continue
            rows.append(MissingField(name=field_name, label=labels.get(field_name, field_name), severity=severity, reason=reason))
        return rows

    def _field_labels(self) -> dict[str, str]:
        try:
            from pct.compilatore_atti import FIELD_CATALOG_RAW

            return {key: _clean(value.get("label")) or key for key, value in FIELD_CATALOG_RAW.items() if isinstance(value, dict)}
        except Exception:
            return {}

    def _has_document(self, title: str, payload: dict[str, Any], documents: list[Any] | None) -> bool:
        document_values = []
        for key in ("attachments_list", "documents_offered", "supporting_documents", "written_evidence", "documents_list_detailed"):
            value = payload.get(key)
            if isinstance(value, str) and _clean(value):
                document_values.append(value)
            elif isinstance(value, list):
                document_values.extend(str(item) for item in value if _clean(item))
        if document_values:
            return True
        needle = _norm(title)
        for row in documents or []:
            if isinstance(row, dict):
                haystack = _norm(" ".join(str(row.get(key, "")) for key in ("nome", "title", "titolo", "filename", "tipo")))
            else:
                haystack = _norm(" ".join(str(getattr(row, key, "")) for key in ("nome", "title", "titolo", "filename", "tipo")))
            if needle and needle in haystack:
                return True
        return False

    def _missing_documents(
        self,
        documents_required: list[Any],
        payload: dict[str, Any],
        documents: list[Any] | None,
        *,
        severity: str,
        reason: str,
    ) -> list[MissingDocument]:
        rows: list[MissingDocument] = []
        for title in [_clean(item) for item in documents_required if _clean(item)]:
            if self._has_document(title, payload, documents):
                continue
            rows.append(MissingDocument(title=title, severity=severity, reason=reason))
        return rows

    def _layout_result(self, layout_profile: ActLayoutProfile | None, profile: TemplateNormativeProfile) -> LayoutComplianceResult:
        if not layout_profile:
            return LayoutComplianceResult(False, "", "", "Profilo layout mancante.", 0, 0, 0, 0, "")
        ok = bool(layout_profile.id and layout_profile.stamp_policy_ok)
        return LayoutComplianceResult(
            ok=ok,
            layout_profile_id=layout_profile.id,
            title=layout_profile.title,
            reason=layout_profile.reason,
            margin_top_mm=layout_profile.margin_top_mm,
            margin_left_mm=layout_profile.margin_left_mm,
            margin_right_mm=layout_profile.margin_right_mm,
            margin_bottom_mm=layout_profile.margin_bottom_mm,
            text_align=layout_profile.text_align,
        )

    def _stamp_result(
        self,
        layout_profile: ActLayoutProfile | None,
        stamp_payload: dict[str, Any] | None,
        stamp_required: bool = True,
    ) -> PageStampComplianceResult:
        policy = StudioStampPlacement().to_dict()
        ok = bool(layout_profile and layout_profile.stamp_policy_ok)
        reason = "Timbro configurato in alto a sinistra su ogni pagina."
        if stamp_required and not stamp_payload:
            ok = False
            reason = "Timbro studio richiesto ma non presente nel contesto di generazione."
        if stamp_payload:
            try:
                from pct.studio_timbro import StudioTimbro

                stamp = StudioTimbro.from_payload(stamp_payload)
                policy = stamp.to_stamp_placement()
                ok = bool(
                    stamp.enabled
                    and policy.get("position") == "top_left"
                    and policy.get("repeat_on_each_page") is True
                    and layout_profile
                    and layout_profile.stamp_policy_ok
                )
                if not stamp.enabled:
                    reason = "Timbro studio non configurato o privo di righe utili."
            except Exception:
                ok = False
                reason = "Timbro studio non leggibile."
        return PageStampComplianceResult(
            ok=ok,
            position=_clean(policy.get("position")) or "top_left",
            repeat_on_each_page=bool(policy.get("repeat_on_each_page")),
            align_within_box=_clean(policy.get("align_within_box")) or "center",
            line_align=_clean(policy.get("line_align")) or "left",
            reason=reason,
            policy=policy,
        )

    def _references_for_rule(self, rule: dict[str, Any], profile: TemplateNormativeProfile) -> list[NormativeReference]:
        rows: list[NormativeReference] = []
        for source_id in rule.get("source_ids") or []:
            source = self._source_registry.get(_clean(source_id))
            if not source:
                continue
            rows.append(
                NormativeReference(
                    id=f"{_clean(rule.get('id'))}:{source.id}",
                    title=_clean(rule.get("title")),
                    source_id=source.id,
                    source_title=source.title,
                    article=_clean(rule.get("article")),
                    paragraph=_clean(rule.get("paragraph")),
                    official_url=source.official_url,
                    reason_for_application=_clean(rule.get("reason")),
                    applies_to=[_clean(item) for item in rule.get("applies_to") or [] if _clean(item)],
                    applies_when=dict(rule.get("applies_when") or {}),
                    verification_status=source.verification_status,
                    last_verified_at=source.last_verified_at,
                    confidence=0.92 if source.verification_status in VERIFIED_STATUSES else 0.68,
                )
            )
        return rows

    def _dedupe_missing_fields(self, rows: list[MissingField]) -> list[MissingField]:
        result: dict[str, MissingField] = {}
        for row in rows:
            existing = result.get(row.name)
            if not existing or existing.severity != "block" and row.severity == "block":
                result[row.name] = row
        return list(result.values())

    def _dedupe_missing_documents(self, rows: list[MissingDocument]) -> list[MissingDocument]:
        result: dict[str, MissingDocument] = {}
        for row in rows:
            key = _norm(row.title)
            existing = result.get(key)
            if not existing or existing.severity != "block" and row.severity == "block":
                result[key] = row
        return list(result.values())

    def _dedupe_references(self, rows: list[NormativeReference]) -> list[NormativeReference]:
        result: dict[str, NormativeReference] = {}
        for row in rows:
            key = f"{row.title}:{row.source_id}:{row.article}"
            result.setdefault(key, row)
        return list(result.values())

    def _reliability(
        self,
        *,
        state: str,
        missing_fields: list[MissingField],
        missing_documents: list[MissingDocument],
        source_statuses: set[str],
        layout_ok: bool,
        stamp_ok: bool,
        risk_flags: list[str],
    ) -> ReliabilityScore:
        value = 0.94
        factors: list[str] = []
        caps: list[str] = []
        value -= min(0.22, len(missing_fields) * 0.025)
        value -= min(0.14, len(missing_documents) * 0.035)
        if any(status not in VERIFIED_STATUSES for status in source_statuses):
            value -= 0.08
            caps.append("fonti non verificate: massimo 0.79")
            value = min(value, 0.79)
        if not layout_ok or not stamp_ok:
            value -= 0.12
            caps.append("layout o timbro mancante: massimo 0.69")
            value = min(value, 0.69)
        if "cliente_non_collegato" in risk_flags or "fascicolo_non_collegato" in risk_flags:
            caps.append("cliente o fascicolo non collegato: massimo 0.59")
            value = min(value, 0.59)
        if state == "block":
            caps.append("gate bloccante: massimo 0.49")
            value = min(value, 0.49)
        if missing_fields:
            factors.append(f"{len(missing_fields)} campi da completare")
        if missing_documents:
            factors.append(f"{len(missing_documents)} documenti da collegare")
        if not factors:
            factors.append("profilo, fonti, layout e timbro coerenti")
        value = max(0.0, min(0.99, round(value, 2)))
        label = "alta" if value >= 0.86 else "media" if value >= 0.65 else "bassa"
        return ReliabilityScore(value=value, label=label, caps_applied=caps, factors=factors)

    def _next_actions(
        self,
        state: str,
        missing_fields: list[MissingField],
        missing_documents: list[MissingDocument],
        unverified_sources: list[NormativeSource],
        layout: LayoutComplianceResult,
        stamp: PageStampComplianceResult,
    ) -> list[str]:
        actions: list[str] = []
        if state == "ok":
            actions.append("Apri l'editor professionale e conserva audit, fonti e profilo layout.")
        if missing_fields:
            labels = ", ".join(item.label for item in missing_fields[:5])
            actions.append(f"Completa i campi: {labels}.")
        if missing_documents:
            labels = ", ".join(item.title for item in missing_documents[:4])
            actions.append(f"Collega i documenti: {labels}.")
        if unverified_sources:
            actions.append("Verifica le fonti ufficiali prima di dichiarare conforme la bozza finale.")
        if not layout.ok:
            actions.append("Associa un profilo layout applicabile al modello.")
        if not stamp.ok:
            actions.append("Configura il timbro studio in alto a sinistra su ogni pagina.")
        if state == "warning":
            actions.append("Per una bozza di lavoro serve conferma esplicita dell'avvocato.")
        if state == "block":
            actions.append("La bozza finale è bloccata finché non sono risolti i punti indicati.")
        return actions

    def _explanation(
        self,
        profile: TemplateNormativeProfile,
        state: str,
        reliability: ReliabilityScore,
        sources: list[NormativeSource],
        references: list[NormativeReference],
    ) -> str:
        source_titles = ", ".join(source.title for source in sources[:4]) or "nessuna fonte primaria applicabile"
        ref_count = len(self._dedupe_references(references))
        if state == "ok":
            prefix = "Il modello può produrre una bozza finale"
        elif state == "warning":
            prefix = "Il modello può produrre solo una bozza di lavoro confermata"
        else:
            prefix = "Il modello non può produrre la bozza finale"
        return (
            f"{prefix}: profilo {profile.rito} {profile.fase}, fonti {source_titles}, "
            f"{ref_count} riferimenti applicabili e affidabilità {reliability.value:.2f}."
        )


def analyze_template_compliance(
    model_code: str,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> CartabiaComplianceResult:
    if "studio_timbro_payload" not in kwargs and isinstance(payload, dict):
        kwargs["studio_timbro_payload"] = payload.get("_studio_timbro")
    return CartabiaContextualComplianceEngine().analyze_template_context(model_code=model_code, payload=payload, **kwargs)


def enforce_generation_gate(
    compliance: CartabiaComplianceResult,
    *,
    requested_draft: str = "final_draft",
    confirmed_warning: bool = False,
) -> tuple[bool, str, str]:
    requested = _clean(requested_draft) or "final_draft"
    if compliance.overall_state == "block" and requested == "working_draft" and confirmed_warning:
        return True, "working_draft", "Bozza di lavoro autorizzata: i controlli verranno ripresi prima del deposito o della conferma finale."
    if compliance.overall_state == "block":
        return False, "blocked", "La bozza finale è bloccata dai controlli applicabili."
    if requested == "final_draft" and not compliance.can_generate_final_draft:
        return False, "warning_requires_confirmation", "La bozza finale richiede controlli ulteriori; puoi creare solo una bozza di lavoro confermata."
    if compliance.overall_state == "warning" and not confirmed_warning:
        return False, "warning_requires_confirmation", "Conferma esplicitamente la bozza di lavoro da revisionare."
    if requested == "working_draft" and compliance.can_generate_working_draft:
        return True, "working_draft", "Bozza di lavoro autorizzata con revisione obbligatoria."
    if requested == "final_draft" and compliance.can_generate_final_draft:
        return True, "final_draft", "Bozza finale autorizzata."
    return False, "blocked", "Gate di generazione non superato."


def build_template_generation_audit(
    *,
    event_type: str,
    model_code: str,
    compliance: CartabiaComplianceResult,
    user_id: str = "",
    tenant_id: str = "",
    fascicolo_id: str = "",
    cliente_id: str = "",
    output_format: str = "html",
    document_id: str = "",
    final_state: str = "blocked",
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "model_code": model_code,
        "template_version": compliance.ruleset_version,
        "layout_profile_id": (compliance.layout_compliance.layout_profile_id if compliance.layout_compliance else ""),
        "stamp_policy": (compliance.page_stamp_compliance.policy if compliance.page_stamp_compliance else {}),
        "ruleset_version": compliance.ruleset_version,
        "compliance_result": compliance.to_dict(),
        "normative_references": [item.to_dict() for item in compliance.normative_references],
        "source_pack": [item.to_dict() for item in compliance.source_pack],
        "verification_status": [item.verification_status for item in compliance.source_pack],
        "reliability_score": compliance.reliability_score.to_dict(),
        "missing_fields": [item.to_dict() for item in compliance.missing_fields],
        "missing_documents": [item.to_dict() for item in compliance.missing_documents],
        "user_id": user_id,
        "tenant_id": tenant_id,
        "fascicolo_id": fascicolo_id,
        "cliente_id": cliente_id,
        "timestamp": _now(),
        "output_format": output_format,
        "document_id": document_id,
        "final_state": final_state,
    }
