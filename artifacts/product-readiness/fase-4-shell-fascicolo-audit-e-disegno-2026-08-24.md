# Fase 4 — Shell, design system e workspace del Fascicolo

**Stato:** implementazione in corso; nessuna accettazione reale finale è ancora dichiarata.

**Commit di partenza:** `4a4fc546bc3863427ca3d9aba640536e52b6cf9e`
**Ambiente osservato:** copia Docker reale locale `http://127.0.0.1:8080`, 24/08/2026, Europe/Rome.
**Mandato di fase:** rendere il fascicolo un workspace rapido, modulare e non duplicativo, mantenendo le route, le API, i dati SQL, i permessi, gli audit e ogni flusso operativo già funzionante.

## 1. Vincoli non negoziabili

- Il fascicolo resta il contesto unico di documenti, scadenze, comunicazioni, depositi, economia, fonti, audit e decisioni.
- Questa fase è una migrazione di shell e componenti React: non modifica significato dei dati, regole procedurali, ownership tenant, contratti API o fonti di verità SQL.
- Le API già usate da `fascicoliData.ts` restano l’unico canale dati. Nessun JSON operativo, mock permanente o fallback legacy viene introdotto.
- Ogni azione con effetto operativo conserva permesso, CSRF, audit, idempotenza e messaggio di errore esistenti.
- La distinzione tra dato certo, proposta e revisione rimane invariata. In particolare, la catalogazione documentale prudenziale non potrà essere semplificata in una classificazione silenziosa.

## 2. Evidenze di baseline

### Codice e bundle

| Indicatore | Evidenza corrente | Valutazione |
| --- | --- | --- |
| `FascicoliPage.tsx` | 500.507 byte, 294 dichiarazioni `function`, 261 occorrenze di hook React, 28 chiamate `fetch` | Superficie troppo accentrata per evolvere senza rischio. |
| `FascicoliPage.css` | 264.308 byte, 116 colori hard-coded distinti, 33 gradienti lineari, 68 blocchi responsive | Regole stratificate e difficile verifica uniforme degli stati. |
| Chunk React Fascicoli | `FascicoliPage-B-5CRpj6.js`, 319.640 byte | Sotto il limite tecnico di 500 kB, ma troppo ampio per il primo caricamento del workspace. |
| CSS pubblicato | `FascicoliPage-CxXXc8BW.css`, 261.527 byte | Da separare per feature, senza cambiare le classi del deposito già verificate. |
| Shell `App.tsx` | 93.906 byte | Il lazy loading della pagina esiste; la pagina caricata contiene però lista, dettaglio, deposito e sezioni non richieste insieme. |

### Prova locale di partenza

- La lista Fascicoli ha caricato dieci fascicoli reali del tenant in sessione, filtri, ordinamento, viste e azioni contestuali.
- È stato eseguito un click materiale sul fascicolo `DD242366`: dalla lista si è aperto il dettaglio reale `Fascicolo da sincronizzare (prova PST)` senza uscire da IUSENTRA.
- Il dettaglio conserva intestazione, RG, cliente, ufficio, stato, sezioni, quadro, presidi, documenti e catalogazione collegati a dati reali.
- Ai viewport di audit 1366×768, 1024×768 e 390×844 non è stato rilevato overflow orizzontale. Questo è un controllo tecnico di baseline, non sostituisce la prova materiale finale desktop, tablet e mobile richiesta alla chiusura della fase.

## 3. Audit tecnico del workspace esistente

| Dimensione | Punteggio | Evidenza e conseguenza |
| --- | ---: | --- |
| Accessibilità | 2/4 | Etichette ARIA e numerosi focus visibili sono presenti, ma molti comandi topbar misurano 40 px e select/input nativi 23–25 px. I target touch e il focus tastiera devono diventare uniformemente verificabili a 44 px. |
| Prestazioni | 2/4 | Caricamento lazy della route presente, ma un unico chunk da 319.640 byte include una superficie con 294 funzioni e CSS da 261.527 byte. Occorre separare lista, dettaglio e strumenti pesanti. |
| Tema e design system | 1/4 | I token `--iu-*` esistono, ma 116 colori diretti e 33 gradienti impediscono una semantica coerente e rendono oneroso il contrasto. |
| Responsive | 3/4 | Nessun overflow ai tre viewport tecnici; il menu laterale collassa correttamente. Restano target sotto soglia e molte eccezioni CSS da consolidare. |
| Anti-pattern | 1/4 | Il dettaglio presenta due quadri intelligenti e più gruppi di card/indicatori che descrivono lo stesso fascicolo. Alcune superfici usano gradienti lineari e card ripetitive non necessarie al lavoro. |
| **Totale** | **9/20** | **Ristrutturazione necessaria prima di promuovere il workspace come shell di riferimento.** |

### Osservazioni prioritarie

1. **P1 — Doppia gerarchia decisionale nel dettaglio.** `Quadro intelligente AI`, `Quadro intelligente`, `Presidio operativo` e la striscia di indicatori espongono in parte le stesse informazioni. L’avvocato deve capire subito una sola prossima azione sicura, non confrontare quattro riepiloghi.
2. **P1 — Monolite React ad alto rischio di regressione.** Lista, creazione, dettaglio, documenti, deposito, firma, relata, economia, audit e CSS vivono prevalentemente nella medesima unità. Un fix locale può modificare involontariamente un flusso sensibile.
3. **P1 — Target e campi sotto 44 px.** Pulsanti icona, controlli della topbar e campi nativi non rispettano con continuità il target tattile e rendono più fragile la navigazione da tastiera e tablet.
4. **P2 — Token incompleti.** Le varianti di stato usano valori diretti anziché un vocabolario condiviso. La verifica del contrasto e la correzione di un tema richiedono ricerca manuale su molte regole.
5. **P2 — Caricamento non proporzionato al compito.** Una ricerca nella lista non dovrebbe richiedere codice di deposito, firma, preview e pannelli di dettaglio non ancora aperti.

### Elementi positivi da preservare

- Navigazione React, endpoint JSON e controllo tenant già reali.
- Dati italiani, importi in euro e collegamenti al fascicolo reale.
- Cache e deduplicazione delle richieste della lista già presenti.
- Sezioni lazy esistenti per deposito e documenti d’ufficio.
- Nessun overflow orizzontale rilevato nella baseline tecnica.

## 4. Disegno confermabile della Fase 4

**Scena d’uso:** un avvocato consulta un fascicolo su notebook in studio, tra un atto, una PEC e una scadenza. Ha pochi secondi per capire cosa fare, perché farlo e quali prove lo sostengono. La superficie resta quindi chiara, luminosa, compatta e istituzionale, senza ornamenti o metriche decorative.

### Struttura del workspace

1. **Intestazione decisionale unica.** Identità del fascicolo, RG, parti, stato, ufficio e azione primaria restano nello stesso blocco. Le azioni secondarie entrano nel menu contestuale, con etichetta e motivo di eventuale blocco.
2. **Una sola area “Prossima azione sicura”.** Riunisce stato procedurale, presidio prioritario, fonte/evidenza, scadenza e comando consentito. Sostituisce la duplicazione dei due quadri senza eliminare alcuna informazione sottostante.
3. **Sezioni per responsabilità, non per widget.** Documenti, attività, comunicazioni, scadenze, economia, audit, soggetti e gestione rimangono ancore interne al fascicolo e vengono caricate soltanto quando richieste.
4. **Lista fascicoli come strumento rapido.** Filtri, tabella, vista compatta e salvati restano; il bundle della lista non carica deposito, firma, relata o preview documentale.
5. **Stati semantici, non decorativi.** Verde, ambra, rosso e azzurro indicano esito, presidio, blocco e informazione. Niente gradienti testuali, card annidate o pannelli duplicati.

### Confini di implementazione

| Sottofase | Intervento | Contratto preservato |
| --- | --- | --- |
| 4A — Confini React | Introdurre moduli `features/fascicoli/list`, `detail`, `shared` e adattatori di presentazione, inizialmente senza cambi visivi. | Route `/fascicoli*`, `fascicoliData.ts`, API JSON e hash delle sezioni. |
| 4B — Lista veloce | Spostare filtri, preferenze, tabella, paginazione e viste in chunk della lista. | Ricerca, filtri, cache, esportazione, RBAC, tenant e salvataggi preferenze. |
| 4C — Dettaglio decisionale | Estrarre header, barra sezioni, prossima azione e sezioni lazy; unificare i due quadri solo quando il mapping dati è verificato. | RG, parti, azioni, fonti, documenti, audit e tutte le ancore esistenti. |
| 4D — Token e accessibilità | Sostituire gradualmente i colori diretti toccati con token semantici; assicurare target 44 px, focus visibile, hover, loading e disabled. | Colori di rischio, testo italiano, contrasto e funzionamento da tastiera. |
| 4E — Budget e regressione | Rendere misurabile il caricamento per route e isolare strumenti pesanti con `lazy`. | Primo caricamento della lista e del dettaglio non peggiore della baseline. |

## 5. Contratti dati, API e sicurezza

La Fase 4 non richiede una nuova tabella né una modifica dei resolver documentali. Ogni componente usa i repository e le API esistenti:

- `GET /api/v1/ui/fascicoli` e dettaglio collegato, tramite `fascicoliData.ts`;
- catalogazione documentale SQL/API già governata, soltanto nel dettaglio del fascicolo selezionato;
- controlli tenant, RBAC, CSRF, audit e idempotenza già presenti nelle azioni;
- Local Signer, PEC, deposito, notifica e download non vengono modificati nella sottofase di shell senza test specifico e prova materiale del flusso coinvolto.

Qualunque necessità emersa durante l’estrazione di modificare dati, schema o API apre un ADR e il doppio controllo SQLite/PostgreSQL prima del relativo codice.

## 6. Budget misurabili e criteri anti-regressione

| Misura | Baseline | Obiettivo della fase |
| --- | ---: | --- |
| Chunk Fascicoli attuale | 319.640 byte | La lista iniziale e il dettaglio iniziale non devono caricare strumenti di deposito/firma/preview; il carico iniziale della singola route deve ridursi o restare entro il 105% della baseline con motivazione misurata. |
| Asset CSS Fascicoli | 261.527 byte | CSS per feature e tokenizzati; nessun asset oltre 500.000 byte, nessuna duplicazione di regole tra lista e dettaglio. |
| Overflow orizzontale | assente ai tre viewport tecnici | Assente a 1366×768, 1024×768 e 390×844 nella prova reale conclusiva. |
| Target interattivi | diversi controlli 40 px o meno | 44×44 px per comandi touch e campi operativi, salvo controlli nativi con area etichetta equivalente e comprovata. |
| Azioni/route | funzionanti | Stessi href, payload, permessi, feedback, audit e risultati osservabili prima e dopo l’estrazione. |

## 7. Test e prova di accettazione previsti

1. Test di contratto per route, ancore, azioni, lazy boundary e assenza di import involontari di deposito/firma nella lista.
2. Typecheck, test React, build Vite, budget asset, test API/RBAC/tenant già esistenti e nuovi test mirati di presentazione.
3. Verifica SQLite/PostgreSQL soltanto se un requisito costringe una modifica persistente.
4. Docker locale aggiornato su `127.0.0.1:8080` e prova materiale con click reali: lista, ricerca, filtri, apertura fascicolo, prossima azione, documenti/catalogo, attività, audit, deposito non invasivo e lettore interno.
5. Scroll completo, hover e focus da tastiera sui controlli principali, più responsive desktop, tablet e mobile effettivi.
6. Benchmark prima/dopo e verifica che nessuna chiamata API aggiuntiva parta fuori dalla sezione richiesta.
7. Solo dopo tutti i PASS: documentazione, commit, push dei branch gemelli, Docker locale, prova reale, deploy Hetzner, controllo del solo `iusentra-app`, health HTTPS e pulizia cache.

## 8. Stato formale

L’audit di partenza è completo. La Fase 4 **non è ancora completata**: sono state avviate mutazioni mirate al workspace e ai presìdi, ma manca ancora la verifica completa sulla copia reale locale, con click materiali, prima di qualunque dichiarazione positiva.

## 9. Integrazione richiesta: fascicolo, catalogo e attività

L’audit ulteriore richiesto sul fascicolo `DD242366` ha evidenziato tre difetti di prodotto che non possono essere coperti da etichette o stati generici.

1. **Catalogazione.** Il catalogo SQL e la pipeline di estrazione del contenuto esistono già, ma la pagina di dettaglio può visualizzare una tipologia ricavata da nome file o metadati del portale come se fosse classificazione del contenuto. Questo è improprio. La visualizzazione dovrà distinguere senza ambiguità: classificazione dal contenuto indicizzato, metadati dichiarati dal portale, classificazione manuale confermata dall’avvocato e documento ancora da acquisire/indicizzare. Il nome del file rimane solo un ausilio di riconoscimento, mai prova del contenuto.
2. **Modifica governata.** L’avvocato deve poter correggere la classificazione nel catalogo stesso. La correzione deve aggiornare l’assegnazione SQL tenant-aware, registrare un audit con i soli campi modificati, mantenere evidenze/candidati e funzionare con SQLite e PostgreSQL. Non è ammessa una correzione soltanto grafica o JSON.
3. **Attività processuali.** Le righe “Acquisizione file ufficiali” da PolisWeb/PST sono eventi tecnici di consultazione/sincronizzazione, non attività processuali. Devono uscire dalla timeline processuale, comparire in una sezione tecnica separata e non produrre stati fittizi “In attesa”. Udienze e iscrizioni a ruolo importate restano invece attività processuali, marcate come registrate/importate dal portale.

Per tutti i documenti, indipendentemente dalla sezione, sono necessari comandi espressi con icona ed etichetta: visualizzazione interna, download, modifica metadati, modifica catalogazione, firma quando applicabile, attestazione, conversione PDF/A, eliminazione e acquisizione dal PST quando il contenuto non è locale. Ogni comando deve mantenere i controlli tenant, permesso, CSRF, audit e feedback di esito già previsti dalle API reali.

La prova conclusiva dovrà includere un documento locale, un documento da acquisire dal PST, una correzione catalogo SQL, un evento tecnico separato dalla timeline, una udienza/importazione processuale, stato presìdio, output di scadenze/audit e tutti i controlli interattivi della pagina a desktop, tablet e mobile.

## 10. Consolidamento del Presidio del fascicolo

L’audit delle superfici attive ha trovato sovrapposizioni fra `Regia Operativa`, `Percorso cliente-incasso`, `Quadro fascicolo`, `Contesto economico`, `Sentenze: controllo economico`, `Presidio operativo` e `Relata notifica`. Le sezioni non sono equivalenti nel dominio, ma la loro presentazione come pannelli principali autonomi duplica conteggi, fa ripetere il contesto e rende difficile capire quale controllo agisca davvero.

Il disegno corretto è un solo **Presidio del fascicolo** nella pagina principale. Esso legge una volta le fonti governate e presenta, per priorità e senza ripetizioni:

1. prossima azione processuale o tecnica, con origine, motivo ed esito osservabile;
2. documenti e catalogazione, inclusa acquisizione, lettura contenuto, firma e deposito;
3. udienze, scadenze e attività processuali; gli eventi tecnici restano separati;
4. comunicazioni, relata e prova notifica come un unico presidio di notifica;
5. incarico, valore, parcelle, tempi e controllo economico di provvedimenti come un unico presidio economico;
6. conformità, audit e duplicati, ciascuno con il proprio resolver e una sola attestazione verificabile.

Le attuali sezioni specialistiche non vengono eliminate nel dominio né rese fittizie: diventano destinazioni di approfondimento dal Presidio del fascicolo, con la stessa fonte dati e gli stessi endpoint. La route `/quadro` resta una vista sintetica e non una terza dashboard: rimanderà al Presidio del fascicolo per azioni e non replicherà più workflow, conteggi o controlli. L’accettazione verificherà che ogni card mostri un solo significato, un solo contatore, una sola azione primaria e il relativo risultato reale.

## 11. Audit di tutte le sezioni del dettaglio

| Superficie attuale | Fonte/obiettivo | Decisione |
| --- | --- | --- |
| Cockpit iniziale, Regia Operativa, Quadro fascicolo | stato, documenti, scadenze, economia, controlli | **Accorpare** nel Presidio del fascicolo. Il Quadro resta soltanto una sintesi stampabile/navigabile, senza comandi o conteggi concorrenti. |
| Presidio operativo, presidio documenti, Conformità | resolver PEC/documenti/relata/economia/doppioni e qualità anagrafica | **Accorpare la presentazione**, mantenendo resolver distinti, esiti, fonti e azioni in una lista prioritaria dei controlli del Presidio. |
| Relata notifica, Comunicazioni/Cancelleria | PEC, ricevute, relata, prova e deposito prova | **Accorpare** nel presidio “Comunicazioni, PEC e notifica”; la relata resta un approfondimento, non una dashboard duplicata. |
| Contesto economico, Sentenze: controllo economico, Percorso cliente-incasso, blocco economico della Regia | preventivi, incarichi, parcelle, incassi, tempi, liquidazioni e spese | **Accorpare** nel presidio “Incarico ed economia”. Le sentenze conservano il resolver dedicato e diventano un controllo/azione di tale presidio. |
| Documenti, Lex, catalogazione, selezione deposito | file, testo indicizzato, assegnazione SQL e requisiti | **Accorpare** nel workspace “Documenti e atti”, con sotto-stati: acquisisci, leggi, correggi catalogo, firma, deposita. Nessun tipo da filename verrà venduto come lettura. |
| Attività processuali, Avanzamento pratica, Eventi tecnici | atti/udienze, transizioni di stato, sincronizzazioni | **Riorganizzare** in “Cronologia della pratica”: processo, stato e tecnica restano filtri/viste separate. Non sono lo stesso dato e non vanno confusi. |
| Profilo, Cliente, Soggetti e parti | dati procedimento, assistito, ruoli e recapiti | **Raggruppare navigazione e presentazione** in “Anagrafica della pratica”, mantenendo modifiche e permessi distinti. |
| Udienze/scadenze, Agenda | termini e appuntamenti | **Mantenere unite** come agenda del fascicolo; il presidio documentale genera soltanto proposte verificabili, non falsi termini. |
| Audit, Archivio/ZIP | evidenze e conservazione | **Mantenere separati**: l’audit è prova; l’archivio è conservazione. Il Presidio mostra solo il loro stato e l’azione disponibile. |
| Uffici competenti, CTU/perizie, Servizi telematici | consultazione, soggetti tecnici, canali esterni | **Mantenere come strumenti verticali**, raggiungibili dal Presidio solo quando il tipo/materia del fascicolo li rende pertinenti. |

Le sezioni che restano distinte non saranno replicate nella barra iniziale: il Presidio mostrerà una sola azione primaria e un collegamento di approfondimento, così da preservare velocità, orientamento e audit del singolo resolver.

## 12. Evidenza parziale — azioni della lista fascicoli

Il 24/08/2026 è stata rilevata nella copia reale una regressione di presentazione: dopo aver reso esplicite le etichette delle azioni di riga, la regola generica delle icone le costringeva ancora in 34 px e ne tagliava il testo. La correzione è limitata a .iu-fas-title-actions: ogni comando conserva il proprio collegamento o POST esistente, ma usa larghezza naturale, area minima di 44 px, testo non spezzato e ritorno a capo nel contenitore della cella.

- Guardrail eseguiti: test React mirati su etichette/target e selezione documenti, pnpm --dir frontend typecheck, git diff --check.
- Prova materiale eseguita su http://127.0.0.1:8080/fascicoli: dopo il caricamento dei dieci fascicoli reali, risultano leggibili Apri, Modifica, Deposito, Notifica, PDF, Elimina; hover su Deposito conserva contrasto ed etichetta; il click materiale su Apri del fascicolo sincronizzato ha aperto il dettaglio reale collegato.
- Nessuna azione distruttiva, deposito, notifica o modifica dati è stata avviata durante il collaudo.

Questa è un'evidenza parziale della Fase 4 e non sostituisce il collaudo conclusivo desktop, tablet e mobile, né autorizza la chiusura della fase.

## 13. Build e budget misurati

La build Vite del 24/08/2026 ha superato typecheck e budget nativo. Il primo tentativo ha rilevato un blocco del file indice causato dal container locale in esecuzione; fermato esclusivamente il servizio app, senza volumi o dati, la build è stata ripetuta con successo e il servizio è stato ricreato healthy.

| Asset | Misura build | Limite Fase 4 | Esito |
| --- | ---: | ---: | --- |
| FascicoliPage JavaScript | 330.080 byte | 335.622 byte | PASS |
| FascicoliPage CSS | 274.466 byte | 274.603 byte | PASS |
| FascicoloDepositoPage lazy | 170.406 byte | separato dalla lista | PASS |

La suite frontend completa è passata. La suite Python mirata a regia, presidio, catalogazione, schema/API e PolisWeb è passata integralmente dopo l'allineamento del guardrail scadTermini al contratto primario del connettore.

## 14. Collaudo locale ulteriore — 24/08/2026

La copia Docker reale `http://127.0.0.1:8080` è stata ricostruita due volte
durante questa tranche, senza toccare volumi o dati applicativi; al termine il
solo container applicativo locale `iusentra-app` è healthy e `/api/pronto`
risponde `ok` in fuso `Europe/Rome`.

- Nel fascicolo reale `DC5BF1DB` sono stati aperti materialmente **Prepara
  deposito telematico** e **Prepara notifica**. Entrambi mostrano l'elenco dei
  documenti reali, il comando esplicito `Visualizza` e l'azione primaria senza
  selezione. Nessun deposito, notifica, firma, modifica o invio è stato
  effettuato.
- Dal selettore deposito è stato aperto `decretoLiquidazioneCTU.pdf` nel
  lettore interno. Il PDF è stato realmente renderizzato; il click su `Scarica`
  ha prodotto il messaggio osservabile `Download avviato:
  decretoLiquidazioneCTU.pdf.` senza errore di fetch o uscita da IUSENTRA.
- Dopo il rebuild, la barra delle sezioni del fascicolo è stata verificata a
  desktop: tutte le dieci sezioni restano leggibili su due righe, senza la
  barra orizzontale visibile e senza troncare `Audit`, `Controlli`, `Soggetti`
  o `Servizi telematici`. Il focus visibile è stato aggiunto alle ancore.
- Il comando PagoPA è stato corretto da immagine raster soggetta a mancata resa
  a icona vettoriale `Landmark`; nel browser reale sono visibili etichetta,
  icona e stato hover leggibili.
- L'audit di igiene ha rimosso due file sperimentali non importati
  (`FascicoloDecisionWorkspace`): non avevano chiamanti, non esponevano
  funzionalità e avrebbero duplicato Quadro, compilatore e Lex contro il
  disegno del Presidio unico.
- Sono passati: contratti frontend completi, typecheck TypeScript, test React,
  tutti i test mirati del catalogo/pipeline/schema/API, test del presidio,
  test PolisWeb sul parametro `scadTermini` e `git diff --check`.

## 15. Collaudo responsive e lettore — 24/08/2026

Il controllo viewport nativo della **stessa scheda browser reale IUSENTRA** ha
consentito il collaudo tablet e mobile senza browser temporanei né mock. Lo
stato complessivo della Fase 4 resta in implementazione fino ai gate, al commit
e al deploy previsti.

- A **768×1024** il fascicolo `DC5BF1DB` mantiene intestazione, comandi, barra
  sezioni e Presidio leggibili; il click sul Presidio ha caricato le card reali
  di priorità e conformità senza tagli o sovrapposizioni.
- A **390×844** sono stati controllati dall'alto al fondo intestazione,
  Presidio, controllo economico, validazione, checklist, Documenti e atti,
  catalogazione, cronologia, servizi e navigazione mobile. Le card
  `Spese distratte`, `Contributo unificato`, `Validazione` e `Documenti
  richiesti` restano leggibili e con una sola azione per riga.
- Nella catalogazione documentale ogni anteprima ora è **icona + etichetta
  `Visualizza`**. Il click materiale su `attoACQ.pdf.p7m` ha aperto il lettore
  interno e renderizzato il PDF reale, mantenendo i comandi `Scarica`,
  `Chiudi`, zoom e adattamento nello stesso software.
- Il click su `Scarica` ha ricevuto il file binario nella sessione autenticata
  e ha mostrato `Download avviato: attoACQ.pdf.p7m.`. Il codice rifiuta
  risposte HTML, file vuoti e stati HTTP non riusciti, quindi non può più
  presentare quell'esito se riceve la shell React al posto del documento.
- Non sono stati confermati cataloghi, caricati file, firmati documenti,
  preparati depositi, inviate notifiche o modificati dati durante il collaudo.

Guardrail aggiunto:
`test_catalogazione_documentale_espone_visualizza_con_etichetta_esplicita` in
`tests/test_regia_ui_react.py`. Sono passati il test mirato (24 casi), la
suite frontend di contratti/design-system/coverage e il build TypeScript
integrato in Vite.
