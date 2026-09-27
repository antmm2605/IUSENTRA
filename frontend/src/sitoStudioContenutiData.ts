import { apiJson, apiPostJson } from './lib/apiClient'

type Raw = Record<string, unknown>

function obj(value: unknown): Raw {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function internal(value: unknown): string {
  const raw = text(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}

export const RACCOLTE_SITO = ['servizi', 'professionisti', 'sedi', 'regole-agenda'] as const
export type RaccoltaSito = typeof RACCOLTE_SITO[number]

export type SitoContenutiRoute =
  | { collection: RaccoltaSito; mode: 'elenco' | 'nuovo' | 'modifica'; id: string }
  | { collection: 'impostazioni'; mode: 'impostazioni'; id: '' }
  | { collection: 'articoli'; mode: 'nuovo-articolo'; id: '' }

export function sitoContenutiRoute(pathname: string): SitoContenutiRoute | null {
  if (/^\/sito-studio\/impostazioni\/?$/i.test(pathname)) return { collection: 'impostazioni', mode: 'impostazioni', id: '' }
  if (/^\/sito-studio\/articoli\/nuovo\/?$/i.test(pathname)) return { collection: 'articoli', mode: 'nuovo-articolo', id: '' }
  const match = pathname.replace(/\/+$/, '').match(/^\/sito-studio\/(servizi|professionisti|sedi|regole-agenda)(?:\/(nuovo|nuova)|\/(\d+)\/modifica)?$/i)
  if (!match) return null
  const collection = match[1].toLowerCase() as RaccoltaSito
  if (match[2]) return { collection, mode: 'nuovo', id: '' }
  if (match[3]) return { collection, mode: 'modifica', id: match[3] }
  return { collection, mode: 'elenco', id: '' }
}

export type CampoSito = {
  name: string
  label: string
  kind: 'text' | 'textarea' | 'number' | 'email' | 'url' | 'checkbox' | 'time' | 'office' | 'weekday' | 'color'
  required: boolean
  help: string
  maxLength: number
  options: Array<{ value: string; label: string }>
}

export type ValoriSito = Record<string, string | boolean>

export type ElencoSito = {
  ok: boolean
  message: string
  collection: { key: string; label: string; singular: string }
  collections: Array<{ key: string; label: string; href: string }>
  fields: CampoSito[]
  defaults: ValoriSito
  items: Array<{ id: string; title: string; visible: boolean; values: ValoriSito; editHref: string }>
  needsOffice: boolean
}

const KINDS = ['text', 'textarea', 'number', 'email', 'url', 'checkbox', 'time', 'office', 'weekday', 'color']

function valori(raw: unknown): ValoriSito {
  return Object.fromEntries(Object.entries(obj(raw)).map(([key, value]) => [key, typeof value === 'boolean' ? value : text(value)]))
}

function campi(value: unknown): CampoSito[] {
  return list(value).map((raw) => {
    const campo = obj(raw)
    const kind = text(campo.kind)
    return {
      name: text(campo.name),
      label: text(campo.label),
      kind: (KINDS.includes(kind) ? kind : 'text') as CampoSito['kind'],
      required: campo.required === true,
      help: text(campo.help),
      maxLength: Number(campo.maxLength) || 0,
      options: list(campo.options).map((opt) => ({ value: text(obj(opt).value), label: text(obj(opt).label) })),
    }
  })
}

export type ImpostazioniSito = { ok: boolean; message: string; fields: CampoSito[]; values: ValoriSito; publicUrl: string }

export async function getImpostazioniSito(): Promise<ImpostazioniSito> {
  const payload = obj(await apiJson<unknown>('/api/v1/ui/sito-studio/contenuti/impostazioni', { ok: false }))
  return { ok: payload.ok === true, message: text(payload.message), fields: campi(payload.fields), values: valori(payload.values), publicUrl: text(payload.publicUrl) }
}

export async function salvaImpostazioniSito(values: ValoriSito): Promise<EsitoSito & { values: ValoriSito }> {
  const raw = await apiPostJson<unknown>('/api/v1/ui/sito-studio/contenuti/impostazioni', values, { ok: false, message: 'Salvataggio non riuscito.' })
  return { ...esito(raw), values: valori(obj(raw).values) }
}

export async function getElencoSito(collection: RaccoltaSito): Promise<ElencoSito> {
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/sito-studio/contenuti/${collection}`, { ok: false }))
  const raccolta = obj(payload.collection)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    collection: { key: text(raccolta.key), label: text(raccolta.label), singular: text(raccolta.singular) },
    collections: list(payload.collections).map((raw) => ({ key: text(obj(raw).key), label: text(obj(raw).label), href: internal(obj(raw).href) })),
    fields: campi(payload.fields),
    defaults: valori(payload.defaults),
    items: list(payload.items).map((raw) => {
      const item = obj(raw)
      return { id: text(item.id), title: text(item.title), visible: item.visible === true, values: valori(item.values), editHref: internal(item.editHref) }
    }),
    needsOffice: payload.needsOffice === true,
  }
}

export type EsitoSito = { ok: boolean; message: string; errors: Record<string, string>; redirectHref: string }

function esito(raw: unknown): EsitoSito {
  const payload = obj(raw)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    errors: Object.fromEntries(Object.entries(obj(payload.errors)).map(([key, value]) => [key, text(value)])),
    redirectHref: internal(payload.redirect_href),
  }
}

export async function salvaSito(collection: RaccoltaSito, id: string, values: ValoriSito): Promise<EsitoSito> {
  const url = `/api/v1/ui/sito-studio/contenuti/${collection}${id ? `/${encodeURIComponent(id)}` : ''}`
  return esito(await apiPostJson<unknown>(url, values, { ok: false, message: 'Salvataggio non riuscito.' }))
}

export async function eliminaSito(collection: RaccoltaSito, id: string): Promise<EsitoSito> {
  return esito(await apiPostJson<unknown>(`/api/v1/ui/sito-studio/contenuti/${collection}/${encodeURIComponent(id)}/elimina`, {}, { ok: false, message: 'Eliminazione non riuscita.' }))
}

export async function creaBozzaArticolo(title: string, authorName: string): Promise<EsitoSito> {
  return esito(await apiPostJson<unknown>('/api/v1/ui/sito-studio/contenuti/articoli/bozza', { title, author_name: authorName }, { ok: false, message: 'Bozza non creata.' }))
}
