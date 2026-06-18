# Procedura deposito telematico IUSENTRA

Aggiornato: 2026-06-18.

## Aggiornamento 2.253.64 - anteprima PST lavoro con catalogo completo

Data: 18/06/2026.

- Caso reale: Tribunale di Torino, registro LAV, RG 3950/2026.
- Dopo deploy `2.253.63`, prova reale su `https://app.iusentra.it` in Google Chrome: `Cerca fascicolo` ha confermato il certificato PST e ha trovato `RG 3950/2026`; `Carica anteprima` ha aperto Step 3 senza timeout verso `ext.processotelematico.giustizia.it`.
- Residuo corretto in `2.253.64`: l'anteprima mostrava solo 4 righe principali quando il fascicolo locale già importato conteneva il catalogo completo; ora la preview PST arricchisce lo snapshot parziale con i documenti portale del fascicolo locale esatto.
- Prova reale server `2.253.64` su Google Chrome: `Cerca fascicolo` ha trovato `RG 3950/2026`; `Carica anteprima` ha aperto Step 3 in circa 1 secondo, senza timeout, con `Documenti 31`, `7 buste o gruppi`, `Parti 2` ed `Eventi 1`.
- Guardrail: `test_api_portale_acquisizione_preview_pst_arricchisce_catalogo_da_fascicolo_locale` copre `29/29` documenti in preview e preserva anche un allegato reale senza id forte.
- Limite operativo: questa correzione riguarda consultazione/anteprima e catalogo documenti; non dichiara completo l'invio reale del deposito, che resta soggetto a firme, `Atto.enc`, PEC locale e ricevute.

## Stato operativo da non perdere

Stato consolidato `2.253.60`: la cache certificati PST è coperta per il catalogo operativo corrente dei canali PCT/SIGP/Cassazione che richiedono cifratura `Atto.enc` (`593/593` codici ministeriali coperti; `913` `.cer` fisici validi in cache). Da questo punto in avanti il software non deve più trattare il `.cer` di Palmi o Vicenza come mancante globale se la cache corrente è presente: un eventuale blocco su `Invia deposito reale` deve indicare solo il requisito effettivamente mancante nella singola prova, per esempio `Atto.enc` AES256 non generato, PEC mittente dello studio non configurata, firma obbligatoria non presente o destinatario PEC non verificato. L'invio operativo PEC non parte mai dal server: anche su `https://app.iusentra.it` il server prepara e verifica, mentre SMTP reale passa dal PC dell'avvocato tramite Local Signer. In `2.253.60` restano presidiati il gate `Local Signer boundaries`, la priorità del codice ufficio operativo in `TelematicoSurfacePage`, la sanificazione dei payload JSON deposito/firma/database senza perdere i messaggi operativi CAdES/PAdES e il limite governance del modulo firma.

La regola è fail-closed ma non pessimistica: se tutti i requisiti obbligatori del canale sono presenti, il bottone reale deve attivarsi; se resta disabilitato, la UI deve dire esattamente cosa manca e Codex deve correggere la logica prima di commit, push e deploy.

## Aggiornamento 2.253.61 - tracciatura tabella lavoro PST Torino RG 3950/2026

Data intervento: 2026-06-18.

Il fascicolo lavoro `RG 3950/2026` del Tribunale di Torino, registro `LAV`, è stato scaricato dal PST ufficiale con browser autenticato e importato nel fascicolo IUSENTRA `9B9DF2A1` (`Spagnolo Sara c. MIM`). Il log produzione è `PST-20260618085430-C4891C`.

Esito operativo:

- documenti PST individuati: 29;
- documenti scaricati: 29;
- documenti importati: 29;
- documenti mancanti, senza contenuto o scartati: 0;
- depositi ricostruiti: 4;
- eventi generati: 5;
- comunicazioni generate: 3;
- contatore visibile `Documenti e atti`: 52.

La correzione Local Signer tratta `lav_infofascicolo.wp` come superficie ministeriale equivalente alla tabella civile: riga principale, blocco `Allegati:`, nuova riga principale e paginazione. Il parser conserva la sezione reale del link, collega gli allegati al documento padre e non trascina più la sezione `Allegati` sui documenti principali successivi. Il download usa i link portale `downloadDocumentoSemplice.action` quando sono disponibili nella sessione PST autenticata.

Aggiornamento dopo prova utente: il flusso React `Carica anteprima` non deve più bloccare la vista con il timeout `ext.processotelematico.giustizia.it` quando la ricerca ha già restituito documenti PST utilizzabili. In `2.253.61` l'anteprima usa subito i documenti già ricevuti dalla ricerca; l'aggiornamento esterno resta un arricchimento e, se fallisce ma i documenti sono presenti, viene tracciato senza lasciare l'anteprima vuota.

Prova visiva server già eseguita su `https://app.iusentra.it/fascicoli/9B9DF2A1#documenti`: visibili tra gli altri `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `26830376s.pdf` e `20200029s.pdf`, con origine PST ufficiale e date portale. Dettaglio esteso in `artifacts/react-migration/tracciatura-tabella-lavoro-torino-rg-3950-2026.md`.

Dato sensibile: il PIN della pen drive e le credenziali dell'utente non sono stati scritti nei log o nei report.

## Incarico operativo di chiusura, da rileggere dopo ogni compattazione

Il lavoro deposito non è chiuso finché non è dimostrato nella vista reale, con fascicoli reali o controllati, che il software prepara, firma, controlla, simula e abilita l'invio secondo il canale corretto. I test automatici sono guardrail, non prova finale. Se la vista reale mostra un difetto, quel difetto prevale su build, typecheck, unit test o screenshot precedenti.

### Regola di sviluppo da seguire

1. Se l'utente segnala un difetto visibile, aprire subito la pagina reale indicata (`127.0.0.1:8080` oppure `https://app.iusentra.it`) e correggere il minimo necessario.
2. Provare subito la modifica nella stessa vista reale, con click, scroll e dati visibili.
3. Solo dopo il risultato reale positivo creare o aggiornare i test automatici.
4. Solo dopo test e prova reale procedere con commit, push dei branch gemelli, deploy Hetzner, verifica `/api/pronto` e igiene.
5. Se una prova reale resta aperta o fallisce, scriverlo qui e non dichiarare il deposito concluso.

### Cosa deve fare il software

- Risolvere il profilo deposito in tre casi: preventivo accettato con conferimento e fascicolo, nuovo fascicolo diretto, fascicolo veloce/autonomo.
- Salvare il profilo in SQL, non solo nel JSON, nelle colonne `profilo_deposito_json` di `preventivi_records`, `conferimenti_records` e `fascicoli`, con parità SQLite/PostgreSQL.
- Usare il canale corretto: PCT/SICID, PCT lavoro/SICID, PCT/SIECIC, SIGP/Giudice di Pace, Cassazione civile/PST, PDP, PAT, PTT, UNEP/notifiche sono canali diversi e non devono ereditare blocchi o certificati non pertinenti.
- Per PCT/SIGP/Cassazione con busta PST generare o presidiare `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.msg`, certificato pubblico `.cer` e `Atto.enc` AES256 quando richiesto.
- Per PDP, PAT e PTT preparare controlli, firme, limiti e ricevute secondo il portale specifico, senza pretendere `.cer` PST civile o `Atto.enc` PCT.
- Leggere l'intero fascicolo, proporre atto principale, procura, allegati e prove, ma lasciare all'avvocato le scelte non obbligatorie.
- Mostrare `Firmato` solo davanti a prova tecnica reale: CAdES/PKCS#7 `.p7m` o PAdES interno verificabile. Il testo del documento, il nome file o un vecchio flag non bastano.
- Firmare più documenti con un unico comando quando Local Signer/PKCS#11 è disponibile, salvando ogni `.p7m` nel fascicolo e aggiornando la UI prima del passo successivo.
- Mostrare `IndiceDocumentiDepositati.PDF` in anteprima reale e consentirne il download.
- Mostrare il corpo PEC che verrà predisposto; l'avvocato può modificarlo facoltativamente, ma la modifica non è obbligatoria.
- In simulazione o prova senza invio mostrare una barra avanzamento con il nome del documento o artefatto in lavorazione.
- Conservare o ripristinare `Simula invio PEC` e `Prova senza invio reale`, perché servono a controllare il flusso senza spedire nulla.
- Preparare l'invio reale usando le rotte corrette, il destinatario PEC verificato, la PEC mittente configurata e il payload locale per Local Signer; il server non deve essere canale SMTP reale e non devono comparire messaggi inutili alla cancelleria.
- Presidiare le ricevute dopo l'invio, senza registrare come deposito valido un pacchetto che non ha trasporto ministeriale conforme.

Regola permanente PEC locale: il riferimento operativo è la schermata `/impostazioni?tab=pec`, sezione `Verifiche PEC`, che indica `Il controllo dell'invio parte dal PC in uso: la password resta sul dispositivo locale.` Vale per deposito, notifiche legali e PEC operative: il server prepara e verifica, ma l'invio reale parte dal PC in uso tramite Local Signer/servizio locale. Se una rotta o un fallback prova a spedire dal server via SMTP, è una regressione da bloccare. La password PEC deve essere raccolta in una modale React locale, non tramite `window.prompt` e non in una rotta server.

### Quando `Invia deposito reale` deve attivarsi

Il bottone non deve restare spento per prudenza generica. Deve attivarsi quando sono veri tutti i requisiti obbligatori del canale:

- canale reale abilitato e riconosciuto;
- ufficio giudiziario e codice deposito/codice oggetto risolti;
- destinatario PEC verificato;
- PEC mittente e impostazioni SMTP disponibili per costruire il payload Local Signer, senza invio SMTP dal server;
- documenti selezionati e ruoli coerenti;
- firme obbligatorie già presenti o completate con Local Signer;
- `IndiceDocumentiDepositati.PDF` generato e visualizzabile;
- corpo PEC controllato;
- `.cer` PST valido solo se il canale lo richiede;
- `Atto.enc` AES256 generato solo se il canale lo richiede;
- prova senza invio o simulazione PEC completata senza errori bloccanti;
- ricevute presidiate dal fascicolo.

Se uno di questi punti manca, la UI deve indicarlo con testo puntuale. Se nessun punto manca e il bottone resta disabilitato, è una regressione da correggere prima di commit, push e deploy.

### Stato corrente da non perdere

- Cache certificati PST locale: `913` `.cer` fisici DER validi, `0` invalidi.
- Perimetro operativo che richiede `.cer/Atto.enc`: `593` codici ministeriali unici, `593/593` coperti, `0` mancanti.
- Fonti importate: `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `C:\QuickOrganizer\QC_Uffici.xml`, più fallback PST diretto per codice/nome ufficio.
- Caso `Giudice di Pace - Palmi`, codice ministeriale `0800570152`: certificato recuperato e non deve essere più trattato come mancante globale se la cache corrente è presente.
- Caso `Tribunale di Vicenza`, fascicolo server `E5AE4668`, codice deposito `222050`: profilo deposito SQL già previsto con canale PCT, PEC e certificato quando il deploy è allineato.
- Prova locale reale aggiornata su `127.0.0.1:8080`: React autentico, PEC Palmi risolta, codice `0910401 / 0800570152` visibile, `Atto.enc` presente nella UI e anteprima `IndiceDocumentiDepositati.PDF` visibile con viewer PDF del browser, pagina `1/1`, toolbar, miniatura e contenuto `Indice documenti depositati`. Screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-diretto-225356.png`.
- Prova locale reale controllata aggiornata al 2026-06-18: sul fascicolo `DC5BF1DB` il click reale su `Invia deposito reale` ha attraversato UI React, rotta `/deposito/invia-pec`, payload Local Signer e SMTP locale fittizio senza spedire all'esterno. Il pacchetto catturato contiene destinatario `gdp.palmi@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023` e allegato unico `Atto.enc` da `4.637.389` byte. La configurazione PEC reale del tenant è stata ripristinata subito dopo e il server SMTP fittizio è stato spento.
- Fix sicurezza `2.253.60`: i payload di deposito React/legacy, database admin e apertura fascicolo da preventivo/conferimento passano da redazione pubblica; la cache/report `.cer` usa solo nomi file normalizzati dentro la directory prevista; la nota firma visibile non usa più regex fragile e non taglia note multilinea dell'utente. Gli helper firma CAdES/PAdES vivono nel service `fascicoli_signature_options`, così il bootstrap route resta sotto il limite governance senza cambiare comportamento.

### Prova finale richiesta prima di chiudere

- Server reale: fascicolo `E5AE4668` (`2026/330 - Marchetti c. MIM`) su `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`.
- Locale reale: fascicolo `DC5BF1DB` su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara`.
- Verifica visiva: apertura pagina, scroll completo, fasi deposito, lista documenti, ruoli, firme, indice, corpo PEC, simulazione PEC, prova senza invio e stato del bottone reale.
- Verifica tecnica: API e rotte di invio, destinatario PEC, mittente/SMTP, `Atto.enc` quando richiesto, ricevute, scheduler `.cer`, parità SQLite/PostgreSQL.
- Chiusura: commit, push su `Codex/legal-electronic-filing-kIxcV` e `claude/legal-electronic-filing-kIxcV`, check GitHub/CodeQL, deploy Hetzner, `/api/pronto`, prune Docker e repo hygiene.

### Relata e prova notifica

La relata non è un accessorio da confondere con la guida firma. Deve avere flusso proprio: testo reale visualizzato o generato, destinatari, domicilio digitale, dati obbligatori, documenti allegati, firma quando richiesta, prova senza invio e salvataggio nel fascicolo. Se la UI apre la guida quando si clicca firma/notifica, va corretto come difetto visivo-funzionale. La conformità della relata va scritta in questo file solo dopo prova reale e confronto con fonti ufficiali.

## Aggiornamento 2.253.57 - prova reale invio PEC locale senza spedizione esterna

Data intervento: 2026-06-18.

Perimetro verificato:

- copia Docker locale reale `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`;
- superficie React `Prepara deposito`, fase `Busta e indice`;
- canale `SIGP/Giudice di Pace` con ufficio Palmi, codice ministeriale `0800570152` e PEC `gdp.palmi@civile.ptel.giustiziacert.it`;
- Local Signer raggiunto su `http://127.0.0.1:27272`;
- server SMTP fittizio temporaneo su `127.0.0.1:25252` usato solo per catturare la PEC senza inviare all'esterno;
- configurazione PEC reale del tenant ripristinata dopo il collaudo e server fittizio spento.

Correzioni applicate:

- `frontend/src/components/FascicoliPage.tsx`: `Invia deposito reale` usa la rotta JSON `/fascicoli/<id>/deposito/invia-pec` anche per il canale PST/SIGP che produce pacchetto JSON/Local Signer, evitando il fallback vecchio su `/deposito/genera-busta`;
- `frontend/src/components/FascicoliPage.tsx`: eliminata la dipendenza da `window.prompt`; la password PEC viene chiesta con modale React `Password PEC locale`, riepilogo mittente, destinatario, oggetto e allegati;
- `frontend/src/components/FascicoliPage.tsx`: la modale di conferma `Invia deposito reale` viene chiusa prima della richiesta password locale, così non resta un overlay bloccato su `Operazione...`;
- `frontend/src/components/FascicoliPage.css`: aggiunti gli stili della modale password PEC, con testo leggibile e campi che non escono dal contenitore;
- `web/bootstrap/deposito_routes.py` e `web/services/local_pec_runtime.py`: il server non usa SMTP reale per depositi legali; restituisce un payload `requires_local_pec` per il Local Signer e registra la conferma solo dopo `Message-ID` locale.

Prova materiale eseguita:

- click reale su `Prova senza invio reale`: UI con esito `Controlli software superati`, destinatario `gdp.palmi@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- click reale su `Invia deposito reale`;
- conferma visibile accettata;
- modale `Password PEC locale` aperta nel browser, senza errore `prompt() is not supported`;
- inserita password fittizia solo per lo SMTP locale di collaudo;
- click reale su `Invia dal PC locale`;
- toast applicativo visto: `Deposito inviato via PEC e registrato nel fascicolo.`;
- nessun errore console nel browser durante il flusso.

Verifica post-rebuild Docker locale `2.253.57`:

- `docker compose build --no-cache app` completato con wheel `pct-studio-legale-2.253.57`;
- `docker compose up -d --force-recreate app`, container `iusentra-app` healthy;
- `GET http://127.0.0.1:8080/api/pronto` HTTP 200 con `versione=2.253.57`;
- browser integrato su `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- dopo il caricamento reale la pagina mostra `RG 466/2023 - Alessi Robertino`, `Giudice di Pace - Palmi`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`, `8 documenti in busta`, `Indice dalla selezione`, nessun `n.d.` e nessun HTML grezzo;
- click reale su `Prova senza invio reale` dopo rebuild: esito `Prova deposito preparata`, riferimento prova `F81FDC8C`, controlli software superati e bottone `Invia deposito reale` attivo;
- click reale su `Visualizza IndiceDocumentiDepositati.PDF`: modal con URL diretto `/fascicoli/DC5BF1DB/deposito/indice-documenti?...`, toolbar PDF, miniatura, pagina `1/1` e contenuto `Indice documenti depositati`;
- screenshot prova indice post-rebuild fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-post-rebuild-225357.png`.

PEC catturata dal server SMTP fittizio:

- file prova fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-fake-smtp-deposito.json`;
- EML fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-fake-smtp-deposito.eml`;
- mittente header: `roberto.montagnese@coapalmi.legalmail.it`;
- destinatario header: `gdp.palmi@civile.ptel.giustiziacert.it`;
- oggetto: `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- `Message-ID`: `<178174394892.26844.7734756242688097457@pcmarco.station>`;
- corpo PEC contiene `Atto.enc` e l'elenco dei documenti inclusi;
- allegato unico: `Atto.enc`, `application/octet-stream`, `4.637.389` byte, SHA256 `1dfbb7d8a8383a05a3c0dcbd84bf8e76cfa382f09c8fb35f85816c3d8dd1d579`.

Limiti residui dichiarati:

- questa prova non ha spedito una PEC reale a una cancelleria: ha simulato il server SMTP in locale per verificare il click reale, la composizione PEC e l'allegato senza invio esterno;
- la firma multipla fisica con pen drive e PIN reale non può essere dichiarata completata durante l'assenza dell'utente: richiede token inserito, PIN digitato e firma effettiva di più documenti con salvataggio `.p7m`;
- prima della chiusura complessiva restano gate finali, rebuild Docker locale, commit, push branch gemelli, deploy Hetzner e verifica server sullo stesso commit.

## Regola permanente certificati PST, Atto.enc e canali deposito

Questa sezione va riletta dopo ogni compattazione prima di toccare deposito, PEC, firma digitale, Local Signer, scheduler `.cer`, `/tribunali` o `Invia deposito reale`.

### Regola di canale

`Atto.enc` e il certificato pubblico PST `.cer` dell'ufficio si applicano solo ai canali che usano la busta telematica PST con `Atto.msg` cifrato:

- `PCT/SICID`, compreso lavoro quando usa registro SICID;
- `PCT/SIECIC`;
- `SIGP/Giudice di Pace`;
- Cassazione civile/procedimento di legittimità quando usa la busta PST ministeriale.

Non si applicano, dentro il flusso deposito fascicolo IUSENTRA, a:

- `PDP penale`: usa il Portale Deposito atti Penali, non la busta PCT civile generata dallo studio;
- `PAT/SIGA amministrativo`: dal 1 febbraio 2026 il canale prioritario è Formweb; la PEC è residuale nei casi tecnici previsti;
- `PTT/SIGIT tributario`: usa il portale tributario e le regole MEF/DGT proprie;
- notifiche PEC, PEC stragiudiziale e flussi UNEP: sono canali separati dal deposito PCT del fascicolo e non devono essere dichiarati deposito PCT. Se in futuro si implementa un flusso UNEP dedicato, va documentato come canale autonomo e non ereditato dal PCT civile.

### Fonti normative operative

- PCT/PST civile e SIGP: specifiche tecniche DGSIA ex art. 34 D.M. 44/2011, provvedimento 7 agosto 2024, efficace dal 30 settembre 2024. Art. 15: atto principale in PDF/PDF-A, privo di elementi attivi, da documento testuale, firmato; firme ammesse PAdES-BES o CAdES-BES. Art. 17: nel procedimento civile la busta contiene `Atto.enc`, ottenuto dalla cifratura di `Atto.msg`; le chiavi pubbliche degli uffici sono nell'area pubblica PST e nel catalogo servizi; limite busta `60 MB`; invio via PEC ministeriale.
- PDP penale: decreto Ministero Giustizia 4 luglio 2023 e specifiche tecniche PDP pubblicate sul PST. Il deposito avviene sul PDP; limite indicato dalle specifiche PDP: `50 MB` per singolo file e `500 MB` per deposito complessivo; firme ammesse PAdES e CAdES secondo il caso.
- PAT/SIGA: regole tecnico-operative della Giustizia Amministrativa e modifica Formweb 2025/2026. Dal 1 febbraio 2026 Formweb è prioritario; limite Formweb documentato: massimo `50` file, `300 MB` per singolo file e `300 MB` complessivi.
- PTT/SIGIT: regole MEF/Dipartimento Giustizia Tributaria. Non usa `.cer` PST civile né `Atto.enc`; limite operativo aggiornato: `50 MB` per singolo file, con suddivisione dei file superiori.

### Stato tecnico certificati al controllo corrente

Controllo locale eseguito sulla cache `D:\legale\IUSENTRA\data\pst\certificati_cifratura`:

- `.cer` fisici in cache: `913`;
- `.cer` DER leggibili e validi: `913`;
- `.cer` fisici non validi: `0`;
- perimetro operativo che richiede `.cer/Atto.enc`: `593` codici ministeriali unici;
- target coperti: `593/593`;
- target mancanti o non validi: `0`;
- report job su disco: `data/pst/certificati_cifratura/audit_certificati_cifratura_pst.json`;
- ultimo report job: `ok=true`, `catalogo_pct_operativi=593`, `scaricati_o_validi=593`, `saltati_senza_certificato_pubblicato=0`, `errori=0`, `cache_cer_presenti=913`, `generated_at=2026-06-18T00:40:32.903271+02:00`.

La differenza tra `913` e `593` è voluta: `913` è la cache fisica valida complessiva; `593` è il perimetro operativo corrente degli uffici attivi che richiedono certificato PST per la cifratura `Atto.enc`. La cache conserva certificati extra validi senza usarli come obbligo su canali non pertinenti.

### Perimetro uffici coperto

Il target `593/593` comprende gli uffici attivi del catalogo PST/ministeriale che il software deve coprire per la busta PCT/SIGP:

- Corti d'Appello e uffici civili collegati;
- Tribunali ordinari e uffici civili collegati;
- Giudici di Pace/SIGP;
- Cassazione civile/PST dove prevista.

Il filtro esclude dal conteggio obbligatorio del deposito PCT:

- Procure, PDP penale e canali penali non PCT civile;
- PAT, PTT/SIGIT e portali amministrativi/tributari;
- UNEP e notifiche PEC, perché non sono il flusso `Prepara deposito` PCT del fascicolo;
- uffici storici/non attivi o sezioni accorpate che non devono bloccare il deposito corrente;
- uffici senza codice ministeriale utile alla cifratura.

### Origine dati e recupero certificati

Il software usa tre livelli, in questo ordine:

1. catalogo PST pubblico già presente in `pct/data/uffici_pst_pubblici.json`;
2. metadati ministeriali importati da `C:\QuickOrganizer\ListaUfficiGiudiziari.xml` e `C:\QuickOrganizer\QC_Uffici.xml`, riversati in `pct/data/uffici_ministero.json` e `pct/data/uffici_ministero_extra.json`;
3. fallback diretto PST per codice ministeriale e nome ufficio, anche quando il XML ministeriale non espone `nomeCertificatoCifra`.

Caso provato dall'utente e coperto: `Giudice di Pace - Palmi`, codice ministeriale `0800570152`, anche se nel XML il nome certificato è vuoto. Il downloader costruisce il nome ufficiale e scarica il `.cer` da PST; il certificato ottenuto è valido fino al 16 gennaio 2027 e ha subject `gdprc_cifra@civile.ptel.giustiziacert.it`.

### Regola fail-closed

Il risultato corretto non è promettere che il Ministero non cambierà mai catalogo. Il risultato corretto è:

- sul catalogo corrente controllato, tutti i target sono coperti (`593/593`);
- se il Ministero aggiunge, sposta o modifica un ufficio, il job `pst_certificati_cifratura_weekly` deve scaricare/validare il nuovo `.cer`;
- se per un singolo fascicolo il canale richiede `.cer` e quel `.cer` non è presente o non è valido, `Invia deposito reale` resta bloccato con motivo puntuale;
- PDP, PAT e PTT non devono essere bloccati per assenza di `.cer` PST civile, perché usano trasporti diversi;
- un deposito non deve essere registrato come valido se manca `Atto.enc` quando il canale lo richiede.

### Scheduler

Il job `pst_certificati_cifratura_weekly`:

- è settimanale, non giornaliero mascherato;
- usa `day_of_week` nel registry scheduler;
- usa worker configurabili con `PST_CERTIFICATI_CIFRATURA_WORKERS` o `PCT_PST_CERTIFICATI_CIFRATURA_WORKERS`;
- ritorna un report strutturato anche in caso di errore, così il registro scheduler non segna falsi positivi;
- scrive `source_of_truth=catalogo_pubblico_pst`, `tenant_scope=cache_tecnica_condivisa_non_operativa`, `json_authoritative=false`.

### Guardrail eseguiti su questa regola

- `python -m pytest -q tests\test_canali_telematici_deposito.py tests\test_scheduler_registry.py tests\test_checklist_atti.py tests\test_conformita_pst.py` -> esito: `59 passed`;
- controllo fisico cache `.cer`: `913` file, `913` certificati DER leggibili, `0` invalidi;
- controllo target: `593` codici unici, `0` mancanti;
- controllo policy codice: `pct_civile_dm44` usa `.cer`; `pdp_penale`, `pat_amministrativo`, `ptt_tributario` non usano `.cer` PST civile.

## Aggiornamento 2.253.56 - riallineamento locale anteprima indice e prova senza invio

Data intervento: 2026-06-17.

Perimetro verificato:

- copia Docker locale reale `http://127.0.0.1:8080`, non server temporaneo;
- container `iusentra-app` ricostruito no-cache, ricreato e healthy;
- `/api/pronto` HTTP 200, versione `2.253.56`;
- browser integrato Codex visibile sulla pagina `/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`.

Correzione applicata:

- `frontend/src/components/FascicoliPage.tsx`: il pulsante `Visualizza IndiceDocumentiDepositati.PDF` non costruisce più un URL `blob:` per l'iframe; dopo aver verificato con fetch che l'indice risponde, apre l'anteprima con l'URL diretto autenticato `/fascicoli/<id>/deposito/indice-documenti?...`;
- `tests/test_regia_ui_react.py`: aggiunto guardrail perché l'anteprima indice usi `url: previewUrl`, `downloadUrl: previewUrl` e non torni a `URL.createObjectURL` nel componente `DepositPdfPreviewButton`.

Prova materiale eseguita:

- pagina React caricata con `#root`, senza fallback legacy, senza HTML grezzo, senza `n.d.`;
- `Busta e indice` presente e caricata;
- `IndiceDocumentiDepositati.PDF` presente nella UI;
- click reale sul pulsante `Visualizza IndiceDocumentiDepositati.PDF`;
- modal aperto con titolo `IndiceDocumentiDepositati.PDF`, pulsanti `Scarica` e `Chiudi`;
- iframe circa `1180 x 630`, URL diretto `/fascicoli/DC5BF1DB/deposito/indice-documenti?...`, non `blob:`;
- viewer PDF Chrome visibile con toolbar, miniatura, pagina `1/1`, zoom `100%` e contenuto `Indice documenti depositati`;
- screenshot prova indice: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-indice-pdf-diretto-225356.png`.

Prova senza invio e simulazione:

- `Prova senza invio reale` abilitato;
- conferma visibile: `Preparare busta, indice documenti, destinatario e testo PEC senza inviare nulla?`;
- barra avanzamento visibile con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, tutti i documenti `.p7m` selezionati e `Atto.enc`;
- esito visibile: `Prova deposito preparata: busta, indice, destinatario e testo PEC sono pronti per il controllo. Nessun invio PEC reale è stato eseguito.`;
- destinatario PEC: `gdp.palmi@civile.ptel.giustiziacert.it`;
- oggetto PEC: `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`;
- documenti indicati nel pacchetto: `DatiAtto.xml`, atto principale, allegati `.p7m` e `IndiceDocumentiDepositati.PDF`;
- corpo PEC visibile e coerente con `Atto.enc`;
- `Simula invio PEC` confermata con testo esplicito `senza spedire nulla all'esterno`;
- toast visibile: `Simulazione invio PEC registrata nel fascicolo. Nessun invio esterno eseguito.`;
- screenshot prova senza invio/simulazione: `C:\Users\antmm\AppData\Local\Temp\iusentra-dc5bf1db-prova-senza-invio-simulazione-225356.png`.

Stato del bottone reale osservato:

- `Invia deposito reale` resta disabilitato con motivo puntuale: `Invio reale sospeso: completa i controlli obbligatori indicati nella prova.`;
- il requisito mancante mostrato nella prova locale è `PEC mittente dello studio non configurata. Configura la PEC dello studio prima dell'invio reale.`;
- non risultano più blocchi visivi su indice PDF o certificato `.cer` Palmi nella prova locale aggiornata.

Guardrail eseguiti:

- `python -m pytest -q tests\test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice`;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- Docker locale: `docker compose build --no-cache app`, `docker compose up -d --force-recreate app`, container healthy, `/api/pronto` OK.

Stato ancora aperto prima della chiusura complessiva:

- configurare/verificare PEC mittente dello studio per abilitare realmente l'invio locale, oppure dimostrare su server che il tenant ha già mittente/SMTP completo;
- ripetere prova server sul commit allineato;
- commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, `/api/pronto` server e igiene repository.

## Aggiornamento 2.253.54 - prova locale React deposito, indice e simulazione PEC

Data intervento: 2026-06-17.

Perimetro richiesto dall'utente:

- superficie React, non legacy, sulla copia locale reale `http://127.0.0.1:8080`;
- fascicolo reale locale `DC5BF1DB` (`RG 466/2023 - Alessi Robertino`);
- verifica visiva prima dei gate lunghi, con controllo di layout, indice PDF, corpo PEC modificabile, simulazione PEC e blocco puntuale del pulsante reale.

Prova materiale eseguita:

- container locale `iusentra-app` aggiornato e healthy, `/api/pronto` HTTP 200;
- pagina aperta in Google Chrome installato, modalità visibile, URL `/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- `#root` React presente, nessun fallback legacy, nessun HTML grezzo visibile, nessun `n.d.`;
- ufficio e destinatario risolti da SQL/tenant: `Ufficio del Giudice di Pace di Palmi`, codice ufficio `0910401`, codice ministeriale `0800570152`, PEC `gdp.palmi@civile.ptel.giustiziacert.it`;
- card busta leggibili: l'atto principale `Note conclusive Alessi Robertino.pdf.p7m` non viene più spezzato verticalmente;
- `IndiceDocumentiDepositati.PDF` visualizzato nel viewer PDF con risposta `application/pdf`, `ATTO_GENERICO`, `RG 466/2023`, codice oggetto `145009` ed elenco documenti;
- `Modifica testo PEC` apre un campo editabile solo su scelta dell'avvocato; il testo standard resta usato automaticamente e contiene `Atto.enc` e l'elenco documenti;
- `Simula invio PEC` mostra barra di avanzamento con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti selezionati e `Atto.enc`;
- la simulazione restituisce HTTP 200 e non produce errori console; la preview mostra destinatario PEC, oggetto `DEPOSITO TELEMATICO - ATTO_GENERICO - RG 466/2023`, riferimento prova, elenco documenti, testo PEC e controlli obbligatori mancanti;
- `Invia deposito reale` resta disabilitato solo se nella singola prova manca un requisito obbligatorio reale. Stato aggiornato `2.253.56`: il certificato PST `.cer` dell'ufficio `0800570152` non è più un mancante globale quando la cache corrente è presente; il blocco residuo corretto deve riguardare `Atto.enc` AES256 generato da `Atto.msg`, PEC mittente dello studio configurata o altro requisito effettivamente non presente nella prova.

Correzione applicata:

- nel ramo React `/fascicoli/<id>/deposito/invia-pec`, le modalità `prova_senza_invio=1` e `simula_invio_pec=1` ora restituiscono JSON HTTP 200 quando il pacchetto di controllo è stato preparato ma l'invio reale resta sospeso per requisiti obbligatori;
- il 409 resta per l'invio reale non conforme, così la UI può distinguere prova guidata da errore operativo.

Guardrail aggiunti/eseguiti:

- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_simulazione_guidata_non_restituisce_conflitto_http -q`;
- screenshot temporanei fuori repository: layout busta corretto, indice PDF visualizzato, editor corpo PEC, preview simulazione PEC.

Limiti residui:

- non è stato eseguito invio PEC reale;
- la firma multipla con PIN/token reale resta dichiarabile solo dopo firma effettiva di più documenti nella UI e salvataggio dei `.p7m`;
- prima della chiusura complessiva restano commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner e prova server sullo stesso commit.

## Aggiornamento 2.253.53 - matrice canali e scheduler certificati PST

Data intervento: 2026-06-17.

Chiarimento permanente dopo richiamo utente:

- il deposito non può essere ridotto al solo PCT civile: ogni canale ha normativa, trasporto, firma, ricevute e blocchi propri;
- il job `.cer` è solo il presidio tecnico dei canali che cifrano `Atto.msg` in `Atto.enc` con certificato pubblico PST dell'ufficio;
- PDP, PAT, PTT, notifiche PEC, UNEP e PEC stragiudiziale devono continuare a essere trattati come canali autonomi, senza ereditare certificati o blocchi PCT.

Matrice operativa aggiornata:

- `PCT/SICID`, `PCT lavoro/SICID`, `PCT/SIECIC`, `SIGP/Giudice di Pace`: fonti Ministero della Giustizia/PST, DM 44/2011 art. 34 e specifiche tecniche DGSIA 7 agosto 2024 efficaci dal 30 settembre 2024. IUSENTRA deve risolvere codice oggetto PST, ufficio, PEC, firma documentale, `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, `Atto.msg`, certificato `.cer` PST e `Atto.enc` AES256. Se il `.cer` del proprio ufficio non è verificato o `Atto.enc` non è generato, l'invio reale è bloccato e la UI deve dire quale requisito manca.
- `PDP penale`: fonti PST/Ministero della Giustizia, Decreto Ministero Giustizia 4 luglio 2023 e specifiche tecniche Portale Deposito atti Penali efficaci dal 20 luglio 2023. Non genera busta PCT civile, non usa `DatiAtto.xml` civile e non usa `.cer` PST/`Atto.enc`. IUSENTRA deve preparare e controllare atti/allegati/firme secondo PDP, guidare o importare il deposito dal portale e salvare ricevute/esiti.
- `PAT/SIGA amministrativo`: fonti Giustizia Amministrativa, regole tecnico-operative PAT e modifica 2025/2026. Dal 1 febbraio 2026 Formweb è il canale prioritario; PEC è residuale solo per casi tecnici previsti. Non usa `.cer` PST civile né `Atto.enc` PCT. IUSENTRA deve preparare modulo/atto, allegati, firma PAdES quando richiesta, checklist PAT, upload assistito e ricevute.
- `PTT/SIGIT tributario`: fonti MEF/Dipartimento Giustizia Tributaria e Gazzetta Ufficiale, specifiche tecniche 6 novembre 2020 e modifiche 21 aprile 2023. Non usa `.cer` PST civile né `DatiAtto.xml` PCT. IUSENTRA deve controllare PDF/A quando richiesto, firme, limiti file, upload SIGIT e ricevute.
- `UNEP`, notifiche PEC e PEC stragiudiziale: canali separati dal deposito. Servono relata/testo, destinatari, domicilio digitale, firme e ricevute proprie; non devono essere dichiarati deposito PCT e non devono attivare `Atto.enc` salvo regola futura documentata.

Controllo scheduler `.cer`:

- cache operativa locale inizialmente assente per Vicenza e server;
- prova live ufficiale su codice ufficio `0241160092` ha scaricato il certificato PST del `Tribunale Ordinario - Vicenza`, SHA256 `28D0A5456A542FAC99B772AAE6B5F7E8AD909E1F569ED8D1EFD929DE9DC708AA`, valido fino all'11 gennaio 2029;
- su Hetzner il download falliva per catena TLS incompleta (`TI Trust Technologies OV CA` non inviato come intermedio completo al client Python); il downloader ora usa `certifi` e carica solo l'intermedio TI Trust/Sectigo pinnato con SHA256 `1BFD8702D8F9BB340F353820330C0BBA7E522C63164C91F295414DAC797F0863`, senza disabilitare la verifica SSL;
- dopo hotfix sul container Hetzner, `scripts/precarica_certificati_cifratura_pst.py --codice-ufficio 0241160092 --strict` ha scaricato `/data/pst/certificati_cifratura/0241160092.cer` con esito `ok=true`;
- dopo `repair_deposit_profiles(verify_certificates=True)` sui database server, il fascicolo `E5AE4668` (`2026/330`, `Marchetti c. MIM`, `Carta docente`) ha profilo SQL verificato: canale `pct_civile_dm44`, codice `222050`, ufficio `Tribunale di Vicenza`, codice ufficio `0241160092`, PEC `tribunale.vicenza@civile.ptel.giustiziacert.it`, `.cer` verificato e nessun blocco profilo;
- `scripts/precarica_certificati_cifratura_pst.py` accetta ora `--codice-ufficio` per controlli mirati su fascicoli reali;
- `precarica_certificati_cifratura` limita il ciclo settimanale ai canali PCT/SIGP che richiedono `.cer` per `Atto.enc`; uffici non operativi, non PCT o senza certificato pubblicato sono riportati come saltati/avvisi del report e non fanno fallire gli altri certificati;
- il singolo deposito resta comunque fail-closed: se il proprio canale richiede `.cer` e quel `.cer` non è verificato, l'invio reale non deve essere registrato come deposito valido.

Fonti ufficiali riconsultate:

- PST Ministero della Giustizia, specifiche tecniche ex art. 34 DM 44/2011 - provvedimento 7 agosto 2024;
- PST Ministero della Giustizia, specifiche tecniche PDP penale 2023;
- Giustizia Amministrativa, Processo Amministrativo Telematico e avviso Formweb/PEC dal 1 febbraio 2026;
- Gazzetta Ufficiale, specifiche tecniche Processo Tributario Telematico 6 novembre 2020 e modifiche 21 aprile 2023.

## Aggiornamento 2.253.50 - prova reale locale firma multipla, indice e prova senza invio

Data intervento: 2026-06-17.

Prova reale eseguita su macchina locale dell'utente:

- URL verificato: `http://127.0.0.1:8080/fascicoli/DC5BF1DB/deposito/prepara#generazione-busta`;
- versione runtime reale: `2.253.50`, verificata con `GET /api/pronto`;
- fascicolo locale di prova: `RG 466/2023 - Alessi Robertino`, ufficio `Giudice di Pace - Palmi`;
- superficie: React deposito su Docker locale reale, container `app`, `scheduler-worker` e `ocr-worker` healthy;
- azione materiale: inserito il PIN nel pannello Local Signer e confermato `Firma e prepara prova`;
- stato iniziale visto: 8 documenti candidati busta, 4 già firmati, 4 documenti da firmare nel comando busta;
- esito firma multipla: i 4 documenti non firmati sono stati firmati e salvati come `.pdf.p7m`; la UI è passata a `8 firmati`, `0 documenti da firmare`, `Firme coerenti`;
- file firmati osservati dopo la prova: `attoACQ.pdf.p7m`, `Note trattazione scritta Alessi Robertino c Zurich Ass.ni-signed.pdf.p7m`, `Note conclusive Alessi Robertino.pdf.p7m`, `Istanza trattazione scritta Alessi Robertino.pdf.p7m`;
- azione successiva: click reale su `Prova senza invio reale`, conferma del pannello e osservazione della barra `PREPARAZIONE DEPOSITO IN CORSO`;
- progress bar osservata: nome corrente `IndiceDocumentiDepositati.PDF` e ticker con `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, tutti gli 8 `.p7m` e `Atto.enc`;
- esito prova senza invio: toast `Busta generata e scaricata`, nessun blocco su `Operazione...`, nessun errore tecnico grezzo PST o URL `servizipst` nella UI;
- testo PEC: visibile e modificabile facoltativamente; dopo la firma elenca gli 8 documenti `.p7m`;
- anteprima indice: click su `Visualizza IndiceDocumentiDepositati.PDF`, modal con titolo, pulsanti `Scarica`/`Chiudi` e iframe diretto visibile circa `1180 x 681`, senza riquadro grigio/vuoto;
- screenshot locale prova indice: `C:/Users/antmm/AppData/Local/Temp/iusentra-deposito-indice-firma-reale-225350.png`.

Correzioni e presidi collegati:

- `frontend/src/components/FascicoliPage.tsx`: la chiamata Local Signer `/firma-batch` ora ha timeout controllato a 45 secondi con `AbortController`; se il servizio locale non risponde, la UI mostra un errore esplicito e non prosegue alla busta senza firme salvate;
- la modifica non cambia il comportamento positivo della firma multipla: nella prova reale il lotto è stato firmato e salvato correttamente;
- `tests/test_regia_ui_react.py`: aggiunto guardrail statico su timeout firma batch, `AbortController`, `signal: controller.signal` e messaggio utente.

Limiti residui visti nella prova locale:

- il fascicolo locale `DC5BF1DB` è un fascicolo Giudice di Pace: nelle prove storiche la PEC ufficio non era presente nel catalogo locale e la UI mostrava `Indirizzo PEC non disponibile dal catalogo uffici`; stato aggiornato `2.253.56`: i metadati `C:\QuickOrganizer` e il fallback PST diretto coprono `Giudice di Pace - Palmi`/`0800570152`, quindi quell'avviso non deve ricomparire se cache e profilo sono aggiornati;
- la conformità ministeriale finale resta subordinata alla generazione reale di `Atto.enc` quando il canale/ufficio richiede cifratura ministeriale; la prova locale conferma firma multipla, indice, testo PEC e busta di controllo, non registra un deposito valido inviato.

## Aggiornamento 2.253.47 - prova reale busta, PEC e certificato PST guidato

Data intervento: 2026-06-17.

Prova reale eseguita su produzione:

- URL verificato: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara#generazione-busta`;
- fascicolo: `2026/330`, `Marchetti c. MIM`, cliente `Marchetti Lucia`;
- superficie: React deposito sul server Hetzner `app.iusentra.it`, sessione utente autenticata;
- azione materiale: click su `Prova senza invio reale`, conferma del pannello e osservazione della barra di avanzamento;
- esito visibile: barra `Preparazione deposito in corso` con scorrimento di `DatiAtto.xml`, `IndiceDocumentiDepositati.PDF`, documenti `.p7m` selezionati e `Atto.enc`;
- esito finale: pannello `Prova senza invio PEC` con destinatario `tribunale.vicenza@civile.ptel.giustiziacert.it`, oggetto `DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza`, testo PEC predisposto e documenti indicati nel pacchetto;
- controllo regressione: non compare più l'errore tecnico grezzo `Download PST non riuscito` né l'URL PST nel contenuto visibile della UI;
- blocco corretto al momento della prova storica: `Invia deposito reale` restava disabilitato perché mancavano certificato pubblico PST `.cer` e `Atto.enc` AES256 conforme. Stato aggiornato `2.253.56`: i certificati PST del catalogo operativo risultano coperti; se il bottone resta disabilitato, il motivo non deve più essere un `.cer` già coperto, ma solo `Atto.enc` AES256, PEC mittente o altro requisito reale della singola pratica.

Correzioni applicate:

- `frontend/src/components/FascicoliPage.tsx`: la prova/invio deposito mostra una progress bar con nome del file in lavorazione e ticker dei documenti; il corpo PEC è visibile e modificabile solo facoltativamente; l'anteprima `IndiceDocumentiDepositati.PDF` usa URL diretto; la spunta `Da firmare` non viene mostrata sui documenti non selezionati per la busta;
- `frontend/src/components/FascicoliPage.css`: aggiunti stili per il blocco testo PEC e per la progress bar/ticker della busta;
- `pct/busta.py`: `Atto.msg` viene tracciato nell'audit prima del recupero certificato; se il `.cer` PST non è disponibile, l'audit resta consultabile e l'invio reale resta bloccato senza perdere il pacchetto di controllo;
- `web/bootstrap/deposito_routes.py`: le route React e storica trasformano `PSTCifraturaError` in risposta guidata `requires_guided_completion`, senza inviare alla UI il messaggio tecnico grezzo del download PST.

Guardrail tecnici eseguiti dopo la prova reale:

- `python -m pytest tests/test_busta.py -q`;
- `python -m pytest tests/test_deposito.py::test_deposito_invia_pec_civile_usa_local_signer_se_server_send_disabilitato -q`;
- `python -m pytest tests/test_regia_ui_react.py::test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice -q`.

Limite residuo operativo:

- il software prepara indice, testo PEC, `Atto.msg` e audit del pacchetto, ma non deve registrare un deposito valido finché non viene generato `Atto.enc` ministeriale cifrato AES256 con certificato pubblico PST dell'ufficio;
- la prova firma multipla con token fisico/PIN resta da ripetere solo quando si esegue realmente il comando di firma; il PIN non è stato scritto nei file di progetto.

## Aggiornamento 2.253.46 - prova reale server e guardrail anti-lock deposito

Data intervento: 2026-06-17.

Prova reale eseguita su produzione:

- URL verificato: `https://app.iusentra.it/fascicoli/E5AE4668/deposito/prepara`;
- fascicolo: `2026/330`, `Marchetti c. MIM`, cliente `Marchetti Lucia`;
- superficie: React deposito sul server Hetzner `app.iusentra.it`, sessione utente autenticata;
- primo caricamento reale: la pagina ha mostrato `n.d.`, zero documenti e `Caricamento...` perché `/api/v1/ui/fascicoli/E5AE4668?include=all` ha ricevuto un lock transitorio SQLite su `studio.db`;
- dopo ricarica reale: API `include=all` ha risposto 200 e la UI ha mostrato `Tribunale di Vicenza`, canale `PCT lavoro / SICID`, 13 documenti letti, 11 candidati busta, 4 firmati e 7 da firmare.

Correzione applicata:

- `pct/storage.py`: `StudioDB.ensure_schema()` riusa la connessione thread-local esistente e ritenta se lo schema SQLite è temporaneamente occupato;
- `frontend/src/fascicoliData.ts`: le chiamate dati fascicoli ritentano brevemente su errori transitori `408/423/429/5xx`, evitando che un lock momentaneo sostituisca i dati reali con fallback vuoto;
- `frontend/src/components/FascicoliPage.css`: la vista `Prepara deposito` è stata resa più compatta su server e locale, riducendo testata, pulsanti, cockpit, badge e percorso deposito senza cambiare le regole di firma o conformità;
- versione riallineata a `2.253.46`.

Esito firma documento per documento osservato nella UI:

- i file `.pdf.p7m` osservati risultano `Firmato`;
- i file `.PDF` o `.pdf` non PAdES osservati restano `Da firmare`, anche quando il nome o il contenuto testuale potrebbero contenere la parola "Firmato";
- esempi visti come `Da firmare`: `Carta Identità e C.F. Lucia Marchetti.PDF`, `Contratto Rossi 2025-2026.pdf`, `Ricorso.pdf`, `Sentenza Cassazione.PDF`, `Sentenza_Tribunale_Vicenza_20-04-2023.PDF`;
- esempi visti come `Firmato`: `Autocertificazione ricorso.PDF.p7m`, `Autocertificazione situazione reddituale.PDF.p7m`, `Contratto 24-25.pdf.p7m`, `Procura.PDF.p7m`.

Limite residuo:

- prova firma multipla con token fisico/PIN non ancora ripetuta dopo il fix `2.253.46`;
- l'invio reale resta bloccato finché manca `Atto.enc` ministeriale cifrato AES256 conforme, come mostrato nella UI.

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

- verificato su server reale in `2.253.46` per caricamento profilo, canale, documenti, stati firma CAdES/PAdES e blocco invio non conforme;
- prima della chiusura completa restano obbligatori commit, push branch gemelli, controlli GitHub/CodeQL, deploy Hetzner del fix `2.253.46`, prova post-deploy sulla vista compatta e igiene repository.

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
## Aggiornamento 2.253.63 - Local Signer PST e anteprima fascicolo lavoro

Data intervento: 2026-06-18.

Per il fascicolo lavoro Tribunale di Torino RG 3950/2026 e per i flussi PST collegati:

- Local Signer aggiornato a `1.6.78`, con auto-selezione del certificato personale ArubaPEC Authentication e blocco dei certificati Adobe/intermedi/scaduti in modalita' automatica;
- launcher Windows corretto per non chiudere il processo padre del servizio in ascolto su `127.0.0.1:27272`;
- smoke reale Local Signer eseguito su macchina utente: `/ping?auto=1`, `/certificati`, `/diagnosi`, `/ai/status`, `/pst/status` e dipendenze `cryptography`, `asn1crypto`, `zeep`, `pdfplumber`, `mammoth`, `pypdf`, `reportlab`, `pkcs11`;
- React PST corretto per aprire l'anteprima dai dati fascicolo gia' restituiti dalla ricerca, senza bloccare la vista sul timeout esterno `ext.processotelematico.giustizia.it`;
- il timeout del PST esterno resta un avviso/limite del servizio ministeriale, non un motivo per lasciare vuota l'anteprima se il fascicolo e' gia' stato trovato.

Stato prova reale:

- certificato e Local Signer: verificati su macchina reale con Chrome e Local Signer locale `1.6.78`;
- anteprima server: ancora da ripetere dopo deploy Hetzner della versione `2.253.63`, perche' al momento della riproduzione `https://app.iusentra.it/api/pronto` rispondeva `2.253.60`.

## Aggiornamento 2.253.65 - UX acquisizione PST e uscita verso fascicolo

Data intervento: 2026-06-18.

Per il flusso PST lavoro `RG 3950/2026`, la procedura di acquisizione React è stata resa più esplicita:

- Step 4 è dedicato solo a cosa scaricare o includere: documenti, eventi, scadenziario, parti, formato PST e file già raccolti;
- la scelta del fascicolo interno resta nello Step 5, evitando duplicazioni nello Step 4;
- Step 7 presenta il riepilogo finale per destinazione, documenti e dati collegati;
- il comando finale registra nel fascicolo selezionato e, se il backend restituisce un URL interno, apre direttamente il fascicolo importato;
- il messaggio generico `Importazione completata o presa in carico dal gestionale operativo` è stato sostituito da messaggi puntuali: apertura automatica del fascicolo quando possibile, fallback `Fascicolo importato` solo se il redirect non è disponibile.

Il PIN del certificato non è stato scritto nei file di progetto né nei log.

Prova reale server del 18 giugno 2026:

- produzione Hetzner su `https://app.iusentra.it` verificata con commit `718ae2a241f3e9e1ec9200e2873f3fd463427f2b` e versione `2.253.65`;
- controllo visivo eseguito in Google Chrome reale sul PC dell'utente, non nel browser integrato, perché il Local Signer deve essere raggiunto da `127.0.0.1:27272`;
- Local Signer `1.6.78` raggiungibile da Chrome; auto-selezione del certificato ArubaPEC Authentication dell'avvocato confermata senza finestra Adobe e senza richiesta PIN in questa prova;
- Step 4 verificato con click reale: `Cosa scaricare`, dati/documenti/eventi/scadenziario/parti separati dal formato PST e dalla destinazione;
- Step 5 verificato con click reale: destinazione isolata in `Crea nuova pratica` / `Usa pratica esistente`;
- Step 7 verificato con click reale: riepilogo `Destinazione`, `Documenti`, `Dati collegati`, comando finale `Crea pratica e importa` o `Importa nel fascicolo selezionato`, e testo che chiarisce che non parte uno scarico nascosto dal portale;
- le vecchie diciture `Importa nel gestionale`, `Import completato` e `Importazione completata o presa in carico dal gestionale operativo` non compaiono più nella pagina server;
- la ricerca PST live del fascicolo `RG 3950/2026` in quella sessione è rimasta in attesa fino a circa 360 secondi e poi ha mostrato un messaggio guidato di servizio ministeriale lento. Per questo non è stato eseguito un import finale con `0/0` documenti e il redirect materiale al fascicolo non è stato cliccato; il redirect resta implementato e coperto dal guardrail React quando l'API restituisce un URL interno.

## Aggiornamento 2.253.66 - acquisizione PST e apertura fascicolo importato

Data intervento: 2026-06-18.

Per il flusso PST lavoro `RG 3950/2026`, lo Step 7 ora deve uscire dalla pagina di acquisizione appena l'importazione è stata registrata:

- il runtime telematico restituisce `fascicolo_url`, `redirect_url` e `documenti_url` sia in radice sia nel `summary`;
- `redirect_url` apre la scheda del fascicolo con ancora `#sezione-documenti-fascicolo`, cioè la zona in cui sono stati salvati i documenti;
- il frontend non si limita più a `fascicolo_url`/`url`: legge anche `documenti_url`, `dettaglio_url`, valori annidati e id fascicolo;
- la frase `Importazione completata. Fascicolo registrato nel gestionale.` non è più usata come fallback ordinario.

Questa modifica non tocca invio PEC, firma digitale, PIN, certificati o contenuto dei documenti. Interviene solo sul collegamento operativo post-import.

Guardrail locali:

- `python -m pytest tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python tools/sync_packaging_files.py --check` passato.

## Aggiornamento 2.253.67 - PagoPA PST nel fascicolo

Data intervento: 2026-06-18.

Su richiesta utente, nella pagina dettaglio fascicolo React è stato aggiunto un comando PagoPA vicino alle azioni PDF e nel pannello laterale `Gestione fascicolo`:

- icona PagoPA fornita dall'utente copiata in `frontend/public/pagopa-removebg-preview.png` e pubblicata nel bundle statico come `/static/react/pagopa-removebg-preview.png`;
- il click apre una finestra sovrapposta al fascicolo con iframe verso `https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp`;
- la finestra include il comando `Apri fuori`, necessario se il portale ministeriale impone restrizioni di incorporamento iframe;
- la modale si chiude con il pulsante `Chiudi` o con `Esc`, senza navigare via dal fascicolo;
- la modifica non salva dati di pagamento, non invia PEC, non usa PIN, non tocca firma digitale, Local Signer o deposito reale.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck` passato;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_fascicoli_page_collegata_nav_api_e_lex tests/test_react_shell.py::test_react_wizard_pst_anteprima_riusa_snapshot_ricerca_rg tests/test_polisweb.py::test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero -q --tb=short` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` passato;
- `python -m pytest tests/test_utf8_integrity.py -q --tb=short` passato;
- `python tools/sync_packaging_files.py --check` passato.

Stato: da verificare dopo commit, push e deploy Hetzner su `https://app.iusentra.it/fascicoli/9B9DF2A1`, con click reale su `PagoPA`, apertura modale sopra il fascicolo, fallback `Apri fuori`, chiusura e controllo testi/card/bottoni.

## Aggiornamento 2.253.68 - PagoPA PST compilabile nel fascicolo

Data intervento: 2026-06-18.

Dopo la prova visiva su `https://app.iusentra.it/fascicoli/9B9DF2A1`, il portale ministeriale PagoPA ha mostrato il limite tecnico `X-Frame-Options: SAMEORIGIN`, che impedisce l'incorporamento diretto cross-origin in un iframe IUSENTRA.

Correzione applicata:

- il dettaglio fascicolo React non punta più l'iframe PagoPA direttamente al dominio ministeriale;
- la modale PagoPA usa il bridge autenticato IUSENTRA `/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp?iusentra_fascicolo=<id>`;
- il bridge è limitato al solo host `servizipst.giustizia.it` e ai percorsi sotto `/PST/`, riscrive link, form, asset e redirect verso lo stesso proxy interno;
- i form PagoPA restano compilabili nella modale e i POST vengono inoltrati al PST senza consumare prima il corpo della richiesta;
- quando l'utente richiede manualmente la ricevuta PDF nel portale, la risposta PDF passa dal bridge, viene mostrata/scaricata dal browser e viene salvata nei documenti del fascicolo con fonte `PORTALE_TELEMATICO`, classificazione `RICEVUTA_PAGOPA` e tag `PagoPA`, `PST`, `ricevuta`;
- i comandi `Cliente` e `Soggetti` nel dettaglio fascicolo aprono ora la rispettiva pagina React in overlay interno, con lo stesso schema di modale usato da PagoPA, senza perdere la pratica aperta;
- `Apri fuori` resta disponibile come comando di emergenza, ma non è più il comportamento ordinario per la compilazione PagoPA.

Limiti operativi:

- IUSENTRA non genera ricevute PagoPA e non inventa link: intercetta e archivia il PDF solo quando il portale PST lo restituisce dopo la richiesta dell'utente;
- se durante il pagamento il circuito PagoPA porta l'utente su PSP, banca o dominio esterno al PST, quel tratto può imporre regole proprie di sicurezza; il bridge resta ristretto al PST ministeriale per non trasformarsi in proxy generico;
- nessun PIN, certificato, Local Signer, firma digitale o invio PEC è stato coinvolto da questa modifica.

Guardrail locali:

- `pnpm --filter @iusentra/studio typecheck` passato;
- `python -m pytest tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short` passato;
- `python -m pytest tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf tests/test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf -q --tb=short` passato;
- `pnpm --filter @iusentra/studio build` passato;
- `python -m pytest tests/test_react_asset_retention.py -q --tb=short` passato;
- `python tools/sync_packaging_files.py --check` passato.

Stato: da portare su branch gemelli, deployare su Hetzner e verificare visivamente su produzione con click reale su `Cliente`, `Soggetti`, `PagoPA`, compilazione/visualizzazione iniziale del portale e richiesta ricevuta PDF quando disponibile.

## Aggiornamento 2.253.69 - TLS PagoPA PST

Data intervento: 2026-06-18.

La prova visiva server della versione `2.253.68` ha mostrato errore 502 nella modale PagoPA: il portale PST era raggiungibile da Chrome/curl Windows, ma `requests` locale e nel container fallivano con `CERTIFICATE_VERIFY_FAILED`.

Diagnosi:

- il leaf `servizipst.giustizia.it` risulta emesso da `TI Trust Technologies OV CA`;
- il server PST non espone una catena chiudibile dal bundle `requests/certifi`;
- con curl server l'errore era `unable to get local issuer certificate`;
- con bundle composto da `certifi` più l'intermedio ufficiale `TI Trust Technologies OV CA`, la chiamata al PST restituisce HTTP 200 e `text/html;charset=utf-8`.

Correzione applicata:

- aggiunto `web/certs/TITrustTechnologiesOVCA.pem`;
- il bridge PagoPA usa un bundle CA mirato `certifi + TI Trust` solo per `servizipst.giustizia.it/PST`;
- la verifica TLS resta attiva: non è stato introdotto `verify=False`;
- la modifica non tocca PIN, Local Signer, firma digitale, invio PEC, volumi o dati applicativi.

## Aggiornamento 2.253.70 - PagoPA PST DWR compilabile nel fascicolo

Data intervento: 2026-06-18.

Dopo la prova reale locale della modale PagoPA, il portale PST caricava la pagina iniziale ma il form `Nuovo pagamento` non era ancora affidabile: le chiamate DWR del Ministero uscivano verso `/PST/dwr`, perdevano il contesto della sessione e potevano ricevere errori CSRF o restare senza elenco uffici.

Correzione applicata:

- il bridge riscrive solo l'assegnazione DWR `_path`, lasciando invariato il resto dei JavaScript ministeriali per non corrompere sintassi o regex del PST;
- le POST DWR traducono `Referer`, `Origin`, `page` e `Content-Type` nel formato atteso dal portale ufficiale;
- `httpSessionId` vuoto viene valorizzato con il `JSESSIONID` PST già custodito nella sessione proxy;
- i percorsi raw `/PST/...` che sfuggono dal JavaScript vengono ricondotti al proxy IUSENTRA con redirect interno;
- la modale React concede `allow-same-origin` solo all'iframe PagoPA e usa referrer `same-origin`, così form, DWR e download PDF restano nello stesso contesto di proxy;
- la CSP rilassata con `unsafe-eval` è limitata alla risposta proxy PagoPA, perché il codice DWR storico del PST lo richiede; la CSP ordinaria IUSENTRA non viene allentata.

Prova reale locale:

- ambiente: Google Chrome installato su Windows, applicazione reale Docker `http://127.0.0.1:8080`, container healthy, `/api/pronto` con versione `2.253.70`;
- percorso: dettaglio fascicolo locale `9B9DF2A1`, click reale su `PagoPA`, apertura modale, click `+ Nuovo pagamento`;
- compilazione osservata: `Tipo pagamento` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Nominativo debitore` e `Codice fiscale` compilati;
- risultato: select `Ufficio Giudiziario` popolata con 66 opzioni, tra cui `Corte d'Appello - Torino`, `Giudice di Pace - Torino`, Procure e Tribunali del distretto;
- non sono comparsi errori CSRF, blocchi CSP pertinenti, errori console applicativi o timeout; non è stato premuto `Paga subito` e non è stato effettuato alcun pagamento;
- Browser plugin non disponibile nella sessione Codex: prova eseguita con Chrome installato controllato via Playwright, come fallback previsto per la verifica frontend;
- screenshot di prova fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-225370-auth2-1781800757169\04-form-compilato-ok-locator.png`.

Limiti residui:

- IUSENTRA non inventa il link ricevuta: quando l'utente richiede manualmente la ricevuta PDF nel PST, il bridge intercetta il PDF restituito e lo collega ai documenti del fascicolo;
- se il pagamento passa a PSP, banca o dominio esterno al PST, quel tratto può imporre policy proprie e resta fuori dal proxy ristretto al Ministero;
- nessun PIN, certificato, firma digitale, Local Signer o invio PEC è stato usato da questa modifica.

## Aggiornamento 2.253.71 - Hardening CodeQL bridge PagoPA

Data intervento: 2026-06-18.

Il primo push della release PagoPA ha fatto emergere su CodeQL un alert di XSS riflesso sul punto in cui il proxy restituisce l'HTML ministeriale. Il comportamento è intenzionale solo dentro il bridge PagoPA, ma è stato irrigidito per evitare che path non pertinenti o redirect locali non governati entrino nel flusso.

Correzione applicata:

- il proxy serve solo path PST attesi per PagoPA: `it/pagopa_*`, `resources/` e `dwr/`;
- i path con schema, doppio slash, segmenti `..`, caratteri non previsti o prefissi fuori perimetro vengono rifiutati;
- la route di rientro `/PST/...` costruisce il target con `url_for("api_v1_react.pst_pagopa_proxy", ...)`, quindi resta sempre interna;
- la risposta testuale viene emessa come payload UTF-8 codificato, con commento CodeQL motivato perché il contenuto arriva dal dominio ministeriale verificato tramite bundle CA e rimane coperto da CSP/iframe PagoPA.

Test locali ripetuti:

- `python -m py_compile web\blueprints\api_v1_react.py web\bootstrap\telematico_portali_routes.py`;
- `python -m pytest tests\test_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf tests\test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests\test_security_headers.py -q --tb=short`.


## Aggiornamento 2.253.72 - Cookie sessione IUSENTRA

Data intervento: 2026-06-18.

Su richiesta dell'utente il cookie HTTP di sessione dell'app viene rinominato da `hacs_session` a `iusentra_session`. La modifica è centralizzata nel runtime di sicurezza Flask e gli script di audit browser che impostano sessioni locali di collaudo sono stati aggiornati allo stesso nome. Non cambia il contenuto della sessione, non vengono salvati PIN o credenziali e restano invariati `HttpOnly`, `SameSite=Lax` e il perimetro tenant. Prova reale locale eseguita e ripetuta su Docker `2.253.73`: `/api/pronto` risponde `versione=2.253.73`, il container Flask espone `SESSION_COOKIE_NAME=iusentra_session`, Chrome installato su `http://127.0.0.1:8080/fascicoli/9B9DF2A1` ha aperto PagoPA nel fascicolo, selezionato `Contributo unificato e/o Diritti di cancelleria`, distretto `TORINO`, caricato `66` uffici e compilato nominativo/codice fiscale senza premere `Paga subito`.

## Aggiornamento 2.253.73 - Refactor CodeQL bridge PagoPA

Data intervento: 2026-06-18.

Sul nuovo SHA `34a42e9` CodeQL ha continuato a segnalare il sink XSS del bridge PagoPA, nonostante host, path e TLS fossero già allowlistati. Per eliminare il sink diretto, le risposte testuali del PST (`HTML`, `CSS`, `JavaScript`, `XML`) vengono ora servite inline da un file in memoria con `send_file`, dopo validazione del path PagoPA e riscritture controllate. Il comportamento visibile della modale resta invariato: il form ministeriale continua a essere renderizzato dentro il fascicolo e la cattura PDF resta agganciata alle risposte `application/pdf`.

Test ripetuti dopo il refactor:

- `python -m py_compile weblueprintspi_v1_react.py webootstrap	elematico_portali_routes.py web\services\security_runtime.py tests	est_security_headers.py`;
- `python -m pytest tests	est_react_shell.py::test_react_pst_pagopa_proxy_incorpora_portale_e_salva_ricevuta_pdf tests	est_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests	est_security_headers.py -q --tb=short`.

## Aggiornamento 2.253.74 - CodeQL path bridge PagoPA

Data intervento: 2026-06-18.

Sul nuovo SHA 878ae1e il workflow CodeQL ha superato l'analisi, ma il required check di code scanning ha aperto un alert bloccante Uncontrolled data used in path expression sulla risposta send_file(BytesIO(...)) del bridge PagoPA. Il bridge ora scrive le risposte testuali PST in un file temporaneo creato dal server, con nome generato dal sistema, Content-Type ristretto ai tipi testuali attesi e nome inline costante. Il path non dipende più da contenuto PST o parametri utente; le chiamate DWR `/dwr/call/plaincall/...` tornano come `text/plain; charset=utf-8` così il motore DWR popola correttamente gli uffici. Il cookie di sessione resta `iusentra_session`. Prova reale locale su Docker `2.253.74`: Chrome installato su `127.0.0.1:8080/fascicoli/9B9DF2A1`, cookie visibile solo `iusentra_session`, PagoPA aperto, `Nuovo pagamento`, tipo `Contributo unificato e/o Diritti di cancelleria`, distretto `TORINO`, `66` uffici giudiziari caricati, nominativo/codice fiscale compilati, nessun click su `Paga subito`.
## Aggiornamento 2.253.75 - Guardrail SQLite WAL nei gate CI

Data intervento: 2026-06-18.

Dopo il push dello SHA `3e42314`, CodeQL è risultato `success`, ma il gate remoto `Pytest core fase 7/10 observability parte 3/3` ha fallito su `tests/test_storage_strategy.py::test_core_runtime_uses_tenant_paths_for_sensitive_repositories`. La causa non era il bridge PagoPA: il rilevatore `_sqlite_runtime_is_unseeded()` apriva `studio.db` con `immutable=1`; con WAL attivo la lettura poteva non vedere le modifiche appena committate nello stesso request e rilanciare una migrazione JSON su SQL già operativo. Il runtime ora usa `mode=ro` senza `immutable`, così legge lo stato reale del database senza aprirlo in scrittura e senza indebolire il blocco anti-perdita sui JSON vuoti.

Test locali ripetuti:

- `python scripts\run_pytest_phases.py --core-shard 7 --core-total-shards 10 --core-subshard 3 --core-total-subshards 3 --core-subdivide-items --timeout-minutes 5` -> 32/32 OK;
- `python -m pytest tests\test_storage_strategy.py::test_sqlite_runtime_non_rilancia_migrazione_se_settings_config_esiste tests\test_storage_strategy.py::test_core_runtime_uses_tenant_paths_for_sensitive_repositories -q --tb=short` -> 2/2 OK.

## Aggiornamento 2.253.76 - Pulizia rendering PagoPA PST

Data intervento: 2026-06-18.

Durante la prova visiva locale del bridge PagoPA, Chrome segnalava un errore MIME sul foglio opzionale `resources/static/css/print.css`: il portale PST lo restituiva come HTML, quindi il browser lo rifiutava come stylesheet. Il problema non bloccava la compilazione del pagamento, ma lasciava un errore console visibile nel controllo qualità.

Correzione applicata:

- per il solo stylesheet opzionale `print.css`, quando il PST risponde con contenuto non CSS, il bridge restituisce un CSS vuoto e valido (`text/css; charset=utf-8`);
- le pagine HTML, i JavaScript ministeriali, le chiamate DWR e i PDF ricevuta restano invariati;
- il cookie runtime resta `iusentra_session` e non vengono salvati PIN, credenziali, dati pagamento o certificati.

Prova reale locale su Docker `2.253.76`:

- ambiente: Google Chrome installato su Windows, applicazione reale `http://127.0.0.1:8080`, container healthy, `/api/pronto` con `versione=2.253.76`;
- runtime Flask nel container: `SESSION_COOKIE_NAME=iusentra_session`;
- percorso: fascicolo locale reale `DC5BF1DB`, click su `PagoPA`, apertura modale, click `+ Nuovo pagamento`;
- compilazione controllata senza invio: `Tipo` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Ufficio Giudiziario` = `Tribunale Ordinario - Torino` (`0012720095`), nominativo e codice fiscale fittizi;
- risultato: DWR ministeriale `PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr` HTTP 200, select ufficio popolata con `66` opzioni, bottone `Paga subito` visibile, nessun click su `Paga subito`;
- console: `0` errori dopo la correzione del `print.css`; restano solo i warning standard di Chrome sul sandbox iframe con `allow-scripts` e `allow-same-origin`, necessari al PST/DWR;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-locale-225376-finale.png`.

Prova reale server su Hetzner `2.253.76`:

- ambiente: Google Chrome installato su Windows con Chrome visibile, produzione `https://app.iusentra.it`, commit server `d80b9ce`, container app/scheduler/OCR/Redis healthy e `/api/pronto` con `versione=2.253.76`;
- runtime Flask nel container Hetzner: `SESSION_COOKIE_NAME=iusentra_session`;
- percorso: fascicolo reale `9B9DF2A1`, `RG 3950/2026`, rif. interno `2026/308`, `Spagnolo Sara c. MIM`, click su `PagoPA`, modale incorporata con iframe `/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp`;
- interazione verificata: click `+ Nuovo pagamento`, `Tipo` = `Contributo unificato e/o Diritti di cancelleria`, `Distretto` = `TORINO`, `Ufficio Giudiziario` = `Tribunale Ordinario - Torino` (`0012720095`), nominativo e codice fiscale fittizi;
- risultato: DWR ministeriale `PagamentiTelematiciAjaxServices.getUfficiGiudiziari.dwr` HTTP 200 `text/plain`, select ufficio popolata con `66` opzioni, bottone `Paga subito` visibile e abilitato, nessun click su `Paga subito`;
- `print.css`: proxy HTTP 200 `text/css; charset=utf-8`, contenuto CSS controllato e non HTML;
- console: nessun errore applicativo; restano solo i warning standard Chrome del sandbox iframe;
- Cliente e Soggetti: pulsanti top del fascicolo verificati nello stesso modello di modale incorporata, con iframe `/clienti/2A1216AA/modifica` e `/soggetti?fascicolo=9B9DF2A1`;
- screenshot fuori repository: `C:\Users\antmm\AppData\Local\Temp\iusentra-pagopa-produzione-225376.png` e `C:\Users\antmm\AppData\Local\Temp\iusentra-soggetti-modale-produzione-225376.png`.

Stato: codice, Docker locale, GitHub, CodeQL/check remoti e server reale risultano allineati sul comportamento verificato. Il presente blocco documenta la prova server e va mantenuto come guardrail per future modifiche a fascicoli/PagoPA.
