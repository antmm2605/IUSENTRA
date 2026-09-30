# Controllo Studio: scadute e ricerca — 30/09/2026

Versione 2.434.2. Pagina React `/workspace-intelligente`.

## Comportamento

«Tutte le scadute» seleziona Scadenze e periodo Scaduto, cancella la ricerca precedente e apre l’elenco in un solo clic. Non completa, cancella o marca letti gli adempimenti. La ricerca immediata combina le parole su titolo, dettaglio, fascicolo/ruolo, data italiana e ora; ignora maiuscole e accenti. Filtri area e periodo restano combinabili. Conteggio completo, cancellazione ricerca, azzeramento filtri e stato senza risultati esplicito.

Ogni fascia mostra 50 voci per pagina: tutte le voci ricevute restano ricercabili, comprese quelle oltre la prima pagina. Il cambio pagina riporta all’inizio dell’elenco; date complete con anno tramite `formatDateIt`, fuso Europe/Rome. Nessuna nuova dipendenza, tabella, migrazione o mutazione: API tenant-aware, RBAC, repository SQLite/PostgreSQL e audit esistenti invariati. Le azioni operative mantengono i collegamenti e le conferme già previsti. Nessuna modifica a deposito, firma o PEC congelati.

## Prova materiale sul server

Browser integrato reale autenticato su `https://app.iusentra.it/workspace-intelligente`, desktop, tablet 768×1024 e telefono 390×844. Visti 1.223 termini scaduti al momento della campagna (conteggio dinamico dello studio). Click su Tutte le scadute: solo termini, fascia aperta, ricerca azzerata. Ricerca combinata nome/ruolo: due termini; nome e data completa: un termine. Ricerca senza corrispondenze: messaggio esplicito. Periodo Oggi: 70 risultati. Azzera filtri ripristina la coda generale. Paginazione: risultati 51–100, pagina 2 di 25, ritorno all’inizio dei nuovi risultati. Apertura del termine reale nel relativo form React; nessun salvataggio o completamento effettuato.

Scroll fino al fondo, focus da tastiera, stato selezionato e passaggio del mouse sui controlli verificati. Etichette e date leggibili; azioni disposte su più righe su telefono senza overflow del contenuto. Il primo hotfix degli asset ha rilevato disallineamento con il servizio statico separato: corretto riallineando anche quel servizio prima della campagna. Backup asset originale sul server `/opt/iusentra/backups/controllo-scadute-20260930/assets-before.tar`; copia degli artefatti e log fuori dal repository sul PC. Dati e volumi non modificati.

## Guardrail e rilascio

Build/typecheck React e budget bundle superati; test frontend, contratti React, ordine hook, governance grafica e copertura pagine superati. Otto test mirati Controllo Studio/preparazione udienza superati. OpenAPI rigenerato per la versione e validato.

Prima delle modifiche letti baseline deposito e manifest del backup accettato. Il componente Controllo Studio non appartiene alla baseline; i quattro file condivisi di versione differivano già dal backup storico per i rilasci successivi. Questo intervento cambia soltanto la loro versione, preservando le dipendenze e i comandi di avvio.

## Prova materiale locale

Copia Docker reale aggiornata su `http://127.0.0.1:8080`, browser autenticato dello studio locale: 177 termini scaduti, dati distinti dalla produzione. Verificati filtro in un clic, ricerca sull’intero elenco, pagina 2, ricerca combinata ruolo/parole (cinque risultati) e data/parole (due risultati), focus da tastiera, stato senza corrispondenze, layout desktop/tablet/telefono e scroll completo. I nomi lunghi dei fascicoli ora vanno a capo senza troncamenti. Nessuna operazione di completamento o salvataggio.

Sul server verificato anche il ritorno alla pagina 1 premendo di nuovo Tutte le scadute. Ricerca materiale nome/ruolo: 137 ms fra inserimento e verifica dello stato aggiornato, inclusi i tempi del controllo browser. La pagina visualizza al massimo 50 righe per fascia invece di oltre 1.200 righe scadute simultanee; nessuna richiesta di rete per ogni ricerca. Screenshot e log conservati in `D:/legale/backups/IUSENTRA/controllo-scadute-20260930`.

Il rilascio richiede commit/push gemelli, tutti i gate del nuovo SHA e deploy Hetzner coerente. Le evidenze finali automatiche sono conservate nello stesso dossier esterno, senza incorporare risultati futuri nel commit verificato.
