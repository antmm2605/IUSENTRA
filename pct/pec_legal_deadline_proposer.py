"""Proponente-termini legali per la PEC (deterministico).

Estrae dal testo della PEC la norma citata, il tipo di dies a quo e la direzione,
risolve la norma nel template versionato e delega il CALCOLO della data al motore
deterministico `termini_processuali.ItalianDeadlineCalculator` (avanti/a ritroso,
sospensione feriale, audit). **Non calcola date da solo** e **non è mai fonte unica**:
propone, con revisione umana obbligatoria; il motore scadenziario persiste.

Regole bloccanti (fonti certe):
- `deposito_sentenza` ⇒ nessun termine breve ex art. 325 dalla sola comunicazione
  (art. 133 c.p.c.);
- "assegna termine" senza durata chiara ⇒ revisione umana, nessun calcolo.

Ambito: civile. Penale/PAT/PTT/SIGIT ⇒ nessun calcolo automatico (ruleset dedicato assente).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pct.termini_processuali import DEFAULT_TEMPLATES, ItalianDeadlineCalculator


DEFAULT_RULESET_PATH = Path(__file__).with_name("data") / "legal_pec_deadline_rules_v2026_07.json"
_RULESET_CACHE: dict[str, dict[str, Any]] = {}
_TEMPLATES_BY_CODE = {template.code: template for template in DEFAULT_TEMPLATES}


def load_ruleset(path: str | Path | None = None) -> dict[str, Any]:
    resolved = str(path or DEFAULT_RULESET_PATH)
    cached = _RULESET_CACHE.get(resolved)
    if cached is None:
        cached = json.loads(Path(resolved).read_text(encoding="utf-8"))
        _RULESET_CACHE[resolved] = cached
    return cached


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text[:len(fmt) + 2], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _resolve_rule(text_norm: str, ruleset: dict[str, Any]) -> dict[str, Any] | None:
    for rule in ruleset.get("regole", []):
        if any(_norm(kw) in text_norm for kw in rule.get("keywords", [])):
            return rule
    return None


def propose_legal_deadline(
    text: str,
    *,
    dies_a_quo_date: Any,
    event_type: str = "",
    ruleset: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Propone un termine LEGALE calcolato dal motore deterministico, o None se non
    riconosciuto. Ogni proposta porta `human_review_required=True` (mai definitiva)."""

    rules = ruleset or load_ruleset()
    text_norm = _norm(text)

    blocco = rules.get("blocco_art_325", {})
    is_deposito_sentenza = event_type == "deposito_sentenza" or any(
        _norm(kw) in text_norm for kw in blocco.get("keywords", [])
    )

    rule = _resolve_rule(text_norm, rules)
    if rule is None:
        if any(_norm(kw) in text_norm for kw in rules.get("assegnazione_generica_keywords", [])):
            return {
                "ok": False,
                "human_review_required": True,
                "reason": "Termine assegnato dal giudice senza durata chiara: revisione umana.",
                "norma": "",
                "template_code": "",
            }
        return None

    template = _TEMPLATES_BY_CODE.get(str(rule.get("template_code") or ""))
    if template is None:
        return None

    # Regola #1 (art. 133/325): la sola comunicazione di deposito sentenza NON fa
    # decorrere il termine breve. Se la PEC è un deposito sentenza e la regola è un
    # termine breve ex art. 325, blocca sempre: il breve parte dalla notificazione
    # (evento distinto), mai dalla comunicazione di cancelleria.
    if template.reference_law.startswith("Art. 325") and is_deposito_sentenza:
        return {
            "ok": False,
            "human_review_required": True,
            "reason": blocco.get("regola", "Termine breve non calcolabile dalla sola comunicazione."),
            "norma": template.reference_law,
            "template_code": template.code,
        }

    dies = _parse_date(dies_a_quo_date)
    if dies is None:
        return {
            "ok": False,
            "human_review_required": True,
            "reason": "Data di decorrenza (dies a quo) non disponibile o non riconosciuta.",
            "norma": template.reference_law,
            "template_code": template.code,
        }

    result = ItalianDeadlineCalculator().calculate(
        dies,
        template.base_value,
        direction=template.direction,
        template_code=template.code,
        template_name=template.name,
        period_type=template.period_type,
        free_term=template.free_term,
        suspend_august=template.suspend_august,
        ferial_suspension_policy=template.ferial_suspension_policy,
        urgent=template.urgent,
        reference_law=template.reference_law,
    )
    return {
        "ok": True,
        "norma": template.reference_law,
        "template_code": template.code,
        "dies_a_quo_type": rule.get("dies_a_quo_type", ""),
        "dies_a_quo_date": dies.isoformat(),
        "direzione": template.direction,
        "durata": template.base_value,
        "unita": template.period_type,
        "tipo": rule.get("tipo", "non_specificato"),
        "deadline": result.get("deadline"),
        "raw_deadline": result.get("rawDeadline"),
        "requires_legal_review": bool(result.get("requiresLegalReview")),
        "steps": result.get("steps", []),
        "explanation": result.get("explanation", ""),
        "confidence": float(rule.get("confidence", 0.75)),
        "azione": rule.get("azione", ""),
        "human_review_required": True,
    }


__all__ = ["load_ruleset", "propose_legal_deadline"]
