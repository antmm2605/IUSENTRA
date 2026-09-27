import { apiJson } from './lib/apiClient'

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

function href(value: unknown, external = false): string {
  const raw = text(value)
  if (raw.startsWith('/') && !raw.startsWith('//')) return raw
  return external && /^https?:\/\//.test(raw) ? raw : ''
}

export type Tono = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

function tono(value: unknown): Tono {
  const raw = text(value)
  return (['success', 'warning', 'danger', 'info'].includes(raw) ? raw : 'neutral') as Tono
}

export type Sezione =
  | { kind: 'metrics'; title: string; items: Array<{ label: string; value: string; note: string; tone: Tono }> }
  | { kind: 'status'; title: string; subtitle: string; items: Array<{ title: string; summary: string; detail: string; tone: Tono; statusLabel: string }> }
  | { kind: 'table'; title: string; subtitle: string; empty: string; columns: Array<{ key: string; label: string }>; rows: Array<{ cells: Record<string, string>; href: string; external: boolean; tone: Tono }> }
  | { kind: 'facts'; title: string; items: Array<{ label: string; value: string }> }
  | { kind: 'notes'; title: string; tone: Tono; items: string[] }
  | { kind: 'shortcuts'; title: string; items: Array<{ label: string; detail: string; href: string }> }

export type PaginaPiattaforma = {
  ok: boolean
  message: string
  page: string
  title: string
  subtitle: string
  user: string
  menu: Array<{ key: string; label: string; href: string }>
  links: Array<{ label: string; href: string; tone: Tono; external: boolean }>
  filter: { name: string; label: string; value: string; options: Array<{ value: string; label: string }> } | null
  sections: Sezione[]
}

function sezione(raw: unknown): Sezione | null {
  const s = obj(raw)
  const title = text(s.title)
  switch (text(s.kind)) {
    case 'metrics':
      return { kind: 'metrics', title, items: list(s.items).map((i) => ({ label: text(obj(i).label), value: text(obj(i).value), note: text(obj(i).note), tone: tono(obj(i).tone) })) }
    case 'status':
      return { kind: 'status', title, subtitle: text(s.subtitle), items: list(s.items).map((i) => ({ title: text(obj(i).title), summary: text(obj(i).summary), detail: text(obj(i).detail), tone: tono(obj(i).tone), statusLabel: text(obj(i).statusLabel) })) }
    case 'table':
      return {
        kind: 'table',
        title,
        subtitle: text(s.subtitle),
        empty: text(s.empty) || 'Nessun dato.',
        columns: list(s.columns).map((c) => ({ key: text(obj(c).key), label: text(obj(c).label) })),
        rows: list(s.rows).map((r) => {
          const row = obj(r)
          const external = row.external === true
          return { cells: Object.fromEntries(Object.entries(obj(row.cells)).map(([k, v]) => [k, text(v)])), href: href(row.href, external), external, tone: tono(row.tone) }
        }),
      }
    case 'facts':
      return { kind: 'facts', title, items: list(s.items).map((i) => ({ label: text(obj(i).label), value: text(obj(i).value) })) }
    case 'shortcuts':
      return { kind: 'shortcuts', title, items: list(s.items).map((i) => ({ label: text(obj(i).label), detail: text(obj(i).detail), href: href(obj(i).href) })).filter((i) => i.href) }
    case 'notes':
      return { kind: 'notes', title, tone: tono(s.tone), items: list(s.items).map(text).filter(Boolean) }
    default:
      return null
  }
}

export async function getPaginaPiattaforma(pagina: string, search: string): Promise<PaginaPiattaforma> {
  const payload = obj(await apiJson<unknown>(`/api/v1/ui/piattaforma/${encodeURIComponent(pagina)}${search}`, { ok: false }))
  const filter = payload.filter ? obj(payload.filter) : null
  return {
    ok: payload.ok === true,
    message: text(payload.message),
    page: text(payload.page),
    title: text(payload.title),
    subtitle: text(payload.subtitle),
    user: text(payload.user),
    menu: list(payload.menu).map((m) => ({ key: text(obj(m).key), label: text(obj(m).label), href: href(obj(m).href) })),
    links: list(payload.links).map((l) => ({ label: text(obj(l).label), href: href(obj(l).href, true), tone: tono(obj(l).tone), external: obj(l).external === true })),
    filter: filter ? { name: text(filter.name), label: text(filter.label), value: text(filter.value), options: list(filter.options).map((o) => ({ value: text(obj(o).value), label: text(obj(o).label) })) } : null,
    sections: list(payload.sections).map(sezione).filter((s): s is Sezione => s !== null),
  }
}
