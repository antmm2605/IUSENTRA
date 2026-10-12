# Epigrafi e recupero del lettore — incarico aperto

## Risultato richiesto

Il lettore deve riconoscere le parti processuali senza trasformare indirizzi,
qualifiche, intestazioni scolastiche o etichette di modelli vuoti in persone.
Ogni codice fiscale resta riferito al soggetto che lo dichiara nella fonte,
senza attraversare la sezione del difensore. I contratti di lavoro e di
prestazione d’opera conservano la propria natura documentale e non producono
parti o date processuali.

## Cause e correzioni della candidata 2.437.13

L’enfasi rappresentata con asterischi spezzava l’ancora del nome: ora si
normalizza conservando i separatori di epigrafe. Il nome dell’ente richiede
un confine di parola. Le qualifiche iniziali vengono separate dal nome;
etichette fiscali non sono nomi. La sezione dell’Avvocatura delimita i dati
della controparte. La classificazione nativa riconosce il titolo del
contratto di prestazione d’opera, senza classificare come contratto un
ricorso che lo cita.

Le letture storiche compatibili restano ferme. La riconvalida è un evento
SQL esplicito sul fascicolo interessato, con le procedure e i motori
condivisi. Nessun filtro della UI nasconde una discordanza e nessuna
decisione manuale viene sostituita.

Il lettore documentale ritenta soltanto le GET interrotte o temporaneamente
non disponibili, con limite di tre richieste e messaggi italiani. I
salvataggi non vengono ripetuti automaticamente. È disponibile il comando
di recupero del caricamento, senza eliminare modifiche locali.

## Riscontri finora osservati

Browser reale 8080: dopo rilettura puntuale del primo fascicolo verificato, la
residenza resta nella citazione del cliente; quattro parti proposte,
nessuna persona ricavata dall’indirizzo o dall’etichetta fiscale. La vista
già aperta aveva conservato la proposta precedente fino al ricaricamento:
il comportamento live resta sotto verifica.

Browser reale, secondo fascicolo: nome privo della qualifica e nessuna intestazione
scolastica tra le parti. Emerso codice del difensore attribuito al
Ministero in due atti; corretto il confine e riscontrati i due originali
con il motore condiviso. Dopo il completamento della coda SQL, riapertura
reale e successivo aggiornamento WIP8 confermano il nome del cliente e il
codice fiscale proprio del Ministero; gli originali restano conservati.

Guardrail: 54 test Python mirati, cinque test di recupero HTTP, Ruff;
gate statico con 26 controlli e 101 verifiche Storybook senza errori.
Sono guardrail tecnici, non accettazione finale. Backup coerenti e fonti
originali conservati fuori Git. Commit, push, riallineamento al commit e
deploy di questo punto non ancora eseguiti; incarico generale aperto.

12/10/2026 — Ulteriori riscontri: il payload storico del verificatore del
 giudice non conteneva fascicoloId e campi necessari al pannello comune;
la GET falliva con KeyError. Il repository restituisce gli identificativi
SQL autorevoli, il produttore conserva confronto e collegamenti alle fonti.
Ripubblicazione nativa sui due fatti verificati, valore manuale preservato.
Browser reale WIP6: avviso con RG completo e due documenti espandibili.
Emersa falsa discordanza dovuta al diverso ordine delle stesse parole del
nome del magistrato: confronto esatto delle parole introdotto, senza
correzioni per somiglianza né sovrascrittura del valore manuale. La nuova
prova reale WIP7 conferma l'assenza della falsa discordanza dopo consegna
nativa dei due fatti: valore manuale invariato, vecchia verifica superata
con audit, nessuna presa visione manuale dell'agente.

Lettore reale: fonte Contratto 21-22.PDF, otto pagine, scroll fino alla
pagina finale con immagine, testo, timbro e sottoscrizioni visibili.
Modifica testo correttamente protetta; nessuna modifica dell'originale.
Questa prova non dichiara qualità OCR integrale o recupero HTTP transitorio.

Scheduler: errore database is locked alle 02:19 durante rilettura puntuale;
lock non presente alla diagnosi delle 02:26, recupero al ciclo naturale
02:34 concluso alle 02:37, prima di ricreare i container. Causa esatta della
contesa ancora sotto presidio. Gate statico primo giro 25/26: inventario
 dei test non aggiornato, generato con script nativo; nuovo giro 26/26,
101 Storybook. Ultimo perimetro Python 75 test positivi, Ruff positivo.
Nessuna dichiarazione di chiusura prima di commit/push, allineamento locale
e deploy verificato. Incarico generale aperto.

12/10/2026 — Apertura delle fonti: nel browser integrato la pagina ha una
cornice esterna non accessibile; il comando veniva inviato a quella cornice
anziché alla shell IUSENTRA. Il dispatcher inoltra al parent soltanto da
un iframe realmente accessibile dello stesso sito; negli altri casi usa
la regia di finestre della pagina corrente. Quattro guardrail dedicati,
più cinque sul recupero GET, positivi. Browser reale 8080 WIP8: Agenda,
impegno del 09/10, Visualizza fonte apre il decreto dalla PEC nel lettore
nativo; pagina originale visibile, tutto schermo, scroll fino al fondo,
chiusura conserva il dettaglio e riapertura mostra di nuovo il PDF.
Foto privata source-window-real-local-wip8.jpg, nessuna modifica o invio.
Gate finale ripetuto: 26 controlli, 101 verifiche Storybook, nessun errore;
75 test Python mirati positivi con Python 3.14 locale. La CI Python 3.12
e il rilascio sullo stesso commit sono ancora da eseguire. Il recupero
HTTP temporaneo è verificato tecnicamente, non ancora osservato durante
una reale interruzione sul commit finale. Copertura live globale, causa
esatta della contesa SQL e altri incarichi restano aperti e presidiati.

Controlli estesi: la raccolta completa della suite ha rilevato che il test
Timesheet già tracciato dal commit 4b7e365f3c importava uno script assente
da Git, checkout, copie recuperate e server. Aggiunta la procedura SQLite
esplicita richiesta da quel contratto: anteprima senza scritture, due
backup nativi con hash e quick_check, rifiuto di collisioni e collegamenti
mancanti, inserimenti puntuali e audit nella transazione. Cinque prove su
archivi temporanei positive, inclusi backup fallito, replay senza nuovo
audit e fonte preservata. Il primo nuovo fixture lasciava aperta una
connessione di controllo su Windows: chiusura esplicita e prova ripetuta.
Nessuna migrazione Timesheet eseguita sui dati reali; concorrenza e adozione
operativa Timesheet restano un incarico distinto aperto.

Registrati i cinque file Python del perimetro nella matrice nativa
quality-overlay: tutti e tre gli shard eseguiti con limite di cinque
minuti, esiti positivi (shard più lungo 40,1 secondi). Raccolta completa
ripetuta senza errori. Una build estesa ha fallito per file index.html
mappato da Windows: ripetizione isolata positiva, senza cambiare il codice
o indebolire il controllo. I restanti gate completi sono ancora in corso.

Prima del rilascio, backup coerente dei registri dei due studi in
/data/backups/identity-release-prod-20261012-before: quick_check positivo,
hash nel report privato. Inventario SQL produttivo: cinque verifiche nel
primo studio, nessuna nel secondo; nessun payload storico incompleto del
giudice aperto. Nessuna verifica rimossa e nessuna presa visione applicata.

Backup strutturato produttivo eseguito dalla procedura nativa prima del
rilascio: snapshot /opt/iusentra/backups/epigrafi-release-20261012/
iusentra-structured-20261012_011229_570864. Tre database dello studio
(incluso il percorso storico), 14.511.976.448 byte, tutte le verifiche
quick_check positive e impronte nel manifest. Nessuna fonte locale
trasferita e nessun dato applicativo rimosso. Un primo comando di sola
lettura del manifest aveva quotatura PowerShell errata: ripetuto con
lettura diretta riuscita; backup non modificato.

Ulteriore riscontro visivo WIP8: scroll reale nel pannello del secondo fascicolo,
cliente con codice fiscale concordante, Ministero con codice fiscale
proprio e difensore separato; ruoli non dimostrati ancora espliciti.
Foto privata case-b-parts-final-local-wip8.jpg. Nessuna aggiunta manuale
al fascicolo o conferma di avvisi.

Prova materiale della navigazione con bozza nuova, senza associazione a
cliente/fascicolo e senza salvataggio: scritto il testo controllato,
clic reale Oggi dalla navigazione principale, finestra caricata, chiusa.
L'editor resta sul proprio URL e conserva il testo e lo stato Modifiche
non salvate. Foto private editor-draft-navigation-local-wip8.jpg e
editor-draft-retained-local-wip8.jpg. Annulla ripristina zero parole;
nessun documento creato nel fascicolo. Non estendere questo riscontro
alla persistenza di tutti i tipi di bozza o a tutti i percorsi editor.
Dal riscontro emerge sovrapposizione parziale della riga di stato con
la toolbar: registrata tra i dettagli editor ancora da correggere.
Ultimo gate statico: 26 verifiche positive, exit 0; controllo completo
ancora in corso.

Nuovi fixture di regressione: nomi e codici personali sintetici, indirizzo inventato e magistrati inventati; 39 prove mirate ripetute positivamente dopo questa verifica. Le fonti reali e le fotografie restano fuori Git. CTU: il rilascio SQL/live del 10/10 è documentato, non ripetere l’adozione. Il riscontro odierno del presidio backup rileva riferimenti non raggiungibili nei due studi; conservati audit e snapshot coerenti correnti, recupero puntuale ancora aperto nel registro.

Guardrail OCR del 12/10: due aspettative statiche del vecchio percorso fallivano anche senza differenze nei file runtime rispetto al commit di base. La prova aggiornata segue FascicoloOcr → OcrConfronto → OcrPageViewer/OcrReview e confronta i quattro estremi dei riquadri con quelli nativi del PDF a 300 dpi (tolleranza di un pixel), preservando font e grassetto. Il solo stile dinamico ammesso nel menu è la sua altezza misurata nel viewport; resta vietato introdurre stili decorativi in linea. Tutte le 55 prove del file passano. Nessuna modifica al motore OCR o alla superficie runtime in questo passaggio; controllo integrale ancora in corso.

Prova materiale del recupero su 8080: apertura dal comando Anteprima del DOCX controllato, chiusura e riapertura durante arresto e riavvio del solo container app locale (scheduler/OCR e server produttivo preservati). Il lettore mostra errore italiano e Riprova caricamento; app torna healthy e pronto HTTP 200. Il clic reale Riprova recupera la policy ma lascia la fonte sulla pagina offline: risultato incompleto, causa nel mancato aggiornamento della revisione del lettore. Corretto il pulsante per aggiornare anche la revisione, con rimontaggio della fonte originale e conservazione degli interventi. Nuova build e ripetizione sullo stesso caso ancora da eseguire; nessuna conferma positiva anticipata. Foto privata reader-real-restart-error-local-wip8.jpg.

Ripetizione sulla copia reale WIP9: tutti i tre container healthy. Riavviato il solo app e riaperta Anteprima dallo stesso DOCX controllato: errore italiano e comando Riprova caricamento con icona e nome accessibile visibili. Dopo pronto HTTP 200, clic reale Riprova: fonte originale riaperta con iuRevision=1, pagina offline assente, testo controllato visibile. Chiusa anteprima: editor conserva 33 parole/232 caratteri e Nessuna modifica pendente. Foto private reader-retry-icon-real-local-wip9.jpg e reader-real-restart-recovered-local-wip9.jpg. Prova del recupero, non attestazione universale di fedeltà DOCX.
Primo gate integrale terminato con quattro passi falliti: build Vite/file Windows in uso, raccolta/tool Timesheet assente, OCR/aspettative statiche obsolete, packaging/versione frontend arretrata e lista extra del test non aggiornata. Correzioni e ripetizioni mirate: 26 statici e 101 Storybook, 55 OCR, 19 packaging, raccolta e cinque Timesheet positivi. Le dipendenze PDF già governate non sono state rimosse o cambiate; riallineata versione frontend 2.437.13 e aspettativa del test. Secondo gate integrale ancora in corso; il primo exit 1 resta documentato.

Verifica aggiuntiva nel browser reale WIP9: ridimensionamento del bordo destro con tastiera, area iframe misurata 460 pixel. Fonte Word controllata e comandi visibili/raggiungibili, testo a capo senza perdita di contenuto; finestra poi chiusa senza modifica del documento. Foto privata reader-narrow-real-local-wip9.jpg. Riscontro della finestra ridimensionata, non prova su dispositivo mobile. Il comando Scarica del titolo passa su una seconda riga: dettaglio di compattazione del lettore da includere nel punto layout, senza nasconderlo o estendere il riscontro a tutti i layout.
12/10/2026 — Recupero puntuale del presidio backup CTU in produzione: riferimenti aggiornati per i due studi soltanto dopo snapshot nativi coerenti dei rispettivi StudioDB, quick_check ok, impronte registrate e verifica SQL successiva in sola lettura. Revisione 1 con un audit __backup_recovery; audit __adoption di revisione 0 conservato, zero incarichi/comandi/rifiuti invariati. Snapshot dichiarati successivi all’adozione, senza ricostruire falsamente i preventivi del 10/10; causa della precedente indisponibilità non dimostrata. Primo tentativo fermato prima di eseguire il recupero perché Compose cercava il tag predefinito e avviava una build: ripristinati i servizi, corretto il wrapper privato con immagine esatta e207cf7, pull never e ripresa senza build né dipendenze. Secondo tentativo exit 0; app/scheduler/OCR/Redis healthy, unico iusentra-app sul commit e207cf7, pronto pubblico 200 versione 2.437.12. Cleanup nativo exit 0, zero immagini rimosse e una conservata; cache incompleta eliminata senza dati/volumi. Browser reale produzione: riapertura fascicolo dall’Agenda, CTU e perizie caricato, Nuovo incarico apre tutti i campi e il calcolo assistito; scroll alto/basso e Annulla senza registrazione. Foto privata ctu-production-after-backup-recovery-fields-20261012.jpg. Prova del recupero del presidio e dell’apertura, non nuova attestazione integrale di ogni procedura CTU. Incarico generale aperto.
12/10/2026 — Candidato epigrafi/lettore 2.437.13: secondo ci_local_gate.sh integrale terminato exit 0, 40 passaggi positivi e zero fallimenti, inclusi dieci gruppi core, acquisizione/OCR, catalogo, shell React, sicurezza, RBAC, distribuzione, Local Signer e 48 prove Lex. Il primo giro exit 1 con quattro passi falliti resta documentato con correzioni e ripetizioni. Guardrail aggiuntivi dell’ultimo cambiamento del lettore: 26 statici/101 Storybook e nove JS positivi; recupero dopo interruzione provato nel browser reale 8080, fonte riaperta e documento controllato invariato (33 parole/232 caratteri). Sono riscontri tecnici e materiali del candidato; commit/push, allineamento dello SHA e rilascio di produzione ancora da eseguire. Nessuna attestazione di copertura globale, fedeltà universale o completamento dell’incarico generale.
