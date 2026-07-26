from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
import warnings
import unicodedata
from urllib.parse import urljoin, urlparse
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests
from lxml import html as lxml_html
from urllib3.exceptions import InsecureRequestWarning

from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.legal_intelligence_repository import (
    GestioneLegalIntelligenceRepository,
    build_legal_alert_rows,
    build_legal_audit_rows,
    build_legal_engine_edges_rows,
    build_legal_engines_rows,
    build_legal_keyword_engine_rows,
    build_legal_keyword_source_rows,
    build_legal_monitoring_rows,
    build_legal_operational_rules,
    build_legal_sources_rows,
    derive_legal_engine_edges_json_path,
    derive_legal_engines_json_path,
    derive_legal_intelligence_repository_db_path,
    derive_legal_intelligence_repository_json_path,
    derive_legal_keyword_engine_json_path,
    derive_legal_keyword_source_json_path,
    derive_legal_operational_json_path,
    derive_legal_sources_json_path,
)
from pct.polisWeb import PST_SEZIONI_WIZARD
from pct.normative_tables import FONTI_OPERATIVE, GestioneTabelleNormative
from pct.pst_catalog import (
    PST_PDP_SPECIFICHE_DETAIL_URL,
    PST_PDP_SPECIFICHE_URL,
    PST_WEB_SERVICES_DOC_DETAIL_URL,
    PST_WEB_SERVICES_DOC_PAGE_URL,
    PST_WEB_SERVICES_DOC_URL,
    PST_WEB_SERVICES_DOC_VERSION,
    PST_WEB_SERVICES_UPDATE_PAGE_URL,
    PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_NAME,
    PST_WEB_SERVICES_WSDL_CATALOG_VERSION,
    PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME,
    PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_VERSION,
    PST_XSD_DOWNLOAD_PAGE_URL,
    PST_FORMAL_ERROR_CODES,
    PST_MAX_BUSTA_BYTES,
    PST_MAX_BUSTA_MB,
    get_catalog_snapshot,
    get_catalog_sources,
    get_official_methods,
    get_wsdl_catalog_modules,
    get_xsd_channel,
    get_xsd_channels,
)
from pct.telematico_repository import (
    GestioneTelematicoRepository,
    build_telematico_action_rows,
    build_telematico_capability_rows,
    build_telematico_catalog_snapshot_row,
    build_telematico_catalog_source_rows,
    build_telematico_methods_rows,
    build_telematico_monitoring_rows,
    build_telematico_rule_rows,
    build_telematico_sources_rows,
    build_telematico_wizard_rows,
    build_telematico_wsdl_rows,
    build_telematico_xsd_rows,
    derive_telematico_actions_json_path,
    derive_telematico_capabilities_json_path,
    derive_telematico_catalog_snapshot_json_path,
    derive_telematico_catalog_sources_json_path,
    derive_telematico_methods_json_path,
    derive_telematico_monitoring_json_path,
    derive_telematico_repository_db_path,
    derive_telematico_repository_json_path,
    derive_telematico_rules_json_path,
    derive_telematico_sources_json_path,
    derive_telematico_wizard_json_path,
    derive_telematico_wsdl_modules_json_path,
    derive_telematico_xsd_channels_json_path,
)

USER_AGENT = "IUSENTRA-Legal-Intelligence/1.0 (+https://pst.giustizia.it)"
MAX_MONITOR_BYTES = 512_000
MAX_MONITOR_RUNS = 600
MAX_ALERTS = 400
MAX_AUDIT_TRACES = 500
REGISTRO_MEDIAZIONE_INFO_URL = "https://www.giustizia.it/giustizia/it/mg_3_4_15.page"
REGISTRO_MEDIAZIONE_DIRECT_URL = "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"
REGISTRO_MEDIAZIONE_ENTI_URL = "https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx"
REGISTRO_MEDIAZIONE_FORMATORI_URL = "https://mediazione.giustizia.it/ROM/AlboFormatori.aspx"
REGISTRO_MEDIAZIONE_TABLE_ID = "organismi_mediazione_elenco"
REGISTRO_MEDIAZIONE_IMPORT_MAX_BYTES = 5 * 1024 * 1024
REGISTRO_MEDIAZIONE_PAGE_SELECT_NAME = "acp_content$gvAlbo$ctl13$ddlPages"
REGISTRO_MEDIAZIONE_MAX_PAGES = 220
REGISTRO_MEDIAZIONE_NOTICE = (
    "Il Ministero della Giustizia segnala che la consultazione del registro diretto puo richiedere "
    "Microsoft Edge in modalita compatibilita con Internet Explorer."
)
PST_SERVIZI_WEB_TITLE_RE = re.compile(
    r"Documentazione servizi web esposti\s*\(versione\s*([0-9.]+)\)",
    re.IGNORECASE,
)
PST_SERVIZI_WEB_PDF_RE = re.compile(
    r"Documentazione_servizi_web_v([0-9.]+)\.pdf",
    re.IGNORECASE,
)
PST_SERVIZI_WEB_PDF_URL_RE = re.compile(
    r"(?P<url>https?://[^\s\"'>]*Documentazione_servizi_web_v[0-9.]+\.pdf|/PST/resources/cms/documents/Documentazione_servizi_web_v[0-9.]+\.pdf)",
    re.IGNORECASE,
)
PST_WSDL_CATALOG_RE = re.compile(
    r"A1[_-]WSDL[_-]CATALOG[_-]v([0-9]+(?:\.[0-9]+)*(?:[a-z])?)(?:\.zip|\b)",
    re.IGNORECASE,
)
PST_XSD_PACKAGE_RE = re.compile(r"(?P<name>[^/]+\.zip)$", re.IGNORECASE)
PST_XSD_PDF_RE = re.compile(r"(?P<name>[^/]+\.pdf)$", re.IGNORECASE)
PST_NEWS_DATE_RE = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\s+[a-z]+\s+\d{4})",
    re.IGNORECASE,
)
PST_XSD_SOURCE_CHANNELS = {
    "pst_xsd_sici": "SICI",
    "pst_xsd_sigp": "SIGP",
    "pst_xsd_unep": "UNEP",
    "pst_xsd_cassazione": "CASSAZIONE",
}
PST_XSD_PRODUCTION_MARKERS = (
    "utilizzabili in ambiente di produzione",
    "utilizzabili in ambiente di esercizio",
    "applicati in esercizio",
    "messi in produzione",
    "messa in produzione",
    "entrata in esercizio",
)
PST_XSD_PREVIEW_MARKERS = (
    "messa in esercizio verra comunicata successivamente",
    "messa in esercizio sara comunicata successivamente",
    "messa in esercizio sara comunicata successivamente",
    "data di messa in esercizio",
    "verra resa nota con successiva comunicazione",
)
ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate(value: str, limit: int = 220) -> str:
    value = _clean_spaces(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def _extract_pst_date(value: str) -> str:
    text = _clean_spaces(value)
    if not text:
        return ""
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return ""
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", text, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month = ITALIAN_MONTHS.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ""
    return ""


def _parse_iso_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _stable_registry_record_id(value: str) -> str:
    return hmac.new(
        b"iusentra-registro-mediazione-record-id-v1",
        str(value or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]


def _looks_like_html(content_type: str, url: str) -> bool:
    value = (content_type or "").lower()
    path = (urlparse(url or "").path or "").lower()
    return (
        "html" in value
        or path.endswith(".html")
        or path.endswith(".htm")
        or path.endswith(".page")
        or not Path(path).suffix
    )


def _normalize_textual_payload(content: bytes, content_type: str, url: str) -> bytes:
    if not _looks_like_html(content_type, url):
        return content
    text = (content or b"").decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = _clean_spaces(text)
    return text.encode("utf-8")


def _detect_protection_page(final_url: str, content: bytes) -> bool:
    normalized = _normalize_textual_payload(content, "text/html", final_url).decode("utf-8", errors="ignore")
    sample = (
        (final_url or "")
        + "\n"
        + (content or b"").decode("utf-8", errors="ignore")[:6000]
        + "\n"
        + normalized[:6000]
    ).lower()
    markers = (
        "validate.perfdrive.com",
        "radware",
        "security challenge",
        "captcha",
        "enable javascript",
        "please wait while we verify",
        "errore nel caricamento delle informazioni",
        "session id:",
        "normattiva - errore",
    )
    return any(marker in sample for marker in markers)


def _requires_tls_fallback(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return (
        host.endswith("giustizia-amministrativa.it")
        or host.endswith("giustizia.it")
    )


def _severity_rank(level: str) -> int:
    return {"critica": 4, "alta": 3, "media": 2, "bassa": 1, "info": 0}.get((level or "").lower(), 0)


def _normalize_label(value: str) -> str:
    cleaned = unicodedata.normalize("NFKD", value or "")
    cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return _clean_spaces(cleaned)


def _normalize_registry_kind(value: str) -> str:
    normalized = _normalize_label(value)
    if "pubblic" in normalized:
        return "Pubblico"
    if "privat" in normalized:
        return "Privato"
    if "camera" in normalized or "camera di commercio" in normalized:
        return "Camera di commercio"
    if "ordine" in normalized:
        return "Ordine professionale"
    return value or ""


@dataclass(frozen=True)
class FonteUfficiale:
    id: str
    nome: str
    motore: str
    area: str
    official_url: str
    monitor_url: str
    connector_kind: str
    cadence: str
    formats: List[str] = field(default_factory=list)
    capability: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MotoreLegale:
    id: str
    nome: str
    short_name: str
    descrizione: str
    output: str
    value: str
    source_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MonitorRun:
    id: str
    source_id: str
    checked_at: str
    published_at: str = ""
    acquired_at: str = ""
    official_url: str = ""
    monitor_url: str = ""
    final_url: str = ""
    status: str = "ok"
    status_code: int = 0
    content_hash: str = ""
    content_type: str = ""
    size_bytes: int = 0
    changed: bool = False
    comparison_mode: str = "raw"
    detected_version: str = ""
    detected_reference: str = ""
    detected_document_url: str = ""
    detected_package: str = ""
    detected_package_date: str = ""
    detected_status: str = ""
    detected_news_date: str = ""
    detected_news_url: str = ""
    summary: str = ""
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorRun":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


@dataclass
class IntelligenceAlert:
    id: str
    created_at: str
    source_id: str
    motore_id: str
    alert_type: str
    severity: str
    title: str
    details: str
    official_url: str = ""
    related_entity_type: str = ""
    related_entity_id: str = ""
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntelligenceAlert":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


@dataclass
class AuditTrace:
    id: str
    created_at: str
    query: str
    user: str = ""
    engine_ids: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)
    source_snapshots: List[Dict[str, str]] = field(default_factory=list)
    ai_model: str = ""
    result_summary: str = ""
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditTrace":
        payload = dict(data or {})
        fields = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in fields})


FONTI_UFFICIALI: Dict[str, FonteUfficiale] = {
    "normattiva": FonteUfficiale(
        id="normattiva",
        nome="Normattiva / Open Data",
        motore="fonti_ufficiali",
        area="Normativa italiana",
        official_url="https://www.normattiva.it/",
        monitor_url="https://dati.normattiva.it/assets/come_fare_per/API_Normattiva_OpenData.pdf",
        connector_kind="open-data",
        cadence="giornaliera",
        formats=["XML", "JSON", "PDF"],
        capability="Testo vigente, multivigenza e API strutturate.",
        notes="Fonte primaria per testo vigente e versionamento normativo.",
    ),
    "gazzetta_ufficiale": FonteUfficiale(
        id="gazzetta_ufficiale",
        nome="Gazzetta Ufficiale",
        motore="fonti_ufficiali",
        area="Pubblicazioni ufficiali",
        official_url="https://www.gazzettaufficiale.it/",
        monitor_url="https://www.gazzettaufficiale.it/rss/SG",
        connector_kind="rss-portal",
        cadence="quotidiana",
        formats=["RSS", "HTML", "PDF"],
        capability="Pubblicazione e archivio degli atti normativi ufficiali.",
        notes="Per pubblicazione, entrata in vigore e serie speciali.",
    ),
    "pst_giustizia": FonteUfficiale(
        id="pst_giustizia",
        nome="PST Giustizia",
        motore="procedurale_telematico",
        area="Telematico",
        official_url=PST_WEB_SERVICES_DOC_PAGE_URL,
        monitor_url=PST_WEB_SERVICES_DOC_PAGE_URL,
        connector_kind="portal-docs",
        cadence="piu-volte-al-giorno",
        formats=["HTML", "PDF", "WSDL", "XSD"],
        capability="Indice ufficiale della documentazione PST per software house, XSD, WSDL e specifiche tecniche.",
        notes=(
            "Pagina ufficiale 'Documentazione' del PST: da qui il Ministero pubblica documentazione servizi web, "
            "schemi XSD, note software house e specifiche tecniche dei canali telematici."
        ),
    ),
    "pst_servizi_web": FonteUfficiale(
        id="pst_servizi_web",
        nome="PST - documentazione servizi web",
        motore="procedurale_telematico",
        area="Telematico / servizi web",
        official_url=PST_WEB_SERVICES_DOC_DETAIL_URL,
        monitor_url=PST_WEB_SERVICES_DOC_DETAIL_URL,
        connector_kind="portal-docs",
        cadence="giornaliera",
        formats=["HTML", "PDF", "ZIP", "WSDL"],
        capability="Monitora la versione pubblicata della documentazione servizi web per software house e del catalogo WSDL allegato.",
        notes=(
            f"La pagina documentazione PST espone attualmente la documentazione servizi web versione {PST_WEB_SERVICES_DOC_VERSION} "
            f"con PDF dedicato {PST_WEB_SERVICES_DOC_URL}, catalogo WSDL pubblicato {PST_WEB_SERVICES_WSDL_CATALOG_PUBLISHED_NAME} "
            f"e pacchetto diretto mantenuto nel catalogo interno {PST_WEB_SERVICES_WSDL_CATALOG_PACKAGE_NAME}."
        ),
    ),
    "pst_download": FonteUfficiale(
        id="pst_download",
        nome="PST - pagina download",
        motore="procedurale_telematico",
        area="Telematico / download ufficiali",
        official_url=PST_XSD_DOWNLOAD_PAGE_URL,
        monitor_url=PST_XSD_DOWNLOAD_PAGE_URL,
        connector_kind="portal-docs",
        cadence="giornaliera",
        formats=["HTML", "ZIP", "CER", "DTD", "XSD", "PDF"],
        capability="Monitora la pagina PST che pubblica certificati proxy, DTD, XSD, ReGIndE e altri file ufficiali scaricabili.",
        notes=(
            "Pagina download del PST usata come indice ufficiale dei file ministeriali scaricabili: "
            "certificati proxy PdA/PST, DTD, XSD SICI/SIGP/UNEP/Cassazione e schemi ReGIndE."
        ),
    ),
    "pst_pdp_specifiche": FonteUfficiale(
        id="pst_pdp_specifiche",
        nome="PST - specifiche tecniche PDP",
        motore="procedurale_telematico",
        area="Telematico / deposito penale",
        official_url=PST_PDP_SPECIFICHE_DETAIL_URL,
        monitor_url=PST_PDP_SPECIFICHE_DETAIL_URL,
        connector_kind="portal-docs",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Monitora la scheda ufficiale PST e il PDF delle specifiche tecniche del Portale Deposito Atti Penali.",
        notes=(
            f"Fonte ufficiale dedicata al PDP sul PST, con dettaglio {PST_PDP_SPECIFICHE_DETAIL_URL} "
            f"e allegato PDF {PST_PDP_SPECIFICHE_URL}."
        ),
    ),
    "pst_xsd_sici": FonteUfficiale(
        id="pst_xsd_sici",
        nome="PST - XSD SICI",
        motore="procedurale_telematico",
        area="Telematico / XSD civile",
        official_url=get_xsd_channel("SICI").download_page_url,
        monitor_url=get_xsd_channel("SICI").download_page_url,
        connector_kind="portal-xsd",
        cadence="giornaliera",
        formats=["HTML", "ZIP", "PDF"],
        capability="Monitora pacchetto XSD SICI, changelog e stato di esercizio del civile.",
        notes=get_xsd_channel("SICI").notes,
    ),
    "pst_xsd_sigp": FonteUfficiale(
        id="pst_xsd_sigp",
        nome="PST - XSD SIGP / Giudice di Pace",
        motore="procedurale_telematico",
        area="Telematico / XSD Giudice di Pace",
        official_url=get_xsd_channel("SIGP").download_page_url,
        monitor_url=get_xsd_channel("SIGP").download_page_url,
        connector_kind="portal-xsd",
        cadence="giornaliera",
        formats=["HTML", "ZIP", "PDF"],
        capability="Monitora pacchetto XSD SIGP e relativo stato di produzione.",
        notes=get_xsd_channel("SIGP").notes,
    ),
    "pst_xsd_unep": FonteUfficiale(
        id="pst_xsd_unep",
        nome="PST - XSD UNEP",
        motore="procedurale_telematico",
        area="Telematico / XSD UNEP",
        official_url=get_xsd_channel("UNEP").download_page_url,
        monitor_url=get_xsd_channel("UNEP").download_page_url,
        connector_kind="portal-xsd",
        cadence="giornaliera",
        formats=["HTML", "ZIP", "PDF"],
        capability="Monitora pacchetto XSD UNEP e la sua entrata in esercizio.",
        notes=get_xsd_channel("UNEP").notes,
    ),
    "pst_xsd_cassazione": FonteUfficiale(
        id="pst_xsd_cassazione",
        nome="PST - XSD Cassazione",
        motore="procedurale_telematico",
        area="Telematico / XSD Cassazione",
        official_url=get_xsd_channel("CASSAZIONE").download_page_url,
        monitor_url=get_xsd_channel("CASSAZIONE").download_page_url,
        connector_kind="portal-xsd",
        cadence="giornaliera",
        formats=["HTML", "ZIP", "PDF"],
        capability="Monitora pacchetto XSD del processo telematico di legittimita e stato di esercizio.",
        notes=get_xsd_channel("CASSAZIONE").notes,
    ),
    "cnf": FonteUfficiale(
        id="cnf",
        nome="Consiglio Nazionale Forense",
        motore="professione_forense",
        area="Professione forense",
        official_url="https://www.consiglionazionaleforense.it/",
        monitor_url="https://www.consiglionazionaleforense.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Codice deontologico, normativa professionale e parametri forensi.",
        notes="Riferimento per preventivi, incarichi ed alert deontologici.",
    ),
    "registro_mediazione": FonteUfficiale(
        id="registro_mediazione",
        nome="Registro organismi di mediazione",
        motore="fonti_ufficiali",
        area="ADR / mediazione civile",
        official_url="https://www.giustizia.it/giustizia/it/mg_3_4_15.page",
        monitor_url="https://www.giustizia.it/giustizia/it/mg_3_4_15.page",
        connector_kind="portal-info",
        cadence="giornaliera",
        formats=["HTML"],
        capability="Registro ufficiale degli organismi di mediazione e istruzioni ministeriali per la consultazione.",
        notes=(
            "La scheda ministeriale del 4 marzo 2026 rinvia al registro online "
            "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX "
            "e segnala l'uso di Microsoft Edge in modalita compatibilita con Internet Explorer."
        ),
    ),
    "cassazione": FonteUfficiale(
        id="cassazione",
        nome="Corte di Cassazione",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza di legittimita",
        official_url="https://www.cortedicassazione.it/",
        monitor_url="https://www.cortedicassazione.it/it/massimario.page",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Servizi online, massimario e raccolte ufficiali.",
        notes="Da collegare a massime, SentenzeWeb e principi di diritto.",
    ),
    "corte_costituzionale": FonteUfficiale(
        id="corte_costituzionale",
        nome="Corte costituzionale",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza costituzionale",
        official_url="https://www.cortecostituzionale.it/",
        monitor_url="https://www.cortecostituzionale.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Decisioni, depositi e comunicati ufficiali.",
        notes="Indispensabile per depositi e decisioni costituzionali.",
    ),
    "giustizia_amministrativa": FonteUfficiale(
        id="giustizia_amministrativa",
        nome="Giustizia amministrativa",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza amministrativa",
        official_url="https://www.giustizia-amministrativa.it/",
        monitor_url="https://www.giustizia-amministrativa.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Decisioni e pareri TAR/Consiglio di Stato.",
        notes="Da collegare a ricorsi, cautelari e orientamenti amministrativi.",
    ),
    "merito_civile_bdp": FonteUfficiale(
        id="merito_civile_bdp",
        nome="Banca Dati di Merito",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza civile di merito",
        official_url="https://pst.giustizia.it/PST/",
        monitor_url="https://pst.giustizia.it/PST/",
        connector_kind="browser-auth",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Provvedimenti civili di Tribunali e Corti d'appello accessibili tramite PST area riservata.",
        notes=(
            "La banca dati di merito civile richiede autenticazione tramite PST e copre i provvedimenti "
            "pubblicati dal 1 gennaio 2016, con esclusione delle materie famiglia, minori e stato della persona."
        ),
    ),
    "giustizia_tributaria": FonteUfficiale(
        id="giustizia_tributaria",
        nome="Giustizia tributaria",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza tributaria",
        official_url="https://www.giustiziatributaria.gov.it/",
        monitor_url="https://www.giustiziatributaria.gov.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Decisioni tributarie, massime e banca dati ufficiale delle controversie.",
        notes="Da usare con recupero assistito e fascicolo tributario interno, senza promettere sync live diretto.",
    ),
    "curia": FonteUfficiale(
        id="curia",
        nome="CURIA",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza UE",
        official_url="https://curia.europa.eu/jcms/jcms/j_6/it/",
        monitor_url="https://curia.europa.eu/juris/recherche.jsf?language=it",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Ricerca ufficiale CGUE e Tribunale UE con ECLI e banca dati giurisprudenziale.",
        notes="Da collegare a fiscalità, concorrenza, appalti, consumatori e privacy.",
    ),
    "eur_lex": FonteUfficiale(
        id="eur_lex",
        nome="EUR-Lex",
        motore="fonti_ufficiali",
        area="Normativa UE",
        official_url="https://eur-lex.europa.eu/",
        monitor_url="https://eur-lex.europa.eu/oj/direct-access.html",
        connector_kind="portal-rss",
        cadence="giornaliera",
        formats=["HTML", "RSS", "XML", "PDF"],
        capability="Gazzetta UE, normativa e giurisprudenza europea.",
        notes="Motore UE per atti e impatti sovranazionali.",
    ),
    "agenzia_entrate": FonteUfficiale(
        id="agenzia_entrate",
        nome="Agenzia delle Entrate - Fatturazione elettronica",
        motore="professione_forense",
        area="Fatturazione elettronica",
        official_url="https://www.agenziaentrate.gov.it/portale/aree-tematiche/fatturazione-elettronica",
        monitor_url="https://www.agenziaentrate.gov.it/portale/aree-tematiche/fatturazione-elettronica",
        connector_kind="portal-guide",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Portale ufficiale per predisposizione, trasmissione e consultazione delle fatture elettroniche.",
        notes="Rilevante per il collegamento tra parcelle, XML FatturaPA e canali di invio o caricamento.",
    ),
    "fatturapa": FonteUfficiale(
        id="fatturapa",
        nome="FatturaPA - tracciato XML",
        motore="professione_forense",
        area="Fatturazione elettronica",
        official_url="https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf",
        monitor_url="https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf",
        connector_kind="schema-docs",
        cadence="giornaliera",
        formats=["PDF", "XML", "XSD"],
        capability="Tracciato XML ufficiale FPR12/FPA12 e controlli extra-schema.",
        notes="Base tecnica ufficiale per XML FatturaPA, caricamento su SdI e provider cloud.",
    ),
    # ── Banca d'Italia ────────────────────────────────────────────────────────
    "bancaditalia": FonteUfficiale(
        id="bancaditalia",
        nome="Banca d'Italia",
        motore="tassi_finanziari",
        area="Tassi / Finanza",
        official_url="https://www.bancaditalia.it/",
        monitor_url="https://www.bancaditalia.it/compiti/vigilanza/compiti-vigilanza/tegm/",
        connector_kind="portal",
        cadence="trimestrale",
        formats=["HTML", "PDF", "XLS"],
        capability="TEGM e soglie antiusura trimestrali, tasso BCE e tassi di riferimento.",
        notes=(
            "Fonte primaria per: tassi usura (L. 108/1996), tasso BCE per mora 231/2002, "
            "tassi di riferimento bancari. Decreto MEF pubblicato ogni trimestre in G.U."
        ),
    ),
    # ── ISTAT ─────────────────────────────────────────────────────────────────
    "istat": FonteUfficiale(
        id="istat",
        nome="ISTAT - Indici dei prezzi al consumo",
        motore="tassi_finanziari",
        area="Indici / Rivalutazione",
        official_url="https://www.istat.it/",
        monitor_url="https://www.istat.it/notizia/indice-dei-prezzi-per-le-rivalutazioni-monetarie/",
        connector_kind="portal",
        cadence="mensile",
        formats=["HTML", "XLS", "CSV"],
        capability="Indici FOI (locazioni abitative), NIC (rivalutazioni generali) e inflazione.",
        notes=(
            "FOI: adeguamento canoni locazione ex L. 431/1998. "
            "NIC: rivalutazione assegni divorzili, liquidazioni, pensioni. "
            "Comunicato mensile ISTAT intorno al 15 del mese successivo."
        ),
    ),
    # ── Cassa Forense ─────────────────────────────────────────────────────────
    "cassa_forense": FonteUfficiale(
        id="cassa_forense",
        nome="Cassa Forense",
        motore="previdenza_forense",
        area="Previdenza forense",
        official_url="https://www.cassaforense.it/",
        monitor_url="https://www.cassaforense.it/contributi-minimi-obbligatori/",
        connector_kind="portal",
        cadence="annuale",
        formats=["HTML", "PDF"],
        capability="Aliquote e minimali contributi previdenziali avvocati, comunicati annuali.",
        notes=(
            "Contributo soggettivo (% reddito netto), integrativo (% compensi, addebitabile al cliente), "
            "maternita/assistenza (importo fisso). Fonte obbligatoria per preventivi e parcelle."
        ),
    ),
    # ── Corte dei Conti ───────────────────────────────────────────────────────
    "corte_conti": FonteUfficiale(
        id="corte_conti",
        nome="Corte dei Conti",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza contabile",
        official_url="https://www.corteconti.it/",
        monitor_url="https://www.corteconti.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Giurisprudenza contabile, responsabilita erariale, sezioni regionali.",
        notes="Rilevante per fascicoli con enti pubblici, appalti e responsabilita amministrativa.",
    ),
    # ── Ministero del Lavoro ──────────────────────────────────────────────────
    "ministero_lavoro": FonteUfficiale(
        id="ministero_lavoro",
        nome="Ministero del Lavoro e delle Politiche Sociali",
        motore="fonti_ufficiali",
        area="Lavoro / Previdenza",
        official_url="https://www.lavoro.gov.it/",
        monitor_url="https://www.lavoro.gov.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Circolari lavoro, CCNL, tutela minori, collocamento disabili.",
        notes="Utile per fascicoli di lavoro, separazioni con figli, infortuni e previdenza.",
    ),
    # ── ANAC ──────────────────────────────────────────────────────────────────
    "anac": FonteUfficiale(
        id="anac",
        nome="ANAC - Autorita Nazionale Anticorruzione",
        motore="fonti_ufficiali",
        area="Appalti pubblici",
        official_url="https://www.anticorruzione.it/",
        monitor_url="https://www.anticorruzione.it/",
        connector_kind="portal",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Soglie rilevanza europea, bandi tipo, commissioni e codice contratti.",
        notes=(
            "Fonte primaria per D.Lgs. 36/2023 (Codice Contratti Pubblici), soglie aggiornate "
            "ogni 2 anni dalla Commissione europea. Rilevante per studi che assistono in appalti."
        ),
    ),
    # ── Corte EDU / CEDU ─────────────────────────────────────────────────────
    "cedu": FonteUfficiale(
        id="cedu",
        nome="Corte europea dei diritti dell'uomo (CEDU)",
        motore="giurisprudenza_orientamenti",
        area="Giurisprudenza europea",
        official_url="https://www.echr.coe.int/",
        monitor_url="https://hudoc.echr.coe.int/",
        connector_kind="portal-rss",
        cadence="giornaliera",
        formats=["HTML", "PDF"],
        capability="Sentenze CEDU rilevanti per il diritto italiano su equo processo, liberta, privacy.",
        notes=(
            "Ricerca in HUDOC (hudoc.echr.coe.int). Filtrare per 'Italy' come Respondent State. "
            "Rilevante per ricorsi ex art. 6 CEDU, art. 8 (privacy), art. 1 Prot. 1 (proprieta)."
        ),
    ),
}


MOTORI_LEGALI: Dict[str, MotoreLegale] = {
    "fonti_ufficiali": MotoreLegale(
        id="fonti_ufficiali",
        nome="Motore Fonti Ufficiali",
        short_name="Fonti ufficiali",
        descrizione="Raccoglie, verifica e indicizza solo fonti istituzionali con URL, hash e data di acquisizione.",
        output="Catalogo fonti, hash, data pubblicazione, data acquisizione.",
        value="Evita fonti non ufficiali e rende verificabile ogni contenuto monitorato.",
        source_ids=[
            "normattiva", "gazzetta_ufficiale", "pst_giustizia", "pst_servizi_web", "pst_download", "pst_pdp_specifiche",
            "cnf", "registro_mediazione", "cassazione", "merito_civile_bdp", "corte_costituzionale",
            "giustizia_amministrativa", "giustizia_tributaria", "curia", "eur_lex", "agenzia_entrate", "fatturapa",
            "ministero_lavoro", "anac",
        ],
    ),
    "vigenza_versionamento": MotoreLegale(
        id="vigenza_versionamento",
        nome="Motore di Vigenza e Versionamento Normativo",
        short_name="Vigenza normativa",
        descrizione="Separa norma vigente, multivigenza, modifiche, abrogazioni e data del fatto o del deposito.",
        output="Vista per data-fatto, data-deposito e versione norma.",
        value="Riduce il rischio di applicare una norma errata rispetto al tempo rilevante.",
        source_ids=["normattiva", "gazzetta_ufficiale", "eur_lex"],
    ),
    "procedurale_telematico": MotoreLegale(
        id="procedurale_telematico",
        nome="Motore Procedurale Telematico",
        short_name="Telematico",
        descrizione="Isola PCT, PDP, PAT, ReGIndE, pagamenti, XSD, WSDL e regole tecniche.",
        output="Checklist tecniche, alert XSD/WSDL e conformita pre-invio.",
        value="Evita errori di deposito dovuti a specifiche tecniche o aggiornamenti di portale.",
        source_ids=[
            "pst_giustizia",
            "pst_servizi_web",
            "pst_download",
            "pst_pdp_specifiche",
            "pst_xsd_sici",
            "pst_xsd_sigp",
            "pst_xsd_unep",
            "pst_xsd_cassazione",
        ],
    ),
    "professione_forense": MotoreLegale(
        id="professione_forense",
        nome="Motore Professione Forense",
        short_name="Professione forense",
        descrizione="Tiene separati codice deontologico, parametri, equo compenso e obblighi professionali.",
        output="Preventivi, incarichi, alert deontologici e controlli formali.",
        value="Rende coerente il gestionale con compensi, informativa preventiva e deontologia.",
        source_ids=["cnf", "gazzetta_ufficiale", "agenzia_entrate", "fatturapa"],
    ),
    "giurisprudenza_orientamenti": MotoreLegale(
        id="giurisprudenza_orientamenti",
        nome="Motore Giurisprudenza e Orientamenti",
        short_name="Giurisprudenza",
        descrizione="Tiene la giurisprudenza distinta dalla normativa e la collega agli articoli coinvolti.",
        output="Orientamenti, massime, principi di diritto e collegamenti normativi.",
        value="Supporta strategia, confronto orientamenti e aggiornamento ragionato.",
        source_ids=["cassazione", "merito_civile_bdp", "corte_costituzionale", "giustizia_amministrativa", "giustizia_tributaria", "curia", "corte_conti", "cedu"],
    ),
    "monitoraggio_alert": MotoreLegale(
        id="monitoraggio_alert",
        nome="Motore Monitoraggio e Alert",
        short_name="Alert",
        descrizione="Schedula controlli distinti per fonte e genera alert utili, non solo notizie generiche.",
        output="Alert su contenuto modificato, nuovi documenti e nuove note tecniche.",
        value="Trasforma il gestionale in un assistente proattivo invece che in un archivio passivo.",
        source_ids=[
            "normattiva", "gazzetta_ufficiale",
            "pst_giustizia", "pst_servizi_web", "pst_download", "pst_pdp_specifiche",
            "pst_xsd_sici", "pst_xsd_sigp", "pst_xsd_unep", "pst_xsd_cassazione",
            "cnf", "registro_mediazione",
            "cassazione", "merito_civile_bdp", "corte_costituzionale", "giustizia_amministrativa", "giustizia_tributaria", "curia",
            "eur_lex", "bancaditalia", "istat", "cassa_forense", "anac",
        ],
    ),
    "audit_affidabilita": MotoreLegale(
        id="audit_affidabilita",
        nome="Motore Audit e Affidabilita",
        short_name="Audit",
        descrizione="Registra query, fonti, versioni, warning e modello AI per ogni risposta assistita.",
        output="Tracce di audit consultabili e storicizzate.",
        value="Aumenta fiducia interna, debugging e responsabilita operativa.",
        source_ids=[
            "normattiva", "gazzetta_ufficiale",
            "pst_giustizia", "pst_servizi_web", "pst_download", "pst_pdp_specifiche",
            "pst_xsd_sici", "pst_xsd_sigp", "pst_xsd_unep", "pst_xsd_cassazione",
            "cnf", "registro_mediazione",
            "cassazione", "merito_civile_bdp", "corte_costituzionale", "giustizia_amministrativa", "giustizia_tributaria", "curia",
            "eur_lex", "bancaditalia", "istat", "cassa_forense",
        ],
    ),
    # ── Nuovi motori ──────────────────────────────────────────────────────────
    "tassi_finanziari": MotoreLegale(
        id="tassi_finanziari",
        nome="Motore Tassi Finanziari e Rivalutazioni",
        short_name="Tassi / ISTAT",
        descrizione=(
            "Centralizza tassi usura (L. 108/1996), tasso BCE, mora commerciale (D.Lgs. 231/2002), "
            "interessi legali e indici ISTAT FOI/NIC per rivalutazioni e adeguamento canoni."
        ),
        output="Tabelle tassi aggiornate per calcolo interessi, usura, rivalutazione e adeguamento locazioni.",
        value=(
            "Evita errori di calcolo su interessi moratori, soglie usura e rivalutazioni monetarie "
            "con dati sempre verificabili su fonti ufficiali Banca d'Italia e ISTAT."
        ),
        source_ids=["bancaditalia", "istat", "gazzetta_ufficiale"],
    ),
    "previdenza_forense": MotoreLegale(
        id="previdenza_forense",
        nome="Motore Previdenza Forense",
        short_name="Cassa Forense",
        descrizione=(
            "Gestisce aliquote e minimali contributivi Cassa Forense (soggettivo, integrativo, "
            "maternita) con aggiornamento annuale. Integra con parcelle e preventivi."
        ),
        output="Aliquote annuali Cassa Forense, minimali, contributo integrativo addebitabile al cliente.",
        value=(
            "Rende trasparente e corretto il calcolo del contributo integrativo in preventivi e parcelle, "
            "evitando errori su aliquote cambiate e minimali annuali."
        ),
        source_ids=["cassa_forense", "gazzetta_ufficiale", "cnf"],
    ),
}


KEYWORD_TO_ENGINE: Dict[str, List[str]] = {
    "pct": ["procedurale_telematico", "monitoraggio_alert"],
    "pst": ["procedurale_telematico", "monitoraggio_alert"],
    "download pst": ["procedurale_telematico", "monitoraggio_alert"],
    "pdp": ["procedurale_telematico", "monitoraggio_alert"],
    "ppt": ["procedurale_telematico", "monitoraggio_alert"],
    "atti penali": ["procedurale_telematico", "monitoraggio_alert"],
    "pat": ["procedurale_telematico", "monitoraggio_alert"],
    "reginde": ["procedurale_telematico"],
    "xsd": ["procedurale_telematico", "monitoraggio_alert"],
    "wsdl": ["procedurale_telematico", "monitoraggio_alert"],
    "software house": ["procedurale_telematico", "monitoraggio_alert"],
    "servizi web": ["procedurale_telematico", "monitoraggio_alert"],
    "xsd": ["procedurale_telematico", "monitoraggio_alert"],
    "sici": ["procedurale_telematico", "monitoraggio_alert"],
    "sigp": ["procedurale_telematico", "monitoraggio_alert"],
    "unep": ["procedurale_telematico", "monitoraggio_alert"],
    "gazzetta": ["fonti_ufficiali", "vigenza_versionamento"],
    "normattiva": ["fonti_ufficiali", "vigenza_versionamento"],
    "vigenza": ["vigenza_versionamento"],
    "abrog": ["vigenza_versionamento", "monitoraggio_alert"],
    "deontolog": ["professione_forense"],
    "compens": ["professione_forense"],
    "preventiv": ["professione_forense"],
    "tariffario": ["professione_forense"],
    "fattur": ["professione_forense"],
    "fatturapa": ["professione_forense"],
    "sdi": ["professione_forense", "monitoraggio_alert"],
    "cnf": ["professione_forense"],
    "mediazione": ["fonti_ufficiali", "monitoraggio_alert"],
    "organismi di mediazione": ["fonti_ufficiali", "monitoraggio_alert"],
    "adr": ["fonti_ufficiali", "monitoraggio_alert"],
    "cassazione": ["giurisprudenza_orientamenti"],
    "banca dati di merito": ["giurisprudenza_orientamenti"],
    "merito civile": ["giurisprudenza_orientamenti"],
    "corte costituzionale": ["giurisprudenza_orientamenti"],
    "tar": ["giurisprudenza_orientamenti"],
    "consiglio di stato": ["giurisprudenza_orientamenti"],
    "giustizia tributaria": ["giurisprudenza_orientamenti"],
    "curia": ["giurisprudenza_orientamenti"],
    "hudoc": ["giurisprudenza_orientamenti"],
    "sentenza": ["giurisprudenza_orientamenti"],
    "giurisprudenza": ["giurisprudenza_orientamenti"],
    "orientament": ["giurisprudenza_orientamenti"],
    "eur-lex": ["fonti_ufficiali", "vigenza_versionamento"],
    "ue": ["fonti_ufficiali", "vigenza_versionamento"],
    # tassi finanziari
    "usura": ["tassi_finanziari", "monitoraggio_alert"],
    "tasso usura": ["tassi_finanziari", "monitoraggio_alert"],
    "tegm": ["tassi_finanziari"],
    "tasso bce": ["tassi_finanziari"],
    "mora commerciale": ["tassi_finanziari"],
    "interessi moratori": ["tassi_finanziari"],
    "interesse legale": ["tassi_finanziari"],
    "istat": ["tassi_finanziari"],
    "rivalutazione": ["tassi_finanziari"],
    "foi": ["tassi_finanziari"],
    "nic": ["tassi_finanziari"],
    "canone locazione": ["tassi_finanziari"],
    "adeguamento istat": ["tassi_finanziari"],
    "banca d'italia": ["tassi_finanziari"],
    "bancaditalia": ["tassi_finanziari"],
    # previdenza forense
    "cassa forense": ["previdenza_forense"],
    "contributo integrativo": ["previdenza_forense"],
    "contributo soggettivo": ["previdenza_forense"],
    "contributi avvocato": ["previdenza_forense"],
    "previdenza forense": ["previdenza_forense"],
    # appalti pubblici
    "appalto": ["fonti_ufficiali"],
    "appalti": ["fonti_ufficiali"],
    "gara pubblica": ["fonti_ufficiali"],
    "anac": ["fonti_ufficiali"],
    "soglia rilevanza": ["fonti_ufficiali"],
    "codice contratti": ["fonti_ufficiali"],
    # corte dei conti e CEDU
    "corte dei conti": ["giurisprudenza_orientamenti"],
    "responsabilita erariale": ["giurisprudenza_orientamenti"],
    "cedu": ["giurisprudenza_orientamenti"],
    "corte europea": ["giurisprudenza_orientamenti"],
    "equo processo": ["giurisprudenza_orientamenti"],
}


KEYWORD_TO_SOURCE: Dict[str, List[str]] = {
    "normattiva": ["normattiva"],
    "gazzetta": ["gazzetta_ufficiale"],
    "pst": ["pst_giustizia", "pst_servizi_web", "pst_download"],
    "pct": ["pst_giustizia", "pst_servizi_web"],
    "download pst": ["pst_download"],
    "certificati proxy": ["pst_download"],
    "proxy pda": ["pst_download"],
    "dtd": ["pst_download"],
    "pdp": ["pst_pdp_specifiche", "pst_giustizia"],
    "ppt": ["pst_pdp_specifiche", "pst_giustizia"],
    "atti penali": ["pst_pdp_specifiche"],
    "processo penale telematico": ["pst_pdp_specifiche"],
    "portale deposito atti penali": ["pst_pdp_specifiche"],
    "pat": ["pst_giustizia"],
    "reginde": ["pst_giustizia", "pst_download"],
    "servizi web": ["pst_servizi_web"],
    "software house": ["pst_servizi_web"],
    "wsdl": ["pst_servizi_web"],
    "xsd": ["pst_xsd_sici", "pst_xsd_sigp", "pst_xsd_unep", "pst_xsd_cassazione"],
    "sici": ["pst_xsd_sici"],
    "sigp": ["pst_xsd_sigp"],
    "giudice di pace": ["pst_xsd_sigp"],
    "unep": ["pst_xsd_unep"],
    "cassazione xsd": ["pst_xsd_cassazione"],
    "xsd cassazione": ["pst_xsd_cassazione"],
    "cnf": ["cnf"],
    "deontolog": ["cnf"],
    "tariffario": ["cnf", "gazzetta_ufficiale"],
    "fattur": ["agenzia_entrate", "fatturapa"],
    "fatturapa": ["fatturapa"],
    "sdi": ["agenzia_entrate", "fatturapa"],
    "mediazione": ["registro_mediazione"],
    "organismi di mediazione": ["registro_mediazione"],
    "organismo di mediazione": ["registro_mediazione"],
    "cassazione": ["cassazione"],
    "banca dati di merito": ["merito_civile_bdp"],
    "merito civile": ["merito_civile_bdp"],
    "corte costituzionale": ["corte_costituzionale"],
    "tar": ["giustizia_amministrativa"],
    "consiglio di stato": ["giustizia_amministrativa"],
    "giustizia tributaria": ["giustizia_tributaria"],
    "curia": ["curia"],
    "hudoc": ["cedu"],
    "eur-lex": ["eur_lex"],
    "ue": ["eur_lex"],
    # tassi
    "usura": ["bancaditalia"],
    "tasso usura": ["bancaditalia"],
    "tegm": ["bancaditalia"],
    "tasso bce": ["bancaditalia"],
    "banca d'italia": ["bancaditalia"],
    "istat": ["istat"],
    "foi": ["istat"],
    "nic": ["istat"],
    "rivalutazione": ["istat"],
    # previdenza forense
    "cassa forense": ["cassa_forense"],
    "contributo integrativo": ["cassa_forense"],
    "contributo soggettivo": ["cassa_forense"],
    # giurisprudenza
    "corte dei conti": ["corte_conti"],
    "responsabilita erariale": ["corte_conti"],
    "cedu": ["cedu"],
    "corte europea dei diritti": ["cedu"],
    "equo processo": ["cedu"],
    # appalti
    "anac": ["anac"],
    "appalti": ["anac"],
    "soglia rilevanza": ["anac"],
}


FINAL_DEPOSIT_STATES = {"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"}
PENDING_DEPOSIT_STATES = {"INVIATO", "ACCETTATO_PEC", "CONSEGNATO", "WARN_CONTROLLI"}
ERROR_DEPOSIT_STATES = {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA", "ERRORE"}


def motori_per_query(query: str) -> List[str]:
    text = (query or "").lower()
    found: List[str] = []
    for keyword, engine_ids in KEYWORD_TO_ENGINE.items():
        if keyword in text:
            for engine_id in engine_ids:
                if engine_id not in found:
                    found.append(engine_id)
    return found or ["fonti_ufficiali", "audit_affidabilita"]


def fonti_per_query(query: str) -> List[str]:
    text = (query or "").lower()
    found: List[str] = []
    for keyword, source_ids in KEYWORD_TO_SOURCE.items():
        if keyword in text:
            for source_id in source_ids:
                if source_id not in found:
                    found.append(source_id)
    return found or ["normattiva", "pst_giustizia"]


def _extract_pst_servizi_web_metadata(content: bytes, content_type: str, final_url: str) -> Dict[str, str]:
    raw_text = (content or b"").decode("utf-8", errors="ignore")
    normalized = _normalize_textual_payload(content, content_type, final_url).decode("utf-8", errors="ignore")
    text = f"{raw_text}\n{normalized}\n{final_url}"

    detected_version = ""
    detected_reference = ""
    detected_document_url = ""
    detected_package = ""

    title_match = PST_SERVIZI_WEB_TITLE_RE.search(text)
    if title_match:
        detected_version = title_match.group(1).strip()
    if not detected_version:
        pdf_version_match = PST_SERVIZI_WEB_PDF_RE.search(text)
        if pdf_version_match:
            detected_version = pdf_version_match.group(1).strip()

    pdf_url_match = PST_SERVIZI_WEB_PDF_URL_RE.search(raw_text)
    if pdf_url_match:
        detected_document_url = urljoin(final_url, pdf_url_match.group("url").strip())
    elif PST_SERVIZI_WEB_PDF_RE.search(final_url):
        detected_document_url = final_url

    wsdl_match = PST_WSDL_CATALOG_RE.search(text)
    if wsdl_match:
        detected_reference = wsdl_match.group(1).strip()
    wsdl_package_match = re.search(
        r"(?P<url>https?://[^\s\"'>]*A1[_-]WSDL[_-]CATALOG[_-]v[0-9.]+[a-z]?\.zip|/PST/resources/cms/documents/A1[_-]WSDL[_-]CATALOG[_-]v[0-9.]+[a-z]?\.zip)",
        raw_text,
        re.IGNORECASE,
    )
    if wsdl_package_match:
        detected_package = Path(urlparse(urljoin(final_url, wsdl_package_match.group("url"))).path).name

    return {
        "detected_version": detected_version,
        "detected_reference": detected_reference,
        "detected_document_url": detected_document_url,
        "detected_package": detected_package,
    }


def _fetch_secondary_text(url: str, fetch: Optional[Callable[..., Any]], timeout: int) -> tuple[str, str]:
    getter = fetch or requests.get
    kwargs = {
        "headers": {"User-Agent": USER_AGENT},
        "timeout": timeout,
        "allow_redirects": True,
    }
    try:
        response = getter(url, **kwargs)
    except TypeError:
        kwargs.pop("allow_redirects", None)
        response = getter(url, **kwargs)
    final_url = str(getattr(response, "url", url) or url)
    content = bytes(getattr(response, "content", b"") or b"")
    return final_url, content.decode("utf-8", errors="ignore")


def _detect_pst_xsd_status(text: str) -> str:
    normalized = _normalize_label(text)
    if any(_normalize_label(marker) in normalized for marker in PST_XSD_PRODUCTION_MARKERS):
        return "production"
    if any(_normalize_label(marker) in normalized for marker in PST_XSD_PREVIEW_MARKERS):
        return "preview"
    return ""


def _extract_pst_xsd_metadata(
    content: bytes,
    content_type: str,
    final_url: str,
    *,
    channel_key: str,
    request_get: Optional[Callable[..., Any]] = None,
    timeout: int = 15,
) -> Dict[str, str]:
    raw_text = (content or b"").decode("utf-8", errors="ignore")
    try:
        document = lxml_html.fromstring(content or b"")
    except Exception:
        document = None

    channel = get_xsd_channel(channel_key)
    links: list[dict[str, str]] = []
    if document is not None:
        for anchor in document.xpath("//a[@href]"):
            href = urljoin(final_url, anchor.get("href", ""))
            label = _clean_spaces(" ".join(anchor.xpath(".//text()")))
            links.append({"label": label, "url": href})

    package_link = next(
        (
            item
            for item in links
            if item["url"].lower().endswith(".zip")
            and ("xsd" in item["label"].lower() or "xsd" in item["url"].lower())
        ),
        None,
    )
    changelog_link = next(
        (
            item
            for item in links
            if item["url"].lower().endswith(".pdf")
            and (
                "nota modifiche" in item["label"].lower()
                or "schemi xsd" in item["label"].lower()
            )
        ),
        None,
    )
    news_link = next(
        (
            item
            for item in links
            if "contentId=NWS" in item["url"]
            and (
                item["label"].lower() == "news"
                or bool(PST_NEWS_DATE_RE.search(item["label"]))
            )
        ),
        None,
    )
    if news_link is None and channel.status_source_news_url:
        news_link = {"label": channel.status_source_news_date, "url": channel.status_source_news_url}

    package_label = package_link["label"] if package_link else ""
    package_url = package_link["url"] if package_link else channel.package_url
    package_name = Path(urlparse(package_url).path).name if package_url else ""
    package_date = _extract_pst_date(package_label) or channel.package_date

    detected_status = ""
    detected_news_date = ""
    detected_news_url = news_link["url"] if news_link else ""
    if news_link:
        try:
            news_final_url, news_text = _fetch_secondary_text(news_link["url"], request_get, timeout)
            detected_news_url = news_final_url
            detected_status = _detect_pst_xsd_status(news_text)
            detected_news_date = _extract_pst_date(news_link["label"]) or _extract_pst_date(news_text)
        except Exception:
            detected_status = ""
            detected_news_date = _extract_pst_date(news_link["label"])

    return {
        "detected_document_url": package_url,
        "detected_package": package_name or package_label,
        "detected_package_date": package_date,
        "detected_reference": (
            Path(urlparse(changelog_link["url"]).path).name if changelog_link else channel.changelog_name
        ),
        "detected_status": detected_status,
        "detected_news_date": detected_news_date or channel.status_source_news_date,
        "detected_news_url": detected_news_url,
    }


def costruisci_tracker_fascicolo(fascicolo: Any) -> Dict[str, Any]:
    attivita = list(getattr(fascicolo, "attivita", []) or [])
    depositi = list(getattr(fascicolo, "depositi_pct", []) or [])
    stato = getattr(getattr(fascicolo, "stato", None), "value", str(getattr(fascicolo, "stato", "")))

    has_opening = True
    has_activity = bool(attivita or depositi or stato in {"IN_CORSO", "SOSPESO", "DEFINITO", "ARCHIVIATO"})
    has_decision = any(
        getattr(getattr(att, "tipo", None), "value", str(getattr(att, "tipo", "")))
        in {"UDIENZA", "PROVVEDIMENTO", "COMUNICAZIONE_CANCELLERIA", "SENTENZA_EMESSA", "APPELLO"}
        for att in attivita
    ) or any((getattr(dep, "stato", "") or "").upper() in FINAL_DEPOSIT_STATES for dep in depositi)
    has_closure = stato in {"DEFINITO", "ARCHIVIATO"}

    steps = [
        {"id": "apertura", "label": "Apertura pratica", "complete": has_opening},
        {"id": "sviluppo", "label": "Depositi e istruttoria", "complete": has_activity},
        {"id": "decisione", "label": "Udienza / provvedimenti", "complete": has_decision},
        {"id": "chiusura", "label": "Definizione", "complete": has_closure},
    ]
    completed = sum(1 for step in steps if step["complete"])
    current_idx = min(completed, len(steps) - 1)
    percent = int(round((completed / len(steps)) * 100))

    ultima_attivita = getattr(fascicolo, "ultima_attivita", None)
    prossima_scadenza = getattr(fascicolo, "prossima_scadenza", None)
    data_udienza = getattr(fascicolo, "data_prossima_udienza", "") or ""

    last_event = ""
    if ultima_attivita:
        last_event = _clean_spaces(
            f"{getattr(ultima_attivita, 'titolo', 'Attivita processuale')} {getattr(ultima_attivita, 'data', '')}"
        )
    elif depositi:
        ultimo_dep = max(depositi, key=lambda dep: getattr(dep, "timestamp", ""))
        last_event = _clean_spaces(
            f"Deposito {getattr(ultimo_dep, 'tipo_atto', '')} {getattr(ultimo_dep, 'timestamp', '')[:10]}"
        )

    next_event = ""
    if prossima_scadenza:
        next_event = _clean_spaces(
            f"{getattr(prossima_scadenza, 'titolo', 'Scadenza')} {getattr(prossima_scadenza, 'data', '')}"
        )
    elif data_udienza:
        next_event = f"Udienza fissata per {data_udienza}"

    current_label = "Pratica definita" if has_closure else steps[current_idx]["label"]
    return {
        "percent": percent,
        "current_label": current_label,
        "steps": steps,
        "last_event": last_event,
        "next_event": next_event,
        "stato": stato,
    }


def costruisci_tracker_fascicoli(fascicoli: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    trackers: Dict[str, Dict[str, Any]] = {}
    for fascicolo in fascicoli or []:
        fascicolo_id = getattr(fascicolo, "id", "")
        if fascicolo_id:
            trackers[fascicolo_id] = costruisci_tracker_fascicolo(fascicolo)
    return trackers


class GestioneLegalIntelligence:
    def __init__(
        self,
        db_path: str = "./intelligence/legal_intelligence.json",
        timeout: int = 15,
        normative_db_path: Optional[str] = None,
        *,
        postgres_dsn: str = "",
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.postgres_dsn = resolve_runtime_postgres_dsn(postgres_dsn)
        self.normative_db_path = normative_db_path or str(Path(db_path).with_name("tabelle_normative.json"))
        self.normative_tables = GestioneTabelleNormative(self.normative_db_path)
        self._data: Dict[str, Any] = {"monitor_runs": [], "alerts": [], "audit_traces": []}
        self.repository_db_path = derive_legal_intelligence_repository_db_path(self.db_path)
        self.repository_json_path = derive_legal_intelligence_repository_json_path(self.db_path)
        self.repository_sources_json_path = derive_legal_sources_json_path(self.db_path)
        self.repository_engines_json_path = derive_legal_engines_json_path(self.db_path)
        self.repository_keyword_engine_json_path = derive_legal_keyword_engine_json_path(self.db_path)
        self.repository_keyword_source_json_path = derive_legal_keyword_source_json_path(self.db_path)
        self.repository_engine_edges_json_path = derive_legal_engine_edges_json_path(self.db_path)
        self.repository_operational_json_path = derive_legal_operational_json_path(self.db_path)
        self.telematico_repository_db_path = derive_telematico_repository_db_path(self.db_path)
        self.telematico_repository_json_path = derive_telematico_repository_json_path(self.db_path)
        self.telematico_catalog_snapshot_json_path = derive_telematico_catalog_snapshot_json_path(self.db_path)
        self.telematico_methods_json_path = derive_telematico_methods_json_path(self.db_path)
        self.telematico_wsdl_json_path = derive_telematico_wsdl_modules_json_path(self.db_path)
        self.telematico_xsd_json_path = derive_telematico_xsd_channels_json_path(self.db_path)
        self.telematico_catalog_sources_json_path = derive_telematico_catalog_sources_json_path(self.db_path)
        self.telematico_sources_json_path = derive_telematico_sources_json_path(self.db_path)
        self.telematico_capabilities_json_path = derive_telematico_capabilities_json_path(self.db_path)
        self.telematico_rules_json_path = derive_telematico_rules_json_path(self.db_path)
        self.telematico_actions_json_path = derive_telematico_actions_json_path(self.db_path)
        self.telematico_wizard_json_path = derive_telematico_wizard_json_path(self.db_path)
        self.telematico_monitoring_json_path = derive_telematico_monitoring_json_path(self.db_path)
        self._repository = GestioneLegalIntelligenceRepository(
            self.repository_db_path,
            json_path=self.repository_json_path,
            sources_json_path=self.repository_sources_json_path,
            engines_json_path=self.repository_engines_json_path,
            keyword_engine_json_path=self.repository_keyword_engine_json_path,
            keyword_source_json_path=self.repository_keyword_source_json_path,
            engine_edges_json_path=self.repository_engine_edges_json_path,
            operational_json_path=self.repository_operational_json_path,
            postgres_dsn=self.postgres_dsn,
        )
        self._telematico_repository = GestioneTelematicoRepository(
            self.telematico_repository_db_path,
            json_path=self.telematico_repository_json_path,
            snapshot_json_path=self.telematico_catalog_snapshot_json_path,
            methods_json_path=self.telematico_methods_json_path,
            wsdl_json_path=self.telematico_wsdl_json_path,
            xsd_json_path=self.telematico_xsd_json_path,
            catalog_sources_json_path=self.telematico_catalog_sources_json_path,
            sources_json_path=self.telematico_sources_json_path,
            capabilities_json_path=self.telematico_capabilities_json_path,
            rules_json_path=self.telematico_rules_json_path,
            actions_json_path=self.telematico_actions_json_path,
            wizard_json_path=self.telematico_wizard_json_path,
            monitoring_json_path=self.telematico_monitoring_json_path,
            postgres_dsn=self.postgres_dsn,
        )
        self._load()
        self._sync_repository()

    def _load(self) -> None:
        from pct import cache as _cache
        try:
            raw = self._repository.load_runtime_state() if self.postgres_dsn else _cache.load(self.db_path, default={})
            self._data["monitor_runs"] = [
                MonitorRun.from_dict(item).to_dict() for item in (raw.get("monitor_runs") or [])
            ]
            self._data["alerts"] = [
                IntelligenceAlert.from_dict(item).to_dict() for item in (raw.get("alerts") or [])
            ]
            self._data["audit_traces"] = [
                AuditTrace.from_dict(item).to_dict() for item in (raw.get("audit_traces") or [])
            ]
        except Exception:
            self._data = {"monitor_runs": [], "alerts": [], "audit_traces": []}

    def _save(self) -> None:
        from pct import cache as _cache
        if self.postgres_dsn:
            self._repository.save_runtime_state(self._data)
        else:
            # indent=None: file fino a 2.9 MB, non serve leggibilità umana
            _cache.save(self.db_path, self._data, indent=None)
        self._sync_repository()

    def _append_limited(self, key: str, payload: Dict[str, Any], limit: int) -> None:
        self._data.setdefault(key, []).append(payload)
        if len(self._data[key]) > limit:
            self._data[key] = self._data[key][-limit:]

    def _sync_repository(self) -> None:
        source_rows = build_legal_sources_rows(FONTI_UFFICIALI)
        engine_rows = build_legal_engines_rows(MOTORI_LEGALI)
        keyword_engine_rows = build_legal_keyword_engine_rows(KEYWORD_TO_ENGINE)
        keyword_source_rows = build_legal_keyword_source_rows(KEYWORD_TO_SOURCE)
        edge_rows = build_legal_engine_edges_rows(engine_rows, source_rows)
        monitoring_rows = build_legal_monitoring_rows(self._source_status_rows())
        alert_rows = build_legal_alert_rows(self.recent_alerts(limit=MAX_ALERTS))
        audit_rows = build_legal_audit_rows(self.recent_audit_traces(limit=MAX_AUDIT_TRACES))
        operational_rows = build_legal_operational_rules()
        self._repository.synchronize_runtime(
            source_rows=source_rows,
            engine_rows=engine_rows,
            keyword_engine_rows=keyword_engine_rows,
            keyword_source_rows=keyword_source_rows,
            edge_rows=edge_rows,
            monitoring_rows=monitoring_rows,
            alert_rows=alert_rows,
            audit_rows=audit_rows,
            operational_rows=operational_rows,
            export_json=True,
        )
        self._sync_telematico_repository()

    def _sync_telematico_repository(self) -> None:
        snapshot = get_catalog_snapshot()
        catalog_sources = get_catalog_sources()
        source_rows = build_telematico_sources_rows(FONTI_UFFICIALI)
        self._telematico_repository.synchronize_runtime(
            {
                "catalog_snapshot": build_telematico_catalog_snapshot_row(snapshot, catalog_sources),
                "methods": build_telematico_methods_rows(get_official_methods()),
                "wsdl_modules": build_telematico_wsdl_rows(get_wsdl_catalog_modules()),
                "xsd_channels": build_telematico_xsd_rows(get_xsd_channels()),
                "catalog_sources": build_telematico_catalog_source_rows(catalog_sources),
                "sources": source_rows,
                "capabilities": build_telematico_capability_rows(),
                "rules": build_telematico_rule_rows(PST_MAX_BUSTA_MB, PST_MAX_BUSTA_BYTES, PST_FORMAL_ERROR_CODES),
                "actions": build_telematico_action_rows(),
                "wizard_sections": build_telematico_wizard_rows(PST_SEZIONI_WIZARD),
                "monitoring": build_telematico_monitoring_rows(source_rows, list(self._data.get("monitor_runs") or [])),
            }
        )

    def statistiche_repository(self) -> Dict[str, Any]:
        return self._repository.storage_stats()

    def repository_payload(self) -> Dict[str, Any]:
        return self._repository.load_repository_payload()

    def export_legal_repositories(self, base_dir: str | None = None) -> Dict[str, str]:
        return self._repository.export_split_jsons(base_dir)

    def resolve_lex_legal_route(self, question: str) -> Dict[str, Any]:
        return self._repository.resolve_route(question)

    def statistiche_telematico_repository(self) -> Dict[str, Any]:
        return self._telematico_repository.storage_stats()

    def telematico_repository_payload(self) -> Dict[str, Any]:
        return self._telematico_repository.load_repository_payload()

    def export_telematico_repositories(self, base_dir: str | None = None) -> Dict[str, str]:
        return self._telematico_repository.export_split_jsons(base_dir)

    def resolve_telematico_route(self, question: str) -> Dict[str, Any]:
        return self._telematico_repository.resolve_route(question)

    def catalogo_fonti(self) -> List[Dict[str, Any]]:
        return [source.to_dict() for source in FONTI_UFFICIALI.values()]

    def catalogo_motori(self) -> List[Dict[str, Any]]:
        return [engine.to_dict() for engine in MOTORI_LEGALI.values()]

    def _latest_runs(self) -> Dict[str, MonitorRun]:
        latest: Dict[str, MonitorRun] = {}
        for raw in self._data.get("monitor_runs", []):
            run = MonitorRun.from_dict(raw)
            current = latest.get(run.source_id)
            if current is None or run.checked_at >= current.checked_at:
                latest[run.source_id] = run
        return latest

    def _latest_success(self, source_id: str) -> Optional[MonitorRun]:
        latest: Optional[MonitorRun] = None
        for raw in self._data.get("monitor_runs", []):
            if raw.get("source_id") != source_id or raw.get("status") != "ok":
                continue
            run = MonitorRun.from_dict(raw)
            if latest is None or run.checked_at >= latest.checked_at:
                latest = run
        return latest

    def _fetch_response(self, fetch: Callable[..., Any], url: str, **request_kwargs: Any) -> tuple[Any, bool]:
        base_kwargs = {
            "headers": {"User-Agent": USER_AGENT},
            "timeout": self.timeout,
            "allow_redirects": True,
            "verify": True,
        }
        base_kwargs.update(request_kwargs)

        def _call(**extra: Any) -> Any:
            kwargs = dict(base_kwargs)
            kwargs.update(extra)
            try:
                return fetch(url, **kwargs)
            except TypeError:
                kwargs.pop("verify", None)
                return fetch(url, **kwargs)

        try:
            return _call(), False
        except requests.exceptions.SSLError:
            if not _requires_tls_fallback(url):
                raise
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InsecureRequestWarning)
                return _call(verify=False), True

    def _fetch_html_document(
        self,
        url: str,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        response, used_tls_fallback = self._fetch_response(request_get or requests.get, url)
        status_code = int(getattr(response, "status_code", 0) or 0)
        final_url = str(getattr(response, "url", url) or url)
        content = bytes(getattr(response, "content", b"") or b"")[:MAX_MONITOR_BYTES]
        content_type = str((getattr(response, "headers", {}) or {}).get("content-type", "") or "")
        text = content.decode("utf-8", errors="ignore")
        return {
            "status_code": status_code,
            "final_url": final_url,
            "content_type": content_type,
            "content": content,
            "text": text,
            "used_tls_fallback": used_tls_fallback,
            "protection_page": _detect_protection_page(final_url, content),
        }

    def _fetch_html_post_document(
        self,
        url: str,
        *,
        request_post: Callable[..., Any],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        response, used_tls_fallback = self._fetch_response(request_post, url, data=data)
        status_code = int(getattr(response, "status_code", 0) or 0)
        final_url = str(getattr(response, "url", url) or url)
        content = bytes(getattr(response, "content", b"") or b"")[:MAX_MONITOR_BYTES]
        content_type = str((getattr(response, "headers", {}) or {}).get("content-type", "") or "")
        text = content.decode("utf-8", errors="ignore")
        return {
            "status_code": status_code,
            "final_url": final_url,
            "content_type": content_type,
            "content": content,
            "text": text,
            "used_tls_fallback": used_tls_fallback,
            "protection_page": _detect_protection_page(final_url, content),
        }

    def _registry_cell_text(self, node: Any) -> str:
        return _clean_spaces(" ".join(node.xpath(".//text()")))

    def _registro_mediazione_document(self, html_payload: Any) -> Optional[Any]:
        if not html_payload:
            return None
        try:
            if isinstance(html_payload, (bytes, bytearray)):
                return lxml_html.fromstring(bytes(html_payload))
            return lxml_html.fromstring(str(html_payload or ""))
        except Exception:
            return None

    def _registro_mediazione_hidden_fields(self, html_payload: Any) -> Dict[str, str]:
        document = self._registro_mediazione_document(html_payload)
        if document is None:
            return {}
        fields: Dict[str, str] = {}
        for node in document.xpath("//form//input[@type='hidden' and @name] | //input[@type='hidden' and @name]"):
            name = _clean_spaces(node.attrib.get("name") or "")
            if not name:
                continue
            fields[name] = str(node.attrib.get("value") or "")
        return fields

    def _registro_mediazione_page_numbers(self, html_payload: Any) -> List[int]:
        document = self._registro_mediazione_document(html_payload)
        if document is None:
            return [1]
        values: List[int] = []
        select_nodes = document.xpath(
            "//select[@name=$name or @id='acp_content_gvAlbo_ctl13_ddlPages' or contains(@name, 'ddlPages')]",
            name=REGISTRO_MEDIAZIONE_PAGE_SELECT_NAME,
        )
        for select in select_nodes:
            for option in select.xpath(".//option"):
                text = _clean_spaces(option.attrib.get("value") or option.text_content())
                if not text.isdigit():
                    continue
                value = int(text)
                if value not in values:
                    values.append(value)
        if not values:
            values = [1]
        values = sorted(value for value in values if value >= 1)
        return values[:REGISTRO_MEDIAZIONE_MAX_PAGES] or [1]

    def _registro_mediazione_expected_rows(self, html_payload: Any) -> int:
        document = self._registro_mediazione_document(html_payload)
        if document is None:
            return 0
        for candidate in document.xpath("//input[@name='acp_content$tot' or @id='acp_content_tot']/@value"):
            text = _clean_spaces(candidate)
            if text.isdigit():
                return int(text)
        text = _clean_spaces(" ".join(document.xpath("//text()")))
        match = re.search(r"\b([0-9]{2,6})\s+(?:record|risultati|organismi)\b", text, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _fetch_registro_mediazione_page(
        self,
        previous_html: Any,
        page_number: int,
        *,
        request_post: Callable[..., Any],
        url: str = REGISTRO_MEDIAZIONE_DIRECT_URL,
    ) -> Dict[str, Any]:
        payload = self._registro_mediazione_hidden_fields(previous_html)
        payload["__EVENTTARGET"] = REGISTRO_MEDIAZIONE_PAGE_SELECT_NAME
        payload["__EVENTARGUMENT"] = ""
        payload[REGISTRO_MEDIAZIONE_PAGE_SELECT_NAME] = str(page_number)
        return self._fetch_html_post_document(
            url,
            request_post=request_post,
            data=payload,
        )

    def _parse_registro_mediazione_documents(self, documents: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for document in documents:
            for row in self._parse_registro_mediazione_rows((document or {}).get("content")):
                key = str(row.get("record_id") or row.get("registration_number") or row.get("name") or "")
                if not key:
                    continue
                merged[key] = row
        return sorted(
            merged.values(),
            key=lambda item: (
                str(item.get("registration_number") or "").zfill(8),
                str(item.get("name") or ""),
            ),
        )

    def _registro_mediazione_defaults(self) -> Dict[str, Any]:
        table = self.normative_tables.get_table(REGISTRO_MEDIAZIONE_TABLE_ID)
        defaults = dict(table.get("defaults") or {})
        defaults.update(
            {
                "official_info_url": REGISTRO_MEDIAZIONE_INFO_URL,
                "official_registry_url": REGISTRO_MEDIAZIONE_DIRECT_URL,
                "consultation_mode": "Microsoft Edge in modalita compatibilita con Internet Explorer",
            }
        )
        return defaults

    def _extract_registro_mediazione_operational_notice(self, html_payload: Any) -> str:
        if not html_payload:
            return ""
        try:
            document = lxml_html.fromstring(html_payload)
        except Exception:
            return ""
        text = _clean_spaces(" ".join(document.xpath("//text()")))
        normalized = _normalize_label(text)
        if "per motivi tecnici" in normalized and "registro degli organismi di mediazione" in normalized:
            return (
                "Avviso ministeriale: per motivi tecnici il Ministero della Giustizia segnala che, al momento, "
                "non e possibile accedere al Registro degli organismi di mediazione. Per la consultazione il "
                "Ministero indica Microsoft Edge in modalita compatibilita con Internet Explorer."
            )
        return ""

    def _fetch_registro_mediazione_context(
        self,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        defaults = self._registro_mediazione_defaults()
        context: Dict[str, Any] = {"defaults": defaults, "warning": ""}
        try:
            info_document = self._fetch_html_document(
                REGISTRO_MEDIAZIONE_INFO_URL,
                request_get=request_get,
            )
            if info_document["status_code"] < 400:
                context["info_document"] = info_document
                defaults.update(
                    {
                        "last_info_fetch_url": info_document["final_url"],
                        "last_info_hash": _sha256(info_document["content"]),
                    }
                )
                operational_notice = self._extract_registro_mediazione_operational_notice(info_document["content"])
                if operational_notice:
                    defaults["technical_notice"] = operational_notice
                    context["warning"] = operational_notice
        except Exception as exc:
            context["info_warning"] = _truncate(str(exc), 280)
        return context

    def _registry_header_role(self, header: str) -> str:
        normalized = _normalize_label(header)
        if not normalized:
            return ""
        if normalized == "cognome":
            return "surname"
        if normalized == "nome":
            return "first_name"
        if "data nascita" in normalized:
            return "birth_date"
        if "num enti" in normalized or "numero enti" in normalized:
            return "entity_count"
        if "tipo docente" in normalized:
            return "teacher_type"
        if "codice fiscale" in normalized or normalized == "cf" or normalized.endswith(" c f"):
            return "tax_code"
        if "partita iva" in normalized or "p iva" in normalized or normalized == "iva":
            return "vat_number"
        if "cancellato" in normalized or "sospeso" in normalized or "sospensione" in normalized:
            if "data" in normalized:
                return "status_date"
            return "status"
        if "pec" in normalized:
            return "pec"
        if "email" in normalized or "e mail" in normalized:
            return "email"
        if "telefono" in normalized or normalized == "tel" or " fax" in normalized:
            return "phone"
        if "sito" in normalized or "web" in normalized:
            return "website"
        if "indirizzo" in normalized or "via" in normalized or "piazza" in normalized:
            return "address"
        if "provincia" in normalized or normalized.endswith(" prov"):
            return "province"
        if "comune" in normalized or "sede" in normalized or "citta" in normalized:
            return "city"
        if "tipo" in normalized or "natura" in normalized or "pubblic" in normalized or "privat" in normalized:
            return "type"
        if "provvedimento" in normalized or ("data" in normalized and "iscriz" in normalized):
            return "registration_date"
        if "numero" in normalized or normalized.startswith("n ") or "iscriz" in normalized or "registro" in normalized:
            return "registration_number"
        if "organismo" in normalized or "denominazione" in normalized or normalized == "nome":
            return "name"
        return ""

    def _pick_registry_table(self, document: Any) -> tuple[List[str], List[Any]]:
        """Compatibilita: restituisce la singola tabella organismi col miglior punteggio."""
        tables = self._pick_registry_tables(document)
        if not tables:
            return [], []
        headers, rows = tables[0]
        return headers, rows

    def _pick_registry_tables(self, document: Any) -> List[tuple[List[str], List[Any]]]:
        """Estrae tutte le tabelle plausibili del registro organismi mediazione.

        Il portale ministeriale (e gli snapshot HTML salvati dal browser) puo' contenere
        piu' tabelle (paginazione, sezioni, ripetizioni per sede). Ogni tabella con
        almeno 2 header riconosciuti come ruoli (es. denominazione + iscrizione)
        viene considerata utile: cosi' nessun organismo va perso al primo match.
        """
        results: List[tuple[int, List[str], List[Any]]] = []
        for table in document.xpath("//table"):
            header_nodes = table.xpath(".//tr[th][1]/th")
            if not header_nodes:
                first_row = table.xpath(".//tr[1]/td")
                header_nodes = list(first_row or [])
            if not header_nodes:
                continue
            headers = [self._registry_cell_text(node) for node in header_nodes]
            roles = [self._registry_header_role(header) for header in headers]
            score = len([role for role in roles if role])
            data_rows = [
                row
                for row in table.xpath(".//tr[td]")
                if any(self._registry_cell_text(cell) for cell in row.xpath("./td"))
            ]
            if data_rows and headers:
                first_cells = [self._registry_cell_text(node) for node in data_rows[0].xpath("./td")]
                if first_cells == headers:
                    data_rows = data_rows[1:]
            # accetto qualsiasi tabella con almeno 2 ruoli riconosciuti e dati
            if score >= 2 and data_rows:
                results.append((score, headers, data_rows))
        results.sort(key=lambda item: item[0], reverse=True)
        return [(headers, rows) for _, headers, rows in results]

    def _parse_registro_mediazione_rows(self, html_payload: Any) -> List[Dict[str, Any]]:
        if html_payload is None:
            return []
        if isinstance(html_payload, (bytes, bytearray)):
            if not bytes(html_payload).strip():
                return []
            payload = bytes(html_payload)
        else:
            html_text = str(html_payload or "")
            if not html_text.strip():
                return []
            payload = html_text
        document = lxml_html.fromstring(payload)
        tables = self._pick_registry_tables(document)
        if not tables:
            return []
        organisms: List[Dict[str, Any]] = []
        seen_ids = set()
        for headers, rows in tables:
            roles = [self._registry_header_role(header) for header in headers]
            for row in rows:
                cells = [self._registry_cell_text(node) for node in row.xpath("./th|./td")]
                if not cells or len(cells) < 2:
                    continue
                organism = self._build_registry_organism(cells, roles, seen_ids)
                if organism is not None:
                    organisms.append(organism)
        organisms.sort(key=lambda item: (item.get("name", ""), item.get("city", ""), item.get("registration_number", "")))
        return organisms

    def _build_registry_organism(
        self,
        cells: List[str],
        roles: List[str],
        seen_ids: set,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "registration_number": "",
            "name": "",
            "type": "",
            "city": "",
            "province": "",
            "address": "",
            "pec": "",
            "email": "",
            "phone": "",
            "website": "",
            "registration_date": "",
            "tax_code": "",
            "vat_number": "",
            "status": "",
            "status_date": "",
            "is_active": True,
            "surname": "",
            "first_name": "",
            "birth_date": "",
            "entity_count": "",
            "teacher_type": "",
        }
        extra_columns: Dict[str, Any] = {}
        for index, cell in enumerate(cells):
            if not cell:
                continue
            role = roles[index] if index < len(roles) else ""
            if role:
                payload[role] = cell
            else:
                extra_columns[f"column_{index + 1}"] = cell
        if payload["surname"] or payload["first_name"]:
            payload["name"] = _clean_spaces(f"{payload['surname']} {payload['first_name']}")
        if payload["teacher_type"] and not payload["type"]:
            payload["type"] = payload["teacher_type"]
        if not payload["name"]:
            payload["name"] = cells[1] if len(cells) > 1 else cells[0]
        registration_number = payload["registration_number"]
        if registration_number:
            match = re.search(r"\d+", registration_number)
            payload["registration_number"] = match.group(0) if match else registration_number
        if not payload["name"] and not payload["registration_number"]:
            return None
        payload["type"] = _normalize_registry_kind(payload["type"])
        status_raw = _clean_spaces(payload.get("status") or "")
        normalized_status = _normalize_label(status_raw)
        if normalized_status in {"no", "n", "0"}:
            payload["status"] = "attivo"
            payload["is_active"] = True
        elif normalized_status in {"si", "s", "1", "yes"}:
            payload["status"] = "cancellato o sospeso"
            payload["is_active"] = False
        elif "cancell" in normalized_status or "sospes" in normalized_status:
            payload["status"] = status_raw
            payload["is_active"] = False
        elif status_raw:
            payload["status"] = status_raw
            payload["is_active"] = "attiv" in normalized_status
        else:
            payload["status"] = "presente"
            payload["is_active"] = True
        payload["classification"] = payload["type"] or "Organismo di mediazione"
        payload["official"] = True
        payload["source"] = "ministero"
        payload["official_registry_url"] = REGISTRO_MEDIAZIONE_DIRECT_URL
        payload["official_info_url"] = REGISTRO_MEDIAZIONE_INFO_URL
        if extra_columns:
            payload["extra_columns"] = extra_columns
        record_base = payload["registration_number"] or (
            f"{payload['name']}|{payload['tax_code']}|{payload['vat_number']}|"
            f"{payload['birth_date']}|{payload['city']}|{payload['pec']}"
        )
        record_id = _stable_registry_record_id(record_base)
        if record_id in seen_ids:
            return None
        seen_ids.add(record_id)
        payload["record_id"] = record_id
        payload["search_text"] = _clean_spaces(
            " ".join(
                [
                    payload["registration_number"],
                    payload["name"],
                    payload["type"],
                    payload["city"],
                    payload["province"],
                    payload["address"],
                    payload["pec"],
                    payload["email"],
                    payload["website"],
                    payload["tax_code"],
                    payload["vat_number"],
                    payload["status"],
                    payload["surname"],
                    payload["first_name"],
                    payload["birth_date"],
                    payload["entity_count"],
                    payload["teacher_type"],
                ]
            )
        ).lower()
        return payload

    def _store_registro_mediazione_rows(
        self,
        rows: List[Dict[str, Any]],
        *,
        defaults: Dict[str, Any],
        current_time: datetime,
        label: str,
        notes: Optional[List[str]] = None,
        warning: str = "",
        origin: str,
        sync_status: str = "sincronizzata",
    ) -> Dict[str, Any]:
        defaults = dict(defaults or {})
        defaults["row_count"] = len(rows)
        update = self.normative_tables.update_table_rows(
            REGISTRO_MEDIAZIONE_TABLE_ID,
            rows,
            now=current_time,
            published_at=current_time.date().isoformat(),
            effective_from=current_time.date().isoformat(),
            label=label,
            notes=notes or [],
            defaults=defaults,
            sync_status=sync_status,
            warning=warning,
            origin=origin,
            source_changed=True,
        )
        return {
            "ok": True,
            "updated": update.get("updated", False),
            "rows": len(rows),
            "warning": warning,
            "used_cached_rows": False,
            "origin": origin,
        }

    def import_registro_mediazione_snapshot(
        self,
        html_payload: Any,
        *,
        filename: str = "",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        if isinstance(html_payload, (bytes, bytearray)) and len(bytes(html_payload)) > REGISTRO_MEDIAZIONE_IMPORT_MAX_BYTES:
            raise ValueError("Il file HTML supera il limite di 5 MB. Ridurre lo snapshot e riprovare.")
        html_text = ""
        if isinstance(html_payload, (bytes, bytearray)):
            html_text = bytes(html_payload).decode("utf-8", errors="ignore")
        else:
            html_text = str(html_payload or "")
        normalized = _normalize_label(html_text[:4000])
        if "multipart related" in normalized and "content transfer encoding" in normalized:
            raise ValueError("Formato non supportato. Salva la pagina del registro come HTML completo, non come archivio MHTML.")

        rows = self._parse_registro_mediazione_rows(html_payload)
        if not rows:
            raise ValueError(
                "Lo snapshot caricato non contiene una tabella leggibile del registro ministeriale. "
                "Apri il registro in Edge modalita compatibilita IE e salva la pagina come HTML."
            )

        context = self._fetch_registro_mediazione_context()
        defaults = dict(context["defaults"])
        defaults.update(
            {
                "registry_notice": REGISTRO_MEDIAZIONE_NOTICE,
                "data_origin": "manual_snapshot",
                "data_origin_label": "Snapshot HTML ufficiale importato",
                "import_filename": filename,
                "imported_at": _now_iso(current_time),
                "last_successful_sync_at": _now_iso(current_time),
                "last_successful_origin": "manual_snapshot",
                "last_successful_row_count": len(rows),
            }
        )
        warning = context.get("warning", "")
        if warning:
            defaults["technical_notice"] = warning
        result = self._store_registro_mediazione_rows(
            rows,
            defaults=defaults,
            current_time=current_time,
            label=f"Import snapshot registro mediazione {current_time.date().isoformat()}",
            notes=[REGISTRO_MEDIAZIONE_NOTICE, "Dati importati da snapshot HTML ufficiale."],
            warning=warning,
            origin="manual_snapshot",
        )
        result["filename"] = filename
        result["imported"] = True
        return result

    def _fetch_state(
        self,
        *,
        source_id: str,
        label: str,
        official_url: str,
        monitor_url: str,
        monitor_urls: Optional[List[str]] = None,
        latest_hash: str = "",
        fetch: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
        change_detection: str = "content_hash",
    ) -> Dict[str, Any]:
        candidates = []
        for candidate in [monitor_url, *(monitor_urls or [])]:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        current_time = now or datetime.now()
        last_payload: Optional[Dict[str, Any]] = None

        for index, candidate in enumerate(candidates):
            response, used_tls_fallback = self._fetch_response(fetch or requests.get, candidate)
            content = bytes(getattr(response, "content", b"") or b"")[:MAX_MONITOR_BYTES]
            status_code = int(getattr(response, "status_code", 0) or 0)
            headers = getattr(response, "headers", {}) or {}
            content_type = str(headers.get("content-type", "") or "")
            final_url = str(getattr(response, "url", candidate) or candidate)
            status = "ok" if status_code < 400 else "errore"
            comparison_mode = "raw"
            warning = ""
            changed = False
            detected_version = ""
            detected_reference = ""
            detected_document_url = ""
            detected_package = ""
            detected_package_date = ""
            detected_status = ""
            detected_news_date = ""
            detected_news_url = ""

            if status == "ok" and _detect_protection_page(final_url, content):
                comparison_mode = "challenge_guard"
                content_hash = latest_hash or _sha256(b"challenge_guard")
                warning = "Controllo limitato da pagina di protezione applicativa."
            elif change_detection == "availability_only" and status == "ok":
                comparison_mode = "availability_only"
                content_hash = latest_hash or _sha256((official_url or final_url or label).encode("utf-8"))
                changed = False
            else:
                normalized = _normalize_textual_payload(content, content_type, final_url)
                comparison_mode = "normalized_text" if normalized != content else "raw"
                content_hash = _sha256(normalized)
                changed = bool(status == "ok" and latest_hash and latest_hash != content_hash)
                if status != "ok":
                    warning = f"HTTP {status_code}"

            if used_tls_fallback:
                extra = "Verifica TLS ridotta per compatibilita del certificato remoto."
                warning = f"{warning} {extra}".strip()

            if status == "ok" and source_id == "pst_servizi_web":
                metadata = _extract_pst_servizi_web_metadata(content, content_type, final_url)
                detected_version = metadata.get("detected_version", "")
                detected_reference = metadata.get("detected_reference", "")
                detected_document_url = metadata.get("detected_document_url", "")
                detected_package = metadata.get("detected_package", "")
            elif status == "ok" and source_id in PST_XSD_SOURCE_CHANNELS:
                metadata = _extract_pst_xsd_metadata(
                    content,
                    content_type,
                    final_url,
                    channel_key=PST_XSD_SOURCE_CHANNELS[source_id],
                    request_get=fetch,
                    timeout=self.timeout,
                )
                detected_reference = metadata.get("detected_reference", "")
                detected_document_url = metadata.get("detected_document_url", "")
                detected_package = metadata.get("detected_package", "")
                detected_package_date = metadata.get("detected_package_date", "")
                detected_status = metadata.get("detected_status", "")
                detected_news_date = metadata.get("detected_news_date", "")
                detected_news_url = metadata.get("detected_news_url", "")

            notes: List[str] = []
            if comparison_mode == "normalized_text":
                notes.append("confronto testo stabile")
            elif comparison_mode == "challenge_guard":
                notes.append("pagina protetta")
            elif comparison_mode == "availability_only":
                notes.append("controllo disponibilita")
            if used_tls_fallback:
                notes.append("retry TLS compatibile")
            if changed:
                notes.append("contenuto modificato")
            if index > 0 and status == "ok":
                notes.append("fonte alternativa ufficiale")
                extra = "Monitoraggio continuato tramite fonte alternativa ufficiale."
                warning = f"{warning} {extra}".strip()
            if detected_version:
                notes.append(f"versione {detected_version}")
            if detected_reference:
                notes.append(f"WSDL catalog {detected_reference}")
            if detected_package:
                notes.append(f"pacchetto {detected_package}")
            if detected_status:
                notes.append(f"stato {detected_status}")
            summary = f"{label}: HTTP {status_code or 'n/d'} - hash {content_hash[:12]}"
            if notes:
                summary += " - " + " - ".join(notes)

            payload = {
                "id": uuid.uuid4().hex,
                "checked_at": _now_iso(current_time),
                "acquired_at": _now_iso(current_time),
                "official_url": official_url,
                "monitor_url": candidate,
                "final_url": final_url,
                "status": status,
                "status_code": status_code,
                "content_hash": content_hash,
                "content_type": content_type,
                "size_bytes": len(content),
                "changed": changed,
                "comparison_mode": comparison_mode,
                "detected_version": detected_version,
                "detected_reference": detected_reference,
                "detected_document_url": detected_document_url,
                "detected_package": detected_package,
                "detected_package_date": detected_package_date,
                "detected_status": detected_status,
                "detected_news_date": detected_news_date,
                "detected_news_url": detected_news_url,
                "summary": summary,
                "warning": warning,
            }
            last_payload = payload
            if status == "ok":
                return payload

        if last_payload is None:
            raise RuntimeError(f"Impossibile controllare la fonte {label}.")
        return last_payload

    def _freshness_status(self, source: FonteUfficiale, run: Optional[MonitorRun]) -> str:
        if run is None:
            return "mai_controllata"
        if run.status == "errore":
            return "errore"
        checked_at = _parse_iso_date(run.checked_at)
        if checked_at is None:
            return "sconosciuta"
        age = datetime.now() - checked_at
        if source.cadence == "piu-volte-al-giorno":
            return "aggiornata" if age <= timedelta(hours=8) else "stale"
        if source.cadence in {"quotidiana", "giornaliera"}:
            return "aggiornata" if age <= timedelta(days=1, hours=6) else "stale"
        return "aggiornata" if age <= timedelta(days=3) else "stale"

    def _alert_kind_for_source(self, source_id: str) -> str:
        if source_id in {"pst_giustizia", "pst_servizi_web", "pst_download", "pst_pdp_specifiche", *PST_XSD_SOURCE_CHANNELS.keys()}:
            return "nuova_documentazione_tecnica"
        if source_id in {"normattiva", "gazzetta_ufficiale", "eur_lex"}:
            return "norma_o_testo_modificato"
        if source_id == "cnf":
            return "aggiornamento_professione_forense"
        return "nuovo_orientamento_ufficiale"

    def _alert_details_for_source(self, source: FonteUfficiale) -> str:
        if source.id == "pst_giustizia":
            return "Rilevata una variazione nella documentazione tecnica o software house del PST."
        if source.id == "pst_servizi_web":
            return "Rilevata una variazione nella pagina ufficiale della documentazione servizi web del PST."
        if source.id == "pst_download":
            return "Rilevata una variazione nella pagina download ufficiale del PST."
        if source.id == "pst_pdp_specifiche":
            return "Rilevata una variazione nelle specifiche tecniche ufficiali del Portale Deposito Atti Penali."
        if source.id in PST_XSD_SOURCE_CHANNELS:
            return "Rilevata una variazione nel pacchetto XSD o nella news di esercizio del canale telematico."
        if source.id in {"normattiva", "gazzetta_ufficiale", "eur_lex"}:
            return "Rilevata una variazione su una fonte normativa ufficiale da riesaminare."
        if source.id == "cnf":
            return "Rilevata una variazione su fonte ufficiale della professione forense."
        return "Rilevata una variazione su una fonte ufficiale giurisprudenziale."

    def _create_alert(
        self,
        *,
        source_id: str,
        motore_id: str,
        alert_type: str,
        severity: str,
        title: str,
        details: str,
        official_url: str = "",
        related_entity_type: str = "",
        related_entity_id: str = "",
        now: Optional[datetime] = None,
    ) -> IntelligenceAlert:
        fingerprint = (source_id, motore_id, alert_type, title, related_entity_type, related_entity_id)
        for idx in range(len(self._data.get("alerts", [])) - 1, -1, -1):
            existing = IntelligenceAlert.from_dict(self._data["alerts"][idx])
            current_key = (
                existing.source_id,
                existing.motore_id,
                existing.alert_type,
                existing.title,
                existing.related_entity_type,
                existing.related_entity_id,
            )
            if current_key != fingerprint or existing.acknowledged:
                continue
            payload = existing.to_dict()
            payload.update(
                {
                    "created_at": _now_iso(now),
                    "severity": severity,
                    "details": details,
                    "official_url": official_url,
                }
            )
            self._data["alerts"][idx] = payload
            return IntelligenceAlert.from_dict(payload)
        alert = IntelligenceAlert(
            id=uuid.uuid4().hex,
            created_at=_now_iso(now),
            source_id=source_id,
            motore_id=motore_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            details=details,
            official_url=official_url,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self._append_limited("alerts", alert.to_dict(), MAX_ALERTS)
        return alert

    def monitor_source(
        self,
        source_id: str,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        source = FONTI_UFFICIALI[source_id]
        current_time = now or datetime.now()
        latest_ok = self._latest_success(source_id)
        try:
            payload = self._fetch_state(
                source_id=source_id,
                label=source.nome,
                official_url=source.official_url,
                monitor_url=source.monitor_url,
                latest_hash=getattr(latest_ok, "content_hash", ""),
                fetch=request_get,
                now=current_time,
            )
            run = MonitorRun(
                source_id=source_id,
                **payload,
            )
            self._append_limited("monitor_runs", run.to_dict(), MAX_MONITOR_RUNS)
            alerts: List[IntelligenceAlert] = []
            if run.status != "ok":
                alerts.append(
                    self._create_alert(
                        source_id=source_id,
                        motore_id=source.motore,
                        alert_type="fonte_non_raggiungibile",
                        severity="alta",
                        title=f"{source.nome} non raggiungibile",
                        details=f"Il controllo ha restituito HTTP {run.status_code}. Verificare la fonte ufficiale.",
                        official_url=source.official_url,
                        now=current_time,
                    )
                )
            elif run.changed:
                alerts.append(
                    self._create_alert(
                        source_id=source_id,
                        motore_id=source.motore,
                        alert_type=self._alert_kind_for_source(source_id),
                        severity="alta" if source_id == "pst_giustizia" else "media",
                        title=f"{source.nome}: contenuto aggiornato",
                        details=self._alert_details_for_source(source),
                        official_url=source.official_url,
                        now=current_time,
                    )
                )
            if (
                source_id == "pst_servizi_web"
                and run.status == "ok"
                and getattr(run, "detected_version", "")
                and getattr(run, "detected_version", "") != PST_WEB_SERVICES_DOC_VERSION
            ):
                detected_document_url = getattr(run, "detected_document_url", "") or PST_WEB_SERVICES_UPDATE_PAGE_URL
                alerts.append(
                    self._create_alert(
                        source_id=source_id,
                        motore_id=source.motore,
                        alert_type="documentazione_servizi_web_da_aggiornare",
                        severity="alta",
                        title=f"PST servizi web: disponibile versione {run.detected_version}",
                        details=(
                            f"La pagina ufficiale PST espone la versione {run.detected_version} della documentazione servizi web, "
                            f"mentre il catalogo interno e tarato su {PST_WEB_SERVICES_DOC_VERSION}. "
                            "Riallineare catalogo, resolver e validatori tecnici."
                        ),
                        official_url=detected_document_url,
                        now=current_time,
                    )
                )
            if source_id in PST_XSD_SOURCE_CHANNELS and run.status == "ok":
                channel = get_xsd_channel(PST_XSD_SOURCE_CHANNELS[source_id])
                package_mismatch = bool(
                    getattr(run, "detected_package", "")
                    and _normalize_label(getattr(run, "detected_package", "")) != _normalize_label(channel.package_name)
                )
                package_date_mismatch = bool(
                    getattr(run, "detected_package_date", "")
                    and getattr(run, "detected_package_date", "") != channel.package_date
                )
                status_mismatch = bool(
                    getattr(run, "detected_status", "")
                    and getattr(run, "detected_status", "") != channel.status
                )
                if package_mismatch or package_date_mismatch or status_mismatch:
                    official_target = (
                        getattr(run, "detected_news_url", "")
                        or getattr(run, "detected_document_url", "")
                        or source.official_url
                    )
                    alerts.append(
                        self._create_alert(
                            source_id=source_id,
                            motore_id=source.motore,
                            alert_type="xsd_canale_da_aggiornare",
                            severity="alta",
                            title=f"{source.nome}: canale da riallineare",
                            details=(
                                f"Il monitor ufficiale del canale {channel.key} espone "
                                f"{getattr(run, 'detected_package', '') or 'un nuovo pacchetto'}"
                                f"{' in stato ' + getattr(run, 'detected_status', '') if getattr(run, 'detected_status', '') else ''}, "
                                f"mentre il catalogo interno e fermo a {channel.package_name} ({channel.status}). "
                                "Aggiorna i validatori e il redattore del canale dedicato."
                            ),
                            official_url=official_target,
                            now=current_time,
                        )
                    )
            self._save()
            return {"ok": run.status == "ok", "run": run.to_dict(), "alerts": [alert.to_dict() for alert in alerts]}
        except Exception as exc:
            run = MonitorRun(
                id=uuid.uuid4().hex,
                source_id=source_id,
                checked_at=_now_iso(current_time),
                acquired_at=_now_iso(current_time),
                official_url=source.official_url,
                monitor_url=source.monitor_url,
                final_url=source.monitor_url,
                status="errore",
                comparison_mode="raw",
                warning=str(exc),
                summary=f"{source.nome}: errore controllo - {exc}",
            )
            self._append_limited("monitor_runs", run.to_dict(), MAX_MONITOR_RUNS)
            alert = self._create_alert(
                source_id=source_id,
                motore_id=source.motore,
                alert_type="fonte_non_raggiungibile",
                severity="alta",
                title=f"{source.nome}: controllo non riuscito",
                details=_truncate(str(exc), 220),
                official_url=source.official_url,
                now=current_time,
            )
            self._save()
            return {"ok": False, "run": run.to_dict(), "alerts": [alert.to_dict()]}

    def run_monitor_cycle(
        self,
        source_ids: Optional[List[str]] = None,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        results = []
        ok_count = 0
        ids = source_ids or list(FONTI_UFFICIALI.keys())
        for source_id in ids:
            result = self.monitor_source(source_id, request_get=request_get, now=now)
            results.append(result)
            if result.get("ok"):
                ok_count += 1
        sync_report = self.sync_normative_tables(source_ids=ids, request_get=request_get, now=now)
        self.registra_trace_risposta(
            query="Monitoraggio fonti ufficiali",
            user="sistema",
            engine_ids=["fonti_ufficiali", "monitoraggio_alert", "audit_affidabilita"],
            source_ids=ids,
            ai_model="sistema",
            result_summary=(
                f"Controllate {len(ids)} fonti ufficiali: {ok_count} riuscite, "
                f"{len(ids) - ok_count} con criticita; sync tabelle {sync_report.get('updated', 0)} aggiornate."
            ),
            warning="" if ok_count == len(ids) else "Alcune fonti ufficiali richiedono verifica operativa.",
            now=now,
        )
        return {
            "ok": ok_count == len(ids),
            "checked": len(ids),
            "successful": ok_count,
            "failed": len(ids) - ok_count,
            "results": results,
            "normative_sync": sync_report,
        }

    def sync_registro_mediazione_elenco(
        self,
        *,
        request_get: Optional[Callable[..., Any]] = None,
        request_post: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        if request_get is None and request_post is None:
            session = requests.Session()
            request_get = session.get
            request_post = session.post
        context = self._fetch_registro_mediazione_context(request_get=request_get)
        defaults = dict(context["defaults"])
        existing_rows = [dict(row) for row in self.normative_tables.rows(REGISTRO_MEDIAZIONE_TABLE_ID)]
        try:
            registry_sources = [
                ("organismo", "Organismi di mediazione", REGISTRO_MEDIAZIONE_DIRECT_URL),
                ("ente", "Enti per la mediazione", REGISTRO_MEDIAZIONE_ENTI_URL),
                ("formatore", "Formatori per la mediazione", REGISTRO_MEDIAZIONE_FORMATORI_URL),
            ]
            rows: List[Dict[str, Any]] = []
            first_document: Optional[Dict[str, Any]] = None
            source_reports: List[Dict[str, Any]] = []
            total_pages_loaded = 0
            total_pages_available = 0
            total_expected_rows = 0
            for registry_kind, registry_label, registry_url in registry_sources:
                document = self._fetch_html_document(
                    registry_url,
                    request_get=request_get,
                )
                if first_document is None:
                    first_document = document
                if document["status_code"] >= 400:
                    raise RuntimeError(f"{registry_label}: HTTP {document['status_code']}")
                if document["protection_page"]:
                    raise RuntimeError(f"{registry_label}: consultazione protetta o browser compatibile richiesto.")

                documents = [document]
                page_numbers = self._registro_mediazione_page_numbers(document["content"])
                expected_rows = self._registro_mediazione_expected_rows(document["content"])
                previous_html = document["content"]
                if request_post and len(page_numbers) > 1:
                    for page_number in page_numbers[1:]:
                        page_document = self._fetch_registro_mediazione_page(
                            previous_html,
                            page_number,
                            request_post=request_post,
                            url=registry_url,
                        )
                        if int(page_document.get("status_code") or 0) >= 400:
                            raise RuntimeError(f"{registry_label}: HTTP {page_document.get('status_code')} durante la pagina {page_number}.")
                        if page_document.get("protection_page"):
                            raise RuntimeError(f"{registry_label}: la pagina {page_number} richiede browser compatibile.")
                        documents.append(page_document)
                        previous_html = page_document.get("content") or previous_html

                source_rows = self._parse_registro_mediazione_documents(documents)
                for row in source_rows:
                    row["registry_kind"] = registry_kind
                    row["registry_section"] = registry_label
                    row["official_registry_url"] = registry_url
                    row["record_id"] = _stable_registry_record_id(
                        f"{registry_kind}|{row.get('record_id') or row.get('registration_number') or row.get('name')}"
                    )
                    row["search_text"] = _clean_spaces(
                        f"{row.get('search_text', '')} {registry_kind} {registry_label}"
                    ).lower()
                rows.extend(source_rows)
                total_pages_loaded += len(documents)
                total_pages_available += len(page_numbers)
                total_expected_rows += expected_rows
                source_reports.append(
                    {
                        "kind": registry_kind,
                        "label": registry_label,
                        "url": registry_url,
                        "rows": len(source_rows),
                        "pages_loaded": len(documents),
                        "pages_available": len(page_numbers),
                        "expected_rows": expected_rows,
                    }
                )
            if not rows:
                raise RuntimeError("Il registro diretto non ha restituito un elenco strutturato leggibile.")
            document = first_document or {}

            defaults.update(
                {
                    "last_registry_fetch_url": document.get("final_url") or REGISTRO_MEDIAZIONE_DIRECT_URL,
                    "last_registry_hash": _sha256(document.get("content") or b""),
                    "registry_notice": REGISTRO_MEDIAZIONE_NOTICE,
                    "data_origin": "live_registry",
                    "data_origin_label": "Registri ministeriali mediazione",
                    "registry_pages_loaded": total_pages_loaded,
                    "registry_pages_available": total_pages_available,
                    "registry_expected_rows": total_expected_rows,
                    "registry_source_reports": source_reports,
                    "last_successful_sync_at": _now_iso(current_time),
                    "last_successful_origin": "live_registry",
                    "last_successful_row_count": len(rows),
                }
            )
            warning = context.get("warning", "")
            result = self._store_registro_mediazione_rows(
                rows,
                defaults=defaults,
                current_time=current_time,
                label=f"Sync registro mediazione {current_time.date().isoformat()}",
                notes=[REGISTRO_MEDIAZIONE_NOTICE],
                warning=warning,
                origin="live_registry",
            )
            result["final_url"] = document.get("final_url") or REGISTRO_MEDIAZIONE_DIRECT_URL
            result["live_ok"] = True
            result["pages_loaded"] = total_pages_loaded
            result["pages_available"] = total_pages_available
            result["expected_rows"] = total_expected_rows
            result["sources"] = source_reports
            return result
        except Exception as exc:
            raw_warning = _truncate(str(exc), 300)
            warning = context.get("warning") or raw_warning
            defaults.update(
                {
                    "registry_notice": REGISTRO_MEDIAZIONE_NOTICE,
                    "last_registry_attempt_at": _now_iso(current_time),
                    "last_registry_attempt_warning": raw_warning,
                }
            )
            if warning:
                defaults["technical_notice"] = warning
            if existing_rows:
                origin = str(defaults.get("data_origin") or defaults.get("last_successful_origin") or "manual_snapshot")
                origin_label = str(defaults.get("data_origin_label") or "").strip()
                if not origin_label:
                    origin_label = "Snapshot HTML ufficiale importato" if origin == "manual_snapshot" else "Registro diretto ministeriale"
                defaults.update(
                    {
                        "data_origin": origin,
                        "data_origin_label": origin_label,
                        "last_successful_row_count": len(existing_rows),
                    }
                )
                self.normative_tables.update_table_rows(
                    REGISTRO_MEDIAZIONE_TABLE_ID,
                    existing_rows,
                    now=current_time,
                    defaults=defaults,
                    sync_status="sincronizzata",
                    warning=warning,
                    origin=origin,
                    source_changed=True,
                )
                return {
                    "ok": True,
                    "updated": False,
                    "rows": len(existing_rows),
                    "warning": warning,
                    "final_url": REGISTRO_MEDIAZIONE_DIRECT_URL,
                    "used_cached_rows": True,
                    "live_ok": False,
                    "origin": origin,
                }
            self.normative_tables.update_table_rows(
                REGISTRO_MEDIAZIONE_TABLE_ID,
                existing_rows,
                now=current_time,
                defaults=defaults,
                sync_status="fonte_non_raggiungibile",
                warning=warning,
                origin="live_registry",
                source_changed=True,
            )
            return {
                "ok": False,
                "updated": False,
                "rows": len(existing_rows),
                "warning": warning,
                "final_url": REGISTRO_MEDIAZIONE_DIRECT_URL,
                "used_cached_rows": False,
                "live_ok": False,
                "origin": "live_registry",
            }

    def mediazione_registry_snapshot(
        self,
        *,
        q: str = "",
        city: str = "",
        registry_number: str = "",
        organismo_type: str = "",
        status: str = "",
        tax_code: str = "",
        vat_number: str = "",
        has_email: str = "",
        has_website: str = "",
    ) -> Dict[str, Any]:
        metadata_rows = self.normative_tables.rows("registro_organismi_mediazione")
        table = self.normative_tables.get_table(REGISTRO_MEDIAZIONE_TABLE_ID)
        defaults = dict(table.get("defaults") or {})
        metadata = dict(metadata_rows[0]) if metadata_rows else {}
        metadata.update({key: value for key, value in defaults.items() if value not in (None, "")})
        rows = [dict(row) for row in self.normative_tables.rows(REGISTRO_MEDIAZIONE_TABLE_ID)]

        q_norm = _normalize_label(q)
        city_norm = _normalize_label(city)
        reg_norm = _normalize_label(registry_number)
        type_norm = _normalize_label(organismo_type)
        status_norm = _normalize_label(status)
        tax_norm = _normalize_label(tax_code)
        vat_norm = _normalize_label(vat_number)
        has_email_norm = _normalize_label(has_email)
        has_website_norm = _normalize_label(has_website)

        filtered: List[Dict[str, Any]] = []
        for row in rows:
            search_text = _normalize_label(row.get("search_text", "")) or _normalize_label(
                " ".join(
                    [
                        str(row.get("registration_number", "")),
                        str(row.get("name", "")),
                        str(row.get("type", "")),
                        str(row.get("city", "")),
                        str(row.get("province", "")),
                        str(row.get("pec", "")),
                        str(row.get("email", "")),
                        str(row.get("website", "")),
                        str(row.get("tax_code", "")),
                        str(row.get("vat_number", "")),
                        str(row.get("status", "")),
                    ]
                )
            )
            if q_norm and q_norm not in search_text:
                continue
            if city_norm and city_norm not in _normalize_label(f"{row.get('city', '')} {row.get('province', '')}"):
                continue
            if reg_norm and reg_norm not in _normalize_label(str(row.get("registration_number", ""))):
                continue
            if type_norm and type_norm not in _normalize_label(str(row.get("type", ""))):
                continue
            if status_norm and status_norm not in _normalize_label(str(row.get("status", ""))):
                continue
            if tax_norm and tax_norm not in _normalize_label(str(row.get("tax_code", ""))):
                continue
            if vat_norm and vat_norm not in _normalize_label(str(row.get("vat_number", ""))):
                continue
            if has_email_norm in {"1", "true", "vero", "si", "yes"} and not str(row.get("email") or row.get("pec") or "").strip():
                continue
            if has_website_norm in {"1", "true", "vero", "si", "yes"} and not str(row.get("website") or "").strip():
                continue
            filtered.append(row)

        type_options = sorted({row.get("type", "") for row in rows if row.get("type")})
        city_options = sorted({row.get("city", "") for row in rows if row.get("city")})[:200]
        status_options = sorted({row.get("status", "") for row in rows if row.get("status")})
        active_count = len([row for row in rows if bool(row.get("is_active"))])
        inactive_count = len([row for row in rows if not bool(row.get("is_active"))])
        with_email_count = len([row for row in rows if str(row.get("email") or row.get("pec") or "").strip()])
        with_website_count = len([row for row in rows if str(row.get("website") or "").strip()])
        data_origin = str(metadata.get("data_origin") or defaults.get("data_origin") or "")
        data_origin_label = str(
            metadata.get("data_origin_label")
            or defaults.get("data_origin_label")
            or ("Registro diretto ministeriale" if data_origin == "live_registry" else "")
        )
        return {
            "metadata": metadata,
            "table": table,
            "filters": {
                "q": q,
                "city": city,
                "registry_number": registry_number,
                "organismo_type": organismo_type,
                "status": status,
                "tax_code": tax_code,
                "vat_number": vat_number,
                "has_email": has_email,
                "has_website": has_website,
            },
            "rows": filtered,
            "total_rows": len(rows),
            "filtered_rows": len(filtered),
            "type_options": type_options,
            "city_options": city_options,
            "status_options": status_options,
            "stats": {
                "attivi": active_count,
                "cancellati_o_sospesi": inactive_count,
                "con_email": with_email_count,
                "con_sito": with_website_count,
            },
            "has_cached_rows": bool(rows),
            "official_notice": metadata.get("consultation_mode") or REGISTRO_MEDIAZIONE_NOTICE,
            "technical_notice": metadata.get("technical_notice") or table.get("last_warning") or "",
            "data_origin": data_origin,
            "data_origin_label": data_origin_label,
            "imported_at": metadata.get("imported_at", ""),
            "import_filename": metadata.get("import_filename", ""),
            "last_successful_sync_at": metadata.get("last_successful_sync_at", ""),
        }

    def lex_mediazione_registry_sources(self, query: str = "", *, limit: int = 12) -> List[Dict[str, Any]]:
        snapshot = self.mediazione_registry_snapshot(q=query)
        rows = list(snapshot.get("rows") or [])
        if not rows and query:
            rows = list(self.mediazione_registry_snapshot().get("rows") or [])
        terms = [_normalize_label(term) for term in re.findall(r"[A-Za-z0-9]+", query or "") if len(term) >= 3]
        selected: List[Dict[str, Any]] = []
        for row in rows:
            haystack = _normalize_label(row.get("search_text", "")) or _normalize_label(
                " ".join(str(row.get(field, "")) for field in ("registration_number", "name", "type", "city", "province", "tax_code", "vat_number", "status"))
            )
            if terms and not any(term in haystack for term in terms):
                continue
            selected.append(row)
            if len(selected) >= max(1, int(limit or 12)):
                break
        if not selected and rows:
            selected = rows[: max(1, int(limit or 12))]
        sources: List[Dict[str, Any]] = []
        for row in selected:
            territory = " ".join(part for part in (row.get("city"), row.get("province")) if part)
            text = _clean_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        f"Organismo {row.get('name')}",
                        f"Sezione {row.get('registry_section')}",
                        f"numero registro {row.get('registration_number')}",
                        row.get("type"),
                        territory,
                        f"stato {row.get('status')}",
                        f"codice fiscale {row.get('tax_code')}",
                        f"partita IVA {row.get('vat_number')}",
                        f"sito {row.get('website')}",
                        f"email {row.get('email') or row.get('pec')}",
                    )
                    if value
                )
            )
            sources.append(
                {
                    "type": "registro_mediazione",
                    "id": f"registro-mediazione:{row.get('record_id') or row.get('registration_number')}",
                    "title": str(row.get("name") or "Organismo di mediazione"),
                    "excerpt": text,
                    "content": text,
                    "score": 0.9,
                    "authority": "Ministero della Giustizia",
                    "official_url": row.get("official_registry_url") or REGISTRO_MEDIAZIONE_DIRECT_URL,
                    "trust_class": "A",
                    "source_level": 1,
                    "verified_reference": True,
                    "published_at": str(snapshot.get("last_successful_sync_at") or ""),
                    "registration_number": row.get("registration_number") or "",
                    "registry_status": row.get("status") or "",
                    "registry_kind": row.get("registry_kind") or "",
                    "registry_section": row.get("registry_section") or "",
                    "territory": territory,
                    "source_policy_tier": "tier_1",
                    "repository": "normative_tables",
                }
            )
        return sources

    def sync_normative_tables(
        self,
        source_ids: Optional[List[str]] = None,
        request_get: Optional[Callable[..., Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        latest_runs = self._latest_runs()
        source_runs = {
            source_id: run.to_dict()
            for source_id, run in latest_runs.items()
            if not source_ids or source_id in source_ids
        }
        source_checks = self.normative_tables.source_checks()
        source_code_runs: Dict[str, Dict[str, Any]] = {}
        current_time = now or datetime.now()
        for code in self.normative_tables.relevant_source_codes(source_ids):
            source = FONTI_OPERATIVE.get(code)
            if not source:
                continue
            try:
                source_code_runs[code] = self._fetch_state(
                    source_id=code,
                    label=source.title,
                    official_url=source.url,
                    monitor_url=source.url,
                    monitor_urls=list(getattr(source, "monitor_urls", []) or []),
                    latest_hash=str((source_checks.get(code) or {}).get("content_hash", "") or ""),
                    fetch=request_get,
                    now=current_time,
                    change_detection=str(getattr(source, "change_detection", "content_hash") or "content_hash"),
                )
            except Exception as exc:
                source_code_runs[code] = {
                    "id": uuid.uuid4().hex,
                    "checked_at": _now_iso(current_time),
                    "acquired_at": _now_iso(current_time),
                    "official_url": source.url,
                    "monitor_url": source.url,
                    "final_url": source.url,
                    "status": "errore",
                    "status_code": 0,
                    "content_hash": "",
                    "content_type": "",
                    "size_bytes": 0,
                    "changed": False,
                    "comparison_mode": "raw",
                    "summary": f"{source.title}: errore controllo - {exc}",
                    "warning": str(exc),
                }
        report = self.normative_tables.sync_from_canonical(
            source_runs=source_runs,
            source_code_runs=source_code_runs,
            source_ids=source_ids,
            now=now,
        )
        mediazione_sync = None
        watched = set(source_ids or [])
        if not watched or "registro_mediazione" in watched:
            mediazione_sync = self.sync_registro_mediazione_elenco(
                request_get=request_get,
                now=current_time,
            )
        alerts: List[Dict[str, Any]] = []
        for table in report.get("tables", []):
            if table.get("updated"):
                alerts.append(
                    self._create_alert(
                        source_id="normattiva",
                        motore_id="vigenza_versionamento",
                        alert_type="tabella_normativa_aggiornata",
                        severity="media",
                        title=f"Tabella normativa sincronizzata: {table.get('title', table.get('id', ''))}",
                        details="Le tabelle normative del gestionale sono state riallineate al catalogo ufficiale interno.",
                        related_entity_type="normative_table",
                        related_entity_id=table.get("id", ""),
                        now=current_time,
                    ).to_dict()
                )
            elif table.get("sync_status") == "verifica_richiesta":
                alerts.append(
                    self._create_alert(
                        source_id="gazzetta_ufficiale",
                        motore_id="monitoraggio_alert",
                        alert_type="tabella_normativa_da_validare",
                        severity="alta",
                        title=f"Verifica richiesta: {table.get('title', table.get('id', ''))}",
                        details="La fonte ufficiale e cambiata, ma la tabella normativa non ha ancora una variazione strutturata automatica.",
                        related_entity_type="normative_table",
                        related_entity_id=table.get("id", ""),
                        now=current_time,
                    ).to_dict()
                )
        if mediazione_sync:
            if mediazione_sync.get("ok") and not mediazione_sync.get("used_cached_rows"):
                alerts.append(
                    self._create_alert(
                        source_id="registro_mediazione",
                        motore_id="fonti_ufficiali",
                        alert_type="registro_mediazione_sincronizzato",
                        severity="media",
                        title="Registro organismi di mediazione sincronizzato",
                        details=f"Elenco interno aggiornato con {mediazione_sync.get('rows', 0)} organismi.",
                        related_entity_type="normative_table",
                        related_entity_id=REGISTRO_MEDIAZIONE_TABLE_ID,
                        official_url=REGISTRO_MEDIAZIONE_INFO_URL,
                        now=current_time,
                    ).to_dict()
                )
            elif mediazione_sync.get("used_cached_rows"):
                origin = str(mediazione_sync.get("origin") or "manual_snapshot")
                origin_label = "snapshot ufficiale" if origin == "manual_snapshot" else "cache interna"
                alerts.append(
                    self._create_alert(
                        source_id="registro_mediazione",
                        motore_id="monitoraggio_alert",
                        alert_type="registro_mediazione_cache_utilizzata",
                        severity="media",
                        title="Registro mediazione non raggiungibile: uso cache",
                        details=(
                            f"Il registro diretto ministeriale non e stato interrogabile. "
                            f"Il gestionale continua a mostrare {mediazione_sync.get('rows', 0)} organismi "
                            f"dalla {origin_label}. {mediazione_sync.get('warning', REGISTRO_MEDIAZIONE_NOTICE)}"
                        ),
                        related_entity_type="normative_table",
                        related_entity_id=REGISTRO_MEDIAZIONE_TABLE_ID,
                        official_url=REGISTRO_MEDIAZIONE_INFO_URL,
                        now=current_time,
                    ).to_dict()
                )
            else:
                alerts.append(
                    self._create_alert(
                        source_id="registro_mediazione",
                        motore_id="monitoraggio_alert",
                        alert_type="registro_mediazione_da_verificare",
                        severity="alta",
                        title="Registro organismi di mediazione da verificare",
                        details=mediazione_sync.get("warning", REGISTRO_MEDIAZIONE_NOTICE),
                        related_entity_type="normative_table",
                        related_entity_id=REGISTRO_MEDIAZIONE_TABLE_ID,
                        official_url=REGISTRO_MEDIAZIONE_INFO_URL,
                        now=current_time,
                    ).to_dict()
                )
        if alerts:
            self._save()
        self.registra_trace_risposta(
            query="Sincronizzazione tabelle normative",
            user="sistema",
            engine_ids=["vigenza_versionamento", "monitoraggio_alert", "audit_affidabilita"],
            source_ids=sorted(set(source_ids or source_runs.keys() or ["normattiva", "gazzetta_ufficiale"])),
            ai_model="sistema",
            result_summary=(
                f"Tabelle processate: {report.get('processed_tables', 0)}, "
                f"aggiornate: {report.get('updated', 0)}, da verificare: {report.get('review_required', 0)}."
            ),
            warning="" if not report.get("review_required") else "Sono presenti tabelle normative da verificare.",
            now=current_time,
        )
        report["alerts"] = alerts
        if mediazione_sync is not None:
            report["mediazione_registry"] = mediazione_sync
        return report

    def _alert_is_resolved(self, alert: IntelligenceAlert, latest_runs: Dict[str, MonitorRun]) -> bool:
        if alert.alert_type == "fonte_non_raggiungibile":
            latest = latest_runs.get(alert.source_id)
            return bool(latest and latest.status == "ok")
        if alert.related_entity_type == "normative_table" and alert.related_entity_id:
            try:
                table = self.normative_tables.get_table(alert.related_entity_id)
            except KeyError:
                return False
            if alert.alert_type == "tabella_normativa_da_validare":
                return table.get("sync_status") != "verifica_richiesta"
        return False

    def registra_trace_risposta(
        self,
        *,
        query: str,
        user: str = "",
        engine_ids: Optional[List[str]] = None,
        source_ids: Optional[List[str]] = None,
        ai_model: str = "",
        result_summary: str = "",
        warning: str = "",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        engine_ids = engine_ids or motori_per_query(query)
        source_ids = source_ids or fonti_per_query(query)
        latest_runs = self._latest_runs()
        snapshots: List[Dict[str, str]] = []
        for source_id in source_ids:
            source = FONTI_UFFICIALI.get(source_id)
            run = latest_runs.get(source_id)
            snapshots.append(
                {
                    "source_id": source_id,
                    "source_name": source.nome if source else source_id,
                    "official_url": source.official_url if source else "",
                    "checked_at": getattr(run, "checked_at", ""),
                    "acquired_at": getattr(run, "acquired_at", ""),
                    "content_hash": getattr(run, "content_hash", ""),
                }
            )
        trace = AuditTrace(
            id=uuid.uuid4().hex,
            created_at=_now_iso(now),
            query=_truncate(query, 600),
            user=user,
            engine_ids=engine_ids,
            source_ids=source_ids,
            source_snapshots=snapshots,
            ai_model=ai_model,
            result_summary=_truncate(result_summary, 400),
            warning=_truncate(warning, 300),
        )
        self._append_limited("audit_traces", trace.to_dict(), MAX_AUDIT_TRACES)
        self._save()
        return trace.to_dict()

    def recent_alerts(self, limit: int = 12) -> List[Dict[str, Any]]:
        alerts = [IntelligenceAlert.from_dict(raw) for raw in self._data.get("alerts", [])]
        alerts.sort(key=lambda item: (item.created_at, _severity_rank(item.severity)), reverse=True)
        latest_runs = self._latest_runs()
        rows: List[Dict[str, Any]] = []
        seen = set()
        for alert in alerts:
            if self._alert_is_resolved(alert, latest_runs):
                continue
            key = (
                alert.source_id,
                alert.motore_id,
                alert.alert_type,
                alert.title,
                alert.related_entity_type,
                alert.related_entity_id,
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(alert.to_dict())
            if len(rows) >= limit:
                break
        return rows

    def recent_audit_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        traces = [AuditTrace.from_dict(raw) for raw in self._data.get("audit_traces", [])]
        traces.sort(key=lambda item: item.created_at, reverse=True)
        return [trace.to_dict() for trace in traces[:limit]]

    def _source_status_rows(self) -> List[Dict[str, Any]]:
        latest_runs = self._latest_runs()
        rows: List[Dict[str, Any]] = []
        for source in FONTI_UFFICIALI.values():
            run = latest_runs.get(source.id)
            rows.append(
                {
                    "id": source.id,
                    "nome": source.nome,
                    "area": source.area,
                    "cadence": source.cadence,
                    "official_url": source.official_url,
                    "monitor_url": source.monitor_url,
                    "connector_kind": source.connector_kind,
                    "formats": source.formats,
                    "freshness": self._freshness_status(source, run),
                    "last_check": getattr(run, "checked_at", ""),
                    "status": getattr(run, "status", "mai_controllata"),
                    "status_code": getattr(run, "status_code", 0),
                    "changed": bool(getattr(run, "changed", False)),
                    "detected_version": getattr(run, "detected_version", ""),
                    "detected_reference": getattr(run, "detected_reference", ""),
                    "detected_document_url": getattr(run, "detected_document_url", ""),
                    "detected_package": getattr(run, "detected_package", ""),
                    "detected_package_date": getattr(run, "detected_package_date", ""),
                    "detected_status": getattr(run, "detected_status", ""),
                    "detected_news_date": getattr(run, "detected_news_date", ""),
                    "detected_news_url": getattr(run, "detected_news_url", ""),
                    "summary": getattr(run, "summary", "Nessun controllo eseguito."),
                    "warning": getattr(run, "warning", ""),
                }
            )
        rows.sort(key=lambda item: (item["freshness"] != "aggiornata", item["nome"]))
        return rows

    def _engine_cards(self, source_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        status_by_source = {row["id"]: row for row in source_rows}
        cards: List[Dict[str, Any]] = []
        for engine in MOTORI_LEGALI.values():
            covered = 0
            fresh = 0
            for source_id in engine.source_ids:
                row = status_by_source.get(source_id)
                if not row:
                    continue
                if row["status"] == "ok":
                    covered += 1
                if row["freshness"] == "aggiornata":
                    fresh += 1
            total = max(1, len(engine.source_ids))
            badge = "operativo" if fresh == total else ("parziale" if covered else "da_alimentare")
            cards.append(
                {
                    "id": engine.id,
                    "nome": engine.nome,
                    "short_name": engine.short_name,
                    "descrizione": engine.descrizione,
                    "output": engine.output,
                    "value": engine.value,
                    "badge": badge,
                    "coverage": covered,
                    "fresh": fresh,
                    "total_sources": total,
                }
            )
        return cards

    def _derived_alerts(self, fascicoli: Iterable[Any], scadenze: Iterable[Any], portali: Optional[Iterable[Any]] = None) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        for fascicolo in fascicoli or []:
            titolo = getattr(fascicolo, "titolo", "Fascicolo")
            fascicolo_id = getattr(fascicolo, "id", "")
            for deposito in getattr(fascicolo, "depositi_pct", []) or []:
                stato = (getattr(deposito, "stato", "") or "").upper()
                tipo_atto = getattr(deposito, "tipo_atto", "") or "Deposito"
                if stato in ERROR_DEPOSIT_STATES:
                    alerts.append({"severity": "critica", "title": f"{titolo}: deposito da verificare", "details": f"{tipo_atto} in stato {stato}. Serve intervento operativo.", "related_entity_type": "fascicolo", "related_entity_id": fascicolo_id, "motore_id": "procedurale_telematico"})
                    break
                if stato in PENDING_DEPOSIT_STATES:
                    alerts.append({"severity": "media", "title": f"{titolo}: deposito in attesa", "details": f"{tipo_atto} fermo in stato {stato}. Monitorare le ricevute.", "related_entity_type": "fascicolo", "related_entity_id": fascicolo_id, "motore_id": "monitoraggio_alert"})
                    break

        today = date.today()
        for scadenza in scadenze or []:
            stato = getattr(getattr(scadenza, "stato", None), "value", str(getattr(scadenza, "stato", "")))
            data_scadenza = getattr(scadenza, "scadenza", None)
            if stato != "APERTO" or not hasattr(data_scadenza, "strftime"):
                continue
            giorni = (data_scadenza - today).days
            if giorni <= 3:
                priorita = getattr(getattr(scadenza, "priorita", None), "value", "")
                severity = "critica" if priorita == "CRITICA" or giorni < 0 else "alta"
                alerts.append({"severity": severity, "title": f"Scadenza ravvicinata: {getattr(scadenza, 'titolo', 'Scadenza')}", "details": f"Scade il {data_scadenza.strftime('%d/%m/%Y')} - priorita {priorita or 'N/D'}.", "related_entity_type": "scadenza", "related_entity_id": getattr(scadenza, "id", ""), "motore_id": "monitoraggio_alert"})

        for portale in portali or []:
            if getattr(portale, "is_attivo", False) and not getattr(portale, "privacy_firmata", False):
                alerts.append({"severity": "media", "title": "Portale cliente con privacy non firmata", "details": "Il cliente ha accesso attivo ma il consenso privacy risulta ancora mancante.", "related_entity_type": "cliente", "related_entity_id": getattr(portale, "id_cliente", ""), "motore_id": "audit_affidabilita"})

        alerts.sort(key=lambda item: _severity_rank(item["severity"]), reverse=True)
        return alerts[:10]

    def _competitive_advantages(self, fascicoli: Iterable[Any], portali: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
        fascicoli = list(fascicoli or [])
        portali = list(portali or [])
        with_portal = sum(1 for portale in portali if getattr(portale, "is_attivo", False))
        with_pending = sum(1 for fascicolo in fascicoli if any((getattr(dep, "stato", "") or "").upper() in PENDING_DEPOSIT_STATES for dep in getattr(fascicolo, "depositi_pct", []) or []))
        closed = sum(1 for fascicolo in fascicoli if getattr(getattr(fascicolo, "stato", None), "value", str(getattr(fascicolo, "stato", ""))) in {"DEFINITO", "ARCHIVIATO"})
        return [
            {"title": "Sentinella scadenze e depositi", "value": with_pending, "description": "Fascicoli con deposito ancora in attesa o da monitorare.", "icon": "bi-bell"},
            {"title": "Trasparenza cliente", "value": with_portal, "description": "Clienti con portale attivo e tracker pratica disponibile.", "icon": "bi-people"},
            {"title": "Pratiche definite", "value": closed, "description": "Base utile per analytics, benchmark interni e modelli predittivi futuri.", "icon": "bi-graph-up-arrow"},
        ]

    def build_dashboard_snapshot(
        self,
        *,
        fascicoli: Iterable[Any],
        clienti: Iterable[Any],
        appuntamenti: Iterable[Any],
        scadenze: Iterable[Any],
        portali: Optional[Iterable[Any]] = None,
    ) -> Dict[str, Any]:
        fascicoli = list(fascicoli or [])
        clienti = list(clienti or [])
        appuntamenti = list(appuntamenti or [])
        scadenze = list(scadenze or [])
        source_rows = self._source_status_rows()
        stored_alerts = self.recent_alerts(limit=8)
        derived_alerts = self._derived_alerts(fascicoli=fascicoli, scadenze=scadenze, portali=portali)
        normative_snapshot = self.normative_tables.snapshot()
        mediazione_snapshot = self.mediazione_registry_snapshot()
        return {
            "headline": {
                "motori_attivi": len(MOTORI_LEGALI),
                "fonti_monitorate": len(source_rows),
                "fonti_aggiornate": sum(1 for row in source_rows if row["freshness"] == "aggiornata"),
                "fonti_da_rivedere": sum(1 for row in source_rows if row["freshness"] != "aggiornata"),
                "alert_totali": len(stored_alerts) + len(derived_alerts),
                "audit_recenti": len(self.recent_audit_traces(limit=8)),
                "tabelle_normative": normative_snapshot["totali"],
                "riferimenti_normativi": normative_snapshot.get("riferimenti_normativi_totali", 0),
                "tabelle_da_validare": normative_snapshot["verifica_richiesta"],
                "fascicoli": len(fascicoli),
                "clienti": len(clienti),
                "appuntamenti": len(appuntamenti),
            },
            "source_rows": source_rows,
            "engine_cards": self._engine_cards(source_rows),
            "stored_alerts": stored_alerts,
            "derived_alerts": derived_alerts,
            "recent_audits": self.recent_audit_traces(limit=8),
            "competitive_advantages": self._competitive_advantages(fascicoli, portali),
            "trackers": costruisci_tracker_fascicoli(fascicoli),
            "normative_tables": normative_snapshot,
            "mediazione_registry": mediazione_snapshot,
        }
