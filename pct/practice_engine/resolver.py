"""Resolver profilo pratica basato sulle fonti operative reali."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pct.legal_platform_catalog import infer_legal_operational_procedure
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, normalize_codice_oggetto_pst

from .models import PracticeProfile, ResolverResult
from .profiles import get_profile, list_profiles


def _value(source: Any, *names: str) -> str:
    for name in names:
        if isinstance(source, dict):
            raw = source.get(name)
        else:
            raw = getattr(source, name, None)
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def _alternative(profile: PracticeProfile, score: float, reason: str) -> dict[str, Any]:
    return {
        "code": profile.code,
        "name": profile.name,
        "channel": profile.channel,
        "registry": profile.registry,
        "confidence": round(score, 2),
        "reason": reason,
    }


def _first_codice_oggetto_pst(*sources: Any) -> tuple[str, dict[str, str] | None]:
    names = (
        "codice_oggetto_pst",
        "codiceOggettoPst",
        "oggetto",
        "title",
        "titolo",
        "tipo_procedimento",
    )
    for source in sources:
        for name in names:
            raw = _value(source, name)
            code = normalize_codice_oggetto_pst(raw)
            if code:
                return code, codice_oggetto_pst_entry(code)
    return "", None


def _source_type(*sources: Any) -> str:
    for source in sources:
        value = _value(source, "tipo", "type", "fascicolo_type", "tipo_fascicolo")
        if value:
            return value.upper()
    return ""


def _profile_from_codice_oggetto_pst(code: str, entry: dict[str, str] | None, *sources: Any) -> PracticeProfile | None:
    if not code or not entry:
        return None
    area = f"{entry.get('area_label', '')} {entry.get('area', '')}".lower()
    registri = str(entry.get("registri") or "").upper()
    fascicolo_type = _source_type(*sources)

    if ("lavoro" in area or "previdenza" in area or fascicolo_type == "LAVORO") and "SICID" in registri:
        return get_profile("PROC_LAV_RETRIB_001")

    return None


@dataclass
class PracticeResolver:
    manual_threshold: float = 0.75

    def resolve(
        self,
        *,
        preventivo: Any | None = None,
        conferimento: Any | None = None,
        fascicolo: Any | None = None,
        template: Any | None = None,
        manual_code: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ResolverResult:
        payload = payload or {}
        sources = [payload, preventivo, conferimento, fascicolo]

        # 1. codice procedura operativo esplicito
        for source in sources:
            code = _value(source, "procedura_operativa_codice", "procedure_code")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.98, "procedura_operativa_codice esplicito")

        # 2. id_pratica da preventivo/conferimento/fascicolo
        for source in sources:
            code = _value(source, "id_pratica", "practice_id")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.94, "id_pratica collegato al workflow commerciale")

        # 3. workflow operativo
        for source in sources:
            code = _value(source, "workflow_operativo_codice", "workflow_code")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.88, "workflow_operativo_codice")

        # 4. canale + registro
        for source in sources:
            channel = _value(source, "canale_operativo", "channel")
            registry = _value(source, "registro_operativo", "registry")
            if channel and registry:
                matches = [
                    profile
                    for profile in list_profiles()
                    if profile.channel.upper() == channel.upper() and profile.registry.upper() == registry.upper()
                ]
                if matches:
                    profile = matches[0]
                    alternatives = [_alternative(item, 0.74, "canale_operativo + registro_operativo") for item in matches[:5]]
                    return ResolverResult(profile, 0.74, "canale_operativo + registro_operativo", alternatives, True)

        # 5. template atto principale selezionato
        template_label = _value(template, "link_compilatore_code", "id", "titolo", "title") or _value(payload, "template_atto")
        if template_label:
            matches = [
                profile
                for profile in list_profiles()
                if template_label.upper() in {label.upper() for label in profile.template_labels}
                or template_label.lower() in profile.name.lower()
            ]
            if matches:
                return ResolverResult(matches[0], 0.72, "template atto principale selezionato", [_alternative(m, 0.72, "template") for m in matches[:5]], True)

        # 6. codice oggetto PST ufficiale gia' acquisito in apertura fascicolo
        pst_code, pst_entry = _first_codice_oggetto_pst(*sources)
        pst_profile = _profile_from_codice_oggetto_pst(pst_code, pst_entry, *sources)
        if pst_profile:
            return ResolverResult(
                pst_profile,
                0.91,
                f"codice oggetto PST ufficiale {pst_code}",
                [_alternative(pst_profile, 0.91, "codice oggetto PST")],
                False,
            )

        # 7. tipo procedimento e oggetto tramite inferenza catalogo esistente
        tipo = ""
        oggetto = ""
        area = ""
        for source in sources:
            tipo = tipo or _value(source, "tipo_procedimento")
            oggetto = oggetto or _value(source, "oggetto", "title", "titolo")
            area = area or _value(source, "area_pratica", "area")
        inferred = infer_legal_operational_procedure(
            procedure_code="",
            practice_id="",
            area_pratica=area,
            tipo_procedimento=tipo,
            oggetto=oggetto,
        )
        if inferred:
            profile = get_profile(getattr(inferred, "code", "")) or get_profile(getattr(inferred, "practice_id", ""))
            if profile:
                confidence = 0.66 if oggetto else 0.62
                return ResolverResult(
                    profile,
                    confidence,
                    "tipo_procedimento/oggetto risolti dal catalogo operativo",
                    [_alternative(profile, confidence, "inferenza catalogo")],
                    True,
                )

        # 8. scelta manuale utente, esplicita e auditabile
        if manual_code:
            profile = get_profile(manual_code)
            if profile:
                return ResolverResult(profile, 0.81, "scelta manuale utente auditabile", [], False)

        alternatives = [_alternative(profile, 0.3, "alternativa da confermare") for profile in list_profiles()[:5]]
        return ResolverResult(None, 0.0, "profilo non determinabile automaticamente", alternatives, True)


def resolve_practice_profile(**kwargs: Any) -> ResolverResult:
    return PracticeResolver().resolve(**kwargs)
