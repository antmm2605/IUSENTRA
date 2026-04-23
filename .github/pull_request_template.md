## Obiettivo

Descrivi in una frase cosa chiude questa PR.

## Tipo modifica

- [ ] feature
- [ ] bugfix
- [ ] refactor
- [ ] hardening
- [ ] documentazione
- [ ] CI/CD

## Checklist

- [ ] dominio aggiornato
- [ ] route / API aggiornate se necessario
- [ ] storage aggiornato se necessario
- [ ] UI aggiornata se necessario
- [ ] permessi verificati
- [ ] test aggiunti o scenario riproducibile documentato
- [ ] documentazione aggiornata
- [ ] nessun segreto introdotto
- [ ] packaging coerente

## Rischi

Indica eventuali rischi, migrazioni o impatti operativi.

## Verifiche eseguite

```bash
python tools/check_repo_governance.py
python tools/sync_packaging_files.py --check
python tools/check_python_baseline.py
python -m pytest -q
```
