# Tranche 8A - Impeccable / Open Design

## Principi usati

- Gerarchia visiva pulita per superfici economiche ad alta responsabilita.
- Token CSS auditabili, prefisso `iu-`, nessun CDN e nessuna dipendenza UI nuova.
- Componenti riusabili esistenti: Page, Button, ButtonLink, Badge, Panel, EmptyState, LoadingState, LegacyPostForm.
- Stati focus visibili e hover misurati, senza effetti decorativi gratuiti.
- Densita professionale: KPI, contratti, warning, sezioni e record leggibili anche su viewport stretti.

## File toccati

- `frontend/src/theme/impeccable-open-design.css`
- `frontend/src/ui/openDesign.ts`
- `frontend/src/components/CompensiForensiPage.tsx`
- `frontend/src/components/CompensiForensiPage.css`
- `frontend/src/components/TariffarioPage.tsx`
- `frontend/src/components/TariffarioPage.css`

## Token creati

- `--iu-od-space-*`
- `--iu-od-radius-*`
- `--iu-od-shadow-*`
- `--iu-od-border`
- `--iu-od-surface`
- `--iu-od-surface-soft`
- `--iu-od-text`
- `--iu-od-muted`
- `--iu-od-focus`
- `--iu-od-transition`

## Componenti interessati

- Dashboard compensi forensi.
- Consultazione tariffario.
- Form di submit HTML verso route Flask legacy.
- Stati vuoti, loading, warning e contratto discreto di provenienza dati.

## Cosa resta escluso

- Nessuna formula economica in React.
- Nessuna generazione documentale in React.
- Nessun pacchetto Impeccable o Open Design.
- Nessuna libreria grafica o design system esterno.

## Verifica regressioni

- `node scripts/react-migration/check-ui-consistency.mjs`
- `node scripts/react-migration/check-tranche-8a-open-design.mjs`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`
