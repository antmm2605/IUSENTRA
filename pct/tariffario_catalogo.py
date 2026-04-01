"""
pct/tariffario_catalogo.py - Catalogo condiviso del tariffario forense.

Raccoglie riferimenti normativi ufficiali, profili di calcolo, opzioni
compenso e canali operativi per preventivi, parcelle e FatturaPA.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "tariffario_dm147_2022.json"

_LABELS_3 = [
    (0.0, 1100.0, "Fino a EUR 1.100"),
    (1100.0, 5200.0, "Da EUR 1.100 a EUR 5.200"),
    (5200.0, float("inf"), "Da EUR 5.200 a EUR 26.000"),
]
_LABELS_7 = [
    (0.0, 1100.0, "Fino a EUR 1.100 (o indeterminabile)"),
    (1100.0, 5200.0, "Da EUR 1.100 a EUR 5.200"),
    (5200.0, 26000.0, "Da EUR 5.200 a EUR 26.000"),
    (26000.0, 52000.0, "Da EUR 26.000 a EUR 52.000"),
    (52000.0, 260000.0, "Da EUR 52.000 a EUR 260.000"),
    (260000.0, 520000.0, "Da EUR 260.000 a EUR 520.000"),
    (520000.0, float("inf"), "Oltre EUR 520.000"),
]

PHASE_KEY_BY_RAW = {
    "Studio": "studio",
    "Introduttiva": "introduttiva",
    "Istruttoria": "istruttoria",
    "Decisoria": "decisionale",
    "Cautelare": "cautelare",
    "Unica": "compenso_unico",
}

PHASE_VALUE_BY_KEY = {
    "studio": "Studio",
    "introduttiva": "Introduttiva",
    "istruttoria": "Istruttoria / Istruzione",
    "decisionale": "Decisionale",
    "esecutiva": "Esecutiva",
    "attivazione": "Fase di attivazione",
    "rivitalizzazione": "Fase di rivitalizzazione",
    "negoziazione": "Fase di negoziazione",
    "conciliazione": "Fase di conciliazione",
    "compenso_unico": "Compenso unico",
    "cautelare": "Cautelare",
}

PHASE_LABEL_BY_KEY = {
    "studio": "Studio",
    "introduttiva": "Introduttiva",
    "istruttoria": "Istruttoria / istruzione",
    "decisionale": "Decisionale",
    "esecutiva": "Esecutiva",
    "attivazione": "Attivazione",
    "rivitalizzazione": "Rivitalizzazione",
    "negoziazione": "Negoziazione",
    "conciliazione": "Conciliazione",
    "compenso_unico": "Compenso unico",
    "cautelare": "Cautelare",
}

GRADE_INPUT_BY_KEY = {
    "GIUDICE_DI_PACE": "Giudice di Pace",
    "TRIBUNALE": "Tribunale",
    "CORTE_APPELLO": "Corte d'Appello",
    "CASSAZIONE": "Corte di Cassazione",
    "TAR": "TAR",
    "CONSIGLIO_DI_STATO": "Consiglio di Stato",
    "CGT_PRIMO_GRADO": "CGT di primo grado",
    "CGT_SECONDO_GRADO": "CGT di secondo grado",
    "FUORI_GIUDIZIO": "Fuori giudizio",
    "PROCEDURA_ADR": "Procedura ADR",
}

_URL_LEGGE_FORENSE = "https://www.gazzettaufficiale.it/eli/id/2013/01/18/13G00018/sg"
_URL_DM55 = (
    "https://www.normattiva.it/atto/caricaDettaglioAtto?"
    "atto.codiceRedazionale=14G00067&atto.dataPubblicazioneGazzetta=2014-04-02"
    "&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=01%2F04%2F2026"
)
_URL_DM147 = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
    "atto.codiceRedazionale=22G00157&atto.dataPubblicazioneGazzetta=2022-10-08"
    "&atto.tipoProvvedimento=DECRETO"
)
_URL_EQUO_COMPENSO = (
    "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?"
    "atto.codiceRedazionale=23G00051&atto.dataPubblicazioneGazzetta=2023-05-05"
    "&atto.tipoProvvedimento=LEGGE"
)
_URL_CASSA_FORENSE = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Alegge%3A1980-09-20%3B576"
_URL_DPR633 = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1972-10-26%3B633"
_URL_DLGS127 = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2015-08-05%3B127"
_URL_FATTURE_CORRISPETTIVI = "https://www1.agenziaentrate.gov.it/web_app_entrate/fatturazione_elettronica.html"
_URL_FATTURAPA = "https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.2/Rappresentazione_Tabellare_FattOrdinaria_V1.2.2.pdf"

TARIFFARIO_REFERENCE_ROWS: List[Dict[str, Any]] = [
    {
        "reference_code": "l247_art13",
        "title": "L. 31 dicembre 2012, n. 247",
        "article": "art. 13",
        "description": "Conferimento dell'incarico, pattuizione del compenso e informativa preventiva al cliente.",
        "url": _URL_LEGGE_FORENSE,
        "domains": ["tariffario", "preventivi", "conferimenti"],
    },
    {
        "reference_code": "dm55_parametri",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "parametri forensi",
        "description": "Regolamento base dei parametri forensi e delle tabelle di liquidazione.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi", "parcelle"],
    },
    {
        "reference_code": "dm147_aggiornamento",
        "title": "D.M. 13 agosto 2022, n. 147",
        "article": "aggiornamento tabelle",
        "description": "Aggiornamento dei parametri forensi, bonus telematico e criteri di variazione.",
        "url": _URL_DM147,
        "domains": ["tariffario", "preventivi", "parcelle"],
    },
    {
        "reference_code": "dm55_art2",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 2",
        "description": "Spese generali forfettarie del 15% sul compenso professionale.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi", "parcelle"],
    },
    {
        "reference_code": "dm55_art4",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 4",
        "description": "Variazione del compenso per singola fase entro i limiti oggi fissati dal regolamento vigente.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi", "parcelle"],
    },
    {
        "reference_code": "dm55_art4bis",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 4, comma 1-bis",
        "description": "Aumento per atti telematici idonei alla ricerca testuale.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi"],
    },
    {
        "reference_code": "dm55_art22bis",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 22-bis",
        "description": "Compenso orario professionale nel range previsto dal regolamento vigente.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi", "conferimenti"],
    },
    {
        "reference_code": "l49_equo_compenso",
        "title": "L. 21 aprile 2023, n. 49",
        "article": "equo compenso",
        "description": "Tutela dell'equo compenso nei rapporti con grandi committenti e clienti qualificati.",
        "url": _URL_EQUO_COMPENSO,
        "domains": ["tariffario", "preventivi", "conferimenti"],
    },
    {
        "reference_code": "l576_art11",
        "title": "L. 20 settembre 1980, n. 576",
        "article": "art. 11",
        "description": "Contributo integrativo del 4% dovuto alla Cassa Forense e addebitabile al cliente.",
        "url": _URL_CASSA_FORENSE,
        "domains": ["tariffario", "parcelle", "fatturazione_elettronica"],
    },
    {
        "reference_code": "dpr633_art15",
        "title": "D.P.R. 26 ottobre 1972, n. 633",
        "article": "art. 15",
        "description": "Anticipazioni in nome e per conto del cliente escluse da imponibile IVA.",
        "url": _URL_DPR633,
        "domains": ["tariffario", "preventivi", "parcelle", "fatturazione_elettronica"],
    },
    {
        "reference_code": "dlgs127_fattura_elettronica",
        "title": "D.Lgs. 5 agosto 2015, n. 127",
        "article": "fatturazione elettronica",
        "description": "Base normativa per fatturazione elettronica e Sistema di Interscambio.",
        "url": _URL_DLGS127,
        "domains": ["parcelle", "fatturazione_elettronica"],
    },
    {
        "reference_code": "ae_fatture_corrispettivi",
        "title": "Agenzia delle Entrate",
        "article": "Fatture e Corrispettivi",
        "description": "Portale operativo per predisposizione, trasmissione e consultazione delle fatture elettroniche.",
        "url": _URL_FATTURE_CORRISPETTIVI,
        "domains": ["fatturazione_elettronica"],
    },
    {
        "reference_code": "fatturapa_tracciato",
        "title": "FatturaPA",
        "article": "Rappresentazione tabellare del tracciato XML",
        "description": "Specifiche ufficiali del formato XML ordinario FPR12/FPA12 e dei controlli extra-schema.",
        "url": _URL_FATTURAPA,
        "domains": ["fatturazione_elettronica"],
    },
]

TABELLE_SNAPSHOT_META: Dict[str, Dict[str, Any]] = {
    "A1": {"table_label": "Tabella 1 - Giudice di Pace", "area_scope": "Civile", "grade_scope": "Giudice di Pace"},
    "A2": {"table_label": "Tabella 2 - Giudizi civili ordinari", "area_scope": "Civile", "grade_scope": "Tribunale / Appello / Cassazione"},
    "A3": {"table_label": "Tabella 3 - Controversie di lavoro", "area_scope": "Civile", "grade_scope": "Tribunale / Appello / Cassazione"},
    "A4": {"table_label": "Tabella 4 - Previdenza e assistenza", "area_scope": "Civile", "grade_scope": "Tribunale / Appello / Cassazione"},
    "A21": {"table_label": "Tabella 21 - Giustizia amministrativa di primo grado", "area_scope": "Amministrativo", "grade_scope": "TAR / primo grado"},
    "A22": {"table_label": "Tabella 22 - Giustizia amministrativa di impugnazione", "area_scope": "Amministrativo", "grade_scope": "Consiglio di Stato / appello"},
    "A23": {"table_label": "Tabella 23 - Giustizia tributaria di primo grado", "area_scope": "Tributario", "grade_scope": "CGT primo grado"},
    "A24": {"table_label": "Tabella 24 - Giustizia tributaria di appello", "area_scope": "Tributario", "grade_scope": "CGT secondo grado"},
    "A25": {"table_label": "Tabella 25 - Prestazioni stragiudiziali", "area_scope": "Stragiudiziale", "grade_scope": "Fuori giudizio / ADR"},
}

PROFILE_ROWS: List[Dict[str, Any]] = [
    {
        "profile_code": "civile_gdp",
        "materia_key": "CIVILE_COGN",
        "materia_label": "Civile di cognizione",
        "grado_key": "GIUDICE_DI_PACE",
        "grado_label": "Giudice di Pace",
        "table_code": "A1",
        "table_label": "Tabella 1 - Giudice di Pace",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "atto_citazione",
        "summary": "Giudizi civili avanti al Giudice di Pace con scaglioni di valore dedicati.",
        "base_note": "Calcolo su tabella 1, con valore della controversia e fasi processuali selezionabili.",
    },
    {
        "profile_code": "civile_tribunale",
        "materia_key": "CIVILE_COGN",
        "materia_label": "Civile di cognizione",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "atto_citazione",
        "summary": "Giudizi civili ordinari di primo grado con articolazione per fasi.",
        "base_note": "Profilo principale per cause civili ordinarie, decreto ingiuntivo e opposizioni con adattamenti di fase.",
    },
    {
        "profile_code": "civile_appello",
        "materia_key": "CIVILE_COGN",
        "materia_label": "Civile di cognizione",
        "grado_key": "CORTE_APPELLO",
        "grado_label": "Corte d'Appello",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.3,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "appello_civile",
        "summary": "Appello civile con coefficiente ricostruttivo sulla tabella di primo grado.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.30 sul profilo civile ordinario.",
    },
    {
        "profile_code": "civile_cassazione",
        "materia_key": "CIVILE_COGN",
        "materia_label": "Civile di cognizione",
        "grado_key": "CASSAZIONE",
        "grado_label": "Corte di Cassazione",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "cassazione_civile",
        "summary": "Giudizio di legittimita con coefficiente ricostruttivo sulla tabella civile.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.60 e riduzione alle fasi normalmente rilevanti.",
    },
    {
        "profile_code": "lavoro_tribunale",
        "materia_key": "LAVORO",
        "materia_label": "Controversie di lavoro",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A3",
        "table_label": "Tabella 3 - Controversie di lavoro",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "controversia_lavoro",
        "summary": "Rito lavoro e controversie individuali di lavoro.",
        "base_note": "Profilo autonomo della tabella lavoro, distinto dal civile ordinario.",
    },
    {
        "profile_code": "lavoro_appello",
        "materia_key": "LAVORO",
        "materia_label": "Controversie di lavoro",
        "grado_key": "CORTE_APPELLO",
        "grado_label": "Corte d'Appello",
        "table_code": "A3",
        "table_label": "Tabella 3 - Controversie di lavoro",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.3,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "appello_lavoro",
        "summary": "Impugnazioni in materia di lavoro con coefficiente ricostruttivo.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.30 sul primo grado lavoro.",
    },
    {
        "profile_code": "lavoro_cassazione",
        "materia_key": "LAVORO",
        "materia_label": "Controversie di lavoro",
        "grado_key": "CASSAZIONE",
        "grado_label": "Corte di Cassazione",
        "table_code": "A3",
        "table_label": "Tabella 3 - Controversie di lavoro",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "appello_lavoro",
        "summary": "Giudizio di legittimita in materia di lavoro con coefficiente ricostruttivo.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.60 sul primo grado lavoro, con focus su studio, introduzione e decisione.",
    },
    {
        "profile_code": "previdenza_tribunale",
        "materia_key": "PREVIDENZA",
        "materia_label": "Previdenza e assistenza",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A4",
        "table_label": "Tabella 4 - Previdenza e assistenza",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "previdenza",
        "summary": "Contenzioso previdenziale e assistenziale.",
        "base_note": "Tabella autonoma per INPS, INAIL e prestazioni assistenziali.",
    },
    {
        "profile_code": "previdenza_appello",
        "materia_key": "PREVIDENZA",
        "materia_label": "Previdenza e assistenza",
        "grado_key": "CORTE_APPELLO",
        "grado_label": "Corte d'Appello",
        "table_code": "A4",
        "table_label": "Tabella 4 - Previdenza e assistenza",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.3,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "previdenza",
        "summary": "Impugnazioni previdenziali e assistenziali con coefficiente ricostruttivo.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.30 sul primo grado previdenziale.",
    },
    {
        "profile_code": "previdenza_cassazione",
        "materia_key": "PREVIDENZA",
        "materia_label": "Previdenza e assistenza",
        "grado_key": "CASSAZIONE",
        "grado_label": "Corte di Cassazione",
        "table_code": "A4",
        "table_label": "Tabella 4 - Previdenza e assistenza",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "previdenza",
        "summary": "Ricorso per Cassazione in materia previdenziale e assistenziale.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.60 con selezione delle fasi normalmente rilevanti nel giudizio di legittimita.",
    },
    {
        "profile_code": "esecuzione_mobiliare",
        "materia_key": "ESEC_MOB",
        "materia_label": "Esecuzione mobiliare",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "esecutiva"],
        "suggested_practice_id": "esecuzione_mobiliare",
        "summary": "Profilo esecutivo ricondotto alla struttura civile con fase esecutiva dedicata.",
        "base_note": "HACS utilizza un profilo ricostruttivo coerente con il motore esecutivo interno.",
    },
    {
        "profile_code": "esecuzione_immobiliare",
        "materia_key": "ESEC_IMMO",
        "materia_label": "Esecuzione immobiliare",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "esecutiva"],
        "suggested_practice_id": "esecuzione_immobiliare",
        "summary": "Profilo esecutivo immobiliare con lettura operativa su fase esecutiva.",
        "base_note": "Ricostruzione controllata del compenso per la fase esecutiva immobiliare.",
    },
    {
        "profile_code": "volontaria",
        "materia_key": "VOLONTARIA",
        "materia_label": "Volontaria giurisdizione",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "A2",
        "table_label": "Tabella 2 - Giudizi civili ordinari",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "separazione_consensuale",
        "summary": "Procedimenti di volontaria giurisdizione con fasi ridotte rispetto al rito pieno.",
        "base_note": "Profilo operativo per procedimenti camerali e volontaria giurisdizione.",
    },
    {
        "profile_code": "penale_base",
        "materia_key": "PENALE",
        "materia_label": "Penale",
        "grado_key": "TRIBUNALE",
        "grado_label": "Tribunale",
        "table_code": "PENALE",
        "table_label": "Profilo sintetico penale HACS",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": False,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "dibattimento_penale",
        "summary": "Profilo sintetico penale per il calcolo operativo interno.",
        "base_note": "In attesa di una UI penale dedicata, il motore mantiene una tabella sintetica tracciata.",
    },
    {
        "profile_code": "penale_appello",
        "materia_key": "PENALE",
        "materia_label": "Penale",
        "grado_key": "CORTE_APPELLO",
        "grado_label": "Corte d'Appello",
        "table_code": "PENALE",
        "table_label": "Profilo sintetico penale HACS",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.3,
        "requires_value": False,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "impugnazioni_penali",
        "summary": "Impugnazioni penali di merito con profilo ricostruttivo coerente con il motore interno.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.30 sul profilo penale sintetico.",
    },
    {
        "profile_code": "penale_cassazione",
        "materia_key": "PENALE",
        "materia_label": "Penale",
        "grado_key": "CASSAZIONE",
        "grado_label": "Corte di Cassazione",
        "table_code": "PENALE",
        "table_label": "Profilo sintetico penale HACS",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": False,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "cassazione_penale",
        "summary": "Giudizio penale di legittimita con profilo ricostruttivo del motore HACS.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.60 sul profilo penale sintetico.",
    },
    {
        "profile_code": "amministrativo_primo_grado",
        "materia_key": "AMMINISTRATIVO",
        "materia_label": "Amministrativo / TAR-CdS",
        "grado_key": "TAR",
        "grado_label": "TAR",
        "table_code": "A21",
        "table_label": "Tabella 21 - Giustizia amministrativa di primo grado",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "ricorso_tar",
        "summary": "Ricorsi TAR e cautelari di primo grado.",
        "base_note": "Profilo dedicato al primo grado amministrativo davanti al TAR.",
    },
    {
        "profile_code": "amministrativo_appello",
        "materia_key": "AMMINISTRATIVO",
        "materia_label": "Amministrativo / TAR-CdS",
        "grado_key": "CONSIGLIO_DI_STATO",
        "grado_label": "Consiglio di Stato",
        "table_code": "A22",
        "table_label": "Tabella 22 - Giustizia amministrativa di impugnazione",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "appello_cds",
        "summary": "Appelli davanti al Consiglio di Stato e riti di impugnazione amministrativa.",
        "base_note": "Profilo dedicato all'appello amministrativo davanti al Consiglio di Stato.",
    },
    {
        "profile_code": "tributario_primo_grado",
        "materia_key": "TRIBUTARIO",
        "materia_label": "Tributario / CGT",
        "grado_key": "CGT_PRIMO_GRADO",
        "grado_label": "CGT di primo grado",
        "table_code": "A23",
        "table_label": "Tabella 23 - Giustizia tributaria di primo grado",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "ricorso_tributario",
        "summary": "Ricorsi davanti alla Corte di giustizia tributaria di primo grado.",
        "base_note": "Profilo dedicato al primo grado tributario davanti alla Corte di giustizia tributaria.",
    },
    {
        "profile_code": "tributario_appello",
        "materia_key": "TRIBUTARIO",
        "materia_label": "Tributario / CGT",
        "grado_key": "CGT_SECONDO_GRADO",
        "grado_label": "CGT di secondo grado",
        "table_code": "A24",
        "table_label": "Tabella 24 - Giustizia tributaria di appello",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "appello_tributario",
        "summary": "Impugnazioni davanti alla Corte di giustizia tributaria di secondo grado.",
        "base_note": "Profilo dedicato all'appello tributario davanti alla Corte di giustizia tributaria di secondo grado.",
    },
    {
        "profile_code": "tributario_cassazione",
        "materia_key": "TRIBUTARIO",
        "materia_label": "Tributario / CGT",
        "grado_key": "CASSAZIONE",
        "grado_label": "Corte di Cassazione",
        "table_code": "A24",
        "table_label": "Tabella 24 - Giustizia tributaria di appello",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "cassazione_tributaria",
        "summary": "Ricorso per cassazione in materia tributaria con profilo ricostruttivo sul grado di impugnazione.",
        "base_note": "Applicazione ricostruttiva del coefficiente 1.60 sul profilo tributario di impugnazione.",
    },
    {
        "profile_code": "stragiudiziale",
        "materia_key": "STRAGIUD",
        "materia_label": "Stragiudiziale / Consulenza",
        "grado_key": "FUORI_GIUDIZIO",
        "grado_label": "Fuori giudizio",
        "table_code": "A25",
        "table_label": "Tabella 25 - Prestazioni stragiudiziali",
        "calc_mode": "compenso_unico",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["compenso_unico"],
        "suggested_practice_id": "consulenza_civile",
        "summary": "Prestazioni stragiudiziali, pareri, diffide e assistenza fuori giudizio.",
        "base_note": "Il compenso e trattato come voce unica tabellare e non per fasi processuali.",
    },
    {
        "profile_code": "mediazione",
        "materia_key": "MEDIAZIONE",
        "materia_label": "Mediazione (D.Lgs. 28/2010)",
        "grado_key": "PROCEDURA_ADR",
        "grado_label": "Procedura ADR",
        "table_code": "A25-MEDIAZIONE",
        "table_label": "Tabella 25 - Profilo mediazione",
        "calc_mode": "per_fasi_adr",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["attivazione", "rivitalizzazione", "conciliazione"],
        "suggested_practice_id": "mediazione",
        "summary": "Mediazione civile con riparto operativo su attivazione, rivitalizzazione e conciliazione.",
        "base_note": "Riparto operativo derivato dal compenso unico stragiudiziale, con fasi ADR dedicate.",
    },
    {
        "profile_code": "negoziazione_assistita",
        "materia_key": "NEGOZIAZIONE_ASSISTITA",
        "materia_label": "Negoziazione Assistita (D.L. 132/2014)",
        "grado_key": "PROCEDURA_ADR",
        "grado_label": "Procedura ADR",
        "table_code": "A25-NEGOZIAZIONE",
        "table_label": "Tabella 25 - Profilo negoziazione assistita",
        "calc_mode": "per_fasi_adr",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["attivazione", "negoziazione", "conciliazione"],
        "suggested_practice_id": "negoziazione_assistita",
        "summary": "Negoziazione assistita con riparto operativo delle fasi ADR.",
        "base_note": "Riparto operativo derivato dal compenso unico stragiudiziale, con fase di negoziazione dedicata.",
    },
]

OPTION_ROWS: List[Dict[str, Any]] = [
    {
        "option_code": "spese_generali_15",
        "label": "Spese generali forfettarie",
        "option_kind": "maggiorazione",
        "value_type": "percent",
        "value": 15.0,
        "default_checked": True,
        "domains": ["tariffario", "preventivi", "parcelle"],
        "description": "Maggiorazione forfettaria del 15% sul compenso professionale.",
        "reference_code": "dm55_art2",
    },
    {
        "option_code": "bonus_telematico_30",
        "label": "Bonus atti telematici",
        "option_kind": "maggiorazione",
        "value_type": "percent",
        "value": 30.0,
        "default_checked": False,
        "domains": ["tariffario", "preventivi"],
        "description": "Aumento per atti telematici idonei alla ricerca testuale.",
        "reference_code": "dm55_art4bis",
    },
    {
        "option_code": "variazione_fasi_pm50",
        "label": "Variazione per fase",
        "option_kind": "forbice",
        "value_type": "percent_range",
        "value_min": -50.0,
        "value_max": 50.0,
        "default_checked": True,
        "domains": ["tariffario", "preventivi", "parcelle"],
        "description": "La variazione del compenso per singola fase resta contenuta entro il +/-50%.",
        "reference_code": "dm55_art4",
    },
    {
        "option_code": "compenso_orario_200_500",
        "label": "Compenso orario",
        "option_kind": "alternativa",
        "value_type": "range",
        "value_min": 200.0,
        "value_max": 500.0,
        "default_checked": False,
        "domains": ["tariffario", "preventivi", "conferimenti"],
        "description": "Compenso pattizio orario nel range previsto dal regolamento.",
        "reference_code": "dm55_art22bis",
    },
    {
        "option_code": "cpa_4",
        "label": "Contributo integrativo Cassa Forense",
        "option_kind": "maggiorazione_fiscale",
        "value_type": "percent",
        "value": 4.0,
        "default_checked": True,
        "domains": ["preventivi", "parcelle", "fatturazione_elettronica"],
        "description": "Contributo integrativo del 4% addebitabile al cliente.",
        "reference_code": "l576_art11",
    },
    {
        "option_code": "iva_22",
        "label": "IVA ordinaria",
        "option_kind": "maggiorazione_fiscale",
        "value_type": "percent",
        "value": 22.0,
        "default_checked": True,
        "domains": ["preventivi", "parcelle", "fatturazione_elettronica"],
        "description": "IVA ordinaria calcolata sulla base imponibile comprensiva di CPA, salvo regimi speciali.",
        "reference_code": "dpr633_art15",
    },
    {
        "option_code": "anticipazioni_art15",
        "label": "Anticipazioni ex art. 15",
        "option_kind": "esclusione",
        "value_type": "manual_amount",
        "default_checked": False,
        "domains": ["preventivi", "parcelle", "fatturazione_elettronica"],
        "description": "Spese vive anticipate in nome e per conto del cliente, escluse da imponibile IVA.",
        "reference_code": "dpr633_art15",
    },
    {
        "option_code": "equo_compenso_check",
        "label": "Verifica equo compenso",
        "option_kind": "compliance",
        "value_type": "flag",
        "default_checked": True,
        "domains": ["tariffario", "preventivi", "conferimenti"],
        "description": "Controllo di coerenza rispetto al presidio dell'equo compenso.",
        "reference_code": "l49_equo_compenso",
    },
]

FATTURAZIONE_ROWS: List[Dict[str, Any]] = [
    {
        "channel_code": "preventivo_guidato",
        "label": "Preventivo guidato",
        "channel_kind": "documento_interno",
        "status": "operativo",
        "description": "Il tariffario puo generare una bozza di preventivo con voci, fasi e riferimenti normativi.",
        "target": "preventivi",
        "reference_code": "l247_art13",
    },
    {
        "channel_code": "parcella_prefill",
        "label": "Parcella precompilata",
        "channel_kind": "documento_interno",
        "status": "operativo",
        "description": "Il risultato tariffario puo aprire la creazione di una parcella gia valorizzata.",
        "target": "fatturazione",
        "reference_code": "dm55_parametri",
    },
    {
        "channel_code": "fatturapa_xml",
        "label": "XML FatturaPA FPR12/FPA12",
        "channel_kind": "xml_sdi",
        "status": "operativo",
        "description": "Esportazione XML conforme al tracciato ufficiale, pronta per caricamento su SdI o provider.",
        "target": "fatturazione_elettronica",
        "reference_code": "fatturapa_tracciato",
    },
    {
        "channel_code": "agenzia_entrate_portale",
        "label": "Portale Agenzia Entrate",
        "channel_kind": "upload",
        "status": "operativo",
        "description": "Il file XML puo essere caricato sul portale Fatture e Corrispettivi dove consentito dal profilo utente.",
        "target": "fatturazione_elettronica",
        "reference_code": "ae_fatture_corrispettivi",
    },
    {
        "channel_code": "provider_cloud",
        "label": "Provider cloud di fatturazione",
        "channel_kind": "upload",
        "status": "operativo",
        "description": "Lo stesso XML puo essere caricato su cloud di intermediazione come Aruba, TeamSystem o Namirial.",
        "target": "fatturazione_elettronica",
        "reference_code": "fatturapa_tracciato",
    },
]


@lru_cache(maxsize=1)
def load_tariffario_snapshot() -> Dict[str, Dict[str, List[Optional[float]]]]:
    try:
        raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    tabelle = raw.get("tabelle", {}) if isinstance(raw, dict) else {}
    return tabelle if isinstance(tabelle, dict) else {}


def _labels_for_table(raw_table: Mapping[str, Iterable[Optional[float]]]) -> List[tuple[float, float, str]]:
    max_count = max((sum(1 for value in values if value is not None) for values in raw_table.values()), default=0)
    return _LABELS_3 if max_count <= 3 else _LABELS_7


def _reference_by_code(reference_code: str) -> Dict[str, Any]:
    for row in TARIFFARIO_REFERENCE_ROWS:
        if row["reference_code"] == reference_code:
            return dict(row)
    return {}


def tariffario_scaglioni_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    snapshot = load_tariffario_snapshot()
    for table_code, meta in TABELLE_SNAPSHOT_META.items():
        raw_table = snapshot.get(table_code) or {}
        if not raw_table:
            continue
        labels = _labels_for_table(raw_table)
        for sc_index, (valore_da, valore_a, label) in enumerate(labels, start=1):
            for raw_phase, values in raw_table.items():
                if sc_index - 1 >= len(values):
                    continue
                base = values[sc_index - 1]
                if base is None:
                    continue
                phase_key = PHASE_KEY_BY_RAW.get(raw_phase, raw_phase.lower())
                phase_value = PHASE_VALUE_BY_KEY.get(phase_key, raw_phase)
                rows.append(
                    {
                        "table_code": table_code,
                        "table_label": meta["table_label"],
                        "area_scope": meta["area_scope"],
                        "grade_scope": meta["grade_scope"],
                        "scaglione_index": sc_index,
                        "scaglione_label": label,
                        "value_from": float(valore_da),
                        "value_to": None if valore_a == float("inf") else float(valore_a),
                        "phase_key": phase_key,
                        "phase_label": PHASE_LABEL_BY_KEY.get(phase_key, phase_value),
                        "phase_value": phase_value,
                        "base_amount": float(base),
                        "minimum_amount": round(float(base) * 0.50, 2),
                        "maximum_amount": round(float(base) * 1.50, 2),
                        "source_snapshot": _SNAPSHOT_PATH.name,
                    }
                )
    return rows


def tariffario_profile_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in PROFILE_ROWS:
        item = dict(row)
        item["grado_input_value"] = GRADE_INPUT_BY_KEY.get(item.get("grado_key", ""), item.get("grado_label", ""))
        item["phase_labels"] = [PHASE_LABEL_BY_KEY.get(key, key) for key in item.get("phase_keys", [])]
        item["phase_values"] = [PHASE_VALUE_BY_KEY.get(key, key) for key in item.get("phase_keys", [])]
        refs = list(TARIFFARIO_REFERENCE_ROWS[:4])
        if item["materia_key"] in {"AMMINISTRATIVO", "TRIBUTARIO", "MEDIAZIONE", "NEGOZIAZIONE_ASSISTITA"}:
            refs.append(_reference_by_code("l49_equo_compenso"))
        item["normative_references"] = [ref for ref in refs if ref]
        rows.append(item)
    return rows


def tariffario_option_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in OPTION_ROWS:
        item = dict(row)
        item["reference"] = _reference_by_code(item.get("reference_code", ""))
        rows.append(item)
    return rows


def tariffario_fatturazione_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in FATTURAZIONE_ROWS:
        item = dict(row)
        item["reference"] = _reference_by_code(item.get("reference_code", ""))
        rows.append(item)
    return rows


def tariffario_reference_rows() -> List[Dict[str, Any]]:
    return [dict(row) for row in TARIFFARIO_REFERENCE_ROWS]


def phase_catalog_by_materia() -> Dict[str, List[Dict[str, str]]]:
    catalog: Dict[str, List[Dict[str, str]]] = {}
    for row in tariffario_profile_rows():
        materia = row["materia_label"]
        target = catalog.setdefault(materia, [])
        for key in row.get("phase_keys", []):
            value = PHASE_VALUE_BY_KEY.get(key, key)
            if any(item["value"] == value for item in target):
                continue
            target.append(
                {
                    "key": key,
                    "label": PHASE_LABEL_BY_KEY.get(key, key),
                    "value": value,
                }
            )
    return catalog


def grade_catalog_by_materia() -> Dict[str, List[str]]:
    catalog: Dict[str, List[str]] = {}
    for row in tariffario_profile_rows():
        materia = row["materia_label"]
        target = catalog.setdefault(materia, [])
        grado = row["grado_input_value"]
        if grado not in target:
            target.append(grado)
    return catalog


def profile_lookup_by_labels(materia_label: str, grado_label: str) -> Optional[Dict[str, Any]]:
    for row in tariffario_profile_rows():
        if row["materia_label"] == materia_label and row["grado_input_value"] == grado_label:
            return dict(row)
    return None


def first_profile_for_materia(materia_label: str) -> Optional[Dict[str, Any]]:
    for row in tariffario_profile_rows():
        if row["materia_label"] == materia_label:
            return dict(row)
    return None
