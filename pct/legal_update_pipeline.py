from __future__ import annotations

from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import requests
from lxml import html as lxml_html

from pct.giurisprudenza import GestioneGiurisprudenza
from pct.legal_update_ai import analyze_document
from pct.legal_update_repository import LegalUpdateDbConfig, LegalUpdateRepository
from pct.legal_update_web_verification import verify_legal_update_against_public_sources
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn


RequestGet = Callable[..., Any]

DEFAULT_SOURCE_ROWS: tuple[dict[str, Any], ...] = (
    {
        "name": "Gazzetta Ufficiale",
        "code": "gazzetta_ufficiale",
        "category": "normativa",
        "base_url": "https://www.gazzettaufficiale.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 60,
        "parser_type": "html",
        "notes": "Fonte primaria ufficiale per nuove leggi, decreti e regolamenti.",
    },
    {
        "name": "Normattiva",
        "code": "normattiva",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 360,
        "parser_type": "html",
        "notes": "Testo vigente, storico e multivigente.",
    },
    {
        "name": "Dati Normattiva",
        "code": "dati_normattiva",
        "category": "normativa",
        "base_url": "https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Canale tecnico/open data per integrazione normativa e API Normattiva.",
    },
    {
        "name": "Corte Costituzionale",
        "code": "corte_costituzionale",
        "category": "giurisprudenza",
        "base_url": "https://www.cortecostituzionale.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 120,
        "parser_type": "html",
        "notes": "Sentenze, comunicati e depositi della Corte costituzionale.",
    },
    {
        "name": "Corte dei Conti",
        "code": "corte_conti",
        "category": "giurisprudenza",
        "base_url": "https://www.corteconti.it/Home/Documenti/Sentenze",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": (
            "Presidio ufficiale per giurisprudenza contabile, responsabilita' "
            "erariale e collegamento alla banca dati pubblica della Corte dei Conti."
        ),
    },
    {
        "name": "Cassazione Massimario",
        "code": "cassazione_massimario",
        "category": "giurisprudenza",
        "base_url": "https://www.cortedicassazione.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 180,
        "parser_type": "html",
        "notes": "Massimario e raccolte della Cassazione.",
    },
    {
        "name": "Giustizia Amministrativa",
        "code": "giustizia_amministrativa",
        "category": "giurisprudenza",
        "base_url": "https://www.giustizia-amministrativa.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": False,
        "polling_minutes": 180,
        "parser_type": "html",
        "notes": (
            "Fonte istituzionale diretta mantenuta in osservazione: il sito HTML "
            "pubblico puo' essere instabile per crawler e verifiche SSL. Il presidio "
            "automatico principale usa OpenGA CKAN ufficiale nelle fonti openga_*."
        ),
    },
    {
        "name": "OpenGA Giustizia Amministrativa",
        "code": "openga_giustizia_amministrativa",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Catalogo OpenGA in formato CKAN: dataset e risorse JSON/CSV/XLS/ODS della Giustizia Amministrativa.",
    },
    {
        "name": "Giustizia Amministrativa - Decisioni e pareri",
        "code": "giustizia_amministrativa_decisioni_pareri",
        "category": "giurisprudenza",
        "base_url": "https://www.giustizia-amministrativa.it/dcsnprr",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": False,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": (
            "Pagina pubblica Decisioni e pareri: censita per verifica puntuale, "
            "ma il ciclo automatico resta su OpenGA finche' il canale HTML diretto "
            "non e' stabile per certificato, paginazione e allegati."
        ),
    },
    {
        "name": "OpenGA - Calendario udienze",
        "code": "openga_calendario_udienze",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:calendario-udienze&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per calendari udienze, acquisito dai metadati CKAN e dalle risorse JSON disponibili.",
    },
    {
        "name": "OpenGA - Decreti",
        "code": "openga_decreti",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:decreti&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per decreti della giustizia amministrativa, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Ordinanze",
        "code": "openga_ordinanze",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:ordinanze&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per ordinanze della giustizia amministrativa, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Pareri",
        "code": "openga_pareri",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:pareri&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per pareri della giustizia amministrativa, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Provvedimenti pubblicati",
        "code": "openga_provvedimenti_pubblicati",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:provvedimenti-pubblicati&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per provvedimenti pubblicati, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Ricorsi definiti",
        "code": "openga_ricorsi_definiti",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:ricorsi-definiti&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per ricorsi definiti, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Ricorsi pendenti",
        "code": "openga_ricorsi_pendenti",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:ricorsi-pendenti&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per ricorsi pendenti, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Ricorsi pervenuti",
        "code": "openga_ricorsi_pervenuti",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:ricorsi-pervenuti&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per ricorsi pervenuti, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "OpenGA - Sentenze",
        "code": "openga_sentenze",
        "category": "giurisprudenza",
        "base_url": "https://openga.giustizia-amministrativa.it/api/3/action/package_search?fq=groups:sentenze&rows=200",
        "source_type": "open_data",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "ckan_json",
        "notes": "Gruppo ufficiale OpenGA per sentenze della giustizia amministrativa, acquisito da dataset e risorse JSON/CSV/ODS.",
    },
    {
        "name": "EUR-Lex",
        "code": "eur_lex",
        "category": "ue",
        "base_url": "https://eur-lex.europa.eu/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 360,
        "parser_type": "html",
        "notes": "Normativa e giurisprudenza UE.",
    },
    {
        "name": "Agenzia Entrate",
        "code": "agenzia_entrate",
        "category": "prassi",
        "base_url": "https://www.agenziaentrate.gov.it/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 240,
        "parser_type": "html",
        "notes": "Circolari, risoluzioni, interpelli e provvedimenti.",
    },
    {
        "name": "Ministero del Lavoro",
        "code": "ministero_lavoro",
        "category": "prassi",
        "base_url": "https://www.lavoro.gov.it/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 240,
        "parser_type": "html",
        "notes": "Prassi, decreti e circolari del lavoro.",
    },
    {
        "name": "Ministero del Lavoro - Interpelli",
        "code": "ministero_lavoro_interpelli",
        "category": "prassi",
        "base_url": "https://www.lavoro.gov.it/documenti-e-norme/interpelli/Pagine/default",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Interpelli ufficiali lavoro, previdenza e salute/sicurezza utili per consulenza e contenzioso.",
    },
    {
        "name": "Garante Privacy - newsletter e provvedimenti",
        "code": "garante_privacy",
        "category": "prassi",
        "base_url": "https://www.garanteprivacy.it/home/stampa-comunicazione/newsletter",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Newsletter e provvedimenti del Garante utili per privacy, data breach, marketing, videosorveglianza e lavoro.",
    },
    {
        "name": "ANAC - atti e documenti",
        "code": "anac_documenti",
        "category": "prassi",
        "base_url": "https://www.anticorruzione.it/it/consulta-i-documenti?delta=30&includeDocuments=true&isDocumentSearchPortlet=true",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Delibere, pareri precontenzioso, linee guida e atti ANAC per appalti, anticorruzione e trasparenza.",
    },
    {
        "name": "INPS - circolari",
        "code": "inps_circolari",
        "category": "prassi",
        "base_url": "https://www.inps.it/it/it.rss.circolari.xml",
        "source_type": "rss",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale INPS per circolari su previdenza, lavoro, contributi e prestazioni.",
    },
    {
        "name": "INPS - messaggi",
        "code": "inps_messaggi",
        "category": "prassi",
        "base_url": "https://www.inps.it/it/it.rss.messaggi.xml",
        "source_type": "rss",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale INPS per messaggi operativi utili a lavoro, previdenza e contenzioso assistenziale.",
    },
    {
        "name": "INPS - sentenze",
        "code": "inps_sentenze",
        "category": "giurisprudenza",
        "base_url": "https://www.inps.it/it/it.rss.sentenze.xml",
        "source_type": "rss",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale INPS per sentenze in materia previdenziale e assistenziale.",
    },
    {
        "name": "Curia - Corte di giustizia UE",
        "code": "curia_cgue_rss",
        "category": "ue",
        "base_url": "https://curia.europa.eu/site/rss.jsp?lang=it&secondLang=en",
        "source_type": "rss",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale Curia per pronunce, conclusioni e comunicati della Corte di giustizia dell'Unione europea.",
    },
    {
        "name": "ISTAT - prezzi e rivalutazioni",
        "code": "istat_prezzi",
        "category": "prassi",
        "base_url": "https://www.istat.it/tema/prezzi/feed",
        "source_type": "rss",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale ISTAT per prezzi, indici e comunicazioni utili a rivalutazioni e calcoli economici.",
    },
    {
        "name": "MIMIT - incentivi e imprese",
        "code": "mimit_incentivi",
        "category": "prassi",
        "base_url": "https://www.mimit.gov.it/index.php/it/incentivi-aggiornamenti?format=feed&type=rss",
        "source_type": "rss",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "feed",
        "notes": "Feed ufficiale MIMIT per incentivi, impresa, mercato e misure economiche rilevanti per consulenza societaria.",
    },
    {
        "name": "AGCM - bollettino settimanale",
        "code": "agcm_bollettino",
        "category": "prassi",
        "base_url": "https://www.agcm.it/pubblicazioni/bollettino-settimanale/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Bollettino ufficiale AGCM con provvedimenti su concorrenza, consumatori, pratiche scorrette e segnalazioni.",
    },
    {
        "name": "AGCOM - atti e provvedimenti",
        "code": "agcom_provvedimenti",
        "category": "prassi",
        "base_url": "https://www.agcom.it/provvedimenti",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Provvedimenti ufficiali AGCOM su comunicazioni elettroniche, media, utenti e diritto d'autore online.",
    },
    {
        "name": "Banca d'Italia - normativa di vigilanza",
        "code": "banca_italia_normativa",
        "category": "prassi",
        "base_url": "https://www.bancaditalia.it/compiti/vigilanza/normativa/archivio-norme/",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Archivio ufficiale Banca d'Italia per disposizioni di vigilanza bancaria e finanziaria.",
    },
    {
        "name": "INAIL - istruzioni operative",
        "code": "inail_istruzioni_operative",
        "category": "prassi",
        "base_url": "https://www.inail.it/portale/it/atti-e-documenti/note-provvedimenti-e-istruzioni-operative/istruzioni-operative.html",
        "source_type": "web",
        "trust_class": "B",
        "is_official": True,
        "enabled": False,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Presidio ufficiale INAIL per sicurezza lavoro e premi assicurativi: resta in catalogo, ma non entra nel ciclo notturno finche' il canale non e' acquisibile con stabilita'.",
    },
    {
        "name": "PST Giustizia - download tecnici",
        "code": "pst_giustizia_download",
        "category": "telematico",
        "base_url": "https://pst.giustizia.it/PST/it/download.page",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "File ufficiali del Processo Civile Telematico: schemi, specifiche e pacchetti tecnici da verificare con allegati.",
    },
    {
        "name": "Codice civile",
        "code": "codice_civile",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva del codice civile: obbligazioni, contratti, famiglia, successioni, responsabilita' e condominio.",
    },
    {
        "name": "Codice di procedura civile",
        "code": "codice_procedura_civile",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva per procedura civile, notifiche, termini processuali, opposizioni e decreto ingiuntivo.",
    },
    {
        "name": "Codice penale",
        "code": "codice_penale",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1930-10-19;1398",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva per codice penale e aggiornamenti sostanziali di interesse penale.",
    },
    {
        "name": "Codice di procedura penale",
        "code": "codice_procedura_penale",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva per rito penale, depositi, notifiche e termini del processo penale.",
    },
    {
        "name": "Codice del processo amministrativo",
        "code": "codice_processo_amministrativo",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-07-02;104",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva per rito amministrativo, TAR, Consiglio di Stato, ricorsi e termini PAT.",
    },
    {
        "name": "Codice della strada",
        "code": "codice_strada",
        "category": "normativa",
        "base_url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1992-04-30;285",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": "Presidio Normattiva per circolazione stradale, sanzioni, sinistri e responsabilita' da circolazione.",
    },
    {
        "name": "Studio Cataldi - Codice civile",
        "code": "studiocataldi_codice_civile",
        "category": "normativa_secondaria",
        "base_url": "https://www.studiocataldi.it/codicecivile/",
        "source_type": "web",
        "trust_class": "C",
        "is_official": False,
        "enabled": False,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": (
            "Fonte privata di consultazione rapida: puo' aiutare a orientare la ricerca, "
            "ma il testo vigente va verificato su Normattiva o Gazzetta Ufficiale."
        ),
    },
    {
        "name": "Avvocato Andreani - Codice procedura civile",
        "code": "avvocatoandreani_codice_procedura_civile",
        "category": "normativa_secondaria",
        "base_url": "https://www.avvocatoandreani.it/servizi/codice-procedura-civile.php",
        "source_type": "web",
        "trust_class": "C",
        "is_official": False,
        "enabled": False,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": (
            "Fonte privata di consultazione rapida: utile come controllo secondario, "
            "non come archivio ufficiale senza conferma Normattiva/Gazzetta."
        ),
    },
    {
        "name": "Studio Cataldi - Codice penale",
        "code": "studiocataldi_codice_penale",
        "category": "normativa_secondaria",
        "base_url": "https://www.studiocataldi.it/codicepenale/",
        "source_type": "web",
        "trust_class": "C",
        "is_official": False,
        "enabled": False,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": (
            "Fonte privata non ufficiale e con pagina rilevata come edizione 2022: "
            "non pubblica testi vigenti se manca riscontro Normattiva."
        ),
    },
    {
        "name": "Avvocato Andreani - Codice della strada",
        "code": "avvocatoandreani_codice_strada",
        "category": "normativa_secondaria",
        "base_url": "https://www.avvocatoandreani.it/servizi/codice-della-strada.php",
        "source_type": "web",
        "trust_class": "C",
        "is_official": False,
        "enabled": False,
        "polling_minutes": 1440,
        "parser_type": "html",
        "notes": (
            "Fonte privata di consultazione rapida: puo' essere usata solo come "
            "supporto secondario rispetto al testo Normattiva del codice della strada."
        ),
    },
    {
        "name": "Cassazione - citazioni e principi verificati",
        "code": "cassazione_citazioni_verificate",
        "category": "giurisprudenza",
        "base_url": "https://www.cortedicassazione.it/",
        "source_type": "web",
        "trust_class": "A",
        "is_official": True,
        "enabled": True,
        "polling_minutes": 720,
        "parser_type": "html",
        "notes": "Presidio ufficiale Cassazione per massime, ordinanze, sentenze e principi: nessuna citazione Lex e' pubblicabile senza riscontro.",
    },
)

HTML_DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/[12]\d{3})\b")
PAGER_FRAME_RE = re.compile(r'parametriUrl\("(?P<element>[^"]+)",\s*"(?P<page>[^"]+)"\)')

LEGAL_PRACTICE_KEYWORDS = (
    "avvocato",
    "studio legale",
    "processo",
    "procedimento",
    "ricorso",
    "sentenza",
    "ordinanza",
    "cassazione",
    "tribunale",
    "tar",
    "consiglio di stato",
    "corte costituzionale",
    "giudice",
    "decreto",
    "legge",
    "circolare",
    "risoluzione",
    "interpello",
    "contratto",
    "responsabilita",
    "lavoro",
    "tribut",
    "privacy",
    "appalto",
    "famiglia",
    "locazione",
    "falliment",
    "crisi d'impresa",
)

NAVIGATION_NOISE_KEYWORDS = (
    "cookie",
    "privacy policy",
    "mappa del sito",
    "contatti",
    "newsletter",
    "login",
    "registrati",
    "seguici",
    "social",
    "home page",
)

LOW_VALUE_ADMIN_ACCOUNTING_MARKERS = (
    "liquidazione fattura",
    "liquidazione della fattura",
    "liquidazione fatture",
    "pagamento fattura",
    "impegno di spesa",
    "mandato di pagamento",
    "rimborso spese",
    "nota di liquidazione",
    "durc",
)

LOW_VALUE_ADMIN_LEGAL_CONTEXT_MARKERS = (
    "ricorso",
    "contenzioso",
    "tar",
    "consiglio di stato",
    "sentenza",
    "ordinanza",
    "appalto",
    "gara",
    "affidamento",
    "contratto pubblico",
    "codice dei contratti",
    "precontenzioso",
    "accesso agli atti",
    "sanzione",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate(value: str, limit: int = 240) -> str:
    cleaned = _clean_spaces(value)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _normalize_document_url(url: str) -> str:
    split = urlsplit(str(url or ""))
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _parse_pub_date(value: Any) -> str:
    text = _clean_spaces(value)
    if not text:
        return ""
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    match = HTML_DATE_RE.search(text)
    if not match:
        return ""
    day, month, year = match.group(1).split("/")
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _year_from_date_like(value: Any) -> str:
    text = _clean_spaces(value)
    if not text:
        return ""
    match = re.search(r"\b(20[0-9]{2}|19[0-9]{2})\b", text)
    return match.group(1) if match else ""


def _looks_like_feed(content: str, content_type: str) -> bool:
    head = content.lstrip()[:400].lower()
    return (
        "xml" in (content_type or "").lower()
        or head.startswith("<rss")
        or head.startswith("<feed")
        or (head.startswith("<?xml") and ("<rss" in head or "<feed" in head))
    )


def _extract_feed_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    docs: list[dict[str, Any]] = []
    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _clean_spaces(item.findtext("title") or item.findtext("{*}title"))
        link = _clean_spaces(item.findtext("link") or item.findtext("{*}link"))
        if not link:
            link_node = item.find("{*}link")
            if link_node is not None:
                link = _clean_spaces(link_node.attrib.get("href") or link_node.text)
        summary = _clean_spaces(item.findtext("description") or item.findtext("{*}summary") or item.findtext("{*}content"))
        published_at = _parse_pub_date(item.findtext("pubDate") or item.findtext("{*}published") or item.findtext("{*}updated"))
        if not title and not link:
            continue
        absolute_url = urljoin(base_url, link or source.get("base_url") or "")
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{title}"),
                "source_url": absolute_url,
                "title": title or absolute_url,
                "published_at": published_at,
                "raw_html": "",
                "raw_text": summary,
                "body_short": _truncate(summary or title),
            }
        )
    return docs


def _extract_html_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        return []
    docs: list[dict[str, Any]] = []
    for anchor in tree.xpath("//a[@href]"):
        title = _clean_spaces(anchor.text_content())
        href = _clean_spaces(anchor.attrib.get("href"))
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        if len(title) < 12:
            continue
        absolute_url = _normalize_document_url(urljoin(base_url, href))
        context = _clean_spaces(" ".join(anchor.xpath(".//text()"))) or title
        row_text = _clean_spaces(
            " ".join(anchor.xpath("./ancestor::*[self::li or self::article or self::div][1]//text()"))
        ) or context
        published_at = _parse_pub_date(f"{title} {row_text}")
        if row_text == title and not published_at:
            continue
        docs.append(
            {
                "external_id": _sha256(
                    f"{source.get('code')}|{absolute_url}|{published_at or title.lower()}"
                ),
                "source_url": absolute_url,
                "title": title,
                "published_at": published_at,
                "raw_html": "",
                "raw_text": row_text,
                "body_short": _truncate(row_text or title),
            }
        )
    if docs:
        unique: dict[str, dict[str, Any]] = {}
        for row in docs:
            unique[row["external_id"]] = row
        return list(unique.values())
    plain = _clean_spaces(" ".join(tree.xpath("//body//text()")))
    return [
        {
            "external_id": _sha256(f"{source.get('code')}|{base_url}|fallback"),
            "source_url": base_url,
            "title": _clean_spaces(tree.findtext(".//title")) or source.get("name") or base_url,
            "published_at": "",
            "raw_html": content,
            "raw_text": plain,
            "body_short": _truncate(plain),
        }
    ]


def _ckan_package_rows(payload: Any) -> list[dict[str, Any]]:
    result = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        return []
    if isinstance(result.get("results"), list):
        return [row for row in result["results"] if isinstance(row, dict)]
    if isinstance(result.get("packages"), list):
        return [row for row in result["packages"] if isinstance(row, dict)]
    if isinstance(result.get("resources"), list):
        return [{"title": result.get("title") or result.get("name"), "notes": result.get("notes"), "resources": result.get("resources")}]
    return []


def _extract_ckan_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    packages = _ckan_package_rows(payload)
    docs: list[dict[str, Any]] = []
    for package in packages:
        package_id = _clean_spaces(package.get("id") or package.get("name"))
        package_title = _clean_spaces(package.get("title") or package.get("name") or package_id)
        package_notes = _clean_spaces(package.get("notes") or package.get("description"))
        package_date = _parse_pub_date(
            package.get("metadata_modified")
            or package.get("modified")
            or package.get("created")
            or package.get("metadata_created")
        )
        package_url = _clean_spaces(package.get("url") or "")
        resources = [row for row in list(package.get("resources") or []) if isinstance(row, dict)]
        if not resources:
            docs.append(
                {
                    "external_id": _sha256(f"{source.get('code')}|{package_id or package_title}|package"),
                    "source_url": package_url or base_url,
                    "title": package_title or source.get("name") or base_url,
                    "published_at": package_date,
                    "raw_html": "",
                    "raw_text": package_notes or package_title,
                    "body_short": _truncate(package_notes or package_title),
                    "resource_format": "dataset",
                    "resource_url": package_url or base_url,
                }
            )
            continue
        for resource in resources:
            resource_id = _clean_spaces(resource.get("id") or resource.get("name") or resource.get("url"))
            resource_name = _clean_spaces(resource.get("name") or resource.get("title") or resource_id)
            resource_url = _normalize_document_url(_clean_spaces(resource.get("url") or package_url or base_url))
            resource_format = _clean_spaces(resource.get("format") or resource.get("mimetype") or resource.get("resource_type"))
            resource_date = _parse_pub_date(
                resource.get("last_modified")
                or resource.get("metadata_modified")
                or resource.get("created")
                or package_date
            )
            title = _clean_spaces(" - ".join(part for part in (package_title, resource_name) if part))
            body = _clean_spaces(
                " ".join(
                    part
                    for part in (
                        package_notes,
                        f"Dataset OpenGA: {package_title}" if package_title else "",
                        f"Risorsa: {resource_name}" if resource_name else "",
                        f"Formato: {resource_format}" if resource_format else "",
                        f"URL: {resource_url}" if resource_url else "",
                    )
                    if part
                )
            )
            docs.append(
                {
                    "external_id": _sha256(f"{source.get('code')}|{package_id}|{resource_id}|{resource_url}"),
                    "source_url": resource_url,
                    "title": title or resource_url or source.get("name") or base_url,
                    "published_at": resource_date or package_date,
                    "raw_html": "",
                    "raw_text": body,
                    "body_short": _truncate(body or title),
                    "resource_format": resource_format,
                    "resource_url": resource_url,
                    "package_id": package_id,
                    "package_title": package_title,
                }
            )
    return _merge_unique_documents(docs)


def _extract_pager_frames(content: str) -> list[str]:
    pages: list[str] = []
    for match in PAGER_FRAME_RE.finditer(str(content or "")):
        page = _clean_spaces(match.group("page"))
        if page and page not in pages and page != "1":
            pages.append(page)
    return pages


def _set_query_param(url: str, key: str, value: str) -> str:
    split = urlsplit(str(url or ""))
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query[str(key)] = str(value)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _merge_unique_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: dict[str, dict[str, Any]] = {}
    for row in documents:
        external_id = str(row.get("external_id") or "")
        if not external_id:
            external_id = _sha256(
                f"{row.get('source_url')}|{row.get('title')}|{row.get('published_at')}"
            )
            row["external_id"] = external_id
        ordered.setdefault(external_id, row)
    return list(ordered.values())


def _verification_note(verification: dict[str, Any], *, prefix: str) -> str:
    confirmations = [
        _clean_spaces(row.get("source_name") or row.get("origin") or row.get("domain"))
        for row in list(verification.get("confirmations") or [])[:4]
        if isinstance(row, dict)
    ]
    searched = verification.get("searched") if isinstance(verification.get("searched"), dict) else {}
    web_results = int((searched or {}).get("web_results") or 0)
    detail = []
    if confirmations:
        detail.append("fonti: " + ", ".join(confirmations))
    detail.append(f"conferme: {int(verification.get('confirmation_count') or 0)}")
    detail.append(f"web: {web_results} risultati")
    reason = _clean_spaces(verification.get("reason"))
    if reason:
        detail.append(reason)
    return _truncate(f"{prefix} {'; '.join(detail)}", 520)


def _is_generic_publication_text(value: Any) -> bool:
    text = _clean_spaces(value).lower()
    if not text:
        return True
    strong_markers = (
        "aggiornamento giuridico",
        "aggiornamento normativo",
        "novita normativa",
        "novita giuridica",
        "novità normativa",
        "novità giuridica",
        "pubblicazione informativa",
    )
    if any(marker in text for marker in strong_markers):
        return True
    weak_markers = ("fonte ufficiale",)
    return len(text) < 140 and any(marker in text for marker in weak_markers)


def _review_needs_publication_verification(review: dict[str, Any]) -> bool:
    searchable_parts = [
        review.get("title"),
        review.get("summary_short"),
        review.get("summary_long"),
        review.get("what_changes"),
        review.get("body_text"),
        review.get("source_excerpt"),
    ]
    text = _clean_spaces(" ".join(_clean_spaces(part) for part in searchable_parts)).lower()
    if any(_is_generic_publication_text(part) for part in searchable_parts[1:5]):
        return True
    if "leggi la notizia" in text:
        return True
    if text.count(" fonte ufficiale") >= 2 and len(text) < 900:
        return True
    dates = re.findall(r"\b[0-3]?\d/[01]?\d/[12]\d{3}\b", text)
    if len(set(dates)) >= 2 and ("leggi" in text or "notizia" in text):
        return True
    return False


def _verification_publication_context(verification: dict[str, Any]) -> tuple[str, str]:
    if not verification.get("ok"):
        return "", ""
    confirmations = [row for row in list(verification.get("confirmations") or []) if isinstance(row, dict)]
    confirmations.sort(key=lambda row: (0 if row.get("official") else 1, -int(row.get("context_chars") or 0)))
    seen: set[str] = set()
    excerpts: list[tuple[str, str]] = []
    for row in confirmations:
        excerpt = _clean_spaces(row.get("excerpt") or row.get("full_context") or row.get("content"))
        if not excerpt:
            continue
        key = excerpt.lower()[:140]
        if key in seen:
            continue
        seen.add(key)
        source_name = _clean_spaces(row.get("source_name") or row.get("domain") or row.get("origin") or "Fonte ufficiale")
        excerpts.append((source_name, _truncate(excerpt, 520)))
        if len(excerpts) >= 4:
            break
    if not excerpts:
        return "", ""
    summary = _truncate(" ".join(excerpt for _, excerpt in excerpts[:2]), 360)
    bullets = "\n".join(f"- {source_name}: {excerpt}" for source_name, excerpt in excerpts)
    return summary, f"Contesto ufficiale verificato:\n{bullets}"


def _review_with_verification_publication_context(
    review: dict[str, Any],
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    if not verification:
        return review
    summary, context = _verification_publication_context(verification)
    if not summary and not context:
        return review
    enriched = dict(review)
    if summary and _is_generic_publication_text(enriched.get("summary_short")):
        enriched["summary_short"] = summary
    current_content = (
        _clean_spaces(enriched.get("what_changes"))
        or _clean_spaces(enriched.get("summary_long"))
        or _clean_spaces(enriched.get("body_text"))
    )
    if context:
        if _is_generic_publication_text(current_content):
            enriched["what_changes"] = context
        elif context not in current_content:
            enriched["what_changes"] = f"{current_content}\n\n{context}"
    return enriched


def _is_navigation_noise(title: str, body_text: str) -> bool:
    text = _clean_spaces(f"{title} {body_text}").lower()
    if not text:
        return True
    if any(keyword in text for keyword in NAVIGATION_NOISE_KEYWORDS):
        has_legal_marker = any(keyword in text for keyword in LEGAL_PRACTICE_KEYWORDS)
        has_numbered_act = bool(re.search(r"\b(?:n\.|numero)\s*[0-9]{1,5}(?:/[0-9]{4})?\b", text))
        return not (has_legal_marker or has_numbered_act)
    return False


class LegalUpdatePipeline:
    def __init__(
        self,
        intelligence_db_path: str,
        *,
        giurisprudenza_db_path: str = "",
        ai_base_url: str = "",
        ai_model: str = "",
        postgres_dsn: str = "",
        export_json_enabled: bool = False,
        mirror_giurisprudenza_json_enabled: bool = False,
    ) -> None:
        self.intelligence_db_path = str(intelligence_db_path or "").strip()
        self.giurisprudenza_db_path = str(giurisprudenza_db_path or "").strip()
        self.ai_base_url = str(ai_base_url or "").strip()
        self.ai_model = str(ai_model or "").strip() or "mistral"
        self.postgres_dsn = resolve_runtime_postgres_dsn(postgres_dsn) if str(postgres_dsn or "").strip() else ""
        self.export_json_enabled = bool(export_json_enabled)
        self.mirror_giurisprudenza_json_enabled = bool(mirror_giurisprudenza_json_enabled)
        cfg = LegalUpdateDbConfig.from_anchor(self.intelligence_db_path)
        self.repository = LegalUpdateRepository(
            cfg.db_path,
            json_path=cfg.json_path,
            postgres_dsn=self.postgres_dsn,
        )
        self.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))

    def _export_repository_json_if_enabled(self) -> str:
        if not self.export_json_enabled:
            return ""
        return self.repository.export_repository_json()

    def list_sources(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        return self.repository.list_sources(enabled_only=enabled_only)

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        return self.repository.get_source_by_id(source_id)

    def _fetch_source(self, source: dict[str, Any], *, request_get: RequestGet) -> list[dict[str, Any]]:
        response = request_get(
            source["base_url"],
            timeout=25,
            headers={"User-Agent": "IUSENTRA-Legal-Updates/1.0"},
        )
        content_type = getattr(response, "headers", {}).get("content-type", "")
        text = ""
        if hasattr(response, "text"):
            text = str(response.text or "")
        elif hasattr(response, "content"):
            text = bytes(response.content or b"").decode("utf-8", errors="ignore")
        parser_type = _clean_spaces(source.get("parser_type")).lower()
        if parser_type == "ckan_json":
            docs = _extract_ckan_items(source, source["base_url"], text)
            enriched_docs: list[dict[str, Any]] = []
            fetched_resources = 0
            for row in docs:
                resource_url = _clean_spaces(row.get("resource_url") or row.get("source_url"))
                resource_format = _clean_spaces(row.get("resource_format")).lower()
                if (
                    resource_url
                    and fetched_resources < 80
                    and ("json" in resource_format or resource_url.lower().endswith(".json"))
                ):
                    try:
                        resource_response = request_get(
                            resource_url,
                            timeout=25,
                            headers={"User-Agent": "IUSENTRA-Legal-Updates/1.0"},
                        )
                        resource_text = ""
                        if hasattr(resource_response, "text"):
                            resource_text = str(resource_response.text or "")
                        elif hasattr(resource_response, "content"):
                            resource_text = bytes(resource_response.content or b"").decode("utf-8", errors="ignore")
                        if resource_text:
                            row["raw_text"] = _truncate(
                                f"{row.get('raw_text') or ''} Contenuto JSON acquisito: {resource_text}",
                                limit=20000,
                            )
                            row["body_short"] = _truncate(row.get("raw_text") or row.get("body_short") or "")
                            row["resource_http_status"] = int(getattr(resource_response, "status_code", 200) or 0)
                            fetched_resources += 1
                    except Exception:
                        row["resource_fetch_warning"] = "Risorsa JSON non raggiungibile durante questa scansione."
                enriched_docs.append(row)
            docs = _merge_unique_documents(enriched_docs)
        elif parser_type in {"feed", "rss", "atom"} or _looks_like_feed(text, content_type):
            docs = _extract_feed_items(source, source["base_url"], text)
        else:
            docs = _extract_html_items(source, source["base_url"], text)
            extra_pages = _extract_pager_frames(text)
            for page in extra_pages:
                page_url = _set_query_param(source["base_url"], "frame3_item", page)
                try:
                    page_response = request_get(
                        page_url,
                        timeout=25,
                        headers={"User-Agent": "IUSENTRA-Legal-Updates/1.0"},
                    )
                except Exception:
                    continue
                page_text = ""
                if hasattr(page_response, "text"):
                    page_text = str(page_response.text or "")
                elif hasattr(page_response, "content"):
                    page_text = bytes(page_response.content or b"").decode("utf-8", errors="ignore")
                docs.extend(_extract_html_items(source, page_url, page_text))
            docs = _merge_unique_documents(docs)
        if not docs:
            docs = [
                {
                    "external_id": _sha256(f"{source['code']}|{source['base_url']}|empty"),
                    "source_url": source["base_url"],
                    "title": source["name"],
                    "published_at": "",
                    "raw_html": text[:20000],
                    "raw_text": _truncate(text, limit=4000),
                    "body_short": _truncate(text),
                }
            ]
        for row in docs:
            row.setdefault("raw_html", text[:20000])
            row.setdefault("raw_text", row.get("body_short") or "")
            row["content_hash"] = _sha256(json.dumps(row, ensure_ascii=False, sort_keys=True))
            row["http_status"] = int(getattr(response, "status_code", 200) or 0)
            row["fetch_status"] = "fetched" if row["http_status"] < 400 else "error"
        return docs

    def _normalize_document(self, source: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        body_text = _clean_spaces(raw.get("raw_text") or raw.get("title"))
        title = _clean_spaces(raw.get("title"))
        issuer = source.get("name") or ""
        document_type_guess = source.get("category") or ""
        return {
            "title": title or source.get("name") or raw.get("source_url") or "Documento acquisito",
            "body_text": body_text,
            "body_short": _truncate(body_text or title),
            "language": "it",
            "issuer": issuer,
            "document_date": _clean_spaces(raw.get("published_at")),
            "document_type_guess": document_type_guess,
            "attachments_json": [],
            "normalized_hash": _sha256(f"{title}|{body_text}|{issuer}|{document_type_guess}"),
        }

    def _match_target(self, analysis: dict[str, Any]) -> dict[str, Any]:
        classification = str(analysis.get("classification_type") or "")
        if classification in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            match = self.repository.find_normative_match(
                str(analysis.get("norm_type") or ""),
                str(analysis.get("norm_number") or ""),
                str(analysis.get("norm_year") or ""),
                str(analysis.get("issuer") or ""),
            )
            if match:
                return {"entity_type": "normative", "entity": match}
        if classification == "GIURISPRUDENZA":
            match = self.repository.find_jurisprudence_match(
                str(analysis.get("court_name") or ""),
                str(analysis.get("decision_number") or ""),
                str(analysis.get("decision_year") or ""),
            )
            if match:
                return {"entity_type": "jurisprudence", "entity": match}
        if classification == "PRASSI":
            match = self.repository.find_prassi_match(
                str(analysis.get("issuer") or ""),
                str(analysis.get("norm_type") or ""),
                str(analysis.get("norm_number") or ""),
                str(analysis.get("norm_year") or ""),
            )
            if match:
                return {"entity_type": "prassi", "entity": match}
        return {"entity_type": "", "entity": None}

    def _review_priority(self, source: dict[str, Any], analysis: dict[str, Any], proposed_action: str) -> int:
        priority = 35
        if self._is_trusted_update_source(source):
            priority += 15
        if proposed_action in {"UPDATE_NORMATIVE", "NEW_NORMATIVE", "NEW_CASE_LAW"}:
            priority += 20
        if str(analysis.get("impact_level") or "") == "alto":
            priority += 15
        priority += int(float(analysis.get("confidence_score") or 0) * 10)
        return max(10, min(priority, 100))

    def _is_trusted_update_source(self, source: dict[str, Any]) -> bool:
        trust_class = _clean_spaces(source.get("trust_class")).upper()
        return bool(source.get("is_official")) or trust_class in {"A", "B"}

    def _auto_publish_threshold(self, proposed_action: str) -> float:
        action = str(proposed_action or "").upper()
        if action == "NEWS_ONLY":
            return 0.67
        if action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}:
            return 0.82
        return 1.0

    def _has_structured_reference(self, analysis: dict[str, Any]) -> bool:
        has_norm_key = all(analysis.get(field) for field in ("norm_type", "norm_number", "norm_year"))
        has_judgment_key = all(analysis.get(field) for field in ("court_name", "decision_number", "decision_year"))
        has_prassi_key = all(analysis.get(field) for field in ("issuer", "norm_type", "norm_number", "norm_year"))
        return bool(has_norm_key or has_judgment_key or has_prassi_key)

    def _is_non_actionable_source_metadata(
        self,
        source: dict[str, Any],
        normalized: dict[str, Any],
        analysis: dict[str, Any],
    ) -> bool:
        if self._has_structured_reference(analysis):
            return False
        source_code = _clean_spaces(source.get("code")).lower()
        source_type = _clean_spaces(source.get("source_type")).lower()
        parser_type = _clean_spaces(source.get("parser_type")).lower()
        title = _clean_spaces(normalized.get("title"))
        body_text = _clean_spaces(normalized.get("body_text") or normalized.get("body_short"))
        text = f"{title} {body_text}".lower()
        if any(marker in text for marker in LOW_VALUE_ADMIN_ACCOUNTING_MARKERS) and not any(
            marker in text for marker in LOW_VALUE_ADMIN_LEGAL_CONTEXT_MARKERS
        ):
            return True
        if source_type == "open_data" or parser_type == "ckan_json" or source_code.startswith("openga_"):
            return True
        if source_code == "dati_normattiva" and any(
            marker in text
            for marker in (
                "api documentation",
                "apidog",
                "open data",
                "opendata",
                "come fare",
                "manuale",
                "dataset",
                "catalogo",
            )
        ):
            return True
        return False

    def _is_auto_publishable_decision(
        self,
        source: dict[str, Any],
        analysis: dict[str, Any],
        proposed_action: str,
    ) -> bool:
        action = str(proposed_action or "").upper()
        if action not in {"NEWS_ONLY", "NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}:
            return False
        if not self._is_trusted_update_source(source):
            return False
        confidence = float(analysis.get("confidence_score") or 0)
        return confidence >= self._auto_publish_threshold(action)

    def _is_useful_for_law_firm(
        self,
        source: dict[str, Any],
        normalized: dict[str, Any],
        analysis: dict[str, Any],
    ) -> bool:
        classification = str(analysis.get("classification_type") or "").upper()
        if classification == "DUPLICATO":
            return True
        if classification == "INCERTO":
            return False
        title = _clean_spaces(normalized.get("title"))
        body_text = _clean_spaces(normalized.get("body_text") or normalized.get("body_short"))
        if _is_navigation_noise(title, body_text):
            return False
        if self._is_non_actionable_source_metadata(source, normalized, analysis):
            return False
        source_category = _clean_spaces(source.get("category")).lower()
        if bool(source.get("is_official")) and source_category in {"normativa", "giurisprudenza", "prassi", "ue"}:
            return True
        text = f"{title} {body_text} {source_category} {_clean_spaces(analysis.get('matter_slug'))}".lower()
        if any(keyword in text for keyword in LEGAL_PRACTICE_KEYWORDS):
            return True
        return float(analysis.get("confidence_score") or 0) >= 0.82 and classification in {"NEWS", "COMMENTO"}

    def _decide_proposal(self, source: dict[str, Any], analysis: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        classification = str(analysis.get("classification_type") or "INCERTO")
        confidence = float(analysis.get("confidence_score") or 0)
        has_norm_key = all(analysis.get(field) for field in ("norm_type", "norm_number", "norm_year"))
        has_judgment_key = all(analysis.get(field) for field in ("court_name", "decision_number", "decision_year"))
        is_official = self._is_trusted_update_source(source)

        proposed_action = "NEEDS_REVIEW"
        target_entity_type = str(target.get("entity_type") or "")
        target_entity = target.get("entity") or {}
        target_entity_id = target_entity.get("id")
        status = "pending"

        if classification in {"NEWS", "COMMENTO"}:
            proposed_action = "NEWS_ONLY"
        elif classification == "GIURISPRUDENZA":
            if target_entity_id:
                proposed_action = "DUPLICATE"
                status = "closed"
            elif is_official and has_judgment_key:
                proposed_action = "NEW_CASE_LAW"
            elif is_official:
                proposed_action = "NEWS_ONLY"
        elif classification == "PRASSI":
            if target_entity_id:
                proposed_action = "DUPLICATE"
                status = "closed"
            elif is_official and analysis.get("norm_number") and analysis.get("norm_year"):
                proposed_action = "NEW_PRASSI"
            elif is_official:
                proposed_action = "NEWS_ONLY"
        elif classification in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            if target_entity_id and classification == "NORMATIVA_NUOVA":
                proposed_action = "DUPLICATE"
                status = "closed"
            elif target_entity_id:
                proposed_action = "UPDATE_NORMATIVE"
                target_entity_type = "normative"
            elif is_official and has_norm_key:
                proposed_action = "NEW_NORMATIVE"
            elif is_official:
                proposed_action = "NEWS_ONLY"
        elif classification == "DUPLICATO":
            proposed_action = "DUPLICATE"
            status = "closed"

        if self._is_auto_publishable_decision(source, analysis, proposed_action):
            status = "approved"
        if proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"} and confidence < 0.8:
            status = "pending"

        return {
            "proposed_action": proposed_action,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "review_status": status,
            "priority": self._review_priority(source, analysis, proposed_action),
        }

    def _build_review_payload(
        self,
        source: dict[str, Any],
        normalized: dict[str, Any],
        analysis: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "source": {
                "code": source.get("code"),
                "name": source.get("name"),
                "category": source.get("category"),
                "trust_class": source.get("trust_class"),
                "is_official": bool(source.get("is_official")),
            },
            "document": {
                "title": normalized.get("title"),
                "document_date": normalized.get("document_date"),
                "issuer": normalized.get("issuer"),
                "body_short": normalized.get("body_short"),
            },
            "analysis": {
                "classification_type": analysis.get("classification_type"),
                "summary_short": analysis.get("summary_short"),
                "summary_long": analysis.get("summary_long"),
                "what_changes": analysis.get("what_changes"),
                "confidence_score": analysis.get("confidence_score"),
                "matter_slug": analysis.get("matter_slug"),
                "submatter_slug": analysis.get("submatter_slug"),
            },
            "decision": decision,
        }

    def process_document(self, source: dict[str, Any], raw_payload: dict[str, Any]) -> dict[str, Any]:
        raw_saved = self.repository.save_raw_document(
            {
                "source_id": source["id"],
                **raw_payload,
            }
        )
        normalized_payload = self._normalize_document(source, raw_saved)
        normalized_saved = self.repository.save_normalized_document(int(raw_saved["id"]), normalized_payload)
        analysis_payload = analyze_document(
            normalized_saved,
            source,
            ai_base_url=self.ai_base_url,
            ai_model=self.ai_model,
        )
        duplicate_target = self.repository.find_published_duplicate(
            source=source,
            normalized=normalized_saved,
            analysis=analysis_payload,
        )
        if duplicate_target:
            target = duplicate_target
            decision = {
                "proposed_action": "DUPLICATE",
                "target_entity_type": str(duplicate_target.get("entity_type") or ""),
                "target_entity_id": (duplicate_target.get("entity") or {}).get("id"),
                "review_status": "closed",
                "priority": self._review_priority(source, analysis_payload, "DUPLICATE"),
            }
        elif self._is_non_actionable_source_metadata(source, normalized_saved, analysis_payload):
            target = {"entity_type": "", "entity": None}
            decision = {
                "proposed_action": "OUT_OF_SCOPE",
                "target_entity_type": "",
                "target_entity_id": None,
                "review_status": "closed",
                "priority": 5,
            }
        elif not self._is_useful_for_law_firm(source, normalized_saved, analysis_payload):
            target = {"entity_type": "", "entity": None}
            decision = {
                "proposed_action": "OUT_OF_SCOPE",
                "target_entity_type": "",
                "target_entity_id": None,
                "review_status": "closed",
                "priority": 10,
            }
        else:
            target = self._match_target(analysis_payload)
            decision = self._decide_proposal(source, analysis_payload, target)
        analysis_saved = self.repository.save_analysis(
            int(normalized_saved["id"]),
            {
                **analysis_payload,
                "proposed_action": decision["proposed_action"],
                "target_entity_type": decision["target_entity_type"],
                "target_entity_id": decision["target_entity_id"],
            },
        )
        review = self.repository.upsert_review_item(
            {
                "normalized_document_id": int(normalized_saved["id"]),
                "analysis_id": int(analysis_saved["id"]),
                "proposal_type": str(analysis_saved.get("classification_type") or "").lower(),
                "proposed_action": decision["proposed_action"],
                "target_entity_type": decision["target_entity_type"],
                "target_entity_id": decision["target_entity_id"],
                "proposal_payload_json": self._build_review_payload(source, normalized_saved, analysis_saved, decision),
                "status": decision["review_status"],
                "priority": decision["priority"],
            }
        )
        verification_evidence = self._record_ingestion_verification_evidence(review, source)
        return {
            "raw": raw_saved,
            "normalized": normalized_saved,
            "analysis": analysis_saved,
            "review": review,
            "verification_evidence": verification_evidence,
        }

    def analyze_raw_document(self, raw_document_id: int, *, auto_publish: bool = True) -> dict[str, Any]:
        raw_saved = self.repository.get_raw_document(raw_document_id)
        if not raw_saved:
            raise ValueError("Documento raw non trovato.")
        source = self.repository.get_source_by_id(int(raw_saved["source_id"]))
        if not source:
            raise ValueError("Fonte associata non trovata.")
        raw_payload = {
            "external_id": raw_saved.get("external_id"),
            "source_url": raw_saved.get("source_url"),
            "title": raw_saved.get("title"),
            "published_at": raw_saved.get("published_at"),
            "raw_html": raw_saved.get("raw_html"),
            "raw_text": raw_saved.get("raw_text"),
            "raw_pdf_path": raw_saved.get("raw_pdf_path"),
            "content_hash": raw_saved.get("content_hash"),
            "fetch_status": raw_saved.get("fetch_status"),
            "http_status": raw_saved.get("http_status"),
        }
        result = self.process_document(source, raw_payload)
        result["autopublished"] = self.publish_auto_news(limit=20) if auto_publish else {"count": 0, "items": []}
        return result

    def scan_source(self, source_code: str, *, request_get: RequestGet = requests.get, auto_publish: bool = True) -> dict[str, Any]:
        source = self.repository.get_source_by_code(source_code)
        if not source:
            raise ValueError(f"Fonte non configurata: {source_code}")
        cleanup = self.repository.deduplicate_archive(performed_by="system")
        documents = self._fetch_source(source, request_get=request_get)
        processed: list[dict[str, Any]] = []
        skipped_unchanged = 0
        verification_attempts = 0
        verification_evidence_saved = 0
        verification_attachments_saved = 0
        for document in documents:
            existing = self.repository.get_raw_document_by_external(int(source["id"]), str(document.get("external_id") or ""))
            if existing and _clean_spaces(existing.get("content_hash")) == _clean_spaces(document.get("content_hash")):
                skipped_unchanged += 1
                continue
            processed_result = self.process_document(source, document)
            evidence = processed_result.get("verification_evidence") if isinstance(processed_result, dict) else {}
            if isinstance(evidence, dict):
                verification_attempts += int(evidence.get("attempted") or 0)
                verification_evidence_saved += int(evidence.get("saved") or 0)
                verification_attachments_saved += int(evidence.get("attachments") or 0)
            processed.append(processed_result)
        self.repository.mark_source_checked(int(source["id"]))
        autopublished = {"count": 0, "items": []}
        if auto_publish:
            autopublished = self.publish_auto_news(limit=20)
        self._export_repository_json_if_enabled()
        return {
            "source": source_code,
            "documents_found": len(documents),
            "processed": len(processed),
            "skipped_unchanged": skipped_unchanged,
            "web_verification_attempts": verification_attempts,
            "verification_evidence_saved": verification_evidence_saved,
            "verification_attachments_saved": verification_attachments_saved,
            "duplicates_removed": int(cleanup.get("removed") or 0),
            "autopublished": autopublished,
        }

    def fetch_source_by_id(self, source_id: int, *, auto_publish: bool = True, request_get: RequestGet = requests.get) -> dict[str, Any]:
        source = self.repository.get_source_by_id(source_id)
        if not source:
            raise ValueError("Fonte non trovata.")
        return self.scan_source(str(source["code"]), request_get=request_get, auto_publish=auto_publish)

    def run_cycle(
        self,
        *,
        source_codes: list[str] | None = None,
        request_get: RequestGet = requests.get,
        auto_publish: bool = True,
    ) -> dict[str, Any]:
        self.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
        cleanup = self.repository.deduplicate_archive(performed_by="system")
        selected = source_codes or [row["code"] for row in self.repository.list_sources(enabled_only=True)]
        reports: list[dict[str, Any]] = []
        for source_code in selected:
            try:
                reports.append(self.scan_source(source_code, request_get=request_get, auto_publish=False))
            except Exception as exc:
                reports.append({"source": source_code, "error": str(exc), "documents_found": 0, "processed": 0})
        autopublished = self.publish_auto_news(limit=40) if auto_publish else {"count": 0, "items": []}
        self._export_repository_json_if_enabled()
        return {
            "ok": True,
            "sources": selected,
            "reports": reports,
            "web_verification_attempts": sum(int(row.get("web_verification_attempts") or 0) for row in reports),
            "verification_evidence_saved": sum(int(row.get("verification_evidence_saved") or 0) for row in reports),
            "verification_attachments_saved": sum(int(row.get("verification_attachments_saved") or 0) for row in reports),
            "duplicates_removed": int(cleanup.get("removed") or 0)
            + sum(int(row.get("duplicates_removed") or 0) for row in reports),
            "autopublished": autopublished,
            "dashboard": self.repository.dashboard_snapshot(),
        }

    def backfill_web_verification_evidence(
        self,
        *,
        limit: int = 100,
        source_codes: list[str] | None = None,
        statuses: tuple[str, ...] | None = None,
        include_closed: bool = False,
        include_open_data: bool = False,
        direct_only: bool = True,
        max_seconds: int = 0,
        query: str = "",
        review_ids: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        source_code_tuple = tuple(_clean_spaces(code) for code in (source_codes or []) if _clean_spaces(code))
        status_tuple = (
            tuple(_clean_spaces(status).lower() for status in statuses if _clean_spaces(status))
            if statuses is not None
            else ("pending", "approved", "published")
        )
        reviews = self.repository.list_reviews_missing_web_evidence(
            limit=max(1, int(limit or 1)),
            source_codes=source_code_tuple,
            statuses=status_tuple,
            include_closed=include_closed,
            include_open_data=include_open_data,
            query=_clean_spaces(query),
            review_ids=tuple(int(value) for value in review_ids if int(value or 0) > 0),
        )
        started = time.monotonic()
        checked = 0
        skipped = 0
        stopped_for_time_limit = False
        verification_attempts = 0
        verification_evidence_saved = 0
        verification_attachments_saved = 0
        rows: list[dict[str, Any]] = []
        for review in reviews:
            if max_seconds and time.monotonic() - started >= max(1, int(max_seconds)):
                stopped_for_time_limit = True
                break
            checked += 1
            source = self._source_for_review(review)
            if not source or not self._is_trusted_update_source(source):
                skipped += 1
                continue
            evidence = self._record_ingestion_verification_evidence(review, source, direct_only=direct_only)
            verification_attempts += int(evidence.get("attempted") or 0)
            verification_evidence_saved += int(evidence.get("saved") or 0)
            verification_attachments_saved += int(evidence.get("attachments") or 0)
            rows.append(
                {
                    "review_id": int(review.get("id") or 0),
                    "source_code": _clean_spaces(review.get("source_code")),
                    "title": _truncate(review.get("title"), 160),
                    "saved": int(evidence.get("saved") or 0),
                    "attachments": int(evidence.get("attachments") or 0),
                    "ok": bool(evidence.get("ok")),
                    "reason": _truncate(evidence.get("reason") or "", 180),
                }
            )
        self._export_repository_json_if_enabled()
        return {
            "ok": True,
            "checked": checked,
            "skipped": skipped,
            "selected": len(reviews),
            "duration_seconds": round(time.monotonic() - started, 2),
            "stopped_for_time_limit": stopped_for_time_limit,
            "direct_only": bool(direct_only),
            "include_closed": bool(include_closed),
            "include_open_data": bool(include_open_data),
            "statuses": list(status_tuple),
            "query": _clean_spaces(query),
            "review_ids": [int(value) for value in review_ids if int(value or 0) > 0],
            "web_verification_attempts": verification_attempts,
            "verification_evidence_saved": verification_evidence_saved,
            "verification_attachments_saved": verification_attachments_saved,
            "items": rows,
            "dashboard": self.repository.dashboard_snapshot(),
        }

    def approve_review(self, review_id: int, *, reviewer: str, notes: str = "") -> dict[str, Any] | None:
        return self.repository.set_review_status(review_id, "approved", reviewer=reviewer, notes=notes)

    def reject_review(self, review_id: int, *, reviewer: str, notes: str = "") -> dict[str, Any] | None:
        return self.repository.set_review_status(review_id, "rejected", reviewer=reviewer, notes=notes)

    def edit_and_approve_review(self, review_id: int, *, reviewer: str, review_notes: str, summary_short: str, what_changes: str) -> dict[str, Any] | None:
        review = self.repository.get_review_item(review_id)
        if not review:
            return None
        proposal = dict(review.get("proposal_payload_json") or {})
        analysis = dict(proposal.get("analysis") or {})
        if summary_short:
            analysis["summary_short"] = _clean_spaces(summary_short)
        if what_changes:
            analysis["what_changes"] = _clean_spaces(what_changes)
        proposal["analysis"] = analysis
        self.repository.upsert_review_item(
            {
                "normalized_document_id": int(review["normalized_document_id"]),
                "analysis_id": int(review["analysis_id"]),
                "proposal_type": review["proposal_type"],
                "proposed_action": review["proposed_action"],
                "target_entity_type": review["target_entity_type"],
                "target_entity_id": review.get("target_entity_id"),
                "proposal_payload_json": proposal,
                "status": "approved",
                "priority": int(review.get("priority") or 50),
                "review_notes": review_notes,
                "reviewed_by": reviewer,
                "reviewed_at": review.get("reviewed_at") or "",
            }
        )
        return self.repository.set_review_status(review_id, "approved", reviewer=reviewer, notes=review_notes)

    def _news_type_for(self, classification_type: str, proposed_action: str) -> str:
        if classification_type == "GIURISPRUDENZA":
            return "giurisprudenza"
        if classification_type == "PRASSI":
            return "prassi"
        if proposed_action == "UPDATE_NORMATIVE":
            return "aggiornamento"
        if classification_type in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            return "normativa"
        if classification_type == "COMMENTO":
            return "commento"
        return "focus"

    def _publish_news_only(self, review: dict[str, Any], *, reviewer: str) -> dict[str, Any]:
        payload = self.repository.create_or_update_news(
            {
                "title": review.get("title"),
                "short_summary": review.get("summary_short"),
                "content": review.get("what_changes") or review.get("summary_long") or review.get("body_text"),
                "news_type": self._news_type_for(str(review.get("classification_type") or ""), str(review.get("proposed_action") or "")),
                "matter_slug": review.get("matter_slug"),
                "submatter_slug": review.get("submatter_slug"),
                "source_url": review.get("source_url"),
                "source_document_id": review.get("normalized_document_id"),
                "is_auto_generated": True,
                "publication_status": "published",
                "published_at": review.get("published_at") or "",
            },
            performed_by=reviewer,
        )
        self.repository.set_review_status(int(review["id"]), "published", reviewer=reviewer, notes="News pubblicata.")
        return {"news": payload}

    def _enrich_review_for_publish(self, review: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(review or {})
        if not enriched.get("decision_year"):
            enriched["decision_year"] = _year_from_date_like(
                enriched.get("document_date") or enriched.get("published_at") or enriched.get("title")
            )
        if not enriched.get("norm_year"):
            enriched["norm_year"] = _year_from_date_like(
                enriched.get("document_date") or enriched.get("published_at") or enriched.get("title")
            )
        if not enriched.get("court_name"):
            source_name = _clean_spaces(enriched.get("source_name"))
            lower_source = source_name.lower()
            if "cassazione" in lower_source:
                enriched["court_name"] = "Corte di Cassazione"
            elif "costituzionale" in lower_source:
                enriched["court_name"] = "Corte costituzionale"
            elif "consiglio di stato" in lower_source:
                enriched["court_name"] = "Consiglio di Stato"
            elif "tar" in lower_source:
                enriched["court_name"] = "TAR"
        if not enriched.get("issuer"):
            enriched["issuer"] = enriched.get("analysis_issuer") or enriched.get("source_name") or ""
        return enriched

    def _resolve_publish_action(self, review: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        enriched = self._enrich_review_for_publish(review)
        proposed_action = str(enriched.get("proposed_action") or "").upper()
        if proposed_action and proposed_action != "NEEDS_REVIEW":
            return proposed_action, enriched

        classification = str(enriched.get("classification_type") or "").upper()
        is_official = bool(enriched.get("is_official"))
        has_norm_key = all(enriched.get(field) for field in ("norm_type", "norm_number", "norm_year"))
        has_judgment_key = all(enriched.get(field) for field in ("court_name", "decision_number", "decision_year"))
        has_prassi_key = all(enriched.get(field) for field in ("issuer", "norm_type", "norm_number", "norm_year"))

        if classification in {"NEWS", "COMMENTO", "INCERTO"}:
            return "NEWS_ONLY", enriched
        if classification == "DUPLICATO":
            return "DUPLICATE", enriched
        if classification == "GIURISPRUDENZA":
            return ("NEW_CASE_LAW" if has_judgment_key else "NEWS_ONLY"), enriched
        if classification == "PRASSI":
            return ("NEW_PRASSI" if is_official and has_prassi_key else "NEWS_ONLY"), enriched
        if classification in {"NORMATIVA_NUOVA", "NORMATIVA_AGGIORNAMENTO"}:
            if is_official and has_norm_key:
                if enriched.get("target_entity_id"):
                    return "UPDATE_NORMATIVE", enriched
                return "NEW_NORMATIVE", enriched
            return "NEWS_ONLY", enriched
        return "NEWS_ONLY", enriched

    def _source_for_review(self, review: dict[str, Any]) -> dict[str, Any] | None:
        source_code = _clean_spaces(review.get("source_code"))
        if source_code:
            source = self.repository.get_source_by_code(source_code)
            if source:
                return source
        source_name = _clean_spaces(review.get("source_name")).lower()
        if source_name:
            for source in self.repository.list_sources(enabled_only=False):
                if _clean_spaces(source.get("name")).lower() == source_name:
                    return source
        return None

    def _record_verification_evidence(
        self,
        review: dict[str, Any],
        source: dict[str, Any] | None,
        verification: dict[str, Any] | None,
        *,
        status: str,
    ) -> dict[str, int]:
        if not source or not verification:
            return {"saved": 0, "attachments": 0}
        try:
            return self.repository.record_web_verification_evidence(
                review_id=int(review.get("id") or 0),
                normalized_document_id=int(review.get("normalized_document_id") or 0),
                source=source,
                verification=verification,
                verification_status=status,
            )
        except Exception:
            return {"saved": 0, "attachments": 0}

    def _record_ingestion_verification_evidence(
        self,
        review: dict[str, Any],
        source: dict[str, Any],
        *,
        direct_only: bool = True,
    ) -> dict[str, Any]:
        """Registra la prova fonte durante l'acquisizione, prima della pubblicazione."""

        if not review or not source or not self._is_trusted_update_source(source):
            return {"attempted": 0, "saved": 0, "attachments": 0, "ok": False, "reason": "fonte non governata"}
        if not _clean_spaces(review.get("source_url")):
            return {"attempted": 0, "saved": 0, "attachments": 0, "ok": False, "reason": "url fonte assente"}
        try:
            verification = verify_legal_update_against_public_sources(review, source, direct_only=direct_only)
        except Exception as exc:
            verification = {
                "ok": False,
                "status": "insufficient",
                "reason": f"Verifica pubblica non completata in acquisizione: {_truncate(str(exc), 160)}",
                "confirmation_count": 0,
                "official_confirmations": 0,
                "confirmations": [],
                "warnings": [],
                "searched": {
                    "query": _clean_spaces(review.get("title")),
                    "queries": [_clean_spaces(review.get("title"))],
                },
            }
        evidence = self._record_verification_evidence(
            review,
            source,
            verification,
            status="verified" if verification.get("ok") else "insufficient",
        )
        return {
            "attempted": 1,
            "saved": int(evidence.get("saved") or 0),
            "attachments": int(evidence.get("attachments") or 0),
            "ok": bool(verification.get("ok")),
            "confirmations": int(verification.get("confirmation_count") or 0),
            "official_confirmations": int(verification.get("official_confirmations") or 0),
            "reason": _truncate(verification.get("reason") or "", 220),
        }

    def _verification_for_manual_publish(self, review: dict[str, Any]) -> dict[str, Any] | None:
        if not _review_needs_publication_verification(review):
            return None
        source = self._source_for_review(review)
        if not source or not self._is_trusted_update_source(source):
            return None
        try:
            verification = verify_legal_update_against_public_sources(review, source)
        except Exception as exc:
            verification = {
                "ok": False,
                "reason": f"Lettura fonte ufficiale non completata: {_truncate(str(exc), 180)}",
                "confirmation_count": 0,
                "confirmations": [],
                "searched": {},
            }
        if verification.get("ok"):
            return verification
        self.repository.set_review_status(
            int(review["id"]),
            "pending",
            reviewer="system",
            notes=_verification_note(
                verification,
                prefix="Pubblicazione sospesa: manca contesto ufficiale leggibile.",
            ),
        )
        raise ValueError("Pubblicazione sospesa: manca un contesto ufficiale leggibile da salvare in IUSENTRA.")

    def publish_review(
        self,
        review_id: int,
        *,
        reviewer: str = "admin",
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        review = self.repository.get_review_item(review_id)
        if not review:
            raise ValueError("Review non trovata.")
        if str(review.get("status") or "").lower() == "rejected":
            raise ValueError("La proposta è stata rifiutata e non può essere pubblicata.")
        if verification is None:
            verification = self._verification_for_manual_publish(review)
        if verification:
            self._record_verification_evidence(
                review,
                self._source_for_review(review),
                verification,
                status="verified" if verification.get("ok") else "insufficient",
            )
        review = _review_with_verification_publication_context(review, verification)
        proposed_action, review = self._resolve_publish_action(review)
        classification = str(review.get("classification_type") or "")
        result: dict[str, Any] = {}

        if proposed_action == "DUPLICATE":
            self.repository.set_review_status(
                int(review_id),
                "closed",
                reviewer=reviewer,
                notes="Elemento gia presente nell'archivio: nessuna nuova pubblicazione.",
            )
            result = {
                "skipped": True,
                "reason": "duplicate",
                "target_entity_type": review.get("target_entity_type"),
                "target_entity_id": review.get("target_entity_id"),
            }
        elif proposed_action == "OUT_OF_SCOPE":
            self.repository.set_review_status(
                int(review_id),
                "closed",
                reviewer=reviewer,
                notes="Elemento non coerente con il perimetro informativo dello studio legale.",
            )
            result = {"skipped": True, "reason": "out_of_scope"}
        elif proposed_action == "NEWS_ONLY":
            result = self._publish_news_only(review, reviewer=reviewer)
        elif proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE"}:
            normative = self.repository.create_or_update_normative(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "norm_type": review.get("norm_type"),
                    "norm_number": review.get("norm_number"),
                    "norm_year": review.get("norm_year"),
                    "issuer": review.get("issuer") or review.get("source_name"),
                    "publication_date": review.get("document_date") or review.get("published_at"),
                    "effective_date": review.get("effective_date") or review.get("document_date"),
                    "status": "vigente",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "text_official": review.get("body_text"),
                    "text_current": review.get("body_text"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "notes": review.get("what_changes"),
                    "version_label": review.get("document_date") or "versione corrente",
                },
                performed_by=reviewer,
            )
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": self._news_type_for(classification, proposed_action),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_normative_id": normative.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Normativa pubblicata.")
            result = {"normative": normative, "news": news}
        elif proposed_action == "NEW_CASE_LAW":
            jurisprudence = self.repository.create_or_update_jurisprudence(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "court_name": review.get("court_name") or review.get("source_name"),
                    "decision_number": review.get("decision_number"),
                    "decision_year": review.get("decision_year"),
                    "decision_date": review.get("document_date") or review.get("published_at"),
                    "publication_date": review.get("published_at") or review.get("document_date"),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "principle_of_law": review.get("what_changes"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "full_text": review.get("body_text"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                },
                performed_by=reviewer,
            )
            if self.mirror_giurisprudenza_json_enabled and self.giurisprudenza_db_path:
                try:
                    GestioneGiurisprudenza(db_path=self.giurisprudenza_db_path).salva(
                        {
                            "titolo": review.get("title"),
                            "fonte": review.get("court_name") or review.get("source_name"),
                            "materia": review.get("matter_name") or review.get("matter_slug"),
                            "riassunto": review.get("summary_short"),
                            "principio_di_diritto": review.get("what_changes"),
                            "link": review.get("source_url"),
                            "numero": review.get("decision_number"),
                            "anno": review.get("decision_year"),
                            "testo_integrale": review.get("body_text"),
                        }
                    )
                except Exception:
                    pass
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": "giurisprudenza",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_jurisprudence_id": jurisprudence.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Giurisprudenza pubblicata.")
            result = {"jurisprudence": jurisprudence, "news": news}
        elif proposed_action == "NEW_PRASSI":
            prassi = self.repository.create_or_update_prassi(
                {
                    "title": review.get("title"),
                    "slug": review.get("title"),
                    "issuing_body": review.get("issuer") or review.get("source_name"),
                    "act_type": review.get("norm_type"),
                    "act_number": review.get("norm_number"),
                    "act_year": review.get("norm_year"),
                    "act_date": review.get("document_date") or review.get("published_at"),
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "summary": review.get("summary_long") or review.get("summary_short"),
                    "full_text": review.get("body_text"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                },
                performed_by=reviewer,
            )
            news = self.repository.create_or_update_news(
                {
                    "title": review.get("title"),
                    "short_summary": review.get("summary_short"),
                    "content": review.get("what_changes") or review.get("summary_long"),
                    "news_type": "prassi",
                    "matter_slug": review.get("matter_slug"),
                    "submatter_slug": review.get("submatter_slug"),
                    "related_prassi_id": prassi.get("id"),
                    "source_url": review.get("source_url"),
                    "source_document_id": review.get("normalized_document_id"),
                    "is_auto_generated": True,
                    "publication_status": "published",
                },
                performed_by=reviewer,
            )
            self.repository.set_review_status(int(review_id), "published", reviewer=reviewer, notes="Prassi pubblicata.")
            result = {"prassi": prassi, "news": news}
        else:
            raise ValueError(f"Azione di pubblicazione non supportata: {proposed_action}")

        self._export_repository_json_if_enabled()
        return result

    def reconcile_pending_reviews(self, *, limit: int = 300, reviewer: str = "system") -> dict[str, Any]:
        items = self.repository.list_review_queue(statuses=("approved", "pending"), limit=limit)
        report: dict[str, Any] = {
            "checked": 0,
            "duplicates_closed": 0,
            "metadata_closed": 0,
            "downgraded_to_news": 0,
            "resolved_actions": 0,
        }
        for row in items:
            review_id = int(row.get("id") or 0)
            if not review_id:
                continue
            review = self.repository.get_review_item(review_id)
            if not review:
                continue
            report["checked"] += 1
            source = self.repository.get_source_by_code(str(review.get("source_code") or ""))
            if not source:
                continue
            normalized = {
                "title": review.get("title"),
                "source_url": review.get("source_url"),
                "published_at": review.get("published_at"),
                "document_date": review.get("document_date"),
                "issuer": review.get("issuer"),
                "body_text": review.get("body_text"),
                "body_short": review.get("body_short"),
            }
            analysis = {
                "classification_type": review.get("classification_type"),
                "confidence_score": review.get("confidence_score"),
                "issuer": review.get("analysis_issuer") or review.get("issuer"),
                "norm_type": review.get("norm_type"),
                "norm_number": review.get("norm_number"),
                "norm_year": review.get("norm_year"),
                "decision_number": review.get("decision_number"),
                "decision_year": review.get("decision_year"),
                "court_name": review.get("court_name"),
                "effective_date": review.get("effective_date"),
            }
            duplicate = self.repository.find_published_duplicate(
                source=source,
                normalized=normalized,
                analysis=analysis,
            )
            if duplicate:
                self.repository.set_review_status(
                    review_id,
                    "closed",
                    reviewer=reviewer,
                    notes="Elemento gia' presente nell'archivio operativo: chiusura automatica.",
                )
                report["duplicates_closed"] += 1
                continue
            if self._is_non_actionable_source_metadata(source, normalized, analysis):
                self.repository.set_review_status(
                    review_id,
                    "closed",
                    reviewer=reviewer,
                    notes=(
                        "Dato tecnico o catalogo open data acquisito per consultazione, "
                        "non e' un aggiornamento giuridico da pubblicare."
                    ),
                )
                report["metadata_closed"] += 1
                continue

            proposed_action = str(review.get("proposed_action") or "").upper()
            confidence = float(review.get("confidence_score") or 0)
            if proposed_action == "NEEDS_REVIEW":
                resolved_action, _ = self._resolve_publish_action(review)
                if resolved_action and resolved_action != "NEEDS_REVIEW":
                    self.repository.set_review_proposed_action(
                        review_id,
                        resolved_action,
                        reviewer=reviewer,
                        notes="Azione risolta automaticamente dal motore di classificazione.",
                    )
                    report["resolved_actions"] += 1
                    if resolved_action == "NEWS_ONLY":
                        report["downgraded_to_news"] += 1
                continue
            if (
                proposed_action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}
                and self._is_trusted_update_source(source)
                and 0.67 <= confidence < self._auto_publish_threshold(proposed_action)
            ):
                self.repository.set_review_proposed_action(
                    review_id,
                    "NEWS_ONLY",
                    target_entity_type="",
                    target_entity_id=None,
                    reviewer=reviewer,
                    notes=(
                        "Confidenza non sufficiente per aggiornare l'archivio strutturato: "
                        "pubblicazione informativa automatica."
                    ),
                )
                report["downgraded_to_news"] += 1
        return report

    def publish_auto_news(self, *, limit: int = 20) -> dict[str, Any]:
        cleanup = self.repository.deduplicate_archive(performed_by="system")
        reconciliation = self.reconcile_pending_reviews(limit=max(limit * 3, 120), reviewer="system")
        candidate_limit = max(max(1, int(limit or 1)) * 12, 40)
        items = self.repository.list_review_queue(statuses=("approved", "pending"), limit=candidate_limit)
        published: list[int] = []
        skipped: list[dict[str, Any]] = []
        verification_attempts = 0
        verification_evidence_saved = 0
        verification_attachments_saved = 0
        for row in items:
            if len(published) >= max(1, int(limit or 1)):
                break
            proposed_action = str(row.get("proposed_action") or "").upper()
            if proposed_action in {"DUPLICATE", "OUT_OF_SCOPE"}:
                skipped.append({"id": int(row["id"]), "reason": proposed_action.lower()})
                continue
            if proposed_action not in {"NEWS_ONLY", "NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}:
                continue
            if not row.get("source_code"):
                continue
            source = self.repository.get_source_by_code(str(row["source_code"]))
            if not source or not self._is_trusted_update_source(source):
                continue
            confidence = float(row.get("confidence_score") or 0)
            threshold = self._auto_publish_threshold(proposed_action)
            can_complete_as_news = proposed_action == "NEWS_ONLY" and confidence >= 0.50
            if confidence < threshold and not can_complete_as_news:
                continue
            review = self.repository.get_review_item(int(row["id"])) or row
            try:
                verification = verify_legal_update_against_public_sources(review, source)
            except Exception as exc:
                verification = {
                    "ok": False,
                    "reason": f"Verifica pubblica non completata: {_truncate(str(exc), 160)}",
                    "confirmation_count": 0,
                }
            verification_attempts += 1
            evidence = self._record_verification_evidence(
                review,
                source,
                verification,
                status="verified" if verification.get("ok") else "insufficient",
            )
            verification_evidence_saved += int(evidence.get("saved") or 0)
            verification_attachments_saved += int(evidence.get("attachments") or 0)
            if not verification.get("ok"):
                reason = _truncate(str(verification.get("reason") or "Verifica pubblica insufficiente."), 220)
                self.repository.set_review_status(
                    int(row["id"]),
                    "pending",
                    reviewer="system",
                    notes=_verification_note(verification, prefix="Verifica fonti insufficiente:"),
                    priority=10,
                )
                skipped.append(
                    {
                        "id": int(row["id"]),
                        "reason": "verifica_fonti_insufficiente",
                        "detail": reason,
                        "confirmations": int(verification.get("confirmation_count") or 0),
                        "evidence_saved": int(evidence.get("saved") or 0),
                        "attachments_saved": int(evidence.get("attachments") or 0),
                    }
                )
                continue
            if confidence < threshold and proposed_action == "NEWS_ONLY":
                review = self.repository.set_review_proposed_action(
                    int(row["id"]),
                    "NEWS_ONLY",
                    target_entity_type="",
                    target_entity_id=None,
                    reviewer="system",
                    notes="Riferimento completato con verifica web ufficiale e pubblicato come notizia informativa.",
                ) or review
            if str(row.get("status") or "").lower() != "approved":
                self.repository.set_review_status(
                    int(row["id"]),
                    "approved",
                    reviewer="system",
                    notes=_verification_note(
                        verification,
                        prefix="Verifica fonti completata: pubblicazione automatica autorizzata.",
                    ),
                )
            try:
                self.publish_review(int(row["id"]), reviewer="system", verification=verification)
            except Exception as exc:
                skipped.append(
                    {
                        "id": int(row["id"]),
                        "reason": "errore_pubblicazione",
                        "detail": _truncate(str(exc), 180),
                    }
                )
                continue
            published.append(int(row["id"]))
        if published:
            self.repository.deduplicate_archive(performed_by="system")
        return {
            "count": len(published),
            "items": published,
            "skipped": skipped,
            "web_verification_attempts": verification_attempts,
            "verification_evidence_saved": verification_evidence_saved,
            "verification_attachments_saved": verification_attachments_saved,
            "duplicates_removed": int(cleanup.get("removed") or 0),
            "reconciled": reconciliation,
        }

    def dashboard_snapshot(self) -> dict[str, Any]:
        return self.repository.dashboard_snapshot()


def build_legal_update_pipeline(
    intelligence_db_path: str,
    *,
    giurisprudenza_db_path: str = "",
    ai_base_url: str = "",
    ai_model: str = "",
    postgres_dsn: str = "",
    export_json_enabled: bool = False,
    mirror_giurisprudenza_json_enabled: bool = False,
) -> LegalUpdatePipeline:
    return LegalUpdatePipeline(
        intelligence_db_path,
        giurisprudenza_db_path=giurisprudenza_db_path,
        ai_base_url=ai_base_url,
        ai_model=ai_model,
        postgres_dsn=postgres_dsn,
        export_json_enabled=export_json_enabled,
        mirror_giurisprudenza_json_enabled=mirror_giurisprudenza_json_enabled,
    )
