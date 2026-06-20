# Specifica permanente - PEC presidiate

Questa specifica deve essere riletta insieme a tutti gli `AGENTS.md` applicabili prima di modificare il flusso PEC. È la fonte persistente dell'incarico per le successive compattazioni di contesto.

## Obiettivo

Trasformare le PEC giudiziarie in eventi processuali correlati, aggiornabili e idempotenti. Le ricevute tecniche dello stesso deposito aggiornano una sola scheda nel fascicolo; non generano notifiche grezze duplicate. Cliente e parte processuale estratti dagli allegati XML devono propagarsi a profilo processuale, fascicolo, agenda, scadenziario e avvisi operativi.

## Acquisizione e conservazione probatoria

- Conservare il MIME originale, `daticert.xml`/`postacert.eml`, tutti gli allegati, hash e metadati di acquisizione.
- Registrare un audit append-only delle decisioni di parsing, correlazione e aggiornamento.
- Il ricalcolo deve essere idempotente e non deve distruggere la cronologia già acquisita.

## Parsing sicuro di `EsitoAtto.xml`

Il parser deve essere namespace-insensitive e non deve risolvere DTD, entità esterne o risorse di rete. Estrarre almeno:

- `IdMsgMitt`;
- `IdMsgPdA/IdMsg`;
- `DatiEsito/MsgEsito/NumeroRuolo`;
- `CodiceEsito`;
- `DescrizioneEsito`;
- data, ora e fuso di `Tempo`;
- impronta e relativo algoritmo/codifica;
- `IDBUSTA` dalla descrizione;
- `RefID`, codice pratica e oggetto dell'atto;
- nome del file depositato.

## Correlazione del deposito

Usare, in ordine, chiavi forti e poi fallback controllati:

1. `IDBUSTA`, con controllo di ufficio/registro quando disponibile;
2. `RefID`;
3. Message-ID originale;
4. impronta del file;
5. fallback composto da RG, ufficio, tipo/oggetto dell'atto, parti e finestra temporale.

Non fondere mai depositi distinti sul solo RG. Quando più fascicoli o depositi restano compatibili, non scegliere silenziosamente: creare un presidio di correlazione ambigua con candidati, punteggi e motivazione.

## Un solo deposito visibile, cronologia completa

Le PEC con oggetto tecnico `ACCETTAZIONE DEPOSITO TELEMATICO` e `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO` devono aggiornare una singola scheda deposito nel fascicolo. La scheda usa come oggetto visibile il documento/atto depositato e mantiene la cronologia di tutti gli esiti.

Caso obbligatorio:

- `IDBUSTA: 35508878`;
- RG `1733/2026`;
- atto `Ricorso Punturiero (originale notificato).pdf`;
- primo esito `CodiceEsito=-1`: non conformità, attesa conferma cancelleria, deposito da non ripetere;
- secondo esito `CodiceEsito=2`: accettazione manuale avvenuta con successo.

Risultato atteso: un solo deposito, due eventi cronologici, stato finale "accettato manualmente". L'esito `-1` non deve suggerire un nuovo deposito quando la descrizione afferma che non è necessario ripeterlo.

## Cliente e parte processuale

Dal messaggio e dagli allegati, in particolare `Comunicazione.xml`, estrarre e mantenere distinti:

- nome e cognome/denominazione cliente;
- soggetto o parte processuale;
- eventuale ruolo della parte;
- identificativi utili alla correlazione.

Propagare questi campi nelle entità, DTO/serializer/API e componenti UI di:

- profilo processuale;
- fascicolo;
- scheda deposito;
- agenda;
- scadenziario;
- avvisi operativi, topbar e push mobile.

Quando il dato manca o è ambiguo, mostrarlo come da verificare.

## Parsing di `Comunicazione.xml` e provvedimenti

Estrarre almeno ufficio, sezione, giudice, RG, evento/oggetto, cliente, soggetto/parte, data e ora dell'udienza, modalità, eventuale link audiovisivo, termini e allegati richiamati.

Esempio da gestire:

- profilo: provvedimento/sentenza da leggere e notificare o presidiare;
- giudice: `TOSONI CLAUDIA`;
- RG: `1754/2026`;
- evento: `SENTENZA EX ART. 429, I comma CPC`;
- udienza da remoto;
- allegato: `8960334s.pdf.zip`.

Il link remoto va cercato prima nei campi XML, poi nel testo del messaggio e nel testo nativo dei PDF/allegati. L'OCR è solo fallback. Se il link non viene trovato, creare un presidio esplicito che indichi l'allegato da verificare; non inventare il collegamento.

## Agenda e scadenziario

- Creare o aggiornare udienze, fissazioni e scadenze con upsert idempotente.
- Usare una chiave evento stabile basata su fascicolo, tipo evento, data/ora, fonte e identificatore comunicazione.
- Una comunicazione successiva aggiorna l'evento esistente e conserva la cronologia delle versioni.
- Riportare gli stessi campi del profilo processuale: ufficio, giudice, RG, evento, cliente, parte/soggetto, modalità, link, fonte e stato di verifica.
- Qualunque termine calcolato resta bozza da confermare finché non è verificato sul documento fonte, salvo regole già presidiate e testate dal gestionale.
- Lo scadenziario deve contenere solo attività realmente operative per l'avvocato: udienze, termini, notifiche, lettura di provvedimenti, produzione di atti o verifica puntuale di allegati. Ricevute tecniche, protocolli, accettazioni e conferme deposito restano nel fascicolo o nel presidio PEC e non devono creare scadenze generiche.

## Fascicoli e prossima scadenza

La lista React dei fascicoli deve mostrare `Prossima scad.` quando esiste una scadenza o udienza aperta già acquisita dalla matrice PEC/documenti, anche se il record storico dello scadenziario non contiene ancora l'ID interno del fascicolo ma contiene un riferimento processuale affidabile.

Ordine di collegamento ammesso:

1. ID interno del fascicolo;
2. alias forti del fascicolo/importazione;
3. RG univoco nel tenant;
4. RG più cliente, parte/soggetto o profilo processuale ricavato da `Comunicazione.xml`, PEC o documento fonte.

Se più fascicoli condividono lo stesso RG e la scadenza non contiene cliente, parte/soggetto o altro dato processuale distintivo, la lista deve lasciare `n.d.` e mantenere un presidio di collegamento ambiguo. Il solo RG non basta per fondere depositi né per assegnare automaticamente una scadenza a un fascicolo ambiguo.

Quando la PEC è stata cancellata o non basta, il servizio automatico deve leggere i documenti indicizzati del fascicolo e creare/upsertare l'evento operativo corretto in agenda e scadenziario; a quel punto la stessa data deve diventare visibile anche nella colonna `Prossima scad.` del fascicolo.

## Lex AI, RAG e presidio documentale automatico

Lex AI non deve limitarsi a inviare testo libero al RAG. La lettura dei documenti del fascicolo deve produrre tre livelli separati:

1. documento sorgente conservato con hash, fascicolo, tenant e audit;
2. testo/chunk indicizzato per ricerca o database vettoriale, con metadati minimi su tenant, fascicolo, RG, ufficio, giudice, cliente, parte/soggetto, documento, pagina/fonte e hash;
3. candidato operativo normalizzato, salvato in SQL/repository applicativi solo quando la data o l'attività risultano certe.

Il RAG o l'indice vettoriale sono livelli di recupero e citazione, non fonte unica di decisione. Le decisioni operative devono essere scritte in fascicolo, agenda e scadenziario tramite upsert idempotente, con motivo leggibile e riferimento al documento letto.

Quando la PEC è stata cancellata o non contiene più tutte le informazioni, il presidio deve rileggere i documenti del fascicolo già indicizzati da Lex AI e cercare:

- udienze, rinvii, fissazioni, discussioni e camere di consiglio;
- termini per deposito note scritte, memorie, costituzioni, notifiche o altri atti da produrre;
- link audiovisivi o istruzioni di collegamento, applicandoli solo al candidato di udienza pertinente;
- ambiguità su fascicolo, parte, data o collegamento remoto.

Esempio obbligatorio: se nel fascicolo esiste un `Decreto fissazione udienza` che indica `termine del 09/07/2026 per il deposito di note scritte`, IUSENTRA deve creare un'attività comprensibile per l'avvocato, collegata al documento fonte, al cliente, alla parte, al RG e all'ufficio. Se nello stesso documento esiste anche un collegamento audiovisivo, il link va riportato sull'udienza o sul profilo remoto corrispondente, non su ogni termine letto nello stesso testo.

Fonti tecniche di riferimento consultate per la struttura:

- OpenAI File Search: vector store con attributi/metadati e filtri;
- Microsoft Azure AI Search RAG, `https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview`: chunking, OCR/PDF, hybrid search, grounding data e risposte strutturate;
- Microsoft Azure AI Search hybrid search, `https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview`: recupero full-text e vettoriale nello stesso ciclo, con fusione dei risultati;
- Qdrant hybrid queries, `https://qdrant.tech/documentation/search/hybrid-queries/`: filtri su payload, recupero ibrido e fusione risultati;
- Pinecone relevance/chunking, `https://docs.pinecone.io/guides/optimize/increase-relevance`: chunk documentali con ID strutturati, metadati completi, filtri e hybrid search;
- Pinecone RAG chatbot, `https://docs.pinecone.io/guides/get-started/build-a-rag-chatbot`: recupero citabile e risposte grounded su documenti indicizzati.

## Politica notifiche

Non creare né mostrare come avvisi separati in topbar o push mobile le ricevute grezze con oggetto:

- `ACCETTAZIONE DEPOSITO TELEMATICO`;
- `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO`.

Queste PEC aggiornano la scheda deposito. È ammesso al massimo un avviso operativo sintetico e deduplicato quando serve intervento umano, emerge un'anomalia reale o arriva un esito finale rilevante.

L'avviso deve usare l'oggetto dell'atto, cliente, parte, RG e stato comprensibile; non il titolo tecnico della ricevuta.

## Compatibilità e migrazioni

Le modifiche a schema e API devono essere retrocompatibili o accompagnate da migrazioni, backfill sicuri e valori nullable coerenti. Dati storici incompleti non devono bloccare l'applicazione.

## Test obbligatori

Aggiungere test eseguibili per:

1. parsing dei due `EsitoAtto.xml` di esempio;
2. sicurezza XML: DTD/entità esterne non risolte;
3. correlazione dei due esiti in un solo deposito con due voci di cronologia;
4. idempotenza su reimport e retry concorrenti;
5. mancata fusione di depositi distinti con lo stesso RG;
6. propagazione di cliente e parte da `Comunicazione.xml` a profilo, fascicolo, agenda e scadenziario;
7. upsert di udienze e termini senza duplicati;
8. estrazione del link remoto e presidio esplicito quando manca;
9. soppressione delle due notifiche tecniche su inbox applicativa, topbar e push;
10. correlazione ambigua non automatica;
11. conservazione di MIME, allegati, hash e audit;
12. recupero da documenti fascicolo indicizzati Lex quando la PEC non basta o non è più presente;
13. metadati RAG/vettoriali su tenant, fascicolo, RG, ufficio, cliente, parte, documento e hash;
14. distinzione fra termine operativo e udienza remota quando lo stesso documento contiene sia scadenza sia link audiovisivo;
15. idempotenza del presidio documentale: nessun duplicato in fascicolo, agenda o scadenziario al secondo passaggio;
16. popolamento di `Prossima scad.` nella lista fascicoli da scadenza/udienza aperta collegata tramite ID, alias forte, RG univoco o RG più cliente/parte;
17. mancata assegnazione automatica di `Prossima scad.` quando il solo RG è ambiguo fra più fascicoli.

Eseguire inoltre lint, typecheck, test e build previsti dal repository e documentare i comandi nella pull request.

## Criteri di accettazione

- I due esiti dell'`IDBUSTA 35508878` producono un solo deposito con stato finale corretto.
- Cliente e parte sono visibili e coerenti in tutti i punti previsti.
- Le notifiche tecniche grezze non compaiono in avvisi, topbar o push.
- Udienze e termini vengono aggiornati senza duplicati.
- La lista fascicoli non mostra `n.d.` se una scadenza o udienza aperta è già collegabile in modo affidabile da PEC o documento fascicolo.
- Il link remoto viene conservato oppure esiste un presidio esplicito se manca.
- I casi ambigui non vengono assegnati automaticamente.
- Test, migrazioni e build risultano verdi.
