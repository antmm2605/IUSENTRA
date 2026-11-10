import { romeInstant } from './agendaTime'

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

/**
 * Legge una data ricevuta dal backend o già scritta in italiano.
 * - gg/mm/aaaa [hh:mm] (anche con - o .) è sempre giorno/mese, mai la lettura americana;
 * - le date-ora senza fuso sono ore civili di Roma, qualunque sia il fuso del browser;
 * - il solo giorno si fissa a mezzogiorno di Roma, così nessun fuso lo sposta.
 */
function parseDateValue(value: string | number | Date | null | undefined): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }
  const raw = String(value ?? '').trim()
  if (!raw) return null
  const italiana = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[ ,T]+(?:ore\s+)?(\d{1,2})[:.](\d{2})(?::(\d{2}))?)?$/i.exec(raw)
  if (italiana) {
    const [, giorno, mese, anno, ore, minuti, secondi] = italiana
    const iso = `${anno}-${mese.padStart(2, '0')}-${giorno.padStart(2, '0')}`
    if (!isCalendarDate(iso)) return null
    return romeInstant(ore === undefined ? `${iso}T12:00:00` : `${iso}T${ore.padStart(2, '0')}:${minuti}:${secondi || '00'}`)
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return isCalendarDate(raw) ? romeInstant(`${raw}T12:00:00`) : null
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$/.test(raw)) {
    const civile = romeInstant(raw)
    if (civile) return civile
  }
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function isCalendarDate(iso: string): boolean {
  const [anno, mese, giorno] = iso.split('-').map(Number)
  const data = new Date(Date.UTC(anno, mese - 1, giorno))
  return data.getUTCFullYear() === anno && data.getUTCMonth() === mese - 1 && data.getUTCDate() === giorno
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

/** Valore macchina per input date, riferito al giorno civile italiano. */
export function formatDateInputIt(value: string | number | Date | null | undefined): string {
  const label = formatDateIt(value)
  if (!label) return ''
  const [day, month, year] = label.split('/')
  return `${year}-${month}-${day}`
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

const ISO_GIORNO = /^\d{4}-\d{2}-\d{2}$/
const ISO_DATA_ORA = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/

/**
 * Etichetta italiana per una data ricevuta così com'è dal backend:
 * ISO giorno → gg/mm/aaaa, ISO con ora → gg/mm/aaaa hh:mm (Europe/Rome);
 * un testo già italiano o non riconosciuto resta com'è (mai rilettura all'americana).
 */
export function formatDateLabelIt(value: string | null | undefined, fallback = ''): string {
  const raw = String(value ?? '').trim()
  if (!raw) return fallback
  if (ISO_GIORNO.test(raw)) return formatDateIt(raw, raw)
  if (ISO_DATA_ORA.test(raw)) {
    const soloMezzanotte = /[T ]00:00(?::00(?:\.0+)?)?$/.test(raw)
    return soloMezzanotte ? formatDateIt(raw.slice(0, 10), raw) : formatDateTimeIt(raw, raw)
  }
  return raw
}
