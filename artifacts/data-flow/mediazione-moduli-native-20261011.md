# Mediazione: sito, modulo e copia compilabile — 11/10/2026

Risultato richiesto: consultare anonimamente il sito dell’organismo dentro IUSENTRA, acquisire la risorsa ufficiale registrata nel fascicolo, compilarne una copia con il lettore nativo e ritrovarla nel procedimento senza perdere l’originale.

La navigazione del sito resta nella stessa finestra, con ritorno alle pagine precedenti. Soltanto risorse presenti nel catalogo verificato dell’organismo possono essere acquisite. Il comando mantiene autorizzazioni, vincolo al fascicolo, impronta e provenienza, attesa ed errori espliciti. Nessun testo dello studio è inviato al sito. La condizione di procedibilità mostra anche la dicitura obbligatoria.

Per PDF senza campi AcroForm, il comando normale apre il lettore PDF nativo e la preparazione della copia. Il testo originale esterno resta protetto. Dopo il salvataggio confermato, il repository SQL collega la copia al modulo esatto, con CAS e audit, conservando decisioni manuali. Consegne ripetute non producono doppioni. Il segnale persistente condiviso aggiorna la mediazione aperta; bozze e salvataggi in corso sospendono l’applicazione del nuovo stato.

## Prova materiale, copia reale 8080

Studio tecnico separato, fascicolo controllato 7ADAFE03, organismo 429. Dal Sito dell’organismo: Modulistica, domanda PDF ufficiale, acquisizione confermata. Originale B1F1470B di quattro pagine, fonte 202603_modulo_domanda_mediazione.pdf. Compilazione normale tramite lettore: aggiunto Controllato Caso, posizionato sulla riga Il/La sottoscritto/a; salvataggio della copia 616439D7 confermato. Senza ricaricare, comparso Visualizza copia 1 nel procedimento. Riapertura da quel comando: nome nel campo corretto, tutte e quattro le pagine scorse fino al piè di pagina conclusivo. Nessuna firma, deposito o trasmissione eseguita.

Riscontro SQL e rendering PDFium nativo: impronta originale uguale alla fonte acquisita, copia collegata, quattro pagine; differenza nella sola area del nome della prima pagina (238,386–417,405 a 144 dpi). Pagine 2–4 identiche nei pixel. Prima copia diagnostica 95F9CC58 conservata nel fascicolo, senza dichiararla collegata dal codice successivo.

Foto e log privati nella cartella agenda-sql-live-20261010 del backup locale: mediazione-linked-copy-direct-reopen.png, mediazione-linked-copy-page4-bottom.png, mediazione-rendered-copy-native-proof.log.

## Guardrail e correzioni diagnostiche

313 verifiche JavaScript, typecheck/build, Ruff e 21 test mirati SQL/rendering/overlay positivi. PostgreSQL nativo verificato su sole tabelle temporanee della sessione: copia, audit, replay, rollback CAS e segnale live. Il primo tentativo PostgreSQL individuava un lookup non qualificato della funzione trigger nello schema temporaneo: qualificata nello schema corrente e ripetuto controllo sulla versione realmente installata.

La riacquisizione della stessa fonte preserva copie compilate e verifica manuale senza nuova revisione; guardrail HTTP mirato. Prova materiale successiva registrata nell’aggiornamento di rilascio.

Errori di strumenti corretti: percorsi relativi dalla directory frontend, script dei contratti nel percorso react-migration, nome di test inesistente. Non sono risultati applicativi positivi. Comando tastiera sul body dell’iframe scaduto; scorrimento eseguito dal controllo accessibile Pagine del documento. Diagnosi MuPDF del font sorgente non usata come accettazione: ripetuto confronto con PDFium nativo senza quell’errore.

## Stato di rilascio

Versione candidata 2.437.10 ricostruita senza cache e installata sull’app reale healthy. Controllo PostgreSQL ripetuto con modulo installato. Ancora da registrare commit/push, gate remoti, riallineamento locale al commit esatto e deploy Hetzner. Nessuna chiusura dell’incarico generale; Utility, Agenda e riconciliazione Anastasi restano punti distinti aperti. Nessuna modifica ai flussi congelati.
## Riscontro finale del candidato

Sul v5 reale 8080, riacquisito lo stesso modulo dal comando normale: originale e copia compilata conservati. Seconda finestra modifica le note del fascicolo mentre la mediazione contiene una bozza: bozza intatta, aggiornamento rinviato esplicitamente. Salvataggio normale successivo conferma la procedura e recupera la vista senza avviso residuo.

Chrome reale, viewport misurata 390×844: sito, Modulistica, ritorno e copia compilata riaperti; scroll nativo fino alla pagina 4 e ritorno alla pagina 1 con nome nel campo corretto. A 820×1080 osservata la finestra del sito e i suoi comandi. Override ripristinati. Il primo ridimensionamento del browser integrato non applicava la misura: escluso dalla prova responsive. Screenshot Chrome intermittenti scaduti durante rendering; DOM e nuovo riscontro visivo dopo azione reale, nessuna conferma dalle immagini bianche intermedie.

La prova ha individuato quattro etichette preload di immagini display:none del sito originale: corretta la rimozione delle sole immagini esplicitamente nascoste prima della trasformazione dei testi alternativi. Installazione puntuale sulla sola app reale con backup del sorgente, riapertura dello stesso sito conferma etichette visibili preservate e preload assenti; ulteriore guardrail HTTP positivo e Ruff positivo. Foto mediazione-website-mobile-final.png e mediazione-copy-mobile.png. Il comando di chiusura dell’anteprima ha un nome diverso da quello ipotizzato: riletto il DOM e usato quello effettivo, senza modifica del prodotto.

Il gate opzionale ui-support rifiuta questo diff perché è un rilascio di prodotto, fuori dal suo perimetro di supporto: non attenuato né dichiarato positivo. Gate di prodotto restano obbligatori. Frontend 313 test e build già positivi; inventario test rigenerato per il nuovo test del lettore pubblico.
