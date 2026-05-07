# Tranche 16A - Backup React operativo

Generato: 2026-05-07

## 1. Route convertita

- `/backup`

## 2. Stato prima

- Manifest: `react_bridge`
- Bridge: `writes=legacy_routes`
- UI: lettura React ma azioni principali tramite route/form legacy

## 3. Stato dopo

- Manifest: `react_operational_full`
- Bridge: `writes=json_api`, `operational=true`, `restore_migrated=false`
- UI: lettura e mutazioni crea/verifica tramite API JSON

## 4. LegacyPostForm rimossi

- `frontend/src/components/BackupPage.tsx` non importa e non usa piu' `LegacyPostForm`.
- `frontend/src/backupData.ts` non normalizza piu' form legacy.

## 5. Link legacy rimasti e perche

- `/backup?_legacy=1` resta solo nel pannello `Rollback tecnico`.
- `/backup/<id>/scarica` resta link backend sicuro per download, senza fetch blob React.
- `/backup/<id>/ripristina?_legacy=1` resta nel payload solo come riferimento tecnico legacy, non come CTA primaria della lista.

## 6. Endpoint JSON creati

- `GET /api/v1/ui/backup`
- `POST /api/v1/ui/backup/crea`
- `POST /api/v1/ui/backup/verifica`

## 7. Permessi controllati

- Lettura: `backup.leggi`
- Creazione backup: `backup.esegui`
- Verifica integrita: `backup.esegui`
- CSRF/sessione: endpoint POST registrati in `web/services/security_runtime.py`

## 8. Audit preservato

- Il legacy backup non registrava audit esplicito nel route handler.
- Le nuove API JSON registrano audit applicativo:
  - `backup.crea`
  - `backup.verifica`
- I dettagli audit non includono path file, hash o stack trace.

## 9. UI state implementati

- Loading lettura registro.
- Saving su crea/verifica.
- Success con messaggio backend.
- Error e validation errors.
- Permission denied con motivazione.
- Empty state lista backup.
- Filtri locali sui dati gia ricevuti.

## 10. Azioni backup convertite

- Crea backup: `createBackup()` -> `POST /api/v1/ui/backup/crea`
- Verifica integrita: `verifyBackupIntegrity()` -> `POST /api/v1/ui/backup/verifica`

## 11. Download backend sicuro

- Il download resta href backend `GET /backup/<id>/scarica`.
- React non usa `response.blob`, `new Blob` o `URL.createObjectURL`.

## 12. Restore lasciato legacy/protetto

- Nessun endpoint restore JSON creato.
- Nessuna funzione restore React implementata.
- `/backup/*` resta escluso dal gate React.

## 13. Delete non introdotto

- Nessun endpoint delete JSON creato.
- Nessuna funzione delete React implementata.

## 14. Test eseguiti

- `python -m py_compile web/services/react_backup_bridge.py web/blueprints/api_v1_react.py scripts/react-migration/check-tranche-16a-backup-api.py` - OK
- `node scripts/react-migration/check-tranche-16a-backup-operational.mjs` - OK
- `python scripts/react-migration/check-tranche-16a-backup-api.py` - OK
- `node scripts/react-migration/check-no-fake-react-full.mjs` - OK
- `cd frontend && node scripts/check-react-contracts.mjs` - OK
- `node scripts/react-migration/audit-anti-mascheramento.mjs` - OK
- `cd frontend && npm run test` - OK
- `cd frontend && npm run typecheck` - OK
- `cd frontend && npm run build` - OK

## 15. Rischi residui

- Restore e delete restano nel legacy e non sono coperti da React operativo in questa PR.
- La verifica integrita legacy non conserva uno storico dedicato; il payload React mostra lo stato derivato dal registro e dall'ultima mutazione JSON.

## 16. Rollback

- Aprire `/backup?_legacy=1` per usare la pagina Jinja legacy exact.
- Le sottoroute `/backup/*` restano legacy/protette dal gate.
