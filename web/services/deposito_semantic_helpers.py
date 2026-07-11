"""Semantic corrections for ministerial PCT deposit metadata."""

from __future__ import annotations

import re
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


def _normalise_payment_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).casefold()).strip("_")


def _payment_amount(value: Any) -> float | None:
    raw = _text(value).replace("EUR", "").replace("eur", "").replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        amount = round(float(raw), 2)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def ministerial_contributo_unificato_for_context(fascicolo: Any) -> dict[str, Any]:
    """Resolve the ministerial contribution state from the fascicolo source of truth."""
    payments = _dict_or_empty(getattr(fascicolo, "pagamenti", {}))
    raw: dict[str, Any] = {}
    for key, value in payments.items():
        if _normalise_payment_token(key) in {"contributo", "contributo_unificato", "cu"}:
            raw = _dict_or_empty(value)
            break

    status = _normalise_payment_token(raw.get("status") or raw.get("stato"))
    nature = _normalise_payment_token(raw.get("natura") or raw.get("nature"))
    evidence = " ".join(
        _text(raw.get(key))
        for key in ("label", "etichetta", "note", "natura", "nature")
    ).casefold()
    amount = _payment_amount(raw.get("importo") if "importo" in raw else raw.get("amount"))
    source = _text(raw.get("documento_fonte") or raw.get("documentSource") or raw.get("documentoFonte"))

    exempt = (
        raw.get("previsto") is False
        or status in {"non_previsto", "non_prevista", "esente", "non_dovuto", "non_dovuta"}
        or any(marker in nature for marker in ("esenzione", "non_dovuto", "non_debenza"))
        or any(marker in evidence for marker in ("esente", "esenzione", "non dovuto", "non debenza"))
    )
    debt = "debito" in nature or "prenot" in nature or "prenot" in evidence and "debito" in evidence
    paid = raw.get("pagato") is True or status in {"pagato", "pagata", "saldato", "saldata"}

    if exempt:
        mode = "esente"
        resolved = True
    elif debt:
        mode = "prenotato_a_debito"
        resolved = amount is not None
    elif paid:
        mode = "pagato"
        resolved = amount is not None
    else:
        mode = "da_definire"
        resolved = False

    return {
        "resolved": resolved,
        "mode": mode,
        "importo": amount,
        "debito": mode == "prenotato_a_debito",
        "source": source,
        "status": status,
        "natura": nature,
    }
