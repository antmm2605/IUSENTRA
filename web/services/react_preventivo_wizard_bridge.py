"""Bridge operativo React per il preventivo guidato.

La pagina React non duplica il tariffario: questo modulo espone cataloghi,
stato iniziale e calcolo usando i servizi Python esistenti del wizard legacy.
"""

from __future__ import annotations


from pct.formatting import format_euro_it
import json
from datetime import date, datetime, timedelta, timezone
from threading import Lock
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
from pct.pratiche_collegate_catalog import codice_oggetto_pst_payload
from pct.preventivi import (
    TipoVoce,
    VocePreventivo,
    catalogo_clausola_controversie,
    fonte_modello_clausola_controversie,
    normalizza_modello_clausola_controversie,
    testo_predefinito_clausola_controversie,
)
from pct.strumenti_legali import GestioneStrumentiLegali
from pct.tariffario import Fase, Grado, livello_compenso_da_complessita
from pct.tariffario_catalogo import default_rule_for_practice, rule_lookup, rules_for_practice, tariffario_complessita_rows
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
    return format_euro_it(value)


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


_STRUMENTI_LEGALI: GestioneStrumentiLegali | None = None
_STRUMENTI_LEGALI_LOCK = Lock()


def _strumenti_legali() -> GestioneStrumentiLegali:
    """Costruisce il calcolatore del contributo unificato alla prima richiesta.

    `GestioneStrumentiLegali()` carica le tabelle normative (2,4 MB) e a livello
    di modulo il costo veniva pagato all'import, quindi ad ogni avvio di worker
    anche quando il wizard preventivi non viene mai aperto. Le due sole funzioni
    che lo usano restano identiche: cambia solo il momento della costruzione.
    """

    global _STRUMENTI_LEGALI
    if _STRUMENTI_LEGALI is None:
        with _STRUMENTI_LEGALI_LOCK:
            if _STRUMENTI_LEGALI is None:
                _STRUMENTI_LEGALI = GestioneStrumentiLegali()
    return _STRUMENTI_LEGALI


def _cu_grade_from_label(grade_label: str) -> str:
    lowered = _text(grade_label).lower()
    if "cassazione" in lowered:
        return "cassazione"
    if "appello" in lowered or "consiglio di stato" in lowered or "secondo grado" in lowered:
        return "appello"
    return "primo_grado"


def _cu_amount_for_practice(practice_id: str, *, value: float, grade_label: str) -> float | None:
    grade = _cu_grade_from_label(grade_label)
    if practice_id in {"atto_citazione", "opposizione_di", "comparsa_risposta", "risarcimento_danni"}:
        result = _strumenti_legali().calcola_contributo_unificato(
            {
                "cu_categoria": "civile_ordinario",
                "cu_grado": grade,
                "cu_valore": value,
                "cu_valore_tipo": "determinato" if value > 0 else "indeterminabile",
            }
        )
        return round(float(result.get("base") or 0.0), 2)
    if practice_id == "decreto_ingiuntivo":
        result = _strumenti_legali().calcola_contributo_unificato(
            {
                "cu_categoria": "decreto_ingiuntivo",
                "cu_grado": "primo_grado",
                "cu_valore": value,
                "cu_valore_tipo": "determinato" if value > 0 else "indeterminabile",
            }
        )
        return round(float(result.get("base") or 0.0), 2)
    return None


def _resolved_practice_expenses(practice: Any, *, value: float, grade_label: str) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in list(getattr(practice, "esborsi_tipici", []) or []):
        row = dict(item)
        descrizione = _text(row.get("descrizione"))
        if "contributo unificato" in descrizione.lower():
            row["descrizione"] = descrizione.replace(" (indicativo)", "").replace("(indicativo)", "").strip()
            amount = _cu_amount_for_practice(_text(getattr(practice, "id", "")), value=value, grade_label=grade_label)
            if amount is not None:
                row["importo"] = amount
                row["source"] = "Calcolato da tabella contributo unificato"
        resolved.append(row)
    return resolved


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


_DEONTOLOGIA_SOURCES = [
    {
        "code": "codice_deontologico_cnf",
        "label": "Codice Deontologico Forense CNF",
        "url": "https://codicedeontologico-cnf.it/",
        "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/cnf-codice-deontologico-home.html",
    },
    {
        "code": "cdf_art25bis_gazzetta_2026",
        "label": "Art. 25-bis CDF, G.U. 5 febbraio 2026",
        "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=26A00480&atto.dataPubblicazioneGazzetta=2026-02-05&tipoSerie=serie_generale&tipoVigenza=originario",
        "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/gazzetta-cdf-art-25bis-2026.html",
    },
    {
        "code": "cdf_art27_cnf",
        "label": "Art. 27 CDF, informazione al cliente",
        "url": "https://codicedeontologico-cnf.it/tag/27-ncdf/",
        "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/cnf-cdf-art-27-tag.html",
    },
]


def _final_options(payload: dict[str, Any]) -> dict[str, Any]:
    final = payload.get("opzioni_finali") if isinstance(payload.get("opzioni_finali"), dict) else {}
    return {
        **final,
        "informativa_art13_resa": payload.get("informativa_art13_resa", final.get("informativa_art13_resa", True)),
        "cliente_qualificato_equo_compenso": payload.get(
            "cliente_qualificato_equo_compenso",
            final.get("cliente_qualificato_equo_compenso", False),
        ),
        "accordo_predisposto_avvocato": payload.get(
            "accordo_predisposto_avvocato",
            final.get("accordo_predisposto_avvocato", True),
        ),
        "equo_compenso_verificato": payload.get(
            "equo_compenso_verificato",
            final.get("equo_compenso_verificato", False),
        ),
        "informativa_scritta_equo_compenso": payload.get(
            "informativa_scritta_equo_compenso",
            final.get("informativa_scritta_equo_compenso", False),
        ),
    }


def _deontologia_wizard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    final = _final_options(payload)
    informativa_art13 = _bool(final.get("informativa_art13_resa"), True)
    cliente_qualificato = _bool(final.get("cliente_qualificato_equo_compenso"), False)
    accordo_predisposto = _bool(final.get("accordo_predisposto_avvocato"), True)
    equo_verificato = _bool(final.get("equo_compenso_verificato"), False)
    informativa_scritta = _bool(final.get("informativa_scritta_equo_compenso"), False)
    presidi: list[dict[str, Any]] = [
        {
            "code": "art_27_informazione_cliente",
            "label": "Informazione chiara e completa al cliente",
            "status": "documentata" if informativa_art13 else "da_documentare",
            "source": "cdf_art27_cnf",
            "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/cnf-cdf-art-27-tag.html",
            "note": "Il wizard registra se l'informativa preventiva è stata resa prima di conferimento e fascicolo.",
        }
    ]
    warnings: list[dict[str, str]] = []
    if not informativa_art13:
        warnings.append(
            _warning(
                "deontologia_informativa_cliente_da_documentare",
                "Documenta l'informativa preventiva al cliente prima di procedere con conferimento o deposito.",
            )
        )
    if cliente_qualificato:
        presidi.append(
            {
                "code": "art_25bis_equo_compenso",
                "label": "Equo compenso per cliente qualificato",
                "status": "verificato" if equo_verificato else "da_verificare",
                "source": "cdf_art25bis_gazzetta_2026",
                "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/gazzetta-cdf-art-25bis-2026.html",
                "note": "Il controllo riguarda PA, banche, assicurazioni, grandi imprese e altri soggetti indicati dalla fonte.",
            }
        )
        if not equo_verificato:
            warnings.append(
                _warning(
                    "deontologia_equo_compenso_da_verificare",
                    "Verifica equo compenso e parametri prima di inviare il preventivo a un cliente qualificato.",
                )
            )
        if accordo_predisposto:
            presidi.append(
                {
                    "code": "art_25bis_informativa_scritta",
                    "label": "Avviso scritto su accordo predisposto dallo studio",
                    "status": "documentata" if informativa_scritta else "da_documentare",
                    "source": "cdf_art25bis_gazzetta_2026",
                    "local_path": "docs/specs/ministero/fonti_ufficiali/2026-06-02/gazzetta-cdf-art-25bis-2026.html",
                    "note": "Quando l'accordo è predisposto dallo studio, il wizard richiede presidio scritto separato.",
                }
            )
            if not informativa_scritta:
                warnings.append(
                    _warning(
                        "deontologia_informativa_scritta_equo_compenso_da_documentare",
                        "Documenta l'avviso scritto previsto per il cliente qualificato prima della sottoscrizione.",
                    )
                )
    return {
        "status": "attenzione" if warnings else "documentato",
        "cliente_qualificato_equo_compenso": cliente_qualificato,
        "accordo_predisposto_avvocato": accordo_predisposto,
        "equo_compenso_verificato": equo_verificato,
        "informativa_art13_resa": informativa_art13,
        "informativa_scritta_equo_compenso": informativa_scritta,
        "sources": _DEONTOLOGIA_SOURCES,
        "presidi": presidi,
        "warnings": warnings,
    }


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
    codice_payload = codice_oggetto_pst_payload(getattr(fascicolo, "codice_oggetto_pst", ""))
    has_codice = bool(codice_payload["codice_oggetto_pst"])
    return {
        "id": _text(getattr(fascicolo, "id", "")),
        "label": _case_label(fascicolo),
        "customerId": _text(getattr(fascicolo, "id_cliente", "")),
        "area": _enum(getattr(getattr(fascicolo, "tipo", None), "value", "")),
        "court": _text(getattr(fascicolo, "tribunale", "")),
        "codiceOggettoPst": codice_payload["codice_oggetto_pst"],
        "fonteCodiceOggetto": (
            _text(getattr(fascicolo, "fonte_codice_oggetto", "")) or codice_payload["fonte_codice_oggetto"]
        )
        if has_codice
        else "",
        "fileFonteCodiceOggetto": (
            _text(getattr(fascicolo, "file_fonte_codice_oggetto", ""))
            or codice_payload["file_fonte_codice_oggetto"]
        )
        if has_codice
        else "",
    }


def _compact_reference(row: Any) -> dict[str, str]:
    item = row if isinstance(row, dict) else {}
    return {
        "title": _text(item.get("title")),
        "article": _text(item.get("article")),
        "description": _text(item.get("description")),
        "url": _text(item.get("url")),
    }


def _compact_rule(row: dict[str, Any]) -> dict[str, Any]:
    profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
    return {
        "rule_code": _text(row.get("rule_code")),
        "label": _text(row.get("label")),
        "rule_label": _text(row.get("rule_label")),
        "table_label": _text(row.get("table_label")),
        "table_code": _text(row.get("table_code")),
        "grado_input_value": _text(row.get("grado_input_value")),
        "allowed_grade_input_values": list(row.get("allowed_grade_input_values") or []),
        "calc_mode": _text(row.get("calc_mode") or profile.get("calc_mode")),
        "exact_snapshot": bool(row.get("exact_snapshot") or profile.get("exact_snapshot")),
        "compliance_status": _text(row.get("compliance_status")),
        "profile": {
            "calc_mode": _text(profile.get("calc_mode")),
            "phase_keys": list(profile.get("phase_keys") or []),
        },
    }


def _compact_practice(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _text(item.get("id")),
        "label": _text(item.get("label")),
        "area": _text(item.get("area")),
        "materia": _text(item.get("materia")),
        "grado_default": _text(item.get("grado_default")),
        "fasi_default": list(item.get("fasi_default") or []),
        "fasi_default_keys": list(item.get("fasi_default_keys") or []),
        "base_normativa": _text(item.get("base_normativa")),
        "tipo_compenso_default": _text(item.get("tipo_compenso_default")),
        "valore_suggerito": item.get("valore_suggerito") or 0,
        "esborsi_tipici": list(item.get("esborsi_tipici") or []),
        "motore_label": _text(item.get("motore_label")),
        "redattore_label": _text(item.get("redattore_label")),
        "summary": _text(item.get("summary")),
        "when_to_use": _text(item.get("when_to_use")),
        "oggetto_template": _text(item.get("oggetto_template")),
        "note_template": _text(item.get("note_template")),
        "checklist_iniziale": list(item.get("checklist_iniziale") or []),
        "normative_references": [_compact_reference(row) for row in list(item.get("normative_references") or [])[:8]],
        "accessori_calcolo": list(item.get("accessori_calcolo") or []),
        "variation_policy": item.get("variation_policy") if isinstance(item.get("variation_policy"), dict) else {},
        "area_tassonomica": _text(item.get("area_tassonomica")),
        "area_tassonomica_code": _text(item.get("area_tassonomica_code")),
        "macro_area_tassonomica": _text(item.get("macro_area_tassonomica")),
        "macro_area_tassonomica_code": _text(item.get("macro_area_tassonomica_code")),
        "sottobranca_tassonomica": _text(item.get("sottobranca_tassonomica")),
        "sottobranca_tassonomica_code": _text(item.get("sottobranca_tassonomica_code")),
        "tassonomia_codice": _text(item.get("tassonomia_codice")),
        "tassonomia_descrizione": _text(item.get("tassonomia_descrizione")),
        "tassonomia_sources": [],
        "procedura_operativa_codice": _text(item.get("procedura_operativa_codice")),
        "procedura_operativa_nome": _text(item.get("procedura_operativa_nome")),
        "subbranch_operativa_codice": _text(item.get("subbranch_operativa_codice")),
        "workflow_operativo_codice": _text(item.get("workflow_operativo_codice")),
        "copertura_operativa": _text(item.get("copertura_operativa")),
        "canale_operativo": _text(item.get("canale_operativo")),
        "registro_operativo": _text(item.get("registro_operativo")),
        "regola_tariffaria_default": _text(item.get("regola_tariffaria_default")),
        "regole_tariffarie": [
            _compact_rule(row)
            for row in item.get("regole_tariffarie") or []
            if isinstance(row, dict)
        ],
    }


def _catalog_rows() -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    grouped = catalogo_wizard()
    flat = {
        _text(item.get("id")): _compact_practice(item)
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
    codice_payload = codice_oggetto_pst_payload(query.get("codice_oggetto_pst"))
    has_codice = bool(codice_payload["codice_oggetto_pst"])
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
        "codiceOggettoPst": codice_payload["codice_oggetto_pst"],
        "fonteCodiceOggetto": (_text(query.get("fonte_codice_oggetto")) or codice_payload["fonte_codice_oggetto"])
        if has_codice
        else "",
        "fileFonteCodiceOggetto": (
            _text(query.get("file_fonte_codice_oggetto")) or codice_payload["file_fonte_codice_oggetto"]
        )
        if has_codice
        else "",
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
    warnings: list[dict[str, str]] = []
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
    aligned = sum(1 for row in audit if row.get("compliance_status") in {"snapshot_esatto", "verificata_snapshot", "verificata_seed"})
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
            "grouped": {},
            "practices": practices,
            "procedures": _operational_options(rows, "procedura_operativa_codice", "procedura_operativa_nome"),
            "workflows": _operational_options(rows, "workflow_operativo_codice"),
            "channels": _operational_options(rows, "canale_operativo"),
            "taxonomyRows": [],
            "taxonomySummary": _taxonomy_summary(taxonomy_rows),
            "taxonomySources": [_compact_reference(row) for row in sources[:8]],
        },
        "options": {
            "complexity": [
                _option(row.get("value", ""), _text(row.get("label")) or _text(row.get("value")), _text(row.get("description")))
                for row in tariffario_complessita_rows()
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
            "references": [_compact_reference(row) for row in refs[:12]],
            "audit": {
                "aligned": aligned,
                "total": len(audit),
                "open": max(0, len(audit) - aligned),
            },
        },
        "actions": {
            "back": "/preventivi",
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
    "Magistrato di Sorveglianza": Grado.MAGISTRATO_SORVEGLIANZA,
    "TAR": Grado.TAR,
    "Consiglio di Stato": Grado.CONSIGLIO_DI_STATO,
    "Corte dei Conti": Grado.CORTE_DEI_CONTI,
    "Corte costituzionale": Grado.CORTE_COSTITUZIONALE,
    "Corte europea dei diritti dell'uomo": Grado.CORTE_EDU,
    "Corte di giustizia UE": Grado.CORTE_GIUSTIZIA_UE,
    "Corte cost. / Corte europea / CGUE": Grado.CORTE_SUPERIORE_UE,
    "Conservatoria / tavolare": Grado.CONSERVATORIA_TAVOLARE,
    "Tribunale concorsuale": Grado.TRIBUNALE_CONCORSUALE,
    "Giudice tutelare": Grado.GIUDICE_TUTELARE,
    "Giudice competente": Grado.GIUDICE_COMPETENTE,
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
    regola_tariffaria = _text(payload.get("regola_tariffaria") or getattr(tp, "regola_tariffaria_default", ""))
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
        "regola_tariffaria": regola_tariffaria,
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


def _phase_keys_for_practice(practice: Any, include_compenso_unico: bool = False) -> list[str]:
    keys = [
        _PHASE_VALUE_TO_KEY.get(fase.value, "")
        for fase in (getattr(practice, "fasi_default", []) or [])
    ]
    keys = [key for key in keys if key]
    if include_compenso_unico and "compenso_unico" not in keys:
        keys.append("compenso_unico")
    return keys


def _rule_code_for_practice(practice_id: str) -> str:
    regola = default_rule_for_practice(practice_id)
    return _text((regola or {}).get("rule_code") or (regola or {}).get("profile_code"))


def _profile_has_compenso_unico(practice_id: str, rule_code: str = "") -> bool:
    regola = rule_lookup(rule_code) if rule_code else None
    if not regola:
        regola = default_rule_for_practice(practice_id)
    profile = (regola or {}).get("profile", {}) or {}
    phase_keys = [str(item or "") for item in (profile.get("phase_keys") or []) if str(item or "")]
    return profile.get("calc_mode") == "compenso_unico" or "compenso_unico" in phase_keys


def _calculation_targets(payload: dict[str, Any], primary_practice_id: str) -> list[str]:
    targets: list[str] = []
    classifications = payload.get("classificazioni_tassonomiche")
    if isinstance(classifications, list):
        for row in classifications:
            if not isinstance(row, dict):
                continue
            practice_id = _text(row.get("tipologia_pratica_id") or row.get("id_pratica"))
            if practice_id and practice_id not in targets:
                targets.append(practice_id)
    if primary_practice_id and primary_practice_id not in targets:
        targets.append(primary_practice_id)
    return targets or ([primary_practice_id] if primary_practice_id else [])


def build_react_preventivo_wizard_calculation_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    state = _state(payload)
    practice_id = state["id_pratica"]
    if not practice_id:
        return {"ok": False, "state": state, "warnings": [_warning("id_pratica_mancante", "Seleziona una tipologia pratica prima del calcolo.")]}
    tp = get_tipo_pratica(practice_id)
    if not tp:
        return {"ok": False, "state": state, "warnings": [_warning("tipologia_non_trovata", f"Tipologia non trovata: {practice_id}.")]}
    form = WizardPayloadForm({**state, **payload})
    variations, increases = _variation_payload(form, tp)
    mediazione_context = parse_mediazione_odm_context(form)
    livello = livello_compenso_da_complessita(state["complessita"])
    perc_spese = _parse_num(state["perc_spese_generali"], 15.0) / 100.0
    anticipazioni_base = _parse_num(state["anticipazioni"], 0.0)
    taxable_rows: list[dict[str, Any]] = []
    extra_rows: list[dict[str, Any]] = []
    target_results: list[dict[str, Any]] = []
    target_ids = _calculation_targets(payload, practice_id)

    for target_index, target_id in enumerate(target_ids, start=1):
        target_tp = get_tipo_pratica(target_id)
        if not target_tp:
            continue
        target_state = dict(state)
        target_state["id_pratica"] = target_id
        target_regola = state["regola_tariffaria"] if target_id == practice_id else _rule_code_for_practice(target_id)
        if target_regola and target_regola not in {str(row.get("rule_code", "") or "") for row in rules_for_practice(target_id)}:
            target_regola = ""
        target_state["regola_tariffaria"] = target_regola
        if target_id != practice_id:
            selected_phase_keys = [_text(item) for item in state.get("fasi", []) if _text(item)]
            if selected_phase_keys:
                target_state["fasi"] = [
                    key
                    for key in selected_phase_keys
                    if key != "compenso_unico" or _profile_has_compenso_unico(target_id, target_regola)
                ]
            else:
                include_unico = "compenso_unico" in (state.get("fasi") or []) and _profile_has_compenso_unico(target_id, target_regola)
                target_state["fasi"] = _phase_keys_for_practice(target_tp, include_compenso_unico=include_unico)
            target_state["grado"] = _enum(getattr(target_tp, "grado_default", ""))
        grado = _GRADE_MAP.get(target_state["grado"]) if target_state["grado"] else None
        fasi, profile_override = _phase_selection(target_state, target_id)
        ris = motore_calcola(
            id_pratica=target_id,
            valore_controversia=_parse_num(state["valore"], 0.0),
            grado=grado,
            regola_tariffaria=target_regola,
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
            anticipazioni=0.0,
        )
        dm = ris.calcolo_dm55
        level_summary = dm.riepilogo_livello(livello)
        target_bonus = round(float(level_summary.get("bonus_telematico", 0.0)), 2)
        target_spese = round(float(level_summary.get("spese_generali", 0.0)), 2)
        target_compenso = round(float(level_summary.get("subtotale", ris.onorario_selezionato)) + target_bonus, 2)
        taxable_rows.append(
            {
                "id": f"compenso_{target_index}_{target_id}",
                "descrizione": f"Compenso professionale per {target_tp.label} - {dm.scaglione}",
                "tipo": TipoVoce.ONORARIO.value,
                "importo": target_compenso,
                "importo_label": _money(target_compenso),
                "fiscale": "imponibile",
                "source": "motore",
                "locked": False,
            }
        )
        if state["spese_generali"] and target_spese > 0:
            taxable_rows.append(
                {
                    "id": f"spese_generali_{target_index}_{target_id}",
                    "descrizione": f"Spese generali {int(round(dm.perc_spese_generali * 100))}% - {target_tp.label}",
                    "tipo": TipoVoce.SPESA_FORFETTARIA.value,
                    "importo": target_spese,
                    "importo_label": _money(target_spese),
                    "fiscale": "imponibile",
                    "source": "motore",
                    "locked": False,
                }
            )
        target_mediazione_odm = calcola_mediazione_odm_da_context(_parse_num(state["valore"], 0.0), mediazione_context) if is_mediazione_practice(target_tp) else None
        if target_mediazione_odm:
            amount = round(float(target_mediazione_odm.get("totale_organismo") or 0.0), 2)
            extra_rows.append(
                {
                    "id": f"mediazione_odm_{target_index}_{target_id}",
                    "descrizione": target_mediazione_odm.get("voce_label") or f"Costi organismo mediazione D.M. 150/2023 - {target_tp.label}",
                    "tipo": TipoVoce.SPESA_VIVA.value,
                    "importo": amount,
                    "importo_label": _money(amount),
                    "fiscale": "anticipazione_art15",
                    "source": "mediazione_odm",
                    "locked": False,
                }
            )
        target_results.append(
            {
                "id": target_id,
                "label": target_tp.label,
                "tp": target_tp,
                "ris": ris,
                "dm": dm,
                "compenso": target_compenso,
                "bonus": target_bonus,
                "spese_generali": target_spese,
                "regola": target_regola,
                "mediazione_odm": target_mediazione_odm,
            }
        )
    if not target_results:
        return {"ok": False, "state": state, "warnings": [_warning("tipologie_non_calcolabili", "Nessuna tipologia pratica calcolabile nella bozza.")]}
    primary_result = next((item for item in target_results if item["id"] == practice_id), target_results[0])
    dm = primary_result["dm"]
    regola = _text(primary_result["regola"])
    resolved_expenses = _resolved_practice_expenses(
        tp,
        value=_parse_num(state["valore"], 0.0),
        grade_label=state["grado"],
    )
    bonus = round(sum(float(item["bonus"] or 0.0) for item in target_results), 2)
    spese_generali = round(sum(float(item["spese_generali"] or 0.0) for item in target_results), 2)
    compenso = round(sum(float(item["compenso"] or 0.0) for item in target_results), 2)
    mediazione_odm = next((item["mediazione_odm"] for item in target_results if item.get("mediazione_odm")), None)
    art15 = anticipazioni_base
    art15 += sum(float(row.get("importo") or 0.0) for row in extra_rows)
    selected_expenses = set(state.get("esborsi") or [])
    for index, item in enumerate(resolved_expenses, start=1):
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
    multi_target = len(target_results) > 1
    fasi_out: dict[str, dict[str, float]] = {}
    for item in target_results:
        item_dm = item["dm"]
        for fase, values in item_dm.dettaglio.items():
            key = f"{item['label']} - {fase}" if multi_target else fase
            fasi_out[key] = {"min": values[0], "base": values[1], "max": values[2]}
    note_calcolo = " | ".join(
        f"{item['label']}: {item['dm'].note}"
        for item in target_results
        if _text(item["dm"].note)
    )
    dm_dict = dm.to_dict()
    audit_tariffario = dm_dict.get("audit_tariffario") if isinstance(dm_dict.get("audit_tariffario"), dict) else {}
    riferimenti_normativi = dm_dict.get("riferimenti_normativi") if isinstance(dm_dict.get("riferimenti_normativi"), list) else []
    reference_codes = dm_dict.get("reference_codes") if isinstance(dm_dict.get("reference_codes"), list) else []
    deontologia = _deontologia_wizard_payload(payload)
    log_context = costruisci_contesto_economico(
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
            "nota": note_calcolo or dm.note,
            "voci_area_pratica": [item["label"] for item in target_results],
            "table_code": dm_dict.get("table_code", ""),
            "table_label": dm_dict.get("table_label", ""),
            "rule_code": dm_dict.get("rule_code", ""),
            "rule_label": dm_dict.get("rule_label", ""),
            "exact_snapshot": dm_dict.get("exact_snapshot", False),
            "compliance_status": dm_dict.get("compliance_status", ""),
            "compliance_note": dm_dict.get("compliance_note", ""),
            "reference_codes": reference_codes,
        },
        audit_tariffario=audit_tariffario,
        riferimenti_normativi=riferimenti_normativi,
    )
    log_context["deontologia"] = deontologia
    log = dump_log_calcolo(log_context)
    profile_payload = tp.to_dict()
    profile_payload["esborsi_tipici"] = resolved_expenses
    return {
        "ok": True,
        "state": state,
        "profile": profile_payload,
        "summary": tp.summary,
        "when_to_use": tp.when_to_use,
        "normative_references": tp.normative_references,
        "base_normativa": tp.base_normativa,
        "fasi": fasi_out,
        "scaglione": dm.scaglione,
        "livello_compenso": primary_result["ris"].livello_compenso,
        "bonus_telematico": bonus,
        "spese_generali": spese_generali,
        "compenso_base": compenso,
        "rows": rows,
        "economic": summary,
        "mediazione_odm": mediazione_odm,
        "deontologia": deontologia,
        "note": _text(payload.get("note")) or tp.note_template,
        "warnings": deontologia["warnings"],
        "audit": {
            "log_calcolo": log,
            "audit_tariffario": audit_tariffario,
            "deontologia": deontologia,
            "reference_codes": reference_codes,
            "riferimenti_normativi": riferimenti_normativi,
            "table_code": dm_dict.get("table_code", ""),
            "table_label": dm_dict.get("table_label", ""),
            "rule_code": dm_dict.get("rule_code", ""),
            "rule_label": dm_dict.get("rule_label", ""),
            "exact_snapshot": dm_dict.get("exact_snapshot", False),
            "compliance_status": dm_dict.get("compliance_status", ""),
            "compliance_note": dm_dict.get("compliance_note", ""),
            "source_snapshot": dm_dict.get("source_snapshot", ""),
        },
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
        "actions": {"back": "/preventivi"},
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
