"""
Contesto economico condiviso tra tariffario, preventivi, parcelle e FatturaPA.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


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
    tipo_compenso: str = "",
    tipo_procedimento: str = "",
    grado_sede: str = "",
    regola_tariffaria: str = "",
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
) -> Dict[str, Any]:
    pratica_text = " ".join(
        part.lower()
        for part in (pratica_label, tipo_procedimento, regola_tariffaria)
        if str(part or "").strip()
    )
    return {
        "source": source,
        "source_label": source_label,
        "created_at": datetime.now().isoformat(),
        "oggetto": oggetto,
        "documento_origine": documento_origine or {},
        "id_pratica": id_pratica,
        "pratica_label": pratica_label,
        "area_pratica": area_pratica,
        "tipo_compenso": tipo_compenso,
        "tipo_procedimento": tipo_procedimento,
        "grado_sede": grado_sede,
        "regola_tariffaria": regola_tariffaria,
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
    }


def riepilogo_contesto_economico(raw: Any) -> Dict[str, Any]:
    data = carica_log_calcolo(raw)
    if not data:
        return {}

    adr = data.get("adr") or {}
    result = data.get("risultato") or {}
    riferimenti = [row for row in data.get("riferimenti_normativi", []) if row][:4]
    return {
        "source_label": str(data.get("source_label") or data.get("source") or "").strip(),
        "oggetto": str(data.get("oggetto") or "").strip(),
        "documento_origine": data.get("documento_origine") or {},
        "id_pratica": str(data.get("id_pratica") or "").strip(),
        "pratica_label": str(data.get("pratica_label") or "").strip(),
        "area_pratica": str(data.get("area_pratica") or "").strip(),
        "tipo_compenso": str(data.get("tipo_compenso") or "").strip(),
        "tipo_procedimento": str(data.get("tipo_procedimento") or "").strip(),
        "grado_sede": str(data.get("grado_sede") or "").strip(),
        "regola_tariffaria": str(data.get("regola_tariffaria") or "").strip(),
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
        "scaglione": str(result.get("scaglione") or "").strip(),
        "onorario_base": round(_safe_float(result.get("onorario_base")), 2),
        "cpa": round(_safe_float(result.get("cpa")), 2),
        "iva": round(_safe_float(result.get("iva")), 2),
        "totale": round(_safe_float(result.get("totale")), 2),
        "nota": str(result.get("nota") or result.get("note") or "").strip(),
    }


def causale_documento_economico(note: str = "", raw_context: Any = None, max_len: int = 200) -> str:
    base = str(note or "").strip()
    summary = riepilogo_contesto_economico(raw_context)

    tags: List[str] = []
    pratica = summary.get("pratica_label") or summary.get("tipo_procedimento")
    if pratica:
        tags.append(str(pratica))
    regola = summary.get("regola_tariffaria")
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
