/**
 * Ricerca "intelligente" nei documenti del fascicolo, interamente nel browser.
 *
 * - nomi file spezzati anche in camelCase e su _ . - (accoglimentoDecretoIngiuntivo.pdf)
 * - maiuscole, accenti e parole vuote italiane ignorati (di, della, alle…)
 * - radici e prefissi: "provvedimenti" trova "provvedimento", "provv" trova tutto il gruppo
 * - sigle e sinonimi forensi: DI, CU, PEC, RdAC, CTU, NIR, procura/mandato, relata/notifica…
 * - refusi: una lettera sbagliata, mancante o invertita dalla quinta lettera in poi
 * - date: 8-3-2024, 08.03.2024, 2024-03-08, 3/2024, "mar 2024", "8 marzo 2024"
 * - "frase esatta" tra virgolette e -parola per escludere
 * - risultati ordinati per pertinenza; se nessun documento contiene tutti i termini
 *   vengono proposti i documenti più simili, dichiarandolo.
 */

export type SearchableDocument = {
  name?: string
  type?: string
  rawType?: string
  catalogLabel?: string
  catalogRole?: string
  source?: string
  portalName?: string
  portalClass?: string
  portalSender?: string
  statusLabel?: string
  notes?: string
  tags?: string[]
  documentDate?: string
  uploadedAt?: string
  portalDate?: string
  signed?: boolean
}

type FieldKey = 'name' | 'label' | 'meta' | 'date'

export type DocumentSearchIndex = {
  fields: Record<FieldKey, string[]>
  nameText: string
}

export type DocumentSearchMode = 'nessuna' | 'esatta' | 'simili' | 'nessun_risultato'

type Alternative = { words: string[]; exact: boolean; quality: number }
type SearchTerm = { label: string; alternatives: Alternative[]; fuzzy: string; exclude: boolean }

const FIELD_WEIGHT: Record<FieldKey, number> = { name: 3, label: 2.2, date: 1.6, meta: 1 }

const ITALIAN_MONTHS = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']

const STOPWORDS = new Set([
  'il', 'lo', 'la', 'i', 'gli', 'le', 'l', 'un', 'uno', 'una', 'di', 'd', 'del', 'dello', 'della', 'dell', 'dei', 'degli', 'delle',
  'da', 'dal', 'dallo', 'dalla', 'dall', 'dai', 'dagli', 'dalle', 'a', 'al', 'allo', 'alla', 'all', 'ai', 'agli', 'alle',
  'in', 'nel', 'nello', 'nella', 'nell', 'nei', 'negli', 'nelle', 'con', 'su', 'sul', 'sulla', 'sull', 'sui', 'per', 'tra', 'fra',
  'e', 'ed', 'o', 'od', 'che', 'come', 'ad',
])

/**
 * Gruppi forensi. `keys`: cosa può scrivere l'utente (sigle comprese).
 * `phrases`: cosa cercare nel documento; ogni parola vale come prefisso,
 * tranne quelle di 3 lettere o meno che devono coincidere.
 */
const LEGAL_GROUPS: ReadonlyArray<{ keys: string[]; phrases: string[] }> = [
  { keys: ['di', 'dig', 'decreto ingiuntivo', 'decreti ingiuntivi', 'ingiuntivo', 'ingiunzione', 'monitorio'], phrases: ['decreto ingiuntiv', 'decreti ingiuntiv', 'ingiuntiv', 'ingiunzion', 'monitori'] },
  { keys: ['cu', 'contributo unificato', 'contributo', 'pagopa', 'pago pa'], phrases: ['contributo unificat', 'contributo', 'pagopa', 'pago pa'] },
  { keys: ['pagamento', 'pagamenti', 'versamento', 'bonifico', 'f23', 'marca bollo', 'bollo'], phrases: ['pagament', 'versament', 'bonific', 'f23', 'marca bollo', 'pagopa', 'contributo unificat'] },
  { keys: ['pec', 'posta certificata', 'posta elettronica certificata', 'email', 'e mail', 'mail'], phrases: ['pec', 'posta elettronica certificat', 'posta certificat', 'email', 'e mail', 'mail', 'eml'] },
  { keys: ['rda', 'ricevuta accettazione', 'accettazione'], phrases: ['ricevuta accettazion', 'accettazion', 'rda'] },
  { keys: ['rdac', 'ricevuta consegna', 'avvenuta consegna', 'consegna'], phrases: ['avvenuta consegn', 'ricevuta consegn', 'consegn', 'rdac'] },
  { keys: ['procura', 'procure', 'procura liti', 'mandato', 'delega'], phrases: ['procur', 'mandat', 'deleg'] },
  { keys: ['citazione', 'atto citazione', 'citazioni'], phrases: ['citazion'] },
  { keys: ['comparsa', 'comparse', 'costituzione', 'comparsa costituzione', 'comparsa risposta'], phrases: ['compars', 'costituzion'] },
  { keys: ['memoria', 'memorie', 'note scritte', 'note autorizzate', 'memoria integrativa'], phrases: ['memori', 'note scritt', 'note autorizzat', '171 ter', '183'] },
  { keys: ['sentenza', 'sentenze', 'sent'], phrases: ['sentenz'] },
  { keys: ['ordinanza', 'ordinanze', 'ord'], phrases: ['ordinanz'] },
  { keys: ['verbale', 'verbali', 'udienza', 'udienze', 'verbale udienza'], phrases: ['verbal', 'udienz'] },
  { keys: ['notifica', 'notifiche', 'notificazione', 'relata', 'relate', 'relata notifica'], phrases: ['notific', 'relata', 'relate'] },
  { keys: ['ctu', 'ctp', 'consulenza', 'consulenza tecnica', 'perizia', 'perizie'], phrases: ['ctu', 'ctp', 'consulenza tecnic', 'periz'] },
  { keys: ['fattura', 'fatture', 'parcella', 'parcelle', 'notula', 'notule'], phrases: ['fattur', 'parcell', 'notul'] },
  { keys: ['precetto', 'precetti', 'atto precetto'], phrases: ['precett'] },
  { keys: ['pignoramento', 'pignoramenti'], phrases: ['pignorament'] },
  { keys: ['firmato', 'firmati', 'firmata', 'firmate', 'firma digitale', 'p7m', 'cades', 'pades'], phrases: ['firmat', 'firma digital', 'p7m', 'cades', 'pades'] },
  { keys: ['firmare', 'non firmato', 'non firmati', 'senza firma'], phrases: ['firmare'] },
  { keys: ['nir', 'nota iscrizione', 'nota iscrizione ruolo', 'iscrizione ruolo'], phrases: ['nota iscrizion', 'iscrizione ruol', 'nir'] },
  { keys: ['ricorso', 'ricorsi'], phrases: ['ricors'] },
  { keys: ['atp', 'accertamento tecnico preventivo'], phrases: ['accertamento tecnico preventiv', 'atp'] },
  { keys: ['opposizione', 'opposizioni', 'opp'], phrases: ['opposizion'] },
  { keys: ['allegato', 'allegati'], phrases: ['allegat'] },
  { keys: ['deposito', 'depositi', 'busta', 'telematico', 'pct'], phrases: ['deposit', 'busta', 'telematic', 'pct'] },
  { keys: ['appello', 'gravame'], phrases: ['appell', 'gravam'] },
  { keys: ['cassazione', 'cass'], phrases: ['cassazion'] },
  { keys: ['gdp', 'giudice pace'], phrases: ['giudice pace', 'gdp'] },
  { keys: ['esecutivo', 'esecutiva', 'formula esecutiva'], phrases: ['esecutiv', 'formula esecutiv'] },
  { keys: ['visura', 'visure'], phrases: ['visur'] },
  { keys: ['cf', 'codice fiscale', 'carta identita', 'documento identita', 'cie', 'passaporto'], phrases: ['codice fiscal', 'carta identit', 'documento identit', 'cie', 'passaport'] },
]

/** Normalizza: camelCase spezzato, minuscole, niente accenti, separatori → spazio (la "/" resta per date e R.G.). */
export function normaliseForSearch(value: string): string {
  return String(value || '')
    .replace(/\b([A-Za-z])\.([A-Za-z])\.(?:([A-Za-z])\.)?(?:([A-Za-z])\.)?/g, (_, a, b, c = '', d = '') => `${a}${b}${c}${d}`)
    .replace(/([a-zà-ÿ])([A-Z])/g, '$1 $2')
    .replace(/([A-Za-z])(\d)/g, '$1 $2')
    .replace(/(\d)([A-Za-z])/g, '$1 $2')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9/]+/g, ' ')
    .trim()
}

function tokens(value: string, dropStopwords = true): string[] {
  const list = normaliseForSearch(value).split(' ').filter(Boolean)
  return dropStopwords ? list.filter((token) => !STOPWORDS.has(token)) : list
}

function parseDateParts(value: string): { day: number; month: number; year: number } | null {
  const raw = String(value || '').trim()
  let match = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/)
  if (match) return { day: Number(match[1]), month: Number(match[2]), year: Number(match[3]) }
  match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (match) return { day: Number(match[3]), month: Number(match[2]), year: Number(match[1]) }
  return null
}

function dateTokens(value: string): string[] {
  const parts = parseDateParts(value)
  if (!parts || parts.month < 1 || parts.month > 12) return []
  const dd = String(parts.day).padStart(2, '0')
  const mm = String(parts.month).padStart(2, '0')
  const month = ITALIAN_MONTHS[parts.month - 1]
  return [`${dd}/${mm}/${parts.year}`, `${mm}/${parts.year}`, String(parts.day), month, String(parts.year)]
}

/** Parole spezzate più le forme compatte originali ("QuickOrganizer" → quick, organizer, quickorganizer). */
function fieldTokens(value: string): string[] {
  const split = tokens(value)
  const compact = String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .split(/[^a-z0-9/]+/)
    .filter((token) => token.length >= 4 && !split.includes(token))
  return compact.length ? [...split, ...compact] : split
}

export function buildDocumentSearchIndex(doc: SearchableDocument, extra: string[] = []): DocumentSearchIndex {
  const join = (values: Array<string | undefined>) => values.filter(Boolean).join(' ')
  return {
    nameText: tokens(doc.name || '', false).join(' '),
    fields: {
      name: fieldTokens(doc.name || ''),
      label: fieldTokens(join([doc.type, doc.rawType, doc.catalogLabel, doc.catalogRole, ...extra])),
      meta: fieldTokens(join([doc.source, doc.portalName, doc.portalClass, doc.portalSender, doc.statusLabel, doc.notes, ...(doc.tags || []), doc.signed ? 'firmato' : 'da firmare'])),
      date: [...dateTokens(doc.documentDate || ''), ...dateTokens(doc.portalDate || ''), ...dateTokens(doc.uploadedAt || '')],
    },
  }
}

/** Date scritte in qualunque forma comune diventano gg/mm/aaaa o mm/aaaa. */
function normaliseQueryDates(query: string): string {
  const year = (value: string) => (value.length === 2 ? `20${value}` : value)
  const pad = (value: string) => value.padStart(2, '0')
  return query
    // Sigle puntate: D.I. → DI, c.t.u. → ctu, R.G. → RG.
    .replace(/\b([A-Za-z])\.([A-Za-z])\.(?:([A-Za-z])\.)?(?:([A-Za-z])\.)?/g, (_, a, b, c = '', d = '') => `${a}${b}${c}${d}`)
    .replace(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/g, (_, y, m, d) => `${pad(d)}/${pad(m)}/${y}`)
    .replace(/\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b/g, (_, d, m, y) => `${pad(d)}/${pad(m)}/${year(y)}`)
    .replace(/(^|[^\d/])(\d{1,2})[./-](\d{4})\b/g, (_, before, m, y) => `${before}${pad(m)}/${y}`)
}

function wordAlternative(word: string, quality: number): Alternative {
  return { words: [word], exact: word.length <= 2, quality }
}

function phraseAlternative(phrase: string, quality: number): Alternative {
  const words = tokens(phrase)
  return { words, exact: false, quality }
}

function normaliseKey(key: string): string {
  const words = tokens(key, false)
  return (words.length > 1 ? words.filter((word) => !STOPWORDS.has(word)) : words).join(' ')
}

let normalisedGroups: Array<{ keys: Set<string>; phrases: string[] }> | null = null

function groupFor(candidate: string): { keys: Set<string>; phrases: string[] } | undefined {
  if (!candidate) return undefined
  normalisedGroups ??= LEGAL_GROUPS.map((group) => ({ keys: new Set(group.keys.map(normaliseKey).filter(Boolean)), phrases: group.phrases }))
  return normalisedGroups.find((group) => group.keys.has(candidate))
}

/** Scompone la ricerca in termini; ogni termine ha alternative (sinonimi, date) di cui ne basta una. */
export function parseDocumentQuery(query: string): SearchTerm[] {
  const source = normaliseQueryDates(String(query || ''))
  const terms: SearchTerm[] = []
  const phraseRegex = /(-?)"([^"]+)"/g
  let rest = source
  for (const match of source.matchAll(phraseRegex)) {
    const words = tokens(match[2])
    if (words.length) terms.push({ label: match[2], alternatives: [{ words, exact: false, quality: 1 }], fuzzy: '', exclude: match[1] === '-' })
    rest = rest.replace(match[0], ' ')
  }
  const rawParts = rest.split(/\s+/).filter(Boolean)
  const parts: Array<{ token: string; upper: boolean; exclude: boolean }> = []
  for (const raw of rawParts) {
    const exclude = raw.startsWith('-') && raw.length > 1
    const clean = exclude ? raw.slice(1) : raw
    const upper = /[A-Z]/.test(clean) && clean === clean.toUpperCase()
    for (const token of tokens(clean, false)) parts.push({ token, upper, exclude })
  }
  const onlyOne = parts.length === 1
  for (let index = 0; index < parts.length;) {
    const part = parts[index]
    let consumed = 0
    // Prima le espressioni di 3 e 2 parole ("decreto ingiuntivo", "posta elettronica certificata").
    for (let size = Math.min(4, parts.length - index); size >= 2 && !consumed; size -= 1) {
      const slice = parts.slice(index, index + size)
      if (slice.some((item) => item.exclude !== part.exclude)) continue
      const candidate = slice.map((item) => item.token).filter((token) => !STOPWORDS.has(token)).join(' ')
      const group = groupFor(candidate)
      if (group) {
        terms.push({ label: candidate, alternatives: [phraseAlternative(candidate, 1), ...group.phrases.map((phrase) => phraseAlternative(phrase, 0.75))], fuzzy: '', exclude: part.exclude })
        consumed = size
      }
    }
    if (consumed) {
      index += consumed
      continue
    }
    const { token, upper, exclude } = part
    index += 1
    const group = groupFor(token)
    const isStopword = STOPWORDS.has(token)
    // "di" è una parola vuota, ma "DI" (o "di" scritto da solo) è la sigla del decreto ingiuntivo.
    if (isStopword && !(group && (upper || onlyOne))) continue
    const alternatives: Alternative[] = []
    const abbreviation = Boolean(group) && token.length <= 3
    if (!(abbreviation && isStopword)) alternatives.push(wordAlternative(token, 1))
    if (group) alternatives.push(...group.phrases.map((phrase) => phraseAlternative(phrase, 0.75)))
    const monthIndex = token.length >= 3 && /^[a-z]+$/.test(token) ? ITALIAN_MONTHS.findIndex((month) => month.startsWith(token)) : -1
    if (monthIndex >= 0) alternatives.push({ words: [ITALIAN_MONTHS[monthIndex]], exact: true, quality: 0.9 })
    const stem = italianStem(token)
    if (stem !== token && stem.length >= 4) alternatives.push({ words: [stem], exact: false, quality: 0.85 })
    terms.push({ label: token, alternatives, fuzzy: /^[a-z]{5,}$/.test(token) ? token : '', exclude })
  }
  return terms.filter((term) => term.alternatives.length)
}

/** Radice leggera: singolare/plurale e maschile/femminile ("notifiche" → "notific", "atti" → "att"). */
export function italianStem(word: string): string {
  if (word.length < 4 || /\d/.test(word)) return word
  if (/(che|chi)$/.test(word)) return word.slice(0, -2)
  if (/(ghe|ghi)$/.test(word)) return word.slice(0, -2)
  if (/(zioni|zione)$/.test(word)) return word.replace(/(zioni|zione)$/, 'zion')
  return word.replace(/[aeio]$/, '')
}

function damerauWithin(a: string, b: string, max: number): boolean {
  if (Math.abs(a.length - b.length) > max) return false
  const rows = a.length + 1
  const cols = b.length + 1
  const d: number[][] = Array.from({ length: rows }, (_, i) => Array.from({ length: cols }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)))
  for (let i = 1; i < rows; i += 1) {
    let rowMin = Number.POSITIVE_INFINITY
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      let value = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) value = Math.min(value, d[i - 2][j - 2] + 1)
      d[i][j] = value
      rowMin = Math.min(rowMin, value)
    }
    if (rowMin > max) return false
  }
  return d[a.length][b.length] <= max
}

function wordMatches(token: string, word: string, exact: boolean): number {
  if (token === word) return 1
  if (exact) return 0
  if (token.startsWith(word)) return 0.8
  // Numeri e riferimenti (R.G. 123/2024, 03/2024 dentro 08/03/2024).
  if (word.length >= 3 && /[\d/]/.test(word) && token.includes(word)) return 0.6
  if (word.length >= 4 && token.includes(word)) return 0.45
  return 0
}

function alternativeScore(fieldTokens: string[], alternative: Alternative): number {
  const { words, exact } = alternative
  if (!words.length || fieldTokens.length < words.length) return 0
  let best = 0
  for (let start = 0; start <= fieldTokens.length - words.length; start += 1) {
    let total = 0
    for (let offset = 0; offset < words.length; offset += 1) {
      const score = wordMatches(fieldTokens[start + offset], words[offset], exact || words[offset].length <= 2)
      if (!score) {
        total = 0
        break
      }
      total += score
    }
    if (total) best = Math.max(best, total / words.length)
    if (best === 1) break
  }
  return best * alternative.quality
}

function termScore(index: DocumentSearchIndex, term: SearchTerm, allowFuzzy: boolean): number {
  let best = 0
  for (const field of Object.keys(FIELD_WEIGHT) as FieldKey[]) {
    const fieldTokens = index.fields[field]
    for (const alternative of term.alternatives) {
      best = Math.max(best, alternativeScore(fieldTokens, alternative) * FIELD_WEIGHT[field])
    }
    if (allowFuzzy && term.fuzzy && best === 0) {
      const max = term.fuzzy.length >= 9 ? 2 : 1
      for (const token of fieldTokens) {
        if (token.length < 4) continue
        const candidates = token.length > term.fuzzy.length + max
          ? [token.slice(0, term.fuzzy.length), token.slice(0, term.fuzzy.length + 1)]
          : [token]
        if (candidates.some((candidate) => damerauWithin(term.fuzzy, candidate, max))) {
          best = Math.max(best, 0.4 * FIELD_WEIGHT[field])
          break
        }
      }
    }
  }
  return best
}

export type DocumentSearchResult<T> = {
  mode: DocumentSearchMode
  terms: string[]
  items: Array<{ item: T; score: number }>
}

/** Filtra e ordina per pertinenza. Senza termini restituisce tutto con punteggio 0. */
export function searchDocumentIndex<T>(items: Array<{ item: T; index: DocumentSearchIndex }>, query: string): DocumentSearchResult<T> {
  const parsed = parseDocumentQuery(query)
  const include = parsed.filter((term) => !term.exclude)
  const exclude = parsed.filter((term) => term.exclude)
  if (!parsed.length) return { mode: 'nessuna', terms: [], items: items.map(({ item }) => ({ item, score: 0 })) }
  const phrase = include.map((term) => term.label).join(' ')
  const candidates = items.filter(({ index }) => !exclude.some((term) => termScore(index, term, false) > 0))
  if (!include.length) return { mode: 'esatta', terms: [], items: candidates.map(({ item }) => ({ item, score: 0 })) }

  const scored = candidates.map(({ item, index }) => {
    const perTerm = include.map((term) => termScore(index, term, true))
    const matched = perTerm.filter((score) => score > 0).length
    let score = perTerm.reduce((sum, value) => sum + value, 0)
    if (phrase.length >= 3 && index.nameText.includes(phrase)) score += 3
    return { item, score, matched }
  })
  const exact = scored.filter((entry) => entry.matched === include.length)
  const byScore = (a: { score: number }, b: { score: number }) => b.score - a.score
  if (exact.length) return { mode: 'esatta', terms: include.map((term) => term.label), items: exact.sort(byScore).map(({ item, score }) => ({ item, score })) }
  if (include.length >= 2) {
    const threshold = Math.ceil(include.length / 2)
    const similar = scored.filter((entry) => entry.matched >= threshold)
    if (similar.length) {
      return {
        mode: 'simili',
        terms: include.map((term) => term.label),
        items: similar.sort((a, b) => b.matched - a.matched || byScore(a, b)).map(({ item, score }) => ({ item, score })),
      }
    }
  }
  return { mode: 'nessun_risultato', terms: include.map((term) => term.label), items: [] }
}
