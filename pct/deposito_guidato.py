"""
pct/deposito_guidato.py - Orchestratore deterministico per il pre-deposito.

Separa:
- knowledge base procedurale
- resolver di competenza
- validatore normativo-redazionale
- validatore tecnico PST / DatiAtto.xml
- validatore documentale
- audit delle validazioni
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from lxml import etree

from legal_deposit.payment_policies import payment_policy_for_channel

from . import __version__ as APP_VERSION
from .busta import Allegato, BustaTelematica, DatiBusta
from .checklist_atti import CANALE_LABEL
from .fascicoli import Fascicolo
from .pst_catalog import (
    PST_CATALOG_VERSION,
    PST_DM44_SPECIFICHE_URL,
    PST_SCHEMA_VERSION,
    PST_MAX_BUSTA_BYTES,
    PST_MAX_BUSTA_MB,
    PST_WEB_SERVICES_DOC_URL,
    PST_WEB_SERVICES_DOC_VERSION,
    get_catalog_snapshot,
    get_catalog_sources,
)
from .pratiche_collegate_catalog import codice_oggetto_pst_entry, normalize_codice_oggetto_pst
from .pst_services import PSTOfficialCatalogAdapter
from .validazione import MAX_BYTES_ALLEGATO, verifica_dimensione, verifica_pdfa


PROCEDURAL_KB_VERSION = "2026.04.02.1"
SCHEMA_CATALOG_VERSION = PST_SCHEMA_VERSION
OFFICE_CATALOG_VERSION = PST_CATALOG_VERSION
PST_NAMESPACE = "http://www.giustizia.it/processo_telematico"

SERVICE_GIURIDICO = "GIURIDICO"
SERVICE_TECNICO = "TECNICO_PST"
SERVICE_DOCUMENTALE = "DOCUMENTALE"

LEVEL_OK = "OK"
LEVEL_WARNING = "WARNING"
LEVEL_BLOCK = "BLOCK"

DEPOSIT_CHANNELS = {
    "PCT_TELEMATICO",
    "PDP_PENALE",
    "PAT_AMMINISTRATIVO",
    "PTT_TRIBUTARIO",
}


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in norm if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower())
    return " ".join(lowered.split())


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    base = _slug(text)
    return any(_slug(needle) in base for needle in needles if needle)


def _is_signed_container_document(doc: dict[str, Any], path: Path | None = None) -> bool:
    values = [
        str(doc.get("nome") or ""),
        str(doc.get("filename") or ""),
        str(doc.get("percorso") or ""),
        str(path or ""),
    ]
    return any(value.lower().endswith((".p7m", ".sig", ".pkcs7")) for value in values if value)


def _guess_comune_from_label(label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    if " di " in text:
        return text.rsplit(" di ", 1)[-1].strip()
    return text


def _service_state(issues: Iterable["ValidationIssue"], service: str) -> str:
    service_issues = [i for i in issues if i.service == service]
    if any(i.level == LEVEL_BLOCK for i in service_issues):
        return "blocco"
    if any(i.level == LEVEL_WARNING for i in service_issues):
        return "warning"
    return "ok"


def _overall_state(issues: Iterable["ValidationIssue"]) -> str:
    if any(i.level == LEVEL_BLOCK for i in issues):
        return "blocco"
    if any(i.level == LEVEL_WARNING for i in issues):
        return "warning"
    return "ok"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _base_fonti() -> list[dict[str, str]]:
    return [
        {
            "label": "PST - aggiornamento XSD SICID 26 gennaio 2026",
            "url": "https://pst.giustizia.it/PST/page/it/processo_civile_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid?contentId=NWS4594",
        },
        {
            "label": f"PST - documentazione servizi web software house v{PST_WEB_SERVICES_DOC_VERSION}",
            "url": PST_WEB_SERVICES_DOC_URL,
        },
        {
            "label": "D.Lgs. 149/2022",
            "url": "https://www.gazzettaufficiale.it/eli/id/2022/10/17/22G00158/sg",
        },
    ] + get_catalog_sources()


def _profile_fonti(*extra: dict[str, str]) -> list[dict[str, str]]:
    return _base_fonti() + list(extra)


def _payment_issue_payload(channel: str) -> dict[str, str]:
    policy = payment_policy_for_channel(channel)
    if policy is None:
        return {
            "detail": "Per questo deposito introduttivo la ricevuta del contributo unificato non e stata rilevata.",
            "source": "Regola procedurale interna versionata",
            "suggested_action": "Verifica se il contributo e dovuto e, in caso affermativo, allega la ricevuta.",
        }
    proof = ", ".join(policy.proof_documents) or "prova pagamento"
    source = "; ".join(policy.official_sources[:2])
    return {
        "detail": (
            f"Il profilo richiede una verifica pagamento secondo la policy '{policy.label}'. "
            f"Non e stata rilevata una prova coerente tra: {proof}."
        ),
        "source": source or "Fonte ufficiale pagamenti telematici",
        "suggested_action": policy.missing_payment_action,
    }


@dataclass
class ProceduralProfile:
    id: str
    label: str
    tipo_atto_codes: List[str]
    channel: str
    materia: str
    rito: str
    giurisdizione: str
    grado: str
    deposit_mode: str
    allowed_fascicolo_types: List[str] = field(default_factory=list)
    allowed_office_types: List[str] = field(default_factory=list)
    allowed_registries: List[str] = field(default_factory=list)
    required_existing_rg: bool = False
    requires_procura: bool = False
    requires_index: bool = False
    requires_contributo: bool = False
    requires_notification_proof: bool = False
    requires_sentenza_impugnata: bool = False
    required_fields: List[str] = field(default_factory=list)
    fonti: List[Dict[str, str]] = field(default_factory=list)
    corrective_hint: str = ""

    def matches_tipo_atto(self, tipo_atto: str) -> bool:
        return _slug(tipo_atto) in {_slug(code) for code in self.tipo_atto_codes}


@dataclass
class ValidationIssue:
    service: str
    level: str
    code: str
    title: str
    detail: str
    source: str
    suggested_action: str
    field: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationRun:
    id: str
    fascicolo_id: str
    created_at: str
    profile_id: str
    profile_label: str
    channel: str
    overall_state: str
    can_prepare_deposit: bool
    semaforo: Dict[str, str]
    resolver: Dict[str, Any]
    snapshot: Dict[str, Any]
    context: Dict[str, Any]
    sources: List[Dict[str, str]] = field(default_factory=list)
    issues: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(raw: dict) -> "ValidationRun":
        return ValidationRun(
            id=raw.get("id", ""),
            fascicolo_id=raw.get("fascicolo_id", ""),
            created_at=raw.get("created_at", ""),
            profile_id=raw.get("profile_id", ""),
            profile_label=raw.get("profile_label", ""),
            channel=raw.get("channel", ""),
            overall_state=raw.get("overall_state", "warning"),
            can_prepare_deposit=bool(raw.get("can_prepare_deposit", False)),
            semaforo=dict(raw.get("semaforo") or {}),
            resolver=dict(raw.get("resolver") or {}),
            snapshot=dict(raw.get("snapshot") or {}),
            context=dict(raw.get("context") or {}),
            sources=list(raw.get("sources") or []),
            issues=list(raw.get("issues") or []),
        )


class ProceduralKnowledgeBase:
    """Catalogo procedimenti / atti / registri / uffici compatibili."""

    def __init__(self) -> None:
        self._profiles = self._build_profiles()

    @property
    def version(self) -> str:
        return PROCEDURAL_KB_VERSION

    def resolve_profile(self, fascicolo: Fascicolo, tipo_atto: str) -> ProceduralProfile:
        matching = [profile for profile in self._profiles if profile.matches_tipo_atto(tipo_atto)]
        fascicolo_tipo = fascicolo.tipo.value
        typed_matches = [
            profile
            for profile in matching
            if not profile.allowed_fascicolo_types or fascicolo_tipo in profile.allowed_fascicolo_types
        ]
        if typed_matches:
            return typed_matches[0]
        if matching:
            return matching[0]
        return ProceduralProfile(
            id="atto_generico_pct",
            label="Atto generico PCT",
            tipo_atto_codes=[tipo_atto or "ATTO_GENERICO"],
            channel="PCT_TELEMATICO",
            materia=fascicolo.tipo.value,
            rito="da verificare",
            giurisdizione="da verificare",
            grado="da verificare",
            deposit_mode="da_verificare",
            allowed_fascicolo_types=[fascicolo.tipo.value],
            allowed_office_types=["TRIBUNALE", "GDP", "CORTE_APPELLO"],
            allowed_registries=["RG", "RGL", "VG", "RGE"],
            required_fields=["tribunale", "oggetto"],
            fonti=_base_fonti(),
            corrective_hint=(
                "Seleziona un atto tipizzato oppure verifica manualmente ufficio, "
                "registro, rito e allegati prima del deposito."
            ),
        )

    def _build_profiles(self) -> List[ProceduralProfile]:
        return [
            ProceduralProfile(
                id="iscrizione_a_ruolo",
                label="Iscrizione a ruolo / atto introduttivo",
                tipo_atto_codes=["ATTO_DI_CITAZIONE", "CITAZIONE", "RICORSO"],
                channel="PCT_TELEMATICO",
                materia="CIVILE",
                rito="introduttivo di cognizione",
                giurisdizione="ordinaria civile",
                grado="primo grado",
                deposit_mode="iscrizione_a_ruolo",
                allowed_fascicolo_types=["CIVILE", "LAVORO", "FAMIGLIA", "CONSULENZA"],
                allowed_office_types=["TRIBUNALE", "GDP"],
                allowed_registries=["RG", "RGL", "VG"],
                requires_procura=True,
                requires_index=True,
                requires_contributo=True,
                requires_notification_proof=True,
                required_fields=["id_cliente", "tribunale", "oggetto", "controparte"],
                fonti=_profile_fonti(
                    {
                        "label": "Codice di procedura civile consolidato",
                        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
                    }
                ),
                corrective_hint=(
                    "Per l'iscrizione a ruolo verifica atto introduttivo notificato, "
                    "procura, prova notifica e contributo unificato."
                ),
            ),
            ProceduralProfile(
                id="decreto_ingiuntivo",
                label="Ricorso per decreto ingiuntivo",
                tipo_atto_codes=["DECRETO_INGIUNTIVO"],
                channel="PCT_TELEMATICO",
                materia="CIVILE",
                rito="monitorio",
                giurisdizione="ordinaria civile",
                grado="primo grado",
                deposit_mode="iscrizione_a_ruolo",
                allowed_fascicolo_types=["CIVILE", "LAVORO"],
                allowed_office_types=["TRIBUNALE", "GDP"],
                allowed_registries=["RG", "RGL"],
                requires_procura=True,
                requires_index=True,
                requires_contributo=True,
                required_fields=["id_cliente", "tribunale", "oggetto", "controparte"],
                fonti=_profile_fonti(
                    {
                        "label": "Artt. 633 ss. c.p.c.",
                        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
                    }
                ),
                corrective_hint="Il ricorso monitorio richiede titolo/prova scritta, procura e contributo.",
            ),
            ProceduralProfile(
                id="comparsa_risposta",
                label="Comparsa di costituzione e risposta",
                tipo_atto_codes=["COMPARSA", "COMPARSA_RISPOSTA"],
                channel="PCT_TELEMATICO",
                materia="CIVILE",
                rito="ordinario di cognizione",
                giurisdizione="ordinaria civile",
                grado="primo grado",
                deposit_mode="in_corso_di_causa",
                allowed_fascicolo_types=["CIVILE", "LAVORO", "FAMIGLIA"],
                allowed_office_types=["TRIBUNALE", "GDP"],
                allowed_registries=["RG", "RGL"],
                required_existing_rg=True,
                requires_procura=True,
                requires_index=True,
                required_fields=["id_cliente", "tribunale", "controparte", "oggetto"],
                fonti=_profile_fonti(
                    {
                        "label": "Codice di procedura civile - artt. 166 e 167",
                        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
                    }
                ),
                corrective_hint=(
                    "Verifica termine di costituzione, decadenze, procura del convenuto e "
                    "coerenza delle eccezioni con il rito scelto."
                ),
            ),
            ProceduralProfile(
                id="memoria_difensiva",
                label="Memoria / deposito in corso di causa",
                tipo_atto_codes=["MEMORIA", "ISTANZA", "ATTO_GENERICO"],
                channel="PCT_TELEMATICO",
                materia="CIVILE",
                rito="in corso di causa",
                giurisdizione="ordinaria civile",
                grado="primo grado",
                deposit_mode="in_corso_di_causa",
                allowed_fascicolo_types=["CIVILE", "LAVORO", "FAMIGLIA", "CONSULENZA"],
                allowed_office_types=["TRIBUNALE", "GDP", "CORTE_APPELLO"],
                allowed_registries=["RG", "RGL", "VG", "RGE"],
                required_existing_rg=True,
                required_fields=["tribunale", "oggetto"],
                fonti=_profile_fonti(
                    {
                        "label": "D.M. 110/2023 - sinteticita' atti",
                        "url": "https://www.gazzettaufficiale.it/eli/id/2023/08/18/23G00118/sg",
                    }
                ),
                corrective_hint=(
                    "Controlla il termine perentorio applicabile e il tipo di memoria "
                    "effettivamente depositabile nel fascicolo."
                ),
            ),
            ProceduralProfile(
                id="ricorso_appello",
                label="Appello civile / impugnazione",
                tipo_atto_codes=["APPELLO", "RICORSO_CASSAZIONE", "CONTRORICORSO"],
                channel="PCT_TELEMATICO",
                materia="CIVILE",
                rito="impugnazione",
                giurisdizione="ordinaria civile",
                grado="impugnazione",
                deposit_mode="impugnazione",
                allowed_fascicolo_types=["CIVILE", "LAVORO", "FAMIGLIA"],
                allowed_office_types=["TRIBUNALE", "CORTE_APPELLO", "CORTE_CASSAZIONE"],
                allowed_registries=["RG", "RGL"],
                required_existing_rg=True,
                requires_procura=True,
                requires_index=True,
                requires_contributo=True,
                requires_sentenza_impugnata=True,
                required_fields=["id_cliente", "tribunale", "oggetto"],
                fonti=_profile_fonti(
                    {
                        "label": "Art. 341 c.p.c. - competenza appello",
                        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
                    }
                ),
                corrective_hint=(
                    "Per l'impugnazione verifica il giudice che ha pronunciato il provvedimento, "
                    "la sede di appello e la presenza della sentenza impugnata."
                ),
            ),
            ProceduralProfile(
                id="precetto",
                label="Precetto / intimazione esecutiva",
                tipo_atto_codes=["PRECETTO"],
                channel="PEC",
                materia="ESECUZIONE",
                rito="stragiudiziale / pre-esecutivo",
                giurisdizione="ordinaria civile",
                grado="fase pre-esecutiva",
                deposit_mode="fuori_pst",
                allowed_fascicolo_types=["CIVILE"],
                allowed_office_types=["TRIBUNALE", "GDP"],
                allowed_registries=["RGE", "RG"],
                required_fields=["id_cliente", "controparte", "oggetto"],
                fonti=_profile_fonti(
                    {
                        "label": "Art. 480 c.p.c.",
                        "url": "https://www.normattiva.it/eli/id/1940/10/28/040U1443/CONSOLIDATED/20240814",
                    }
                ),
                corrective_hint=(
                    "Il precetto non si deposita normalmente come busta PCT introduttiva: "
                    "usa il canale notificatorio/PEC e poi la successiva fase esecutiva."
                ),
            ),
            ProceduralProfile(
                id="atto_difensivo_pdp",
                label="Atto difensivo PDP Penale",
                tipo_atto_codes=[
                    "ATTO_DIFESA",
                    "MEMORIA",
                    "IMPUGNAZIONE",
                    "APPELLO",
                    "ISTANZA",
                    "RICHIESTA_RIESAME",
                    "OPPOSIZIONE",
                    "MOTIVI_NUOVI",
                    "DEPOSITO_DOCUMENTI",
                    "NOMINA",
                    "ALTRO",
                ],
                channel="PDP_PENALE",
                materia="PENALE",
                rito="deposito penale telematico",
                giurisdizione="ordinaria penale",
                grado="fase penale",
                deposit_mode="portale_penale",
                allowed_fascicolo_types=["PENALE"],
                allowed_office_types=["PROCURA", "TRIBUNALE", "CORTE_APPELLO", "CORTE_CASSAZIONE"],
                allowed_registries=["PDP_ATTI", "RGNR", "RG", "GIP", "GUP", "RGES"],
                requires_procura=True,
                required_fields=["tribunale", "oggetto"],
                fonti=_profile_fonti(
                    {
                        "label": "D.M. 217/2023 - Portale deposito atti penali",
                        "url": "https://www.gazzettaufficiale.it/eli/id/2023/12/30/23G00232/sg",
                    }
                ),
                corrective_hint=(
                    "Verifica che l'atto sia abilitato sul PDP per fase, ufficio penale e soggetto depositante."
                ),
            ),
            ProceduralProfile(
                id="ricorso_pat",
                label="Ricorso / deposito PAT Amministrativo",
                tipo_atto_codes=[
                    "RICORSO",
                    "APPELLO",
                    "MEMORIA",
                    "REPLICA",
                    "MOTIVI_AGGIUNTI",
                    "RICORSO_INCIDENTALE",
                    "ISTANZA",
                    "DEPOSITO_DOCUMENTI",
                    "ALTRO",
                ],
                channel="PAT_AMMINISTRATIVO",
                materia="AMMINISTRATIVO",
                rito="processo amministrativo telematico",
                giurisdizione="amministrativa",
                grado="tar_cds",
                deposit_mode="portale_pat",
                allowed_fascicolo_types=["AMMINISTRATIVO"],
                allowed_office_types=["TAR", "CDS", "CGARS"],
                allowed_registries=["PAT_DEP", "RG"],
                requires_procura=True,
                requires_notification_proof=True,
                required_fields=["tribunale", "oggetto", "controparte"],
                fonti=_profile_fonti(
                    {
                        "label": "D.P.C.M. 16 febbraio 2016 - PAT",
                        "url": "https://www.gazzettaufficiale.it/eli/id/2016/04/20/16A02974/sg",
                    },
                    {
                        "label": "Giustizia Amministrativa - Portale dell'Avvocato",
                        "url": "https://www.giustizia-amministrativa.it/web/guest/portale-avvocato",
                    },
                    {
                        "label": "Giustizia Amministrativa - nuovo Portale Avvocato operativo",
                        "url": "https://pe.prod.cloud.giustizia-amministrativa.it",
                    },
                ),
                corrective_hint=(
                    "Conferma TAR/Consiglio di Stato competente, notifica, allegati SIGA/Formweb e firma PAdES del modulo/atto."
                ),
            ),
            ProceduralProfile(
                id="ricorso_tributario",
                label="Ricorso / deposito PTT Tributario",
                tipo_atto_codes=[
                    "RICORSO",
                    "RICORSO_TRIBUTARIO",
                    "MEMORIA",
                    "REPLICA",
                    "CONTRODEDUZIONI",
                    "ISTANZA",
                    "DEPOSITO_DOCUMENTI",
                    "ALTRO",
                ],
                channel="PTT_TRIBUTARIO",
                materia="TRIBUTARIO",
                rito="processo tributario telematico",
                giurisdizione="tributaria",
                grado="primo_grado",
                deposit_mode="portale_sigit",
                allowed_fascicolo_types=["TRIBUTARIO"],
                allowed_office_types=["CPT", "CGT"],
                allowed_registries=["PTT_RICORSI"],
                requires_procura=True,
                requires_contributo=True,
                requires_notification_proof=True,
                required_fields=["tribunale", "oggetto", "controparte"],
                fonti=_profile_fonti(
                    {
                        "label": "D.M. 163/2013 - Processo tributario telematico",
                        "url": "https://www.gazzettaufficiale.it/eli/id/2013/11/19/13A09382/sg",
                    },
                    {
                        "label": "SIGIT - Telecontenzioso",
                        "url": "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
                    },
                    {
                        "label": "MEF - Utilizzare deposito telematico ricorsi e appelli",
                        "url": "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3059",
                    },
                ),
                corrective_hint=(
                    "Per il PTT conferma CGT competente, notifica all'ente, contributo e NIR firmata prima della chiusura."
                ),
            ),
            ProceduralProfile(
                id="appello_tributario",
                label="Appello PTT Tributario",
                tipo_atto_codes=["APPELLO", "APPELLO_TRIBUTARIO"],
                channel="PTT_TRIBUTARIO",
                materia="TRIBUTARIO",
                rito="processo tributario telematico",
                giurisdizione="tributaria",
                grado="secondo_grado",
                deposit_mode="portale_sigit",
                allowed_fascicolo_types=["TRIBUTARIO"],
                allowed_office_types=["CGT"],
                allowed_registries=["PTT_RICORSI"],
                required_existing_rg=True,
                requires_procura=True,
                requires_contributo=True,
                requires_notification_proof=True,
                requires_sentenza_impugnata=True,
                required_fields=["tribunale", "oggetto", "controparte"],
                fonti=_profile_fonti(
                    {
                        "label": "D.Lgs. 546/1992 - Appello tributario",
                        "url": "https://www.normattiva.it/eli/id/1992/12/31/092G0587/CONSOLIDATED/20240404",
                    },
                    {
                        "label": "MEF - Workflow processo tributario telematico",
                        "url": "https://assistenza.dgt.mef.gov.it/GiustiziaTributaria/s/articolo-detail?urlName=DF-GiustiziaTributaria-3016",
                    },
                    {
                        "label": "SIGIT - Telecontenzioso",
                        "url": "https://sigit.giustiziatributaria.gov.it/Sigit/index.do",
                    },
                ),
                corrective_hint=(
                    "Per l'appello tributario verifica sentenza impugnata, termine breve/lungo e NIR firmata."
                ),
            ),
        ]


def _unique_sources(*groups: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: List[Dict[str, str]] = []
    for group in groups:
        for item in group or []:
            key = (item.get("label", ""), item.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _doc_matches(doc: Dict[str, Any], *, types: Iterable[str] = (), names: Iterable[str] = ()) -> bool:
    doc_type = _slug(str(doc.get("tipo", "")))
    doc_name = _slug(str(doc.get("nome", "")))
    wanted_types = {_slug(item) for item in types if item}
    if wanted_types and doc_type in wanted_types:
        return True
    return _contains_any(doc_name, names)


def _classify_documents(documenti: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "procura": [d for d in documenti if _doc_matches(d, types=("PROCURA",), names=("procura",))],
        "contributo": [
            d for d in documenti
            if _doc_matches(d, names=("contributo", "unificato", "pagopa", "f23", "f24"))
        ],
        "notifica": [
            d for d in documenti
            if _doc_matches(
                d,
                types=("NOTIFICA",),
                names=(
                    "notifica",
                    "notificazione",
                    "relata",
                    "ricevuta pec",
                    "ricevuta accettazione",
                    "ricevuta consegna",
                    "accettazione",
                    "consegna",
                    "rac",
                    "rdac",
                    "notifica_id",
                    "originale notificato",
                    "legge n 53",
                    "l 53",
                ),
            )
        ],
        "sentenza": [
            d for d in documenti
            if _doc_matches(
                d,
                types=("SENTENZA", "ORDINANZA", "DECRETO"),
                names=("sentenza", "ordinanza", "decreto", "provvedimento impugnato"),
            )
        ],
        "indice": [d for d in documenti if _doc_matches(d, names=("indice", "indice deposito"))],
        "nir": [
            d for d in documenti
            if _doc_matches(d, names=("nir", "nota iscrizione a ruolo", "nota_iscrizione_a_ruolo"))
        ],
    }


class CompetenceResolver:
    """Risoluzione deterministica di ufficio, sede, grado e registro."""

    def __init__(
        self,
        office_cache_path: str = "",
        *,
        pst_wsdl_catalog_zip_path: str = "",
        pst_official_cache_path: str = "",
        pst_catalog_endpoint: str = "",
        pst_timeout: float = 8.0,
    ) -> None:
        self.office_cache_path = office_cache_path
        self.official = PSTOfficialCatalogAdapter(
            wsdl_catalog_zip_path=pst_wsdl_catalog_zip_path,
            cache_path=pst_official_cache_path,
            catalog_endpoint=pst_catalog_endpoint,
            timeout=pst_timeout,
        )

    def _load_offices(self) -> List[Dict[str, Any]]:
        try:
            from .uffici_giudiziari import get_gestore

            return list(get_gestore(self.office_cache_path or "").carica())
        except Exception:
            return []

    def resolve(
        self,
        fascicolo: Fascicolo,
        profile: ProceduralProfile,
        codice_registro: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = dict(context or {})
        offices = self._load_offices()
        tribunale = (fascicolo.tribunale or "").strip()
        office = None
        match_mode = "none"

        if tribunale:
            office = next((u for u in offices if str(u.get("codice", "")).strip() == tribunale), None)
            if office:
                match_mode = "code"
            else:
                office = next(
                    (u for u in offices if _slug(str(u.get("nome", ""))) == _slug(tribunale)),
                    None,
                )
                if office:
                    match_mode = "name"

        office_name = str((office or {}).get("nome", tribunale or ""))
        office_code = str((office or {}).get("codice", tribunale or ""))
        office_type = str((office or {}).get("tipo", "")).upper()
        office_distretto = str((office or {}).get("distretto", ""))
        office_comune = str((office or {}).get("comune", "")).strip() or _guess_comune_from_label(office_name)
        requested_registry = (codice_registro or "").strip().upper()

        official_office_lookup = {"item": {}, "source": "disabled", "matched_on": "none"}
        official_office = {}
        if tribunale and (office_comune or office_distretto or office_name):
            official_office_lookup = self.official.find_office(
                office_name=office_name or tribunale,
                office_code=office_code,
                comune=office_comune,
                distretto=office_distretto,
                penale=profile.channel == "PDP_PENALE",
            )
            official_office = dict(official_office_lookup.get("item") or {})

        effective_office = office or {}
        if official_office:
            effective_office = {
                "nome": official_office.get("descrizione", office_name or tribunale),
                "codice": official_office.get("codice_ufficio", office_code or tribunale),
                "tipo": official_office.get("tipo_ufficio", office_type),
                "distretto": official_office.get("distretto", office_distretto),
                "comune": official_office.get("comune", office_comune),
            }

        effective_office_name = str(effective_office.get("nome", office_name or tribunale))
        effective_office_code = str(effective_office.get("codice", office_code or tribunale))
        effective_office_type = str(effective_office.get("tipo", office_type)).upper()
        effective_office_distretto = str(effective_office.get("distretto", office_distretto))

        official_registries = (
            self.official.get_registries_for_office(effective_office_code)
            if effective_office_code
            else self.official.get_registries_for_office("")
        )
        official_registry_codes = [
            str(item.get("codice", "")).strip().upper()
            for item in official_registries.items
            if str(item.get("codice", "")).strip()
        ]
        effective_allowed_registries = official_registry_codes or list(profile.allowed_registries)

        rito_seed = requested_registry or (effective_allowed_registries[0] if effective_allowed_registries else "")
        official_riti = self.official.get_riti_for_registry(rito_seed) if rito_seed else self.official.get_riti_for_registry("")
        effective_riti = [
            str(item.get("descrizione", "")).strip()
            for item in official_riti.items
            if str(item.get("descrizione", "")).strip()
        ]

        official_normativa = None
        normativa_id = str(context.get("id_atti_depositabili") or "").strip()
        if normativa_id:
            official_normativa = self.official.get_normativa(normativa_id).to_dict()

        official_sync = self.official.get_runtime_snapshot()
        official_sync.update(
            {
                "office_lookup": {
                    "source": official_office_lookup.get("source", "disabled"),
                    "matched_on": official_office_lookup.get("matched_on", "none"),
                    "matched_code": official_office.get("codice_ufficio", ""),
                },
                "registries": official_registries.to_dict(),
                "riti": official_riti.to_dict(),
                "effective_registry_source": official_registries.source,
                "effective_rito_source": official_riti.source,
            }
        )
        if official_normativa:
            official_sync["normativa"] = official_normativa

        payload = {
            "office_found": bool(office),
            "office_match_mode": match_mode,
            "office_name": office_name,
            "office_code": office_code,
            "office_type": office_type,
            "office_distretto": office_distretto,
            "requested_registry": requested_registry,
            "requested_channel": profile.channel,
            "requested_grade": profile.grado,
            "requested_rito": profile.rito,
            "allowed_office_types": list(profile.allowed_office_types),
            "allowed_registries": list(profile.allowed_registries),
            "effective_allowed_registries": effective_allowed_registries,
            "effective_riti": effective_riti,
            "official_office_found": bool(official_office),
            "official_office_match_mode": official_office_lookup.get("matched_on", "none"),
            "official_office_name": str(official_office.get("descrizione", "")),
            "official_office_code": str(official_office.get("codice_ufficio", "")),
            "official_office_type": str(official_office.get("tipo_ufficio", "")).upper(),
            "official_office_distretto": str(official_office.get("distretto", "")),
            "effective_office_found": bool(effective_office_name),
            "effective_office_name": effective_office_name,
            "effective_office_code": effective_office_code,
            "effective_office_type": effective_office_type,
            "effective_office_distretto": effective_office_distretto,
            "official_registries": official_registries.to_dict(),
            "official_riti": official_riti.to_dict(),
            "pst_official_runtime": official_sync,
            "catalog_versions": {
                "procedural_kb": PROCEDURAL_KB_VERSION,
                "office_catalog": OFFICE_CATALOG_VERSION,
                "schema_catalog": SCHEMA_CATALOG_VERSION,
                "pst_webservices_doc_version": PST_WEB_SERVICES_DOC_VERSION,
            },
            "pst_official_catalog": get_catalog_snapshot(),
        }
        payload["catalog_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return payload


class ValidatorNormativoRedazionale:
    """Controlli giuridici, procedurali e redazionali basati su regole versionate."""

    def validate(
        self,
        fascicolo: Fascicolo,
        profile: ProceduralProfile,
        resolver: Dict[str, Any],
        context: Dict[str, Any],
        selected_documents: List[Dict[str, Any]],
        all_documents: List[Dict[str, Any]],
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        numero_rg = str(context.get("numero_rg") or "").strip()
        anno_rg = _safe_int(context.get("anno_rg"))
        registro = str(context.get("codice_registro") or "").strip().upper()
        oggetto = str(context.get("oggetto") or "").strip()
        codice_oggetto_pst = normalize_codice_oggetto_pst(
            context.get("codice_oggetto_pst")
            or getattr(fascicolo, "codice_oggetto_pst", "")
            or context.get("oggetto")
            or getattr(fascicolo, "oggetto", "")
        )
        operatore = str(context.get("operatore") or "").strip()
        fascicolo_tipo = fascicolo.tipo.value
        selected_groups = _classify_documents(selected_documents)
        all_groups = _classify_documents(all_documents)

        if profile.channel not in DEPOSIT_CHANNELS:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="canale_non_depositabile",
                    title="La tipologia selezionata non e depositabile come busta PCT",
                    detail=(
                        f"L'atto '{profile.label}' e classificato come canale {profile.channel} "
                        "e non come deposito PCT standard."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action=profile.corrective_hint or "Seleziona un atto depositabile via PCT.",
                    field="tipo_atto",
                )
            )

        if profile.channel == "PCT_TELEMATICO":
            codice_entry = codice_oggetto_pst_entry(codice_oggetto_pst)
            if not codice_oggetto_pst:
                issues.append(
                    ValidationIssue(
                        service=SERVICE_GIURIDICO,
                        level=LEVEL_BLOCK,
                        code="codice_oggetto_pst_mancante",
                        title="Codice oggetto PST mancante",
                        detail=(
                            "Il DatiAtto.xml richiede un codice oggetto ministeriale: "
                            "la tipologia tariffaria del preventivo non viene usata come sostituto."
                        ),
                        source="PST - XSD tipi-base.xsd / CodiceOggetto",
                        suggested_action="Seleziona l'oggetto deposito dal catalogo ufficiale PST nei dati del fascicolo.",
                        field="codice_oggetto_pst",
                    )
                )
            elif not codice_entry:
                issues.append(
                    ValidationIssue(
                        service=SERVICE_GIURIDICO,
                        level=LEVEL_BLOCK,
                        code="codice_oggetto_pst_non_ufficiale",
                        title="Codice oggetto PST non ufficiale",
                        detail=(
                            f"Il codice '{codice_oggetto_pst}' non risulta tra i codici oggetto "
                            "del catalogo ufficiale importato dagli XSD PST."
                        ),
                        source="PST - XSD tipi-base.xsd / CodiceOggetto",
                        suggested_action="Sostituisci il codice con una voce selezionata dal catalogo ufficiale.",
                        field="codice_oggetto_pst",
                    )
                )

        if profile.allowed_fascicolo_types and fascicolo_tipo not in profile.allowed_fascicolo_types:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="materia_non_compatibile",
                    title="Materia del fascicolo non coerente con l'atto",
                    detail=(
                        f"Il fascicolo e classificato come {fascicolo_tipo}, mentre il profilo "
                        f"procedurale '{profile.label}' ammette {', '.join(profile.allowed_fascicolo_types)}."
                    ),
                    source="Knowledge base procedurale versionata",
                    suggested_action="Rivedi materia/tipologia dell'atto oppure usa il canale corretto.",
                    field="tipo_atto",
                )
            )

        if not fascicolo.tribunale:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="sede_mancante",
                    title="Sede / ufficio non indicato nel fascicolo",
                    detail="La verifica di competenza non puo essere completata senza un ufficio giudiziario.",
                    source="Regola procedurale interna versionata",
                    suggested_action="Compila il campo tribunale / ufficio nel fascicolo prima del deposito.",
                    field="tribunale",
                )
            )

        if fascicolo.tribunale and not resolver.get("effective_office_found"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="ufficio_non_risolto",
                    title="Ufficio non risolto sul catalogo giudiziario",
                    detail=(
                        f"L'ufficio '{fascicolo.tribunale}' non e stato risolto in modo certo sul catalogo "
                        "degli uffici giudiziari; la sede va confermata manualmente."
                    ),
                    source="Catalogo uffici giudiziari / PST",
                    suggested_action="Verifica il nome o il codice dell'ufficio e riallinea il fascicolo.",
                    field="tribunale",
                )
            )

        office_type = resolver.get("effective_office_type", "") or resolver.get("office_type", "")
        if office_type and profile.allowed_office_types and office_type not in profile.allowed_office_types:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="competenza_ufficio_errata",
                    title="Ufficio selezionato non coerente con la competenza",
                    detail=(
                        f"L'ufficio risolto e di tipo {office_type}, mentre questo profilo consente "
                        f"{', '.join(profile.allowed_office_types)}."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Correggi sede / grado o scegli la tipologia di atto corretta.",
                    field="tribunale",
                )
            )

        effective_registries = list(
            resolver.get("effective_allowed_registries")
            or profile.allowed_registries
        )
        if effective_registries and registro and registro not in effective_registries:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="registro_errato",
                    title="Registro non compatibile con il procedimento",
                    detail=(
                        f"Il registro {registro} non rientra tra quelli consentiti per il profilo "
                        f"'{profile.label}' ({', '.join(effective_registries)})."
                    ),
                    source="Resolver procedurale + catalogo PST ufficiale",
                    suggested_action="Seleziona il registro compatibile con rito e grado del deposito.",
                    field="codice_registro",
                )
            )

        effective_riti = [
            str(item).strip()
            for item in (resolver.get("effective_riti") or [])
            if str(item).strip()
        ]
        if effective_riti and profile.rito:
            rito_atteso = _slug(profile.rito)
            if rito_atteso and not any(rito_atteso in _slug(item) for item in effective_riti):
                issues.append(
                    ValidationIssue(
                        service=SERVICE_GIURIDICO,
                        level=LEVEL_WARNING,
                        code="rito_da_confermare",
                        title="Rito da confermare sul catalogo PST",
                        detail=(
                            f"Il catalogo ufficiale restituisce i riti {', '.join(effective_riti)} "
                            f"per il registro {registro or resolver.get('requested_registry')}, mentre il profilo usa "
                            f"'{profile.rito}'."
                        ),
                        source="Catalogo servizi PST - getRito",
                        suggested_action="Conferma il rito applicabile e il registro prima della preparazione finale.",
                        field="codice_registro",
                    )
                )

        if profile.required_existing_rg and not (numero_rg and anno_rg):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="rg_obbligatorio",
                    title="Manca il riferimento al procedimento gia iscritto",
                    detail="Questo deposito richiede numero e anno di RG gia esistenti nel fascicolo.",
                    source="Regola procedurale interna versionata",
                    suggested_action="Completa il fascicolo con numero RG e anno prima di depositare.",
                    field="numero_rg",
                )
            )

        if profile.deposit_mode == "iscrizione_a_ruolo" and numero_rg and anno_rg:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="rg_presente_su_intro",
                    title="Atto introduttivo con RG gia presente",
                    detail=(
                        "Il fascicolo contiene gia un numero RG: verifica che non si tratti di un "
                        "deposito in corso di causa o di un atto successivo."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Conferma se l'atto e introduttivo oppure riallinea tipologia e fascicolo.",
                    field="numero_rg",
                )
            )

        for field_name in profile.required_fields:
            value = getattr(fascicolo, field_name, "") if hasattr(fascicolo, field_name) else context.get(field_name, "")
            if not str(value or "").strip():
                value = context.get(field_name, value)
            if str(value or "").strip():
                continue
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING if field_name == "controparte" else LEVEL_BLOCK,
                    code=f"campo_mancante_{field_name}",
                    title=f"Campo richiesto mancante: {field_name}",
                    detail=(
                        f"Per il profilo '{profile.label}' il campo '{field_name}' e necessario per una "
                        "verifica giuridica e redazionale completa."
                    ),
                    source="Knowledge base procedurale versionata",
                    suggested_action=f"Compila il campo '{field_name}' nel fascicolo o nel wizard.",
                    field=field_name,
                )
            )

        if not operatore:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="depositante_non_identificato",
                    title="Legittimazione del depositante non esplicitata",
                    detail=(
                        "Il deposito non riporta l'operatore / avvocato depositante nella validazione corrente."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Esegui il deposito da una sessione autenticata con utente identificato.",
                    field="operatore",
                )
            )

        if len(oggetto) < 8:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="oggetto_troppo_breve",
                    title="Oggetto dell'atto troppo sintetico",
                    detail="L'oggetto inserito e molto breve e puo non descrivere correttamente il deposito.",
                    source="D.M. 110/2023 - sinteticita degli atti",
                    suggested_action="Usa un oggetto piu preciso e leggibile per atto, ufficio e fascicolo.",
                    field="oggetto",
                )
            )

        main_doc = next((d for d in selected_documents if d.get("id") == context.get("atto_principale_id")), None)
        if main_doc and _doc_matches(
            main_doc,
            types=("PROCURA", "NOTIFICA"),
            names=("procura", "relata", "contributo", "accettazione", "consegna", "rac", "rdac", "notifica_id", "originale notificato"),
        ):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="atto_principale_non_coerente",
                    title="Il documento principale selezionato sembra un allegato",
                    detail=(
                        f"Il file principale '{main_doc.get('nome')}' somiglia a procura, relata o documento accessorio."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Seleziona come atto principale il PDF/p7m dell'atto da depositare.",
                    field="atto_principale_id",
                )
            )

        def _missing_required(group_name: str) -> bool:
            return not selected_groups[group_name]

        def _available_not_selected(group_name: str) -> bool:
            return bool(all_groups[group_name]) and not bool(selected_groups[group_name])

        if profile.requires_procura and _missing_required("procura"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK if not _available_not_selected("procura") else LEVEL_WARNING,
                    code="procura_mancante",
                    title="Procura non inclusa nella selezione",
                    detail="Il profilo procedurale richiede la procura alle liti tra i documenti del deposito.",
                    source="Codice di procedura civile / regola interna",
                    suggested_action=(
                        "Allega la procura; se e gia presente nel fascicolo ma non selezionata, "
                        "includila tra gli allegati del deposito."
                    ),
                    field="allegati_ids",
                )
            )

        if profile.requires_contributo and _missing_required("contributo"):
            payment_issue = _payment_issue_payload(profile.channel)
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="contributo_non_evidenziato",
                    title="Ricevuta contributo unificato non rilevata",
                    detail=payment_issue["detail"],
                    source=payment_issue["source"],
                    suggested_action=payment_issue["suggested_action"],
                    field="allegati_ids",
                )
            )

        if profile.requires_notification_proof and _missing_required("notifica"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="prova_notifica_non_rilevata",
                    title="Prova di notifica non rilevata",
                    detail=(
                        "Non risultano relate o ricevute di notifica tra gli allegati selezionati, "
                        "pur trattandosi di un deposito che normalmente le richiede."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Controlla se occorre allegare relata, ricevute PEC o attestazione di conformita.",
                    field="allegati_ids",
                )
            )

        if profile.requires_sentenza_impugnata and _missing_required("sentenza"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK if not _available_not_selected("sentenza") else LEVEL_WARNING,
                    code="provvedimento_impugnato_mancante",
                    title="Sentenza o provvedimento impugnato non incluso",
                    detail="L'impugnazione richiede il provvedimento impugnato tra i documenti selezionati.",
                    source="Art. 341 c.p.c. / regola procedurale interna",
                    suggested_action="Allega sentenza, ordinanza o decreto impugnato al deposito.",
                    field="allegati_ids",
                )
            )

        if profile.requires_index and _missing_required("indice"):
            # L'indice documenti viene generato automaticamente nel pacchetto busta.
            pass

        if profile.channel == "PTT_TRIBUTARIO" and profile.deposit_mode == "portale_sigit":
            tipo_atto_norm = _slug(context.get("tipo_atto") or "")
            richiede_nir = tipo_atto_norm in {"ricorso", "ricorso tributario", "appello", "appello tributario"}
            if richiede_nir and not all_groups["nir"]:
                issues.append(
                    ValidationIssue(
                        service=SERVICE_GIURIDICO,
                        level=LEVEL_BLOCK,
                        code="nir_tributaria_mancante",
                        title="NIR del PTT non rilevata",
                        detail=(
                            "Nel flusso tributario la Nota di Iscrizione a Ruolo generata dal portale MEF "
                            "deve essere scaricata, firmata in CAdES e ricaricata prima della chiusura del deposito."
                        ),
                        source="D.M. 163/2013 / workflow SIGIT-PTT / assistenza MEF",
                        suggested_action="Genera la NIR sul portale SIGIT/PTT, firmala e allegala al fascicolo prima del deposito.",
                        field="allegati_ids",
                    )
                )

        if main_doc and _safe_int(main_doc.get("dimensione_bytes")) < 2048:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="atto_molto_breve",
                    title="Atto principale molto breve",
                    detail=(
                        f"Il documento principale '{main_doc.get('nome')}' ha dimensioni molto ridotte; "
                        "verifica la completezza narrativa minima dell'atto."
                    ),
                    source="D.M. 110/2023 - sinteticita e completezza",
                    suggested_action="Controlla che l'atto contenga parti, fatto, diritto, conclusioni e allegati essenziali.",
                    field="atto_principale_id",
                )
            )

        return issues


class DocumentValidator:
    """Controlli su selezione documenti, firma, PDF/A e limiti dimensionali."""

    def validate(
        self,
        profile: ProceduralProfile,
        context: Dict[str, Any],
        selected_documents: List[Dict[str, Any]],
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        main_doc_id = context.get("atto_principale_id")
        if not main_doc_id:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_BLOCK,
                    code="atto_principale_non_selezionato",
                    title="Atto principale non selezionato",
                    detail="Per costruire la busta e necessario selezionare il documento principale del deposito.",
                    source="Regola operativa PCT",
                    suggested_action="Seleziona l'atto principale nello step documenti.",
                    field="atto_principale_id",
                )
            )
            return issues

        main_doc = next((d for d in selected_documents if d.get("id") == main_doc_id), None)
        if not main_doc:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_BLOCK,
                    code="atto_principale_non_trovato",
                    title="Atto principale non presente tra i documenti selezionati",
                    detail="Il documento indicato come atto principale non e stato risolto nel fascicolo.",
                    source="Regola operativa PCT",
                    suggested_action="Riseleziona l'atto principale o ricarica i documenti del fascicolo.",
                    field="atto_principale_id",
                )
            )
            return issues

        total_bytes = 0
        for doc in selected_documents:
            path = Path(str(doc.get("percorso") or ""))
            if not path.exists():
                issues.append(
                    ValidationIssue(
                        service=SERVICE_DOCUMENTALE,
                        level=LEVEL_BLOCK,
                        code="documento_non_trovato",
                        title="Documento selezionato non trovato su disco",
                        detail=f"Il file '{doc.get('nome')}' non e disponibile nel percorso atteso.",
                        source="Regola operativa interna",
                        suggested_action="Ricarica il documento nel fascicolo prima del deposito.",
                        field="allegati_ids",
                    )
                )
                continue

            dim = verifica_dimensione(str(path), max_bytes=MAX_BYTES_ALLEGATO)
            doc_bytes = _safe_int(dim.get("bytes"))
            total_bytes += doc_bytes
            if not dim.get("ok"):
                issues.append(
                    ValidationIssue(
                        service=SERVICE_DOCUMENTALE,
                        level=LEVEL_BLOCK,
                        code="allegato_troppo_grande",
                        title="Documento oltre il limite dimensionale PST",
                        detail=(
                            f"Il file '{doc.get('nome')}' supera il limite tecnico di "
                            f"{PST_MAX_BUSTA_MB} MB."
                        ),
                        source="Specifiche tecniche DGSIA 7 agosto 2024, art. 17",
                        suggested_action="Riduci il file, comprimilo o suddividi il deposito.",
                        field="allegati_ids",
                    )
                )

            if doc.get("id") == main_doc_id:
                if not bool(doc.get("firmato_digitalmente")) and not _is_signed_container_document(doc, path):
                    issues.append(
                        ValidationIssue(
                            service=SERVICE_DOCUMENTALE,
                            level=LEVEL_BLOCK,
                            code="atto_principale_non_firmato",
                            title="Atto principale non firmato digitalmente",
                            detail="L'atto principale deve essere firmato digitalmente prima del deposito.",
                            source="D.M. 44/2011 art. 12",
                            suggested_action="Firma il documento principale in CAdES/PAdES prima di creare la busta.",
                            field="atto_principale_id",
                        )
                    )
                pdfa = verifica_pdfa(str(path))
                if pdfa.get("conforme") is False:
                    issues.append(
                        ValidationIssue(
                            service=SERVICE_DOCUMENTALE,
                            level=LEVEL_BLOCK,
                            code="atto_principale_non_pdfa",
                            title="Atto principale non conforme PDF/A",
                            detail=str(pdfa.get("messaggio") or "Il documento principale non risulta PDF/A."),
                            source="D.M. 44/2011 art. 12",
                            suggested_action="Converti il PDF in PDF/A prima della firma e del deposito.",
                            field="atto_principale_id",
                        )
                    )
                elif pdfa.get("conforme") is None:
                    issues.append(
                        ValidationIssue(
                            service=SERVICE_DOCUMENTALE,
                            level=LEVEL_WARNING,
                            code="pdfa_non_verificabile_su_p7m",
                            title="Conformita PDF/A non verificabile sul wrapper firmato",
                            detail=(
                                "Il file principale e un wrapper .p7m: la conformita PDF/A del PDF interno va "
                                "verificata sul documento originale prima della firma."
                            ),
                            source="D.M. 44/2011 art. 12",
                            suggested_action="Se necessario conserva anche il PDF originale validato PDF/A.",
                            field="atto_principale_id",
                        )
                    )

        if total_bytes > PST_MAX_BUSTA_BYTES:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_BLOCK,
                    code="dimensione_busta_t003",
                    title="Busta oltre il limite ministeriale",
                    detail=(
                        f"La selezione attuale pesa circa {round(total_bytes / (1024 * 1024), 2)} MB "
                        f"e supera il limite PST di {PST_MAX_BUSTA_MB} MB (controllo T003)."
                    ),
                    source="Specifiche tecniche D.M. 44/2011 rev. 04.01.24",
                    suggested_action="Riduci la dimensione complessiva del deposito prima di generare la busta.",
                    field="allegati_ids",
                )
            )
        elif total_bytes > int(PST_MAX_BUSTA_BYTES * 0.75):
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_WARNING,
                    code="busta_pesante",
                    title="Busta documentale pesante",
                    detail=(
                        f"La selezione attuale pesa circa {round(total_bytes / (1024 * 1024), 2)} MB: "
                        "verifica il margine residuo rispetto al limite ministeriale e l'opportunita di un deposito piu snello."
                    ),
                    source="Specifiche tecniche D.M. 44/2011 rev. 04.01.24",
                    suggested_action="Valuta la riduzione di scansioni e allegati non essenziali.",
                    field="allegati_ids",
                )
            )

        return issues


class ValidatorSchemiPST:
    """Controlli tecnici su DatiAtto.xml, namespace, registro e struttura busta."""

    def validate(
        self,
        fascicolo: Fascicolo,
        profile: ProceduralProfile,
        resolver: Dict[str, Any],
        context: Dict[str, Any],
        selected_documents: List[Dict[str, Any]],
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if profile.channel == "PTT_TRIBUTARIO":
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_WARNING,
                    code="schema_sigit_formweb",
                    title="Controllo tecnico PTT eseguito senza DatiAtto.xml",
                    detail=(
                        "Per il canale tributario la verifica tecnica non genera DatiAtto.xml o busta .enc: "
                        "controlla coerenza di Corte di giustizia tributaria, registro PTT, NIR, CUT pagoPA "
                        "e allegati richiesti dal portale SIGIT."
                    ),
                    source="SIGIT / PTT - workflow portale / assistenza MEF",
                    suggested_action=(
                        "Usa la simulazione SIGIT/PTT e conferma NIR, registro PTT_RICORSI, firma CAdES "
                        "e associazione CUT pagoPA al numero RGR/RGA."
                    ),
                    field="codice_registro",
                )
            )
            return issues
        if profile.channel in {"PAT_AMMINISTRATIVO", "PDP_PENALE"}:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_WARNING,
                    code="schema_portale_non_pct",
                    title="Controllo tecnico eseguito sul canale portale dedicato",
                    detail=(
                        "Per questo canale il preflight conferma fascicolo, ufficio, registro e allegati, "
                        "ma non genera il DatiAtto.xml del PCT civile."
                    ),
                    source="Workflow portali telematici dedicati",
                    suggested_action="Completa la verifica documentale e usa la simulazione del canale dedicato.",
                    field="tipo_atto",
                )
            )
            return issues
        if profile.channel != "PCT_TELEMATICO":
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="schema_non_pct",
                    title="Profilo non compatibile con il generatore DatiAtto.xml",
                    detail="La validazione schemi PST e disponibile solo per profili depositabili via PCT.",
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Usa il canale procedurale coerente con l'atto selezionato.",
                    field="tipo_atto",
                )
            )
            return issues

        main_doc = next((d for d in selected_documents if d.get("id") == context.get("atto_principale_id")), None)
        if not main_doc:
            return issues
        codice_oggetto_pst = normalize_codice_oggetto_pst(
            context.get("codice_oggetto_pst")
            or getattr(fascicolo, "codice_oggetto_pst", "")
            or context.get("oggetto")
            or getattr(fascicolo, "oggetto", "")
        )
        codice_oggetto_entry = codice_oggetto_pst_entry(codice_oggetto_pst)
        if not codice_oggetto_pst:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="xml_codice_oggetto_mancante",
                    title="DatiAtto.xml senza codice oggetto",
                    detail="Il nodo Oggetto del DatiAtto.xml deve contenere un CodiceOggetto PST, non la descrizione della pratica.",
                    source="PST - XSD tipi-base.xsd / CodiceOggetto",
                    suggested_action="Completa il codice oggetto PST nel fascicolo e ripeti la validazione.",
                    field="codice_oggetto_pst",
                )
            )
            return issues
        if not codice_oggetto_entry:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="xml_codice_oggetto_non_ufficiale",
                    title="DatiAtto.xml con codice oggetto non ufficiale",
                    detail=f"Il valore '{codice_oggetto_pst}' non e presente nel catalogo PST importato.",
                    source="PST - XSD tipi-base.xsd / CodiceOggetto",
                    suggested_action="Seleziona un codice oggetto ufficiale prima di generare la busta.",
                    field="codice_oggetto_pst",
                )
            )
            return issues

        if not resolver.get("effective_office_found"):
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="ufficio_non_mappato_catalogo",
                    title="Ufficio non mappato sul catalogo PST",
                    detail=(
                        "Il DatiAtto.xml richiede un ufficio coerente con il catalogo ministeriale; "
                        "la sede attuale non e stata risolta in modo certo."
                    ),
                    source="PST - catalogo uffici giudiziari",
                    suggested_action="Correggi il campo tribunale / ufficio nel fascicolo prima di generare la busta.",
                    field="tribunale",
                )
            )
            return issues

        try:
            allegati = [
                Allegato(
                    percorso=str(doc.get("percorso") or ""),
                    descrizione=str(doc.get("nome") or ""),
                    tipo="ALLEGATO",
                )
                for doc in selected_documents
                if doc.get("id") != context.get("atto_principale_id")
            ]
            dati = DatiBusta(
                codice_ufficio=str(
                    resolver.get("effective_office_code")
                    or resolver.get("office_code")
                    or fascicolo.tribunale
                    or "SCONOSCIUTO"
                ),
                codice_registro=str(context.get("codice_registro") or "RG"),
                oggetto=codice_oggetto_pst,
                tipo_atto=str(context.get("tipo_atto") or "ATTO_GENERICO"),
                atto_principale=str(main_doc.get("percorso") or ""),
                allegati=allegati,
                numero_rg=str(context.get("numero_rg") or fascicolo.numero_rg or "") or None,
                anno_rg=_safe_int(context.get("anno_rg") or fascicolo.anno_rg) or None,
                operatore=str(context.get("operatore") or ""),
                cf_mittente=str(context.get("cf_mittente") or ""),
            )
            busta = BustaTelematica(dati)
            xml_bytes = busta._crea_xml_dati_atto()
            root = etree.fromstring(xml_bytes)
            busta_audit = busta.audit_conformita_pst()
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="xml_non_generabile",
                    title="DatiAtto.xml non generabile",
                    detail=f"Il generatore tecnico ha restituito un errore: {exc}",
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Correggi i metadati del deposito e riprova la validazione tecnica.",
                    field="tipo_atto",
                )
            )
            return issues

        ns_default = root.nsmap.get(None, "")
        ns = {"p": PST_NAMESPACE}
        if ns_default != PST_NAMESPACE:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="namespace_errato",
                    title="Namespace XML non conforme",
                    detail=f"Il namespace generato e '{ns_default}', atteso '{PST_NAMESPACE}'.",
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Verifica il generatore DatiAtto.xml e la versione schema attiva.",
                    field="tipo_atto",
                )
            )

        attoprincipale = root.find(".//p:Documenti/p:Attoprincipale", ns)
        if attoprincipale is None:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="attoprincipale_mancante",
                    title="Nodo Attoprincipale mancante",
                    detail="Il DatiAtto.xml non contiene il nodo Attoprincipale richiesto dalla struttura PST.",
                    source="D.M. 44/2011 Allegato 2 / specifiche PST",
                    suggested_action="Verifica la selezione del documento principale e rigenera la busta.",
                    field="atto_principale_id",
                )
            )
        codice_registro_xml = root.findtext(".//p:UfficioGiudiziario/p:CodiceRegistro", namespaces=ns) or ""
        if codice_registro_xml.strip().upper() != str(context.get("codice_registro") or "").strip().upper():
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="registro_xml_non_coerente",
                    title="Registro del DatiAtto.xml non coerente",
                    detail=(
                        f"Il XML riporta il registro '{codice_registro_xml}', diverso dal valore selezionato "
                        f"'{context.get('codice_registro')}'."
                    ),
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Riallinea il registro e riesegui la validazione tecnica.",
                    field="codice_registro",
                )
            )

        tipo_atto_xml = root.findtext(".//p:Atto/p:TipoAtto", namespaces=ns) or ""
        if _slug(tipo_atto_xml) != _slug(str(context.get("tipo_atto") or "")):
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="tipo_atto_xml_non_coerente",
                    title="Tipo atto del DatiAtto.xml non coerente",
                    detail=(
                        f"Il XML riporta '{tipo_atto_xml}', diverso dalla selezione attuale "
                        f"'{context.get('tipo_atto')}'."
                    ),
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Riallinea il tipo atto prima della generazione della busta.",
                    field="tipo_atto",
                )
            )

        oggetto_xml = root.findtext(".//p:Atto/p:Oggetto", namespaces=ns) or ""
        if oggetto_xml.strip() != codice_oggetto_pst:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="codice_oggetto_xml_non_coerente",
                    title="Codice oggetto nel DatiAtto.xml non coerente",
                    detail=(
                        f"Il XML riporta '{oggetto_xml}', diverso dal codice oggetto validato "
                        f"'{codice_oggetto_pst}'."
                    ),
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Rigenera il DatiAtto.xml dopo aver riallineato il codice oggetto del fascicolo.",
                    field="codice_oggetto_pst",
                )
            )

        codice_ufficio_xml = root.findtext(".//p:UfficioGiudiziario/p:CodiceUfficio", namespaces=ns) or ""
        if str(codice_ufficio_xml).strip() != str(
            resolver.get("effective_office_code") or resolver.get("office_code") or ""
        ).strip():
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_WARNING,
                    code="codice_ufficio_xml_non_verificato",
                    title="Codice ufficio XML da verificare",
                    detail=(
                        f"Il XML riporta il codice ufficio '{codice_ufficio_xml}', verifica che corrisponda "
                        "al catalogo ministeriale attivo."
                    ),
                    source="PST - catalogo uffici giudiziari",
                    suggested_action="Confronta ufficio, sede e catalogo aggiornato se il fascicolo e datato.",
                    field="tribunale",
                )
            )

        hash_el = root.findtext(".//p:Documenti/p:Attoprincipale/p:Hash", namespaces=ns) or ""
        if not re.fullmatch(r"[A-F0-9]{64}", hash_el.strip()):
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="hash_principale_non_valido",
                    title="Hash dell'atto principale non valido",
                    detail="L'hash del documento principale non ha il formato SHA-256 atteso.",
                    source="D.M. 44/2011 Allegato 2",
                    suggested_action="Rigenera la busta dopo aver verificato il documento principale.",
                    field="atto_principale_id",
                )
            )

        if profile.required_existing_rg and root.find(".//p:RiferimentoProcedimento", ns) is None:
            issues.append(
                ValidationIssue(
                    service=SERVICE_TECNICO,
                    level=LEVEL_BLOCK,
                    code="riferimento_procedimento_assente",
                    title="RiferimentoProcedimento assente nel DatiAtto.xml",
                    detail="Per questo deposito e richiesto il riferimento a numero e anno RG nel XML tecnico.",
                    source="PST - specifiche tecniche deposito",
                    suggested_action="Compila numero e anno RG nel fascicolo e rigenera la validazione.",
                    field="numero_rg",
                )
            )

        context["pst_busta_audit"] = busta_audit

        return issues


class GestioneValidazioniDeposito:
    """Persistenza JSON delle validazioni di pre-deposito."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {"runs": []}
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {"runs": []}
        if isinstance(raw, list):
            return {"runs": raw}
        if isinstance(raw, dict):
            raw.setdefault("runs", [])
            return raw
        return {"runs": []}

    def _save(self, payload: Dict[str, Any]) -> None:
        self.db_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def salva_run(self, run: ValidationRun) -> None:
        payload = self._load()
        runs = [r for r in payload.get("runs", []) if r.get("id") != run.id]
        runs.insert(0, run.to_dict())
        payload["runs"] = runs[:500]
        self._save(payload)

    def ultimo_fascicolo(self, fascicolo_id: str) -> Optional[ValidationRun]:
        payload = self._load()
        for raw in payload.get("runs", []):
            if raw.get("fascicolo_id") == fascicolo_id:
                return ValidationRun.from_dict(raw)
        return None

    def lista_fascicolo(self, fascicolo_id: str) -> List[ValidationRun]:
        payload = self._load()
        return [
            ValidationRun.from_dict(raw)
            for raw in payload.get("runs", [])
            if raw.get("fascicolo_id") == fascicolo_id
        ]


class OrchestratoreDepositoGuidato:
    """Orchestratore centrale: resolver + validator giuridico + validator tecnico/documentale."""

    def __init__(
        self,
        validation_db_path: str,
        office_cache_path: str = "",
        *,
        pst_wsdl_catalog_zip_path: str = "",
        pst_official_cache_path: str = "",
        pst_catalog_endpoint: str = "",
        pst_timeout: float = 8.0,
    ) -> None:
        self.kb = ProceduralKnowledgeBase()
        self.resolver = CompetenceResolver(
            office_cache_path=office_cache_path,
            pst_wsdl_catalog_zip_path=pst_wsdl_catalog_zip_path,
            pst_official_cache_path=pst_official_cache_path,
            pst_catalog_endpoint=pst_catalog_endpoint,
            pst_timeout=pst_timeout,
        )
        self.validator_normativo = ValidatorNormativoRedazionale()
        self.validator_tecnico = ValidatorSchemiPST()
        self.validator_documentale = DocumentValidator()
        self.store = GestioneValidazioniDeposito(validation_db_path)

    def valida(
        self,
        fascicolo: Fascicolo,
        context: Dict[str, Any],
        selected_documents: List[Dict[str, Any]],
        all_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> ValidationRun:
        all_documents = list(all_documents or selected_documents)
        normalized_context = {
            "tipo_atto": str(context.get("tipo_atto") or "ATTO_GENERICO").strip(),
            "codice_registro": str(context.get("codice_registro") or "RG").strip().upper(),
            "oggetto": str(context.get("oggetto") or fascicolo.titolo or "").strip(),
            "codice_oggetto_pst": normalize_codice_oggetto_pst(
                context.get("codice_oggetto_pst")
                or getattr(fascicolo, "codice_oggetto_pst", "")
                or context.get("oggetto")
                or getattr(fascicolo, "oggetto", "")
            ),
            "numero_rg": str(context.get("numero_rg") or fascicolo.numero_rg or "").strip(),
            "anno_rg": _safe_int(context.get("anno_rg") or fascicolo.anno_rg),
            "atto_principale_id": str(context.get("atto_principale_id") or "").strip(),
            "allegati_ids": list(context.get("allegati_ids") or []),
            "note": str(context.get("note") or "").strip(),
            "operatore": str(context.get("operatore") or "").strip(),
            "cf_mittente": str(context.get("cf_mittente") or "").strip(),
        }

        profile = self.kb.resolve_profile(fascicolo, normalized_context["tipo_atto"])
        resolver = self.resolver.resolve(
            fascicolo,
            profile,
            normalized_context["codice_registro"],
            context=normalized_context,
        )

        issues: List[ValidationIssue] = []
        issues.extend(
            self.validator_normativo.validate(
                fascicolo=fascicolo,
                profile=profile,
                resolver=resolver,
                context=normalized_context,
                selected_documents=selected_documents,
                all_documents=all_documents,
            )
        )
        issues.extend(
            self.validator_documentale.validate(
                profile=profile,
                context=normalized_context,
                selected_documents=selected_documents,
            )
        )
        issues.extend(
            self.validator_tecnico.validate(
                fascicolo=fascicolo,
                profile=profile,
                resolver=resolver,
                context=normalized_context,
                selected_documents=selected_documents,
            )
        )

        semaforo = {
            "giuridico": _service_state(issues, SERVICE_GIURIDICO),
            "tecnico_pst": _service_state(issues, SERVICE_TECNICO),
            "documentale": _service_state(issues, SERVICE_DOCUMENTALE),
        }
        overall_state = _overall_state(issues)
        selected_summary = [
            {
                "id": doc.get("id"),
                "nome": doc.get("nome"),
                "tipo": doc.get("tipo"),
                "firmato_digitalmente": bool(doc.get("firmato_digitalmente")),
                "dimensione_bytes": _safe_int(doc.get("dimensione_bytes")),
            }
            for doc in selected_documents
        ]
        snapshot = {
            "validated_at": _now_iso(),
            "app_version": APP_VERSION,
            "procedural_kb_version": self.kb.version,
            "schema_catalog_version": SCHEMA_CATALOG_VERSION,
            "office_catalog_version": OFFICE_CATALOG_VERSION,
            "pst_webservices_doc_version": PST_WEB_SERVICES_DOC_VERSION,
            "pst_webservices_doc_url": PST_WEB_SERVICES_DOC_URL,
            "pst_dm44_specifiche_url": PST_DM44_SPECIFICHE_URL,
            "profile_channel": profile.channel,
            "profile_deposit_mode": profile.deposit_mode,
            "codice_oggetto_pst": normalized_context["codice_oggetto_pst"],
            "pst_busta_audit": dict(normalized_context.get("pst_busta_audit") or {}),
            "selected_documents": selected_summary,
            "selected_count": len(selected_summary),
        }
        snapshot["snapshot_hash"] = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]

        run = ValidationRun(
            id=uuid.uuid4().hex[:12],
            fascicolo_id=fascicolo.id,
            created_at=_now_iso(),
            profile_id=profile.id,
            profile_label=profile.label,
            channel=profile.channel,
            overall_state=overall_state,
            can_prepare_deposit=overall_state != "blocco",
            semaforo=semaforo,
            resolver=resolver,
            snapshot=snapshot,
            context=normalized_context,
            sources=_unique_sources(profile.fonti, _base_fonti()),
            issues=[issue.to_dict() for issue in issues],
        )
        self.store.salva_run(run)
        return run


# ================================================================
# API di convenienza — integrazione con PracticeProfile
# ================================================================

def get_deposit_policy(practice_id: str) -> Optional[Any]:
    """
    Restituisce il DepositPolicy del PRACTICE_REGISTRY per la pratica indicata.

    Utile per i validatori che devono sapere se una pratica richiede
    DatiAtto.xml (PCT), mTLS (PDP/PAT), pre-deposito obbligatorio, ecc.
    Restituisce None se la pratica non è nel registry.

    Esempio::

        policy = get_deposit_policy("comparsa_risposta")
        if policy and policy.needs_ministerial_xml:
            # valida DatiAtto.xml
    """
    try:
        from pct.practice_profiles import get_practice_profile as _gpp
        profile = _gpp(practice_id)
        return profile.deposit_policy if profile else None
    except Exception:
        return None


def get_conformity_binding(practice_id: str) -> Optional[Any]:
    """
    Restituisce il ConformityBinding del PRACTICE_REGISTRY per la pratica.

    Consente ai validatori di conoscere i blocking_checks specifici
    della pratica senza cablare logica per-practice nel validator.
    """
    try:
        from pct.practice_profiles import get_practice_profile as _gpp
        profile = _gpp(practice_id)
        return profile.conformity if profile else None
    except Exception:
        return None
