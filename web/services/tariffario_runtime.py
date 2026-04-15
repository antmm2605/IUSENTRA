"""Support helpers for the tariffario route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pct.tariffario import Fase, Grado, parse_numero_locale


def parse_float(value: Any, default: float = 0.0) -> float:
    """Parse localised numeric input used by the tariffario form."""

    return parse_numero_locale(value, default)


def fase_key_from_value(fase_value: str) -> str:
    mapping = {
        Fase.STUDIO.value: "studio",
        Fase.INTRODUTTIVA.value: "introduttiva",
        Fase.ISTRUTTORIA.value: "istruttoria",
        Fase.DECISIONALE.value: "decisionale",
        Fase.ESECUTIVA.value: "esecutiva",
        Fase.ATTIVAZIONE.value: "attivazione",
        Fase.RIVITALIZZAZIONE.value: "rivitalizzazione",
        Fase.NEGOZIAZIONE_TRATTAZIONE.value: "negoziazione",
        Fase.CONCILIAZIONE.value: "conciliazione",
        "Compenso unico": "compenso_unico",
    }
    return mapping.get(fase_value, fase_value)


def fase_value_from_key(fase_key: str) -> str:
    mapping = {
        "studio": Fase.STUDIO.value,
        "introduttiva": Fase.INTRODUTTIVA.value,
        "istruttoria": Fase.ISTRUTTORIA.value,
        "decisionale": Fase.DECISIONALE.value,
        "esecutiva": Fase.ESECUTIVA.value,
        "attivazione": Fase.ATTIVAZIONE.value,
        "rivitalizzazione": Fase.RIVITALIZZAZIONE.value,
        "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE.value,
        "conciliazione": Fase.CONCILIAZIONE.value,
        "compenso_unico": "Compenso unico",
    }
    return mapping.get(fase_key, fase_key)


def variation_policy_for(tipo_pratica: Any) -> dict[str, Any]:
    if not tipo_pratica:
        return {}
    return dict(getattr(tipo_pratica, "variation_policy", {}) or {})


def variation_keys_for(tipo_pratica: Any) -> list[str]:
    policy = variation_policy_for(tipo_pratica)
    return [
        str(item.get("key"))
        for item in policy.get("phase_controls", []) or []
        if str(item.get("key") or "").strip()
    ]


def variazioni_fasi_da_form(form: Any, tipo_pratica: Any) -> dict[str, float]:
    rows: dict[str, float] = {}
    for key in variation_keys_for(tipo_pratica):
        raw = (form.get(f"var_{key}") or "").strip()
        if not raw:
            continue
        rows[fase_value_from_key(key)] = 1.0 + (parse_float(raw, 0.0) / 100.0)
    return rows


def maggiorazioni_adr_da_form(form: Any, tipo_pratica: Any) -> dict[str, float]:
    if form.get("adr_accordo") != "1":
        return {}
    policy = variation_policy_for(tipo_pratica)
    agreement_bonus = dict(policy.get("agreement_bonus", {}) or {})
    if not agreement_bonus.get("enabled"):
        return {}
    pct = parse_float(agreement_bonus.get("pct", 0), 0.0)
    if pct <= 0:
        return {}
    multiplier = 1.0 + (pct / 100.0)
    rows: dict[str, float] = {}
    for key in agreement_bonus.get("phase_keys", []) or []:
        rows[fase_value_from_key(str(key))] = multiplier
    return rows


def variazioni_prefill_from_form(form: Any) -> dict[str, str]:
    rows: dict[str, str] = {}
    for key in ("attivazione", "rivitalizzazione", "negoziazione", "conciliazione"):
        raw = (form.get(f"var_{key}") or "").strip()
        if raw:
            rows[key] = raw
    return rows


def preferred_grade(gradi: list[str]) -> str:
    ordine = [
        "Tribunale",
        "Giudice competente",
        "Giudice tutelare",
        "GIP / GUP",
        "Tribunale monocratico",
        "Tribunale collegiale",
        "Corte d'Assise",
        "Magistrato di Sorveglianza",
        "Fuori giudizio",
        "Procedura ADR",
        "TAR",
        "Corte dei Conti",
        "Conservatoria / tavolare",
        "Tribunale concorsuale",
        "CGT di primo grado",
        "Giudice di Pace",
        "Corte d'Appello",
        "Corte d'Appello penale",
        "Corte d'Assise d'Appello",
        "Corte di Cassazione",
        "Tribunale di Sorveglianza",
        "Corte cost. / Corte europea / CGUE",
        "Consiglio di Stato",
        "CGT di secondo grado",
    ]
    for voce in ordine:
        if voce in gradi:
            return voce
    return gradi[0] if gradi else Grado.TRIBUNALE.value


def esborsi_catalogo(
    tipo_pratica: Any,
    accessori_ids: list[str],
    *,
    get_tipo_pratica: Callable[[str], Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not tipo_pratica:
        return rows
    for index, item in enumerate(tipo_pratica.esborsi_tipici or []):
        rows.append(
            {
                "key": f"{tipo_pratica.id}:{index}",
                "descrizione": item.get("descrizione", ""),
                "importo": float(item.get("importo", 0) or 0),
                "source": tipo_pratica.id,
            }
        )
    accessori_map = {item.get("id"): item for item in tipo_pratica.accessori_calcolo or []}
    for accessorio_id in accessori_ids:
        accessorio = accessori_map.get(accessorio_id)
        if not accessorio:
            continue
        tipo_pratica_accessorio = get_tipo_pratica(accessorio.get("tipo_pratica_id", ""))
        if not tipo_pratica_accessorio:
            continue
        for index, item in enumerate(tipo_pratica_accessorio.esborsi_tipici or []):
            rows.append(
                {
                    "key": f"{accessorio_id}:{index}",
                    "descrizione": item.get("descrizione", ""),
                    "importo": float(item.get("importo", 0) or 0),
                    "source": accessorio_id,
                }
            )
    return rows


def manual_rows_from_form(form: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    descrizioni = form.getlist("manual_descr[]")
    importi = form.getlist("manual_importo[]")
    tipi = form.getlist("manual_tipo[]")
    for descrizione, importo, tipo in zip(descrizioni, importi, tipi):
        descrizione = (descrizione or "").strip()
        if not descrizione:
            continue
        rows.append(
            {
                "descrizione": descrizione,
                "tipo": (tipo or "Onorario").strip() or "Onorario",
                "importo": round(parse_float(importo, 0.0), 2),
            }
        )
    return rows
