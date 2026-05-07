"""Calcolo operativo per la console React del tariffario."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from flask import url_for

from pct.economico_context import costruisci_contesto_economico, dump_log_calcolo
from pct.motore_preventivo import get_tipo_pratica, motore_calcola
from pct.tariffario import (
    ComplessitaStimata,
    Fase,
    Grado,
    LivelloCompenso,
    Materia,
    calcola_compenso,
    livello_compenso_da_complessita,
)
from pct.tariffario_catalogo import (
    first_profile_for_materia,
    grade_catalog_by_materia,
    phase_catalog_by_materia,
    profile_lookup_by_labels,
    profile_lookup_by_rule,
    rule_lookup,
)
from web.services.mediazione_dm150_runtime import (
    calcola_mediazione_odm_da_context,
    is_mediazione_practice,
    mediazione_odm_context_for_prefill,
)
from web.services.tariffario_runtime import (
    esborsi_catalogo,
    maggiorazioni_adr_da_form,
    parse_float,
    preferred_grade,
    variazioni_fasi_da_form,
    variazioni_prefill_from_form,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    rendered = str(value or "").strip()
    return rendered or fallback


def _euro(value: Any, *, signed: bool = False) -> str:
    amount = float(value or 0.0)
    rendered = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    prefix = "+ " if signed and amount >= 0 else ""
    return f"{prefix}EUR {rendered}"


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


class _PayloadForm:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload or {}

    def _raw(self, key: str) -> Any:
        if key in self._payload:
            return self._payload[key]
        if key.endswith("[]"):
            return self._payload.get(key[:-2])
        return None

    def get(self, key: str, default: Any = "") -> Any:
        raw = self._raw(key)
        if raw is None:
            return default
        if isinstance(raw, list):
            return raw[0] if raw else default
        if isinstance(raw, bool):
            return "1" if raw else "0"
        return raw

    def getlist(self, key: str) -> list[str]:
        raw = self._raw(key)
        if raw is None:
            return []
        if isinstance(raw, list):
            return [_text(item) for item in raw if _text(item)]
        if isinstance(raw, bool):
            return ["1"] if raw else []
        rendered = _text(raw)
        if not rendered:
            return []
        if "," in rendered and key not in {"valore", "perc_spese_generali"}:
            return [part.strip() for part in rendered.split(",") if part.strip()]
        return [rendered]


def _switch_from_payload(payload: dict[str, Any], key: str, *, default: bool = False) -> bool:
    values = _PayloadForm(payload).getlist(key)
    if values:
        normalized = [value.strip().lower() for value in values]
        if any(value in {"1", "true", "on", "si", "s", "yes"} for value in normalized):
            return True
        if any(value in {"0", "false", "off", "no"} for value in normalized):
            return False
    raw = _text(payload.get(key)).lower()
    if raw in {"1", "true", "on", "si", "s", "yes"}:
        return True
    if raw in {"0", "false", "off", "no"}:
        return False
    return default


def _table_rows(
    get_normative_tables: Callable[[], Any],
    method: str,
    warnings: list[dict[str, str]],
    label: str,
) -> list[dict[str, Any]]:
    try:
        manager = get_normative_tables()
        reader = getattr(manager, method, None)
        if callable(reader):
            return [row for row in reader() if isinstance(row, dict)]
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
    return []


def _manual_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_rows = payload.get("manual_lines")
    if isinstance(raw_rows, list):
        for index, raw in enumerate(raw_rows, start=1):
            if not isinstance(raw, dict):
                continue
            descrizione = _text(raw.get("descrizione"))
            if not descrizione or raw.get("inclusa") is False:
                continue
            rows.append(
                {
                    "id": _text(raw.get("id")) or f"manuale_{index}",
                    "descrizione": descrizione,
                    "tipo": _text(raw.get("tipo"), "Onorario"),
                    "importo": round(parse_float(raw.get("importo"), 0.0), 2),
                    "fiscale": _text(raw.get("fiscale"), "imponibile"),
                    "inclusa": True,
                }
            )
        return rows
    form = _PayloadForm(payload)
    for index, (descrizione, importo, tipo) in enumerate(
        zip(form.getlist("manual_descr[]"), form.getlist("manual_importo[]"), form.getlist("manual_tipo[]")),
        start=1,
    ):
        if not _text(descrizione):
            continue
        rows.append(
            {
                "id": f"manuale_{index}",
                "descrizione": _text(descrizione),
                "tipo": _text(tipo, "Onorario"),
                "importo": round(parse_float(importo, 0.0), 2),
                "fiscale": "imponibile",
                "inclusa": True,
            }
        )
    return rows


def _default_state(
    *,
    payload: dict[str, Any],
    phase_catalog: dict[str, list[dict[str, Any]]],
    grade_catalog: dict[str, list[str]],
) -> dict[str, Any]:
    materie = [m.value for m in Materia]
    materia_sel = _text(payload.get("materia")) or (materie[0] if materie else "")
    regola_sel = _text(payload.get("regola_tariffaria"))
    regola_attiva = rule_lookup(regola_sel) if regola_sel else None
    profilo_default = first_profile_for_materia(materia_sel)
    grade_defaults = grade_catalog.get(materia_sel) or [Grado.TRIBUNALE.value]
    grado_sel = (
        _text(payload.get("grado"))
        or _text((regola_attiva or {}).get("grado_input_value"))
        or _text((profilo_default or {}).get("grado_input_value"))
        or preferred_grade(grade_defaults)
    )
    if grado_sel not in grade_defaults:
        grado_sel = preferred_grade(grade_defaults)
    complessita_sel = _text(payload.get("complessita"), ComplessitaStimata.MEDIA.value)
    if complessita_sel not in {item.value for item in ComplessitaStimata}:
        complessita_sel = ComplessitaStimata.MEDIA.value
    fasi = _PayloadForm(payload).getlist("fasi")
    valid_phases = phase_catalog.get(materia_sel) or []
    if not fasi:
        fasi = [_text(item.get("value")) for item in valid_phases if _text(item.get("value"))]
    state = {
        "materia": materia_sel,
        "regola_tariffaria": regola_sel,
        "grado": grado_sel,
        "valore": _text(payload.get("valore"), "0"),
        "complessita": complessita_sel,
        "fasi": fasi,
        "compenso_unico": _switch_from_payload(payload, "compenso_unico", default=True),
        "spese_generali": _switch_from_payload(payload, "spese_generali", default=True),
        "bonus_telematico": _switch_from_payload(payload, "bonus_telematico"),
        "perc_spese_generali": _text(payload.get("perc_spese_generali"), "15"),
        "accessori": _PayloadForm(payload).getlist("accessori"),
        "esborsi": _PayloadForm(payload).getlist("esborsi"),
        "adr_accordo": _switch_from_payload(payload, "adr_accordo"),
        "mediazione_odm_attiva": _switch_from_payload(payload, "mediazione_odm_attiva"),
        "mediazione_odm_regime": _text(payload.get("mediazione_odm_regime"), "volontaria"),
        "mediazione_odm_esito": _text(payload.get("mediazione_odm_esito"), "primo_incontro_senza_accordo"),
        "mediazione_odm_art31_maggiorazione_20": _switch_from_payload(payload, "mediazione_odm_art31_maggiorazione_20"),
        "manual_lines": _manual_rows_from_payload(payload),
    }
    for key, value in (payload or {}).items():
        rendered_key = _text(key)
        if rendered_key.startswith("var_"):
            state[rendered_key] = _text(value)
    return state


def _active_profile(state: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Any | None]:
    regola = rule_lookup(state.get("regola_tariffaria", "")) if state.get("regola_tariffaria") else None
    profilo = (
        profile_lookup_by_rule(state.get("regola_tariffaria", ""), state.get("grado", ""))
        or profile_lookup_by_labels(state.get("materia", ""), state.get("grado", ""))
        or first_profile_for_materia(state.get("materia", ""))
    )
    pratica = get_tipo_pratica((regola or {}).get("suggested_practice_id", "")) if regola else None
    if not pratica and profilo:
        pratica = get_tipo_pratica(profilo.get("suggested_practice_id", ""))
    return profilo, regola, pratica


def _dynamic_options(
    *,
    state: dict[str, Any],
    pratica: Any | None,
    phase_catalog: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    accessori = [dict(item) for item in (getattr(pratica, "accessori_calcolo", []) or [])] if pratica else []
    expenses = esborsi_catalogo(pratica, state.get("accessori", []), get_tipo_pratica=get_tipo_pratica)
    mediazione_targets: list[str] = []
    mediazione_eligible_targets: list[str] = []
    selected_accessori = set(state.get("accessori", []))
    variation_policies: list[dict[str, Any]] = []
    if pratica and is_mediazione_practice(pratica):
        mediazione_targets.append(getattr(pratica, "id", "mediazione"))
        mediazione_eligible_targets.append(getattr(pratica, "id", "mediazione"))
        variation_policies.append(dict(getattr(pratica, "variation_policy", {}) or {}))
    for accessorio in accessori:
        target = get_tipo_pratica(accessorio.get("tipo_pratica_id", ""))
        if target and is_mediazione_practice(target):
            target_id = accessorio.get("id") or getattr(target, "id", "mediazione")
            mediazione_eligible_targets.append(target_id)
            if target_id in selected_accessori:
                mediazione_targets.append(target_id)
                variation_policies.append(dict(getattr(target, "variation_policy", {}) or {}))
    if not variation_policies and pratica:
        variation_policies.append(dict(getattr(pratica, "variation_policy", {}) or {}))
    variation_policy = _merge_variation_policies(variation_policies)
    return {
        "phaseOptions": phase_catalog.get(state.get("materia", ""), []),
        "accessori": accessori,
        "expenseOptions": [
            {
                "key": _text(item.get("key")),
                "descrizione": _text(item.get("descrizione")),
                "importo": float(item.get("importo") or 0.0),
                "importo_label": _euro(item.get("importo") or 0.0),
                "source": _text(item.get("source")),
            }
            for item in expenses
        ],
        "variationPolicy": variation_policy,
        "mediazioneEnabled": bool(mediazione_targets),
        "mediazioneTargets": mediazione_targets,
        "mediazioneEligible": bool(mediazione_eligible_targets),
        "mediazioneEligibleTargets": mediazione_eligible_targets,
        "manualTypes": ["Onorario", "Spesa viva", "Anticipazione art. 15", "Spesa forfettaria"],
        "fiscalTypes": ["imponibile", "esente", "anticipazione art. 15"],
    }


def _merge_variation_policies(policies: list[dict[str, Any]]) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []
    seen_controls: set[str] = set()
    references: list[str] = []
    agreement_bonus: dict[str, Any] = {}
    for policy in policies:
        if not policy:
            continue
        for control in policy.get("phase_controls", []) or []:
            if not isinstance(control, dict):
                continue
            key = _text(control.get("key"))
            if not key or key in seen_controls:
                continue
            seen_controls.add(key)
            controls.append(dict(control))
        current_bonus = dict(policy.get("agreement_bonus", {}) or {})
        if current_bonus.get("enabled"):
            phase_keys = list(agreement_bonus.get("phase_keys") or [])
            for key in current_bonus.get("phase_keys", []) or []:
                if key not in phase_keys:
                    phase_keys.append(key)
            agreement_bonus = {
                **current_bonus,
                "enabled": True,
                "phase_keys": phase_keys,
                "pct": max(float(agreement_bonus.get("pct") or 0.0), float(current_bonus.get("pct") or 0.0)),
            }
        for ref in policy.get("references", []) or []:
            rendered = _text(ref)
            if rendered and rendered not in references:
                references.append(rendered)
    if not controls and not agreement_bonus:
        return {}
    return {
        "kind": "adr_pm50_con_accordo",
        "range_pct": {"min": -50, "max": 50, "default": 0},
        "phase_controls": controls,
        "agreement_bonus": agreement_bonus,
        "references": references,
    }


def _table_payload(risultato: Any, selected: str) -> dict[str, Any]:
    columns = [
        {"id": LivelloCompenso.MINIMO.value, "label": "MINIMO"},
        {"id": LivelloCompenso.BASE.value, "label": "BASE"},
        {"id": LivelloCompenso.MASSIMO.value, "label": "MASSIMO"},
    ]
    rows: list[dict[str, Any]] = []
    for fase, values in risultato.dettaglio.items():
        rows.append(
            {
                "id": _text(fase).lower().replace(" ", "_").replace("/", "_"),
                "label": fase,
                "kind": "phase",
                "values": {
                    LivelloCompenso.MINIMO.value: _euro(values[0]),
                    LivelloCompenso.BASE.value: _euro(values[1]),
                    LivelloCompenso.MASSIMO.value: _euro(values[2]),
                },
            }
        )
    rows.append(
        {
            "id": "subtotale_onorari",
            "label": "Subtotale onorari",
            "kind": "subtotal",
            "values": {
                level.value: _euro(risultato.subtotale_livello(level.value))
                for level in (LivelloCompenso.MINIMO, LivelloCompenso.BASE, LivelloCompenso.MASSIMO)
            },
        }
    )
    if risultato.bonus_telematico_attivo:
        rows.append(
            {
                "id": "bonus_telematico",
                "label": "Bonus telematico 30%",
                "kind": "adjustment",
                "values": {
                    level.value: _euro(risultato.bonus_telematico_livello(level.value), signed=True)
                    for level in (LivelloCompenso.MINIMO, LivelloCompenso.BASE, LivelloCompenso.MASSIMO)
                },
            }
        )
    if risultato.includi_spese_generali:
        label = f"Spese generali {int(round(float(risultato.perc_spese_generali or 0) * 100))}%"
        rows.append(
            {
                "id": "spese_generali",
                "label": label,
                "kind": "expense",
                "values": {
                    level.value: _euro(risultato.spese_generali_livello(level.value), signed=True)
                    for level in (LivelloCompenso.MINIMO, LivelloCompenso.BASE, LivelloCompenso.MASSIMO)
                },
            }
        )
    rows.append(
        {
            "id": "totale_compenso",
            "label": "Totale compenso",
            "kind": "total",
            "values": {
                level.value: _euro(risultato.totale_compenso_livello(level.value))
                for level in (LivelloCompenso.MINIMO, LivelloCompenso.BASE, LivelloCompenso.MASSIMO)
            },
        }
    )
    return {"columns": columns, "rows": rows, "selected": selected}


def _included_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": _text(row.get("fonte")) or f"voce_{index}",
            "descrizione": _text(row.get("descrizione")),
            "tipo": _text(row.get("tipo"), "Voce"),
            "importo": float(row.get("importo") or 0.0),
            "importo_label": _euro(row.get("importo") or 0.0),
            "fiscale": _text(row.get("fiscale"), "imponibile"),
        }
        for index, row in enumerate(rows, start=1)
    ]


def _economic_payload(summary: dict[str, Any] | None) -> dict[str, Any]:
    values = summary or {"imponibile": 0.0, "cassa": 0.0, "iva": 0.0, "anticipazioni_art15": 0.0, "totale": 0.0}
    return {
        "rows": [
            {"id": "imponibile", "label": "Imponibile complessivo", "value": _euro(values.get("imponibile"))},
            {"id": "cpa", "label": "CPA 4%", "value": _euro(values.get("cassa"))},
            {"id": "iva", "label": "IVA 22%", "value": _euro(values.get("iva"))},
            {"id": "anticipazioni_art15", "label": "Anticipazioni art. 15", "value": _euro(values.get("anticipazioni_art15"))},
            {"id": "totale", "label": "Totale fattura teorica", "value": _euro(values.get("totale")), "tone": "primary"},
        ],
        "total": _euro(values.get("totale")),
        "base": _euro(values.get("imponibile")),
    }


def _profile_payload(profilo: dict[str, Any] | None, pratica: Any | None, state: dict[str, Any]) -> dict[str, Any]:
    profilo = profilo or {}
    badges = [
        _text(profilo.get("table_label"), "Tabella tariffaria"),
        _text(profilo.get("label"), _text(profilo.get("materia_label"), state.get("materia", ""))),
        "snapshot ufficiale" if profilo.get("exact_snapshot") else "integrazione controllata",
    ]
    return {
        "title": _text(profilo.get("summary"), "Profilo tariffario operativo."),
        "description": _text(profilo.get("base_note"), "Calcolo con valore della controversia e fasi selezionabili."),
        "when": _text(getattr(pratica, "when_to_use", ""), _text(profilo.get("description"), "")),
        "badges": [badge for badge in badges if badge],
        "metadata": [
            {"label": "Pratica suggerita", "value": _text(getattr(pratica, "label", ""), _text(profilo.get("suggested_practice_id"), "-"))},
            {"label": "Grado operativo", "value": _text(profilo.get("grado_input_value"), state.get("grado", ""))},
        ],
        "practiceId": _text(profilo.get("suggested_practice_id")),
        "profileCode": _text(profilo.get("profile_code")),
    }


def _actions_for_result(
    *,
    risultato: Any,
    profilo: dict[str, Any] | None,
    regola: dict[str, Any] | None,
    pratica: Any | None,
    state: dict[str, Any],
    selected: str,
    manual_rows: list[dict[str, Any]],
    included_rows: list[dict[str, Any]],
    economic: dict[str, Any],
    references: list[dict[str, Any]],
) -> dict[str, str]:
    if not risultato or not profilo:
        return {"preventivo": "", "parcella": ""}
    manual_voci_json = json.dumps(manual_rows, ensure_ascii=False)
    esborsi_json = json.dumps(state.get("esborsi", []), ensure_ascii=False)
    accessori_json = json.dumps(state.get("accessori", []), ensure_ascii=False)
    variazioni = variazioni_prefill_from_form(_PayloadForm(state))
    mediazione_context = mediazione_odm_context_for_prefill(_PayloadForm(state))
    wizard_params = {
        "id_pratica": profilo.get("suggested_practice_id", ""),
        "area": getattr(pratica, "area", state.get("materia", "")) if pratica else state.get("materia", ""),
        "valore": state.get("valore", "0") or "0",
        "grado": state.get("grado", ""),
        "regola_tariffaria": state.get("regola_tariffaria", ""),
        "complessita": state.get("complessita", ""),
        "fasi": ",".join(state.get("fasi", [])),
        "bonus_telematico": "1" if state.get("bonus_telematico") else "0",
        "spese_generali": "1" if state.get("spese_generali") else "0",
        "perc_spese_generali": _text(state.get("perc_spese_generali"), "15"),
        "mediazione_odm_attiva": "1" if mediazione_context.get("attiva") else "0",
        "mediazione_odm_regime": mediazione_context.get("regime") or "",
        "mediazione_odm_esito": mediazione_context.get("esito") or "",
        "mediazione_odm_art31_maggiorazione_20": "1" if mediazione_context.get("art31_comma3_maggiorazione_20") else "0",
        "applica_cpa": "1",
        "applica_iva": "1",
        "anticipazioni": "0",
        "adr_accordo": "1" if state.get("adr_accordo") else "0",
        "accessori_json": accessori_json,
        "esborsi_json": esborsi_json,
        "manual_voci_json": manual_voci_json,
        "auto_calcola": "1",
        "entry": "tariffario",
    }
    for key, raw_value in variazioni.items():
        wizard_params[f"var_{key}"] = raw_value
    try:
        preventivo = url_for("preventivi.wizard", **wizard_params)
    except Exception:
        preventivo = "/preventivi/wizard"
    voci_parcella = [
        {"descrizione": row.get("descrizione", ""), "quantita": 1, "prezzo_unitario": f"{float(row.get('importo') or 0.0):.2f}"}
        for row in included_rows
    ]
    log_parcella = dump_log_calcolo(
        costruisci_contesto_economico(
            source="tariffario_forense",
            source_label="Tariffario forense",
            oggetto=getattr(pratica, "label", "") if pratica else "",
            id_pratica=profilo.get("suggested_practice_id", ""),
            pratica_label=getattr(pratica, "label", "") if pratica else profilo.get("label", ""),
            area_pratica=getattr(pratica, "area", state.get("materia", "")) if pratica else state.get("materia", ""),
            tipo_compenso=getattr(pratica, "tipo_compenso_default", "") if pratica else "Per fasi processuali (D.M. 55/2014)",
            tipo_procedimento=profilo.get("label", ""),
            grado_sede=state.get("grado", ""),
            regola_tariffaria=(regola.get("rule_label", "") if regola else state.get("regola_tariffaria", "")),
            regola_tariffaria_code=(regola.get("rule_code", "") if regola else state.get("regola_tariffaria", "")),
            complessita=state.get("complessita", ""),
            valore_controversia=state.get("valore", "0") or "0",
            bonus_telematico=bool(state.get("bonus_telematico")),
            spese_generali=bool(state.get("spese_generali")),
            perc_spese_generali=parse_float(state.get("perc_spese_generali"), 15.0),
            applica_cpa=True,
            applica_iva=True,
            anticipazioni_art15=float(economic.get("anticipazioni_art15") or 0.0),
            adr_accordo=bool(state.get("adr_accordo")),
            variazioni_fasi_pct=variazioni,
            accessori=state.get("accessori", []),
            esborsi=state.get("esborsi", []),
            manual_voci=manual_rows,
            risultato={
                "scaglione": risultato.scaglione,
                "onorario_base": risultato.totale_compenso_livello(selected),
                "cpa": economic.get("cassa", 0.0),
                "iva": economic.get("iva", 0.0),
                "totale": economic.get("totale", 0.0),
                "nota": risultato.note,
            },
            audit_tariffario=risultato.to_dict().get("audit_tariffario") or regola,
            riferimenti_normativi=risultato.to_dict().get("riferimenti_normativi") or [row.get("title", "") for row in references[:4]],
        )
    )
    try:
        parcella = url_for(
            "fatturazione.nuova",
            voci_json=json.dumps(voci_parcella, ensure_ascii=False),
            note=risultato.note,
            applica_cassa="1",
            applica_iva="1",
            origine="tariffario",
            id_pratica=profilo.get("suggested_practice_id", ""),
            area_pratica=getattr(pratica, "area", state.get("materia", "")) if pratica else state.get("materia", ""),
            tipo_compenso=getattr(pratica, "tipo_compenso_default", "") if pratica else "Per fasi processuali (D.M. 55/2014)",
            tipo_procedimento=profilo.get("label", ""),
            valore_controversia=state.get("valore", "0") or "0",
            complessita=state.get("complessita", ""),
            log_calcolo=log_parcella,
        )
    except Exception:
        parcella = "/fatturazione/nuova"
    return {"preventivo": preventivo, "parcella": parcella}


def _run_engine(
    *,
    state: dict[str, Any],
    profilo: dict[str, Any] | None,
    regola: dict[str, Any] | None,
    pratica: Any | None,
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    form = _PayloadForm(state)
    materia = Materia(state.get("materia", ""))
    grado = Grado(state.get("grado", ""))
    valore = parse_float(state.get("valore"), 0.0)
    complessita = state.get("complessita") or ComplessitaStimata.MEDIA.value
    selected = livello_compenso_da_complessita(complessita).value
    fasi: list[Fase] = []
    for fase_val in state.get("fasi", []):
        try:
            fasi.append(Fase(fase_val))
        except ValueError:
            continue
    if not fasi:
        fasi = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.ISTRUTTORIA, Fase.DECISIONALE]
    perc_spese = parse_float(state.get("perc_spese_generali"), 15.0)
    risultato = calcola_compenso(
        materia,
        grado,
        valore,
        fasi,
        profile_code=(profilo or {}).get("profile_code", ""),
        bonus_telematico=bool(state.get("bonus_telematico")),
        includi_spese_generali=bool(state.get("spese_generali")),
        perc_spese_generali=max(0.0, perc_spese / 100.0),
        variazioni_fasi=variazioni_fasi_da_form(form, pratica) or None,
        maggiorazioni_fasi=maggiorazioni_adr_da_form(form, pratica) or None,
        complessita=complessita,
    )
    included: list[dict[str, Any]] = [
        {
            "descrizione": f"Compenso professionale per {(profilo or {}).get('table_label', state.get('materia', ''))} - {risultato.scaglione}",
            "tipo": "Onorario",
            "importo": risultato.totale_compenso_livello(selected),
            "fonte": "principale",
            "fiscale": "imponibile",
        }
    ]
    mediazione_context = mediazione_odm_context_for_prefill(form)
    mediazione_target_calcolato = False
    if pratica and is_mediazione_practice(pratica):
        mediazione_target_calcolato = True
        mediazione_odm = calcola_mediazione_odm_da_context(valore, mediazione_context)
        if mediazione_odm:
            included.append(
                {
                    "descrizione": mediazione_odm.get("voce_label") or "Costi organismo mediazione D.M. 150/2023",
                    "tipo": "Spesa viva",
                    "importo": float(mediazione_odm.get("totale_organismo") or 0.0),
                    "fonte": "mediazione_odm:principale",
                    "fiscale": "anticipazione_art15",
                }
            )
    accessori = {item.get("id"): item for item in (getattr(pratica, "accessori_calcolo", []) or [])} if pratica else {}
    phase_key_map = {
        "studio": Fase.STUDIO,
        "introduttiva": Fase.INTRODUTTIVA,
        "istruttoria": Fase.ISTRUTTORIA,
        "decisionale": Fase.DECISIONALE,
        "esecutiva": Fase.ESECUTIVA,
        "attivazione": Fase.ATTIVAZIONE,
        "rivitalizzazione": Fase.RIVITALIZZAZIONE,
        "negoziazione": Fase.NEGOZIAZIONE_TRATTAZIONE,
        "conciliazione": Fase.CONCILIAZIONE,
    }
    for accessorio_id in state.get("accessori", []):
        accessorio = accessori.get(accessorio_id)
        if not accessorio:
            continue
        tp_accessorio = get_tipo_pratica(accessorio.get("tipo_pratica_id", ""))
        fasi_accessorio = [phase_key_map[key] for key in accessorio.get("fasi_default_keys", []) if key in phase_key_map] or None
        ris_accessorio = motore_calcola(
            id_pratica=accessorio.get("tipo_pratica_id", ""),
            valore_controversia=valore,
            livello_compenso=selected,
            complessita=complessita,
            bonus_telematico=bool(state.get("bonus_telematico")),
            includi_spese_generali=bool(state.get("spese_generali")),
            perc_spese_generali=max(0.0, perc_spese / 100.0),
            variazioni_fasi=variazioni_fasi_da_form(form, tp_accessorio) or None,
            maggiorazioni_fasi=maggiorazioni_adr_da_form(form, tp_accessorio) or None,
            fasi=fasi_accessorio,
            applica_cpa=False,
            applica_iva=False,
        )
        included.append(
            {
                "descrizione": accessorio.get("row_label") or f"Compenso professionale per {ris_accessorio.tipo_pratica.label}",
                "tipo": "Onorario",
                "importo": ris_accessorio.onorario_selezionato,
                "fonte": f"accessorio:{accessorio_id}",
                "fiscale": "imponibile",
            }
        )
        if tp_accessorio and is_mediazione_practice(tp_accessorio):
            mediazione_target_calcolato = True
            mediazione_odm_accessorio = calcola_mediazione_odm_da_context(valore, mediazione_context)
            if mediazione_odm_accessorio:
                included.append(
                    {
                        "descrizione": (
                            f"{mediazione_odm_accessorio.get('voce_label') or 'Costi organismo mediazione D.M. 150/2023'}"
                            f" - {accessorio.get('label') or tp_accessorio.label}"
                        ),
                        "tipo": "Spesa viva",
                        "importo": float(mediazione_odm_accessorio.get("totale_organismo") or 0.0),
                        "fonte": f"mediazione_odm:{accessorio_id}",
                        "fiscale": "anticipazione_art15",
                    }
                )
    selected_expenses = set(state.get("esborsi", []))
    for item in esborsi_catalogo(pratica, state.get("accessori", []), get_tipo_pratica=get_tipo_pratica):
        if item["key"] not in selected_expenses:
            continue
        included.append(
            {
                "descrizione": item["descrizione"],
                "tipo": "Spesa viva",
                "importo": item["importo"],
                "fonte": f"esborso:{item['key']}",
                "fiscale": "anticipazione_art15",
            }
        )
    manual_rows = _manual_rows_from_payload(state)
    for row in manual_rows:
        included.append(
            {
                "descrizione": row["descrizione"],
                "tipo": row["tipo"],
                "importo": row["importo"],
                "fonte": f"manuale:{row['id']}",
                "fiscale": row.get("fiscale") or "imponibile",
            }
        )
    warnings_result: list[str] = []
    if mediazione_context.get("attiva") and not mediazione_target_calcolato:
        warnings_result.append(
            "Costi organismo mediazione non inclusi: seleziona una pratica di mediazione o un'integrazione mediazione collegata."
        )

    def _is_art15(row: dict[str, Any]) -> bool:
        fiscale = _text(row.get("fiscale")).lower().replace(".", "").replace(" ", "_")
        tipo = _text(row.get("tipo")).lower()
        return "anticipazione_art15" in fiscale or "art_15" in fiscale or tipo.startswith("anticipazione")

    imponibile = round(sum(float(row["importo"]) for row in included if not _is_art15(row)), 2)
    anticipazioni_art15 = round(sum(float(row["importo"]) for row in included if _is_art15(row)), 2)
    cassa = round(imponibile * 0.04, 2)
    base_iva = round(imponibile + cassa, 2)
    iva = round(base_iva * 0.22, 2)
    totale = round(base_iva + iva + anticipazioni_art15, 2)
    economic = {
        "imponibile": imponibile,
        "cassa": cassa,
        "base_iva": base_iva,
        "iva": iva,
        "anticipazioni_art15": anticipazioni_art15,
        "totale": totale,
    }
    links = _actions_for_result(
        risultato=risultato,
        profilo=profilo,
        regola=regola,
        pratica=pratica,
        state=state,
        selected=selected,
        manual_rows=manual_rows,
        included_rows=included,
        economic=economic,
        references=references,
    )
    tipo_compenso = getattr(pratica, "tipo_compenso_default", "") if pratica else "Per fasi processuali (D.M. 55/2014)"
    risultato_dict = risultato.to_dict()
    audit_tariffario = risultato_dict.get("audit_tariffario") if isinstance(risultato_dict.get("audit_tariffario"), dict) else {}
    result_refs = risultato_dict.get("riferimenti_normativi") if isinstance(risultato_dict.get("riferimenti_normativi"), list) else []
    reference_codes = risultato_dict.get("reference_codes") if isinstance(risultato_dict.get("reference_codes"), list) else []
    calc_mode = _text(audit_tariffario.get("calc_mode") or (profilo or {}).get("calc_mode"))
    compliance_status = _text(risultato_dict.get("compliance_status") or audit_tariffario.get("compliance_status"))
    high_range = "Oltre EUR 520.000" in risultato.scaglione
    indeterminabile = float(risultato.valore_input or 0.0) <= 0 and bool(risultato.complessita_stimata)
    badges = []
    if compliance_status == "snapshot_esatto":
        badges.append("Snapshot esatto")
    elif compliance_status == "ricostruzione":
        badges.append("Ricostruzione dichiarata")
    elif compliance_status:
        badges.append("Fallback tecnico")
    if high_range:
        badges.append("Fascia alta")
    if indeterminabile:
        badges.append("Valore indeterminabile")
    if calc_mode == "compenso_unico":
        badges.append("Compenso unico")
    elif calc_mode == "per_fasi_adr":
        badges.append("ADR")
        badges.append("Per fasi")
    else:
        badges.append("Per fasi")
    metadata = [
        {"label": "Area", "value": _text(audit_tariffario.get("area_scope") or state.get("materia", ""))},
        {"label": "Materia", "value": state.get("materia", "")},
        {"label": "Grado", "value": state.get("grado", "")},
        {"label": "Regola", "value": risultato_dict.get("rule_label") or risultato_dict.get("rule_code") or state.get("regola_tariffaria", "Standard")},
        {"label": "Tabella", "value": f"{risultato_dict.get('table_code', '')} - {risultato_dict.get('table_label', '')}".strip(" -")},
        {"label": "Scaglione", "value": risultato.scaglione},
        {"label": "Fasi", "value": ", ".join(risultato.fasi_selezionate)},
        {"label": "Complessita", "value": "molto alta / oltre EUR 520.000" if complessita == "molto_alta" else complessita},
    ]
    selected_summary = risultato.riepilogo_livello(selected)
    return {
        "ok": True,
        "result": {
            "title": "Risultato del calcolo",
            "engineLabel": "Motore di calcolo attivo",
            "engineText": (
                f"{tipo_compenso} - {getattr(pratica, 'oggetto_template', '') or getattr(pratica, 'label', 'Atto operativo')}. "
                f"Spese generali {'incluse' if state.get('spese_generali') else 'escluse'} nel totale."
            ),
            "metadata": metadata,
            "badges": badges,
            "table": _table_payload(risultato, selected),
            "note": risultato.note,
            "warnings": [
                warning for warning in [
                    "Calcolo non pienamente coperto: verificare fallback tecnico." if compliance_status == "fallback_tecnico" else "",
                    "Valore indeterminabile parametrizzato: verificare congruita prima dell'invio al cliente." if indeterminabile else "",
                ] if warning
            ] + warnings_result,
            "audit": audit_tariffario,
            "references": result_refs or references,
            "referenceCodes": reference_codes,
            "tableCode": risultato_dict.get("table_code", ""),
            "tableLabel": risultato_dict.get("table_label", ""),
            "ruleCode": risultato_dict.get("rule_code", ""),
            "ruleLabel": risultato_dict.get("rule_label", ""),
            "exactSnapshot": risultato_dict.get("exact_snapshot", False),
            "complianceStatus": compliance_status,
            "complianceNote": risultato_dict.get("compliance_note", ""),
            "sourceSnapshot": risultato_dict.get("source_snapshot", ""),
            "highRange": high_range,
            "indeterminate": indeterminabile,
            "included": _included_rows(included),
            "economic": _economic_payload(economic),
            "actions": links,
            "selectedLevel": selected,
            "selectedTotal": _euro(selected_summary.get("totale_compenso")),
            "rangeTotals": {
                LivelloCompenso.MINIMO.value: _euro(risultato.totale_compenso_livello(LivelloCompenso.MINIMO.value)),
                LivelloCompenso.BASE.value: _euro(risultato.totale_compenso_livello(LivelloCompenso.BASE.value)),
                LivelloCompenso.MASSIMO.value: _euro(risultato.totale_compenso_livello(LivelloCompenso.MASSIMO.value)),
            },
        },
        "economicRaw": economic,
    }


def build_react_tariffario_run_payload(
    payload: dict[str, Any] | None,
    *,
    get_normative_tables: Callable[[], Any],
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    payload = payload or {}
    phase_catalog = phase_catalog_by_materia()
    grade_catalog = grade_catalog_by_materia()
    state = _default_state(payload=payload, phase_catalog=phase_catalog, grade_catalog=grade_catalog)
    references = _table_rows(get_normative_tables, "tariffario_riferimenti", warnings, "riferimenti")
    profilo, regola, pratica = _active_profile(state)
    dynamic = _dynamic_options(state=state, pratica=pratica, phase_catalog=phase_catalog)
    try:
        run = _run_engine(state=state, profilo=profilo, regola=regola, pratica=pratica, references=references)
    except (ValueError, KeyError) as exc:
        return {
            "ok": False,
            "state": state,
            "profile": _profile_payload(profilo, pratica, state),
            "dynamic": dynamic,
            "result": None,
            "warnings": [_warning("calcolo_non_completato", str(exc))],
        }
    return {
        "ok": True,
        "state": state,
        "profile": _profile_payload(profilo, pratica, state),
        "dynamic": dynamic,
        "warnings": warnings,
        **run,
    }
