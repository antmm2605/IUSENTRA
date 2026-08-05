# Separazione notifica e deposito - 05/08/2026

## Perimetro

Questa nota riguarda solo la creazione della relata, l'attestazione di conformità e l'invio PEC della notifica L. 53/1994 dal PC locale dell'avvocato.

Il deposito telematico è un flusso distinto: non viene usato per decidere se la notifica può essere inviata e non riceve controlli sugli allegati della PEC di notifica.

## Regola applicata agli allegati della notifica

Gli allegati selezionati o inseriti dall'avvocato nella notifica non sono sottoposti a blocco per confronto di impronta con dati precedenti del form.

Durante la preparazione della PEC locale il software:

- legge il file reale salvato nel fascicolo;
- allega quel contenuto alla PEC locale;
- calcola l'impronta SHA-256 del contenuto effettivamente allegato;
- non blocca l'invio per una vecchia impronta diversa presente nel payload.

Il vecchio blocco sull'impronta diversa degli allegati è stato rimosso dal perimetro notifiche.

## Stato test

Guardrail mirato: la preparazione PEC locale viene provata con impronte stale volutamente diverse dal contenuto reale, e deve comunque produrre gli allegati effettivi del fascicolo.
