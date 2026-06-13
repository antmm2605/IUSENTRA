import commandCatalog from './studioVoiceCommands.json'

export type StudioVoiceCommandKind =
  | 'route'
  | 'new-client-flow'
  | 'edit-current-record'
  | 'note-flow'
  | 'dictation'
  | 'search'
  | 'lex'
  | 'help'
  | 'back'
  | 'reload'
  | 'stop'

export type StudioVoiceCommand = {
  id: string
  label: string
  href?: string
  group: string
  kind: StudioVoiceCommandKind
  phrases: string[]
}

type StudioVoiceCatalog = {
  baseUserCommands: string[]
  routeCommands: Array<Omit<StudioVoiceCommand, 'kind'>>
  specialCommands: Array<StudioVoiceCommand>
}

export type VoiceClientDraft = {
  nome: string
  cognome: string
  codice_fiscale: string
}

export type VoiceClientField = keyof VoiceClientDraft

export type VoiceNote = {
  id: string
  text: string
  createdAt: string
  targetAt: string | null
  notifyAt: string | null
  notifiedAt: string | null
}

export type VoiceNoteReminder = {
  targetAt: Date
  notifyAt: Date
}

const catalog = commandCatalog as StudioVoiceCatalog

export const BASE_USER_COMMANDS = catalog.baseUserCommands

export const VOICE_ROUTE_COMMANDS: StudioVoiceCommand[] = catalog.routeCommands.map((command) => ({
  ...command,
  kind: 'route',
}))

export const VOICE_SPECIAL_COMMANDS: StudioVoiceCommand[] = catalog.specialCommands

export const ALL_STUDIO_VOICE_COMMANDS: StudioVoiceCommand[] = [
  ...VOICE_SPECIAL_COMMANDS,
  ...VOICE_ROUTE_COMMANDS,
]

const SEARCH_PREFIXES = [
  'studio cerca nello studio',
  'studio trova nello studio',
  'studio cerca',
  'studio trova',
  'studio ricerca',
  'cerca nello studio',
  'trova nello studio',
  'cerca',
  'trova',
  'ricerca',
]

const CONFIRM_WORDS = ['confermo', 'si confermo', 'sì confermo', 'salva', 'aggiungi', 'procedi', 'va bene']
const NEGATIVE_CONFIRMATION_WORDS = ['no', 'no grazie', 'non confermo', 'non va bene', 'correggi', 'devo correggere', 'voglio modificare', 'modifica un campo']
const CANCEL_WORDS = ['annulla', 'annulli tutto', 'annulla tutto', 'cancella', 'cancella tutto', 'ferma inserimento', 'non salvare', 'interrompi']
const CLIENT_FIELD_CHANGE_PREFIXES = [
  'modifica',
  'cambia',
  'correggi',
  'rettifica',
  'sostituisci',
  'voglio modificare',
  'devo modificare',
  'campo',
]

export const NOTE_REMINDER_OFFSET_MS = 10 * 60 * 1000
export const MAX_VOICE_NOTE_TIMEOUT_MS = 2_147_000_000
export const MAX_STORED_VOICE_NOTES = 30
export const VOICE_NOTE_TIME_ZONE = 'Europe/Rome'

const ITALIAN_MONTHS: Record<string, number> = {
  gennaio: 0,
  febbraio: 1,
  marzo: 2,
  aprile: 3,
  maggio: 4,
  giugno: 5,
  luglio: 6,
  agosto: 7,
  settembre: 8,
  ottobre: 9,
  novembre: 10,
  dicembre: 11,
}

const SMALL_NUMBER_WORDS: Record<string, number> = {
  zero: 0,
  uno: 1,
  una: 1,
  un: 1,
  due: 2,
  tre: 3,
  quattro: 4,
  cinque: 5,
  sei: 6,
  sette: 7,
  otto: 8,
  nove: 9,
  dieci: 10,
  undici: 11,
  dodici: 12,
  tredici: 13,
  quattordici: 14,
  quindici: 15,
  sedici: 16,
  diciassette: 17,
  diciotto: 18,
  diciannove: 19,
  venti: 20,
  ventuno: 21,
  ventidue: 22,
  ventitre: 23,
  ventitré: 23,
}

const DIGIT_WORDS: Record<string, string> = {
  zero: '0',
  uno: '1',
  una: '1',
  due: '2',
  tre: '3',
  quattro: '4',
  cinque: '5',
  sei: '6',
  sette: '7',
  otto: '8',
  nove: '9',
}

const LETTER_WORDS: Record<string, string> = {
  a: 'A',
  bi: 'B',
  b: 'B',
  ci: 'C',
  c: 'C',
  di: 'D',
  d: 'D',
  e: 'E',
  effe: 'F',
  f: 'F',
  gi: 'G',
  g: 'G',
  acca: 'H',
  h: 'H',
  i: 'I',
  elle: 'L',
  l: 'L',
  emme: 'M',
  m: 'M',
  enne: 'N',
  n: 'N',
  o: 'O',
  pi: 'P',
  p: 'P',
  qu: 'Q',
  cu: 'Q',
  q: 'Q',
  erre: 'R',
  r: 'R',
  esse: 'S',
  s: 'S',
  ti: 'T',
  t: 'T',
  u: 'U',
  vu: 'V',
  v: 'V',
  zeta: 'Z',
  z: 'Z',
}

const CLIENT_FIELD_PREFIXES: Record<VoiceClientField, string[]> = {
  nome: ['nome', 'il nome è', 'il nome e', 'si chiama', 'cliente nome', 'modifica nome', 'cambia nome', 'correggi nome'],
  cognome: ['cognome', 'il cognome è', 'il cognome e', 'cliente cognome', 'modifica cognome', 'cambia cognome', 'correggi cognome'],
  codice_fiscale: ['codice fiscale', 'cf', 'codice', 'cliente codice fiscale', 'modifica codice fiscale', 'cambia codice fiscale', 'correggi codice fiscale'],
}

const DICTATION_POLISH_COMMANDS = [
  'correggi punteggiatura',
  'sistema punteggiatura',
  'correggi la punteggiatura',
  'correggi ortografia',
  'scrivi bene',
  'rifinisci testo',
]

export function normalizeVoiceText(value: string): string {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’']/g, ' ')
    .toLocaleLowerCase('it-IT')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function upperItalian(value: string): string {
  return value.toLocaleUpperCase('it-IT')
}

function lowerItalian(value: string): string {
  return value.toLocaleLowerCase('it-IT')
}

function capitalizeItalianWord(value: string): string {
  if (!value) return ''
  return upperItalian(value.slice(0, 1)) + lowerItalian(value.slice(1))
}

function capitalizeItalianSentences(value: string): string {
  return value.replace(/(^|[.!?]\s+|\n+\s*)([a-zàèéìòù])/giu, (_match, prefix: string, letter: string) => (
    `${prefix}${upperItalian(letter)}`
  ))
}

function restoreCompactEmailText(value: string): string {
  return value
    .replace(/([\p{L}\p{N}_%+-])\.\s+([\p{L}\p{N}_%+-]+@)/giu, '$1.$2')
    .replace(/(@[\p{L}\p{N}._%+-]+)\.\s+([a-z]{2,12})(\b)/giu, '$1.$2')
    .replace(/\b[\p{L}\p{N}._%+-]+@[\p{L}\p{N}.-]+\.[a-z]{2,12}\b/giu, (match) => lowerItalian(match))
}

function includesNormalizedPhrase(normalized: string, phrase: string): boolean {
  const cleanPhrase = normalizeVoiceText(phrase)
  if (!cleanPhrase) return false
  if (normalized === cleanPhrase) return true
  if (cleanPhrase.length <= 3) return normalized.split(' ').includes(cleanPhrase)
  return normalized.includes(cleanPhrase)
}

export function formatItalianDictationText(value: string): string {
  let text = String(value || '').trim()
  if (!text) return ''

  text = text
    .replace(/\bnuovo\s+paragrafo\b/giu, '\n\n')
    .replace(/\b(?:a\s+capo|nuova\s+riga)\b/giu, '\n')
    .replace(/\bpunto\s+e\s+virgola\b/giu, ';')
    .replace(/\bpunto\s+virgola\b/giu, ';')
    .replace(/\bdue\s+punti\b/giu, ':')
    .replace(/\bpunto\s+(?:interrogativo|di\s+domanda|domanda)\b/giu, '?')
    .replace(/\bpunto\s+(?:esclamativo|escamativo|esclamazione)\b/giu, '!')
    .replace(/\bpunto\s+fermo\b/giu, '.')
    .replace(/\bvirgola\b/giu, ',')
    .replace(/\bpunto\b/giu, '.')
    .replace(/\bapr[io]\s+parentesi\b/giu, '(')
    .replace(/\bchiud[io]\s+parentesi\b/giu, ')')
    .replace(/\bapr[io]\s+virgolette\b/giu, '“')
    .replace(/\bchiud[io]\s+virgolette\b/giu, '”')
    .replace(/\bapostrofo\b/giu, "'")
    .replace(/\b(?:asterisco|aterisco)\b/giu, '*')
    .replace(/\b(?:chiocciola|chiocciolina|ciocciola)\b/giu, '@')
    .replace(/\b(?:underscore|under score|ancscore|and score|trattino basso)\b/giu, '_')
    .replace(/\bspazio\s+meno\s+spazio\b/giu, ' - ')
    .replace(/\bspazio\s+(?:piu|più)\s+spazio\b/giu, ' + ')
    .replace(/\bspazio\s+per\s+spazio\b/giu, ' × ')
    .replace(/\bspazio\s+diviso\s+spazio\b/giu, ' / ')
    .replace(/\bsegno\s+meno\b/giu, '-')
    .replace(/\bsegno\s+(?:piu|più)\b/giu, '+')
    .replace(/\bsegno\s+per\b/giu, '×')
    .replace(/\bsegno\s+diviso\b/giu, '/')
    .replace(/\bsegno\s+uguale\b/giu, '=')
    .replace(/\bsegno\s+asterisco\b/giu, '*')
    .replace(/\bsegno\s+chiocciola\b/giu, '@')
    .replace(/\btrattino\b/giu, '-')
    .replace(/\bbarra\s+obliqua\b/giu, '/')
    .replace(/\bbarra\b/giu, '/')
    .replace(/\buguale\b/giu, '=')
    .replace(/\bspazio\b/giu, ' ')

  text = text
    .replace(/(\d+)\s+meno\s+(\d+)/giu, '$1 - $2')
    .replace(/(\d+)\s+(?:piu|più)\s+(\d+)/giu, '$1 + $2')
    .replace(/(\d+)\s+per\s+(\d+)/giu, '$1 × $2')
    .replace(/(\d+)\s+diviso\s+(\d+)/giu, '$1 / $2')
    .replace(/\bmeno\s+(\d+)/giu, '-$1')

  text = restoreCompactEmailText(text)
  text = text
    .replace(/[ \t]+/g, ' ')
    .replace(/[ \t]*\n[ \t]*/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/\s+([,.;:?!])/g, '$1')
    .replace(/([,;:?!])(?=\S)/g, '$1 ')
    .replace(/([.!?])\s+([,.;:?!])/g, '$1 ')
    .replace(/\(\s+/g, '(')
    .replace(/\s+\)/g, ')')
    .replace(/\s+([”])/g, '$1')
    .replace(/([“])\s+/g, '$1')
    .replace(/\s*'\s*/g, "'")
    .replace(/\s*(@)\s*/g, '$1')
    .replace(/\s*([+/×=])\s*/g, ' $1 ')
    .replace(/\s*([*_])\s*/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .trim()

  return restoreCompactEmailText(capitalizeItalianSentences(text))
}

export function isDictationPolishCommand(input: string): boolean {
  const normalized = normalizeVoiceText(input)
  return DICTATION_POLISH_COMMANDS.some((command) => normalized === normalizeVoiceText(command))
}

function phraseSignature(value: string): string {
  const normalized = normalizeVoiceText(value)
  return normalized.replace(/^studio\s+/, '').replace(/^iusentra\s+/, '').trim()
}

function looseVoiceToken(token: string): string {
  const aliases: Record<string, string> = {
    fascicolo: 'fascicol',
    fascicoli: 'fascicol',
    cliente: 'client',
    clienti: 'client',
    soggetto: 'soggett',
    soggetti: 'soggett',
    parte: 'part',
    parti: 'part',
    messaggio: 'messagg',
    messaggi: 'messagg',
    scadenza: 'scadenz',
    scadenze: 'scadenz',
    notifica: 'notific',
    notifiche: 'notific',
    fattura: 'fattur',
    fatture: 'fattur',
    preventivo: 'preventiv',
    preventivi: 'preventiv',
    documento: 'document',
    documenti: 'document',
    permesso: 'permess',
    permessi: 'permess',
  }
  if (aliases[token]) return aliases[token]
  if (/^\d+$/.test(token)) return token
  return token.length > 4 ? token.replace(/[aeiou]$/u, '') : token
}

function loosePhraseSignature(value: string): string {
  return phraseSignature(value).split(' ').filter(Boolean).map(looseVoiceToken).join(' ')
}

function commandPhrases(command: StudioVoiceCommand): string[] {
  return command.phrases.map(phraseSignature)
}

function voiceDictationPrefixMatch(input: string): { command: StudioVoiceCommand; text: string } | null {
  const signature = phraseSignature(input)
  if (!signature) return null
  const dictationCommand = VOICE_SPECIAL_COMMANDS.find((command) => command.kind === 'dictation')
  if (!dictationCommand) return null
  const phrases = dictationCommand.phrases
    .map(phraseSignature)
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
  for (const phrase of phrases) {
    if (signature === phrase) {
      return { command: dictationCommand, text: '' }
    }
    if (signature.startsWith(`${phrase} `)) {
      return { command: dictationCommand, text: signature.slice(phrase.length).trim() }
    }
  }
  return null
}

export function voiceCommandSummary() {
  const base = new Set(BASE_USER_COMMANDS.map(phraseSignature))
  const allPhrases = ALL_STUDIO_VOICE_COMMANDS.flatMap((command) => command.phrases)
  const addedPhrases = allPhrases.filter((phrase) => !base.has(phraseSignature(phrase)))
  return {
    base: BASE_USER_COMMANDS.length,
    added: addedPhrases.length,
    totalPhrases: allPhrases.length,
    destinations: VOICE_ROUTE_COMMANDS.length,
    actions: VOICE_SPECIAL_COMMANDS.length,
  }
}

export function findStudioVoiceCommand(transcript: string): StudioVoiceCommand | null {
  const signature = phraseSignature(transcript)
  if (!signature) return null
  const searchTerm = parseStudioSearchTerm(transcript)
  if (searchTerm) {
    return VOICE_SPECIAL_COMMANDS.find((command) => command.kind === 'search') || null
  }
  const dictationPrefixCommand = voiceDictationPrefixMatch(transcript)
  if (dictationPrefixCommand) return dictationPrefixCommand.command
  const exactCommand = (
    ALL_STUDIO_VOICE_COMMANDS.find((command) => commandPhrases(command).includes(signature)) ||
    ALL_STUDIO_VOICE_COMMANDS.find((command) => commandPhrases(command).some((phrase) => phrase && signature === phrase)) ||
    null
  )
  if (exactCommand) return exactCommand
  const looseSignature = loosePhraseSignature(transcript)
  return (
    ALL_STUDIO_VOICE_COMMANDS.find((command) => command.phrases.some((phrase) => loosePhraseSignature(phrase) === looseSignature)) ||
    null
  )
}

export function stripVoiceDictationCommand(input: string): string {
  return voiceDictationPrefixMatch(input)?.text || ''
}

export function parseStudioSearchTerm(transcript: string): string {
  const normalized = normalizeVoiceText(transcript)
  for (const prefix of SEARCH_PREFIXES) {
    const cleanPrefix = normalizeVoiceText(prefix)
    if (normalized === cleanPrefix) return ''
    if (normalized.startsWith(`${cleanPrefix} `)) {
      return normalized.slice(cleanPrefix.length).trim()
    }
  }
  return ''
}

export function extractSpokenPin(transcript: string): string {
  const tokens = normalizeVoiceText(transcript).split(' ').filter(Boolean)
  const digits = tokens.flatMap((token) => {
    if (/^\d+$/.test(token)) return token.split('')
    if (DIGIT_WORDS[token]) return [DIGIT_WORDS[token]]
    return []
  })
  return digits.join('').slice(0, 12)
}

export function isVoiceConfirmation(transcript: string): boolean {
  const normalized = normalizeVoiceText(transcript)
  return CONFIRM_WORDS.some((word) => includesNormalizedPhrase(normalized, word))
}

export function isVoiceNegativeConfirmation(transcript: string): boolean {
  const normalized = normalizeVoiceText(transcript)
  return NEGATIVE_CONFIRMATION_WORDS.some((word) => includesNormalizedPhrase(normalized, word))
}

export function isVoiceCancel(transcript: string): boolean {
  const normalized = normalizeVoiceText(transcript)
  return CANCEL_WORDS.some((word) => includesNormalizedPhrase(normalized, word))
}

export function parseClientCorrectionField(transcript: string): VoiceClientField | null {
  const normalized = normalizeVoiceText(transcript)
  if (!normalized) return null
  const tokens = normalized.split(' ').filter(Boolean)
  const hasChangeIntent = CLIENT_FIELD_CHANGE_PREFIXES.some((prefix) => normalized.includes(normalizeVoiceText(prefix)))
  const fieldOnly = tokens.length <= 3

  if (normalized.includes('codice fiscale') || tokens.includes('codice') || tokens.includes('cf')) return 'codice_fiscale'
  if (tokens.includes('cognome')) return 'cognome'
  if (tokens.includes('nome') && (hasChangeIntent || fieldOnly)) return 'nome'
  return null
}

function valueAfterPrefix(transcript: string, prefixes: string[]): string {
  const normalized = normalizeVoiceText(transcript)
  for (const prefix of prefixes) {
    const cleanPrefix = normalizeVoiceText(prefix)
    if (normalized.startsWith(`${cleanPrefix} `)) {
      return normalized.slice(cleanPrefix.length).trim()
    }
    if (normalized.startsWith(`studio ${cleanPrefix} `)) {
      return normalized.slice(`studio ${cleanPrefix}`.length).trim()
    }
  }
  return ''
}

function titleCaseItalian(value: string): string {
  return formatItalianDictationText(value)
    .replace(/[.,;:!?()[\]{}“”]/g, ' ')
    .replace(/\s*-\s*/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter(Boolean)
    .map((part) => part.split('-').map(capitalizeItalianWord).join('-'))
    .join(' ')
}

export function normalizeFiscalCodeFromVoice(value: string): string {
  const direct = String(value || '').trim()
  if (/^[a-zA-Z0-9\s-]{11,40}$/.test(direct) && /[a-zA-Z]/.test(direct)) {
    const compact = direct.replace(/[^a-zA-Z0-9]/g, '').toLocaleUpperCase('it-IT')
    if (compact.length >= 11) return compact.slice(0, 16)
  }
  const tokens = normalizeVoiceText(value).split(' ').filter(Boolean)
  const pieces = tokens.flatMap((token) => {
    if (/^\d+$/.test(token)) return token.split('')
    if (DIGIT_WORDS[token]) return [DIGIT_WORDS[token]]
    if (LETTER_WORDS[token]) return [LETTER_WORDS[token]]
    return [token.toLocaleUpperCase('it-IT').replace(/[^A-Z0-9]/g, '')]
  })
  return pieces.join('').replace(/[^A-Z0-9]/g, '').slice(0, 16)
}

export function parseVoiceClientField(
  transcript: string,
  expectedField?: VoiceClientField,
): { field: VoiceClientField; value: string } | null {
  for (const field of Object.keys(CLIENT_FIELD_PREFIXES) as VoiceClientField[]) {
    const raw = valueAfterPrefix(transcript, CLIENT_FIELD_PREFIXES[field])
    if (raw) {
      return {
        field,
        value: field === 'codice_fiscale' ? normalizeFiscalCodeFromVoice(raw) : titleCaseItalian(raw),
      }
    }
  }
  if (!expectedField) return null
  const cleaned = expectedField === 'codice_fiscale'
    ? normalizeFiscalCodeFromVoice(transcript)
    : titleCaseItalian(transcript)
  return cleaned ? { field: expectedField, value: cleaned } : null
}

export function nextMissingClientField(draft: VoiceClientDraft): VoiceClientField | null {
  if (!draft.nome.trim()) return 'nome'
  if (!draft.cognome.trim()) return 'cognome'
  if (!draft.codice_fiscale.trim()) return 'codice_fiscale'
  return null
}

export function labelForClientField(field: VoiceClientField): string {
  if (field === 'codice_fiscale') return 'codice fiscale'
  return field
}

export function buildClientConfirmation(draft: VoiceClientDraft): string {
  return `Nome ${draft.nome.trim()}, cognome ${draft.cognome.trim()}, codice fiscale ${draft.codice_fiscale.trim().toLocaleUpperCase('it-IT')}. Confermi l'inserimento?`
}

function parseVoiceNoteYear(rawYear: string | undefined, fallbackYear: number): { year: number; explicit: boolean } {
  if (!rawYear) return { year: fallbackYear, explicit: false }
  const numeric = Number(rawYear)
  if (!Number.isFinite(numeric)) return { year: fallbackYear, explicit: false }
  return { year: numeric < 100 ? 2000 + numeric : numeric, explicit: true }
}

function parseSmallNumberToken(token: string): number {
  if (/^\d+$/.test(token)) return Number(token)
  return SMALL_NUMBER_WORDS[normalizeVoiceText(token)] ?? Number.NaN
}

function parseVoiceNoteTime(clean: string): { hour: number; minute: number; explicit: boolean } {
  const numericTime = clean.match(/\b(?:alle\s+ore|alle|ore|h)\s*(\d{1,2})(?:[.:](\d{1,2}))?\b/) || clean.match(/\b(\d{1,2})[.:](\d{2})\b/)
  if (numericTime) {
    const hour = Number(numericTime[1])
    const minute = numericTime[2] ? Number(numericTime[2]) : 0
    if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) return { hour, minute, explicit: true }
  }

  const wordTime = clean.match(/\b(?:alle\s+ore|alle|ore)\s+(zero|uno|una|un|due|tre|quattro|cinque|sei|sette|otto|nove|dieci|undici|dodici|tredici|quattordici|quindici|sedici|diciassette|diciotto|diciannove|venti|ventuno|ventidue|ventitre|ventitré)\b/)
  if (wordTime) {
    const hour = parseSmallNumberToken(wordTime[1])
    if (Number.isFinite(hour) && hour >= 0 && hour <= 23) return { hour, minute: 0, explicit: true }
  }

  return { hour: 0, minute: 0, explicit: false }
}

function validVoiceNoteDate(date: Date, day: number, month: number, year: number): boolean {
  return date.getDate() === day && date.getMonth() === month && date.getFullYear() === year
}

function buildVoiceNoteReminder(targetAt: Date, now: Date): VoiceNoteReminder | null {
  if (targetAt.getTime() <= now.getTime()) return null
  return {
    targetAt,
    notifyAt: new Date(Math.max(now.getTime(), targetAt.getTime() - NOTE_REMINDER_OFFSET_MS)),
  }
}

export function parseVoiceNoteReminder(input: string, now = new Date()): VoiceNoteReminder | null {
  const clean = normalizeVoiceText(input)
  if (!clean) return null

  const relativeDuration = clean.match(/\b(?:tra|fra)\s+(\d{1,3}|un|uno|una|due|tre|quattro|cinque|sei|sette|otto|nove|dieci|undici|dodici|tredici|quattordici|quindici|sedici|diciassette|diciotto|diciannove|venti)\s+(minuto|minuti|ora|ore)\b/)
  if (relativeDuration) {
    const amount = parseSmallNumberToken(relativeDuration[1])
    if (Number.isFinite(amount) && amount > 0) {
      const unitMs = relativeDuration[2].startsWith('or') ? 60 * 60 * 1000 : 60 * 1000
      return buildVoiceNoteReminder(new Date(now.getTime() + amount * unitMs), now)
    }
  }

  const time = parseVoiceNoteTime(clean)
  if (!time.explicit) return null

  let day = 0
  let month = 0
  let year = now.getFullYear()
  let explicitYear = false
  let hasDate = false

  const relativeDate = clean.match(/\b(oggi|domani|dopodomani)\b/)
  if (relativeDate) {
    const base = new Date(now)
    if (relativeDate[1] === 'domani') base.setDate(base.getDate() + 1)
    if (relativeDate[1] === 'dopodomani') base.setDate(base.getDate() + 2)
    day = base.getDate()
    month = base.getMonth()
    year = base.getFullYear()
    explicitYear = true
    hasDate = true
  }

  if (!hasDate) {
    const monthNames = Object.keys(ITALIAN_MONTHS).join('|')
    const writtenDate = new RegExp(`\\b(\\d{1,2})\\s+(${monthNames})(?:\\s+(?:del\\s+)?(\\d{2,4}))?\\b`).exec(clean)
    if (writtenDate) {
      day = Number(writtenDate[1])
      month = ITALIAN_MONTHS[writtenDate[2]]
      const parsedYear = parseVoiceNoteYear(writtenDate[3], now.getFullYear())
      year = parsedYear.year
      explicitYear = parsedYear.explicit
      hasDate = true
    }
  }

  if (!hasDate) {
    const numericDate = clean.match(/\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/)
    if (numericDate) {
      day = Number(numericDate[1])
      month = Number(numericDate[2]) - 1
      const parsedYear = parseVoiceNoteYear(numericDate[3], now.getFullYear())
      year = parsedYear.year
      explicitYear = parsedYear.explicit
      hasDate = true
    }
  }

  if (!hasDate) return null

  let targetAt = new Date(year, month, day, time.hour, time.minute, 0, 0)
  if (!validVoiceNoteDate(targetAt, day, month, year)) return null
  if (!explicitYear && targetAt.getTime() <= now.getTime()) {
    targetAt = new Date(year + 1, month, day, time.hour, time.minute, 0, 0)
  }
  if (!validVoiceNoteDate(targetAt, day, month, targetAt.getFullYear())) return null
  return buildVoiceNoteReminder(targetAt, now)
}

function voiceNoteStartSignatures(customPhrase?: string): string[] {
  const signatures = [
    'note',
    'nota',
    'registra nota',
    'nuova nota',
    'prendi nota',
    'dettatura nota',
  ]
  const custom = phraseSignature(customPhrase || '')
  return custom && !signatures.includes(custom) ? [custom, ...signatures] : signatures
}

function voiceNoteInputSignatures(input: string): string[] {
  const signature = phraseSignature(input)
  const withoutWakeWord = signature.replace(/^(?:studio|iusentra)\s+/, '').trim()
  return Array.from(new Set([signature, withoutWakeWord].filter(Boolean)))
}

export function isVoiceNoteStartCommand(input: string, customPhrase?: string): boolean {
  const signatures = voiceNoteInputSignatures(input)
  return voiceNoteStartSignatures(customPhrase).some((phrase) => signatures.some((signature) => (
    signature === phrase ||
    signature.startsWith(`${phrase} `)
  )))
}

export function stripVoiceNoteStartCommand(input: string, customPhrase?: string): string {
  const original = String(input || '')
  const defaultStripped = original
    .replace(/^\s*(?:studio|iusentra)?[\s,.;:-]*(?:note|nota|registra nota|nuova nota|prendi nota|dettatura nota)\b[\s,.;:-]*/i, '')
    .trim()
  if (defaultStripped !== original.trim()) return defaultStripped

  const signatures = voiceNoteInputSignatures(original)
  for (const phrase of voiceNoteStartSignatures(customPhrase).sort((a, b) => b.length - a.length)) {
    for (const signature of signatures) {
      if (signature === phrase) return ''
      if (signature.startsWith(`${phrase} `)) return signature.slice(phrase.length).trim()
    }
  }
  return original.trim()
}

export function isVoiceNoteStopCommand(input: string): boolean {
  const clean = normalizeVoiceText(input)
  return ['fine nota', 'fine note', 'salva nota', 'termina nota', 'chiudi nota', 'stop nota', 'stop note', 'termina registrazione'].includes(clean)
}

export function stripVoiceNoteStopPhrases(input: string): { text: string; shouldStop: boolean } {
  const clean = normalizeVoiceText(input)
  const stopPhrases = ['fine nota', 'fine note', 'salva nota', 'termina nota', 'chiudi nota', 'stop nota', 'stop note', 'termina registrazione']
  const shouldStop = stopPhrases.some((phrase) => clean === phrase || clean.includes(` ${phrase}`) || clean.includes(`${phrase} `))
  if (!shouldStop) return { text: String(input || '').trim(), shouldStop: false }
  const text = String(input || '')
    .replace(/\b(?:fine nota|fine note|salva nota|termina nota|chiudi nota|stop nota|stop note|termina registrazione)\b/gi, '')
    .trim()
  return { text, shouldStop: true }
}

export function compactVoiceNoteText(value: string, maxLength = 180): string {
  const clean = String(value || '').replace(/\s+/g, ' ').trim()
  return clean.length > maxLength ? `${clean.slice(0, Math.max(1, maxLength - 3))}...` : clean
}

export function emptyVoiceClientDraft(): VoiceClientDraft {
  return { nome: '', cognome: '', codice_fiscale: '' }
}
