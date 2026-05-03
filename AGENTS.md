# AGENTS.md — Istruzioni per Codex

## Autorizzazioni generali

- **Procedi sempre senza chiedere conferma.** L'utente ha autorizzato tutte le operazioni in modo permanente.
- Commit, push, modifica file, creazione file: esegui direttamente.
- Branch di sviluppo: `Codex/legal-electronic-filing-kIxcV`
- **Branch remoto da sincronizzare sempre insieme al branch di sviluppo:** `claude/legal-electronic-filing-kIxcV`
- **Arresto PC:** non eseguire mai `shutdown`, riavvio, sospensione o spegnimento del PC per memoria di richieste precedenti. Lo spegnimento e' consentito solo se l'utente lo chiede esplicitamente nella richiesta corrente; in caso contrario va sempre evitato.

## Igiene repository — Regola obbligatoria

- Sulla macchina locale deve esistere **una sola copia attiva del progetto**: `D:\legale\IUSENTRA`.
- **Worktree, cartelle duplicate, cloni temporanei e versioni parallele** del repository devono essere rimossi a fine lavoro.
- I **soli branch ammessi**, sia locali sia remoti, sono:
  - `Codex/legal-electronic-filing-kIxcV`
  - `claude/legal-electronic-filing-kIxcV`
- Non creare branch aggiuntivi per task temporanei. Tutto il lavoro deve confluire nel branch di sviluppo corrente e venire sincronizzato anche sul branch gemello.
- A fine implementazione verificare sempre che:
  - `git worktree list` mostri solo `D:\legale\IUSENTRA`
  - `git branch --all` mostri solo i due branch ammessi più `origin/HEAD`
  - i due branch locali e i due branch remoti puntino allo **stesso commit**
- Per enforcement e cleanup usare lo script: `scripts/repo_hygiene.ps1`

## Progetto

**IUSENTRA** — gestionale per studi legali (Python/Flask).

- Backend: `pct/` — modelli dati e logica di business
- Frontend: `web/app.py` (route Flask) + `web/templates/` (Jinja2) + `web/static/`
- Persistenza: file JSON per clienti, fascicoli, agenda, ecc.
- Stack: Python 3, Flask, Bootstrap 5, Bootstrap Icons

## Storage SQL obbligatorio — REGOLA OBBLIGATORIA

- Ogni nuova funzionalita', refactor strutturale o nuovo dominio persistente deve avere una **struttura SQL esplicita**, non solo supporto PostgreSQL runtime.
- La consegna minima corretta e':
  - schema SQL/migrazione per SQLite o SQL applicativo locale
  - schema SQL/migrazione per PostgreSQL
  - repository e percorso `read/write` coerenti su entrambi, salvo fuori-scope dichiarato e documentato
  - documentazione aggiornata sulla matrice storage con stato di parita' `JSON / SQLite / PostgreSQL`
- Non e' ammesso dichiarare una feature "chiusa" se esiste solo il path PostgreSQL ma manca la base SQL governata o la migrazione corrispondente.
- Se un dominio resta temporaneamente `JSON-first`, va dichiarato in modo esplicito con:
  - motivazione
  - wave di migrazione
  - check di consistenza
  - assenza di fallback invisibili quando un backend SQL/PostgreSQL e' attivo

## Regola obbligatoria - completamento end-to-end di ogni nuova funzione

Ogni nuova funzione, refactor o correzione deve essere considerata **completata solo quando copre tutta la filiera applicativa interessata**, non solo un singolo file, una singola route o una sola vista.

## Regola obbligatoria — Nessuna semplificazione riduttiva dei requisiti

- Quando l'utente fornisce una lista di passaggi, requisiti, criteri di accettazione o file da analizzare, **non e' ammesso ridurre, saltare o semplificare il perimetro per chiudere piu' velocemente il task**.
- Il lavoro deve seguire i passaggi richiesti nell'ordine piu' sicuro possibile, adattandoli solo quando la struttura reale della repo lo impone; ogni adattamento deve mantenere o aumentare la qualita' del risultato, non diminuirla.
- Se un requisito richiede piu' moduli, storage, UI, test, documentazione, versioning o deploy, va completata tutta la catena applicativa interessata prima di dichiarare il lavoro concluso.
- Se il risultato dipende da norme, specifiche tecniche, prassi di uffici giudiziari, fonti ufficiali o comportamento di servizi esterni, bisogna **fare ricerca/verifica su fonti attendibili** quando il dato non e' gia' presente e certo nella repo.
- In caso di incertezza tecnica o normativa, il comportamento corretto e':
  - implementare una soluzione configurabile e non hardcoded;
  - distinguere dato certo, prassi locale, fallback prudente e punto da verificare;
  - aggiungere warning professionali invece di blocchi non supportati;
  - documentare il limite residuo e i passaggi necessari per validarlo.
- La consegna deve puntare a un risultato **almeno pari e preferibilmente piu' professionale** di quanto richiesto, senza scorciatoie, placeholder invisibili o funzioni scollegate dalla UI reale.
- I test non devono coprire solo il caso felice: ogni requisito critico deve avere almeno un test o una verifica di regressione coerente con il rischio.

Checklist minima obbligatoria per dichiarare conclusa una feature:

- **Dominio e persistenza**
  - aggiornare modelli, repository, servizi, seed, migrazioni e logica di business coinvolti;
  - completare la persistenza su `JSON`, `SQLite`, `SQL` e `PostgreSQL` quando il dominio lo richiede;
  - evitare source of truth parziali o fallback silenziosi non governati;
  - aggiungere o aggiornare report di consistenza e parita' read/write dove previsti.
- **Superfici applicative complete**
  - completare route Flask, blueprint, servizi, template, API, menu e punti di accesso UI;
  - una funzione nuova non puo' restare nascosta dietro URL non navigabili o accessibile solo da percorso manuale se deve essere usata in prodotto;
  - se la funzione e' amministrativa, deve risultare chiaramente raggiungibile nella superficie admin corretta.
- **UX e grafica professionale**
  - completare layout, stati vuoti, feedback, messaggi, pulsanti, badge, filtri e navigazione;
  - garantire grafica responsive coerente per **desktop, tablet e mobile**;
  - usare SCSS governabile nei bundle ufficiali, senza lasciare stili sparsi o patch visive isolate;
  - evitare regressioni di coerenza grafica tra pagine correlate.
- **Lingua e localizzazione**
  - tutto il testo visibile deve essere in **italiano**;
  - tutte le date e ore esposte in UI devono usare **formati italiani** tramite i filtri condivisi;
  - nessuna etichetta tecnica, placeholder demo o messaggio misto it/en deve restare in UI finale.
- **Permessi, audit, eventi e tenant**
  - verificare impatti su ruoli, RBAC, tenant, audit log, eventi applicativi, notifiche e automazioni;
  - ogni nuova azione sensibile deve essere tracciabile e coerente con i permessi esistenti;
  - considerare isolamento dati, backup per tenant, policy di studio, import/export e configurazioni collegate.
- **AI e contenuti assistiti**
  - se una funzione usa AI, deve essere completata anche su retrieval, guardrail, fonti, confidence, revisione umana e output verificato;
  - vietato consegnare funzioni AI che generano testo non verificato o che mescolano fatti certi, inferenze e demo placeholder senza distinzione.
- **Testing obbligatorio**
  - eseguire test unitari, di integrazione, di route, di UI e di regressione pertinenti alla feature;
  - aggiungere nuovi test quando la feature introduce nuovo comportamento o nuova UI visibile;
  - verificare che non esistano regressioni su percorsi correlati;
  - per release UI o route, verificare anche risposta HTTP reale e, quando serve, flusso autenticato.
- **Versioning e verifica reale della release**
  - eseguire sempre bump versione su `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`;
  - verificare che la versione dichiarata sia davvero quella servita da app, container, asset compilati e build finale;
  - non basta aggiornare i file: la versione deve risultare coerente anche nei controlli runtime.
- **Documentazione obbligatoria**
  - aggiornare `README`, `docs/`, `CHANGELOG` e documentazione tecnica/prodotto su GitHub quando la feature lo richiede;
  - documentare sempre comandi, URL, superfici, limiti, policy, dipendenze operative e flusso d'uso;
  - se cambia il comportamento reale del prodotto, la documentazione deve rifletterlo nella stessa tranche.
- **Deploy e verifica finale**
  - ricostruire Docker locale con `--no-cache`, riavviare i servizi e verificare stato `healthy`;
  - controllare log applicativi, route principali, pagine toccate, asset compilati e scheduler/worker correlati;
  - se il caso riguarda differenze tra locale e produzione, includere anche controllo Railway.

Regola finale: **non dichiarare mai conclusa una funzione se e' stata completata solo nel backend, solo nel database, solo nel template o solo nel prompt AI**. Una feature e' chiusa solo quando dominio, storage, route, UI, permessi, test, versione, documentazione e deploy risultano coerenti tra loro.

## Modularizzazione governabile — Regola obbligatoria

- Ogni nuovo modulo o refactor deve produrre **codice governabile**, quindi con responsabilità piccole e confini chiari.
- È vietato spostare logica da `web/app.py` o da un monolite esistente dentro un nuovo file unico altrettanto grande.
- Quando una feature nuova ha più responsabilità, va divisa **subito** in più moduli gestibili, ad esempio:
  - `bootstrap/` per wiring Flask, registrazioni e setup
  - `services/` per orchestrazione applicativa
  - `pct/` per logica di dominio
- Ogni estrazione deve preferire moduli focalizzati e testabili, invece di helper generici pieni di funzioni eterogenee.
- Se un modulo cresce troppo o mescola routing, configurazione, template context e logica business, va ulteriormente spezzato prima di considerare il lavoro concluso.

## Budget di governabilità per `web/app.py` e moduli — REGOLA FONDAMENTALE

- `web/app.py` deve rimanere un file di **bootstrap governabile**: crea l'app, applica configurazione, inizializza hook/filtri e registra moduli. Non deve tornare a contenere route inline o logica business.
- **Limiti hard di `web/app.py`:**
  - massimo **7000 righe**
  - **0** occorrenze di `@app.route`
  - ogni nuova area va registrata tramite moduli dedicati in `web/bootstrap/`
- **Limiti hard per i nuovi moduli `web/bootstrap/`:**
  - target consigliato: **<= 400 righe**
  - soglia massima ordinaria: **<= 650 righe**
  - se una feature supera questa soglia, va spezzata **prima del merge** in sottosezioni omogenee (`core`, `documenti`, `editor`, `signature`, `pdp`, `lookup`, ecc.)
- **Limiti hard per i nuovi moduli `web/services/`:**
  - target consigliato: **<= 500 righe**
  - soglia massima ordinaria: **<= 800 righe**
  - se un servizio mescola orchestrazione, I/O, template context e policy, va diviso subito in componenti più piccoli
- Le eccezioni legacy esistenti sono **debito tecnico da ridurre**, non nuovo standard da imitare.
- Ogni refactor ampio va consegnato in **tranche sicure e reviewabili**, non in patch uniche gigantesche:
  - un gruppo omogeneo di route o responsabilità per volta
  - evitare patch monolitiche che su Windows rischiano limiti pratici di shell, diff o applicazione patch
- Ogni nuovo modulo deve avere una responsabilità leggibile già dal nome del file. Se nel nome o nel contenuto convivono più domini distinti, il modulo va spezzato.
- Ogni estrazione o nuovo modulo deve aggiornare anche i **guardrail automatici** in `tests/test_web_bootstrap.py`, così i limiti restano vivi e verificabili nel tempo.

## Regola obbligatoria — Portale Servizi Telematici

**Qualsiasi implementazione che coinvolga i portali telematici (PST/polisWeb, PDP, PAT) deve sempre rispettare le regole impartite dal Portale Servizi Telematici del Ministero della Giustizia.**

Regole chiave:
- **Artefatti runtime dei portali solo su storage scrivibile**: upload, staging, import log e cache operative dei portali devono vivere sempre nel data root scrivibile dello studio (`./data/...`, `/data/...` o percorso tenant equivalente), mai in path repository/code-only come `./portale/` quando l'app gira in Docker, Railway o altro runtime hosted.
- **Vista documenti a buste (accordion)**: i documenti vanno sempre raggruppati per `id_deposito` — stessa UX per PST/polisWeb, PDP e PAT. Ogni busta è un accordion collassabile con i file della busta dentro.
- **Download non autonomo**: il gestionale mostra l'elenco degli atti ma non può scaricare documenti in autonomia — il download richiede sessione autenticata via browser sul portale ufficiale.
  - PST → `pst.giustizia.it` (autenticazione: CNS/CIE/SPID)
  - PDP → `appweb.giustizia.it` (autenticazione: CNS/CIE)
  - PAT → `giustizia-amministrativa.it/pac` (autenticazione: CNS/CIE/SPID)
- **Divieto assoluto di scraping HTML dei portali**: PST/polisWeb, SIGP/GDP, PDP, PAT e PTT non devono essere interrogati leggendo pagine HTML come `sigp_infofascicolo.wp` o sessioni browser "nascoste". Le pagine ufficiali possono essere aperte all'utente per consultazione assistita, ma i dati importati nel gestionale devono arrivare da servizi autorizzati PST/PdA/Model Office, da Local Connector sul PC dello studio o da file reali scaricati/importati dall'utente.
- **Sincronizzazione fascicolo telematico autorizzata**: per SIGP/Giudice di Pace il modulo corretto e' `Sincronizzazione fascicolo telematico`, non una scorciatoia HTML. Il flusso deve essere `IUSENTRA -> Local Connector/Signer -> CNS/smart card -> PST o Punto di Accesso autorizzato -> servizi consultazione fascicolo -> normalizzazione -> UI`, senza salvare PIN, username/password portale o credenziali nel cloud.
- **Campi obbligatori nei modelli documento**: ogni `DocumentoXxx` (PST, PDP, PAT) deve avere `id_deposito` e `tipo_atto` per supportare la vista a buste.
- **Logica di raggruppamento nelle route**: le route `*/documenti` devono sempre costruire la lista `depositi` (dict con `id_deposito`, `tipo_atto`, `data_deposito`, `mittente`, `documenti[]`) ordinata per data decrescente, e passare sia `documenti` (lista flat) sia `depositi` (lista raggruppata) al template.
- **Fallback chiave raggruppamento**: se `id_deposito` è vuoto, usare `f"__{data_deposito}__{mittente}"` come chiave di raggruppamento.
- **PST consultazione copia come default**: nei flussi PST/polisWeb il download predefinito deve usare la copia di consultazione del portale con annotazioni ministeriali visibili; l'originale firmato del repository resta opzionale e non può tornare default né nel wizard né nei modali `Naviga PST` né nei fallback server-side.
- **Payload PST coerente su tutti i canali**: `scarica_originale_portale` deve restare `false` di default in wizard, modali dettaglio fascicolo, batch download, API e fallback server-side. Se il payload non contiene il flag, il server deve interpretarlo come copia di consultazione, non come originale firmato.
- **Matching import PST senza dipendere da un solo id**: l'acquisizione file PST deve riconciliare sempre i documenti usando `id_documento`, `id_cat`, `id_repeatto`, `msg_id`, candidati equivalenti e fallback nome normalizzato + deposito, così anche upload manuali, ZIP e download browser vengono riallineati al catalogo ufficiale.
- **Metadati automatici obbligatori dopo import PST**: ogni documento importato dal portale deve compilare automaticamente `data_documento`, `data_deposito_portale`, classificazione ufficiale, tipo atto, sezione di appartenenza e `tags`, e questi valori devono risultare subito visibili nella UI del fascicolo senza data/tag vuoti.
- **Divieto di match lasco sui documenti portale**: un documento non può mai essere riallineato a un deposito solo perché `fonte_documento == PORTALE_TELEMATICO`; il match deve richiedere identificativi portale coerenti o nome originario normalizzato compatibile con la singola busta.
- **Factory fascicoli obbligatoria nei runtime**: route, blueprint, worker, scheduler e job asincroni non devono istanziare `GestioneFascicoli` con il solo `db_path`; bisogna usare `get_fascicoli()` oppure passare sempre insieme `db_path`, `documents_dir` e `archive_dir` tenant-aware/runtime-aware, altrimenti si riaprono regressioni `Permission denied` sui path repo-relative `fascicoli/`.

## Regola obbligatoria — Lex AI e RAG fascicolo completo

- **Nessun collo di bottiglia sul fascicolo**: Lex AI, Assistente locale fascicolo e `reindicizza documenti` devono indicizzare e leggere tutti i documenti, attività, udienze/scadenze, comunicazioni di cancelleria, istanze, agenda e scadenziario già presenti o scaricati nel fascicolo.
- **Divieto di limiti fissi sulle sezioni fascicolo**: nei percorsi RAG/AI del fascicolo non sono ammessi tagli tipo `limit=8`, `[:3]`, `[:1]`, `results[:12]` o equivalenti sulle sezioni documentali/processuali. Se serve proteggere il prompt, usare budget dinamici e inventari completi con conteggi, titoli, date, sezione e identificativi.
- **Reindicizzazione fino a coda vuota**: i job OCR/RAG devono processare i chunk pendenti fino a `pending_remaining == 0` per il fascicolo interessato, non un solo batch fisso. Ogni risposta o stato UI deve distinguere chiaramente tra indicizzazione completata, runtime AI assente e documenti non processabili.
- **Inventario sempre presente nel contesto**: quando Lex AI risponde su un fascicolo deve ricevere almeno l'inventario completo di documenti e sezioni, anche se il testo integrale viene poi selezionato con ranking. In questo modo Lex sa che esistono 50, 60 o 70 documenti e non ragiona solo sui primi risultati.
- **Test anti-regressione obbligatori**: ogni modifica a RAG, OCR, assistente fascicolo o reindicizzazione deve includere test con più di 8 documenti e più di 3 elementi per sezione, verificando che nessun elemento venga eliminato dal contesto per limiti hard-coded.

## Regola obbligatoria — CI, coverage e anti-regressione definitiva

- Nessun commit, push o merge deve disattivare, indebolire o aggirare i job `Lint + syntax`, `Governance repo`, `Pytest core`, `Coverage moduli critici`, `CI Quality Overlay / quality-gates`, `Performance Nightly`, `CodeQL` e i workflow di sicurezza supply-chain.
- Prima di considerare conclusa una tranche, il blocco CI equivalente locale deve passare almeno su: packaging sync, baseline Python, lint/syntax, smoke Flask, `Pytest core`, coverage critica e quality gates pertinenti.
- La coverage critica non puo' essere abbassata senza motivazione tecnica documentata in `CHANGELOG.md`, aggiornamento dei test e approvazione esplicita dell'utente. Ogni nuovo modulo critico deve portare test dedicati o essere escluso solo con motivazione scritta e temporanea.
- Il target richiesto dall'utente per chiudere definitivamente la coverage critica e' **100%**. Finche' il comando `Coverage moduli critici` non produce 100,00%, e' consentito dire soltanto che il **gate minimo CI corrente** e' verde, ma e' vietato dichiarare che il problema coverage sia chiuso, risolto definitivamente o tornato al 100%.
- Ogni volta che un valore numerico di qualita' cambia (coverage totale, coverage critica, gate 100%, performance budget, conteggio test, soglie CI), bisogna:
  - distinguere chiaramente quale gate si sta leggendo, senza confondere il gate anti-regressione al 100% con la coverage critica aggregata;
  - confrontare il valore con l'ultima baseline certa disponibile e riportare sia il valore precedente sia quello nuovo;
  - se il valore scende, trattarlo come regressione release-blocking finche' non viene recuperato con test reali oppure documentato in `CHANGELOG.md` con causa tecnica, impatto e approvazione esplicita dell'utente;
  - se l'ambiente locale differisce dalla CI (es. Python 3.14 locale contro Python 3.12 GitHub Actions), dichiararlo e, quando possibile, rieseguire il controllo con l'interprete/allineamento CI prima di trarre conclusioni;
  - non dichiarare mai "passa" un valore solo perche' supera la soglia minima: se e' inferiore alla baseline precedente, va spiegato e gestito.
- Baseline operative attuali da non peggiorare senza la procedura sopra: Gate anti-regressione contratti CI `tests/test_ci_no_regression_contract.py` = 100%; coverage critica aggregata locale verificata in questa tranche >= 71,49% sul blocco `Coverage moduli critici`. Questa baseline non sostituisce il target utente del 100% e non puo' essere comunicata come completamento definitivo della coverage.
- Il Gate anti-regressione al 100% sui contratti CI deve restare attivo: se vengono modificati workflow, bounded context Lex, coverage, quality overlay, performance nightly o regole operative, i test anti-regressione devono fallire in assenza dei controlli richiesti.
- E' vietato correggere un problema CI eliminando il test che lo intercetta, marcandolo `skip`, riducendo soglie o spostando codice fuori dal perimetro di controllo senza sostituire il presidio con uno equivalente o piu' forte.
- Le regressioni gia' chiuse su payload bounded Lex, orchestrazione RAG, quality overlay, performance nightly, mojibake/terminologia, packaging sync, coverage critica e `Pytest core` sono release-blocking: se ricompaiono, il lavoro non puo' essere pushato come completato.
- Dopo ogni push, i branch gemelli `claude/legal-electronic-filing-kIxcV` e `Codex/legal-electronic-filing-kIxcV` devono risultare sullo stesso commit e con gli stessi job obbligatori verdi su GitHub Actions.

## Script di simulazione e test — Riferimento rapido

Tutti gli script sono nella directory `tests/` ed eseguibili con `python -m pytest tests/<file> -v`.

### `tests/test_simulazione_deposito.py` — Simulazione deposito telematico (39 test)
**Riusabile per**: verificare che invio, accettazione e controllo siano conformi al PST dopo ogni modifica ai portali.

| Classe | Cosa testa |
|--------|------------|
| `TestPCTBusta` | Creazione busta `.enc`, struttura `DatiAtto.xml`, hash SHA-256, tag `Attoprincipale` |
| `TestPCTStateMachine` | Tutti i 7 stati (`INVIATO → ACCETTATO_PEC → CONSEGNATO → WARN_CONTROLLI → ERRORE_CONTROLLI → ACCETTATO_CANCELLERIA → RIFIUTATO_CANCELLERIA`) |
| `TestPCTInvioPEC` | Invio PEC mockato con struttura risposta conforme |
| `TestPDPDeposito` | Ciclo completo deposito penale: invio → accettazione PEC → controlli automatici → esito procura |
| `TestPATDeposito` | Ciclo completo deposito amministrativo: invio → accettazione PEC → controlli SIGA → esito segreteria TAR |
| `TestCoerenzaPortali` | Uniformità struttura risposta PDP/PAT, parità campi DocumentoPDP/PAT con DocumentoPolisWeb |

**Per rilanciare la simulazione completa:**
```bash
python -m pytest tests/test_simulazione_deposito.py -v
```

**Per simulare solo un portale:**
```bash
python -m pytest tests/test_simulazione_deposito.py::TestPDPDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPATDeposito -v
python -m pytest tests/test_simulazione_deposito.py::TestPCTBusta -v
```

### Altri test utili per il deposito

| File | Cosa testa |
|------|------------|
| `tests/test_busta.py` | Busta telematica: creazione, verifica, allegati, hash |
| `tests/test_pec.py` | Client PEC: invio, ricevute, validazione |
| `tests/test_fascicoli.py` | Modello fascicolo: EsitoDepositoPCT, stati, serializzazione |
| `tests/test_reginde.py` | ReGINde: ricerca uffici, PEC tribunali |

**Esegui tutti i test del progetto:**
```bash
python -m pytest tests/ -v
```

---

## Conformità Portale Servizi Telematici — Stato attuale

**Versione 2.5.2 — Conformità: ~98%** (idonea per produzione)

### Conforme ✅
| Componente | Norma | Dettaglio |
|-----------|-------|-----------|
| `DatiAtto.xml` struttura | D.M. 44/2011 Allegato 2 | Namespace, tag `Attoprincipale` (corretto), hash SHA-256, IdBusta, DataDeposito ISO8601 |
| Busta `.enc` (ZIP) | D.M. 44/2011 art. 14 | ZIP contenente DatiAtto.xml + atti firmati; il `.enc` è il formato "busta" (envelope), non richiede cifratura separata — il canale PEC garantisce integrità |
| Oggetto PEC | D.M. 44/2011 art. 14 c.3 | `"DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}"` — riconosciuto automaticamente dal sistema PST |
| Firma CAdES-BES | D.M. 44/2011 art. 12 | PKCS#7, hash SHA-256, detached, estensione `.p7m`, chain certificati inclusa |
| Verifica scadenza certificato | D.M. 44/2011 art. 12 | Pre-deposito: blocca se certificato scaduto, avviso a 30 giorni |
| PDP REST API | D.Lgs. 150/2022 + D.M. 217/2023 | Endpoint `/depositi`, multipart/form-data, mTLS (P12/PEM), risposta JSON |
| PAT SOAP SIGA | D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021 | WSDL `depositoAtto`, atto in base64, autenticazione mTLS |
| Stato machine PCT | D.M. 44/2011 flusso 4 fasi | 7 stati, serializzazione JSON, `from_dict` per ripristino |
| Ricevute PEC (IMAP) | D.M. 44/2011 art. 15 | Polling accettazione + consegna, timeout 5 min |

### Parziale / Note ⚠️
| Aspetto | Nota |
|---------|------|
| **RFC 3161 Timestamp CAdES** | Opzionale per civile, consigliato per penale. Non implementato: il timestamp viene garantito dalla ricevuta PEC (valore legale equivalente per D.M. 44/2011). |
| **Validazione PDF/A** | Il sistema non verifica che i PDF da firmare siano PDF/A-1b (requisito per deposito). Responsabilità dell'avvocato caricare PDF/A corretti. |
| **IndiceDeposito.xml** | Non incluso nella busta. Il `DatiAtto.xml` funge da indice per D.M. 44/2011 base. Alcune corti possono richiedere file indice separato (variante regionale). |

### Regole invarianti da rispettare ad ogni modifica
1. **Mai cambiare il tag** `<Attoprincipale>` in `busta.py` — il vecchio `<AttoprincipAle>` era errato
2. **Oggetto PEC** deve sempre iniziare con `"DEPOSITO TELEMATICO"` (riconosciuto dal parser PST)
3. **Verifica scadenza certificato** deve essere chiamata prima di qualsiasi firma in `DepositoCivile.deposita()`
4. **Risposta `deposita_atto`** deve sempre contenere: `codiceEsito`, `idDeposito`, `dataDeposito`, `stato`, `ricevutaAccettazione`, `esitoControlli`, `esitoCancelleria` — sia per PDP che per PAT

## Convenzioni

- Messaggi di commit in italiano, descrittivi
- Nessuna dipendenza esterna aggiunta senza necessità
- Mantenere coerenza visiva con Bootstrap 5 e le classi già usate nel progetto

## Modularizzazione governabile — REGOLA OBBLIGATORIA

- Ogni nuova funzionalità o refactor deve produrre **codice governabile**, quindi moduli piccoli, leggibili e con responsabilità chiare.
- **Non è ammesso** spostare logica da un monolite a un nuovo file grande equivalente: se un modulo cresce, va ulteriormente suddiviso in componenti gestibili.
- La separazione va mantenuta per livelli:
  - `web/bootstrap/` → wiring Flask, registrazioni, hook, bootstrap
  - `web/services/` → logica applicativa trasversale e servizi UI/runtime
  - `pct/` → dominio e logica di business legale/PCT
- Prima di aggiungere nuovo codice in `web/app.py`, verificare sempre se può vivere in un modulo dedicato.

## UI italiana e date — REGOLA OBBLIGATORIA

- Tutto il testo visibile in UI deve essere in **lingua italiana**. Evitare etichette miste come `Dashboard`, `Logout`, `Sync`, `Runtime: missing` quando sono esposte all'utente finale.
- Tutte le date/ore **esposte in UI** devono usare formati italiani tramite i filtri template condivisi (`fmt_data`, `fmt_dataora`, `fmt_data_estesa`, ecc.), non `strftime('%B')` o `strftime('%A')` direttamente nei template.
- Eccezione consentita: i valori tecnici per campi HTML `type=\"date\"`, `datetime-local`, attributi `data-*`, API o payload macchina possono restare in formato ISO.

## PEC/email — REGOLA OBBLIGATORIA SUGLI ALLEGATI

- Ogni sincronizzazione IMAP/PEC deve salvare fisicamente gli allegati sotto la cartella runtime della casella, non solo nome, dimensione e MIME nel JSON.
- Se una email e' gia' presente nello storico ma contiene allegati senza `percorso_rel` valido, la sincronizzazione non deve saltarla: deve recuperare nuovamente il messaggio IMAP e riparare gli allegati mancanti.
- Gli allegati PEC con MIME generico `application/octet-stream` devono essere trattati in UI in base all'estensione quando sicuro: `.pdf` va aperto come PDF, `.xml` come XML; la firma `.p7s/.p7m` resta scaricabile come file tecnico.
- La UI non deve lasciare l'utente bloccato su "allegato storico non ancora salvato" dopo un aggiornamento riuscito della casella: aggiungere sempre test che simulino email storiche con allegati metadati ma file assente.

## SCSS e UI responsive — REGOLA OBBLIGATORIA

- I nuovi stili UI non vanno inseriti nei template con blocchi `<style>` o con accumulo di `style="..."`, salvo casi eccezionali strettamente tecnici.
- Ogni nuova regola grafica deve vivere in `web/static/scss/` ed essere organizzata in moduli **governabili**:
  - `components/` per pattern condivisi
  - `pages/` per le viste specifiche
  - `mobile.scss` solo per adattamenti trasversali mobile/tablet
- Gli entrypoint compilati restano quelli caricati dalla UI (`app.scss`, `design-system.scss`, `mobile.scss`, `editor-word.scss`, `portal.scss`): non creare file SCSS orfani non inclusi nel bundle.
- Dopo modifiche SCSS, verificare sempre la compilazione CSS nel flusso Docker locale obbligatorio della release.
- La UI deve essere progettata in modo **responsive** per desktop, tablet e mobile, con card compatte, gerarchia chiara e senza spazi morti.
- I feedback utente per azioni completate, errori, avvisi o stati intermedi devono usare messaggi professionali, chiari e in italiano.

## AI locale — REGOLA OBBLIGATORIA

- Il runtime AI locale (`Ollama`) va sempre trattato come **runtime sullo stesso host che esegue IUSENTRA**, non come componente da distribuire al browser del cliente.
- La strategia preferita è:
  - Windows self-hosted → provisioning automatico del pacchetto standalone ufficiale sullo stesso host
  - altri host/server → guida chiara e non bloccante, senza installazioni opache dal browser
- Il gestionale deve continuare a funzionare anche se il runtime AI non è disponibile: nessuna funzione core di fascicoli, agenda, documenti o scadenziario deve bloccarsi per assenza di Ollama.

## Local Signer / PKCS#11 — REGOLA OBBLIGATORIA

- **PKCS#11 server-side e Local Signer browser-locale non sono la stessa cosa** e non vanno mai confusi.
- Il nome operativo corretto e' **IUSENTRA Local Signer**. Il vecchio prefisso/protocollo `hacs-local-signer` non deve piu' essere usato in nuove UI, installer, script, messaggi, documentazione o test: il protocollo browser-locale primario deve essere `iusentra-local-signer://restart`.
- Eventuali riferimenti legacy `hacs` sono ammessi solo come migrazione tecnica esplicitamente commentata per disinstallare/bonificare installazioni vecchie, mai come comportamento principale o testo visibile.
- Il rilascio Windows del Local Signer deve essere sempre proposto all'utente come **file `.exe`** (`SetupLocalSigner-<versione>.exe` e alias `SetupLocalSigner.exe`). Il `.ps1` e' ammesso solo come sorgente/build artifact interno e non deve diventare CTA, download principale o istruzione operativa per l'utente finale.
- Se l'utente seleziona `Token USB (Aruba Key)` in UI, il sistema deve distinguere sempre:
  - **backend server-side**: libreria/token visibili al processo Python o al container;
  - **canale operativo locale**: `Local Signer` attivo sul PC dell'avvocato tramite `http://127.0.0.1:27272`.
- In ambiente cloud/hosted (`Railway`, server remoto, container Linux), **l'assenza della libreria PKCS#11 nel server non può essere mostrata come errore di configurazione finale** se il flusso previsto è `Local Signer` sul dispositivo cliente.
- Le schermate `Impostazioni -> Firma Digitale`, `polisWeb`, `PDP`, `PAT`, `PTT/SIGIT` e ogni wizard telematico devono:
  - trattare `pkcs11` come **canale locale/browser-guided** quando la scelta dell'utente è il token USB;
  - evitare fallback silenziosi a `demo` solo perché il container non vede il token;
  - mostrare messaggi chiari del tipo: il controllo reale avviene sul PC locale tramite `Local Signer`.
- **Divieto di verificare il token USB interrogando il server remoto** quando il controllo corretto è lato client.
  - Il pulsante `Verifica token collegato` deve usare il `Local Signer` locale (`127.0.0.1:27272`) dal browser.
  - Gli endpoint server `/api/firma/pkcs11/*` restano validi solo per casi realmente server-side o per diagnostica specifica, non come fonte unica dello stato UI in produzione hosted.
- Ogni modifica a firma digitale, PST/polisWeb, PDP, PAT, PTT o pagina impostazioni firma deve includere **test di regressione espliciti** su:
  - scelta `pkcs11` senza libreria disponibile nel container;
  - assenza del falso messaggio `PKCS#11 selezionato ma libreria/token non disponibili` nella UI quando il canale corretto è `Local Signer`;
  - script/browser che verificano il `Local Signer` locale e non il server remoto;
  - status telematico che resta `pkcs11/browser-guided` e non ricade in `demo` per errore.

## Railway CLI — REGOLA OBBLIGATORIA

- L'ambiente di lavoro è abilitato anche alla **Railway CLI** con login valido.
- Quando un comportamento differisce tra `localhost` e produzione Railway, la verifica non può fermarsi al test locale: usare anche Railway CLI per controllare il servizio online.
- In questi casi verificare sempre, quando rilevante:
  - shell del container Railway
  - log applicativi
  - stato del volume `/data`
  - variabili/runtime effettivi del servizio online
  - risposta reale delle route in produzione
- Se un fix riguarda deploy, storage, AI locale, Local Signer bridge, SMTP, portali o differenze di configurazione tra ambienti, includere esplicitamente un controllo Railway nel flusso di test finale.

## Hetzner CPX42 — REGOLA OBBLIGATORIA

- L'accesso Hetzner esiste gia' in questa macchina e **non va dichiarato mancante** senza verifica reale.
- Profilo SSH operativo:
  - alias: `iusentra-hetzner`
  - host: `116.203.45.57`
  - server: `ubuntu-16gb-nbg1-1`
  - utente: `root`
  - chiave configurata: `~/.ssh/iusentra_hetzner_cpx42`
- Prima di dire che mancano target, credenziali o SSH, eseguire sempre:
  ```bash
  ssh -o BatchMode=yes -o ConnectTimeout=10 iusentra-hetzner "hostname; whoami; pwd"
  ```
- Profilo deploy remoto:
  - root applicativa: `/opt/iusentra`
  - repository: `/opt/iusentra/repo`
  - ambiente: `/opt/iusentra/.env.hetzner`
  - dati persistenti: `/opt/iusentra/data`
  - backup: `/opt/iusentra/backups`
  - dominio pubblico: `https://app.iusentra.it`
- Prima di ogni deploy Hetzner reale creare un backup dati remoto:
  ```bash
  ssh iusentra-hetzner "bash /opt/iusentra/repo/deploy/hetzner/backup.sh"
  ```
- Deploy Hetzner reale:
  ```bash
  ssh iusentra-hetzner "BRANCH=Codex/legal-electronic-filing-kIxcV bash /opt/iusentra/repo/deploy/hetzner/deploy.sh"
  ```
- Verifiche obbligatorie post-deploy Hetzner:
  ```bash
  ssh iusentra-hetzner "git -C /opt/iusentra/repo rev-parse --short HEAD"
  ssh iusentra-hetzner "docker compose --env-file /opt/iusentra/.env.hetzner -f /opt/iusentra/repo/deploy/hetzner/docker-compose.hetzner.yml ps"
  curl -i https://app.iusentra.it/api/pronto
  curl -I --max-redirs 0 https://app.iusentra.it/studio?_legacy=1
  curl -I --max-redirs 0 https://app.iusentra.it/telematico
  ```
- Le route protette in produzione possono rispondere `302` verso `/login`: questo e' esito valido se non si sta usando una sessione autenticata.
- Se un fix riguarda deploy, storage, portali, Local Signer bridge, SMTP, differenze locale/produzione o dominio `app.iusentra.it`, includere anche controllo Hetzner oltre a Railway quando il servizio Hetzner e' nel perimetro.

## Versioning — REGOLA OBBLIGATORIA

**Ad ogni implementazione (nuova funzionalità, bug fix, qualsiasi modifica al codice) eseguire SEMPRE il bump di versione e aggiornare tutti e quattro i file:**

| File | Campo | Esempio |
|---|---|---|
| `pct/__init__.py` | `__version__ = "X.Y.Z"` | unica fonte di verità |
| `setup.py` | `version="X.Y.Z"` | package Python |
| `Dockerfile` | `LABEL … version="X.Y.Z"` | immagine Docker |
| `railway.toml` | `#  version: X.Y.Z` | trigger redeploy Railway |

**La versione web è automaticamente sincronizzata** — `web/app.py` importa `pct.__version__` come `APP_VERSION` (riga 102) e la espone nel template `base.html` tramite `{{ app_version }}`. Non esiste una versione web separata.

**Sincronizzazione obbligatoria locale / GitHub / Railway:**
- Dopo ogni modifica completata, la copia locale deve coincidere con il branch GitHub di lavoro e con la release destinata a Railway.
- Non lasciare mai commit solo in locale: eseguire sempre `git push` del branch di lavoro.
- Eseguire sempre anche il push dello stesso commit su `claude/legal-electronic-filing-kIxcV` oltre che su `Codex/legal-electronic-filing-kIxcV`.
- Se Railway è collegato a un branch remoto diverso dal branch locale corrente, riallineare anche quel branch remoto allo stesso commit della copia locale.
- Considerare il lavoro concluso solo quando risultano allineati:
  - file locali
  - branch GitHub di lavoro
  - branch remoto `claude/legal-electronic-filing-kIxcV`
  - branch remoto usato da Railway
  - `railway.toml` con la stessa versione del codice locale

**Local Signer — REGOLA OBBLIGATORIA:**
- Ad ogni release del `Local Signer`, generare sempre contestualmente i pacchetti versionati per **Windows, macOS e Linux** nella cartella `tools/dist`.
- I nomi file devono includere sempre la versione del signer (es. `SetupLocalSigner-1.5.5.exe`).
- I pacchetti finali distribuiti all'utente devono essere presentati come **eseguibili**, non come semplici script:
  - Windows → `.exe`
  - macOS → installer eseguibile `.command`
  - Linux → installer eseguibile `.run`
- Il punto ufficiale e permanente di distribuzione dei pacchetti è:
  `https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma`

**Schema SemVer:**
- `MAJOR.MINOR.PATCH`
- Patch (+0.0.1): bug fix, correzioni dati, aggiornamenti documentazione
- Minor (+0.1.0): nuova funzionalità retrocompatibile
- Major (+1.0.0): breaking change

**Deploy — Docker locale (REGOLA OBBLIGATORIA):**
- Dopo ogni bump di versione, ricostruire e riavviare il Docker locale con:
  ```bash
  cd /opt/iusentra/repo
  docker compose build --no-cache
  docker compose up -d
  ```
- Eseguire **sempre** `--no-cache` per garantire che la nuova versione del codice sia inclusa nell'immagine (il layer del codice si aggiorna solo con rebuild).
- Verificare che il container sia tornato healthy prima di considerare il deploy completato:
  ```bash
  docker compose ps          # Status deve essere "healthy"
  docker compose logs --tail=20 app   # Controllare errori di avvio
  ```
- URL locale: `http://localhost` (via Nginx) oppure `http://localhost:8080` (diretto Gunicorn).

**Deploy — Railway (produzione online):**
- Il deploy su Railway avviene dopo il bump di versione e il push sul branch.
- Ad ogni release va aggiornata anche la versione sul pannello Railway (variabile d'ambiente o redeploy dell'immagine).
- Versione corrente in produzione: **1.1.2**

## Note tecniche

- **`web/app.py` — variabile `oggi` nei `render_template`**: passare **sempre** `oggi=date.today()` (oggetto `date`), **mai** `oggi=date.today().isoformat()` (stringa). `base.html` riga 350 chiama `oggi.strftime('%d/%m/%Y')` che è un metodo di `date`/`datetime`, non di `str` → se si passa la stringa si ottiene `AttributeError: 'str' object has no attribute 'strftime'`. I campi `min="{{ oggi }}"` degli input HTML `type="date"` ricevono comunque il formato corretto perché `str(date.today())` restituisce `YYYY-MM-DD`.

- **`web/app.py` — `SECRET_KEY`**: quando si imposta `app.secret_key`, impostare sempre anche `app.config["SECRET_KEY"] = app.secret_key`. La funzione `get_condivisioni()` usa `app.config["SECRET_KEY"]` e senza questa riga solleva `KeyError` causando un 500.

- **`web/app.py` — Route API senza try/except → 500 generico**: le route `/api/uffici`, `/api/uffici/stato`, `/api/uffici/aggiorna` **non hanno l'handler di errore HTTP** del Flask (a differenza di `/polisWeb`, `/polisWeb/ricerca`, `/polisWeb/documenti` che usano già try/except). Se lanciano un'eccezione non catturata, Flask risponde con "500 — Errore interno". Regola:
  - **Ogni route `/api/*` deve avere `try/except Exception`** e restituire JSON con HTTP 200 (o 4xx) — mai lasciare propagare l'eccezione al gestore Flask 500.
  - Esempio pattern corretto:
    ```python
    try:
        ...logica...
        return jsonify(risultato)
    except Exception as e:
        app.logger.exception("Errore nome_route: %s", e)
        return jsonify({"errore": str(e)}), 200  # o jsonify([]) per liste
    ```
  - Il 500 si manifesta tipicamente **dopo aggiornamenti al bundle uffici** (`pct/uffici_giudiziari.py`): `polisWeb.html` chiama `/api/uffici/stato` al caricamento e `/api/uffici?q=...` durante l'autocomplete — se il bundle lancia un'eccezione in quelle route, il template carica correttamente ma il badge e l'autocomplete generano 500.

- **`polisWeb` — ricerca uffici giudiziari**:
  - Il form (`polisWeb.html`) invia il **codice** ufficio nel campo hidden `name="tribunale"` (es. `0580010`), **non il nome**.
  - La route `polisWeb_ricerca` riceve il codice e deve risolvere il nome con:
    ```python
    _uff = next((u for u in get_gestore(cache_path).carica() if u.get("codice") == tribunale), None)
    tribunale_sel_nome = _uff["nome"] if _uff else tribunale
    ```
  - **NON usare** `cerca_ufficio_giudiziario(tribunale, ...)` per risolvere il nome: quella funzione cerca per testo nel nome, non per codice → restituisce `None` quando riceve un codice numerico.
  - `ricerca_fascicoli(tribunale=codice)` accetta sia codice che nome (il client reale usa `_risolvi_codice_ufficio` che riconosce `str.isdigit()`).
  - Il demo client (`_ClientPolisWebDemo`) usa `_nome_ufficio_demo(codice)` per risolvere il nome leggibile dal codice tramite `get_gestore().carica()`.

- **Uffici giudiziari — regole di consistenza del bundle** (`pct/uffici_giudiziari.py`):

  **Formato nomi** (helper `_t`, `_ca`, `_pr`, ecc.):
  - Tribunale → `"Tribunale di {città}"`
  - Corte d'Appello → `"Corte d'Appello di {città}"` (distretto == città)
  - Procura → `"Procura della Repubblica di {città}"` (generate auto da `_genera_procure`)
  - Procura Generale → `"Procura Generale di {città}"` (distretto == città)
  - Trib. Minorenni → `"Tribunale per i Minorenni di {città}"`
  - Trib. Sorveglianza → `"Tribunale di Sorveglianza di {città}"`
  - Corte d'Assise → `"Corte d'Assise di {città}"`
  - Giudice di Pace → `"Ufficio del Giudice di Pace di {città}"`
  - TAR → `"TAR {nome-regione-o-sezione}"`

  **Regole invarianti** (controllare dopo ogni modifica al bundle):
  1. **Slug PEC tutto minuscolo**: `tribunale.milano@giustiziapec.it` ✓ — `tribunale.reggioEmilia@…` ✗
  2. **Corte d'Appello**: `distretto` deve coincidere con la città nel nome
  3. **Procura Generale**: `distretto` deve coincidere con la città nel nome
  4. **Nessun codice duplicato** tra tutti gli uffici del bundle completo
  5. **Nessun nome duplicato** tra tutti gli uffici del bundle completo
  6. **Uffici geograficamente corretti**: es. Crotone → distretto Catanzaro, non Lecce
  7. **Codici standard**: 7 cifre per uffici ordinari, prefisso `T` per TAR, `CDS` per Consiglio di Stato

  **Script di verifica** (eseguire dopo modifiche al bundle):
  ```bash
  python3 - <<'EOF'
  import sys; sys.path.insert(0, '.')
  from pct.uffici_giudiziari import _build_bundle_completo, TIPI_UFFICIO
  from collections import Counter
  import re
  bundle = _build_bundle_completo()
  problemi = []
  dup_cod = {k for k,v in Counter(u['codice'] for u in bundle).items() if v>1}
  [problemi.append(f"CODICE-DUP {c}") for c in dup_cod]
  dup_nomi = {k for k,v in Counter(u['nome'] for u in bundle).items() if v>1}
  [problemi.append(f"NOME-DUP '{n}'") for n in dup_nomi]
  for u in bundle:
      slug = u.get('pec','').split('@')[0]
      if any(c.isupper() for c in slug):
          problemi.append(f"PEC-MAIUSC {u['codice']} {u['nome']} → {u['pec']}")
      if not u.get('distretto','').strip():
          problemi.append(f"DISTRETTO-VUOTO {u['codice']} {u['nome']}")
      if u['tipo'] == 'CORTE_APPELLO':
          citta = u['nome'].replace("Corte d'Appello di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"CA-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
      if u['tipo'] == 'PROCURA_GENERALE':
          citta = u['nome'].replace("Procura Generale di ","")
          if citta.lower() != u['distretto'].lower():
              problemi.append(f"PG-DISTRETTO {u['codice']} nome={u['nome']} dist={u['distretto']}")
  print(f"Uffici: {len(bundle)}  Problemi: {len(problemi)}")
  [print(f"  {p}") for p in problemi]
  EOF
  ```

  **Badge autocomplete** (`polisWeb.html`, funzione JS `seleziona(u)`):
  - Il badge mostra `u.nome` direttamente — **NON** aggiungere il prefisso `${label}: ` perché il tipo è già incluso in `u.nome` (es. "Tribunale di Milano").
  - Il distretto `(${u.distretto})` può apparire in parentesi per indicare il distretto di appartenenza (es. "Tribunale di Reggio Calabria (Catanzaro)" è **corretto**: Reggio Calabria appartiene al distretto Catanzaro).

  **Valore inviato dai form** (differenze per sezione app):
  - `polisWeb.html`: campo hidden invia `u.codice` (es. `0580010`)
  - `fascicoli/form.html`, `form_appuntamento.html`, `clienti/form.html`: `<select>` invia `u.nome` (es. `"Tribunale di Milano"`)

  **Verifica visiva dopo ogni modifica al bundle** — pannello admin in `polisWeb.html`:
  - Il badge "N uffici · aggiornati" (verde) è visibile solo agli admin.
  - Cliccandolo si apre il pannello con il **breakdown per tipo** (Tribunali, Procure, G.d.P., ecc.).
  - Dopo ogni modifica al bundle, cliccare **"Ricarica bundle"** per rigenerare la cache dal codice aggiornato (senza attendere TTL né fonti remote).
  - Valori attesi a bundle v1.0.2: 648 uffici totali — GDP: 155, TRIBUNALE: 146, PROCURA: 147, CORTE_APPELLO: 23, PROCURA_GENERALE: 23, SORVEGLIANZA: 26, TM: 26, TAR: 31, CORTE_ASSISE: 69.
  - Se i numeri non corrispondono dopo "Ricarica bundle", il deploy non ha incluso le modifiche a `pct/uffici_giudiziari.py`.

  **Auto-upgrade automatico** (`GestoreUfficiGiudiziari.carica()`):
  - Se la cache su disco ha **meno uffici del bundle interno**, `carica()` rigenera automaticamente la cache dal bundle al primo accesso dopo il redeploy.
  - Questo risolve il caso in cui Railway (o qualsiasi server) abbia una cache salvata da sorgente remota (PST/URL esterno) con meno uffici di quanti ne ha il bundle aggiornato.
  - Il log mostra: `Auto-upgrade cache uffici: N (cache) < M (bundle) → rigenero`
  - **Non modificare questa logica**: è la salvaguardia principale contro dati incompleti su produzione.

- **Mobile — Modal visualizzatore documenti** (`fascicoli/dettaglio.html`, `#modalVisualizzatore`):
  - Il modal deve avere **sempre** `modal-fullscreen-sm-down` per occupare tutto lo schermo su mobile.
  - Il `modal-content` deve avere `display:flex;flex-direction:column` affinché il body con l'iframe possa espandersi con `flex:1`.
  - Struttura corretta:
    ```html
    <div class="modal-dialog modal-xl modal-fullscreen-sm-down" style="max-width:95vw;height:92vh;margin:.5rem auto">
      <div class="modal-content" style="height:100%;display:flex;flex-direction:column">
        <div class="modal-header py-2">…</div>
        <div class="modal-body p-0" style="flex:1 1 auto;overflow:hidden;display:flex;flex-direction:column">
          <iframe … style="width:100%;flex:1;border:0;min-height:0"></iframe>
        </div>
      </div>
    </div>
    ```
  - **Senza `display:flex` sul `modal-content`**: il `flex:1` sul modal-body non funziona → l'iframe collassa a altezza 0 → maschera apparentemente vuota/troppo piccola.

- **Mobile — Modal Bootstrap: z-index backdrop e posizionamento**:
  - I modal devono essere **figli diretti del `<body>`**, non annidati dentro `#main` o altri container con `position:relative/absolute` → altrimenti il backdrop Bootstrap non copre correttamente tutta la pagina e il modal può apparire parzialmente nascosto o in posizione errata.
  - Regola: tutti i `<div class="modal fade" …>` vanno inseriti **in fondo al file HTML, fuori da qualsiasi wrapper**.

- **Mobile — footer navbar fisso e scroll**:
  - Il footer di navigazione mobile (`base.html`) usa `position:fixed;bottom:0` con `z-index:1030`.
  - Il contenuto principale `#main` deve avere `padding-bottom` sufficiente (≥ 70px) per non essere coperto dal footer.
  - Su iOS Safari il `100vh` include la barra URL → usare `min-height: -webkit-fill-available` come fallback per i modal fullscreen.

- **Mobile — Dropdown tagliati da `overflow:hidden` su `#main`**:
  - Su mobile `#main` è `position:fixed` con `overflow-y:auto; overflow-x:hidden` (vedi `app.css` riga ~614). Qualsiasi `position:absolute` dentro `#main` — inclusi i Bootstrap dropdown-menu — viene **clippato** ai bordi del container e risulta invisibile o troncato.
  - **Sintomo**: cliccando un dropdown (es. "Esporta") appare un rettangolo bianco vuoto invece dei voci del menu.
  - **Fix obbligatorio**: inizializzare i dropdown via JavaScript con `popperConfig: { strategy: 'fixed' }` — Popper usa `position:fixed` e aggira il clipping. Il fix globale è già in `base.html` (script alla fine del `<body>`):
    ```javascript
    new bootstrap.Dropdown(el, { popperConfig: { strategy: 'fixed' } });
    ```
  - **Regola**: ogni volta che si aggiunge un nuovo dropdown dentro `#main`, verificare che venga inizializzato dallo script globale (`[data-bs-toggle="dropdown"]` auto-rilevato). Non serve azione manuale se l'attributo standard è presente.
  - **Non usare** `data-bs-display="static"` come workaround: disabilita il posizionamento dinamico di Popper e il menu appare sempre in posizione fissa rispetto al pulsante, ignorando i bordi del viewport.

- **Mobile — pulsanti azione documento** (`fascicoli/dettaglio.html`, sezione atti):
  - I pulsanti (Visualizza, Scarica, Firma, Elimina) nelle card documento su mobile erano non cliccabili a causa di un overlay trasparente generato da un elemento parent con `pointer-events` errato.
  - Verificare sempre che i bottoni nelle card abbiano `position:relative;z-index` superiore a eventuali pseudo-elementi `::after` del container.
  - I titoli delle sezioni (es. "Atti") non devono sovrapporsi ai pulsanti: usare `d-flex align-items-center justify-content-between` per header sezione + pulsante "Aggiungi".

## MetaHarness workflow — Regola di perimetro

- MetaHarness e' ammesso solo come strumento esterno di sviluppo per ottimizzare harness, istruzioni Codex, script di test, script di validazione e documentazione operativa.
- MetaHarness non e' una dipendenza runtime di IUSENTRA e non va aggiunto a `requirements.txt`, `requirements/base.txt`, `requirements/dev.txt`, `pyproject.toml` o `setup.py` senza autorizzazione esplicita.
- Per questo repository, i run MetaHarness non devono modificare direttamente codice applicativo core (`pct/`, `web/`, `lex/`), storage, migrazioni, portali telematici, Lex AI o UI prodotto senza review manuale.
- Ogni scaffold o run con provider reali deve essere autorizzato nel task corrente.
- I risultati MetaHarness vanno trattati come proposte: prima review del diff, poi test pertinenti, poi eventuale integrazione.
- E' vietato usare MetaHarness per indebolire CI, coverage, quality gates, workflow di sicurezza o regole gia' presenti in questo `AGENTS.md`.

## Autoresearch-lite workflow — Regola di sicurezza

- Autoresearch-lite e' solo un metodo di lavoro ispirato a `karpathy/autoresearch`, adattato a IUSENTRA.
- Non e' consentito installare `karpathy/autoresearch`, aggiungere dipendenze ML/GPU o modificare dipendenze runtime per questo workflow.
- Sono vietati loop infiniti, esperimenti notturni non presidiati, branch extra, reset distruttivi e run autonomi senza nuovo task esplicito.
- Ogni esperimento deve avere obiettivo, baseline, file modificabili, file vietati, comandi di verifica e criteri `keep/discard`.
- Ogni risultato va classificato come `keep`, `discard`, `crash`, `scope-violation` o `needs-review`.
- Su IUSENTRA il ciclo sperimentale deve migliorare la qualita' di Codex senza indebolire storage, CI, coverage, portali telematici, Lex AI, multi-tenant, sicurezza o audit.

## Open Design support — Regola UI/UX

- Open Design support e' ammesso solo come supporto esterno per migliorare design system, skill UI/UX, prototipi e prompt grafici di Codex.
- Non e' consentito installare `nexu-io/open-design` dentro IUSENTRA, aggiungere dipendenze Node/pnpm al gestionale o modificare package manager per questo workflow senza autorizzazione esplicita.
- Le risorse ufficiali per Codex vivono in `tools/open-design-support/`.
- Per ogni task UI/UX, Codex deve leggere `tools/open-design-support/IUSENTRA_DESIGN.md`, `tools/open-design-support/IUSENTRA_UI_RULES.md` e la skill pertinente prima di modificare template, React, CSS o SCSS.
- Ogni modifica UI deve rispettare lingua italiana, date italiane, responsive desktop/tablet/mobile, stati vuoti, loading, errore, conferma, accessibilita' e coerenza con l'architettura esistente.
- Open Design support non autorizza modifiche libere a `web/`, `web/templates/`, `web/static/`, `web/blueprints/`, `/app-v2`, route Flask, API o storage.
- Ogni prototipo o artifact grafico va trattato come proposta: prima review, poi adattamento a Jinja/React/CSS, poi test o smoke pertinenti.

## Codex quality gate — Regola pre-report

- Per task di tooling, MetaHarness, autoresearch-lite o Open Design support, prima del report finale eseguire:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

- Per task UI/UX di supporto, eseguire:

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode ui-support
```

- Se il quality gate fallisce, non dichiarare il task completato: correggere la violazione oppure segnalarla chiaramente nel report finale.
- Il quality gate non sostituisce i test applicativi quando si modifica codice prodotto.
