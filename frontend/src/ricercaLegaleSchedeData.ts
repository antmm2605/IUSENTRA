import { csrfHeader } from './api/csrf'
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

function external(value: unknown): string {
  const raw = text(value)
  return /^https?:\/\//.test(raw) ? raw : ''
}

function internal(value: unknown): string {
  const raw = text(value)
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : ''
}

export type RicercaLegaleScheda =
  | { mode: 'news'; key: string }
  | { mode: 'fonte'; key: string }
  | { mode: 'variazione'; key: string }

export function ricercaLegaleSchedaRoute(pathname: string): RicercaLegaleScheda | null {
  const path = pathname.replace(/\/+$/, '')
  const semplice = path.match(/^\/ricerca-legale\/(news|fonte)\/([^/]+)$/i)
  if (semplice) return { mode: semplice[1].toLowerCase() === 'news' ? 'news' : 'fonte', key: decodeURIComponent(semplice[2]) }
  const variazione = path.match(/^\/ricerca-legale\/daily\/update\/(\d+)\/diff$/i)
  if (variazione) return { mode: 'variazione', key: variazione[1] }
  return null
}

export type NewsScheda = {
  slug: string
  title: string
  type: string
  matter: string
  submatter: string
  summary: string
  content: string
  publishedAt: string
  origin: string
  sourceName: string
  sourceOfficial: boolean
  sourceHref: string
}

export type Variazione = {
  id: string
  title: string
  summary: string
  detectedAt: string
  status: string
  statusLabel: string
  severity: string
  applyMode: string
  detailHref: string
  approveAction: string
  oldSha256: string
  newSha256: string
  diff: string
}

export type FonteScheda = {
  id: string
  name: string
  area: string
  channel: string
  cadence: string
  warning: string
  freshness: string
  officialHref: string
  monitorHref: string
  formats: string[]
  fetcherNote: string
  impactAreas: string[]
  monitor: Record<'lastCheck' | 'status' | 'httpStatus' | 'version' | 'reference' | 'package' | 'packageStatus', string> & { changed: boolean }
  latest: { fetchedAt: string; href: string; sha256: string; etag: string; lastModified: string } | null
  downloadHref: string
  history: Array<{ fetchedAt: string; httpStatus: string; sha256: string; bytes: number; etag: string; lastModified: string }>
  updates: Variazione[]
  lastError: string
}

export type Esito<T> = { ok: boolean; message: string; item: T | null }

function variazione(raw: unknown): Variazione {
  const item = obj(raw)
  return {
    id: text(item.id),
    title: text(item.title),
    summary: text(item.summary),
    detectedAt: text(item.detectedAt),
    status: text(item.status),
    statusLabel: text(item.statusLabel),
    severity: text(item.severity),
    applyMode: text(item.applyMode),
    detailHref: internal(item.detailHref),
    approveAction: internal(item.approveAction),
    oldSha256: text(item.oldSha256),
    newSha256: text(item.newSha256),
    diff: text(item.diff),
  }
}

export async function getNewsScheda(slug: string): Promise<Esito<NewsScheda>> {
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/ricerca-legale/news/${encodeURIComponent(slug)}`, { ok: false }))
  const item = obj(payload.item)
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: payload.ok === true ? {
      slug: text(item.slug),
      title: text(item.title),
      type: text(item.type),
      matter: text(item.matter),
      submatter: text(item.submatter),
      summary: text(item.summary),
      content: text(item.content),
      publishedAt: text(item.publishedAt),
      origin: text(item.origin),
      sourceName: text(item.sourceName),
      sourceOfficial: item.sourceOfficial === true,
      sourceHref: external(item.sourceHref),
    } : null,
  }
}

export async function getFonteScheda(id: string): Promise<Esito<FonteScheda>> {
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/ricerca-legale/fonti/${encodeURIComponent(id)}`, { ok: false }))
  const item = obj(payload.item)
  const monitor = obj(item.monitor)
  const latest = item.latest ? obj(item.latest) : null
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    item: payload.ok === true ? {
      id: text(item.id),
      name: text(item.name),
      area: text(item.area),
      channel: text(item.channel),
      cadence: text(item.cadence),
      warning: text(item.warning),
      freshness: text(item.freshness),
      officialHref: external(item.officialHref),
      monitorHref: external(item.monitorHref),
      formats: list(item.formats).map(text).filter(Boolean),
      fetcherNote: text(item.fetcherNote),
      impactAreas: list(item.impactAreas).map(text).filter(Boolean),
      monitor: {
        lastCheck: text(monitor.lastCheck),
        status: text(monitor.status),
        httpStatus: text(monitor.httpStatus),
        changed: monitor.changed === true,
        version: text(monitor.version),
        reference: text(monitor.reference),
        package: text(monitor.package),
        packageStatus: text(monitor.packageStatus),
      },
      latest: latest ? {
        fetchedAt: text(latest.fetchedAt),
        href: external(latest.href),
        sha256: text(latest.sha256),
        etag: text(latest.etag),
        lastModified: text(latest.lastModified),
      } : null,
      downloadHref: internal(item.downloadHref),
      history: list(item.history).map((raw) => {
        const snap = obj(raw)
        return {
          fetchedAt: text(snap.fetchedAt),
          httpStatus: text(snap.httpStatus),
          sha256: text(snap.sha256),
          bytes: Number(snap.bytes) || 0,
          etag: text(snap.etag),
          lastModified: text(snap.lastModified),
        }
      }),
      updates: list(item.updates).map(variazione),
      lastError: text(item.lastError),
    } : null,
  }
}

export async function getVariazioneScheda(id: string): Promise<Esito<Variazione>> {
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/ricerca-legale/aggiornamenti/${encodeURIComponent(id)}`, { ok: false }))
  return { ok: payload.ok === true, message: text(payload.message), item: payload.ok === true ? variazione(payload.item) : null }
}

export async function approvaVariazione(action: string): Promise<{ ok: boolean; message: string }> {
  const payload = obj(await apiPostJson<unknown>(action, {}, { ok: false, message: 'Approvazione non riuscita.' }))
  return { ok: payload.ok === true, message: text(payload.message) }
}

export type ControlloGiornaliero = {
  ok: boolean
  running: boolean
  canRun: boolean
  runAction: string
  operations: Array<{ key: string; label: string; detail: string; action: string }>
  importAction: string
  lastRun: { startedAt: string; finishedAt: string; status: string } | null
  counts: Record<'sources' | 'updates' | 'pending' | 'applied' | 'errors', number>
  sources: Array<{ id: string; name: string; category: string; lastCheck: string; status: string; error: string; href: string }>
  updates: Variazione[]
}

export async function getControlloGiornaliero(): Promise<ControlloGiornaliero> {
  const payload = obj(await apiJson<unknown>('/api/v1/ui/ricerca-legale/controllo-giornaliero', { ok: false }))
  const counts = obj(payload.counts)
  const lastRun = payload.lastRun ? obj(payload.lastRun) : null
  return {
    ok: payload.ok === true,
    running: payload.running === true,
    canRun: payload.canRun === true,
    runAction: internal(payload.runAction),
    operations: list(payload.operations).map((raw) => {
      const row = obj(raw)
      return { key: text(row.key), label: text(row.label), detail: text(row.detail), action: internal(row.action) }
    }).filter((row) => row.action),
    importAction: internal(payload.importAction),
    lastRun: lastRun ? { startedAt: text(lastRun.startedAt), finishedAt: text(lastRun.finishedAt), status: text(lastRun.status) } : null,
    counts: {
      sources: Number(counts.sources) || 0,
      updates: Number(counts.updates) || 0,
      pending: Number(counts.pending) || 0,
      applied: Number(counts.applied) || 0,
      errors: Number(counts.errors) || 0,
    },
    sources: list(payload.sources).map((raw) => {
      const row = obj(raw)
      return { id: text(row.id), name: text(row.name), category: text(row.category), lastCheck: text(row.lastCheck), status: text(row.status), error: text(row.error), href: internal(row.href) }
    }),
    updates: list(payload.updates).map(variazione),
  }
}

export async function avviaControlloGiornaliero(action: string): Promise<{ ok: boolean; message: string }> {
  const payload = obj(await apiPostJson<unknown>(action, {}, { ok: false, message: 'Controllo non avviato.' }))
  return { ok: payload.ok === true, message: text(payload.message) }
}

/** Importa la pagina ufficiale del registro della mediazione (file HTML salvato dal sito del Ministero). */
export async function importaRegistroMediazione(action: string, file: File): Promise<{ ok: boolean; message: string }> {
  const body = new FormData()
  body.append('snapshot_file', file)
  try {
    const response = await fetch(action, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', ...csrfHeader() }, body })
    const payload = obj(await response.json().catch(() => ({})))
    return { ok: response.ok && payload.ok === true, message: text(payload.message) || 'Importazione non riuscita.' }
  } catch {
    return { ok: false, message: 'Importazione non riuscita: riprova fra poco.' }
  }
}
