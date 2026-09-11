/**
 * Distanza del termine rispetto alla data del piano (calendario Europe/Rome).
 *
 * Il conteggio è solo informativo per l'avvocato: non ricalcola termini
 * processuali (proroga festivi/sabato ex art. 155 c.p.c. resta al motore
 * dello scadenziario) e segnala le date lette che risultano incoerenti.
 */

export type StatoTermine = {
  giorni: number
  label: string
  tono: 'danger' | 'warning' | 'neutral'
  anomalo: boolean
}

const GIORNO_MS = 86_400_000
/** Oltre un anno prima della data del piano la data letta va verificata. */
const SOGLIA_ANOMALIA_GIORNI = -365

function giornoUtc(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || '').trim())
  if (!match) return null
  const [, anno, mese, giorno] = match
  const ms = Date.UTC(Number(anno), Number(mese) - 1, Number(giorno))
  return Number.isNaN(ms) ? null : ms
}

export function oggiRoma(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Rome',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function statoTermine(scadenza: string, dataPiano: string): StatoTermine | null {
  const termine = giornoUtc(scadenza)
  const riferimento = giornoUtc(dataPiano || oggiRoma())
  if (termine === null || riferimento === null) return null
  const giorni = Math.round((termine - riferimento) / GIORNO_MS)
  let label: string
  if (giorni < -1) label = `Scaduto da ${Math.abs(giorni)} giorni`
  else if (giorni === -1) label = 'Scaduto ieri'
  else if (giorni === 0) label = 'Scade oggi'
  else if (giorni === 1) label = 'Scade domani'
  else label = `Mancano ${giorni} giorni`
  const anomalo = giorni < SOGLIA_ANOMALIA_GIORNI
  return {
    giorni,
    label: anomalo ? 'Data da verificare' : label,
    tono: anomalo ? 'warning' : giorni <= 0 ? 'danger' : giorni <= 3 ? 'warning' : 'neutral',
    anomalo,
  }
}

export const avvisoTermineAnomalo =
  'La data letta è anteriore di oltre un anno al giorno del piano: controllala sul documento prima di registrare o depositare.'
