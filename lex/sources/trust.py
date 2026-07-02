"""Valutazione di affidabilità delle fonti per l'apprendimento di Lex.

Compone i motori ESISTENTI senza duplicarli:
- `lex.research.source_policy.evaluation.evaluate_source` → tier/score/
  affidabilità per area (20 aree governate, pesi e soglie versionati);
- `lex.research.source_registry.get_source_registry` → flag `official`,
  `requires_credentials`, chiave fonte.

Decisione `allowed_for_learning` (fail-closed):
- denylist → mai ammessa (vince su tutto);
- fonte con credenziali richieste → mai ammessa (niente aree riservate);
- allowlist non vuota → il dominio deve appartenervi;
- `require_official=True` → ammessi solo tier_1/tier_2 (fonti primarie e
  istituzionali secondarie); tier_3 = solo contesto, unknown = mai autorevole.
Blog, forum e social non compaiono nei tier del Source Policy System, quindi
risultano `unknown` → mai ammessi come fonte di apprendimento.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from lex.sources.models import SourceTrustAssessment


def _domain_matches(domain: str, pattern: str) -> bool:
    domain = domain.casefold().lstrip(".")
    pattern = str(pattern or "").casefold().strip().lstrip(".")
    if not domain or not pattern:
        return False
    return domain == pattern or domain.endswith(f".{pattern}")


def assess_source(
    url: str,
    *,
    area: str,
    mode: str = "strict",
    require_official: bool = True,
    allowlist: Iterable[str] = (),
    denylist: Iterable[str] = (),
) -> SourceTrustAssessment:
    """Valuta una URL per l'apprendimento: tier + registro + liste governate."""

    # Import pigri: moduli puri (dati + funzioni), caricati solo al primo uso.
    from lex.research.source_policy.evaluation import evaluate_source
    from lex.research.source_registry import get_source_registry

    url = str(url or "").strip()
    domain = (urlsplit(url).hostname or "").casefold()
    assessment = SourceTrustAssessment(url=url, domain=domain, area=str(area or ""))
    if not url or not domain:
        assessment.reasons.append("URL vuota o senza dominio: fonte scartata.")
        return assessment

    evaluation = evaluate_source(url, area, mode)
    assessment.tier = evaluation.tier.value
    assessment.score = float(evaluation.score)
    assessment.reliability = evaluation.reliability
    assessment.authority_band = evaluation.authority_band
    assessment.warnings.extend(evaluation.warnings)
    if evaluation.reason:
        assessment.reasons.append(evaluation.reason)

    registered = get_source_registry().find_by_host(url)
    restricted = False
    publicly_readable = True
    if registered is not None:
        assessment.official = bool(getattr(registered, "official", False))
        assessment.source_id = str(getattr(registered, "key", "") or "")
        assessment.requires_credentials = bool(getattr(registered, "requires_credentials", False))
        restricted = bool(getattr(registered, "restricted", False))
        publicly_readable = bool(getattr(registered, "supports_public_web_search", True))
    else:
        assessment.official = assessment.tier == "tier_1"

    deny_hit = next((pattern for pattern in denylist if _domain_matches(domain, pattern)), "")
    if deny_hit:
        assessment.reasons.append(f"Dominio in denylist ({deny_hit}): mai ammesso.")
        return assessment
    if restricted:
        assessment.reasons.append("Fonte riservata nel registro: esclusa dall'apprendimento autonomo.")
        return assessment
    # Le credenziali bloccano SOLO se sono l'unica via d'accesso: fonti come
    # EUR-Lex richiedono registrazione per l'API ma restano pubblicamente
    # leggibili via web (supports_public_web_search).
    if assessment.requires_credentials and not publicly_readable:
        assessment.reasons.append("La fonte richiede credenziali per ogni accesso: esclusa dall'apprendimento autonomo.")
        return assessment
    if assessment.requires_credentials:
        assessment.warnings.append("L'accesso API della fonte richiede registrazione: il ciclo legge solo le pagine pubbliche.")
    allow_patterns = [pattern for pattern in allowlist if str(pattern or "").strip()]
    if allow_patterns and not any(_domain_matches(domain, pattern) for pattern in allow_patterns):
        assessment.requires_review = True
        assessment.reasons.append("Dominio fuori dalla allowlist configurata: richiede revisione umana.")
        return assessment

    if assessment.tier in {"tier_1", "tier_2"}:
        assessment.allowed_for_learning = True
        assessment.reasons.append(
            "Fonte primaria ufficiale ammessa." if assessment.tier == "tier_1" else "Fonte istituzionale secondaria ammessa."
        )
        return assessment
    if assessment.tier == "tier_3" and not require_official:
        assessment.allowed_for_learning = True
        assessment.requires_review = True
        assessment.reasons.append("Fonte di contesto (tier_3) ammessa solo come supporto, mai come verità primaria.")
        return assessment
    assessment.requires_review = assessment.tier == "tier_3"
    assessment.reasons.append(
        "Fonte non classificata dai tier governati: mai autorevole per l'apprendimento."
        if assessment.tier == "unknown"
        else "Fonte di contesto (tier_3) esclusa: è richiesta una fonte ufficiale."
    )
    return assessment


__all__ = ["assess_source"]
