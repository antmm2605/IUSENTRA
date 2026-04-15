"""Facciata compatibile per il riconoscimento web execution di Lex.

Il modulo reale vive in ``lex.memory.web_execution``.
"""

from lex.memory.web_execution import (
    WebExecutionIntent,
    is_web_execution_request,
    previous_user_message,
    resolve_effective_query,
    resolve_web_execution_intent,
)

__all__ = [
    "WebExecutionIntent",
    "is_web_execution_request",
    "previous_user_message",
    "resolve_effective_query",
    "resolve_web_execution_intent",
]
