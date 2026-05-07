export const openDesignContract = {
  system: 'Impeccable / Open Design',
  classPrefix: 'iu-',
  forbids: [
    'nuove dipendenze UI',
    'CDN',
    'classi Bootstrap nei nuovi componenti',
    'stili inline per layout',
    'colori hardcoded nei TSX',
    'griglie generiche di card ripetitive',
    'effetti decorativi non funzionali',
  ],
} as const

export const openDesignDocumentSurface = {
  surface: 'iu-od-surface',
  grid: 'iu-od-grid',
  card: 'iu-od-card',
  meta: 'iu-od-meta',
  warning: 'iu-od-warning',
  actionRow: 'iu-od-action-row',
  focusRing: 'iu-od-focus-ring',
} as const

export const openDesignLegalKnowledgeSurface = {
  sourceCard: 'iu-od-source-card',
  sourceMeta: 'iu-od-source-meta',
  sourceBadge: 'iu-od-source-badge',
  evidencePanel: 'iu-od-evidence-panel',
  inferenceWarning: 'iu-od-inference-warning',
  legalList: 'iu-od-legal-list',
  actionRow: 'iu-od-action-row',
  focusRing: 'iu-od-focus-ring',
} as const
