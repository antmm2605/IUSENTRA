# Prova reale server deposito fascicolo E5AE4668

Data incarico: 16 giugno 2026.

Questo file è la traccia operativa dell'incarico corrente e va riletto dopo ogni compattazione prima di proseguire sul deposito.

## Incarico ricevuto

- Ambiente di prova reale: `https://app.iusentra.it`.
- Fascicolo da usare: `E5AE4668`.
- Riferimento visibile: `2026/330`.
- Fascicolo: `Marchetti c. MIM`.
- Materia/oggetto: `Carta docente`.
- Area: civile/lavoro secondo il profilo deposito risolto dal software.
- Cliente: `Marchetti Lucia`.
- Accesso: credenziali fornite dall'utente per la sola prova; non vengono salvate in questo file.
- Interfaccia: React, senza percorsi legacy o fallback `?_legacy=1`.
- Vincolo esplicito: nessun backup per questa attività.
- Vincolo esplicito: nessun invio PEC reale e nessun deposito reale.

## Cosa deve essere verificato

1. Aprire sul server la pagina React del fascicolo e il percorso `Prepara deposito`.
2. Eseguire prova visiva reale con browser visibile: pagina iniziale, scroll completo, fasi deposito, pannelli, pulsanti, testi, card, responsive se il flusso richiede adattamenti.
   - Il controllo visivo deve includere card, testi, formattazione, layout, visibilità, bottoni, select, checkbox, stati di caricamento, stati di errore/successo e leggibilità completa dei campi.
   - Se un pannello è troppo denso o poco intuitivo, va corretto prima del report e riverificato nel browser.
   - Per il deposito la UI deve lavorare a fasi, con un pannello operativo alla volta, e il pannello documenti deve permettere di visualizzare tutti i documenti del fascicolo, selezionare quelli da inviare oppure inviarli tutti, classificarli come atto principale/procura/allegato/prova/fuori busta e indicare quelli da firmare.
3. Generare il pacchetto/busta di prova fermandosi prima dell'invio.
   - La prova deve comportarsi come deposito reale fino alla generazione busta, ma non deve procedere all'invio PEC reale.
   - La busta/pacchetto generato deve essere scaricato o ispezionato realmente, non solo dedotto dalla UI.
   - Il contenuto generato deve essere confrontato con i campioni reali e la normativa già acquisiti: ordine documenti, atto principale, procura, allegati/prove, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, oggetto/contenuto email e presenza/assenza di `Atto.enc`.
4. Verificare che siano generati o mostrati:
   - proposta documenti;
   - atto principale;
   - allegati;
   - `DatiAtto.xml` o equivalente firmato se la firma avviene;
   - `IndiceDocumentiDepositati.PDF`;
   - contenuto/oggetto email di deposito se previsto dal flusso;
   - eventuale `Atto.enc` solo se realmente prodotto dall'adapter ministeriale.
5. Verificare che il flusso non registri un deposito come valido se manca `Atto.enc` AES256 ministeriale.
6. Verificare Local Signer su macchina reale:
   - rilevazione da pagina server;
   - versione e token;
   - comportamento di aggiornamento automatico;
   - chiusura delle istanze Local Signer duplicate o vecchie prima del riavvio;
   - firma multipla reale con PIN digitato al momento della firma e token fisico rilevato, senza simulare esiti.
7. Documentare con esito onesto cosa è stato visto, cosa è stato generato, cosa coincide con i depositi reali allegati dall'utente e cosa resta bloccante.

## Regole operative durante la prova

- Non salvare password, PIN, token o dati segreti in report, screenshot o file committati.
- Non cliccare comandi di invio PEC/deposito reale.
- Non creare backup e non cancellare dati applicativi.
- Se il server o la UI mostrano un problema, il problema prevale sui test automatici.
- Se la firma multipla non viene eseguita con PIN reale e salvataggio di più `.p7m`, non va dichiarata funzionante.
- Se il pacchetto prodotto è solo di controllo, va chiamato pacchetto di controllo e non busta ministeriale valida.

## Stato iniziale

- Incarico scritto.
- Prova server ancora da eseguire.
- Audit busta ancora da eseguire.
- Verifica multifirma ancora da eseguire.

## Aggiornamento codice 2.253.26 - 16 giugno 2026

Obiettivo dell'intervento: rendere il deposito più semplice, veloce, intuitivo e funzionale, con un percorso operativo a pannelli e con documenti gestiti in un unico slot documentale.

Modifiche applicate:

- la pagina React `Prepara deposito` usa una barra fasi e mantiene aperto un solo pannello alla volta;
- `Documenti da inviare` mostra l'intero fascicolo utile al deposito, non solo la proposta automatica;
- l'avvocato può selezionare singoli documenti, usare `Invia tutto`, correggere la classificazione e salvare prima del comando finale;
- la classificazione copre atto principale, procura, allegati, prove, prove di notifica e documenti fuori busta;
- il comando finale salva prima la classificazione visibile, poi avvia la firma multipla dei documenti realmente da firmare, poi prepara il pacchetto;
- lo stato `Firmato` non è più modificabile dalla UI: deriva solo dal documento reale o da un esito di firma salvato dal sistema;
- aggiunto endpoint protetto `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` collegato ai dati reali del fascicolo e agli slot deposito.

Guardrail già eseguiti:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest tests/test_regia_api_payloads.py tests/test_regia_ui_react.py tests/test_security_headers.py -q`;
- `pnpm --filter @iusentra/studio test`;
- `pnpm --filter @iusentra/studio build`;
- `python tools\sync_packaging_files.py --check`;
- `python scripts\react-migration\generate_api_contracts.py` e `--check`;
- `python scripts\validate_openapi.py docs\openapi.yaml`;
- `python scripts\verify_openapi_provider.py`;
- `python -m pytest tests\test_openapi_contracts_phase6.py -q --tb=short`;
- `python -m pytest tests\test_utf8_integrity.py -q --tb=short`.

Nota prestazionale: la build resta riuscita, ma segnala ancora il chunk principale React sopra 500 kB. Non blocca la correzione deposito, però resta debito da affrontare con una tranche di code splitting e baseline reale.

Chiarimento operativo dell'utente:

- la macchina locale deve essere aggiornata e deve rispondere su `127.0.0.1:8080/api/pronto`;
- la prova visiva con click, scroll completo e responsive deve essere svolta solo sul server reale `https://app.iusentra.it`, non sulla copia locale.

Stato non chiuso:

- versione `2.253.26` ancora da committare, pushare e distribuire;
- server `app.iusentra.it` ancora da verificare dopo deploy;
- macchina locale reale `127.0.0.1:8080` ancora da ricostruire e verificare tramite `/api/pronto`;
- busta/pacchetto dry-run ancora da generare e ispezionare senza invio PEC;
- firma multipla ancora da provare con PIN digitato al momento della firma, token fisico rilevato e salvataggio di più `.p7m`;
- nessun invio PEC reale deve essere eseguito durante la prova.

## Difetto rilevato nella prova server e hotfix 2.253.27

Durante la prova visiva reale sul server, URL `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#firma-busta`, il browser ha mostrato che i pannelli del deposito risultavano tutti aperti contemporaneamente. Questo non rispettava il requisito dell'utente: flusso semplice, veloce, intuitivo e con un solo pannello operativo alla volta.

Correzione applicata:

- `DetailSection` ora governa esplicitamente lo stato `open` del nodo `<details>` tramite React e riferimento DOM, così il browser non conserva stati aperti non voluti;
- gli approfondimenti secondari del deposito, come documenti candidati, catalogo portale e dati fascicolo, partono chiusi;
- il percorso principale resta concentrato sulle cinque fasi operative.

Guardrail rilanciati prima del nuovo deploy:

- `pnpm --filter @iusentra/studio typecheck`;
- `python -m pytest tests/test_regia_ui_react.py tests/test_regia_api_payloads.py tests/test_react_asset_retention.py -q --tb=short`;
- `pnpm --filter @iusentra/studio build`.

Stato da riverificare dopo deploy `2.253.27`:

- desktop: un solo pannello deposito aperto alla volta;
- tablet e mobile: assenza di overflow e testi leggibili;
- click reale sulle fasi `Documenti da inviare`, `Firma documenti`, `Busta e indice`;
- salvataggio classificazione e busta dry-run ancora da eseguire;
- firma multipla reale ancora non dichiarabile senza PIN digitato al momento della firma, token fisico rilevato e salvataggio dei `.p7m`.

## Correzione UI/lettore 2.253.28 - 16 giugno 2026

Problemi segnalati durante la prova visiva server:

- il rail `Slot documentali` restava troppo stretto: testo, select e pulsante `Collega` venivano compressi e la scheda non era leggibile;
- `Verifica operativa` e `Prepara controllo busta` sembravano non fare nulla perché il feedback era poco visibile;
- il deposito non appariva ancora come un percorso a step reale, perché la pagina lasciava visibili pannelli di supporto insieme alla fase attiva.

Correzione applicata:

- la pagina `Prepara deposito` ora mostra un solo pannello operativo alla volta sotto lo stepper;
- gli slot documentali sono stati spostati dentro la fase `Documenti da inviare`, con card larghe e form non compressi;
- le card di stato aprono le fasi reali (`Documenti`, `Firma`, `Inventario`) invece di puntare a sezioni tecniche di supporto;
- i pulsanti `Verifica operativa` e `Prepara controllo busta` mostrano lo stato `Operazione...`, registrano un messaggio visibile nel pannello e portano alla fase successiva coerente;
- aggiunto lettore globale per allegati `.pdf.p7m` di PEC ed email ordinaria: anteprima del PDF interno quando il contenitore CAdES lo espone, download sempre del `.p7m` originale;
- aggiunto nello Studio il pannello `Editor professionale` con accessi rapidi a redazione, modelli, ricerca documenti, fascicoli e Lex editor.

Stato da verificare dopo deploy `2.253.28`:

- server reale `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`: desktop/tablet/mobile, scroll completo, click sulle cinque fasi, click reale su `Verifica operativa` e `Prepara controllo busta`;
- il pannello `Slot documentali` deve essere leggibile, senza testo verticale o pulsanti tagliati;
- Studio deve mostrare `Editor professionale` e i collegamenti devono aprire le route previste;
- se sul server è disponibile un `.pdf.p7m`, l'anteprima deve mostrare il PDF interno; in ogni caso i test automatici devono confermare PEC ed email ordinaria;
- la firma multipla resta non dichiarabile verde finché non viene eseguita con PIN digitato al momento della firma, token fisico rilevato dal Local Signer, più documenti firmati, salvataggio `.p7m` e riabilitazione del passo successivo.

## Controllo approfondito ruoli documentali 2.253.29 - 16 giugno 2026

Problema segnalato durante la prova visiva server:

- nel menu ruolo compariva `Allegato / prova`, voce troppo ambigua per il lavoro dell'avvocato;
- gli slot documentali usavano spazio disponibile male, con testo e comandi ancora troppo compressi nella zona laterale;
- su visualizzazione laptop il rail laterale poteva risultare troppo stretto o sparire, mentre in fondo alla fase compariva una seconda copia dello stesso pannello `Slot documentali`;
- nei documenti selezionabili mancavano azioni immediate di visualizzazione/scarico vicino al documento, quindi l'avvocato non poteva controllare rapidamente cosa stava classificando.

Controllo fonti eseguito:

- pagina ufficiale PST `Specifiche Tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024`: alla data del controllo risultano il provvedimento 7 agosto 2024 e le rettifiche 16 settembre 2024 e 30 ottobre 2024;
- specifiche DGSIA 2024 salvate in `docs/specs/ministero/Specifiche_Tecniche_DGSIA_DM44_2011_2024_08_07.pdf`;
- DTD `IndiceBusta.dtd`: busta con `Atto` e `Allegato`, con tipi tecnici per allegato semplice, procura, dati atto, ricevute e PEC di notifica;
- direttive notifiche legali e matrice probatoria già salvate sotto `docs/specs/ministero`.

Regola corretta:

- menu visibile: `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- `Allegato / prova` non deve più comparire;
- `Prova notifica` resta solo per atto notificato, relata, PEC inviata, RAC/RdAC, ricevute ed evidenze richieste dal deposito prova;
- il valore storico interno `allegato_prova` è accettato solo come compatibilità e normalizzato a `Allegato`.

Correzione applicata nel codice:

- React normalizza il ruolo storico prima di mostrarlo, salvarlo e usarlo per soddisfare gli slot;
- backend `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` normalizza alias vecchi come `prova`, `documento_prova` e `allegato_prova` in `allegato`;
- aggiunti comandi `Visualizza` e `Scarica` direttamente sulle righe dei documenti da inviare;
- lo slot documentale resta in un solo pannello largo: laterale quando lo schermo lo consente, impilato come unico pannello quando la larghezza non basta, senza scroll interno e senza una seconda copia in fondo alla fase `Documenti da inviare`;
- la sidebar dell'app resta visibile nella fascia laptop, così durante il deposito non si perde la navigazione principale;
- aggiunto guardrail in `tests/test_regia_ui_react.py` per impedire il ritorno della voce `Allegato / prova`.

Stato da verificare dopo deploy `2.253.29`:

- sul server reale il menu ruolo non deve mostrare `Allegato / prova`;
- ogni documento ordinario deve proporre `Allegato`;
- le prove di notifica devono restare distinte;
- i pulsanti `Visualizza` e `Scarica` devono aprire/servire il documento corretto;
- il pannello `Slot documentali` deve comparire una sola volta, nel rail laterale largo o impilato come unico pannello su schermi più stretti, con testo e pulsanti leggibili;
- sul server non deve esistere una seconda sezione `Slot documentali` in fondo alla fase documenti;
- la prova visiva deve coprire desktop, tablet, mobile, scroll completo e click reali sui passaggi della fase deposito.

## Piano di chiusura totale 2.253.30 - 16 giugno 2026

Richiesta utente: aggiornare tutto il lavoro da fare e portare la tranche alla chiusura totale, senza falso verde. Dopo ogni compattazione questo file va riletto insieme ad `AGENTS.md`, `artifacts/data-flow/incarico-operativo-permanente.md` e `artifacts/react-migration/procedura-deposito-telematico.md`.

Perimetro da chiudere:

1. Deposito fascicolo server `E5AE4668`.
   - Correggere il menu ruolo che, quando aperto, risultava disallineato nella lista `Documenti da inviare`.
   - Il menu non deve usare la select nativa se questa produce popup fuori asse: deve aprirsi come pannello React ancorato alla riga, leggibile e cliccabile.
   - Il menu deve mostrare solo `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`.
   - `Allegato / prova` non deve tornare.

2. Editor professionale.
   - Deve comparire come voce autonoma nella nav sotto `Studio`.
   - Non deve sostituire né duplicare il significato di `Redazione Atti`.
   - `Redazione Atti` resta il modulo specifico per redigere atti.
   - `Editor professionale` è il centro operativo più ampio: scrittura, controllo, ricerca documenti, lettura firmati, fascicoli, PEC/email e Lex editor.
   - La route dedicata è `/editor-professionale`, full React, con contratto di migrazione e test.

3. Lettore documenti legali globale.
   - Estendere l'anteprima senza download a `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m`, oltre a `.pdf.p7m`.
   - Valere in tutto il software dove passano documenti/allegati: fascicolo, PEC ed email ordinaria.
   - Il download deve continuare a servire l'originale, soprattutto per i contenitori `.p7m`.
   - L'anteprima deve essere HTML sicuro, leggibile e in italiano, senza salvare audio o dati non richiesti.

4. Test automatici e audit tecnico.
   - Test React UI: nav `Editor professionale`, route `/editor-professionale`, menu ruolo custom, assenza `Allegato / prova`.
   - Test fascicolo: anteprima reale di XML, XML.P7M, EML e TXT.
   - Test PEC/email ordinaria: anteprima reale di XML, XML.P7M, EML e TXT, con download originale invariato.
   - Typecheck, test frontend, build Vite, gate contratti, UTF-8 integrity, test deposito/regia/email/fascicoli mirati.
   - Registrare esiti in `pytest-confirmed-ok.md` e problemi residui in `pytest-open-issues.md`.

5. Commit, push, GitHub e deploy.
   - Bump versione.
   - Worktree pulita prima del commit.
   - Commit sul branch `Codex/legal-electronic-filing-kIxcV`.
   - Push anche su `claude/legal-electronic-filing-kIxcV` allo stesso SHA.
   - Verificare tutti i check GitHub dello SHA corrente, inclusi CodeQL/code scanning.
   - Deploy Hetzner sul commit pushato, container healthy, `https://app.iusentra.it/api/pronto` OK.
   - Pulire cache Docker build Hetzner e snapshot temporaneo.
   - Ricostruire/allineare Docker locale su `127.0.0.1:8080` e verificare `/api/pronto`.

6. Prova reale e visiva sul server.
   - Browser reale visibile su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`.
   - Scroll completo dei pannelli, senza fermarsi alla prima vista.
   - Click reale su `Documenti da inviare`, apertura menu ruolo e verifica allineamento.
   - Click reale su `Editor professionale` dalla nav e verifica che la pagina sia distinta da `Redazione Atti`.
   - Test responsive server desktop, tablet e mobile.
   - Test apertura visuale dei formati disponibili o controllati: PDF/P7M, XML/XML.P7M, EML e TXT.
   - Test flusso deposito fino alla generazione/ispezione pacchetto senza invio PEC reale.
   - Se manca ancora `Atto.enc` ministeriale AES256, il report deve dire pacchetto di controllo, non deposito valido.

Stato attuale del piano: aperto. Non usare le parole completato, funzionante, verde o risolto finché i punti sopra non sono realmente verificati.

## Stato tecnico Local Signer e certificato 2.253.33 - 16 giugno 2026

- Aggiunto salvataggio della scadenza certificato nella configurazione `Firma Digitale` dello studio dopo verifica Local Signer.
- La UI React `Impostazioni > Firma Digitale` mostra `Certificato memorizzato`, data italiana, codice fiscale, intestatario, emittente e stato `mancano X giorni` quando il dato e' disponibile.
- Al login viene generato un avviso operativo se il certificato firma salvato scade entro 20 giorni, o se risulta gia' scaduto.
- Test automatici eseguiti: `test_impostazioni_firma_salva_scadenza_certificato_local_signer`, `test_avviso_login_certificato_firma_a_venti_giorni`, `test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale`, `test_diagnosi_windows_mostra_certificato_avvocato_selezionato`, `test_local_signer_ha_guardia_istanza_unica_e_diagnosi_certificato`.
- Prova reale ancora da eseguire dopo deploy/rebuild: click su `Verifica dispositivo collegato` in `Impostazioni > Firma Digitale` con Local Signer reale, salvataggio scadenza e controllo visivo della card.

## Stato tecnico Local Signer 2.253.32 - 16 giugno 2026

- Local Signer aggiornato a `1.6.74` per correggere la regressione percepita sulla diagnostica del certificato dell'avvocato.
- `/ping` continuava a restituire `certificato_windows_selezionato` con codice fiscale e scadenza; `/diagnosi` invece mostrava solo i primi certificati e poteva nascondere quello realmente scelto.
- Aggiunta visualizzazione diagnostica del certificato avvocato selezionato con codice fiscale e scadenza.
- Aggiunta guardia di istanza unica sul processo Local Signer per evitare piu' processi `pythonw.exe local_signer.py` sulla stessa porta.
- Verificati i conteggi reali dei cataloghi copiati nel pacchetto signer: 534 uffici ministeriali mappati, 13 non mappati, 1.781 voci PST civili e 1.416 penali.
- Nota interpretativa: `Catalogo pubblico uffici PST civile/penale copiato` significa catalogo PST pubblico del Local Signer, non copertura esclusiva di tutti i servizi telematici; PAT, PTT, PDP e altri flussi restano separati.

## Stato tecnico pre-commit 2.253.30 - 16 giugno 2026

Modifiche pronte per commit:

- menu ruolo deposito convertito da select nativa a pannello React ancorato alla riga;
- ruoli visibili limitati a `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- `Allegato / prova` escluso dalla UI e coperto da normalizzazione/test;
- `/editor-professionale` aggiunto come route full React autonoma, senza sostituire `Redazione Atti`;
- anteprima globale estesa a `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m`, `.pdf.p7m`;
- bundle React separato in chunk vendor e icone per evitare il warning sul chunk principale;
- governance repo rientrata dopo rimozione dei rami morti `.eml`/`.txt` nel preview fascicoli.

Verifiche tecniche locali già eseguite:

- TypeScript, frontend test, build Vite;
- OpenAPI generato, validato e provider verification;
- contratti React e route gate;
- test mirati deposito/regia, route Editor professionale, fascicoli, PEC, email ordinaria, UTF-8 e asset retention;
- audit dati/tenant/topbar su tenant locale reale senza repair;
- packaging, release readiness, governance repo, py_compile;
- quality gate `code` non usato come verde finale perché sullo stage completo segnala come protetti i file di versione che `AGENTS.md` impone di aggiornare.

Esito da non interpretare come accettazione utente:

- `python tools\codex_harness\run_codex_quality_gate.py --mode ui-support` fallisce perché tratta gli asset Vite committati in `web/static/react/assets` come directory protetta/fuori perimetro del supporto UI. Non è un esito positivo né viene usato come prova di funzionamento; resta registrato in `pytest-open-issues.md`.

Stato aperto obbligatorio:

- commit e push sui branch `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`;
- controlli GitHub dello SHA corrente, incluso `Code scanning results / CodeQL`;
- deploy Hetzner sullo stesso commit e verifica `https://app.iusentra.it/api/pronto`;
- ricostruzione Docker locale e verifica `http://127.0.0.1:8080/api/pronto`;
- prova visiva server su `E5AE4668` con scroll completo, menu ruolo aperto, responsive desktop/tablet/mobile, Editor professionale dalla nav e anteprime documentali disponibili;
- dry-run del pacchetto deposito senza invio PEC reale;
- firma multipla reale non dichiarabile finché non avviene prova con PIN digitato al momento della firma, token fisico rilevato e salvataggio di più `.p7m`.

## Hotfix deposito 2.253.34 - `Da firmare`, menu ruolo e layout laptop

Problemi confermati dalle schermate reali dell'utente:

- nella fase `Documenti da inviare`, la spunta `Da firmare` non era cliccabile;
- la firma multipla sembrava non reagire perché il comando finale non portava sempre l'avvocato nel pannello `Firma documenti` quando PIN o Local Signer non erano pronti;
- sui formati laptop la lista non distribuiva correttamente spazio, icone, ruolo e badge; alcuni elementi uscivano dal pannello;
- il menu ruolo doveva restare compatto e allineato alla riga, non aprirsi come pannello disassato.

Correzioni applicate a codice React:

- `frontend/src/components/FascicoliPage.tsx`: aggiunto `requiresSignature` alla classificazione deposito, payload `requires_signature`, filtro firma multipla sui soli documenti marcati da firmare e apertura automatica della fase `Firma documenti` in caso di blocco firma;
- `frontend/src/components/FascicoliPage.tsx`: spunta `Da firmare` resa cliccabile per i documenti non firmati; `Firmato` resta disabilitato e informativo;
- `frontend/src/components/FascicoliPage.css`: griglia riga deposito ridotta, azioni documento solo icone, controlli ruolo contenuti nella colonna, menu ruolo con altezza e z-index governati, regole dedicate per laptop sotto 1600 px.

Verifiche tecniche già eseguite:

- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build:vite`;
- `python -m pytest tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_collega_slot_e_metadati tests/test_regia_ui_react.py -q`.

Verifiche ancora obbligatorie prima della chiusura:

- commit e push branch gemelli;
- check GitHub dello SHA corrente, incluso CodeQL/code scanning;
- deploy Hetzner dello stesso SHA e `https://app.iusentra.it/api/pronto`;
- prova visiva reale server sul fascicolo `E5AE4668`: desktop/laptop, tablet, mobile, scroll completo, click su `Da firmare`, apertura menu ruolo, verifica che badge/testi/icone non escano dalla card;
- dry-run server senza invio PEC reale e audit del pacchetto;
- firma multipla reale solo con PIN/token reale e salvataggio di più `.p7m` nel fascicolo.
