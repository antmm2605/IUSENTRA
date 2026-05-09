import { apiJson, apiPostJson } from './lib/apiClient'
import { csrfHeader } from './api/csrf'
import { sanitizeDisplayText } from './displayText'

export type BuilderTone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

export type BuilderBlockItem = {
  title: string
  text: string
  image_url: string
  image_alt: string
  button_text: string
  button_url: string
}

export type BuilderBlock = {
  type: string
  title: string
  subtitle: string
  text: string
  image_url: string
  image_alt: string
  button_text: string
  button_url: string
  style_variant: string
  background: string
  spacing: string
  alignment: string
  animation: string
  visibility: { desktop: boolean; tablet: boolean; mobile: boolean }
  items: BuilderBlockItem[]
}

export type BuilderPage = {
  id: number
  title: string
  slug: string
  excerpt: string
  status: string
  statusLabel: string
  home: boolean
  showInMenu: boolean
  blocksCount: number
  updatedAt: string
  href: string
}

export type BuilderTemplate = { code: string; name: string; description: string; active: boolean }
export type BuilderPreset = { type: string; label: string; defaults: BuilderBlock }
export type BuilderAsset = { id: number; title: string; url: string; altText: string; category: string; createdAt: string }
export type BuilderRevision = { id: number; label: string; createdAt: string; createdBy: string }
export type BuilderValidationItem = { severity: 'error' | 'warning' | 'info'; message: string }
export type BuilderValidationGroup = { id: string; label: string; items: BuilderValidationItem[] }

export type BuilderTheme = {
  templateCode: string
  tokens: Record<string, string>
  typography: Record<string, string>
  layout: Record<string, string>
  effects: Record<string, string>
}

export type BuilderSite = {
  id: number
  studioName: string
  siteName: string
  title: string
  description: string
  claim: string
  publicSlug: string
  published: boolean
  active: boolean
  themeTemplate: string
  updatedAt: string
  publicUrl: string
}

export type SitoStudioBuilderData = {
  ok: boolean
  message: string
  generatedAt: string
  site: BuilderSite
  theme: BuilderTheme
  templates: BuilderTemplate[]
  blockPresets: BuilderPreset[]
  pages: BuilderPage[]
  activePage: BuilderPage
  activePageId: number
  activeBlocks: BuilderBlock[]
  assets: BuilderAsset[]
  revisions: BuilderRevision[]
  validation: { groups: BuilderValidationGroup[]; generatedAt: string; issues: number; blocking: number }
  publicUrl: string
  activePreviewUrl: string
  previewUrl: string
}

export type BuilderMutation = {
  ok: boolean
  message: string
  payload?: SitoStudioBuilderData
  blocks?: BuilderBlock[]
  validation?: SitoStudioBuilderData['validation']
  asset?: BuilderAsset
  assets?: BuilderAsset[]
}

const emptyBlock: BuilderBlock = {
  type: 'rich_text',
  title: '',
  subtitle: '',
  text: '',
  image_url: '',
  image_alt: '',
  button_text: '',
  button_url: '',
  style_variant: 'default',
  background: 'default',
  spacing: 'standard',
  alignment: 'start',
  animation: 'fade-up',
  visibility: { desktop: true, tablet: true, mobile: true },
  items: [],
}

export const emptySitoStudioBuilderData: SitoStudioBuilderData = {
  ok: false,
  message: '',
  generatedAt: '',
  site: {
    id: 0,
    studioName: '',
    siteName: '',
    title: '',
    description: '',
    claim: '',
    publicSlug: '',
    published: false,
    active: false,
    themeTemplate: '',
    updatedAt: '',
    publicUrl: '',
  },
  theme: { templateCode: '', tokens: {}, typography: {}, layout: {}, effects: {} },
  templates: [],
  blockPresets: [],
  pages: [],
  activePage: { id: 0, title: '', slug: '', excerpt: '', status: '', statusLabel: '', home: false, showInMenu: false, blocksCount: 0, updatedAt: '', href: '' },
  activePageId: 0,
  activeBlocks: [],
  assets: [],
  revisions: [],
  validation: { groups: [], generatedAt: '', issues: 0, blocking: 0 },
  publicUrl: '',
  activePreviewUrl: '',
  previewUrl: '',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function recordTextMap(value: unknown): Record<string, string> {
  return Object.fromEntries(Object.entries(asRecord(value)).map(([key, entry]) => [key, text(entry)]))
}

function normaliseItem(raw: unknown): BuilderBlockItem {
  const item = asRecord(raw)
  return {
    title: display(item.title),
    text: display(item.text),
    image_url: text(item.image_url),
    image_alt: display(item.image_alt),
    button_text: display(item.button_text),
    button_url: text(item.button_url),
  }
}

export function normaliseBlock(raw: unknown): BuilderBlock {
  const item = asRecord(raw)
  const visibility = asRecord(item.visibility)
  return {
    ...emptyBlock,
    type: text(item.type, 'rich_text'),
    title: display(item.title),
    subtitle: display(item.subtitle),
    text: display(item.text),
    image_url: text(item.image_url),
    image_alt: display(item.image_alt),
    button_text: display(item.button_text),
    button_url: text(item.button_url),
    style_variant: text(item.style_variant, 'default'),
    background: text(item.background, 'default'),
    spacing: text(item.spacing, 'standard'),
    alignment: text(item.alignment, 'start'),
    animation: text(item.animation, 'fade-up'),
    visibility: {
      desktop: visibility.desktop === undefined ? true : bool(visibility.desktop),
      tablet: visibility.tablet === undefined ? true : bool(visibility.tablet),
      mobile: visibility.mobile === undefined ? true : bool(visibility.mobile),
    },
    items: list(item.items).map(normaliseItem),
  }
}

function normalisePage(raw: unknown): BuilderPage {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    title: display(item.title) || 'Pagina senza titolo',
    slug: text(item.slug),
    excerpt: display(item.excerpt),
    status: text(item.status),
    statusLabel: display(item.statusLabel) || 'Bozza',
    home: bool(item.home),
    showInMenu: bool(item.showInMenu),
    blocksCount: number(item.blocksCount),
    updatedAt: text(item.updatedAt),
    href: text(item.href),
  }
}

function normaliseSeverity(value: unknown): BuilderValidationItem['severity'] {
  const clean = text(value).toLowerCase()
  return clean === 'error' || clean === 'warning' || clean === 'info' ? clean : 'info'
}

function normaliseValidation(raw: unknown): SitoStudioBuilderData['validation'] {
  const item = asRecord(raw)
  return {
    generatedAt: text(item.generatedAt),
    issues: number(item.issues),
    blocking: number(item.blocking),
    groups: list(item.groups).map((entry) => {
      const group = asRecord(entry)
      return {
        id: text(group.id),
        label: display(group.label) || 'Controllo',
        items: list(group.items).map((row) => {
          const issue = asRecord(row)
          return { severity: normaliseSeverity(issue.severity), message: display(issue.message) || 'Controllo disponibile.' }
        }),
      }
    }),
  }
}

export function blockLabel(blockType: string, presets: BuilderPreset[]): string {
  return presets.find((item) => item.type === blockType)?.label || blockType.replace(/[_-]+/g, ' ')
}

export function optionLabel(value: string): string {
  return ({
    default: 'Standard',
    muted: 'Neutro',
    dark: 'Scuro istituzionale',
    accent: 'Accento',
    compact: 'Compatta',
    standard: 'Normale',
    wide: 'Ampia',
    start: 'Sinistra',
    center: 'Centro',
    end: 'Destra',
    'fade-up': 'Comparsa morbida',
    'soft-reveal': 'Rivelazione discreta',
    none: 'Nessuna',
    desktop: 'Desktop',
    tablet: 'Tablet',
    mobile: 'Mobile',
    system_professional: 'Sistema professionale',
    serif_elegant: 'Serif elegante',
    modern_sans: 'Sans moderna',
    editorial_legal: 'Editoriale legale',
    compact_business: 'Compatto business',
  } as Record<string, string>)[value] || value.replace(/[_-]+/g, ' ')
}

export function normaliseBuilder(raw: unknown): SitoStudioBuilderData {
  const page = asRecord(raw)
  const site = asRecord(page.site)
  const theme = asRecord(page.theme)
  return {
    ...emptySitoStudioBuilderData,
    ok: bool(page.ok),
    message: display(page.message),
    generatedAt: text(page.generated_at),
    site: {
      id: number(site.id),
      studioName: display(site.studioName),
      siteName: display(site.siteName),
      title: display(site.title),
      description: display(site.description),
      claim: display(site.claim),
      publicSlug: text(site.publicSlug),
      published: bool(site.published),
      active: bool(site.active),
      themeTemplate: text(site.themeTemplate),
      updatedAt: text(site.updatedAt),
      publicUrl: text(site.publicUrl),
    },
    theme: {
      templateCode: text(theme.templateCode),
      tokens: recordTextMap(theme.tokens),
      typography: recordTextMap(theme.typography),
      layout: recordTextMap(theme.layout),
      effects: recordTextMap(theme.effects),
    },
    templates: list(page.templates).map((entry) => {
      const item = asRecord(entry)
      return { code: text(item.code), name: display(item.name), description: display(item.description), active: bool(item.active) }
    }),
    blockPresets: list(page.blockPresets).map((entry) => {
      const item = asRecord(entry)
      return { type: text(item.type), label: display(item.label) || 'Blocco', defaults: normaliseBlock(item.defaults) }
    }).filter((item) => item.type),
    pages: list(page.pages).map(normalisePage).filter((item) => item.id),
    activePage: normalisePage(page.activePage),
    activePageId: number(page.activePageId),
    activeBlocks: list(page.activeBlocks).map(normaliseBlock),
    assets: list(page.assets).map(normaliseAsset).filter((item) => item.id || item.url),
    revisions: list(page.revisions).map((entry) => {
      const item = asRecord(entry)
      return { id: number(item.id), label: display(item.label) || 'Revisione', createdAt: text(item.createdAt), createdBy: display(item.createdBy) }
    }).filter((item) => item.id),
    validation: normaliseValidation(page.validation),
    publicUrl: text(page.publicUrl),
    activePreviewUrl: text(page.activePreviewUrl),
    previewUrl: text(page.previewUrl),
  }
}

function normaliseAsset(raw: unknown): BuilderAsset {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    title: display(item.title) || 'Immagine',
    url: text(item.url),
    altText: display(item.altText),
    category: display(item.category),
    createdAt: text(item.createdAt),
  }
}

function normaliseMutation(raw: unknown): BuilderMutation {
  const item = asRecord(raw)
  return {
    ok: bool(item.ok),
    message: display(item.message) || (bool(item.ok) ? 'Operazione completata.' : 'Operazione non completata.'),
    payload: item.payload ? normaliseBuilder(item.payload) : undefined,
    blocks: list(item.blocks).map(normaliseBlock),
    validation: item.validation ? normaliseValidation(item.validation) : undefined,
    asset: item.asset ? normaliseAsset(item.asset) : undefined,
    assets: list(item.assets).map(normaliseAsset),
  }
}

export function getSitoStudioBuilder(pageId?: number, signal?: AbortSignal): Promise<SitoStudioBuilderData> {
  const suffix = pageId ? `?page_id=${encodeURIComponent(String(pageId))}` : ''
  return apiJson<unknown>(`/api/v1/ui/sito-studio/builder${suffix}`, emptySitoStudioBuilderData, { signal }).then(normaliseBuilder)
}

export function postBuilderJson(url: string, payload: Record<string, unknown>): Promise<BuilderMutation> {
  return apiPostJson<unknown>(url, payload, { ok: false, message: 'Operazione non completata.' }).then(normaliseMutation)
}

export function deleteBuilderPage(pageId: number): Promise<BuilderMutation> {
  return apiPostJson<unknown>(
    `/api/v1/ui/sito-studio/builder/pages/${pageId}`,
    {},
    { ok: false, message: 'Rimozione pagina non completata.' },
    { method: 'DELETE' },
  ).then(normaliseMutation)
}

export function saveBuilderBlocks(pageId: number, blocks: BuilderBlock[]): Promise<BuilderMutation> {
  return postBuilderJson(`/api/v1/ui/sito-studio/builder/pages/${pageId}/blocks`, { blocks })
}

export function publishBuilderBlocks(pageId: number, blocks: BuilderBlock[]): Promise<BuilderMutation> {
  return postBuilderJson(`/api/v1/ui/sito-studio/builder/pages/${pageId}/publish`, { blocks })
}

export function uploadBuilderAsset(file: File, values: { altText: string; title: string; category: string }): Promise<BuilderMutation> {
  const body = new FormData()
  body.append('file', file)
  body.append('alt_text', values.altText)
  body.append('title', values.title)
  body.append('category', values.category)
  return fetch('/api/v1/ui/sito-studio/builder/assets/upload', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...csrfHeader() },
    body,
  }).then((response) => response.json()).then(normaliseMutation)
}
