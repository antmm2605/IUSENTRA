# Tranche 9A - Impeccable / Open Design

## Principi usati

- Gerarchia compatta per superfici documentali: intestazione chiara, KPI essenziali, catalogo scansionabile e warning separati dalle azioni.
- Spacing coerente basato sui token `--iu-*` gia' presenti.
- Classi auditabili con prefisso `iu-`, senza Bootstrap nei nuovi TSX.
- Focus ring accessibile, hover leggibile e stati vuoti professionali.
- Nessun elemento decorativo non funzionale e nessun dato demo.

## File toccati

- `frontend/src/theme/impeccable-open-design.css`
- `frontend/src/ui/openDesign.ts`
- `frontend/src/components/TemplateAttiPage.tsx`
- `frontend/src/components/TemplateAttiPage.css`
- `frontend/src/components/RedazioneAttiPage.tsx`
- `frontend/src/components/RedazioneAttiPage.css`

## Token creati

- `--iu-od-doc-gap`
- `--iu-od-doc-card-radius`
- `--iu-od-doc-section-gap`
- `--iu-od-doc-meta-size`
- `--iu-od-doc-focus-ring`

## Utility create

- `.iu-od-card`
- `.iu-od-meta`
- `.iu-od-warning`
- `.iu-od-action-row`

Le utility riusano le superfici gia' introdotte in 8A: `.iu-od-surface`, `.iu-od-grid`, `.iu-od-stack` e `.iu-od-focus-ring`.

## Componenti interessati

- `TemplateAttiPage` usa i token documentali per dashboard e catalogo template.
- `RedazioneAttiPage` usa gli stessi pattern per workflow, azioni legacy e fonti collegate come metadati.

## Cosa resta escluso

- Editor template.
- Editor documento.
- Redazione guidata completa.
- Produzione PDF/DOCX/export.
- Legal intelligence, giurisprudenza e checklist deposito.

## Verifica regressioni

- `node scripts/react-migration/check-ui-consistency.mjs`
- `node scripts/react-migration/check-tranche-9a-open-design.mjs`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Nessuna libreria grafica

Impeccable e Open Design restano un contratto interno: token CSS, classi `iu-*`, componenti riusabili e report auditabile. Non sono state aggiunte dipendenze, CDN, font esterni o framework di design.
