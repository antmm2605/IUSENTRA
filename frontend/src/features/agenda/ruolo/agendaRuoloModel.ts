import type { AgendaDay, AgendaEvent } from '../../../agendaData'

/** Il genere che dà il colore della banda: come l'avvocato distingue gli impegni a colpo d'occhio. */
export type GenereImpegno = 'udienza' | 'termine' | 'cancelleria' | 'notifica' | 'studio'

export const ETICHETTE_GENERE: Record<GenereImpegno, string> = {
  udienza: 'Udienza',
  termine: 'Termine',
  cancelleria: 'Comunicazione di cancelleria',
  notifica: 'Notifica',
  studio: 'Appuntamento di studio',
}

export type FiltroRapido = 'tutti' | 'lavoro' | GenereImpegno

const testo = (event: AgendaEvent) => `${event.legalLabel} ${event.title} ${event.originTitle}`.toLocaleLowerCase('it-IT')

export function genereImpegno(event: AgendaEvent): GenereImpegno {
  const t = testo(event)
  if (/comunicazione di cancelleria|pec ricevuta/.test(t) && event.kind !== 'udienza') return 'cancelleria'
  // Notifica dello studio (L. 53/1994), relata, copia informatica dal PST: non la parola «notificato» in un deposito.
  if (/notifica (?:legale|in proprio)|notificazione ai sensi|l\. ?53|relata|copia informatica|ricevuta di consegna/.test(t)) return 'notifica'
  if (/cancelleria/.test(t) && event.kind !== 'udienza') return 'cancelleria'
  if (event.kind === 'udienza') return 'udienza'
  if (event.kind === 'scadenza' || event.kind === 'deposito') return 'termine'
  return 'studio'
}

export function daLavorare(event: AgendaEvent): boolean {
  return event.pendingCount > 0 && !event.completed
}

export function corrispondeFiltro(event: AgendaEvent, filtro: FiltroRapido): boolean {
  if (filtro === 'tutti') return true
  if (filtro === 'lavoro') return daLavorare(event)
  return genereImpegno(event) === filtro
}

export function titoloImpegno(event: AgendaEvent, { conTipo = false } = {}): string {
  const origine = event.originTitle.trim()
  const titolo = origine && origine.toLocaleLowerCase('it-IT') !== 'appuntamento' ? origine : event.legalLabel || event.title || 'Impegno'
  if (conTipo) return titolo
  // In elenco il tipo lo dicono la banda e la scritta «PEC»: resta il contenuto della comunicazione.
  const senzaPrefisso = titolo.replace(/^Comunicazione di cancelleria:\s*/i, '')
  return senzaPrefisso.charAt(0).toLocaleUpperCase('it-IT') + senzaPrefisso.slice(1)
}

/** «Rossi Maria», «Fascicolo 2026/327 · RG 901/2026 · Tribunale di Vicenza»: il cliente in evidenza, poi il resto. */
export function contestoImpegno(event: AgendaEvent): { cliente: string; resto: string } {
  const parti = (event.contextLine || [event.client, event.matter, event.court].filter(Boolean).join(' · '))
    .split(' · ').map((parte) => parte.trim()).filter(Boolean)
  const cliente = event.client && parti[0] === event.client ? parti.shift() || '' : ''
  return { cliente, resto: parti.join(' · ') }
}

export function senzaOra(event: AgendaEvent): boolean {
  return !/^\d{1,2}:\d{2}$/.test(event.timeLabel.trim())
}

export function ordina(eventi: AgendaEvent[]): AgendaEvent[] {
  return [...eventi].sort((a, b) => {
    if (senzaOra(a) !== senzaOra(b)) return senzaOra(a) ? -1 : 1
    return new Date(a.start).getTime() - new Date(b.start).getTime()
  })
}

export function giornoEsteso(iso: string): string {
  const giorno = new Date(`${iso.slice(0, 10)}T12:00:00`)
  const testoGiorno = giorno.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' })
  return testoGiorno.charAt(0).toLocaleUpperCase('it-IT') + testoGiorno.slice(1)
}

export function quantiImpegni(n: number): string {
  if (!n) return 'nessun impegno'
  return n === 1 ? '1 impegno' : `${n} impegni`
}

export function giorniConImpegni(days: AgendaDay[]): AgendaDay[] {
  return days.filter((day) => day.events.length)
}
