"""Profilazione deterministica delle richieste per Lex."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .source_policy import infer_area_with_confidence


@dataclass(frozen=True, slots=True)
class LexRequestProfile:
    intent: str
    intent_label: str
    area: str
    area_confidence: float
    risk_level: str
    source_mode: str
    response_schema: tuple[str, ...]
    needs_internal_retrieval: bool
    needs_external_validation: bool
    drafting_mode: bool
    reasoning: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_INTENT_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "intent": "preventivo_guidato",
        "label": "preventivo guidato",
        "patterns": (
            r"\bpreventiv",
            r"\bvorrei fare un preventivo\b",
            r"\bcrea(?:re)? un preventivo\b",
            r"\bpreventivo professionale\b",
        ),
        "schema": ("Obiettivo", "Dati necessari", "Percorso consigliato", "Prossima azione", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "tariffario_economico",
        "label": "tariffario e compensi",
        "patterns": (r"\btariffario\b", r"\bcompenso\b", r"\bonorario\b", r"\bscaglione\b", r"\bd\.m\.?\s*55\b"),
        "schema": ("Sintesi", "Dati economici", "Calcolo o percorso", "Prossima azione", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "fatturazione_economica",
        "label": "fatturazione, parcella o pagamento",
        "patterns": (r"\bfattura\b", r"\bfatture\b", r"\bparcella\b", r"\bparcelle\b", r"\bpagament", r"\bincasso\b"),
        "schema": ("Sintesi", "Stato economico", "Verifiche residue", "Prossima azione", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "bozza_atto",
        "label": "bozza atto o memoria",
        "patterns": (r"\bbozza\b", r"\bredig", r"\bmemoria\b", r"\bricorso\b", r"\bcomparsa\b", r"\bcitazione\b", r"\batto\b"),
        "schema": ("Obiettivo", "Bozza", "Dati da personalizzare", "Verifiche necessarie", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": True,
    },
    {
        "intent": "bozza_lettera",
        "label": "bozza lettera, diffida o PEC",
        "patterns": (r"\bdiffida\b", r"\bpec\b", r"\blettera\b", r"\bsollecito\b", r"\bmessa in mora\b"),
        "schema": ("Obiettivo", "Bozza", "Punti da adattare", "Verifiche necessarie", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": True,
    },
    {
        "intent": "sintesi_fascicolo",
        "label": "sintesi fascicolo",
        "patterns": (r"\briassum", r"\bsintesi fascicolo\b", r"\bstato fascicolo\b", r"\bquadro fascicolo\b"),
        "schema": ("Sintesi", "Eventi rilevanti", "Criticita", "Prossime azioni", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": False,
        "drafting": False,
    },
    {
        "intent": "sintesi_documento",
        "label": "sintesi documento",
        "patterns": (r"\briassum", r"\bsintesi documento\b", r"\bestrai\b", r"\banalizza il pdf\b", r"\banalizza documento\b"),
        "schema": ("Sintesi", "Punti chiave", "Rischi o lacune", "Prossime azioni", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": False,
        "drafting": False,
    },
    {
        "intent": "checklist_operativa",
        "label": "checklist operativa",
        "patterns": (r"\bchecklist\b", r"\bcosa devo fare\b", r"\bpassi\b", r"\bcontrolli\b", r"\bdeposito\b"),
        "schema": ("Obiettivo", "Checklist", "Errori da evitare", "Prossima azione", "Fonti e affidabilita"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "normativa",
        "label": "verifica normativa",
        "patterns": (r"\bnorma\b", r"\bnormativa\b", r"\blegge\b", r"\bdecreto\b", r"\barticolo\b", r"\bvigente\b", r"\baggiornat"),
        "schema": ("Sintesi", "Quadro normativo", "Applicazione pratica", "Limiti o eccezioni", "Fonti e affidabilita"),
        "risk": "high",
        "source_mode": "strict",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "giurisprudenza",
        "label": "ricerca giurisprudenziale",
        "patterns": (r"\bsentenza\b", r"\bsentenze\b", r"\bgiurisprudenza\b", r"\bmassima\b", r"\bpronuncia\b", r"\bcassazione\b", r"\btar\b"),
        "schema": ("Sintesi", "Orientamenti", "Applicazione pratica", "Contrasti o limiti", "Fonti e affidabilita"),
        "risk": "high",
        "source_mode": "strict",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "pratica_procedura",
        "label": "procedura pratica o operativa",
        "patterns": (r"\bprocedura\b", r"\bcome si fa\b", r"\bworkflow\b", r"\btelematic", r"\bpst\b", r"\bpdp\b", r"\bpat\b"),
        "schema": ("Sintesi", "Passaggi operativi", "Rischi o blocchi", "Prossima azione", "Fonti e affidabilita"),
        "risk": "high",
        "source_mode": "strict",
        "internal": True,
        "external": True,
        "drafting": False,
    },
    {
        "intent": "spiegazione_cliente",
        "label": "spiegazione per cliente",
        "patterns": (r"\bspiega al cliente\b", r"\bspiegazione semplice\b", r"\bin parole semplici\b", r"\bcome lo spiego\b"),
        "schema": ("Spiegazione semplice", "Conseguenze pratiche", "Cosa conviene fare", "Cosa verificare"),
        "risk": "medium",
        "source_mode": "balanced",
        "internal": True,
        "external": True,
        "drafting": False,
    },
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _score_intent(question: str, patterns: tuple[str, ...]) -> int:
    haystack = _clean_spaces(question).lower()
    if not haystack:
        return 0
    return sum(1 for pattern in patterns if re.search(pattern, haystack))


def _default_profile(question: str) -> LexRequestProfile:
    inferred = infer_area_with_confidence(question) or {"area": "default", "confidence": 0.25}
    return LexRequestProfile(
        intent="domanda_generica",
        intent_label="domanda generica",
        area=str(inferred.get("area") or "default"),
        area_confidence=float(inferred.get("confidence") or 0.25),
        risk_level="medium",
        source_mode="balanced",
        response_schema=("Sintesi", "Punto centrale", "Prossima azione", "Fonti e affidabilita"),
        needs_internal_retrieval=True,
        needs_external_validation=False,
        drafting_mode=False,
        reasoning=("Richiesta non specializzata: Lex deve restare operativo e prudente.",),
    )


def classify_request(question: str, *, requested_mode: str = "") -> LexRequestProfile:
    clean_question = _clean_spaces(question)
    inferred = infer_area_with_confidence(clean_question) or {"area": "default", "confidence": 0.25}
    scored = []
    for item in _INTENT_CATALOG:
        score = _score_intent(clean_question, tuple(item["patterns"]))
        if score > 0:
            scored.append((score, item))
    if not scored:
        profile = _default_profile(clean_question)
    else:
        scored.sort(key=lambda row: row[0], reverse=True)
        matched = scored[0][1]
        risk_level = matched["risk"]
        source_mode = matched["source_mode"]
        requested = _clean_spaces(requested_mode).lower()
        if requested in {"strict", "balanced", "broad"}:
            source_mode = requested
        elif requested in {"draft", "drafting", "bozza"}:
            source_mode = "broad"
        reasoning = [
            f"Intento rilevato: {matched['label']}.",
            f"Area giuridica prevalente: {inferred.get('area') or 'default'}.",
        ]
        if risk_level == "high":
            reasoning.append("Richiesta ad alto impatto: servono fonti forti e controllo dei limiti.")
        if matched["drafting"]:
            reasoning.append("Modalita drafting: il testo va prodotto ma sempre con punti da verificare.")
        profile = LexRequestProfile(
            intent=matched["intent"],
            intent_label=matched["label"],
            area=str(inferred.get("area") or "default"),
            area_confidence=float(inferred.get("confidence") or 0.25),
            risk_level=risk_level,
            source_mode=source_mode,
            response_schema=tuple(matched["schema"]),
            needs_internal_retrieval=bool(matched["internal"]),
            needs_external_validation=bool(matched["external"]),
            drafting_mode=bool(matched["drafting"]),
            reasoning=tuple(reasoning),
        )

    if any(token in clean_question.lower() for token in ("parere", "valuta i rischi", "e' lecito", "si puo fare", "possiamo fare")):
        profile = LexRequestProfile(
            intent=profile.intent,
            intent_label=profile.intent_label,
            area=profile.area,
            area_confidence=profile.area_confidence,
            risk_level="high",
            source_mode="strict",
            response_schema=profile.response_schema,
            needs_internal_retrieval=profile.needs_internal_retrieval,
            needs_external_validation=True,
            drafting_mode=profile.drafting_mode,
            reasoning=tuple([*profile.reasoning, "Richiesta assimilabile a parere: Lex deve alzare la prudenza."]),
        )
    return profile


def build_request_profile_prompt(profile: LexRequestProfile) -> str:
    lines = [
        f"Profilo richiesta: {profile.intent_label}.",
        f"Area prevalente: {profile.area} (confidenza {profile.area_confidence:.2f}).",
        f"Livello di rischio: {profile.risk_level}.",
        f"Modalita fonti: {profile.source_mode}.",
        "Schema risposta richiesto: " + "; ".join(profile.response_schema) + ".",
        "Non scrivere mai testo meta come 'ecco la risposta', 'simulazione', 'motivazione', 'risposta:' o spiegazioni su come risponderai.",
    ]
    if profile.needs_internal_retrieval:
        lines.append("Usa prima il contesto interno di studio e del fascicolo.")
    if profile.needs_external_validation:
        lines.append("Se il contesto interno non basta, integra con fonti esterne coerenti con la policy.")
    if profile.drafting_mode:
        lines.append("La bozza deve restare modificabile e deve evidenziare i punti da verificare.")
    if profile.intent == "preventivo_guidato":
        lines.append(
            "Se l'utente vuole avviare un preventivo, parti subito dal percorso operativo corretto e chiedi solo i dati davvero necessari per chiuderlo."
        )
    if profile.intent in {"tariffario_economico", "fatturazione_economica"}:
        lines.append(
            "Per l'area economica distingui sempre tra preventivo, tariffario, parcella, fattura e pagamento senza mescolare i piani."
        )
    for item in profile.reasoning:
        lines.append(item)
    return "\n".join(lines).strip()


__all__ = [
    "LexRequestProfile",
    "build_request_profile_prompt",
    "classify_request",
]
