# Release workspace IUSENTRA

Aggiornato: 2026-05-17.

Changesets è predisposto per governare versioni future dei package interni, ma
nessun pacchetto viene pubblicato automaticamente. Tutti i package introdotti in
questa fase restano `"private": true`.

## Comandi

```powershell
pnpm changeset
pnpm version-packages
pnpm release
```

`pnpm release` usa `changeset publish`, ma va eseguito solo dopo decisione
esplicita sul publishing e configurazione del registry. Fino ad allora serve
come comando governato, non come automatismo.

## Policy

- Accesso `restricted` per eventuali package pubblicabili in futuro.
- Versionamento dei package privati consentito, tagging disattivato.
- Base branch Changesets: `Codex/legal-electronic-filing-kIxcV`.
- Nessun dato studio, tenant, cliente, fascicolo o segreto può entrare nei
  package condivisi o negli artefatti di release.

## Prossimi passaggi

1. Migrare `frontend` verso `apps/studio` solo in una fase dedicata.
2. Estrarre componenti in `packages/ui` uno alla volta, con import aggiornati e
   build verificata.
3. Attivare Chromatic in CI configurando il segreto.
4. Aggiungere baseline visuali e controlli di accessibilità automatici.
