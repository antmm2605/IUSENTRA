# Assistente vocale Studio

L'assistente vocale Studio consente all'avvocato di navigare IUSENTRA, aprire Lex AI, cercare nello studio e inserire rapidamente un nuovo cliente usando comandi vocali in italiano.

## Attivazione

1. Aprire il pulsante con icona assistente nella barra superiore.
2. Inserire un PIN numerico locale.
3. Registrare la voce: il browser raccoglie una calibrazione locale di 30 secondi e non invia il profilo al server.
4. Per attivare l'ascolto, il browser avvisa a voce che sta controllando il tono, ascolta una breve frase di attivazione e poi chiede il PIN pronunciato.
5. Dopo il PIN corretto l'assistente resta in richiamo vocale: ascolta solo la frase di attivazione configurata dallo studio. Il valore predefinito è "Studio"; il pannello permette di cambiarlo, ad esempio in "Studio Legale" o nel nome dello studio.
6. La frase di attivazione apre una sessione operativa. Da quel momento i comandi autorizzati si pronunciano senza ripetere "Studio", fino al comando "stop".

Il controllo voce è un presidio locale di comodità e non sostituisce permessi, login, audit e autorizzazioni dello studio.

## Ascolto continuo tra le pagine

Quando l'avvocato attiva "Voce Studio", il richiamo vocale resta attivo nella stessa scheda anche se cambia pagina, apre un cliente, entra in modifica o naviga tra Clienti, Soggetti e Parti, Agenda, Ricerca Studio e altre sezioni. Il cambio pagina non deve disattivare l'assistente.

L'ascolto si spegne solo con un'azione esplicita:

- pulsante "Disattiva ascolto";
- comando vocale "disattiva assistente" o "chiudi assistente" quando la sessione operativa è attiva;
- rimozione del profilo vocale;
- blocco o revoca reale del microfono da parte del browser.

Il comando "stop" non spegne il microfono: sospende solo la sessione operativa e riporta l'assistente in richiamo vocale. L'avvocato può dire di nuovo la frase di attivazione, ad esempio "Studio", per riprendere i comandi.

Messaggio guida obbligatorio in stato di richiamo: "Richiamo pronto. Di’ “Studio” per attivare la sessione operativa. Di’ “stop” per bloccare la sessione operativa e tornare al richiamo." Se la frase di attivazione è personalizzata, al posto di "Studio" deve comparire il valore scelto dallo studio.

Il pannello non deve aprirsi automaticamente durante navigazione, cambio pagina, ripristino ascolto o riavvio del riconoscimento di Chrome. Deve restare chiuso se l'avvocato lo ha chiuso, così non copre la scheda anagrafica, agenda, scadenziario o ricerca. Il pannello si apre solo con il pulsante "Voce Studio" oppure per flussi guidati che richiedono una conferma visibile, come nuovo cliente e note vocali.

La persistenza è limitata alla sessione della scheda del browser: non salva audio e non rende permanente l'ascolto dopo chiusura della scheda.

## Dettatura nei campi

Quando la sessione operativa è attiva e l'avvocato si trova dentro un campo compilabile, la dettatura deve scrivere direttamente in quel campo. Non deve aprire un riquadro aggiuntivo solo per mostrare cosa è stato ascoltato: il controllo avviene nel valore del campo che si sta compilando.

Con il comando esplicito "detta" o "scrivi qui", il campo mostra l'anteprima mentre il browser ascolta e resta evidenziato durante la dettatura. Con la dettatura libera in sessione operativa, il testo finale viene inserito nel campo selezionato o nell'ultimo campo valido e resta selezionato per un breve controllo visivo.

La normalizzazione è unica per tutto IUSENTRA e deve rispettare il tipo di campo:

- il servizio legge automaticamente tipo, nome, etichetta e placeholder del campo prima di scrivere;
- campi testuali ordinari: primo carattere in maiuscolo;
- codice fiscale: lettere maiuscole e nessuno spazio;
- telefono, cellulare, fax, CAP, civico e numero documento: spazi tra cifre rimossi senza perdere zeri iniziali, quindi "00 100" resta "00100";
- numero documento: codice alfanumerico compatto e maiuscolo, ad esempio "CA 61 007 P" diventa "CA61007P";
- email e PEC: tutto minuscolo, senza spazi, senza falsi trattini fra lettere e numeri;
- sito web e URL: tutto minuscolo e senza spazi, ad esempio "Www.Marco.rossi.it" diventa "www.marco.rossi.it";
- campi data: qualunque input data, o campo riconoscibile come data da etichetta italiana, deve convertire la data dettata in italiano in valore data valido del campo, non inserirla come testo libero.
- campi a scelta: se il campo contiene opzioni, la voce deve selezionare l'opzione compatibile; per "sesso" o "genere", "maschile", "maschio" o "uomo" selezionano Maschile, mentre "femminile", "femmina" o "donna" selezionano Femminile.

## PIN vocale

Quando l'avvocato preme "Attiva ascolto", l'assistente deve parlare subito: "Controllo il tono di voce. Pronuncia Studio con voce naturale." Solo dopo questo avviso raccoglie il breve campione vocale.

Dopo il riconoscimento del tono, il messaggio "Sto ascoltando il PIN. Pronuncia solo le cifre oppure inseriscile a mano." deve essere anche pronunciato dall'assistente, non solo mostrato a video. Solo dopo la frase parlata parte l'ascolto del PIN.

Se il PIN è corretto, l'assistente conferma "PIN corretto. Richiamo vocale pronto." e attiva l'ascolto continuo in modalità richiamo. Se il PIN è errato, non viene letto o viene letto male, l'assistente ripete a voce cosa ha capito e riapre automaticamente l'ascolto fino a tre tentativi, senza chiedere all'avvocato di premere un altro pulsante. Il campo manuale compare solo come ripiego quando il riconoscimento non parte o dopo i tentativi vocali falliti.

Durante questi tentativi la UI non deve sembrare ferma o non in ascolto: lo stato principale mostra "Verifica PIN vocale" e il pulsante di attivazione diventa "PIN in ascolto" finché il flusso automatico non termina o non passa al ripiego manuale.

## Calibrazione del tono

La registrazione del tono deve durare almeno 30 secondi. Durante la calibrazione l'assistente non riproduce audio sintetico, così la voce del professionista non viene contaminata dalla voce del browser.

Frase consigliata:

> Studio legale IUSENTRA, autorizzo l'assistente vocale dello studio. Apri panoramica, clienti, calendario e fascicoli. Riconosci il mio tono naturale con voce chiara, costante e professionale.

Se la frase termina prima dei 30 secondi, rileggerla con lo stesso ritmo. Parlare in modo naturale, con distanza costante dal microfono e in un ambiente silenzioso.

Il pannello mostra:

- la frase consigliata;
- la barra di avanzamento della calibrazione;
- il campo PIN mascherato;
- il registro "Cosa ho ascoltato", dove compare il testo riconosciuto quando l'ascolto è attivo;
- la frase di attivazione personalizzabile.

## Copertura comandi

Il catalogo è in `frontend/src/studioVoiceCommands.json` e contiene:

- i 40 comandi indicati dall'utente come base;
- 350 frasi aggiunte;
- 390 frasi totali;
- 59 destinazioni o aree apribili;
- azioni speciali per ricerca, Lex, aiuto, indietro, ricarica, disattivazione, dettatura unica, modifica cliente/soggetto corrente e nuovo cliente guidato.

Esempi di famiglie coperte:

- Panoramica, Regia Operativa, Ricerca Studio;
- Agenda, Calendario, nuovo appuntamento, Timesheet;
- Fascicoli, nuovo fascicolo, archivio fascicoli;
- Clienti, nuovo cliente vocale, soggetti e parti;
- modifica cliente corrente e modifica soggetto o parte corrente;
- PEC, email ordinaria, notifiche, messaggi, WhatsApp;
- Scadenze, nuova scadenza, preparazione udienza;
- Servizi Telematici, PolisWeb, PDP, PAT, PTT, controlli atti;
- Fatture, Preventivi, Compensi Forensi, Documenti, Redazione Atti;
- Ricerca Legale, News disponibili, Archivio Giurisprudenza;
- Strumenti Forensi, Strumenti Operativi, Sito Studio;
- Impostazioni, Backup, Calendari, Amministrazione, Utenti, Profili, Database, Registro GDPR.

## Nuovo cliente da voce

Con la sessione operativa attiva, il comando "nuovo cliente" avvia il flusso guidato:

1. l'assistente chiede il nome;
2. chiede il cognome;
3. chiede il codice fiscale;
4. rilegge i tre dati;
5. salva solo dopo conferma vocale o pulsante "Aggiungi cliente".

Il salvataggio usa `POST /api/v1/ui/clienti/voce/crea`, richiede permesso `clienti.scrivi`, valida tutti i campi obbligatori, usa `GestioneClienti`, registra audit e pubblica l'evento di sincronizzazione.

## Note vocali e promemoria

Le note vocali sono un sotto-modulo dell'assistente vocale Studio. La frase predefinita del sotto-comando è "note", ma lo studio può personalizzarla dal pannello "Note vocali", ad esempio "appunti" o "memo". Se il richiamo non è ancora in sessione operativa, l'avvocato può dire "Studio, note" in un'unica frase: "Studio" attiva la sessione e "note" apre il sotto-modulo. Durante la sessione operativa basta dire "note".

Esempi:

- "Studio, note. Domani alle 18 ricordami di controllare la PEC del fascicolo Bianchi. Fine nota."
- con sessione già attiva: "note ricordami il 20 giugno alle ore 18 di chiamare il cliente fine nota."
- se il sotto-comando è stato cambiato in "appunti": "appunti ricordami domani alle 18 di chiamare il cliente fine nota."

La prima versione salva solo la trascrizione testuale sul dispositivo e non conserva audio grezzo. È una scelta prudente perché le note di studio possono contenere dati sensibili.

Quando la nota contiene data e ora riconoscibili, l'assistente prepara un promemoria browser 10 minuti prima. Le date e gli orari visibili sono mostrati in ora italiana, fuso `Europe/Rome`.

Limite operativo: il promemoria frontend funziona mentre IUSENTRA resta aperto. Per notifiche garantite anche con browser o scheda chiusi servirà una fase successiva con salvataggio backend, integrazione Agenda, service worker e Web Push.

## Dettatura unica sul campo attivo

Dal 13 giugno 2026 la dettatura non deve essere progettata come un microfono separato per ogni campo. IUSENTRA usa un servizio unico, esposto in pagina come `window.IusentraVoiceInput` e alimentato dallo stesso motore di `PctLexVoice`.

Logica operativa:

1. l'avvocato seleziona il campo, l'area di ricerca o l'editor in cui vuole scrivere;
2. se la sessione operativa non è attiva, pronuncia prima "Studio"; poi usa "scrivi qui", "detta" o una variante contestuale come "detta cliente", "detta soggetto", "detta scadenza", "detta agenda" o "detta ricerca";
3. l'assistente controlla il microfono una sola volta, tramite lo stesso servizio usato da Lex AI;
4. il testo viene trascritto, normalizzato con punteggiatura italiana e inserito nel campo selezionato;
5. se il pannello vocale prende il focus, il servizio usa l'ultimo campo valido selezionato, così non perde il punto di scrittura.

Con sessione operativa già attiva, il comando esplicito non è obbligatorio per ogni campo: se la frase pronunciata non corrisponde a un comando autorizzato e c'è un campo valido selezionato, IUSENTRA la tratta come testo dettato e prova a inserirla direttamente in quel campo. I comandi riconosciuti, come "apri clienti" o "nuovo cliente", restano prioritari rispetto alla dettatura libera.

Aree coperte dal modello strutturale:

- Clienti e nuovo cliente, per campi anagrafici e note;
- Soggetti e parti, per campi anagrafici e descrittivi;
- Scadenziario e nuova scadenza, per oggetto, descrizione e annotazioni;
- Agenda e nuovo appuntamento, per titolo, luogo, descrizione e note;
- Ricerca Studio e ricerca globale, per testo di ricerca;
- email ordinaria, PEC, messaggi e comunicazioni;
- Lex AI, editor documento, editor professionale e template atti.

Il servizio centrale deve restare leggero e performante: nessuna inizializzazione pesante per ogni campo, nessun secondo controllo permessi in Lex, nessun microfono duplicato su ogni input. I singoli editor possono usare il proprio comando di inserimento interno, ma il controllo microfono, la trascrizione e la normalizzazione devono passare dallo stesso servizio comune.

Regola di test: la dettatura unica va verificata su Chrome reale e sulla copia locale `http://127.0.0.1:8080`, selezionando materialmente campi di Clienti/Soggetti, Scadenziario, Agenda e Ricerca Studio, poi usando il comando vocale o il pulsante editor e controllando che il testo appaia nel campo corretto.

## Audit reale del 13 giugno 2026

Esito locale su Docker reale `http://127.0.0.1:8080`, versione `2.253.3`:

- catalogo aggiornato: 390 frasi riconosciute, 350 frasi aggiunte, 59 destinazioni e 11 azioni rapide;
- Docker locale ricostruito con `--no-cache`, container `app`, `scheduler-worker` e `ocr-worker` healthy;
- `/api/pronto` risponde con `ok=true` e versione `2.253.3`;
- Google Chrome installato su Windows confermato dall'utente sulla macchina reale: il microfono funziona dopo la correzione e la prova materiale;
- l'ascolto deve restare attivo nella stessa scheda dopo cambio pagina e deve spegnersi solo con disattivazione esplicita o revoca reale del microfono;
- il prompt del PIN vocale deve essere parlato prima dell'ascolto del codice; PIN errato o non letto richiede una nuova ripetizione;
- hotfix successivo della prova reale: il click su "Attiva ascolto" ora deve pronunciare anche l'avviso di controllo tono prima del campione; la soglia del tono è stata resa più prudente per non respingere una voce reale quando Chrome ha già concesso e usa il microfono;
- aggiunti comandi "modifica cliente", "modifica clienti", "modifica soggetto" e "modifica soggetti e parti";
- il servizio unico resta il riferimento per Studio, Lex AI, editor documento, editor professionale, template atti e campi attivi di Clienti, Soggetti, Scadenziario, Agenda e Ricerca Studio;
- resta da ripetere a ogni modifica successiva la prova materiale dei singoli campi: selezione campo, richiamo "Studio" se serve, comando "scrivi qui" o variante contestuale, testo inserito e pannello che resta chiuso se l'avvocato lo ha chiuso.

## Verifiche obbligatorie

Gate mirati:

- `node frontend\scripts\check-studio-voice-assistant.mjs`;
- `python -m pytest tests\test_studio_voice_assistant.py -q --tb=short`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- Docker reale su `http://127.0.0.1:8080`;
- browser desktop, tablet e mobile sulla copia reale `8080`.

La prova browser automatizzata può usare microfono e riconoscimento sintetici in pagina per rendere ripetibili voce, PIN e comandi senza dipendere dal microfono fisico della macchina. La verifica finale deve comunque osservare l'interfaccia reale e controllare testi, pulsanti, layout, overflow, console e destinazioni aperte.

Per rilanciare l'audit CDP usare un utente locale temporaneo autorizzato nello studio di prova e passare la password con `IUSENTRA_VOICE_E2E_PASSWORD`; la password non è salvata nello script né nei report.

## Audit reale visibile del 13 giugno 2026, versione 2.253.4

Esito sulla copia Docker reale `http://127.0.0.1:8080`, container healthy e `/api/pronto` con versione `2.253.4`.

- Browser usato: Google Chrome installato `C:/Program Files/Google/Chrome/Application/chrome.exe`, aperto in modo visibile sulla macchina locale.
- Permesso microfono osservato da Chrome: `granted`; il pannello non mostrava più lo sblocco microfono.
- Audit ripetibile con riconoscimento vocale pilotato in pagina per poter eseguire autonomamente PIN, comandi e dettatura senza voce umana dell'utente. Non va confuso con una nuova lettura fisica umana del tono di voce.
- Registrazione profilo/PIN: UI con voce registrata, calibrazione di 30 secondi completata, PIN parlato dal flusso e richiamo pronto.
- Flusso operativo: dopo PIN il sistema resta in richiamo; pronunciando "Studio" entra in sessione operativa e i comandi successivi funzionano senza ripetere "Studio".
- Note vocali: comando personalizzato `appunti`, nota "domani alle 18", evento visualizzato `14 giu 2026, 18:00`, promemoria `14 giu 2026, 17:50`, fuso "Roma" e notifica browser simulata/registrata nel pannello.
- Responsive: desktop `1365x768`, tablet `820x1180`, mobile `390x844`; nessun overflow orizzontale, nessun pulsante vuoto, nessun testo richiesto mancante.
- Dettatura in campi reali su `/clienti/nuovo`: `Mario`, telefono `00100`, CAP `00100`, numero documento `CA61007P`, email `antmm2605@gmail.com`, PEC `studio-legale@example.com`, sito `www.marco.rossi.it`, data nascita `2026-06-13`, data rilascio `2026-06-07`, sesso `F`.
- Ricerca vocale in sessione operativa: "cerca Rossi" apre `/global-search?q=rossi`, senza ripetere la parola di attivazione.
- Nuovo cliente vocale: il flusso chiede nome, cognome e codice fiscale, rilegge i dati, salva solo dopo conferma, poi il cliente di prova viene eliminato tramite API.
- Disattivazione e riattivazione: "disattiva assistente" spegne l'ascolto; il test riapre Configurazione, ripete PIN e "Studio" prima di verificare le 59 destinazioni vocali.
- Tutte le 59 destinazioni vocali sono state aperte, con 390 frasi in catalogo e zero failure nel report `artifacts/react-migration/studio-voice-assistant-browser-audit.json`.

Difetti trovati durante l'audit e corretti prima dell'esito positivo:

- `doc_numero` non veniva riconosciuto come campo numero documento: aggiunti alias `doc_numero` e `numero_doc` alla normalizzazione.
- "cerca Rossi" senza "Studio" non era accettato in sessione operativa: aggiunti prefissi ricerca `cerca`, `trova` e `ricerca`.
- Dopo una disattivazione completa, l'audit parlava prima che il richiamo fosse pronto: lo script ora torna su Configurazione, attende il PIN e il richiamo, poi pronuncia "Studio".

Caso noto post-deploy: la build Vite resta verde ma segnala il chunk principale `index-D9Xs3IhZ.js` a `503,51 kB` minificato. Va trattato dopo il deploy con una tranche dedicata di code splitting, misurazione asset reali e nuova verifica di caricamento sulla copia reale.

## Audit reale del 12 giugno 2026

Esito locale su Docker reale `http://127.0.0.1:8080`, versione `2.253.1`:

- catalogo verificato: 330 frasi, 290 frasi aggiunte e 59 destinazioni;
- pannello aperto materialmente nel browser integrato, con scroll completo del pannello e verifica visiva di testi, pulsanti, card, frase consigliata e layout desktop;
- frase di attivazione personalizzata in "Studio Legale", ricaricata e riletta correttamente dopo refresh;
- registrazione profilo voce e PIN: il click reale su "Registra voce e PIN" è stato eseguito, ma il browser ha negato il microfono. Esito visibile: "Microfono non autorizzato. Consenti il microfono dal browser, poi reinserisci il PIN e premi di nuovo Registra voce e PIN.";
- con microfono negato il profilo non viene salvato: dopo il tentativo resta visibile "Registra voce e PIN" e non "Attiva ascolto";
- PIN di registrazione e verifica mascherati in UI e svuotati dopo errore di registrazione;
- la registrazione effettiva di 30 secondi e il salvataggio reale del tono restano bloccati finché il browser non concede il permesso microfono;
- comandi speciali verificati: ricerca `Studio cerca Rossi`, Lex AI, aiuto, indietro, ricarica e disattivazione;
- flusso "nuovo cliente" verificato: nome, cognome, codice fiscale, rilettura, conferma, salvataggio reale e pulizia del cliente di test;
- tutte le 59 destinazioni vocali aperte realmente da comando vocale, senza errori console, overflow orizzontale o termini tecnici vietati;
- responsive verificato su desktop `1365x768`, tablet `820x1180` e mobile `390x844`;
- baseline visuale su Panoramica, Fascicoli, Statistiche, Contatti Sito Studio e Builder Sito: 15 controlli verdi.

Report prodotti:

- `artifacts/react-migration/studio-voice-assistant-browser-audit.json`;
- `artifacts/react-migration/studio-voice-assistant-desktop.png`;
- `artifacts/react-migration/studio-voice-assistant-mobile.png`;
- `artifacts/react-migration/visual-2.253.1-studio-voice-performance/visual-load-audit.md`.
