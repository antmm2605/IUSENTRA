"""Policy deterministica per separare voce LLM e verita' applicativa in Lex."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LexExecutionPolicy:
    mode: str
    summary_label: str
    llm_role: str
    truth_strategy: str
    requires_verified_legal_reference: bool
    requires_verified_normative_freshness: bool
    requires_verified_pdf: bool
    requires_internal_state_source: bool
    forbid_invented_missing_data: bool
    allow_web_fallback: bool
    prompt_block: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CASE_LAW_PATTERNS: tuple[str, ...] = (
    r"\bsentenza\b",
    r"\bsentenze\b",
    r"\bgiurisprudenza\b",
    r"\bmassima\b",
    r"\bpronuncia\b",
    r"\bpronunce\b",
    r"\bcassazione\b",
    r"\btribunale\b",
    r"\bcorte d['’]appello\b",
    r"\btar\b",
    r"\bconsiglio di stato\b",
)

_NORMATIVE_PATTERNS: tuple[str, ...] = (
    r"\bnorma\b",
    r"\bnormativa\b",
    r"\blegge\b",
    r"\bdecreto\b",
    r"\barticolo\b",
    r"\bregolamento\b",
    r"\bcircolare\b",
    r"\bvigen[tz]\b",
    r"\bvigente\b",
)

_PDF_PATTERNS: tuple[str, ...] = (
    r"\bpdf\b",
    r"\bscaric[a-z]*\b",
    r"\bdownload\b",
    r"\blink ufficiale\b",
    r"\btesto integrale\b",
)

_INTERNAL_STATE_PATTERNS: tuple[str, ...] = (
    r"\bstato\b",
    r"\battiv[oi]\b",
    r"\bin lavorazione\b",
    r"\bdeposit[oi]\b",
    r"\besito\b",
    r"\bcancelleria\b",
    r"\bfascicolo\b",
    r"\bprocedimento\b",
    r"\bpratica\b",
    r"\budienza\b",
    r"\bscadenza\b",
)

_RECENCY_PATTERNS: tuple[str, ...] = (
    r"\bultima\b",
    r"\bultime\b",
    r"\bultimo\b",
    r"\bultimi\b",
    r"\baggiornat[oaie]\b",
    r"\boggi\b",
    r"\brecent[ei]\b",
    r"\bvigente\b",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: str) -> str:
    return _clean_spaces(value).lower()


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    haystack = _normalize_text(text)
    if not haystack:
        return False
    return any(re.search(pattern, haystack) for pattern in patterns)


def _build_policy_prompt_lines(*, requires_verified_legal_reference: bool, requires_verified_normative_freshness: bool, requires_verified_pdf: bool, requires_internal_state_source: bool, allow_web_fallback: bool) -> list[str]:
    lines = [
        "Policy Lex: il modello serve per tono umano, scrittura, sintesi, follow-up, riformulazione e spiegazioni operative.",
        "Policy Lex: il modello non puo' stabilire da solo cosa e' vero. Verita', stato, vincoli e riferimenti puntuali vengono solo da contesto applicativo, fonti ufficiali verificate e controlli del codice.",
        "Se un dato manca o non e' verificato, dichiaralo chiaramente e non riempire i vuoti con ipotesi.",
    ]
    if requires_verified_legal_reference:
        lines.append(
            "Per sentenze o pronunce specifiche puoi citare numero, sezione, organo o link solo se risultano da una fonte verificata."
        )
    if requires_verified_normative_freshness:
        lines.append(
            "Per dire che una norma e' aggiornata o vigente serve una fonte ufficiale verificata; senza verifica non usare formule assolute."
        )
    if requires_verified_pdf:
        lines.append(
            "Per confermare che un PDF esiste o puo' essere scaricato serve un link ufficiale verificato; altrimenti dillo esplicitamente."
        )
    if requires_internal_state_source:
        lines.append(
            "Per stato di fascicoli, depositi, udienze o scadenze usa solo i dati interni disponibili; se il contesto non basta, non inventare lo stato reale."
        )
    if allow_web_fallback:
        lines.append(
            "Se il contesto interno non basta e la richiesta e' esterna o aggiornata, integra con fonti ufficiali live; non usare il web a caso."
        )
    return lines


def build_execution_policy(
    *,
    question: str,
    focus_topic: str = "",
    verified_legal_references: list[dict[str, Any]] | None = None,
    web_execution_requested: bool = False,
) -> LexExecutionPolicy:
    clean_question = _normalize_text(question)
    clean_topic = _normalize_text(focus_topic)
    has_verified_legal_reference = bool(list(verified_legal_references or []))

    is_case_law = _matches_any(clean_question, _CASE_LAW_PATTERNS) or clean_topic == "sentenze_civili"
    is_normative = _matches_any(clean_question, _NORMATIVE_PATTERNS)
    is_pdf_request = _matches_any(clean_question, _PDF_PATTERNS)
    is_internal_state = (
        clean_topic in {"fascicoli", "udienze", "agenda", "scadenze", "economico"}
        or _matches_any(clean_question, _INTERNAL_STATE_PATTERNS)
    )
    has_recency = _matches_any(clean_question, _RECENCY_PATTERNS)

    requires_verified_legal_reference = bool(is_case_law)
    requires_verified_normative_freshness = bool(is_normative and has_recency)
    requires_verified_pdf = bool(is_pdf_request and (is_case_law or is_normative))
    requires_internal_state_source = bool(is_internal_state)
    allow_web_fallback = bool(web_execution_requested or is_case_law or is_normative)

    mode = "operational_voice"
    summary_label = "voce operativa vincolata alle fonti"
    truth_strategy = "contesto_interno_e_fonti_verificate"
    if requires_verified_legal_reference or requires_verified_normative_freshness:
        truth_strategy = "fonti_ufficiali_verificate"
    elif requires_internal_state_source:
        truth_strategy = "contesto_applicativo_interno"

    if requires_verified_legal_reference and has_verified_legal_reference:
        summary_label = "ricerca legale con fonti verificate"
    if requires_verified_normative_freshness and has_recency:
        summary_label = "normativa aggiornata con fonti verificate"

    if requires_verified_legal_reference and not has_verified_legal_reference:
        mode = "strict_verified_sources"
        summary_label = "riferimenti legali solo verificati"
    elif requires_internal_state_source:
        mode = "strict_internal_state"
        summary_label = "stato applicativo solo da dati interni"
    elif requires_verified_normative_freshness:
        mode = "strict_normative_freshness"
        summary_label = "normativa aggiornata solo da fonti ufficiali"

    prompt_block = "\n".join(
        _build_policy_prompt_lines(
            requires_verified_legal_reference=requires_verified_legal_reference,
            requires_verified_normative_freshness=requires_verified_normative_freshness,
            requires_verified_pdf=requires_verified_pdf,
            requires_internal_state_source=requires_internal_state_source,
            allow_web_fallback=allow_web_fallback,
        )
    ).strip()

    return LexExecutionPolicy(
        mode=mode,
        summary_label=summary_label,
        llm_role="voce_e_ragionamento_locale",
        truth_strategy=truth_strategy,
        requires_verified_legal_reference=requires_verified_legal_reference,
        requires_verified_normative_freshness=requires_verified_normative_freshness,
        requires_verified_pdf=requires_verified_pdf,
        requires_internal_state_source=requires_internal_state_source,
        forbid_invented_missing_data=True,
        allow_web_fallback=allow_web_fallback,
        prompt_block=prompt_block,
    )


__all__ = ["LexExecutionPolicy", "build_execution_policy"]
