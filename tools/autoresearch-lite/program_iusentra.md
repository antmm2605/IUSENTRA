# Programma autoresearch-lite per IUSENTRA

Questo file guida Codex in esperimenti controllati su IUSENTRA.

## Regole non negoziabili

- Non creare branch nuovi.
- Non eseguire loop infiniti.
- Non lavorare durante la notte in autonomia.
- Non fare reset distruttivi.
- Non eseguire push automatici fuori dal task corrente.
- Non installare dipendenze ML/GPU.
- Non installare `karpathy/autoresearch`.
- Non installare Open Design dentro IUSENTRA.
- Non modificare file fuori scope.
- Non modificare dipendenze runtime.
- Non indebolire `AGENTS.md`.
- Non indebolire CI, coverage, security workflow o quality gates.

## Flusso esperimento

1. Definire obiettivo.
2. Definire baseline.
3. Definire file modificabili.
4. Definire file vietati.
5. Definire comandi di verifica.
6. Applicare una modifica piccola.
7. Eseguire verifiche.
8. Classificare risultato:
   - `keep`
   - `discard`
   - `crash`
   - `scope-violation`
   - `needs-review`
9. Scrivere report finale.
10. Non continuare con un secondo esperimento senza nuovo task esplicito.

## Metriche consigliate

### Per task documentali

- chiarezza maggiore;
- nessuna regola rimossa;
- nessuna contraddizione;
- nessun file runtime modificato.

### Per task test

- test aggiunti o migliorati;
- test pertinenti eseguiti;
- nessuna soglia abbassata;
- nessun test rimosso o skippato senza sostituzione equivalente.

### Per task codice

- patch piccola;
- area coerente;
- storage rispettato;
- permessi/audit/tenant considerati;
- UI italiana se visibile;
- test pertinenti;
- nessuna regressione su workflow collegati.

### Per task UI/UX

- rispetto di `tools/open-design-support/IUSENTRA_DESIGN.md`;
- rispetto di `tools/open-design-support/IUSENTRA_UI_RULES.md`;
- prototipo o descrizione grafica prima dell'integrazione;
- responsive desktop/tablet/mobile;
- stati vuoti, errore, loading e conferma;
- microcopy italiano;
- nessun effetto grafico gratuito o incoerente con uno studio legale;
- nessuna regressione di navigazione.

## Criterio keep/discard

Tenere solo modifiche che migliorano il risultato senza aumentare il rischio.

Scartare modifiche che:
- toccano aree vietate;
- aggiungono complessita' non necessaria;
- non passano i controlli;
- cambiano comportamento non richiesto;
- peggiorano leggibilita' o manutenibilita';
- creano incoerenza tra JSON, SQLite e PostgreSQL;
- indeboliscono controlli esistenti;
- peggiorano coerenza grafica o accessibilita'.
