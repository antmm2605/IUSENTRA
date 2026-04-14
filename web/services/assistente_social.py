"""Gestione sobria di saluti, cortesia e messaggi relazionali per Lex."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SocialIntent:
    kind: str
    confidence: float
    social_text: str = ""
    remaining_text: str = ""


_SOCIAL_PATTERNS = {
    "greeting": [
        r"\bciao\b",
        r"\bsalve\b",
        r"\bbuongiorno\b",
        r"\bbuonasera\b",
        r"\bbuon pomeriggio\b",
        r"\behi\b",
    ],
    "thanks": [
        r"\bgrazie\b",
        r"\bgrazie mille\b",
        r"\bti ringrazio\b",
        r"\bmolte grazie\b",
    ],
    "ack": [
        r"\bok\b",
        r"\bva bene\b",
        r"\bperfetto\b",
        r"\bottimo\b",
        r"\bbene\b",
        r"\bd['’]accordo\b",
    ],
    "farewell": [
        r"\ba domani\b",
        r"\ba dopo\b",
        r"\bci sentiamo dopo\b",
        r"\bci aggiorniamo\b",
        r"\bbuona giornata\b",
        r"\bbuona serata\b",
        r"\bbuona notte\b",
        r"\bbuon lavoro\b",
        r"\bbuon weekend\b",
    ],
    "apology": [
        r"\bscusa\b",
        r"\bscusami\b",
        r"\bmi sono spiegato male\b",
        r"\bforse non sono stato chiaro\b",
        r"\bforse non sono stata chiara\b",
    ],
    "praise": [
        r"\bbrava\b",
        r"\bbravo\b",
        r"\bcomplimenti\b",
        r"\bottimo lavoro\b",
        r"\bmolto bene\b",
    ],
}


def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _canonical_text(text: str) -> str:
    value = _normalize_text(text)
    value = re.sub(r"^[\s,;:.!?-]+|[\s,;:.!?-]+$", "", value)
    return value.lower()


def _is_only_social_text(text: str) -> Optional[str]:
    q = _canonical_text(text)
    if not q:
        return None

    for kind, patterns in _SOCIAL_PATTERNS.items():
        for pattern in patterns:
            if re.fullmatch(pattern, q):
                return kind
    return None


def _extract_leading_social_part(text: str) -> tuple[Optional[str], str, str]:
    original = _normalize_text(text)
    if not original:
        return None, "", ""

    for kind, patterns in _SOCIAL_PATTERNS.items():
        for pattern in patterns:
            match = re.match(rf"^({pattern})[,;:.!\s-]*(.*)$", original, flags=re.IGNORECASE)
            if match:
                social = _canonical_text(match.group(1))
                remaining = _normalize_text(match.group(2))
                if remaining:
                    return kind, social, remaining
    return None, "", original


def _is_substantive_request_tail(text: str) -> bool:
    original = _normalize_text(text)
    canonical = _canonical_text(original)
    if not canonical:
        return False

    if canonical in {"lex", "lex ai", "ai lex", "ai", "hacs", "hacs lex"}:
        return False

    tokens = [token for token in canonical.split() if token]
    if len(tokens) == 1 and "?" not in original and not any(char.isdigit() for char in canonical):
        return False

    return True


def classify_social_message(text: str) -> SocialIntent:
    q = _normalize_text(text)
    if not q:
        return SocialIntent(kind="none", confidence=0.0)

    only_kind = _is_only_social_text(q)
    if only_kind:
        return SocialIntent(
            kind=only_kind,
            confidence=1.0,
            social_text=_canonical_text(q),
            remaining_text="",
        )

    leading_kind, social_text, remaining = _extract_leading_social_part(q)
    if leading_kind and remaining and remaining != q and _is_substantive_request_tail(remaining):
        return SocialIntent(
            kind=f"{leading_kind}_with_request",
            confidence=0.9,
            social_text=social_text,
            remaining_text=remaining,
        )

    if leading_kind and remaining and remaining != q:
        return SocialIntent(
            kind=leading_kind,
            confidence=0.8,
            social_text=social_text,
            remaining_text="",
        )

    return SocialIntent(kind="none", confidence=0.0, remaining_text=q)


def build_social_reply(
    intent: SocialIntent,
    *,
    now: Optional[datetime] = None,
) -> Optional[str]:
    _ = (now or datetime.now()).hour

    if intent.kind == "greeting":
        social = intent.social_text
        if "buongiorno" in social:
            return "Buongiorno. Dimmi pure."
        if "buonasera" in social:
            return "Buonasera."
        if "buon pomeriggio" in social:
            return "Buon pomeriggio."
        if "ciao" in social:
            return "Ciao."
        if "salve" in social:
            return "Salve."
        return "Dimmi pure."

    if intent.kind == "thanks":
        social = intent.social_text
        if "grazie mille" in social:
            return "Di nulla."
        if "ti ringrazio" in social:
            return "Prego."
        return "Prego."

    if intent.kind == "ack":
        social = intent.social_text
        if "perfetto" in social:
            return "Perfetto."
        if "ottimo" in social:
            return "Ottimo."
        if "va bene" in social:
            return "Va bene."
        return "Va bene."

    if intent.kind == "farewell":
        social = intent.social_text
        if "a domani" in social:
            return "A domani."
        if "a dopo" in social:
            return "A dopo."
        if "ci sentiamo dopo" in social:
            return "A dopo."
        if "ci aggiorniamo" in social:
            return "Va bene, ci aggiorniamo."
        if "buona giornata" in social:
            return "Buona giornata."
        if "buona serata" in social:
            return "Buona serata."
        if "buona notte" in social:
            return "Buona notte."
        if "buon lavoro" in social:
            return "Grazie, buon lavoro anche a te."
        if "buon weekend" in social:
            return "Buon weekend."
        return "Va bene."

    if intent.kind == "apology":
        if "chiaro" in intent.social_text:
            return "Nessun problema, dimmi pure."
        return "Nessun problema."

    if intent.kind == "praise":
        social = intent.social_text
        if "molto bene" in social:
            return "Bene."
        return "Grazie."

    if intent.kind.endswith("_with_request"):
        base_kind = intent.kind.replace("_with_request", "")
        if base_kind == "greeting":
            if "buongiorno" in intent.social_text:
                return "Buongiorno."
            if "buonasera" in intent.social_text:
                return "Buonasera."
            if "buon pomeriggio" in intent.social_text:
                return "Buon pomeriggio."
            if "salve" in intent.social_text:
                return "Salve."
            return "Ciao."
        if base_kind == "thanks":
            return "Prego."
        if base_kind == "ack":
            return "Va bene."
        if base_kind == "apology":
            return "Nessun problema."
        if base_kind == "praise":
            return "Grazie."

    return None


def prepend_social_prefix(prefix: str, answer: str) -> str:
    clean_prefix = str(prefix or "").strip()
    clean_answer = str(answer or "").strip()
    if not clean_prefix:
        return clean_answer
    if not clean_answer:
        return clean_prefix
    if clean_answer.lower().startswith(clean_prefix.lower()):
        return clean_answer
    return f"{clean_prefix} {clean_answer}".strip()


def is_social_only_intent(intent: SocialIntent) -> bool:
    return intent.kind in {"greeting", "thanks", "ack", "farewell", "apology", "praise"}


__all__ = [
    "SocialIntent",
    "build_social_reply",
    "classify_social_message",
    "is_social_only_intent",
    "prepend_social_prefix",
]
