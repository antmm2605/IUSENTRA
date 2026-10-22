# Conservazione anagrafica e Timesheet — candidata2.447.4

Stato: preparata e verificata tecnicamente; non ancora accettata su8080 né in produzione.

## Risultato richiesto

Una modifica ordinaria di nota, recapito o minuti deve conservare gli attributi
storici SQL non modificati. Un comando anagrafico respinto non può ricomparire
quando lo stesso gestore salva un'altra scheda. Restano validi confronto della
revisione, collegamenti cliente/fascicolo e segnale SQL del proprietario.

## Sottografo verificato

EXTRACTED: GestioneClienti._salva (pct/clienti.py:358) confronta lo snapshot SQL
prima dell'upsert della sola riga. Il nuovo payload confermato (365) applica il
delta del modello alla fonte originale; dopo il commit diventa il nuovo snapshot.
Il ramo d'errore ripristina la cache del gestore prima di propagare il conflitto.

EXTRACTED: GestioneTimesheet._salva richiama timesheet_sql_writer.save_changes;
row_values (pct/timesheet_sql_writer.py:21) applica il delta ai metadati originali.
Le colonne canoniche, il confronto di tutte le colonne e i vincoli sui collegamenti
rimangono del writer nativo. Il comando composto conserva la transazione esterna.

EXTRACTED: json_snapshot_delta.merge_delta (riga10) è la medesima funzione già
usata da Fascicoli, estratta senza cambiare la logica. fascicoli_sql_writer importa
l'alias precedente: collezioni e metadati mantengono il comportamento verificato.
Nessuna fusione fra revisioni concorrenti né identificazione per somiglianza.

Il grafo Graphify ufficiale esterno è stato aggiornato sul perimetro WIP selezionato;
il grafo indica relazioni statiche, non è una prova di esecuzione. Nessun dato,
documento dello studio, chiave o contenuto PEC è stato inviato a Graphify.

## Prove eseguite e limiti

Tre guardrail nuovi falliscono sul codice pubblicato476f7f prima della correzione:
perdita metadati recapiti; cache del comando rifiutato che impedisce il salvataggio
successivo; perdita estensioni Timesheet. Dopo la correzione94casi SQLite del
perimetro esportato passano. Su PostgreSQL16 reale temporaneo40casi passano e un
caso specifico SQLite è saltato; container tmpfs rimosso, nessun volume creato.
Ruff positivo. I log sono conservati nella cartella tecnica esterna pdfcraft.

Il perimetro comprende i metadati accettati dai modelli e già presenti negli
snapshot SQL, conservati durante le modifiche provate; non dichiara importazione
di schemi sconosciuti o sincronizzazione globale di tutti gli archivi.

Nella candidata non sono inclusi gli adapter offline, il trasporto o la nuova
superficie impostazioni ancora WIP. La replica resta disabilitata. Nessuna modifica
a firma, classificazione, busta, SMTP/PEC o requisiti di deposito.

Prima della chiusura restano: prova reale sul dato controllato tramite interfaccia
8080, salvataggio e riapertura, confronto SQL, commit/push, tutti i gate sullo stesso
SHA, deploy, verifica produzione e pulizia governata. Non è un esito finale offline.

## Accettazione locale candidata — 22/10/2026

Copia reale8080 aggiornata alla candidata2.447.4: app, OCR e scheduler healthy,
/api/pronto positivo. Browser reale visibile, comandi del modulo anagrafica e
Timesheet, salvataggio e riapertura effettivi.

Sul cliente fittizio C6A3CB60 (Collaudo Editor Alfa) una nota confermata conserva
il metadato tecnico annidato nei recapiti. Nota ripristinata attraverso il modulo;
metadato di prova rimosso e campi controllati ripristinati mediante confronto CAS,
senza sovrascrivere la data di modifica. Il modulo preesistente richiede sesso e,
completando il dato fittizio, calcola CF e CAP: effetti osservati e ripristinati,
non introdotti dal writer di questa patch. Nessuna persona reale modificata.

Nel fascicolo controllato C729BD2B creata dal modulo una voce di cinque minuti,
non fatturabile e valore zero. Inserita un'estensione tecnica controllata nel
payload SQL: passaggio Validata e successiva Annullata mediante i pulsanti normali
la conservano entrambi. Dopo riapertura la voce risulta Annullata e Interna;
SQL conferma ANNULLATO, cinque minuti, non fatturabile e metadato conservato.
La voce tecnica resta annullata con tracciabilità, senza cancellazioni fisiche.

Prove esterne: client-24474-controlled-original.json, client-24474-after-ui.json,
timesheet-24474-controlled-original.json, timesheet-24474-ui-result.json e
screenshot timesheet-24474-riaperto.png nella cartella tecnica pdfcraft.
Restano necessari gate remoti, deploy, confronto dello stesso SHA e accettazione
in produzione. La sincronizzazione offline rimane incompleta e disabilitata.
