# Monorepo IUSENTRA

Aggiornato: 2026-05-17.

IUSENTRA usa una fondazione monorepo pnpm workspace + Turborepo senza spostare
il frontend Vite/React esistente. La web app reale resta in `frontend`; `apps/*`
è predisposto per una futura migrazione controllata verso `apps/studio`;
`packages/*` ospita librerie private e configurazioni condivise.

## Struttura workspace

```text
frontend/              app React/Vite esistente
packages/config/       configurazioni TypeScript condivise
packages/ui/           primitive UI private e token IUSENTRA
packages/api-client/   predisposizione SDK TypeScript interno
apps/*                 spazio riservato a migrazioni future
```

## Comandi principali

```powershell
corepack enable
corepack prepare pnpm@11.1.2 --activate
pnpm install
pnpm dev
pnpm test
pnpm typecheck
pnpm build
pnpm build:storybook
```

`npm run test`, `npm run typecheck` e `npm run build` restano disponibili dal
root, ma invocano gli script pnpm dichiarati nel workspace. CI e Docker devono
quindi abilitare Corepack prima dell'installazione.

## Prova Railway prima di Hetzner

Per questa fase Railway può essere usato come ambiente di prova della foundation
monorepo, senza promuovere subito il branch su Hetzner:

1. Il servizio Railway continua a usare `railway.toml` con builder Dockerfile.
2. Il Dockerfile abilita pnpm nello stage `frontend-builder` e compila
   `@iusentra/studio` con `pnpm --filter @iusentra/studio build:vite`.
3. La prova è accettabile solo se `/api/pronto` risponde correttamente e il
   bundle React viene servito da `web/static/react`.
4. Hetzner resta l'ambiente di produzione reale: si passa a Hetzner solo dopo CI
   verde, prova Railway riuscita e merge controllato.

## Aggiungere un package

1. Creare `packages/<nome>/package.json` con `"private": true`.
2. Dichiarare script `typecheck`, `build` e `clean` solo se reali.
3. Evitare dipendenze da `frontend`, route Flask, storage runtime o dati tenant.
4. Collegare il package a un'app solo dopo `pnpm typecheck` e `pnpm build`.

## Regole dati

- Nessun dato studio, tenant, cliente, fascicolo, PEC, token o segreto nei package
  pubblici o potenzialmente pubblicabili.
- JSON ammesso solo per bootstrap, export o fallback dichiarato; mai fallback
  silenzioso da database o storage tenant-aware.
- I package condivisi devono essere fail-closed: se manca configurazione, devono
  segnalare errore esplicito.
