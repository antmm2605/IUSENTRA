# Verifica reale archivio, lettore e presidi — 16/09/2026

Stato: lavoro aperto. Implementazione sul server reale in corso; nessuna chiusura, nessun commit o riallineamento locale ancora effettuato. Registro del perimetro composto richiesto dall’utente.

## Perimetro e stato

- Posta: paginazione a blocchi di 80, comandi sopra e sotto implementati sul server. Vista PEC 81–160 verificata con click reale; campagna completa ancora da eseguire.
- Lettore: selezione, copia e evidenziazione temporanea del testo PDF implementate. Copia di TRIBUNALE e incolla nel campo del software verificati nel Chrome reale. OCR senza testo selezionabile e formati non PDF ancora da verificare.
- Finestra lettore e dettaglio notifica: distanziati dalla topbar, portali React, nome cliente e chiusura visibili nella prova Mandaglio; campagna responsive/focus completa ancora da eseguire.
- Giacobbe 06928604: sentenza di un’altra causa non determina più la fase; fase Trattazione vista realmente. Date dei contratti scolastici e data di emissione erroneamente considerate termini: riconvalida più rigorosa implementata; rettifica delle consegne automatiche e prova completa ancora aperte.
- Cronologia: eliminazione delle duplicazioni tra viste e distinzione tra eventi futuri, prove senza invio e operazioni compiute in corso. L’allegato dell’utente evidenzia anche udienze di precedenti giurisprudenziali, ricevute lette come nuovi termini e date di caricamento spacciate per provvedimenti.
- Notifiche legali: dettaglio Mandaglio e PDF reale in ZIP aperti; correlazione specifica delle prove e catena con nuovo archivio ancora da correggere/verificare.
- Archivio unico: individuate riletture da vecchi indici e testi nel presidio documentale, scadenze, economico e contesto Lex. Rimozione governata in corso; nessun archivio documentale cancellato.
- Fonti: richieste art. 127-ter c.p.c., tutte le norme mancanti citate nei fascicoli e Specifiche tecniche DGSIA. Acquisizione e lettore interno ancora aperti. Fonte DGSIA ufficiale identificata: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429 (provvedimento 2024 e rettifiche).

## Provenienza e protezioni

Produzione: /opt/iusentra/repo, container unico iusentra-app. Sorgenti precedenti in /opt/iusentra/giacobbe-before-20260916, /opt/iusentra/reader-before-20260916 e /opt/iusentra/mail-pagination-before-20260916. Backup SQLite registro prima delle rettifiche in /opt/iusentra/giacobbe-before-20260916/registro.db. Dati reali restano sul server. Nessun invio PEC o modifica al comportamento deposito/firma congelato. Il registro delle letture usa SQLite dedicato; i dati core restano nel proprio backend SQL.

## Chiusura ancora necessaria

Completare implementazione complessiva sul server, campagna unica con click reali e scroll completo, riallineare una volta la copia reale locale 8080, verificare SQL SQLite/PostgreSQL e guardrail mirati, aggiornare documentazione/versione, commit e push dei due branch gemelli, CI richieste, deploy Hetzner sul medesimo SHA, contenitore unico healthy e pulizia Docker senza volumi/dati.


## Verifica materiale successiva, 16/09/2026
Browser Chrome reale autenticato, server app.iusentra.it, fascicolo 06928604. Aperti i 18 pannelli principali, schede fasi e norme, presidio economico, documenti, attività, comunicazioni, audit e gestione. Il controllo non è ancora una campagna di accettazione superata.

Prove materiali: aperto Contratto 2026-27 nel lettore, selezionato un brano con il mouse, Copia restituisce «contratto individuale di lavoro» negli appunti; evidenziatore visibile. Aperta la carta d’identità di Fabiana Giacobbe, osservati fronte e retro; filtro dedicato cliccato e carta visibile. La copia su portale aveva un’identificazione SQL differente: corretto il collegamento del testo per impronta del contenuto. Cartella cliente implementata con riferimenti agli originali e nessuna copia fisica, ancora da provare materialmente.

Rettifiche SQL reversibili con prova: annullate due opposizioni ricavate da ricevute di deposito e un doppione del termine per note; conservati documenti e motivi. Snapshot SQLite 13.682.606.080 byte, quick_check già superato, copiato fuori container in /opt/iusentra/backups/archivio-rettifiche-20260916. Le rettifiche restano distinte dalle decisioni dell’avvocato.

Problemi ancora nel perimetro: catalogazione contratto/decreto, procure/PEC, verbali/note; attività processuali derivate da sentenze di altri procedimenti; contatori letto/non leggibile incoerenti; contratto inviato non raccordato all’accettazione; messaggi qualità giallo presentati come autenticità; udienze senza data da ricevute; anagrafica con date ISO e Avvocatura rappresentante mostrata come controparte; firma non verificata presentata come da firmare; audit ordinamento e pulsante riscontro; prove notifica risolte solo con ancora di sezione; simulazione genera accettazione esposta nel presidio; lettore scansioni senza selezione OCR; salto verticale della notifica di evidenziazione. Verificare scroll integrale, hover/focus e responsive dopo tutte le correzioni.

Norme: registrati art. 127-ter c.p.c. (testo Normattiva nelle note del correttivo), art. 309 c.p.c. (PDF MEF), Specifiche DGSIA integrali e rettifiche ufficiali del 16/09/2024 e 30/10/2024. Lettore interno autenticato con controllo impronta, ancora da provare materialmente.

Lavoro aperto. Locale 8080, GitHub e deploy finale non ancora riallineati: si eseguono una volta sola dopo la campagna completa sul server.
