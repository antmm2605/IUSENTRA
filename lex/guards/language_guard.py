"""Guardia linguistica autonoma con retry e fallback deterministico.

Uso diretto (fuori dalla pipeline di guardie):
    from lex.guards.language_guard import validate_italian_output
    result = validate_italian_output(text, context={"workflow": "drafting_legal_letter"})
"""

from __future__ import annotations

from typing import Any, Callable

from .italian_response_guard import detect_non_italian_response, rewrite_or_reject_non_italian_response


def validate_italian_output(
    text: str,
    *,
    context: dict[str, Any] | None = None,
    retry_fn: Callable[[], str] | None = None,
    max_retries: int = 1,
) -> tuple[str, bool]:
    """Valida e tenta di correggere una risposta non italiana.

    Restituisce ``(testo_finale, era_italiano)`` dove:
    - ``testo_finale`` è il testo definitivo (potenzialmente riscritto o ottenuto via retry)
    - ``era_italiano`` è True se il testo originale era già conforme

    Strategia:
    1. Se il testo è già in italiano → restituisce il testo originale (era_italiano=True)
    2. Tenta di riscrivere le formule inglesi note
    3. Se ancora non italiano e ``retry_fn`` disponibile → richiama il provider (max ``max_retries`` volte)
    4. Se tutto fallisce → applica il fallback deterministico dal contesto
    """
    original = str(text or "").strip()

    if not detect_non_italian_response(original):
        return original, True

    ctx = dict(context or {})
    rewritten = rewrite_or_reject_non_italian_response(original, ctx)
    if not detect_non_italian_response(rewritten):
        return rewritten, False

    if retry_fn is not None:
        for attempt in range(max_retries):
            try:
                retried = str(retry_fn() or "").strip()
                if retried and not detect_non_italian_response(retried):
                    return retried, False
            except Exception:
                pass

    workflow = str(ctx.get("workflow") or "").lower()
    query = str(ctx.get("query") or "").lower()
    if workflow in {"drafting_legal_letter", "lettera", "bozza_lettera"} or any(
        kw in query for kw in ("diffida", "messa in mora", "sollecito", "lettera legale")
    ):
        try:
            from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
            return build_diffida_messa_in_mora_template(ctx), False
        except Exception:
            pass

    fallback = (
        "La risposta generata non era conforme alla lingua italiana e non viene mostrata. "
        "Lex risponde sempre in italiano. Riformula la richiesta o riprova."
    )
    return fallback, False


__all__ = ["validate_italian_output"]
