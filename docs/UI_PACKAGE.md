# Package UI IUSENTRA

Aggiornato: 2026-05-17.

`packages/ui` è una libreria privata per primitive React e token condivisi.
Questa fase non estrae componenti complessi dal frontend: aggiunge solo `Button`,
`Card`, token e storie Storybook minime per costruire una baseline sicura.

## Comandi

```powershell
pnpm --filter @iusentra/ui typecheck
pnpm --filter @iusentra/ui build
```

## Regole di utilizzo

- Importare da `@iusentra/ui` solo dopo verifica di build e Storybook.
- Mantenere testi di esempio in italiano e senza dati personali.
- Non importare storage, API Flask, sessione, permessi o runtime tenant.
- Non duplicare componenti già presenti in `frontend/src/ui/*`: le estrazioni
  future devono essere progressive, piccole e accompagnate da test.

## Token

I token sono esportati da `@iusentra/ui/tokens` e rispecchiano la palette
IUSENTRA documentata in `docs/UI_DESIGN_SYSTEM.md`: blu istituzionale, accento
legale sobrio, superfici neutre, stati leggibili e radius operativo da 8 px.
