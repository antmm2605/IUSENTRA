/**
 * Conversioni del campo data italiano (CampoData).
 *
 * L'avvocato vede e scrive sempre gg/mm/aaaa (con l'ora gg/mm/aaaa hh:mm);
 * il codice chiamante e i payload ricevono il valore tecnico che dava l'input
 * nativo del browser: YYYY-MM-DD oppure YYYY-MM-DDTHH:MM.
 */

export type StatoTestoData = 'vuoto' | 'incompleto' | 'non_valido' | 'valido'

export type LetturaData = {
  stato: StatoTestoData
  /** Valore tecnico (ISO) quando la data è valida, altrimenti stringa vuota. */
  iso: string
}

export const MESI_IT = [
  'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
  'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre',
] as const

/** Settimana italiana: da lunedì a domenica. */
export const GIORNI_BREVI_IT = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'] as const
export const GIORNI_IT = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'] as const

const due = (numero: number) => String(numero).padStart(2, '0')

export function giorniNelMese(anno: number, mese: number): number {
  if (mese === 2) return (anno % 4 === 0 && anno % 100 !== 0) || anno % 400 === 0 ? 29 : 28
  return [4, 6, 9, 11].includes(mese) ? 30 : 31
}

export function dataDiCalendario(anno: number, mese: number, giorno: number): boolean {
  return Number.isInteger(anno) && anno >= 1000 && anno <= 9999
    && Number.isInteger(mese) && mese >= 1 && mese <= 12
    && Number.isInteger(giorno) && giorno >= 1 && giorno <= giorniNelMese(anno, mese)
}

function oraValida(ore: number, minuti: number): boolean {
  return Number.isInteger(ore) && ore >= 0 && ore <= 23 && Number.isInteger(minuti) && minuti >= 0 && minuti <= 59
}

function isoGiorno(anno: number, mese: number, giorno: number): string {
  return `${anno}-${due(mese)}-${due(giorno)}`
}

/** Scompone un valore tecnico (YYYY-MM-DD, con eventuale THH:MM[:SS]) già valido. */
function leggiIso(valore: string): { anno: number; mese: number; giorno: number; ore?: number; minuti?: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/.exec(valore.trim())
  if (!match) return null
  const [anno, mese, giorno] = [Number(match[1]), Number(match[2]), Number(match[3])]
  if (!dataDiCalendario(anno, mese, giorno)) return null
  if (match[4] === undefined) return { anno, mese, giorno }
  const [ore, minuti] = [Number(match[4]), Number(match[5])]
  if (!oraValida(ore, minuti)) return null
  return { anno, mese, giorno, ore, minuti }
}

/**
 * Legge quello che l'avvocato ha scritto o incollato.
 * Accetta gg/mm/aaaa, gg-mm-aaaa, gg.mm.aaaa, ggmmaaaa e, se incollato,
 * anche il formato tecnico aaaa-mm-gg (non ambiguo). Mai mm/gg/aaaa.
 */
export function leggiTestoData(testo: string, conOra = false): LetturaData {
  const pulito = testo.trim().replace(/\s+/g, ' ')
  if (!pulito) return { stato: 'vuoto', iso: '' }

  const tecnico = leggiIso(pulito)
  if (tecnico) {
    if (!conOra) return { stato: 'valido', iso: isoGiorno(tecnico.anno, tecnico.mese, tecnico.giorno) }
    if (tecnico.ore === undefined) return { stato: 'incompleto', iso: '' }
    return { stato: 'valido', iso: `${isoGiorno(tecnico.anno, tecnico.mese, tecnico.giorno)}T${due(tecnico.ore)}:${due(tecnico.minuti ?? 0)}` }
  }

  const [parteData, ...resto] = pulito.replace(/,/g, ' ').replace(/\s+ore\s+/i, ' ').replace(/\s+/g, ' ').split(' ')
  const parteOra = resto.join('').trim()

  let giorno: number
  let mese: number
  let anno: number
  const compatta = /^(\d{2})(\d{2})(\d{4})$/.exec(parteData)
  const separata = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/.exec(parteData)
  if (compatta) {
    [giorno, mese, anno] = [Number(compatta[1]), Number(compatta[2]), Number(compatta[3])]
  } else if (separata) {
    [giorno, mese, anno] = [Number(separata[1]), Number(separata[2]), Number(separata[3])]
  } else {
    // Ancora in scrittura: cifre e separatori ammessi, ma la data non è completa.
    return /^[\d/.-]*$/.test(parteData) && parteData.length < 10 && !parteOra
      ? { stato: 'incompleto', iso: '' }
      : { stato: 'non_valido', iso: '' }
  }
  if (!dataDiCalendario(anno, mese, giorno)) return { stato: 'non_valido', iso: '' }
  const giornoIso = isoGiorno(anno, mese, giorno)

  if (!conOra) return parteOra ? { stato: 'non_valido', iso: '' } : { stato: 'valido', iso: giornoIso }
  if (!parteOra) return { stato: 'incompleto', iso: '' }
  const ora = /^(\d{1,2})[:.](\d{2})$/.exec(parteOra) || /^(\d{2})(\d{2})$/.exec(parteOra)
  if (!ora) return /^\d{1,2}[:.]?\d?$/.test(parteOra) ? { stato: 'incompleto', iso: '' } : { stato: 'non_valido', iso: '' }
  const [ore, minuti] = [Number(ora[1]), Number(ora[2])]
  if (!oraValida(ore, minuti)) return { stato: 'non_valido', iso: '' }
  return { stato: 'valido', iso: `${giornoIso}T${due(ore)}:${due(minuti)}` }
}

/**
 * Testo da mostrare per un valore ricevuto dal codice chiamante.
 * Un valore tecnico diventa gg/mm/aaaa [hh:mm]; un valore già italiano si normalizza;
 * qualunque altra cosa resta com'è (l'avvocato la vede e la corregge).
 */
export function testoDaValore(valore: string | null | undefined, conOra = false): string {
  const grezzo = String(valore ?? '').trim()
  if (!grezzo) return ''
  const tecnico = leggiIso(grezzo)
  if (tecnico) {
    const data = `${due(tecnico.giorno)}/${due(tecnico.mese)}/${tecnico.anno}`
    if (!conOra) return data
    return tecnico.ore === undefined ? data : `${data} ${due(tecnico.ore)}:${due(tecnico.minuti ?? 0)}`
  }
  const letto = leggiTestoData(grezzo, conOra)
  return letto.stato === 'valido' ? testoDaValore(letto.iso, conOra) : grezzo
}

/** Valore tecnico per un valore ricevuto (ISO o italiano); '' se non è una data valida. */
export function isoDaValore(valore: string | null | undefined, conOra = false): string {
  return leggiTestoData(String(valore ?? ''), conOra).iso
}

/** Parte giorno (YYYY-MM-DD) di un valore tecnico. */
export function giornoDiIso(iso: string): string {
  return iso.slice(0, 10)
}

export function oraDiIso(iso: string): string {
  return iso.length >= 16 ? iso.slice(11, 16) : ''
}

/** Data in lettere per lo schermo e i lettori di schermo: «lunedì 27 luglio 2026». */
export function dataInLettere(isoGiornoValore: string): string {
  const parti = leggiIso(isoGiornoValore)
  if (!parti) return ''
  return `${GIORNI_IT[giornoSettimana(parti.anno, parti.mese, parti.giorno)]} ${parti.giorno} ${MESI_IT[parti.mese - 1]} ${parti.anno}`
}

/** 0 = lunedì … 6 = domenica (calcolo sul calendario, senza fuso orario). */
export function giornoSettimana(anno: number, mese: number, giorno: number): number {
  const domenicaZero = new Date(Date.UTC(anno, mese - 1, giorno)).getUTCDay()
  return (domenicaZero + 6) % 7
}

export function spostaGiorni(isoGiornoValore: string, giorni: number): string {
  const parti = leggiIso(isoGiornoValore)
  if (!parti) return isoGiornoValore
  const data = new Date(Date.UTC(parti.anno, parti.mese - 1, parti.giorno + giorni))
  return isoGiorno(data.getUTCFullYear(), data.getUTCMonth() + 1, data.getUTCDate())
}

/** Sposta di n mesi tenendo il giorno, ridotto all'ultimo del mese se serve (31/01 → 28/02). */
export function spostaMesi(isoGiornoValore: string, mesi: number): string {
  const parti = leggiIso(isoGiornoValore)
  if (!parti) return isoGiornoValore
  const indice = parti.anno * 12 + (parti.mese - 1) + mesi
  const anno = Math.floor(indice / 12)
  const mese = (indice % 12) + 1
  return isoGiorno(anno, mese, Math.min(parti.giorno, giorniNelMese(anno, mese)))
}

export type CellaCalendario = { iso: string; giorno: number; delMese: boolean }

/** Sei settimane da lunedì per il mese che contiene il giorno indicato. */
export function grigliaMese(isoGiornoValore: string): CellaCalendario[][] {
  const parti = leggiIso(isoGiornoValore)
  if (!parti) return []
  const primo = isoGiorno(parti.anno, parti.mese, 1)
  const inizio = spostaGiorni(primo, -giornoSettimana(parti.anno, parti.mese, 1))
  const settimane: CellaCalendario[][] = []
  for (let s = 0; s < 6; s += 1) {
    const riga: CellaCalendario[] = []
    for (let g = 0; g < 7; g += 1) {
      const iso = spostaGiorni(inizio, s * 7 + g)
      riga.push({ iso, giorno: Number(iso.slice(8, 10)), delMese: Number(iso.slice(5, 7)) === parti.mese })
    }
    settimane.push(riga)
  }
  return settimane
}

export function titoloMese(isoGiornoValore: string): string {
  const parti = leggiIso(isoGiornoValore)
  return parti ? `${MESI_IT[parti.mese - 1]} ${parti.anno}` : ''
}

/** «Oggi» nel giorno civile italiano (Europe/Rome), indipendente dal fuso del browser. */
export function oggiRoma(adesso: Date = new Date()): string {
  const parti = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(adesso)
  const valore = (tipo: string) => parti.find((parte) => parte.type === tipo)?.value || ''
  return `${valore('year')}-${valore('month')}-${valore('day')}`
}

/** Messaggio di errore per il campo, oppure '' se il valore è accettabile. */
export function erroreCampoData(lettura: LetturaData, conOra: boolean, min?: string, max?: string, testo = ''): string {
  const formato = conOra ? 'gg/mm/aaaa hh:mm' : 'gg/mm/aaaa'
  if (lettura.stato === 'vuoto') return ''
  if (lettura.stato === 'incompleto') {
    const soloGiorno = conOra && leggiTestoData(testo.trim().split(/[\sT]/)[0] || '', false).stato === 'valido'
    return soloGiorno ? 'Indica anche l’ora nel formato hh:mm.' : `Completa la data nel formato ${formato}.`
  }
  if (lettura.stato === 'non_valido') return `Data non valida: scrivi una data di calendario nel formato ${formato}.`
  const minimo = min ? isoDaValore(min, conOra && min.length > 10) : ''
  const massimo = max ? isoDaValore(max, conOra && max.length > 10) : ''
  const confronto = (iso: string, limite: string) => (limite.length === 10 ? giornoDiIso(iso) : iso).localeCompare(limite)
  if (minimo && confronto(lettura.iso, minimo) < 0) return `La data non può essere precedente al ${testoDaValore(minimo, minimo.length > 10)}.`
  if (massimo && confronto(lettura.iso, massimo) > 0) return `La data non può essere successiva al ${testoDaValore(massimo, massimo.length > 10)}.`
  return ''
}
