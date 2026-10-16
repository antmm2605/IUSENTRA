# Lex: interrogazioni operative dello studio

Richiesta del 16 ottobre 2026. Lavoro aperto: questa matrice definisce gli esiti
da dimostrare; non attesta che siano già disponibili o rilasciati.

Ulteriore prova materiale del 16/10 sulla copia reale8080 ancora2.437.49:
alla domanda «PEC ricevute il14/10/2026» la risposta mostra anche cartelle
INVIATI e CESTINO e una timeline con messaggi del giorno precedente; il widget
riporta11secondi di elaborazione. Questa è una prova del difetto precedente,
non un'accettazione della candidata50. Nessun dato dello studio è stato modificato.

Ricevute presenti nei fascicoli incluse nell'analisi: consultazione del registro
nativo con impronta corrente, stato della prova e fonti documento/PEC mantenute.
Le copie byte-per-byte vengono raggruppate soltanto nello stesso fascicolo e
per la stessa natura della prova, conservando tutti i riferimenti. Le date
provengono dai fatti già collaudati della stessa fonte e impronta; assenza,
discordanza e budget superato restano espliciti. Una classificazione RAC non
diventa accettazione della cancelleria e una data di importazione non sostituisce
la data della ricevuta. Ventidue guardie native SQLite/PostgreSQL positive sul
registro ricevute, sul catalogo PEC e sulla migrazione riprendibile. Prima
ripetizione PostgreSQL aveva rilevato JSONB già decodificato e un campo di
invalidazione mancante(event_type): corretti entrambi. Estesa l'invalidazione
anche ai metadati che determinano l'ultima analisi e serializzata la proiezione
per messaggio. Ulteriore prova del worker con snapshot SQLite reale positiva:
backup verificato, recupero del solo evento pendente, corpo MIME immutato,
nessuna costruzione della pipeline PEC e nessun archivio creato per altri studi.
Script esplicito con budget finito e migrazione consultiva aggiunti alla candidata;
nessuna migrazione sui dati reali ancora eseguita. Collegamento completo dei
depositi e ricevute documentali alla risposta Lex ancora aperto; nessun rilascio50.

Aggiornamento del collaudo consultivo notificazioni: undici guardie native sui
database SQLite e PostgreSQL positive, includendo data RAC mancante, cambio
giorno italiano, microsecondi, stato successivo alla consegna, isolamento e
assenza di scritture nel lettore. Prima ripetizione PostgreSQL fallita perché
i timestamp nativi sono TIMESTAMPTZ, non TEXT: conversione UTC esplicita nella
sola query; nessun dato o stato modificato. La costruzione sintetica della
catena è stata corretta per rispettare il precedente stato realmente registrato,
senza disattivare i trigger di integrità. Sei guardie aggiuntive positive per
RBAC, tenant discordante e cursori firmati con evento/stato. Gruppo condiviso
di 79 guardie positivo; due aspettative HTTP inizialmente fallivano perché la
fonte sintetica non dimostrava la direzione ricevuta: assegnata INBOX nella
preparazione controllata, mantenendo la data assente. Successiva ripetizione
dei 19 casi del modulo HTTP positiva, compresa consultazione notificazioni
sincrona e streaming con dipendenze AI vietate e byte del database immutati.
Il collegamento di notificazioni alla risposta e alla continuazione del widget
è presente nella candidata; nessuna accettazione visiva o attivazione su dati reali ancora
eseguita. Restano aperti Agenda, Scadenziario, depositi, prestazioni e rilascio.

Preparazione del calendario: metadati ricavati dai modelli nativi, separando
giorno italiano dell'appuntamento e giorno legale del termine. Nessun gestore
JSON viene aperto durante la consultazione. Ventisette guardie SQLite positive
per ricostruzione, proiezione e concorrenza; ripetizione PostgreSQL esplicita con
CTU_TEST_POSTGRES=1 positiva sui 19 casi di concorrenza Agenda/Scadenziario.
Cinque guardie di metadati e invalidazione outbox positive sui backend controllati;
quattro guardie ulteriori positive per pagina SQL, filtri, studio discordante e
mutazione pendente. A seguire, collegati nella candidata la migrazione con backup
condiviso, il worker finito nella regia esistente e la superficie Lex. Le udienze
richiedono il tipo UDIENZA, senza mescolare consulenze. Salvatori nativi aggiornano
la proiezione nella stessa transazione; il savepoint protegge il dato richiesto
se l'indice fallisce e conserva l'evento pendente. Dodici guardie repository
SQLite/PostgreSQL positive, compreso guasto controllato e successivo recupero;
42 guardie posta/HTTP positive dopo l'estrazione del worker condiviso. Ulteriori
32 guardie SQL/HTTP positive dopo l'eliminazione delle letture per singola riga:
le fonti della pagina sono recuperate in un'unica selezione per chiavi. Ottanta
guardie selector/cursor/HTTP positive, inclusi contesto fascicolo preservato,
continuazione firmata e backup SQLite reale con quick_check e ripresa. Il primo
test del worker calendario aveva una riga di asserzione del test precedente
spostata nel punto errato: corretta e ripetuti positivamente i tre casi di
migrazione/worker. Due test di gestori iniettati ora provano esplicitamente il
ramo storico; il nuovo percorso semplice è verificato sul SQL controllato e
non usa quei gestori. Nessuna condizione produttiva allentata per i test.
Queste componenti non sono installate sul runtime reale. Il Browser ora
restituisce visibilità true; le schede
di collaudo sono conservate, senza accettare come prova UI i soli test tecnici.

Diagnosi depositi sul dato locale, sola lettura SQLite query_only: il registro
risolve una storage_key distinta dallo slug; la cartella con il solo slug è
storica e i suoi conteggi non rappresentano lo studio corrente. Osservati
esiti nativi consegnati, importati e prove senza invio; le sessioni procedurali
non coprono invece le ricevute effettivamente presenti nell'archivio PEC.
I report di deposito consultati mostrano fase, correlazione e data evento
presenti, distinguendo accettazione PEC e cancelleria. Nessun evento audit
pec.deposit.upserted presente: non basta quindi interrogare quel solo registro
per concludere che non esistano ricevute. I depositi importati non diventano
depositi dello studio accettati per somiglianza. Nessun documento, messaggio,
stato o collegamento modificato durante la diagnosi; integrazione depositi aperta.

## Risultato richiesto

Una domanda consultiva seleziona il dominio, il periodo e lo stato richiesti nei
repository SQL autorizzati dello studio corrente. Non avvia acquisizioni, OCR,
invii, firme, depositi, riconvalide o caricamenti di altri domini. Restituisce
risultati collegati alle fonti, distinguendo assenza di risultati, errore di
lettura, selezione ambigua e pagina successiva. Un limite di risultati non può
essere presentato come conteggio totale.

| Domanda controllata | Selezione da dimostrare |
| --- | --- |
| PEC ricevute il 14 10 2026 | Messaggi ricevuti il 14 ottobre, non ricerca della data nel corpo |
| PEC ricevute il 14/10/26 | Identico insieme e medesimo ordinamento |
| PEC ricevute il 14/10/2026 | Identico insieme e medesimo ordinamento |
| PEC ricevute il 14.10.2026 | Identico insieme e medesimo ordinamento |
| PEC ricevute il 14-10-2026 | Identico insieme e medesimo ordinamento |
| PEC ricevute il 14-10-26 | Identico insieme e medesimo ordinamento |
| PEC ricevute oggi / ieri | Giorno civile Europe/Rome, incluso passaggio ora legale e mezzanotte |
| PEC inviate il 14/10/2026 | Direzione inviata; non ricevute di altri invii |
| Depositi accettati ieri | Esito del deposito dimostrato; la sola accettazione SMTP non basta |
| Deposti accettai ieri | Variante ortografica delimitata dello stesso intento, senza alterare nomi o identificativi |
| Depositi da fare | Attività pendenti governate; esclusi completati, annullati e non dovuti |
| Notifiche accettate | Ricevute di accettazione delle notificazioni legali; distinte dalla consegna |
| Notifiche da fare | Procedimenti di notificazione pendenti; non avvisi della campanella |
| Agenda il 14/10/2026 / oggi / ieri | Solo il giorno richiesto, senza intervallo implicito di quattordici giorni |
| Agenda dal 14/10/2026 al 16/10/2026 | Estremi inclusi e ordinamento cronologico |
| PEC il 31/02/2026 | Data non valida esplicita; nessun allargamento silenzioso della ricerca |
| PEC oggi e ieri | Unione dei due giorni dichiarata; non scelta arbitraria del primo |

## Percorsi esistenti e difetti osservati nel codice

- `lex/operational_knowledge/query_router.py`: il ramo con «oggi» precede agenda;
  «notifiche» può selezionare le notifiche utente invece delle notificazioni.
- `lex/operational_knowledge/service.py`: alcuni rami agenda usano quattordici
  giorni indipendentemente dalla data scritta nella domanda.
- `lex/operational_knowledge/tools.py`: consultazione email tramite `tutte` e
  agenda tramite `tutti`, con filtri e limiti successivi in memoria. Il percorso
  va ricondotto ai filtri SQL pertinenti, senza importare interi cataloghi.
- `pct/email_client.py`: `tutte` può deduplicare e salvare durante la lettura;
  questa operazione non è ammissibile come effetto di una semplice domanda.
- `pct/email_mailbox_repository.py`: esiste già il catalogo SQL tenant-aware;
  conservarne bootstrap, isolamento, audit e mutazioni puntuali.
- `pct/pec_notification_presidio/repository_queries.py`: esistono già filtri
  SQL per stato e periodo dei presìdi legali; non creare una procedura parallela.
- `lex/risposte_certe.py`: esiste già il riconoscimento di date numeriche e
  letterali; estenderlo con guardie, senza creare parser incompatibili.

## Accettazione necessaria

Confrontare gli identificativi restituiti da ciascuna formulazione con quelli
selezionati dai repository proprietari. Provare due tenant, permessi negati,
record fuori periodo, stati discordanti, paginazione, errori SQL, retry e
assenza di scritture o lavorazioni estranee. Verificare SQLite e PostgreSQL,
poi domande reali nel browser visibile su 127.0.0.1:8080, fonti apribili e
prestazioni confrontabili. Commit, CI e deploy soltanto dopo tali verifiche.

## Riscontri di ricostruzione del 16 ottobre 2026

- Il router tratta oggi/domani prima del ramo agenda: una data relativa può cambiare il dominio richiesto. Il riconoscimento del dominio esplicito deve precedere quello del periodo.
- Il servizio agenda impone oggi più quattordici giorni e ignora la data esplicita. Il periodo deve provenire dal parser comune e una data non valida deve bloccare la selezione.
- Il percorso notifiche usa get_notifiche_utente: queste sono notifiche applicative, non prove di notificazioni legali. Riutilizzare il repository pec_notification_presidio e le ricevute dei destinatari; accettazione e consegna restano fatti distinti.
- Agenda e scadenziario hanno già tabelle e indici SQL per data/stato. I manager attuali caricano tutti i record nel costruttore: aggiungere filtri dopo la costruzione non elimina la lettura globale. Il percorso consultivo deve raggiungere direttamente il database proprietario risolto dal tenant, senza inizializzare manager o dati.
- Un deposito accettato richiede ACCETTATO_CANCELLERIA; la sola ricevuta PEC non dimostra tale stato. Le attività da fare richiedono invece le procedure pendenti, senza confonderle con depositi già inviati.

Questi sono riscontri sul codice, non prove di accettazione della funzione. Il rilascio49 rimane distinto e ancora in verifica CI/deploy; nessuna migrazione dei dati reali è avviata da questa analisi.
- Ulteriore riscontro sul percorso consultivo: _tenant_manager costruisce StudioDB SQLite direttamente; la nuova interrogazione deve rispettare il profilo PostgreSQL/SQLite effettivo e il tenant autorizzato, senza inizializzazioni di schema o migrazioni durante la domanda. Riutilizzare i resolver esistenti di storage_runtime e i backend esistenti con initialize_schema=False dove necessario, evitando fallback verso mirror JSON/SQLite quando PostgreSQL è proprietario.
- Nel messaggio strutturato ora conservato si osservano fonti di catalogo generiche estranee alla questione penale puntuale. Distinguere fonti soltanto catalogate, evidenze esaminate e fonti effettivamente usate: non presentare un catalogo come prova di lettura o pertinenza. La correzione del lettore del banco di prova non dimostra la soluzione di questa selezione.

16/10/2026 — Avanzamento incarico50 (non rilasciato): il49 è stato rilasciato su41375ed64f1d79b2551f6096063ceed60f4df2dc, locale eHetzner2.437.49. Nuovi lettori privati SQLite/PostgreSQL in sola lettura, senza singleton scrivibili, inizializzazione o fallback sul mirror; test nativi con due studi sintetici. Risolto un errore della migrazione a lotti: la riga compatibile PostgreSQL va letta per indice, non scomposta tramite iterazione delle chiavi. Gruppo nativo di98casi positivo. Selettore consultivo distingue giorno italiano, direzione PEC, cestino, accettazione gestore/cancelleria, RAC e data di scadenza delle attività da fare. Sei casi aggiuntivi agenda verificano i confini di giorno e i cambi di ora legale; gruppo date/selettore83casi positivo. Cestino e direzione indipendenti provati sui due database; gruppo casella/confine15casi positivo. Strumento query_pec_page legge soltanto la pagina SQL autorizzata, espone paginazione e date originali mancanti; cinque prove native del confine richiesta positive, con blocco permessi prima dell'accesso SQL e divieto di gestore MIME/load completo/DDL durante la domanda.

Ancora necessari: regia dell'aggiornamento della proiezione senza scansione globale in richiesta, migrazione governata dopo backup, domini agenda/scadenziario/depositi/notificazioni sulle rispettive fonti native, instradamento e risposta completa con continuazione, test concorrenza e regressioni, immagine locale8080, prova reale visibile, commit/CI/deploy/pulizia. Nessuna modifica dell'incarico50 attiva sulla copia8080 o sul server; nessuna accettazione utente dichiarata. Individuata outbox transazionale condivisa pct/transactional_outbox.py per il riuso: non introdurre una coda duplicata prima di ricostruirne produttori e consumatori. I dati JSON storici di Agenda possono prevalere sulle colonne: non filtrare fiduciosamente una colonna discordante senza diagnosi e riallineamento governato.

16/10/2026 16:18 — Proiezione posta: sostituita la ricerca globale NOT EXISTS con controllo indicizzato di bootstrap e consegne pendenti/fallite nell'outbox transazionale esistente. Trigger privati sulle sole mutazioni della fonte e sulla perdita di una proiezione; nessun avvio MIME/OCR. Scrittori nativi confermano fonte e indice nella stessa transazione. Recupero a lotti degli eventi con massimo cinque tentativi e attesa persistente; ripetizione senza doppioni e cancellazione della sola proiezione priva di fonte provate sui due database. Ventuno casi della proiezione positivi. Prima verifica estesa ha rilevato otto errori: quattro aspettative del test adattatore non coerenti con il costruttore già presente al commit413 (nessun load vuoto e snapshot originale None), quattro contratti di schema/migrazione da integrare. Confrontato il sorgente HEAD, aggiornate le asserzioni mantenendo il divieto di caricamento dell'intero catalogo; struttura consultiva inclusa nei DDL core già composti e confronto della migrazione storica06 più incrementale16, senza riscrivere il file storico. Ripetizione del gruppo adattatori/factory/repository/schema/proiezione positiva; classi base e fixture prive di configurazione sono esplicitamente saltate. Ancora nessuna nuova funzione attiva su8080: integrazione delle ricerche e prova reale restano richieste.

16/10/2026 — Collegamento consultivo: domande PEC semplici instradate alla sola sorgente email_pec; i filtri per cliente/allegati e i comandi dispositivi non sono scartati per forzarli in questo percorso. Le sei varianti di data attraversano servizio, repository SQL controllato e compositore senza leggere altri domini. Consultazione eseguita senza corrispondenze distinta da consultazione fallita; nessuna fonte-messaggio inventata per giustificare lo zero. Cursore firmato con scadenza, tenant/utente e filtri originali, inviato dal comando esistente Mostra altre PEC; firma alterata, scadenza, studio/utente diverso e cambiamento dei filtri rifiutati. Compositore preservato quando si usa la continuazione; il token resta nell'azione, non nel testo della domanda, e il pulsante viene ricostruito alla riapertura della conversazione. Il click durante una richiesta attiva non avvia duplicati; una continuazione interna non viene trasformata in ricerca Web dalla preferenza globale.

Guardrail HTTP ha individuato due difetti durante lo sviluppo: variabile query_verified inizialmente inserita nel rilevatore di intento invece che nel verificatore, e helper storico che tratta una lista vuota come errore. Corretti nel nuovo percorso; ripetizione dei due contratti HTTP sincrono/SSE positiva. La ricerca strutturata viene eseguita dopo autorizzazione ma prima di contesti estesi, runtime del modello, generazione del prompt e cataloghi estranei; i test vietano tali dipendenze. Prove estese ancora in esecuzione. Inserita ripresa governata nella regia periodica esistente, mantenendo congelati invio PEC, firma e deposito; connessioni private scrivibili del worker non inizializzano schemi e non condividono singleton. Schemi ridotti di test esclusi dall'installazione dei trigger posta, versione della migrazione persistita e installazione PostgreSQL serializzata. Ancora necessarie migrazione controllata, altri domini richiesti, browser reale8080, CI, commit/deploy/pulizia; nessuna accettazione finale.

16/10/2026 — Punto di avanzamento successivo:179guardie native positive su conoscenza operativa, selettori/cursori, confine richiesta, widget e ponte/orchestratore HTTP. Ulteriore gruppo87casi positivo su date, repository casella SQLite/PostgreSQL e richieste reali controllate (guardrail, non accettazione utente). Migrazione ora con registro SQL persistente, backup nativo verificato, hash del backup, autore e cursore; tentativi di salto righe, cambio backup e autore discordante bloccati. Script scripts/mailbox/rebuild-query-index.py riusa i backup SQLite coerenti e pg_dump16 già previsti; legge solo il catalogo SQL proprietario, non importa mirror né cambia stati della posta. Collaudo sintetico effettivo di snapshot SQLite quick_check=ok e ripresa dopo un lotto positivo, con payload dei messaggi immutati. Recupero periodico separa i guasti dei singoli studi e non li nasconde.

Diagnosi sulla copia reale: tentato mostra pannelloBrowser della scheda propria16 tramite open_in_codex, navigazione alla chat corrente e capability visibility. Il controllo continua a restituire false/queued; nessuna nuova prova materiale può essere accettata come visibile in questo stato. Nessuna richiesta all'utente ripetuta; sviluppo e controlli indipendenti proseguono. Runtime reale locale e produzione restano413/2.437.49. Non è stato eseguito commit/deploy dell'incarico50 né modificata la fonte dati reale.

Guardrail aggiuntivi in corso: una data incompleta o un intervallo senza estremo finale non possono allargare la casella; una data d'importazione non viene mostrata come data originale mancante. Zero risultati con fonti senza data viene descritto come assenza di corrispondenze tra le PEC databili, con messaggi non attribuibili espliciti, senza certezza fittizia. Restano da collegare i domini Agenda, Scadenziario, depositi e notificazioni alle fonti native e da completare accettazione reale, gate e rilascio.

16/10/2026 — Preparazione altri domini: ricostruzione puntuale delle righe Agenda/Scadenziario estratta dalle procedure native in pct/calendar_sql_records.py, mantenendo priorità del JSON storico e campi integrativi SQL. Individuata e corretta la mutazione dello snapshot originale nel caso scadenza senza dati_json: gli array decodificati restano nel modello, i valori raw nello snapshot del salvataggio ottimistico. Quarantasette guardie native positive con concorrenza SQLite/PostgreSQL, precedenze, identità, data legale e proiezione casella. L'estrazione non avvia gestori, letture di mirror o eventi documentali.

Trigger outbox della posta ricondotti al piccolo installatore condiviso pct/query_projection_outbox.py per il riuso nei cataloghi richiesti, senza un secondo dispatcher; ventitré guardie native della proiezione positive sui due database dopo l'estrazione. Aggiunto accesso read_only al repository notificazioni e alla factory esistente, con default di scrittura invariato. Runtime produttivo del presidio continua a usare il proprio PEC_AUDIT_DB SQLite autorizzato: PostgreSQL core non viene sostituito a questo archivio verticale. Prove sintetiche supportano entrambi i backend. Primo test nuovo fallito per destinatario sintetico assente e per stub unitario PostgreSQL non sostituito prima della raccolta; corretti il dato controllato e il pre-caricamento nativo di pct.postgres_runtime_support, senza modificare regole del presidio o conftest condiviso. Tre guardie native positive: lettura del candidato, tentativo SQL di cancellazione bloccato, writer indipendente e archivio assente non creato. La ricerca per stato/data delle notificazioni non è ancora collegata; fonte legal_notifications censita separatamente dalle notifiche della campanella.

16/10/2026, candidata50 — Aggiornamento del collaudo reale: immagine senza cache con9565impronte runtime/asset/SQL coincidenti, Python3.12.15 e pacchetti invariati; preparazione nativa dei tre studi locali senza ulteriori modifiche. Copia8080 alla2.437.50 con app, scheduler eOCR healthy. Browser reale visibile: PEC ricevute e inviate del14ottobre distinte, cestino distinto, varianti data italiana, Agenda oggi senza risultati esplicita, Agenda paginata con bozza preservata, Scadenziario aperto e notificazioni accettate per data di registrazioneRAC. Collegamento PEC apre il messaggio controllato corretto. Nessuna accettazione globale dichiarata.

Difetto emerso e lavoro aperto: apertura casella impiega85secondi, blocca un worker e ritarda una richiesta Scadenziario a57secondi. Profilazione dei processi reali e replica SQL in sola lettura dimostrano query riepilogo PEC con331header e317risultati:59,08secondi; forzare il vecchio indice header richiede ancora50,54secondi. Previsto indice coprente sui soli campi del riepilogo, senza MIME/metadata_json e senza modifica della query o del flusso PEC. Dieci guardie native della preparazione positive, inclusa conservazione dei byte della fonte e pianoSQL coprente. Preparazione reale dopo verifica del backup e nuova immagine ancora in corso; prove ripetute, CI, commit e deploy richiesti. Depositi e ricevute nei fascicoli/PEC restano incarico successivo distinto, senza attribuire RAC ad accettazione della cancelleria.

16/10/2026, collaudo50 — Le due letture SQL della casella hanno ora indici coprenti sui soli campi consultati, con preparazione nativa dopo backup prima dell'avvio. Misurata la stessa query di317riepiloghi in14,541ms e l'elenco di200righe in6,822ms; API della pagina reale718,4ms contro85,061secondi prima, dettaglio348,5ms. Gli indici non dimostrano alcun nuovo fatto legale e non modificano gli originali. Impronta di schema predisposta dal repository nativo prima dello swap. Necessarie nuova immagine, prova dei link e della validazione, commit/CI/deploy/pulizia.

16/10/2026, immagineG candidata50 — Ripetizione finale con visibilità effettiva controllata prima e dopo le interazioni: tutti i sei formati14 10 2026,14/10/26,14/10/2026,14.10.2026,14-10-2026,14-10-26 restituiscono lo stesso messaggio controllato ricevuto del14ottobre. Ricerche inviate/cestino distinte; oggi16ottobre e ieri15ottobre producono zero corrispondenze esplicite. Agenda eScadenziario restituiscono12voci per pagina; udienza controllata20ottobre trovata e collegamento aperto nel dettaglio corretto; scadenza16dicembre aperta nel proprio dettaglio. Continuazione Agenda restituisce la pagina successiva mantenendo la bozza digitata. Notificazioni accettate e dafare, con e senza data: zero corrispondenze nel catalogo locale, nessuna prova positiva di notifica accettata inventata. Data impossibile31/02 rifiutata senza falso avviso di permessi; link interni renderizzati e aperti realmente. Telefono375x812 e tablet805x1000: risposta e scorrimento osservati, bozza conservata chiudendo/riaprendo, dimensioni ripristinate. Prima fase con visibilità non confermata trattata come diagnosi e ripetuta: non usata per l'accettazione. Prove e schermate riservate fuoriGit.

ImmagineG senza cache:9565sorgenti eseguibili/asset/SQL confrontati, nessuna differenza; Python3.12.15 e pacchetti uguali alla candidata precedente verificata. Preparazione nativa finale su tre studi, studio operativo senza ulteriori modifiche; app/scheduler/OCR healthy su8080. Commit, controlli GitHub e deploy ancora richiesti; incarico non rilasciato.
