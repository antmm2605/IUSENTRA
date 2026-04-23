# Dependency locking strategy

IUSENTRA usa una strategia in due fasi:

1. file sorgente leggibili e manutenibili (`requirements/*.txt`);
2. vincoli globali condivisi (`requirements/constraints.txt`).

## Obiettivo

Garantire installazioni più riproducibili senza bloccare troppo presto tutte le dipendenze.

## Regola pratica

- per sviluppo ordinario: aggiornare i file sorgente;
- per stabilizzazione release: verificare compatibilità con `constraints.txt`;
- per ambienti critici: introdurre progressivamente lock più stretti dopo validazione completa.

## Evoluzione consigliata

Quando la pipeline sarà stabile, introdurre:

- `pip-compile`; oppure
- lockfile separati per runtime e dev.
