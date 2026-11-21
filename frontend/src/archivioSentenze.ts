// Archivio sentenze per corte: richieste e intestazioni condivise fra le sezioni Cassazione e Corte costituzionale.
export type FiltriCassazione = { q: string; numero: string; anno: string; sezione: string; ramo: string }

export function sentenzeWebQuery(filtri: FiltriCassazione) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filtri)) if (value.trim()) params.set(key, value.trim())
  return params.toString()
}

export function statoArchivioCassazione(result: { caseCount?: number | null; status?: string }) {
  if (result.caseCount === null || result.caseCount === undefined) return 'Conteggio delle decisioni in aggiornamento: la ricerca è già disponibile.'
  const passata = result.status === 'complete' ? 'acquisizione completata' : 'acquisizione storica o giornaliera in corso'
  return `${result.caseCount.toLocaleString('it-IT')} decisioni nell’archivio · ${passata}`
}

export function consultaQuery(testo: string, anno: string) {
  const domanda = testo.trim()
  const conAnno = anno.trim() && /^\d{1,6}$/.test(domanda) ? `${domanda}/${anno.trim()}` : [domanda, anno.trim()].filter(Boolean).join(' ')
  return new URLSearchParams({ fonte: 'corte_costituzionale', q: conAnno }).toString()
}

export function estremiConsulta(record: { kind?: string; number?: string; year?: number | string; title?: string }) {
  const tipo = (record.kind || '').trim().toLowerCase()
  if (record.number && record.year) return `Corte costituzionale, ${tipo && tipo !== 'provvedimento' ? `${tipo} ` : ''}n. ${record.number}/${record.year}`
  return record.title || 'Pronuncia della Corte costituzionale'
}

