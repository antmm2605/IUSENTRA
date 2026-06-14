"""Catalogo centrale della piattaforma legale operativa."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from pct.legal_platform_seed import LEGAL_PLATFORM_SEED


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _slug(value: Any) -> str:
    text = _clean(value).lower()
    replacements = {
        "a'": "a",
        "e'": "e",
        "i'": "i",
        "o'": "o",
        "u'": "u",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _is_telematic(channel_code: str) -> bool:
    channel = _clean(channel_code).upper()
    return channel in {
        "PCT_CIVILE",
        "PCT_LAVORO",
        "PDP_PENALE",
        "PAT_AMMINISTRATIVO",
        "PTT_TRIBUTARIO",
        "SPORTELLO_PA",
        "PORTALE_MINISTERIALE",
        "PEC_ONLY",
    }


def _default_compensation_mode(area_label: str, channel_code: str) -> str:
    area = _clean(area_label).lower()
    channel = _clean(channel_code).upper()
    if channel in {"PCT_CIVILE", "PCT_LAVORO", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO", "PDP_PENALE"}:
        return "Per fasi processuali (D.M. 55/2014)"
    if area in {"amministrativo", "tributario", "lavoro", "sanitario"}:
        return "Per fasi processuali (D.M. 55/2014)"
    return "Compenso fisso"


def _billing_milestones(proc: "LegalOperationalProcedure") -> list[str]:
    if proc.telematic:
        return [
            "Acconto iniziale e apertura pratica",
            "Sviluppo della fase procedurale e gestione depositi",
            "Definizione, chiusura o esito del procedimento",
        ]
    if proc.area_label in {"Societario", "Compliance", "Privacy e digitale", "Cybersecurity"}:
        return [
            "Kick-off e raccolta documenti",
            "Produzione deliverable o negoziazione",
            "Consegna finale e chiusura incarico",
        ]
    return [
        "Apertura e studio iniziale",
        "Sviluppo della pratica",
        "Chiusura o definizione dell'incarico",
    ]


@dataclass(frozen=True)
class LegalOperationalProcedure:
    code: str
    name: str
    source_wave: str
    area_label: str
    subbranch_code: str
    coverage_mode: str
    operational_priority: int
    channel_code: str
    registry_code: str
    workflow_code: str
    complexity_level: str
    estimated_duration_days: int
    requires_human_review: bool
    requires_hearing: bool
    requires_registry_enrollment: bool
    allows_settlement: bool
    practice_id: str = ""
    act_compiler_model_code: str = ""
    checklist_template_id: str = ""
    fascicolo_type: str = ""
    tariffario_hint: str = ""
    required_documents: tuple[str, ...] = ()
    checklist: tuple[str, ...] = ()
    deadlines: tuple[str, ...] = ()
    template_labels: tuple[str, ...] = ()

    @property
    def slug(self) -> str:
        return _slug(self.name)

    @property
    def telematic(self) -> bool:
        return _is_telematic(self.channel_code)

    @property
    def module_bindings(self) -> dict[str, dict[str, Any]]:
        compensation_mode = _default_compensation_mode(self.area_label, self.channel_code)
        return {
            "preventivo": {
                "tipo_compenso": compensation_mode,
                "tipo_procedimento": self.name,
                "practice_id": self.practice_id,
                "practice_label": self.name,
                "tariffario_hint": self.tariffario_hint,
            },
            "conferimento": {
                "oggetto": f"Conferimento incarico - {self.name}",
                "firma_cliente_richiesta": True,
                "workflow_channel": "ONLINE" if self.telematic else "STUDIO",
            },
            "tariffario": {
                "tariffario_hint": self.tariffario_hint,
                "richiede_valore": compensation_mode == "Per fasi processuali (D.M. 55/2014)",
                "durata_stimata_giorni": self.estimated_duration_days,
            },
            "fascicolo": {
                "tipo": self.fascicolo_type,
                "canale": self.channel_code,
                "registro": self.registry_code,
                "workflow_code": self.workflow_code,
            },
            "parcella": {
                "causale": f"Compenso professionale per {self.name.lower()}",
                "milestones": _billing_milestones(self),
            },
            "fattura": {
                "causale": f"Prestazione professionale - {self.name}",
                "note": f"Workflow {self.workflow_code} | copertura {self.coverage_mode}",
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "slug": self.slug,
            "source_wave": self.source_wave,
            "area_label": self.area_label,
            "subbranch_code": self.subbranch_code,
            "coverage_mode": self.coverage_mode,
            "operational_priority": self.operational_priority,
            "channel_code": self.channel_code,
            "registry_code": self.registry_code,
            "workflow_code": self.workflow_code,
            "complexity_level": self.complexity_level,
            "estimated_duration_days": self.estimated_duration_days,
            "requires_human_review": self.requires_human_review,
            "requires_hearing": self.requires_hearing,
            "requires_registry_enrollment": self.requires_registry_enrollment,
            "allows_settlement": self.allows_settlement,
            "practice_id": self.practice_id,
            "act_compiler_model_code": self.act_compiler_model_code,
            "checklist_template_id": self.checklist_template_id,
            "fascicolo_type": self.fascicolo_type,
            "tariffario_hint": self.tariffario_hint,
            "required_documents": list(self.required_documents),
            "checklist": list(self.checklist),
            "deadlines": list(self.deadlines),
            "template_labels": list(self.template_labels),
            "telematic": self.telematic,
            "module_bindings": self.module_bindings,
        }


PROCEDURE_REGISTRY: dict[str, LegalOperationalProcedure] = {
    row["code"]: LegalOperationalProcedure(
        code=str(row["code"]),
        name=str(row["name"]),
        source_wave=str(row["source_wave"]),
        area_label=str(row["area_label"]),
        subbranch_code=str(row["subbranch_code"]),
        coverage_mode=str(row["coverage_mode"]),
        operational_priority=int(row["operational_priority"]),
        channel_code=str(row["channel_code"]),
        registry_code=str(row["registry_code"]),
        workflow_code=str(row["workflow_code"]),
        complexity_level=str(row["complexity_level"]),
        estimated_duration_days=int(row["estimated_duration_days"]),
        requires_human_review=bool(row["requires_human_review"]),
        requires_hearing=bool(row["requires_hearing"]),
        requires_registry_enrollment=bool(row["requires_registry_enrollment"]),
        allows_settlement=bool(row["allows_settlement"]),
        practice_id=str(row.get("practice_id") or ""),
        act_compiler_model_code=str(row.get("act_compiler_model_code") or ""),
        checklist_template_id=str(row.get("checklist_template_id") or ""),
        fascicolo_type=str(row.get("fascicolo_type") or ""),
        tariffario_hint=str(row.get("tariffario_hint") or ""),
        required_documents=tuple(str(item) for item in row.get("required_documents") or []),
        checklist=tuple(str(item) for item in row.get("checklist") or []),
        deadlines=tuple(str(item) for item in row.get("deadlines") or []),
        template_labels=tuple(str(item) for item in row.get("template_labels") or []),
    )
    for row in LEGAL_PLATFORM_SEED
}

_PRACTICE_INDEX = {
    proc.practice_id: proc.code
    for proc in PROCEDURE_REGISTRY.values()
    if proc.practice_id
}

_KEYWORD_ALIASES = {
    "licenziamento": "PROC_LIC_IMP_001",
    "gdpr": "PROC_PRIV_INF_001",
    "data breach": "PROC_PRIV_DB_001",
    "accesso agli atti": "PROC_ACC_ATTI_001",
    "permesso di costruire": "PROC_PDC_001",
    "permesso di soggiorno": "PROC_PDS_001",
    "responsabilita medica": "PROC_SAN_RM_001",
    "delibera societaria": "PROC_SOC_DEL_001",
    "patto parasociale": "PROC_SOC_PATTI_001",
    "impugnazione delibera": "PROC_SOC_IMP_001",
    "composizione negoziata": "PROC_CCI_NEGO_001",
    "ricorso tributario": "PROC_TRIB_RIC_002",
    "rateizzazione": "PROC_TRIB_RISC_001",
    "riscossione": "PROC_TRIB_RISC_001",
    "appalto": "PROC_APP_GARA_001",
    "gara": "PROC_APP_GARA_001",
    "sanatoria edilizia": "PROC_EDIL_SAN_001",
    "ambientale": "PROC_AMB_SANZ_001",
    "marchio": "PROC_IP_MARCHI_001",
    "cyber": "PROC_CYB_INC_001",
    "disciplinare": "PROC_LAV_DISC_001",
    "consumatore": "PROC_CONS_REC_001",
    "garanzia": "PROC_CONS_REC_001",
    "recesso": "PROC_CONS_REC_001",
}


def get_legal_operational_procedure(code: str) -> LegalOperationalProcedure | None:
    return PROCEDURE_REGISTRY.get(_clean(code))


def list_legal_operational_procedures(
    *,
    coverage_mode: str = "",
    telematic_only: bool | None = None,
    area_label: str = "",
) -> list[LegalOperationalProcedure]:
    procedures = list(PROCEDURE_REGISTRY.values())
    if coverage_mode:
        procedures = [item for item in procedures if item.coverage_mode == _clean(coverage_mode)]
    if telematic_only is True:
        procedures = [item for item in procedures if item.telematic]
    if telematic_only is False:
        procedures = [item for item in procedures if not item.telematic]
    if area_label:
        wanted = _clean(area_label).lower()
        procedures = [item for item in procedures if item.area_label.lower() == wanted]
    return sorted(procedures, key=lambda item: (-item.operational_priority, item.name))


def infer_legal_operational_procedure(
    *,
    procedure_code: str = "",
    practice_id: str = "",
    area_pratica: str = "",
    tipo_procedimento: str = "",
    oggetto: str = "",
) -> LegalOperationalProcedure | None:
    direct = get_legal_operational_procedure(procedure_code)
    if direct:
        return direct

    practice_key = _clean(practice_id)
    if practice_key and practice_key in _PRACTICE_INDEX:
        return PROCEDURE_REGISTRY[_PRACTICE_INDEX[practice_key]]

    haystack = " ".join(
        part.lower()
        for part in (tipo_procedimento, oggetto, area_pratica, practice_id)
        if _clean(part)
    )
    for label, code in _KEYWORD_ALIASES.items():
        if label in haystack and code in PROCEDURE_REGISTRY:
            return PROCEDURE_REGISTRY[code]

    return None


def build_operational_fields(
    *,
    procedure_code: str = "",
    practice_id: str = "",
    area_pratica: str = "",
    tipo_procedimento: str = "",
    oggetto: str = "",
) -> dict[str, Any]:
    procedure = infer_legal_operational_procedure(
        procedure_code=procedure_code,
        practice_id=practice_id,
        area_pratica=area_pratica,
        tipo_procedimento=tipo_procedimento,
        oggetto=oggetto,
    )
    if not procedure:
        return {
            "procedura_operativa_codice": "",
            "procedura_operativa_nome": "",
            "subbranch_operativa_codice": "",
            "workflow_operativo_codice": "",
            "copertura_operativa": "",
            "canale_operativo": "",
            "registro_operativo": "",
            "procedura_operativa": {},
        }
    return {
        "procedura_operativa_codice": procedure.code,
        "procedura_operativa_nome": procedure.name,
        "subbranch_operativa_codice": procedure.subbranch_code,
        "workflow_operativo_codice": procedure.workflow_code,
        "copertura_operativa": procedure.coverage_mode,
        "canale_operativo": procedure.channel_code,
        "registro_operativo": procedure.registry_code,
        "procedura_operativa": procedure.to_dict(),
    }


def catalogo_piattaforma_legale() -> dict[str, Any]:
    procedures = list_legal_operational_procedures()
    by_area: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for item in procedures:
        by_area[item.area_label] = by_area.get(item.area_label, 0) + 1
        by_channel[item.channel_code] = by_channel.get(item.channel_code, 0) + 1
    return {
        "stats": {
            "procedure_totali": len(procedures),
            "procedure_telematiche": len([item for item in procedures if item.telematic]),
            "aree_coperte": len(by_area),
            "canali_coperti": len(by_channel),
        },
        "by_area": by_area,
        "by_channel": by_channel,
        "procedures": [item.to_dict() for item in procedures],
    }


__all__ = [
    "LegalOperationalProcedure",
    "PROCEDURE_REGISTRY",
    "build_operational_fields",
    "catalogo_piattaforma_legale",
    "get_legal_operational_procedure",
    "infer_legal_operational_procedure",
    "list_legal_operational_procedures",
]
