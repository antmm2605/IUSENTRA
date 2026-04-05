"""
pct/practice_profiles.py — Registry centralizzato dei profili pratica.

Unifica in un unico oggetto immutabile (PracticeProfile) tutta la conoscenza
operativa di una tipologia di pratica:
  - tassonomia (area / macro / sub / procedimento)
  - template checklist atti
  - policy di firma e deposito telematico
  - binding workflow / onboarding
  - binding conformità pre-deposito
  - riferimenti normativi (ID dal SOURCE_CATALOG di tassonomia_preventivi)

Il PRACTICE_REGISTRY viene costruito al momento dell'import:
  1. genera un profilo base per ogni TipoPratica in CATALOGO
     (canale, registro, grado, tassonomia inferiti automaticamente)
  2. applica i patch espliciti per le pratiche con dati specifici
     (checklist_template_id, workflow binding, conformity binding, …)

API pubblica:
  get_practice_profile(practice_id) -> Optional[PracticeProfile]
  list_practice_profiles(*, channel, area_code) -> List[PracticeProfile]
  profiles_by_channel() -> Dict[str, List[PracticeProfile]]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pct.motore_preventivo import CATALOGO, TipoPratica
from pct.tariffario import Grado, Materia
from pct.tassonomia_preventivi import (
    PRACTICE_NODE_MAP,
    taxonomy_for_practice,
)


# ================================================================
# Dataclasses pubblici
# ================================================================

@dataclass(frozen=True)
class RequiredDocumentRule:
    code: str
    label: str
    required: bool = True
    source: str = ""           # checklist_atto | regola_studio | norma | workflow
    note: str = ""
    accepted_types: List[str] = field(default_factory=list)
    generated_by_system: bool = False


@dataclass(frozen=True)
class SignaturePolicy:
    mode: str = "cades"        # cades | pades
    backend_allowed: List[str] = field(default_factory=lambda: ["pkcs11", "p12", "pem"])
    required: bool = True
    pin_required: bool = False
    batch_pin_session: bool = False
    note: str = ""


@dataclass(frozen=True)
class DepositPolicy:
    enabled: bool = False
    channel: str = ""          # PCT_TELEMATICO | PDP_PENALE | PAT_AMMINISTRATIVO | PTT_TRIBUTARIO | PEC | CARTACEO
    supports_notification: bool = False
    needs_ministerial_xml: bool = False
    needs_predeposit_check: bool = False
    supports_batch_download: bool = False
    official_portal_source: str = ""   # PST | PDP | PAT | PTT | PEC | CARTACEO
    note: str = ""


@dataclass(frozen=True)
class WorkflowBinding:
    workflow_profile_id: str = ""
    onboarding_profile_id: str = ""
    next_step_hint: str = ""
    auto_create_initial_activities: bool = True
    auto_create_initial_deadlines: bool = True


@dataclass(frozen=True)
class ConformityBinding:
    conformity_profile_id: str = ""
    requires_main_document: bool = True
    requires_required_documents: bool = True
    requires_signature: bool = True
    requires_channel_coherence: bool = True
    requires_registry_grade_coherence: bool = False
    requires_fascicolo_min_data: bool = True
    requires_predeposit_ok: bool = False
    blocking_checks: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PracticeProfile:
    # ── chiave unica operativa ─────────────────────────────────
    practice_id: str

    # ── etichette business / UI ────────────────────────────────
    label: str
    short_label: str = ""
    description: str = ""

    # ── tassonomia ────────────────────────────────────────────
    area_code: str = ""
    area_label: str = ""
    macro_code: str = ""
    macro_label: str = ""
    branch_code: str = ""
    branch_label: str = ""
    sub_code: str = ""
    sub_label: str = ""
    procedimento_code: str = ""
    procedimento_label: str = ""
    variant_code: str = ""
    variant_label: str = ""

    # ── collegamenti ai modelli ────────────────────────────────
    template_id: str = ""
    checklist_template_id: str = ""
    act_compiler_model_code: str = ""
    preventive_type_id: str = ""

    # ── contesto procedurale ──────────────────────────────────
    channel: str = ""
    registry: str = ""
    grade: str = ""
    office_scope: str = ""
    rito: str = ""
    materia: str = ""

    # ── documenti richiesti ───────────────────────────────────
    required_documents: List[RequiredDocumentRule] = field(default_factory=list)
    optional_documents: List[RequiredDocumentRule] = field(default_factory=list)

    # ── firma / deposito ─────────────────────────────────────
    signature_policy: SignaturePolicy = field(default_factory=SignaturePolicy)
    deposit_policy: DepositPolicy = field(default_factory=DepositPolicy)

    # ── workflow / conformità ─────────────────────────────────
    workflow: WorkflowBinding = field(default_factory=WorkflowBinding)
    conformity: ConformityBinding = field(default_factory=ConformityBinding)

    # ── norme ────────────────────────────────────────────────
    normative_reference_ids: List[str] = field(default_factory=list)

    # ── metadati ─────────────────────────────────────────────
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    active: bool = True

    # ── helper properties ────────────────────────────────────

    @property
    def taxonomy_path(self) -> List[str]:
        return [v for v in [
            self.area_label,
            self.macro_label,
            self.branch_label,
            self.sub_label,
            self.procedimento_label,
            self.variant_label,
        ] if v]

    @property
    def requires_deposit(self) -> bool:
        return self.deposit_policy.enabled

    @property
    def requires_notification(self) -> bool:
        return self.deposit_policy.supports_notification

    @property
    def required_document_codes(self) -> List[str]:
        return [d.code for d in self.required_documents if d.required]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "practice_id": self.practice_id,
            "label": self.label,
            "short_label": self.short_label,
            "description": self.description,
            "area_code": self.area_code,
            "area_label": self.area_label,
            "macro_code": self.macro_code,
            "macro_label": self.macro_label,
            "branch_code": self.branch_code,
            "branch_label": self.branch_label,
            "sub_code": self.sub_code,
            "sub_label": self.sub_label,
            "procedimento_code": self.procedimento_code,
            "procedimento_label": self.procedimento_label,
            "variant_code": self.variant_code,
            "variant_label": self.variant_label,
            "template_id": self.template_id,
            "checklist_template_id": self.checklist_template_id,
            "act_compiler_model_code": self.act_compiler_model_code,
            "preventive_type_id": self.preventive_type_id,
            "channel": self.channel,
            "registry": self.registry,
            "grade": self.grade,
            "office_scope": self.office_scope,
            "rito": self.rito,
            "materia": self.materia,
            "required_documents": [
                {
                    "code": d.code,
                    "label": d.label,
                    "required": d.required,
                    "source": d.source,
                    "note": d.note,
                    "accepted_types": list(d.accepted_types),
                    "generated_by_system": d.generated_by_system,
                }
                for d in self.required_documents
            ],
            "optional_documents": [
                {
                    "code": d.code,
                    "label": d.label,
                    "required": d.required,
                    "source": d.source,
                    "note": d.note,
                    "accepted_types": list(d.accepted_types),
                    "generated_by_system": d.generated_by_system,
                }
                for d in self.optional_documents
            ],
            "signature_policy": {
                "mode": self.signature_policy.mode,
                "backend_allowed": list(self.signature_policy.backend_allowed),
                "required": self.signature_policy.required,
                "pin_required": self.signature_policy.pin_required,
                "batch_pin_session": self.signature_policy.batch_pin_session,
                "note": self.signature_policy.note,
            },
            "deposit_policy": {
                "enabled": self.deposit_policy.enabled,
                "channel": self.deposit_policy.channel,
                "supports_notification": self.deposit_policy.supports_notification,
                "needs_ministerial_xml": self.deposit_policy.needs_ministerial_xml,
                "needs_predeposit_check": self.deposit_policy.needs_predeposit_check,
                "supports_batch_download": self.deposit_policy.supports_batch_download,
                "official_portal_source": self.deposit_policy.official_portal_source,
                "note": self.deposit_policy.note,
            },
            "workflow": {
                "workflow_profile_id": self.workflow.workflow_profile_id,
                "onboarding_profile_id": self.workflow.onboarding_profile_id,
                "next_step_hint": self.workflow.next_step_hint,
                "auto_create_initial_activities": self.workflow.auto_create_initial_activities,
                "auto_create_initial_deadlines": self.workflow.auto_create_initial_deadlines,
            },
            "conformity": {
                "conformity_profile_id": self.conformity.conformity_profile_id,
                "requires_main_document": self.conformity.requires_main_document,
                "requires_required_documents": self.conformity.requires_required_documents,
                "requires_signature": self.conformity.requires_signature,
                "requires_channel_coherence": self.conformity.requires_channel_coherence,
                "requires_registry_grade_coherence": self.conformity.requires_registry_grade_coherence,
                "requires_fascicolo_min_data": self.conformity.requires_fascicolo_min_data,
                "requires_predeposit_ok": self.conformity.requires_predeposit_ok,
                "blocking_checks": list(self.conformity.blocking_checks),
            },
            "normative_reference_ids": list(self.normative_reference_ids),
            "tags": list(self.tags),
            "notes": self.notes,
            "active": self.active,
            "taxonomy_path": self.taxonomy_path,
        }


# ================================================================
# Costanti interne per l'inference automatica
# ================================================================

# Canale operativo per materia DM 55/2014
_CHANNEL_BY_MATERIA: Dict[Materia, str] = {
    Materia.CIVILE_COGN:             "PCT_TELEMATICO",
    Materia.LAVORO:                  "PCT_TELEMATICO",
    Materia.PREVIDENZA:              "PCT_TELEMATICO",
    Materia.ESEC_IMMO:               "PCT_TELEMATICO",
    Materia.ESEC_MOB:                "PCT_TELEMATICO",
    Materia.VOLONTARIA:              "PCT_TELEMATICO",
    Materia.PENALE:                  "PDP_PENALE",
    Materia.AMMINISTRATIVO:          "PAT_AMMINISTRATIVO",
    Materia.TRIBUTARIO:              "PTT_TRIBUTARIO",
    Materia.STRAGIUD:                "CARTACEO",
    Materia.MEDIAZIONE:              "CARTACEO",
    Materia.NEGOZIAZIONE_ASSISTITA:  "CARTACEO",
    Materia.ARBITRATO:               "CARTACEO",
    Materia.CONTABILE:               "PAT_AMMINISTRATIVO",
    Materia.GIURISDIZIONI_SUPERIORI: "PCT_TELEMATICO",
    Materia.AFFARI_IPOTECARI:        "CARTACEO",
    Materia.CRISI_IMPRESA:           "PCT_TELEMATICO",
}

# Override per singole pratiche (eccezzioni rispetto alla materia)
_CHANNEL_ID_OVERRIDES: Dict[str, str] = {
    # Penale difensivo → deposito via PDP
    "difesa_indagini":          "PDP_PENALE",
    "difesa_gup":               "PDP_PENALE",
    "difesa_monocratico":       "PDP_PENALE",
    "difesa_collegiale":        "PDP_PENALE",
    "difesa_assise":            "PDP_PENALE",
    "riti_alternativi":         "PDP_PENALE",
    "difesa_appello_penale":    "PDP_PENALE",
    "difesa_cassazione_penale": "PDP_PENALE",
    "difesa_cautelari":         "PDP_PENALE",
    "difesa_sorveglianza":      "PDP_PENALE",
    # Penale difensivo consultivo → stragiudiziale
    "consulenza_difensiva":     "CARTACEO",
    "assistenza_vittima_reato": "CARTACEO",
    # Tributario stragiudiziale (grado fuori giudizio)
    "autotutela":               "CARTACEO",
    "accertamento_adesione":    "CARTACEO",
    "consulenza_tributaria":    "CARTACEO",
    "procedure_deflattive":     "CARTACEO",
    "concordato_biennale":      "CARTACEO",
    # Previdenza / penale consultivo
    "assistenza_previdenziale": "CARTACEO",
    "consulenza_penale":        "CARTACEO",
    # Amministrativo accessori stragiudiziali
    "sanzioni_amministrative":  "CARTACEO",
}

_REGISTRY_BY_CHANNEL: Dict[str, str] = {
    "PCT_TELEMATICO":     "RG",
    "PDP_PENALE":         "PENALE",
    "PAT_AMMINISTRATIVO": "RICORSO",
    "PTT_TRIBUTARIO":     "CGT",
    "PEC":                "RG",
    "CARTACEO":           "FUORI_GIUDIZIO",
}

_OFFICE_BY_CHANNEL: Dict[str, str] = {
    "PCT_TELEMATICO":     "Tribunale",
    "PDP_PENALE":         "Procura / Tribunale penale",
    "PAT_AMMINISTRATIVO": "TAR / Consiglio di Stato",
    "PTT_TRIBUTARIO":     "Corte di Giustizia Tributaria",
    "PEC":                "Tribunale",
    "CARTACEO":           "Fuori giudizio",
}

_RITO_BY_MATERIA: Dict[Materia, str] = {
    Materia.CIVILE_COGN:             "Ordinario",
    Materia.LAVORO:                  "Lavoro",
    Materia.PREVIDENZA:              "Previdenza",
    Materia.ESEC_IMMO:               "Esecutivo",
    Materia.ESEC_MOB:                "Esecutivo",
    Materia.VOLONTARIA:              "Volontaria Giurisdizione",
    Materia.PENALE:                  "Penale",
    Materia.AMMINISTRATIVO:          "Amministrativo",
    Materia.TRIBUTARIO:              "Tributario",
    Materia.STRAGIUD:                "Stragiudiziale",
    Materia.MEDIAZIONE:              "ADR / Mediazione",
    Materia.NEGOZIAZIONE_ASSISTITA:  "ADR / Negoziazione Assistita",
    Materia.ARBITRATO:               "Arbitrato",
    Materia.CONTABILE:               "Contabile",
    Materia.GIURISDIZIONI_SUPERIORI: "Cassazione",
    Materia.AFFARI_IPOTECARI:        "Tavolare / Ipotecario",
    Materia.CRISI_IMPRESA:           "Concorsuale",
}

# ── Deposit policy pre-built per canale ─────────────────────────

_SIG_JUDICIAL = SignaturePolicy(
    mode="cades",
    backend_allowed=["pkcs11", "p12", "pem"],
    required=True,
    note="Firma CAdES-BES obbligatoria (D.M. 44/2011 art. 12)",
)
_SIG_PADES = SignaturePolicy(
    mode="pades",
    backend_allowed=["pkcs11", "p12", "pem"],
    required=True,
    note="Firma PAdES (PAT / documenti PDF nativi)",
)
_SIG_OPTIONAL = SignaturePolicy(
    mode="cades",
    backend_allowed=["pkcs11", "p12", "pem"],
    required=False,
    note="Firma raccomandata ma non obbligatoria per attività stragiudiziali",
)

_DEPOSIT_BY_CHANNEL: Dict[str, DepositPolicy] = {
    "PCT_TELEMATICO": DepositPolicy(
        enabled=True,
        channel="PCT_TELEMATICO",
        supports_notification=True,
        needs_ministerial_xml=True,
        needs_predeposit_check=True,
        supports_batch_download=True,
        official_portal_source="PST",
        note=(
            "Deposito tramite redattore atti (Consolle Avvocato / FileSafe / Lextel) → PST Ministero. "
            "Richiede DatiAtto.xml, firma CAdES, busta .enc (D.M. 44/2011)."
        ),
    ),
    "PDP_PENALE": DepositPolicy(
        enabled=True,
        channel="PDP_PENALE",
        supports_notification=False,
        needs_ministerial_xml=False,
        needs_predeposit_check=True,
        supports_batch_download=True,
        official_portal_source="PDP",
        note="Deposito penale via PDP REST API con mTLS (D.Lgs. 150/2022 + D.M. 217/2023).",
    ),
    "PAT_AMMINISTRATIVO": DepositPolicy(
        enabled=True,
        channel="PAT_AMMINISTRATIVO",
        supports_notification=False,
        needs_ministerial_xml=False,
        needs_predeposit_check=True,
        supports_batch_download=True,
        official_portal_source="PAT",
        note="Deposito amministrativo via PAT SOAP/SIGA (D.P.C.M. 16/02/2016).",
    ),
    "PTT_TRIBUTARIO": DepositPolicy(
        enabled=True,
        channel="PTT_TRIBUTARIO",
        supports_notification=False,
        needs_ministerial_xml=False,
        needs_predeposit_check=False,
        supports_batch_download=False,
        official_portal_source="PTT",
        note="Deposito tributario via Portale della Giustizia Tributaria (MEF / PTT / SIGIT).",
    ),
    "PEC": DepositPolicy(
        enabled=True,
        channel="PEC",
        supports_notification=False,
        needs_ministerial_xml=False,
        needs_predeposit_check=False,
        supports_batch_download=False,
        official_portal_source="PEC",
        note="Deposito via PEC diretta alla cancelleria (uffici non ancora telematici).",
    ),
    "CARTACEO": DepositPolicy(
        enabled=False,
        channel="CARTACEO",
        official_portal_source="CARTACEO",
        note="Attività stragiudiziale o deposito fisico in cancelleria.",
    ),
}

_SIG_BY_CHANNEL: Dict[str, SignaturePolicy] = {
    "PCT_TELEMATICO":     _SIG_JUDICIAL,
    "PDP_PENALE":         _SIG_JUDICIAL,
    "PAT_AMMINISTRATIVO": _SIG_PADES,
    "PTT_TRIBUTARIO":     _SIG_JUDICIAL,
    "PEC":                _SIG_JUDICIAL,
    "CARTACEO":           _SIG_OPTIONAL,
}

# ================================================================
# Patch espliciti per pratiche con dati specifici
# (checklist_template_id, workflow/conformity binding, note, ...)
# Ogni dict si fonde sopra il profilo base auto-generato.
# ================================================================

_PATCHES: Dict[str, Dict[str, Any]] = {

    # ── Civile cognizione ────────────────────────────────────

    "comparsa_risposta": {
        "checklist_template_id": "comparsa_risposta",
        "workflow": WorkflowBinding(
            workflow_profile_id="comparsa_risposta",
            onboarding_profile_id="comparsa_risposta",
            next_step_hint="Verificare subito il termine di costituzione (art. 166 c.p.c.)",
        ),
        "conformity": ConformityBinding(
            conformity_profile_id="comparsa_risposta",
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_costituzione"],
        ),
    },

    "decreto_ingiuntivo": {
        "checklist_template_id": "decreto_ingiuntivo",
        "workflow": WorkflowBinding(
            workflow_profile_id="decreto_ingiuntivo",
            next_step_hint="Verificare prova scritta ex art. 634 c.p.c. prima del deposito",
        ),
        "conformity": ConformityBinding(
            conformity_profile_id="decreto_ingiuntivo",
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "prova_scritta"],
        ),
    },

    "iscrizione_a_ruolo": {
        "checklist_template_id": "iscrizione_a_ruolo",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "atto_citazione": {
        "checklist_template_id": "iscrizione_a_ruolo",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "memoria_difensiva": {
        "checklist_template_id": "memoria_difensiva",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "appello_civile": {
        "checklist_template_id": "ricorso_appello",
        "workflow": WorkflowBinding(
            workflow_profile_id="appello_civile",
            next_step_hint="Verificare termini impugnazione (art. 325 c.p.c.)",
        ),
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_impugnazione"],
        ),
    },

    "appello_famiglia_minori": {
        "checklist_template_id": "ricorso_appello",
    },

    "cassazione_civile": {
        "checklist_template_id": "ricorso_appello",
    },

    "cassazione_lavoro": {
        "checklist_template_id": "ricorso_appello",
    },

    "appello_lavoro": {
        "checklist_template_id": "ricorso_appello",
    },

    # ── Opposizioni ──────────────────────────────────────────

    "opposizione_di": {
        "checklist_template_id": "opposizione_decreto_ingiuntivo",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_opposizione"],
        ),
    },

    "opposizione_esecutiva": {
        "checklist_template_id": "opposizione_decreto_ingiuntivo",
    },

    "opposizione_atti_esecutivi": {
        "checklist_template_id": "opposizione_decreto_ingiuntivo",
    },

    # ── Esecuzioni ───────────────────────────────────────────

    "precetto": {
        "checklist_template_id": "atto_precetto",
        "conformity": ConformityBinding(
            requires_predeposit_ok=False,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "pignoramento": {
        "checklist_template_id": "pignoramento",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "esecuzione_immobiliare": {
        "checklist_template_id": "pignoramento",
    },

    "esecuzione_mobiliare": {
        "checklist_template_id": "pignoramento",
    },

    "esecuzione_terzi": {
        "checklist_template_id": "pignoramento",
    },

    # ── Cautelari / istruzione ───────────────────────────────

    "istruzione_preventiva": {
        "checklist_template_id": "ricorso_cautelare",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "cautelare_civile": {
        "checklist_template_id": "ricorso_cautelare",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    # ── ADR ─────────────────────────────────────────────────

    "mediazione": {
        "checklist_template_id": "mediazione",
        "workflow": WorkflowBinding(
            workflow_profile_id="mediazione",
            next_step_hint="Depositare domanda di mediazione entro i termini (D.Lgs. 28/2010)",
        ),
    },

    # ── Penale ───────────────────────────────────────────────

    "denuncia_querela": {
        "checklist_template_id": "denuncia_querela",
        "workflow": WorkflowBinding(
            workflow_profile_id="denuncia_querela",
            next_step_hint="Verificare termini di querela (art. 124 c.p.)",
        ),
        "conformity": ConformityBinding(
            conformity_profile_id="denuncia_querela",
            requires_signature=False,
            requires_predeposit_ok=True,
            blocking_checks=["termine_querela"],
        ),
    },

    "nomina_difensore": {
        "checklist_template_id": "nomina_difensore",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "impugnazioni_penali": {
        "checklist_template_id": "appello_penale",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_impugnazione"],
        ),
    },

    "difesa_appello_penale": {
        "checklist_template_id": "appello_penale",
    },

    "difesa_cassazione_penale": {
        "checklist_template_id": "appello_penale",
    },

    "opposizione_archiviazione": {
        "checklist_template_id": "opposizione_archiviazione",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["termine_opposizione_archiviazione"],
        ),
    },

    "rinuncia_revoca_mandato": {
        "checklist_template_id": "rinuncia_revoca_mandato",
    },

    # ── Amministrativo ───────────────────────────────────────

    "ricorso_tar": {
        "checklist_template_id": "ricorso_tar",
        "workflow": WorkflowBinding(
            workflow_profile_id="ricorso_tar",
            next_step_hint="Verificare termine decadenziale 60 giorni (art. 29 c.p.a.)",
        ),
        "conformity": ConformityBinding(
            conformity_profile_id="ricorso_tar",
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_decadenziale_60gg"],
        ),
    },

    "cautelare_sospensiva": {
        "checklist_template_id": "ricorso_cautelare",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "motivi_aggiunti": {
        "checklist_template_id": "ricorso_tar",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido"],
        ),
    },

    "appello_cds": {
        "checklist_template_id": "ricorso_appello",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_impugnazione"],
        ),
    },

    # ── Tributario ───────────────────────────────────────────

    "ricorso_tributario": {
        "checklist_template_id": "ricorso_tributario",
        "workflow": WorkflowBinding(
            workflow_profile_id="ricorso_tributario",
            next_step_hint="Verificare termine 60 giorni dalla notifica atto (D.Lgs. 546/92 art. 21)",
        ),
        "conformity": ConformityBinding(
            conformity_profile_id="ricorso_tributario",
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_ricorso_tributario"],
        ),
    },

    "appello_tributario": {
        "checklist_template_id": "appello_tributario",
        "conformity": ConformityBinding(
            requires_predeposit_ok=True,
            blocking_checks=["certificato_firma_valido", "termine_impugnazione"],
        ),
    },

}


# ================================================================
# Factory: costruisce un PracticeProfile da TipoPratica + taxo + patch
# ================================================================

def _infer_channel(tp: TipoPratica) -> str:
    """Canale operativo: prima i override per ID, poi la materia, poi fuori giudizio."""
    if tp.id in _CHANNEL_ID_OVERRIDES:
        return _CHANNEL_ID_OVERRIDES[tp.id]
    if tp.grado_default in (Grado.FUORI_GIUDIZIO, Grado.PROCEDURA_ADR):
        return "CARTACEO"
    return _CHANNEL_BY_MATERIA.get(tp.materia, "CARTACEO")


def _build_profile(tp: TipoPratica, taxo: Dict[str, Any], patch: Dict[str, Any]) -> PracticeProfile:
    channel = _infer_channel(tp)
    deposit_policy = patch.get("deposit_policy", _DEPOSIT_BY_CHANNEL[channel])
    signature_policy = patch.get("signature_policy", _SIG_BY_CHANNEL[channel])
    workflow = patch.get("workflow", WorkflowBinding())
    conformity = patch.get("conformity", ConformityBinding(
        requires_predeposit_ok=deposit_policy.enabled and deposit_policy.needs_predeposit_check,
    ))

    source_ids = [
        s.get("id", "")
        for s in taxo.get("sources", [])
        if s.get("id")
    ]

    return PracticeProfile(
        practice_id=tp.id,
        label=tp.label,
        short_label=tp.label,
        description=tp.summary or "",

        area_code=taxo.get("area_code", ""),
        area_label=taxo.get("area_label", ""),
        macro_code=taxo.get("macro_code", ""),
        macro_label=taxo.get("macro_label", ""),
        sub_code=taxo.get("sub_code", ""),
        sub_label=taxo.get("sub_label", ""),
        procedimento_code=taxo.get("node_code", ""),
        procedimento_label=taxo.get("description", ""),

        preventive_type_id=tp.id,
        checklist_template_id=patch.get("checklist_template_id", ""),
        template_id=patch.get("template_id", ""),
        act_compiler_model_code=patch.get("act_compiler_model_code", ""),

        channel=channel,
        registry=_REGISTRY_BY_CHANNEL.get(channel, ""),
        grade=tp.grado_default.value,
        office_scope=_OFFICE_BY_CHANNEL.get(channel, ""),
        rito=_RITO_BY_MATERIA.get(tp.materia, ""),
        materia=tp.materia.value,

        required_documents=list(patch.get("required_documents", [])),
        optional_documents=list(patch.get("optional_documents", [])),

        signature_policy=signature_policy,
        deposit_policy=deposit_policy,
        workflow=workflow,
        conformity=conformity,

        normative_reference_ids=source_ids,
        tags=[tp.area.lower().replace(" ", "_")],
        notes=tp.when_to_use or "",
        active=True,
    )


# ================================================================
# Build del registry al momento dell'import
# ================================================================

def _build_registry() -> Dict[str, PracticeProfile]:
    registry: Dict[str, PracticeProfile] = {}
    for tp in CATALOGO:
        if tp.id in PRACTICE_NODE_MAP:
            try:
                taxo = taxonomy_for_practice(tp.id, tp.normative_references)
            except Exception:
                taxo = {}
        else:
            taxo = {}
        patch = _PATCHES.get(tp.id, {})
        registry[tp.id] = _build_profile(tp, taxo, patch)
    return registry


PRACTICE_REGISTRY: Dict[str, PracticeProfile] = _build_registry()


# ================================================================
# API pubblica
# ================================================================

def get_practice_profile(practice_id: str) -> Optional[PracticeProfile]:
    """Restituisce il PracticeProfile per l'id pratica, o None se non trovato."""
    return PRACTICE_REGISTRY.get(practice_id)


def list_practice_profiles(
    *,
    channel: str = "",
    area_code: str = "",
    active_only: bool = True,
) -> List[PracticeProfile]:
    """Restituisce la lista dei profili filtrata per canale e/o area tassonomica."""
    profiles = list(PRACTICE_REGISTRY.values())
    if active_only:
        profiles = [p for p in profiles if p.active]
    if channel:
        profiles = [p for p in profiles if p.channel == channel]
    if area_code:
        profiles = [p for p in profiles if p.area_code == area_code]
    return profiles


def profiles_by_channel() -> Dict[str, List[PracticeProfile]]:
    """Restituisce il registry raggruppato per canale operativo."""
    result: Dict[str, List[PracticeProfile]] = {}
    for p in PRACTICE_REGISTRY.values():
        result.setdefault(p.channel, []).append(p)
    return result
