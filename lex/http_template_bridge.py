"""Ingresso mirato per i comandi espliciti di compilazione da template."""
from __future__ import annotations

import re
from typing import Any


def template_http_payload(*, user, studio, data: dict[str, Any], question: str, attachments):
    from .http_bounded_bridge import (
        _is_template_act_request,
        _manual_free_web_enabled,
        build_bounded_http_payload,
    )

    if attachments or _manual_free_web_enabled(data):
        return None
    # La sola menzione di un atto in una domanda di diritto non è un comando.
    if not re.match(r"\s*(?:usa|prepara|compila|redigi)\b", question, re.I):
        return None
    active = data.get("active_context") if isinstance(data.get("active_context"), dict) else {}
    if not _is_template_act_request(question, {"active_context": active}, {}):
        return None
    return build_bounded_http_payload(
        user=user, studio=studio, data=data, current_user_message=question,
        resolved_effective_question=question, attachments=[],
        studio_context={"effective_question": question, "focus_topic": "template_act",
                        "focus_label": "Template atti", "active_context": active,
                        "request_profile": {"intent": "template_act_prefill", "source_mode": "internal"}},
    )
