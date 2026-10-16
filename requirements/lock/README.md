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

## Runtime Docker Linux x64 / CPython 3.12

`runtime-linux-py312.txt` conserva le 119 dipendenze effettivamente verificate
della release accettata 2.437.50. Il package applicativo segue invece la versione
di `pct/__init__.py`. La build controlla anche assenze, package inattesi e versioni
discordanti mediante `tools/check_runtime_lock.py`, prima di creare la release.
Gli aggiornamenti delle librerie richiedono modifica esplicita del profilo e
collaudo: una nuova build non deve introdurli automaticamente.

Questo profilo non modifica i vincoli CI/dev di `requirements/constraints.txt`.
La produzione accettata contiene già versioni oltre alcuni suoi limiti storici
(cryptography, reportlab, stripe, redis e Flask-Limiter): non si effettua qui
un downgrade o un riallineamento silenzioso dei due ambienti. La loro convergenza
resta una verifica distinta. `runtime-pdf.txt` resta come riferimento storico;
le sue versioni accettate sono comprese nel nuovo profilo completo.
