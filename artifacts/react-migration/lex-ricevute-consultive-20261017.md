# Ricevute consultive in Lex — candidata 2.437.52

## Risultato richiesto

Consultare per data le ricevute già analizzate nel repository PEC e quelle
archiviate nei documenti dei fascicoli, aprendo le fonti originali. Distinguere
accettazione del gestore, accettazione della cancelleria e mera prova di
trasporto; nessuna consultazione deve confermare una notificazione, attribuire
un procedimento o modificare il flusso deposito/firma/PEC.

## Procedura

- Cataloghi SQL derivati, tenant e autorizzazioni prima dell'accesso.
- Preparazione esplicita con backup verificato, cursore e lotti finiti;
  nessuna inizializzazione, lettura MIME o OCR nella domanda Lex.
- Aggiornamento tramite la outbox condivisa dei soli oggetti modificati.
- Data dell'evento, con precisione e discordanza conservate; mai data di importazione.
- Copie byte-identiche raggruppate soltanto nello stesso fascicolo e per
  lo stesso tipo di prova; tutti i collegamenti documentali conservati.
- Report PEC con impronta discordante o fonte modificata non confermati,
  anche dopo retry. Un messaggio sostituito richiede il percorso nativo
  di acquisizione; la proiezione non rilegge il MIME.
- Cambi di compatibilità dei lettori invalidano il catalogo fino alla
  preparazione esplicita dei soli metadati già archiviati.
- Pagine SQL e continuazioni firmate per studio, utente, selezione e fase.
  Le domande con cliente/fascicolo attivo mantengono il percorso contestuale
  esistente: il router globale non scarta quei filtri.

## Verifiche tecniche eseguite

Il gruppo nativo di 138 casi su SQLite/PostgreSQL è positivo. Ulteriori
15 casi su accesso Lex agli archivi, collegamenti alle copie originali,
RBAC e migrazioni sono positivi; gruppi sovrapposti, non sommabili.
Ruff sui nuovi moduli positivo. Preparazione con più di 50 eventi e budget
insufficiente provata: nessun esito COMPLETED con consegne residue.
Questi controlli non sono accettazione utente.

Successiva esecuzione sul commit99173f6f6d, in contesto Git pulito e montato
in sola lettura:185 casi nativi positivi, uscita0, nessuno skipped.
Python3.12.15 e120pacchetti identici alla51 salvo il package applicativo52;
9857 sorgenti Python/JavaScript/SQL dell'immagine corrispondenti a Git.
Un gruppo più generale sulle fonti ufficiali è stato interrotto: attivava
acquisizioni non pertinenti e generava tre artefatti sintetici nella root;
questi sono stati preservati fuori dal repository con impronte, non inclusi
nel commit e non presentati come prova positiva.

Rifinitura del provisioning: il nuovo studio prepara anche l'archivio PEC
vuoto mediante il repository nativo e backup verificato, senza avviare
analisi o invii. La prima fonte produce poi la consegna della proiezione;
un archivio già popolato richiede la migrazione esplicita esistente.
Sette guardie native provisioning/migrazione/worker positive. Necessari
nuova immagine e collaudo materiale prima del push.

La preparazione locale iniziale è stata interrotta (uscita137) durante il
backup PEC: aggiornamenti concorrenti e filesystem condiviso rallentavano
la copia. Il parziale è conservato. Ripetuto lo stesso backup nativo su
ext4 temporaneo, quick_check positivo; poi copia persistente di2789781504byte
e confronto integrale SHA2564108dc8df9b28818aa70b646d29a5496bb362b7545f4ba4ae03e47c8ee1d0b21.
Manifest nativo pubblicato soltanto dopo la verifica; ripresa con il
preparatore originale. Nessuna cancellazione di backup o modifica al
motore di acquisizione PEC, nessun intervento sull'addestramento.

## Stato della consegna

Restano immagine canonica, prova materiale nel browser visibile su 8080,
verifica delle domande sul caso reale, CI/copertura, push, deploy sullo stesso
commit e pulizia verificata. Candidata non dichiarata rilasciata.

## Capacità e backup del server

Al controllo del 17 ottobre il server dispone di 104.442.994.688 byte liberi.
Il percorso storico `preserved-before-fascicoli51-4344` non esiste più.
I registri di manutenzione già presenti sul server dichiarano la sua rimozione
e quella di altri snapshot intermedi, previa verifica del backup più recente.
Copie dei registri sono conservate nel dossier privato; non dimostrano un
trasferimento su D:. Nessuna copia locale del vecchio snapshot è stata
verificata da questo incarico e non si attesta l'offload autorizzato.
Il backup strutturato più recente e il baseline del deposito sono presenti.
Nessuna ulteriore cancellazione di backup è stata eseguita durante questi controlli.

## Aggiornamento preparazione del 17 ottobre

La preparazione reale è stata fermata sul cursore persistito di 400 messaggi:
l'aggiornamento identico dell'identità PEC riscriveva inutilmente righe contenenti
il MIME. La proiezione SQLite ora serializza sul piccolo catalogo derivato;
PostgreSQL acquisisce il blocco della sola identità con SELECT FOR UPDATE.
La migrazione consulta la fonte senza aggiornarla. Il test negativo che vieta
qualsiasi UPDATE dei messaggi falliva prima della correzione; ora passa anche
attraversando il lotto di migrazione. Passati inoltre 22 controlli mirati nativi
SQLite/PostgreSQL di repository, migrazione e consegna. Backup verificato e
cursore restano conservati per la ripresa; nessuna accettazione reale della
candidata 52 è ancora dichiarata.

## Gate copertura e correzione dei test

Il primo push della candidata è stato fermato dal confronto critico:
baseline 28741/35144 (81,7806738%), candidata 28828/35288 (81,6934935%).
Gli altri 88 job erano positivi. I test delle ricevute erano già inclusi
nella suite critica: mancavano prove sulla composizione delle risposte,
non una voce nel manifest. Aggiunti controlli sui link originali, date italiane,
distinzione gestore/cancelleria, copie identiche, fonti non confermate,
assenza di risultati e continuazioni firmate. Il gruppo nativo passa 17 casi;
46 istruzioni precedentemente mancanti risultano esercitate localmente.
Questa indicazione non sostituisce il nuovo confronto CI dei dodici shard.
Nessuna soglia o esclusione di misura modificata.

La copia reale locale è stata aggiornata a39fe7d8037 e risponde2.437.52;
app, scheduler e OCR healthy. Preparazione conclusa:590 messaggi esaminati,
46 righe derivate, nessuna consegna PEC pendente. Le impronte dei sette
insiemi di dati principali prima/dopo coincidono. Pulizia locale eseguita,
backup e dieci volumi conservati. Verifica utente NON eseguita: il browser
integrato restituisce disabilitato; Computer Use nativo interrompe la lettura
perché non determina con sufficiente certezza l'URL di Chrome. L'utente,
informato del vincolo, ha richiesto espressamente push e deploy comunque.
Il collaudo materiale resta aperto e non viene sostituito dai test tecnici.

## Blocco SQLite della preparazione su Hetzner

La CI del commit d8b2f7441f è positiva: candidata28874/35288=81,8238495%,
baseline28741/35144=81,7806738%, ambiente omogeneo. Il deploy si è invece
fermato nella preparazione dell'archivio ricevute, lasciando la versione
precedente healthy. Riprodotto database is locked con due fascicoli,
prove sintetiche grandi e cache SQLite ridotta: dopo lo spill della prima
scrittura, la seconda connessione di lettura era bloccata dalla transazione
stessa. La proiezione riusa ora la propria connessione per lettura e datazione
delle fonti. La funzione consultiva autonoma conserva apertura/chiusura native;
la connessione fornita dal chiamante non viene chiusa, confermata o annullata.
La prova include rollback completo delle righe derivate.59controlli nativi
SQLite/PostgreSQL positivi dopo la correzione, nessuno skipped.
Backup e cursore di produzione conservati; necessaria ripresa sul nuovo commit.
