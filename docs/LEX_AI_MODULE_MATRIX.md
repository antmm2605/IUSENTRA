# Lex AI - Matrice Moduli

Data di aggiornamento: 3 maggio 2026

## Regola architetturale

I moduli specialistici restano proprietari della verita' operativa.
Lex Core non sostituisce i motori deterministici: legge eventi, facts e metadati, costruisce memoria, recupera fonti, genera insight e restituisce contesto riusabile a Cabina e assistenti.

Ogni modulo deve dialogare con Lex tramite:

- `eventi`
- `facts`
- `context request`
- `result pack`

## Presidio fascicoli

Sul dominio `Fascicoli` Lex deve leggere la stessa struttura che l'utente vede nella pagina pratica. Il contesto strutturato del fascicolo deve quindi mantenere sempre queste sezioni governate:

- `attivita_processuali`
- `documenti_fascicolo`
- `udienze_scadenze`
- `comunicazioni_cancelleria`
- `istanze`

Regola operativa: sui fascicoli aperti non sono ammessi cap rigidi come `limit=8` sul caricamento documentale del RAG. Se servono limiti per ranking o presentazione, devono vivere a valle dell'indicizzazione completa e non nel caricamento del contesto.

## Presidio studio e RAG per compiti

Lex non deve lavorare su un unico indice indistinto dello studio. Il contesto strutturato deve essere separato per compito e alimentato dai moduli deterministici originali del gestionale:

- `studio_operativo`
- `fascicolo_intelligence`
- `conformita_fascicolo`
- `economico`

Regola operativa: queste sezioni non vanno ricostruite con prompt o deduzioni se esiste gia' un modulo specialistico che conosce il dominio. Lex deve leggere e riusare:

- `WorkspaceIntelligenteService` per cabina, priorita', scadenze, agenda e fascicoli attenzionati
- `build_fascicolo_compliance_summary(...)` per controllo conformita', documenti mancanti, gate e prossimo passo
- moduli economici (`preventivi`, `conferimenti`, `fatturazione`) per stato economico della pratica e dello studio
- anagrafiche reali (`clienti`, `soggetti`, `parti_fascicolo`) per cliente, assistiti, controparti e soggetti collegati
- `Update Intelligence` tramite `legal_updates.db` per fonti monitorate, news pubblicate, normativa, giurisprudenza, prassi e audit, senza passare da export JSON runtime

Regola finale: se un evento o un dato e' gia' strutturato nel gestionale, Lex deve riceverlo nel proprio `structured_context` e nel retrieval dedicato, non cercarlo solo nel testo libero dei documenti.

## Matrice

| Modulo | Ruolo | Tipo | Input | Output | Eventi prodotti | Eventi consumati | Priorita' |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cabina Intelligente | Quadro strategico unico dello studio | Ibrido AI-assisted | headline studio, motori attivi, alert, fonti ufficiali, policy esecutiva | priorita', anomalie, prossime azioni, focus operativo | `cockpit_snapshot_loaded` | facts ed eventi da tutti i moduli core | Alta |
| Fascicoli | Verita' della pratica, fase, stato, timeline, parti | Deterministico con supporto Lex | stato pratica, fase, ufficio, RG, timeline, note strutturate | riepilogo intelligente, prossime azioni, criticita' | `fascicolo_context_loaded`, cambi stato pratica | documenti, agenda, telematico, anagrafiche | Alta |
| Documenti e Atti | Archivio strutturato, classificazione, versioni, metadati | Ibrido | nuovi documenti, testo estratto, classificazione, versioni, firma/PDF-A | sintesi, punti chiave, richiamo atti, confronto versioni | `document_context_loaded`, upload, classificazione | fascicolo, strumenti, compliance, ricerca | Alta |
| Agenda | Appuntamenti, udienze, blocchi operativi | Deterministico | eventi agenda, udienze, promemoria | priorita' del giorno, preparazione udienza, conflitti operativi | `agenda_context_loaded`, nuova udienza, promemoria aperto | fascicolo, scadenziario, assistente udienza | Alta |
| Scadenziario | Termini e scadenze della pratica e dello studio | Deterministico | scadenze vicine, attivita' aperte, ritardi | alert, next best action, rischio ritardo | `scadenziario_context_loaded`, scadenza creata/aggiornata | fascicolo, agenda, compliance | Alta |
| Centro Servizi Telematici | PST, PDP, PAT, import, depositi, anomalie canale | Deterministico specialistico + osservatore intelligente | esiti deposito, import portale, documenti acquisiti, errori canale | spiegazioni operative, priorita' telematiche, pratiche da riallineare | `telematico_snapshot_loaded`, `pst_import_completed`, esito deposito, errore canale | fascicolo, documenti, cabina, compliance | Alta |
| Preventivi | Percorso economico dell'incarico | Ibrido a regole forti | tipologia pratica, fasi preventivate, compensi previsti, accettazione | proposta struttura, alert di coerenza, confronto preventivo/reale | `preventivi_snapshot_loaded`, preventivo accettato | tariffario, fatture, fascicolo | Media |
| Tariffario Forense | Calcolo compensi e scenari economici | Deterministico | scaglioni, fasi, parametri, aumenti, riduzioni | spiegazione percorso scelto, scenario economico, coerenza fase/pratica | `tariffario_snapshot_loaded`, valorizzazione attivita' | preventivi, fatture, insight economici | Media |
| Fatture e Pagamenti | Emissione documenti economici e monitoraggio incassi | Deterministico amministrativo | fatture emesse, incassato, insoluti, residui | alert economici, pratiche mature per fatturazione, saldo aperto | `fatture_snapshot_loaded`, fattura emessa, pagamento registrato | preventivi, tariffario, fascicolo | Media |
| Anagrafiche | Clienti, controparti, difensori, uffici, riferimenti fiscali | Deterministico | profili soggetti, collegamenti cross-fascicolo, recapiti | disambiguazione, vista relazionale, collegamenti soggetti/pratiche | `anagrafica_context_loaded`, soggetto aggiornato | fascicolo, documenti, agenda | Media |
| Strumenti Operativi | Utility di lavoro e controlli tecnici | Ibrido | verifiche allegati, PDF-A, firma, comparazione, estrazione dati | scelta strumento, precompilazione input, interpretazione esiti | `strumenti_snapshot_loaded`, check eseguito | documenti, telematico, compliance | Media |
| Ricerca Legale / Lex Research | Normativa, giurisprudenza, prassi, Update Intelligence SQL e fonti esterne verificate | AI-first con guardrail forti | query contestualizzate, `legal_updates.db`, fonti trusted, fonti ufficiali, evidence pack | citazioni, pacchetto fonti, riferimenti aggiornati, freshness | `evidence_pack_built`, query pianificata | fascicolo, atto, udienza, telematico, cabina | Alta |
| Lex Core | Orchestrazione, retrieval, memoria, reasoning, explainability | AI-first con guardrail forti | eventi, facts, metadata, result pack, evidence pack | working memory, insight, contesto riusabile, risposta consultiva | persistenza memory, telemetry request | tutti i moduli specialistici | Alta |
| Assistente Fascicolo | Interfaccia contestuale della pratica | AI-first con guardrail forti | working memory, facts fascicolo, documenti, agenda, telematico | sintesi pratica, fase, rischi, prossime mosse | richiesta contesto fascicolo | fascicoli, documenti, agenda, telematico, ricerca | Alta |
| Assistente Redazione Atti | Supporto alla costruzione dell'atto | AI-first con guardrail forti | facts pratica, documenti rilevanti, compliance, fonti | struttura suggerita, lacune, allegati, richiami normativi | richiesta contesto atto | documenti, ricerca, compliance, strumenti | Media |
| Assistente Udienza | Preparazione udienza e quadro sintetico | AI-first con guardrail forti | agenda, scadenziario, fascicolo, documenti, timeline | punti chiave, documenti da rivedere, timeline, questioni aperte | richiesta contesto udienza | agenda, scadenziario, fascicolo, documenti | Media |
| Assistente Operativo Locale | Supporto immediato nel modulo aperto | AI-assisted | stato UI, modulo corrente, errori, facts locali | spiegazione errori, prossimo passo, suggerimenti contestuali | richiesta contesto locale | modulo corrente, Lex Core | Media |

## Contratto tecnico consigliato

Ogni modulo dovrebbe produrre payload del tipo:

```json
{
  "module": "telematico",
  "event_type": "pst_import_completed",
  "practice_id": "PRA_2026_0007",
  "documents_found": 32,
  "documents_imported": 12,
  "documents_missing": 20,
  "has_errors": true,
  "error_types": ["download_failed", "classification_uncertain"],
  "source": "pst"
}
```

## Ordine di sviluppo consigliato

1. Lex Core, adapters base, facts, timeline, profiles, working memory.
2. Cabina Intelligente e Assistente Fascicolo.
3. Integrazione forte con Centro Servizi Telematici, Documenti e Agenda/Scadenziario.
4. Preventivi, Tariffario, Fatture e insight economici.
5. Ricerca Legale con evidence pack e fonti ufficiali verificate.
6. Assistente Redazione, Assistente Udienza e strumenti avanzati.
