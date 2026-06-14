# Piano operativo full React, PEC, agenda, scadenziario e deposito

Data: 14 giugno 2026

Questo file va riletto dopo ogni compattazione prima di riprendere il lavoro. Non sostituisce `AGENTS.md`: `AGENTS.md` resta la fonte obbligatoria da rileggere prima di ogni attività, modifica, test, commit, push, deploy o report.

## Obiettivo utente

Portare realmente tutto l'applicativo lato studio/prodotto a full React, eliminando le rotte rimaste su `?_legacy=1` quando esiste una superficie React governata, e correggere i flussi PEC che oggi sporcano Agenda e Scadenziario con voci generiche, duplicate o prive di informazione utile per l'avvocato.

L'utente chiede una prova visiva reale sulla macchina locale/remota, con browser reale su `http://127.0.0.1:8080` o `http://localhost:8080`, prima di dichiarare qualunque esito positivo.

## Regole operative da non dimenticare

- Non dichiarare mai "completato", "verde", "funzionante" o "risolto" senza verifica reale su Docker locale `127.0.0.1:8080` con browser reale visibile.
- I test automatici, TypeScript, build, Playwright o CDP sono solo guardrail tecnici. L'accettazione richiede click reali, scroll, hover, dati visibili e controllo dei testi.
- Le password ricevute dall'utente servono solo per la verifica runtime locale. Non scriverle nei sorgenti, nei report pubblici o in questo file.
- Le modifiche a dati runtime `data/` non vanno committate salvo decisione esplicita e motivata. Gli hash password locali sono dati runtime per test.
- Ogni modifica codice deve avere bump versione nei quattro file richiesti da `AGENTS.md`: `pct/__init__.py`, `setup.py`, `Dockerfile`, `railway.toml`.
- A fine lavoro reale servono: test mirati, build Vite, Docker locale no-cache, browser reale, report aggiornati, commit, push branch gemelli, check GitHub/CodeQL, deploy Hetzner, container healthy, `/api/pronto`, prune Docker.
- Nel deposito telematico non si rimanda a una "fase finale guidata" quello che il software può risolvere subito: classificazione, indice documenti e firma multipla devono essere eseguiti immediatamente quando i dati e il Local Signer sono disponibili.
- La firma multipla deve essere provata sulla macchina reale con browser reale, più documenti selezionati, PIN inserito dall'utente, salvataggio di ogni `.p7m` nel fascicolo e riabilitazione del passo successivo del deposito. Fino a quel test reale resta "non verificato su macchina reale".
- Dopo un test reale positivo la parte verificata va blindata: test mirati, guardrail statici/contratti, nota nel piano e divieto di refactor non necessari senza ripetere le verifiche specifiche.

## Registro avanzamento per compattazioni

Usare questi stati in modo rigoroso:

- `completata`: fase finita e, se visibile all'utente, verificata anche su macchina reale `127.0.0.1:8080`.
- `eseguita a livello codice`: modifica applicata e guardrail tecnico passato, ma manca test reale.
- `in corso`: modifica iniziata, da completare o da stabilizzare.
- `da fare`: fase non ancora eseguita.

| Fase | Stato | Prova/nota |
| --- | --- | --- |
| Creazione del piano operativo persistente | completata | File `artifacts/react-migration/full-react-pec-agenda-deposito-work-plan-2026-06-14.md` creato per ripresa dopo compattazione. |
| Aggiornamento credenziali runtime locale per test | completata | Hash aggiornati con `GestioneUtenti.cambia_password`; password non riportate in chiaro nel file. |
| Deposito prepara full React | eseguita a livello codice | Route e componenti già modificati; servono test reali su `/fascicoli/9B9DF2A1/deposito/prepara`. |
| Analisi campioni deposito reale RG 1754/2026 | completata | Letti in modo sanificato i campioni EML/MIME locali del deposito iniziale, deposito di ricorso notificato e deposito successivo di documento richiesto. Confermata struttura reale: PEC con `Atto.enc`, copia non crittografata con `DatiAtto.xml.p7m`, atto principale, NIR/procura/allegati, ricevute RAC/RdAC, attestazione, decreto notificato e indice documenti depositati. |
| Topbar operativa su route profonde | eseguita a livello codice | Recenti/notifiche deposito aggiornati; manca verifica reale dopo rebuild. |
| Policy PEC deposito fuori da Agenda/Scadenziario | in corso | Codice aggiornato per `pct_deposito`; test mirati e browser reale ancora da eseguire. |
| Agenda da PEC solo con orario certo | in corso | Codice aggiornato per evitare slot inventati; test mirati e dati reali ancora da verificare. |
| Google Calendar per scadenze senza orario | eseguita a livello codice | Le scadenze PEC senza orario non diventano appuntamenti finti in Agenda; il motore calendario le esporta/pusha come termini a giornata intera dallo Scadenziario, senza slot `09:00`, con testo professionale e deduplica tecnica. Manca prova reale su `127.0.0.1:8080`. |
| Motore Google Calendar diretto | eseguita a livello codice | Il canale principale e' il motore lettura/scrittura Google/Outlook; i link ICS/WebCal sono stati declassati a copia in sola lettura nella UI. Il push selettivo dopo scadenza PEC e' coperto da test; la lettura Google realmente push/webhook resta da completare e verificare. |
| Duplicati PEC in Agenda | in corso | Codice aggiornato per eliminare vecchie voci dello stesso audit PEC; da coprire con test. |
| Presidio PEC massivo incrementale | in corso | Filtro candidati aggiunto; da verificare con primo run, secondo run senza nuove PEC e run con PEC nuova. |
| Tooltip Agenda unico e leggibile | eseguita a livello codice | Rimosso `title` nativo e rifinito tooltip React; manca hover reale su browser. |
| Etichette scadenze senza orario | eseguita a livello codice | Bridge agenda invia `Entro giornata`/`Scadenza`; manca verifica visiva. |
| Pulizia testi tecnici Agenda/Scadenziario | eseguita a livello codice | Bridge Agenda, bridge Scadenziario, motore calendario e feed ICS sanitizzano i testi visibili; serve controllo browser reale sulle card e sugli hover. |
| Py compile mirato PEC/API/Agenda bridge | completata | `python -m py_compile pct\calendar_sync_engine.py pct\calendar_providers\google.py pct\ical.py pct\pec_pipeline.py web\blueprints\pec_pipeline_api.py` eseguito dopo patch calendario/PEC. |
| Typecheck React | completata | `pnpm --filter @iusentra/studio typecheck` eseguito dopo patch Agenda/Scadenziario/Impostazioni calendario. |
| Test pytest mirati aggiornati | eseguita a livello codice | 26 test mirati passati su PEC, udienze remote, deposito PEC, presidio locale, Agenda/Scadenziario React e calendario Google/ICS. |
| Build Vite finale | eseguita a livello codice | `pnpm --filter @iusentra/studio build` eseguito; resta warning storico sul chunk principale sopra 500 kB. Manca rebuild Docker reale. |
| Docker locale reale `127.0.0.1:8080` | completata | Rebuild no-cache `app scheduler-worker ocr-worker`, recreate e `/api/pronto` eseguiti sulla build corrente `2.253.14`; app, scheduler e OCR healthy. |
| Test visivo reale PEC -> Agenda/Scadenziario | completata | Audit Chrome visibile su `127.0.0.1:8080`: Agenda senza duplicati/tooltip nativi/eventi finti alle 09:00 nel range corrente; Scadenziario desktop/mobile scrollato top/medio/fondo, 8 card senza duplicati, card operative uniformi; Calendari con sincronizzazione diretta Google/Outlook. |
| Presidio da documento notificato nel fascicolo | eseguita a livello codice | Nuovo caso utente 14/06/2026: fascicolo produzione `EFBE9117`, RG 1754/2026, cliente Vinci Rosa Maria, tenant Studio Legale Giuseppe Montagnese; documento `Decreto fissazione udienza (originale notificato).pdf` in sezione Relata notifica. Il test mirato conferma estrazione di udienza 20/05/2026 ore 10:00, link Teams esatto non normalizzato, creazione di una sola scadenza e un solo evento Agenda, più deduplica al secondo import. Manca prova visiva reale sul fascicolo tenant. |
| Proposta busta e scelta manuale documenti | eseguita a livello codice | La pagina React `Prepara deposito` mostra proposta busta, atto principale, allegati collegati dagli slot, documenti da firmare, azione `Invia via PEC` o `Genera busta pronta`, e selettori manuali per collegare i documenti quando la classificazione non è certa. Test mirati su classificazione certa/incerta e codice oggetto PST passati. |
| Selezione documenti da inviare in busta | completata | Docker locale reale `2.253.16` ricostruito no-cache su `127.0.0.1:8080`; in browser visibile sulla pagina `/fascicoli/2DE106E6/deposito/prepara` la sezione `Documenti da inviare` mostra 2 checkbox, `Ripristina proposta`, `Seleziona tutti i documenti`, conteggio `2 selezionati`; togliendo la prima spunta il conteggio diventa `1 selezionato`, poi torna a `2 selezionati`. La card `Atto principale` non spezza più il nome file in verticale e lo scroll fino al fondo non mostra overflow orizzontale. |
| Docker/browser reale deposito `2.253.16` | completata | Eseguiti `pnpm --filter @iusentra/studio build`, `docker compose build --no-cache app scheduler-worker ocr-worker`, `docker compose up -d --force-recreate app scheduler-worker ocr-worker`; `/api/pronto` risponde `ok=true`, `versione=2.253.16`, container app/scheduler/OCR healthy. |
| Profilo pratica per documenti obbligatori | eseguita a livello codice | Il profilo determina cosa bisogna depositare per il tipo di pratica e non solo cosa l'avvocato ha selezionato. Guardrail aggiunto: `contratto` non viene più scambiato per `atto`; in `PROC_LIC_IMP_001` `Atto principale` resta obbligatorio separato e contratto/lettera/buste paga restano documenti di prova. |
| Aggiornamento PST XSD SICI 11/06/2026 | eseguita a livello codice | Fonte ministeriale verificata: il PST anticipa nuovi XSD SICI e rinvia a successiva comunicazione la messa in esercizio. IUSENTRA traccia `RichiestaVerbaleSINDACA` e codice `110046` come anticipazione non produttiva, senza usarli per validare depositi reali finché non saranno in esercizio. |
| Firma multipla immediata deposito | eseguita a livello codice | UI React e guardrail backend pronti: firma batch con un solo comando/PIN, salvataggio di ogni `.p7m`, blocco invio diretto se manca `Atto.enc` AES256 ministeriale. Serve test reale con PIN inserito dall'utente prima di qualunque esito positivo sulla macchina reale. |
| Report, bump versione, commit, push, deploy Hetzner | in corso | Bump `2.253.16`, gate tecnici, Docker reale e verifica visiva selezione documenti passati. Restano firma multipla con PIN, igiene runtime, commit, push branch gemelli, check GitHub/CodeQL e deploy Hetzner. |

## Perimetro funzionale richiesto

1. Full React reale:
   - Route studio/prodotto senza fallback operativo a `?_legacy=1`.
   - Route profonda già segnalata: `/fascicoli/9B9DF2A1/deposito/prepara`.
   - Topbar React con notifiche operative, ultimi elementi aperti, scadenze rapide e classificazione fascicoli/PEC corretta.

2. Deposito telematico:
   - La pagina deposito prepara deve leggere i documenti presenti nell'intero fascicolo.
   - La logica deve rispettare la normativa ministeriale e la distinzione tra atti inviabili direttamente dal software e casi in cui va generata/esportata la busta `.enc` per deposito dal portale ministeriale.
   - Le ricevute di deposito, accettazione, consegna ed esiti non devono creare voci in Agenda o Scadenziario. Devono restare nel fascicolo e nel pannello deposito, dove il software controlla che accettazione e consegna arrivino.
   - Il software propone automaticamente l'atto principale e gli allegati obbligatori solo quando la classificazione è forte. Se il documento è ambiguo, ad esempio `Documento richiesto - prova interesse ad agire Istanza GPS corretta`, resta da scegliere manualmente dall'avvocato.
   - La selezione dei documenti da inviare deve essere visibile nella pagina `Prepara deposito`, non nascosta negli slot laterali: l'avvocato deve vedere una lista `Documenti da inviare` con spunte su atto principale, allegati e prove proposte dal software, poter correggere subito la selezione, e il pulsante finale deve usare esattamente quella selezione per validazione, firma multipla e generazione busta.
   - Se il software non riesce a classificare con certezza un documento, quel documento deve comunque comparire nella lista di scelta come `Da classificare`/`Da verificare`: il blocco deve spiegare cosa manca, non impedire all'avvocato di selezionare il documento.
   - Quando i documenti obbligatori da firmare sono presenti, il software deve proporre firma multipla immediata: un solo comando e un solo PIN per tutti i documenti selezionati, con salvataggio/verifica di ogni file firmato nel fascicolo. Il test reale va eseguito appena il flusso è pronto, con PIN inserito dall'utente.
   - I campioni reali confermano che il deposito via PEC deve produrre una busta `Atto.enc`; la copia non crittografata è utile solo per audit/controllo del contenuto e mostra `DatiAtto.xml.p7m`, atto principale, allegati e indice documenti.
   - Per il procedimento civile PCT la busta è inviata via PEC all'ufficio destinatario. Per i canali che richiedono portale o canale ufficiale non gestito direttamente, il software deve generare la busta pronta e guidare l'avvocato al caricamento manuale, senza fingere un invio eseguito dal software.
   - Finché manca l'adapter ministeriale reale che produce `Atto.enc` da `Atto.msg` cifrato AES256, il software deve preparare controllo, indice, firma e pacchetto possibile, spiegare cosa manca e bloccare solo la registrazione dell'invio come deposito valido.

3. PEC, Agenda e Scadenziario:
   - In Agenda e Scadenziario devono finire solo elementi seri e utili: udienze, adempimenti e notifiche con termine o impegno concreto.
   - Non devono comparire voci generiche come `Notifica · Notifica` senza cliente, senza cosa fare e senza contesto.
   - Non deve comparire testo tecnico in Agenda o Scadenziario: niente `PEC_AUDIT`, `pipeline`, `audit-grade`, codici interni, `source_event`, `profile`, `payload`, `runtime`, `backend`, `frontend`, `legacy`, `json_api`, nomi di job o frasi da log. Il testo visibile deve essere solo giuridico-professionale, chiaro, conciso e utile all'avvocato.
   - Non deve essere inventato sempre l'orario `09:00`.
   - Se la PEC, il PDF o la proposta operativa non contengono un orario certo, la voce non deve comparire in Agenda. Deve restare nello Scadenziario, nel fascicolo o nel presidio PEC come attività da valutare, senza appuntamenti finti.
   - La sincronizzazione Google Calendar o calendario esterno non deve dipendere solo dagli appuntamenti Agenda: le scadenze senza orario certo devono essere pubblicate come eventi a giornata intera dallo Scadenziario, con titolo e descrizione giuridico-professionali, senza slot orari inventati e senza duplicati.
   - Per Google Calendar il percorso preferito è il motore diretto lettura/scrittura collegato da Impostazioni. Dopo la creazione o modifica di una scadenza PEC, il software deve tentare il push selettivo della scadenza verso i calendari collegati; il feed in sola lettura resta un export di emergenza, non il flusso primario.
   - Le PEC duplicate non devono essere riportate due volte.
   - Le comunicazioni o notifiche senza termine certo devono restare da valutare nel presidio PEC/fascicolo, non diventare eventi automatici.
   - Il dettaglio al passaggio del mouse deve essere unico, chiaro e conciso: azione, cliente/parte, fascicolo/RG, quando, luogo se presente.
   - Quando la PEC o il PDF indicano un'udienza audiovisiva, il collegamento deve essere estratto e conservato nella stringa esatta letta dalla fonte quando è già integro. Non va decodificato, riscritto, accorciato o normalizzato, perché il link può smettere di funzionare. Se il testo OCR contiene spazi o rotture e serve ricostruire il link, la voce deve restare da controllare sull'allegato e non va presentata come identica alla fonte.
   - Il presidio non deve dipendere solo dalla PEC: i documenti notificati presenti nel fascicolo, in particolare nella sezione Relata notifica o documenti equivalenti, devono essere letti come fonte processuale autonoma quando contengono decreto di fissazione udienza, data, ora, RG, ufficio, parte/cliente e collegamento audiovisivo.
   - Per il documento `Decreto fissazione udienza (originale notificato).pdf` il sistema deve estrarre `RG 1754/2026`, udienza `20/05/2026 ore 10:00`, `Tribunale di Milano - Sezione Lavoro`, cliente/fascicolo `Vinci Rosa Maria`, e il link Teams esatto `https://teams.microsoft.com/meet/38858779158973?p=Js9ShyCOEg7O19oPeQ`, senza normalizzarlo.
   - Se l'avvocato cancella la PEC per spazio, il fascicolo deve restare presidiato grazie ai documenti già salvati: Agenda, Scadenziario e notifiche push devono poter nascere anche dal documento notificato, con deduplica rispetto a eventuali voci PEC già presenti.

4. Logica notifiche legali da fascicolo, Relata e Comunicazioni:
   - La PEC dell'ufficio o della cancelleria è un presidio operativo: segnala che esiste un provvedimento/documento da notificare e quale documento va recuperato, ma non è di regola l'originale da usare per la notifica.
   - Il documento da notificare deve essere scaricato dal Portale Servizi Telematici o dal portale ufficiale competente tramite acquisizione autenticata, evitando duplicati e collegandolo al fascicolo corretto.
   - Dopo lo scarico dal portale, il documento originale acquisito deve essere visibile nel fascicolo e collegato al presidio Relata notifica. La Relata deve dire all'avvocato cosa deve fare: preparare/revisionare/firmare/inviare la notifica oppure, se già inviata, completare la prova.
   - La notifica si esegue dalla pagina `Notifiche legali` (`/notifiche-legali`) usando il documento originale scaricato dal portale, non l'allegato PEC d'ufficio quando questo non è l'originale processuale.
   - Dopo l'invio della notifica, il software deve presidiare la PEC e cercare automaticamente esito di invio, RAC e RdAC. Le ricevute devono essere importate nel fascicolo nella sezione `Comunicazioni / Cancelleria`, insieme al documento notificato, alla relata firmata e agli eventuali file di attestazione.
   - Se RAC/RdAC o PEC inviata risultano già presenti nella sezione Comunicazioni o nei documenti del fascicolo, il software non deve riproporre un nuovo invio. Deve mostrare stato `Ricevute notifica da completare` oppure `Prova notifica pronta per deposito`, deduplicando per `Notifica_ID`, hash o nome normalizzato.
   - La sezione `Relata notifica` è il cruscotto di presidio e prossima azione; la sezione `Comunicazioni / Cancelleria` è il luogo dove l'avvocato ritrova le prove di invio: PEC inviata, RAC, RdAC, documento originale notificato e relata.
   - Il deposito della prova di notifica deve leggere queste prove dalla sezione Comunicazioni/fascicolo e includerle nella proposta busta; RAC/RdAC sono ricevute originali e non devono essere trattate come nuovi atti da notificare né come appuntamenti Agenda.
   - In Agenda e Scadenziario non devono comparire accettazione/consegna/deposito prova come eventi autonomi; restano nel fascicolo e nel presidio operativo della notifica/deposito.

5. Fonti normative e conformità della logica notifiche/deposito prova:
   - Legge 21 gennaio 1994, n. 53, articolo 3-bis: la notifica telematica dell'avvocato si esegue via PEC verso indirizzi risultanti da pubblici elenchi, usando PEC del notificante risultante da pubblici elenchi; il perfezionamento si collega a ricevuta di accettazione per il notificante e ricevuta di avvenuta consegna per il destinatario. Fonte ufficiale Normattiva: https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1994-01-21;53~art3-bis=
   - D.M. Giustizia 21 febbraio 2011, n. 44, articolo 18, come sostituito dal D.M. 3 aprile 2013, n. 48: l'avvocato allega al messaggio PEC documenti informatici o copie informatiche, anche per immagine, privi di elementi attivi e nei formati consentiti; l'asseverazione di conformità della copia per immagine va inserita nella relazione di notificazione; la RdAC richiesta è quella completa ex DPR 68/2005. Fonte Normattiva D.M. 48/2013: https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=13G00090&atto.dataPubblicazioneGazzetta=2013-05-09
   - Scheda PST Ministero Giustizia "Notificazioni per via telematica eseguite dagli avvocati e dai procuratori legali": conferma oggetto PEC "notificazione ai sensi della legge n. 53 del 1994", allegati necessari (atto PDF da notificare, eventuale procura, relazione di notificazione firmata digitalmente), possibilità che l'atto sia un originale informatico estratto dal fascicolo di cancelleria, necessità di richiedere RdAC completa, e deposito in cancelleria di atto notificato più RAC e RdAC indicizzate in DatiAtto.xml. Fonte PST: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12
   - Specifiche Tecniche ex art. 34 D.M. 44/2011, Provvedimento 7 agosto 2024, efficaci dal 30 settembre 2024: sono il riferimento ministeriale vigente per formati, regole tecniche e flussi telematici. Fonte PST: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429
   - Formato Busta Telematica PST: la busta contiene IndiceBusta.xml, DatiAtto.xml, atto principale PDF firmato digitalmente e allegati; questo giustifica la proposta busta che distingue atto principale, allegati e prove di notifica. Fonte PST: https://pst.giustizia.it/PST/resources/cms/documents/Formato_Busta_Telematica.pdf
   - Formato messaggi PEC e flusso di deposito PST: per il deposito via PEC l'oggetto deve rispettare la sintassi `DEPOSITO ...`, deve essere allegato un unico file `.enc` corrispondente ad `Atto.enc`, il messaggio deve essere solo testo; la RdAC del Ministero segna la ricezione della busta e le ricevute/esiti vengono salvati nel fascicolo informatico. Fonte PST: https://pst.giustizia.it/PST/resources/cms/documents/Formato_messaggi_e_descrizione_flusso_di_deposito_2.pdf
   - Regola applicativa derivata: IUSENTRA deve quindi usare la PEC d'ufficio come segnale di presidio, scaricare/collegare l'originale dal Portale Servizi quando necessario, notificare tramite `/notifiche-legali` con relazione firmata e allegati conformi, presidiare PEC inviata/RAC/RdAC, conservarle in Comunicazioni e usarle per il deposito prova/busta, senza riproporre notifiche già inviate.

6. Presidio PEC massivo:
   - Se lo studio ha già presidiato, ad esempio, 500 email, un nuovo presidio su 3 PEC nuove deve lavorare solo le 3 non ancora presidiate.
   - Il pulsante non deve ripartire dall'intero archivio storico.
   - Il risultato deve dire quante PEC nuove sono state lavorate e quante erano già presidiate e quindi saltate.

## Modifiche già avviate in questa tranche

### Deposito full React

- `frontend/src/components/FascicoliPage.tsx`: introdotta la pagina React `DepositPreparePage` per `/fascicoli/:id/deposito/prepara`.
- `web/bootstrap/deposito_routes.py`: la GET deposito prepara serve la shell React salvo richiesta esplicita `?_legacy=1`.
- `web/bootstrap/react_route_gate.py` e `web/blueprints/react_shell.py`: route profonda deposito esclusa dal blocco legacy.
- `pct/practice_engine/evaluator.py`: aggiunta una prima `deliveryPolicy` per il deposito.
- `tools/react-migration/route-manifest.json`: aggiunta route `/fascicoli/:id/deposito/prepara` come React governata.
- `pct/practice_engine/deposit_readiness.py`: proposta automatica degli slot documentali solo con confidenza sufficiente; se il documento è ambiguo resta scelta manuale dell'avvocato.
- `frontend/src/components/FascicoliPage.tsx`: aggiunta la sezione `Proposta busta`, il riepilogo documenti inclusi, l'elenco dei documenti da firmare, il pulsante finale coerente col canale e i selettori manuali `Scegli documento`/`Collega`.
- `web/bootstrap/deposito_routes.py`: la generazione della busta usa `codice_oggetto_pst` validato quando presente, invece del solo titolo libero del fascicolo.
- Test già passati prima della presente nota: pytest mirato deposito/shell, `pnpm --filter @iusentra/studio typecheck`, `node frontend/scripts/check-react-contracts.mjs`, `node scripts/react-migration/check-route-gate.mjs`, `pnpm --filter @iusentra/studio build`.

### Campioni reali deposito RG 1754/2026 analizzati

- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso [JQ280-L01] [RefID_001_c3pnY4kBVA].EML`: copia non crittografata con `DatiAtto.xml.p7m`, `Ricorso.PDF`, `Nota d'iscrizione a ruolo.PDF`, `Procura.PDF`, allegati probatori, RAC/RdAC della diffida e `IndiceDocumentiDepositati.PDF`.
- `DEPOSITO TELEMATICO_ Ricorso (originale notificato).pdf RG_ 1754 - 2026 [JQ280-L01] [RefID_001_zVNsJkqBF9]`: file con nome ingannevole ma contenuto MIME; PEC reale del 25/02/2026 con un solo allegato `Atto.enc` e corpo che elenca ricorso notificato, relata, RAC/RdAC, attestazione, decreto fissazione udienza e procura.
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Ricorso (originale notificato).pdf RG_ 1754 - 2026 [JQ280-L01] [RefID_001_zVNsJkqBF9]`: copia non crittografata del precedente, con `DatiAtto.xml.p7m`, ricorso notificato, relata, ricevute, attestazione, decreto, procura e indice.
- `DEPOSITO TELEMATICO_ Documento richiesto - prova interesse ad agire Istanza GPS corretta RG_ 1754 - 2026 [JQ280-L01] [RefID_001_YiumPOKKPX].eml`: deposito successivo del 20/05/2026 con un solo `Atto.enc` e riferimento RG 1754/2026.
- `COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO_ Documento richiesto - prova interesse ad agire Istanza GPS corretta RG_ 1754 - 2026 [JQ280-L01] [RefID_001_YiumPOKKPX].EML`: copia non crittografata con `DatiAtto.xml.p7m`, il documento richiesto e indice documenti depositati.

### Fonti ministeriali consultate

- PST, `Deposito generico di un atto`: conferma busta telematica inviata come allegato PEC, atto PDF firmato, `DatiAtto.xml` firmato, mittente registrato ReGIndE e ricevute/esiti del flusso.
- PST, `Formato messaggi e descrizione flusso di deposito`: oggetto PEC con sintassi `DEPOSITO ...`, un solo allegato `.enc`, PEC in solo testo, ricevuta di accettazione, RdAC, esito controlli automatici ed esito intervento ufficio.
- PST, `Formato Busta Telematica`: busta cifrata con chiave pubblica dell'ufficio, contenente `IndiceBusta.xml`, `DatiAtto.xml`, atto PDF firmato e allegati; dimensione massima indicata nella scheda.
- Specifiche tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024: articolo 15 su formato atto e `DatiAtto.xml`, articolo 16 su formati allegati e procura firmata, articolo 17 su trasmissione civile via PEC/busta, controlli e anomalie, articolo 26 su notifica e deposito di ricevute RAC/RdAC in busta.

### Topbar operativa

- `frontend/src/components/layout/TopBar.tsx`: tracciamento recenti anche su route profonde.
- `frontend/src/hooks/useRecentItems.ts`: ascolto evento per refresh ultimi elementi.
- `web/services/topbar_operational.py`: notifiche deposito puntano alla preparazione deposito/fascicolo.

### PEC e deposito

- `pct/pec_pipeline.py`: `build_deadline_proposal` ora tratta `pct_deposito` come `not_needed`, `auto_create=False`, `calendar_scope="fascicolo_deposito"`.
- Le comunicazioni di cancelleria senza udienza o termine certo non creano più scadenze automatiche.
- Le notifiche giudiziarie senza termine certo restano in revisione professionale.
- Le scadenze critiche restano nello Scadenziario, ma non devono generare appuntamenti finti in Agenda.

### Agenda da PEC

- `pct/pec_pipeline.py`: aggiunti helper per estrarre data/ora certa da PEC e proposta (`_agenda_datetime_for_pec_proposal`, `_agenda_datetime_from_text`, `_agenda_title_for_pec_deadline`).
- `_sync_pec_deadline_to_agenda` è stato avviato verso questa logica: Agenda solo con udienza/impegno con orario certo; se manca l'orario certo non si crea alcun evento Agenda. Titolo senza prefisso `Presidio PEC`, luogo vuoto o `Udienza da remoto`, durata coerente.
- `_sync_related_pec_agenda_entries` è stato modificato per eliminare duplicati dello stesso audit PEC quando esiste una voce primaria.

### Presidio massivo incrementale

- `web/blueprints/pec_pipeline_api.py`: avviato filtro dei candidati in `_pec_acquire_local_emails_chunked`.
- Nuovi avvii senza `run_id` filtrano le PEC già acquisite o già presidiate.
- Run esistenti con `run_id` continuano a rispettare il cursore già avviato.
- Aggiunto contatore `skipped_already_presided` nella risposta e nel payload del run.

### UI Agenda

- `frontend/src/components/AgendaPage.tsx`: rimosso il tooltip nativo `title` dalla card evento, che causava doppia finestra sovrapposta al passaggio del mouse.
- Il tooltip React ora mostra righe operative: cliente/parte, fascicolo/RG, quando, luogo e dettagli essenziali.
- `AgendaFocus` usa `Dettaglio operativo`, `Cliente/parte`, `Fascicolo/RG`, `Origine` leggibile, non la fonte tecnica grezza.
- `frontend/src/index.css`: tooltip agenda più leggibile, più largo, con righe distinte e z-index alto.
- `frontend/src/agendaData.ts`: React rispetta `timeLabel` e `durationLabel` inviati dal backend.
- `web/services/react_agenda_bridge.py`: le scadenze senza orario esplicito vengono etichettate come `Entro giornata` e `Scadenza`, invece di apparire come `09:00 · 45 min`.

## Stato credenziali runtime locale

Su richiesta dell'utente sono state aggiornate localmente le password degli utenti di test tramite `GestioneUtenti.cambia_password`, senza salvare password in chiaro:

- utente studio `antmm26051975` nel tenant `tenant-8bf98719c459`;
- utente piattaforma `admin` nell'archivio globale.

Non riportare le password in file di progetto o report pubblici. Le modifiche a `data/auth/utenti.json` e `data/tenants/tenant-8bf98719c459/auth/utenti.json` sono runtime locale e vanno trattate con cautela prima del commit.

## Cose ancora da fare

1. Completare e verificare il codice PEC:
   - controllare `_sync_pec_deadline_to_agenda` dopo le patch;
   - assicurare che non usi più `_agenda_datetime_candidates` per creare slot inventati;
   - confermare che il titolo Agenda non contenga `Presidio PEC`;
   - confermare che `Agenda studio` non sia più usato come luogo fittizio per PEC;
   - verificare che i duplicati dello stesso audit PEC vengano rimossi.

2. Completare e verificare il presidio incrementale:
   - compilazione Python già da ripetere dopo ogni patch;
   - testare primo run, run con `run_id`, secondo nuovo run senza PEC nuove, run con una PEC nuova;
   - verificare che `skipped_already_presided` sia coerente e che il messaggio utente sia chiaro.

3. Aggiornare test:
   - `tests/test_pec_audit_pipeline.py` per deposito `pct_deposito` senza agenda/scadenziario;
   - test udienza remota con orario reale e tipo `UDIENZA`;
   - test duplicati agenda dello stesso audit PEC;
   - test presidio massivo incrementale;
   - test statico React per assenza di `title={tooltipText}` in Agenda;
   - test bridge agenda per `Entro giornata`.

4. Eseguire gate tecnici mirati:
   - `python -m py_compile pct\pec_pipeline.py web\blueprints\pec_pipeline_api.py web\services\react_agenda_bridge.py`;
   - pytest mirati su PEC, Agenda bridge, React shell interessato;
   - `pnpm --filter @iusentra/studio typecheck`;
   - `pnpm --filter @iusentra/studio build`;
   - `node frontend/scripts/check-react-contracts.mjs`;
   - `node scripts/react-migration/check-route-gate.mjs`.

   Gate eseguiti il 14/06/2026 dopo le patch deposito/agenda/scadenziario:
   - `python -m py_compile pct\practice_engine\deposit_readiness.py web\services\pdf_deadline_import.py web\services\react_agenda_bridge.py web\services\react_scadenziario_bridge.py pct\scadenziario.py web\bootstrap\deposito_routes.py`;
   - `node --check scripts\react-migration\pec_agenda_scadenziario_visual_audit.mjs`;
   - `python -m pytest tests\test_practice_engine_validators.py tests\test_regia_api_payloads.py tests\test_regia_ui_react.py -q --tb=short`;
   - `python -m pytest tests\test_react_scadenziario_additions.py tests\test_react_shell.py::test_react_agenda_bridge_traduce_pec_udienza_in_linguaggio_professionale -q --tb=short`;
   - `python -m pytest tests\test_deposito_guidato.py::test_api_validazione_deposito_restituisce_semaforo_e_consente_con_warning tests\test_deposito_guidato.py::test_generazione_busta_usa_codice_oggetto_pst_validato tests\test_deposito_guidato.py::test_orchestratore_blocca_deposito_pct_senza_codice_oggetto_pst -q --tb=short`;
   - `pnpm --filter @iusentra/studio typecheck`;
   - `pnpm --filter @iusentra/studio build`;
   - `node frontend\scripts\check-react-contracts.mjs`;
   - `node scripts\react-migration\check-route-gate.mjs`.

5. Verifica reale obbligatoria:
   - ricostruire/aggiornare Docker locale reale su `127.0.0.1:8080`;
   - verificare `/api/pronto`;
   - login con utenti runtime configurati;
   - aprire PEC reali;
   - lanciare presidio PEC;
   - controllare Agenda e Scadenziario su dati reali;
   - aprire la pagina React dello Scadenziario sulla macchina remota/locale reale, scorrere tutta la pagina dall'alto al fondo e controllare specificamente che le card non siano ripetute inutilmente, non abbiano dimensioni diverse senza motivo, non creino spazi vuoti o disallineamenti e mantengano testi leggibili;
   - hover sugli eventi Agenda per verificare che appaia un solo dettaglio leggibile;
   - verificare desktop, tablet e mobile;
   - scorrere tutta la pagina o pannello, non solo la prima schermata.

6. Report e release:
   - aggiornare `artifacts/react-migration/pytest-confirmed-ok.md`;
   - aggiornare `artifacts/react-migration/pytest-open-issues.md`;
   - aggiornare report React/audit pertinenti;
   - aggiornare `CHANGELOG.md`;
   - bump versione;
   - pulire artefatti runtime non committabili;
   - commit e push branch gemelli;
   - attendere GitHub checks e CodeQL;
   - deploy Hetzner e verifica `https://app.iusentra.it/api/pronto`;
   - prune Docker su Hetzner.

## Criterio di chiusura

Il lavoro non può essere dichiarato chiuso finché non risultano veri tutti questi punti:

- route deposito profonda full React su copia reale;
- PEC deposito non genera più agenda/scadenziario;
- udienze PEC con orario certo arrivano in Agenda una sola volta, con cliente/fascicolo/cosa fare comprensibili;
- scadenze senza orario non appaiono più come appuntamenti finti alle 09:00;
- presidio massivo lavora solo PEC non ancora presidiate;
- hover Agenda mostra una sola finestra chiara, senza sovrapposizioni;
- test mirati, build e gate React passano;
- verifica visiva reale su `127.0.0.1:8080` eseguita e documentata;
- repo pulito o con sole modifiche intenzionali committate;
- branch gemelli, GitHub checks, Hetzner e `/api/pronto` allineati.
