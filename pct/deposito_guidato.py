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

from . import __version__ as APP_VERSION
from .busta import Allegato, BustaTelematica, DatiBusta
from .checklist_atti import CANALE_LABEL
from .fascicoli import Fascicolo
from .validazione import MAX_BYTES_ALLEGATO, verifica_dimensione, verifica_pdfa


PROCEDURAL_KB_VERSION = "2026.04.02.1"
SCHEMA_CATALOG_VERSION = "PCT-SNAPSHOT-2026-01-26"
OFFICE_CATALOG_VERSION = "PST-CATALOGO-UFFICI-2026"
PST_NAMESPACE = "http://www.giustizia.it/processo_telematico"

SERVICE_GIURIDICO = "GIURIDICO"
SERVICE_TECNICO = "TECNICO_PST"
SERVICE_DOCUMENTALE = "DOCUMENTALE"

LEVEL_OK = "OK"
LEVEL_WARNING = "WARNING"
LEVEL_BLOCK = "BLOCK"


def _slug(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in norm if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9]+", " ", ascii_only.lower())
    return " ".join(lowered.split())


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    base = _slug(text)
    return any(_slug(needle) in base for needle in needles if needle)


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
            "label": "PST - documentazione servizi web software house",
            "url": "https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.52_1.pdf",
        },
        {
            "label": "D.Lgs. 149/2022",
            "url": "https://www.gazzettaufficiale.it/eli/id/2022/10/17/22G00158/sg",
        },
    ]


def _profile_fonti(*extra: dict[str, str]) -> list[dict[str, str]]:
    return _base_fonti() + list(extra)


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
        for profile in self._profiles:
            if profile.matches_tipo_atto(tipo_atto):
                return profile
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
            if _doc_matches(d, types=("NOTIFICA",), names=("notifica", "relata", "ricevuta pec", "ricevuta consegna"))
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
    }


class CompetenceResolver:
    """Risoluzione deterministica di ufficio, sede, grado e registro."""

    def __init__(self, office_cache_path: str = "") -> None:
        self.office_cache_path = office_cache_path

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
    ) -> Dict[str, Any]:
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

        payload = {
            "office_found": bool(office),
            "office_match_mode": match_mode,
            "office_name": str((office or {}).get("nome", tribunale or "")),
            "office_code": str((office or {}).get("codice", tribunale or "")),
            "office_type": str((office or {}).get("tipo", "")).upper(),
            "office_distretto": str((office or {}).get("distretto", "")),
            "requested_registry": (codice_registro or "").strip().upper(),
            "requested_channel": profile.channel,
            "requested_grade": profile.grado,
            "requested_rito": profile.rito,
            "allowed_office_types": list(profile.allowed_office_types),
            "allowed_registries": list(profile.allowed_registries),
            "catalog_versions": {
                "procedural_kb": PROCEDURAL_KB_VERSION,
                "office_catalog": OFFICE_CATALOG_VERSION,
                "schema_catalog": SCHEMA_CATALOG_VERSION,
            },
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
        operatore = str(context.get("operatore") or "").strip()
        fascicolo_tipo = fascicolo.tipo.value
        selected_groups = _classify_documents(selected_documents)
        all_groups = _classify_documents(all_documents)

        if profile.channel != "PCT_TELEMATICO":
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

        if fascicolo.tribunale and not resolver.get("office_found"):
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

        office_type = resolver.get("office_type", "")
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

        if profile.allowed_registries and registro and registro not in profile.allowed_registries:
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_BLOCK,
                    code="registro_errato",
                    title="Registro non compatibile con il procedimento",
                    detail=(
                        f"Il registro {registro} non rientra tra quelli consentiti per il profilo "
                        f"'{profile.label}' ({', '.join(profile.allowed_registries)})."
                    ),
                    source="Regola procedurale interna versionata",
                    suggested_action="Seleziona il registro compatibile con rito e grado del deposito.",
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
        if main_doc and _doc_matches(main_doc, types=("PROCURA", "NOTIFICA"), names=("procura", "relata", "contributo")):
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
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="contributo_non_evidenziato",
                    title="Ricevuta contributo unificato non rilevata",
                    detail="Per questo deposito introduttivo la ricevuta del contributo unificato non e stata rilevata.",
                    source="Regola procedurale interna versionata",
                    suggested_action="Verifica se il contributo e dovuto e, in caso affermativo, allega la ricevuta.",
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
            issues.append(
                ValidationIssue(
                    service=SERVICE_GIURIDICO,
                    level=LEVEL_WARNING,
                    code="indice_non_rilevato",
                    title="Indice deposito non rilevato",
                    detail=(
                        "Non e stato rilevato un indice documenti esplicito. In alcune prassi puo essere opportuno "
                        "predisporre un indice separato o una nota di deposito piu analitica."
                    ),
                    source="Prassi redazionale interna",
                    suggested_action="Valuta se allegare un indice sintetico o arricchire l'atto principale.",
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
                        detail=f"Il file '{doc.get('nome')}' supera il limite tecnico di 30 MB.",
                        source="D.M. 44/2011 art. 14",
                        suggested_action="Riduci il file, comprimilo o suddividi il deposito.",
                        field="allegati_ids",
                    )
                )

            if doc.get("id") == main_doc_id:
                if not bool(doc.get("firmato_digitalmente")):
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

        if total_bytes > MAX_BYTES_ALLEGATO:
            issues.append(
                ValidationIssue(
                    service=SERVICE_DOCUMENTALE,
                    level=LEVEL_WARNING,
                    code="busta_pesante",
                    title="Busta documentale pesante",
                    detail=(
                        f"La selezione attuale pesa circa {round(total_bytes / (1024 * 1024), 2)} MB: "
                        "verifica limiti PEC e opportunita di deposito piu snello."
                    ),
                    source="Regola tecnica operativa",
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

        if not resolver.get("office_found"):
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
                codice_ufficio=str(resolver.get("office_code") or fascicolo.tribunale or "SCONOSCIUTO"),
                codice_registro=str(context.get("codice_registro") or "RG"),
                oggetto=str(context.get("oggetto") or fascicolo.titolo or ""),
                tipo_atto=str(context.get("tipo_atto") or "ATTO_GENERICO"),
                atto_principale=str(main_doc.get("percorso") or ""),
                allegati=allegati,
                numero_rg=str(context.get("numero_rg") or fascicolo.numero_rg or "") or None,
                anno_rg=_safe_int(context.get("anno_rg") or fascicolo.anno_rg) or None,
                operatore=str(context.get("operatore") or ""),
                cf_mittente=str(context.get("cf_mittente") or ""),
            )
            xml_bytes = BustaTelematica(dati)._crea_xml_dati_atto()
            root = etree.fromstring(xml_bytes)
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

        codice_ufficio_xml = root.findtext(".//p:UfficioGiudiziario/p:CodiceUfficio", namespaces=ns) or ""
        if str(codice_ufficio_xml).strip() != str(resolver.get("office_code") or "").strip():
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

    def __init__(self, validation_db_path: str, office_cache_path: str = "") -> None:
        self.kb = ProceduralKnowledgeBase()
        self.resolver = CompetenceResolver(office_cache_path=office_cache_path)
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
            "numero_rg": str(context.get("numero_rg") or fascicolo.numero_rg or "").strip(),
            "anno_rg": _safe_int(context.get("anno_rg") or fascicolo.anno_rg),
            "atto_principale_id": str(context.get("atto_principale_id") or "").strip(),
            "allegati_ids": list(context.get("allegati_ids") or []),
            "note": str(context.get("note") or "").strip(),
            "operatore": str(context.get("operatore") or "").strip(),
            "cf_mittente": str(context.get("cf_mittente") or "").strip(),
        }

        profile = self.kb.resolve_profile(fascicolo, normalized_context["tipo_atto"])
        resolver = self.resolver.resolve(fascicolo, profile, normalized_context["codice_registro"])

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
            "profile_channel": profile.channel,
            "profile_deposit_mode": profile.deposit_mode,
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
