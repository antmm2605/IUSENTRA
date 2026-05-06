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
