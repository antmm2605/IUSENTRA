# @iusentra/ui

Libreria privata per componenti e token UI condivisi IUSENTRA.

Questa prima fondazione non sposta componenti dal frontend esistente: aggiunge
solo primitive minime per Storybook e per estrazioni future controllate.

## Comandi

```powershell
pnpm --filter @iusentra/ui typecheck
pnpm --filter @iusentra/ui build
```

## Regole

- Nessun dato studio, tenant, fascicolo, segreto o contenuto cliente.
- Nessuna chiamata API e nessun fallback silenzioso.
- Import nel frontend solo dopo build/typecheck e verifica visuale.
