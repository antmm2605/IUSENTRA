/**
 * Testo delle PEC di cancelleria in forma leggibile: nomi propri, testo del registro in carattere normale, nomi dei file
 * tecnici del gestore e il messaggio diviso in consegna, campi della comunicazione e avvertenze.
 */

const testo = (valore: unknown) => (typeof valore === 'string' ? valore.trim() : '')

const SIGLE = new Set(['RG', 'PEC', 'INPS', 'INAIL', 'MIM', 'TAR', 'CTU', 'PST', 'SPA', 'SRL'])
const MINUSCOLE = new Set(['di', 'del', 'della', 'dello', 'dei', 'degli', 'delle', 'e', 'ed', 'in', 'per', 'a', 'al', 'alla', 'da', 'con'])
const TECNICI: Array<[RegExp, string]> = [
  [/^daticert\.xml$/i, 'Ricevuta del gestore PEC'],
  [/^smime\.p7s$/i, 'Firma del gestore PEC'],
  [/^indicebusta\.xml$/i, 'Indice della busta telematica'],
  [/^comunicazione\.xml(\.p7m)?$/i, 'Dati strutturati della comunicazione'],
  [/^postacert\.eml$/i, 'Messaggio originale'],
]


/** «TRIBUNALE ORDINARIO DI VICENZA» → «Tribunale Ordinario di Vicenza»; sigle invariate. */
export function nomeProprio(valore: string): string {
  if (valore !== valore.toLocaleUpperCase('it-IT')) return valore
  return valore.toLocaleLowerCase('it-IT').split(' ').map((parola, indice) => {
    if (SIGLE.has(parola.toLocaleUpperCase('it-IT'))) return parola.toLocaleUpperCase('it-IT')
    if (indice && MINUSCOLE.has(parola)) return parola
    const elisa = parola.match(/^(dell|dall|nell|sull|all|l|d)(['’])(.+)$/)
    if (elisa && indice) return `${elisa[1]}${elisa[2]}${elisa[3].charAt(0).toLocaleUpperCase('it-IT')}${elisa[3].slice(1)}`
    return parola.replace(/(^|['’])(\p{L})/gu, (_, prima: string, lettera: string) => prima + lettera.toLocaleUpperCase('it-IT'))
  }).join(' ')
}

/** Il testo del registro, tutto maiuscolo, in carattere normale: iniziale maiuscola, sigle e numeri invariati. */
export function fraseDelRegistro(valore: string): string {
  const lettere = valore.match(/\p{L}/gu) || []
  const maiuscole = lettere.filter((c) => c === c.toLocaleUpperCase('it-IT') && c !== c.toLocaleLowerCase('it-IT')).length
  if (!valore || !lettere.length || maiuscole / lettere.length < 0.7) return valore
  const frase = valore.toLocaleLowerCase('it-IT').replace(/\b(rg|pec|inps|inail|mim|ctu)\b/g, (s) => s.toLocaleUpperCase('it-IT'))
  return frase.charAt(0).toLocaleUpperCase('it-IT') + frase.slice(1)
}

/** «01» → «sezione 01»; «LAVORO» → «sezione Lavoro»; una sezione già descritta resta com'è. */
export function sezioneLeggibile(valore: string): string {
  if (!valore) return ''
  const nome = nomeProprio(valore)
  return /^sez/i.test(nome) ? nome : `sezione ${nome}`
}

export function etichettaTecnica(nome: string): string {
  return TECNICI.find(([regola]) => regola.test(nome.trim()))?.[1] || ''
}

const CAMPI_REGISTRO: Array<[string, string]> = [
  ['Sez/Coll.', 'Sezione / collegio'],
  ['Tipo procedimento', 'Tipo di procedimento'],
  ['Numero di Ruolo generale', 'Numero di ruolo'],
  ['Giudice', 'Giudice'],
  ['Ricorr. principale', 'Ricorrente'],
  ['Resist. principale', 'Resistente'],
  ['Attore principale', 'Attore'],
  ['Conv. principale', 'Convenuto'],
  ['Oggetto', 'Oggetto'],
  ['Descrizione', 'Descrizione'],
  ['Note', 'Note'],
]

export type TestoPec = { consegna: string; campi: Array<[string, string]>; avvertenze: string[] }

/**
 * Il testo della PEC di cancelleria in tre parti: la consegna (dal messaggio del gestore, senza la copia in inglese),
 * i campi della comunicazione (una volta sola, anche se il gestore la ripete) e le avvertenze finali.
 */
export function formattaTestoPec(corpo: string): TestoPec {
  const pulito = corpo.replace(/\s+/g, ' ').trim()
  const consegna = pulito.match(/Il giorno (\d{2}\/\d{2}\/\d{4}) alle ore (\d{2}:\d{2})(?::\d{2})?.*?il messaggio\s*"([^"]+)"\s*è stato inviato da\s*"([^"]+)"\s*ed indirizzato a:?\s*(\S+?)\s.*?Identificativo messaggio:\s*(\S+)/i)
  const riga = consegna
    ? `Consegnata il ${consegna[1]} alle ${consegna[2]}: «${consegna[3]}», da ${consegna[4]} a ${consegna[5]}. Identificativo: ${consegna[6]}`
    : ''
  const inizio = pulito.search(/Comunicazione di cancelleria/i)
  let comunicazione = inizio >= 0 ? pulito.slice(inizio).replace(/^Comunicazione di cancelleria\s*/i, '') : ''
  const ripetuta = comunicazione.search(/--\s*Comunicazione di cancelleria/i)
  if (ripetuta > 0) comunicazione = comunicazione.slice(0, ripetuta)
  const avvertenze: string[] = []
  comunicazione = comunicazione.replace(/(?:--\s*)?(Si vedano gli eventuali allegati\.?|Si prega di non replicare a questo messaggio automatico\.?|Per ulteriori informazioni:\s*\S+)/gi, (frase: string) => {
    avvertenze.push(frase.replace(/^--\s*/, '').trim()); return ' '
  }).replace(/\s*--\s*$/, '')
  const posizioni = CAMPI_REGISTRO
    .map(([chiave, etichetta]) => ({ etichetta, indice: comunicazione.search(new RegExp(`${chiave.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}\\s*:`, 'i')), chiave }))
    .filter((voce) => voce.indice >= 0)
    .sort((a, b) => a.indice - b.indice)
  const campi = posizioni.map((voce, i) => {
    const fine = i + 1 < posizioni.length ? posizioni[i + 1].indice : comunicazione.length
    const valore = comunicazione.slice(voce.indice, fine).replace(/^[^:]*:\s*/, '').replace(/\s*--\s*$/, '').trim()
    return [voce.etichetta, valore] as [string, string]
  }).filter(([, valore]) => valore)
  return { consegna: riga, campi, avvertenze: [...new Set(avvertenze)] }
}

export function haDatiDiCancelleria(profilo: Record<string, unknown>): boolean {
  return Boolean(testo(profilo.ufficio) && (testo(profilo.numero_rg) || testo(profilo.tipo_evento) || testo(profilo.oggetto_evento)))
}

