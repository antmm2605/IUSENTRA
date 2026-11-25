"""Schede degli strumenti di Lex: che cosa si chiede a ciascuna fonte e con quali parametri.

Qui sta solo ciò che il codice non sa dire da sé (a che cosa serve la fonte per l'avvocato, i parametri della
chiamata, un esempio di domanda, i segnali che la riconoscono). Tutto il resto — sorgenti del registro operativo,
adattatori del retrieval, tool del registro Lex, calcolatori, funzioni che leggono i dati, firme e permessi — lo
ricava ``lex.strumenti.mappa`` dal codice, e il test ``lex/tests/test_strumenti_mappa.py`` fallisce se:

- una sorgente, un adattatore, un tool o un calcolatore nuovo non è in nessuna scheda né in ``FUORI_MAPPA``;
- una scheda nomina una funzione, una sorgente o un tool che nel codice non c'è più;
- ``mappa.json`` non coincide con la mappa rigenerata dal codice.

Parametri: ``tipo`` è testo, intero, data (gg/mm/aaaa), scelta, booleano o oggetto; ``valori`` elenca le scelte
ammesse, ``valori_da`` le prende dal codice (``codici_normattiva``, ``calcolatori``, ``serie_gazzetta``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Scheda:
    nome: str
    titolo: str
    gruppo: str  # fascicolo | studio | fonti_pubbliche | calcoli | redazione | telematico | software
    contenuto: str
    parametri: dict[str, dict[str, Any]]
    funzioni: tuple[str, ...]  # «modulo:Oggetto.metodo» — chi legge davvero i dati
    esempio: str
    segnali: tuple[str, ...] = ()  # espressioni regolari sulla domanda normalizzata (minuscole, senza accenti)
    sorgenti_registro: tuple[str, ...] = ()  # lex.operational_knowledge.source_registry
    adattatori: tuple[str, ...] = ()  # classi di lex/retrieval/sources
    tool_lex: tuple[str, ...] = ()  # lex.tools.registry
    dati_dello_studio: bool = True
    permessi: tuple[str, ...] = ()  # in aggiunta a quelli del registro operativo
    tempo_tipico: str = ""
    collegata_a_lex: bool = True  # False: il software ha la fonte, Lex non la consulta ancora
    nota: str = ""


_FASCICOLO = {"tipo": "testo", "obbligatorio": True,
              "descrizione": "«corrente» solo per il fascicolo aperto; se la domanda nomina una pratica (nome, «Castagnoli contro "
                             "Pianigiani», «RG 1234/2025») quella, mai «corrente»: se più pratiche corrispondono, chiedere quale"}
_FASCICOLO_OPZ = {**_FASCICOLO, "obbligatorio": False}
_DAL = {"tipo": "data", "obbligatorio": False, "descrizione": "dal giorno (gg/mm/aaaa)"}
_AL = {"tipo": "data", "obbligatorio": False, "descrizione": "al giorno (gg/mm/aaaa)"}
_CERCA = {"tipo": "testo", "obbligatorio": True, "descrizione": "parole da cercare"}
_CERCA_OPZ = {**_CERCA, "obbligatorio": False}


SCHEDE: tuple[Scheda, ...] = (
    # ------------------------------------------------------------------ fascicolo
    Scheda(
        "fascicolo_quadro", "Quadro del fascicolo", "fascicolo",
        "Il quadro in alto del fascicolo dal modello unico della causa: rito, ufficio, RG, ruolo del cliente, "
        "prossimo passo, termini gravi, udienze, economia e notifiche, ciascuno con documento e data da cui è letto.",
        {"fascicolo": _FASCICOLO,
         "sezione": {"tipo": "scelta", "obbligatorio": False,
                     "valori": ["tutto", "prossimi_passi", "termini", "udienze", "economia", "notifiche", "parti", "documenti"],
                     "descrizione": "parte del quadro richiesta"}},
        ("lex.harness.causa:fatti_del_fascicolo", "pct.fascicolo_quadro:riga_prossimo_passo",
         "pct.fascicolo_quadro:riga_termini", "pct.fascicolo_quadro:riga_economia"),
        "Nel fascicolo aperto qual è il prossimo passo e quando scade?",
        (r"\bprossim\w* pass", r"\bquadro del fascicolo\b", r"\bnel fascicolo\b", r"\b(?:a che punto|stato) (?:e|della) (?:la )?(?:causa|pratica)\b",
         r"\bche cosa (?:devo|dobbiamo) fare\b", r"\bcosa (?:devo|dobbiamo) fare\b"),
        sorgenti_registro=("fascicoli",), adattatori=("FascicoliSource",), tool_lex=("fascicolo", "collect_fascicolo_context"),
        tempo_tipico="0,2-2 s (modello della causa in sola lettura)",
    ),
    Scheda(
        "fascicolo_catena", "Catena e controlli di coerenza del fascicolo", "fascicolo",
        "I controlli del guardiano della catena (termini, agenda, passi, stato, quadro, freschezza, bozze): che cosa "
        "non torna fra letture, scadenze, udienze e quadro, con la regola che ripara o l'avviso.",
        {"fascicolo": _FASCICOLO},
        ("pct.catena.guardiano:controlla_termini", "pct.catena.guardiano:controlla_agenda",
         "pct.catena.guardiano:controlla_quadro", "pct.catena.mappa:lacune", "pct.catena.registro:RegistroGuardiano.incoerenze"),
        "Ci sono incoerenze fra le scadenze e l'agenda in questa pratica?",
        (r"\bincoerenz", r"\bnon (?:torna|tornano|combacia)", r"\bcatena\b", r"\bdisallineat"),
        tempo_tipico="< 0,5 s (registro SQLite del guardiano)",
    ),
    Scheda(
        "fascicolo_lettura", "Lettura del fascicolo", "fascicolo",
        "La «Lettura» del fascicolo: cronologia, atti, notifiche, depositi, PEC lette, termini certi, fase e "
        "narrativa della causa, costruita dai documenti e dalle PEC del fascicolo.",
        {"fascicolo": _FASCICOLO,
         "parte": {"tipo": "scelta", "obbligatorio": False,
                   "valori": ["tutto", "cronologia", "atti", "notifiche", "depositi", "pec", "termini", "narrativa", "fase"],
                   "descrizione": "parte della lettura"}},
        ("pct.fascicolo_lettura:costruisci_lettura", "pct.fascicolo_lettura:lettura_come_payload",
         "lex.context.fascicolo_lettura_context:load_fascicolo_lettura_context"),
        "Ricostruiscimi la cronologia degli atti di questa causa.",
        (r"\bcronologi", r"\bricostru\w* (?:la )?(?:vicenda|storia|causa)", r"\blettura del fascicolo\b", r"\bnarrativa\b"),
        tempo_tipico="1-5 s (dipende dal numero di documenti)",
    ),
    Scheda(
        "documenti_fascicolo", "Documenti del fascicolo e catalogo", "fascicolo",
        "I documenti del fascicolo con la classificazione del catalogo (tipo di atto, data, parte), la ricerca nel "
        "testo letto (OCR compreso) e la rilettura di un documento.",
        {"fascicolo": _FASCICOLO, "cerca": _CERCA_OPZ,
         "tipo_documento": {"tipo": "testo", "obbligatorio": False, "descrizione": "tipo del catalogo (es. sentenza, decreto ingiuntivo, relata)"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.get_documenti_fascicolo",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_documenti_fascicolo",
         "pct.fascicolo_document_catalog:classify_fascicolo_document"),
        "Trovami nel fascicolo la relata di notifica del decreto ingiuntivo.",
        (r"\bdocument[oi]\b", r"\ballegat[oi]\b", r"\brelata\b", r"\bnel (?:testo|documento)\b", r"\bcatalogo documenti\b"),
        sorgenti_registro=("documenti_fascicolo", "pdf_manager"), adattatori=("DocumentiSource",),
        tool_lex=("documento", "list_fascicolo_documents", "read_fascicolo_document", "find_in_fascicolo_document"),
        tempo_tipico="0,2-3 s",
    ),
    Scheda(
        "scadenziario", "Scadenziario e termini dello studio", "studio",
        "Le scadenze registrate dello studio (per fascicolo, cliente o periodo), con stato e origine del termine, "
        "e il piano del giorno.",
        {"fascicolo": _FASCICOLO_OPZ, "cliente": {"tipo": "testo", "obbligatorio": False, "descrizione": "nome del cliente"},
         "dal": _DAL, "al": _AL,
         "stato": {"tipo": "scelta", "obbligatorio": False, "valori": ["aperte", "scadute", "tutte"], "descrizione": "quali scadenze"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.get_scadenze_by_fascicolo",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.get_scadenze_by_cliente",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.query_calendar_page"),
        "Quali scadenze ho la prossima settimana?",
        (r"\bscadenz", r"\bscadenziario\b", r"\bin scadenza\b", r"\bscadono\b"),
        sorgenti_registro=("scadenziario",), adattatori=("ScadenziarioSource",), tool_lex=("scadenziario", "daily_plan"),
        tempo_tipico="< 0,5 s",
    ),
    Scheda(
        "agenda_udienze", "Agenda e udienze", "studio",
        "Gli appuntamenti e le udienze dell'agenda dello studio, per periodo, fascicolo o tipo.",
        {"dal": _DAL, "al": _AL, "fascicolo": _FASCICOLO_OPZ,
         "tipo": {"tipo": "scelta", "obbligatorio": False, "valori": ["udienze", "appuntamenti", "tutti"], "descrizione": "che cosa cercare"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.get_agenda_range",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_agenda"),
        "Che udienze ho domani?",
        (r"\budienz", r"\bagenda\b", r"\bappuntament", r"\bimpegni\b"),
        sorgenti_registro=("agenda",), adattatori=("AgendaSource",), tool_lex=("agenda",),
        tempo_tipico="< 0,5 s",
    ),
    Scheda(
        "pec_comunicazioni", "PEC e comunicazioni", "studio",
        "Le PEC e le email ricevute e inviate (casella PEC, posta ordinaria, messaggi), con allegati, controlli "
        "automatici sulla PEC e gli eventi giuridici che ne derivano (Control Tower).",
        {"fascicolo": _FASCICOLO_OPZ, "cerca": _CERCA_OPZ,
         "mittente": {"tipo": "testo", "obbligatorio": False, "descrizione": "mittente (es. cancelleria, controparte)"},
         "dal": _DAL, "al": _AL,
         "casella": {"tipo": "scelta", "obbligatorio": False, "valori": ["pec", "ordinaria", "tutte"], "descrizione": "quale casella"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.query_pec_page",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.list_pec_messages",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.get_pec_message",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.list_ordinary_email_messages",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.answer_pec_control_question"),
        "Mostrami l'ultima PEC arrivata dalla cancelleria.",
        (r"\bpec\b", r"\bemail\b", r"\be-mail\b", r"\bposta\b", r"\bcomunicazion\w* di cancelleria\b", r"\bmessagg"),
        sorgenti_registro=("email_pec", "pec_audit", "pec_control_tower", "email_ordinaria", "messaggi"),
        tempo_tipico="< 1 s (catalogo SQL della casella)",
    ),
    Scheda(
        "notifiche_ricevute", "Notificazioni e ricevute PEC", "studio",
        "Le notificazioni legali (presìdi e prove di notifica), le ricevute di deposito telematico (accettazione, "
        "consegna, esito della cancelleria) e le ricevute archiviate nei fascicoli.",
        {"fascicolo": _FASCICOLO_OPZ,
         "tipo": {"tipo": "scelta", "obbligatorio": False,
                  "valori": ["notificazioni", "ricevute_deposito", "ricevute_archiviate", "tutte"], "descrizione": "che cosa cercare"},
         "dal": _DAL, "al": _AL},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.query_legal_notifications_page",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.query_deposit_receipts_page",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.query_archived_receipts_page"),
        "È arrivata la ricevuta di consegna della notifica all'avvocato di controparte?",
        (r"\bricevut", r"\bnotific\w*\b", r"\bavvenuta consegna\b", r"\baccettazione\b", r"\besito (?:del )?deposito\b"),
        sorgenti_registro=("legal_notifications", "deposit_receipts", "archived_receipts"),
        tempo_tipico="< 1 s",
    ),
    Scheda(
        "avvisi_utente", "Avvisi della campanella", "studio",
        "Gli avvisi dell'utente nella campanella del software (non sono notificazioni legali).",
        {"limite": {"tipo": "intero", "obbligatorio": False, "descrizione": "quanti avvisi"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.get_notifiche_utente",),
        "Che avvisi ho nella campanella?",
        (r"\bcampanell", r"\bavvisi\b"),
        sorgenti_registro=("notifiche",), tempo_tipico="< 0,2 s",
    ),
    Scheda(
        "economia_conto", "Economia e conto del fascicolo", "studio",
        "Il conto economico del fascicolo (contributo, spese liquidate in sentenza, parcelle, incassi), preventivi, "
        "conferimenti d'incarico, attività e timesheet, pagamenti e fatturazione elettronica.",
        {"fascicolo": _FASCICOLO_OPZ, "cliente": {"tipo": "testo", "obbligatorio": False, "descrizione": "nome del cliente"},
         "voce": {"tipo": "scelta", "obbligatorio": False,
                  "valori": ["conto", "parcelle", "pagamenti", "preventivi", "conferimenti", "attivita", "spese_liquidate", "contributo_unificato", "sdi"],
                  "descrizione": "voce economica richiesta"}},
        ("pct.fascicolo_conto_economico:conto_economico", "pct.quadro_economia:percorso_economico",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.get_parcelle_by_fascicolo",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.get_pagamenti_status",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_preventivi",
         "lex.tools.economic_context_tools:dispatch_tool"),
        "Quanto ha incassato lo studio su questa pratica e che cosa resta da fatturare?",
        (r"\bparcell", r"\bfattur", r"\bincass", r"\bpreventiv", r"\bconto economico\b", r"\bspese liquidate\b",
         r"\bpagament", r"\bconferiment", r"\btimesheet\b", r"\bda fatturare\b"),
        sorgenti_registro=("economic_judgment", "preventivi", "conferimenti", "fatturazione", "timesheet", "pagamenti",
                           "fatturazione_elettronica_sdi"),
        adattatori=("PreventiviSource",), tool_lex=("preventivi",),
        tempo_tipico="0,3-2 s",
    ),
    Scheda(
        "clienti_soggetti", "Clienti e soggetti", "studio",
        "Anagrafica dei clienti e dei soggetti (parti, controparti, avvocati), recapiti, fascicoli del cliente e parti "
        "del fascicolo.",
        {"cerca": _CERCA_OPZ, "fascicolo": _FASCICOLO_OPZ,
         "dato": {"tipo": "scelta", "obbligatorio": False, "valori": ["anagrafica", "recapiti", "fascicoli", "parti"],
                  "descrizione": "che cosa serve"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.search_clienti",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_soggetti",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.parti_by_fascicolo",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.fascicoli_by_cliente"),
        "Dammi la PEC e il codice fiscale del cliente Castagnoli.",
        (r"\bcliente\b", r"\banagrafic", r"\bcodice fiscale\b", r"\brecapit", r"\bcontroparte\b", r"\bsoggett"),
        sorgenti_registro=("clienti", "soggetti"), tempo_tipico="< 0,5 s",
    ),
    Scheda(
        "ricerca_studio", "Ricerca in tutto lo studio", "studio",
        "La ricerca unica fra fascicoli, clienti, documenti e registri dello studio, quando non si sa ancora dove "
        "sta il dato.",
        {"cerca": _CERCA},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.search_fascicoli",),
        "Dove ho già trattato una revocatoria fallimentare?",
        (r"\bcerca (?:in|nello) studio\b", r"\bdove (?:ho|abbiamo) (?:gia )?(?:trattato|seguito)\b", r"\bin quali (?:pratiche|fascicoli)\b"),
        sorgenti_registro=("ricerca_studio",), adattatori=("StudioDatabaseSource", "OperationalSource"),
        tool_lex=("operational_knowledge",), tempo_tipico="0,3-2 s",
    ),
    # ------------------------------------------------------------------ fonti pubbliche
    Scheda(
        "norma_testo_vigente", "Biblioteca normativa: testo vigente", "fonti_pubbliche",
        "Il testo vigente di un articolo dall'archivio Normattiva della biblioteca, con commi (dall'XML ufficiale), "
        "modifiche e abrogazioni differite (vigenza nel tempo) e collegamento ufficiale.",
        {"atto": {"tipo": "testo", "obbligatorio": True, "valori_da": "codici_normattiva",
                  "descrizione": "codice (c.c., c.p.c., c.p., c.p.p., Cost., ...) o atto «d.lgs. 28/2010»"},
         "articolo": {"tipo": "testo", "obbligatorio": True, "descrizione": "numero dell'articolo (es. 2043, 163-bis)"},
         "comma": {"tipo": "testo", "obbligatorio": False, "descrizione": "comma richiesto"},
         "alla_data": {"tipo": "data", "obbligatorio": False, "descrizione": "vigenza a una data (gg/mm/aaaa)"}},
        ("lex.testi_ufficiali:riconosci_articolo", "lex.testi_ufficiali:testo_articolo", "lex.harness.norme:testo_norma",
         "lex.normativa.commi:commi_articolo", "lex.normativa.abrogazioni_differite:nota_articolo",
         "lex.retrieval.normativa:search_normativa_sources"),
        "Cosa dice il secondo comma dell'art. 2051 c.c.?",
        (r"\bart(?:icolo|\.)?\s*\d+", r"\btesto (?:vigente|dell)", r"\bcomma\b", r"\babrogat", r"\bvigent"),
        sorgenti_registro=("fonti_ufficiali",), adattatori=("NormativeSource",),
        dati_dello_studio=False, tempo_tipico="0,05-0,5 s (SQLite della biblioteca)",
    ),
    Scheda(
        "norma_per_argomento", "Biblioteca normativa: norma per argomento", "fonti_pubbliche",
        "La norma vigente che disciplina un istituto, trovata dalle rubriche ufficiali dei codici quando la domanda "
        "non cita l'articolo.",
        {"argomento": {"tipo": "testo", "obbligatorio": True, "descrizione": "istituto o tema (es. caparra confirmatoria)"},
         "atto": {"tipo": "testo", "obbligatorio": False, "valori_da": "codici_normattiva", "descrizione": "codice in cui cercare"}},
        ("lex.harness.rubriche:candidati", "lex.harness.rubriche:rispondi_da_rubrica"),
        "Quale norma disciplina la caparra confirmatoria?",
        (r"\bquale norma\b", r"\bche norma\b", r"\bdove (?:e|sta) (?:disciplinat|previst)", r"\bdisciplin\w*\b"),
        dati_dello_studio=False, tempo_tipico="0,1-0,5 s",
    ),
    Scheda(
        "sentenze_per_norma", "Sentenze per norma", "fonti_pubbliche",
        "Le pronunce già associate a un articolo nell'indice precalcolato della giurisprudenza (lettura istantanea, "
        "con le fonti consultate quando non ce ne sono).",
        {"norma": {"tipo": "testo", "obbligatorio": True, "descrizione": "articolo e codice (es. art. 1385 c.c.)"}},
        ("lex.harness.giurisprudenza:per_norme",),
        "Che sentenze ci sono sull'art. 1385 c.c.?",
        (r"\bsentenz\w* (?:sull|sul|in tema|relativ)", r"\bgiurisprudenza (?:sull|sul)", r"\bpronunce sull"),
        adattatori=("GiurisprudenzaSource", "NormativeSource"), dati_dello_studio=False, tempo_tipico="< 0,05 s (indice precalcolato)",
    ),
    Scheda(
        "giurisprudenza_cassazione_consulta", "Archivio Cassazione e Corte costituzionale", "fonti_pubbliche",
        "Le pronunce della Cassazione (SentenzeWeb) e della Corte costituzionale negli archivi di IUSENTRA, per "
        "estremi (numero/anno) o per testo, con massima e collegamento ufficiale.",
        {"corte": {"tipo": "scelta", "obbligatorio": False, "valori": ["cassazione", "consulta", "tutte"], "descrizione": "quale corte"},
         "numero": {"tipo": "intero", "obbligatorio": False, "descrizione": "numero della pronuncia"},
         "anno": {"tipo": "intero", "obbligatorio": False, "descrizione": "anno della pronuncia"},
         "sezione": {"tipo": "testo", "obbligatorio": False, "descrizione": "sezione (es. 3, lavoro, S.U.)"},
         "cerca": _CERCA_OPZ},
        ("lex.harness.giurisprudenza:cerca", "lex.harness.giurisprudenza:per_estremi", "lex.testi_ufficiali:trova_sentenza",
         "pct.sentenzeweb_corpus:configured_corpus"),
        "Trovami Cass. civ. sez. III n. 9449/2016.",
        (r"\bcass(?:azione|\.)", r"\bcorte costituzionale\b", r"\bconsulta\b", r"\bsezioni unite\b", r"\bs\.u\.",
         r"\bsentenza n\.", r"\bordinanza n\.", r"\borientament", r"\bgiurisprudenz", r"\bprecedent"),
        sorgenti_registro=("citazioni_cassazione",), adattatori=("GiurisprudenzaSource",), tool_lex=("giurisprudenza",),
        dati_dello_studio=False, tempo_tipico="0,1-6 s (per estremi rapido; per testo fino al limite di 6 s)",
    ),
    Scheda(
        "giustizia_amministrativa", "Testi della giustizia amministrativa", "fonti_pubbliche",
        "Sentenze e ordinanze di TAR, Consiglio di Stato e CGARS: catalogo OpenGA e testo integrale dall'archivio o "
        "letto subito dal sito ufficiale.",
        {"organo": {"tipo": "scelta", "obbligatorio": False, "valori": ["consiglio_di_stato", "tar", "cgars", "tutti"],
                    "descrizione": "organo"},
         "sede": {"tipo": "testo", "obbligatorio": False, "descrizione": "sede del TAR (es. Lazio, Milano)"},
         "numero": {"tipo": "intero", "obbligatorio": False, "descrizione": "numero del provvedimento"},
         "anno": {"tipo": "intero", "obbligatorio": False, "descrizione": "anno"},
         "cerca": _CERCA_OPZ},
        ("lex.retrieval.archivi_pubblici:cerca_testi_ga", "pct.openga_search:search_openga",
         "lex.testi_ufficiali:testo_amministrativo_ufficiale", "pct.giustizia_amministrativa_testi:testo_su_richiesta"),
        "Cerca sentenze del Consiglio di Stato sull'accesso agli atti di gara.",
        (r"\btar\b", r"\bconsiglio di stato\b", r"\bcons\. ?stato\b", r"\bcgars\b", r"\bgiustizia amministrativa\b", r"\bgiudice amministrativo\b"),
        adattatori=("GiustiziaAmministrativaSource",), dati_dello_studio=False,
        tempo_tipico="0,05-0,5 s (archivio dei testi); catalogo OpenGA 0,5-4 s; testo dal sito fino a 20 s",
    ),
    Scheda(
        "prassi_ade_inps", "Prassi dell'Agenzia delle Entrate e dell'INPS", "fonti_pubbliche",
        "Circolari e risoluzioni dell'Agenzia delle Entrate, circolari e messaggi dell'INPS, con data, numero, oggetto "
        "e testo integrale (ricerca full-text).",
        {"ente": {"tipo": "scelta", "obbligatorio": False, "valori": ["agenzia_entrate", "inps", "tutti"], "descrizione": "ente"},
         "cerca": _CERCA_OPZ,
         "numero": {"tipo": "intero", "obbligatorio": False, "descrizione": "numero della circolare o risoluzione"},
         "anno": {"tipo": "intero", "obbligatorio": False, "descrizione": "anno"}},
        ("lex.retrieval.archivi_pubblici:cerca_prassi", "pct.prassi.archivio:ArchivioPrassi.cerca",
         "pct.prassi.archivio:ArchivioPrassi.testo"),
        "C'è una circolare INPS sul congedo parentale del 2024?",
        (r"\bcircolar", r"\brisoluzion\w* (?:dell'?)?(?:agenzia|ade)", r"\bagenzia delle entrate\b", r"\binps\b", r"\bprassi\b", r"\binterpell"),
        adattatori=("PrassiSource",), dati_dello_studio=False, tempo_tipico="0,05-0,5 s (FTS SQLite)",
    ),
    Scheda(
        "gazzetta_ufficiale", "Gazzetta Ufficiale", "fonti_pubbliche",
        "I sommari ufficiali delle sei serie della Gazzetta Ufficiale con i testi degli atti: ricerca per parole, "
        "serie, tipo di atto, emittente e periodo.",
        {"cerca": _CERCA_OPZ,
         "serie": {"tipo": "scelta", "obbligatorio": False, "valori_da": "serie_gazzetta", "descrizione": "serie (SG, S1...S5)"},
         "dal": _DAL, "al": _AL,
         "tipo_atto": {"tipo": "testo", "obbligatorio": False, "descrizione": "tipo di atto (legge, decreto legislativo, ...)"}},
        ("lex.retrieval.archivi_pubblici:cerca_gazzetta", "pct.gazzetta.archivio:ArchivioGazzetta.cerca",
         "pct.gazzetta.archivio:ArchivioGazzetta.testo", "web.services.gazzetta_runtime:costruisci_vista"),
        "Che decreti legislativi sono usciti in Gazzetta questo mese?",
        (r"\bgazzetta\b", r"\bg\.u\.", r"\bpubblicat\w* in gazzetta\b", r"\bserie generale\b"),
        adattatori=("GazzettaSource",), dati_dello_studio=False, tempo_tipico="0,05-1 s (FTS SQLite)",
    ),
    Scheda(
        "aggiornamenti_normativi", "Aggiornamenti normativi e legal intelligence", "fonti_pubbliche",
        "Le novità normative, giurisprudenziali e di prassi pubblicate dalla pipeline degli aggiornamenti, la memoria "
        "di estratti già letti da fonti ufficiali e il catalogo della legal intelligence.",
        {"cerca": _CERCA, "dal": _DAL},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.get_update_intelligence_items",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.get_legal_intelligence_items",
         "lex.retrieval.legal_updates:search_legal_update_sources"),
        "Quali novità ci sono sulla riforma del processo civile negli ultimi mesi?",
        (r"\bnovit", r"\baggiornament", r"\briform", r"\bultime modifiche\b", r"\bcosa e cambiato\b"),
        sorgenti_registro=("legal_intelligence", "update_intelligence"),
        adattatori=("LegalUpdatesSource", "LegalIntelligenceSource", "LexMemorySource"), tool_lex=("legal_intelligence",),
        dati_dello_studio=False, tempo_tipico="0,1-1 s",
    ),
    Scheda(
        "web_ufficiale", "Siti ufficiali e web pubblico", "fonti_pubbliche",
        "La ricerca sui siti istituzionali ammessi (e, solo se l'avvocato lo attiva, sul web libero), quando gli "
        "archivi locali non bastano.",
        {"cerca": _CERCA, "solo_ufficiali": {"tipo": "booleano", "obbligatorio": False, "descrizione": "solo siti istituzionali"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.search_free_public_web",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_legal_sources"),
        "Cerca sul sito del Ministero della giustizia le istruzioni per il deposito degli atti penali.",
        (r"\bsul sito\b", r"\bsul web\b", r"\bin rete\b", r"\bsito (?:del|della|ufficiale)\b", r"\bonline\b"),
        sorgenti_registro=("web_libero",), adattatori=("OfficialWebSource",),
        dati_dello_studio=False, tempo_tipico="2-15 s (rete)",
    ),
    # ------------------------------------------------------------------ redazione e procedure
    Scheda(
        "modelli_atto", "Modelli d'atto", "redazione",
        "Il catalogo dei modelli d'atto (citazioni, ricorsi, comparse, diffide, contratti, pareri) con campi da "
        "compilare e la bozza nell'editor.",
        {"cerca": _CERCA_OPZ,
         "materia": {"tipo": "testo", "obbligatorio": False, "descrizione": "materia (civile, lavoro, famiglia, ...)"},
         "codice_modello": {"tipo": "testo", "obbligatorio": False, "descrizione": "codice del modello, se noto"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.search_template_atti",
         "lex.retrieval.sources.template_atti:TemplateAttiSource.search"),
        "C'è un modello di ricorso per decreto ingiuntivo?",
        (r"\bmodell[oi]\b", r"\btemplate\b", r"\bfac[- ]?simile\b", r"\bschema di (?:atto|ricorso|contratto)\b", r"\bbozza\b",
         r"\bredig", r"\bprepara\w* (?:un|l)'?(?:atto|ricorso|citazione|diffida)"),
        sorgenti_registro=("template_atti", "contratti_pareri"), adattatori=("TemplateAttiSource",),
        tool_lex=("template_atti", "list_template_atti", "read_template_atto", "read_editor_document"),
        dati_dello_studio=False, tempo_tipico="0,1-1 s",
    ),
    Scheda(
        "norme_modello", "Norme dei modelli d'atto", "redazione",
        "Le norme e le fonti ufficiali di ogni modello d'atto (fonte specifica, telematica, deontologica) e il "
        "controllo di conformità del modello compilato (requisiti, documenti e campi mancanti).",
        {"codice_modello": {"tipo": "testo", "obbligatorio": False, "descrizione": "codice del modello"},
         "atto": {"tipo": "testo", "obbligatorio": False, "descrizione": "nome dell'atto (es. atto di citazione)"}},
        ("lex.operational_knowledge.tools:OperationalKnowledgeTools.search_template_atti_sources",
         "pct.template_normative_compliance:analyze_template_compliance"),
        "Su quali norme si basa il modello di atto di precetto?",
        (r"\bnorme del modello\b", r"\brequisiti (?:dell'?|del )(?:atto|ricorso|citazione)", r"\bconformit", r"\bsu quali norme\b",
         r"\bcontenuto (?:dell'?|del )(?:atto|ricorso|citazione)"),
        sorgenti_registro=("template_atti_fonti_ufficiali",), adattatori=("ComplianceSource",), tool_lex=("compliance",),
        dati_dello_studio=False, tempo_tipico="0,1-1 s",
    ),
    Scheda(
        "procedura_guidata", "Procedure guidate", "redazione",
        "Le guide pratiche per istituto e materia (rito, competenza, termini, allegati, passi) con le norme vigenti, "
        "la matrice della pratica legale e le schede di completamento delle procedure.",
        {"procedura": {"tipo": "testo", "obbligatorio": True, "descrizione": "procedura o istituto (es. monitorio, sfratto)"},
         "materia": {"tipo": "testo", "obbligatorio": False, "descrizione": "materia"}},
        ("lex.retrieval.sources.guida_pratica:GuidaPraticaSource.search",
         "lex.operational_knowledge.tools:OperationalKnowledgeTools.search_legal_practice_matrix"),
        "Come si fa un'opposizione a decreto ingiuntivo: passi, termini e allegati?",
        (r"\bcome si fa\b", r"\bcome (?:si )?procede\b", r"\bpassi\b", r"\bprocedur", r"\bche cosa serve per\b", r"\bguida\b",
         r"\badempiment"),
        sorgenti_registro=("matrice_pratica_legale",), adattatori=("GuidaPraticaSource",),
        tool_lex=("procedure_completion_preview", "procedure_completion_search", "procedure_completion_explain_article",
                  "procedure_completion_suggest_template", "procedure_completion_list_gaps"),
        dati_dello_studio=False, tempo_tipico="0,05-0,5 s",
    ),
    # ------------------------------------------------------------------ calcoli
    Scheda(
        "calcolo", "Calcoli certi (Strumenti legali)", "calcoli",
        "I calcolatori di Strumenti legali con le tabelle normative vigenti: termini processuali e di impugnazione, "
        "interessi, rivalutazione, contributo unificato, compensi forensi, danno, imposte, prescrizione e gli altri. "
        "Il modello non calcola: sceglie il calcolatore e gli passa i dati.",
        {"strumento": {"tipo": "scelta", "obbligatorio": True, "valori_da": "calcolatori", "descrizione": "identificativo del calcolatore"},
         "campi": {"tipo": "oggetto", "obbligatorio": False,
                   "descrizione": "dati del calcolo: solo i campi dichiarati dal calcolatore (vedi «calcolatori»)"}},
        ("lex.calcoli_certi:risposta_calcolatore", "lex.calcoli_certi.riconoscimento:scegli_strumento",
         "pct.calcolatori.schema:schema_calcolatore", "lex.harness.termini:termine"),
        "Calcola gli interessi legali su 12.000 euro dal 01/03/2024 a oggi.",
        (r"\bcalcol", r"\bquanto (?:e|fa|spetta|devo|costa)\b", r"\ba quanto ammont", r"\bentro quando\b", r"\bquando scade\b"),
        sorgenti_registro=("tariffario", "uffici_giudiziari"),
        dati_dello_studio=False, tempo_tipico="< 0,1 s",
    ),
    # ------------------------------------------------------------------ telematico
    Scheda(
        "deposito_telematico", "Deposito telematico", "telematico",
        "Il deposito telematico guidato (PST/PCT, PDP penale, PAT, PTT): profilo procedurale, controlli su atto, "
        "firma e PDF, schema DatiAtto, stato e spiegazione degli errori.",
        {"fascicolo": _FASCICOLO_OPZ,
         "canale": {"tipo": "scelta", "obbligatorio": False, "valori": ["pct", "pdp", "pat", "ptt"], "descrizione": "canale telematico"},
         "controllo": {"tipo": "scelta", "obbligatorio": False,
                       "valori": ["checklist", "errore", "firma", "pdf", "datiatto", "stato"], "descrizione": "che cosa controllare"},
         "atto": {"tipo": "testo", "obbligatorio": False, "descrizione": "atto da depositare"}},
        ("pct.deposito_guidato:OrchestratoreDepositoGuidato", "pct.deposito_guidato:get_deposit_policy"),
        "Che controlli devo fare prima di depositare la comparsa sul PCT?",
        (r"\bdeposit\w*\b", r"\btelematic", r"\bpst\b", r"\bpct\b", r"\bpdp\b", r"\bpat\b", r"\bptt\b", r"\bbusta\b",
         r"\bdatiatto\b", r"\bfirma (?:digitale|cades|pades)\b", r"\bpdf/a\b"),
        sorgenti_registro=("telematico", "firma_digitale"), adattatori=("TelematicoSource",), tool_lex=("telematico",),
        tempo_tipico="0,1-1 s",
    ),
    # ------------------------------------------------------------------ software
    Scheda(
        "pagine_software", "Pagine e moduli del software", "software",
        "Dove si trova una funzione nel software IUSENTRA: moduli, sezioni, pagine e modalità di accesso.",
        {"cerca": _CERCA},
        ("pct.applicazioni_catalogo:cerca_applicazioni", "lex.retrieval.sources.applicazioni:ApplicazioniSource.search"),
        "Dove trovo nel programma la pagina per il controllo dei depositi?",
        (r"\bdove (?:trovo|si trova|sta)\b.*\b(?:pagina|programma|software|menu|funzione)\b", r"\bnel (?:programma|software|menu)\b"),
        adattatori=("ApplicazioniSource",), dati_dello_studio=False, tempo_tipico="< 0,2 s",
    ),
)


# Ciò che il codice registra ma non è una fonte d'informazione per le domande dell'avvocato, con il motivo.
# Una voce nuova del codice che non è né in una scheda né qui fa fallire il test della mappa.
FUORI_MAPPA: dict[str, dict[str, str]] = {
    "sorgenti_registro": {
        "sito_studio": "stato di configurazione del sito dello studio, non un'informazione per le pratiche",
        "privacy_gdpr": "registro di governance (permesso ai.audit), non consultato per le domande giuridiche",
        "backup_storage": "manutenzione (backup e spazio), non una fonte",
        "database": "stato del database, non una fonte",
        "ai_locale": "stato dell'AI locale, non una fonte",
        "editor_ai": "supporto alla redazione nell'editor: scrive bozze, non è una fonte",
        "chat_lex_editor": "copilota dell'editor sul documento aperto, non una fonte",
        "client_portal": "stato del portale cliente, non una fonte per le domande",
        "antiriciclaggio": "stato degli adempimenti antiriciclaggio (permesso ai.audit), non una fonte giuridica",
        "rest_api_webhooks": "catalogo delle integrazioni per il superadmin",
        "integrazioni_native": "stato delle integrazioni configurate",
        "audit": "registro delle attività (permesso ai.audit)",
    },
    "tool_lex": {
        "generate_editor_draft": "scrive una bozza: azione, non lettura",
        "propose_editor_edits": "propone modifiche: azione con conferma",
        "export_editor_document": "esporta un documento: azione",
        "create_task": "crea un'attività: azione con conferma",
        "create_deadline": "crea una scadenza: azione con conferma",
        "create_document_draft": "crea una bozza: azione con conferma",
        "create_timesheet_entry": "registra un'attività: azione con conferma",
        "create_invoice_draft": "crea una fattura in bozza: azione con conferma",
        "create_client_draft": "crea un cliente in bozza: azione con conferma",
        "create_fascicolo_draft": "crea un fascicolo in bozza: azione con conferma",
        "create_pec_draft": "crea una PEC in bozza: azione con conferma",
        "update_checklist": "aggiorna una checklist: azione con conferma",
    },
    "adattatori": {},
    "calcolatori": {},
}


__all__ = ["FUORI_MAPPA", "SCHEDE", "Scheda"]
