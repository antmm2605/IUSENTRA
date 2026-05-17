# Storybook IUSENTRA

Aggiornato: 2026-05-17.

Storybook è configurato sul frontend attuale (`frontend/.storybook`) e legge
storie sia dall'app sia dal package UI:

```text
frontend/src/**/*.stories.@(ts|tsx|mdx)
packages/ui/src/**/*.stories.@(ts|tsx|mdx)
```

## Comandi

```powershell
pnpm storybook
pnpm build:storybook
```

`pnpm build:storybook` genera `frontend/storybook-static`.

## Scrivere una story

- Collocare la story accanto al componente: `Nome.stories.tsx`.
- Usare esempi neutri e professionali, senza dati studio o tenant.
- Coprire almeno stato normale, azione principale e variante secondaria quando
  il componente la prevede.
- Evitare testo tecnico visibile all'utente finale.

## Chromatic

Gli script sono predisposti senza token nel repository:

```powershell
pnpm build:storybook
pnpm chromatic
pnpm chromatic:changed
```

Il token va fornito solo tramite variabile d'ambiente:

```text
CHROMATIC_PROJECT_TOKEN=
```

In GitHub Actions Chromatic viene eseguito solo quando il segreto
`CHROMATIC_PROJECT_TOKEN` è presente; in caso contrario il job resta non
bloccante.
