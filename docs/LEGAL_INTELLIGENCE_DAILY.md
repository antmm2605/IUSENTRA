# Legal Intelligence giornaliera

Il motore giornaliero controlla fonti ufficiali abilitate, salva snapshot con hash SHA-256, confronta le variazioni con l'ultimo contenuto noto e registra gli aggiornamenti in revisione o applicati in modo tecnico sicuro.

## Comando

Da root progetto:

```powershell
python -m legal_intelligence.jobs.daily_sync
```

Opzioni utili:

```powershell
python -m legal_intelligence.jobs.daily_sync --list
python -m legal_intelligence.jobs.daily_sync --source normattiva_opendata --json
python -m legal_intelligence.jobs.daily_sync --db data/legal_intelligence/daily.sqlite
```

## Railway Cron

Creare un servizio Railway separato di tipo Cron con comando:

```bash
python -m legal_intelligence.jobs.daily_sync
```

Schedule consigliata:

```text
15 3 * * *
```

Railway interpreta la schedule in UTC. Il job deve terminare al completamento: non e' un processo web persistente.

## Variabile ambiente opzionale

```text
LEGAL_INTELLIGENCE_DAILY_DB=/data/legal_intelligence/daily.sqlite
```

Se non configurata, il motore usa `data/legal_intelligence/daily.sqlite`.

## Regole di sicurezza

- Le fonti ufficiali con `apply_mode=manual` generano aggiornamenti in `pending_review`.
- Le fonti tecniche con `apply_mode=auto` possono essere marcate come applicate solo quando l'analisi le classifica come aggiornamenti operativi sicuri.
- Nessuna fonte non ufficiale aggiorna regole operative automaticamente.
- Le modifiche normative o interpretative restano sempre in revisione manuale.
- Ogni run conserva log, conteggi, fonti controllate, errori e stato applicazione.

## UI

La pagina `/legal-intelligence/` mostra:

- ultimo controllo reale;
- fonti controllate;
- variazioni rilevate;
- aggiornamenti applicati;
- aggiornamenti in revisione;
- errori;
- azioni per eseguire il controllo, vedere il diff, approvare e rigenerare l'indice AI.
