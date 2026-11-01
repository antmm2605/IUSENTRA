# 2.470.11 — Backup preventivo che finisce anche durante il recupero delle letture

- Il backup preventivo del deploy (`deploy/hetzner/backup_structured.py`) copiava ogni database SQLite a blocchi
  con una pausa: SQLite ricomincia la copia a ogni scrittura di un altro processo, e durante il recupero delle
  letture il backup superava i 290 secondi e fermava il deploy della 2.470.10 (01/11/2026). Ora la copia avviene
  in un solo passo, con il controllo d'integrità invariato. Test `tests/test_hetzner_backup_sotto_scrittura.py`:
  con il codice precedente il backup sotto scrittura continua non termina, con la correzione sì.
- Contiene la 2.470.9 e la 2.470.10, mai arrivate in produzione.
