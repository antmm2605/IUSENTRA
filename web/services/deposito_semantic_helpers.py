"""Semantic corrections for ministerial PCT deposit metadata."""

from __future__ import annotations

from typing import Any


PUBLIC_EMPLOYMENT_RETRIBUZIONE_CODE = "222050"
PRIVATE_EMPLOYMENT_RETRIBUZIONE_CODE = "220050"
CARTA_DOCENTE_DEFAULT_VALUE = 500.0


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nested_text(root: Any, *path: str) -> str:
    current = root
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return _text(current)


def fascicolo_semantic_text(fascicolo: Any, form: Any | None = None) -> str:
    values: list[str] = []
    form_get = getattr(form, "get", None)
    if callable(form_get):
        values.extend(
            [
                _text(form_get("oggetto", "")),
                _text(form_get("tipo_procedimento", "")),
                _text(form_get("codice_oggetto_pst", "")),
            ]
        )
    values.extend(
        [
            _text(getattr(fascicolo, "titolo", "")),
            _text(getattr(fascicolo, "oggetto", "")),
            _text(getattr(fascicolo, "tipo_procedimento", "")),
            _text(getattr(fascicolo, "area_pratica", "")),
            _text(getattr(fascicolo, "controparte", "")),
            _text(getattr(fascicolo, "note", "")),
            _text(getattr(fascicolo, "codice_oggetto_pst", "")),
        ]
    )
    dati = _dict_or_empty(getattr(fascicolo, "dati_json", {}))
    profilo = _dict_or_empty(getattr(fascicolo, "profilo_deposito", {}))
    values.extend(
        [
            _text(dati.get("oggetto")),
            _text(dati.get("tipo_procedimento")),
            _text(dati.get("area_pratica")),
            _text(dati.get("controparte")),
            _text(dati.get("codice_oggetto_pst")),
            _nested_text(dati, "profilo_deposito", "codice_deposito", "codice_oggetto_pst"),
            _nested_text(profilo, "codice_deposito", "codice_oggetto_pst"),
        ]
    )
    return " ".join(value for value in values if value).casefold()


def is_carta_docente_pubblico_impiego(fascicolo: Any, form: Any | None = None) -> bool:
    text = fascicolo_semantic_text(fascicolo, form)
    has_carta_docente = (
        "carta docente" in text
        or "carta del docente" in text
        or "bonus docente" in text
        or "annualità" in text and "docente" in text
        or "annualita" in text and "docente" in text
    )
    has_public_counterparty = (
        "mim" in text
        or "ministero" in text
        or "istruzione" in text
        or "merito" in text
        or "avvocatura" in text and "stato" in text
        or "pubblico impiego" in text
    )
    return has_carta_docente and has_public_counterparty


def correct_deposito_oggetto_for_context(raw_code: str, fascicolo: Any, form: Any | None = None) -> str:
    code = _text(raw_code)
    if code == PRIVATE_EMPLOYMENT_RETRIBUZIONE_CODE and is_carta_docente_pubblico_impiego(fascicolo, form):
        return PUBLIC_EMPLOYMENT_RETRIBUZIONE_CODE
    return code


def ministerial_valore_causa_for_context(fascicolo: Any) -> float | None:
    candidates: list[Any] = [
        getattr(fascicolo, "valore_causa", None),
        _dict_or_empty(getattr(fascicolo, "dati_json", {})).get("valore_causa"),
        _dict_or_empty(getattr(fascicolo, "dati_json", {})).get("valore"),
        _dict_or_empty(getattr(fascicolo, "dati_json", {})).get("importo"),
        _dict_or_empty(getattr(fascicolo, "profilo_deposito", {})).get("valore_causa"),
    ]
    for candidate in candidates:
        try:
            value = float(str(candidate).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    if is_carta_docente_pubblico_impiego(fascicolo):
        return CARTA_DOCENTE_DEFAULT_VALUE
    return None
