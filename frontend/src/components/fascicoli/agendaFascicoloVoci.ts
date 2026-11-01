/** Linea del tempo dell'agenda del fascicolo: prossimi dal più vicino, poi passati dal più recente (giorno di Roma). */
import type { FascicoloAppointment, FascicoloDeadline } from '../../fascicoliData'
import type { Tone } from '../../data'

export type Voce = {
  id: string
  titolo: string
  quando: string
  giorno: string
  etichetta: string
  tono: Tone
  href: string
  passata: boolean
  perentorio: boolean
  genere: 'scadenza' | 'appuntamento'
}

function giornoIso(data: string, iso = ''): string {
  if (/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso.slice(0, 10)
  const parti = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(data.trim())
  return parti ? `${parti[3]}-${parti[2]}-${parti[1]}` : ''
}

export function oggiRoma(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
}

export function vociAgendaFascicolo(scadenze: FascicoloDeadline[], appuntamenti: FascicoloAppointment[], oggi = oggiRoma()): Voce[] {
  const voci: Voce[] = [
    ...scadenze.map((s): Voce => {
      const giorno = giornoIso(s.date, s.dateIso)
      return {
        id: `s-${s.id}`, titolo: s.title, quando: s.date, giorno, etichetta: s.priority || s.type || 'termine',
        tono: s.tone, href: s.href, passata: Boolean(giorno) && giorno < oggi, perentorio: s.peremptory, genere: 'scadenza',
      }
    }),
    ...appuntamenti.map((a): Voce => {
      const giorno = giornoIso(a.date)
      return {
        id: `a-${a.id}`, titolo: a.title, quando: [a.date, a.time, a.place].filter(Boolean).join(' '), giorno,
        etichetta: a.type || 'agenda', tono: a.tone, href: a.href, passata: a.past || (Boolean(giorno) && giorno < oggi),
        perentorio: false, genere: 'appuntamento',
      }
    }),
  ]
  const prossime = voci.filter((v) => !v.passata).sort((x, y) => (x.giorno || '9999').localeCompare(y.giorno || '9999'))
  const passate = voci.filter((v) => v.passata).sort((x, y) => y.giorno.localeCompare(x.giorno))
  return [...prossime, ...passate]
}


/** I primi impegni non passati per l'agenda compatta in testa al fascicolo. */
export function prossimiImpegni(voci: Voce[], quanti = 5): { voci: Voce[]; altri: number } {
  const prossime = voci.filter((v) => !v.passata)
  return { voci: prossime.slice(0, quanti), altri: Math.max(0, prossime.length - quanti) }
}
