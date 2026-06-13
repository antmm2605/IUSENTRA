# Assistente vocale Studio - file di lettura incarico

Data avvio: 12 giugno 2026.

## Incarico ricevuto

Integrare l'assistente vocale Studio nella copia reale IUSENTRA, partendo dal pacchetto fornito in `C:\Users\antmm\Downloads\iusentra-studio-voice-assistant-files.zip`, senza applicare codice con testi corrotti. L'assistente deve:

- riconoscere tutti i comandi vocali indicati dall'utente;
- aggiungere almeno 100 comandi/frasi ulteriori;
- registrare tono di voce e PIN locale prima dell'ascolto;
- attivare e disattivare l'ascolto da UI e da comando vocale;
- aprire davvero pannelli e pagine richieste;
- gestire "Studio cerca Rossi" verso `/global-search?q=rossi`;
- aprire Lex AI nel contesto corrente;
- creare un cliente da voce chiedendo solo nome, cognome e codice fiscale, rileggendo i dati e salvando solo dopo conferma;
- mantenere UI professionale, responsive, in italiano corretto, senza linguaggio tecnico visibile;
- verificare con test reali, Docker locale su `127.0.0.1:8080`, push dei branch gemelli e deploy Hetzner.

## Fonti e contesto letti

- `AGENTS.md` fornito nel messaggio utente;
- `README.md`;
- `docs/UI_DESIGN_SYSTEM.md`;
- `tools/open-design-support/IUSENTRA_UI_RULES.md`;
- `tools/open-design-support/IUSENTRA_DESIGN.md`;
- `docs/REACT_MIGRATION_MASTER_PLAN.md`;
- `docs/REACT_OPERATIONAL_AUDIT.md`;
- `docs/COMMIT_PUSH_REQUIRED_GATES.md`;
- report React in `artifacts/react-migration/`;
- pacchetto ZIP estratto in `%TEMP%\iusentra-voice-assistant-import`.

## Decisioni implementative

- Il componente ZIP non è stato copiato in blocco perché conteneva mojibake e non copriva il flusso cliente richiesto.
- Il catalogo comandi è sorgente dati in `frontend/src/studioVoiceCommands.json`.
- Il motore puro è in `frontend/src/studioVoiceAssistant.ts` per testare normalizzazione, PIN, ricerca, conferme e campi cliente.
- Il pannello React è in `frontend/src/components/StudioVoiceAssistant.tsx` con stile governato in `frontend/src/components/layout/TopBar.css` e caricamento pigro dalla topbar.
- La creazione cliente passa dall'API reale `POST /api/v1/ui/clienti/voce/crea`, con permessi `clienti.scrivi`, `GestioneClienti`, audit e sincronizzazione.

## Stato attuale

Completato localmente nel codice:

- catalogo con 368 frasi vocali totali, 328 frasi aggiunte rispetto ai comandi iniziali, 59 destinazioni e 11 azioni rapide;
- registrazione locale voce + PIN con calibrazione di 30 secondi;
- frase di attivazione personalizzabile e persistente sul dispositivo;
- registro visibile "Cosa ho ascoltato" per mostrare i comandi riconosciuti;
- attivazione con controllo tono voce e PIN pronunciato o inserito;
- prompt PIN pronunciato dall'assistente prima dell'ascolto del codice, con ripetizione guidata se il PIN è errato o non viene letto;
- ascolto continuo con memoria di sessione nella stessa scheda: il cambio pagina non lo disattiva, mentre lo spegnimento resta solo su "Disattiva ascolto", comando vocale "disattiva assistente"/"chiudi assistente", rimozione profilo o revoca reale del microfono;
- sessione operativa separata dal richiamo: dopo PIN corretto l'assistente resta in richiamo vocale; dicendo la frase di attivazione, per esempio "Studio", entra in sessione operativa e da quel momento i comandi funzionano senza ripetere la frase di attivazione fino a "stop";
- "stop" sospende solo la sessione operativa e lascia attivo il richiamo vocale; per riattivare i comandi basta dire di nuovo la frase di attivazione;
- il pannello non deve aprirsi automaticamente durante cambio pagina, navigazione, ripristino ascolto o riavvio del riconoscimento di Chrome; se l'avvocato lo chiude, resta chiuso e non copre la scheda;
- comandi di navigazione, ricerca, Lex, aiuto, indietro, ricarica, disattivazione e modifica record corrente;
- flusso "nuovo cliente" con nome, cognome, codice fiscale, rilettura, conferma e salvataggio durante la sessione operativa;
- comandi "modifica cliente", "modifica clienti", "modifica soggetto" e "modifica soggetti e parti", con apertura della modifica del record corrente quando la pagina contiene già un cliente o un soggetto;
- sotto-modulo note con richiamo combinabile "Studio, note" quando la sessione non è ancora operativa, oppure comando diretto "note" durante la sessione; dettatura libera, chiusura "fine nota" o "fine note", estrazione di data e ora, salvataggio della sola trascrizione testuale e promemoria browser 10 minuti prima quando consentito;
- servizio unico di dettatura `IusentraVoiceInput` / `PctLexVoice`, senza microfono duplicato su ogni campo, con comando "scrivi qui" e varianti esplicite per clienti, soggetti, scadenziario, agenda e ricerca;
- Lex AI, editor documento, editor professionale e template atti collegati allo stesso controllo microfono e alla stessa normalizzazione della dettatura;
- memoria dell'ultimo campo valido selezionato, così la dettatura resta nel contesto scelto anche quando il pannello assistente prende il focus;
- test statici e API mirati.

Verifiche già passate:

- `node frontend\scripts\check-studio-voice-assistant.mjs`;
- `python -m py_compile web\blueprints\api_v1_react.py pct\clienti.py`;
- `python -m pytest tests\test_studio_voice_assistant.py -q --tb=short`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `docker compose build app`;
- `docker compose up -d --no-deps --force-recreate app`;
- `GET http://127.0.0.1:8080/api/pronto` con versione `2.253.1`;
- `python -m pytest tests\test_studio_voice_assistant.py tests\test_utf8_integrity.py -q --tb=short`;
- `docker compose build --no-cache app scheduler-worker ocr-worker`;
- `docker compose up -d --force-recreate app scheduler-worker ocr-worker`;
- `GET http://127.0.0.1:8080/api/pronto` con versione `2.253.1`;
- `IUSENTRA_VOICE_E2E_PASSWORD=<utente temporaneo> node scripts\react-migration\studio_voice_assistant_browser_audit.mjs`, eseguito con utente temporaneo locale: 59 destinazioni, 330 frasi, ascolto/disattivazione/cliente guidato verificati con microfono e riconoscimento simulati; la password non è versionata;
- `node scripts\react-migration\visual-load-audit.mjs`: 15 controlli desktop/tablet/mobile verdi su Panoramica, Fascicoli, Statistiche, Contatti Sito Studio e Builder Sito.
- `node tests\js\lex_tts_voice_contract.test.mjs`;
- `node frontend\scripts\check-studio-voice-assistant.mjs`;
- `python -m pytest tests\test_studio_voice_assistant.py tests\test_security_headers.py tests\test_utf8_integrity.py -q --tb=short`;
- `python -m pytest tests\test_studio_voice_assistant.py tests\test_utf8_integrity.py -q --tb=short`;
- `python -m pytest tests\test_react_asset_retention.py -q --tb=short`;
- `pnpm --filter @iusentra/studio test`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- `docker compose build --no-cache app scheduler-worker ocr-worker`;
- `docker compose up -d --force-recreate app scheduler-worker ocr-worker`;
- `GET http://127.0.0.1:8080/api/pronto` con versione `2.253.3`;
- conferma utente su macchina reale, 13 giugno 2026: il microfono funziona nella prova materiale.

## Verifica reale del microfono - 13 giugno 2026

Eseguita dopo rebuild Docker locale `2.253.3` e caricamento degli asset aggiornati su `http://127.0.0.1:8080`.

- Il codice del servizio microfono e' stato reso piu' robusto: prima richiesta semplice `audio: true`, poi applicazione facoltativa di cancellazione eco, riduzione rumore e controllo guadagno.
- Il controllo Lex AI e la dettatura Studio passano dallo stesso servizio, evitando messaggi discordanti tra moduli.
- Il profilo Chrome dell'utente e Windows risultano autorizzati al microfono.
- L'utente ha confermato sulla macchina reale che il microfono funziona.
- Hotfix successivo dello stesso giorno: l'ascolto Studio ora deve restare attivo nella stessa scheda anche cambiando pagina; il prompt PIN viene pronunciato prima della lettura del codice; i comandi modifica cliente/soggetto sono stati aggiunti al catalogo.
- Hotfix sessione operativa 13 giugno 2026: tutte le frasi comando autorizzate sono state ripulite dalla parola "Studio"; il catalogo operativo contiene 390 frasi, 350 aggiunte, 59 destinazioni e zero frasi con prefisso di attivazione. La frase di attivazione serve solo a entrare in sessione. Dopo "stop" l'assistente torna in richiamo vocale e non spegne il microfono.
- Hotfix pannello 13 giugno 2026: il pannello non deve riaprirsi da solo quando l'avvocato naviga o quando Chrome riavvia il riconoscimento. Sono ammesse aperture automatiche solo per flussi guidati che richiedono interazione visibile, ad esempio nuovo cliente e note vocali.
- Prova reale successiva in Chrome: il microfono risulta consentito e Chrome mostra "Microfono in uso", ma il primo flusso ha respinto il tono e l'utente non ha sentito alcun prompt. Hotfix applicato: "Attiva ascolto" pronuncia subito l'avviso di controllo tono, usa un campione più lungo e una soglia più prudente; il PIN resta la conferma prima dell'ascolto operativo.
- Hotfix PIN vocale 13 giugno 2026: il PIN non deve dipendere da un pulsante di ripetizione. Se Chrome non sente il PIN, non legge cifre valide o legge un codice errato, l'assistente deve parlare automaticamente, dire cosa ha capito quando possibile e riaprire da solo l'ascolto fino a tre tentativi. Il campo manuale "Conferma PIN" compare solo come ripiego se il riconoscimento non parte o dopo i tentativi vocali falliti.
- Hotfix UI PIN 13 giugno 2026 da prova reale Chrome: durante il retry automatico del PIN la UI non deve mostrare solo "Studio non in ascolto" né lasciare "Attiva ascolto" come azione ambigua. Deve mostrare "Verifica PIN vocale", spiegare che sta ascoltando automaticamente e sostituire il pulsante con "PIN in ascolto" fino alla conclusione del flusso.
- Hotfix dettatura libera 13 giugno 2026: con sessione operativa attiva, se un campo valido è selezionato e la frase pronunciata non corrisponde a un comando autorizzato, l'assistente deve provare a scrivere direttamente quella frase nel campo selezionato o nell'ultimo campo valido ricordato. I comandi riconosciuti restano prioritari sulla dettatura.
- Hotfix microcopy richiamo 13 giugno 2026: nello stato di richiamo deve essere visibile la guida completa "Richiamo pronto. Di’ “Studio” per attivare la sessione operativa. Di’ “stop” per bloccare la sessione operativa e tornare al richiamo.", usando la frase di attivazione personalizzata quando diversa da "Studio".
- Hotfix dettatura nei campi 13 giugno 2026: il riscontro "cosa ho ascoltato" durante la compilazione non deve aprire un pannello aggiuntivo. Il testo deve comparire direttamente nel campo selezionato: con "detta" o "scrivi qui" il campo mostra l'anteprima mentre Chrome ascolta, con dettatura libera il testo finale resta selezionato per controllo visivo. I campi testuali devono partire con iniziale maiuscola, il codice fiscale va uniformato in maiuscolo, email/PEC e telefoni non devono essere alterati con maiuscole forzate.
- Hotfix normalizzazione campi 13 giugno 2026: il servizio deve leggere automaticamente tipo, nome, etichetta e placeholder del campo prima di scrivere. Campi numero/telefono/CAP/civico/documento compattano cifre e zeri, email/PEC correggono spazi e falsi trattini senza togliere trattini legittimi, URL/sito web vengono resi minuscoli e compatti, i campi data convertono date italiane in valore valido e i select, inclusi sesso/genere, scelgono l'opzione compatibile.
- Non dichiarare automaticamente concluse le superfici di dettatura: per Clienti, Soggetti, Scadenziario, Agenda, Ricerca Studio, email/PEC ed editor serve comunque selezionare un campo reale, dettare e vedere il testo inserito.

## Verifica visiva reale del microfono - 12 giugno 2026

Eseguita sul browser integrato visibile, copia reale `http://127.0.0.1:8080`, asset React aggiornato e container Docker ricreato.

- Aperto materialmente il pannello "Assistente vocale Studio".
- Scrollato l'intero pannello: intestazione, stato, "Cosa ho ascoltato", "Voce e PIN locale", frase consigliata, nuovo cliente guidato ed elenco comandi.
- Salvata frase di attivazione "Studio Legale"; dopo ricarica la frase resta nel campo, quindi viene riletta dal dispositivo.
- Premuto materialmente "Registra voce e PIN" con PIN inserito.
- Il browser ha negato l'accesso al microfono: la registrazione di 30 secondi non è partita e il tono non può essere dichiarato salvato.
- Esito visibile corretto: "Microfono non autorizzato. Consenti il microfono dal browser, poi reinserisci il PIN e premi di nuovo Registra voce e PIN."
- Il PIN è mascherato nel campo e viene svuotato dopo il tentativo fallito.
- Dopo il tentativo fallito resta visibile "Registra voce e PIN" e non compare "Attiva ascolto": quindi il profilo non risulta salvato quando il microfono è negato.

Blocco reale: per completare la registrazione effettiva del tono e verificare il salvataggio del profilo vocale serve autorizzare il microfono nel browser. Appena il permesso è concesso, ripetere il click e leggere la frase consigliata per tutti i 30 secondi.

## Domande operative obbligatorie da verificare nel browser

Ogni test visivo dell'assistente vocale deve rispondere in modo evidente, davanti alla UI reale, a queste domande:

1. Dove vedo se lo studio è realmente in ascolto?
   - Nel riquadro "Richiamo vocale pronto" / "Sessione operativa attiva" / "Studio non in ascolto", quando il pannello è aperto. Se il pannello è chiuso, il pulsante "Voce Studio" resta attivo e non deve coprire la pagina.
2. Dove vedo i comandi che sto richiedendo?
   - Nella sezione "Comandi autorizzati", riquadro "Cosa ho ascoltato", e nel riepilogo dell'ultimo comando operativo.
3. Come capisco che il comando è stato eseguito?
   - Il riepilogo deve mostrare "Comando richiesto" e poi "Comando eseguito" con l'area aperta o l'azione compiuta.
4. Come sospendo o disattivo l'ascolto?
   - "Stop" sospende la sessione operativa e lascia pronto il richiamo vocale. "Disattiva assistente", "chiudi assistente" o il pulsante "Disattiva ascolto" fermano davvero l'ascolto.
5. Se cambio pagina lo studio resta in ascolto?
   - Sì, nella stessa scheda deve restare in ascolto dopo apertura cliente, modifica cliente, Soggetti e Parti o altre pagine. Se si disattiva da solo, è una regressione da correggere nel codice. Se il pannello si riapre da solo e copre la pagina, è un'altra regressione da correggere subito.
6. Il PIN viene solo mostrato o anche parlato?
   - Deve essere parlato: l'assistente deve dire "Sto ascoltando il PIN. Pronuncia solo le cifre oppure inseriscile a mano." e solo dopo aprire l'ascolto del codice.
   - Se non capisce, deve ripetere automaticamente l'ascolto: nessun pulsante di ripetizione deve essere necessario per il flusso vocale normale.
7. Quando premo "Attiva ascolto" sento qualcosa prima del PIN?
   - Sì: l'assistente deve dire che sta controllando il tono e chiedere di pronunciare la frase di attivazione. Se resta silenzioso, il flusso non è accettabile anche se il microfono è consentito.
8. La configurazione è completa?
   - La sezione "Configurazione" deve mostrare "Voce registrata" dopo salvataggio reale o "Voce non registrata" se il microfono non ha consentito la registrazione.
9. Durante la registrazione cosa devo vedere?
   - Timer dei secondi rimanenti, barra di avanzamento, testo rilevato durante la lettura e stato finale di salvataggio.

Protocollo di prova obbligatorio: desktop, tablet e mobile devono essere verificati con browser visibile, scroll completo del pannello, click reale sulle tab "Configurazione", "Comandi autorizzati" e "Richieste operative", click reale su "Registra voce e PIN", "Avvia guida" e, quando il profilo è disponibile, "Attiva ascolto" e "Disattiva ascolto".

## Sotto-modulo note vocali - richiesta 12 giugno 2026

Il sotto-modulo note vocali deve essere parte dell'assistente vocale Studio e non una funzione separata.

Requisiti operativi obbligatori:

1. comando di apertura: "note" durante sessione operativa, oppure "Studio, note" come frase unica quando serve anche il richiamo;
2. comando note personalizzabile dallo studio, ad esempio "appunti" o "memo", mantenendo la frase di attivazione generale separata;
3. dettatura libera della nota dopo l'apertura;
4. comando di chiusura: "fine nota" o "fine note";
5. supporto della frase completa in un solo comando, ad esempio "Studio, note ricordami il 20 giugno alle ore 18 di chiamare il cliente fine nota" oppure, con sessione già attiva, "note ricordami il 20 giugno alle ore 18 di chiamare il cliente fine nota";
6. estrazione prudente di data e ora da frasi come "domani alle 18" e "20 giugno alle ore 18";
7. salvataggio della sola trascrizione testuale, mai dell'audio grezzo;
8. promemoria browser 10 minuti prima dell'orario estratto, se il permesso notifiche è concesso;
9. ogni orario estratto, salvato nel riepilogo e visualizzato nel pannello deve essere presentato in ora italiana con fuso `Europe/Rome`, mai in UTC o in formato ambiguo;
10. nota visibile sul limite: il promemoria frontend funziona mentre IUSENTRA resta aperto; per notifiche affidabili a browser chiuso servono backend, Agenda, service worker e Web Push;
11. test visivo completo della sequenza configurazione, attivazione, comando note, dettatura, chiusura, salvataggio, promemoria e disattivazione;
12. verifica responsive desktop, tablet e mobile con scroll completo del pannello e correzione immediata di difetti grafici, testi tagliati, pulsanti poco chiari o card non responsive.

## Servizio dettatura unico - richiesta 13 giugno 2026

La dettatura deve essere strutturale e non frammentata. Non va aggiunto un microfono su ogni campo di IUSENTRA.

Regola implementativa:

1. un solo servizio comune in pagina, `window.IusentraVoiceInput`, riusa il motore `PctLexVoice`;
2. Lex AI non deve piu' fare un controllo microfono separato che contraddice Chrome;
3. durante la sessione operativa il comando globale "detta" / "scrivi qui" deve inserire testo nel campo attivo o nell'ultimo campo valido selezionato;
4. varianti esplicite del catalogo devono coprire "detta cliente", "detta soggetto", "detta scadenza", "detta scadenziario", "detta agenda", "detta appuntamento", "detta ricerca", "detta email" e "detta PEC";
5. il servizio deve riconoscere e normalizzare punteggiatura e simboli dettati: virgola, punto, punto e virgola, punto interrogativo, punto esclamativo, a capo, spazio, trattino, meno, piu', diviso, chiocciola, underscore/ancscore e asterisco/aterisco;
6. le superfici da verificare materialmente sono almeno: Clienti, Soggetti e parti, Scadenziario, Agenda/Nuovo appuntamento, Ricerca Studio, email, PEC, Lex AI, editor documento, editor professionale e template atti;
7. la prova finale non puo' essere solo automatica: serve Chrome reale, copia `127.0.0.1:8080`, campo selezionato, comando/pulsante avviato e testo visibile nel punto corretto.

## Da fare prima di chiudere

- commit e push su `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`;
- attendere check GitHub/CodeQL dello SHA corrente;
- deploy Hetzner, container healthy, `https://app.iusentra.it/api/pronto`, prune Docker e pulizia snapshot.

Nota di ripresa: prima del commit ripristinare i soli file runtime generati da login/test Docker (`data/**`), pulire gli asset React non referenziati dalla build corrente e lasciare in stage solo sorgente, test, documentazione, report e asset statici intenzionali.

## Stato attuale 13 giugno 2026, audit Chrome reale visibile 2.253.4

- Copia Docker reale `http://127.0.0.1:8080` ricostruita no-cache, container `app` healthy, `/api/pronto` con `versione=2.253.4`.
- Browser usato per l'audit: Google Chrome installato `C:/Program Files/Google/Chrome/Application/chrome.exe`, non Chromium Playwright.
- Esito audit `artifacts/react-migration/studio-voice-assistant-browser-audit.json`: zero failure, 390 frasi, 59 destinazioni vocali, browser visibile, permesso microfono `granted`, desktop/tablet/mobile senza overflow.
- Flusso verificato: registrazione profilo/PIN con calibrazione, richiamo pronto, parola "Studio", sessione operativa, note vocali con comando personalizzato `appunti`, promemoria in ora Roma, aiuto, Lex, ricerca "cerca Rossi", nuovo cliente con conferma, pulizia cliente di prova, disattivazione, riattivazione e 59 destinazioni.
- Dettatura campi reali su `/clienti/nuovo`: nome `Mario`, telefono `00100`, CAP `00100`, numero documento `CA61007P`, email `antmm2605@gmail.com`, PEC `studio-legale@example.com`, sito `www.marco.rossi.it`, date ISO da dettatura italiana e sesso `F`.
- Bug trovati dall'audit e corretti: `doc_numero` non compattava il numero documento; "cerca Rossi" senza `Studio` non partiva in sessione operativa; la riattivazione post-disattivazione nello script non attendeva il richiamo pronto.
- Nota anti falso-verde: il riconoscimento delle frasi nell'audit è pilotato in pagina per renderlo ripetibile senza voce umana dell'utente. La UI, Chrome, route, salvataggi, responsive, click, scroll e stati sono stati osservati sulla macchina reale; una nuova lettura fisica umana del tono resta distinta.
- Caso noto scritto nel piano post-deploy: chunk principale Vite `index-D9Xs3IhZ.js` a `503,51 kB` minificato, da affrontare con code splitting dopo deploy.

## Piano post-deploy da avviare dopo questa release

1. Caso noto prestazionale: il warning Vite sul chunk principale React sopra 500 kB non va piu' trattato come "noto" senza azione. Dopo deploy va aperta una tranche dedicata di code splitting: misurare asset reali, individuare import pesanti, spezzare superfici non critiche, ripetere build e verificare caricamento/passo pagina sulla copia reale `127.0.0.1:8080`.
2. Notifiche e scadenze rapide: spostare la sezione operativa coerentemente dentro Comunicazioni, lasciando nella topbar solo scadenze rapide utili. Rimuovere duplicazioni massive di avvisi scaduti gia' presenti in Agenda/Scadenziario e ridisegnare UI responsive desktop/tablet/mobile con testi legali chiari, card compatte e pulsanti leggibili.
3. Verifica reale obbligatoria anche per il piano post-deploy: browser visibile, click materiali, scroll completo della pagina/pannello, correzione immediata di difetti grafici, overflow, testi tagliati o comportamenti ambigui.

## Protocollo dopo compattazione

Quando la conversazione viene compattata o ripresa, rileggere questo file prima di proseguire. Verificare:

1. stato worktree con `git status --short`;
2. ultimo blocco "Stato attuale";
3. lista "Da fare prima di chiudere";
4. se sono stati toccati file UI/route/API dopo gli ultimi test, rilanciare solo i gate collegati;
5. non dichiarare completato finché Docker reale, browser, push, check remoti e deploy Hetzner non sono conclusi.
