from __future__ import annotations

import hashlib
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

from pct.normative_tables import FONTI_OPERATIVE, GestioneTabelleNormative
from pct.pst_catalog import (
    PST_WEB_SERVICES_DOC_PAGE_URL,
    PST_WEB_SERVICES_DOC_URL,
    PST_WEB_SERVICES_DOC_VERSION,
    PST_WEB_SERVICES_UPDATE_PAGE_URL,
    PST_WEB_SERVICES_WSDL_CATALOG_VERSION,
)

USER_AGENT = "HACS-Legal-Intelligence/1.0 (+https://pst.giustizia.it)"
MAX_MONITOR_BYTES = 512_000
MAX_MONITOR_RUNS = 600
MAX_ALERTS = 400
MAX_AUDIT_TRACES = 500
REGISTRO_MEDIAZIONE_INFO_URL = "https://www.giustizia.it/giustizia/it/mg_3_4_15.page"
REGISTRO_MEDIAZIONE_DIRECT_URL = "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"
REGISTRO_MEDIAZIONE_TABLE_ID = "organismi_mediazione_elenco"
REGISTRO_MEDIAZIONE_IMPORT_MAX_BYTES = 5 * 1024 * 1024
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
    r"A1[_-]WSDL[_-]CATALOG[_-]v([0-9.]+)\.zip",
    re.IGNORECASE,
)


def _now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).replace(microsecond=0).isoformat()


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate(value: str, limit: int = 220) -> str:
    value = _clean_spaces(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def _parse_iso_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


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
        official_url="https://pst.giustizia.it/",
        monitor_url="https://pst.giustizia.it/PST/resources/cms/documents/Note_per_le_software_house_versioni_aggiornate_1.pdf",
        connector_kind="portal-docs",
        cadence="piu-volte-al-giorno",
        formats=["HTML", "PDF", "WSDL", "XSD"],
        capability="Documentazione software house, servizi web e note tecniche.",
        notes="Fonte primaria per XSD, WSDL, ReGIndE, pagamenti e consultazione registri.",
    ),
    "pst_servizi_web": FonteUfficiale(
        id="pst_servizi_web",
        nome="PST - documentazione servizi web",
        motore="procedurale_telematico",
        area="Telematico / servizi web",
        official_url=PST_WEB_SERVICES_DOC_PAGE_URL,
        monitor_url=PST_WEB_SERVICES_DOC_PAGE_URL,
        connector_kind="portal-docs",
        cadence="giornaliera",
        formats=["HTML", "PDF", "ZIP", "WSDL"],
        capability="Monitora la versione pubblicata della documentazione servizi web per software house e del catalogo WSDL allegato.",
        notes=(
            f"La pagina documentazione PST espone attualmente la documentazione servizi web versione {PST_WEB_SERVICES_DOC_VERSION} "
            f"con PDF dedicato {PST_WEB_SERVICES_DOC_URL}."
        ),
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
        nome="Agenzia delle Entrate - Fatture e Corrispettivi",
        motore="professione_forense",
        area="Fatturazione elettronica",
        official_url="https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html",
        monitor_url="https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html",
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
}


MOTORI_LEGALI: Dict[str, MotoreLegale] = {
    "fonti_ufficiali": MotoreLegale(
        id="fonti_ufficiali",
        nome="Motore Fonti Ufficiali",
        short_name="Fonti ufficiali",
        descrizione="Raccoglie, verifica e indicizza solo fonti istituzionali con URL, hash e data di acquisizione.",
        output="Catalogo fonti, hash, data pubblicazione, data acquisizione.",
        value="Evita fonti non ufficiali e rende verificabile ogni contenuto monitorato.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "pst_servizi_web", "cnf", "registro_mediazione", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex", "agenzia_entrate", "fatturapa"],
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
        source_ids=["pst_giustizia", "pst_servizi_web"],
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
        source_ids=["cassazione", "corte_costituzionale", "giustizia_amministrativa"],
    ),
    "monitoraggio_alert": MotoreLegale(
        id="monitoraggio_alert",
        nome="Motore Monitoraggio e Alert",
        short_name="Alert",
        descrizione="Schedula controlli distinti per fonte e genera alert utili, non solo notizie generiche.",
        output="Alert su contenuto modificato, nuovi documenti e nuove note tecniche.",
        value="Trasforma il gestionale in un assistente proattivo invece che in un archivio passivo.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "pst_servizi_web", "cnf", "registro_mediazione", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex"],
    ),
    "audit_affidabilita": MotoreLegale(
        id="audit_affidabilita",
        nome="Motore Audit e Affidabilita",
        short_name="Audit",
        descrizione="Registra query, fonti, versioni, warning e modello AI per ogni risposta assistita.",
        output="Tracce di audit consultabili e storicizzate.",
        value="Aumenta fiducia interna, debugging e responsabilita operativa.",
        source_ids=["normattiva", "gazzetta_ufficiale", "pst_giustizia", "pst_servizi_web", "cnf", "registro_mediazione", "cassazione", "corte_costituzionale", "giustizia_amministrativa", "eur_lex"],
    ),
}


KEYWORD_TO_ENGINE: Dict[str, List[str]] = {
    "pct": ["procedurale_telematico", "monitoraggio_alert"],
    "pst": ["procedurale_telematico", "monitoraggio_alert"],
    "pdp": ["procedurale_telematico", "monitoraggio_alert"],
    "pat": ["procedurale_telematico", "monitoraggio_alert"],
    "reginde": ["procedurale_telematico"],
    "xsd": ["procedurale_telematico", "monitoraggio_alert"],
    "wsdl": ["procedurale_telematico", "monitoraggio_alert"],
    "software house": ["procedurale_telematico", "monitoraggio_alert"],
    "servizi web": ["procedurale_telematico", "monitoraggio_alert"],
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
    "corte costituzionale": ["giurisprudenza_orientamenti"],
    "tar": ["giurisprudenza_orientamenti"],
    "consiglio di stato": ["giurisprudenza_orientamenti"],
    "sentenza": ["giurisprudenza_orientamenti"],
    "giurisprudenza": ["giurisprudenza_orientamenti"],
    "orientament": ["giurisprudenza_orientamenti"],
    "eur-lex": ["fonti_ufficiali", "vigenza_versionamento"],
    "ue": ["fonti_ufficiali", "vigenza_versionamento"],
}


KEYWORD_TO_SOURCE: Dict[str, List[str]] = {
    "normattiva": ["normattiva"],
    "gazzetta": ["gazzetta_ufficiale"],
    "pst": ["pst_giustizia"],
    "pct": ["pst_giustizia"],
    "pdp": ["pst_giustizia"],
    "pat": ["pst_giustizia"],
    "reginde": ["pst_giustizia"],
    "servizi web": ["pst_servizi_web"],
    "software house": ["pst_servizi_web"],
    "wsdl": ["pst_servizi_web"],
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
    "corte costituzionale": ["corte_costituzionale"],
    "tar": ["giustizia_amministrativa"],
    "consiglio di stato": ["giustizia_amministrativa"],
    "eur-lex": ["eur_lex"],
    "ue": ["eur_lex"],
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

    return {
        "detected_version": detected_version,
        "detected_reference": detected_reference,
        "detected_document_url": detected_document_url,
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
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.normative_db_path = normative_db_path or str(Path(db_path).with_name("tabelle_normative.json"))
        self.normative_tables = GestioneTabelleNormative(self.normative_db_path)
        self._data: Dict[str, Any] = {"monitor_runs": [], "alerts": [], "audit_traces": []}
        self._load()

    def _load(self) -> None:
        path = Path(self.db_path)
        if not path.exists():
            return
        try:
            with path.open(encoding="utf-8") as fh:
                raw = json.load(fh)
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
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)

    def _append_limited(self, key: str, payload: Dict[str, Any], limit: int) -> None:
        self._data.setdefault(key, []).append(payload)
        if len(self._data[key]) > limit:
            self._data[key] = self._data[key][-limit:]

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

    def _fetch_response(self, fetch: Callable[..., Any], url: str) -> tuple[Any, bool]:
        base_kwargs = {
            "headers": {"User-Agent": USER_AGENT},
            "timeout": self.timeout,
            "allow_redirects": True,
            "verify": True,
        }

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

    def _registry_cell_text(self, node: Any) -> str:
        return _clean_spaces(" ".join(node.xpath(".//text()")))

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
        best_headers: List[str] = []
        best_rows: List[Any] = []
        best_score = -1
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
            data_rows = [row for row in table.xpath(".//tr[td]") if any(self._registry_cell_text(cell) for cell in row.xpath("./td"))]
            if data_rows and headers:
                first_cells = [self._registry_cell_text(node) for node in data_rows[0].xpath("./td")]
                if first_cells == headers:
                    data_rows = data_rows[1:]
            if score > best_score and data_rows:
                best_score = score
                best_headers = headers
                best_rows = data_rows
        return best_headers, best_rows

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
        headers, rows = self._pick_registry_table(document)
        if not headers or not rows:
            return []
        roles = [self._registry_header_role(header) for header in headers]
        organisms: List[Dict[str, Any]] = []
        seen_ids = set()
        for row in rows:
            cells = [self._registry_cell_text(node) for node in row.xpath("./th|./td")]
            if not cells or len(cells) < 2:
                continue
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
            if not payload["name"]:
                payload["name"] = cells[1] if len(cells) > 1 else cells[0]
            registration_number = payload["registration_number"]
            if registration_number:
                match = re.search(r"\d+", registration_number)
                payload["registration_number"] = match.group(0) if match else registration_number
            payload["type"] = _normalize_registry_kind(payload["type"])
            payload["official_registry_url"] = REGISTRO_MEDIAZIONE_DIRECT_URL
            payload["official_info_url"] = REGISTRO_MEDIAZIONE_INFO_URL
            if extra_columns:
                payload["extra_columns"] = extra_columns
            record_base = payload["registration_number"] or f"{payload['name']}|{payload['city']}|{payload['pec']}"
            record_id = hashlib.sha1(record_base.encode("utf-8")).hexdigest()[:16]
            if record_id in seen_ids:
                continue
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
                    ]
                )
            ).lower()
            organisms.append(payload)
        organisms.sort(key=lambda item: (item.get("name", ""), item.get("city", ""), item.get("registration_number", "")))
        return organisms

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
        if source_id in {"pst_giustizia", "pst_servizi_web"}:
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
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = now or datetime.now()
        context = self._fetch_registro_mediazione_context(request_get=request_get)
        defaults = dict(context["defaults"])
        existing_rows = [dict(row) for row in self.normative_tables.rows(REGISTRO_MEDIAZIONE_TABLE_ID)]
        try:
            document = self._fetch_html_document(
                REGISTRO_MEDIAZIONE_DIRECT_URL,
                request_get=request_get,
            )
            if document["status_code"] >= 400:
                raise RuntimeError(f"HTTP {document['status_code']}")
            if document["protection_page"]:
                raise RuntimeError("La consultazione diretta del registro e protetta o richiede browser compatibile.")

            rows = self._parse_registro_mediazione_rows(document["content"])
            if not rows:
                raise RuntimeError("Il registro diretto non ha restituito un elenco strutturato leggibile.")

            defaults.update(
                {
                    "last_registry_fetch_url": document["final_url"],
                    "last_registry_hash": _sha256(document["content"]),
                    "registry_notice": REGISTRO_MEDIAZIONE_NOTICE,
                    "data_origin": "live_registry",
                    "data_origin_label": "Registro diretto ministeriale",
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
            result["final_url"] = document["final_url"]
            result["live_ok"] = True
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
            filtered.append(row)

        type_options = sorted({row.get("type", "") for row in rows if row.get("type")})
        city_options = sorted({row.get("city", "") for row in rows if row.get("city")})[:200]
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
            },
            "rows": filtered[:400],
            "total_rows": len(rows),
            "filtered_rows": len(filtered),
            "type_options": type_options,
            "city_options": city_options,
            "has_cached_rows": bool(rows),
            "official_notice": metadata.get("consultation_mode") or REGISTRO_MEDIAZIONE_NOTICE,
            "technical_notice": metadata.get("technical_notice") or table.get("last_warning") or "",
            "data_origin": data_origin,
            "data_origin_label": data_origin_label,
            "imported_at": metadata.get("imported_at", ""),
            "import_filename": metadata.get("import_filename", ""),
            "last_successful_sync_at": metadata.get("last_successful_sync_at", ""),
        }

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
