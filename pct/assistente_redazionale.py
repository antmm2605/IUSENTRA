"""
pct/assistente_redazionale.py - Assistente redazionale guidato e deterministico.

Questo modulo collega:
- compilatore atti strutturato
- motore giuridico deterministico
- catalogo versionato degli schemi ministeriali / canali
- riepilogo intelligente con audit persistente
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List

from . import __version__ as APP_VERSION
from .compilatore_atti import (
    get_modello,
    professional_guidance_for_model,
    validate_payload,
)
from .deposito_guidato import (
    LEVEL_BLOCK,
    LEVEL_WARNING,
    OFFICE_CATALOG_VERSION,
    PST_NAMESPACE,
    SCHEMA_CATALOG_VERSION,
    CompetenceResolver,
    ProceduralProfile,
    ValidationIssue,
    ValidatorNormativoRedazionale,
)


REDACTION_RULESET_VERSION = "2026.04.02.1"
MINISTERIAL_SCHEMA_CATALOG_VERSION = "2026.04.02.1"

SERVICE_GIURIDICO = "GIURIDICO"
SERVICE_TECNICO = "TECNICO_MINISTERIALE"
SERVICE_DOCUMENTALE = "DOCUMENTALE"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in norm if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower())
    return " ".join(lowered.split())


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return bool(str(value).strip())


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:
                if _has_value(item):
                    return str(item).strip()
            continue
        if _has_value(value):
            return str(value).strip()
    return ""


def _split_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").replace("\r", "")
    return [line.strip() for line in text.split("\n") if line.strip()]


def _issue_state(issues: Iterable[ValidationIssue], service: str) -> str:
    scoped = [issue for issue in issues if issue.service == service]
    if any(issue.level == LEVEL_BLOCK for issue in scoped):
        return "blocco"
    if any(issue.level == LEVEL_WARNING for issue in scoped):
        return "warning"
    return "ok"


def _overall_state(issues: Iterable[ValidationIssue]) -> str:
    if any(issue.level == LEVEL_BLOCK for issue in issues):
        return "blocco"
    if any(issue.level == LEVEL_WARNING for issue in issues):
        return "warning"
    return "ok"


def _dedupe_sources(*groups: Iterable[Dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for group in groups:
        for item in group or []:
            label = item.get("label", "").strip()
            url = item.get("url", "").strip()
            key = (label, url)
            if not label or key in seen:
                continue
            seen.add(key)
            result.append({"label": label, "url": url})
    return result


def _essential_attachment_keywords() -> dict[str, list[str]]:
    return {
        "procura": ["procura", "mandato", "nomina difensore"],
        "notifica": ["notifica", "relata", "ricevuta pec", "ricevuta consegna"],
        "contributo": ["contributo", "unificato", "pagopa", "f23", "f24"],
        "sentenza": ["sentenza", "ordinanza", "decreto", "provvedimento impugnato"],
        "indice": ["indice", "nota deposito", "indice allegati"],
    }


def _attachment_matches(name: str, keywords: Iterable[str]) -> bool:
    base = _slug(name)
    return any(_slug(keyword) in base for keyword in keywords if keyword)


@dataclass
class SchemaChannelProfile:
    channel: str
    label: str
    schema_version: str
    namespace: str
    family: str
    supports_xml: bool
    supports_busta: bool
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RedactionProfile:
    id: str
    label: str
    tipo_atto_code: str
    channel: str
    materia: str
    rito: str
    giurisdizione: str
    competence_rule: str
    grado: str
    grade_label: str
    registry_suggestion: str
    allowed_registries: List[str] = field(default_factory=list)
    allowed_office_types: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    required_narrative_fields: List[str] = field(default_factory=list)
    required_document_keys: List[str] = field(default_factory=list)
    procedural_note: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_procedural_profile(self) -> ProceduralProfile:
        return ProceduralProfile(
            id=self.id,
            label=self.label,
            tipo_atto_codes=[self.tipo_atto_code],
            channel=self.channel,
            materia=self.materia,
            rito=self.rito,
            giurisdizione=self.giurisdizione,
            grado=self.grado,
            deposit_mode="redazione_guidata",
            allowed_fascicolo_types=["CIVILE", "LAVORO", "FAMIGLIA", "CONSULENZA", "SUCCESSIONI"],
            allowed_office_types=list(self.allowed_office_types),
            allowed_registries=list(self.allowed_registries),
            required_existing_rg="appello" in _slug(self.label) or "comparsa" in _slug(self.label),
            requires_procura="procura" in self.required_document_keys,
            requires_index="indice" in self.required_document_keys,
            requires_contributo="contributo" in self.required_document_keys,
            requires_notification_proof="notifica" in self.required_document_keys,
            requires_sentenza_impugnata="sentenza" in self.required_document_keys,
            required_fields=list(self.required_fields),
            fonti=list(self.sources),
            corrective_hint=self.procedural_note,
        )


@dataclass
class RedactionRun:
    id: str
    created_at: str
    model_code: str
    model_name: str
    fascicolo_id: str
    cliente_id: str
    overall_state: str
    can_generate_preview: bool
    semaforo: Dict[str, str]
    profile: Dict[str, Any]
    schema_channel: Dict[str, Any]
    resolver: Dict[str, Any]
    snapshot: Dict[str, Any]
    sections: List[Dict[str, Any]] = field(default_factory=list)
    required_documents: List[Dict[str, Any]] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GestioneAssistenteRedazionale:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def carica(self) -> list[RedactionRun]:
        if not self.db_path.exists():
            return []
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8") or "[]")
            return [
                RedactionRun(
                    id=item.get("id", ""),
                    created_at=item.get("created_at", ""),
                    model_code=item.get("model_code", ""),
                    model_name=item.get("model_name", ""),
                    fascicolo_id=item.get("fascicolo_id", ""),
                    cliente_id=item.get("cliente_id", ""),
                    overall_state=item.get("overall_state", "warning"),
                    can_generate_preview=bool(item.get("can_generate_preview", False)),
                    semaforo=dict(item.get("semaforo") or {}),
                    profile=dict(item.get("profile") or {}),
                    schema_channel=dict(item.get("schema_channel") or {}),
                    resolver=dict(item.get("resolver") or {}),
                    snapshot=dict(item.get("snapshot") or {}),
                    sections=list(item.get("sections") or []),
                    required_documents=list(item.get("required_documents") or []),
                    next_steps=list(item.get("next_steps") or []),
                    issues=list(item.get("issues") or []),
                    sources=list(item.get("sources") or []),
                )
                for item in raw
                if isinstance(item, dict)
            ]
        except Exception:
            return []

    def salva_run(self, run: RedactionRun, *, limit: int = 250) -> None:
        runs = self.carica()
        runs = [item for item in runs if item.id != run.id]
        runs.insert(0, run)
        payload = [item.to_dict() for item in runs[:limit]]
        self.db_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


SCHEMA_CHANNELS: dict[str, SchemaChannelProfile] = {
    "PCT_TELEMATICO": SchemaChannelProfile(
        channel="PCT_TELEMATICO",
        label="PCT civile / lavoro / famiglia",
        schema_version=SCHEMA_CATALOG_VERSION,
        namespace=PST_NAMESPACE,
        family="DatiAtto.xml / SICID-SIECIC",
        supports_xml=True,
        supports_busta=True,
        sources=[
            {
                "label": "PST - aggiornamento specifiche tecniche deposito atti SICID",
                "url": "https://pst.giustizia.it/PST/page/it/processo_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid_ritualita_immigrati?contentId=NWS3782",
            },
            {
                "label": "PST - documentazione servizi web software house",
                "url": "https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.52_1.pdf",
            },
        ],
    ),
    "PDP_PENALE": SchemaChannelProfile(
        channel="PDP_PENALE",
        label="Portale Deposito Atti Penali (PDP)",
        schema_version="PDP-SNAPSHOT-2023-07-11",
        namespace="https://pst.giustizia.it/pdp",
        family="Specifiche tecniche PDP",
        supports_xml=False,
        supports_busta=False,
        sources=[
            {
                "label": "PST - specifiche tecniche Portale Deposito Atti Penali",
                "url": "https://pst.giustizia.it/PST/page/it/decreto_del_ministro_della_giustizia_del_4_luglio_2023__portale_deposito_atti_penali_pdp_pubblicato_sulla_gu_n_155_del_5_luglio_2023_adozione_delle_specifiche_tecniche?contentId=NWS2789&modelId=4",
            }
        ],
    ),
    "PAT_AMMINISTRATIVO": SchemaChannelProfile(
        channel="PAT_AMMINISTRATIVO",
        label="Processo amministrativo telematico",
        schema_version="PAT-FORMWEB-2026-02-01",
        namespace="https://www.giustizia-amministrativa.it/pat",
        family="Regole tecniche operative PAT",
        supports_xml=False,
        supports_busta=False,
        sources=[
            {
                "label": "Giustizia Amministrativa - Portale avvocato",
                "url": "https://www.giustizia-amministrativa.it/web/guest/portale-avvocato",
            },
            {
                "label": "Giustizia Amministrativa - fine applicazione norme transitorie PAT",
                "url": "https://www.giustizia-amministrativa.it/-/152174-737",
            },
        ],
    ),
    "PTT_TRIBUTARIO": SchemaChannelProfile(
        channel="PTT_TRIBUTARIO",
        label="Processo tributario telematico",
        schema_version="PTT-SIGIT-2019-07-04",
        namespace="https://sigit.giustiziatributaria.gov.it",
        family="SIGIT / PTT",
        supports_xml=False,
        supports_busta=False,
        sources=[
            {
                "label": "MEF - Circolare PTT 4 luglio 2019",
                "url": "https://www.finanze.gov.it/export/sites/finanze/it/.content/Documenti/Varie/prot.-5764-19-Circolare-PTT-4-7-2019.pdf",
            },
            {
                "label": "Portale della Giustizia Tributaria - Telecontenzioso",
                "url": "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
            },
        ],
    ),
    "PEC": SchemaChannelProfile(
        channel="PEC",
        label="Invio / notifica a mezzo PEC",
        schema_version="NESSUN_XSD_MINISTERIALE",
        namespace="mailto:",
        family="Canale PEC senza DatiAtto.xml",
        supports_xml=False,
        supports_busta=False,
        sources=[
            {
                "label": "L. 53/1994 - notificazioni in proprio",
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1994-01-21;53",
            }
        ],
    ),
}


SECTION_FIELD_HINTS: dict[str, list[str]] = {
    "intestazione": ["court_name", "recipient_or_court", "appeal_court", "competent_tar", "competent_tax_court", "proceeding_authority"],
    "parti": ["plaintiff", "defendant", "claimant", "respondent", "appellant", "appellee", "client_or_sender", "counterparty_or_recipient", "assisted_person"],
    "fatto": ["facts", "relevant_facts", "relevant_facts_summary", "contested_facts", "claim_subject", "dispute_background"],
    "posizione_sui_fatti": ["position_on_facts", "defence_on_facts", "client_position", "clarifications_or_objections"],
    "diritto": ["legal_arguments", "legal_analysis", "legal_summary", "grounds_of_opposition", "specific_grounds_of_appeal", "defensive_arguments"],
    "vocatio_in_ius": ["hearing_date", "appearance_notice", "ritual_warnings"],
    "mezzi_istruttori": ["evidence_means", "written_evidence", "admissible_evidence_or_documents", "supporting_documents"],
    "conclusioni": ["requests_or_conclusions", "final_conclusions", "request_for_reform_or_annulment", "specific_requests", "request_content"],
    "atto_impugnato": ["appealed_judgment", "challenged_administrative_act", "challenged_tax_act", "challenged_measure"],
    "allegati": ["attachments_list", "documents_offered", "supporting_attachments", "essential_attachments"],
}


class AssistenteRedazionale:
    def __init__(self, audit_db_path: str = "", office_cache_path: str = "") -> None:
        self.store = GestioneAssistenteRedazionale(audit_db_path) if audit_db_path else None
        self.resolver = CompetenceResolver(office_cache_path=office_cache_path)
        self.legal_validator = ValidatorNormativoRedazionale()

    def analyze(
        self,
        model_code: str,
        payload: Dict[str, Any],
        *,
        fascicolo: Any = None,
        cliente: Any = None,
        utente: Any = None,
    ) -> RedactionRun:
        model = get_modello(model_code)
        if not model:
            raise ValueError(f"Modello non trovato: {model_code}")

        profile = self._build_profile(model, fascicolo=fascicolo)
        schema_channel = SCHEMA_CHANNELS.get(profile.channel, SCHEMA_CHANNELS["PEC"])
        synthetic_fascicolo = self._build_fascicolo_proxy(model, payload, fascicolo=fascicolo, cliente=cliente)
        resolver = self.resolver.resolve(
            synthetic_fascicolo,
            profile.to_procedural_profile(),
            profile.registry_suggestion,
        )

        issues: list[ValidationIssue] = []
        if profile.channel == "PCT_TELEMATICO":
            issues.extend(
                self._validate_pct_legal(
                    profile=profile,
                    model=model,
                    payload=payload,
                    fascicolo=synthetic_fascicolo,
                    resolver=resolver,
                    utente=utente,
                )
            )
        else:
            issues.extend(
                self._validate_non_pct_legal(
                    profile=profile,
                    model=model,
                    payload=payload,
                    resolver=resolver,
                )
            )

        issues.extend(
            self._validate_schema_preview(
                profile=profile,
                resolver=resolver,
                schema_channel=schema_channel,
            )
        )

        sections = self._evaluate_sections(model, payload)
        required_documents = self._evaluate_required_documents(profile, payload)
        issues.extend(self._validate_documental(sections, required_documents))

        semaforo = {
            "giuridico": _issue_state(issues, SERVICE_GIURIDICO),
            "tecnico_ministeriale": _issue_state(issues, SERVICE_TECNICO),
            "documentale": _issue_state(issues, SERVICE_DOCUMENTALE),
        }
        overall = _overall_state(issues)
        sources = _dedupe_sources(
            profile.sources,
            schema_channel.sources,
            [{"label": ref, "url": ""} for ref in professional_guidance_for_model(model_code).get("references", [])],
        )
        run = RedactionRun(
            id=str(uuid.uuid4()),
            created_at=_now_iso(),
            model_code=model["code"],
            model_name=model["name"],
            fascicolo_id=getattr(fascicolo, "id", "") if fascicolo else "",
            cliente_id=getattr(cliente, "id", "") if cliente else "",
            overall_state=overall,
            can_generate_preview=overall != "blocco",
            semaforo=semaforo,
            profile={**asdict(profile), "channel_label": schema_channel.label},
            schema_channel=schema_channel.to_dict(),
            resolver=resolver,
            snapshot={
                "app_version": APP_VERSION,
                "redaction_ruleset_version": REDACTION_RULESET_VERSION,
                "ministerial_schema_catalog_version": MINISTERIAL_SCHEMA_CATALOG_VERSION,
                "compiler_renderer": model.get("renderer", ""),
                "office_catalog_version": OFFICE_CATALOG_VERSION,
            },
            sections=sections,
            required_documents=required_documents,
            next_steps=self._next_steps(issues, sections, required_documents, profile),
            issues=[issue.to_dict() for issue in issues],
            sources=sources,
        )
        if self.store:
            self.store.salva_run(run)
        return run

    def _build_profile(self, model: Dict[str, Any], *, fascicolo: Any = None) -> RedactionProfile:
        area = str(model.get("area", "")).upper()
        name = _slug(model.get("name", ""))
        fascicolo_tipo = str(getattr(getattr(fascicolo, "tipo", None), "value", "")).upper()

        if area == "PENALE":
            return RedactionProfile(
                id="penale_redazionale",
                label=model["name"],
                tipo_atto_code="MEMORIA",
                channel="PDP_PENALE",
                materia="PENALE",
                rito="penale telematico",
                giurisdizione="ordinaria penale",
                competence_rule="Procura / ufficio penale competente per fase e atto depositabile",
                grado="fase_penale",
                grade_label="Autorita procedente",
                registry_suggestion="PDP_ATTI",
                allowed_registries=["PDP_ATTI"],
                allowed_office_types=["PROCURA", "TRIBUNALE", "CORTE_APPELLO", "CORTE_CASSAZIONE"],
                required_fields=["subject", "proceeding_authority", "assisted_person"],
                required_narrative_fields=["facts", "defensive_arguments", "specific_requests"],
                required_document_keys=["procura"],
                procedural_note="Nel penale il deposito dipende dalla fase, dall'autorita e dagli atti effettivamente abilitati sul PDP.",
                sources=SCHEMA_CHANNELS["PDP_PENALE"].sources,
            )

        if area == "AMMINISTRATIVO":
            grado = "appello" if "consiglio di stato" in name or "appello" in name or "reclamo" in name else "primo_grado"
            office_types = ["CDS", "CGARS"] if grado == "appello" else ["TAR"]
            return RedactionProfile(
                id="amministrativo_redazionale",
                label=model["name"],
                tipo_atto_code="RICORSO",
                channel="PAT_AMMINISTRATIVO",
                materia="AMMINISTRATIVO",
                rito="processo amministrativo telematico",
                giurisdizione="amministrativa",
                competence_rule="TAR / Consiglio di Stato / CGARS in base a grado e provvedimento impugnato",
                grado=grado,
                grade_label="TAR" if grado == "primo_grado" else "Consiglio di Stato / CGARS",
                registry_suggestion="PAT_DEP",
                allowed_registries=["PAT_DEP"],
                allowed_office_types=office_types,
                required_fields=["subject", "competent_tar", "claimant", "respondent_administration"],
                required_narrative_fields=["facts", "legal_arguments", "requests_or_conclusions"],
                required_document_keys=["procura", "notifica"],
                procedural_note="Dal 2026 il deposito PAT privilegia Formweb; la PEC resta residuale nei casi tecnici previsti.",
                sources=SCHEMA_CHANNELS["PAT_AMMINISTRATIVO"].sources,
            )

        if area == "TRIBUTARIO":
            grado = "appello" if "appello" in name else "primo_grado"
            return RedactionProfile(
                id="tributario_redazionale",
                label=model["name"],
                tipo_atto_code="RICORSO",
                channel="PTT_TRIBUTARIO",
                materia="TRIBUTARIO",
                rito="processo tributario telematico",
                giurisdizione="tributaria",
                competence_rule="Corte di Giustizia Tributaria competente per grado e sede dell'atto impugnato",
                grado=grado,
                grade_label="CGT",
                registry_suggestion="PTT_RICORSI",
                allowed_registries=["PTT_RICORSI"],
                allowed_office_types=["CGT", "CPT"],
                required_fields=["subject", "competent_tax_court", "claimant", "tax_authority_or_resistant_party"],
                required_narrative_fields=["facts", "legal_arguments", "requests_or_conclusions"],
                required_document_keys=["procura", "notifica", "contributo"],
                procedural_note="In tributario l'atto introduttivo e l'appello seguono il canale SIGIT/PTT con controlli tecnici e documentali dedicati.",
                sources=SCHEMA_CHANNELS["PTT_TRIBUTARIO"].sources,
            )

        if area == "STRAGIUDIZIALE":
            return RedactionProfile(
                id="stragiudiziale_redazionale",
                label=model["name"],
                tipo_atto_code="ATTO_GENERICO",
                channel="PEC",
                materia="STRAGIUDIZIALE",
                rito="fuori giudizio",
                giurisdizione="non contenziosa / stragiudiziale",
                competence_rule="Nessuna busta ministeriale: verifica canale PEC, destinatario e completezza documentale",
                grado="fuori_giudizio",
                grade_label="Fuori giudizio",
                registry_suggestion="PEC",
                allowed_registries=["PEC"],
                allowed_office_types=[],
                required_fields=["subject", "client_or_sender", "counterparty_or_recipient"],
                required_narrative_fields=["facts", "requests_or_conclusions"],
                required_document_keys=[],
                procedural_note="Per gli atti stragiudiziali il controllo tecnico riguarda il canale di invio e la coerenza degli allegati, non il DatiAtto.xml.",
                sources=SCHEMA_CHANNELS["PEC"].sources,
            )

        registry = "VG" if any(token in name for token in ("amministrazione di sostegno", "tutela", "curatela", "congiunto", "consensuale")) else "RG"
        if fascicolo_tipo == "LAVORO" or "lavoro" in name or "previdenza" in name:
            registry = "RGL"
        if any(token in name for token in ("precetto", "pignoramento", "esecuzione")):
            registry = "RGE"
        if "appello" in name:
            office_types = ["TRIBUNALE", "CORTE_APPELLO"]
            degree = "appello"
            competence = "Tribunale o Corte d'Appello in base al giudice che ha emesso il provvedimento impugnato"
            required_docs = ["procura", "sentenza", "contributo"]
        elif "cassazione" in name:
            office_types = ["CORTE_CASSAZIONE"]
            degree = "legittimita"
            competence = "Corte di Cassazione secondo il rito applicabile"
            required_docs = ["procura", "sentenza", "contributo"]
        elif "comparsa" in name or "memoria" in name:
            office_types = ["TRIBUNALE", "GDP", "CORTE_APPELLO"]
            degree = "in_corso_di_causa"
            competence = "Ufficio presso cui pende il fascicolo e registro gia assegnato"
            required_docs = ["procura", "indice"]
        elif "citazione" in name:
            office_types = ["TRIBUNALE", "GDP"]
            degree = "primo_grado"
            competence = "Tribunale o Giudice di Pace in base a materia, valore e territorio"
            required_docs = ["procura", "notifica", "contributo", "indice"]
        elif "decreto ingiuntivo" in name or "monitorio" in name:
            office_types = ["TRIBUNALE", "GDP"]
            degree = "primo_grado"
            competence = "Tribunale o Giudice di Pace in base a materia, valore e territorio"
            required_docs = ["procura", "contributo", "indice"]
        else:
            office_types = ["TRIBUNALE", "GDP"]
            degree = "primo_grado"
            competence = "Tribunale o Giudice di Pace in base a materia, valore e territorio"
            required_docs = ["procura", "contributo"]

        return RedactionProfile(
            id="civile_redazionale",
            label=model["name"],
            tipo_atto_code=self._tipo_atto_for_model_name(name),
            channel="PCT_TELEMATICO",
            materia="CIVILE",
            rito="telematico civile",
            giurisdizione="ordinaria civile",
            competence_rule=competence,
            grado=degree,
            grade_label=self._grade_label_for_profile(degree, registry),
            registry_suggestion=registry,
            allowed_registries=["RG", "RGL", "VG", "RGE"],
            allowed_office_types=office_types,
            required_fields=["id_cliente", "tribunale", "oggetto", "controparte"],
            required_narrative_fields=["facts", "requests_or_conclusions"],
            required_document_keys=required_docs,
            procedural_note="Il motore usa un controllo deterministico su materia, rito, competenza, registro e allegati essenziali prima della bozza finale.",
            sources=SCHEMA_CHANNELS["PCT_TELEMATICO"].sources,
        )

    def _tipo_atto_for_model_name(self, name: str) -> str:
        if "citazione" in name:
            return "ATTO_DI_CITAZIONE"
        if "comparsa" in name:
            return "COMPARSA_RISPOSTA"
        if "decreto ingiuntivo" in name:
            return "DECRETO_INGIUNTIVO"
        if "appello" in name:
            return "APPELLO"
        if "cassazione" in name or "controricorso" in name:
            return "RICORSO_CASSAZIONE"
        if "precetto" in name:
            return "PRECETTO"
        if "ricorso" in name:
            return "RICORSO"
        if "memoria" in name:
            return "MEMORIA"
        return "ATTO_GENERICO"

    def _grade_label_for_profile(self, degree: str, registry: str) -> str:
        mapping = {
            "primo_grado": "Primo grado",
            "appello": "Impugnazione",
            "legittimita": "Cassazione",
            "in_corso_di_causa": "Fascicolo pendente",
            "fuori_giudizio": "Fuori giudizio",
            "fase_penale": "Autorita procedente",
        }
        base = mapping.get(degree, degree.replace("_", " "))
        if registry == "VG":
            return f"{base} / Volontaria Giurisdizione"
        if registry == "RGL":
            return f"{base} / Lavoro"
        if registry == "RGE":
            return f"{base} / Esecuzioni"
        return base

    def _build_fascicolo_proxy(self, model: Dict[str, Any], payload: Dict[str, Any], *, fascicolo: Any = None, cliente: Any = None):
        tribunal = _first_text(
            payload.get("court_name"),
            payload.get("recipient_or_court"),
            payload.get("appeal_court"),
            payload.get("competent_tar"),
            payload.get("competent_tax_court"),
            payload.get("proceeding_authority"),
            getattr(fascicolo, "tribunale", "") if fascicolo else "",
        )
        area = str(model.get("area", "")).upper()
        area_to_fascicolo = {
            "CIVILE": "CIVILE",
            "PENALE": "PENALE",
            "AMMINISTRATIVO": "AMMINISTRATIVO",
            "TRIBUTARIO": "TRIBUTARIO",
            "STRAGIUDIZIALE": "STRAGIUDIZIALE",
        }
        return SimpleNamespace(
            id=getattr(fascicolo, "id", "") if fascicolo else "",
            titolo=_first_text(payload.get("title"), model.get("name", "")),
            oggetto=_first_text(payload.get("subject"), payload.get("claim_subject"), payload.get("request_subject"), model.get("name", "")),
            tribunale=tribunal,
            numero_rg=_first_text(payload.get("proceeding_number"), getattr(fascicolo, "numero_rg", "") if fascicolo else ""),
            anno_rg=getattr(fascicolo, "anno_rg", 0) if fascicolo else 0,
            controparte=_first_text(
                payload.get("counterparty_or_recipient"),
                payload.get("defendant"),
                payload.get("respondent"),
                payload.get("appellee"),
                payload.get("respondent_administration"),
                payload.get("tax_authority_or_resistant_party"),
                getattr(fascicolo, "controparte", "") if fascicolo else "",
            ),
            id_cliente=getattr(cliente, "id", "") if cliente else getattr(fascicolo, "id_cliente", "") if fascicolo else "",
            note=_first_text(payload.get("facts"), payload.get("relevant_facts"), payload.get("relevant_facts_summary")),
            nome_cliente=_first_text(payload.get("client_or_sender"), getattr(cliente, "nome_completo", "") if cliente else ""),
            tipo=SimpleNamespace(value=area_to_fascicolo.get(area, "ALTRO")),
        )

    def _validate_pct_legal(
        self,
        *,
        profile: RedactionProfile,
        model: Dict[str, Any],
        payload: Dict[str, Any],
        fascicolo: Any,
        resolver: Dict[str, Any],
        utente: Any = None,
    ) -> list[ValidationIssue]:
        draft_documents = self._draft_documents(model, payload)
        context = {
            "tipo_atto": profile.tipo_atto_code,
            "codice_registro": profile.registry_suggestion,
            "oggetto": _first_text(payload.get("subject"), payload.get("title"), model["name"]),
            "numero_rg": _first_text(payload.get("proceeding_number"), getattr(fascicolo, "numero_rg", "")),
            "anno_rg": getattr(fascicolo, "anno_rg", 0),
            "atto_principale_id": "__draft__",
            "operatore": getattr(utente, "username", "") if utente else "",
            "id_cliente": getattr(fascicolo, "id_cliente", ""),
            "controparte": getattr(fascicolo, "controparte", ""),
            "recipient_or_court": _first_text(payload.get("court_name"), payload.get("recipient_or_court")),
            "tribunale": fascicolo.tribunale,
        }
        issues = self.legal_validator.validate(
            fascicolo=fascicolo,
            profile=profile.to_procedural_profile(),
            resolver=resolver,
            context=context,
            selected_documents=draft_documents,
            all_documents=draft_documents,
        )
        compiler_errors = validate_payload(model["code"], payload)
        for field_name, error in compiler_errors.items():
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code=f"payload_{field_name}",
                    title=f"Campo redazionale obbligatorio: {field_name}",
                    detail=error,
                    source="Schema compilatore / modello atto",
                    suggested_action=f"Completa il campo '{field_name}' prima di generare la bozza finale.",
                    field=field_name,
                )
            )
        return issues

    def _validate_non_pct_legal(
        self,
        *,
        profile: RedactionProfile,
        model: Dict[str, Any],
        payload: Dict[str, Any],
        resolver: Dict[str, Any],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        compiler_errors = validate_payload(model["code"], payload)
        for field_name, error in compiler_errors.items():
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code=f"payload_{field_name}",
                    title=f"Campo redazionale obbligatorio: {field_name}",
                    detail=error,
                    source="Schema compilatore / modello atto",
                    suggested_action=f"Completa il campo '{field_name}' prima di generare la bozza finale.",
                    field=field_name,
                )
            )
        if profile.allowed_office_types and not resolver.get("office_found"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="ufficio_non_risolto",
                    title="Ufficio / autorita non risolta sul catalogo",
                    detail="La sede indicata non e stata risolta con certezza sul catalogo uffici.",
                    source="Catalogo uffici / regole procedurali interne",
                    suggested_action="Conferma l'ufficio competente o seleziona una sede coerente con il grado scelto.",
                    field="recipient_or_court",
                )
            )
        office_type = resolver.get("office_type", "")
        if office_type and profile.allowed_office_types and office_type not in profile.allowed_office_types:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="competenza_ufficio_errata",
                    title="La sede indicata non e coerente con il canale procedurale",
                    detail=(
                        f"L'ufficio risolto e di tipo {office_type}, ma il profilo '{profile.label}' "
                        f"prevede {', '.join(profile.allowed_office_types)}."
                    ),
                    source="Knowledge base procedurale versionata",
                    suggested_action="Allinea sede, grado o tipologia dell'atto.",
                    field="recipient_or_court",
                )
            )
        return issues

    def _validate_schema_preview(
        self,
        *,
        profile: RedactionProfile,
        resolver: Dict[str, Any],
        schema_channel: SchemaChannelProfile,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if schema_channel.channel == "PEC":
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level="OK",
                    code="pec_no_xsd",
                    title="Canale senza XSD ministeriale",
                    detail="Per questa tipologia non e previsto un DatiAtto.xml ministeriale: il controllo tecnico resta sul canale PEC e sugli allegati.",
                    source="Canale PEC / regola interna versionata",
                    suggested_action="Verifica indirizzo PEC, relata, allegati e prova di invio.",
                )
            )
            return issues

        office_type = resolver.get("office_type", "")
        if schema_channel.channel == "PCT_TELEMATICO":
            if not resolver.get("office_found"):
                issues.append(
                    ValidationIssue(
                        service=SERVICE_TECNICO,
                        level=LEVEL_WARNING,
                        code="schema_office_unresolved",
                        title="Ufficio non ancora risolto per l'anteprima DatiAtto.xml",
                        detail="Finche l'ufficio non e risolto con certezza, il preview dello schema ministeriale resta prudenziale.",
                        source="Catalogo uffici PST",
                        suggested_action="Conferma l'ufficio del fascicolo o indica la sede giudiziaria completa.",
                        field="recipient_or_court",
                    )
                )
            elif profile.allowed_office_types and office_type not in profile.allowed_office_types:
                issues.append(
                    ValidationIssue(
                        service=SERVICE_TECNICO,
                        level=LEVEL_BLOCK,
                        code="schema_office_type_mismatch",
                        title="Tipo ufficio incompatibile con lo schema di deposito",
                        detail=(
                            f"Lo schema PCT previsto per '{profile.label}' non e coerente con un ufficio di tipo {office_type}."
                        ),
                        source="Catalogo schemi ministeriali versionato",
                        suggested_action="Allinea la sede al giudice compatibile prima della generazione della busta.",
                        field="recipient_or_court",
                    )
                )
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level="OK",
                    code="schema_pst_preview",
                    title="Schema ministeriale PST pronto in anteprima",
                    detail=(
                        f"Il modello usa la famiglia {schema_channel.family} con namespace {schema_channel.namespace} "
                        f"e snapshot {schema_channel.schema_version}; la validazione XML finale avverra al pre-deposito."
                    ),
                    source="Catalogo schemi ministeriali versionato",
                    suggested_action="Continua la redazione; il controllo XML definitivo scattera sulla busta reale.",
                )
            )
            return issues

        if profile.allowed_office_types and office_type and office_type not in profile.allowed_office_types:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="schema_channel_office_mismatch",
                    title="Sede incoerente con il canale tecnico selezionato",
                    detail=(
                        f"Il canale {schema_channel.label} non e coerente con un ufficio di tipo {office_type} "
                        f"per la tipologia '{profile.label}'."
                    ),
                    source="Catalogo schemi ministeriali versionato",
                    suggested_action="Verifica la sede / ufficio prima di procedere con la bozza.",
                    field="recipient_or_court",
                )
            )
        issues.append(
            ValidationIssue(
                service=SERVICE_TECNICO,
                level="OK",
                code="schema_channel_preview",
                title="Snapshot tecnico del canale disponibile",
                detail=(
                    f"Il profilo e agganciato al catalogo {schema_channel.schema_version} "
                    f"({schema_channel.family})."
                ),
                source="Catalogo schemi ministeriali versionato",
                suggested_action="Usa questo snapshot per redazione, pre-check e audit del fascicolo.",
            )
        )
        return issues

    def _draft_documents(self, model: Dict[str, Any], payload: Dict[str, Any]) -> list[dict[str, Any]]:
        docs = [
            {
                "id": "__draft__",
                "nome": f"{model['code']}.pdf",
                "tipo": "ATTO_GIUDIZIARIO",
                "dimensione_bytes": max(len(json.dumps(payload, ensure_ascii=False)), 6000),
                "firmato_digitalmente": False,
            }
        ]
        for index, name in enumerate(_split_lines(payload.get("attachments_list")) or list(payload.get("documents_offered") or []), start=1):
            docs.append(
                {
                    "id": f"draft-attachment-{index}",
                    "nome": name,
                    "tipo": "ALLEGATO",
                    "dimensione_bytes": 4096,
                    "firmato_digitalmente": True,
                }
            )
        return docs

    def _evaluate_sections(self, model: Dict[str, Any], payload: Dict[str, Any]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for section in model.get("sections", []):
            candidates = list(SECTION_FIELD_HINTS.get(section, []))
            if not candidates:
                if "fatto" in section:
                    candidates = ["facts", "relevant_facts", "relevant_facts_summary"]
                elif "diritto" in section or "motivi" in section:
                    candidates = ["legal_arguments", "legal_analysis", "specific_grounds_of_appeal", "grounds_of_opposition"]
                elif "conclusion" in section or "richiest" in section:
                    candidates = ["requests_or_conclusions", "final_conclusions", "request_content"]
                elif "alleg" in section:
                    candidates = ["attachments_list", "documents_offered", "supporting_attachments"]
            filled = [field for field in candidates if _has_value(payload.get(field))]
            if not candidates:
                state = "ok"
                detail = "Sezione gestita dal renderer del modello."
            elif len(filled) == 0:
                state = "missing"
                detail = "Nessun contenuto rilevato nei campi collegati a questa sezione."
            elif len(filled) < len(candidates):
                state = "partial"
                detail = f"Sezione avviata con {len(filled)} campo/i compilati su {len(candidates)} collegati."
            else:
                state = "ok"
                detail = "Sezione completa rispetto ai campi strutturati collegati."
            sections.append(
                {
                    "key": section,
                    "label": section.replace("_", " ").title(),
                    "state": state,
                    "detail": detail,
                    "filled_fields": filled,
                    "fields": candidates,
                }
            )
        return sections

    def _evaluate_required_documents(self, profile: RedactionProfile, payload: Dict[str, Any]) -> list[dict[str, Any]]:
        attachments = _split_lines(payload.get("attachments_list")) or list(payload.get("documents_offered") or [])
        keyword_map = _essential_attachment_keywords()
        result: list[dict[str, Any]] = []
        for key in profile.required_document_keys:
            keywords = keyword_map.get(key, [key])
            matched = [name for name in attachments if _attachment_matches(name, keywords)]
            label_map = {
                "procura": "Procura / nomina difensore",
                "notifica": "Relata / ricevute di notifica",
                "contributo": "Ricevuta contributo unificato",
                "sentenza": "Sentenza o provvedimento impugnato",
                "indice": "Indice allegati / nota deposito",
            }
            result.append(
                {
                    "key": key,
                    "label": label_map.get(key, key.replace("_", " ").title()),
                    "state": "ok" if matched else "missing",
                    "matched": matched,
                    "detail": "Documento rilevato tra gli allegati strutturati." if matched else "Documento essenziale non ancora rilevato.",
                }
            )
        return result

    def _validate_documental(
        self,
        sections: List[Dict[str, Any]],
        required_documents: List[Dict[str, Any]],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        missing_sections = [section for section in sections if section["state"] == "missing"]
        if missing_sections:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_WARNING,
                    code="sezioni_redazionali_mancanti",
                    title="Blocchi redazionali ancora vuoti",
                    detail=(
                        "Le seguenti sezioni risultano ancora prive di contenuto strutturato: "
                        + ", ".join(section["label"] for section in missing_sections[:4])
                    ),
                    source="Schema redazionale del modello",
                    suggested_action="Completa i blocchi essenziali prima di chiudere la bozza.",
                )
            )
        missing_docs = [item for item in required_documents if item["state"] == "missing"]
        if missing_docs:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_WARNING,
                    code="allegati_essenziali_non_rilevati",
                    title="Allegati essenziali non ancora rilevati",
                    detail="Mancano riferimenti strutturati a: " + ", ".join(item["label"] for item in missing_docs),
                    source="Checklist documentale del procedimento",
                    suggested_action="Aggiungi i documenti nella lista allegati o conferma che saranno prodotti dopo.",
                )
            )
        if not sections:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_WARNING,
                    code="schema_sezioni_non_configurato",
                    title="Modello senza mappa sezioni dettagliata",
                    detail="Il renderer del modello non espone ancora una sezione guidata completa.",
                    source="Schema compilatore del modello",
                    suggested_action="Usa il riepilogo normativo e verifica manualmente la struttura della bozza.",
                )
            )
        return issues

    def _next_steps(
        self,
        issues: List[ValidationIssue],
        sections: List[Dict[str, Any]],
        required_documents: List[Dict[str, Any]],
        profile: RedactionProfile,
    ) -> list[str]:
        steps: list[str] = []
        blockers = [issue for issue in issues if issue.level == LEVEL_BLOCK]
        if blockers:
            steps.append(f"Risolvi {len(blockers)} blocco/i prima della generazione della bozza finale.")
        if any(section["state"] == "missing" for section in sections):
            steps.append("Completa i blocchi redazionali ancora vuoti e rileggi fatto, diritto e conclusioni.")
        if any(item["state"] == "missing" for item in required_documents):
            steps.append("Aggiorna l'elenco allegati essenziali e conferma procura, notifiche e contributo dove dovuti.")
        if profile.channel == "PCT_TELEMATICO":
            steps.append("Dopo la bozza passa al pre-deposito: il motore PST validhera XML, busta, firma e limiti tecnici.")
        elif profile.channel == "PAT_AMMINISTRATIVO":
            steps.append("Verifica il canale PAT/Formweb applicabile alla sede e il rispetto dei termini di deposito.")
        elif profile.channel == "PDP_PENALE":
            steps.append("Controlla che l'atto sia effettivamente abilitato sul PDP per fase e ufficio penale competente.")
        elif profile.channel == "PTT_TRIBUTARIO":
            steps.append("Conferma CGT competente, atti notificati e allegati conformi prima del deposito SIGIT.")
        else:
            steps.append("Per il canale PEC conferma destinatario, prova di invio e completezza degli allegati.")
        return steps
