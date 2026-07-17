# Fatturazione, proforma e impostazioni - 13 luglio 2026

## Obiettivo

Rendere il flusso economico dello studio semplice e governato: creazione esplicita della proforma, dati fiscali precompilati dalle impostazioni dello studio, modifica nel documento prima del salvataggio e distinzione corretta tra persona fisica e soggetto giuridico.

## Correzioni applicate

- Il comando principale e l'azione rapida dell'archivio indicano `Nuova proforma` e aprono il form React corrispondente.
- I pannelli descrittivi tecnici non necessari sono stati rimossi dal percorso operativo dell'avvocato.
- Per una persona fisica il destinatario usa `Nome` e `Cognome`; `Denominazione` resta riservata a studi, società ed enti.
- I vecchi dati in cui la denominazione ripeteva nome e cognome vengono normalizzati anche durante la generazione XML, senza duplicare il nominativo.
- Il CAP dello studio viene ricavato dai dati territoriali già disponibili quando comune e indirizzo lo consentono; nessun CAP viene inventato se mancano i dati del destinatario.
- Le coordinate di pagamento comprendono beneficiario, banca, IBAN e BIC/SWIFT.
- Il BIC/SWIFT è configurabile nella sezione `Fatturazione` delle Impostazioni Studio, accetta soltanto 8 o 11 caratteri alfanumerici ed è proposto nelle nuove proforme.
- Il pannello delle impostazioni governa regime fiscale, IVA, Cassa Forense, ritenuta, bollo, spese generali, metodo e scadenza di pagamento.
- Le proforme non trasmesse possono essere riallineate ai nuovi valori predefiniti tramite conferma esplicita; i documenti annullati o già trasmessi non vengono modificati.
- Il salvataggio verifica la persistenza del documento e riapre il dettaglio React; il flusso non usa pagine legacy come percorso operativo.
- Dal controllo economico del fascicolo è disponibile la generazione governata della proforma, con presidio contro i duplicati e apertura del documento già esistente quando presente.

## Struttura dati e sicurezza tenant

- Le impostazioni operative sono lette dal repository SQL tenant-aware; il file di configurazione resta un mirror controllato.
- L'identità dello studio non viene accettata dal payload del browser: viene ricostruita dalla sessione e dal tenant sul server.
- I valori fiscali sono validati sia nel form sia nell'API.
- La generazione FatturaPA mantiene i formati macchina previsti dallo schema XML; la UI e i documenti leggibili usano importi e date in formato italiano.
- Nessun dato di un altro studio viene usato come ripiego.

## Guardrail automatici eseguiti

- `python -m py_compile` sui moduli modificati: superato.
- `python -m compileall -q pct web scripts tools`: superato.
- `npm --prefix frontend run typecheck`: superato.
- `npm --prefix frontend run build`: superato, bundle React `index-Bk0DD0Pc.js` e stile `style-B_Zu55JL.css`.
- `python -m pytest -q tests/test_react_fatturazione_bridge.py tests/test_fattura_pa.py`: 20 test superati.
- Copertura specifica: separazione nome/cognome, riparazione snapshot storico, BIC/SWIFT nel profilo e nell'XML, assenza dei pannelli tecnici rimossi.

## Prova reale in produzione

Pagina: `https://app.iusentra.it/fatturazione/nuova?documento_operativo=PROFORMA`

- Accesso reale allo studio e caricamento della pagina `Nuova proforma`.
- Click reale del comando principale `Nuova proforma` dall'archivio: destinazione corretta e nessun errore console.
- Selezione reale di una persona fisica: `Giovanna` nel campo Nome e `Alessi` nel campo Cognome, senza duplicazione.
- Click reale `Ricarica anagrafica cliente`: nome, cognome e CAP restano coerenti.
- Studio mostrato come denominazione e CAP `89029` compilato.
- Campo `BIC o SWIFT` presente nel documento e nelle Impostazioni Studio.
- Click reali tra `Dati Studio` e `Fatturazione`; focus tastiera verificato sul campo BIC/SWIFT.
- Viewport mobile: nessun overflow orizzontale; scroll materiale dall'inizio al centro e fino al fondo; comando `Crea proforma` raggiungibile.
- Nessuna proforma creata, nessuna fattura emessa e nessun dato bancario fittizio salvato.
- Server: unico container applicativo `iusentra-app`, healthy; `/api/pronto` restituisce `ok: true` e fuso `Europe/Rome`.

## Prova reale locale

Pagina: `http://127.0.0.1:8080/fatturazione/nuova?documento_operativo=PROFORMA`

- Docker locale ricostruito con app, scheduler e worker OCR healthy.
- Caso esatto segnalato verificato con click reale: `Alessi Robertino` produce `Nome: Robertino` e `Cognome: Alessi`.
- Il destinatario non possiede indirizzo o comune nell'anagrafica locale: il CAP resta vuoto correttamente; lo studio mostra `TAURIANOVA`, provincia `RC` e CAP `89029`.
- Impostazioni Fatturazione verificate a 390 x 844 e 1366 x 768: nessun overflow orizzontale, BIC/SWIFT leggibile e pulsante `Salva sezione` raggiungibile dopo scroll completo.
- I pannelli tecnici rimossi non sono presenti.

## Limite operativo preservato

Il BIC/SWIFT reale dello studio non era disponibile durante la prova. Il campo e la propagazione sono verificati, ma non è stato salvato un codice inventato. La prima compilazione deve usare il valore bancario effettivo dello studio.
