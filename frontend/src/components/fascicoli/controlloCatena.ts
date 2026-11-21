// Controllo della catena del fascicolo: tipi del payload di /api/v1/ui/fascicoli/<id>/guardiano-catena
// e le frasi da mostrare. Il controllo gira in sfondo sul server (pct/catena): qui si legge solo il suo registro.
// Gli anelli visibili e il loro esito sono decisi dal server (pct/catena/esito.py): letture → termini → passi →
// economia → quadro.

export type AvvisoCatena = { codice: string; anello?: string; descrizione: string; perche: string; norma: string; dal: string }

export type EsitoAnello = 'verificato' | 'riparato' | 'da_verificare' | 'in_aggiornamento' | 'non_controllato'

export type AnelloCatena = {
  codice: string
  nome: string
  descrizione: string
  esito: EsitoAnello
  etichetta: string
  avvisi: number
  riparate: number
}

export type ControlloCatenaPayload = {
  ok?: boolean
  stato?: 'verificato' | 'in_aggiornamento' | 'mai_controllato' | 'non_disponibile'
  statoEtichetta?: string
  ultimoControllo?: { quando?: string } | null
  anelli?: AnelloCatena[]
  avvisi?: AvvisoCatena[]
}

// Gli anelli si mostrano sempre, anche quando il registro non risponde: l'avvocato deve sapere se la catena è stata
// controllata, non trovare un riquadro vuoto.
export const ANELLI_PREDEFINITI: ReadonlyArray<Pick<AnelloCatena, 'codice' | 'nome' | 'descrizione'>> = [
  { codice: 'letture', nome: 'Letture', descrizione: 'documenti e PEC letti, catalogo e fatti' },
  { codice: 'termini', nome: 'Termini e udienze', descrizione: 'scadenziario e agenda allineati ai termini certi e alle udienze' },
  { codice: 'passi', nome: 'Prossimi passi', descrizione: 'passi da fare, adempimenti già provati e bozze' },
  { codice: 'economia', nome: 'Economia', descrizione: 'conto economico, crediti e incassi' },
  { codice: 'quadro', nome: 'Quadro', descrizione: 'quadro e stato del fascicolo coerenti con la Lettura' },
]

export function avvisiDaMostrare(payload: ControlloCatenaPayload | null | undefined): AvvisoCatena[] {
  if (!payload?.ok || !Array.isArray(payload.avvisi)) return []
  return payload.avvisi.filter((avviso) => Boolean(avviso?.descrizione))
}

export function anelliDaMostrare(payload: ControlloCatenaPayload | null | undefined): AnelloCatena[] {
  const dalServer = payload?.ok && Array.isArray(payload.anelli) ? payload.anelli : []
  return ANELLI_PREDEFINITI.map((base) => {
    const anello = dalServer.find((voce) => voce?.codice === base.codice)
    if (anello) return { ...base, ...anello }
    return { ...base, esito: 'non_controllato', etichetta: 'non ancora controllato', avvisi: 0, riparate: 0 }
  })
}

export function primaLettera(testo: string): string {
  return testo ? testo.charAt(0).toUpperCase() + testo.slice(1) : testo
}

function dataOraItaliana(iso: string | undefined): string {
  if (!iso) return ''
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  const parti = new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).formatToParts(data)
  const valore = (tipo: string) => parti.find((parte) => parte.type === tipo)?.value || ''
  return `${valore('day')}/${valore('month')}/${valore('year')} ${valore('hour')}:${valore('minute')}`
}

// La frase di stato in testa al pannello.
export function statoDelControllo(payload: ControlloCatenaPayload | null | undefined): string {
  if (!payload) return 'Controllo della catena in caricamento.'
  if (!payload.ok) return 'Controllo della catena non disponibile in questo momento: riprova più tardi.'
  const quando = dataOraItaliana(payload.ultimoControllo?.quando)
  const ultimo = quando ? ` Ultimo controllo: ${quando}.` : ''
  if (payload.stato === 'in_aggiornamento') return `Controllo della catena in aggiornamento: i dati del fascicolo sono appena cambiati.${ultimo}`
  if (payload.stato === 'mai_controllato') return 'Il controllo della catena non è ancora stato eseguito su questo fascicolo: parte da solo dopo la prossima lettura.'
  if (payload.stato === 'non_disponibile') return 'Controllo della catena non disponibile per questo studio.'
  const avvisi = avvisiDaMostrare(payload).length
  if (avvisi) return `Catena controllata: ${avvisi === 1 ? '1 punto da verificare' : `${avvisi} punti da verificare`}.${ultimo}`
  return `Catena verificata: letture, termini, passi, economia e quadro coerenti fra loro.${ultimo}`
}
