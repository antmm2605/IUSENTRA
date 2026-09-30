/**
 * Memoria del calcolo del contributo unificato (D.P.R. 115/2002 art. 13) condivisa fra la scheda
 * del fascicolo, la finestra di calcolo e il pagamento PagoPA.
 */
import type { FascicoloFull } from '../../fascicoliData'

export type ContributoUnificatoResult = {
  categoria?: string
  categoria_label?: string
  grado?: string
  grado_label?: string
  valore_tipo?: string
  valore_tipo_label?: string
  valore?: number | string | null
  numero_parti_ricorrenti?: number
  base?: number | string | null
  anticipazione_forfettaria?: number | string | null
  totale?: number | string | null
  sezione_specializzata_impresa?: boolean
  dati_obbligatori_mancanti?: boolean
  regole_applicate?: Array<Record<string, unknown>>
  notes?: string[]
  warnings?: string[]
  sources?: Array<Record<string, unknown>>
}
export type ContributoUnificatoMemory = {
  fascicoloId: string
  title: string
  reference: string
  objectLabel: string
  clientName: string
  totalLabel: string
  totalValue: number | null
  createdAt: string
  copyText: string
  result: ContributoUnificatoResult
}

export const CONTRIBUTION_MEMORY_STORAGE_PREFIX = 'iusentra.fascicolo.contributoUnificato.'

export function contributionStorageKey(fascicoloId: string): string {
  return `${CONTRIBUTION_MEMORY_STORAGE_PREFIX}${fascicoloId || 'corrente'}`
}

export function readContributionMemory(fascicoloId: string): ContributoUnificatoMemory | null {
  if (typeof window === 'undefined' || !fascicoloId) return null
  try {
    const raw = window.sessionStorage.getItem(contributionStorageKey(fascicoloId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as ContributoUnificatoMemory
    return parsed && parsed.fascicoloId === fascicoloId && parsed.copyText ? parsed : null
  } catch {
    return null
  }
}

export function saveContributionMemory(memory: ContributoUnificatoMemory): void {
  if (typeof window === 'undefined' || !memory.fascicoloId) return
  try {
    window.sessionStorage.setItem(contributionStorageKey(memory.fascicoloId), JSON.stringify(memory))
  } catch {
    // La memoria PagoPA resta disponibile nello stato React anche se il browser blocca sessionStorage.
  }
}

export function cleanDisplayText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

export function contributoAmountNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const raw = String(value ?? '').trim()
  if (!raw) return null
  let normalized = raw.replace(/€/g, '').replace(/EUR/gi, '').replace(/\s+/g, '')
  if (normalized.includes(',')) normalized = normalized.replace(/\./g, '').replace(',', '.')
  normalized = normalized.replace(/[^0-9.-]/g, '')
  const parsed = Number.parseFloat(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

export function fascicoloOggettoRicorso(fascicolo: FascicoloFull): string {
  const snapshot = fascicolo.sourceSnapshot
  const candidates = [
    fascicolo.object,
    snapshot?.oggetto,
    fascicolo.subtitle,
    fascicolo.procedureType,
    fascicolo.title,
  ]
  return candidates.map(cleanDisplayText).find(Boolean) || ''
}

export async function copyTextForUser(value: string): Promise<void> {
  if (!value) return
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  if (typeof document === 'undefined') return
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', 'true')
  textarea.className = 'iu-fas-clipboard-buffer'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}
