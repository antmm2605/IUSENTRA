from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import unicodedata
import uuid
import zipfile
from email.utils import parsedate_to_datetime
from html import escape as _html_escape
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlencode, urljoin, urlparse

import requests
from lxml import etree as lxml_etree
from lxml import html as lxml_html
import pdfplumber

from pct import cache as _cache
from pct.giurisprudenza_corpus import (
    GestioneCorpusGiurisprudenza,
    derive_corpus_db_path,
)
from pct.giurisprudenza_repository import (
    GestioneRepositoryGiurisprudenza,
    build_giurisprudenza_sources_rows,
    build_giurisprudenza_sync_rows,
    build_giurisprudenza_taxonomy_rows,
    build_giurisprudenza_usage_rows,
    derive_giurisprudenza_repository_db_path,
    derive_giurisprudenza_repository_json_path,
    derive_giurisprudenza_sources_json_path,
    derive_giurisprudenza_sync_json_path,
    derive_giurisprudenza_taxonomy_json_path,
    derive_giurisprudenza_usage_json_path,
)
from pct.legal_intelligence import FONTI_UFFICIALI

USER_AGENT_GIURISPRUDENZA = "IUSENTRA-Giurisprudenza/1.0"
MAX_SYNC_ITEMS = 12
MAX_SYNC_RUNS = 300
GIURISPRUDENZA_STORAGE_VERSION = 2
MAX_TEXT_VERSIONS = 8


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _normalize(value: str) -> str:
    return _slug(value).replace("_", " ").strip()


def _sha1(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()


def _split_multi(value: str | Iterable[str]) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        items = [str(item or "").strip() for item in value]
    else:
        items = re.split(r"[,;\n\r]+", str(value or ""))
    out: List[str] = []
    seen = set()
    for item in items:
        cleaned = _clean_spaces(item)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)
    return out


def _parse_iso_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], pattern).date().isoformat()
        except ValueError:
            continue
    return ""


def _extract_date(text: str) -> str:
    raw = _clean_spaces(text)
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except Exception:
        pass
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if match:
        day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return ""
    months = {
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
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", raw, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month = months.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return ""
    return ""


def _extract_year(text: str) -> str:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", text or "")
    return match.group(1) if match else ""


def _extract_number(text: str) -> str:
    match = re.search(r"(?:n\.?|nr\.?|num(?:ero)?)\s*([0-9]{1,6}(?:/[0-9]{2,4})?)", text or "", re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_case_reference(text: str) -> str:
    raw = _clean_spaces(text)
    if not raw:
        return ""
    eu_refs = re.findall(r"\b(?:[A-Z]{1,3}-\d+/\d+(?:\s*[A-Z])?)\b", raw)
    if eu_refs:
        unique_refs = list(dict.fromkeys(ref.strip() for ref in eu_refs if ref.strip()))
        return "; ".join(unique_refs[:4])
    application_ref = re.search(r"\b(\d{3,6}/\d{2,4}(?:\s*;\s*\d{3,6}/\d{2,4})*)\b", raw)
    if application_ref:
        return re.sub(r"\s*;\s*", "; ", application_ref.group(1))
    return ""


def _extract_ecli(text: str) -> str:
    match = re.search(r"(ECLI:[A-Z]{2}:[A-Z0-9_.:]+)", text or "", re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _truncate(text: str, limit: int = 280) -> str:
    cleaned = _clean_spaces(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "â€¦"


def _source_url(existing_id: str, fallback: str) -> str:
    src = FONTI_UFFICIALI.get(existing_id)
    return src.official_url if src else fallback


def _infer_openga_grade(office_name: str) -> str:
    lowered = _clean_spaces(office_name).lower()
    if "consiglio di stato" in lowered:
        return "Consiglio di Stato"
    if "consiglio di giustizia amministrativa" in lowered or "c.g.a." in lowered:
        return "CGA"
    if "tar" in lowered:
        return "TAR"
    return ""


def _hudoc_rss_url(language: str = "eng") -> str:
    query = "contentsitename:ECHR AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD))"
    params = {
        "library": f"echr{language}",
        "query": query,
        "sort": "kpdate Descending",
        "start": "0",
    }
    return "https://hudoc.echr.coe.int/app/transform/rss?" + urlencode(params)


@dataclass(frozen=True)
class FonteGiurisprudenziale:
    id: str
    nome: str
    giurisdizione: str
    coverage: str
    official_url: str
    search_url: str
    access_mode: str
    sync_mode: str
    note: str
    badge: str
    icon: str = "bi-bank"
    search_label: str = "Apri fonte ufficiale"
    supports_auto_sync: bool = False
    default_area: str = ""
    default_grade: str = ""
    license_note: str = ""
    link_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SOURCE_SPECS: List[FonteGiurisprudenziale] = [
    FonteGiurisprudenziale(
        id="openga",
        nome="OpenGA - Giustizia amministrativa",
        giurisdizione="Amministrativa",
        coverage="Dataset ufficiali di provvedimenti amministrativi in formato CSV, JSON e ODS per sede e anno.",
        official_url="https://openga.giustizia-amministrativa.it/",
        search_url="https://openga.giustizia-amministrativa.it/api/3/action/package_search?q=sentenze&rows=100",
        access_mode="open_data",
        sync_mode="automatico_dataset",
        note=(
            "Canale migliore per popolamento automatico della giurisprudenza amministrativa: "
            "dataset ufficiali CKAN, aggiornamento mensile e licenza aperta."
        ),
        badge="Open data",
        icon="bi-database-check",
        search_label="Apri OpenGA",
        supports_auto_sync=True,
        default_area="Amministrativo",
        license_note="CC BY 4.0",
        link_keywords=["sentenze", "provvedimenti", "dataset", "json"],
    ),
    FonteGiurisprudenziale(
        id="cassazione",
        nome="Corte di Cassazione",
        giurisdizione="Ordinaria",
        coverage="LegittimitÃ , sentenze, ordinanze, massimario e principi di diritto.",
        official_url=_source_url("cassazione", "https://www.cortedicassazione.it/"),
        search_url="https://www.cortedicassazione.it/it/massimario.page",
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Fonte primaria per legittimitÃ  civile e penale; utile per principi di diritto e orientamenti consolidati.",
        badge="Fonte primaria",
        icon="bi-building-check",
        search_label="Apri Cassazione",
        supports_auto_sync=True,
        default_grade="Cassazione",
        license_note="Consultazione pubblica istituzionale",
        link_keywords=["sentenza", "ordinanza", "massimario", "principio", "diritto"],
    ),
    FonteGiurisprudenziale(
        id="merito_civile_bdp",
        nome="Banca Dati di Merito",
        giurisdizione="Ordinaria",
        coverage="Provvedimenti civili di Tribunali e Corti d'appello pubblicati dal 1 gennaio 2016.",
        official_url="https://pst.giustizia.it/PST/",
        search_url="https://pst.giustizia.it/PST/",
        access_mode="area_riservata_pst",
        sync_mode="recupero_assistito",
        note=(
            "Accesso tramite PST area riservata con autenticazione. Copertura civile di merito; "
            "esclusi famiglia, minori e stato della persona secondo le regole ministeriali."
        ),
        badge="Area riservata",
        icon="bi-shield-lock",
        search_label="Apri PST area riservata",
        supports_auto_sync=False,
        default_area="Civile",
        license_note="Accesso autenticato PST",
        link_keywords=["tribunale", "corte d'appello", "sentenza", "ordinanza"],
    ),
    FonteGiurisprudenziale(
        id="corte_costituzionale",
        nome="Corte costituzionale",
        giurisdizione="Costituzionale",
        coverage="Pronunce, massime, ultimo deposito e schede ufficiali.",
        official_url=_source_url("corte_costituzionale", "https://www.cortecostituzionale.it/"),
        search_url="https://dati.cortecostituzionale.it/Scarica_i_dati/Scarica_i_dati",
        access_mode="open_data",
        sync_mode="automatico_dataset",
        note="Fonte primaria per pronunce costituzionali da dataset ufficiali aperti, con testi integrali e metadati strutturati.",
        badge="Fonte primaria",
        icon="bi-columns-gap",
        search_label="Apri Corte costituzionale",
        supports_auto_sync=True,
        default_area="Costituzionale",
        license_note="CC BY-SA 3.0",
        link_keywords=["sentenza", "ordinanza", "pronuncia", "massima", "deposito"],
    ),
    FonteGiurisprudenziale(
        id="giustizia_amministrativa",
        nome="Giustizia amministrativa",
        giurisdizione="Amministrativa",
        coverage="TAR, Consiglio di Stato, pareri e massime ufficiali.",
        official_url=_source_url("giustizia_amministrativa", "https://www.giustizia-amministrativa.it/"),
        search_url="https://www.giustizia-amministrativa.it/",
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Fonte primaria per TAR, Consiglio di Stato e CGA; utile per cautelari, appalti e processo amministrativo.",
        badge="Fonte primaria",
        icon="bi-bank2",
        search_label="Apri Giustizia amministrativa",
        supports_auto_sync=True,
        default_area="Amministrativo",
        license_note="Consultazione pubblica istituzionale",
        link_keywords=["decisione", "sentenza", "ordinanza", "parere", "massima"],
    ),
    FonteGiurisprudenziale(
        id="giustizia_tributaria",
        nome="Giustizia tributaria",
        giurisdizione="Tributaria",
        coverage="Decisioni, massime ed estremi delle controversie tributarie.",
        official_url="https://www.giustiziatributaria.gov.it/",
        search_url="https://www.giustiziatributaria.gov.it/",
        access_mode="portale_ufficiale",
        sync_mode="recupero_assistito",
        note="Fonte ufficiale per controversie tributarie; acquisizione guidata consigliata con handoff al portale istituzionale.",
        badge="Portale ufficiale",
        icon="bi-receipt-cutoff",
        search_label="Apri Giustizia tributaria",
        supports_auto_sync=False,
        default_area="Tributario",
        license_note="Portale istituzionale e banca dati ufficiale",
        link_keywords=["decisione", "massima", "sentenza", "tributaria"],
    ),
    FonteGiurisprudenziale(
        id="curia",
        nome="CURIA",
        giurisdizione="UE / CEDU",
        coverage="Corte di Giustizia e Tribunale dell'Unione europea con ricerca giurisprudenziale.",
        official_url="https://curia.europa.eu/jcms/jcms/j_6/it/",
        search_url="https://curia.europa.eu/site/",
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Motore ufficiale UE; utile per ECLI, giurisprudenza su appalti, concorrenza, consumatori e fiscalitÃ .",
        badge="Fonte europea",
        icon="bi-globe-europe-africa",
        search_label="Apri CURIA",
        supports_auto_sync=True,
        default_area="UE / CEDU",
        license_note="Consultazione pubblica ufficiale",
        link_keywords=["judgment", "opinion", "order", "curia", "case", "recent judgment"],
    ),
    FonteGiurisprudenziale(
        id="hudoc",
        nome="HUDOC / CEDU",
        giurisdizione="UE / CEDU",
        coverage="Sentenze e decisioni della Corte EDU con filtri per Stato, articolo e materia.",
        official_url="https://hudoc.echr.coe.int/",
        search_url=_hudoc_rss_url(),
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Fonte ufficiale CEDU; utile per equo processo, proprietÃ , vita privata e familiare.",
        badge="Fonte europea",
        icon="bi-globe2",
        search_label="Apri HUDOC",
        supports_auto_sync=True,
        default_area="UE / CEDU",
        license_note="Consultazione pubblica ufficiale",
        link_keywords=["judgment", "decision", "article", "italy", "echr", "hudoc"],
    ),
    FonteGiurisprudenziale(
        id="corte_conti",
        nome="Corte dei Conti",
        giurisdizione="Contabile",
        coverage="Giurisprudenza contabile, responsabilitÃ  erariale e sezioni regionali.",
        official_url=_source_url("corte_conti", "https://www.corteconti.it/"),
        search_url="https://www.corteconti.it/",
        access_mode="pubblico",
        sync_mode="recupero_assistito",
        note="Fonte specialistica per responsabilitÃ  amministrativa e contabile.",
        badge="Fonte specialistica",
        icon="bi-safe2",
        supports_auto_sync=False,
        default_area="Contabile",
        license_note="Consultazione pubblica istituzionale",
        link_keywords=["sentenza", "decisione", "responsabilitÃ ", "erariale"],
    ),
    FonteGiurisprudenziale(
        id="simpliciter_cliente",
        nome="Simpliciter (materiale cliente)",
        giurisdizione="Trasversale",
        coverage="Import assistito da URL, testo, PDF o HTML forniti dall'utente.",
        official_url="https://simpliciter.ai/ricerca/",
        search_url="https://simpliciter.ai/ricerca/",
        access_mode="materiale_cliente",
        sync_mode="import_assistito",
        note=(
            "IUSENTRA non esegue scraping della banca dati Simpliciter. "
            "Importa solo materiali, output o file che il cliente ha giÃ  ottenuto legittimamente nel proprio account."
        ),
        badge="Import assistito",
        icon="bi-inbox",
        search_label="Apri Simpliciter",
        supports_auto_sync=False,
        license_note="Materiale fornito dal cliente",
        link_keywords=["sentenza", "ordinanza", "decreto", "decisione", "massima", "principio di diritto"],
    ),
    FonteGiurisprudenziale(
        id="manuale_interno",
        nome="Inserimento redazionale interno",
        giurisdizione="Trasversale",
        coverage="Schede sentenza inserite, arricchite e collegate dallo studio.",
        official_url="",
        search_url="",
        access_mode="manuale",
        sync_mode="manuale",
        note="Usa questo canale per inserimenti redazionali, recuperi dal browser e pulizia delle schede sentenza.",
        badge="Interno studio",
        icon="bi-pencil-square",
        search_label="Nuova scheda",
        supports_auto_sync=False,
        license_note="Archivio interno studio",
    ),
]


ORIENTAMENTI = ["conforme", "contrario", "superato", "in formazione", "isolato"]
RILEVANZE_PRATICHE = ["alta", "media", "bassa"]
USI_NEL_SOFTWARE = ["citabile in atto", "precedente forte", "precedente debole", "solo studio"]
TIPI_PROVVEDIMENTO = ["sentenza", "ordinanza", "decreto", "decisione", "parere", "massima"]


TASSONOMIA_GIURISPRUDENZA: List[Dict[str, Any]] = [
    {
        "id": "civile",
        "title": "Civile",
        "icon": "bi-house-door",
        "description": "Contenzioso civile, merito e legittimitÃ .",
        "branches": [
            {"title": "Obbligazioni e contratti", "subbranches": ["Compravendita", "Appalto", "Locazione", "Mandato", "Leasing", "Mediazione", "Mutuo", "Fideiussione", "Clausole vessatorie", "NullitÃ  / annullabilitÃ  / risoluzione / rescissione", "Inadempimento", "Prescrizione", "Prova del contratto"]},
            {"title": "ResponsabilitÃ  civile", "subbranches": ["RC auto", "ResponsabilitÃ  medica", "ResponsabilitÃ  professionale", "Danno da cose in custodia", "Danno da insidia", "Diffamazione", "Danno non patrimoniale", "Perdita di chance", "Danno parentale"]},
            {"title": "Diritti reali", "subbranches": ["Usucapione", "ServitÃ¹", "Comunione", "Possesso", "Azione di rivendica"]},
            {"title": "Condominio", "subbranches": ["Ripartizione spese", "Delibere assembleari", "Impugnazioni", "Innovazioni"]},
            {"title": "Locazioni", "subbranches": ["MorositÃ ", "Rinnovo", "Canone", "Recesso", "Sfratto"]},
            {"title": "Successioni", "subbranches": ["Legittima", "Testamento", "Collazione", "Riduzione", "Divisione ereditaria"]},
            {"title": "Famiglia e persone", "subbranches": ["Separazione", "Divorzio", "Affidamento", "Assegno di mantenimento", "Stato della persona"]},
            {"title": "Lavoro", "subbranches": ["Licenziamento", "Demansionamento", "Mobbing", "Differenze retributive", "Appalto e somministrazione"]},
            {"title": "Previdenza e assistenza", "subbranches": ["Pensione", "InvaliditÃ ", "Contributi", "Prestazioni assistenziali"]},
            {"title": "Societario e commerciale", "subbranches": ["Impugnazione delibere", "Amministratori", "Soci", "Recesso", "Bilancio"]},
            {"title": "Bancario e finanziario", "subbranches": ["Anatocismo", "Usura", "Mutui", "Derivati", "Segnalazioni a sofferenza"]},
            {"title": "Assicurazioni", "subbranches": ["Polizza", "Sinistro", "Manleva", "RCA", "Azione diretta"]},
            {"title": "Esecuzioni", "subbranches": ["Pignoramento", "Opposizioni", "Vendita forzata", "Assegnazione", "Terzo pignorato"]},
            {"title": "Procedure concorsuali / crisi d'impresa", "subbranches": ["Fallimento", "Liquidazione giudiziale", "Concordato", "Composizione negoziata", "Revocatorie"]},
            {"title": "Volontaria giurisdizione", "subbranches": ["Amministrazione di sostegno", "Tutele", "Autorizzazioni", "Nomine"]},
            {"title": "ProprietÃ  industriale e intellettuale", "subbranches": ["Marchi", "Brevetti", "Concorrenza sleale", "Diritto d'autore"]},
            {"title": "Consumatori", "subbranches": ["Clausole abusive", "Pratiche commerciali scorrette", "Credito al consumo", "Garanzia beni"]},
            {"title": "Agrario", "subbranches": ["Affitto fondo rustico", "Prelazione", "Migliorie"]},
            {"title": "Internazionale privato e giurisdizione", "subbranches": ["Competenza", "Legge applicabile", "Riconoscimento sentenze", "Arbitrato internazionale"]},
        ],
    },
    {
        "id": "penale",
        "title": "Penale",
        "icon": "bi-shield-lock",
        "description": "Parte generale, reati e procedura penale.",
        "branches": [
            {"title": "Parte generale", "subbranches": ["Elemento soggettivo", "Tentativo", "Concorso di persone", "Circostanze", "Cause di giustificazione"]},
            {"title": "Delitti contro la persona", "subbranches": ["Lesioni", "Omicidio", "Violenza privata", "Maltrattamenti", "Stalking"]},
            {"title": "Delitti contro il patrimonio", "subbranches": ["Furto", "Rapina", "Estorsione", "Truffa", "Appropriazione indebita", "Ricettazione", "Riciclaggio", "Autoriciclaggio"]},
            {"title": "Delitti contro la pubblica amministrazione", "subbranches": ["Corruzione", "Concussione", "Peculato", "Abuso d'ufficio"]},
            {"title": "Delitti economici / societari / tributari", "subbranches": ["False comunicazioni sociali", "Bancarotta", "Dichiarazione fraudolenta", "Omesso versamento"]},
            {"title": "Reati edilizi e ambientali", "subbranches": ["Abusi edilizi", "Rifiuti", "Inquinamento", "Lottizzazione abusiva"]},
            {"title": "Reati stradali", "subbranches": ["Guida in stato di ebbrezza", "Omicidio stradale", "Lesioni stradali"]},
            {"title": "Stupefacenti", "subbranches": ["Detenzione", "Spaccio", "Associazione", "Lieve entitÃ "]},
            {"title": "Misure cautelari", "subbranches": ["Custodia cautelare", "Arresti domiciliari", "Divieti e obblighi", "Esigenze cautelari"]},
            {"title": "Esecuzione penale", "subbranches": ["Ordine di esecuzione", "Sospensione", "Misure alternative"]},
            {"title": "Ordinamento penitenziario", "subbranches": ["Permessi", "Liberazione anticipata", "Affidamento", "Detenzione domiciliare"]},
            {"title": "Procedura penale", "subbranches": ["Notificazioni", "NullitÃ ", "Prova", "Impugnazioni", "Abbreviato"]},
            {"title": "Misure di prevenzione", "subbranches": ["Personali", "Patrimoniali", "Confisca", "Sequestro"]},
            {"title": "ResponsabilitÃ  da reato degli enti ex d.lgs. 231/2001", "subbranches": ["Modelli organizzativi", "Interesse o vantaggio", "Reati presupposto", "Sanzioni"]},
        ],
    },
    {
        "id": "amministrativo",
        "title": "Amministrativo",
        "icon": "bi-bank2",
        "description": "TAR, Consiglio di Stato e contenzioso con la PA.",
        "branches": [
            {"title": "Appalti pubblici", "subbranches": ["Requisiti di partecipazione", "Avvalimento", "Soccorso istruttorio", "Anomalia dell'offerta", "Esclusione", "Subappalto", "Accesso agli atti", "Revisione prezzi", "Esecuzione contratto"]},
            {"title": "Edilizia e urbanistica", "subbranches": ["Permesso di costruire", "SCIA", "Abusi", "Pianificazione", "Sanatoria"]},
            {"title": "Pubblico impiego", "subbranches": ["Sanzioni disciplinari", "Progressioni", "MobilitÃ ", "Mansioni"]},
            {"title": "Concorsi", "subbranches": ["Bando", "Valutazione titoli", "Prove", "Scorrimento graduatorie"]},
            {"title": "Ambiente", "subbranches": ["VIA", "AIA", "Bonifiche", "Rifiuti"]},
            {"title": "Espropriazione", "subbranches": ["IndennitÃ ", "Occupazione", "Dichiarazione di pubblica utilitÃ "]},
            {"title": "SanitÃ ", "subbranches": ["Accreditamenti", "ResponsabilitÃ  sanitaria pubblica", "Farmacie"]},
            {"title": "UniversitÃ  e scuola", "subbranches": ["Graduatorie", "Abilitazioni", "Trasferimenti", "Tasse universitarie"]},
            {"title": "Immigrazione", "subbranches": ["Permesso di soggiorno", "Cittadinanza", "Espulsione", "Asilo"]},
            {"title": "Elettorale", "subbranches": ["Ammissione liste", "Operazioni elettorali", "Proclamazione eletti"]},
            {"title": "Antimafia / interdittive", "subbranches": ["Informative", "White list", "Appalti", "Prevenzione"]},
            {"title": "Processo amministrativo", "subbranches": ["Giurisdizione", "Competenza", "Cautelari", "Ottemperanza", "Impugnazioni"]},
        ],
    },
    {
        "id": "tributario",
        "title": "Tributario",
        "icon": "bi-receipt-cutoff",
        "description": "Contenzioso e riscossione tributaria.",
        "branches": [
            {"title": "Imposte dirette", "subbranches": ["IRPEF", "IRES", "Redditi d'impresa", "Redditi di lavoro autonomo"]},
            {"title": "IVA", "subbranches": ["Detrazione", "Operazioni imponibili", "Operazioni inesistenti", "Reverse charge"]},
            {"title": "Registro / ipocatastali", "subbranches": ["Registro", "Ipotecaria", "Catastale", "Agevolazioni prima casa"]},
            {"title": "Tributi locali", "subbranches": ["IMU", "TARI", "TOSAP / COSAP", "Imposta di soggiorno"]},
            {"title": "Riscossione ed esecuzione", "subbranches": ["Cartella", "Intimazione", "Fermo", "Ipoteca", "Prescrizione", "Notifica", "Estratto di ruolo", "Rateazione"]},
            {"title": "Sanzioni tributarie", "subbranches": ["Elemento soggettivo", "Cumulo", "Ravvedimento", "Obiettiva incertezza"]},
            {"title": "Processo tributario", "subbranches": ["AmmissibilitÃ  ricorso", "Termini", "Notifiche", "Sospensione", "Appello"]},
            {"title": "Abuso del diritto / elusione", "subbranches": ["Operazioni elusive", "Riqualificazione", "Onere della prova"]},
            {"title": "Transfer pricing / fiscalitÃ  d'impresa", "subbranches": ["Prezzi di trasferimento", "Stabile organizzazione", "Documentazione"]},
            {"title": "Agevolazioni e crediti d'imposta", "subbranches": ["Bonus edilizi", "Ricerca e sviluppo", "Industria 4.0"]},
        ],
    },
    {
        "id": "costituzionale",
        "title": "Costituzionale",
        "icon": "bi-columns-gap",
        "description": "Pronunce e questioni costituzionali.",
        "branches": [
            {"title": "Diritti fondamentali", "subbranches": ["Uguaglianza", "Salute", "Difesa", "LibertÃ  personale"]},
            {"title": "Riparto Stato-Regioni", "subbranches": ["Competenze legislative", "Leale collaborazione", "Finanza regionale"]},
            {"title": "Processo costituzionale", "subbranches": ["Incidente di costituzionalitÃ ", "Conflitti", "Referendum"]},
            {"title": "Ordinamento giudiziario", "subbranches": ["Status magistrati", "CSM", "Organizzazione"]},
            {"title": "Materia penale", "subbranches": ["Riserva di legge", "IrretroattivitÃ ", "ProporzionalitÃ  pena"]},
            {"title": "Materia civile", "subbranches": ["Tutela giurisdizionale", "Famiglia", "Patrimonio"]},
            {"title": "Materia tributaria", "subbranches": ["CapacitÃ  contributiva", "Ragionevolezza", "Sanzioni"]},
            {"title": "Materia amministrativa", "subbranches": ["Accesso", "Pubblico impiego", "Procedimento"]},
        ],
    },
    {
        "id": "ue_cedu",
        "title": "UE / CEDU",
        "icon": "bi-globe-europe-africa",
        "description": "Giurisprudenza della Corte di Giustizia UE e della Corte EDU.",
        "branches": [
            {"title": "Libera circolazione", "subbranches": ["Persone", "Servizi", "Capitali", "Stabilimento"]},
            {"title": "Concorrenza", "subbranches": ["Intese", "Abuso di posizione dominante", "Aiuti di Stato"]},
            {"title": "Appalti", "subbranches": ["Affidamenti", "Concorrenza", "Trasparenza", "Rimedi"]},
            {"title": "Consumatori", "subbranches": ["Clausole abusive", "Pratiche scorrette", "Garanzie"]},
            {"title": "Lavoro", "subbranches": ["ParitÃ  di trattamento", "Orario", "Trasferimenti"]},
            {"title": "Privacy / dati personali", "subbranches": ["GDPR", "Sorveglianza", "Trattamenti illeciti"]},
            {"title": "Asilo e immigrazione", "subbranches": ["Protezione internazionale", "Ricongiungimento", "Espulsioni"]},
            {"title": "FiscalitÃ ", "subbranches": ["IVA", "Aiuti fiscali", "Doppia imposizione"]},
            {"title": "Equo processo", "subbranches": ["Ragionevole durata", "Contraddittorio", "ImparzialitÃ "]},
            {"title": "ProprietÃ ", "subbranches": ["Espropriazione", "Vincoli", "Prot. 1 art. 1"]},
            {"title": "Vita privata e familiare", "subbranches": ["Art. 8 CEDU", "Minori", "Protezione dati"]},
        ],
    },
    {
        "id": "contabile",
        "title": "Contabile",
        "icon": "bi-safe2",
        "description": "Giurisprudenza della Corte dei Conti e responsabilitÃ  erariale.",
        "branches": [
            {"title": "ResponsabilitÃ  amministrativa", "subbranches": ["Danno erariale", "Colpa grave", "Prescrizione", "Quantificazione"]},
            {"title": "ContabilitÃ  pubblica", "subbranches": ["Enti locali", "SocietÃ  partecipate", "Controlli", "Pareri"]},
        ],
    },
]


def tassonomia_flat() -> Dict[str, List[str]]:
    aree: List[str] = []
    branche: List[str] = []
    sottobranche: List[str] = []
    for area in TASSONOMIA_GIURISPRUDENZA:
        aree.append(area["title"])
        for branch in area.get("branches", []):
            branche.append(branch["title"])
            for sub in branch.get("subbranches", []):
                sottobranche.append(sub)
    return {"aree": aree, "branche": branche, "sottobranche": sottobranche}


class GestioneGiurisprudenza:
    def __init__(self, db_path: str = "./intelligence/giurisprudenza.json", timeout: int = 12):
        self.db_path = db_path
        self.corpus_db_path = derive_corpus_db_path(db_path)
        self.repository_db_path = derive_giurisprudenza_repository_db_path(self.db_path)
        self.repository_json_path = derive_giurisprudenza_repository_json_path(self.db_path)
        self.repository_sources_json_path = derive_giurisprudenza_sources_json_path(self.db_path)
        self.repository_taxonomy_json_path = derive_giurisprudenza_taxonomy_json_path(self.db_path)
        self.repository_usage_json_path = derive_giurisprudenza_usage_json_path(self.db_path)
        self.repository_sync_json_path = derive_giurisprudenza_sync_json_path(self.db_path)
        self.timeout = timeout
        self._data: Dict[str, Any] = self._empty_storage()
        self._corpus = GestioneCorpusGiurisprudenza(self.corpus_db_path)
        self._repository = GestioneRepositoryGiurisprudenza(
            self.repository_db_path,
            json_path=self.repository_json_path,
            sources_json_path=self.repository_sources_json_path,
            taxonomy_json_path=self.repository_taxonomy_json_path,
            usage_json_path=self.repository_usage_json_path,
            sync_json_path=self.repository_sync_json_path,
        )
        self._load()
        self._sync_repository()

    def _empty_storage(self) -> Dict[str, Any]:
        return {
            "storage_version": GIURISPRUDENZA_STORAGE_VERSION,
            "legal_sources": [],
            "ingestion_runs": [],
            "raw_documents": [],
            "judgment_texts": [],
            "practice_judgments": [],
            "judgments": [],
            "sync_runs": [],
        }

    def _load(self) -> None:
        try:
            raw = _cache.load(self.db_path, default={}) or {}
            base = self._empty_storage()
            base["judgments"] = list(raw.get("judgments") or [])
            base["ingestion_runs"] = list(raw.get("ingestion_runs") or raw.get("sync_runs") or [])
            base["sync_runs"] = list(base["ingestion_runs"])
            base["legal_sources"] = list(raw.get("legal_sources") or [])
            base["raw_documents"] = list(raw.get("raw_documents") or [])
            base["judgment_texts"] = list(raw.get("judgment_texts") or [])
            base["practice_judgments"] = list(raw.get("practice_judgments") or [])
            base["storage_version"] = int(raw.get("storage_version") or GIURISPRUDENZA_STORAGE_VERSION)
            self._data = base
            changed = self._seed_sources_registry()
            changed = self._migrate_existing_judgments() or changed
            if changed:
                self._save()
        except Exception:
            self._data = self._empty_storage()
            self._seed_sources_registry()

    def _save(self) -> None:
        payload = dict(self._data)
        payload["sync_runs"] = list(payload.get("ingestion_runs") or [])
        _cache.save(self.db_path, payload, indent=2)
        self._sync_repository()

    def _seed_sources_registry(self) -> bool:
        rows = {str(item.get("id") or ""): dict(item) for item in self._data.get("legal_sources", []) if item.get("id")}
        changed = False
        seeded: List[Dict[str, Any]] = []
        for source in SOURCE_SPECS:
            current = rows.get(source.id, {})
            normalized = {
                "id": source.id,
                "code": source.id.upper(),
                "name": source.nome,
                "type": source.sync_mode,
                "official_url": source.official_url,
                "search_url": source.search_url,
                "license_note": source.license_note,
                "access_mode": source.access_mode,
                "sync_mode": source.sync_mode,
                "is_active": current.get("is_active", True),
                "giurisdizione": source.giurisdizione,
                "coverage": source.coverage,
                "badge": source.badge,
                "icon": source.icon,
                "search_label": source.search_label,
                "supports_auto_sync": source.supports_auto_sync,
                "default_area": source.default_area,
                "default_grade": source.default_grade,
                "link_keywords": list(source.link_keywords or []),
                "note": source.note,
                "created_at": current.get("created_at") or _now_iso(),
                "updated_at": _now_iso(),
            }
            seeded.append(normalized)
            comparable_current = dict(current)
            comparable_current.pop("updated_at", None)
            comparable_normalized = dict(normalized)
            comparable_normalized.pop("updated_at", None)
            if comparable_current != comparable_normalized:
                changed = True
        if changed or len(seeded) != len(self._data.get("legal_sources", [])):
            self._data["legal_sources"] = seeded
        return changed

    def _migrate_existing_judgments(self) -> bool:
        changed = False
        if not self._data.get("judgment_texts"):
            versions: List[Dict[str, Any]] = []
            for row in self._data.get("judgments", []):
                text_original = _clean_spaces(
                    "\n\n".join(
                        item
                        for item in [
                            row.get("massima", ""),
                            row.get("principio_diritto", ""),
                            row.get("abstract", ""),
                        ]
                        if str(item or "").strip()
                    )
                )
                if not text_original:
                    continue
                versions.append(
                    {
                        "id": uuid.uuid4().hex,
                        "judgment_id": row.get("id"),
                        "text_original": text_original,
                        "text_cleaned": text_original,
                        "text_structured": "",
                        "language": "it",
                        "version": 1,
                        "created_at": row.get("created_at") or _now_iso(),
                    }
                )
            self._data["judgment_texts"] = versions
            changed = bool(versions)
        if not self._data.get("practice_judgments"):
            links: List[Dict[str, Any]] = []
            for row in self._data.get("judgments", []):
                for practice_id in _split_multi(row.get("fascicoli_collegati") or []):
                    links.append(
                        {
                            "id": uuid.uuid4().hex,
                            "practice_id": practice_id,
                            "judgment_id": row.get("id"),
                            "link_type": "collegata",
                            "note": "",
                            "relevance_score": "",
                            "created_at": row.get("created_at") or _now_iso(),
                        }
                    )
            self._data["practice_judgments"] = links
            changed = bool(links) or changed
        return changed

    def catalogo_fonti(self) -> List[Dict[str, Any]]:
        latest_runs = self._latest_runs()
        counts: Dict[str, int] = {}
        for row in self._data.get("judgments", []):
            source_id = row.get("source_system") or "manuale_interno"
            counts[source_id] = counts.get(source_id, 0) + 1
        out: List[Dict[str, Any]] = []
        for item in self._data.get("legal_sources", []):
            row = dict(item)
            row["nome"] = row.get("nome") or row.get("name") or row.get("id")
            row["judgment_count"] = counts.get(row["id"], 0)
            row["last_run"] = latest_runs.get(row["id"])
            out.append(row)
        return out

    def tassonomia(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(TASSONOMIA_GIURISPRUDENZA)

    def statistiche(self) -> Dict[str, Any]:
        judgments = list(self._data.get("judgments", []))
        source_ids = {item.get("source_system") for item in judgments if item.get("source_system")}
        aree = {item.get("area") for item in judgments if item.get("area")}
        corpus_stats = self._corpus.storage_stats()
        return {
            "totale_sentenze": len(judgments),
            "fonti_attive": len(self._data.get("legal_sources", [])),
            "fonti_usate": len(source_ids),
            "aree_coperte": len(aree),
            "sync_pubblici": len([source for source in SOURCE_SPECS if source.supports_auto_sync]),
            "bozze_da_classificare": len([row for row in judgments if not row.get("branca") or not row.get("sottobranca")]),
            "documenti_raw": len(self._data.get("raw_documents", [])),
            "testi_normalizzati": len(self._data.get("judgment_texts", [])),
            "fascicoli_collegati": len(self._data.get("practice_judgments", [])),
            "corpus_professionale_attivo": True,
            "corpus_sentenze": int(corpus_stats.get("sentenze", 0)),
            "corpus_documenti": int(corpus_stats.get("documenti_sentenza", 0)),
            "corpus_principi": int(corpus_stats.get("principi_diritto", 0)),
        }

    def filtri(self) -> Dict[str, List[str]]:
        flat = tassonomia_flat()
        stored = list(self._data.get("judgments", []))
        grades = sorted({row.get("grado", "") for row in stored if row.get("grado")})
        organs = sorted({row.get("organo_giudicante", "") for row in stored if row.get("organo_giudicante")})
        sources = [source["id"] for source in self.catalogo_fonti()]
        return {
            "aree": flat["aree"],
            "branche": flat["branche"],
            "sottobranche": flat["sottobranche"],
            "gradi": grades,
            "organi": organs,
            "fonti": sources,
            "orientamenti": list(ORIENTAMENTI),
            "usi": list(USI_NEL_SOFTWARE),
            "tipi_provvedimento": list(TIPI_PROVVEDIMENTO),
        }

    def _latest_runs(self) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for row in self._data.get("ingestion_runs", []):
            source_id = row.get("source_id")
            current = latest.get(source_id)
            marker = row.get("ended_at") or row.get("checked_at") or row.get("started_at") or ""
            current_marker = (
                current.get("ended_at") or current.get("checked_at") or current.get("started_at") or ""
            ) if current else ""
            if current is None or str(marker) >= str(current_marker):
                latest[source_id] = row
        return latest

    def recent_sync_runs(self, limit: int = 12) -> List[Dict[str, Any]]:
        rows = sorted(
            self._data.get("ingestion_runs", []),
            key=lambda item: item.get("ended_at") or item.get("checked_at") or item.get("started_at") or "",
            reverse=True,
        )
        return rows[:limit]

    def storage_stats(self) -> Dict[str, int]:
        stats = {
            "storage_version": int(self._data.get("storage_version") or GIURISPRUDENZA_STORAGE_VERSION),
            "legal_sources": len(self._data.get("legal_sources", [])),
            "ingestion_runs": len(self._data.get("ingestion_runs", [])),
            "raw_documents": len(self._data.get("raw_documents", [])),
            "judgments": len(self._data.get("judgments", [])),
            "judgment_texts": len(self._data.get("judgment_texts", [])),
            "practice_judgments": len(self._data.get("practice_judgments", [])),
        }
        corpus_stats = self._corpus.storage_stats()
        stats["corpus_sentenze"] = int(corpus_stats.get("sentenze", 0))
        stats["corpus_documenti"] = int(corpus_stats.get("documenti_sentenza", 0))
        stats["corpus_massime"] = int(corpus_stats.get("massime", 0))
        stats["corpus_principi"] = int(corpus_stats.get("principi_diritto", 0))
        return stats

    def _sync_repository(self) -> None:
        catalog_rows = self.catalogo_fonti()
        source_rows = build_giurisprudenza_sources_rows(SOURCE_SPECS, catalog_rows)
        taxonomy_rows = build_giurisprudenza_taxonomy_rows(TASSONOMIA_GIURISPRUDENZA)
        usage_rows = build_giurisprudenza_usage_rows(
            ORIENTAMENTI,
            RILEVANZE_PRATICHE,
            USI_NEL_SOFTWARE,
            TIPI_PROVVEDIMENTO,
        )
        sync_rows = build_giurisprudenza_sync_rows(catalog_rows)
        self._repository.synchronize_runtime(
            source_rows=source_rows,
            taxonomy_rows=taxonomy_rows,
            usage_rows=usage_rows,
            sync_rows=sync_rows,
            export_json=True,
        )

    def statistiche_repository(self) -> Dict[str, Any]:
        return self._repository.storage_stats()

    def repository_payload(self) -> Dict[str, Any]:
        return self._repository.load_repository_payload()

    def export_giurisprudenza_repositories(self, base_dir: str | None = None) -> Dict[str, str]:
        return self._repository.export_split_jsons(base_dir)

    def resolve_lex_giurisprudenza_route(self, question: str) -> Dict[str, Any]:
        route = self._repository.resolve_route(question)
        prefer_pdf = bool(route.get("prefer_pdf"))
        prefer_verified_only = bool(route.get("prefer_verified_only"))

        candidate_queries: List[str] = []
        for candidate in (
            question,
            route.get("preferred_subbranch_title"),
            route.get("preferred_branch_title"),
            route.get("preferred_area_title"),
        ):
            cleaned = _clean_spaces(candidate)
            if cleaned and cleaned not in candidate_queries:
                candidate_queries.append(cleaned)

        corpus_rows: List[Dict[str, Any]] = []
        for candidate_query in candidate_queries:
            if prefer_verified_only:
                corpus_rows = self.cerca_corpus_professionale(
                    q=candidate_query,
                    stato_verifica="verificata",
                    solo_con_pdf=prefer_pdf,
                    limit=6,
                )
                if not corpus_rows:
                    corpus_rows = self.cerca_corpus_professionale(
                        q=candidate_query,
                        stato_verifica="parzialmente_verificata",
                        solo_con_pdf=prefer_pdf,
                        limit=6,
                    )
            if not corpus_rows:
                corpus_rows = self.cerca_corpus_professionale(
                    q=candidate_query,
                    solo_con_pdf=prefer_pdf,
                    limit=6,
                )
            if corpus_rows:
                break

        archive_rows = self.cerca(q=question)[:4] if _clean_spaces(question) else self.cerca()[:4]
        route["corpus_rows"] = corpus_rows
        route["archive_rows"] = archive_rows
        return route

    def cerca_corpus_professionale(
        self,
        *,
        q: str = "",
        organo_giudicante: str = "",
        materia_principale: str = "",
        stato_verifica: str = "",
        solo_con_pdf: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return self._corpus.cerca_sentenze(
            q=q,
            organo_giudicante=organo_giudicante,
            materia_principale=materia_principale,
            stato_verifica=stato_verifica,
            solo_con_pdf=solo_con_pdf,
            limit=limit,
        )

    def scheda_corpus_professionale(self, sentenza_id: Any) -> Dict[str, Any] | None:
        try:
            return self._corpus.get_sentenza(int(sentenza_id))
        except (TypeError, ValueError):
            return None

    def riferimento_professionale_verificato(self, sentenza_id: Any) -> bool:
        return self._corpus.can_cite_sentenza(self.scheda_corpus_professionale(sentenza_id))

    def pdf_professionale_disponibile(self, sentenza_id: Any) -> bool:
        return self._corpus.can_offer_pdf(self.scheda_corpus_professionale(sentenza_id))

    def empty_record(self, source_id: str = "manuale_interno") -> Dict[str, Any]:
        source = self._source(source_id)
        return {
            "id": "",
            "titolo": "",
            "source_system": source_id,
            "giurisdizione": source.giurisdizione if source else "",
            "ufficio": source.nome if source and source.nome != "Inserimento redazionale interno" else "",
            "grado": source.default_grade if source else "",
            "sezione": "",
            "numero_provvedimento": "",
            "data_decisione": "",
            "data_deposito": "",
            "tipo_provvedimento": "",
            "area": source.default_area if source else "",
            "branca": "",
            "sottobranca": "",
            "microtema": "",
            "rito": "",
            "materia": "",
            "norme_citate": [],
            "parole_chiave": [],
            "massima": "",
            "principio_diritto": "",
            "principio_sintetico": "",
            "abstract": "",
            "esito": "",
            "orientamento": "",
            "rilevanza_pratica": "",
            "uso_nel_software": "",
            "ecli": "",
            "identificatore_stabile": "",
            "url_origine": source.official_url if source else "",
            "url_pagina_ufficiale": source.official_url if source else "",
            "url_pdf_ufficiale": "",
            "stato_verifica_fonte": "da_verificare",
            "fonte_ufficiale_confermata": False,
            "pdf_ufficiale_presente": False,
            "collegamenti_precedenti": [],
            "collegamenti_norme": [],
            "precedenti_citati": [],
            "fascicoli_collegati": [],
            "note_redazionali": "",
        }

    def cerca(
        self,
        *,
        q: str = "",
        source_system: str = "",
        area: str = "",
        branca: str = "",
        sottobranca: str = "",
        grado: str = "",
        giurisdizione: str = "",
        orientamento: str = "",
        uso_nel_software: str = "",
    ) -> List[Dict[str, Any]]:
        rows = list(self._data.get("judgments", []))
        query = _normalize(q)

        def _matches(row: Dict[str, Any]) -> bool:
            if source_system and row.get("source_system") != source_system:
                return False
            if area and row.get("area") != area:
                return False
            if branca and row.get("branca") != branca:
                return False
            if sottobranca and row.get("sottobranca") != sottobranca:
                return False
            if grado and row.get("grado") != grado:
                return False
            if giurisdizione and row.get("giurisdizione") != giurisdizione:
                return False
            if orientamento and row.get("orientamento") != orientamento:
                return False
            if uso_nel_software and row.get("uso_nel_software") != uso_nel_software:
                return False
            if not query:
                return True
            haystack = " ".join(
                str(row.get(key, ""))
                for key in (
                    "titolo",
                    "area",
                    "branca",
                    "sottobranca",
                    "microtema",
                    "massima",
                    "principio_diritto",
                    "abstract",
                    "organo_giudicante",
                    "ufficio",
                    "materia",
                )
            )
            haystack += " " + " ".join(row.get("norme_citate") or [])
            haystack += " " + " ".join(row.get("parole_chiave") or [])
            latest_text = self._latest_text_row(row.get("id"))
            if latest_text:
                haystack += " " + str(latest_text.get("text_cleaned") or "")
            return query in _normalize(haystack)

        filtered = [row for row in rows if _matches(row)]
        filtered.sort(
            key=lambda row: (
                row.get("data_deposito", ""),
                row.get("data_decisione", ""),
                row.get("updated_at", ""),
            ),
            reverse=True,
        )
        return filtered

    def judgment_text_versions(self, judgment_id: str) -> List[Dict[str, Any]]:
        rows = [dict(row) for row in self._data.get("judgment_texts", []) if row.get("judgment_id") == judgment_id]
        rows.sort(key=lambda item: (item.get("version", 0), item.get("created_at", "")), reverse=True)
        return rows

    def raw_documents(self, judgment_id: str) -> List[Dict[str, Any]]:
        rows = [dict(row) for row in self._data.get("raw_documents", []) if row.get("judgment_id") == judgment_id]
        rows.sort(key=lambda item: item.get("downloaded_at", ""), reverse=True)
        return rows

    def practice_links(self, judgment_id: str) -> List[Dict[str, Any]]:
        rows = [dict(row) for row in self._data.get("practice_judgments", []) if row.get("judgment_id") == judgment_id]
        rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return rows

    def _latest_text_row(self, judgment_id: str) -> Optional[Dict[str, Any]]:
        rows = self.judgment_text_versions(judgment_id)
        return rows[0] if rows else None

    def get(self, judgment_id: str) -> Optional[Dict[str, Any]]:
        for row in self._data.get("judgments", []):
            if row.get("id") == judgment_id:
                item = dict(row)
                latest_text = self._latest_text_row(judgment_id)
                raw_rows = self.raw_documents(judgment_id)
                practice_rows = self.practice_links(judgment_id)
                item["text_versions_count"] = len(self.judgment_text_versions(judgment_id))
                item["raw_documents_count"] = len(raw_rows)
                item["practice_links_count"] = len(practice_rows)
                item["testo_integrale"] = (latest_text or {}).get("text_original", "")
                item["testo_normalizzato"] = (latest_text or {}).get("text_cleaned", "")
                item["latest_text_version"] = (latest_text or {}).get("version", 0)
                item["practice_links"] = practice_rows
                item["raw_items"] = raw_rows[:5]
                return item
        return None

    def related(self, judgment_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        record = self.get(judgment_id)
        if not record:
            return []
        rows = [row for row in self._data.get("judgments", []) if row.get("id") != judgment_id]
        scored: List[tuple[int, Dict[str, Any]]] = []
        for row in rows:
            score = 0
            if row.get("area") and row.get("area") == record.get("area"):
                score += 3
            if row.get("branca") and row.get("branca") == record.get("branca"):
                score += 4
            if row.get("sottobranca") and row.get("sottobranca") == record.get("sottobranca"):
                score += 5
            if row.get("source_system") == record.get("source_system"):
                score += 2
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: (item[0], item[1].get("data_deposito", "")), reverse=True)
        return [dict(item[1]) for item in scored[:limit]]

    def salva(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = self._normalize_record(payload)
        judgments = list(self._data.get("judgments", []))
        replaced = False
        for idx, row in enumerate(judgments):
            if row.get("id") == record["id"]:
                judgments[idx] = record
                replaced = True
                break
        if not replaced:
            judgments.append(record)
        self._data["judgments"] = judgments
        self._sync_practice_links(record)
        self._store_text_version(
            record["id"],
            payload.get("text_original")
            or "\n\n".join(
                item
                for item in [
                    record.get("massima", ""),
                    record.get("principio_diritto", ""),
                    record.get("abstract", ""),
                ]
                if str(item or "").strip()
            ),
        )
        self._sync_record_to_corpus(record, payload=payload)
        self._save()
        return record

    def salva_da_form(self, form: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(form or {})
        payload["norme_citate"] = _split_multi(payload.get("norme_citate", ""))
        payload["parole_chiave"] = _split_multi(payload.get("parole_chiave", ""))
        payload["fascicoli_collegati"] = _split_multi(payload.get("fascicoli_collegati", ""))
        payload["collegamenti_precedenti"] = _split_multi(payload.get("collegamenti_precedenti", ""))
        payload["collegamenti_norme"] = _split_multi(payload.get("collegamenti_norme", ""))
        return self.salva(payload)

    def importa_da_materiale(
        self,
        *,
        source_id: str = "",
        source_url: str = "",
        pasted_text: str = "",
        file_name: str = "",
        file_bytes: bytes | None = None,
        hints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = str(source_url or "").strip()
        raw_text = str(pasted_text or "")
        uploaded_name = str(file_name or "").strip()
        uploaded_bytes = bytes(file_bytes or b"")
        extracted_text = self._extract_material_text(uploaded_name, uploaded_bytes) if uploaded_bytes else ""
        material_text = (raw_text.strip() + "\n\n" + extracted_text.strip()).strip()
        if not material_text and not url:
            raise ValueError("Inserisci almeno testo, file o URL del materiale da importare.")

        detected_source = source_id or self._detect_source_from_url(url) or ""
        if not detected_source or detected_source == "manuale_interno":
            lowered = f"{url}\n{material_text}".lower()
            detected_source = "simpliciter_cliente" if "simpliciter" in lowered else "manuale_interno"
        source = self._source(detected_source) or self._source("manuale_interno")
        candidate_blocks = self._extract_material_candidates(material_text, source, source_url=url)
        if not candidate_blocks:
            candidate_blocks = [
                {
                    "titolo": self._material_title(material_text, url, source.nome if source else "Scheda importata"),
                    "url_origine": url,
                    "abstract": _truncate(material_text, 320),
                    "massima": _truncate(material_text, 220),
                    "identificatore_stabile": f"{detected_source}:{_sha1((url or uploaded_name or 'materiale') + '|' + material_text[:400])}",
                }
            ]

        imported = 0
        updated = 0
        saved_records: List[Dict[str, Any]] = []
        for candidate in candidate_blocks:
            payload = self.empty_record(detected_source)
            payload.update(candidate)
            payload["source_system"] = detected_source
            payload["url_origine"] = payload.get("url_origine") or url
            payload["text_original"] = payload.get("text_original") or material_text
            payload["raw_text"] = material_text
            payload["raw_json"] = {"source_url": url, "file_name": uploaded_name} if (url or uploaded_name) else {}
            payload["mime_type"] = "text/plain" if material_text else "application/octet-stream"
            payload["note_redazionali"] = payload.get("note_redazionali") or self._import_note(source, uploaded_name)
            for key, value in (hints or {}).items():
                if value and key in payload and not payload.get(key):
                    payload[key] = value
            result = self._upsert_import_payload(payload)
            saved_records.append(result["record"])
            if result["created"]:
                imported += 1
            else:
                updated += 1

        run = {
            "id": uuid.uuid4().hex,
            "source_id": detected_source,
            "source_label": source.nome if source else detected_source,
            "checked_at": _now_iso(),
            "status": "import_assistito",
            "imported": imported,
            "updated": updated,
            "candidates": len(candidate_blocks),
            "message": "Importazione assistita completata da materiale fornito dal cliente.",
        }
        self._append_sync_run(run)
        self._save()
        return {"ok": True, "imported": imported, "updated": updated, "records": saved_records, "run": run}

    def importa_da_url(
        self,
        url: str,
        *,
        source_id: str = "",
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        cleaned_url = str(url or "").strip()
        if not cleaned_url:
            raise ValueError("URL ufficiale mancante.")
        detected_source = source_id or self._detect_source_from_url(cleaned_url) or "manuale_interno"
        source = self._source(detected_source)
        title = cleaned_url
        abstract = ""
        ecli = ""
        text = ""
        if source and source.access_mode == "pubblico":
            response = self._fetch(cleaned_url, request_get=request_get)
            text = response.get("text", "")
            title = response.get("title") or title
            abstract = _truncate(response.get("summary") or text, 320)
            ecli = _extract_ecli(text)
        elif source and source.access_mode == "open_data":
            response = self._fetch(cleaned_url, request_get=request_get)
            text = response.get("text", "")
            title = response.get("title") or title
            abstract = _truncate(response.get("summary") or text, 320)
            ecli = _extract_ecli(text)
        mime_type = str((response or {}).get("content_type") or "text/html")
        raw_json: Any = {}
        if "json" in mime_type and text:
            try:
                raw_json = json.loads(text)
            except Exception:
                raw_json = {}
        payload = self.empty_record(detected_source)
        payload.update(
            {
                "titolo": title,
                "url_origine": cleaned_url,
                "abstract": abstract,
                "massima": abstract if len(abstract) <= 220 else "",
                "ecli": ecli,
                "numero_provvedimento": _extract_case_reference(text or title) or _extract_number(text or title),
                "data_deposito": _extract_date(text or title),
                "data_decisione": _extract_date(title),
                "identificatore_stabile": ecli or f"{detected_source}:{_sha1(cleaned_url)}",
                "text_original": text,
                "raw_text": text,
                "raw_json": raw_json,
                "mime_type": mime_type,
                "note_redazionali": (
                    "Scheda creata da recupero URL ufficiale. "
                    + ("Completare classificazione e metadati processuali." if not source or source.access_mode != "pubblico" else "")
                ).strip(),
            }
        )
        result = self._upsert_import_payload(payload)
        self._save()
        return result["record"]

    def sync_sources(
        self,
        *,
        source_ids: Optional[List[str]] = None,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        selected = [self._source(source_id) for source_id in (source_ids or [source.id for source in SOURCE_SPECS])]
        selected = [source for source in selected if source]
        runs: List[Dict[str, Any]] = []
        imported_total = 0
        for source in selected:
            run = self._sync_source(source, request_get=request_get)
            imported_total += int(run.get("imported", 0) or 0)
            runs.append(run)
        updated_total = sum(int(run.get("updated", 0) or 0) for run in runs)
        self._save()
        return {
            "ok": True,
            "runs": runs,
            "imported_total": imported_total,
            "updated_total": updated_total,
            "changed_total": imported_total + updated_total,
        }

    def _sync_source(
        self,
        source: FonteGiurisprudenziale,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        started_at = _now_iso()
        run_id = uuid.uuid4().hex
        if not source.supports_auto_sync:
            run = {
                "id": run_id,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": started_at,
                "started_at": started_at,
                "ended_at": started_at,
                "status": "handoff_richiesto",
                "items_found": 0,
                "items_imported": 0,
                "items_updated": 0,
                "items_skipped": 0,
                "imported": 0,
                "updated": 0,
                "candidates": 0,
                "message": "La fonte richiede recupero assistito o consultazione dal portale ufficiale.",
            }
            self._append_sync_run(run)
            return run

        try:
            candidates = self._sync_candidates_for_source(source, request_get=request_get)
            imported = 0
            updated = 0
            skipped = 0
            for candidate in candidates[:MAX_SYNC_ITEMS]:
                result = self._upsert_synced_candidate(source, candidate, started_at, run_id=run_id)
                if result == "created":
                    imported += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1
            ended_at = _now_iso()
            run = {
                "id": run_id,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": ended_at,
                "started_at": started_at,
                "ended_at": ended_at,
                "status": "ok" if candidates else "vuoto",
                "items_found": len(candidates),
                "items_imported": imported,
                "items_updated": updated,
                "items_skipped": skipped,
                "imported": imported,
                "updated": updated,
                "candidates": len(candidates),
                "message": "Recupero completato." if candidates else "Nessuna decisione pubblica individuata nella pagina ufficiale monitorata.",
            }
        except Exception as exc:
            ended_at = _now_iso()
            run = {
                "id": run_id,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": ended_at,
                "started_at": started_at,
                "ended_at": ended_at,
                "status": "errore",
                "items_found": 0,
                "items_imported": 0,
                "items_updated": 0,
                "items_skipped": 0,
                "imported": 0,
                "updated": 0,
                "candidates": 0,
                "message": _truncate(str(exc), 240),
            }
        self._append_sync_run(run)
        return run

    def _append_sync_run(self, run: Dict[str, Any]) -> None:
        runs = list(self._data.get("ingestion_runs", []))
        runs.append(run)
        if len(runs) > MAX_SYNC_RUNS:
            runs = runs[-MAX_SYNC_RUNS:]
        self._data["ingestion_runs"] = runs
        self._data["sync_runs"] = list(runs)

    def _upsert_synced_candidate(
        self,
        source: FonteGiurisprudenziale,
        candidate: Dict[str, Any],
        checked_at: str,
        *,
        run_id: str = "",
    ) -> str:
        stable_id = candidate.get("identificatore_stabile") or candidate.get("ecli") or f"{source.id}:{_sha1(candidate.get('url', '') or candidate.get('title', ''))}"
        judgments = list(self._data.get("judgments", []))
        existing_idx = next((idx for idx, row in enumerate(judgments) if row.get("identificatore_stabile") == stable_id), None)
        payload = self.empty_record(source.id)
        payload.update(
            {
                "titolo": candidate.get("title", source.nome),
                "abstract": candidate.get("summary", ""),
                "massima": candidate.get("massima", candidate.get("summary", "")),
                "principio_diritto": candidate.get("principio_diritto", ""),
                "principio_sintetico": candidate.get("principio_diritto", ""),
                "tipo_provvedimento": candidate.get("tipo_provvedimento", ""),
                "numero_provvedimento": candidate.get("numero_provvedimento", ""),
                "data_deposito": candidate.get("data_deposito", ""),
                "data_decisione": candidate.get("data_decisione", ""),
                "ecli": candidate.get("ecli", ""),
                "identificatore_stabile": stable_id,
                "url_origine": candidate.get("url", source.official_url),
                "url_pagina_ufficiale": candidate.get("url", source.official_url),
                "url_pdf_ufficiale": candidate.get("pdf_url", candidate.get("url", "") if str(candidate.get("url", "")).lower().endswith(".pdf") else ""),
                "organo_giudicante": candidate.get("organo_giudicante", source.nome),
                "ufficio": candidate.get("ufficio", source.nome),
                "sezione": candidate.get("sezione", ""),
                "area": candidate.get("area", source.default_area),
                "grado": candidate.get("grado", source.default_grade),
                "rito": candidate.get("rito", ""),
                "materia": candidate.get("materia", ""),
                "esito": candidate.get("esito", ""),
                "parole_chiave": _split_multi(candidate.get("keywords", [])),
                "stato_verifica_fonte": candidate.get(
                    "stato_verifica",
                    "parzialmente_verificata" if candidate.get("url") and source.access_mode in {"pubblico", "open_data"} else "da_verificare",
                ),
                "fonte_ufficiale_confermata": bool(candidate.get("url")) and source.access_mode in {"pubblico", "open_data"},
                "pdf_ufficiale_presente": bool(candidate.get("pdf_url")) or str(candidate.get("url", "")).lower().endswith(".pdf"),
                "note_redazionali": candidate.get(
                    "note_redazionali",
                    "Scheda generata da recupero automatico leggero. Verificare classificazione giuridica e massima.",
                ),
                "ultimo_sync_at": checked_at,
            }
        )
        if existing_idx is not None:
            current = dict(judgments[existing_idx])
            current.update({k: v for k, v in payload.items() if v not in ("", [], {})})
            record = self._normalize_record(current)
            judgments[existing_idx] = record
            self._data["judgments"] = judgments
            self._store_raw_document(source, candidate, record["id"], checked_at, run_id=run_id)
            self._store_text_version(record["id"], candidate.get("text_original") or payload.get("massima") or payload.get("abstract"))
            self._sync_practice_links(record)
            self._sync_record_to_corpus(record, payload=payload)
            return "updated"
        saved = self._normalize_record(payload)
        judgments.append(saved)
        self._data["judgments"] = judgments
        self._store_raw_document(source, candidate, saved["id"], checked_at, run_id=run_id)
        self._store_text_version(saved["id"], candidate.get("text_original") or payload.get("massima") or payload.get("abstract"))
        self._sync_practice_links(saved)
        self._sync_record_to_corpus(saved, payload=payload)
        return "created"

    def _sync_candidates_for_source(
        self,
        source: FonteGiurisprudenziale,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        if source.id == "openga":
            return self._fetch_openga_candidates(source, request_get=request_get)
        if source.id == "corte_costituzionale":
            return self._fetch_corte_costituzionale_candidates(source, request_get=request_get)
        response = self._fetch(source.search_url or source.official_url, request_get=request_get)
        return self._extract_candidates(response["document"], response["final_url"], source)

    def _store_raw_document(
        self,
        source: FonteGiurisprudenziale,
        candidate: Dict[str, Any],
        judgment_id: str,
        downloaded_at: str,
        *,
        run_id: str = "",
    ) -> None:
        raw_text = str(candidate.get("raw_text") or "")
        raw_json = candidate.get("raw_json")
        raw_json_text = json.dumps(raw_json, ensure_ascii=False) if isinstance(raw_json, (dict, list)) else str(raw_json or "")
        digest_seed = raw_json_text or raw_text or str(candidate.get("url") or candidate.get("external_id") or judgment_id)
        sha256 = hashlib.sha256(digest_seed.encode("utf-8", errors="ignore")).hexdigest()
        rows = list(self._data.get("raw_documents", []))
        existing_idx = next((idx for idx, row in enumerate(rows) if row.get("sha256") == sha256 and row.get("judgment_id") == judgment_id), None)
        payload = {
            "id": rows[existing_idx]["id"] if existing_idx is not None else uuid.uuid4().hex,
            "judgment_id": judgment_id,
            "source_id": source.id,
            "run_id": run_id,
            "external_id": candidate.get("external_id") or candidate.get("identificatore_stabile") or "",
            "source_url": candidate.get("url", source.official_url),
            "mime_type": candidate.get("mime_type") or ("application/json" if raw_json_text else "text/plain"),
            "raw_text": raw_text,
            "raw_json": raw_json_text,
            "file_path": candidate.get("file_path", ""),
            "sha256": sha256,
            "downloaded_at": downloaded_at,
        }
        if existing_idx is not None:
            rows[existing_idx] = payload
        else:
            rows.append(payload)
        self._data["raw_documents"] = rows

    def _store_text_version(self, judgment_id: str, text_original: str, *, language: str = "it") -> None:
        text = _clean_spaces(str(text_original or ""))
        if not text:
            return
        cleaned = text
        rows = self.judgment_text_versions(judgment_id)
        latest = rows[0] if rows else None
        if latest and _clean_spaces(latest.get("text_cleaned", "")) == cleaned:
            return
        version = max((int(row.get("version") or 0) for row in rows), default=0) + 1
        payload = {
            "id": uuid.uuid4().hex,
            "judgment_id": judgment_id,
            "text_original": text,
            "text_cleaned": cleaned,
            "text_structured": "",
            "language": language,
            "version": version,
            "created_at": _now_iso(),
        }
        all_rows = list(self._data.get("judgment_texts", []))
        all_rows.append(payload)
        per_judgment = [row for row in all_rows if row.get("judgment_id") == judgment_id]
        if len(per_judgment) > MAX_TEXT_VERSIONS:
            removable = sorted(per_judgment, key=lambda item: (item.get("version", 0), item.get("created_at", "")))[:-MAX_TEXT_VERSIONS]
            removable_ids = {row["id"] for row in removable}
            all_rows = [row for row in all_rows if row.get("id") not in removable_ids]
        self._data["judgment_texts"] = all_rows

    def _sync_practice_links(self, record: Dict[str, Any]) -> None:
        wanted = _split_multi(record.get("fascicoli_collegati") or [])
        current = [dict(row) for row in self._data.get("practice_judgments", [])]
        kept = [row for row in current if row.get("judgment_id") != record.get("id")]
        for practice_id in wanted:
            kept.append(
                {
                    "id": uuid.uuid4().hex,
                    "practice_id": practice_id,
                    "judgment_id": record.get("id"),
                    "link_type": "collegata",
                    "note": "",
                    "relevance_score": "",
                    "created_at": _now_iso(),
                }
            )
        self._data["practice_judgments"] = kept

    def _fetch_json_payload(
        self,
        url: str,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Any:
        getter = request_get or requests.get
        response = getter(
            url,
            headers={"User-Agent": USER_AGENT_GIURISPRUDENZA},
            timeout=self.timeout,
            allow_redirects=True,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise RuntimeError(f"Fonte ufficiale non raggiungibile ({status_code}).")
        return json.loads(bytes(getattr(response, "content", b"") or b"").decode("utf-8", errors="ignore") or "{}")

    def _fetch_binary(
        self,
        url: str,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> bytes:
        getter = request_get or requests.get
        response = getter(
            url,
            headers={"User-Agent": USER_AGENT_GIURISPRUDENZA},
            timeout=max(self.timeout, 40),
            allow_redirects=True,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise RuntimeError(f"Download ufficiale non riuscito ({status_code}).")
        return bytes(getattr(response, "content", b"") or b"")

    def _fetch_openga_candidates(
        self,
        source: FonteGiurisprudenziale,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        payload = self._fetch_json_payload(source.search_url, request_get=request_get)
        results = list(((payload or {}).get("result") or {}).get("results") or [])
        current_year = date.today().year
        packages = sorted(results, key=lambda item: str(item.get("metadata_modified") or ""), reverse=True)
        candidates: List[Dict[str, Any]] = []
        seen = set()
        for package in packages:
            if len(candidates) >= MAX_SYNC_ITEMS * 3:
                break
            for resource in package.get("resources") or []:
                if len(candidates) >= MAX_SYNC_ITEMS * 3:
                    break
                format_name = str(resource.get("format") or "").upper()
                resource_name = str(resource.get("name") or "")
                resource_url = str(resource.get("url") or "")
                if format_name != "JSON" or not resource_url:
                    continue
                year_match = re.search(r"\b(20\d{2})\b", resource_name)
                resource_year = int(year_match.group(1)) if year_match else current_year
                if resource_year < current_year - 1:
                    continue
                rows = self._fetch_json_payload(resource_url, request_get=request_get)
                if not isinstance(rows, list):
                    continue
                sorted_rows = sorted(rows, key=lambda item: str(item.get("DATA_PUBBLICAZIONE") or ""), reverse=True)
                for item in sorted_rows[:12]:
                    external_id = f"{item.get('CODICE_SEDE', '')}:{item.get('NUMERO_PROVVEDIMENTO', '')}:{item.get('DATA_PUBBLICAZIONE', '')}"
                    if not external_id or external_id in seen:
                        continue
                    seen.add(external_id)
                    office_name = _clean_spaces(str(item.get("NOME_SEDE") or source.nome))
                    oggetto = _clean_spaces(str(item.get("OGGETTO_RICORSO") or ""))
                    tipo = _clean_spaces(str(item.get("TIPO_PROVVEDIMENTO") or "Sentenza")).title()
                    titolo = f"{tipo} n. {item.get('NUMERO_PROVVEDIMENTO', '')} - {item.get('NOME_SEDE', '')}".strip(" -")
                    candidates.append(
                        {
                            "external_id": external_id,
                            "title": titolo,
                            "summary": _truncate(oggetto or f"{item.get('TIPO_RICORSO', '')} - {item.get('ESITO_PROVVEDIMENTO', '')}", 320),
                            "massima": _truncate(oggetto, 220),
                            "url": resource_url,
                            "data_deposito": item.get("DATA_PUBBLICAZIONE", ""),
                            "data_decisione": item.get("DATA_PUBBLICAZIONE", ""),
                            "tipo_provvedimento": tipo,
                            "numero_provvedimento": str(item.get("NUMERO_PROVVEDIMENTO") or ""),
                            "organo_giudicante": office_name,
                            "ufficio": office_name,
                            "grado": _infer_openga_grade(office_name),
                            "sezione": _clean_spaces(str(item.get("NOME_SEZIONE") or "")),
                            "materia": _clean_spaces(str(item.get("TIPO_RICORSO") or "")),
                            "rito": _clean_spaces(str(item.get("TIPO_UDIENZA") or "")),
                            "esito": _clean_spaces(str(item.get("ESITO_PROVVEDIMENTO") or "")),
                            "keywords": _split_multi(
                                [
                                    item.get("NOME_SEDE", ""),
                                    item.get("NOME_SEZIONE", ""),
                                    item.get("TIPO_RICORSO", ""),
                                    item.get("ESITO_PROVVEDIMENTO", ""),
                                    "OpenGA",
                                ]
                            ),
                            "raw_json": item,
                            "raw_text": oggetto,
                            "mime_type": "application/json",
                            "identificatore_stabile": f"openga:{external_id}",
                            "note_redazionali": "Scheda generata da dataset ufficiale OpenGA. Verificare classificazione interna, tema e sottobranca.",
                        }
                    )
        return candidates

    def _fetch_corte_costituzionale_candidates(
        self,
        source: FonteGiurisprudenziale,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> List[Dict[str, Any]]:
        page = self._fetch(source.search_url or source.official_url, request_get=request_get)
        html_text = str(page.get("text") or "")
        match = re.search(
            r"https://dati\.cortecostituzionale\.it/opendata/distribuzione/pronunce/P_json2001_oggi\.zip",
            html_text,
            re.IGNORECASE,
        )
        zip_url = match.group(0) if match else "https://dati.cortecostituzionale.it/opendata/distribuzione/pronunce/P_json2001_oggi.zip"
        outer_bytes = self._fetch_binary(zip_url, request_get=request_get)
        outer_zip = zipfile.ZipFile(io.BytesIO(outer_bytes))
        year_candidates = [date.today().year, date.today().year - 1]
        inner_name = next((name for year in year_candidates for name in outer_zip.namelist() if f"{year}" in name), outer_zip.namelist()[-1])
        inner_zip = zipfile.ZipFile(io.BytesIO(outer_zip.read(inner_name)))
        json_name = inner_zip.namelist()[0]
        raw_json_text = inner_zip.read(json_name).decode("cp1252", errors="ignore")
        payload = json.loads(raw_json_text)
        records = list(payload.get("elenco_pronunce") or [])
        records.sort(key=lambda item: _parse_iso_date(item.get("data_deposito", "")).replace("-", ""), reverse=True)
        candidates: List[Dict[str, Any]] = []
        for item in records[: MAX_SYNC_ITEMS * 3]:
            numero = str(item.get("numero_pronuncia") or "")
            anno = str(item.get("anno_pronuncia") or "")
            deposito = _parse_iso_date(str(item.get("data_deposito") or ""))
            decisione = _parse_iso_date(str(item.get("data_decisione") or ""))
            ecli = _clean_spaces(str(item.get("ecli") or ""))
            tipologia = self._map_corte_cost_tipo(str(item.get("tipologia_pronuncia") or ""))
            epigrafe = _clean_spaces(str(item.get("epigrafe") or ""))
            testo = _clean_spaces(str(item.get("testo") or ""))
            dispositivo = _clean_spaces(str(item.get("dispositivo") or ""))
            title = f"{tipologia} n. {numero}/{anno} - Corte costituzionale".strip()
            candidates.append(
                {
                    "external_id": f"{anno}:{numero}",
                    "title": title,
                    "summary": _truncate(epigrafe or dispositivo or testo, 320),
                    "massima": _truncate(epigrafe or dispositivo, 220),
                    "principio_diritto": _truncate(dispositivo, 260),
                    "url": source.official_url,
                    "ecli": ecli,
                    "data_deposito": deposito,
                    "data_decisione": decisione,
                    "tipo_provvedimento": tipologia,
                    "numero_provvedimento": f"{numero}/{anno}" if numero and anno else numero,
                    "organo_giudicante": source.nome,
                    "ufficio": source.nome,
                    "grado": "Corte costituzionale",
                    "keywords": _split_multi([source.nome, "pronuncia", item.get("presidente", ""), item.get("relatore_pronuncia", "")]),
                    "raw_json": item,
                    "raw_text": testo,
                    "text_original": testo,
                    "mime_type": "application/json",
                    "identificatore_stabile": ecli or f"corte_costituzionale:{anno}:{numero}",
                    "note_redazionali": "Scheda generata da dataset open data della Corte costituzionale. Verificare classificazione e collegamenti normativi.",
                }
            )
        return candidates

    def _map_corte_cost_tipo(self, value: str) -> str:
        mapping = {"S": "Sentenza", "O": "Ordinanza", "D": "Decreto"}
        return mapping.get(_clean_spaces(value).upper(), _clean_spaces(value).title() or "Pronuncia")

    def _fetch(self, url: str, *, request_get: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
        getter = request_get or requests.get
        response = getter(
            url,
            headers={"User-Agent": USER_AGENT_GIURISPRUDENZA},
            timeout=self.timeout,
            allow_redirects=True,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise RuntimeError(f"Fonte ufficiale non raggiungibile ({status_code}).")
        final_url = str(getattr(response, "url", url) or url)
        content = bytes(getattr(response, "content", b"") or b"")
        content_type = str(getattr(response, "headers", {}).get("content-type", "") or "").lower()
        if "pdf" in content_type or final_url.lower().endswith(".pdf"):
            text = self._extract_material_text(final_url, content)
            synthetic_html = (
                "<html><head><title>"
                + _html_escape(final_url.rsplit("/", 1)[-1] or "documento.pdf")
                + "</title></head><body><main>"
                + _html_escape(text)
                + "</main></body></html>"
            )
            document = lxml_html.fromstring(synthetic_html.encode("utf-8"))
            title = self._material_title(text, final_url, "Documento ufficiale")
            return {
                "final_url": final_url,
                "content": content,
                "content_type": content_type,
                "text": text,
                "document": document,
                "title": title,
                "summary": _truncate(text, 320),
            }
        if "json" in content_type or final_url.lower().endswith(".json"):
            text = content.decode("utf-8", errors="ignore")
            synthetic_html = (
                "<html><head><title>"
                + _html_escape(final_url.rsplit("/", 1)[-1] or "documento.json")
                + "</title></head><body><main>"
                + _html_escape(text[:8000])
                + "</main></body></html>"
            )
            document = lxml_html.fromstring(synthetic_html.encode("utf-8"))
            return {
                "final_url": final_url,
                "content": content,
                "content_type": content_type,
                "text": text,
                "document": document,
                "title": final_url.rsplit("/", 1)[-1] or final_url,
                "summary": _truncate(text, 320),
            }
        if "xml" in content_type or final_url.lower().endswith(".xml") or content.lstrip().startswith(b"<rss"):
            try:
                document = lxml_etree.fromstring(content)
            except Exception as exc:
                raise RuntimeError(f"Feed ufficiale non leggibile: {exc}") from exc
            title = _clean_spaces(" ".join(document.xpath("//channel/title/text()") or document.xpath("//title/text()"))) or final_url
            summary = _clean_spaces(" ".join(document.xpath("//channel/description/text()") or document.xpath("//description/text()"))) or title
            return {
                "final_url": final_url,
                "content": content,
                "content_type": content_type,
                "text": content.decode("utf-8", errors="ignore"),
                "document": document,
                "title": title,
                "summary": _truncate(summary, 320),
            }
        text = content.decode("utf-8", errors="ignore")
        try:
            document = lxml_html.fromstring(content)
        except Exception as exc:
            raise RuntimeError(f"Pagina ufficiale non leggibile: {exc}") from exc
        title = _clean_spaces(" ".join(document.xpath("//title/text()"))) or final_url
        summary = _clean_spaces(" ".join(document.xpath("//main//text()")[:40])) or _clean_spaces(" ".join(document.xpath("//body//text()")[:40]))
        return {
            "final_url": final_url,
            "content": content,
            "content_type": content_type,
            "text": text,
            "document": document,
            "title": title,
            "summary": summary,
        }

    def _extract_candidates(self, document: Any, base_url: str, source: FonteGiurisprudenziale) -> List[Dict[str, Any]]:
        if document is not None and getattr(document, "tag", "").lower() == "rss":
            return self._extract_rss_candidates(document, source)
        if document is not None and document.xpath("//item"):
            return self._extract_rss_candidates(document, source)
        if source.id == "curia":
            return self._extract_curia_candidates(document, base_url, source)
        candidates: List[Dict[str, Any]] = []
        seen = set()
        keywords = [keyword.lower() for keyword in (source.link_keywords or [])]
        for anchor in document.xpath("//a[@href]"):
            href = str(anchor.get("href") or "").strip()
            if not href or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            text = _clean_spaces(" ".join(anchor.xpath(".//text()")))
            if len(text) < 5:
                continue
            url = urljoin(base_url, href)
            bag = f"{text} {url}".lower()
            if keywords and not any(keyword in bag for keyword in keywords):
                continue
            if url in seen:
                continue
            seen.add(url)
            parent = anchor.getparent()
            context_node = parent if parent is not None else anchor
            context = _clean_spaces(" ".join(context_node.xpath(".//text()")))
            title = text
            summary = _truncate(context or text, 220)
            candidate = {
                "title": title,
                "summary": summary,
                "url": url,
                "ecli": _extract_ecli(context),
                "numero_provvedimento": _extract_case_reference(context or title) or _extract_number(context or title),
                "data_deposito": _extract_date(context or title),
                "data_decisione": _extract_date(title),
                "tipo_provvedimento": self._guess_tipo(title + " " + context),
                "keywords": [source.nome, source.giurisdizione, source.default_area],
            }
            candidates.append(candidate)
        return candidates

    def _guess_tipo(self, text: str) -> str:
        lowered = (text or "").lower()
        for label in TIPI_PROVVEDIMENTO:
            if label in lowered:
                return label.title()
        english_aliases = {
            "judgment": "Sentenza",
            "decision": "Decisione",
            "order": "Ordinanza",
            "opinion": "Parere",
        }
        for token, mapped in english_aliases.items():
            if token in lowered:
                return mapped
        return ""

    def _extract_rss_candidates(self, document: Any, source: FonteGiurisprudenziale) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen = set()
        for item in document.xpath("//item"):
            title = _clean_spaces(" ".join(item.xpath("./title/text()")))
            url = self._normalize_hudoc_link(_clean_spaces(" ".join(item.xpath("./link/text()"))))
            summary = _truncate(_clean_spaces(" ".join(item.xpath("./description/text()"))) or title, 220)
            pub_date = _clean_spaces(" ".join(item.xpath("./pubDate/text()")))
            if not title or not url or url in seen:
                continue
            seen.add(url)
            combined = f"{title} {summary}"
            candidates.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "ecli": _extract_ecli(combined),
                    "numero_provvedimento": _extract_case_reference(combined) or _extract_number(combined),
                    "data_deposito": _extract_date(pub_date),
                    "data_decisione": _extract_date(pub_date),
                    "tipo_provvedimento": self._guess_tipo(combined),
                    "keywords": [source.nome, source.giurisdizione, source.default_area],
                }
            )
        return candidates

    def _extract_curia_candidates(self, document: Any, base_url: str, source: FonteGiurisprudenziale) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen = set()
        skip_titles = {"latest judgments and opinions", "yearly selection of major judgments"}
        for anchor in document.xpath("//a[@href]"):
            href = str(anchor.get("href") or "").strip()
            if not href or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            text = _clean_spaces(" ".join(anchor.xpath(".//text()")))
            url = urljoin(base_url, href)
            lowered_text = text.lower()
            if not text or lowered_text in skip_titles or re.fullmatch(r"[A-Z]{2}", text or ""):
                continue
            if len(text) < 18 and "recent-judgment" not in url.lower():
                continue
            bag = f"{text} {url}".lower()
            if not (
                "recent-judgment" in bag
                or ("judgment" in bag and "case" in bag)
                or "opinion" in bag
                or re.search(r"/cp\d+.*(?:it|en)\.pdf$", url, re.IGNORECASE)
            ):
                continue
            if url in seen:
                continue
            seen.add(url)
            context_node = anchor.getparent() if anchor.getparent() is not None else anchor
            if getattr(context_node, "tag", "").lower() in {"body", "html"}:
                context_node = anchor
            context = _clean_spaces(" ".join(context_node.xpath(".//text()")))
            combined = f"{text} {context}"
            candidates.append(
                {
                    "title": text,
                    "summary": _truncate(context or text, 220),
                    "url": url,
                    "ecli": _extract_ecli(combined),
                    "numero_provvedimento": _extract_case_reference(combined) or _extract_number(combined),
                    "data_deposito": _extract_date(combined) or _extract_date(url.replace("/", " ")),
                    "data_decisione": _extract_date(text) or _extract_date(combined),
                    "tipo_provvedimento": self._guess_tipo(combined),
                    "keywords": [source.nome, source.giurisdizione, source.default_area],
                }
            )
        return candidates

    def _normalize_hudoc_link(self, url: str) -> str:
        raw = _clean_spaces(url)
        if "itemid" not in raw:
            return raw
        match = re.search(r'"itemid"\s*:\s*\[\s*"([^"]+)"\s*\]', raw)
        if not match:
            return raw
        return f"https://hudoc.echr.coe.int/?i={match.group(1)}"

    def _source(self, source_id: str) -> Optional[FonteGiurisprudenziale]:
        return next((source for source in SOURCE_SPECS if source.id == source_id), None)

    def _detect_source_from_url(self, url: str) -> str:
        host = (urlparse(url or "").hostname or "").lower()
        if "simpliciter.ai" in host:
            return "simpliciter_cliente"
        if "openga.giustizia-amministrativa.it" in host:
            return "openga"
        if "cortedicassazione" in host:
            return "cassazione"
        if "cortecostituzionale" in host:
            return "corte_costituzionale"
        if "giustizia-amministrativa" in host:
            return "giustizia_amministrativa"
        if "giustiziatributaria" in host:
            return "giustizia_tributaria"
        if "curia.europa" in host:
            return "curia"
        if "hudoc.echr" in host or "echr.coe" in host:
            return "hudoc"
        if "corteconti" in host:
            return "corte_conti"
        if "pst.giustizia" in host or "giustizia.it" in host:
            return "merito_civile_bdp"
        return "manuale_interno"

    def _extract_material_text(self, file_name: str, file_bytes: bytes) -> str:
        if not file_bytes:
            return ""
        lowered = (file_name or "").lower()
        if lowered.endswith(".pdf"):
            pages: List[str] = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages[:80]:
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(text)
            return "\n\n".join(pages)
        if lowered.endswith(".html") or lowered.endswith(".htm"):
            try:
                document = lxml_html.fromstring(file_bytes)
                return _clean_spaces(" ".join(document.xpath("//main//text()") or document.xpath("//body//text()")))
            except Exception:
                return file_bytes.decode("utf-8", errors="ignore")
        return file_bytes.decode("utf-8", errors="ignore")

    def _extract_material_candidates(
        self,
        text: str,
        source: Optional[FonteGiurisprudenziale],
        *,
        source_url: str = "",
    ) -> List[Dict[str, Any]]:
        raw = str(text or "").strip()
        if not raw:
            return []
        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        blocks: List[str] = []
        paragraphs = [chunk.strip() for chunk in re.split(r"\n\s*\n+", normalized) if chunk.strip()]
        if len(paragraphs) > 1:
            for chunk in paragraphs:
                if _extract_ecli(chunk) or _extract_number(chunk) or self._guess_tipo(chunk) or len(chunk) > 180:
                    blocks.append(chunk)
        else:
            marker = re.compile(
                r"(?im)^(?=(?:.*\bECLI:[A-Z]{2}:)|(?:.*\b(?:sentenza|ordinanza|decreto|decisione|parere)\b(?:.*\bn\.?\s*\d+)?))"
            )
            starts = [match.start() for match in marker.finditer(normalized)]
            if len(starts) >= 2:
                for idx, start in enumerate(starts):
                    end = starts[idx + 1] if idx + 1 < len(starts) else len(normalized)
                    chunk = normalized[start:end].strip()
                    if len(chunk) >= 80:
                        blocks.append(chunk)
            else:
                blocks = [normalized]

        source_name = source.nome if source else "Scheda importata"
        candidates: List[Dict[str, Any]] = []
        for ordinal, block in enumerate(blocks[:MAX_SYNC_ITEMS], start=1):
            summary = _truncate(block, 320)
            title = self._material_title(block, source_url, source_name, ordinal=ordinal)
            deposito = _extract_date(block)
            payload = {
                "titolo": title,
                "abstract": summary,
                "massima": self._extract_massima(block, fallback=summary),
                "principio_diritto": self._extract_principio(block),
                "numero_provvedimento": _extract_case_reference(block or title) or _extract_number(block or title),
                "data_deposito": deposito,
                "data_decisione": _extract_date(title) or deposito,
                "tipo_provvedimento": self._guess_tipo(block),
                "organo_giudicante": self._extract_organo(block, source),
                "ufficio": self._extract_organo(block, source),
                "ecli": _extract_ecli(block),
                "url_origine": source_url,
                "identificatore_stabile": _extract_ecli(block)
                or f"{(source.id if source else 'manuale_interno')}:{_sha1((source_url or '') + '|' + title + '|' + block[:600])}",
                "parole_chiave": self._material_keywords(block, source),
                "note_redazionali": self._import_note(source, ""),
            }
            candidates.append(payload)
        return candidates

    def _material_title(self, text: str, source_url: str, source_name: str, ordinal: int = 1) -> str:
        lines = [line.strip(" -\t") for line in str(text or "").splitlines() if line.strip()]
        for line in lines[:6]:
            cleaned = _clean_spaces(line)
            if len(cleaned) >= 12 and (self._guess_tipo(cleaned) or _extract_ecli(cleaned) or _extract_number(cleaned)):
                return cleaned[:180]
        if source_url:
            tail = urlparse(source_url).path.rsplit("/", 1)[-1].strip() or "sentenza"
            return f"{source_name} - {tail}"[:180]
        return f"{source_name} - scheda importata {ordinal}"

    def _extract_massima(self, text: str, fallback: str = "") -> str:
        match = re.search(r"massima[:\s-]+(.+?)(?:principio di diritto[:\s-]+|$)", text or "", re.IGNORECASE | re.DOTALL)
        if match:
            return _truncate(match.group(1), 220)
        return _truncate(fallback or text, 220)

    def _extract_principio(self, text: str) -> str:
        match = re.search(r"principio di diritto[:\s-]+(.+?)(?:massima[:\s-]+|$)", text or "", re.IGNORECASE | re.DOTALL)
        if match:
            return _truncate(match.group(1), 260)
        return ""

    def _extract_organo(self, text: str, source: Optional[FonteGiurisprudenziale]) -> str:
        lowered = (text or "").lower()
        patterns = [
            ("Corte di Cassazione", ["cassazione"]),
            ("Corte costituzionale", ["corte costituzionale", "cortecostituzionale"]),
            ("Consiglio di Stato", ["consiglio di stato"]),
            ("TAR", ["tar "]),
            ("Corte di Giustizia Tributaria", ["corte di giustizia tributaria", "giustizia tributaria"]),
            ("Corte EDU", ["cedu", "hudoc", "echr"]),
            ("Corte di Giustizia UE", ["curia", "corte di giustizia"]),
            ("Corte dei Conti", ["corte dei conti"]),
        ]
        for label, tokens in patterns:
            if any(token in lowered for token in tokens):
                return label
        return source.nome if source and source.nome != "Inserimento redazionale interno" else ""

    def _material_keywords(self, text: str, source: Optional[FonteGiurisprudenziale]) -> List[str]:
        bag = _split_multi([
            source.nome if source else "",
            source.giurisdizione if source else "",
            source.default_area if source else "",
            _extract_ecli(text),
        ])
        lowered = (text or "").lower()
        topic_map = {
            "consenso informato": ["consenso informato"],
            "appalti": ["appalti", "subappalto", "soccorso istruttorio"],
            "accesso agli atti": ["accesso agli atti", "accesso difensivo"],
            "cartella": ["cartella", "riscossione", "estratto di ruolo"],
            "responsabilitÃ  medica": ["responsabilitÃ  medica", "sanitaria"],
            "licenziamento": ["licenziamento"],
            "stupefacenti": ["stupefacenti"],
        }
        for label, tokens in topic_map.items():
            if any(token in lowered for token in tokens):
                bag.append(label)
        return _split_multi(bag)

    def _import_note(self, source: Optional[FonteGiurisprudenziale], file_name: str) -> str:
        details = []
        if file_name:
            details.append(f"file {file_name}")
        if source and source.id == "simpliciter_cliente":
            details.append("materiale cliente Simpliciter")
        suffix = f" ({', '.join(details)})" if details else ""
        return (
            "Scheda creata da import assistito su materiale fornito dal cliente"
            f"{suffix}. Verificare classificazione, completezza dei metadati e utilizzabilitÃ  redazionale."
        )

    def _upsert_import_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stable = str(payload.get("identificatore_stabile") or payload.get("ecli") or "").strip()
        judgments = list(self._data.get("judgments", []))
        existing_idx = next((idx for idx, row in enumerate(judgments) if stable and row.get("identificatore_stabile") == stable), None)
        if existing_idx is None and payload.get("url_origine") and payload.get("titolo"):
            existing_idx = next(
                (
                    idx
                    for idx, row in enumerate(judgments)
                    if row.get("url_origine") == payload.get("url_origine") and row.get("titolo") == payload.get("titolo")
                ),
                None,
            )
        if existing_idx is not None:
            current = dict(judgments[existing_idx])
            merged = dict(current)
            for key, value in payload.items():
                if value not in ("", [], {}, None):
                    merged[key] = value
            merged["id"] = current.get("id")
            record = self._normalize_record(merged)
            judgments[existing_idx] = record
            self._data["judgments"] = judgments
            self._store_raw_document(
                self._source(record.get("source_system") or "") or self._source("manuale_interno"),
                {
                    "external_id": stable,
                    "url": payload.get("url_origine") or record.get("url_origine"),
                    "raw_text": payload.get("raw_text") or payload.get("text_original") or "",
                    "raw_json": payload.get("raw_json") or {},
                    "mime_type": payload.get("mime_type") or "text/plain",
                },
                record["id"],
                _now_iso(),
            )
            self._store_text_version(record["id"], payload.get("text_original") or payload.get("raw_text") or record.get("abstract") or "")
            self._sync_practice_links(record)
            self._sync_record_to_corpus(record, payload=payload)
            return {"created": False, "record": record}
        record = self._normalize_record(payload)
        judgments.append(record)
        self._data["judgments"] = judgments
        self._store_raw_document(
            self._source(record.get("source_system") or "") or self._source("manuale_interno"),
            {
                "external_id": stable or record.get("identificatore_stabile"),
                "url": payload.get("url_origine") or record.get("url_origine"),
                "raw_text": payload.get("raw_text") or payload.get("text_original") or "",
                "raw_json": payload.get("raw_json") or {},
                "mime_type": payload.get("mime_type") or "text/plain",
            },
            record["id"],
            _now_iso(),
        )
        self._store_text_version(record["id"], payload.get("text_original") or payload.get("raw_text") or record.get("abstract") or "")
        self._sync_practice_links(record)
        self._sync_record_to_corpus(record, payload=payload)
        return {"created": True, "record": record}

    def _normalize_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = _now_iso()
        source_id = str(payload.get("source_system") or "manuale_interno").strip()
        source = self._source(source_id)
        existing = self.get(str(payload.get("id") or "")) or {}
        title = _clean_spaces(str(payload.get("titolo") or payload.get("title") or "Sentenza senza titolo"))
        source_label = source.nome if source else source_id
        stable = str(payload.get("identificatore_stabile") or payload.get("ecli") or "").strip()
        if not stable:
            stable = f"{source_id}:{_sha1((payload.get('url_origine') or '') + '|' + title)}"
        record = {
            "id": str(payload.get("id") or existing.get("id") or uuid.uuid4().hex),
            "titolo": title,
            "source_system": source_id,
            "source_label": source_label,
            "giurisdizione": _clean_spaces(str(payload.get("giurisdizione") or existing.get("giurisdizione") or (source.giurisdizione if source else ""))),
            "organo_giudicante": _clean_spaces(str(payload.get("organo_giudicante") or payload.get("ufficio") or existing.get("organo_giudicante") or "")),
            "ufficio": _clean_spaces(str(payload.get("ufficio") or existing.get("ufficio") or "")),
            "grado": _clean_spaces(str(payload.get("grado") or existing.get("grado") or (source.default_grade if source else ""))),
            "sezione": _clean_spaces(str(payload.get("sezione") or existing.get("sezione") or "")),
            "numero_provvedimento": _clean_spaces(str(payload.get("numero_provvedimento") or existing.get("numero_provvedimento") or "")),
            "data_decisione": _parse_iso_date(str(payload.get("data_decisione") or existing.get("data_decisione") or "")),
            "data_deposito": _parse_iso_date(str(payload.get("data_deposito") or existing.get("data_deposito") or "")),
            "tipo_provvedimento": _clean_spaces(str(payload.get("tipo_provvedimento") or existing.get("tipo_provvedimento") or "")),
            "area": _clean_spaces(str(payload.get("area") or existing.get("area") or (source.default_area if source else ""))),
            "branca": _clean_spaces(str(payload.get("branca") or existing.get("branca") or "")),
            "sottobranca": _clean_spaces(str(payload.get("sottobranca") or existing.get("sottobranca") or "")),
            "microtema": _clean_spaces(str(payload.get("microtema") or existing.get("microtema") or "")),
            "rito": _clean_spaces(str(payload.get("rito") or existing.get("rito") or "")),
            "materia": _clean_spaces(str(payload.get("materia") or existing.get("materia") or "")),
            "norme_citate": _split_multi(payload.get("norme_citate") or existing.get("norme_citate") or []),
            "parole_chiave": _split_multi(payload.get("parole_chiave") or existing.get("parole_chiave") or []),
            "massima": _clean_spaces(str(payload.get("massima") or existing.get("massima") or "")),
            "principio_diritto": _clean_spaces(str(payload.get("principio_diritto") or existing.get("principio_diritto") or "")),
            "principio_sintetico": _clean_spaces(str(payload.get("principio_sintetico") or existing.get("principio_sintetico") or payload.get("principio_diritto") or "")),
            "abstract": _clean_spaces(str(payload.get("abstract") or existing.get("abstract") or "")),
            "esito": _clean_spaces(str(payload.get("esito") or existing.get("esito") or "")),
            "orientamento": _clean_spaces(str(payload.get("orientamento") or existing.get("orientamento") or "")),
            "rilevanza_pratica": _clean_spaces(str(payload.get("rilevanza_pratica") or existing.get("rilevanza_pratica") or "")),
            "uso_nel_software": _clean_spaces(str(payload.get("uso_nel_software") or existing.get("uso_nel_software") or "")),
            "ecli": _clean_spaces(str(payload.get("ecli") or existing.get("ecli") or "")),
            "identificatore_stabile": stable,
            "url_origine": _clean_spaces(str(payload.get("url_origine") or existing.get("url_origine") or (source.official_url if source else ""))),
            "url_pagina_ufficiale": _clean_spaces(str(payload.get("url_pagina_ufficiale") or existing.get("url_pagina_ufficiale") or payload.get("url_origine") or existing.get("url_origine") or (source.official_url if source else ""))),
            "url_pdf_ufficiale": _clean_spaces(str(payload.get("url_pdf_ufficiale") or existing.get("url_pdf_ufficiale") or "")),
            "stato_verifica_fonte": _clean_spaces(str(payload.get("stato_verifica_fonte") or existing.get("stato_verifica_fonte") or "da_verificare")),
            "fonte_ufficiale_confermata": bool(payload.get("fonte_ufficiale_confermata") if payload.get("fonte_ufficiale_confermata") is not None else existing.get("fonte_ufficiale_confermata")),
            "pdf_ufficiale_presente": bool(payload.get("pdf_ufficiale_presente") if payload.get("pdf_ufficiale_presente") is not None else existing.get("pdf_ufficiale_presente")),
            "collegamenti_precedenti": _split_multi(payload.get("collegamenti_precedenti") or existing.get("collegamenti_precedenti") or []),
            "collegamenti_norme": _split_multi(payload.get("collegamenti_norme") or existing.get("collegamenti_norme") or []),
            "precedenti_citati": _split_multi(payload.get("precedenti_citati") or existing.get("precedenti_citati") or []),
            "fascicoli_collegati": _split_multi(payload.get("fascicoli_collegati") or existing.get("fascicoli_collegati") or []),
            "note_redazionali": _clean_spaces(str(payload.get("note_redazionali") or existing.get("note_redazionali") or "")),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "ultimo_sync_at": _clean_spaces(str(payload.get("ultimo_sync_at") or existing.get("ultimo_sync_at") or "")),
            "anno": _extract_year(str(payload.get("data_deposito") or payload.get("data_decisione") or existing.get("data_deposito") or existing.get("data_decisione") or "")),
            "access_mode": source.access_mode if source else "",
        }
        return record

    def _corpus_payload_from_record(
        self,
        record: Dict[str, Any],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw_payload = dict(payload or {})
        source = self._source(record.get("source_system") or "") or self._source("manuale_interno")
        number = _clean_spaces(record.get("numero_provvedimento"))
        year = 0
        if "/" in number:
            tail = number.split("/")[-1].strip()
            if len(tail) == 4 and tail.isdigit():
                year = int(tail)
            elif len(tail) == 2 and tail.isdigit():
                year = int(f"20{tail}")
        source_kind = "ufficiale" if source and source.access_mode in {"pubblico", "open_data"} else "import_manuale"
        stato_verifica = _clean_spaces(raw_payload.get("stato_verifica_fonte") or record.get("stato_verifica_fonte") or "")
        if not stato_verifica:
            if source and source.access_mode in {"pubblico", "open_data"} and record.get("url_pagina_ufficiale"):
                stato_verifica = "parzialmente_verificata"
            else:
                stato_verifica = "da_verificare"
        official_page = _clean_spaces(raw_payload.get("url_pagina_ufficiale") or record.get("url_pagina_ufficiale") or record.get("url_origine") or "")
        official_pdf = _clean_spaces(raw_payload.get("url_pdf_ufficiale") or record.get("url_pdf_ufficiale") or "")
        if not official_pdf and official_page.lower().endswith(".pdf"):
            official_pdf = official_page
        fonte_confermata = bool(
            raw_payload.get("fonte_ufficiale_confermata")
            if raw_payload.get("fonte_ufficiale_confermata") is not None
            else record.get("fonte_ufficiale_confermata")
        )
        if not fonte_confermata and source and source.access_mode in {"pubblico", "open_data"} and official_page:
            fonte_confermata = True
        documents: List[Dict[str, Any]] = []
        if official_page:
            doc_type = "pdf_ufficiale" if official_pdf else ("html_ufficiale" if official_page.startswith("http") else "altro")
            documents.append(
                {
                    "tipo_documento": doc_type,
                    "titolo": record.get("titolo") or "Documento ufficiale",
                    "url_origine": official_pdf or official_page,
                    "mime_type": "application/pdf" if official_pdf else "text/html",
                    "ufficiale": True,
                    "valido": True,
                }
            )
        for raw_item in self.raw_documents(record.get("id"))[:1]:
            documents.append(
                {
                    "tipo_documento": "allegato",
                    "titolo": record.get("titolo") or "Documento importato",
                    "url_origine": raw_item.get("source_url") or "",
                    "mime_type": raw_item.get("mime_type") or "",
                    "sha256": raw_item.get("sha256") or "",
                    "testo_estratto": raw_item.get("raw_text") or "",
                    "testo_estratto_chars": len(raw_item.get("raw_text") or ""),
                    "ufficiale": False,
                    "valido": True,
                }
            )
        principles = []
        if record.get("principio_diritto"):
            principles.append(
                {
                    "testo": record.get("principio_diritto"),
                    "formulazione_breve": record.get("principio_sintetico") or record.get("principio_diritto"),
                    "ufficiale": fonte_confermata,
                    "livello_affidabilita": 80 if fonte_confermata else 55,
                    "tema": record.get("microtema") or record.get("branca"),
                    "sotto_tema": record.get("sottobranca"),
                    "principale": True,
                }
            )
        massime = []
        if record.get("massima"):
            massime.append(
                {
                    "testo": record.get("massima"),
                    "sintetica": record.get("massima"),
                    "ufficiale": fonte_confermata,
                    "fonte_massima": source.nome if source else "",
                    "stato_verifica": stato_verifica,
                    "principale": True,
                }
            )
        norms = [
            {
                "tipo_norma": "norma",
                "testo_riferimento": ref,
                "primaria": idx == 0,
            }
            for idx, ref in enumerate(_split_multi(record.get("norme_citate") or []))
        ]
        precedents = [
            {
                "riferimento_testuale": ref,
                "tipo_relazione": "citata",
                "verificata": fonte_confermata,
            }
            for ref in _split_multi(record.get("precedenti_citati") or record.get("collegamenti_precedenti") or [])
        ]
        verifications = []
        if official_page:
            verifications.append(
                {
                    "tipo_verifica": "esistenza_url",
                    "esito": "ok" if fonte_confermata else "warning",
                    "dettaglio": official_page,
                }
            )
        if official_pdf:
            verifications.append(
                {
                    "tipo_verifica": "pdf_presente",
                    "esito": "ok",
                    "dettaglio": official_pdf,
                }
            )
        return {
            "uuid_interno": record.get("identificatore_stabile") or record.get("id"),
            "fonte": {
                "codice": source.id if source else record.get("source_system") or "manuale_interno",
                "nome": source.nome if source else record.get("source_label") or "Fonte interna",
                "tipo_fonte": source_kind,
                "ente": record.get("organo_giudicante") or (source.nome if source else ""),
                "url_home": source.official_url if source else official_page,
                "url_ricerca": source.search_url if source else "",
            },
            "ecli": record.get("ecli"),
            "numero_sentenza": number,
            "anno_sentenza": year,
            "organo_giudicante": record.get("organo_giudicante") or record.get("ufficio") or (source.nome if source else ""),
            "sezione": record.get("sezione"),
            "data_decisione": record.get("data_decisione"),
            "data_deposito": record.get("data_deposito"),
            "area_diritto": record.get("area"),
            "materia_principale": record.get("branca") or record.get("materia"),
            "sottomateria_principale": record.get("sottobranca") or record.get("microtema"),
            "rito": record.get("rito"),
            "grado_giudizio": record.get("grado"),
            "tipo_provvedimento": (record.get("tipo_provvedimento") or "provvedimento").lower(),
            "titolo": record.get("titolo"),
            "oggetto": record.get("materia") or record.get("microtema"),
            "abstract": record.get("abstract"),
            "principio_sintetico": record.get("principio_sintetico") or record.get("principio_diritto"),
            "massima_ufficiale": record.get("massima"),
            "testo_integrale": record.get("testo_integrale") or record.get("testo_normalizzato") or "",
            "esito": record.get("esito"),
            "orientamento": record.get("orientamento") or "non_classificato",
            "rilevanza": 80 if record.get("uso_nel_software") == "precedente forte" else 55,
            "precedente_guida": record.get("uso_nel_software") in {"precedente forte", "citabile in atto"},
            "sezioni_unite": "sezioni unite" in _clean_spaces(record.get("sezione")).lower(),
            "nomofilattica": bool(record.get("ecli")) and "cass" in _clean_spaces(record.get("ecli")).lower(),
            "stato_verifica": stato_verifica,
            "fonte_ufficiale_confermata": fonte_confermata,
            "pdf_ufficiale_presente": bool(official_pdf),
            "testo_integrale_presente": bool(record.get("testo_integrale") or record.get("testo_normalizzato")),
            "url_pagina_ufficiale": official_page,
            "url_pdf_ufficiale": official_pdf,
            "url_html_ufficiale": official_page if official_page and not official_pdf else "",
            "documenti": documents,
            "massime": massime,
            "principi_diritto": principles,
            "norme": norms,
            "precedenti": precedents,
            "verifiche": verifications,
        }

    def _sync_record_to_corpus(
        self,
        record: Dict[str, Any],
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._corpus.salva_sentenza(self._corpus_payload_from_record(record, payload=payload))


__all__ = [
    "GestioneGiurisprudenza",
    "SOURCE_SPECS",
    "TASSONOMIA_GIURISPRUDENZA",
    "ORIENTAMENTI",
    "RILEVANZE_PRATICHE",
    "USI_NEL_SOFTWARE",
    "TIPI_PROVVEDIMENTO",
    "tassonomia_flat",
]

