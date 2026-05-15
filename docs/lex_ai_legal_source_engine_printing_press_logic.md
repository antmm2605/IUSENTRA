# Workflow ispirato a Printing Press per IUSENTRA Legal Source Engine

IUSENTRA replica il pattern di workflow di Printing Press, non il suo codice e non il suo runtime. Il Legal Source Engine e' nativo IUSENTRA: non importa, non vendorizza, non esegue e non richiede Printing Press.

La logica concettuale utile e':

```text
scoperta fonte
-> manoscritto di ricerca
-> contratto normalizzato
-> strumenti riutilizzabili
-> verifica
-> dogfood test
-> scorecard
-> output fondato sulle fonti
```

## 1. Scoperta fonte

Per ogni fonte occorre identificare le capacita ufficiali:

- open data;
- API;
- RSS;
- XML;
- JSON;
- ricerca HTML pubblica documentata;
- archivi PDF ufficiali;
- identificativi stabili;
- versioning.

La scoperta registra rate limit, termini d'uso, formato citazionale, affidabilita, copertura e limiti noti. Non e' autorizzato crawling di interi siti o scraping aggressivo.

## 2. Manoscritto di ricerca della fonte

Ogni fonte deve avere un manoscritto strutturato con:

- source ID;
- nome fonte;
- URL ufficiale;
- categoria;
- giurisdizione;
- modalita di accesso;
- identificativi supportati;
- supporto versioning;
- requisiti citazionali;
- strategia di ingestione;
- comportamenti vietati;
- limiti noti;
- note.

Il manoscritto e' il punto in cui si documenta che cosa e' ammesso, che cosa e' vietato e quali condizioni servono prima di abilitare una fonte.

## 3. Contratto fonte

Ogni fonte espone lo stesso contratto interno:

- `discover()`;
- `search()`;
- `fetch()`;
- `fetch_version()`;
- `normalize()`;
- `cite()`;
- `validate_policy()`;
- `healthcheck()`.

La base implementation non fa rete. I metodi che in futuro richiederanno rete restituiscono vuoto sicuro o sollevano un errore controllato.

## 4. Registro tool

I tool Lex AI futuri devono essere costruiti dai contratti fonte. Tool consentiti:

- `search_legal_sources`;
- `search_normattiva`;
- `search_gazzetta_ufficiale`;
- `get_legal_document`;
- `get_article`;
- `get_case_law`;
- `get_version_at_date`;
- `compare_versions`;
- `explain_with_sources`.

Tool ampi vietati:

- `browse_everything`;
- `answer_legal_question_freely`;
- `scrape_site`;
- `execute_legal_action`.

## 5. Verifica prima dell'uso

Una fonte o tool non puo essere abilitata se non:

- esiste metadata fonte;
- esiste manoscritto di ricerca fonte;
- esiste policy citazionale;
- esiste rate limit;
- rete disabilitata di default;
- nessun segreto richiesto per fonte pubblica;
- nessun dato cliente coinvolto;
- test dimostrano che risposte senza citazioni vengono rifiutate;
- test dimostrano che l'ordinamento per priorita fonte funziona;
- test dimostrano assenza di chiamate live nei test unitari.

## 6. Dogfood test

I dogfood test sono dry-run:

- usano solo fixture;
- non usano rete;
- non usano dati legali reali;
- simulano domande giuridiche comuni;
- validano answer policy;
- validano citation policy;
- validano distinzione tra fonti.

Esempi minimi:

- domanda con passaggio normativa fixture citato;
- domanda senza passaggi;
- domanda su diritto vigente senza data versione;
- domanda basata su prassi/autorita;
- domanda che chiede azione legale.

## 7. Scorecard

Ogni fonte/tool ha una scorecard con:

- ufficialita;
- qualita citazionale;
- stabilita identificativi;
- supporto versioning;
- affidabilita retrieval;
- copertura;
- aggiornabilita;
- rischio legale;
- completezza implementativa;
- raccomandazione abilitazione.

La raccomandazione e' disabilitata di default. Una fonte senza citation policy, manoscritto o rete spenta di default non puo essere raccomandata.

## 8. Modalita dry-run

La modalita dry-run prevede:

- nessuna rete salvo abilitazione esplicita futura;
- solo fixture locali;
- log delle operazioni previste;
- validazione policy fonte;
- produzione report;
- nessuna persistenza fuori da cartelle artefatti ignorate.

La modalita operativa locale controllata estende il dry-run con auto-populate seed:

- genera registry, manoscritti e scorecard in `data/legal_sources/`;
- genera un indice JSONL di source-card citabili in `indexes/legal_sources/`;
- genera report in `artifacts/legal_sources/reports/`;
- non scarica fonti giuridiche;
- non usa rete;
- non legge dati cliente o tenant;
- serve solo ad abilitare discovery, retrieval locale e citation policy prima dell'ingestione fonte-per-fonte.

## 9. Disciplina artefatti

Report generati, manoscritti operativi, scorecard generate, fixture, documenti scaricati, indici, embeddings e file temporanei devono andare in cartelle ignorate.

Nulla di generato va committato salvo revisione esplicita.

## 10. Generazione risposta fondata

Pipeline:

```text
domanda utente
-> selezione fonte/tool
-> retrieval
-> validazione citazioni
-> bozza risposta
-> controllo answer policy
-> risposta finale con citazioni
```

Se i passaggi recuperati o le citazioni non bastano, la risposta finale non viene prodotta.

## 11. Nessuna dipendenza runtime da Printing Press

Regole:

- non importare Printing Press;
- non vendorizzare Printing Press;
- non shellare Printing Press;
- non richiedere Printing Press per eseguire IUSENTRA;
- replicare solo il pattern architetturale.
