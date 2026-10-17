# Preventivi e Incarichi: concorrenza e fonte SQL

Risultato atteso: due sessioni che modificano voci distinte conservano entrambe le
modifiche. Sulla stessa voce, la seconda modifica obsoleta viene rifiutata senza
alterare quanto confermato, senza audit di successo e conservando la bozza.

La prova iniziale su archivio sintetico ha prodotto `different_rows_preserved=false`.
La causa è `_salva_preventivi`/`_salva_conferimenti`, che sostituivano le tabelle
partendo dallo snapshot del singolo gestore. Le copie della proiezione venivano
inoltre ricostruite/esportate durante inizializzazione e salvataggio.

Il writer dedicato usa le transazioni del backend esistente, solo sulle righe
modificate. Confronta tutte le colonne dello snapshot prima di aggiornare o
eliminare; inserimenti con conflitto esplicito, numerazione assegnata sotto lock
transazionale (SQLite BEGIN IMMEDIATE; PostgreSQL advisory lock per dominio).
I metadati non modellati restano nella stessa riga. I campi storici discordanti
non vengono riallineati per effetto di una modifica estranea. Non cambia il
calcolo di compensi, accessori, imponibile, incassi o fatture.

La superficie React riceve la revisione della voce e la invia con il cambio di
stato. Revisioni mancanti/obsolete restituiscono 409; la selezione locale resta
visibile. Gli altri comandi SQL sono protetti dal confronto concorrente; non si
attribuisce a questa correzione la revisione preventiva di ogni modulo storico.
Errori concorrenti nelle API sono espliciti; le form storiche conservano i campi
in una pagina di errore senza ripetere automaticamente il comando.

La vista del catalogo riusa il builder e i selettori del repository nativo,
leggendo preventivi e conferimenti dal SQL proprietario. La cache della vista è
validata con le revisioni persistenti esistenti; massimo due tentativi se cambia
la fonte durante la costruzione, poi conflitto esplicito. I JSON storici e il
vecchio database di proiezione restano conservati; non sono fonte autorevole
nel percorso SQL. Esportazione soltanto su comando esplicito. Il percorso JSON
standalone degli strumenti storici resta disponibile e coperto dai test.

Audit read-only: tre studi locali, uno con un preventivo e un incarico; due studi
server, ciascuno con un preventivo. Nessun ID dei JSON esaminati manca dal SQL.
Un riferimento storico a pratica assente resta segnalato e non viene trasformato
in associazione valida. Nessuna riconvalida massiva o modifica dei dati reali.

Verifiche: prove sintetiche SQLite/PostgreSQL, parità della vista con il catalogo
esistente, revisione obsoleta e corrente, rollback, metadati, cancellazioni,
revisioni/conversione, route di conferimento/accettazione, wizard e permessi.
La misura del miglioramento non equivale a una prova di velocità globale: il
caricamento integrale iniziale delle due tabelle resta nel perimetro futuro di
paginazione e interrogazioni mirate.

Stato: candidata 56 in verifica. Collaudo visivo non verificato su macchina reale;
prosecuzione fino a commit e deploy autorizzata dall’utente il 17/10/2026 anche
con canale browser indisponibile. Non dichiarare superata questa prova.

Riscontri prima del rilascio:21 casi SQLite positivi;20 positivi PostgreSQL e1 skip del solo probe SQLite;66 casi wizard/motore positivi;gruppo integrato36 positivo con repository storico, route e pagina profonda. I gruppi si sovrappongono e non vanno sommati. Typecheck, build e guardie frontend positivi. Nessuna funzione preesistente modificata nei due blueprint condivisi:aggiunti soltanto gestori dell’errore concorrente, come verificato sul confronto AST.
