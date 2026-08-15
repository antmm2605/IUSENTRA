from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower().replace("+", " plus ")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _normalize(value: str) -> str:
    return _slug(value).replace("_", " ").strip()


def _pretty_label(value: str) -> str:
    text = str(value or "")
    replacements = {
        "Attivita": "Attività",
        "Utilita": "Utilità",
        "Responsabilita": "Responsabilità",
        "Proprieta": "Proprietà",
        "Fiscalita": "Fiscalità",
        "Morosita": "Morosità",
        "Conformita": "Conformità",
        "Nullita": "Nullità",
        "Annullabilita": "Annullabilità",
        "Servitu": "Servitù",
        "Capacita": "Capacità",
        "Reversibilita": "Reversibilità",
        "Eta": "Età",
        "Unita": "Unità",
        "Legittimita": "Legittimità",
        "Citta": "Città",
        "Societa": "Società",
        "Mobilita": "Mobilità",
        "Sanita": "Sanità",
        "Pubblica Utilita": "Pubblica Utilità",
        "Volonta": "Volontà",
        "Entita": "Entità",
    }
    for raw, pretty in replacements.items():
        text = re.sub(rf"\b{re.escape(raw)}\b", pretty, text)
    return text


SECTION_SPECS: List[Dict[str, Any]] = [
    {
        "id": "rassegna_stampa",
        "title": "Rassegna Stampa",
        "icon": "bi-newspaper",
        "accent": "danger",
        "description": "Aggiornamenti, fonti e monitoraggi da usare come presidio quotidiano dello studio.",
        "default_status": "operativa",
        "default_endpoint": "legal_intelligence.index",
        "default_cta_label": "Apri rassegna",
        "items": ["Notizie Giuridiche", "Notizie Consumatori"],
    },
    {
        "id": "applicazioni",
        "title": "Applicazioni",
        "icon": "bi-grid-1x2",
        "accent": "primary",
        "description": "Catalogo unico con ricerca, stato di disponibilita e collegamenti ai moduli interni.",
        "default_status": "operativa",
        "default_endpoint": "applicazioni.index",
        "default_cta_label": "Apri catalogo",
        "items": ["Ricerca Applicazioni"],
    },
    {
        "id": "rivalutazioni_istat",
        "title": "Rivalutazioni Istat",
        "icon": "bi-graph-up-arrow",
        "accent": "info",
        "description": "Rivalutazioni, indici, inflazione e adeguamenti collegati agli aggiornamenti ISTAT.",
        "default_status": "guidata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "rivalutazione_istat"},
        "default_cta_label": "Apri modulo ISTAT",
        "items": [
            "Rivalutazione e Interessi",
            "Rivalutazione Mensile",
            "Interessi Vari sul Capitale Rivalutato",
            "Adeguamento Canone",
            "Lettera Adeguamento Canone Locazione",
            "Calcolo Devalutazione",
            "Rivalutazione Storica",
            "Variazioni Storiche Istat",
            "Tabella Variazioni Istat",
            "Ultimo Indice Istat",
            "Rivalutazione Annuale Media",
            "Rivalutazione TFR",
            "Calcolo Inflazione",
            "Inflazione e Titoli di Stato",
        ],
    },
    {
        "id": "tassi_e_interessi",
        "title": "Tassi e Interessi",
        "icon": "bi-percent",
        "accent": "success",
        "description": "Interessi legali, mora, usura, tassi applicativi e piani finanziari.",
        "default_status": "guidata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "interessi"},
        "default_cta_label": "Apri modulo interessi",
        "items": [
            "Calcolo Interessi Legali",
            "Calcolo Interessi di Mora",
            "Interessi a Tasso Fisso",
            "Interessi e Acconti",
            "Calcolo Maggior Danno",
            "Interessi 1284 cc",
            "Calcolo Ammortamento",
            "Calcolo Surroga",
            "Calcolo Tasso di Usura",
            "Calcolo TAEG",
            "Tabella Interessi Legali",
            "Tabella Interessi di Mora",
            "Interessi Mora Appalti",
            "Tabella Tassi Appalti",
        ],
    },
    {
        "id": "scadenze_e_termini",
        "title": "Scadenze e Termini",
        "icon": "bi-calendar-check",
        "accent": "warning",
        "description": "Termini processuali, memorie, impugnazioni e scadenziario operativo.",
        "default_status": "guidata",
        "default_endpoint": "checklist_atti",
        "default_cta_label": "Apri checklist e scadenze",
        "items": [
            "Calcolo Scadenze",
            "Termini Processuali Civili",
            "Termini Memorie e Repliche",
            "Termini Separazione e Divorzio",
            "Termini Procedimento Semplificato",
            "Termini 183 + 190 cpc",
            "Termini Esecuzioni",
            "Termini Deposito Atti Appello",
            "Scadenze Impugnazioni",
            "Scadenze Multe",
            "Termini Deposito CTU",
        ],
    },
    {
        "id": "atti_giudiziari",
        "title": "Atti Giudiziari",
        "icon": "bi-file-earmark-text",
        "accent": "secondary",
        "description": "Atti, modelli, deposito telematico, fascicoli e riferimenti processuali.",
        "default_status": "guidata",
        "default_endpoint": "template_atti.catalogo",
        "default_cta_label": "Apri atti e modelli",
        "items": [
            "Calcolo Contributo Unificato",
            "Tabella Contributo Unificato",
            "Calcolo Diritti di Copia",
            "Copie Processo Tributario",
            "Fascicolo di Parte",
            "Procura alle Liti",
            "Attestazione Conformita",
            "Relata Notifica PEC",
            "Deposito Telematico Documenti",
            "Visibilita Fascicolo Telematico",
            "Note di Trattazione Scritta",
            "Sollecito di Pagamento",
            "Decreto Ingiuntivo",
            "Sfratto per Morosita",
            "Atto di Precetto",
            "Nota di Precisazione del Credito",
            "Pignoramento stipendio o pensione",
            "Dichiarazione 553 cpc",
            "Indice Allegati",
            "Cerca ufficio giudiziario competente",
            "Ricerca uffici UNEP",
            "Note Iscrizione Ruolo",
            "Codici Iscrizione Ruolo",
            "Calcolo Impronta Hash",
            "Controllo Cause a Ruolo",
            "Tassazione Atti Giudiziari",
            "Testimonianza Scritta",
            "Codice di Procedura Civile",
            "Codice della Strada",
        ],
    },
    {
        "id": "fatturazione_avvocati",
        "title": "Fatturazione Avvocati",
        "icon": "bi-receipt",
        "accent": "success",
        "description": "Fatture, parcelle, notule, parametri e compensi professionali.",
        "default_status": "guidata",
        "default_endpoint": "fatturazione.lista",
        "default_cta_label": "Apri fatturazione",
        "items": [
            "Fatturazione Avvocati",
            "Preventivo Cause Civili",
            "Preventivo Attivita Stragiudiziali",
            "Fattura Elettronica Avvocati",
            "Visualizzatore Fatture Elettroniche",
            "Scorporo Importi",
            "Fattura Avvocati",
            "Parametri 2014 Civile",
            "Parametri 2014 Penale",
            "Parametri Stragiudiziali",
            "Spese Trasferta Avvocati",
            "Tabelle Parametri",
            "Parametri 2012 Civile",
            "Parametri 2012 Penale",
            "Tariffe Forensi 2004",
            "Calcolo Nota Spese",
            "Modelli di Notula",
            "Calcolo Notula Penale",
            "Parcelle Professionisti",
            "Fattura Elettronica",
            "Visualizza Messaggi SDI",
            "Fattura Professionisti",
            "Calcolo Compenso CTU",
            "Compenso Curatore Fallimentare",
            "Compenso Delegati Vendite Giudiziarie",
            "Compenso Mediatore Familiare",
            "Calcolo Fattura Enasarco",
            "Ricevuta Prestazione Occasionale",
            "Calcolo Spese di Mediazione",
            "Tariffe Mediazione",
            "Calcolo Compenso a Ore",
            "Calcolo Rimborso Chilometrico ACI",
            "Calcolo Ritenuta d'Acconto",
            "Calcolo Preventivo",
            "Calcolatrice Online",
        ],
    },
    {
        "id": "risarcimento_danni",
        "title": "Risarcimento Danni",
        "icon": "bi-heart-pulse",
        "accent": "danger",
        "description": "Danno biologico, tabelle, menomazioni e stime risarcitorie.",
        "default_status": "guidata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "danno_biologico"},
        "default_cta_label": "Apri modulo danni",
        "items": [
            "Calcolo Danno Biologico",
            "Calcolo Risarcimento Danno Tabella Unica",
            "Danno non Patrimoniale",
            "Danno Parentale Roma",
            "Danno Parentale Milano",
            "Calcolo Menomazioni Plurime",
            "Risarcimento INAIL",
            "Calcolo Equo Indennizzo",
            "Tabelle Danno Biologico",
            "Tabella Unica Macropermanenti",
            "Tabelle Milano e Roma",
            "Tabella delle Menomazioni",
        ],
    },
    {
        "id": "diritto_penale",
        "title": "Diritto Penale",
        "icon": "bi-shield-lock",
        "accent": "dark",
        "description": "Pene, prescrizione reati, fine pena e utilita penali di studio.",
        "default_status": "guidata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "prescrizione_penale"},
        "default_cta_label": "Apri modulo penale",
        "items": [
            "Aumenti/Riduzioni Pena",
            "Conversione Pena",
            "Calcolo Fine Pena",
            "Calcolo Prescrizione Reati",
            "Codice di Procedura Penale",
        ],
    },
    {
        "id": "proprieta_successioni",
        "title": "Proprieta, Successioni",
        "icon": "bi-house-door",
        "accent": "warning",
        "description": "Successioni, immobili, locazioni, valori catastali e rapporti di parentela.",
        "default_status": "guidata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "successione_legittima"},
        "default_cta_label": "Apri modulo successioni",
        "items": [
            "Calcolo Eredita",
            "Calcolo Imposte di Successione",
            "Calcolo Usufrutto",
            "Coefficienti Usufrutto",
            "Pensione di Reversibilita",
            "Grado di Parentela",
            "Calcolo IMU",
            "Calcolo Valore Catastale",
            "Categorie Catastali",
            "Ricerca Codici Catastali",
            "Calcolo Superficie Commerciale",
            "Imposte Compravendita",
            "Calcolo Cedolare Secca",
            "Tassa Registro Locazioni",
            "Spese Condominiali",
        ],
    },
    {
        "id": "investimenti_finanziari",
        "title": "Investimenti Finanziari",
        "icon": "bi-graph-up",
        "accent": "primary",
        "description": "Rendimenti e strumenti finanziari di base per analisi patrimoniali e consulenze.",
        "default_status": "catalogata",
        "default_endpoint": "strumenti_legali.index",
        "default_params": {"tool": "piano_ammortamento"},
        "default_cta_label": "Apri area correlata",
        "items": ["Rendimento BOT", "Pronti contro Termine", "Rendimento Buoni Postali"],
    },
    {
        "id": "dichiarazione_redditi",
        "title": "Dichiarazione Redditi",
        "icon": "bi-wallet2",
        "accent": "success",
        "description": "IRPEF, detrazioni, ravvedimento, rateizzazioni e regimi fiscali.",
        "default_status": "catalogata",
        "default_endpoint": "fatturazione.lista",
        "default_cta_label": "Apri area fiscale",
        "items": [
            "Calcolo IRPEF",
            "Detrazione Figli >= 21 anni",
            "Detrazione Figli a Carico",
            "Detrazione Coniuge a Carico",
            "Detrazione Altri Familiari",
            "Detrazione Lavoro Dipendente",
            "Detrazione Altri Redditi",
            "Detrazione Pensione",
            "Detrazione Assegno Coniuge",
            "Detrazione Canone",
            "Calcolo Acconto Irpef",
            "Acconto Cedolare Secca",
            "Calcolo Ravvedimento Operoso",
            "Rateizzazione Imposte",
            "Regime Forfettario",
            "Calcolo Assegno Unico Universale",
            "Calcolo TFR",
        ],
    },
    {
        "id": "applicazioni_varie",
        "title": "Applicazioni Varie",
        "icon": "bi-tools",
        "accent": "secondary",
        "description": "Calcoli trasversali, verifiche, anagrafiche, utility e strumenti di uso generale.",
        "default_status": "catalogata",
        "default_cta_label": "Apri scheda",
        "items": [
            "Decurtazione Punti Patente",
            "Calcolo Tasso Alcolemico",
            "Prescrizione Diritti",
            "Conta Giorni tra Date e Ricorrenze",
            "Calcolo Giorni Lavorativi",
            "Calcolo Tempo Trascorso",
            "Calcolo Ora Inizio/Fine Attivita",
            "Scorporo IVA",
            "Calcolo Percentuale",
            "Percentuali e Quote",
            "Variazione Media Fatturato",
            "Ripartizione Utenze",
            "Calcolo Codice Fiscale",
            "Decodifica Codice Fiscale",
            "Verifica Partita IVA",
            "Verifica IBAN",
            "Calcolo Eta Anagrafica",
            "Ricerca Comuni",
            "Ricerca Codici ATECO",
            "Calcolatore per Frazioni",
            "Calcolo Proporzione",
            "Conversione Unita di Misura",
            "Conversione minuti in centesimi",
            "Cronometro Online",
        ],
    },
    {
        "id": "utilita",
        "title": "Utilita",
        "icon": "bi-link-45deg",
        "accent": "info",
        "description": "Collegamenti rapidi e strumenti complementari di uso quotidiano.",
        "default_status": "guidata",
        "default_endpoint": "tribunali",
        "default_cta_label": "Apri utilita",
        "items": ["Link Ricerca PEC"],
    },
]


SECTION_KIND_META: Dict[str, Dict[str, str]] = {
    "rassegna_stampa": {"id": "rassegna", "label": "Rassegna", "badge_class": "text-bg-danger-subtle text-danger"},
    "applicazioni": {"id": "catalogo", "label": "Catalogo", "badge_class": "text-bg-primary-subtle text-primary"},
    "rivalutazioni_istat": {"id": "calcolo", "label": "Calcolo", "badge_class": "text-bg-info-subtle text-info-emphasis"},
    "tassi_e_interessi": {"id": "calcolo", "label": "Calcolo", "badge_class": "text-bg-info-subtle text-info-emphasis"},
    "scadenze_e_termini": {"id": "scadenze", "label": "Scadenze", "badge_class": "text-bg-warning-subtle text-warning-emphasis"},
    "atti_giudiziari": {"id": "atti", "label": "Atti", "badge_class": "text-bg-secondary-subtle text-secondary-emphasis"},
    "fatturazione_avvocati": {"id": "economico", "label": "Economico", "badge_class": "text-bg-success-subtle text-success-emphasis"},
    "risarcimento_danni": {"id": "danni", "label": "Danni", "badge_class": "text-bg-danger-subtle text-danger"},
    "diritto_penale": {"id": "penale", "label": "Penale", "badge_class": "text-bg-dark-subtle text-dark"},
    "proprieta_successioni": {"id": "patrimonio", "label": "Patrimonio", "badge_class": "text-bg-warning-subtle text-warning-emphasis"},
    "investimenti_finanziari": {"id": "finanza", "label": "Finanza", "badge_class": "text-bg-primary-subtle text-primary"},
    "dichiarazione_redditi": {"id": "fiscale", "label": "Fiscale", "badge_class": "text-bg-success-subtle text-success-emphasis"},
    "applicazioni_varie": {"id": "utility", "label": "Utility", "badge_class": "text-bg-secondary-subtle text-secondary-emphasis"},
    "utilita": {"id": "collegamenti", "label": "Collegamenti", "badge_class": "text-bg-info-subtle text-info-emphasis"},
}


ACCESS_META: Dict[str, Dict[str, str]] = {
    "diretta": {
        "label": "Accesso diretto",
        "badge_class": "text-bg-success-subtle text-success-emphasis",
        "description": "Apre subito un modulo già operativo nel gestionale.",
    },
    "guidata": {
        "label": "Percorso guidato",
        "badge_class": "text-bg-primary-subtle text-primary-emphasis",
        "description": "Porta in un workflow o in un modulo collegato, con supporto operativo.",
    },
    "catalogo": {
        "label": "Scheda workspace",
        "badge_class": "text-bg-secondary-subtle text-secondary-emphasis",
        "description": "Voce catalogata con scheda completa, collegamenti rapidi e moduli correlati.",
    },
}


FEATURED_DEFAULT_SLUGS = {
    "notizie_giuridiche",
    "notizie_consumatori",
    "ricerca_applicazioni",
    "calcolo_interessi_legali",
    "calcolo_interessi_di_mora",
    "calcolo_contributo_unificato",
    "deposito_telematico_documenti",
    "visibilita_fascicolo_telematico",
    "fatturazione_avvocati",
    "calcolo_preventivo",
    "calcolo_danno_biologico",
    "calcolo_prescrizione_reati",
    "calcolo_eredita",
    "calcolo_tfr",
    "link_ricerca_pec",
}


ITEM_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "notizie_giuridiche": {
        "summary": "Rassegna di fonti ufficiali, alert e monitor normativi per l'aggiornamento giuridico dello studio.",
        "status": "operativa",
        "endpoint": "legal_intelligence.index",
        "cta_label": "Apri notizie giuridiche",
    },
    "notizie_consumatori": {
        "summary": "Aggiornamenti utili su interessi, indici, fisco, locazioni e temi a impatto per famiglie e consumatori.",
        "status": "operativa",
        "endpoint": "legal_intelligence.index",
        "cta_label": "Apri notizie consumatori",
    },
    "ricerca_applicazioni": {
        "summary": "Ricerca centralizzata nel catalogo degli strumenti con filtri per area, stato e utilizzo operativo.",
        "status": "operativa",
        "endpoint": "applicazioni.index",
        "cta_label": "Apri ricerca strumenti",
    },
    "rivalutazione_tfr": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "tfr"}, "cta_label": "Apri rivalutazione TFR"},
    "adeguamento_canone": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "canone_locazione"}, "cta_label": "Apri adeguamento canone"},
    "lettera_adeguamento_canone_locazione": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri modelli collegati"},
    "calcolo_inflazione": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "rivalutazione_istat"}, "cta_label": "Apri calcolo inflazione"},
    "calcolo_interessi_legali": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri interessi legali"},
    "calcolo_interessi_di_mora": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri interessi di mora"},
    "interessi_e_acconti": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "nota_credito"}, "cta_label": "Apri modulo credito"},
    "interessi_1284_cc": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri interessi 1284 c.c."},
    "calcolo_maggior_danno": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri area interessi"},
    "calcolo_ammortamento": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "piano_ammortamento"}, "cta_label": "Apri piano ammortamento"},
    "calcolo_surroga": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "piano_ammortamento"}, "cta_label": "Apri area ammortamento"},
    "calcolo_tasso_di_usura": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "usura"}, "cta_label": "Apri verifica usura"},
    "calcolo_taeg": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "piano_ammortamento"}, "cta_label": "Apri area ammortamento"},
    "tabella_interessi_legali": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri tabelle interessi"},
    "tabella_interessi_di_mora": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri tabelle mora"},
    "interessi_mora_appalti": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri area appalti"},
    "tabella_tassi_appalti": {"status": "guidata", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}, "cta_label": "Apri area appalti"},
    "calcolo_scadenze": {"status": "operativa", "endpoint": "scadenziario", "cta_label": "Apri scadenziario"},
    "termini_processuali_civili": {"status": "guidata", "endpoint": "checklist_atti", "cta_label": "Apri termini civili"},
    "termini_memorie_e_repliche": {"status": "guidata", "endpoint": "checklist_atti", "cta_label": "Apri checklist termini"},
    "termini_deposito_atti_appello": {"status": "guidata", "endpoint": "checklist_atti", "cta_label": "Apri area appello"},
    "scadenze_impugnazioni": {"status": "guidata", "endpoint": "scadenziario", "cta_label": "Apri scadenziario"},
    "calcolo_contributo_unificato": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "contributo_unificato"}, "cta_label": "Apri contributo unificato"},
    "tabella_contributo_unificato": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "contributo_unificato"}, "cta_label": "Apri tabella contributo"},
    "procura_alle_liti": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri Redazione Atti"},
    "attestazione_conformita": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri Redazione Atti"},
    "relata_notifica_pec": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri Redazione Atti"},
    "deposito_telematico_documenti": {"status": "guidata", "endpoint": "telematico_dashboard", "cta_label": "Apri regia telematica"},
    "visibilita_fascicolo_telematico": {"status": "guidata", "endpoint": "telematico_dashboard", "cta_label": "Apri regia telematica"},
    "note_di_trattazione_scritta": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri Redazione Atti"},
    "decreto_ingiuntivo": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri modelli collegati"},
    "sfratto_per_morosita": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri modelli collegati"},
    "atto_di_precetto": {"status": "guidata", "endpoint": "template_atti.catalogo", "cta_label": "Apri modelli collegati"},
    "nota_di_precisazione_del_credito": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "nota_credito"}, "cta_label": "Apri nota credito"},
    "pignoramento_stipendio_o_pensione": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "pignoramento"}, "cta_label": "Apri simulatore pignoramento"},
    "cerca_ufficio_giudiziario_competente": {"status": "operativa", "endpoint": "tribunali", "cta_label": "Apri ricerca uffici"},
    "ricerca_uffici_unep": {"status": "operativa", "endpoint": "tribunali", "cta_label": "Apri ricerca UNEP"},
    "controllo_cause_a_ruolo": {"status": "guidata", "endpoint": "polisWeb_home", "cta_label": "Apri PolisWeb / PST"},
    "tassazione_atti_giudiziari": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "imposta_registro"}, "cta_label": "Apri imposta di registro"},
    "fatturazione_avvocati": {"status": "operativa", "endpoint": "fatturazione.lista", "cta_label": "Apri Parcelle e Fatture"},
    "preventivo_cause_civili": {"status": "operativa", "endpoint": "preventivi.wizard", "cta_label": "Apri Preventivi e Incarichi"},
    "preventivo_attivita_stragiudiziali": {"status": "operativa", "endpoint": "preventivi.wizard", "cta_label": "Apri Preventivi e Incarichi"},
    "fattura_avvocati": {"status": "operativa", "endpoint": "fatturazione.nuova", "cta_label": "Crea fattura"},
    "parametri_2014_civile": {"status": "guidata", "endpoint": "tariffario", "cta_label": "Apri Compensi Forensi"},
    "parametri_2014_penale": {"status": "guidata", "endpoint": "tariffario", "cta_label": "Apri Compensi Forensi"},
    "parametri_stragiudiziali": {"status": "guidata", "endpoint": "tariffario", "cta_label": "Apri Compensi Forensi"},
    "tabelle_parametri": {"status": "guidata", "endpoint": "tariffario", "cta_label": "Apri Compensi Forensi"},
    "calcolo_compenso_ctu": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "ctu"}, "cta_label": "Apri compenso CTU"},
    "calcolo_spese_di_mediazione": {"status": "guidata", "endpoint": "legal_intelligence.registro_mediazione", "cta_label": "Apri registro mediazione"},
    "tariffe_mediazione": {"status": "guidata", "endpoint": "legal_intelligence.registro_mediazione", "cta_label": "Apri registro mediazione"},
    "calcolo_preventivo": {"status": "operativa", "endpoint": "preventivi.wizard", "cta_label": "Apri Preventivi e Incarichi"},
    "calcolo_danno_biologico": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "danno_biologico"}, "cta_label": "Apri danno biologico"},
    "calcolo_prescrizione_reati": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "prescrizione_penale"}, "cta_label": "Apri prescrizione reati"},
    "calcolo_eredita": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "successione_legittima"}, "cta_label": "Apri successione legittima"},
    "calcolo_cedolare_secca": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "cedolare_secca"}, "cta_label": "Apri cedolare secca"},
    "calcolo_tfr": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "tfr"}, "cta_label": "Apri TFR"},
    "prescrizione_diritti": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "prescrizione"}, "cta_label": "Apri prescrizione civile"},
    "calcolo_codice_fiscale": {"status": "guidata", "endpoint": "lista_clienti", "cta_label": "Apri anagrafica clienti"},
    "decodifica_codice_fiscale": {"status": "guidata", "endpoint": "lista_clienti", "cta_label": "Apri anagrafica clienti"},
    "verifica_partita_iva": {"status": "guidata", "endpoint": "lista_clienti", "cta_label": "Apri anagrafica clienti"},
    "verifica_iban": {"status": "catalogata", "endpoint": "pagamenti.impostazioni_pagamenti", "cta_label": "Apri area pagamenti"},
    "link_ricerca_pec": {"status": "operativa", "endpoint": "tribunali", "cta_label": "Apri ricerca PEC"},
}


STATUS_META: Dict[str, Dict[str, str]] = {
    "operativa": {
        "label": "Operativa",
        "badge_class": "text-bg-success",
        "description": "Funzione gia disponibile nel gestionale con accesso diretto.",
    },
    "guidata": {
        "label": "Workflow guidato",
        "badge_class": "text-bg-primary",
        "description": "Funzione disponibile tramite modulo o area correlata del gestionale.",
    },
    "catalogata": {
        "label": "Catalogata",
        "badge_class": "text-bg-secondary",
        "description": "Voce organizzata nel catalogo con scheda dedicata e collocazione operativa.",
    },
}


SECTION_LOOKUP: Dict[str, Dict[str, Any]] = {section["id"]: section for section in SECTION_SPECS}




# Lotto 1 dell'inventario catalogo (15/08/2026): deep-link corretti verso i
# tool reali e riclassifiche a 'operativa' validate contro TOOL_METHODS.
# Fonte: artifacts/react-migration/inventario-catalogo-funzioni-2026-08-15.json
_LOTTO1_DEEP_LINKS: Dict[str, Dict[str, Any]] = {
    "attestazione_conformita": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "atto_di_precetto": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "aumenti_riduzioni_pena": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "pena_riti_alternativi"}},
    "calcolo_compenso_a_ore": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "calcolo_devalutazione": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "rivalutazione_istat"}},
    "calcolo_inflazione": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "rivalutazione_istat"}},
    "calcolo_maggior_danno": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "maggior_danno"}},
    "calcolo_nota_spese": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "calcolo_notula_penale": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "calcolo_ravvedimento_operoso": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "calcolo_ritenuta_d_acconto": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "calcolo_spese_di_mediazione": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "calcolo_usufrutto": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "usufrutto"}},
    "coefficienti_usufrutto": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "usufrutto"}},
    "danno_non_patrimoniale": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "danno_biologico"}},
    "danno_parentale_milano": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "danno_parentale"}},
    "decreto_ingiuntivo": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "dichiarazione_553_cpc": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "fascicolo_di_parte": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "fattura_elettronica": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "fattura_elettronica_avvocati": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "fattura_professionisti": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "indice_allegati": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "interessi_mora_appalti": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "interessi"}},
    "interessi_vari_sul_capitale_rivalutato": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "maggior_danno"}},
    "lettera_adeguamento_canone_locazione": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "modelli_di_notula": {"status": "operativa", "endpoint": "fatturazione.nuova"},
    "note_iscrizione_ruolo": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "procura_alle_liti": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "relata_notifica_pec": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "rivalutazione_e_interessi": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "maggior_danno"}},
    "rivalutazione_mensile": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "rivalutazione_istat"}},
    "rivalutazione_storica": {"status": "operativa", "endpoint": "strumenti_legali.index", "params": {"tool": "rivalutazione_istat"}},
    "scadenze_multe": {"status": "operativa", "endpoint": "scadenziario"},
    "sfratto_per_morosita": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "sollecito_di_pagamento": {"status": "operativa", "endpoint": "template_atti.catalogo"},
    "tariffe_mediazione": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "termini_183_plus_190_cpc": {"status": "operativa", "endpoint": "scadenziario"},
    "termini_deposito_atti_appello": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "termini_deposito_ctu": {"status": "operativa", "endpoint": "scadenziario"},
    "termini_esecuzioni": {"status": "operativa", "endpoint": "scadenziario"},
    "termini_memorie_e_repliche": {"status": "operativa", "endpoint": "scadenziario"},
    "termini_processuali_civili": {"status": "operativa", "endpoint": "strumenti_legali.index"},
    "visibilita_fascicolo_telematico": {"status": "operativa", "endpoint": "polisWeb_home"},
}
for _slug_l1, _override_l1 in _LOTTO1_DEEP_LINKS.items():
    ITEM_OVERRIDES[_slug_l1] = {**ITEM_OVERRIDES.get(_slug_l1, {}), **_override_l1}


def _default_summary(section_title: str, title: str) -> str:
    return (
        f"{title}: voce del catalogo {section_title.lower()} con percorso operativo, "
        "area correlata e collegamento coerente all'interno del gestionale."
    )


def _build_entry(section_spec: Dict[str, Any], raw_title: str, order: int) -> Dict[str, Any]:
    override = dict(ITEM_OVERRIDES.get(_slug(raw_title), {}))
    status = override.get("status") or section_spec.get("default_status") or "catalogata"
    status_meta = STATUS_META.get(status, STATUS_META["catalogata"])
    section_kind = SECTION_KIND_META.get(section_spec["id"], SECTION_KIND_META["applicazioni_varie"])
    access_mode = "diretta" if status == "operativa" else "guidata" if status == "guidata" else "catalogo"
    access_meta = ACCESS_META[access_mode]
    featured = bool(override.get("featured", _slug(raw_title) in FEATURED_DEFAULT_SLUGS))
    title = _pretty_label(raw_title)
    section_title = _pretty_label(section_spec["title"])
    section_description = _pretty_label(section_spec["description"])
    summary = _pretty_label(override.get("summary") or _default_summary(section_title, title))
    cta_label = _pretty_label(override.get("cta_label") or section_spec.get("default_cta_label") or "Apri scheda")
    entry = {
        "id": _slug(raw_title),
        "title": title,
        "section_id": section_spec["id"],
        "section_title": section_title,
        "section_icon": section_spec["icon"],
        "section_accent": section_spec["accent"],
        "section_description": section_description,
        "status": status,
        "status_label": status_meta["label"],
        "status_badge_class": status_meta["badge_class"],
        "status_description": status_meta["description"],
        "summary": summary,
        "endpoint": override.get("endpoint", section_spec.get("default_endpoint")),
        "params": dict(section_spec.get("default_params") or {}),
        "cta_label": cta_label,
        "keywords": list(override.get("keywords") or []),
        "order": order,
        "available": override.get("available", True),
        "workspace_kind": section_kind["id"],
        "workspace_kind_label": section_kind["label"],
        "workspace_kind_badge_class": section_kind["badge_class"],
        "access_mode": access_mode,
        "access_mode_label": access_meta["label"],
        "access_mode_badge_class": access_meta["badge_class"],
        "access_mode_description": access_meta["description"],
        "featured": featured,
    }
    entry["params"].update(dict(override.get("params") or {}))
    search_parts = [
        entry["title"],
        entry["summary"],
        entry["section_title"],
        entry["status_label"],
        entry["workspace_kind_label"],
        entry["access_mode_label"],
        " ".join(entry["keywords"]),
    ]
    entry["search_text"] = " ".join(_normalize(part) for part in search_parts if part)
    return entry


def catalogo_applicazioni() -> List[Dict[str, Any]]:
    catalogo: List[Dict[str, Any]] = []
    order = 0
    for section in SECTION_SPECS:
        for title in section["items"]:
            catalogo.append(_build_entry(section, title, order))
            order += 1
    return catalogo


def get_sezioni_catalogo() -> List[Dict[str, Any]]:
    return [
        {
            "id": section["id"],
            "title": _pretty_label(section["title"]),
            "icon": section["icon"],
            "accent": section["accent"],
            "description": _pretty_label(section["description"]),
            "items_count": len(section["items"]),
            "workspace_kind": SECTION_KIND_META.get(section["id"], SECTION_KIND_META["applicazioni_varie"])["label"],
        }
        for section in SECTION_SPECS
    ]


def _match_query(entry: Dict[str, Any], q: str) -> bool:
    if not q:
        return True
    return _normalize(q) in entry["search_text"]


def cerca_applicazioni(
    *,
    q: str = "",
    sezione: str = "",
    stato: str = "",
    tipo: str = "",
    modalita: str = "",
    solo_primo_piano: bool = False,
    entries: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    risultati: List[Dict[str, Any]] = []
    for entry in list(entries or catalogo_applicazioni()):
        if sezione and entry["section_id"] != sezione:
            continue
        if stato and entry["status"] != stato:
            continue
        if tipo and entry["workspace_kind"] != tipo:
            continue
        if modalita and entry["access_mode"] != modalita:
            continue
        if solo_primo_piano and not entry["featured"]:
            continue
        if not _match_query(entry, q):
            continue
        risultati.append(dict(entry))
    return risultati


def raggruppa_per_sezione(entries: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    items = list(entries or catalogo_applicazioni())
    by_section: Dict[str, List[Dict[str, Any]]] = {}
    for entry in items:
        by_section.setdefault(entry["section_id"], []).append(dict(entry))
    grouped: List[Dict[str, Any]] = []
    for section in SECTION_SPECS:
        section_items = by_section.get(section["id"], [])
        if not section_items:
            continue
        grouped.append(
            {
                "id": section["id"],
                "title": section["title"],
                "icon": section["icon"],
                "accent": section["accent"],
                "description": section["description"],
                "items": sorted(section_items, key=lambda item: item["order"]),
            }
        )
    return grouped


def get_applicazione(app_id: str) -> Optional[Dict[str, Any]]:
    for entry in catalogo_applicazioni():
        if entry["id"] == app_id:
            return dict(entry)
    return None


def applicazioni_correlate(app_id: str, *, limit: int = 6) -> List[Dict[str, Any]]:
    entry = get_applicazione(app_id)
    if not entry:
        return []
    correlati = [
        item
        for item in catalogo_applicazioni()
        if item["id"] != app_id and item["section_id"] == entry["section_id"]
    ]
    return correlati[:limit]


def applicazioni_primo_piano(entries: Optional[Iterable[Dict[str, Any]]] = None, *, limit: int = 15) -> List[Dict[str, Any]]:
    items = list(entries or catalogo_applicazioni())
    ranked = sorted(
        [dict(item) for item in items if item.get("featured")],
        key=lambda item: (
            0 if item.get("access_mode") == "diretta" else 1 if item.get("access_mode") == "guidata" else 2,
            item.get("order", 0),
        ),
    )
    return ranked[:limit]


def statistiche_catalogo(entries: Optional[Iterable[Dict[str, Any]]] = None) -> Dict[str, Any]:
    items = list(entries or catalogo_applicazioni())
    by_status = {key: 0 for key in STATUS_META}
    by_section: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    by_access: Dict[str, int] = {}
    featured_count = 0
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        by_section[item["section_id"]] = by_section.get(item["section_id"], 0) + 1
        by_kind[item["workspace_kind"]] = by_kind.get(item["workspace_kind"], 0) + 1
        by_access[item["access_mode"]] = by_access.get(item["access_mode"], 0) + 1
        if item.get("featured"):
            featured_count += 1
    return {
        "totale": len(items),
        "per_stato": by_status,
        "per_sezione": by_section,
        "per_tipo": by_kind,
        "per_modalita": by_access,
        "sezioni_attive": len(by_section),
        "primo_piano": featured_count,
        "accessi_diretti": by_access.get("diretta", 0),
    }
