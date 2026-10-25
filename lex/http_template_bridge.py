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
    # Intento di redazione, separato dal nome dell'atto: nessuna frase completa codificata.
    from .http_bounded_bridge import _VERBI_REDAZIONE
    from pct.template_atti_lex_service import errore_battitura_minimo, normalize_text, resolve_template_for_query

    verbi = [v for v in _VERBI_REDAZIONE if v not in {"bozza", "template", "modello", "catalogo", "fac-simile", "facsimile"}]
    verbi += ["usa", "preparami", "compilami", "redigimi", "creami", "stendi", "predisponi", "produci", "genera", "elabora", "imposta", "fammi una bozza", "fammi un modello"]
    comando = "(?:" + "|".join(re.escape(v) for v in verbi) + r")\b"
    infinito = r"(?:usare|preparare|compilare|redigere|scrivere|creare|stendere|predisporre|produrre|generare|elaborare|impostare)\b"
    richiesta = r"(?:vorrei|voglio|desidero|devo|dovrei|intendo)\s+" + infinito
    domanda = r"(?:puoi|potresti)\s+(?:aiutarmi\s+a\s+)?" + infinito
    testo = re.sub(r"^\s*(?:(?:ciao|buongiorno|per favore|gentilmente)[,!:]?\s+)+", "", question, flags=re.I)
    words = testo.split(maxsplit=1)
    if words and len(words[0]) >= 5 and words[0].lower() not in verbi:
        vicini = [v for v in verbi if " " not in v and errore_battitura_minimo(words[0].lower(), v)]
        if len(vicini) == 1:
            testo = vicini[0] + (" " + words[1] if len(words) > 1 else "")
    necessita = r"(?:mi serve|mi occorre|ho bisogno di|ho necessita di)\s+(.*)"
    azione = re.match(r"\s*(?:" + comando + "|" + richiesta + "|" + domanda + r")\s*(.*)", testo, re.I)
    if not azione:
        azione = re.match(necessita, normalize_text(testo), re.I)
    if not azione:
        return None
    oggetto = normalize_text(azione.group(1))
    if re.match(r"(?:un[ao]?\s+)?(?:spiegazione|analisi|sintesi|riassunto|commento|sapere|capire|parere\s+su)\b", oggetto):
        # Un parere con titolo completo del catalogo e un modello redigibile;
        # una domanda informativa o un parere generico resta fuori dal percorso.
        if not re.match(r"(?:un[ao]?\s+)?parere\s+su\b", oggetto):
            return None
        catalog_match = resolve_template_for_query(testo)
        catalog_name = normalize_text(catalog_match.name)
        if not catalog_match.found or not catalog_name or f" {catalog_name} " not in f" {oggetto} ":
            return None
    active = data.get("active_context") if isinstance(data.get("active_context"), dict) else {}
    if not _is_template_act_request(question, {"active_context": active}, {}):
        # Riusa il catalogo reale anche per atti non compresi nei vecchi indizi HTTP.
        match = resolve_template_for_query(testo, {"active_context": active})
        tokens = set(oggetto.split()) - {"un", "una", "il", "la", "lo", "di", "del", "della", "per", "atto", "bozza", "modello"}
        if not match.found or not (match.score >= 0.35 or tokens.intersection(normalize_text(match.name).split())):
            return None
    return build_bounded_http_payload(
        user=user, studio=studio, data=data, current_user_message=question,
        resolved_effective_question=question, attachments=[],
        studio_context={"effective_question": question, "focus_topic": "template_act",
                        "focus_label": "Template atti", "active_context": active,
                        "request_profile": {"intent": "template_act_prefill", "source_mode": "internal"}},
    )
