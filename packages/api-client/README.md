# @iusentra/api-client

SDK TypeScript privato per chiamate API interne IUSENTRA.

In questa fase espone solo un helper JSON tipizzato e fail-closed:

- accetta esclusivamente percorsi relativi interni;
- non contiene endpoint applicativi hardcoded;
- non legge dati tenant o dati studio;
- non introduce fallback silenziosi.

## Comandi

```powershell
pnpm --filter @iusentra/api-client typecheck
pnpm --filter @iusentra/api-client build
```
