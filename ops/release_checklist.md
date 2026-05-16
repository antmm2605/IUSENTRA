# Release checklist

## Prima del rilascio
- [ ] Governance check
- [ ] Packaging sync
- [ ] Python baseline
- [ ] Local Signer boundaries
- [ ] Lex quality gates
- [ ] Performance budget
- [ ] Pytest verde

## Smoke manuale
- [ ] login
- [ ] dashboard
- [ ] import/sync minimo
- [ ] Local Signer ping
- [ ] route healthcheck
- [ ] storage persistente

## Dopo il rilascio
- [ ] verifica log iniziali
- [ ] verifica healthcheck
- [ ] pulizia cache build Docker con `docker builder prune --all --force`
- [ ] rimozione eventuale `/opt/iusentra/tmp-backup-snapshot` residuo
- [ ] controllo che PEC/email multi-studio non abbiano ricreato `/data/email`
- [ ] controllo lettore allegati compresso attivo (`IUSENTRA_EMAIL_ATTACHMENT_STORAGE=archive`)
- [ ] controllo scheduler aggiornamenti legali con timeout per elemento (`IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS`)
- [ ] verifica errori critici
