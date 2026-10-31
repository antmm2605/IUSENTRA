import { formatDateTimeIt } from './formatting'

/**
 * Dati tecnici (JSON registrati nei log, valori annidati) mostrati all'avvocato come testo leggibile:
 * «nome: valore», date e ore italiane, nessuna parentesi o virgoletta tecnica (verifica del 31/10/2026, V25).
 */
const DATA_ISO = /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/

function etichetta(chiave: string): string {
  const testo = chiave.replace(/[_-]+/g, ' ').trim()
  return testo ? testo.charAt(0).toUpperCase() + testo.slice(1) : ''
}

export function valoreLeggibile(valore: unknown, profondita = 0): string {
  if (valore === null || valore === undefined || valore === '') return '—'
  if (typeof valore === 'boolean') return valore ? 'sì' : 'no'
  if (typeof valore === 'number') return valore.toLocaleString('it-IT')
  if (typeof valore === 'string') {
    if (DATA_ISO.test(valore)) return valore.length <= 10 ? valore.split('-').reverse().join('/') : formatDateTimeIt(valore, valore)
    return valore
  }
  if (Array.isArray(valore)) return valore.slice(0, 5).map((v) => valoreLeggibile(v, profondita + 1)).join(', ') + (valore.length > 5 ? ', …' : '')
  if (typeof valore === 'object') {
    if (profondita >= 2) return '…'
    return Object.entries(valore as Record<string, unknown>)
      .slice(0, 6)
      .map(([chiave, v]) => `${etichetta(chiave)}: ${valoreLeggibile(v, profondita + 1)}`)
      .join(' · ')
  }
  return String(valore)
}

/** Un testo che contiene un JSON registrato diventa «nome: valore · …»; un testo normale resta com'è. */
export function testoLeggibile(testo: string): string {
  const pulito = String(testo || '').trim()
  if (!pulito.startsWith('{') && !pulito.startsWith('[')) return pulito
  try {
    return valoreLeggibile(JSON.parse(pulito))
  } catch {
    return pulito
  }
}
