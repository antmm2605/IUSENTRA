# Fascicolo: modulo originale e acquisizione da dispositivi

Data: 06/09/2026. Stato: lavoro aperto, accettazione hardware e distribuzione
finale non eseguite. Questo documento non attesta un deposito o una firma.

## Perimetro e riuso

Superficie full React del fascicolo locale `DD242366`, sezione Documenti e atti
e compilatore PDF Mediazione. Il procedimento usato per la prova visiva reca
il titolo «Prova tecnica mediazione — non depositare».

Il nuovo pannello usa il servizio WIA già presente nel Local Signer, l'API
`/api/v1/ui/document-tools/multipage` e il caricamento documentale esistente
`/fascicoli/{id}/documenti/carica`. Non modifica resolver PST, autenticazione
smart card, PIN, wizard, busta, firma singola/multipla o invii PEC. Il client
scanner è condiviso anche con Strumenti documentali: solo le letture di
disponibilità possono provare entrambi i nomi loopback; il comando WIA non
viene ripetuto automaticamente dopo una risposta incerta o negativa.

Non sono introdotte tabelle o mirror JSON. Il salvataggio confermato usa il
repository documenti tenant-aware già esistente, con SQL SQLite/PostgreSQL
come fonte operativa e audit `fascicoli.documento.carica`. La selezione del
fascicolo è un parametro esplicito ricavato dalla pagina, non un valore globale.
La nuova acquisizione non è stata ancora salvata materialmente in alcun
fascicolo; la parità del percorso di persistenza è riuso architetturale, non
una nuova prova end-to-end positiva.

## Modulo originale: comportamento e prova reale

- Pulsante testuale «Tutto schermo» nell'intestazione del compilatore.
- «Vista normale» ed Esc ripristinano la vista e il focus sul comando.
- Nessun rimontaggio, nuova scheda, invio o rilettura dei campi al cambio vista.
- Larghezza iniziale della pagina 800 px; zoom 50–200%, con ripristino a 100%.
  Documento e campi sovrapposti conservano le proporzioni del PDF originale.
- API fullscreen nativa quando disponibile; espansione interna equivalente
  negli ambienti incorporati che non la concedono. Il contenuto resta lo stesso.

Prova materiale nel browser integrato visibile su `127.0.0.1:8080`, stessa
sessione autenticata dell'utente: click su apertura e ritorno, Esc, riapertura
da tastiera con Invio, zoom 75% e ripristino 100%, scorrimento del foglio fino
al fondo. Pagina selezionata e un testo temporaneo non salvato sono rimasti
presenti tra le viste. Il testo di prova è stato poi rimosso; nessuna copia
compilata è stata salvata e nessun documento è stato inviato. La schermata
fullscreen osservata occupava 1936×1048 pixel; titolo, comandi e salvataggio
rimanevano visibili, con il foglio centrato.

La scheda originale dell'utente non è stata ricaricata perché contiene campi
non salvati: continua quindi a mostrare il vecchio bundle finché l'utente non
conserva le proprie modifiche. La dimostrazione aggiornata è in una scheda di
verifica della stessa copia locale. Tablet/mobile e hover materiale non sono
stati verificati; non si assume accettazione da screenshot o emulazione.

## Acquisizione: confini operativi

1. L'avvocato avvia scanner, webcam oppure fotocamera del telefono.
2. Ogni immagine viene decodificata e ricodificata in JPEG: orientamento EXIF
   applicato, metadati di posizione non copiati. Limiti: 60 MB per file in
   ingresso, 50 megapixel, 80 pagine e 180 MB complessivi.
3. Le pagine restano nella memoria del browser, con anteprima, rotazione,
   riordino e rimozione. La chiusura richiede conferma dello scarto.
4. «Prepara PDF da verificare» produce una risposta PDF in memoria dal server,
   senza creare un documento nel fascicolo. Viene mostrata l'anteprima interna.
5. Solo dopo revisione esplicita si abilita «Conferma e salva nel fascicolo».
   Il client richiede `ok=true` e un ID documento persistito prima del successo.

Audio e registrazione video non sono richiesti. Le tracce della fotocamera
vengono fermate alla chiusura, al cambio di scheda o alla chiusura della sezione
Documenti; anche una concessione tardiva del permesso dopo la chiusura viene
rilasciata. Non vengono scritti file nella cartella Download del PC.

Prova reale: il click «Scanner Windows» ha restituito il messaggio
«Acquisizione annullata o scanner non disponibile». Il controllo WIA in lettura
non ha enumerato dispositivi. Il click «Webcam / fotocamera» ha mostrato la
richiesta di consentire la fotocamera, senza ottenere un'immagine. La richiesta
è stata annullata ricaricando solo la nostra scheda di prova priva di pagine
acquisite; non è stata aggirata alcuna autorizzazione del browser o di Windows.
Acquisizione hardware, qualità delle immagini, anteprima PDF finale e salvataggio
del PDF nel fascicolo corretto: **non verificato su macchina reale**.

## Controlli tecnici eseguiti

- `node --test tests/js/document_capture.test.mjs`: 11 test superati.
  Payload non validi, probe loopback, comando scanner unico, annullamento,
  servizio assente, click simultanei, limiti immagini, normalizzazione pixel,
  rilascio bitmap, HTML/risposte vuote, ordine/rotazioni, ID fascicolo e CSRF.
- `python -m pytest tests/test_document_capture_contracts.py tests/test_document_tools.py -q --no-cov`:
  12 test superati. Sono guardrail tecnici, non prove hardware.
- `npm --prefix frontend run build`: typecheck e build superati, 2281 moduli,
  Vite circa 1,46 secondi. La dimensione del chunk Fascicoli è passata da
  358,63 a 356,89 kB nel ciclo di estrazione del client scanner condiviso;
  non è una misura del tempo percepito di apertura della pagina.
- I nuovi test Node sono collegati al comando test frontend già eseguito in CI.
- `npm --prefix frontend test`: catena frontend superata dopo aver registrato
  i due fogli di stile e gli stili dinamici di geometria nella governance. I
  bordi laterali spessi preesistenti nel nuovo CSS Mediazione sono stati
  sostituiti con bordi completi sottili, senza eccezioni ai pattern vietati.
- `tests/test_utf8_integrity.py`: 4 test superati.
- Il gate tooling `run_codex_quality_gate.py --mode ui-support` non è superato:
  la sua verifica di perimetro respinge il worktree applicativo, che contiene
  anche numerose modifiche pregresse estranee al solo supporto UI. Dipendenze,
  guardrail AGENTS e Open Design sono passati. Non è stata indebolita la policy
  e non è stato dichiarato superato il gate complessivo.

Asset aggiornati sulla copia Docker locale per la prova rapida. Nessun commit,
push o deploy di produzione eseguito per questa tranche; rebuild definitivo,
campagna reale completa e allineamento dei tre ambienti restano da eseguire.

## Fonti tecniche consultate

- Permessi e contesto sicuro della fotocamera:
  https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- Acquisizione da dispositivo mobile:
  https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture
- Arresto delle tracce:
  https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamTrack/stop

La funzione non interpreta norme, non certifica conformità del documento,
non appone firme e non invia istanze. La skill Impeccable ha orientato il riuso
dei controlli esistenti, l'espansione senza perdita dei campi e l'acquisizione
inline con conferma distinta dal salvataggio.
