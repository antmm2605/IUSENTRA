"""Contesto anagrafico cliente/parti per Lex."""

from __future__ import annotations

from typing import Any

from web.helpers import get_clienti, get_fascicoli, get_soggetti


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _serialize_cliente(row: Any) -> dict[str, Any]:
    recapiti = getattr(row, "recapiti", None)
    return {
        "id": getattr(row, "id", ""),
        "nome": getattr(row, "nome", "") or getattr(row, "nome_completo", ""),
        "cognome": getattr(row, "cognome", ""),
        "nome_completo": getattr(row, "nome_completo", "") or _clean_spaces(
            f"{getattr(row, 'cognome', '')} {getattr(row, 'nome', '')}"
        ),
        "cf": getattr(row, "codice_fiscale", "") or getattr(row, "identificativo_fiscale", ""),
        "partita_iva": getattr(row, "partita_iva", ""),
        "email": getattr(recapiti, "email", "") if recapiti is not None else getattr(row, "email", ""),
        "pec": getattr(recapiti, "pec", "") if recapiti is not None else getattr(row, "pec", ""),
    }


def _serialize_soggetto(row: Any, *, ruolo: str = "", note: str = "") -> dict[str, Any]:
    recapiti = getattr(row, "recapiti", None)
    return {
        "id": getattr(row, "id", ""),
        "nome": getattr(row, "nome", "") or getattr(row, "ragione_sociale", "") or getattr(row, "nome_completo", ""),
        "cognome": getattr(row, "cognome", ""),
        "nome_completo": getattr(row, "nome_completo", "") or _clean_spaces(
            f"{getattr(row, 'cognome', '')} {getattr(row, 'nome', '')}"
        ),
        "cf": getattr(row, "codice_fiscale", "") or getattr(row, "partita_iva", "") or getattr(row, "identificativo", ""),
        "email": getattr(recapiti, "email", "") if recapiti is not None else "",
        "pec": getattr(recapiti, "pec", "") if recapiti is not None else "",
        "ruolo": ruolo,
        "note": note,
    }


def load_anagrafica_context(*, pratica_id: str = "", limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    target = _clean_spaces(pratica_id).lower()
    clienti_rows: list[dict[str, Any]] = []
    soggetti_rows: list[dict[str, Any]] = []
    fascicolo = None

    if target:
        try:
            fascicolo = get_fascicoli().get(pratica_id)
        except Exception:
            fascicolo = None
    if fascicolo is not None:
        if getattr(fascicolo, "id_cliente", ""):
            cliente = get_clienti().get(getattr(fascicolo, "id_cliente", ""))
            if cliente is not None:
                clienti_rows.append(_serialize_cliente(cliente))
        try:
            for parte, soggetto in get_soggetti().parti_fascicolo(fascicolo.id):
                ruolo = getattr(getattr(parte, "ruolo", None), "value", getattr(parte, "ruolo", ""))
                soggetti_rows.append(
                    _serialize_soggetto(
                        soggetto,
                        ruolo=str(ruolo or ""),
                        note=str(getattr(parte, "note", "") or ""),
                    )
                )
                if len(soggetti_rows) >= max(int(limit or 0), 1):
                    break
        except Exception:
            soggetti_rows = []
        return {
            "clienti": clienti_rows[: max(int(limit or 0), 1)],
            "soggetti": soggetti_rows[: max(int(limit or 0), 1)],
        }

    for row in get_clienti().tutti()[:100]:
        haystack = " ".join(
            _clean_spaces(part).lower()
            for part in [
                getattr(row, "nome_completo", ""),
                getattr(row, "nome", ""),
                getattr(row, "cognome", ""),
                getattr(row, "codice_fiscale", ""),
                getattr(row, "partita_iva", ""),
            ]
        )
        if target and target not in haystack:
            continue
        clienti_rows.append(_serialize_cliente(row))
        if len(clienti_rows) >= max(int(limit or 0), 1):
            break

    try:
        for row in get_soggetti().tutti()[:100]:
            haystack = " ".join(
                _clean_spaces(part).lower()
                for part in [
                    getattr(row, "nome_completo", ""),
                    getattr(row, "nome", ""),
                    getattr(row, "cognome", ""),
                    getattr(row, "ragione_sociale", ""),
                    getattr(row, "codice_fiscale", ""),
                    getattr(row, "partita_iva", ""),
                ]
            )
            if target and target not in haystack:
                continue
            soggetti_rows.append(_serialize_soggetto(row, ruolo=_enum_value(getattr(row, "tipo", ""))))
            if len(soggetti_rows) >= max(int(limit or 0), 1):
                break
    except Exception:
        soggetti_rows = []

    return {"clienti": clienti_rows, "soggetti": soggetti_rows}
