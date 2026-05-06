import type { WizardDraftRow, WizardPractice } from './preventivoWizardData'

export type WizardValidationInput = {
  customerId: string
  quickClientEnabled: boolean
  quickClientName: string
  quickClientSurname: string
  quickClientCompany: string
  object: string
  issuedAt: string
  dueAt: string
  practiceId: string
  rows: WizardDraftRow[]
  clauseEnabled: boolean
  clauseText: string
}

export type WizardValidationErrors = Record<string, string>

export function formatEuro(value: number | null | undefined, fallback = '€ 0,00'): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  const amount = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)
  return `€ ${amount}`
}

export function parseEuroInput(value: string): number {
  const normalized = String(value || '').trim().replace(/\./g, '').replace(',', '.')
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

export function dateToItalian(value: string): string {
  if (!value) return ''
  const [year, month, day] = value.slice(0, 10).split('-')
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

export function normalizeAmountInput(value: string): string {
  return String(value || '').replace(/[^\d,.-]/g, '')
}

export function mergeCalculatedRowsWithManualRows(calculated: WizardDraftRow[], current: WizardDraftRow[]): WizardDraftRow[] {
  const manualRows = current.filter((row) => row.source === 'manuale')
  return [...calculated.filter((row) => row.source !== 'manuale'), ...manualRows]
}

export function isCompensoUnicoProfile(practice: WizardPractice | null): boolean {
  if (!practice) return false
  return practice.regole_tariffarie.some((rule) => {
    const profile = rule.profile
    if (!profile || typeof profile !== 'object' || Array.isArray(profile)) return false
    const calcMode = String((profile as Record<string, unknown>).calc_mode || '')
    const phaseKeys = Array.isArray((profile as Record<string, unknown>).phase_keys)
      ? (profile as Record<string, unknown>).phase_keys as unknown[]
      : []
    return calcMode === 'compenso_unico' || phaseKeys.includes('compenso_unico')
  })
}

export function phaseKeyLabel(key: string): string {
  return {
    studio: 'Studio',
    introduttiva: 'Introduttiva',
    istruttoria: 'Istruttoria / istruzione',
    decisionale: 'Decisionale',
    esecutiva: 'Esecutiva',
    attivazione: 'Attivazione',
    rivitalizzazione: 'Rivitalizzazione',
    negoziazione: 'Negoziazione',
    conciliazione: 'Conciliazione',
    compenso_unico: 'Compenso unico',
  }[key] || key
}

export function validateWizardForm(input: WizardValidationInput): WizardValidationErrors {
  const errors: WizardValidationErrors = {}
  const hasQuickClient = input.quickClientEnabled && (
    input.quickClientCompany.trim() || input.quickClientName.trim() || input.quickClientSurname.trim()
  )
  if (!input.customerId && !hasQuickClient) {
    errors.customer = 'Seleziona un cliente oppure compila l’inserimento rapido.'
  }
  if (!input.object.trim()) {
    errors.object = 'Inserisci l’oggetto del preventivo.'
  }
  if (!input.issuedAt) {
    errors.issuedAt = 'Inserisci una data emissione valida.'
  }
  if (!input.dueAt) {
    errors.dueAt = 'Inserisci una scadenza valida.'
  }
  if (input.issuedAt && input.dueAt && input.dueAt < input.issuedAt) {
    errors.dueAt = 'La scadenza non può precedere la data emissione.'
  }
  if (!input.practiceId) {
    errors.practice = 'Seleziona una tipologia pratica.'
  }
  if (!input.rows.length) {
    errors.rows = 'Calcola la bozza o aggiungi almeno una voce.'
  }
  input.rows.forEach((row, index) => {
    if (!row.descrizione.trim()) {
      errors[`row-${row.id}-descrizione`] = `La voce ${index + 1} richiede una descrizione.`
    }
    if (!Number.isFinite(row.importo) || row.importo < 0) {
      errors[`row-${row.id}-importo`] = `La voce ${index + 1} richiede un importo valido.`
    }
  })
  if (input.clauseEnabled && !input.clauseText.trim()) {
    errors.clauseText = 'Inserisci il testo della clausola o disattivala.'
  }
  return errors
}
