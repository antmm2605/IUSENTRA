"""Profili pratica derivati dal catalogo operativo IUSENTRA."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
import re

from pct.legal_platform_catalog import PROCEDURE_REGISTRY, LegalOperationalProcedure

from .models import PracticeProfile, PracticeRequirement, SlotType


DEPOSITABLE_CHANNELS = {
    "PCT_CIVILE",
    "PCT_LAVORO",
    "PST_GDP",
    "SIGP_GDP",
    "PDP_PENALE",
    "PAT_AMMINISTRATIVO",
    "PTT_TRIBUTARIO",
}

PEC_ONLY_CHANNELS = {"PEC_ONLY", "PEC", "STRAGIUDIZIALE_PEC"}

DEFAULT_BLOCKING_VALIDATORS = [
    "cliente_presente",
    "cliente_cf_valido",
    "cliente_email_presente",
    "avvocato_referente_presente",
    "ufficio_giudiziario_presente",
    "registro_presente",
]

DEFAULT_ECONOMIC_VALIDATORS = [
    "preventivo_accettato",
    "conferimento_firmato",
    "pagamento_acconto_registrato",
]

DEFAULT_DEPOSIT_VALIDATORS = [
    "codice_oggetto_pst_valido",
    "atto_principale_presente",
    "procura_presente",
    "file_presente",
    "file_apribile",
    "hash_calcolato",
    "pdfa_valido",
    "pdf_non_cifrato",
    "dimensione_file_ok",
    "firma_digitale_presente",
    "dati_atto_xml_generabile",
    "busta_generabile",
    "busta_sotto_limite",
    "pec_destinatario_ufficio_valida",
    "oggetto_pec_conforme",
]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text or "documento"


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _has_token(value: str, *tokens: str) -> bool:
    words = _tokens(value)
    return any(token in words for token in tokens)


def _is_main_act_label(value: str) -> bool:
    raw = str(value or "").lower()
    if "atto principale" in raw:
        return True
    return _has_token(raw, "atto", "ricorso", "istanza", "comparsa", "memoria", "appello", "reclamo", "opposizione")


def _slot_type_for(label_or_code: str) -> str:
    raw = str(label_or_code or "").lower()
    if "procura" in raw or "mandato" in raw:
        return SlotType.PROCURA.value
    if "contributo" in raw or "cu" == raw.strip():
        return SlotType.CONTRIBUTO_UNIFICATO.value
    if "marca" in raw or "bollo" in raw:
        return SlotType.MARCA_BOLLO.value
    if "nota" in raw and "iscrizione" in raw:
        return SlotType.NOTA_ISCRIZIONE_RUOLO.value
    if "ricev" in raw:
        return SlotType.RICEVUTA.value
    if "provved" in raw:
        return SlotType.PROVVEDIMENTO.value
    if _has_token(raw, "contratto", "buste", "paga", "lettera", "prova", "quietanza"):
        return SlotType.DOCUMENTO_PROVA.value
    if _is_main_act_label(raw):
        return SlotType.ATTO_PRINCIPALE.value
    return SlotType.ALLEGATO.value


def _requirement_from(value: Any, *, source: str, index: int = 0) -> PracticeRequirement:
    if isinstance(value, dict):
        key = str(value.get("key") or value.get("code") or _slug(value.get("label") or value.get("title") or "")).upper()
        label = str(value.get("label") or value.get("title") or key).strip()
        required = bool(value.get("required", True))
        blocking = bool(value.get("blocking", required))
        message = str(value.get("message") or "")
        action = str(value.get("suggested_action") or value.get("action") or "")
    else:
        label = str(value or "").strip() or f"Requisito {index + 1}"
        key = _slug(label).upper()
        required = True
        blocking = True
        message = ""
        action = ""
    return PracticeRequirement(
        key=key,
        label=label,
        required=required,
        blocking=blocking,
        source=source,
        message=message,
        suggested_action=action,
    )


def _required_documents(procedure: LegalOperationalProcedure) -> list[PracticeRequirement]:
    rows = [
        _requirement_from(item, source="legal_platform_seed.required_documents", index=index)
        for index, item in enumerate(getattr(procedure, "required_documents", []) or [])
    ]
    labels = {row.label.lower() for row in rows}
    if getattr(procedure, "channel_code", "") in DEPOSITABLE_CHANNELS:
        if not any(_is_main_act_label(label) for label in labels):
            rows.insert(0, PracticeRequirement("ATTO_PRINCIPALE", "Atto principale", True, True, "practice_engine"))
        if not any("procura" in label or "mandato" in label for label in labels):
            rows.insert(1, PracticeRequirement("PROCURA_ALLE_LITI", "Procura alle liti", True, True, "practice_engine"))
    return rows


def _checklist(procedure: LegalOperationalProcedure) -> list[PracticeRequirement]:
    rows = [
        _requirement_from(item, source="legal_platform_seed.checklist", index=index)
        for index, item in enumerate(getattr(procedure, "checklist", []) or [])
    ]
    if not rows:
        rows = [
            PracticeRequirement("VERIFICA_DATI", "Verifica dati cliente e parti", True, True, "practice_engine"),
            PracticeRequirement("VERIFICA_DOCUMENTI", "Completa documenti richiesti", True, True, "practice_engine"),
            PracticeRequirement("VERIFICA_SCADENZE", "Imposta scadenze iniziali", True, False, "practice_engine"),
        ]
    return rows


def _template_labels(procedure: LegalOperationalProcedure) -> list[str]:
    labels = [str(item or "").strip() for item in getattr(procedure, "template_labels", []) or [] if str(item or "").strip()]
    compiler = str(getattr(procedure, "act_compiler_model_code", "") or "").strip()
    if compiler and compiler not in labels:
        labels.append(compiler)
    return labels


def _required_slots(required_docs: list[PracticeRequirement], procedure: LegalOperationalProcedure) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, req in enumerate(required_docs):
        slot_type = _slot_type_for(f"{req.key} {req.label}")
        slot_key = req.key.upper()
        if slot_type == SlotType.ATTO_PRINCIPALE.value:
            slot_key = "ATTO_PRINCIPALE"
        elif slot_type == SlotType.PROCURA.value:
            slot_key = "PROCURA"
        if slot_key in seen:
            slot_key = f"{slot_key}_{index + 1}"
        seen.add(slot_key)
        validators = ["file_presente", "file_apribile", "hash_calcolato"]
        if slot_type == SlotType.ATTO_PRINCIPALE.value:
            validators.extend(["pdfa_valido", "pdf_non_cifrato", "dimensione_file_ok", "firma_digitale_presente"])
        slots.append(
            {
                "slot_key": slot_key,
                "label": req.label,
                "type": slot_type,
                "required": req.required,
                "blocking": req.blocking,
                "validators": validators,
                "sort_order": index + 1,
            }
        )
    if getattr(procedure, "channel_code", "") in DEPOSITABLE_CHANNELS and "RICEVUTE_DEPOSITO" not in seen:
        slots.append(
            {
                "slot_key": "RICEVUTE_DEPOSITO",
                "label": "Ricevute ed esiti deposito",
                "type": SlotType.RICEVUTA.value,
                "required": False,
                "blocking": False,
                "validators": ["ricevuta_finale_presente"],
                "sort_order": len(slots) + 1,
            }
        )
    return slots


def build_profile_from_procedure(procedure: LegalOperationalProcedure) -> PracticeProfile:
    required_docs = _required_documents(procedure)
    channel = str(getattr(procedure, "channel_code", "") or "").strip().upper()
    if str(getattr(procedure, "fascicolo_type", "") or "").strip().upper() == "PENALE" and channel == "AUTORITA_GIUDIZIARIA":
        channel = "PDP_PENALE"
    registry = str(getattr(procedure, "registry_code", "") or "").strip().upper()
    depositable = channel in DEPOSITABLE_CHANNELS
    blocking = list(DEFAULT_BLOCKING_VALIDATORS)
    warnings = list(DEFAULT_ECONOMIC_VALIDATORS)
    if depositable:
        blocking.extend(DEFAULT_DEPOSIT_VALIDATORS)
    if channel in PEC_ONLY_CHANNELS:
        warnings.extend(["ricevuta_pec_monitorata", "risposta_pa_monitorata"])
    return PracticeProfile(
        id=str(getattr(procedure, "code", "") or getattr(procedure, "practice_id", "")),
        code=str(getattr(procedure, "code", "") or getattr(procedure, "practice_id", "")),
        name=str(getattr(procedure, "name", "") or getattr(procedure, "practice_id", "")),
        area=str(getattr(procedure, "area_label", "") or ""),
        fascicolo_type=str(getattr(procedure, "fascicolo_type", "") or "ALTRO"),
        channel=channel,
        registry=registry,
        workflow_code=str(getattr(procedure, "workflow_code", "") or ""),
        practice_id=str(getattr(procedure, "practice_id", "") or ""),
        procedure_code=str(getattr(procedure, "code", "") or ""),
        required_documents=required_docs,
        checklist_items=_checklist(procedure),
        deadlines=list(getattr(procedure, "deadlines", []) or []),
        template_labels=_template_labels(procedure),
        required_slots=_required_slots(required_docs, procedure),
        blocking_validators=blocking,
        warning_validators=warnings,
        depositable=depositable,
        requires_human_review=True,
        requires_hearing=bool(getattr(procedure, "requires_hearing", False)),
        requires_registry_enrollment=bool(getattr(procedure, "requires_registry_enrollment", False) or registry),
        allows_settlement=not str(getattr(procedure, "area_label", "") or "").lower().startswith("penale"),
    )


@lru_cache(maxsize=1)
def _profile_map() -> dict[str, PracticeProfile]:
    profiles = [build_profile_from_procedure(procedure) for procedure in PROCEDURE_REGISTRY.values()]
    profiles.extend(_supplemental_profiles())
    by_key: dict[str, PracticeProfile] = {}
    for profile in profiles:
        for key in {profile.id, profile.code, profile.practice_id, profile.procedure_code, profile.workflow_code}:
            if key:
                by_key[str(key).upper()] = profile
    return by_key


def _supplemental_profiles() -> list[PracticeProfile]:
    lavoro_retribuzione_docs = [
        PracticeRequirement("ATTO_PRINCIPALE", "Atto principale", True, True, "catalogo PST XSD SICI"),
        PracticeRequirement("PROCURA_ALLE_LITI", "Procura alle liti", True, True, "catalogo PST XSD SICI"),
        PracticeRequirement("DOCUMENTI_RETRIBUTIVI", "Documenti retributivi e prove del rapporto", True, True, "catalogo PST XSD SICI"),
        PracticeRequirement("CONTRIBUTO_UNIFICATO", "Contributo unificato e diritti se dovuti", False, False, "catalogo PST XSD SICI"),
    ]
    lavoro_retribuzione = PracticeProfile(
        id="PROC_LAV_RETRIB_001",
        code="PROC_LAV_RETRIB_001",
        name="Retribuzione e differenze retributive",
        area="Lavoro e previdenza",
        fascicolo_type="LAVORO",
        channel="PCT_LAVORO",
        registry="SICID",
        workflow_code="WF_LAVORO_RETRIBUZIONE",
        practice_id="retribuzione_lavoro",
        procedure_code="PROC_LAV_RETRIB_001",
        source="catalogo PST XSD SICI",
        required_documents=lavoro_retribuzione_docs,
        checklist_items=[
            PracticeRequirement("CODICE_OGGETTO_PST", "Codice oggetto PST ufficiale", True, True, "catalogo PST XSD SICI"),
            PracticeRequirement("CLASSIFICAZIONE_ATTI", "Classificazione atto principale e allegati", True, True, "practice_engine"),
            PracticeRequirement("FIRMA_E_BUSTA", "Firma digitale e busta ministeriale", True, True, "practice_engine"),
        ],
        deadlines=[{"title": "Presidiare deposito e ricevute PCT", "due_in_days": 2}],
        template_labels=["Ricorso ex art. 414 c.p.c.", "Memoria rito lavoro"],
        required_slots=[
            {"slot_key": "ATTO_PRINCIPALE", "label": "Atto principale", "type": SlotType.ATTO_PRINCIPALE.value, "required": True, "blocking": True, "validators": ["file_presente", "file_apribile", "hash_calcolato", "pdfa_valido", "pdf_non_cifrato", "dimensione_file_ok", "firma_digitale_presente"], "sort_order": 1},
            {"slot_key": "PROCURA", "label": "Procura alle liti", "type": SlotType.PROCURA.value, "required": True, "blocking": True, "validators": ["file_presente", "file_apribile", "hash_calcolato"], "sort_order": 2},
            {"slot_key": "DOCUMENTI_RETRIBUTIVI", "label": "Documenti retributivi e prove del rapporto", "type": SlotType.DOCUMENTO_PROVA.value, "required": True, "blocking": True, "validators": ["file_presente", "file_apribile", "hash_calcolato"], "sort_order": 3},
            {"slot_key": "CONTRIBUTO_UNIFICATO", "label": "Contributo unificato e diritti se dovuti", "type": SlotType.CONTRIBUTO_UNIFICATO.value, "required": False, "blocking": False, "validators": ["file_presente", "hash_calcolato"], "sort_order": 4},
            {"slot_key": "RICEVUTE_DEPOSITO", "label": "Ricevute ed esiti deposito", "type": SlotType.RICEVUTA.value, "required": False, "blocking": False, "validators": ["ricevuta_finale_presente"], "sort_order": 5},
        ],
        blocking_validators=DEFAULT_BLOCKING_VALIDATORS + DEFAULT_DEPOSIT_VALIDATORS,
        warning_validators=DEFAULT_ECONOMIC_VALIDATORS,
        depositable=True,
        requires_human_review=True,
        requires_registry_enrollment=True,
    )
    sigp_docs = [
        PracticeRequirement("ATTO_PRINCIPALE", "Atto principale", True, True, "docs/SIGP_GIUDICE_DI_PACE.md"),
        PracticeRequirement("PROCURA_ALLE_LITI", "Procura alle liti quando necessaria", False, False, "docs/SIGP_GIUDICE_DI_PACE.md"),
        PracticeRequirement("XSD_SIGP", "Schema XSD SIGP disponibile", True, True, "docs/SIGP_GIUDICE_DI_PACE.md"),
    ]
    sigp = PracticeProfile(
        id="PROC_SIGP_GDP_001",
        code="PROC_SIGP_GDP_001",
        name="Giudice di Pace - sincronizzazione fascicolo telematico",
        area="Civile",
        fascicolo_type="CIVILE",
        channel="SIGP_GDP",
        registry="GDP",
        workflow_code="WF_SIGP_GDP",
        practice_id="sigp_giudice_pace",
        procedure_code="PROC_SIGP_GDP_001",
        source="docs/SIGP_GIUDICE_DI_PACE.md",
        required_documents=sigp_docs,
        checklist_items=[
            PracticeRequirement("NO_SCRAPING", "Usare solo sincronizzazione autorizzata o import guidato", True, True, "docs/SIGP_GIUDICE_DI_PACE.md"),
            PracticeRequirement("LOCAL_CONNECTOR", "Verificare Local Connector e smart card", True, True, "docs/SIGP_GIUDICE_DI_PACE.md"),
        ],
        deadlines=[{"title": "Monitorare esito SIGP", "due_in_days": 3}],
        template_labels=["Ricorso Giudice di Pace", "Istanza Giudice di Pace"],
        required_slots=[
            {"slot_key": "ATTO_PRINCIPALE", "label": "Atto principale", "type": SlotType.ATTO_PRINCIPALE.value, "required": True, "blocking": True, "validators": ["file_presente", "file_apribile", "hash_calcolato", "pdfa_valido", "firma_digitale_presente"], "sort_order": 1},
            {"slot_key": "PROCURA", "label": "Procura alle liti quando necessaria", "type": SlotType.PROCURA.value, "required": False, "blocking": False, "validators": ["file_presente", "file_apribile", "hash_calcolato"], "sort_order": 2},
            {"slot_key": "ESITO_SIGP", "label": "Esito SIGP", "type": SlotType.ESITO_PORTALE.value, "required": False, "blocking": False, "validators": ["ricevuta_finale_presente"], "sort_order": 3},
        ],
        blocking_validators=DEFAULT_BLOCKING_VALIDATORS + DEFAULT_DEPOSIT_VALIDATORS + ["schema_xsd_presente"],
        warning_validators=DEFAULT_ECONOMIC_VALIDATORS,
        depositable=True,
        requires_human_review=True,
        requires_registry_enrollment=True,
    )
    return [lavoro_retribuzione, sigp]


def list_profiles() -> list[PracticeProfile]:
    seen: set[str] = set()
    rows: list[PracticeProfile] = []
    for profile in _profile_map().values():
        if profile.code in seen:
            continue
        seen.add(profile.code)
        rows.append(profile)
    return sorted(rows, key=lambda item: (item.area, item.name, item.code))


def get_profile(code: str) -> PracticeProfile | None:
    return _profile_map().get(str(code or "").strip().upper())
