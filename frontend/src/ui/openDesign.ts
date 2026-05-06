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
