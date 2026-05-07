# Tranche 10A - Impeccable / Open Design

Data: 2026-05-07

## Principi usati

- Gerarchia visiva pulita per archivi, fonti, news e registro mediazione.
- Spacing coerente tramite variabili `--iu-*` e `--iu-od-*`.
- Densita professionale: KPI, fonti, metadati e liste leggibili senza decorazioni non operative.
- Focus visibile e stati hover/focus delegati a token interni.
- Distinzione esplicita tra fonte, metadato, inferenza backend, warning e azione legacy.

## File toccati

- `frontend/src/theme/impeccable-open-design.css`
- `frontend/src/ui/openDesign.ts`
- `frontend/src/components/GiurisprudenzaPage.tsx`
- `frontend/src/components/GiurisprudenzaPage.css`
- `frontend/src/components/LegalIntelligencePage.tsx`
- `frontend/src/components/LegalIntelligencePage.css`

## Token creati o aggiornati

- `--iu-od-source-gap`
- `--iu-od-source-card-radius`
- `--iu-od-source-meta-size`
- `--iu-od-source-focus-ring`
- `--iu-od-evidence-border`
- `--iu-od-evidence-surface`

## Utility create o aggiornate

- `.iu-od-source-card`
- `.iu-od-source-meta`
- `.iu-od-source-badge`
- `.iu-od-evidence-panel`
- `.iu-od-inference-warning`
- `.iu-od-legal-list`
- `.iu-od-action-row`

## Componenti interessati

- `GiurisprudenzaPage`: archivio metadati, fonti, filtri client-side, provvedimenti, warning e link legacy.
- `LegalIntelligencePage`: dashboard, news, mediazione e hub ricerca legale con record read-only.
- `openDesignLegalKnowledgeSurface`: contratto interno di classi riusabili, senza dipendenze esterne.

## Distinzione fonte/inferenza

- Le fonti usano badge `iu-od-source-badge` e card `iu-od-source-card`.
- I metadati sono in `dl` semantici e non contengono corpo documento.
- Le inferenze sono mostrate solo se gia esposte dal backend e rese distinguibili con righe evidenza.
- I warning usano `iu-od-inference-warning` e segnalano cosa resta legacy.

## Esclusioni

- Nessuna libreria grafica.
- Nessun CDN.
- Nessun font esterno.
- Nessun nuovo design system.
- Nessuna chiamata live a fonti esterne.
- Nessun editor, chart, download o generazione contenuti.

## Verifica regressioni

- `node scripts/react-migration/check-ui-consistency.mjs`
- `node scripts/react-migration/check-tranche-10a-open-design.mjs`
- `frontend/scripts/check-react-contracts.mjs`
- `npm run typecheck`
- `npm run build`

## Motivo assenza librerie grafiche

Impeccable e Open Design sono trattati come principi interni: token CSS auditabili, classi `iu-*`, componenti gia presenti nel UI kit e nessun lock-in verso librerie proprietarie.
