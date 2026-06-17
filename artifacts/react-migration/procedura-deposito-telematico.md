# Procedura deposito telematico IUSENTRA

Aggiornato: 2026-06-17.

## Aggiornamento 2026-06-17 - profilo deposito SQL da preventivo a fascicolo

Data intervento: 2026-06-17.

Regola dati applicata:

- la fonte operativa è sempre SQL: `studio.db` in locale e PostgreSQL in produzione;
- i JSON tenant-aware restano solo mirror, bootstrap, import/export storico o cache rigenerabile;
- il profilo deposito non deve restare nascosto solo in `dati_json`: deve essere salvato anche nella colonna dedicata `profilo_deposito_json`;
- la colonna dedicata esiste e viene riallineata su `fascicoli`, `preventivi_records` e `conferimenti_records`, sia per SQLite sia per PostgreSQL;
- `StudioDB.ensure_schema()` applica l'upgrade idempotente anche su database già esistenti, così i tenant attivi non restano con una struttura vecchia dopo il deploy.

Flusso operativo deciso:

- quando nasce un preventivo o un fascicolo veloce, IUSENTRA prova a risolvere subito canale, regola canale, codice deposito, ufficio giudiziario, PEC ufficiale e certificato di cifratura `.cer` quando il canale lo richiede;
- quando il preventivo viene accettato, il profilo passa al conferimento incarico;
- quando dal conferimento incarico nasce il fascicolo, il profilo passa al fascicolo e viene rafforzato con i dati effettivi del fascicolo, in particolare ufficio giudiziario e codice deposito;
- la stessa logica vale anche per `Nuovo Fascicolo` e `Fascicolo veloce` autonomi: anche se non nascono da preventivo o conferimento, devono risolvere canale, regole, codice deposito, PEC ufficio, ufficio giudiziario e certificato `.cer` quando richiesto;
- il fascicolo non deve perdere il profilo se viene creato da preventivo, da conferimento, da form nuovo fascicolo o da fascicolo veloce;
- PAT, PTT e PDP sono canali distinti: non devono usare in modo improprio il certificato PST civile, ma devono avere regole dedicate e stato di validazione separato.

Fonti ufficiali rilette per la matrice canali:

- Portale Servizi Telematici del Ministero della Giustizia, documentazione e servizi PCT/PDP;
- Giustizia Amministrativa, sezione Processo Amministrativo Telematico;
- Dipartimento della Giustizia Tributaria, sezione Processo Tributario Telematico PTT/SIGIT.

Guardrail tecnici eseguiti:

- `python -m pytest tests/test_profilo_deposito.py -q`;
- `python -m pytest tests/test_profilo_deposito.py tests/test_canali_telematici_deposito.py tests/test_busta.py tests/test_simulazione_deposito.py tests/test_deposito_server_dry_run_audit.py tests/test_scheduler_registry.py -q`.

Guardrail aggiunto dopo chiarimento utente:

- `test_fascicolo_autonomo_risolve_profilo_deposito_senza_preventivo` crea un fascicolo diretto senza preventivo/conferimento e verifica canale PCT, codice `222050`, PEC del Tribunale di Vicenza, certificato `.cer` verificato e colonna SQL `profilo_deposito_json` popolata.

Stato prova reale:

- non verificato su macchina reale in questa tranche: le prove sopra sono guardrail tecnici e non sostituiscono la verifica visiva/server richiesta dall'utente;
- prima della chiusura restano obbligatori build, prova reale su server/locale secondo incarico, commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner e igiene repository.

Aggiornamento operativo 2.253.45:

- rilanciato il blocco mirato deposito/canali/busta/scheduler e il guardrail React deposito dopo il chiarimento sul fascicolo autonomo;
- aggiunto il presidio documento per documento sulla firma digitale: `Firmato` in UI deriva solo da contenitore CAdES (`.p7m`/PKCS#7) o da prova tecnica PAdES salvata nel fascicolo;
- un file `.PDF` resta `Da firmare` se contiene solo testo o nome con "Firmato", oppure solo il vecchio flag `firmato`/`signed`, senza firma PAdES interna verificabile;
- la route di upload firma ora rifiuta PDF non PAdES e `.p7m` non CAdES, e salva nel fascicolo un metadato tecnico `signature_metadata` quando la firma è provata;
- se `studio.db` è vuoto, il JSON configurato viene usato solo per bootstrap controllato e poi rigenerato come mirror dopo il salvataggio SQL;
- confermati `pnpm --filter @iusentra/studio build`, retention asset React, packaging e `git diff --check`;
- il PIN fornito dall'utente per la firma reale non è stato scritto in file né log applicativi e va usato solo durante la prova materiale in UI;
- la chiusura resta subordinata a prova reale su `127.0.0.1:8080`, commit/push branch gemelli, CI/CodeQL, deploy Hetzner, health e prune Docker.

## Aggiornamento 2.253.44 - presidio CI SQL prima della prova server

Data intervento: 2026-06-17.

Stato operativo:

- rilevata sullo SHA `0f3a8eb` una failure di `Pytest core fase 6/10 parte 9/16`;
- corretto il presidio: il test semina `studio.db` con record SQL reali e svuota i JSON mirror per confermare che l'attivazione SQLite resti no-op SQL e non cancelli dati;
- verifiche locali verdi: shard 6/10 parte 9/16, test mirato e `tests/test_database.py` completo.

La prova deposito server resta aperta: non e' chiusa finche' non vengono verificati visivamente su `https://app.iusentra.it` selezione documenti, firma multipla Local Signer con PIN/token reale, creazione busta, indice documenti, testo email e dry-run senza invio PEC.

## Aggiornamento 2.253.43 - gate CI prima della prova server

Data intervento: 2026-06-17.

Stato operativo:

- il deposito e la firma multipla restano aperti fino alla prova visiva reale su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- prima della prova server e del deploy finale sono stati chiusi localmente i due rossi GitHub rimasti sullo SHA precedente: `Pytest core fase 6/10 parte 10/16` e `Pytest core fase 10/10`;
- il test database amministrazione ora conferma la regola `SQL operativo`: quando `studio.db` e' popolato, i JSON non sono piu' fonte vera ma mirror;
- i test Lex/Local AI usano un servizio applicativo finto ma conforme a `LexResponse` solo nei casi in cui devono verificare prompt, policy, follow-up e allegati, evitando timeout non pertinenti al deposito.

Guardrail tecnici confermati:

- `python -m pytest -q tests/test_local_ai.py --durations=10`;
- `python -m pytest -q tests\test_assistente_followup.py --durations=10`;
- `python -m pytest -q tests\test_web_bootstrap.py --durations=10`;
- `python scripts\run_pytest_phases.py --core-shard 6 --core-total-shards 10 --core-subshard 10 --core-total-subshards 16 --core-subdivide-items --timeout-minutes 5`;
- `python scripts\run_pytest_phases.py --core-shard 10 --core-total-shards 10 --core-subshard 1 --core-total-subshards 1 --timeout-minutes 5`.

Da fare prima della chiusura:

- commit e push dei branch gemelli;
- attesa completa dei gate GitHub, incluso `Code scanning results / CodeQL`;
- deploy Hetzner sullo stesso commit;
- verifica server con browser reale, scroll completo, dry-run deposito senza invio PEC e prova firma multipla reale con PIN/token.

Questo file va riletto prima di ogni intervento su `Prepara deposito`, busta, firma multipla, notifiche legali, portali telematici, agenda/scadenziario collegati a PEC e ricevute. Non sostituisce `AGENTS.md`: lo integra come memoria operativa specifica del deposito.

## Aggiornamento 2026-06-17 - hotfix CI dopo prova server deposito

Il primo push del lavoro deposito ha lasciato GitHub rosso sullo SHA `499e156` anche se la prova server hotfix era stata eseguita. Il lavoro non è considerato chiuso finché il nuovo SHA non passa CI/CodeQL, deploy Hetzner e riallineamento locale.

Correzioni applicate:

- la pre-verifica SQLite non confronta più `Impostazioni` come JSON grezzo: per gli studi SQL usa le sezioni normalizzate `settings_config`, così i JSON storici restano bootstrap/mirror e non diventano fonte di verità;
- il blocco anti-perdita resta operativo per dati core come clienti, fascicoli, agenda, scadenze, soggetti e comunicazioni;
- la route amministrativa database è stata alleggerita spostando l'ottimizzazione SQLite in helper dedicato, senza cambiare il flusso visibile;
- OpenAPI e versione sono riallineati a `2.253.38`.

Test locali mirati eseguiti prima del nuovo rilascio:

- database/pre-verifica SQLite Impostazioni e anti-perdita dati core;
- governance repository;
- provider OpenAPI;
- smoke contratti App V2;
- test mirati deposito React, classificazione, UI e nomi `.p7m`.

Stato: da chiudere con nuovo commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, `/api/pronto` produzione, prune Docker e riallineamento Docker locale reale.

Nota successiva sullo SHA `116b3cf`: i gate SQL, governance, provider e CodeQL sono passati, ma il job `Local Signer e PKCS#11 (ubuntu-latest) parte 2/4` ha evidenziato un dist Local Signer non allineato al sorgente e un guardrail batch non aggiornato a `cert_thumbprint`. Il rilascio resta aperto finché il nuovo SHA non conferma anche la matrice Local Signer.

Nota successiva sullo SHA `9e0a776`: il fix precedente ha sbloccato il caso batch, ma la matrice remota ha segnalato anche `macos-latest` parte 3/4 sulla firma singola. Sono stati aggiornati i guardrail di firma singola e batch; localmente sono passati tutti gli shard Local Signer/PKCS#11 1/4, 2/4, 3/4 e 4/4. Il rilascio resta comunque aperto fino al verde remoto, deploy e riallineamento locale.

Nota successiva sullo SHA `49f9d8c`: `Coverage moduli critici parte 4/12` ha segnalato un test obsoleto che pretendeva ancora il fallback a JSON quando SQLite non è disponibile. La regola definitiva resta: SQL va creato/riallineato; se non riesce, il flusso si blocca con messaggio chiaro e non usa JSON storici come verità operativa.

Nota successiva sullo SHA `995683b`: `Coverage moduli critici parte 10/12` ha segnalato una seconda migrazione falsa su archivi tenant vuoti come `privacy/registro.json`, anche se `studio.db` era già inizializzato. Il runtime ora riconosce `settings_config` e i mirror SQL come seed valido e non rilancia migrazioni inutili, mantenendo SQL come fonte operativa.

## Aggiornamento 2026-06-17 - prova server reale e fix rapidi UI deposito

Ambiente verificato: produzione `https://app.iusentra.it`, fascicolo reale `E5AE4668` (`2026/330 - Marchetti Lucia`), studio `studio-legale-giuseppe-montagnese`.

Interventi applicati prima sul server, come richiesto dal workflow server-first:

- corretto l'adattamento topbar su laptop: il pulsante `+ Nuovo` non viene più tagliato e `Assistenza remota` passa a icona compatta sotto 1600 px;
- corretto il widget Lex chiuso: su tablet/mobile non resta più sovrapposto al logo, alla topbar o alla lista deposito;
- corretto il menu `Ruolo` della lista `Documenti da inviare`: il menu resta allineato sotto il campo, non esce dalla card e ora si chiude con `Esc`;
- confermato che `Da firmare` funziona a menu chiuso e, dopo il fix `Esc`, anche subito dopo avere aperto/chiuso il menu ruolo;
- verificato che i documenti firmati vengono mostrati con estensione reale `.pdf.p7m` e microcopy `File firmato .p7m`, senza dichiarare firmato un PDF non firmato;
- verificato che il lettore apre un `.p7m` direttamente in anteprima, con titolo documento, pulsanti `Scarica` e `Chiudi`, senza obbligare l'avvocato a scaricare il file;
- verificata la pagina firma singola reale `/fascicoli/E5AE4668/documenti/1CE0BB0F/firma`: mostra di nuovo `Modalità firma visibile nel PDF`, posizione firma, luogo, data/ora, PIN token e `Firma tramite Local Signer`; non mostra più il pannello inutile `Riallinea automaticamente`.

Prove visive server eseguite con browser reale collegato alla sessione autenticata:

- desktop 1524x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- tablet 900x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- mobile 430x857: scroll alto, centro e fondo della pagina `Prepara deposito`;
- click reale del menu `Ruolo`: 1 menu aperto, rettangolo menu allineato al campo, voci `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- pressione `Esc`: menu aperto `1 -> 0`;
- click reale `Da firmare`: stato `true -> false -> true`;
- click reale `Visualizza` su `Autocertificazione ricorso.PDF.p7m`: visualizzatore aperto e contenuto PDF visibile;
- fase `Firma`: stato visibile `0 documenti da firmare` e `Firme coerenti`, senza `Local Signer non rilevato` e senza riallineamento inutile;
- fase `Busta e indice`: aperta con click reale dal percorso deposito, non con hash manuale; mostrati `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e documenti `.p7m` selezionati;
- click reale `Genera controllo e indice`, conferma modale `Prepara controllo`, download `Busta_2026-330_RICORSO.enc`.

Esito pacchetto scaricato nella prova server:

- file: `Busta_2026-330_RICORSO.enc`;
- dimensione download browser: 12.834.405 byte;
- SHA-256 locale della prova: `8d8c5f146970f480d179c7022ac885c90baf09c2a189bdf4deff3df62b7d2d94`;
- il file è un pacchetto di controllo leggibile come archivio zip, non un invio PEC e non va registrato come deposito valido ministeriale;
- voci presenti: `DatiAtto.xml`, `Autocertificazione ricorso.PDF.p7m`, `Autocertificazione situazione reddituale.PDF.p7m`, `Procura.PDF.p7m`, `IndiceDocumentiDepositati.PDF`;
- non è stata chiamata la route di invio PEC e nella UI non compare testo di PEC inviata.

Stato operativo:

- la parte server visibile del deposito è migliorata e provata sul fascicolo reale;
- resta obbligatorio riallineare la copia locale, eseguire build/gate mirati, aggiornare gli artefatti React, fare commit, push dei branch gemelli, controlli GitHub/CodeQL e deploy ordinato sullo stesso commit;
- il pacchetto generato è correttamente un pacchetto di controllo: finché manca l'adapter ministeriale per `Atto.enc` AES256, il software deve continuare a spiegare il limite e non deve presentarlo come deposito valido inviato.

## Regola utente non negoziabile

- Il deposito non va trattato come “fase finale guidata” da rinviare: il software deve risolvere subito tutto ciò che può risolvere.
- L’avvocato deve arrivare alla pagina `Prepara deposito` e vedere una proposta pronta, chiara e correggibile: atto principale, allegati, prove, ricevute, documenti da firmare, indice e canale.
- Se il software non riesce a classificare un documento con certezza, deve chiedere all’avvocato di selezionare/correggere solo quel punto, spiegando cosa manca e perché.
- Bloccano l’invio solo requisiti obbligatori previsti dal canale e dalla normativa. Le mancanze non obbligatorie sono avvisi professionali, non blocchi.
- Nessun blocco muto: ogni blocco deve indicare esattamente cosa manca e cosa deve fare l’avvocato per procedere.
- Non dichiarare la firma multipla funzionante finché, su `127.0.0.1:8080` con browser reale, l’utente non inserisce il PIN e il software firma più documenti nella stessa operazione, salva ogni `.p7m` nel fascicolo e abilita il passo successivo.
- Ogni intervento operativo su deposito, fascicolo, classificazione documenti, portali ministeriali, PEC, notifiche legali, firma digitale, Local Signer, PKCS#11, buste o ricevute deve essere trascritto in file. La traccia deve dire cosa è stato cambiato, quali fonti/norme sono state usate, quali test sono stati eseguiti, se la prova reale su `127.0.0.1:8080` è stata fatta oppure manca, e quali limiti restano aperti.

## Fonti ufficiali rilette il 2026-06-14

- PST, specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento DGSIA 7 agosto 2024.
- PST, formato messaggi PEC e flusso deposito: il depositante predispone atto e allegati; il software produce la busta telematica; la PEC trasporta la busta; RdA/RdAC/esiti vanno presidiati.
- PST, aggiornamento algoritmo cifratura busta telematica: introduzione AES256 per `Atto.msg` e dismissione 3DES; da febbraio 2026 i depositi non conformi ad AES256 diventano bloccanti.
- PST documentazione ufficiale: PDP penale è canale autonomo del difensore; non va confuso con sistemi interni degli uffici.
- Giustizia Amministrativa, PAT: dal 1 febbraio 2026 Formweb è canale prioritario; PEC è residuale e solo per casi tecnici previsti. Alcune istanze particolari restano temporaneamente a modulo PEC secondo avvisi ufficiali.
- Specifiche/istruzioni PAT: atti nativi digitali, PDF, firma PAdES per ricorso/modulo quando richiesto.

## Evidenza reale allegata dall’utente

File letti da `C:\Users\antmm\Downloads` il 2026-06-14:

- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso [JQ280-L01] [RefID_001_c3pnY4kBVA].EML`
  - allegati letti: `DatiAtto.xml.p7m`, `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `Procura.PDF`, prove documentali, ricevute PEC di notifica, `IndiceDocumentiDepositati.PDF`.
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso (originale notificato).pdf RG_ 1754 - 2026 [JQ280-L01] [RefID_001_zVNsJkqBF9]`
  - allegati letti: `DatiAtto.xml.p7m`, ricorso notificato, relata, ricevute di consegna/accettazione notifica, attestazione conformità, decreto fissazione udienza, procura, `IndiceDocumentiDepositati.PDF`.
- Depositi successivi reali letti: `Documento richiesto - prova interesse ad agire`, `Note scritte in sostituzione dell’udienza`, `Pagamento CU`, `Richiesta note scritte`, `Ricorso Contarino`.
  - nelle copie non crittografate è sempre presente `IndiceDocumentiDepositati.PDF`, anche quando l’invio contiene pochi documenti.
- Corrispondenti EML di invio reale letti:
  - contengono `Atto.enc` come allegato unico cifrato.

Conclusione operativa da questi file:

- La vista React deve mostrare tutti i documenti selezionati che entreranno nella busta.
- Il software deve generare sempre un indice documenti nel pacchetto preparato.
- Il pacchetto di controllo può contenere struttura verificabile, `DatiAtto.xml`/indice/documenti, ma non va presentato come deposito valido se manca `Atto.enc` ministeriale cifrato AES256.
- Un invio reale conforme PCT/SIGP richiede `Atto.enc`; le copie non crittografate servono come modello per controllare contenuto e indice.

## Caso reale PEC/EML JQ306-L01 fornito il 2026-06-16

L'utente ha fornito un esempio reale di deposito per chiarire la differenza tra copia non crittografata e PEC effettiva di deposito. I dati personali e gli indirizzi completi non vanno ricopiati nei report pubblici: la struttura tecnica invece diventa requisito operativo.

Schema osservato:

- la copia non crittografata ha oggetto `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: Ricorso [JQ306-L01] [RefID_...]`;
- la PEC effettiva ha oggetto `DEPOSITO TELEMATICO: Ricorso [JQ306-L01] [RefID_...]`;
- la PEC effettiva contiene come allegato operativo `Atto.enc` con MIME `application/octet-stream`;
- la copia non crittografata espone gli allegati leggibili o firmati indicati nel deposito, tra cui `DatiAtto.xml.p7m`, `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `Procura.PDF`, allegati documentali, ricevute/prove `.eml` quando incluse e `IndiceDocumentiDepositati.PDF`;
- il corpo del messaggio usa la formula al cancelliere e l'elenco puntuale dei file contenuti in `Atto.enc`;
- il riferimento `[JQ306-L01] [RefID_...]` va riportato nel corpo come riferimento da citare nella risposta;
- la data visibile della PEC è in ora italiana con offset `+0200`.

Regole software derivate dal caso reale:

- IUSENTRA deve produrre o mostrare chiaramente due oggetti distinti: `PEC effettiva di deposito` e `copia non crittografata di controllo`.
- La `PEC effettiva di deposito` non deve allegare singolarmente tutti i documenti: deve allegare `Atto.enc` quando l'adapter ministeriale è disponibile e conforme.
- La `copia non crittografata di controllo` deve servire a verificare contenuto, ordine, indice e allegati senza confonderla con l'invio valido.
- Il corpo del messaggio non deve essere duplicato: nell'esempio reale la visualizzazione mostra due volte la stessa formula/elenco; il software deve normalizzare la preview e generare un corpo unico, pulito e leggibile.
- La lista nel corpo deve coincidere con il contenuto della busta: atto principale, NIR quando presente, `DatiAtto.xml`/`DatiAtto.xml.p7m`, procura, allegati, prove PEC/EML e indice.
- I caratteri italiani devono restare UTF-8 validi: testi come `annualità` e virgolette italiane non devono diventare mojibake o caratteri sostitutivi.
- Gli allegati `.eml`, `.xml`, `.xml.p7m`, `.pdf.p7m` e `.txt` devono essere apribili in anteprima dal lettore globale, mantenendo il download dell'originale.
- Il validatore deve confrontare oggetto, destinatario ufficio, `Message-ID`, data, elenco allegati nel corpo, allegato `Atto.enc`, dimensione pacchetto e presenza dell'indice.
- Se viene generata solo la copia non crittografata o un pacchetto di controllo, la UI deve dire che non è ancora un deposito telematico valido e non deve registrare l'invio come completato.

Prova obbligatoria da eseguire sul server reale quando il flusso è pronto:

- generare il pacchetto del fascicolo reale senza invio PEC;
- verificare che la preview della PEC effettiva mostri `Atto.enc` come allegato unico;
- verificare che la copia non crittografata mostri gli allegati leggibili/firmati, `DatiAtto.xml.p7m` e `IndiceDocumentiDepositati.PDF`;
- verificare che il corpo non sia duplicato e che l'elenco dei file corrisponda esattamente alla busta;
- aprire visivamente almeno un `.eml`, un `.xml`/`.xml.p7m` e un `.pdf.p7m` dal lettore globale;
- fermarsi prima dell'invio PEC reale.

## Caso reale PEC/EML JQ332-L01 fornito il 2026-06-16

L'utente ha fornito tre ricevute reali collegate alla stessa busta di deposito. La struttura è stata verificata tramite `PecAuditRepository` sui file allegati alla conversazione, senza invio PEC e senza modificare dati di fascicolo.

Evidenza tecnica rilevata:

- la ricevuta `ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO` contiene `Codice esito: -1`, `IDBUSTA: 35508878`, `NOME FILE: DatiAtto.xml.p7m`;
- il testo ministeriale indica `Atto non conforme alle specifiche`, ma aggiunge che l'atto è in attesa di conferma della cancelleria, verrà comunque accettato e non è necessario effettuare nuovamente il deposito;
- le due ricevute successive `ACCETTAZIONE DEPOSITO TELEMATICO` contengono `Codice esito: 2`, lo stesso `IDBUSTA` e l'accettazione manuale avvenuta con successo;
- gli allegati di servizio osservati includono `EsitoAtto.xml`, `daticert.xml`, `postacert.eml` e `smime.p7s`.

Regola software derivata:

- `Codice esito -1` con `atto non conforme` non è sempre un rifiuto o un errore critico;
- se nello stesso testo è presente l'indicazione che la cancelleria deve confermare, che l'atto verrà comunque accettato o che non va ripetuto il deposito, IUSENTRA deve classificare l'esito come `warning`/presidio intermedio, non come `danger`;
- il software deve attendere o collegare la successiva ricevuta di accettazione/rifiuto deposito e non creare una nuova scadenza operativa duplicata;
- solo `errore fatale`, `rifiuto tecnico`, `rifiuto deposito` o accettazione negata esplicita devono produrre esito critico.

Verifica eseguita il 2026-06-16:

- primo EML JQ332: `event_type=pct_deposito`, `stage=esito_controlli_deposito`, `status=warning`, issue `pct_deposit_followup_expected`;
- secondo EML JQ332: `event_type=pct_deposito`, `stage=accettazione_deposito`, `status=ok`, nessuna issue critica di deposito;
- terzo EML JQ332: stesso esito positivo della ricevuta di accettazione.

## Matrice canali e comportamento software

### PCT SICID civile e PCT lavoro/SICID

- Esempi: civile ordinario, lavoro, previdenza, famiglia, decreto ingiuntivo, ricorso lavoro.
- Il codice oggetto PST ufficiale deve determinare pratica/canale. Se arriva come `222050 - Retribuzione`, il software deve normalizzare a `222050` per `DatiAtto.xml`.
- Il codice non deve essere una regola speciale per `222050`: qualunque codice ufficiale PST deve essere riconosciuto dal catalogo.
- Il software deve:
  - leggere l’intero fascicolo;
  - proporre atto principale e allegati;
  - separare comunicazioni/ricevute/cancelleria dal pacchetto, salvo siano prove necessarie;
  - includere prove di notifica quando il deposito è prova o ricorso originale notificato;
  - generare `DatiAtto.xml`;
  - generare `IndiceDocumentiDepositati.PDF`;
  - verificare codice ufficio, registro, RG/anno se necessari, codice oggetto ufficiale, firme, PDF/PDF-A, dimensione busta;
  - firmare in blocco i documenti richiesti quando Local Signer è pronto;
  - se manca adapter ministeriale reale, preparare controllo e indice ma sospendere l’invio diretto come deposito valido, spiegando che manca `Atto.enc` AES256.

### PCT SIECIC

- Esempi: esecuzioni mobiliari/immobiliari, pignoramenti, interventi, concorsuali, crisi d’impresa.
- Non deve essere confuso con SICID.
- Deve usare profilo `pct_siecic`, controlli propri e registro SIECIC.
- Generazione analoga a PCT: `DatiAtto.xml`, indice, atto, allegati, verifica dimensioni/firme, `Atto.enc` ministeriale per invio valido.

### SIGP / Giudice di Pace

- Canale autonomo, non PCT civile generico.
- Deve usare XSD/profilo SIGP, documenti e ricevute di portale.
- Il software prepara pacchetto, controlli, indice e guida upload/portale quando l’invio diretto non è disponibile.

### PDP penale

- Portale Deposito Penale del difensore.
- Non generare busta PCT civile.
- Il software deve preparare atti firmati, metadati, controlli formato/firma/PDF-A dove richiesti, e guidare upload sul portale PDP.
- Ricevute/stati PDP vanno importati nel fascicolo e non duplicati in agenda/scadenziario come scadenze operative improprie.

### PAT / SIGA amministrativo

- Dal 1 febbraio 2026 Formweb è prioritario.
- PEC solo residuale nei casi tecnici previsti; alcune istanze possono restare a modulo PEC secondo avvisi ufficiali.
- Il software deve preparare modulo/atto, allegati, firma PAdES quando richiesta, indice/checklist e guidare Formweb; non deve presentare l’invio PEC come canale ordinario se non ricorre il caso previsto.

### PTT / SIGIT tributario

- Canale tributario autonomo.
- Il software deve preparare atto e allegati, controllare limiti PTT/SIGIT, firma, ricevute e upload guidato.
- Non generare `DatiAtto.xml` PCT civile per PTT.

### UNEP

- Richieste notifiche/esecuzioni/492-bis e pagamenti collegati.
- Non confondere con relata L. 53/1994.
- Il software prepara richiesta, allegati, pagamenti se dovuti e ricevute portale/UNEP.

### PEC stragiudiziale e notifiche PEC L. 53/1994

- Canale distinto dal deposito PCT.
- La pagina principale per notifiche legali è `/notifiche-legali`.
- Dopo notifica, il software deve presidiare PEC e inserire RAC/RdAC/esiti nella sezione Comunicazioni del fascicolo, collegandoli al documento notificato.
- Se la notifica è già stata inviata e le prove sono già nel fascicolo/comunicazioni, non va riproposta come nuova attività.
- Le ricevute di deposito/accettazione/consegna non devono creare scadenze inutili in agenda/scadenziario: restano nel fascicolo e nei controlli del deposito/notifica.
- Le RAC/RdAC o ricevute equivalenti, quando sono prova della notifica da depositare, possono invece entrare nella busta come documenti prova. La regola è: niente duplicati operativi in Agenda/Scadenziario, ma conservazione e uso probatorio nel fascicolo/deposito quando necessario.

## Regola selezione documenti e busta

- La UI React deve mostrare `Proposta busta` con:
  - numero documenti selezionati;
  - checkbox per includere/escludere;
  - atto principale;
  - allegati;
  - prove notifica;
  - scelte manuali;
  - documenti da firmare;
  - elenco completo dei documenti che entreranno nel pacchetto.
- Il backend deve costruire la busta usando solo `atto_principale_id` e `allegati_ids` derivati dalla selezione visuale.
- Se arriva `documenti_selezionati_ids`, il backend deve verificare che corrisponda esattamente ad atto principale più allegati.
- Se la selezione vista a video e la busta divergono, bloccare la generazione con messaggio chiaro.
- Se un documento selezionato non è più nel fascicolo o non è reperibile su disco, bloccare la generazione spiegando quale file va ricaricato/corretto.

## Indice documenti

- Dai depositi reali allegati risulta presente `IndiceDocumentiDepositati.PDF` nelle copie non crittografate.
- Il software deve generare l’indice in tempo reale nel pacchetto preparato.
- L’indice deve riflettere l’ordine e i ruoli mostrati:
  - `DatiAtto.xml`;
  - atto principale;
  - allegati/prove/notifiche;
  - ricevute/attestazioni se incluse;
  - indice stesso come documento di chiusura del pacchetto.
- Il validatore non deve chiedere all’avvocato di allegare a mano l’indice se il software lo genera automaticamente.

## Stato codice al 2026-06-14

Già fatto in questa tranche:

- Normalizzazione centrale codice oggetto PST (`codice - descrizione` -> codice ufficiale).
- Resolver pratica/canale da codice PST, senza regola speciale solo per `222050`.
- Tutti i 1018 codici oggetto PST ufficiali importati dagli XSD ministeriali vengono accettati sia come codice puro sia come `codice - descrizione`, e arrivano al deposito come codice ministeriale pulito.
- Il codice scelto in apertura fascicolo non resta informativo: viene usato da Regia/Prepara deposito per profilo, canale, validazione e `DatiAtto.xml` quando il flusso lo richiede.
- Canale `PCT lavoro / SICID` mostrato per pratica lavoro/retribuzione.
- Matrice canali preservata: `pct_sicid`, `pct_siecic`, `sigp_gdp`, `pdp_penale`, `pat_siga`, `ptt_sigit`, `unep`, `pec_stragiudiziale`, `notifiche_pec`.
- La matrice canali non può essere ridotta a `PCT_CIVILE/PCT_LAVORO`: restano governati anche PCT SIECIC, SIGP/Giudice di Pace, PDP penale, PAT/SIGA, PTT/SIGIT, UNEP, PEC stragiudiziale e notifiche PEC.
- Tutti i profili depositabili devono risolvere una politica concreta (`direct_pec` o `portal_upload`), con canale ufficiale, tipo pacchetto e indice documenti generato dal software. Non deve passare un canale generico o ambiguo mascherato da deposito.
- Gli alias operativi dei canali sono blindati: `pct_sicid`, `pct_siecic`, `sigp`, `unep`, `pdp`, `pat`, `ptt`, `pec`, `notifica_pec`.
- Backend busta: controllo che selezione visuale e documenti effettivi coincidano.
- Generazione `IndiceDocumentiDepositati.PDF` dentro il pacchetto preparato.
- `DatiAtto.xml` richiama l'indice generato con hash SHA-256.
- Audit tecnico busta aggiornato: `indice_busta_generated = true` quando l'indice è presente.
- Runner server dry-run HTTP `scripts/server_deposito_dry_run_http.py`: effettua login sull'ambiente server, legge `/api/v1/ui/fascicoli/<id>?include=all`, costruisce la proposta documentale dalla stessa logica della pagina React e scarica il `.enc` dalla route reale `/fascicoli/<id>/deposito/genera-busta`, senza chiamare mai l'invio PEC.
- Test automatici passati in questa tranche:
  - `tests/test_codici_oggetto_pst_catalog.py`: 6 test, incluso controllo su tutti i 1018 codici ufficiali.
  - `tests/test_practice_engine_profiles.py`: 8 test, inclusi canali depositabili, alias e matrice non ridotta al solo PCT.
  - blocco mirato deposito/regia/portale/firma batch/asset React/dry-run server: 39 test.
  - `pnpm --filter @iusentra/studio typecheck`, `pnpm --filter @iusentra/studio test`, `pnpm --filter @iusentra/studio build`.
  - `check-route-gate`, `check-react-contracts`, OpenAPI provider e packaging.

Da fare/subito in questa tranche:

- Verificare UI reale su `127.0.0.1:8080`: proposta busta, elenco completo, selezione, scroll, card compatte, canale risolto, documenti mostrati senza tagli.
- Per richiesta esplicita dell'utente, la prova che chiude questa tranche deve essere server reale su `https://app.iusentra.it`: generare busta/pacchetto su ambiente server, non inviare a PEC reale, non registrare deposito valido se manca `Atto.enc` ministeriale AES256, e confrontare la struttura con i depositi reali allegati dall’utente.
- Non dichiarare firma multipla “funzionante” finché non avviene test reale con PIN e più `.p7m`.
- Aggiornare report, changelog, versione, Docker locale, push branch gemelli, checks GitHub, deploy Hetzner.

## Risposta operativa alla domanda sui codici

Alla data 2026-06-14, a livello codice e test automatici, il deposito riconosce tutti i 1018 codici oggetto PST ufficiali disponibili in apertura fascicolo.

Regola applicata:

- se il fascicolo contiene `222050 - Retribuzione`, il deposito usa `222050`;
- lo stesso vale per ogni altro codice ufficiale del catalogo, compresi codici numerici e alfanumerici come `B02001`;
- un codice non presente negli XSD ministeriali non viene accettato come codice deposito valido;
- il canale resta `da verificare` solo quando manca un codice ufficiale, il profilo non è determinabile o il canale richiede una scelta professionale effettiva.

Questa regola è protetta da test, ma non va dichiarata conclusa sul prodotto finché non viene vista nella pagina reale `Prepara deposito` dopo rebuild Docker su `127.0.0.1:8080`.

## Prova server dry-run della busta come deposito reale

La prova richiesta dall’utente va eseguita direttamente sull’ambiente server, dopo deploy della versione corrente, con invio PEC disattivato. Non deve essere una simulazione documentale finta: il software deve usare lo stesso flusso di generazione previsto per il deposito reale, fermandosi solo prima della spedizione PEC.

Obiettivo:

- generare la busta come se il deposito fosse reale, partendo da un fascicolo reale o controllato;
- fermare il flusso prima dell’invio PEC;
- verificare che il contenuto sia coerente con i depositi reali allegati dall’utente;
- produrre un report salvato in repository/artifact con differenze e blocchi.

Regole della prova:

- mai inviare PEC reale durante questa simulazione;
- usare destinatario di prova non consegnabile o modalità server `dry-run`, senza percorso demo che alteri la busta;
- non dichiarare deposito valido se manca `Atto.enc` ministeriale cifrato AES256;
- se il software produce solo pacchetto di controllo e non la busta ministeriale reale, il report deve dirlo chiaramente e bloccare ogni equivalenza con l’invio reale;
- confrontare almeno:
  - presenza e posizione di `DatiAtto.xml` o `DatiAtto.xml.p7m` quando firmato;
  - presenza di `IndiceDocumentiDepositati.PDF`;
  - ordine logico atto principale, procura, NIR, allegati, prove notifica, ricevute;
  - oggetto deposito e RG;
  - hash documenti;
  - dimensione pacchetto;
  - distinzione tra copia non crittografata e invio reale con `Atto.enc`;
  - assenza di documenti non selezionati;
  - messaggi operativi comprensibili per l’avvocato.

La prova è considerata riuscita solo se il report dice esattamente cosa coincide con i depositi reali allegati e cosa resta diverso perché manca adapter ministeriale o firma reale.

Esito preparatorio locale del 2026-06-14:

- creato `scripts/audit_deposito_server_dry_run.py`;
- creato `scripts/server_deposito_dry_run_http.py`;
- aggiunto test `tests/test_deposito_server_dry_run_audit.py`;
- audit locale su pacchetto generato e campioni reali allegati dall’utente:
  - pacchetto di controllo coerente con copia non crittografata: sì;
  - `IndiceDocumentiDepositati.PDF`: presente;
  - `DatiAtto.xml`: presente nel pacchetto generato;
  - campione reale copia non crittografata: contiene `DatiAtto.xml.p7m` e indice;
  - campione reale invio: contiene `Atto.enc`;
  - equivalenza con invio ministeriale reale: no, perché manca `Atto.enc` AES256 generato dall’adapter ministeriale e `DatiAtto.xml` firmato.

Quindi la prossima prova server deve usare lo stesso flusso reale di generazione busta via HTTP, fermarsi prima dell’invio PEC e produrre lo stesso audit. Se il risultato resta `ATTO_ENC_AES256_MISSING`, il software deve spiegare all’avvocato che il pacchetto è pronto per controllo ma non è ancora busta ministeriale valida per invio.

Comando operativo previsto dopo deploy:

```bash
python scripts/server_deposito_dry_run_http.py \
  --base-url https://app.iusentra.it \
  --username antmm26051975 \
  --password "$IUSENTRA_DRY_RUN_PASSWORD" \
  --fascicolo-id EFBE9117 \
  --output-dir /opt/iusentra/deposito-dry-run \
  --report-json /opt/iusentra/deposito-dry-run/server-dry-run.json
```

Subito dopo va eseguito l'audit sul file `.enc` prodotto dal server. La password non va scritta in report o file committati.

## Verifica visiva server E5AE4668 del 2026-06-14

Ambiente verificato davanti all'utente: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`, browser visibile, login eseguito dall'utente, scroll completo della pagina dall'alto al fondo. Non è stato effettuato alcun invio PEC reale.

Esito onesto della prova:

- La pagina si apre sul server e legge il fascicolo reale.
- Il canale viene risolto come `PCT lavoro / SICID` quando è presente il codice ministeriale `222050`.
- Il fascicolo mostra cliente e ufficio, ma il campo RG risulta ancora `n.d.` in una vista in cui il deposito dovrebbe avere dati completi e verificabili.
- Il software genera/mostra `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF`, ma il flusso non può essere dichiarato deposito pronto.
- Il pulsante `Prepara controllo busta` porta lo stato in preparazione e non invia PEC, ma non dimostra ancora la generazione ministeriale completa e conforme.

Problemi da correggere prima di dichiarare il deposito pronto:

- La firma digitale funziona nel prodotto, ma il deposito non deve limitarsi a dire che ci sono documenti da firmare: deve usare il flusso di firma multipla già previsto, firmare in blocco i documenti obbligatori prima del deposito, salvare ogni esito nel fascicolo e riabilitare il passo successivo.
- Il pannello `Verifica deposito` non va bene nella forma attuale: mostra blocchi lunghi e tecnici invece di una verifica professionale per avvocato con `pronto`, `da completare`, `bloccante`, `avviso` e azione immediata per risolvere.
- L'avvocato deve poter selezionare, escludere, allegare o correggere i documenti della proposta. Non basta mostrare solo ciò che il software ha scelto.
- Se il software non è sicuro della classificazione, deve evidenziare solo quel documento e chiedere conferma, non bloccare o nascondere la possibilità di correzione.
- Il pulsante di generazione controllo/indice risulta visivamente primario ma non azionabile; deve spiegare chiaramente perché è disabilitato e quale azione risolve il blocco.
- Non devono comparire stati tecnici visibili come `NON_INVIATO`, `IN_PREPARAZIONE` o `BLOCCATO_DA_ERRORI`: servono testi giuridici professionali.
- Le card compatte devono restare compatte ma leggibili; non devono tagliare parole come `Tutto fascicolo`, `Da firmare` o `Catalogo portale`.
- I documenti che la normativa richiede firmati devono entrare automaticamente nella firma multipla, non essere lasciati come promemoria finale.
- I blocchi obbligatori devono fermare l'invio solo quando il software non può risolverli da solo; i mancanti non obbligatori devono restare avvisi.

Stato della tranche dopo questa verifica: aperta. Il deposito non va dichiarato completo né conforme finché la prova reale non mostra selezione documenti correggibile, firma multipla effettiva su più documenti, indice generato dalla stessa selezione, busta coerente con i campioni reali e messaggi professionali senza testo tecnico.

## Aggiornamento server E5AE4668 del 2026-06-14 ore 19:58

Intervento eseguito direttamente sul server richiesto dall'utente, senza passaggio GitHub/deploy formale:

- aggiornato `frontend/src/components/FascicoliPage.tsx`;
- aggiornato `frontend/src/components/FascicoliPage.css`;
- ricompilato bundle React con `pnpm --filter @iusentra/studio build:vite`;
- copiato il bundle compilato in `/opt/iusentra/repo/web/static/react`;
- copiato il bundle nel container `iusentra-app-1:/app/web/static/react`;
- verificato container `iusentra-app-1` ancora `healthy`.

Regola applicata nella pagina `Prepara deposito`:

- la fase di preparazione non blocca più il lavoro solo perché i documenti devono essere firmati;
- i documenti non firmati entrano nella firma del comando finale `Firma e genera busta`;
- il comando finale richiama la firma multipla registrata dal pannello Local Signer prima della generazione busta;
- se il PIN non è inserito, il software deve chiederlo solo al momento della firma e non deve salvarlo; se invece Local Signer, versione, riavvio o token rilevabile non sono pronti, il software React deve tentare avvio, aggiornamento e riallineamento automatico prima di bloccare la firma;
- i soli blocchi visivi del comando finale restano atto principale mancante e scelte obbligatorie documentali non confermate.

Correzioni UI completate e viste sul server:

- badge e card non mostrano più `NON_INVIATO`, `IN_PREPARAZIONE` o `BLOCCATO_DA_ERRORI`;
- chip `n.d.` sostituito dal riferimento utile `2026/330` quando il campo RG normalizzato è mancante;
- canale visualizzato come `PCT lavoro / SICID`;
- nota errata `PCT civile SICID` sostituita con `Profilo lavoro applicato: usare il canale PCT lavoro/SICID`;
- messaggi grezzi `Impossibile validare...` trasformati in azioni operative:
  - `Collega il documento richiesto alla busta`;
  - `Ricarica il documento oppure correggi il collegamento`;
  - `Ricalcola l'impronta del documento prima della generazione`;
- aggiunta sezione `Documenti da inviare` con selezione correggibile;
- aggiunti comandi `Ripristina proposta`, `Seleziona tutti i documenti`, `Apri documenti fascicolo`;
- aggiunto pannello `Allega documentazione al fascicolo` dentro la proposta busta;
- verificato click reale sul pannello allegati: il form mostra file, classificazione, data documento, etichette, note, `Già firmato` e `Carica documenti`;
- card compatte riviste: `Tutto fascicolo`, `Firma software`, `Catalogo portale` e `Firme` non tagliano il testo;
- artefatti `DatiAtto.xml` e `IndiceDocumentiDepositati.PDF` separati dalla descrizione, senza testo attaccato;
- testo `firma multipla immediata` sostituito con `comando finale`;
- messaggio finale corretto da `1 slot obbligatori` a `1 scelta obbligatoria richiede la conferma dell'avvocato`;
- scroll visivo eseguito dall'alto al fondo della pagina server.

Screenshot locali della verifica visiva reale:

- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_top_final.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_scroll_1_final2.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_upload_form.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_final_block_after_grammar.png`;
- `%TEMP%/iusentra-e5ae4668-deposito-visual-20260614/server_bottom_final.png`.

Stato completato in questa fase:

- preparazione deposito resa lavorabile senza falso blocco sulle firme;
- selezione documenti visibile e correggibile;
- allegato documento visibile e apribile;
- firma multipla agganciata al comando finale sul lato React;
- messaggi principali resi professionali e leggibili;
- scroll completo pagina server eseguito.

Stato ancora aperto e non dichiarabile verde:

- Local Signer nella sessione server/Chrome verificata risulta `non rilevato`;
- non è stato inserito PIN reale;
- non è stata eseguita firma multipla reale di più documenti;
- non sono stati salvati `.p7m` reali nel fascicolo in questa prova;
- non è stato generato un `Atto.enc` ministeriale valido AES256;
- non è stato eseguito invio PEC reale, per scelta corretta della prova.

Prossima prova obbligatoria:

- con Local Signer rilevato e token pronto, l'utente inserisce il PIN;
- premere `Firma e genera busta`;
- verificare che il software firmi in lotto i documenti selezionati, salvi ogni firmato nel fascicolo, aggiorni esiti/impronte, generi indice e pacchetto coerente con la selezione;
- se manca ancora l'adapter ministeriale `Atto.msg` -> `Atto.enc` AES256, il software deve continuare a spiegare che il pacchetto è di controllo/preparazione e non deposito ministeriale valido.

## Aggiornamento navigazione a fasi del 2026-06-14 ore 20:10

Richiesta utente: rendere `Prepara deposito` intuitivo, veloce e professionale, migliorandolo in fasi navigabili.

Intervento eseguito direttamente sul server, senza commit/push GitHub su richiesta operativa dell'utente:

- aggiornata la pagina React `frontend/src/components/FascicoliPage.tsx`;
- aggiornato lo stile `frontend/src/components/FascicoliPage.css`;
- ricompilato il bundle React con `pnpm --filter @iusentra/studio build:vite`;
- copiati sorgenti e bundle su `iusentra-hetzner`;
- copiati gli asset nel container `iusentra-app-1`;
- verificato container `iusentra-app-1` ancora `healthy`.

Nuova struttura visibile:

1. `Verifica pratica`: canale, profilo pratica, regola operativa e controlli obbligatori.
2. `Documenti da inviare`: selezione correggibile dei documenti, allegati e proposta busta.
3. `Firma documenti`: fase separata per firma multipla, PIN, Local Signer e documenti da firmare.
4. `Busta e indice`: riepilogo atto principale, allegati, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti inclusi e comando finale.
5. `Inventario fascicolo`: lettura dell'intero fascicolo usata per classificazione e controllo.

Correzioni di navigazione:

- aggiunta barra `Percorso deposito` sopra i pannelli;
- ogni fase ha numero, titolo, stato e descrizione breve;
- le descrizioni sono state accorciate dopo prova visiva perché due testi venivano troncati;
- i link a `#firma-busta` e `#generazione-busta` ora aprono automaticamente il pannello e scorrono alla sezione anche quando la pagina React carica i dati dopo l'apertura;
- aggiunto margine di scorrimento per evitare che la sezione aperta finisca nascosta sotto la topbar;
- firma e busta/indice sono pannelli separati, non più nascosti dentro la stessa area documenti.

Verifica visiva reale su server:

- URL: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- browser: Google Chrome visibile sulla macchina dell'utente;
- screenshot iniziale: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_top_final.png`;
- test link diretto firma: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_firma_final.png`;
- test link diretto busta: `%TEMP%/iusentra-e5ae4668-deposito-fasi-20260614/fase_busta_final.png`.

Esito visivo:

- barra fasi visibile e compatta;
- testi delle fasi leggibili senza tagli evidenti;
- fase `Firma documenti` apre direttamente Local Signer e spiega che il PIN serve al comando finale;
- fase `Busta e indice` mostra atto principale, allegati, firme previste, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti inclusi e motivo del blocco finale;
- il blocco finale resta professionale: `1 scelta obbligatoria richiede la conferma dell'avvocato`;
- il comportamento resta coerente con la regola: i documenti da firmare non bloccano la preparazione, vengono firmati nel comando finale.

Stato ancora aperto:

- Local Signer nella prova risulta ancora non rilevato;
- non è stato inserito PIN reale;
- non è stata eseguita firma multipla reale;
- non è stato prodotto `Atto.enc` AES256 reale;
- non è stato effettuato invio PEC reale.

## Verifica reale obbligatoria

Prima di dichiarare chiuso:

- Docker locale ricostruito no-cache e healthy su `http://127.0.0.1:8080`.
- Browser reale visibile sulla macchina dell’utente.
- Aprire almeno:
  - `/fascicoli/95557727/deposito/prepara` o fascicolo equivalente con codice `222050 - Retribuzione`;
  - `/fascicoli/2DE106E6/deposito/prepara` per firma multipla/pannello documenti;
  - un fascicolo con documenti da portale/import QuickOrganizer.
- Controllare visivamente:
  - canale non `da verificare` quando codice ufficiale è presente;
  - tutti i documenti selezionati visibili;
  - indice indicato e generato;
  - nessun testo tecnico incomprensibile;
  - nessuna card enorme o testo tagliato;
  - scroll fino in fondo;
  - mobile/tablet/desktop quando UI cambia.

## Fix Local Signer del 2026-06-14 ore 20:27

Richiesta utente: ripristinare il Local Signer, che prima funzionava e nella pagina `Prepara deposito` risultava `Local Signer non rilevato`.

Diagnosi reale:

- il servizio locale rispondeva su `http://127.0.0.1:27272`, ma il processo attivo era disallineato e mostrava `riavvio_signer_consigliato`;
- dopo riavvio controllato dei soli processi `IUSENTRA\LocalSigner\local_signer.py`, il ping locale ha rilevato il token:
  - versione Local Signer `1.6.72`;
  - token `CNS - Bit4id - JS2048 (LB) - slot 0`;
  - seriale token `7430010029148677`;
- nonostante il token pronto, Chrome sulla pagina server continuava a mostrare `Local Signer non rilevato`;
- causa effettiva trovata negli header HTTPS: `Permissions-Policy` negava `local-network-access`, `local-network` e `loopback-network`, impedendo alla pagina di usare correttamente `127.0.0.1:27272`.

Intervento eseguito:

- aggiornato `core/security/headers.py`: le pagine operative consentono ora `local-network-access=(self)`, `local-network=(self)` e `loopback-network=(self)`;
- aggiornato `deploy/hetzner/Caddyfile` con la stessa policy per il reverse proxy pubblico;
- aggiornato `tests/test_security_headers.py` per impedire regressioni verso `local-network-access=()`;
- test mirato eseguito: `python -m pytest tests/test_security_headers.py -q` -> `5 passed`;
- copiati i file corretti su `iusentra-hetzner`;
- ricostruita l'immagine `app` con `docker compose ... build --no-cache app`;
- ricreati i container `app` e `caddy` sul server reale;
- verificato `https://app.iusentra.it/api/pronto` con risposta `200 OK`, versione `2.253.22`;
- verificati header pubblici: entrambe le `Permissions-Policy` ora consentono loopback/local network a `self`.

Verifica visiva reale su macchina dell'utente:

- URL: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara?codex_local_signer=2#firma-busta`;
- browser: Google Chrome reale visibile;
- prima del fix: pannello `Firma documenti` mostrava `Local Signer non rilevato`;
- dopo il fix: pannello verde `Local Signer pronto`, con `CNS - Bit4id - JS2048 (LB) - slot 0`, versione `1.6.72`;
- click reale su `Riverifica`: il pannello resta `Local Signer pronto`;
- screenshot di prova:
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-signer-restart.png`;
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-policy-fix.png`;
  - `%TEMP%/iusentra-local-signer-fix-20260614/desktop-after-riverifica-click.png`.

Stato chiuso per questa sotto-fase:

- rilevazione Local Signer da browser reale su server ripristinata;
- token PKCS#11 visibile nella UI del deposito;
- bottone `Firma 2 documenti` visibile e abilitato quando il token è pronto;
- guardrail header aggiornato con test dedicato.

Stato ancora aperto e da non dichiarare verde:

- non è stato inserito il PIN reale;
- non è stata eseguita firma multipla reale;
- non sono stati salvati `.p7m` nel fascicolo durante questa verifica;
- non è stato verificato il passaggio successivo `firma -> salvataggio documenti firmati -> generazione busta`;
- resta obbligatoria prova con PIN inserito dall'avvocato prima di dichiarare funzionante la firma multipla del deposito.

## Aggiornamento 2026-06-16 - Deposito guidato semplice e slot documentale unico

Regola di esperienza utente:

- il deposito deve essere semplice, veloce, intuitivo e funzionale;
- la pagina `Prepara deposito` deve mostrare un pannello operativo alla volta, evitando schermate dense dove l'avvocato deve interpretare troppe sezioni insieme;
- la navigazione deve seguire le fasi `Verifica pratica`, `Documenti da inviare`, `Firma documenti`, `Busta e indice`, `Inventario fascicolo`;
- i pulsanti devono indicare azioni reali e comprensibili, senza linguaggio tecnico superfluo.

Slot documentale:

- tutti i documenti del fascicolo utili al deposito devono essere visibili nella sezione `Documenti da inviare`;
- l'avvocato può selezionare un documento, selezionare tutto con `Invia tutto`, oppure escludere un documento come `Fuori busta`;
- ogni documento selezionato deve avere una classificazione chiara e non ambigua: `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- la voce ibrida `Allegato / prova` non deve comparire nel menu: i documenti probatori ordinari del fascicolo sono `Allegato`, mentre `Prova notifica` è riservata a atto notificato, relata, PEC inviata, RAC/RdAC e ricevute/evidenze richieste dal deposito prova;
- la direttiva normativa e tecnica sui ruoli documentali è salvata in `docs/specs/ministero/PCT_RUOLI_DOCUMENTALI_DEPOSITO_2026-06-16.md` e va riletta prima di modificare il menu o la classificazione deposito;
- deve esistere un solo atto principale selezionato; se la proposta automatica ne trova più di uno, il sistema mantiene il primo coerente e riclassifica gli altri come allegati/prove;
- la classificazione visibile deve essere salvata prima di firma e busta tramite endpoint reale, non solo tenuta nello stato React.

Firma:

- lo stato `Firmato` è informativo e deriva dal documento reale;
- la UI non deve permettere di segnare manualmente come firmato un documento che non ha esito di firma reale;
- la firma multipla può essere dichiarata funzionante solo dopo prova reale in React con PIN digitato al momento della firma, token rilevato dal Local Signer, firma di più documenti nella stessa operazione, salvataggio dei `.p7m` nel fascicolo e riabilitazione del passo successivo senza errori.

Busta e invio:

- il comando finale deve salvare la classificazione, avviare la firma dei documenti realmente da firmare e poi generare il pacchetto;
- la prova richiesta per il fascicolo `E5AE4668` deve arrivare alla generazione o ispezione del pacchetto/busta senza invio PEC reale;
- se manca l'adapter ministeriale reale che produce `Atto.enc` AES256 conforme, il pacchetto deve essere chiamato pacchetto di controllo e non deposito valido;
- il sistema non deve registrare un invio come deposito valido se manca `Atto.enc` ministeriale o un requisito obbligatorio non producibile.

Lettore documenti firmati:

- i file `.pdf.p7m` devono essere visualizzabili in tutto il software, non solo nel deposito;
- l'anteprima deve estrarre il PDF interno quando il contenitore CAdES lo espone;
- il download deve continuare a servire il `.p7m` originale, senza sostituirlo con il PDF estratto;
- la stessa logica deve valere per documenti fascicolo, PEC, email ordinaria e ogni pannello che apre allegati/documenti firmati.

Regola UI corretta dopo prova server:

- lo stepper deve mostrare un solo pannello operativo alla volta;
- `Verifica operativa` e `Prepara controllo busta` devono dare un riscontro visibile immediato e portare alla fase coerente;
- gli slot documentali devono stare in un solo pannello largo, senza scroll interno, con testo, select e pulsanti leggibili;
- lo stesso pannello resta laterale sui desktop/laptop larghi e si impila come unico pannello sugli schermi più stretti;
- non deve esistere una seconda copia in fondo alla fase documentale.

Verifiche obbligatorie per questa tranche:

- browser reale visibile su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`, con scroll completo dei pannelli;
- responsive desktop, tablet e mobile sul server reale;
- salvataggio classificazione documenti da UI sul server reale;
- aggiornamento macchina locale Docker e verifica `http://127.0.0.1:8080/api/pronto`;
- generazione pacchetto dry-run o ispezione reale equivalente;
- controllo contenuti: documenti selezionati, atto principale, procura, allegati, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, oggetto e testo email se prodotti;
- prova Local Signer React con controllo automatico di versione, avvio, aggiornamento e stop delle istanze vecchie; la firma multipla reale richiede poi il PIN digitato al momento della firma e il token fisico rilevato.

## Aggiornamento 2.253.36 - prova server firma multipla e pacchetto busta

Data intervento: 2026-06-16.

Prova reale eseguita sul server `https://app.iusentra.it`, fascicolo `E5AE4668` (`2026/330 - Marchetti Lucia`):

- accesso autenticato allo studio `studio-legale-giuseppe-montagnese` e lettura payload React `/api/v1/ui/fascicoli/E5AE4668?include=all`;
- verificato che l'atto principale `Autocertificazione ricorso.PDF.p7m` e la procura `Procura.PDF.p7m` risultano già firmati, con estensione `.p7m` visibile nel payload;
- scaricati dal server due documenti reali non firmati: `Autocertificazione situazione reddituale.PDF` e `Contratto 24-25.pdf`;
- firmati insieme con una sola chiamata Local Signer `/firma-batch`, token CNS Bit4id reale e PIN inserito nel processo di prova, senza salvare il PIN;
- ricaricati nel fascicolo come `Autocertificazione situazione reddituale.PDF.p7m` e `Contratto 24-25.pdf.p7m`;
- riletto il payload React dopo upload: entrambi i documenti risultano `signed=true` e mantengono il nome originale con sola aggiunta dell'estensione `.p7m`;
- salvata classificazione deposito con 4 documenti in busta: atto principale, procura, autocertificazione reddituale e contratto;
- chiamata la validazione deposito con form reale: 5 avvisi, 0 blocchi;
- generato il pacchetto con `/fascicoli/E5AE4668/deposito/genera-busta` senza usare `/deposito/invia-pec`;
- verificato il file `Busta_2026-330_RICORSO.enc` scaricato dal server: è un pacchetto zip di controllo con 6 voci, cioè `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF` e i quattro documenti `.p7m`.

Avvisi rilevati nella validazione:

- atto introduttivo con RG già presente;
- oggetto dell'atto troppo sintetico;
- ricevuta contributo unificato non rilevata;
- prova di notifica non rilevata;
- conformità PDF/A non verificabile sul wrapper `.p7m`.

Stato operativo:

- la firma multipla Local Signer ha funzionato su documenti reali e ha salvato i `.p7m` nel fascicolo;
- il pacchetto busta di controllo è stato generato e contiene `DatiAtto.xml`, indice e documenti firmati;
- non è stato eseguito invio PEC;
- resta aperta la verifica visiva materiale nella scheda autenticata del browser dell'utente, con scroll completo di `#proposta-busta` e `#firma-busta`, controllo layout desktop/tablet/mobile e conferma che il pannello singolo documento mostra di nuovo le impostazioni di firma visibile al posto del blocco di riallineamento inutile.

## Aggiornamento 2.253.34 - scelta `Da firmare` e layout lista deposito

Data intervento: 2026-06-16.

Problema corretto:

- nella lista `Documenti da inviare` la voce `Da firmare` risultava percepita come controllo, ma non era utilizzabile dall'avvocato;
- la firma multipla doveva leggere una scelta reale per ogni documento, non soltanto dedurre tutto dal nome o dallo stato iniziale;
- sui formati laptop la riga documento e il menu ruolo potevano uscire dal pannello o comprimere testo, icone e badge.

Cambio operativo:

- `Da firmare` è diventato una spunta cliccabile per i documenti non ancora firmati che richiedono firma;
- se l'avvocato toglie la spunta, il documento resta selezionabile in busta ma non entra nel lotto firma;
- se l'avvocato rimette la spunta, il documento viene incluso e marcato per la firma nel comando finale;
- `Firmato` resta solo informativo e continua a derivare dal documento reale, da `.p7m` o da esito Local Signer salvato;
- il payload React verso `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` porta anche `requires_signature`, così il backend può restituire e presidiare la scelta;
- se il comando finale trova documenti da firmare ma il pannello firma o il PIN non sono pronti, apre la fase `Firma documenti` e mostra il blocco nel punto corretto;
- la riga deposito è stata ricompattata in quattro colonne governate: invio, documento, azioni icona, ruolo/firma;
- le azioni `Visualizza` e `Scarica` restano icone con tooltip/label accessibile, senza testo visibile che rompa la griglia;
- il menu ruolo è ancorato alla riga con altezza controllata e z-index dedicato, evitando il pannello fuori asse visto nella prova reale.

Guardrail tecnici eseguiti prima del commit:

- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build:vite`;
- `python -m pytest tests/test_regia_api_payloads.py::test_api_deposito_classifica_documenti_collega_slot_e_metadati tests/test_regia_ui_react.py -q`.

Stato prova reale:

- non ancora chiuso: serve deploy produzione sullo SHA corrente, poi prova visiva server su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara` con scroll completo, click reale sulla spunta `Da firmare`, apertura menu ruolo, verifica layout laptop/tablet/mobile, dry-run senza invio PEC e prova firma multipla con PIN/token reale.

## Aggiornamento 2.253.33 - scadenza certificato firma in Impostazioni

Data intervento: 2026-06-16.

Cambio operativo:

- la sezione React `Impostazioni > Firma Digitale` legge dal Local Signer il certificato Windows selezionato, inclusi codice fiscale, intestatario, emittente e scadenza;
- la scadenza viene salvata nella configurazione firma dello studio con data ISO per i calcoli e data italiana `gg/mm/aaaa` per la visualizzazione;
- il salvataggio usa l'endpoint dedicato `/api/v1/ui/impostazioni/firma/certificato`, senza modificare P12, PEM, driver PKCS#11 o altre impostazioni firma;
- al login, se mancano 20 giorni o meno alla scadenza salvata, l'avvocato vede un avviso con i giorni mancanti; se il certificato risulta scaduto, il messaggio invita al rinnovo prima di firmare o depositare atti.

Test automatici eseguiti:

- `python -m pytest tests/test_react_shell.py::test_impostazioni_firma_salva_scadenza_certificato_local_signer tests/test_react_shell.py::test_avviso_login_certificato_firma_a_venti_giorni tests/test_react_shell.py::test_impostazioni_react_frontend_copre_local_signer_occhio_e_ai_locale tests/test_local_signer.py::test_diagnosi_windows_mostra_certificato_avvocato_selezionato tests/test_local_signer.py::test_local_signer_ha_guardia_istanza_unica_e_diagnosi_certificato -q`

Stato prova reale:

- da verificare su macchina reale dopo rebuild Docker `127.0.0.1:8080`: apertura `Impostazioni > Firma Digitale`, click reale su `Verifica dispositivo collegato`, salvataggio scadenza letta dal Local Signer, ricarica UI con data italiana e avviso login se la soglia e' applicabile.

## Aggiornamento 2.253.32 - Local Signer 1.6.74, certificato e cataloghi

Intervento richiesto dopo il dubbio dell'utente su certificato avvocato e catalogo PST:

- `/ping` rilevava correttamente il certificato Windows selezionato dell'avvocato, ma `/diagnosi` mostrava solo i primi certificati dello store e poteva non visualizzare quello operativo;
- `/diagnosi` ora espone anche `certificato_windows_selezionato` e una riga leggibile `Certificato avvocato selezionato` con codice fiscale e scadenza;
- il processo Local Signer ora acquisisce una guardia di istanza unica per porta prima di aprire il server, cosi' una seconda istanza richiamata da avvio automatico o protocollo locale si chiude invece di restare viva in parallelo;
- il catalogo copiato dal pacchetto Local Signer e' stato ricontrollato: `uffici_ministero.json` contiene 534 uffici mappati e 13 non mappati; `uffici_pst_pubblici.json` contiene 1.781 uffici civili e 1.416 penali, totale 3.197 voci PST pubbliche;
- il messaggio `Catalogo pubblico uffici PST civile/penale copiato` riguarda il catalogo PST pubblico civile/penale usato dal Local Signer e non esaurisce l'intero perimetro dei servizi telematici, dove PAT, PTT, PDP e altri flussi restano registri o adapter separati.

## Aggiornamento 2.253.30 - menu ruolo, Editor professionale e lettore globale

Intervento tecnico applicato prima della chiusura richiesta:

- sostituita la select nativa dei ruoli deposito con un selettore React ancorato alla riga, per evitare popup fuori asse nella lista `Documenti da inviare`;
- mantenuti come ruoli visibili solo `Atto principale`, `Procura alle liti`, `Allegato`, `Prova notifica`, `Fuori busta`;
- il valore storico `allegato_prova` resta accettato solo in compatibilità e viene normalizzato a `Allegato`;
- aggiunta la route full React `/editor-professionale`, distinta da `/redazione-atti`, con voce autonoma sotto `Studio`;
- esteso il lettore globale di allegati/documenti a `.xml`, `.xml.p7m`, `.eml`, `.eml.p7m`, `.txt`, `.txt.p7m`, oltre a `.pdf.p7m`;
- il download resta sempre dell'originale, soprattutto per i contenitori `.p7m`;
- rimossi rami di preview fascicolo duplicati per `.eml` e `.txt`, ora gestiti dal lettore unico, mantenendo `fascicoli_document_routes.py` sotto il limite di governance;
- introdotto code splitting Vite per separare vendor e icone e rimuovere il warning del chunk principale sopra 500 kB.

Guardrail tecnici eseguiti e registrati in `pytest-confirmed-ok.md`:

- TypeScript, contratti React, route gate, OpenAPI, frontend test e build Vite;
- test mirati deposito/regia, Editor professionale, fascicoli, PEC, email ordinaria, UTF-8 e asset retention;
- audit dati/tenant/topbar senza repair;
- quality gate `code` non usato come verde finale perché sullo stage completo blocca il bump versione obbligatorio di `Dockerfile`, `pct/__init__.py` e `railway.toml`;
- governance repo e sintassi Python.

Stato ancora aperto prima di dichiarare chiuso il deposito:

- commit, push branch gemelli e check GitHub/CodeQL dello SHA corrente;
- deploy Hetzner e verifica `/api/pronto`;
- riallineamento Docker locale su `127.0.0.1:8080`;
- prova visiva reale server desktop/tablet/mobile con click e scroll completo;
- dry-run server del fascicolo `E5AE4668` senza invio PEC reale;
- firma multipla reale da chiudere con PIN digitato al momento della firma e token fisico rilevato; installazione, aggiornamento e riallineamento Local Signer non sono un prerequisito esterno, ma responsabilità del software React.
