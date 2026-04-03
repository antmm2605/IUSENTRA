"""
Tassonomia strutturata del wizard preventivi.

Questo modulo separa:
- area operativa del motore tariffario (es. "Civile", "Penale")
- classificazione tassonomica professionale per intake e reporting

La classificazione tassonomica resta indipendente dal calcolo economico:
serve a guidare la selezione della pratica, a filtrare il catalogo e a
conservare un tracciato di fonti ufficiali per futuri aggiornamenti.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence


COMMON_SOURCE_IDS = (
    "forense_art13",
    "forense_dm55",
    "forense_dm147",
    "fiscale_art15",
)


SOURCE_CATALOG: Dict[str, Dict[str, str]] = {
    "forense_art13": {
        "id": "forense_art13",
        "title": "L. 31 dicembre 2012, n. 247",
        "article": "art. 13",
        "authority": "Gazzetta Ufficiale",
        "url": "https://www.gazzettaufficiale.it/eli/id/2013/01/18/13G00018/sg",
        "checked_on": "2026-04-03",
        "scope": "compenso e informativa preventiva",
        "note": "Fonte generale sul conferimento dell'incarico e sull'obbligo di informativa.",
    },
    "forense_dm55": {
        "id": "forense_dm55",
        "title": "D.M. 10 marzo 2014, n. 55",
        "article": "parametri forensi",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=14G00067&atto.dataPubblicazioneGazzetta=2014-04-02&bloccoAggiornamentoBreadCrumb=true&classica=true&dataVigenza=11%2F03%2F2026",
        "checked_on": "2026-04-03",
        "scope": "parametri forensi",
        "note": "Base tabellare generale del motore preventivi.",
    },
    "forense_dm147": {
        "id": "forense_dm147",
        "title": "D.M. 13 agosto 2022, n. 147",
        "article": "aggiornamento tabelle",
        "authority": "Gazzetta Ufficiale",
        "url": "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.codiceRedazionale=22G00157&atto.dataPubblicazioneGazzetta=2022-10-08&atto.tipoProvvedimento=DECRETO",
        "checked_on": "2026-04-03",
        "scope": "aggiornamento parametri forensi",
        "note": "Aggiornamento ufficiale delle tabelle DM 55/2014.",
    },
    "fiscale_art15": {
        "id": "fiscale_art15",
        "title": "D.P.R. 26 ottobre 1972, n. 633",
        "article": "art. 15",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1972-10-26%3B633",
        "checked_on": "2026-04-03",
        "scope": "anticipazioni e spese vive",
        "note": "Riferimento generale per anticipazioni escluse da IVA.",
    },
    "cpc": {
        "id": "cpc",
        "title": "Codice di procedura civile",
        "article": "r.d. 28 ottobre 1940, n. 1443",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Aregio.decreto%3A1940-10-28%3B1443",
        "checked_on": "2026-04-03",
        "scope": "rito civile e volontaria giurisdizione",
        "note": "Fonte normativa base per cognizione, esecuzioni, famiglia e volontaria giurisdizione.",
    },
    "cpp": {
        "id": "cpp",
        "title": "Codice di procedura penale",
        "article": "d.P.R. 22 settembre 1988, n. 447",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.del.presidente.della.repubblica%3A1988-09-22%3B447",
        "checked_on": "2026-04-03",
        "scope": "rito penale",
        "note": "Fonte base per indagini, udienza preliminare, dibattimento, misure e impugnazioni penali.",
    },
    "ads_ministero": {
        "id": "ads_ministero",
        "title": "Ministero della Giustizia | Amministrazione di sostegno",
        "article": "scheda informativa ministeriale",
        "authority": "Ministero della Giustizia",
        "url": "https://www.giustizia.it/giustizia/it/mg_3_2_1.page",
        "checked_on": "2026-04-03",
        "scope": "amministrazione di sostegno",
        "note": "Fonte istituzionale aggiornata sul procedimento davanti al giudice tutelare.",
    },
    "cpa": {
        "id": "cpa",
        "title": "D.Lgs. 2 luglio 2010, n. 104",
        "article": "Codice del processo amministrativo",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2010-07-02%3B104",
        "checked_on": "2026-04-03",
        "scope": "giustizia amministrativa",
        "note": "Fonte base per ricorsi TAR, cautelari, motivi aggiunti, appello e ottemperanza.",
    },
    "ga_funzioni": {
        "id": "ga_funzioni",
        "title": "Giustizia Amministrativa | Funzioni della Giustizia Amministrativa",
        "article": "Consiglio di Stato e TAR",
        "authority": "Giustizia Amministrativa",
        "url": "https://www.giustizia-amministrativa.it/en/funzioni-della-giustizia-amministrativa",
        "checked_on": "2026-04-03",
        "scope": "organi e gradi",
        "note": "Fonte istituzionale che conferma il primo grado TAR e l'appello al Consiglio di Stato.",
    },
    "tributario_546": {
        "id": "tributario_546",
        "title": "D.Lgs. 31 dicembre 1992, n. 546",
        "article": "processo tributario",
        "authority": "Normattiva / Giustizia Tributaria",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A1992-12-31%3B546",
        "checked_on": "2026-04-03",
        "scope": "rito tributario",
        "note": "Fonte normativa base del processo tributario.",
    },
    "tributario_130_2022": {
        "id": "tributario_130_2022",
        "title": "L. 31 agosto 2022, n. 130",
        "article": "riforma della giustizia tributaria",
        "authority": "Giustizia Tributaria",
        "url": "https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?codiceOrdinamento=0000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&id=%7BE8A2C712-95F0-48E2-9FE0-01C0C7F52D66%7D&idAttoNormativo=%7BE95D5A17-CF76-45C2-818A-347C53261BD6%7D",
        "checked_on": "2026-04-03",
        "scope": "corti di giustizia tributaria di primo e secondo grado",
        "note": "Fonte istituzionale aggiornata sulla ridenominazione e sul sistema di primo e secondo grado.",
    },
    "mediazione_28_2010": {
        "id": "mediazione_28_2010",
        "title": "D.Lgs. 4 marzo 2010, n. 28",
        "article": "mediazione civile e commerciale",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2010-03-04%3B28",
        "checked_on": "2026-04-03",
        "scope": "ADR",
        "note": "Fonte base per mediazione obbligatoria e facoltativa.",
    },
    "mediazione_dm150_2023": {
        "id": "mediazione_dm150_2023",
        "title": "D.M. 24 ottobre 2023, n. 150",
        "article": "spese e indennita di mediazione",
        "authority": "Gazzetta Ufficiale",
        "url": "https://www.gazzettaufficiale.it/atto/serie_generale/caricaDettaglioAtto/originario?atto.codiceRedazionale=23G00162&atto.dataPubblicazioneGazzetta=2023-10-31&atto.tipoProvvedimento=DECRETO",
        "checked_on": "2026-04-03",
        "scope": "costi e indennita mediazione",
        "note": "Fonte aggiornata post Cartabia per organismi e indennita di mediazione.",
    },
    "negoziazione_132_2014": {
        "id": "negoziazione_132_2014",
        "title": "D.L. 12 settembre 2014, n. 132",
        "article": "negoziazione assistita",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legge%3A2014-09-12%3B132",
        "checked_on": "2026-04-03",
        "scope": "ADR",
        "note": "Fonte base della convenzione di negoziazione assistita.",
    },
    "crisi_14_2019": {
        "id": "crisi_14_2019",
        "title": "D.Lgs. 12 gennaio 2019, n. 14",
        "article": "Codice della crisi d'impresa e dell'insolvenza",
        "authority": "Normattiva",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn%3Anir%3Astato%3Adecreto.legislativo%3A2019%3B14=",
        "checked_on": "2026-04-03",
        "scope": "crisi d'impresa",
        "note": "Fonte base per liquidazione giudiziale e accertamento del passivo.",
    },
}


NODE_CATALOG: Dict[str, Dict[str, Any]] = {
    "STR_CIV_PARERI_DIFFIDE": {
        "area_code": "STR",
        "area_label": "Stragiudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "PARERI_DIFFIDE",
        "sub_label": "Pareri civili, diffide e primo inquadramento",
        "description": "Ingressi consulenziali civili a bassa strutturazione processuale.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "GIU_CIV_COGNIZIONE": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "COGNIZIONE_CREDITI",
        "sub_label": "Crediti, monitori e cognizione ordinaria",
        "description": "Cognizione civile ordinaria, monitoria e impugnazioni di base.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "ESE_CIV_ESECUZIONI": {
        "area_code": "ESE",
        "area_label": "Esecuzione Forzata",
        "macro_code": "ESE_CIV",
        "macro_label": "Esecuzioni Civili",
        "sub_code": "ESECUZIONE_CIVILE",
        "sub_label": "Precetti, pignoramenti e opposizioni esecutive",
        "description": "Esecuzioni civili e opposizioni agli atti e all'esecuzione.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "GIU_FAM_FAMIGLIA_MINORI": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "FAM",
        "macro_label": "Diritto di Famiglia",
        "sub_code": "FAMIGLIA_MINORI",
        "sub_label": "Separazione, divorzio, minori e reclami",
        "description": "Procedimenti in materia di persone, minori e famiglie.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "VOL_VG_PROTEZIONE": {
        "area_code": "VOL",
        "area_label": "Volontaria Giurisdizione",
        "macro_code": "VG",
        "macro_label": "Protezione della persona",
        "sub_code": "ADS_TUTELA_CURATELA",
        "sub_label": "Amministrazione di sostegno, tutela e curatela",
        "description": "Procedimenti davanti al giudice tutelare e reclami collegati.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc", "ads_ministero"),
    },
    "GIU_CIV_LOCAZIONI": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "LOCAZIONI_SFRATTI",
        "sub_label": "Locazioni e sfratti",
        "description": "Convalide di sfratto e contenzioso locatizio.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc", "mediazione_28_2010"),
    },
    "GIU_CIV_RESPONSABILITA": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "RESPONSABILITA_DANNI",
        "sub_label": "Responsabilita civile e risarcimento",
        "description": "Danni contrattuali ed extracontrattuali in sede giudiziale.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "GIU_LAV_LAVORO": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "LAV",
        "macro_label": "Diritto del Lavoro",
        "sub_code": "LAVORO_SUBORDINATO",
        "sub_label": "Lavoro subordinato, licenziamenti e differenze retributive",
        "description": "Rito lavoro di primo grado e impugnazioni.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "GIU_PRE_PREVIDENZA": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "PRE",
        "macro_label": "Previdenza e assistenza",
        "sub_code": "PREVIDENZA_ASSISTENZA",
        "sub_label": "INPS, INAIL, assistenza e ricorsi amministrativi",
        "description": "Contenzioso previdenziale e fasi amministrative collegate.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "GIU_PEN_ORDINARIO": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "PEN",
        "macro_label": "Diritto Penale",
        "sub_code": "PENALE_ORDINARIO",
        "sub_label": "Indagini, udienza preliminare, dibattimento e impugnazioni",
        "description": "Procedimento penale ordinario e costituzione di parte civile.",
        "source_ids": COMMON_SOURCE_IDS + ("cpp",),
    },
    "GIU_PEN_SPECIALI": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "PEN",
        "macro_label": "Diritto Penale",
        "sub_code": "GDP_MISURE_SORVEGLIANZA",
        "sub_label": "Giudice di pace penale, misure cautelari e sorveglianza",
        "description": "Rami penali speciali con gradi e giudici dedicati.",
        "source_ids": COMMON_SOURCE_IDS + ("cpp",),
    },
    "GIU_AMM_AMMINISTRATIVO": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "AMM",
        "macro_label": "Giustizia Amministrativa",
        "sub_code": "TAR_CDS",
        "sub_label": "TAR, Consiglio di Stato e ottemperanza",
        "description": "Giudizio amministrativo di primo grado, cautelare, appello e ottemperanza.",
        "source_ids": COMMON_SOURCE_IDS + ("cpa", "ga_funzioni"),
    },
    "GIU_TRB_TRIBUTARIO": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "TRB",
        "macro_label": "Giustizia Tributaria",
        "sub_code": "CGT_PRIMO_SECONDO_GRADO",
        "sub_label": "Corti di giustizia tributaria e definizioni",
        "description": "Ricorsi tributari, appelli, cassazione e strumenti deflattivi collegati.",
        "source_ids": COMMON_SOURCE_IDS + ("tributario_546", "tributario_130_2022"),
    },
    "STR_CONS_CONTRATTI": {
        "area_code": "STR",
        "area_label": "Stragiudiziale",
        "macro_code": "CONS",
        "macro_label": "Consulenza e contrattualistica",
        "sub_code": "CONSULENZA_CONTRATTI",
        "sub_label": "Pareri, trattative, contratti e transazioni",
        "description": "Assistenza consulenziale e contrattuale fuori giudizio.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "STR_CIV_RECUPERO": {
        "area_code": "STR",
        "area_label": "Stragiudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "RECUPERO_STRAGIUD_SINISTRI",
        "sub_label": "Recupero crediti stragiudiziale e sinistri",
        "description": "Attivita preparatorie e recupero bonario fuori giudizio.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "ADR_MED_MEDIAZIONE": {
        "area_code": "ADR",
        "area_label": "ADR / Composizione Assistita",
        "macro_code": "MED",
        "macro_label": "Mediazione",
        "sub_code": "MEDIAZIONE_CIVILE",
        "sub_label": "Mediazione civile e commerciale",
        "description": "Mediazione obbligatoria, delegata o facoltativa.",
        "source_ids": COMMON_SOURCE_IDS + ("mediazione_28_2010", "mediazione_dm150_2023"),
    },
    "ADR_NEG_NEGOZIAZIONE": {
        "area_code": "ADR",
        "area_label": "ADR / Composizione Assistita",
        "macro_code": "NEG",
        "macro_label": "Negoziazione Assistita",
        "sub_code": "NEGOZIAZIONE_ASSISTITA",
        "sub_label": "Convenzioni e accordi assistiti",
        "description": "Negoziazione assistita stragiudiziale.",
        "source_ids": COMMON_SOURCE_IDS + ("negoziazione_132_2014",),
    },
    "ARB_ARB_ARBITRATO": {
        "area_code": "ARB",
        "area_label": "Arbitrato",
        "macro_code": "ARB",
        "macro_label": "Arbitrato",
        "sub_code": "ARBITRATO_RITUALE_IRRITUALE",
        "sub_label": "Arbitrato rituale e irrituale",
        "description": "Gestione del procedimento arbitrale e del lodo.",
        "source_ids": COMMON_SOURCE_IDS,
    },
    "SPE_VAR_SERVIZI": {
        "area_code": "SPE",
        "area_label": "Giurisdizioni e servizi speciali",
        "macro_code": "VAR",
        "macro_label": "Servizi professionali particolari",
        "sub_code": "DOMICILIAZIONE_E_TEMPO",
        "sub_label": "Domiciliazioni, attivita a tempo e procedure varie",
        "description": "Prestazioni professionali non rigidamente tipizzate dal rito.",
        "source_ids": COMMON_SOURCE_IDS,
    },
    "GIU_CIV_ISTRUZIONE_CAUTELARE": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "CIV",
        "macro_label": "Diritto Civile",
        "sub_code": "ISTR_PREV_CAUTELARE",
        "sub_label": "Istruzione preventiva e cautelari civili",
        "description": "ATP, istruzione preventiva e misure cautelari civili.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "SPE_CONT_CORTE_CONTI": {
        "area_code": "SPE",
        "area_label": "Giurisdizioni e servizi speciali",
        "macro_code": "CONT",
        "macro_label": "Giustizia Contabile",
        "sub_code": "CORTE_DEI_CONTI",
        "sub_label": "Giudizi innanzi alla Corte dei Conti",
        "description": "Giurisdizione contabile e responsabilita amministrativo-contabile.",
        "source_ids": COMMON_SOURCE_IDS,
    },
    "SPE_SUP_GIURISDIZIONI": {
        "area_code": "SPE",
        "area_label": "Giurisdizioni e servizi speciali",
        "macro_code": "SUP",
        "macro_label": "Giurisdizioni superiori / europee",
        "sub_code": "CORTE_COST_CEDU_CGUE",
        "sub_label": "Corte costituzionale, CEDU e CGUE",
        "description": "Giurisdizioni superiori e sovranazionali.",
        "source_ids": COMMON_SOURCE_IDS,
    },
    "GIU_IMM_TAVOLARE": {
        "area_code": "GIU",
        "area_label": "Giudiziale",
        "macro_code": "IMM",
        "macro_label": "Diritto Immobiliare e Tavolare",
        "sub_code": "PUBBLICITA_TAVOLARE",
        "sub_label": "Iscrizioni ipotecarie e pubblicita tavolare",
        "description": "Affari tavolari e pubblicita immobiliare giudiziale.",
        "source_ids": COMMON_SOURCE_IDS + ("cpc",),
    },
    "SPE_CRI_CONCORSUALE": {
        "area_code": "SPE",
        "area_label": "Giurisdizioni e servizi speciali",
        "macro_code": "CRI",
        "macro_label": "Crisi d'impresa e concorsuale",
        "sub_code": "LIQUIDAZIONE_E_PASSIVO",
        "sub_label": "Liquidazione giudiziale e accertamento del passivo",
        "description": "Procedure concorsuali e stato passivo.",
        "source_ids": COMMON_SOURCE_IDS + ("crisi_14_2019",),
    },
}


PRACTICE_NODE_MAP: Dict[str, str] = {
    "consulenza_civile": "STR_CIV_PARERI_DIFFIDE",
    "diffida": "STR_CIV_PARERI_DIFFIDE",
    "recupero_crediti": "GIU_CIV_COGNIZIONE",
    "decreto_ingiuntivo": "GIU_CIV_COGNIZIONE",
    "opposizione_di": "GIU_CIV_COGNIZIONE",
    "atto_citazione": "GIU_CIV_COGNIZIONE",
    "comparsa_risposta": "GIU_CIV_COGNIZIONE",
    "appello_civile": "GIU_CIV_COGNIZIONE",
    "cassazione_civile": "GIU_CIV_COGNIZIONE",
    "precetto": "ESE_CIV_ESECUZIONI",
    "pignoramento": "ESE_CIV_ESECUZIONI",
    "esecuzione_mobiliare": "ESE_CIV_ESECUZIONI",
    "esecuzione_immobiliare": "ESE_CIV_ESECUZIONI",
    "esecuzione_terzi": "ESE_CIV_ESECUZIONI",
    "opposizione_esecutiva": "ESE_CIV_ESECUZIONI",
    "opposizione_atti_esecutivi": "ESE_CIV_ESECUZIONI",
    "separazione_consensuale": "GIU_FAM_FAMIGLIA_MINORI",
    "separazione_giudiziale": "GIU_FAM_FAMIGLIA_MINORI",
    "divorzio_congiunto": "GIU_FAM_FAMIGLIA_MINORI",
    "divorzio_giudiziale": "GIU_FAM_FAMIGLIA_MINORI",
    "procedimenti_famiglia": "GIU_FAM_FAMIGLIA_MINORI",
    "procedimenti_minori": "GIU_FAM_FAMIGLIA_MINORI",
    "modifica_condizioni_famiglia": "GIU_FAM_FAMIGLIA_MINORI",
    "responsabilita_genitoriale": "GIU_FAM_FAMIGLIA_MINORI",
    "reclamo_famiglia_minori": "GIU_FAM_FAMIGLIA_MINORI",
    "appello_famiglia_minori": "GIU_FAM_FAMIGLIA_MINORI",
    "amministrazione_sostegno": "VOL_VG_PROTEZIONE",
    "nomina_amministratore_sostegno": "VOL_VG_PROTEZIONE",
    "modifica_revoca_ads": "VOL_VG_PROTEZIONE",
    "tutela_curatela": "VOL_VG_PROTEZIONE",
    "reclamo_giudice_tutelare": "VOL_VG_PROTEZIONE",
    "sfratto_morosita": "GIU_CIV_LOCAZIONI",
    "risarcimento_danni": "GIU_CIV_RESPONSABILITA",
    "controversia_lavoro": "GIU_LAV_LAVORO",
    "licenziamento": "GIU_LAV_LAVORO",
    "differenze_retributive": "GIU_LAV_LAVORO",
    "appello_lavoro": "GIU_LAV_LAVORO",
    "cassazione_lavoro": "GIU_LAV_LAVORO",
    "previdenza": "GIU_PRE_PREVIDENZA",
    "appello_previdenza": "GIU_PRE_PREVIDENZA",
    "cassazione_previdenza": "GIU_PRE_PREVIDENZA",
    "assistenza_previdenziale": "GIU_PRE_PREVIDENZA",
    "consulenza_penale": "GIU_PEN_ORDINARIO",
    "denuncia_querela": "GIU_PEN_ORDINARIO",
    "indagini_preliminari": "GIU_PEN_ORDINARIO",
    "udienza_preliminare": "GIU_PEN_ORDINARIO",
    "dibattimento_penale": "GIU_PEN_ORDINARIO",
    "impugnazioni_penali": "GIU_PEN_ORDINARIO",
    "cassazione_penale": "GIU_PEN_ORDINARIO",
    "parte_civile": "GIU_PEN_ORDINARIO",
    "giudice_pace_penale": "GIU_PEN_SPECIALI",
    "indagini_difensive": "GIU_PEN_SPECIALI",
    "convalida_arresto": "GIU_PEN_SPECIALI",
    "misure_cautelari_penali": "GIU_PEN_SPECIALI",
    "sorveglianza_penale": "GIU_PEN_SPECIALI",
    "ricorso_tar": "GIU_AMM_AMMINISTRATIVO",
    "cautelare_sospensiva": "GIU_AMM_AMMINISTRATIVO",
    "motivi_aggiunti": "GIU_AMM_AMMINISTRATIVO",
    "appello_cds": "GIU_AMM_AMMINISTRATIVO",
    "ottemperanza": "GIU_AMM_AMMINISTRATIVO",
    "ricorso_tributario": "GIU_TRB_TRIBUTARIO",
    "appello_tributario": "GIU_TRB_TRIBUTARIO",
    "cassazione_tributaria": "GIU_TRB_TRIBUTARIO",
    "autotutela": "GIU_TRB_TRIBUTARIO",
    "accertamento_adesione": "GIU_TRB_TRIBUTARIO",
    "parere": "STR_CONS_CONTRATTI",
    "consulenza": "STR_CONS_CONTRATTI",
    "assistenza_trattativa": "STR_CONS_CONTRATTI",
    "redazione_contratto": "STR_CONS_CONTRATTI",
    "revisione_contratto": "STR_CONS_CONTRATTI",
    "transazione": "STR_CONS_CONTRATTI",
    "sinistro_stradale_stragiudiziale": "STR_CIV_RECUPERO",
    "recupero_crediti_stragiud": "STR_CIV_RECUPERO",
    "mediazione": "ADR_MED_MEDIAZIONE",
    "negoziazione_assistita": "ADR_NEG_NEGOZIAZIONE",
    "arbitrato": "ARB_ARB_ARBITRATO",
    "domiciliazione": "SPE_VAR_SERVIZI",
    "attivita_tempo": "SPE_VAR_SERVIZI",
    "procedure_particolari": "SPE_VAR_SERVIZI",
    "istruzione_preventiva": "GIU_CIV_ISTRUZIONE_CAUTELARE",
    "cautelare_civile": "GIU_CIV_ISTRUZIONE_CAUTELARE",
    "giudizio_corte_conti": "SPE_CONT_CORTE_CONTI",
    "giurisdizioni_superiori": "SPE_SUP_GIURISDIZIONI",
    "iscrizione_ipotecaria_tavolare": "GIU_IMM_TAVOLARE",
    "apertura_liquidazione_giudiziale": "SPE_CRI_CONCORSUALE",
    "accertamento_passivo": "SPE_CRI_CONCORSUALE",
}


def _as_practice_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    return {
        "id": getattr(item, "id", ""),
        "label": getattr(item, "label", ""),
        "normative_references": list(getattr(item, "normative_references", []) or []),
    }


def _source_from_ref(ref: Dict[str, Any]) -> Dict[str, str]:
    description = str(ref.get("description") or ref.get("note") or "").strip()
    return {
        "id": str(ref.get("id") or "").strip(),
        "title": str(ref.get("title") or "").strip(),
        "article": str(ref.get("article") or "").strip(),
        "authority": str(ref.get("authority") or "").strip(),
        "url": str(ref.get("url") or "").strip(),
        "checked_on": str(ref.get("checked_on") or "").strip(),
        "scope": str(ref.get("scope") or "").strip(),
        "note": description,
        "description": description,
    }


def _normalize_sources(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for raw in rows or []:
        row = _source_from_ref(raw)
        key = (
            row.get("url", ""),
            row.get("title", ""),
            row.get("article", ""),
        )
        if not any(key) or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def node_for_practice(practice_id: str) -> Dict[str, Any]:
    node_code = PRACTICE_NODE_MAP.get(practice_id)
    if not node_code:
        raise KeyError(practice_id)
    node = dict(NODE_CATALOG[node_code])
    node["node_code"] = node_code
    return node


def taxonomy_for_practice(practice_id: str, practice_refs: Sequence[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    node = node_for_practice(practice_id)
    node_sources = [_source_from_ref(SOURCE_CATALOG[source_id]) for source_id in node.get("source_ids", ()) if source_id in SOURCE_CATALOG]
    merged_sources = _normalize_sources([*node_sources, *(practice_refs or [])])
    return {
        "node_code": node["node_code"],
        "area_code": node["area_code"],
        "area_label": node["area_label"],
        "macro_code": node["macro_code"],
        "macro_label": node["macro_label"],
        "sub_code": node["sub_code"],
        "sub_label": node["sub_label"],
        "description": node["description"],
        "sources": merged_sources,
    }


def validate_taxonomy_coverage(practice_ids: Iterable[str]) -> List[str]:
    missing = sorted({str(practice_id) for practice_id in practice_ids if practice_id not in PRACTICE_NODE_MAP})
    return missing


def catalogo_tassonomia_preventivi(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for raw_item in rows or []:
        item = _as_practice_dict(raw_item)
        practice_id = str(item.get("id") or "").strip()
        if not practice_id or practice_id not in PRACTICE_NODE_MAP:
            continue
        node = taxonomy_for_practice(practice_id, item.get("normative_references") or [])
        area_key = node["area_code"]
        macro_key = f"{node['area_code']}::{node['macro_code']}"
        sub_key = f"{macro_key}::{node['sub_code']}"
        area_row = grouped.setdefault(
            area_key,
            {
                "area_code": node["area_code"],
                "area_label": node["area_label"],
                "macros": {},
            },
        )
        macro_row = area_row["macros"].setdefault(
            macro_key,
            {
                "macro_code": node["macro_code"],
                "macro_label": node["macro_label"],
                "subs": {},
            },
        )
        sub_row = macro_row["subs"].setdefault(
            sub_key,
            {
                "sub_code": node["sub_code"],
                "sub_label": node["sub_label"],
                "description": node["description"],
                "practice_ids": [],
                "practice_labels": [],
                "sources": [],
            },
        )
        if practice_id not in sub_row["practice_ids"]:
            sub_row["practice_ids"].append(practice_id)
        practice_label = str(item.get("label") or practice_id).strip()
        if practice_label and practice_label not in sub_row["practice_labels"]:
            sub_row["practice_labels"].append(practice_label)
        sub_row["sources"] = _normalize_sources([*sub_row["sources"], *node["sources"]])

    result: List[Dict[str, Any]] = []
    for area_row in grouped.values():
        macros: List[Dict[str, Any]] = []
        for macro_row in area_row["macros"].values():
            subs: List[Dict[str, Any]] = []
            for sub_row in macro_row["subs"].values():
                subs.append(
                    {
                        "sub_code": sub_row["sub_code"],
                        "sub_label": sub_row["sub_label"],
                        "description": sub_row["description"],
                        "count": len(sub_row["practice_ids"]),
                        "practice_ids": sorted(sub_row["practice_ids"]),
                        "practice_labels": sorted(sub_row["practice_labels"]),
                        "sources": sub_row["sources"],
                    }
                )
            subs.sort(key=lambda row: row["sub_label"])
            macros.append(
                {
                    "macro_code": macro_row["macro_code"],
                    "macro_label": macro_row["macro_label"],
                    "count": sum(row["count"] for row in subs),
                    "subs": subs,
                }
            )
        macros.sort(key=lambda row: row["macro_label"])
        result.append(
            {
                "area_code": area_row["area_code"],
                "area_label": area_row["area_label"],
                "count": sum(row["count"] for row in macros),
                "macros": macros,
            }
        )
    result.sort(key=lambda row: row["area_label"])
    return result


def catalogo_fonti_tassonomia(rows: Iterable[Any]) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    for raw_item in rows or []:
        item = _as_practice_dict(raw_item)
        practice_id = str(item.get("id") or "").strip()
        if not practice_id or practice_id not in PRACTICE_NODE_MAP:
            continue
        node = taxonomy_for_practice(practice_id, item.get("normative_references") or [])
        sources.extend(node["sources"])
    result = _normalize_sources(sources)
    result.sort(key=lambda row: (row.get("title", ""), row.get("article", ""), row.get("url", "")))
    return result
