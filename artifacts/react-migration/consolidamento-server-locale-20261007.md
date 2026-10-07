# Riallineamento server e locale — 07/10/2026

Su richiesta corrente dell’utente, trasferimento della produzione IBH alla copia reale su 8080 senza ripetere la campagna visiva integrale. 562 file server, inclusi 268 asset correnti, confrontati con SHA-256; originali locali conservati fuori dal repository. Nessun volume o dato dello studio copiato dalla produzione. La prova di avvio/versione locale e i gate commit/push restano obbligatori.

La presa visione SQL è stata osservata sul server dopo riavvio: «Già letta», «Presa visione salvata», discordanza originale ancora consultabile. Le altre prove materiali sono registrate nel diario operativo conservato nel backup. Non si dichiara accettazione completa di tutto il prodotto.

Restano aperti: conversione Word con geometria identica, campagna completa di ogni card/strumento e dettagli residui indicati nel diario. Il candidato IBI per dimensioni pagina non è distribuito. Il deposito/firma/PEC del 09/09/2026 resta congelato.

## Verifica di avvio locale

07/10/2026 08:51, Europe/Rome: copia reale 8080 versione 2.436.10, app/scheduler/OCR healthy; browser reale aperto su Controllo Studio con card e filtri. Il catalogo delle comunicazioni richiede la migrazione già applicata in produzione.

La lettura diretta del database da Python Windows ha segnalato corruzione; il primo controllo nativo positivo riguardava erroneamente la cartella storica. Il confronto successivo sul percorso registrato tenant-8bf98719c459 conferma la corruzione; la cartella storica contiene 2.092 email ordinarie e rimane soltanto una fonte SQL da confrontare. Nessun database è stato sostituito: il candidato di recupero Windows resta escluso. Le operazioni SQL locali proseguono esclusivamente nel motore Linux del profilo reale.

Guardrail: build React/typecheck riusciti; npm test 185 test più contratti, hook, presìdi, design system e copertura UI riusciti; 86 test Node mirati delle finestre/fonti/OCR; 33 test mirati presa visione/scheduler. I primi tentativi hanno rilevato nomi TypeScript ambigui su Windows e contratti test non aggiornati; corretti senza alterare il flusso deposito/firma/PEC.

Il riallineamento dei sorgenti è separato dal difetto SQL preesistente nella copia locale. Nessuna sostituzione del database corrente autorizzata dal solo esito del candidato di recupero. Le tabelle native leggibili confrontate col candidato sono 123 e coincidono; la tabella dei moduli recuperata ha righe mancanti o danneggiate. La migrazione locale della posta resta aperta, senza importazione cieca del JSON storico.
