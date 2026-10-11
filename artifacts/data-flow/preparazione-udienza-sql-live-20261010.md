# Preparazione udienza SQL/live — incarico aperto

## Risultato richiesto

Avvio senza sessioni doppie, salvataggi concorrenti con bozza preservata,
esito e consegne in Agenda/Scadenziario/Fascicolo nella stessa transazione.
Una risposta persa va riscontrata dalla ricevuta SQL dello stesso comando,
senza ripetere effetti o inventare conferme. Le viste autorizzate aperte
ricevono il segnale solo dopo il commit. Nessuna modifica a firma, deposito
o invio PEC; nessuna lettura documentale massiva nelle richieste.

## Procedura esistente riscontrata

`get_wizard_pro` apre ancora il gestore JSON. Le rotte React chiamano il
runtime nativo e poi salvano la sessione nel file; l'esito scrive prima
rinvio, termini e attività. Il blocco di scritture non è atomico: un errore
successivo può lasciare effetti senza il relativo riferimento nella sessione.
La UI fa aggiornamenti ottimistici e ricarica dopo l'errore, senza protezione
completa della bozza. Esistono anche scrittori nel blueprint classico:
devono confluire nello stesso protocollo, senza duplicare le procedure.

## Preparazione del codice, non installazione

Nuovo repository `pct/udienze/repository.py`: schema esplicito con adozione,
sessioni per studio, indice univoco dell'udienza, revisioni per sessione,
intenti immutabili, ricevute e audit generale nella transazione nativa.
Costruttori e letture non fanno DDL/import. Fonti invalide o con campi
sconosciuti restano errori espliciti; non diventano archivi vuoti.
Il callback degli effetti riceve la connessione della transazione e non
può fare commit o scrivere mirror. Revisioni superate impediscono di
eseguirlo. Un secondo avvio restituisce la sessione corrente senza
azzerare il lavoro; un errore nell'avvio non lascia una sessione parziale.

La ricevuta lega operatore, studio, sessione, azione, versione e intento.
Checklist e date derivate non diventano un nuovo intento quando si ripete
una risposta persa: il replay restituisce il primo risultato confermato.
Audit mancante o riferito a un altro operatore impedisce la conferma.
Il segnale predisposto usa il dominio Agenda della regia condivisa e i
suoi permessi, senza un secondo canale live.

## Riscontri tecnici del 10/10/2026

Guardrail repository: prima 11, poi 13 e 15 casi passati; dopo l'adeguamento
dell'intento di avvio, quattro casi pertinenti ripetuti positivamente
(inclusi due nuovi casi). Ruff positivo. Le verifiche sono tecniche e non
sostituiscono l'accettazione UI. Primo comando nella venv non eseguibile:
pytest non presente correttamente; usato Python di sistema con pytest.
Due difetti dei fixture corretti: database vuoto non creato prima dell'apertura
existing-only e tabella impostazioni inesistente nel test di rollback;
il test usa ora una riga nella tabella Agenda nativa e ne prova l'annullamento.

PostgreSQL reale tramite PostgresStudioDB: adozione, mapping delle righe,
commit, replay senza nuovi effetti, conflitto e rollback riscontrati in
sole tabelle TEMP, senza scritture nei dati dello studio. Ripetizione dopo
l'ultima modifica del repository positiva. Script privato e prova in
`D:/legale/backups/IUSENTRA/agenda-sql-live-20261010/`.

## Passaggi ancora obbligatori

Procedura esplicita di adozione con backup coerente e produttori drenati;
consegne native atomiche con provenienza e preservazione delle decisioni
manuali; factory tenant-aware, API/versioni/RBAC, scrittori classici,
ricevute di rifiuto, bozze e live React; prova del comando normale nel
browser reale su 8080 con salvataggio/riapertura, retry e concorrenza;
commit/push dei due branch, copia locale esatta e deploy Hetzner verificato.

Questa preparazione non è installata né verificata nell'interfaccia.
L'incarico resta aperto; Agenda 2.437.2 è un rilascio separato.

10/10/2026 — Preparazione udienza, consegna SQL WIP: aggiunti snapshot dei gestori nativi e callback per esito/Agenda/Scadenziario/Fascicolo nella transazione del comando; nessun commit interno, JSON operativo o rilettura documentale. Rifiuti persistenti con esito audit RIFIUTATO; eliminazione della sola preparazione conserva fatti già consegnati e ricevuta ripetibile. Nuovo dispatcher unico per passi/documenti/verifiche/esito/archiviazione/eliminazione, ancora NON collegato alle route.
Guardrail: repository 20 e consegna esito 10 passati insieme; tre nuovi casi (discordanza colonne SQL, rinvio annullato, rettifica termine) eseguiti: i primi due positivi, il terzo ha mostrato l'errata supposizione che il termine nativo fosse BOZZA. Il motore crea APERTO: corretto il controllo, rettifica esplicita della stessa voce aperta tramite aggiorna nativo, preservando COMPLETATO/ANNULLATO/SCADUTO e riscontri precedenti. Caso rettifica ripetuto positivo; protezione termine completato positiva. Dispatcher sette test positivi, ulteriore concorrenza reale tra due connessioni/operatori positiva: una consegna, un conflitto persistente, nessun doppione. PostgreSQL reale PostgresStudioDB su sole tabelle TEMP: effetti atomici, metadati preservati, replay, ripetizione dello stesso fatto, rollback e rifiuto persistente positivi. Ruff positivo.
Primo fixture esito ometteva durata_minuti e luogo obbligatori del modello Appuntamento; corretto prima delle prove. Prime ricerche con percorsi presunti inesistenti corrette tramite inventario rg: non costituiscono analisi di quei file. Nessuna installazione/accettazione UI del candidato, nuovo commit/push o nuovo deploy del Wizard. Restano adozione con backup/drain, factory tenant-aware, tutti gli scrittori/API/RBAC e protezione bozze/live nell'interfaccia, prova reale e rilascio.
Browser Chrome precedentemente selezionato non disponibile: consultata diagnosi ufficiale, inventario conferma assenza di Chrome, apertura Chrome tramite API documentata non disponibile. Aperto browser reale in-app visibile sulla copia 8080: osservato il cruscotto della versione pubblicata con quattro udienze da preparare e ricerca per cliente/R.G.; nessuna scrittura su procedimenti reali. Questa osservazione NON prova il codice WIP.

## 11/10/2026 — Installazione locale e accettazione in corso

Factory tenant-aware, API React, scrittori classici, dispatcher unico, ricevute persistenti, RBAC e bozze/live sono ora collegati nel candidato locale. Le letture non eseguono DDL né importazioni; dopo l'adozione il vecchio gestore JSON rifiuta anche le scritture da istanze già aperte. L'esito richiede insieme agenda.scrivi, scadenziario.scrivi e fascicoli.scrivi. Il replay conserva l'intento originario e non ricostruisce il comando dalla bozza successiva.

Sul solo tenant tecnico accettazione-prima-nota è stata applicata l'adozione con app drenata, backup coerente e sorgente vuota verificata. Nessuna riconvalida documentale o scansione dei fascicoli. Un primo backup ha rilevato corruzione fisica nella tabella mirror moduli_json_records: recupero SQLite ufficiale conservato separatamente, confronto di tutte le 128 tabelle canoniche leggibili senza differenze, ricostruzione dei soli mirror dalle 69 fonti attuali verificate, quick_check positivo e audit della riparazione. Originale danneggiato, dump, manifesti e quarantena sono preservati. La causa iniziale della corruzione NON è stata dimostrata; non dichiarata risolta globalmente. Due indici SQLite censiti come JSON rimangono un rilievo separato del catalogo.

Prova materiale nel browser in-app visibile, copia reale 127.0.0.1:8080: sessione controllata 323a3f26-eb41-5356-a3ac-9f27216b3b23, fascicolo tecnico 7FFD0C5D. Avvio normale da Agenda; salvataggi automatici di note e tipo; seconda vista aggiornata senza ricaricamento; conflitto fra due note conservato con scelta esplicita della versione. Provati Mantieni la mia bozza e Salva bozza, poi riapertura con testo conservato. Checklist documento pronto e due documenti extra salvati dal comando normale. Due campi della strategia digitati durante il primo invio conservati e riaperti. Verifica trasferta e promemoria salvati insieme.

Guasto reale di audit simulato soltanto sul tenant tecnico con trigger temporaneo SQLite: risposta non confermata, bozza e intento conservati, Recupera salvataggio ripete lo stesso comando dopo rimozione del trigger; Salvato osservato. Il trigger è stato rimosso e la sua assenza verificata. Non è una simulazione HTTP né sostituisce la prova reale.

Esito normale Rinvio al 16/12/2026 09:00 e termine 10/12/2026: rinvio E2F76C56, termine e6db1a22-f171-45b5-966e-14f45e5e9d9e e nota 828B623E confermati atomicamente. Agenda e Scadenziario già aperti aggiornati live; cronologia del fascicolo mostra una sola nota Rinviato. Riapertura dell'esito conserva gli stessi riferimenti. Nessuna comunicazione, firma o deposito attivato.

Difetti emersi e corretti: Agenda scambiava la parte mese/anno di 11/10/2026 per RG10/2026; esclusione delle date dall'inferenza e collegamento esplicito alla preparazione. Il rinvio conserva anche id_fascicolo nel payload SQL nativo per mantenere il collegamento dopo eliminazione della sola preparazione. Il ruolo usa rg_completo, incluso l'anno. Nome del professionista separato dall'identità macchina dell'audit: riconferma governata del solo esito tecnico, con fonte corrente e comando persistente, non crea nuovi seguiti. Cronologia già aperta mostra Accettazione tecnica al posto dell'UUID.

Riscontri tecnici: 74 guardrail della prima integrazione, 8 RBAC/HTTP/classici aggiuntivi, 11 JavaScript delle bozze/comandi; 28 Agenda e 50 Agenda/consegna/collegamenti nella ripetizione pertinente. Nuovi test professionista e collegamento conservato dopo eliminazione. PostgreSQL reale su sole tabelle TEMP: avvio, modulo classico, revisione, replay, effetti atomici, metadati, rollback e rifiuto persistente positivi. Build con typecheck positiva. Questi riscontri non sostituiscono la prova materiale descritta.

Preflight server: trovati sorgenti non consolidati Codici e leggi, salvati nel backup /opt/iusentra/backups/preparazioni-server-source-20261011 con bundle Git, patch, sorgenti e asset; seconda copia privata locale verificata SHA256. Recuperati senza copiare database o corpus normativi. Guardrail di questo codice recuperato hanno rilevato selezione delle preleggi al posto del codice civile: mantenuta la raccolta richiesta, 13 test normativi/Lex e 19 JavaScript pertinenti positivi. Fixture Windows reso esplicitamente UTF-8. Un comando di copia usava erroneamente la directory di destinazione come sorgente: nessun file modificato da quell'errore, ripetuto con percorso assoluto; primo Ruff da directory frontend non ha verificato i Python, ripetuto dalla radice con esito positivo.

Prove private: hearing-command-pending.png, hearing-conflict-choices.png, hearing-agenda-linked.png, hearing-case-confirmed.png e manifesti sotto D:/legale/backups/IUSENTRA/agenda-sql-live-20261010. Il candidato è installato localmente; non è ancora un rilascio confermato. Restano consolidamento, ultime prove pertinenti, commit/push dei due branch, copia locale sul commit esatto, adozione SQL sul server con backup/drain, deploy unico healthy e controllo server. L'incarico generale rimane aperto, fonti normative locali e EmbeddingGemma300M invariati, PC acceso.

11/10/2026 — Accettazione aggiuntiva sulla copia reale 8080.
Salvato il briefing dal pulsante classico Salva e continua: redirect al passo Documenti, seconda finestra React già aperta aggiornata automaticamente con la stessa nota. Riapertura classica conferma la persistenza. Trovate date ISO nei due riquadri Udienza e nel riepilogo finale: sostituite con filtri condivisi fmt_data/fmt_ora; riapertura materiale osserva 11/11/2026 alle 09:00. Screenshot privato hearing-classic-confirmed.png. Scheda React scorsa fino al comando Avanti, campi e termini visibili.
82 guardrail mirati della catena completa Preparazione udienza conclusi con exit 0 (preparazioni-release-final-pytest.log), oltre ai controlli Agenda, PostgreSQL TEMP e JavaScript già registrati. Biblioteca normativa recuperata dal server: aperto Codice civile, articolo 1 Capacità giuridica, testo integrale e collegamento Normattiva osservati nel browser reale; nessun dato dello studio trasmesso. Screenshot codici-articolo-recovered.png.
Allineamento dei processi ancora aperto: scheduler locale usa la precedente immagine, rifiuta il nuovo campo Appuntamento.id_fascicolo e il presidio notifiche risulta unhealthy. Non nascosto né resettato. Prima del riavvio controllata la lavorazione normativa locale attiva: riallineamento articoli ha raggiunto il timeout nativo di 7200 secondi, poi la pipeline ha avviato integrazione leggi essenziali. Originali/checkpoint preservati; questa lavorazione locale non viene trasferita in produzione. Aspettare drain verificato o procedura di ripresa sicura prima di ricreare scheduler; tutti i lettori devono infine usare la stessa immagine candidata. Nessuna conferma di rilascio finché questo problema resta.


## 11/10/2026 — Conservazione dei collegamenti storici non riscontrati

Preflight nativo sul server, prima di qualsiasi adozione: 15 preparazioni in due studi. Otto richiamano quattro fascicoli storici assenti; una ulteriore preparazione richiama quattro documenti assenti. Per quest'ultima la colonna documenti SQL, il payload e il mirror corrente del medesimo fascicolo non contengono i documenti richiesti. Nessun riferimento ricostruito per somiglianza e nessun fascicolo inventato o trasferito fra studi.

L'adozione ordinaria continua a rifiutare i collegamenti mancanti. Opzioni amministrative esplicite conservano tutte le righe, le note, gli identificatori originali e il backup coerente, registrando nell'audit i collegamenti non dimostrati. Le preparazioni interessate diventano consultabili in sola lettura, escluse dagli esiti verificati e dagli effetti automatici. Discordanza d'identità SQL, udienze discordanti e termini senza consegna dimostrata continuano a interrompere l'adozione. Sul server il nuovo preflight è positivo per entrambi gli studi: 9 righe (4 da verificare), 6 righe (5 da verificare). È solo un piano: nessuna adozione produttiva o deploy effettuati in questa fase.

Guardrail SQLite: 12 casi di adozione positivi, inclusi originali intatti, divieto di modifica/esito/archiviazione/eliminazione, replay del rifiuto, isolamento studio, conservazione della checklist con fonte mancante e rifiuto di termini discordanti. Il nuovo fixture inizialmente lasciava un'udienza obbligatoria inesistente; corretto eliminando il riferimento dal solo caso controllato. PostgreSQL reale con PostgresStudioDB e sole tabelle TEMP: ripetuti effetti atomici, avvio/modulo classico, rollback e replay; aggiunta conservazione storica con audit/rifiuto persistente senza scritture nei dati degli studi.

Accettazione materiale sulla copia reale 127.0.0.1:8080: studio tecnico separato creato con repository nativi, fonte controllata senza fascicolo, adozione con backup. Browser visibile: elenco separato, apertura del pannello, entrambe le note originali leggibili, data italiana, ricaricamento e riapertura. Chrome reale a 390×844: titolo, avviso e tutte le note scorse fino al fondo, nessun comando mutativo; screenshot privati historical-readonly-notes.png e historical-readonly-mobile-notes.png. Questa prova non sostituisce il successivo rilascio esatto né prova i dati della produzione.

GitHub sul commit 816cd688: errore della matrice Storybook dovuto alla pagina CodiciLeggiPage recuperata dal server senza story. Aggiunta la pagina reale alla matrice e fixture di sole fonti normative pubbliche con i contratti atti/articoli/testo. Typecheck, 301 guardrail JavaScript e tutti i controlli frontend, inclusa matrice 84/84, positivi. Nessun criterio attenuato né modifica al flusso firma/PEC congelato. Primo helper PostgreSQL fallito per quoting della shell: riscritto come file e prova ripetuta con esito positivo.

Il candidato resta aperto: allineamento scheduler locale (vecchia immagine, presidio notifiche unhealthy), lavorazione normativa locale da preservare, commit/push/gate, adozione produttiva con drain, installazione esatta e deploy verificato. Le fonti normative e i loro checkpoint non vengono portati sul server.


11/10/2026 — Riscontro materiale aggiuntivo e correzione del percorso primario. Dopo installazione esatta 485bcd53, dashboard e note storiche confermate nel Chrome reale 8080; accesso diretto al passo mostrava però ancora il modulo modificabile. Causa: presidio presente nell’API wizard-pro storica, mentre React usa /api/v1/ui/preparazione-udienza/<id>. Aggiunto il rifiuto 409 al GET realmente consumato, senza mostrare un modulo scrivibile; esteso il controllo anche al riepilogo API storico. Riavvio della sola app locale per prova correttiva, scheduler e lavorazione normativa preservati. Riapertura nel browser osserva motivo e comando Riprova, nessun campo modificabile. Foto privata historical-primary-route-refused.png. Cinque guardrail HTTP positivi, inclusi dettaglio 409, rifiuto persistente/replay del salvataggio e note/revisione immutate; primo fixture duplicava ID audit, corretto con command_key distinto e prova ripetuta. Questa installazione contiene la correzione successiva a 485bcd53: non viene chiamata copia esatta finale.
Consolidamento server: preservati 160 percorsi hot in backup recuperabile, 13 sorgenti confrontate con la release. Dodici identiche; il test restante differisce solo per encoding UTF-8 esplicito già incorporato. Override hot e asset non tracciati spostati in backup; sorgenti runtime e dati non rimossi. Presidio deploy --check-only riscontra sorgenti/asset runtime nella release candidata. CI frontend e quality overlay positivi; gate integrali ancora in corso. Deploy 485bcd53 annullato prima del riavvio per includere il difetto scoperto nel browser. Nessuna adozione produttiva o nuova conferma di rilascio.
