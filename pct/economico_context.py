"""
Contesto economico condiviso tra tariffario, preventivi, parcelle e FatturaPA.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from pct.legal_platform_catalog import build_operational_fields


def carica_log_calcolo(raw: Any) -> Dict[str, Any]:
    """Carica in modo robusto un contesto di calcolo serializzato."""
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def dump_log_calcolo(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _compact_tariffario_audit(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
    rule_label = str(
        row.get("rule_label")
        or row.get("label")
        or row.get("regola_tariffaria_label")
        or row.get("regola_tariffaria")
        or ""
    ).strip()
    return {
        "rule_code": str(row.get("rule_code") or row.get("regola_tariffaria_code") or "").strip(),
        "rule_label": rule_label,
        "table_code": str(row.get("table_code") or profile.get("table_code") or "").strip(),
        "table_label": str(row.get("table_label") or profile.get("table_label") or "").strip(),
        "compliance_status": str(row.get("compliance_status") or "").strip(),
        "compliance_label": str(row.get("compliance_label") or "").strip(),
        "compliance_badge": str(row.get("compliance_badge") or "").strip(),
        "compliance_note": str(row.get("compliance_note") or "").strip(),
        "snapshot_origin": str(row.get("snapshot_origin") or "").strip(),
        "source_snapshot": str(row.get("source_snapshot") or "").strip(),
    }


def _resolve_tariffario_audit(
    *,
    rule_code: str = "",
    rule_label: str = "",
    practice_id: str = "",
    fallback_rule_value: str = "",
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    compact_existing = _compact_tariffario_audit(existing)
    if compact_existing.get("rule_code"):
        return compact_existing

    try:
        from pct.tariffario_catalogo import default_rule_for_practice, rule_lookup, rules_for_practice
    except Exception:
        return compact_existing

    row: Optional[Dict[str, Any]] = None
    candidate_code = str(rule_code or fallback_rule_value or "").strip()
    if candidate_code:
        row = rule_lookup(candidate_code)

    if row is None and practice_id:
        practice_rows = rules_for_practice(practice_id)
        normalized_label = str(rule_label or fallback_rule_value or "").strip().lower()
        if normalized_label:
            row = next(
                (
                    item for item in practice_rows
                    if str(item.get("rule_label") or item.get("label") or "").strip().lower() == normalized_label
                ),
                None,
            )
        if row is None:
            row = default_rule_for_practice(practice_id)

    return _compact_tariffario_audit(row)


def sincronizza_contesto_economico(raw: Any) -> Dict[str, Any]:
    data = carica_log_calcolo(raw)
    if not data:
        return {}

    audit = _resolve_tariffario_audit(
        rule_code=str(data.get("regola_tariffaria_code") or "").strip(),
        rule_label=str(data.get("regola_tariffaria_label") or "").strip(),
        practice_id=str(data.get("id_pratica") or "").strip(),
        fallback_rule_value=str(data.get("regola_tariffaria") or "").strip(),
        existing=data.get("audit_tariffario"),
    )
    if audit:
        data["audit_tariffario"] = audit
        if audit.get("rule_code"):
            data["regola_tariffaria_code"] = audit["rule_code"]
        if audit.get("rule_label"):
            data["regola_tariffaria_label"] = audit["rule_label"]
            if not str(data.get("regola_tariffaria") or "").strip() or str(data.get("regola_tariffaria") or "").strip() == audit["rule_code"]:
                data["regola_tariffaria"] = audit["rule_label"]

    return data


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _compact_refs(refs: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for ref in refs or []:
        if isinstance(ref, dict):
            title = str(ref.get("title") or "").strip()
            article = str(ref.get("article") or "").strip()
            label = " — ".join(part for part in (title, article) if part)
        else:
            label = str(ref or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def _variation_list(variation_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for fase, raw_pct in (variation_map or {}).items():
        pct = _safe_float(raw_pct)
        if abs(pct) < 0.001:
            continue
        rows.append(
            {
                "fase": str(fase),
                "pct": round(pct, 2),
                "label": f"{fase}: {'+' if pct > 0 else ''}{pct:.0f}%",
            }
        )
    return rows


def costruisci_contesto_economico(
    *,
    source: str,
    source_label: str,
    oggetto: str = "",
    documento_origine: Optional[Dict[str, Any]] = None,
    id_pratica: str = "",
    pratica_label: str = "",
    area_pratica: str = "",
    area_tassonomica: str = "",
    macro_area_tassonomica: str = "",
    sottobranca_tassonomica: str = "",
    tassonomia_codice: str = "",
    procedura_operativa_codice: str = "",
    procedura_operativa_nome: str = "",
    subbranch_operativa_codice: str = "",
    workflow_operativo_codice: str = "",
    copertura_operativa: str = "",
    canale_operativo: str = "",
    registro_operativo: str = "",
    tipo_compenso: str = "",
    tipo_procedimento: str = "",
    grado_sede: str = "",
    regola_tariffaria: str = "",
    regola_tariffaria_code: str = "",
    complessita: str = "",
    valore_controversia: float = 0.0,
    bonus_telematico: bool = False,
    spese_generali: bool = True,
    perc_spese_generali: float = 15.0,
    applica_cpa: bool = True,
    applica_iva: bool = True,
    anticipazioni_art15: float = 0.0,
    adr_accordo: bool = False,
    variazioni_fasi_pct: Optional[Dict[str, Any]] = None,
    accessori: Optional[List[Dict[str, Any]]] = None,
    esborsi: Optional[List[Dict[str, Any]]] = None,
    manual_voci: Optional[List[Dict[str, Any]]] = None,
    risultato: Optional[Dict[str, Any]] = None,
    riferimenti_normativi: Optional[Iterable[Any]] = None,
    riferimenti_tassonomia: Optional[Iterable[Any]] = None,
    classificazioni_tassonomiche: Optional[Iterable[Dict[str, Any]]] = None,
    audit_tariffario: Optional[Dict[str, Any]] = None,
    compenso_a_tempo: Optional[dict] = None,
) -> Dict[str, Any]:
    audit = _resolve_tariffario_audit(
        rule_code=regola_tariffaria_code,
        rule_label=regola_tariffaria,
        practice_id=id_pratica,
        fallback_rule_value=regola_tariffaria,
        existing=audit_tariffario,
    )
    regola_display = str(regola_tariffaria or "").strip()
    if audit.get("rule_label"):
        regola_display = audit["rule_label"]
    regola_code = str(regola_tariffaria_code or "").strip() or str(audit.get("rule_code") or "").strip()

    pratica_text = " ".join(
        part.lower()
        for part in (pratica_label, tipo_procedimento, regola_display)
        if str(part or "").strip()
    )
    operational_fields = build_operational_fields(
        procedure_code=procedura_operativa_codice,
        practice_id=id_pratica,
        area_pratica=area_pratica,
        tipo_procedimento=tipo_procedimento,
        oggetto=oggetto or pratica_label,
    )
    if procedura_operativa_nome and not operational_fields.get("procedura_operativa_nome"):
        operational_fields["procedura_operativa_nome"] = procedura_operativa_nome
    classificazioni_norm = [
        {
            "uid": str(row.get("uid") or "").strip(),
            "area_pratica": str(row.get("area_pratica") or "").strip(),
            "area_tassonomica_code": str(row.get("area_tassonomica_code") or "").strip(),
            "area_tassonomica": str(row.get("area_tassonomica") or "").strip(),
            "macro_area_tassonomica_code": str(row.get("macro_area_tassonomica_code") or "").strip(),
            "macro_area_tassonomica": str(row.get("macro_area_tassonomica") or "").strip(),
            "sottobranca_tassonomica_code": str(row.get("sottobranca_tassonomica_code") or "").strip(),
            "sottobranca_tassonomica": str(row.get("sottobranca_tassonomica") or "").strip(),
            "tassonomia_codice": str(row.get("tassonomia_codice") or "").strip(),
            "tipologia_pratica_id": str(row.get("tipologia_pratica_id") or "").strip(),
            "tipologia_pratica_label": str(row.get("tipologia_pratica_label") or "").strip(),
            "tipo_compenso": str(row.get("tipo_compenso") or "").strip(),
        }
        for row in (classificazioni_tassonomiche or [])
        if isinstance(row, dict)
    ]
    return {
        "source": source,
        "source_label": source_label,
        "created_at": datetime.now().isoformat(),
        "oggetto": oggetto,
        "documento_origine": documento_origine or {},
        "id_pratica": id_pratica,
        "pratica_label": pratica_label,
        "area_pratica": area_pratica,
        "area_tassonomica": area_tassonomica,
        "macro_area_tassonomica": macro_area_tassonomica,
        "sottobranca_tassonomica": sottobranca_tassonomica,
        "tassonomia_codice": tassonomia_codice,
        "procedura_operativa_codice": operational_fields.get("procedura_operativa_codice", procedura_operativa_codice),
        "procedura_operativa_nome": operational_fields.get("procedura_operativa_nome", procedura_operativa_nome),
        "subbranch_operativa_codice": operational_fields.get("subbranch_operativa_codice", subbranch_operativa_codice),
        "workflow_operativo_codice": operational_fields.get("workflow_operativo_codice", workflow_operativo_codice),
        "copertura_operativa": operational_fields.get("copertura_operativa", copertura_operativa),
        "canale_operativo": operational_fields.get("canale_operativo", canale_operativo),
        "registro_operativo": operational_fields.get("registro_operativo", registro_operativo),
        "procedura_operativa": operational_fields.get("procedura_operativa", {}),
        "tipo_compenso": tipo_compenso,
        "tipo_procedimento": tipo_procedimento,
        "grado_sede": grado_sede,
        "regola_tariffaria": regola_display,
        "regola_tariffaria_code": regola_code,
        "regola_tariffaria_label": str(audit.get("rule_label") or regola_display),
        "complessita": complessita,
        "valore_controversia": round(_safe_float(valore_controversia), 2),
        "bonus_telematico": bool(bonus_telematico),
        "spese_generali": bool(spese_generali),
        "perc_spese_generali": round(_safe_float(perc_spese_generali), 2),
        "applica_cpa": bool(applica_cpa),
        "applica_iva": bool(applica_iva),
        "anticipazioni_art15": round(_safe_float(anticipazioni_art15), 2),
        "adr": {
            "enabled": bool(
                variazioni_fasi_pct
                or adr_accordo
                or "mediazion" in pratica_text
                or "negoziazion" in pratica_text
                or " adr" in f" {pratica_text}"
            ),
            "accordo": bool(adr_accordo),
            "variazioni_fasi_pct": dict(variazioni_fasi_pct or {}),
        },
        "accessori": list(accessori or []),
        "esborsi": list(esborsi or []),
        "manual_voci": list(manual_voci or []),
        "risultato": dict(risultato or {}),
        "riferimenti_normativi": _compact_refs(riferimenti_normativi or []),
        "riferimenti_tassonomia": _compact_refs(riferimenti_tassonomia or []),
        "classificazioni_tassonomiche": classificazioni_norm,
        "audit_tariffario": audit,
        "compenso_a_tempo": dict(compenso_a_tempo or {}),
    }


def riepilogo_contesto_economico(raw: Any) -> Dict[str, Any]:
    data = sincronizza_contesto_economico(raw)
    if not data:
        return {}

    adr = data.get("adr") or {}
    result = data.get("risultato") or {}
    compenso_a_tempo = data.get("compenso_a_tempo") if isinstance(data.get("compenso_a_tempo"), dict) else {}
    riferimenti = [row for row in data.get("riferimenti_normativi", []) if row][:4]
    audit = _compact_tariffario_audit(data.get("audit_tariffario"))
    return {
        "source_label": str(data.get("source_label") or data.get("source") or "").strip(),
        "oggetto": str(data.get("oggetto") or "").strip(),
        "documento_origine": data.get("documento_origine") or {},
        "id_pratica": str(data.get("id_pratica") or "").strip(),
        "pratica_label": str(data.get("pratica_label") or "").strip(),
        "area_pratica": str(data.get("area_pratica") or "").strip(),
        "area_tassonomica": str(data.get("area_tassonomica") or "").strip(),
        "macro_area_tassonomica": str(data.get("macro_area_tassonomica") or "").strip(),
        "sottobranca_tassonomica": str(data.get("sottobranca_tassonomica") or "").strip(),
        "tassonomia_codice": str(data.get("tassonomia_codice") or "").strip(),
        "procedura_operativa_codice": str(data.get("procedura_operativa_codice") or "").strip(),
        "procedura_operativa_nome": str(data.get("procedura_operativa_nome") or "").strip(),
        "subbranch_operativa_codice": str(data.get("subbranch_operativa_codice") or "").strip(),
        "workflow_operativo_codice": str(data.get("workflow_operativo_codice") or "").strip(),
        "copertura_operativa": str(data.get("copertura_operativa") or "").strip(),
        "canale_operativo": str(data.get("canale_operativo") or "").strip(),
        "registro_operativo": str(data.get("registro_operativo") or "").strip(),
        "procedura_operativa": data.get("procedura_operativa") or {},
        "tipo_compenso": str(data.get("tipo_compenso") or "").strip(),
        "tipo_procedimento": str(data.get("tipo_procedimento") or "").strip(),
        "grado_sede": str(data.get("grado_sede") or "").strip(),
        "regola_tariffaria": str(data.get("regola_tariffaria") or "").strip(),
        "regola_tariffaria_code": str(data.get("regola_tariffaria_code") or audit.get("rule_code") or "").strip(),
        "regola_tariffaria_label": str(data.get("regola_tariffaria_label") or audit.get("rule_label") or data.get("regola_tariffaria") or "").strip(),
        "complessita": str(data.get("complessita") or "").strip(),
        "valore_controversia": round(_safe_float(data.get("valore_controversia")), 2),
        "bonus_telematico": bool(data.get("bonus_telematico")),
        "spese_generali": bool(data.get("spese_generali")),
        "perc_spese_generali": round(_safe_float(data.get("perc_spese_generali")), 2),
        "applica_cpa": bool(data.get("applica_cpa", True)),
        "applica_iva": bool(data.get("applica_iva", True)),
        "anticipazioni_art15": round(_safe_float(data.get("anticipazioni_art15")), 2),
        "adr_enabled": bool(adr.get("enabled")),
        "adr_accordo": bool(adr.get("accordo")),
        "variazioni_fasi": _variation_list(adr.get("variazioni_fasi_pct") or {}),
        "riferimenti_normativi": riferimenti,
        "riferimenti_tassonomia": [row for row in data.get("riferimenti_tassonomia", []) if row][:4],
        "classificazioni_tassonomiche": [
            row for row in (data.get("classificazioni_tassonomiche") or []) if isinstance(row, dict)
        ][:6],
        "scaglione": str(result.get("scaglione") or "").strip(),
        "onorario_base": round(_safe_float(result.get("onorario_base")), 2),
        "cpa": round(_safe_float(result.get("cpa")), 2),
        "iva": round(_safe_float(result.get("iva")), 2),
        "totale": round(_safe_float(result.get("totale")), 2),
        "nota": str(result.get("nota") or result.get("note") or "").strip(),
        "audit_tariffario": audit,
        "compenso_a_tempo": {
            "source": str(compenso_a_tempo.get("source") or "").strip(),
            "source_label": str(compenso_a_tempo.get("source_label") or "").strip(),
            "fonte_normativa": str(compenso_a_tempo.get("fonte_normativa") or "").strip(),
            "tariffa_oraria": round(_safe_float(compenso_a_tempo.get("tariffa_oraria")), 2),
            "ore_fatturabili": round(_safe_float(compenso_a_tempo.get("ore_fatturabili")), 4),
            "criterio_arrotondamento": str(compenso_a_tempo.get("criterio_arrotondamento") or "").strip(),
            "compenso_base": round(_safe_float(compenso_a_tempo.get("compenso_base")), 2),
            "warnings": list(compenso_a_tempo.get("warnings") or []),
        } if compenso_a_tempo else {},
    }


def causale_documento_economico(note: str = "", raw_context: Any = None, max_len: int = 200) -> str:
    base = str(note or "").strip()
    summary = riepilogo_contesto_economico(raw_context)

    tags: List[str] = []
    pratica = summary.get("pratica_label") or summary.get("tipo_procedimento") or summary.get("procedura_operativa_nome")
    if pratica:
        tags.append(str(pratica))
    regola = summary.get("regola_tariffaria_label") or summary.get("regola_tariffaria")
    if regola:
        tags.append(f"regola {regola}")
    if summary.get("adr_accordo"):
        tags.append("ADR con accordo")
    elif summary.get("adr_enabled"):
        tags.append("ADR")
    if summary.get("variazioni_fasi"):
        tags.append("variazioni ADR applicate")

    tail = " | ".join(tag for tag in tags if tag)
    if base and tail:
        return f"{base} | {tail}"[:max_len]
    if base:
        return base[:max_len]
    return tail[:max_len]
