from __future__ import annotations

import copy
import hashlib
import io
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from lxml import html as lxml_html
import pdfplumber

from pct import cache as _cache
from pct.legal_intelligence import FONTI_UFFICIALI

USER_AGENT_GIURISPRUDENZA = "HACS-Giurisprudenza/1.0"
MAX_SYNC_ITEMS = 12
MAX_SYNC_RUNS = 300


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


def _extract_ecli(text: str) -> str:
    match = re.search(r"(ECLI:[A-Z]{2}:[A-Z0-9_.:]+)", text or "", re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _truncate(text: str, limit: int = 280) -> str:
    cleaned = _clean_spaces(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _source_url(existing_id: str, fallback: str) -> str:
    src = FONTI_UFFICIALI.get(existing_id)
    return src.official_url if src else fallback


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
    link_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SOURCE_SPECS: List[FonteGiurisprudenziale] = [
    FonteGiurisprudenziale(
        id="cassazione",
        nome="Corte di Cassazione",
        giurisdizione="Ordinaria",
        coverage="Legittimità, sentenze, ordinanze, massimario e principi di diritto.",
        official_url=_source_url("cassazione", "https://www.cortedicassazione.it/"),
        search_url="https://www.cortedicassazione.it/it/massimario.page",
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Fonte primaria per legittimità civile e penale; utile per principi di diritto e orientamenti consolidati.",
        badge="Fonte primaria",
        icon="bi-building-check",
        search_label="Apri Cassazione",
        supports_auto_sync=True,
        default_grade="Cassazione",
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
        link_keywords=["tribunale", "corte d'appello", "sentenza", "ordinanza"],
    ),
    FonteGiurisprudenziale(
        id="corte_costituzionale",
        nome="Corte costituzionale",
        giurisdizione="Costituzionale",
        coverage="Pronunce, massime, ultimo deposito e schede ufficiali.",
        official_url=_source_url("corte_costituzionale", "https://www.cortecostituzionale.it/"),
        search_url="https://www.cortecostituzionale.it/",
        access_mode="pubblico",
        sync_mode="automatico_leggero",
        note="Fonte primaria per sentenze, ordinanze e massime costituzionali.",
        badge="Fonte primaria",
        icon="bi-columns-gap",
        search_label="Apri Corte costituzionale",
        supports_auto_sync=True,
        default_area="Costituzionale",
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
        link_keywords=["decisione", "massima", "sentenza", "tributaria"],
    ),
    FonteGiurisprudenziale(
        id="curia",
        nome="CURIA",
        giurisdizione="UE / CEDU",
        coverage="Corte di Giustizia e Tribunale dell'Unione europea con ricerca giurisprudenziale.",
        official_url="https://curia.europa.eu/jcms/jcms/j_6/it/",
        search_url="https://curia.europa.eu/juris/recherche.jsf?language=it",
        access_mode="pubblico",
        sync_mode="recupero_assistito",
        note="Motore ufficiale UE; utile per ECLI, giurisprudenza su appalti, concorrenza, consumatori e fiscalità.",
        badge="Fonte europea",
        icon="bi-globe-europe-africa",
        search_label="Apri CURIA",
        supports_auto_sync=False,
        default_area="UE / CEDU",
        link_keywords=["judgment", "order", "ecli", "curia", "case"],
    ),
    FonteGiurisprudenziale(
        id="hudoc",
        nome="HUDOC / CEDU",
        giurisdizione="UE / CEDU",
        coverage="Sentenze e decisioni della Corte EDU con filtri per Stato, articolo e materia.",
        official_url="https://hudoc.echr.coe.int/",
        search_url="https://hudoc.echr.coe.int/",
        access_mode="pubblico",
        sync_mode="recupero_assistito",
        note="Fonte ufficiale CEDU; utile per equo processo, proprietà, vita privata e familiare.",
        badge="Fonte europea",
        icon="bi-globe2",
        search_label="Apri HUDOC",
        supports_auto_sync=False,
        default_area="UE / CEDU",
        link_keywords=["judgment", "decision", "article", "italy", "echr"],
    ),
    FonteGiurisprudenziale(
        id="corte_conti",
        nome="Corte dei Conti",
        giurisdizione="Contabile",
        coverage="Giurisprudenza contabile, responsabilità erariale e sezioni regionali.",
        official_url=_source_url("corte_conti", "https://www.corteconti.it/"),
        search_url="https://www.corteconti.it/",
        access_mode="pubblico",
        sync_mode="recupero_assistito",
        note="Fonte specialistica per responsabilità amministrativa e contabile.",
        badge="Fonte specialistica",
        icon="bi-safe2",
        supports_auto_sync=False,
        default_area="Contabile",
        link_keywords=["sentenza", "decisione", "responsabilità", "erariale"],
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
            "HACS non esegue scraping della banca dati Simpliciter. "
            "Importa solo materiali, output o file che il cliente ha già ottenuto legittimamente nel proprio account."
        ),
        badge="Import assistito",
        icon="bi-inbox",
        search_label="Apri Simpliciter",
        supports_auto_sync=False,
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
        "description": "Contenzioso civile, merito e legittimità.",
        "branches": [
            {"title": "Obbligazioni e contratti", "subbranches": ["Compravendita", "Appalto", "Locazione", "Mandato", "Leasing", "Mediazione", "Mutuo", "Fideiussione", "Clausole vessatorie", "Nullità / annullabilità / risoluzione / rescissione", "Inadempimento", "Prescrizione", "Prova del contratto"]},
            {"title": "Responsabilità civile", "subbranches": ["RC auto", "Responsabilità medica", "Responsabilità professionale", "Danno da cose in custodia", "Danno da insidia", "Diffamazione", "Danno non patrimoniale", "Perdita di chance", "Danno parentale"]},
            {"title": "Diritti reali", "subbranches": ["Usucapione", "Servitù", "Comunione", "Possesso", "Azione di rivendica"]},
            {"title": "Condominio", "subbranches": ["Ripartizione spese", "Delibere assembleari", "Impugnazioni", "Innovazioni"]},
            {"title": "Locazioni", "subbranches": ["Morosità", "Rinnovo", "Canone", "Recesso", "Sfratto"]},
            {"title": "Successioni", "subbranches": ["Legittima", "Testamento", "Collazione", "Riduzione", "Divisione ereditaria"]},
            {"title": "Famiglia e persone", "subbranches": ["Separazione", "Divorzio", "Affidamento", "Assegno di mantenimento", "Stato della persona"]},
            {"title": "Lavoro", "subbranches": ["Licenziamento", "Demansionamento", "Mobbing", "Differenze retributive", "Appalto e somministrazione"]},
            {"title": "Previdenza e assistenza", "subbranches": ["Pensione", "Invalidità", "Contributi", "Prestazioni assistenziali"]},
            {"title": "Societario e commerciale", "subbranches": ["Impugnazione delibere", "Amministratori", "Soci", "Recesso", "Bilancio"]},
            {"title": "Bancario e finanziario", "subbranches": ["Anatocismo", "Usura", "Mutui", "Derivati", "Segnalazioni a sofferenza"]},
            {"title": "Assicurazioni", "subbranches": ["Polizza", "Sinistro", "Manleva", "RCA", "Azione diretta"]},
            {"title": "Esecuzioni", "subbranches": ["Pignoramento", "Opposizioni", "Vendita forzata", "Assegnazione", "Terzo pignorato"]},
            {"title": "Procedure concorsuali / crisi d'impresa", "subbranches": ["Fallimento", "Liquidazione giudiziale", "Concordato", "Composizione negoziata", "Revocatorie"]},
            {"title": "Volontaria giurisdizione", "subbranches": ["Amministrazione di sostegno", "Tutele", "Autorizzazioni", "Nomine"]},
            {"title": "Proprietà industriale e intellettuale", "subbranches": ["Marchi", "Brevetti", "Concorrenza sleale", "Diritto d'autore"]},
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
            {"title": "Stupefacenti", "subbranches": ["Detenzione", "Spaccio", "Associazione", "Lieve entità"]},
            {"title": "Misure cautelari", "subbranches": ["Custodia cautelare", "Arresti domiciliari", "Divieti e obblighi", "Esigenze cautelari"]},
            {"title": "Esecuzione penale", "subbranches": ["Ordine di esecuzione", "Sospensione", "Misure alternative"]},
            {"title": "Ordinamento penitenziario", "subbranches": ["Permessi", "Liberazione anticipata", "Affidamento", "Detenzione domiciliare"]},
            {"title": "Procedura penale", "subbranches": ["Notificazioni", "Nullità", "Prova", "Impugnazioni", "Abbreviato"]},
            {"title": "Misure di prevenzione", "subbranches": ["Personali", "Patrimoniali", "Confisca", "Sequestro"]},
            {"title": "Responsabilità da reato degli enti ex d.lgs. 231/2001", "subbranches": ["Modelli organizzativi", "Interesse o vantaggio", "Reati presupposto", "Sanzioni"]},
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
            {"title": "Pubblico impiego", "subbranches": ["Sanzioni disciplinari", "Progressioni", "Mobilità", "Mansioni"]},
            {"title": "Concorsi", "subbranches": ["Bando", "Valutazione titoli", "Prove", "Scorrimento graduatorie"]},
            {"title": "Ambiente", "subbranches": ["VIA", "AIA", "Bonifiche", "Rifiuti"]},
            {"title": "Espropriazione", "subbranches": ["Indennità", "Occupazione", "Dichiarazione di pubblica utilità"]},
            {"title": "Sanità", "subbranches": ["Accreditamenti", "Responsabilità sanitaria pubblica", "Farmacie"]},
            {"title": "Università e scuola", "subbranches": ["Graduatorie", "Abilitazioni", "Trasferimenti", "Tasse universitarie"]},
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
            {"title": "Processo tributario", "subbranches": ["Ammissibilità ricorso", "Termini", "Notifiche", "Sospensione", "Appello"]},
            {"title": "Abuso del diritto / elusione", "subbranches": ["Operazioni elusive", "Riqualificazione", "Onere della prova"]},
            {"title": "Transfer pricing / fiscalità d'impresa", "subbranches": ["Prezzi di trasferimento", "Stabile organizzazione", "Documentazione"]},
            {"title": "Agevolazioni e crediti d'imposta", "subbranches": ["Bonus edilizi", "Ricerca e sviluppo", "Industria 4.0"]},
        ],
    },
    {
        "id": "costituzionale",
        "title": "Costituzionale",
        "icon": "bi-columns-gap",
        "description": "Pronunce e questioni costituzionali.",
        "branches": [
            {"title": "Diritti fondamentali", "subbranches": ["Uguaglianza", "Salute", "Difesa", "Libertà personale"]},
            {"title": "Riparto Stato-Regioni", "subbranches": ["Competenze legislative", "Leale collaborazione", "Finanza regionale"]},
            {"title": "Processo costituzionale", "subbranches": ["Incidente di costituzionalità", "Conflitti", "Referendum"]},
            {"title": "Ordinamento giudiziario", "subbranches": ["Status magistrati", "CSM", "Organizzazione"]},
            {"title": "Materia penale", "subbranches": ["Riserva di legge", "Irretroattività", "Proporzionalità pena"]},
            {"title": "Materia civile", "subbranches": ["Tutela giurisdizionale", "Famiglia", "Patrimonio"]},
            {"title": "Materia tributaria", "subbranches": ["Capacità contributiva", "Ragionevolezza", "Sanzioni"]},
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
            {"title": "Lavoro", "subbranches": ["Parità di trattamento", "Orario", "Trasferimenti"]},
            {"title": "Privacy / dati personali", "subbranches": ["GDPR", "Sorveglianza", "Trattamenti illeciti"]},
            {"title": "Asilo e immigrazione", "subbranches": ["Protezione internazionale", "Ricongiungimento", "Espulsioni"]},
            {"title": "Fiscalità", "subbranches": ["IVA", "Aiuti fiscali", "Doppia imposizione"]},
            {"title": "Equo processo", "subbranches": ["Ragionevole durata", "Contraddittorio", "Imparzialità"]},
            {"title": "Proprietà", "subbranches": ["Espropriazione", "Vincoli", "Prot. 1 art. 1"]},
            {"title": "Vita privata e familiare", "subbranches": ["Art. 8 CEDU", "Minori", "Protezione dati"]},
        ],
    },
    {
        "id": "contabile",
        "title": "Contabile",
        "icon": "bi-safe2",
        "description": "Giurisprudenza della Corte dei Conti e responsabilità erariale.",
        "branches": [
            {"title": "Responsabilità amministrativa", "subbranches": ["Danno erariale", "Colpa grave", "Prescrizione", "Quantificazione"]},
            {"title": "Contabilità pubblica", "subbranches": ["Enti locali", "Società partecipate", "Controlli", "Pareri"]},
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
        self.timeout = timeout
        self._data: Dict[str, Any] = {"judgments": [], "sync_runs": []}
        self._load()

    def _load(self) -> None:
        try:
            raw = _cache.load(self.db_path, default={}) or {}
            self._data["judgments"] = list(raw.get("judgments") or [])
            self._data["sync_runs"] = list(raw.get("sync_runs") or [])
        except Exception:
            self._data = {"judgments": [], "sync_runs": []}

    def _save(self) -> None:
        _cache.save(self.db_path, self._data, indent=2)

    def catalogo_fonti(self) -> List[Dict[str, Any]]:
        latest_runs = self._latest_runs()
        counts: Dict[str, int] = {}
        for row in self._data.get("judgments", []):
            source_id = row.get("source_system") or "manuale_interno"
            counts[source_id] = counts.get(source_id, 0) + 1
        out: List[Dict[str, Any]] = []
        for source in SOURCE_SPECS:
            item = source.to_dict()
            item["judgment_count"] = counts.get(source.id, 0)
            item["last_run"] = latest_runs.get(source.id)
            out.append(item)
        return out

    def tassonomia(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(TASSONOMIA_GIURISPRUDENZA)

    def statistiche(self) -> Dict[str, Any]:
        judgments = list(self._data.get("judgments", []))
        source_ids = {item.get("source_system") for item in judgments if item.get("source_system")}
        aree = {item.get("area") for item in judgments if item.get("area")}
        return {
            "totale_sentenze": len(judgments),
            "fonti_attive": len(SOURCE_SPECS),
            "fonti_usate": len(source_ids),
            "aree_coperte": len(aree),
            "sync_pubblici": len([source for source in SOURCE_SPECS if source.supports_auto_sync]),
            "bozze_da_classificare": len([row for row in judgments if not row.get("branca") or not row.get("sottobranca")]),
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
        for row in self._data.get("sync_runs", []):
            source_id = row.get("source_id")
            current = latest.get(source_id)
            if current is None or str(row.get("checked_at", "")) >= str(current.get("checked_at", "")):
                latest[source_id] = row
        return latest

    def recent_sync_runs(self, limit: int = 12) -> List[Dict[str, Any]]:
        rows = sorted(self._data.get("sync_runs", []), key=lambda item: item.get("checked_at", ""), reverse=True)
        return rows[:limit]

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
            "abstract": "",
            "esito": "",
            "orientamento": "",
            "rilevanza_pratica": "",
            "uso_nel_software": "",
            "ecli": "",
            "identificatore_stabile": "",
            "url_origine": source.official_url if source else "",
            "collegamenti_precedenti": [],
            "collegamenti_norme": [],
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

    def get(self, judgment_id: str) -> Optional[Dict[str, Any]]:
        for row in self._data.get("judgments", []):
            if row.get("id") == judgment_id:
                return dict(row)
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
        payload = self.empty_record(detected_source)
        payload.update(
            {
                "titolo": title,
                "url_origine": cleaned_url,
                "abstract": abstract,
                "massima": abstract if len(abstract) <= 220 else "",
                "ecli": ecli,
                "numero_provvedimento": _extract_number(text or title),
                "data_deposito": _extract_date(text or title),
                "data_decisione": _extract_date(title),
                "identificatore_stabile": ecli or f"{detected_source}:{_sha1(cleaned_url)}",
                "note_redazionali": (
                    "Scheda creata da recupero URL ufficiale. "
                    + ("Completare classificazione e metadati processuali." if not source or source.access_mode != "pubblico" else "")
                ).strip(),
            }
        )
        return self.salva(payload)

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
        self._save()
        return {"ok": True, "runs": runs, "imported_total": imported_total}

    def _sync_source(
        self,
        source: FonteGiurisprudenziale,
        *,
        request_get: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        checked_at = _now_iso()
        if not source.supports_auto_sync:
            run = {
                "id": uuid.uuid4().hex,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": checked_at,
                "status": "handoff_richiesto",
                "imported": 0,
                "candidates": 0,
                "message": "La fonte richiede recupero assistito o consultazione dal portale ufficiale.",
            }
            self._append_sync_run(run)
            return run

        try:
            response = self._fetch(source.search_url or source.official_url, request_get=request_get)
            candidates = self._extract_candidates(response["document"], response["final_url"], source)
            imported = 0
            for candidate in candidates[:MAX_SYNC_ITEMS]:
                saved = self._upsert_synced_candidate(source, candidate, checked_at)
                if saved:
                    imported += 1
            run = {
                "id": uuid.uuid4().hex,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": checked_at,
                "status": "ok" if candidates else "vuoto",
                "imported": imported,
                "candidates": len(candidates),
                "message": "Recupero completato." if candidates else "Nessuna decisione pubblica individuata nella pagina ufficiale monitorata.",
            }
        except Exception as exc:
            run = {
                "id": uuid.uuid4().hex,
                "source_id": source.id,
                "source_label": source.nome,
                "checked_at": checked_at,
                "status": "errore",
                "imported": 0,
                "candidates": 0,
                "message": _truncate(str(exc), 240),
            }
        self._append_sync_run(run)
        return run

    def _append_sync_run(self, run: Dict[str, Any]) -> None:
        runs = list(self._data.get("sync_runs", []))
        runs.append(run)
        if len(runs) > MAX_SYNC_RUNS:
            runs = runs[-MAX_SYNC_RUNS:]
        self._data["sync_runs"] = runs

    def _upsert_synced_candidate(
        self,
        source: FonteGiurisprudenziale,
        candidate: Dict[str, Any],
        checked_at: str,
    ) -> bool:
        stable_id = candidate.get("ecli") or f"{source.id}:{_sha1(candidate.get('url', '') or candidate.get('title', ''))}"
        judgments = list(self._data.get("judgments", []))
        existing_idx = next((idx for idx, row in enumerate(judgments) if row.get("identificatore_stabile") == stable_id), None)
        payload = self.empty_record(source.id)
        payload.update(
            {
                "titolo": candidate.get("title", source.nome),
                "abstract": candidate.get("summary", ""),
                "massima": candidate.get("summary", ""),
                "tipo_provvedimento": candidate.get("tipo_provvedimento", ""),
                "numero_provvedimento": candidate.get("numero_provvedimento", ""),
                "data_deposito": candidate.get("data_deposito", ""),
                "data_decisione": candidate.get("data_decisione", ""),
                "ecli": candidate.get("ecli", ""),
                "identificatore_stabile": stable_id,
                "url_origine": candidate.get("url", source.official_url),
                "organo_giudicante": source.nome,
                "ufficio": source.nome,
                "area": source.default_area,
                "grado": source.default_grade,
                "parole_chiave": _split_multi(candidate.get("keywords", [])),
                "note_redazionali": "Scheda generata da recupero automatico leggero. Verificare classificazione giuridica e massima.",
                "ultimo_sync_at": checked_at,
            }
        )
        if existing_idx is not None:
            current = dict(judgments[existing_idx])
            current.update({k: v for k, v in payload.items() if v not in ("", [], {})})
            current["updated_at"] = _now_iso()
            judgments[existing_idx] = current
            self._data["judgments"] = judgments
            return False
        saved = self._normalize_record(payload)
        judgments.append(saved)
        self._data["judgments"] = judgments
        return True

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
            "text": text,
            "document": document,
            "title": title,
            "summary": summary,
        }

    def _extract_candidates(self, document: Any, base_url: str, source: FonteGiurisprudenziale) -> List[Dict[str, Any]]:
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
                "numero_provvedimento": _extract_number(context or title),
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
        return ""

    def _source(self, source_id: str) -> Optional[FonteGiurisprudenziale]:
        return next((source for source in SOURCE_SPECS if source.id == source_id), None)

    def _detect_source_from_url(self, url: str) -> str:
        host = (urlparse(url or "").hostname or "").lower()
        if "simpliciter.ai" in host:
            return "simpliciter_cliente"
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
                "numero_provvedimento": _extract_number(block or title),
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
            "responsabilità medica": ["responsabilità medica", "sanitaria"],
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
            f"{suffix}. Verificare classificazione, completezza dei metadati e utilizzabilità redazionale."
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
            return {"created": False, "record": record}
        record = self._normalize_record(payload)
        judgments.append(record)
        self._data["judgments"] = judgments
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
            "abstract": _clean_spaces(str(payload.get("abstract") or existing.get("abstract") or "")),
            "esito": _clean_spaces(str(payload.get("esito") or existing.get("esito") or "")),
            "orientamento": _clean_spaces(str(payload.get("orientamento") or existing.get("orientamento") or "")),
            "rilevanza_pratica": _clean_spaces(str(payload.get("rilevanza_pratica") or existing.get("rilevanza_pratica") or "")),
            "uso_nel_software": _clean_spaces(str(payload.get("uso_nel_software") or existing.get("uso_nel_software") or "")),
            "ecli": _clean_spaces(str(payload.get("ecli") or existing.get("ecli") or "")),
            "identificatore_stabile": stable,
            "url_origine": _clean_spaces(str(payload.get("url_origine") or existing.get("url_origine") or (source.official_url if source else ""))),
            "collegamenti_precedenti": _split_multi(payload.get("collegamenti_precedenti") or existing.get("collegamenti_precedenti") or []),
            "collegamenti_norme": _split_multi(payload.get("collegamenti_norme") or existing.get("collegamenti_norme") or []),
            "fascicoli_collegati": _split_multi(payload.get("fascicoli_collegati") or existing.get("fascicoli_collegati") or []),
            "note_redazionali": _clean_spaces(str(payload.get("note_redazionali") or existing.get("note_redazionali") or "")),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "ultimo_sync_at": _clean_spaces(str(payload.get("ultimo_sync_at") or existing.get("ultimo_sync_at") or "")),
            "anno": _extract_year(str(payload.get("data_deposito") or payload.get("data_decisione") or existing.get("data_deposito") or existing.get("data_decisione") or "")),
            "access_mode": source.access_mode if source else "",
        }
        return record


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
