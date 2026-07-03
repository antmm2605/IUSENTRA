export function parseItalianAmount(value: string | number | null | undefined, fallback = 0): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : fallback
  let normalized = String(value ?? '')
    .trim()
    .replace(/€/g, '')
    .replace(/EUR/gi, '')
    .replace(/\s+/g, '')

  if (!normalized) return fallback

  if (normalized.includes(',')) {
    normalized = normalized.replace(/\./g, '').replace(',', '.')
  } else if (/^-?\d{1,3}(?:\.\d{3})+$/.test(normalized)) {
    normalized = normalized.replace(/\./g, '')
  }

  normalized = normalized.replace(/[^0-9.-]/g, '')
  const parsed = Number.parseFloat(normalized)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function formatDecimalIt(value: number, fractionDigits = 2): string {
  const safeValue = Number.isFinite(value) ? value : 0
  const sign = safeValue < 0 ? '-' : ''
  const [integerPart, decimalPart = ''] = Math.abs(safeValue).toFixed(fractionDigits).split('.')
  const groupedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return fractionDigits > 0 ? `${sign}${groupedInteger},${decimalPart}` : `${sign}${groupedInteger}`
}

export function formatEuroIt(value: string | number | null | undefined, fallback = '€ 0,00'): string {
  const parsed = parseItalianAmount(value, Number.NaN)
  if (!Number.isFinite(parsed)) return fallback
  return `€ ${formatDecimalIt(parsed, 2)}`
}

export function formatEuroInput(value: string | number | null | undefined): string {
  const raw = String(value ?? '').trim()
  return raw ? formatEuroIt(raw) : ''
}

export const ITALIAN_TIME_ZONE = 'Europe/Rome'

function parseDateValue(value: string | number | Date | null | undefined): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const raw = String(value ?? '').trim()
  if (!raw) return null
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T12:00:00` : raw
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatDateIt(value: string | number | Date | null | undefined, fallback = ''): string {
  const parsed = parseDateValue(value)
  if (!parsed) return fallback
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: ITALIAN_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(parsed)
}

export function formatTimeIt(value: string | number | Date | null | undefined, fallback = ''): string {
  const parsed = parseDateValue(value)
  if (!parsed) return fallback
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: ITALIAN_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

export function formatDateTimeIt(
  value: string | number | Date | null | undefined,
  fallback = '',
  options: { includeTimezone?: boolean } = {},
): string {
  const parsed = parseDateValue(value)
  if (!parsed) return fallback
  const label = new Intl.DateTimeFormat('it-IT', {
    timeZone: ITALIAN_TIME_ZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed).replace(/,\s*/, ' ')
  return options.includeTimezone ? `${label} (Europe/Rome)` : label
}
