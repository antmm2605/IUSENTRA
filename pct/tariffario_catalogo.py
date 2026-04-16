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
    "GIUDICE_COMPETENTE": "Giudice competente",
    "GIUDICE_TUTELARE": "Giudice tutelare",
    "GIP_GUP": "GIP / GUP",
    "TRIBUNALE_MONOCRATICO": "Tribunale monocratico",
    "TRIBUNALE_COLLEGIALE": "Tribunale collegiale",
    "CORTE_ASSISE": "Corte d'Assise",
    "CORTE_APPELLO": "Corte d'Appello",
    "CORTE_APPELLO_PENALE": "Corte d'Appello penale",
    "CORTE_ASSISE_APPELLO": "Corte d'Assise d'Appello",
    "CASSAZIONE": "Corte di Cassazione",
    "TRIBUNALE_SORVEGLIANZA": "Tribunale di Sorveglianza",
    "MAGISTRATO_SORVEGLIANZA": "Magistrato di Sorveglianza",
    "TAR": "TAR",
    "CONSIGLIO_DI_STATO": "Consiglio di Stato",
    "CORTE_DEI_CONTI": "Corte dei Conti",
    "CORTE_COSTITUZIONALE": "Corte costituzionale",
    "CORTE_EDU": "Corte europea dei diritti dell'uomo",
    "CORTE_GIUSTIZIA_UE": "Corte di giustizia UE",
    "CORTE_SUPERIORE_UE": "Corte cost. / Corte europea / CGUE",
    "CONSERVATORIA_TAVOLARE": "Conservatoria / tavolare",
    "TRIBUNALE_CONCORSUALE": "Tribunale concorsuale",
    "CGT_PRIMO_GRADO": "CGT di primo grado",
    "CGT_SECONDO_GRADO": "CGT di secondo grado",
    "FUORI_GIUDIZIO": "Fuori giudizio",
    "PROCEDURA_ADR": "Procedura ADR",
}

COMPLESSITA_ROWS = [
    {
        "value": "bassa",
        "label": "Bassa",
        "description": "Valore indeterminabile collocato nel range base 26.000-52.000 EUR.",
    },
    {
        "value": "media",
        "label": "Media",
        "description": "Valore indeterminabile collocato nel range intermedio 52.000-260.000 EUR.",
    },
    {
        "value": "alta",
        "label": "Alta",
        "description": "Valore indeterminabile collocato nel range superiore 260.000-520.000 EUR.",
    },
]

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
_URL_CODICE_GIUSTIZIA_CONTABILE = "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=16G00187&atto.dataPubblicazioneGazzetta=2016-09-07&qId=&tipoDettaglio=multivigenza"
_URL_CODICE_CRISE_IMPRESA = "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2019%3B14="
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
        "reference_code": "dm55_art19",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 19",
        "description": "Per mediazione e negoziazione assistita i valori medi possono essere aumentati o diminuiti entro il limite del 50%.",
        "url": _URL_DM55,
        "domains": ["tariffario", "preventivi", "parcelle"],
    },
    {
        "reference_code": "dm55_art20_adr",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "art. 20, comma 1-bis",
        "description": "Se mediazione o negoziazione si concludono con accordo, restando ferma la fase di conciliazione, le fasi iniziali ADR aumentano del 30%.",
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
        "reference_code": "dlgs174_giustizia_contabile",
        "title": "D.Lgs. 26 agosto 2016, n. 174",
        "article": "Codice di giustizia contabile",
        "description": "Base normativa dei giudizi innanzi alla Corte dei Conti.",
        "url": _URL_CODICE_GIUSTIZIA_CONTABILE,
        "domains": ["tariffario", "preventivi"],
    },
    {
        "reference_code": "dlgs14_crisi_impresa",
        "title": "D.Lgs. 12 gennaio 2019, n. 14",
        "article": "Codice della crisi d'impresa e dell'insolvenza",
        "description": "Disciplina vigente della liquidazione giudiziale e dell'accertamento del passivo.",
        "url": _URL_CODICE_CRISE_IMPRESA,
        "domains": ["tariffario", "preventivi"],
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
    "A7": {"table_label": "Tabella 7 - Volontaria giurisdizione", "area_scope": "Civile", "grade_scope": "Tribunale / camerale"},
    "A21": {"table_label": "Tabella 21 - Giustizia amministrativa di primo grado", "area_scope": "Amministrativo", "grade_scope": "TAR / primo grado"},
    "A22": {"table_label": "Tabella 22 - Giustizia amministrativa di impugnazione", "area_scope": "Amministrativo", "grade_scope": "Consiglio di Stato / appello"},
    "A23": {"table_label": "Tabella 23 - Giustizia tributaria di primo grado", "area_scope": "Tributario", "grade_scope": "CGT primo grado"},
    "A24": {"table_label": "Tabella 24 - Giustizia tributaria di appello", "area_scope": "Tributario", "grade_scope": "CGT secondo grado"},
    "A25": {"table_label": "Tabella 25 - Prestazioni stragiudiziali", "area_scope": "Stragiudiziale", "grade_scope": "Fuori giudizio / ADR"},
}

TARIFFARIO_SNAPSHOT_SUPPLEMENTS: Dict[str, Dict[str, List[Optional[float]]]] = {
    "A15-CONVALIDA": {
        "Studio": [378.0],
        "Introduttiva": [None],
        "Istruttoria": [473.0],
        "Decisoria": [709.0],
        "Unica": [None],
        "Cautelare": [None],
    },
    "A15-MSORV": {
        "Studio": [315.0],
        "Introduttiva": [378.0],
        "Istruttoria": [None],
        "Decisoria": [945.0],
        "Unica": [None],
        "Cautelare": [None],
    },
    "A20-BIS": {
        "Studio": [168.0, 341.0, 735.0, 1344.0, 2042.0, 2835.0],
        "Introduttiva": [105.0, 341.0, 620.0, 966.0, 1302.0, 1869.0],
        "Istruttoria": [158.0, 683.0, 1344.0, 1444.0, 4536.0, 8327.0],
        "Decisoria": [158.0, 683.0, 1344.0, 2326.0, 3402.0, 4930.0],
        "Unica": [None, None, None, None, None, None],
        "Cautelare": [None, None, None, None, None, None],
    },
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
        "profile_code": "civile_appello_tribunale",
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
        "suggested_practice_id": "appello_civile",
        "summary": "Appello civile contro sentenza del Giudice di Pace, devoluto al Tribunale.",
        "base_note": "Applicazione della tabella 2 quando, ai sensi dell'art. 341 c.p.c., il giudice dell'appello è il Tribunale.",
    },
    {
        "profile_code": "civile_appello",
        "materia_key": "CIVILE_COGN",
        "materia_label": "Civile di cognizione",
        "grado_key": "CORTE_APPELLO",
        "grado_label": "Corte d'Appello",
        "table_code": "A12",
        "table_label": "Tabella 12 - Giudizi innanzi alla Corte d'Appello",
        "calc_mode": "per_fasi",
        "exact_snapshot": True,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
        "suggested_practice_id": "appello_civile",
        "summary": "Appello civile contro sentenza del Tribunale, devoluto alla Corte d'Appello.",
        "base_note": "Applicazione della tabella 12 quando, ai sensi dell'art. 341 c.p.c., il giudice dell'appello è la Corte d'Appello.",
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
        "base_note": "IUSENTRA utilizza un profilo ricostruttivo coerente con il motore esecutivo interno.",
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
        "table_label": "Profilo sintetico penale IUSENTRA",
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
        "table_label": "Profilo sintetico penale IUSENTRA",
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
        "table_label": "Profilo sintetico penale IUSENTRA",
        "calc_mode": "per_fasi",
        "exact_snapshot": False,
        "coeff": 1.6,
        "requires_value": False,
        "phase_keys": ["studio", "introduttiva", "decisionale"],
        "suggested_practice_id": "cassazione_penale",
        "summary": "Giudizio penale di legittimita con profilo ricostruttivo del motore IUSENTRA.",
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
        "table_code": "A27",
        "table_label": "Tabella 27 - Mediazione e negoziazione assistita",
        "calc_mode": "per_fasi_adr",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["attivazione", "rivitalizzazione", "conciliazione"],
        "suggested_practice_id": "mediazione",
        "summary": "Mediazione civile con riparto operativo su attivazione, rivitalizzazione e conciliazione.",
        "base_note": "Valori letti dalla tabella 27 con mapping attivazione / rivitalizzazione / conciliazione.",
    },
    {
        "profile_code": "negoziazione_assistita",
        "materia_key": "NEGOZIAZIONE_ASSISTITA",
        "materia_label": "Negoziazione Assistita (D.L. 132/2014)",
        "grado_key": "PROCEDURA_ADR",
        "grado_label": "Procedura ADR",
        "table_code": "A27",
        "table_label": "Tabella 27 - Mediazione e negoziazione assistita",
        "calc_mode": "per_fasi_adr",
        "exact_snapshot": False,
        "coeff": 1.0,
        "requires_value": True,
        "phase_keys": ["attivazione", "negoziazione", "conciliazione"],
        "suggested_practice_id": "negoziazione_assistita",
        "summary": "Negoziazione assistita con riparto operativo delle fasi ADR.",
        "base_note": "Valori letti dalla tabella 27 con mapping attivazione / negoziazione / conciliazione.",
    },
]

RULE_ROWS: List[Dict[str, Any]] = [
    {
        "rule_code": "civile_gdp",
        "materia_label": "Civile di cognizione",
        "label": "Civile ordinario davanti al Giudice di Pace",
        "summary": "Cognizione ordinaria o risarcitoria di competenza del Giudice di Pace.",
        "profile_code": "civile_gdp",
        "suggested_practice_id": "atto_citazione",
        "grado_input_value": "Giudice di Pace",
        "allowed_grade_input_values": ["Giudice di Pace"],
    },
    {
        "rule_code": "civile_cognizione_primo_grado",
        "materia_label": "Civile di cognizione",
        "label": "Cognizione ordinaria di primo grado",
        "summary": "Giudizi civili ordinari di primo grado davanti al Tribunale.",
        "profile_code": "civile_tribunale",
        "suggested_practice_id": "atto_citazione",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "civile_monitorio",
        "materia_label": "Civile di cognizione",
        "label": "Procedimento monitorio / decreto ingiuntivo",
        "summary": "Ricorsi monitori ex art. 633 c.p.c. e moduli collegati di recupero crediti.",
        "profile_code": "civile_tribunale",
        "suggested_practice_id": "decreto_ingiuntivo",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
        {
            "rule_code": "civile_opposizione_monitorio",
            "materia_label": "Civile di cognizione",
            "label": "Opposizione a decreto ingiuntivo",
            "summary": "Opposizione monitoria con sviluppo pieno delle fasi di cognizione.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "opposizione_di",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_opposizione_monitorio_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Opposizione a decreto ingiuntivo del Giudice di Pace",
            "summary": "L'opposizione si radica davanti al Giudice di Pace che ha emesso il decreto, con profilo di cognizione ordinaria davanti al GDP.",
            "profile_code": "civile_gdp",
            "suggested_practice_id": "opposizione_di",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "civile_convalida_sfratto",
        "materia_label": "Civile di cognizione",
        "label": "Convalida di sfratto / locazione",
        "summary": "Procedimenti locatizi con possibile mediazione obbligatoria da includere nel preventivo.",
        "profile_code": "civile_tribunale",
        "suggested_practice_id": "sfratto_morosita",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
        {
            "rule_code": "civile_risarcimento_danni",
            "materia_label": "Civile di cognizione",
            "label": "Risarcimento danni",
            "summary": "Azioni risarcitorie extracontrattuali o da circolazione con possibile istruttoria tecnica.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "risarcimento_danni",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_risarcimento_danni_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Risarcimento danni davanti al Giudice di Pace",
            "summary": "Azioni risarcitorie rientranti nella competenza del Giudice di Pace.",
            "profile_code": "civile_gdp",
            "suggested_practice_id": "risarcimento_danni",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "civile_appello_da_gdp",
        "materia_label": "Civile di cognizione",
        "label": "Appello civile contro sentenza del Giudice di Pace",
        "summary": "L'appello si propone al Tribunale nella cui circoscrizione ha sede il Giudice di Pace che ha pronunciato la sentenza, ai sensi dell'art. 341 c.p.c.",
        "profile_code": "civile_appello_tribunale",
        "suggested_practice_id": "appello_civile",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
        {
            "rule_code": "civile_appello",
            "materia_label": "Civile di cognizione",
            "label": "Appello civile contro sentenza del Tribunale",
            "summary": "L'appello si propone alla Corte d'Appello nella cui circoscrizione ha sede il Tribunale che ha pronunciato la sentenza, ai sensi dell'art. 341 c.p.c.",
            "profile_code": "civile_appello",
            "suggested_practice_id": "appello_civile",
            "grado_input_value": "Corte d'Appello",
            "allowed_grade_input_values": ["Corte d'Appello"],
        },
        {
            "rule_code": "civile_comparsa_risposta_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Comparsa di risposta davanti al Giudice di Pace",
            "summary": "Difesa in giudizio ordinario di cognizione davanti al Giudice di Pace.",
            "profile_code": "civile_gdp",
            "suggested_practice_id": "comparsa_risposta",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "civile_cassazione",
        "materia_label": "Civile di cognizione",
        "label": "Ricorso per Cassazione",
        "summary": "Giudizio di legittimita con focus su studio, ricorso e fase decisionale.",
        "profile_code": "civile_cassazione",
        "suggested_practice_id": "cassazione_civile",
        "grado_input_value": "Corte di Cassazione",
        "allowed_grade_input_values": ["Corte di Cassazione"],
    },
    {
        "rule_code": "esecuzione_precetto",
        "materia_label": "Esecuzione mobiliare",
        "label": "Atto di precetto",
        "summary": "Intimazione ad adempiere prodromica all'esecuzione forzata.",
        "profile_code": "esecuzione_mobiliare",
        "suggested_practice_id": "precetto",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "esecuzione_mobiliare",
        "materia_label": "Esecuzione mobiliare",
        "label": "Esecuzione mobiliare",
        "summary": "Procedure esecutive su beni mobili con fasi introduttive ed esecutive.",
        "profile_code": "esecuzione_mobiliare",
        "suggested_practice_id": "esecuzione_mobiliare",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "esecuzione_presso_terzi",
        "materia_label": "Esecuzione mobiliare",
        "label": "Pignoramento presso terzi",
        "summary": "Esecuzione presso terzi con controllo su udienza, terzo pignorato e allegati essenziali.",
        "profile_code": "esecuzione_mobiliare",
        "suggested_practice_id": "esecuzione_terzi",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "esecuzione_immobiliare",
        "materia_label": "Esecuzione immobiliare",
        "label": "Esecuzione immobiliare",
        "summary": "Procedure esecutive su beni immobili con fasi esecutive dedicate.",
        "profile_code": "esecuzione_immobiliare",
        "suggested_practice_id": "esecuzione_immobiliare",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "volontaria_giurisdizione",
        "materia_label": "Volontaria giurisdizione",
        "label": "Procedimento camerale / volontaria giurisdizione",
        "summary": "Regola generica per procedimenti camerali e di volontaria giurisdizione quando non vuoi ancora vincolare il preventivo a una sottotipologia familiare specifica.",
        "profile_code": "volontaria",
        "suggested_practice_id": "",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "lavoro_primo_grado",
        "materia_label": "Controversie di lavoro",
        "label": "Rito lavoro di primo grado",
        "summary": "Controversie di lavoro ex art. 409 c.p.c. davanti al Tribunale.",
        "profile_code": "lavoro_tribunale",
        "suggested_practice_id": "controversia_lavoro",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "lavoro_licenziamento",
        "materia_label": "Controversie di lavoro",
        "label": "Impugnazione licenziamento",
        "summary": "Controversie su licenziamento con regole del rito lavoro e possibile urgenza cautelare.",
        "profile_code": "lavoro_tribunale",
        "suggested_practice_id": "licenziamento",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "lavoro_differenze_retributive",
        "materia_label": "Controversie di lavoro",
        "label": "Differenze retributive",
        "summary": "Recupero differenze retributive e crediti di lavoro con prova documentale e conteggi.",
        "profile_code": "lavoro_tribunale",
        "suggested_practice_id": "differenze_retributive",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale", "Fuori giudizio"],
    },
    {
        "rule_code": "lavoro_appello",
        "materia_label": "Controversie di lavoro",
        "label": "Appello lavoro",
        "summary": "Giudizi di impugnazione in materia di lavoro davanti alla Corte d'Appello.",
        "profile_code": "lavoro_appello",
        "suggested_practice_id": "appello_lavoro",
        "grado_input_value": "Corte d'Appello",
        "allowed_grade_input_values": ["Corte d'Appello"],
    },
    {
        "rule_code": "lavoro_cassazione",
        "materia_label": "Controversie di lavoro",
        "label": "Cassazione lavoro",
        "summary": "Ricorsi per Cassazione in materia di lavoro con struttura concentrata sulle fasi essenziali.",
        "profile_code": "lavoro_cassazione",
        "suggested_practice_id": "appello_lavoro",
        "grado_input_value": "Corte di Cassazione",
        "allowed_grade_input_values": ["Corte di Cassazione"],
    },
    {
        "rule_code": "previdenza_giudiziale",
        "materia_label": "Previdenza e assistenza",
        "label": "Contenzioso previdenziale giudiziale",
        "summary": "Cause previdenziali e assistenziali davanti al Tribunale.",
        "profile_code": "previdenza_tribunale",
        "suggested_practice_id": "previdenza",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "previdenza_ricorso_amministrativo",
        "materia_label": "Previdenza e assistenza",
        "label": "Ricorso amministrativo / fase non giudiziale",
        "summary": "Fase amministrativa o precontenziosa INPS/INAIL collegabile poi al giudizio.",
        "profile_code": "previdenza_tribunale",
        "suggested_practice_id": "assistenza_previdenziale",
        "grado_input_value": "Fuori giudizio",
        "allowed_grade_input_values": ["Fuori giudizio", "Tribunale"],
    },
    {
        "rule_code": "previdenza_appello",
        "materia_label": "Previdenza e assistenza",
        "label": "Appello previdenza",
        "summary": "Impugnazioni previdenziali con coefficiente di appello sul profilo di primo grado.",
        "profile_code": "previdenza_appello",
        "suggested_practice_id": "previdenza",
        "grado_input_value": "Corte d'Appello",
        "allowed_grade_input_values": ["Corte d'Appello"],
    },
    {
        "rule_code": "penale_indagini",
        "materia_label": "Penale",
        "label": "Indagini preliminari / fase pre-dibattimentale",
        "summary": "Assistenza penale in indagini preliminari o attivita pre-dibattimentale.",
        "profile_code": "penale_base",
        "suggested_practice_id": "indagini_preliminari",
        "grado_input_value": "Fuori giudizio",
        "allowed_grade_input_values": ["Fuori giudizio", "Tribunale"],
    },
    {
        "rule_code": "penale_primo_grado",
        "materia_label": "Penale",
        "label": "Giudizio penale di primo grado",
        "summary": "Udienza preliminare o dibattimento penale di primo grado.",
        "profile_code": "penale_base",
        "suggested_practice_id": "dibattimento_penale",
        "grado_input_value": "Tribunale",
        "allowed_grade_input_values": ["Tribunale"],
    },
    {
        "rule_code": "penale_appello",
        "materia_label": "Penale",
        "label": "Impugnazione penale in appello",
        "summary": "Giudizio di appello in materia penale.",
        "profile_code": "penale_appello",
        "suggested_practice_id": "impugnazioni_penali",
        "grado_input_value": "Corte d'Appello",
        "allowed_grade_input_values": ["Corte d'Appello"],
    },
    {
        "rule_code": "penale_cassazione",
        "materia_label": "Penale",
        "label": "Ricorso per Cassazione penale",
        "summary": "Ricorso di legittimita in materia penale.",
        "profile_code": "penale_cassazione",
        "suggested_practice_id": "cassazione_penale",
        "grado_input_value": "Corte di Cassazione",
        "allowed_grade_input_values": ["Corte di Cassazione"],
    },
    {
        "rule_code": "amministrativo_tar",
        "materia_label": "Amministrativo / TAR-CdS",
        "label": "Ricorso al TAR",
        "summary": "Ricorsi di primo grado davanti al TAR con possibile domanda cautelare.",
        "profile_code": "amministrativo_primo_grado",
        "suggested_practice_id": "ricorso_tar",
        "grado_input_value": "TAR",
        "allowed_grade_input_values": ["TAR"],
    },
    {
        "rule_code": "amministrativo_cautelare_tar",
        "materia_label": "Amministrativo / TAR-CdS",
        "label": "Istanza cautelare al TAR",
        "summary": "Misure cautelari nel giudizio amministrativo di primo grado.",
        "profile_code": "amministrativo_primo_grado",
        "suggested_practice_id": "cautelare_sospensiva",
        "grado_input_value": "TAR",
        "allowed_grade_input_values": ["TAR"],
    },
    {
        "rule_code": "amministrativo_cds",
        "materia_label": "Amministrativo / TAR-CdS",
        "label": "Appello al Consiglio di Stato",
        "summary": "Impugnazioni in secondo grado davanti al Consiglio di Stato.",
        "profile_code": "amministrativo_appello",
        "suggested_practice_id": "appello_cds",
        "grado_input_value": "Consiglio di Stato",
        "allowed_grade_input_values": ["Consiglio di Stato"],
    },
    {
        "rule_code": "tributario_primo_grado",
        "materia_label": "Tributario / CGT",
        "label": "Ricorso alla CGT di primo grado",
        "summary": "Ricorso tributario introduttivo davanti alla Corte di Giustizia Tributaria di primo grado.",
        "profile_code": "tributario_primo_grado",
        "suggested_practice_id": "ricorso_tributario",
        "grado_input_value": "CGT di primo grado",
        "allowed_grade_input_values": ["CGT di primo grado"],
    },
    {
        "rule_code": "tributario_secondo_grado",
        "materia_label": "Tributario / CGT",
        "label": "Appello alla CGT di secondo grado",
        "summary": "Impugnazioni tributarie davanti alla Corte di Giustizia Tributaria di secondo grado.",
        "profile_code": "tributario_appello",
        "suggested_practice_id": "appello_tributario",
        "grado_input_value": "CGT di secondo grado",
        "allowed_grade_input_values": ["CGT di secondo grado"],
    },
    {
        "rule_code": "tributario_cassazione",
        "materia_label": "Tributario / CGT",
        "label": "Cassazione tributaria",
        "summary": "Ricorso di legittimita in materia tributaria.",
        "profile_code": "tributario_cassazione",
        "suggested_practice_id": "cassazione_tributaria",
        "grado_input_value": "Corte di Cassazione",
        "allowed_grade_input_values": ["Corte di Cassazione"],
    },
    {
        "rule_code": "stragiud_consulenza",
        "materia_label": "Stragiudiziale / Consulenza",
        "label": "Consulenza / parere",
        "summary": "Pareri, analisi strategiche e assistenza fuori giudizio.",
        "profile_code": "stragiudiziale",
        "suggested_practice_id": "consulenza",
        "grado_input_value": "Fuori giudizio",
        "allowed_grade_input_values": ["Fuori giudizio"],
    },
    {
        "rule_code": "stragiud_diffida",
        "materia_label": "Stragiudiziale / Consulenza",
        "label": "Diffida / messa in mora",
        "summary": "Attivita stragiudiziale di diffida e messa in mora.",
        "profile_code": "stragiudiziale",
        "suggested_practice_id": "diffida",
        "grado_input_value": "Fuori giudizio",
        "allowed_grade_input_values": ["Fuori giudizio"],
    },
    {
        "rule_code": "stragiud_sinistro",
        "materia_label": "Stragiudiziale / Consulenza",
        "label": "Sinistro stradale stragiudiziale",
        "summary": "Gestione stragiudiziale del danno prima dell'eventuale giudizio.",
        "profile_code": "stragiudiziale",
        "suggested_practice_id": "sinistro_stradale_stragiudiziale",
        "grado_input_value": "Fuori giudizio",
        "allowed_grade_input_values": ["Fuori giudizio"],
    },
    {
        "rule_code": "mediazione_adr",
        "materia_label": "Mediazione (D.Lgs. 28/2010)",
        "label": "Mediazione civile / commerciale",
        "summary": "Procedura di mediazione con calcolo dedicato alle fasi ADR.",
        "profile_code": "mediazione",
        "suggested_practice_id": "mediazione",
        "grado_input_value": "Procedura ADR",
        "allowed_grade_input_values": ["Procedura ADR"],
    },
    {
        "rule_code": "negoziazione_adr",
        "materia_label": "Negoziazione Assistita (D.L. 132/2014)",
        "label": "Negoziazione assistita",
        "summary": "Convenzione e trattativa assistita nella fase ADR.",
        "profile_code": "negoziazione_assistita",
        "suggested_practice_id": "negoziazione_assistita",
        "grado_input_value": "Procedura ADR",
        "allowed_grade_input_values": ["Procedura ADR"],
    },
]

TABELLE_SNAPSHOT_META.update(
    {
        "A5": {"table_label": "Tabella 5 - Procedimenti per convalida locatizia", "area_scope": "Civile", "grade_scope": "Tribunale"},
        "A6": {"table_label": "Tabella 6 - Atto di precetto", "area_scope": "Esecuzioni", "grade_scope": "Tribunale"},
        "A7": {"table_label": "Tabella 7 - Volontaria giurisdizione", "area_scope": "Civile", "grade_scope": "Tribunale"},
        "A8": {"table_label": "Tabella 8 - Procedimenti monitori", "area_scope": "Civile", "grade_scope": "Tribunale"},
        "A9": {"table_label": "Tabella 9 - Procedimenti di istruzione preventiva", "area_scope": "Civile", "grade_scope": "Giudice competente"},
        "A10": {"table_label": "Tabella 10 - Procedimenti cautelari", "area_scope": "Civile", "grade_scope": "Giudice competente"},
        "A11": {"table_label": "Tabella 11 - Giudizi innanzi alla Corte dei Conti", "area_scope": "Contabile", "grade_scope": "Corte dei Conti"},
        "A12": {"table_label": "Tabella 12 - Giudizi innanzi alla Corte d'Appello", "area_scope": "Civile / lavoro / previdenza", "grade_scope": "Corte d'Appello"},
        "A13": {"table_label": "Tabella 13 - Giudizi innanzi alla Corte di Cassazione e alle giurisdizioni superiori", "area_scope": "Civile / lavoro / previdenza / tributario", "grade_scope": "Corte di Cassazione"},
        "A14": {"table_label": "Tabella 14 - Giudizi innanzi alla Corte costituzionale, alla Corte europea, alla Corte di giustizia UE", "area_scope": "Giurisdizioni superiori", "grade_scope": "Corte costituzionale / Corte europea dei diritti dell'uomo / Corte di giustizia UE"},
        "A15-1": {"table_label": "Tabella 15 - Penale / Giudice di Pace", "area_scope": "Penale", "grade_scope": "Giudice di Pace"},
        "A15-2": {"table_label": "Tabella 15 - Penale / indagini preliminari", "area_scope": "Penale", "grade_scope": "Indagini preliminari"},
        "A15-3": {"table_label": "Tabella 15 - Penale / indagini difensive", "area_scope": "Penale", "grade_scope": "Fuori giudizio"},
        "A15-CONVALIDA": {"table_label": "Tabella 15 - Penale / convalida dell'arresto", "area_scope": "Penale", "grade_scope": "GIP / GUP"},
        "A15-4": {"table_label": "Tabella 15 - Penale / cautelari personali", "area_scope": "Penale", "grade_scope": "GIP / GUP"},
        "A15-5": {"table_label": "Tabella 15 - Penale / cautelari reali", "area_scope": "Penale", "grade_scope": "GIP / GUP"},
        "A15-6": {"table_label": "Tabella 15 - Penale / GIP-GUP", "area_scope": "Penale", "grade_scope": "GIP / GUP"},
        "A15-7": {"table_label": "Tabella 15 - Penale / Tribunale monocratico", "area_scope": "Penale", "grade_scope": "Tribunale monocratico"},
        "A15-8": {"table_label": "Tabella 15 - Penale / Tribunale collegiale", "area_scope": "Penale", "grade_scope": "Tribunale collegiale"},
        "A15-9": {"table_label": "Tabella 15 - Penale / Corte d'Assise", "area_scope": "Penale", "grade_scope": "Corte d'Assise"},
        "A15-10": {"table_label": "Tabella 15 - Penale / Corte d'Appello", "area_scope": "Penale", "grade_scope": "Corte d'Appello penale"},
        "A15-11": {"table_label": "Tabella 15 - Penale / Tribunale di Sorveglianza", "area_scope": "Penale", "grade_scope": "Tribunale di Sorveglianza"},
        "A15-MSORV": {"table_label": "Tabella 15 - Penale / Magistrato di Sorveglianza", "area_scope": "Penale", "grade_scope": "Magistrato di Sorveglianza"},
        "A15-12": {"table_label": "Tabella 15 - Penale / Corte d'Assise d'Appello", "area_scope": "Penale", "grade_scope": "Corte d'Assise d'Appello"},
        "A15-13": {"table_label": "Tabella 15 - Penale / Cassazione e giurisdizioni superiori", "area_scope": "Penale", "grade_scope": "Corte di Cassazione"},
        "A16": {"table_label": "Tabella 16 - Procedure esecutive mobiliari", "area_scope": "Esecuzioni", "grade_scope": "Tribunale"},
        "A17": {"table_label": "Tabella 17 - Esecuzione presso terzi / consegna / rilascio", "area_scope": "Esecuzioni", "grade_scope": "Tribunale"},
        "A18": {"table_label": "Tabella 18 - Procedure esecutive immobiliari", "area_scope": "Esecuzioni", "grade_scope": "Tribunale"},
        "A19": {"table_label": "Tabella 19 - Iscrizione ipotecaria / affari tavolari", "area_scope": "Ipotecaria / tavolare", "grade_scope": "Conservatoria / tavolare"},
        "A20": {"table_label": "Tabella 20 - Procedimenti per dichiarazione di fallimento", "area_scope": "Crisi d'impresa", "grade_scope": "Tribunale concorsuale"},
        "A20-BIS": {"table_label": "Tabella 20-bis - Accertamento del passivo nel fallimento e nella liquidazione giudiziale", "area_scope": "Crisi d'impresa", "grade_scope": "Tribunale concorsuale"},
        "A26": {"table_label": "Tabella 26 - Arbitrato", "area_scope": "Speciali", "grade_scope": "Procedura ADR"},
        "A27": {"table_label": "Tabella 27 - Mediazione e negoziazione assistita", "area_scope": "ADR", "grade_scope": "Procedura ADR"},
    }
)


def _upsert_rows(rows: List[Dict[str, Any]], key_name: str, incoming: Iterable[Dict[str, Any]]) -> None:
    index = {row.get(key_name): pos for pos, row in enumerate(rows)}
    for row in incoming:
        key = row.get(key_name)
        if key in index:
            rows[index[key]] = row
        else:
            rows.append(row)
            index[key] = len(rows) - 1


_upsert_rows(
    PROFILE_ROWS,
    "profile_code",
    [
        {
            "profile_code": "civile_appello_tribunale",
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
            "suggested_practice_id": "appello_civile",
            "summary": "Appello civile contro sentenza del Giudice di Pace, deciso dal Tribunale.",
            "base_note": "Calcolo diretto sulla tabella 2 quando, ai sensi dell'art. 341 c.p.c., il giudice dell'appello è il Tribunale.",
        },
        {
            "profile_code": "civile_appello",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "CORTE_APPELLO",
            "grado_label": "Corte d'Appello",
            "table_code": "A12",
            "table_label": "Tabella 12 - Giudizi innanzi alla Corte d'Appello",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "appello_civile",
            "summary": "Appello civile contro sentenza del Tribunale, deciso dalla Corte d'Appello.",
            "base_note": "Calcolo diretto sulla tabella 12 quando, ai sensi dell'art. 341 c.p.c., il giudice dell'appello è la Corte d'Appello.",
        },
        {
            "profile_code": "civile_cassazione",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "CASSAZIONE",
            "grado_label": "Corte di Cassazione",
            "table_code": "A13",
            "table_label": "Tabella 13 - Giudizi in Cassazione",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "cassazione_civile",
            "summary": "Giudizi civili di legittimita davanti alla Corte di Cassazione.",
            "base_note": "Calcolo diretto sulla tabella 13 del D.M. 147/2022.",
        },
        {
            "profile_code": "civile_monitorio_gdp",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "GIUDICE_DI_PACE",
            "grado_label": "Giudice di Pace",
            "table_code": "A8",
            "table_label": "Tabella 8 - Procedimenti monitori",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "decreto_ingiuntivo",
            "summary": "Procedimenti monitori davanti al Giudice di Pace.",
            "base_note": "Compenso unico tabellare ex tabella 8 per monitorio di competenza del Giudice di Pace.",
        },
        {
            "profile_code": "civile_monitorio",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A8",
            "table_label": "Tabella 8 - Procedimenti monitori",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "decreto_ingiuntivo",
            "summary": "Procedimenti monitori e ricorsi per decreto ingiuntivo.",
            "base_note": "Compenso unico tabellare ex tabella 8.",
        },
        {
            "profile_code": "civile_convalida_locatizia",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A5",
            "table_label": "Tabella 5 - Procedimenti per convalida locatizia",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "sfratto_morosita",
            "summary": "Convalida di sfratto e procedimenti locatizi speciali.",
            "base_note": "Calcolo diretto sulla tabella 5 del D.M. 147/2022.",
        },
        {
            "profile_code": "lavoro_appello",
            "materia_key": "LAVORO",
            "materia_label": "Controversie di lavoro",
            "grado_key": "CORTE_APPELLO",
            "grado_label": "Corte d'Appello",
            "table_code": "A12",
            "table_label": "Tabella 12 - Giudizi innanzi alla Corte d'Appello",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "appello_lavoro",
            "summary": "Appello in materia di lavoro.",
            "base_note": "Per il secondo grado il motore usa la tabella 12 e non piu coefficienti ricostruttivi.",
        },
        {
            "profile_code": "lavoro_cassazione",
            "materia_key": "LAVORO",
            "materia_label": "Controversie di lavoro",
            "grado_key": "CASSAZIONE",
            "grado_label": "Corte di Cassazione",
            "table_code": "A13",
            "table_label": "Tabella 13 - Giudizi in Cassazione",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "cassazione_lavoro",
            "summary": "Giudizio di legittimita in materia di lavoro.",
            "base_note": "Calcolo diretto sulla tabella 13.",
        },
        {
            "profile_code": "previdenza_appello",
            "materia_key": "PREVIDENZA",
            "materia_label": "Previdenza e assistenza",
            "grado_key": "CORTE_APPELLO",
            "grado_label": "Corte d'Appello",
            "table_code": "A12",
            "table_label": "Tabella 12 - Giudizi innanzi alla Corte d'Appello",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "appello_previdenza",
            "summary": "Appello in materia previdenziale e assistenziale.",
            "base_note": "Calcolo diretto sulla tabella 12.",
        },
        {
            "profile_code": "previdenza_cassazione",
            "materia_key": "PREVIDENZA",
            "materia_label": "Previdenza e assistenza",
            "grado_key": "CASSAZIONE",
            "grado_label": "Corte di Cassazione",
            "table_code": "A13",
            "table_label": "Tabella 13 - Giudizi in Cassazione",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "cassazione_previdenza",
            "summary": "Ricorso per Cassazione in materia previdenziale e assistenziale.",
            "base_note": "Calcolo diretto sulla tabella 13.",
        },
    ],
)

_upsert_rows(
    RULE_ROWS,
    "rule_code",
    [
        {
            "rule_code": "civile_monitorio_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Procedimento monitorio / decreto ingiuntivo davanti al Giudice di Pace",
            "summary": "Ricorsi monitori di competenza del Giudice di Pace con compenso unico tabellare.",
            "profile_code": "civile_monitorio_gdp",
            "suggested_practice_id": "decreto_ingiuntivo",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "civile_monitorio",
            "materia_label": "Civile di cognizione",
            "label": "Procedimento monitorio / decreto ingiuntivo",
            "summary": "Ricorsi monitori ex art. 633 c.p.c. con compenso unico tabellare.",
            "profile_code": "civile_monitorio",
            "suggested_practice_id": "decreto_ingiuntivo",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_convalida_sfratto",
            "materia_label": "Civile di cognizione",
            "label": "Convalida di sfratto / locazione",
            "summary": "Procedimenti locatizi speciali con tabella 5 e possibile integrazione ADR.",
            "profile_code": "civile_convalida_locatizia",
            "suggested_practice_id": "sfratto_morosita",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "esecuzione_precetto",
            "materia_label": "Esecuzione mobiliare",
            "label": "Atto di precetto",
            "summary": "Intimazione ad adempiere prodromica all'esecuzione forzata.",
            "profile_code": "esecuzione_precetto",
            "suggested_practice_id": "precetto",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "esecuzione_presso_terzi",
            "materia_label": "Esecuzione mobiliare",
            "label": "Pignoramento presso terzi",
            "summary": "Procedure esecutive presso terzi con tabella 17.",
            "profile_code": "esecuzione_presso_terzi",
            "suggested_practice_id": "esecuzione_terzi",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "lavoro_cassazione",
            "materia_label": "Controversie di lavoro",
            "label": "Ricorso per Cassazione in materia di lavoro",
            "summary": "Giudizio di legittimita in materia di lavoro.",
            "profile_code": "lavoro_cassazione",
            "suggested_practice_id": "cassazione_lavoro",
            "grado_input_value": "Corte di Cassazione",
            "allowed_grade_input_values": ["Corte di Cassazione"],
        },
        {
            "rule_code": "previdenza_appello",
            "materia_label": "Previdenza e assistenza",
            "label": "Appello previdenziale / assistenziale",
            "summary": "Secondo grado in materia previdenziale e assistenziale.",
            "profile_code": "previdenza_appello",
            "suggested_practice_id": "appello_previdenza",
            "grado_input_value": "Corte d'Appello",
            "allowed_grade_input_values": ["Corte d'Appello"],
        },
        {
            "rule_code": "previdenza_cassazione",
            "materia_label": "Previdenza e assistenza",
            "label": "Ricorso per Cassazione previdenziale / assistenziale",
            "summary": "Giudizio di legittimita in materia previdenziale e assistenziale.",
            "profile_code": "previdenza_cassazione",
            "suggested_practice_id": "cassazione_previdenza",
            "grado_input_value": "Corte di Cassazione",
            "allowed_grade_input_values": ["Corte di Cassazione"],
        },
        {
            "rule_code": "tributario_cassazione",
            "materia_label": "Tributario / CGT",
            "label": "Ricorso per Cassazione tributaria",
            "summary": "Giudizio di legittimita sulle controversie tributarie.",
            "profile_code": "tributario_cassazione",
            "suggested_practice_id": "cassazione_tributaria",
            "grado_input_value": "Corte di Cassazione",
            "allowed_grade_input_values": ["Corte di Cassazione"],
        },
        {
            "rule_code": "arbitrato_rituale",
            "materia_label": "Arbitrato",
            "label": "Arbitrato rituale / irrituale",
            "summary": "Procedimento arbitrale con compenso unico tabellare.",
            "profile_code": "arbitrato",
            "suggested_practice_id": "arbitrato",
            "grado_input_value": "Procedura ADR",
            "allowed_grade_input_values": ["Procedura ADR"],
        },
        {
            "rule_code": "recupero_crediti_monitorio",
            "materia_label": "Civile di cognizione",
            "label": "Recupero crediti con procedimento monitorio",
            "summary": "Recupero crediti tramite ricorso per decreto ingiuntivo.",
            "profile_code": "civile_monitorio",
            "suggested_practice_id": "recupero_crediti",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "recupero_crediti_monitorio_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Recupero crediti monitorio davanti al Giudice di Pace",
            "summary": "Recupero crediti tramite ricorso monitorio rientrante nella competenza del Giudice di Pace.",
            "profile_code": "civile_monitorio_gdp",
            "suggested_practice_id": "recupero_crediti",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "recupero_crediti_ordinario",
            "materia_label": "Civile di cognizione",
            "label": "Recupero crediti con giudizio ordinario",
            "summary": "Recupero crediti in cognizione ordinaria o opposizione piena.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "recupero_crediti",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "recupero_crediti_ordinario_gdp",
            "materia_label": "Civile di cognizione",
            "label": "Recupero crediti ordinario davanti al Giudice di Pace",
            "summary": "Recupero crediti in cognizione ordinaria quando la competenza appartiene al Giudice di Pace.",
            "profile_code": "civile_gdp",
            "suggested_practice_id": "recupero_crediti",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "civile_comparsa_risposta",
            "materia_label": "Civile di cognizione",
            "label": "Comparsa di costituzione e risposta",
            "summary": "Difesa nel giudizio civile ordinario di primo grado.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "comparsa_risposta",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "esecuzione_pignoramento_mobiliare",
            "materia_label": "Esecuzione mobiliare",
            "label": "Pignoramento mobiliare",
            "summary": "Pignoramento mobiliare nel processo esecutivo.",
            "profile_code": "esecuzione_mobiliare",
            "suggested_practice_id": "pignoramento",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_opposizione_esecutiva",
            "materia_label": "Civile di cognizione",
            "label": "Opposizione all'esecuzione",
            "summary": "Opposizione all'esecuzione ex artt. 615 e 619 c.p.c. in sede di cognizione.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "opposizione_esecutiva",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_opposizione_atti_esecutivi",
            "materia_label": "Civile di cognizione",
            "label": "Opposizione agli atti esecutivi",
            "summary": "Opposizione agli atti esecutivi ex art. 617 c.p.c. con profilo di cognizione ordinaria.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "opposizione_atti_esecutivi",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_separazione_consensuale",
            "materia_label": "Volontaria giurisdizione",
            "label": "Separazione consensuale",
            "summary": "Domanda congiunta di separazione personale con regola camerale e compenso unico ex tabella 7.",
            "profile_code": "volontaria",
            "suggested_practice_id": "separazione_consensuale",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_separazione_giudiziale",
            "materia_label": "Civile di cognizione",
            "label": "Separazione giudiziale",
            "summary": "Procedimento contenzioso di separazione.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "separazione_giudiziale",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_divorzio_congiunto",
            "materia_label": "Volontaria giurisdizione",
            "label": "Divorzio congiunto",
            "summary": "Procedimento congiunto in materia di crisi familiare.",
            "profile_code": "volontaria",
            "suggested_practice_id": "divorzio_congiunto",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_divorzio_giudiziale",
            "materia_label": "Civile di cognizione",
            "label": "Divorzio giudiziale",
            "summary": "Procedimento contenzioso di divorzio.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "divorzio_giudiziale",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_camerale",
            "materia_label": "Volontaria giurisdizione",
            "label": "Procedimento camerale di famiglia",
            "summary": "Procedimento camerale familiare non pienamente contenzioso, con regola di volontaria giurisdizione.",
            "profile_code": "volontaria",
            "suggested_practice_id": "procedimenti_famiglia",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_procedimenti_minori",
            "materia_label": "Civile di cognizione",
            "label": "Procedimenti relativi ai minori",
            "summary": "Procedimenti relativi ai minori trattati con profilo prudenziale di cognizione davanti al tribunale competente.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "procedimenti_minori",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_modifica_condizioni",
            "materia_label": "Civile di cognizione",
            "label": "Modifica condizioni separazione / divorzio",
            "summary": "Ricorso per revisione di affidamento, mantenimento o altre condizioni gia fissate nel procedimento familiare.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "modifica_condizioni_famiglia",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_responsabilita_genitoriale",
            "materia_label": "Civile di cognizione",
            "label": "Responsabilita genitoriale e affidamento",
            "summary": "Controversie su affidamento, collocamento, mantenimento e responsabilita genitoriale davanti al tribunale competente.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "responsabilita_genitoriale",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "famiglia_reclamo",
            "materia_label": "Civile di cognizione",
            "label": "Reclamo famiglia / minori",
            "summary": "Reclamo sui provvedimenti temporanei e urgenti del rito persone, minorenni e famiglie davanti alla Corte d'Appello.",
            "profile_code": "civile_appello",
            "suggested_practice_id": "reclamo_famiglia_minori",
            "grado_input_value": "Corte d'Appello",
            "allowed_grade_input_values": ["Corte d'Appello"],
        },
        {
            "rule_code": "famiglia_appello_minori",
            "materia_label": "Civile di cognizione",
            "label": "Appello famiglia / minori",
            "summary": "Appello contro la sentenza del tribunale in materia di persone, minorenni e famiglie davanti alla Corte d'Appello.",
            "profile_code": "civile_appello",
            "suggested_practice_id": "appello_famiglia_minori",
            "grado_input_value": "Corte d'Appello",
            "allowed_grade_input_values": ["Corte d'Appello"],
        },
        {
            "rule_code": "volontaria_amministrazione_sostegno",
            "materia_label": "Volontaria giurisdizione",
            "label": "Amministrazione di sostegno",
            "summary": "Ricorso e gestione del procedimento di amministrazione di sostegno davanti al giudice tutelare con compenso unico tabellare.",
            "profile_code": "volontaria_giudice_tutelare",
            "suggested_practice_id": "amministrazione_sostegno",
            "grado_input_value": "Giudice tutelare",
            "allowed_grade_input_values": ["Giudice tutelare"],
        },
        {
            "rule_code": "volontaria_nomina_ads",
            "materia_label": "Volontaria giurisdizione",
            "label": "Nomina amministratore di sostegno",
            "summary": "Ricorso iniziale per la nomina dell'amministratore di sostegno davanti al giudice tutelare.",
            "profile_code": "volontaria_giudice_tutelare",
            "suggested_practice_id": "nomina_amministratore_sostegno",
            "grado_input_value": "Giudice tutelare",
            "allowed_grade_input_values": ["Giudice tutelare"],
        },
        {
            "rule_code": "volontaria_modifica_ads",
            "materia_label": "Volontaria giurisdizione",
            "label": "Modifica / revoca amministrazione di sostegno",
            "summary": "Istanza per modificare i poteri, sostituire o revocare l'amministratore di sostegno davanti al giudice tutelare.",
            "profile_code": "volontaria_giudice_tutelare",
            "suggested_practice_id": "modifica_revoca_ads",
            "grado_input_value": "Giudice tutelare",
            "allowed_grade_input_values": ["Giudice tutelare"],
        },
        {
            "rule_code": "volontaria_tutela_curatela",
            "materia_label": "Volontaria giurisdizione",
            "label": "Tutela / curatela ordinaria",
            "summary": "Procedimenti ordinari di tutela o curatela davanti al giudice tutelare con compenso unico tabellare.",
            "profile_code": "volontaria_giudice_tutelare",
            "suggested_practice_id": "tutela_curatela",
            "grado_input_value": "Giudice tutelare",
            "allowed_grade_input_values": ["Giudice tutelare"],
        },
        {
            "rule_code": "volontaria_reclamo_giudice_tutelare",
            "materia_label": "Volontaria giurisdizione",
            "label": "Reclamo avverso decreto del giudice tutelare",
            "summary": "Reclamo al tribunale competente contro un decreto del giudice tutelare, con regola di volontaria giurisdizione.",
            "profile_code": "volontaria",
            "suggested_practice_id": "reclamo_giudice_tutelare",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
        {
            "rule_code": "civile_procedure_particolari",
            "materia_label": "Civile di cognizione",
            "label": "Procedure civili particolari / varie",
            "summary": "Contenitore operativo per procedimenti civili speciali non ancora tipizzati in modo autonomo.",
            "profile_code": "civile_tribunale",
            "suggested_practice_id": "procedure_particolari",
            "grado_input_value": "Tribunale",
            "allowed_grade_input_values": ["Tribunale"],
        },
    ],
)

_upsert_rows(
    PROFILE_ROWS,
    "profile_code",
    [
        {
            "profile_code": "civile_istruzione_preventiva",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "GIUDICE_COMPETENTE",
            "grado_label": "Giudice competente",
            "table_code": "A9",
            "table_label": "Tabella 9 - Procedimenti di istruzione preventiva",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria"],
            "suggested_practice_id": "istruzione_preventiva",
            "summary": "Procedimenti di istruzione preventiva, compresa la consulenza tecnica preventiva.",
            "base_note": "Calcolo diretto sulla tabella 9 del D.M. 147/2022.",
        },
        {
            "profile_code": "civile_cautelare",
            "materia_key": "CIVILE_COGN",
            "materia_label": "Civile di cognizione",
            "grado_key": "GIUDICE_COMPETENTE",
            "grado_label": "Giudice competente",
            "table_code": "A10",
            "table_label": "Tabella 10 - Procedimenti cautelari",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "cautelare_civile",
            "summary": "Procedimenti cautelari civili e misure urgenti davanti al giudice competente.",
            "base_note": "Calcolo diretto sulla tabella 10 del D.M. 147/2022.",
        },
        {
            "profile_code": "contabile_corte_conti",
            "materia_key": "CONTABILE",
            "materia_label": "Contabile / Corte dei Conti",
            "grado_key": "CORTE_DEI_CONTI",
            "grado_label": "Corte dei Conti",
            "table_code": "A11",
            "table_label": "Tabella 11 - Giudizi innanzi alla Corte dei Conti",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "giudizio_corte_conti",
            "summary": "Giudizi di responsabilita, pensionistici o contabili davanti alla Corte dei Conti.",
            "base_note": "Calcolo diretto sulla tabella 11 del D.M. 147/2022.",
        },
        {
            "profile_code": "giurisdizioni_superiori_corte_costituzionale",
            "materia_key": "GIURISDIZIONI_SUPERIORI",
            "materia_label": "Giurisdizioni superiori / europee",
            "grado_key": "CORTE_COSTITUZIONALE",
            "grado_label": "Corte costituzionale",
            "table_code": "A14",
            "table_label": "Tabella 14 - Giudizi innanzi alla Corte costituzionale, alla Corte europea, alla Corte di giustizia UE",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "giurisdizioni_superiori",
            "summary": "Giudizi davanti alla Corte costituzionale con tabella dedicata.",
            "base_note": "Tabella 14 del D.M. 147/2022, stessa voce tariffaria delle altre giurisdizioni superiori sovranazionali.",
        },
        {
            "profile_code": "giurisdizioni_superiori_corte_edu",
            "materia_key": "GIURISDIZIONI_SUPERIORI",
            "materia_label": "Giurisdizioni superiori / europee",
            "grado_key": "CORTE_EDU",
            "grado_label": "Corte europea dei diritti dell'uomo",
            "table_code": "A14",
            "table_label": "Tabella 14 - Giudizi innanzi alla Corte costituzionale, alla Corte europea, alla Corte di giustizia UE",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "giurisdizioni_superiori",
            "summary": "Giudizi davanti alla Corte europea dei diritti dell'uomo con tabella dedicata.",
            "base_note": "Tabella 14 del D.M. 147/2022, riferita nella UI alla Corte europea dei diritti dell'uomo per distinguere la sede sovranazionale.",
        },
        {
            "profile_code": "giurisdizioni_superiori_corte_giustizia_ue",
            "materia_key": "GIURISDIZIONI_SUPERIORI",
            "materia_label": "Giurisdizioni superiori / europee",
            "grado_key": "CORTE_GIUSTIZIA_UE",
            "grado_label": "Corte di giustizia UE",
            "table_code": "A14",
            "table_label": "Tabella 14 - Giudizi innanzi alla Corte costituzionale, alla Corte europea, alla Corte di giustizia UE",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "giurisdizioni_superiori",
            "summary": "Giudizi davanti alla Corte di giustizia dell'Unione europea con tabella dedicata.",
            "base_note": "Tabella 14 del D.M. 147/2022, usata in UI per il foro CGUE separato dalle altre sedi costituzionali o convenzionali.",
        },
        {
            "profile_code": "penale_giudice_pace",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "GIUDICE_DI_PACE",
            "grado_label": "Giudice di Pace",
            "table_code": "A15-1",
            "table_label": "Tabella 15 - Penale / Giudice di Pace",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "giudice_pace_penale",
            "summary": "Giudizi penali davanti al Giudice di Pace.",
            "base_note": "Valori letti dalla tabella 15, colonna Giudice di Pace.",
        },
        {
            "profile_code": "penale_indagini_difensive",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "FUORI_GIUDIZIO",
            "grado_label": "Fuori giudizio",
            "table_code": "A15-3",
            "table_label": "Tabella 15 - Penale / indagini difensive",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "istruttoria"],
            "suggested_practice_id": "indagini_difensive",
            "summary": "Attivita difensiva investigativa ex artt. 391-bis e seguenti c.p.p.",
            "base_note": "Valori letti dalla tabella 15, colonna indagini difensive.",
        },
        {
            "profile_code": "penale_convalida_arresto",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "GIP_GUP",
            "grado_label": "GIP / GUP",
            "table_code": "A15-CONVALIDA",
            "table_label": "Tabella 15 - Penale / convalida dell'arresto",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "istruttoria", "decisionale"],
            "suggested_practice_id": "convalida_arresto",
            "summary": "Procedimento di convalida dell'arresto o del fermo davanti al GIP.",
            "base_note": "Valori integrati dal testo ufficiale della tabella 15, colonna convalida dell'arresto.",
        },
        {
            "profile_code": "penale_cautelari_personali",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "GIP_GUP",
            "grado_label": "GIP / GUP",
            "table_code": "A15-4",
            "table_label": "Tabella 15 - Penale / cautelari personali",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "misure_cautelari_penali",
            "summary": "Misure cautelari personali in fase penale.",
            "base_note": "Valori letti dalla tabella 15, colonna cautelari personali.",
        },
        {
            "profile_code": "penale_cautelari_reali",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "GIP_GUP",
            "grado_label": "GIP / GUP",
            "table_code": "A15-5",
            "table_label": "Tabella 15 - Penale / cautelari reali",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "misure_cautelari_penali",
            "summary": "Misure cautelari reali in fase penale.",
            "base_note": "Valori letti dalla tabella 15, colonna cautelari reali.",
        },
        {
            "profile_code": "penale_magistrato_sorveglianza",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "MAGISTRATO_SORVEGLIANZA",
            "grado_label": "Magistrato di Sorveglianza",
            "table_code": "A15-MSORV",
            "table_label": "Tabella 15 - Penale / Magistrato di Sorveglianza",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "sorveglianza_penale",
            "summary": "Procedimenti davanti al Magistrato di Sorveglianza.",
            "base_note": "Valori integrati dal testo ufficiale della tabella 15, colonna Magistrato di Sorveglianza.",
        },
        {
            "profile_code": "affari_ipotecari_tavolari",
            "materia_key": "AFFARI_IPOTECARI",
            "materia_label": "Iscrizione ipotecaria / affari tavolari",
            "grado_key": "CONSERVATORIA_TAVOLARE",
            "grado_label": "Conservatoria / tavolare",
            "table_code": "A19",
            "table_label": "Tabella 19 - Iscrizione ipotecaria / affari tavolari",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "iscrizione_ipotecaria_tavolare",
            "summary": "Affari ipotecari e tavolari con compenso unico tabellare.",
            "base_note": "Compenso unico diretto sulla tabella 19 del D.M. 147/2022.",
        },
        {
            "profile_code": "crisi_impresa_apertura",
            "materia_key": "CRISI_IMPRESA",
            "materia_label": "Crisi d'impresa / concorsuale",
            "grado_key": "TRIBUNALE_CONCORSUALE",
            "grado_label": "Tribunale concorsuale",
            "table_code": "A20",
            "table_label": "Tabella 20 - Procedimenti per dichiarazione di fallimento",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "apertura_liquidazione_giudiziale",
            "summary": "Procedimenti di apertura della procedura concorsuale con compenso unico tabellare.",
            "base_note": "Compenso unico diretto sulla tabella 20 del D.M. 147/2022, oggi coordinata con la liquidazione giudiziale.",
        },
        {
            "profile_code": "crisi_impresa_passivo",
            "materia_key": "CRISI_IMPRESA",
            "materia_label": "Crisi d'impresa / concorsuale",
            "grado_key": "TRIBUNALE_CONCORSUALE",
            "grado_label": "Tribunale concorsuale",
            "table_code": "A20-BIS",
            "table_label": "Tabella 20-bis - Accertamento del passivo nel fallimento e nella liquidazione giudiziale",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "accertamento_passivo",
            "summary": "Accertamento del passivo nella liquidazione giudiziale con tabella dedicata.",
            "base_note": "Valori integrati dal testo ufficiale della tabella 20-bis del D.M. 147/2022.",
        },
    ],
)

_upsert_rows(
    RULE_ROWS,
    "rule_code",
    [
        {
            "rule_code": "civile_istruzione_preventiva",
            "materia_label": "Civile di cognizione",
            "label": "Istruzione preventiva / ATP",
            "summary": "Procedimenti ex artt. 692 ss. c.p.c. e consulenza tecnica preventiva ai fini della composizione della lite.",
            "profile_code": "civile_istruzione_preventiva",
            "suggested_practice_id": "istruzione_preventiva",
            "grado_input_value": "Giudice competente",
            "allowed_grade_input_values": ["Giudice competente"],
        },
        {
            "rule_code": "civile_cautelare",
            "materia_label": "Civile di cognizione",
            "label": "Cautelare civile",
            "summary": "Procedimenti cautelari uniformi ex artt. 669-bis ss. c.p.c. davanti al giudice competente.",
            "profile_code": "civile_cautelare",
            "suggested_practice_id": "cautelare_civile",
            "grado_input_value": "Giudice competente",
            "allowed_grade_input_values": ["Giudice competente"],
        },
        {
            "rule_code": "penale_giudice_pace",
            "materia_label": "Penale",
            "label": "Giudizio penale davanti al Giudice di Pace",
            "summary": "Procedimenti penali attribuiti al Giudice di Pace con tabella dedicata.",
            "profile_code": "penale_giudice_pace",
            "suggested_practice_id": "giudice_pace_penale",
            "grado_input_value": "Giudice di Pace",
            "allowed_grade_input_values": ["Giudice di Pace"],
        },
        {
            "rule_code": "penale_indagini_difensive",
            "materia_label": "Penale",
            "label": "Indagini difensive",
            "summary": "Attivita difensiva investigativa con colonna dedicata della tabella penale.",
            "profile_code": "penale_indagini_difensive",
            "suggested_practice_id": "indagini_difensive",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "penale_convalida_arresto",
            "materia_label": "Penale",
            "label": "Convalida arresto / fermo",
            "summary": "Procedimento di convalida davanti al GIP con valori ufficiali distinti.",
            "profile_code": "penale_convalida_arresto",
            "suggested_practice_id": "convalida_arresto",
            "grado_input_value": "GIP / GUP",
            "allowed_grade_input_values": ["GIP / GUP"],
        },
        {
            "rule_code": "penale_cautelari_personali",
            "materia_label": "Penale",
            "label": "Misure cautelari personali",
            "summary": "Procedimenti cautelari personali in sede penale.",
            "profile_code": "penale_cautelari_personali",
            "suggested_practice_id": "misure_cautelari_penali",
            "grado_input_value": "GIP / GUP",
            "allowed_grade_input_values": ["GIP / GUP"],
        },
        {
            "rule_code": "penale_cautelari_reali",
            "materia_label": "Penale",
            "label": "Misure cautelari reali",
            "summary": "Procedimenti cautelari reali in sede penale.",
            "profile_code": "penale_cautelari_reali",
            "suggested_practice_id": "misure_cautelari_penali",
            "grado_input_value": "GIP / GUP",
            "allowed_grade_input_values": ["GIP / GUP"],
        },
        {
            "rule_code": "penale_sorveglianza_tribunale",
            "materia_label": "Penale",
            "label": "Tribunale di Sorveglianza",
            "summary": "Procedimenti davanti al Tribunale di Sorveglianza.",
            "profile_code": "penale_sorveglianza",
            "suggested_practice_id": "sorveglianza_penale",
            "grado_input_value": "Tribunale di Sorveglianza",
            "allowed_grade_input_values": ["Tribunale di Sorveglianza"],
        },
        {
            "rule_code": "penale_sorveglianza_magistrato",
            "materia_label": "Penale",
            "label": "Magistrato di Sorveglianza",
            "summary": "Procedimenti davanti al Magistrato di Sorveglianza con valori dedicati.",
            "profile_code": "penale_magistrato_sorveglianza",
            "suggested_practice_id": "sorveglianza_penale",
            "grado_input_value": "Magistrato di Sorveglianza",
            "allowed_grade_input_values": ["Magistrato di Sorveglianza"],
        },
        {
            "rule_code": "contabile_corte_conti",
            "materia_label": "Contabile / Corte dei Conti",
            "label": "Giudizio innanzi alla Corte dei Conti",
            "summary": "Profilo tabellare dedicato ai giudizi contabili e pensionistici davanti alla Corte dei Conti.",
            "profile_code": "contabile_corte_conti",
            "suggested_practice_id": "giudizio_corte_conti",
            "grado_input_value": "Corte dei Conti",
            "allowed_grade_input_values": ["Corte dei Conti"],
        },
        {
            "rule_code": "giurisdizioni_superiori_corte_costituzionale",
            "materia_label": "Giurisdizioni superiori / europee",
            "label": "Corte costituzionale",
            "summary": "Giudizi davanti alla Corte costituzionale con applicazione della tabella 14.",
            "profile_code": "giurisdizioni_superiori_corte_costituzionale",
            "suggested_practice_id": "giurisdizioni_superiori",
            "grado_input_value": "Corte costituzionale",
            "allowed_grade_input_values": ["Corte costituzionale"],
        },
        {
            "rule_code": "giurisdizioni_superiori_corte_edu",
            "materia_label": "Giurisdizioni superiori / europee",
            "label": "Corte europea dei diritti dell'uomo",
            "summary": "Giudizi davanti alla Corte europea dei diritti dell'uomo con applicazione della tabella 14.",
            "profile_code": "giurisdizioni_superiori_corte_edu",
            "suggested_practice_id": "giurisdizioni_superiori",
            "grado_input_value": "Corte europea dei diritti dell'uomo",
            "allowed_grade_input_values": ["Corte europea dei diritti dell'uomo"],
        },
        {
            "rule_code": "giurisdizioni_superiori_corte_giustizia_ue",
            "materia_label": "Giurisdizioni superiori / europee",
            "label": "Corte di giustizia UE",
            "summary": "Giudizi davanti alla Corte di giustizia dell'Unione europea con applicazione della tabella 14.",
            "profile_code": "giurisdizioni_superiori_corte_giustizia_ue",
            "suggested_practice_id": "giurisdizioni_superiori",
            "grado_input_value": "Corte di giustizia UE",
            "allowed_grade_input_values": ["Corte di giustizia UE"],
        },
        {
            "rule_code": "affari_ipotecari_tavolari",
            "materia_label": "Iscrizione ipotecaria / affari tavolari",
            "label": "Iscrizione ipotecaria / affari tavolari",
            "summary": "Affari ipotecari e tavolari con compenso unico tabellare.",
            "profile_code": "affari_ipotecari_tavolari",
            "suggested_practice_id": "iscrizione_ipotecaria_tavolare",
            "grado_input_value": "Conservatoria / tavolare",
            "allowed_grade_input_values": ["Conservatoria / tavolare"],
        },
        {
            "rule_code": "crisi_impresa_apertura",
            "materia_label": "Crisi d'impresa / concorsuale",
            "label": "Apertura liquidazione giudiziale",
            "summary": "Procedimento di apertura della procedura concorsuale con compenso unico tabellare.",
            "profile_code": "crisi_impresa_apertura",
            "suggested_practice_id": "apertura_liquidazione_giudiziale",
            "grado_input_value": "Tribunale concorsuale",
            "allowed_grade_input_values": ["Tribunale concorsuale"],
        },
        {
            "rule_code": "crisi_impresa_passivo",
            "materia_label": "Crisi d'impresa / concorsuale",
            "label": "Accertamento del passivo",
            "summary": "Domande tempestive, tardive e opposizioni nello stato passivo con tabella dedicata.",
            "profile_code": "crisi_impresa_passivo",
            "suggested_practice_id": "accertamento_passivo",
            "grado_input_value": "Tribunale concorsuale",
            "allowed_grade_input_values": ["Tribunale concorsuale"],
        },
    ],
)

_upsert_rows(
    PROFILE_ROWS,
    "profile_code",
    [
        {
            "profile_code": "penale_base",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "TRIBUNALE_MONOCRATICO",
            "grado_label": "Tribunale monocratico",
            "table_code": "A15-7",
            "table_label": "Tabella 15 - Penale / Tribunale monocratico",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "dibattimento_penale",
            "summary": "Dibattimento penale davanti al Tribunale monocratico.",
            "base_note": "Valori letti dalla tabella 15, colonna Tribunale monocratico.",
        },
        {
            "profile_code": "penale_indagini_preliminari",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "FUORI_GIUDIZIO",
            "grado_label": "Fuori giudizio",
            "table_code": "A15-2",
            "table_label": "Tabella 15 - Penale / indagini preliminari",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "indagini_preliminari",
            "summary": "Assistenza penale nella fase delle indagini preliminari.",
            "base_note": "Valori letti dalla tabella 15, colonna indagini preliminari.",
        },
        {
            "profile_code": "penale_udienza_preliminare",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "GIP_GUP",
            "grado_label": "GIP / GUP",
            "table_code": "A15-6",
            "table_label": "Tabella 15 - Penale / GIP-GUP",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "udienza_preliminare",
            "summary": "Attivita davanti al GIP/GUP e udienza preliminare.",
            "base_note": "Valori letti dalla tabella 15, colonna GIP/GUP.",
        },
        {
            "profile_code": "penale_collegiale",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "TRIBUNALE_COLLEGIALE",
            "grado_label": "Tribunale collegiale",
            "table_code": "A15-8",
            "table_label": "Tabella 15 - Penale / Tribunale collegiale",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "dibattimento_penale",
            "summary": "Dibattimento penale davanti al Tribunale collegiale.",
            "base_note": "Valori letti dalla tabella 15, colonna Tribunale collegiale.",
        },
        {
            "profile_code": "penale_assise",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "CORTE_ASSISE",
            "grado_label": "Corte d'Assise",
            "table_code": "A15-9",
            "table_label": "Tabella 15 - Penale / Corte d'Assise",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "dibattimento_penale",
            "summary": "Dibattimento penale davanti alla Corte d'Assise.",
            "base_note": "Valori letti dalla tabella 15, colonna Corte d'Assise.",
        },
        {
            "profile_code": "penale_appello",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "CORTE_APPELLO_PENALE",
            "grado_label": "Corte d'Appello penale",
            "table_code": "A15-10",
            "table_label": "Tabella 15 - Penale / Corte d'Appello",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "impugnazioni_penali",
            "summary": "Impugnazioni penali di merito davanti alla Corte d'Appello.",
            "base_note": "Valori letti dalla tabella 15, colonna Corte d'Appello.",
        },
        {
            "profile_code": "penale_sorveglianza",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "TRIBUNALE_SORVEGLIANZA",
            "grado_label": "Tribunale di Sorveglianza",
            "table_code": "A15-11",
            "table_label": "Tabella 15 - Penale / Tribunale di Sorveglianza",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "impugnazioni_penali",
            "summary": "Procedimenti di sorveglianza.",
            "base_note": "Valori letti dalla tabella 15, colonna Tribunale di Sorveglianza.",
        },
        {
            "profile_code": "penale_assise_appello",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "CORTE_ASSISE_APPELLO",
            "grado_label": "Corte d'Assise d'Appello",
            "table_code": "A15-12",
            "table_label": "Tabella 15 - Penale / Corte d'Assise d'Appello",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "suggested_practice_id": "impugnazioni_penali",
            "summary": "Impugnazioni davanti alla Corte d'Assise d'Appello.",
            "base_note": "Valori letti dalla tabella 15, colonna Corte d'Assise d'Appello.",
        },
        {
            "profile_code": "penale_cassazione",
            "materia_key": "PENALE",
            "materia_label": "Penale",
            "grado_key": "CASSAZIONE",
            "grado_label": "Corte di Cassazione",
            "table_code": "A15-13",
            "table_label": "Tabella 15 - Penale / Cassazione",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": False,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "cassazione_penale",
            "summary": "Ricorso per Cassazione in materia penale.",
            "base_note": "Valori letti dalla tabella 15, colonna Cassazione e magistrature superiori.",
        },
    ],
)

_upsert_rows(
    PROFILE_ROWS,
    "profile_code",
    [
        {
            "profile_code": "esecuzione_precetto",
            "materia_key": "ESEC_MOB",
            "materia_label": "Esecuzione mobiliare",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A6",
            "table_label": "Tabella 6 - Atto di precetto",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "precetto",
            "summary": "Atto di precetto quale fase prodromica all'esecuzione forzata.",
            "base_note": "Compenso unico tabellare ex tabella 6.",
        },
        {
            "profile_code": "esecuzione_mobiliare",
            "materia_key": "ESEC_MOB",
            "materia_label": "Esecuzione mobiliare",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A16",
            "table_label": "Tabella 16 - Procedure esecutive mobiliari",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "esecutiva"],
            "suggested_practice_id": "esecuzione_mobiliare",
            "summary": "Procedure esecutive mobiliari.",
            "base_note": "La fase esecutiva deriva dalla colonna istruttoria della tabella 16.",
        },
        {
            "profile_code": "esecuzione_presso_terzi",
            "materia_key": "ESEC_MOB",
            "materia_label": "Esecuzione mobiliare",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A17",
            "table_label": "Tabella 17 - Presso terzi / consegna / rilascio",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["introduttiva", "esecutiva"],
            "suggested_practice_id": "esecuzione_terzi",
            "summary": "Pignoramento presso terzi ed esecuzioni affini.",
            "base_note": "Le fasi operative usano la colonna introduttiva e la colonna istruttoria della tabella 17; la fase studio non e valorizzata nello snapshot ufficiale.",
        },
        {
            "profile_code": "esecuzione_immobiliare",
            "materia_key": "ESEC_IMMO",
            "materia_label": "Esecuzione immobiliare",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A18",
            "table_label": "Tabella 18 - Procedure esecutive immobiliari",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["introduttiva", "esecutiva"],
            "suggested_practice_id": "esecuzione_immobiliare",
            "summary": "Procedure esecutive immobiliari.",
            "base_note": "Le fasi operative usano la colonna introduttiva e la colonna istruttoria della tabella 18; la fase studio non e valorizzata nello snapshot ufficiale.",
        },
        {
            "profile_code": "volontaria",
            "materia_key": "VOLONTARIA",
            "materia_label": "Volontaria giurisdizione",
            "grado_key": "TRIBUNALE",
            "grado_label": "Tribunale",
            "table_code": "A7",
            "table_label": "Tabella 7 - Volontaria giurisdizione",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "separazione_consensuale",
            "summary": "Volontaria giurisdizione e procedimenti camerali.",
            "base_note": "Compenso unico tabellare ex tabella 7.",
        },
        {
            "profile_code": "volontaria_giudice_tutelare",
            "materia_key": "VOLONTARIA",
            "materia_label": "Volontaria giurisdizione",
            "grado_key": "GIUDICE_TUTELARE",
            "grado_label": "Giudice tutelare",
            "table_code": "A7",
            "table_label": "Tabella 7 - Volontaria giurisdizione",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "amministrazione_sostegno",
            "summary": "Procedimenti di volontaria giurisdizione davanti al giudice tutelare, compresa l'amministrazione di sostegno.",
            "base_note": "Compenso unico tabellare ex tabella 7 anche per i procedimenti davanti al giudice tutelare.",
        },
        {
            "profile_code": "tributario_cassazione",
            "materia_key": "TRIBUTARIO",
            "materia_label": "Tributario / CGT",
            "grado_key": "CASSAZIONE",
            "grado_label": "Corte di Cassazione",
            "table_code": "A13",
            "table_label": "Tabella 13 - Giudizi in Cassazione",
            "calc_mode": "per_fasi",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["studio", "introduttiva", "decisionale"],
            "suggested_practice_id": "cassazione_tributaria",
            "summary": "Ricorso per Cassazione in materia tributaria.",
            "base_note": "Per la legittimita il motore usa la tabella 13.",
        },
        {
            "profile_code": "mediazione",
            "materia_key": "MEDIAZIONE",
            "materia_label": "Mediazione (D.Lgs. 28/2010)",
            "grado_key": "PROCEDURA_ADR",
            "grado_label": "Procedura ADR",
            "table_code": "A27",
            "table_label": "Tabella 27 - Mediazione e negoziazione assistita",
            "calc_mode": "per_fasi_adr",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["attivazione", "rivitalizzazione", "conciliazione"],
            "suggested_practice_id": "mediazione",
            "summary": "Mediazione civile e commerciale.",
            "base_note": "Valori letti dalla tabella 27 con mapping attivazione / rivitalizzazione / conciliazione.",
        },
        {
            "profile_code": "negoziazione_assistita",
            "materia_key": "NEGOZIAZIONE_ASSISTITA",
            "materia_label": "Negoziazione Assistita (D.L. 132/2014)",
            "grado_key": "PROCEDURA_ADR",
            "grado_label": "Procedura ADR",
            "table_code": "A27",
            "table_label": "Tabella 27 - Mediazione e negoziazione assistita",
            "calc_mode": "per_fasi_adr",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["attivazione", "negoziazione", "conciliazione"],
            "suggested_practice_id": "negoziazione_assistita",
            "summary": "Negoziazione assistita.",
            "base_note": "Valori letti dalla tabella 27 con mapping attivazione / negoziazione / conciliazione.",
        },
        {
            "profile_code": "arbitrato",
            "materia_key": "ARBITRATO",
            "materia_label": "Arbitrato",
            "grado_key": "PROCEDURA_ADR",
            "grado_label": "Procedura ADR",
            "table_code": "A26",
            "table_label": "Tabella 26 - Arbitrato",
            "calc_mode": "compenso_unico",
            "exact_snapshot": True,
            "coeff": 1.0,
            "requires_value": True,
            "phase_keys": ["compenso_unico"],
            "suggested_practice_id": "arbitrato",
            "summary": "Arbitrato rituale e irrituale con compenso unico tabellare.",
            "base_note": "Valori letti dalla tabella 26 del D.M. 147/2022.",
        },
    ],
)

_upsert_rows(
    RULE_ROWS,
    "rule_code",
    [
        {
            "rule_code": "penale_indagini",
            "materia_label": "Penale",
            "label": "Indagini preliminari",
            "summary": "Assistenza nella fase delle indagini preliminari.",
            "profile_code": "penale_indagini_preliminari",
            "suggested_practice_id": "indagini_preliminari",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "penale_udienza_preliminare",
            "materia_label": "Penale",
            "label": "Udienza preliminare / GIP-GUP",
            "summary": "Attivita penale davanti al GIP/GUP.",
            "profile_code": "penale_udienza_preliminare",
            "suggested_practice_id": "udienza_preliminare",
            "grado_input_value": "GIP / GUP",
            "allowed_grade_input_values": ["GIP / GUP"],
        },
        {
            "rule_code": "penale_primo_grado",
            "materia_label": "Penale",
            "label": "Dibattimento penale monocratico",
            "summary": "Primo grado penale davanti al Tribunale monocratico.",
            "profile_code": "penale_base",
            "suggested_practice_id": "dibattimento_penale",
            "grado_input_value": "Tribunale monocratico",
            "allowed_grade_input_values": ["Tribunale monocratico"],
        },
        {
            "rule_code": "penale_collegiale",
            "materia_label": "Penale",
            "label": "Dibattimento penale collegiale",
            "summary": "Primo grado penale davanti al Tribunale collegiale.",
            "profile_code": "penale_collegiale",
            "suggested_practice_id": "dibattimento_penale",
            "grado_input_value": "Tribunale collegiale",
            "allowed_grade_input_values": ["Tribunale collegiale"],
        },
        {
            "rule_code": "penale_assise",
            "materia_label": "Penale",
            "label": "Corte d'Assise",
            "summary": "Primo grado penale davanti alla Corte d'Assise.",
            "profile_code": "penale_assise",
            "suggested_practice_id": "dibattimento_penale",
            "grado_input_value": "Corte d'Assise",
            "allowed_grade_input_values": ["Corte d'Assise"],
        },
        {
            "rule_code": "penale_appello",
            "materia_label": "Penale",
            "label": "Appello penale",
            "summary": "Impugnazioni penali davanti alla Corte d'Appello.",
            "profile_code": "penale_appello",
            "suggested_practice_id": "impugnazioni_penali",
            "grado_input_value": "Corte d'Appello penale",
            "allowed_grade_input_values": ["Corte d'Appello penale"],
        },
        {
            "rule_code": "penale_sorveglianza",
            "materia_label": "Penale",
            "label": "Tribunale di Sorveglianza",
            "summary": "Procedimenti di sorveglianza.",
            "profile_code": "penale_sorveglianza",
            "suggested_practice_id": "impugnazioni_penali",
            "grado_input_value": "Tribunale di Sorveglianza",
            "allowed_grade_input_values": ["Tribunale di Sorveglianza"],
        },
        {
            "rule_code": "penale_assise_appello",
            "materia_label": "Penale",
            "label": "Corte d'Assise d'Appello",
            "summary": "Impugnazioni davanti alla Corte d'Assise d'Appello.",
            "profile_code": "penale_assise_appello",
            "suggested_practice_id": "impugnazioni_penali",
            "grado_input_value": "Corte d'Assise d'Appello",
            "allowed_grade_input_values": ["Corte d'Assise d'Appello"],
        },
        {
            "rule_code": "penale_cassazione",
            "materia_label": "Penale",
            "label": "Ricorso per Cassazione penale",
            "summary": "Giudizio di legittimita in materia penale.",
            "profile_code": "penale_cassazione",
            "suggested_practice_id": "cassazione_penale",
            "grado_input_value": "Corte di Cassazione",
            "allowed_grade_input_values": ["Corte di Cassazione"],
        },
        {
            "rule_code": "penale_parte_civile_monocratico",
            "materia_label": "Penale",
            "label": "Parte civile nel dibattimento monocratico",
            "summary": "Costituzione di parte civile nel giudizio penale monocratico.",
            "profile_code": "penale_base",
            "suggested_practice_id": "parte_civile",
            "grado_input_value": "Tribunale monocratico",
            "allowed_grade_input_values": ["Tribunale monocratico"],
        },
        {
            "rule_code": "penale_parte_civile_collegiale",
            "materia_label": "Penale",
            "label": "Parte civile nel dibattimento collegiale",
            "summary": "Costituzione di parte civile nel giudizio penale collegiale.",
            "profile_code": "penale_collegiale",
            "suggested_practice_id": "parte_civile",
            "grado_input_value": "Tribunale collegiale",
            "allowed_grade_input_values": ["Tribunale collegiale"],
        },
        {
            "rule_code": "penale_parte_civile_assise",
            "materia_label": "Penale",
            "label": "Parte civile davanti alla Corte d'Assise",
            "summary": "Costituzione di parte civile davanti alla Corte d'Assise.",
            "profile_code": "penale_assise",
            "suggested_practice_id": "parte_civile",
            "grado_input_value": "Corte d'Assise",
            "allowed_grade_input_values": ["Corte d'Assise"],
        },
    ],
)

_upsert_rows(
    RULE_ROWS,
    "rule_code",
    [
        {
            "rule_code": "civile_consulenza_parere",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Consulenza / parere civile",
            "summary": "Pareri e assistenza fuori giudizio in ambito civile.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "consulenza_civile",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "penale_consulenza_parere",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Consulenza / parere penale",
            "summary": "Pareri e assistenza fuori giudizio in materia penale.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "consulenza_penale",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "penale_denuncia_querela",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Denuncia / querela",
            "summary": "Redazione e assistenza per denuncia o querela in fase stragiudiziale.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "denuncia_querela",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "amministrativo_motivi_aggiunti",
            "materia_label": "Amministrativo / TAR-CdS",
            "label": "Motivi aggiunti",
            "summary": "Deposito di motivi aggiunti davanti al TAR.",
            "profile_code": "amministrativo_primo_grado",
            "suggested_practice_id": "motivi_aggiunti",
            "grado_input_value": "TAR",
            "allowed_grade_input_values": ["TAR"],
        },
        {
            "rule_code": "amministrativo_ottemperanza",
            "materia_label": "Amministrativo / TAR-CdS",
            "label": "Giudizio di ottemperanza",
            "summary": "Giudizio di ottemperanza davanti al TAR.",
            "profile_code": "amministrativo_primo_grado",
            "suggested_practice_id": "ottemperanza",
            "grado_input_value": "TAR",
            "allowed_grade_input_values": ["TAR"],
        },
        {
            "rule_code": "tributario_autotutela",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Autotutela tributaria",
            "summary": "Istanza e gestione stragiudiziale dell'autotutela tributaria.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "autotutela",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "tributario_accertamento_adesione",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Accertamento con adesione",
            "summary": "Assistenza e definizione stragiudiziale in accertamento con adesione.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "accertamento_adesione",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_parere",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Parere legale",
            "summary": "Parere pro veritate, nota o memorandum legale fuori giudizio.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "parere",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_assistenza_trattativa",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Assistenza in trattativa",
            "summary": "Assistenza stragiudiziale in trattative e negoziazioni private.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "assistenza_trattativa",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_redazione_contratto",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Redazione contratto",
            "summary": "Predisposizione e redazione di contratti in sede stragiudiziale.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "redazione_contratto",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_revisione_contratto",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Revisione / due diligence contrattuale",
            "summary": "Revisione e due diligence contrattuale in sede stragiudiziale.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "revisione_contratto",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_transazione",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Transazione / accordo stragiudiziale",
            "summary": "Definizione transattiva e negoziazione dell'accordo.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "transazione",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "stragiud_recupero_crediti",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Recupero crediti stragiudiziale",
            "summary": "Assistenza stragiudiziale per solleciti, diffide e recupero crediti prima del giudizio.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "recupero_crediti_stragiud",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "speciali_domiciliazione",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Domiciliazione",
            "summary": "Attivita di domiciliazione e sostituzione esterna.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "domiciliazione",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
        {
            "rule_code": "speciali_attivita_tempo",
            "materia_label": "Stragiudiziale / Consulenza",
            "label": "Attivita a tempo / compenso orario",
            "summary": "Prestazioni pattuite a tempo con valorizzazione oraria ex art. 13 L. 247/2012.",
            "profile_code": "stragiudiziale",
            "suggested_practice_id": "attivita_tempo",
            "grado_input_value": "Fuori giudizio",
            "allowed_grade_input_values": ["Fuori giudizio"],
        },
    ],
)

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
        "option_code": "accordo_adr_30",
        "label": "Maggiorazione accordo ADR",
        "option_kind": "maggiorazione",
        "value_type": "percent",
        "value": 30.0,
        "default_checked": False,
        "domains": ["tariffario", "preventivi", "parcelle"],
        "description": "Se la procedura ADR si chiude con accordo, le fasi iniziali aumentano del 30% mentre la conciliazione resta ferma.",
        "reference_code": "dm55_art20_adr",
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
        return dict(TARIFFARIO_SNAPSHOT_SUPPLEMENTS)
    tabelle = raw.get("tabelle", {}) if isinstance(raw, dict) else {}
    snapshot = dict(tabelle) if isinstance(tabelle, dict) else {}
    for table_code, table_data in TARIFFARIO_SNAPSHOT_SUPPLEMENTS.items():
        if table_code not in snapshot:
            snapshot[table_code] = dict(table_data)
    return snapshot


def _labels_for_table(raw_table: Mapping[str, Iterable[Optional[float]]]) -> List[tuple[float, float, str]]:
    max_count = max((sum(1 for value in values if value is not None) for values in raw_table.values()), default=0)
    if max_count <= 3:
        return list(_LABELS_3)
    labels = list(_LABELS_7)
    # Verifica regresso al 7° scaglione: se il compenso medio dell'indice 6 è
    # inferiore a quello dell'indice 5, il 7° valore è il "valore indeterminabile"
    # (DM 55/2014 art. 5) e non un genuino scaglione progressivo.
    # Si rimuove il 7° e si apre il 6° a infinito (coerente con _snapshot_table).
    all_vals = [list(v) for v in raw_table.values()]
    valori_sc6 = [float(v[5]) for v in all_vals if len(v) > 5 and v[5] is not None]
    valori_sc7 = [float(v[6]) for v in all_vals if len(v) > 6 and v[6] is not None]
    if valori_sc6 and valori_sc7:
        media6 = sum(valori_sc6) / len(valori_sc6)
        media7 = sum(valori_sc7) / len(valori_sc7)
        if media7 < media6 * 0.95:
            da, _, lbl = labels[5]
            labels[5] = (da, float("inf"), lbl)
            labels = labels[:6]
    return labels


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
        if item["materia_key"] in {"MEDIAZIONE", "NEGOZIAZIONE_ASSISTITA"}:
            refs.extend(
                [
                    _reference_by_code("dm55_art19"),
                    _reference_by_code("dm55_art20_adr"),
                ]
            )
        if item["materia_key"] == "CONTABILE":
            refs.append(_reference_by_code("dlgs174_giustizia_contabile"))
        if item["materia_key"] == "CRISI_IMPRESA":
            refs.append(_reference_by_code("dlgs14_crisi_impresa"))
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


def tariffario_complessita_rows() -> List[Dict[str, str]]:
    return [dict(row) for row in COMPLESSITA_ROWS]


@lru_cache(maxsize=1)
def raw_tariffario_snapshot_codes() -> set[str]:
    try:
        raw = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    tabelle = raw.get("tabelle", {}) if isinstance(raw, dict) else {}
    return {str(code) for code in tabelle.keys()} if isinstance(tabelle, dict) else set()


def _available_phase_keys_for_table(raw_table: Mapping[str, Iterable[Optional[float]]]) -> set[str]:
    phase_keys: set[str] = set()
    for raw_phase, values in (raw_table or {}).items():
        if not any(value is not None for value in values or []):
            continue
        phase_keys.add(PHASE_KEY_BY_RAW.get(str(raw_phase), str(raw_phase).lower()))
    return phase_keys


def _compliance_payload_for_rule(item: Mapping[str, Any], profile: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    snapshot = load_tariffario_snapshot()
    table_code = str((profile or {}).get("table_code") or "")
    table_snapshot = snapshot.get(table_code) or {}
    snapshot_origin = "snapshot" if table_code in raw_tariffario_snapshot_codes() else ("seed" if table_code in snapshot else "")
    available_phase_keys = _available_phase_keys_for_table(table_snapshot)
    profile_phase_keys = [str(key) for key in ((profile or {}).get("phase_keys") or [])]
    phase_aliases = {
        "A16": {"esecutiva": "istruttoria"},
        "A17": {"esecutiva": "istruttoria"},
        "A18": {"esecutiva": "istruttoria"},
        "A27": {
            "attivazione": "introduttiva",
            "rivitalizzazione": "istruttoria",
            "negoziazione": "istruttoria",
            "conciliazione": "decisionale",
        },
    }.get(table_code, {})
    missing_phase_keys: List[str] = []
    mapped_phase_keys: List[str] = []
    for key in profile_phase_keys:
        if key in available_phase_keys:
            continue
        alias_key = phase_aliases.get(key, "")
        if alias_key and alias_key in available_phase_keys:
            mapped_phase_keys.append(key)
            continue
        missing_phase_keys.append(key)
    exact_snapshot = bool((profile or {}).get("exact_snapshot"))
    ref_count = len(list(item.get("normative_references") or []))

    status = "verificata_snapshot"
    label = "Verificata su snapshot"
    badge = "success"
    note = "Regola allineata al catalogo tariffario e alla tabella ufficiale presente nello snapshot DM 147/2022."

    if not profile:
        status = "da_verificare"
        label = "Da verificare"
        badge = "danger"
        note = "Regola tariffaria priva di profilo di calcolo collegato."
    elif not table_code or not table_snapshot:
        status = "da_verificare"
        label = "Da verificare"
        badge = "danger"
        note = "La tabella indicata dal profilo non e presente nello snapshot tariffario disponibile."
    elif missing_phase_keys:
        status = "da_verificare"
        label = "Da verificare"
        badge = "danger"
        note = (
            "La regola usa fasi non coperte integralmente dalla tabella collegata: "
            + ", ".join(missing_phase_keys)
            + "."
        )
    elif ref_count == 0:
        status = "da_verificare"
        label = "Da verificare"
        badge = "danger"
        note = "Regola senza riferimenti normativi ufficiali agganciati."
    elif not exact_snapshot:
        status = "ricostruttiva"
        label = "Ricostruttiva"
        badge = "warning"
        note = "Profilo operativo ricostruito dal motore: utile e coerente, ma non speculare uno-a-uno alla tabella ministeriale."
    elif mapped_phase_keys:
        status = "ricostruttiva"
        label = "Ricostruttiva"
        badge = "warning"
        note = (
            "La regola usa un mapping operativo di fase rispetto alle colonne ufficiali della tabella: "
            + ", ".join(mapped_phase_keys)
            + "."
        )
    elif snapshot_origin == "seed":
        status = "verificata_seed"
        label = "Verificata su integrazione"
        badge = "info"
        note = "Regola coperta da integrazione seed del catalogo tariffario, sincronizzata insieme allo snapshot ufficiale."

    return {
        "compliance_status": status,
        "compliance_label": label,
        "compliance_badge": badge,
        "compliance_note": note,
        "snapshot_origin": snapshot_origin,
        "snapshot_present": bool(table_snapshot),
        "phase_alignment_ok": not missing_phase_keys,
        "missing_phase_keys": missing_phase_keys,
        "mapped_phase_keys": mapped_phase_keys,
        "normative_reference_count": ref_count,
        "source_snapshot": _SNAPSHOT_PATH.name,
        "severity_rank": {
            "da_verificare": 3,
            "ricostruttiva": 2,
            "verificata_seed": 1,
            "verificata_snapshot": 0,
        }.get(status, 9),
    }


def _profile_by_code(profile_code: str) -> Optional[Dict[str, Any]]:
    for row in tariffario_profile_rows():
        if row.get("profile_code") == profile_code:
            return dict(row)
    return None


def tariffario_rule_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in RULE_ROWS:
        item = dict(row)
        profile = _profile_by_code(item.get("profile_code", ""))
        item["profile"] = profile
        item["grado_input_value"] = item.get("grado_input_value") or (profile or {}).get("grado_input_value", "")
        item["allowed_grade_input_values"] = list(item.get("allowed_grade_input_values") or ([item["grado_input_value"]] if item.get("grado_input_value") else []))
        refs = list(TARIFFARIO_REFERENCE_ROWS[:4])
        if item.get("materia_label") in {"Amministrativo / TAR-CdS", "Tributario / CGT", "Mediazione (D.Lgs. 28/2010)", "Negoziazione Assistita (D.L. 132/2014)"}:
            refs.append(_reference_by_code("l49_equo_compenso"))
        if item.get("materia_label") in {"Mediazione (D.Lgs. 28/2010)", "Negoziazione Assistita (D.L. 132/2014)"}:
            refs.extend(
                [
                    _reference_by_code("dm55_art19"),
                    _reference_by_code("dm55_art20_adr"),
                ]
            )
        if item.get("materia_label") == "Contabile / Corte dei Conti":
            refs.append(_reference_by_code("dlgs174_giustizia_contabile"))
        if item.get("materia_label") == "Crisi d'impresa / concorsuale":
            refs.append(_reference_by_code("dlgs14_crisi_impresa"))
        item["normative_references"] = [ref for ref in refs if ref]
        item.update(_compliance_payload_for_rule(item, profile))
        rows.append(item)
    return rows


def tariffario_audit_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in tariffario_rule_rows():
        rows.append(
            {
                "rule_code": row.get("rule_code", ""),
                "rule_label": row.get("label", ""),
                "suggested_practice_id": row.get("suggested_practice_id", ""),
                "materia_label": row.get("materia_label", ""),
                "grado_input_value": row.get("grado_input_value", ""),
                "table_code": (row.get("profile") or {}).get("table_code", ""),
                "table_label": (row.get("profile") or {}).get("table_label", ""),
                "profile_code": row.get("profile_code", ""),
                "exact_snapshot": bool((row.get("profile") or {}).get("exact_snapshot")),
                "snapshot_origin": row.get("snapshot_origin", ""),
                "snapshot_present": bool(row.get("snapshot_present")),
                "phase_alignment_ok": bool(row.get("phase_alignment_ok")),
                "missing_phase_keys": list(row.get("missing_phase_keys") or []),
                "mapped_phase_keys": list(row.get("mapped_phase_keys") or []),
                "normative_reference_count": int(row.get("normative_reference_count") or 0),
                "compliance_status": row.get("compliance_status", ""),
                "compliance_label": row.get("compliance_label", ""),
                "compliance_badge": row.get("compliance_badge", "secondary"),
                "compliance_note": row.get("compliance_note", ""),
                "severity_rank": int(row.get("severity_rank") or 0),
                "source_snapshot": row.get("source_snapshot", _SNAPSHOT_PATH.name),
            }
        )
    rows.sort(
        key=lambda item: (
            int(item.get("severity_rank", 0)),
            item.get("materia_label", ""),
            item.get("rule_label", ""),
        )
    )
    return rows


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


def rule_catalog_by_materia() -> Dict[str, List[Dict[str, Any]]]:
    catalog: Dict[str, List[Dict[str, Any]]] = {}
    for row in tariffario_rule_rows():
        catalog.setdefault(row["materia_label"], []).append(row)
    return catalog


def rule_lookup(rule_code: str) -> Optional[Dict[str, Any]]:
    for row in tariffario_rule_rows():
        if row.get("rule_code") == rule_code:
            return dict(row)
    return None


def rules_for_practice(practice_id: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in tariffario_rule_rows() if row.get("suggested_practice_id") == practice_id]


def default_rule_for_practice(practice_id: str) -> Optional[Dict[str, Any]]:
    rows = rules_for_practice(practice_id)
    if not rows:
        return None
    practice_map = {
        "atto_citazione": "Tribunale",
        "decreto_ingiuntivo": "Tribunale",
        "comparsa_risposta": "Tribunale",
        "precetto": "Tribunale",
        "esecuzione_mobiliare": "Tribunale",
        "esecuzione_terzi": "Tribunale",
        "esecuzione_immobiliare": "Tribunale",
        "opposizione_esecutiva": "Tribunale",
        "opposizione_atti_esecutivi": "Tribunale",
        "istruzione_preventiva": "Giudice competente",
        "cautelare_civile": "Giudice competente",
        "sfratto_morosita": "Tribunale",
        "risarcimento_danni": "Tribunale",
        "controversia_lavoro": "Tribunale",
        "licenziamento": "Tribunale",
        "previdenza": "Tribunale",
        "separazione_consensuale": "Tribunale",
        "separazione_giudiziale": "Tribunale",
        "divorzio_congiunto": "Tribunale",
        "divorzio_giudiziale": "Tribunale",
        "procedimenti_famiglia": "Tribunale",
        "procedimenti_minori": "Tribunale",
        "modifica_condizioni_famiglia": "Tribunale",
        "responsabilita_genitoriale": "Tribunale",
        "reclamo_famiglia_minori": "Corte d'Appello",
        "appello_famiglia_minori": "Corte d'Appello",
        "amministrazione_sostegno": "Giudice tutelare",
        "nomina_amministratore_sostegno": "Giudice tutelare",
        "modifica_revoca_ads": "Giudice tutelare",
        "tutela_curatela": "Giudice tutelare",
        "reclamo_giudice_tutelare": "Tribunale",
        "appello_civile": "Corte d'Appello",
        "appello_lavoro": "Corte d'Appello",
        "cassazione_lavoro": "Corte di Cassazione",
        "appello_previdenza": "Corte d'Appello",
        "cassazione_previdenza": "Corte di Cassazione",
        "cassazione_civile": "Corte di Cassazione",
        "cassazione_tributaria": "Corte di Cassazione",
        "giudizio_corte_conti": "Corte dei Conti",
        "giurisdizioni_superiori": "Corte costituzionale",
        "iscrizione_ipotecaria_tavolare": "Conservatoria / tavolare",
        "apertura_liquidazione_giudiziale": "Tribunale concorsuale",
        "accertamento_passivo": "Tribunale concorsuale",
        "giudice_pace_penale": "Giudice di Pace",
        "indagini_preliminari": "Fuori giudizio",
        "indagini_difensive": "Fuori giudizio",
        "convalida_arresto": "GIP / GUP",
        "misure_cautelari_penali": "GIP / GUP",
        "udienza_preliminare": "GIP / GUP",
        "dibattimento_penale": "Tribunale monocratico",
        "impugnazioni_penali": "Corte d'Appello penale",
        "sorveglianza_penale": "Tribunale di Sorveglianza",
        "parte_civile": "Tribunale monocratico",
        "cassazione_penale": "Corte di Cassazione",
        "ricorso_tar": "TAR",
        "appello_cds": "Consiglio di Stato",
        "ricorso_tributario": "CGT di primo grado",
        "appello_tributario": "CGT di secondo grado",
        "mediazione": "Procedura ADR",
        "negoziazione_assistita": "Procedura ADR",
        "arbitrato": "Procedura ADR",
    }
    preferred_grade = practice_map.get(practice_id)
    if preferred_grade:
        for row in rows:
            if row.get("grado_input_value") == preferred_grade:
                return dict(row)
    return dict(rows[0])


def grade_catalog_for_rule(rule_code: str) -> List[str]:
    row = rule_lookup(rule_code)
    if not row:
        return []
    return list(row.get("allowed_grade_input_values") or [])


def profile_lookup_by_rule(rule_code: str, grado_label: str = "") -> Optional[Dict[str, Any]]:
    row = rule_lookup(rule_code)
    if not row:
        return None
    profile_code = row.get("profile_code", "")
    for profile in tariffario_profile_rows():
        if profile.get("profile_code") != profile_code:
            continue
        if not grado_label or profile.get("grado_input_value") == grado_label:
            return dict(profile)
    return _profile_by_code(profile_code)


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


def first_rule_for_materia(materia_label: str) -> Optional[Dict[str, Any]]:
    for row in tariffario_rule_rows():
        if row["materia_label"] == materia_label:
            return dict(row)
    return None

