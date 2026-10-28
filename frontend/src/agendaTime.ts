/** Ore civili dello studio risolte con il database IANA del browser. */
const civil = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
})
const clock = new Intl.DateTimeFormat('it-IT', {
  timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

const zonedClock = new Intl.DateTimeFormat('it-IT', {
  timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit', timeZoneName: 'short', hourCycle: 'h23',
})
const offsetLabel = new Intl.DateTimeFormat('en', { timeZone: 'Europe/Rome', timeZoneName: 'shortOffset' })

function localParts(epoch: number): number[] {
  const parts = civil.formatToParts(new Date(epoch))
  return ['year', 'month', 'day', 'hour', 'minute', 'second'].map(
    key => Number(parts.find(part => part.type === key)?.value),
  )
}

export function romeInstant(value: string): Date | null {
  const raw = value.trim()
  if (!raw) return null
  if (/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw)) {
    const parsed = new Date(raw)
    return Number.isFinite(parsed.getTime()) ? parsed : null
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?$/.exec(raw)
  if (!match) return null
  const wanted = match.slice(1, 7).map(part => Number(part || 0))
  const [year, month, day, hour, minute, second] = wanted
  const nominal = Date.UTC(year, month - 1, day, hour, minute, second) + Number((match[7] || '').padEnd(3, '0').slice(0, 3))
  const offsets = new Set<number>()
  for (const hours of [-36, 0, 36]) {
    const epoch = nominal + hours * 3600000
    const [y, m, d, h, min, sec] = localParts(epoch)
    offsets.add(Date.UTC(y, m - 1, d, h, min, sec) - Math.floor(epoch / 1000) * 1000)
  }
  const candidates = [...offsets].map(offset => nominal - offset).filter(
    epoch => localParts(epoch).every((part, index) => part === wanted[index]),
  )
  // Nessun candidato nell'ora inesistente; prima occorrenza nell'ora ripetuta,
  // coerente con i dati locali legacy del repository. Gli offset espliciti restano distinti.
  return candidates.length ? new Date(Math.min(...candidates)) : null
}

export function romeDateKey(value: Date): string {
  const [year, month, day] = localParts(value.getTime())
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function romeTime(value: Date): string {
  return clock.format(value)
}

export function romeTimeRange(date: string, time: string, duration: number): string {
  const start = romeInstant(`${date}T${time}`)
  if (!start || !Number.isFinite(duration) || duration <= 0) return 'Orario non valido nel fuso italiano'
  const end = new Date(start.getTime() + duration * 60000)
  const offset = (value: Date) => offsetLabel.formatToParts(value).find(part => part.type === 'timeZoneName')?.value
  const formatter = offset(start) === offset(end) ? clock : zonedClock
  return `${formatter.format(start)} - ${formatter.format(end)}`
}
