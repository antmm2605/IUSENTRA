# 2.470.18 — Lavori programmati in corsie, uno alla volta; recupero del piano una volta al giorno

Primo passo della catena dei lavori chiesta dall'avvocato il 02/11/2026 (lavori uno alla volta, controllati).

- Lo scheduler usava l'esecutore predefinito di APScheduler: dieci thread, fino a dieci lavori insieme sugli
  stessi archivi. Ne venivano «database is locked», «Fascicolo aggiornato da un altro processo» e la memoria
  esaurita. Ora i lavori stanno in corsie (`pct/scheduler_corsie.py`), ciascuna con un lavoro alla volta:
  - **rapida**: PEC, presidio delle notifiche, avvisi di agenda e scadenze, calendari, registri PST;
  - **lunga**: tutti gli altri (letture, presìdi, fonti legali, Lex, piano del giorno, verifiche), uno alla volta
    in tutto il processo;
  - **infrastruttura**: i giri tecnici di consegna degli eventi.
  Un lavoro che trova la corsia occupata aspetta in coda; le esecuzioni manuali dalla console seguono la corsia
  del lavoro.
- Il recupero del piano del giorno dopo un riavvio del worker si tenta al massimo una volta al giorno
  (`pct/scheduler_recupero_piano.py`): un riavvio per memoria esaurita non può più rilanciare la ricostruzione
  completa a ripetizione.
- Test in `tests/test_scheduler_corsie.py` con lo scheduler reale (due lavori pesanti mai sovrapposti, la corsia
  rapida non aspetta la lunga, un recupero al giorno).
