"""Semantic corrections for ministerial PCT deposit metadata."""

from __future__ import annotations

import re
from collections.abc import Iterable
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


def expected_deposito_object_parent_for_context(fascicolo: Any, form: Any | None = None) -> str:
    """Restituisce la famiglia PST certa per i soli casi governati semanticamente."""

    if is_carta_docente_pubblico_impiego(fascicolo, form):
        return "222"
    return ""


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


def _document_attr(document: Any, name: str) -> Any:
    if isinstance(document, dict):
        return document.get(name)
    return getattr(document, name, None)


def _document_source_name(document: Any) -> str:
    for key in ("nome", "name", "nome_originale", "filename", "percorso", "path"):
        value = _text(_document_attr(document, key))
        if value:
            return value.replace("\\", "/").split("/")[-1]
    return "documento"


def _document_semantic_text(document: Any) -> str:
    values: list[str] = []
    for key in (
        "nome",
        "name",
        "nome_originale",
        "filename",
        "percorso",
        "path",
        "tipo",
        "descrizione",
        "description",
        "note",
        "ruolo",
        "deposit_role",
        "depositRole",
        "catalog_role",
        "catalogRole",
        "catalog_label",
        "catalogLabel",
        "catalog_section",
        "catalogSection",
        "classificazione_portale",
        "tipo_atto_portale",
    ):
        value = _document_attr(document, key)
        if isinstance(value, dict):
            values.extend(_text(item) for item in value.values())
        elif isinstance(value, (list, tuple, set)):
            values.extend(_text(item) for item in value)
        else:
            values.append(_text(value))
    return " ".join(value for value in values if value).casefold()


def _payment_amount_from_text(value: str) -> float | None:
    for match in re.finditer(r"(?:eur|euro|€)?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,.]\d{2})", value, flags=re.IGNORECASE):
        amount = _payment_amount(match.group(1))
        if amount is not None:
            return amount
    return None


def _contributo_unificato_from_documents(
    fascicolo: Any,
    documents: Iterable[Any] | None,
) -> dict[str, Any] | None:
    selected_documents = list(documents or [])
    for document in selected_documents:
        text = _document_semantic_text(document)
        if not text:
            continue
        contribution_context = (
            "contributo unificato" in text
            or "cu " in f"{text} "
            or " cu" in text
            or "spese giustizia" in text
        )
        payment_marker = any(
            marker in text
            for marker in (
                "pagopa",
                "ricevuta telematica",
                "ricevuta pagamento",
                "pagamento contributo",
                "versamento contributo",
                "quietanza",
                "f23",
                "f24",
                "iuv",
            )
        )
        if contribution_context and payment_marker:
            document_amount = _payment_amount_from_text(text)
            return {
                "resolved": document_amount is not None,
                "mode": "pagato",
                "importo": document_amount,
                "debito": False,
                "source": _document_source_name(document),
                "status": "pagato",
                "natura": "pagamento_contributo_unificato",
                "payment_evidence": True,
            }

    for document in selected_documents:
        text = _document_semantic_text(document)
        if not text:
            continue
        explicit_exemption = any(
            marker in text
            for marker in (
                "esenzione contributo unificato",
                "esente dal pagamento",
                "contributo unificato non dovuto",
                "contributo non dovuto",
                "non debenza",
                "patrocinio a spese dello stato",
                "prenotazione a debito",
                "art. 9 comma 1-bis",
                "articolo 9 comma 1-bis",
                "dpr 115",
            )
        )
        carta_docente_reddituale = (
            is_carta_docente_pubblico_impiego(fascicolo)
            and any(marker in text for marker in ("autocertific", "dichiarazione sostitutiva"))
            and any(marker in text for marker in ("reddito", "reddituale", "situazione reddituale", "isee"))
        )
        if explicit_exemption or carta_docente_reddituale:
            return {
                "resolved": True,
                "mode": "esente",
                "importo": None,
                "debito": False,
                "source": _document_source_name(document),
                "status": "non_previsto",
                "natura": "esenzione_contributo_unificato",
                "payment_evidence": False,
            }
    return None


def ministerial_contributo_unificato_for_context(
    fascicolo: Any,
    documents: Iterable[Any] | None = None,
) -> dict[str, Any]:
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
        resolved = True
    elif paid:
        mode = "pagato"
        resolved = False
    else:
        mode = "da_definire"
        resolved = False

    document_state = _contributo_unificato_from_documents(fascicolo, documents)
    if document_state and document_state["mode"] == "esente" and (not raw or mode == "da_definire"):
        return document_state

    if mode == "pagato" or (document_state and document_state["mode"] == "pagato"):
        document_amount = document_state.get("importo") if document_state else None
        effective_amount = amount if amount is not None else document_amount
        if documents is None:
            payment_evidence = bool(source) or bool(document_state and document_state.get("payment_evidence"))
            effective_source = source or str((document_state or {}).get("source") or "")
        else:
            payment_evidence = bool(document_state and document_state.get("payment_evidence"))
            effective_source = str((document_state or {}).get("source") or "")
        if effective_amount is None:
            blocking_message = "Manca il contributo unificato: inserisci l'importo pagato."
        elif not payment_evidence:
            blocking_message = (
                "Mancano gli estremi di pagamento del Contributo Unificato: "
                "inserisci la ricevuta telematica tra i documenti del deposito."
            )
        else:
            blocking_message = ""
        return {
            "resolved": effective_amount is not None and payment_evidence,
            "mode": "pagato",
            "importo": effective_amount,
            "debito": False,
            "source": effective_source,
            "status": status or "pagato",
            "natura": nature or "pagamento_contributo_unificato",
            "payment_evidence": payment_evidence,
            "blocking_message": blocking_message,
        }

    if document_state and not raw:
        return document_state

    return {
        "resolved": resolved,
        "mode": mode,
        "importo": amount,
        "debito": mode == "prenotato_a_debito",
        "source": source,
        "status": status,
        "natura": nature,
        "payment_evidence": False,
        "blocking_message": (
            "Manca il contributo unificato: indica se non è dovuto, esente, a debito o pagato."
            if not resolved
            else ""
        ),
    }
