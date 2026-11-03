"""Bridge operativo per la superficie React dei compensi forensi."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode
from typing import Any, Callable

import re

from pct.motore_preventivo import catalogo_wizard_counts
from pct.tariffario_catalogo import phase_catalog_by_materia, rule_lookup
from web.services.react_tariffario_compute import build_react_tariffario_run_payload


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(
    aid: str,
    label: str,
    href: str,
    tone: str = "neutral",
    *,
    enabled: bool = True,
    legacy_fallback: bool = False,
) -> dict[str, Any]:
    return {
        "id": aid,
        "label": label,
        "href": href,
        "method": "GET",
        "tone": tone,
        "enabled": enabled,
        "legacy_fallback": legacy_fallback,
    }


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _table_rows(
    manager: Any,
    method: str,
    warnings: list[dict[str, str]],
    label: str,
) -> list[dict[str, Any]]:
    try:
        reader = getattr(manager, method, None)
        if callable(reader):
            return [row for row in reader() if isinstance(row, dict)]
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
    return []


def _preventivi_totals(get_preventivi: Callable[[], Any] | None, warnings: list[dict[str, str]]) -> tuple[int, int]:
    if not callable(get_preventivi):
        return 0, 0
    try:
        manager = get_preventivi()
        preventivi = getattr(manager, "tutti_preventivi", lambda: [])()
        conferimenti = getattr(manager, "tutti_conferimenti", lambda: [])()
        return len(list(preventivi)), len(list(conferimenti))
    except Exception as exc:
        warnings.append(_warning("mandato_non_disponibile", f"Archivio mandato non disponibile: {type(exc).__name__}."))
        return 0, 0


def _wizard_sections(warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        catalog = catalogo_wizard_counts()
    except Exception as exc:
        warnings.append(_warning("catalogo_guidato_non_disponibile", "Catalogo guidato non disponibile."))
        return []
    sections: list[dict[str, Any]] = []
    for area, count in catalog.items():
        sections.append(
            _item(
                _text(area).lower().replace(" ", "_") or "area",
                _text(area) or "Area operativa",
                int(count or 0),
                "Percorsi esistenti nel catalogo operativo",
                "primary" if int(count or 0) else "neutral",
            )
        )
    return sections


def _safe_record(row: dict[str, Any], index: int, kind: str = "profili") -> dict[str, Any]:
    title = (_text(row.get("label")) if kind == "regole" else _text(row.get("table_label"))) or _text(row.get("label")) or _text(row.get("materia_label"))
    subtitle = (_text(row.get("summary")) if kind == "regole" else _text(row.get("grado_input_value"))) or _text(row.get("article")) or _text(row.get("description"))
    if kind == "profili" and _text(row.get("summary")):
        # Riverifica 03/11/2026: profili con la stessa tabella (es. Tabella 2 primo grado e appello dal Giudice di Pace)
        # si distinguono solo per il procedimento descritto.
        subtitle = " · ".join(part for part in (subtitle, _text(row.get("summary"))) if part)
    return {
        "id": (_text(row.get("rule_code")) if kind == "regole" else _text(row.get("profile_code"))) or _text(row.get("reference_code")) or f"record_{index}",
        "kind": kind,
        "title": title or "Voce tariffaria",
        "subtitle": subtitle,
        "meta": _text(row.get("materia_label")) or _text(row.get("domains")) or "Dato tariffario",
        "stateLabel": "Disponibile",
        "stateTone": "neutral",
        "href": "/tariffario?" + urlencode({key: value for key, value in {"materia": _text(row.get("materia_label")), "grado": _text(row.get("grado_input_value")), "regola_tariffaria": _text(row.get("rule_code")) if kind == "regole" else ""}.items() if value}),
    }


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "canonical_calculation": "servizi_governati",
        "dm55_calculation": "servizi_governati",
        "migration_report": "artifacts/react-migration/legacy-contracts/compensi-forensi.json",
    }


def _permissions(current_user: Any | None) -> dict[str, bool]:
    can_read = bool(current_user and getattr(current_user, "ha_permesso", lambda _permesso: False)("fatturazione.leggi"))
    can_write = bool(current_user and getattr(current_user, "ha_permesso", lambda _permesso: False)("fatturazione.scrivi"))
    return {
        "canCalculate": can_read,
        "canSaveLog": False,
        "canCreatePreventivo": can_write,
        "canOpenTariffario": can_read,
    }


def _proceedings(regole: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Procedimenti selezionabili: una voce per regola tariffaria, tutte le regole.

    Si usano solo i codici regola (non i codici profilo, che coincidono in parte con
    quelli delle regole e non sono riconosciuti dal motore come regola): ogni voce porta
    con sé tabella e grado corretti. Le etichette uguali nella stessa area si
    distinguono con il grado.
    """
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in regole:
        code = _text(row.get("rule_code"))
        if not code or code in seen:
            continue
        seen.add(code)
        rows.append(
            {
                "value": code,
                "label": _text(row.get("label")) or _text(row.get("table_label")) or "Parametro tariffario",
                "area": _text(row.get("materia_label")),
                "grade": _text(row.get("grado_input_value")),
                "_summary": _text(row.get("summary")).rstrip("."),
            }
        )
    for attempt in ("grade", "_summary"):
        counts: dict[tuple[str, str], int] = {}
        for row in rows:
            counts[(row["area"], row["label"])] = counts.get((row["area"], row["label"]), 0) + 1
        for row in rows:
            extra = row[attempt]
            if counts[(row["area"], row["label"])] > 1 and extra and extra.lower() not in row["label"].lower():
                row["label"] = f"{row['label']} ({extra})"
    for row in rows:
        row.pop("_summary", None)
    return rows


def _parameters(profili: list[dict[str, Any]], regole: list[dict[str, Any]]) -> dict[str, Any]:
    areas = sorted({_text(row.get("materia_label")) for row in profili + regole if _text(row.get("materia_label"))})
    return {
        "areas": [{"value": area, "label": area} for area in areas],
        "proceedings": _proceedings(regole),
        # Il motore conosce quattro livelli di complessità (pct.tariffario.ComplessitaStimata).
        "complexities": [
            {"value": "bassa", "label": "Bassa"},
            {"value": "media", "label": "Media"},
            {"value": "alta", "label": "Alta"},
            {"value": "molto_alta", "label": "Molto alta"},
        ],
        "fiscal_options": {
            "applica_iva": True,
            "applica_cassa": True,
            "applica_ritenuta": False,
        },
    }


def build_react_compensi_forensi_payload(
    *,
    get_normative_tables: Callable[[], Any],
    get_preventivi: Callable[[], Any] | None = None,
    current_user: Any | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    manager: Any | None = None
    try:
        manager = get_normative_tables()
    except Exception as exc:
        warnings.append(_warning("tariffario_non_disponibile", f"Sorgente tariffaria non disponibile: {type(exc).__name__}."))
    profili = _table_rows(manager, "tariffario_profili", warnings, "profili") if manager is not None else []
    regole = _table_rows(manager, "tariffario_regole", warnings, "regole") if manager is not None else []
    audit = _table_rows(manager, "tariffario_audit", warnings, "audit") if manager is not None else []
    preventivi_count, conferimenti_count = _preventivi_totals(get_preventivi, warnings)
    wizard_items = _wizard_sections(warnings)
    parameters = _parameters(profili, regole)
    records = [_safe_record(row, index, "profili") for index, row in enumerate(profili, start=1)]
    records.extend(_safe_record(row, index, "regole") for index, row in enumerate(regole, start=1))

    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "parameters": parameters,
        "areas": parameters["areas"],
        "phases": [],
        "options": parameters["fiscal_options"],
        "last_results": [],
        "actions": {
            **_permissions(current_user),
            "links": [
                _action("tariffario", "Apri tariffario", "/tariffario", "primary"),
                _action("preventivi", "Archivio preventivi", "/preventivi", "neutral"),
                _action("percorso_recupero", "Percorso di recupero", "/compensi-forensi?_legacy=1", "warning", legacy_fallback=True),
            ],
        },
        "metrics": [
            _metric("profili", "Profili tariffari", len(profili), "Letti dalle tabelle normative", "primary"),
            _metric("regole", "Regole disponibili", len(regole), "Catalogo operativo", "info"),
            _metric("preventivi", "Preventivi collegati", preventivi_count, "Archivio mandato", "neutral"),
            _metric("conferimenti", "Conferimenti", conferimenti_count, "Archivio incarichi", "neutral"),
        ],
        "sections": [
            _section("percorsi", "Aree di calcolo disponibili", "percorsi", wizard_items, "Nessun percorso disponibile."),
            _section(
                "presidi",
                "Presidi conservati",
                "Calcolo governato",
                [
                    _item("tariffario", "Tariffario canonico", "governato", "Parametri e risultato arrivano dai controlli operativi", "success"),
                    _item("registro", "Registro tariffario", len(audit), "Righe di controllo disponibili", "info" if audit else "neutral"),
                ],
                "Nessun presidio rilevato.",
            ),
        ],
        "records": records,
        "warnings": warnings,
    }


def _validation_error(message: str, errors: dict[str, str], status: int = 400) -> tuple[dict[str, Any], int]:
    return {"ok": False, "message": message, "errors": errors, "result": None, "warnings": []}, status


def _audit(get_utenti: Callable[[], Any] | None, current_user: Any, resource_id: str, ip: str) -> None:
    if not callable(get_utenti):
        return
    try:
        get_utenti().registra_evento(
            "compensi_forensi.calcola",
            id_utente=_text(getattr(current_user, "id", "")),
            username=_text(getattr(current_user, "username", "")),
            risorsa_tipo="compenso_forense",
            risorsa_id=resource_id,
            dettagli="Calcolo eseguito via API JSON React.",
            ip=ip,
        )
    except Exception:
        pass


def _phase_key(value: str) -> str:
    text = _text(value).lower().replace("’", "'")
    text = re.sub(r"^fase\s+(?:di|della|dello|del|dell')?\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _fasi_richieste(area: str, payload: dict[str, Any]) -> tuple[list[str], str]:
    """Riconosce le fasi indicate a testo; una fase sconosciuta non si ignora in silenzio."""
    raw = payload.get("fasi") or ([payload.get("fase")] if _text(payload.get("fase")) else [])
    if not isinstance(raw, list):
        raw = [raw]
    catalog = phase_catalog_by_materia().get(area) or []
    if not raw:
        return [], ""
    if not catalog:
        return [_text(item) for item in raw if _text(item)], ""
    chosen: list[str] = []
    for item in raw:
        wanted = _phase_key(item)
        if not wanted:
            continue
        exact = [row["value"] for row in catalog if wanted in {_phase_key(row["value"]), _phase_key(row["label"])}]
        partial = [row["value"] for row in catalog if len(wanted) >= 4 and _phase_key(row["value"]).startswith(wanted)]
        found = exact or (partial if len(partial) == 1 else [])
        if not found:
            ammesse = ", ".join(row["label"] for row in catalog)
            return [], f"Fase «{_text(item)}» non prevista per quest'area. Fasi ammesse: {ammesse}."
        if found[0] not in chosen:
            chosen.append(found[0])
    return chosen, ""


def calculate_react_compensi_forensi(
    *,
    get_normative_tables: Callable[[], Any],
    get_utenti: Callable[[], Any] | None,
    current_user: Any,
    payload: dict[str, Any],
    ip_address: str,
) -> tuple[dict[str, Any], int]:
    allowed = {
        "area",
        "procedimento",
        "fase",
        "fasi",
        "valore_controversia",
        "complessita",
        "aumenti",
        "riduzioni",
        "opzioni_fiscali",
    }
    forbidden = {"totale", "risultato", "compenso_calcolato", "iva", "cassa", "ritenuta"}
    unknown = sorted(set(payload) - allowed)
    blocked = sorted(set(payload) & forbidden)
    if unknown or blocked:
        errors = {key: "Campo non ammesso come fonte canonica." for key in unknown + blocked}
        return _validation_error("Payload calcolo non valido.", errors)
    area = _text(payload.get("area"))
    value = _text(payload.get("valore_controversia")) or "0"
    if not area:
        return _validation_error("Seleziona l'area del calcolo.", {"area": "Campo obbligatorio."})
    procedimento = _text(payload.get("procedimento"))
    if procedimento:
        regola = rule_lookup(procedimento)
        if not regola or _text(regola.get("materia_label")) != area:
            return _validation_error(
                "Il procedimento scelto non appartiene all'area indicata: sceglilo di nuovo.",
                {"procedimento": "Procedimento non coerente con l'area."},
            )
    fasi, fase_error = _fasi_richieste(area, payload)
    if fase_error:
        return _validation_error(fase_error, {"fase": "Fase non riconosciuta."})
    calc_payload = {
        "materia": area,
        "regola_tariffaria": procedimento,
        "valore": value,
        "complessita": _text(payload.get("complessita")) or "media",
        "fasi": fasi,
        "spese_generali": True,
        "bonus_telematico": False,
    }
    result = build_react_tariffario_run_payload(calc_payload, get_normative_tables=get_normative_tables)
    warnings = [row for row in result.get("warnings", []) if isinstance(row, dict)]
    if not result.get("ok") or not result.get("result"):
        return {
            "ok": False,
            "message": "Calcolo non completato.",
            "errors": {"_form": "Verifica i parametri indicati."},
            "result": None,
            "warnings": warnings,
        }, 400
    _audit(get_utenti, current_user, _text(result.get("result", {}).get("ruleCode")) or area, ip_address)
    return {
        "ok": True,
        "message": "Calcolo eseguito.",
        "errors": {},
        "result": result.get("result"),
        "warnings": warnings,
    }, 200


def save_react_compensi_log(*, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return _validation_error(
        "Salvataggio log non disponibile nella configurazione corrente.",
        {"unsupported": "Azione non disponibile."},
        status=409,
    )


def create_react_preventivo_from_compenso(*, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return _validation_error(
        "Creazione preventivo diretta dai compensi non disponibile nella configurazione corrente.",
        {"unsupported": "Usa il flusso /preventivi/nuovo con dati controllati."},
        status=409,
    )


def build_react_compensi_forensi_error_payload(message: str = "Compensi forensi non disponibili.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "parameters": {},
        "areas": [],
        "phases": [],
        "options": {},
        "last_results": [],
        "actions": {
            **_permissions(None),
            "links": [_action("percorso_recupero", "Percorso di recupero", "/compensi-forensi?_legacy=1", "warning", enabled=False, legacy_fallback=True)],
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "warnings": [_warning("compensi_errore_controllato", message)],
    }
