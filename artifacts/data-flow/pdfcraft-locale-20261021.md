# Editor PDF locale — collaudo in corso, 21/10/2026

Componente PDFCraftTool/pdfcraft, revisione 0503080d60a337e40cc9888a749890ff49ed6b11.
Analisi REA statica: ev_38d6fa6ec72cac108326206c9a6f2fe843bca5f3608f0ff71955ee059b82dfa0.
L’ispezione REA WASM e scaduta per timeout: non costituisce una verifica positiva.

## Percorso dimostrato dai sorgenti

- ViewerDocumentEditor -> NativePdfEditor (caricamento differito) -> frame sandbox allow-scripts.
- Il componente indipendente riceve PDF e caratteri selezionati via messaggi con nonce e verifica della finestra.
- Tutti gli asset e il WASM sono locali; CSP limita connessioni a self/blob, senza CDN.
- GET pdf-diretto legge soltanto il documento autorizzato e la revisione richiesta.
- POST pdf-diretto usa repository SQL nativo, crittografia nativa, revisione, comando idempotente, versioni, evento e audit.
- Il flusso di firma/deposito/PEC non viene modificato. PDF firmati ed evidenze esterne restano non sostituibili.

## Osservato sulla copia reale 8080

Caso controllato C729BD2B, PDF DD64A59C: apertura nativa, modifica del titolo con PROVA PDF LOCALE, salvataggio confermato e riapertura nel lettore con testo modificato. Il software comunica che la versione precedente e conservata.
Un primo GET ha incontrato un lock tecnico non scrivibile; riallineata soltanto la directory tecnica editor-locks e un lock vuoto del tenant di collaudo, senza cancellare dati.
Il componente originale mostrava zero pagine: collegati contatore e ingresso pagina al motore nativo.
Il link tecnico e stato raccolto in Informazioni editor PDF, chiuso inizialmente; assenza del link nel pannello chiuso osservata sulla copia reale.

## Ancora da verificare

Caricamento e applicazione dei caratteri del PC, documenti multipagina con immagini/tabelle/formati misti, concorrenza visibile, responsive e prestazioni, chiusura e recupero errori; consolidamento bundle/versione, commit/push, tutti i gate e deploy.
I test automatici sono guardrail e non sostituiscono queste prove.
La sorgente upstream contiene JS e binario WASM; non e stata individuata la sorgente C++ del motore in quella revisione. Non si dichiara certificata la provenienza completa della compilazione WASM.

## Aggiornamento caratteri e browser

Selettore nella cornice IUSENTRA: Arial letto dal PC e confermato nel menu; applicazione e salvataggio avviati, ma la persistenza del carattere non e ancora dimostrata. Catalogo completo tramite queryLocalFonts nella cornice, con lettura differita dei soli stili scelti: implementato, prova reale ancora da eseguire. Nessun servizio remoto per i caratteri.
La conferma nativa di chiusura della bozza tecnica nella scheda 46 ha bloccato il controllo del browser. Tentati getJsDialog, Esc, chiusura della sola scheda e gestione del dialogo tramite capability del browser: tutti falliscono sul focus. Richiesto all’utente di chiudere quella conferma. Nessun test sintetico sostituisce il collaudo mancante.
Candidato locale v8, runtime pronto 2.447.2, non rilasciato. Main riallineato in fast-forward a 019f0d049 (soli due file tools del pacchetto atti), preservando il lavoro in corso.

## Aggiornamento 21/10: caratteri, forme e lingua

Nel browser reale 8080 il campione di tutte le 480 varianti PC ha superato lettura, rendering, salvataggio e riapertura in memoria. Evidenza locale separata `font-probe-second-pass.json`; non certifica tutti i glifi e tutti i documenti. Salvataggio normale del PDF tecnico FB132C61 confermato nella UI, con versione precedente conservata. Applicazione finale delle singole famiglie ancora da accettare.

EXTRACTED: ViewerDocumentEditor -> NativePdfEditor -> host-adapter -> app/core -> endpoint pdf-diretto. La barra lettore usa FilePenLine senza testo compresso; tooltip e nome accessibile mantenuti. Le forme usano shape-path.mjs e insertShape in core, percorsi PDFium nativi e selezione/history/salvataggio già esistenti: cerchio/ellisse, rettangolo, linea, freccia, freccia doppia, triangolo, rombo; contorno, spessore e riempimento. Tre guardrail geometrici passano. La prova reale del trascinamento non è ancora eseguita: il canale browser rifiuta coordinate di iframe frazionarie. Aggiunto comando nativo a tutto schermo, da collaudare; nessuna simulazione sostitutiva.

Dizionario italiano esteso a etichette, tooltip, menu, pannelli adattivi e messaggi dinamici; locale italiana nativa in main.js, titolo pagina e caricamento tradotti. Esclusi dal traduttore contenuti del PDF e nomi propri dei caratteri. La copertura visiva di tutti i menu e degli errori resta aperta, come commit e deploy.

### Prova reale successiva

Browser reale scheda 50, copia 8080: menu forme, selezione dei due estremi tramite clic sul PDF, freccia vettoriale visualizzata e selezionata con maniglie. Salvataggio normale confermato: «PDF salvato nel fascicolo. La versione precedente è conservata». Pannello Trova/Sostituisci aperto con comandi italiani; rientro nel lettore e riapertura dell’editor eseguiti. I trascinamenti del canale browser non producono eventi, mentre i clic semantici sulla stessa pagina funzionano; il trascinamento manuale resta da accettare, come ellissi e altre forme, ridimensionamento, responsive e gli altri casi già elencati.

Le forme supportano sia trascinamento sia due clic sugli estremi, con Esc per annullare; nessuna scrittura prima del secondo punto. Tradotto anche HTML statico (lingua it), non soltanto il dizionario dinamico: niente scritte inglesi nella prima visualizzazione.

## Riscontri aggiuntivi del21/10

Su8080 ellisse, rettangolo, triangolo, rombo, linea e freccia doppia inseriti tramite due estremi, visualizzati e annullati singolarmente. Georgia applicato alla parola TECNICO, salvato e riaperto: Georgia incorporato (ecdoc1), carattere circostante preservato. Immagine locale inserita al punto scelto e salvata; corretto setTool che ne cancellava la selezione. Nuova prova mostra maniglie, rotazione90gradi e salvataggio. L’utente conferma spostamento e ridimensionamento corretti sul suo PC.

Finestra reale ridotta a500e380pixel: barra forme disponibile, correzione del ritorno a capo della barra ospitante tramite container query. Ultimo ordine CSS da riprovare. Pulsanti Annulla/Ripeti visibili con tooltip italiani. Dieci test API, sei guardie Node, TypeScript e preflight export positivi.

Deploy019f0d049a/run39627185556 concluso success; prova reale Lex: chat_model/gateway_model iusentra-lex-v3:9b, digest17f76afef984b98f460bf8bab67811949a4e774ae2e7ac58c61980688813766a, done=true, eval_count22. Configurazione locale/server concordante. Nove atti biblioteca_20261020 già importati: impronte e429testi degli articoli confrontati integralmente in entrambe le copie, nessun articolo diverso o mancante, quick_checkok. Importazione una tantum non ripetuta.

## Collaudo successivo: salvataggio concorrente e finestra compatta

Copia reale8080, candidato v16: prima sessione salva cerchio pieno dopo Annulla/Ripeti. Seconda sessione, aperta sulla revisione precedente, tenta il salvataggio di un rettangolo: messaggio esplicito di modifica da altra sessione e conservazione della bozza; nessuna sovrascrittura. Prova conservata in conflitto-reale.png. Annullata la sola modifica tecnica; conferma di chiusura del browser richiede intervento utente per limite del canale.

Finestra380pixel: comandi ospitanti a capo e documento adattato dopo riapertura; finestra820pixel: barra forme su riga propria. Proprietà documento mostra nome,513,4KB,2pagine e209,9x297mm, senza modificare metadati. Corrette tre etichette residue nella barra compatta dopo Annulla. L’utente conferma nuovamente: «Spostamento e dimensioni corretti». Questa è conferma utente, distinta dalle prove dell’agente.

Rilascio ancora aperto: verifica ultima traduzione, consolidamento commit, gate remoti, deploy e pulizia governata. Non si dichiara copertura globale di tutti i PDF e glifi.

### Recupero concorrente: difetto emerso e correzione

Il rientro nel lettore dopo il409 è riuscito, ma Riprova apertura richiedeva ancora la vecchia impronta e riceveva409. La GET ora restituisce la versione corrente e X-PDF-Revision sotto lo stesso lock e permessi; il POST continua a esigere l’impronta della versione realmente letta. Il frontend verifica il nuovo header prima di caricare i byte e lo usa per il successivo salvataggio. Undici test API positivi, compreso riapertura dopo conflitto e nuovo salvataggio. Registrato il CSS della cornice nel catalogo governato, con motivazione; check design system positivo. Prova reale finale e gate in corso.

### Riscontro candidato v18

Su8080 riapertura riuscita della revisione corrente: cerchio pieno, freccia, caratteri e immagini salvati visibili; seconda pagina visitata e preservata. Corretto lo scroll ereditato dal lettore che nascondeva parzialmente la barra ospitante: all’apertura viene ripristinato lo scroll del contenitore, conservato per il ritorno al lettore. Barra completa osservata nella finestra reale, prova editor-ripresa-corrente.png. Build e typecheck positivi. CI/deploy/pulizia ancora in corso.

## Rilascio b8c7ec53b6 e correzione della cache

CI, frontend, CodeQL, supply chain, overlay e gate richiesti del commit b8c7ec53b636d381c8dc101c1cec89bf5df362e3 conclusi success. Deploy39652553930 success; server pronto2.447.2, Lex chat/gateway iusentra-lex-v3:9b, digest17f76afef984b98f460bf8bab67811949a4e774ae2e7ac58c61980688813766a, done=true, eval_count19. Pulizia server rimuove una immagine obsoleta e conserva due riferimenti; seconda pulizia success. Locale sullo stesso commit,752sorgenti e296asset concordanti, app/worker healthy. Rimossi18riferimenti intermedi del collaudo, senza volumi o dati; layer condivisi e cache non attribuita conservati, nessuna pretesa di GB recuperati sul disco Windows.

Verifica HTTPS della risorsa pubblica dell’editor: Cache-Control public,max-age604800. La cache settimanale può mantenere vecchio codice ai successivi rilasci. Correzione mirata: dopo la richiesta Flask i soli asset del componente richiedono rivalidazione; Caddy li esclude dalla regola statica settimanale e mantiene ETag/304; Nginx li inoltra senza aggiungere expires7d. Risorse mancanti no-store; API private e asset React con impronta invariati.

Caddy validate con la configurazione aggiornata nel container reale: configurazione valida, senza ricaricare il server prima del rilascio. Nginx test nella cornice HTTP corretta e poi sulla configurazione effettiva locale: positivo, reload riuscito. Su8080 e proxy locale intestazione public,must-revalidate,no-cache,max-age0. Apertura reale del PDF nel browser riuscita, testo/immagini/cerchio/freccia presenti; prova editor-cache-rivalidata.png. Undici test API passano, comprese intestazioni sulla risorsa reale e404non memorizzabile.

Baseline accettata consultata in sola lettura: nginx.conf coincide prima della modifica (762ff9ad713fb6dd10fba87ad7d285af9e78a4096c1c7ab9b3096e5da22a16c0); Caddyfile accettato b4cf181c96941a1efd970348620489b1cf8682a93dfb461c61be836042d35e1d, già evoluto prima dell’intervento a589c4bd1e6778e1286eaaec5fbaf4c4cf0a01070a8ef898f503825cea197e144. Il diff nuovo modifica soltanto la cache del componente, senza alterare autenticazione, firme, deposito, PEC, TLS o destinazioni del proxy.

La correzione cache richiede ancora commit, gate del nuovo SHA e verifica dell’intestazione HTTPS dopo il deploy. Questo aggiornamento prevale sulle precedenti sezioni cronologiche relative a prove non ancora eseguite; non certifica ogni PDF o ogni glifo esistente.

## Diagnosi del servizio statico reale e distribuzione con impronta

EXTRACTED: Caddy handle_path /static/* inoltra a static-assets:8090, senza attraversare Flask. Verifica HTTPS su b8: oltre a max-age604800 mancavano Access-Control-Allow-Origin, Cross-Origin-Resource-Policy e Content-Security-Policy. La sola intestazione Flask verificata su8080 non dimostrava la parità del server. Il deploy b8 era riuscito; non è una prova positiva dell’editor nel browser di produzione.

Correzione del confine effettivo: Caddy applica ai soli file pubblici /static/vendor/pdfcraft-direct/* le stesse policy di isolamento già provate localmente. Un test confronta le due CSP e verifica che il CORS pubblico non sia esteso alle API. Caddy validate sul binario reale è positivo.

I vecchi indirizzi possono essere già memorizzati con le vecchie intestazioni. Perciò l’editor ora usa /releases/d17d8e3b53ea1b08c087/editor: indirizzo derivato dalle impronte di tutti i file, binari preservati, terminatori testuali normalizzati come Git. tools/build_pdf_editor_release.py pubblica la nuova copia senza alterare le precedenti; --check respinge sorgente diversa, byte pubblicati alterati o file aggiunti. Il controllo entra nel pre-push e nel test frontend; nessuna dipendenza runtime o scansione dei documenti.

Quattro guardrail del costruttore e dodici test API/policy passano. Bundle753sorgenti/296asset concordante. Sul browser reale8080 l’iframe usa il nuovo indirizzo e apre il documento tecnico completo con testo, immagine, cerchio e freccia. Conferma visiva conservata separatamente. L’ultima correzione richiede nuovo commit, CI e prova delle policy HTTPS sul nuovo indirizzo; il lavoro sul server resta formalmente aperto.
