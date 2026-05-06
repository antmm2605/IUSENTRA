"""Bridge operativo React per il preventivo guidato.

La pagina React non duplica il tariffario: questo modulo espone cataloghi,
stato iniziale e calcolo usando i servizi Python esistenti del wizard legacy.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from flask import url_for

from pct.economico_context import costruisci_contesto_economico, dump_log_calcolo
from pct.motore_preventivo import (
    AREE_WIZARD,
    catalogo_fonti_tassonomia,
    catalogo_tassonomia_incompleto,
    catalogo_tassonomia_preventivi,
    catalogo_wizard,
    get_tipo_pratica,
    motore_calcola,
)
from pct.preventivi import (
    TipoVoce,
    VocePreventivo,
    catalogo_clausola_controversie,
    fonte_modello_clausola_controversie,
    normalizza_modello_clausola_controversie,
    testo_predefinito_clausola_controversie,
)
from pct.tariffario import Fase, Grado, livello_compenso_da_complessita
from pct.tariffario_catalogo import default_rule_for_practice, rule_lookup, rules_for_practice
from web.services.mediazione_dm150_runtime import (
    calcola_mediazione_odm_da_context,
    is_mediazione_practice,
    mediazione_odm_context_for_prefill,
    parse_mediazione_odm_context,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    rendered = str(value or "").strip()
    return rendered or fallback


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    raw = _text(value).lower()
    if raw in {"1", "true", "on", "si", "s", "yes"}:
        return True
    if raw in {"0", "false", "off", "no"}:
        return False
    return default


def _money(value: Any) -> str:
    try:
        amount = float(value or 0.0)
    except (TypeError, ValueError):
        amount = 0.0
    rendered = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"EUR {rendered}"


def _date_it(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return raw


def _parse_num(value: Any, default: float = 0.0) -> float:
    raw = _text(value)
    if not raw:
        return default
    try:
        return float(raw.replace(".", "").replace(",", ".")) if "," in raw else float(raw)
    except (TypeError, ValueError):
        return default


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _option(value: Any, label: str, description: str = "") -> dict[str, Any]:
    return {"value": _text(value), "label": label, "description": description, "enabled": True}


def _safe_all(loader: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[Any]:
    try:
        manager = loader()
        func = getattr(manager, method, None)
        if callable(func):
            return list(func())
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
    return []


def _client_label(cliente: Any) -> str:
    return (
        _text(getattr(cliente, "nome_completo", ""))
        or _text(getattr(cliente, "denominazione", ""))
        or _text(getattr(cliente, "ragione_sociale", ""))
        or "Cliente non indicato"
    )


def _case_label(fascicolo: Any) -> str:
    title = _text(getattr(fascicolo, "titolo", "")) or _text(getattr(fascicolo, "oggetto", ""))
    rg = _text(getattr(fascicolo, "numero_rg", ""))
    anno = _text(getattr(fascicolo, "anno_rg", ""))
    rg_label = f"RG {rg}/{anno}" if rg and anno else f"RG {rg}" if rg else ""
    return f"{rg_label} - {title}" if rg_label and title else title or rg_label or "Fascicolo senza titolo"


def _client_payload(cliente: Any) -> dict[str, Any]:
    recapiti = getattr(cliente, "recapiti", None)
    return {
        "id": _text(getattr(cliente, "id", "")),
        "label": _client_label(cliente),
        "type": _enum(getattr(cliente, "tipo", "")),
        "state": _enum(getattr(cliente, "stato", "")),
        "email": _text(getattr(recapiti, "email", "")),
        "phone": _text(getattr(recapiti, "telefono", "")) or _text(getattr(recapiti, "cellulare", "")),
        "fiscalId": _text(getattr(cliente, "identificativo_fiscale", "")),
        "minimumProfile": bool(getattr(cliente, "profilo_minimo_per_preventivo", False)),
        "engagementReady": bool(getattr(cliente, "profilo_completo_per_conferimento", False)),
        "missingEngagementFields": list(getattr(cliente, "campi_mancanti_per_conferimento", []) or []),
    }


def _case_payload(fascicolo: Any) -> dict[str, Any]:
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "label": _case_label(fascicolo),
        "customerId": _text(getattr(fascicolo, "id_cliente", "")),
        "area": _enum(getattr(getattr(fascicolo, "tipo", None), "value", "")),
        "court": _text(getattr(fascicolo, "tribunale", "")),
    }


def _catalog_rows() -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    grouped = catalogo_wizard()
    flat = {
        _text(item.get("id")): item
        for rows in grouped.values()
        for item in rows
        if isinstance(item, dict) and _text(item.get("id"))
    }
    return grouped, flat


def _area_counts(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "id": area.lower().replace(" ", "_"),
            "label": f"{area} ({len(grouped.get(area, []))})",
            "value": area,
            "count": len(grouped.get(area, [])),
        }
        for area in AREE_WIZARD
        if area in grouped
    ]


def _operational_options(rows: list[dict[str, Any]], key: str, label_key: str | None = None) -> list[dict[str, Any]]:
    options = [_option("", "Tutti" if key != "canale_operativo" else "Tutti i canali")]
    seen: set[str] = set()
    for item in rows:
        value = _text(item.get(key))
        if not value or value in seen:
            continue
        seen.add(value)
        label = _text(item.get(label_key or key)) or value
        options.append(_option(value, label))
    return options


def _taxonomy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    areas = sorted({_text(row.get("area_tassonomica")) for row in rows if _text(row.get("area_tassonomica"))})
    macros = sorted({_text(row.get("macro_area_tassonomica")) for row in rows if _text(row.get("macro_area_tassonomica"))})
    subs = sorted({_text(row.get("sottobranca_tassonomica")) for row in rows if _text(row.get("sottobranca_tassonomica"))})
    return {
        "areas": areas,
        "macroAreas": macros,
        "subBranches": subs,
        "missing": catalogo_tassonomia_incompleto(),
    }


def _prefill(query: dict[str, Any] | None) -> dict[str, Any]:
    query = query or {}
    raw_area = _text(query.get("area"))
    area_prefill = {
        "CIVILE_COGN": "Civile",
        "ESEC_MOB": "Civile",
        "ESEC_IMMO": "Civile",
        "VOLONTARIA": "Civile",
        "MEDIAZIONE": "Stragiudiziale",
        "NEGOZIAZIONE_ASSISTITA": "Stragiudiziale",
    }.get(raw_area.upper(), raw_area)
    return {
        "idCliente": _text(query.get("id_cliente")),
        "idFascicolo": _text(query.get("id_fascicolo")),
        "idPratica": _text(query.get("id_pratica")),
        "area": area_prefill,
        "oggetto": _text(query.get("oggetto")),
        "valore": _text(query.get("valore")) or "0",
        "grado": _text(query.get("grado")),
        "regolaTariffaria": _text(query.get("regola_tariffaria")),
        "complessita": _text(query.get("complessita"), "media"),
        "fasi": [item.strip() for item in _text(query.get("fasi")).split(",") if item.strip()],
        "bonusTelematico": _bool(query.get("bonus_telematico")),
        "speseGenerali": _bool(query.get("spese_generali"), True),
        "percSpeseGenerali": _text(query.get("perc_spese_generali"), "15"),
        "applicaCpa": _bool(query.get("applica_cpa"), True),
        "applicaIva": _bool(query.get("applica_iva"), True),
        "anticipazioni": _text(query.get("anticipazioni")) or "0",
        "mediazioneOdm": mediazione_odm_context_for_prefill(query),
        "autoCalcola": _bool(query.get("auto_calcola")),
    }


def _table_rows(get_normative_tables: Callable[[], Any], method: str, warnings: list[dict[str, str]], label: str) -> list[dict[str, Any]]:
    try:
        reader = getattr(get_normative_tables(), method, None)
        if callable(reader):
            return [row for row in reader() if isinstance(row, dict)]
    except Exception as exc:
        warnings.append(_warning(f"{label}_non_disponibile", f"Sorgente {label} non disponibile: {type(exc).__name__}."))
    return []


def build_react_preventivo_wizard_payload(
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_normative_tables: Callable[[], Any],
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = [
        _warning("motore_backend", "Il calcolo economico resta nel motore preventivo Python."),
        _warning("fallback_legacy", "La vista tecnica storica resta disponibile con ?_legacy=1."),
    ]
    clienti = _safe_all(get_clienti, "tutti", warnings, "clienti")
    fascicoli = _safe_all(get_fascicoli, "tutti", warnings, "fascicoli")
    grouped, practices = _catalog_rows()
    rows = list(practices.values())
    taxonomy_rows = catalogo_tassonomia_preventivi()
    sources = catalogo_fonti_tassonomia()
    today = date.today()
    due = today + timedelta(days=30)
    clausole = catalogo_clausola_controversie()
    default_clause = next((item for item in clausole if item.get("id") == "TUTELA_CLIENTE_CONSUMATORE"), clausole[0] if clausole else {})
    refs = _table_rows(get_normative_tables, "tariffario_riferimenti", warnings, "riferimenti")
    audit = _table_rows(get_normative_tables, "tariffario_audit", warnings, "audit")
    aligned = sum(1 for row in audit if row.get("compliance_status") in {"verificata_snapshot", "verificata_seed"})
    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
            "legacy_contract": "artifacts/react-migration/legacy-contracts/preventivi__wizard.json",
        },
        "defaults": {
            "issuedAt": today.isoformat(),
            "issuedAtLabel": _date_it(today.isoformat()),
            "dueAt": due.isoformat(),
            "dueAtLabel": _date_it(due.isoformat()),
            "mode": "guidato",
            "applicaCpa": True,
            "applicaIva": True,
            "speseGenerali": True,
            "percSpeseGenerali": "15",
            "informativaArt13": True,
        },
        "prefill": _prefill(query),
        "clients": [_client_payload(cliente) for cliente in clienti],
        "cases": [_case_payload(fascicolo) for fascicolo in fascicoli],
        "catalog": {
            "areas": _area_counts(grouped),
            "grouped": grouped,
            "practices": practices,
            "procedures": _operational_options(rows, "procedura_operativa_codice", "procedura_operativa_nome"),
            "workflows": _operational_options(rows, "workflow_operativo_codice"),
            "channels": _operational_options(rows, "canale_operativo"),
            "taxonomyRows": taxonomy_rows,
            "taxonomySummary": _taxonomy_summary(taxonomy_rows),
            "taxonomySources": sources,
        },
        "options": {
            "complexity": [
                _option("bassa", "Bassa"),
                _option("media", "Media"),
                _option("alta", "Alta"),
            ],
            "voiceTypes": [_option(item.value, item.value) for item in TipoVoce],
            "manualFiscalTypes": [
                _option("imponibile", "Imponibile"),
                _option("anticipazione_art15", "Anticipazione art. 15"),
            ],
            "quickClientTypes": [
                _option("PERSONA_FISICA", "Persona fisica"),
                _option("PERSONA_GIURIDICA", "Persona giuridica"),
            ],
            "clauseModels": clausole,
            "defaultClause": {
                "id": _text(default_clause.get("id")),
                "label": _text(default_clause.get("label")),
                "source": _text(default_clause.get("source")),
                "defaultText": _text(default_clause.get("default_text")),
            },
        },
        "support": {
            "references": refs,
            "audit": {
                "aligned": aligned,
                "total": len(audit),
                "open": max(0, len(audit) - aligned),
            },
        },
        "actions": {
            "back": "/preventivi",
            "legacy": "/preventivi/wizard?_legacy=1",
            "calculate": "/api/v1/ui/preventivi/wizard/calculate",
            "create": "/api/v1/ui/preventivi/wizard/create",
        },
        "warnings": warnings,
    }


_GRADE_MAP = {
    "Giudice di Pace": Grado.GIUDICE_DI_PACE,
    "Tribunale": Grado.TRIBUNALE,
    "GIP / GUP": Grado.GIP_GUP,
    "Tribunale monocratico": Grado.TRIBUNALE_MONOCRATICO,
    "Tribunale collegiale": Grado.TRIBUNALE_COLLEGIALE,
    "Corte d'Assise": Grado.CORTE_ASSISE,
    "Corte d'Appello": Grado.CORTE_APPELLO,
    "Corte d'Appello penale": Grado.CORTE_APPELLO_PENALE,
    "Corte d'Assise d'Appello": Grado.CORTE_ASSISE_APPELLO,
    "Corte di Cassazione": Grado.CASSAZIONE,
    "Tribunale di Sorveglianza": Grado.TRIBUNALE_SORVEGLIANZA,
    "TAR": Grado.TAR,
    "Consiglio di Stato": Grado.CONSIGLIO_DI_STATO,
    "CGT di primo grado": Grado.CGT_PRIMO_GRADO,
    "CGT di secondo grado": Grado.CGT_SECONDO_GRADO,
    "Fuori giudizio": Grado.FUORI_GIUDIZIO,
    "Procedura ADR": Grado.PROCEDURA_ADR,
}

_PHASE_MAP = {
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

_PHASE_VALUE_TO_KEY = {fase.value: key for key, fase in _PHASE_MAP.items()}


class WizardPayloadForm:
    """Adapter MultiDict-like usato da helper legacy e runtime tariffario."""

    def __init__(self, payload: dict[str, Any] | None):
        self.payload = payload or {}

    def _raw(self, key: str) -> Any:
        if key in self.payload:
            return self.payload[key]
        if key.endswith("[]"):
            return self.payload.get(key[:-2])
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
        return [rendered] if rendered else []


def _state(payload: dict[str, Any]) -> dict[str, Any]:
    practice_id = _text(payload.get("id_pratica") or payload.get("practiceId"))
    tp = get_tipo_pratica(practice_id) if practice_id else None
    phases = payload.get("fasi")
    if not isinstance(phases, list) or not phases:
        phases = [
            _PHASE_VALUE_TO_KEY.get(fase.value, "")
            for fase in (getattr(tp, "fasi_default", []) or [])
        ] if tp else []
        phases = [phase for phase in phases if phase]
    if _bool(payload.get("compenso_unico"), False) and "compenso_unico" not in phases:
        phases = [*phases, "compenso_unico"]
    manual_lines = payload.get("manual_lines") if isinstance(payload.get("manual_lines"), list) else payload.get("voci_bozza")
    return {
        "id_pratica": practice_id,
        "valore": _text(payload.get("valore") or payload.get("valore_controversia"), "0"),
        "grado": _text(payload.get("grado") or getattr(getattr(tp, "grado_default", None), "value", "")),
        "regola_tariffaria": _text(payload.get("regola_tariffaria") or getattr(tp, "regola_tariffaria_default", "")),
        "complessita": _text(payload.get("complessita"), "media"),
        "fasi": phases,
        "bonus_telematico": _bool(payload.get("bonus_telematico")),
        "spese_generali": _bool(payload.get("spese_generali"), True),
        "perc_spese_generali": _text(payload.get("perc_spese_generali"), "15"),
        "applica_cpa": _bool(payload.get("applica_cpa"), True),
        "applica_iva": _bool(payload.get("applica_iva"), True),
        "anticipazioni": _text(payload.get("anticipazioni") or payload.get("anticipazioni_art15"), "0"),
        "adr_accordo": _bool(payload.get("adr_accordo")),
        "mediazione_odm_attiva": _bool(payload.get("mediazione_odm_attiva")),
        "mediazione_odm_regime": _text(payload.get("mediazione_odm_regime"), "volontaria"),
        "mediazione_odm_esito": _text(payload.get("mediazione_odm_esito"), "primo_incontro_senza_accordo"),
        "mediazione_odm_art31_maggiorazione_20": _bool(payload.get("mediazione_odm_art31_maggiorazione_20")),
        "accessori": payload.get("accessori") if isinstance(payload.get("accessori"), list) else [],
        "esborsi": payload.get("esborsi") if isinstance(payload.get("esborsi"), list) else [],
        "manual_lines": manual_lines if isinstance(manual_lines, list) else [],
    }


def _phase_selection(state: dict[str, Any], practice_id: str) -> tuple[list[Fase] | None, str | None]:
    regola = rule_lookup(state["regola_tariffaria"]) if state["regola_tariffaria"] else None
    if not regola:
        regola = default_rule_for_practice(practice_id)
    profile = (regola or {}).get("profile", {}) or {}
    unico_profile = profile.get("calc_mode") == "compenso_unico" or "compenso_unico" in (profile.get("phase_keys") or [])
    phase_keys = [_text(item) for item in state.get("fasi", []) if _text(item)]
    parsed = [_PHASE_MAP[key] for key in phase_keys if key in _PHASE_MAP]
    explicit = "fasi" in state
    unico_on = "compenso_unico" in phase_keys
    if unico_profile and unico_on:
        return parsed or [Fase.STUDIO], None
    if parsed:
        return parsed, "" if explicit and unico_profile else None
    if explicit:
        return [], "" if unico_profile else None
    return None, None


def _variation_payload(form: WizardPayloadForm, tp: Any) -> tuple[dict[str, float], dict[str, float]]:
    variations: dict[str, float] = {}
    for key, fase in _PHASE_MAP.items():
        raw = form.get(f"var_{key}", "")
        if _text(raw):
            variations[fase.value] = 1.0 + (_parse_num(raw, 0.0) / 100.0)
    increases: dict[str, float] = {}
    policy = dict(getattr(tp, "variation_policy", {}) or {})
    bonus = dict(policy.get("agreement_bonus", {}) or {})
    if _bool(form.get("adr_accordo")) and bonus.get("enabled"):
        multiplier = 1.0 + (float(bonus.get("pct", 0) or 0) / 100.0)
        for key in bonus.get("phase_keys", []) or []:
            phase = _PHASE_MAP.get(str(key))
            if phase:
                increases[phase.value] = multiplier
    return variations, increases


def _manual_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("manual_lines") if isinstance(payload.get("manual_lines"), list) else [], start=1):
        if not isinstance(raw, dict) or raw.get("inclusa") is False:
            continue
        descrizione = _text(raw.get("descrizione"))
        if not descrizione:
            continue
        tipo = _text(raw.get("tipo"), TipoVoce.ONORARIO.value)
        fiscale = _text(raw.get("fiscale"), "imponibile")
        lines.append(
            {
                "id": _text(raw.get("id")) or f"manuale_{index}",
                "descrizione": descrizione,
                "tipo": tipo,
                "importo": round(_parse_num(raw.get("importo"), 0.0), 2),
                "fiscale": fiscale,
                "source": "manuale",
            }
        )
    return lines


def _tax_summary(*, taxable_rows: list[dict[str, Any]], art15: float, applica_cpa: bool, applica_iva: bool) -> dict[str, Any]:
    from pct.preventivi import Preventivo

    voci = [
        VocePreventivo(
            descrizione=_text(row.get("descrizione")),
            importo=float(row.get("importo") or 0.0),
            tipo=TipoVoce.SPESA_FORFETTARIA if _text(row.get("tipo")) == TipoVoce.SPESA_FORFETTARIA.value else TipoVoce.ONORARIO,
        )
        for row in taxable_rows
        if float(row.get("importo") or 0.0) > 0
    ]
    preview = Preventivo(
        id="preview",
        numero="preview",
        id_cliente="",
        id_fascicolo=None,
        data_emissione=date.today().isoformat(),
        data_scadenza=None,
        oggetto="",
        voci=voci,
        applica_cassa=applica_cpa,
        applica_iva=applica_iva,
        anticipazioni_art15=round(float(art15 or 0.0), 2),
    )
    return {
        "imponibile_voci": preview.imponibile,
        "cpa": preview.cassa_forense,
        "base_iva": preview.base_iva,
        "iva": preview.iva,
        "anticipazioni_art15": round(float(art15 or 0.0), 2),
        "totale": preview.totale,
        "imponibile_label": _money(preview.imponibile),
        "cpa_label": _money(preview.cassa_forense),
        "iva_label": _money(preview.iva),
        "anticipazioni_label": _money(art15),
        "totale_label": _money(preview.totale),
    }


def build_react_preventivo_wizard_calculation_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    state = _state(payload)
    practice_id = state["id_pratica"]
    if not practice_id:
        return {"ok": False, "state": state, "warnings": [_warning("id_pratica_mancante", "Seleziona una tipologia pratica prima del calcolo.")]}
    tp = get_tipo_pratica(practice_id)
    if not tp:
        return {"ok": False, "state": state, "warnings": [_warning("tipologia_non_trovata", f"Tipologia non trovata: {practice_id}.")]}
    regola = state["regola_tariffaria"]
    if regola and regola not in {str(row.get("rule_code", "") or "") for row in rules_for_practice(practice_id)}:
        regola = ""
        state["regola_tariffaria"] = ""
    grado = _GRADE_MAP.get(state["grado"]) if state["grado"] else None
    form = WizardPayloadForm({**state, **payload})
    fasi, profile_override = _phase_selection(state, practice_id)
    variations, increases = _variation_payload(form, tp)
    mediazione_context = parse_mediazione_odm_context(form)
    livello = livello_compenso_da_complessita(state["complessita"])
    perc_spese = _parse_num(state["perc_spese_generali"], 15.0) / 100.0
    anticipazioni_base = _parse_num(state["anticipazioni"], 0.0)
    ris = motore_calcola(
        id_pratica=practice_id,
        valore_controversia=_parse_num(state["valore"], 0.0),
        grado=grado,
        regola_tariffaria=regola,
        profile_code_override=profile_override,
        fasi=fasi,
        livello_compenso=livello,
        complessita=state["complessita"],
        bonus_telematico=state["bonus_telematico"],
        includi_spese_generali=state["spese_generali"],
        perc_spese_generali=perc_spese,
        variazioni_fasi=variations or None,
        maggiorazioni_fasi=increases or None,
        applica_cpa=state["applica_cpa"],
        applica_iva=state["applica_iva"],
        anticipazioni=anticipazioni_base,
    )
    dm = ris.calcolo_dm55
    level_summary = dm.riepilogo_livello(livello)
    bonus = round(float(level_summary.get("bonus_telematico", 0.0)), 2)
    spese_generali = round(float(level_summary.get("spese_generali", 0.0)), 2)
    compenso = round(float(level_summary.get("subtotale", ris.onorario_selezionato)) + bonus, 2)
    taxable_rows = [
        {
            "id": "compenso_principale",
            "descrizione": f"Compenso professionale per {tp.label} - {dm.scaglione}",
            "tipo": TipoVoce.ONORARIO.value,
            "importo": compenso,
            "importo_label": _money(compenso),
            "fiscale": "imponibile",
            "source": "motore",
            "locked": False,
        }
    ]
    if state["spese_generali"] and spese_generali > 0:
        taxable_rows.append(
            {
                "id": "spese_generali",
                "descrizione": f"Spese generali {int(round(dm.perc_spese_generali * 100))}%",
                "tipo": TipoVoce.SPESA_FORFETTARIA.value,
                "importo": spese_generali,
                "importo_label": _money(spese_generali),
                "fiscale": "imponibile",
                "source": "motore",
                "locked": False,
            }
        )
    art15 = anticipazioni_base
    extra_rows: list[dict[str, Any]] = []
    mediazione_odm = calcola_mediazione_odm_da_context(_parse_num(state["valore"], 0.0), mediazione_context) if is_mediazione_practice(tp) else None
    if mediazione_odm:
        amount = round(float(mediazione_odm.get("totale_organismo") or 0.0), 2)
        art15 += amount
        extra_rows.append(
            {
                "id": "mediazione_odm",
                "descrizione": mediazione_odm.get("voce_label") or "Costi organismo mediazione D.M. 150/2023",
                "tipo": TipoVoce.SPESA_VIVA.value,
                "importo": amount,
                "importo_label": _money(amount),
                "fiscale": "anticipazione_art15",
                "source": "mediazione_odm",
                "locked": False,
            }
        )
    selected_expenses = set(state.get("esborsi") or [])
    for index, item in enumerate(getattr(tp, "esborsi_tipici", []) or [], start=1):
        key = _text(item.get("key")) or f"{practice_id}:{index - 1}"
        if key not in selected_expenses:
            continue
        amount = round(_parse_num(item.get("importo"), 0.0), 2)
        art15 += amount
        extra_rows.append(
            {
                "id": f"esborso_{key}",
                "descrizione": _text(item.get("descrizione"), "Spesa viva suggerita"),
                "tipo": TipoVoce.SPESA_VIVA.value,
                "importo": amount,
                "importo_label": _money(amount),
                "fiscale": "anticipazione_art15",
                "source": "esborso",
                "locked": False,
            }
        )
    for line in _manual_lines(state):
        if line["fiscale"] == "anticipazione_art15" or line["tipo"].lower().startswith("anticipazione"):
            art15 += float(line["importo"] or 0.0)
            extra_rows.append({**line, "importo_label": _money(line["importo"]), "locked": False})
        else:
            taxable_rows.append({**line, "importo_label": _money(line["importo"]), "locked": False})
    summary = _tax_summary(
        taxable_rows=taxable_rows,
        art15=art15,
        applica_cpa=state["applica_cpa"],
        applica_iva=state["applica_iva"],
    )
    rows = taxable_rows + extra_rows
    fasi_out = {fase: {"min": values[0], "base": values[1], "max": values[2]} for fase, values in dm.dettaglio.items()}
    log = dump_log_calcolo(
        costruisci_contesto_economico(
            source="preventivo_guidato_react",
            source_label="Preventivo guidato",
            oggetto=_text(payload.get("oggetto")),
            id_pratica=practice_id,
            pratica_label=tp.label,
            area_pratica=tp.area,
            tipo_compenso=tp.tipo_compenso_default,
            tipo_procedimento=tp.label,
            grado_sede=state["grado"],
            regola_tariffaria=regola,
            regola_tariffaria_code=regola,
            complessita=state["complessita"],
            valore_controversia=state["valore"],
            bonus_telematico=state["bonus_telematico"],
            spese_generali=state["spese_generali"],
            perc_spese_generali=state["perc_spese_generali"],
            applica_cpa=state["applica_cpa"],
            applica_iva=state["applica_iva"],
            anticipazioni_art15=summary["anticipazioni_art15"],
            adr_accordo=state["adr_accordo"],
            risultato={
                "scaglione": dm.scaglione,
                "onorario_base": compenso,
                "cpa": summary["cpa"],
                "iva": summary["iva"],
                "totale": summary["totale"],
                "nota": dm.note,
            },
        )
    )
    return {
        "ok": True,
        "state": state,
        "profile": tp.to_dict(),
        "summary": tp.summary,
        "when_to_use": tp.when_to_use,
        "normative_references": tp.normative_references,
        "base_normativa": tp.base_normativa,
        "fasi": fasi_out,
        "scaglione": dm.scaglione,
        "livello_compenso": ris.livello_compenso,
        "bonus_telematico": bonus,
        "spese_generali": spese_generali,
        "compenso_base": compenso,
        "rows": rows,
        "economic": summary,
        "mediazione_odm": mediazione_odm,
        "note": _text(payload.get("note")) or tp.note_template,
        "warnings": [],
        "audit": {"log_calcolo": log},
        "transfer": {
            "voce_descr": [row["descrizione"] for row in rows],
            "voce_importo": [row["importo"] for row in rows],
            "voce_tipo": [row["tipo"] for row in rows],
            "anticipazioni_art15_totali": summary["anticipazioni_art15"],
        },
    }


def build_react_preventivo_wizard_error_payload(message: str = "Preventivo guidato non disponibile.") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {"mock_fallback": False, "writes": "operational_routes", "route_owner": "react_shell"},
        "defaults": {},
        "prefill": {},
        "clients": [],
        "cases": [],
        "catalog": {},
        "options": {},
        "support": {},
        "actions": {"back": "/preventivi", "legacy": "/preventivi/wizard?_legacy=1"},
        "warnings": [_warning("preventivo_wizard_errore", message)],
    }


def default_clause_payload(model: str | None = None) -> dict[str, str]:
    modello = normalizza_modello_clausola_controversie(model or "TUTELA_CLIENTE_CONSUMATORE")
    return {
        "model": modello,
        "source": fonte_modello_clausola_controversie(modello),
        "text": testo_predefinito_clausola_controversie(modello),
    }


def detail_url_for_preventivo(preventivo_id: str) -> str:
    try:
        return url_for("preventivi.dettaglio_preventivo", id_preventivo=preventivo_id)
    except Exception:
        return f"/preventivi/p/{preventivo_id}"
