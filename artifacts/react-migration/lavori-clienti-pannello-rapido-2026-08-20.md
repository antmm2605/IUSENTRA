# Lavori pannello rapido clienti - 20/08/2026

## Perimetro richiesto

- Pagina `/clienti`: aggiungere pannello rapido al click destro sul cliente.
- Nel pannello mostrare la cartella/fascicoli del cliente; se i fascicoli sono più di uno, permettere di scegliere quale aprire.
- Aggiungere nel pannello anche `Portale clienti`.
- Riutilizzare le procedure già presenti nel software, senza creare flussi paralleli.

## Lavori da eseguire

- [x] Collegare il click destro sulle righe cliente desktop.
- [x] Collegare il click destro sulle card cliente mobile.
- [x] Recuperare i fascicoli dalla API reale della cartella cliente.
- [x] Mostrare nel pannello la scelta dei fascicoli collegati.
- [x] Aggiungere azioni rapide: scheda cliente, modifica, cartella, portale clienti, nuovo fascicolo, preventivo, messaggio, scadenza, fattura e copia contatti.
- [x] Aggiungere stili responsive con pannello non tagliato dai bordi.
- [x] Aggiornare il test di contratto React della pagina clienti.
- [ ] Eseguire typecheck/test mirati.
- [ ] Verificare visivamente su `http://127.0.0.1:8080/clienti`.

## Stato verifica

- Prova reale browser: da eseguire.
- Test automatici: da eseguire.
