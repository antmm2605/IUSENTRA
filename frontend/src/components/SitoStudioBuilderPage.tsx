import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent, type FormEvent, type MouseEvent as ReactMouseEvent, type ReactNode, type RefObject } from 'react'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Bot,
  Check,
  CheckCircle2,
  Copy,
  Eye,
  EyeOff,
  FilePlus2,
  FileText,
  Globe2,
  Home,
  ImagePlus,
  Italic,
  Layers3,
  Link2,
  Mail,
  MapPin,
  Monitor,
  Palette,
  PanelBottom,
  PanelTop,
  Phone,
  Plus,
  RefreshCw,
  Rocket,
  Save,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Smartphone,
  Subscript,
  Superscript,
  Tablet,
  Trash2,
  Type,
  Underline,
  UploadCloud,
  WandSparkles,
  type LucideIcon,
} from 'lucide-react'
import {
  deleteBuilderAsset,
  deleteBuilderPage,
  emptySitoStudioBuilderData,
  getSitoStudioBuilder,
  normaliseBlock,
  postBuilderJson,
  publishBuilderBlocks,
  saveBuilderBlocks,
  uploadBuilderAsset,
  type BuilderAsset,
  type BuilderBlock,
  type BuilderBlockItem,
  type BuilderPage,
  type BuilderPreset,
  type BuilderSite,
  type BuilderTheme,
  type SitoStudioBuilderData,
} from '../sitoStudioBuilderData'
import { blockLabel, optionLabel } from '../sitoStudioBuilderData'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import './SitoStudioBuilderPage.css'
import './SitoStudioBuilderPage.panels.css'

type PreviewSize = 'desktop' | 'tablet' | 'mobile'
type BuilderTabId = 'setup' | 'pagine' | 'blocchi' | 'contenuti' | 'aspetto' | 'media' | 'seo' | 'privacy' | 'ai' | 'pubblica'
type TextFieldKey = 'title' | 'subtitle' | 'text'
type RichTextFormat = 'italic' | 'underline' | 'sup' | 'sub'

type SiteDraft = {
  siteName: string
  siteTitle: string
  siteDescription: string
  claim: string
  contactEmail: string
  contactPhone: string
  whatsappNumber: string
  address: string
  city: string
  province: string
  zipCode: string
  publicSlug: string
  logoUrl: string
  faviconUrl: string
  footerText: string
  privacyUrl: string
  cookiePolicyUrl: string
  accessibilityStatementUrl: string
  legalDisclaimer: string
  cookieBannerEnabled: boolean
  analyticsEnabled: boolean
}

type PageDraft = {
  title: string
  slug: string
  excerpt: string
  seoTitle: string
  seoDescription: string
  showInMenu: boolean
  home: boolean
}

type BuilderMutationResult = {
  ok: boolean
  message: string
  payload?: SitoStudioBuilderData
  blocks?: BuilderBlock[]
  validation?: SitoStudioBuilderData['validation']
  asset?: BuilderAsset
  assets?: BuilderAsset[]
}

const tabs: Array<{ id: BuilderTabId; label: string; short: string; icon: LucideIcon; description: string }> = [
  { id: 'setup', label: 'Setup', short: 'Setup', icon: Settings2, description: 'Dati studio, contatti e avvio guidato.' },
  { id: 'pagine', label: 'Pagine', short: 'Pagine', icon: FileText, description: 'Pagine, indirizzi e menu del sito.' },
  { id: 'blocchi', label: 'Blocchi', short: 'Blocchi', icon: Layers3, description: 'Struttura della pagina selezionata.' },
  { id: 'contenuti', label: 'Contenuti', short: 'Testi', icon: Type, description: 'Testi, pulsanti, bio e FAQ.' },
  { id: 'aspetto', label: 'Aspetto', short: 'Aspetto', icon: Palette, description: 'Template, colori, font, header e footer.' },
  { id: 'media', label: 'Media', short: 'Media', icon: ImagePlus, description: 'Logo, immagini, documenti e testi alternativi.' },
  { id: 'seo', label: 'SEO', short: 'SEO', icon: Search, description: 'Titoli, descrizioni, slug e anteprime.' },
  { id: 'privacy', label: 'Privacy e conformita', short: 'Privacy', icon: ShieldCheck, description: 'Privacy, cookie, deontologia e accessibilita.' },
  { id: 'ai', label: 'AI', short: 'AI', icon: Bot, description: 'Azioni assistite sempre governate in modo sicuro.' },
  { id: 'pubblica', label: 'Pubblica', short: 'Pubblica', icon: Rocket, description: 'Controlli finali, URL pubblico e versioni.' },
]

const starterPages = ['Home', 'Chi siamo', 'Aree di attivita', 'Professionisti', 'Contatti', 'Blog / News', 'Privacy', 'Cookie', 'Note legali']
const blockedClaims = ['Risultato garantito', 'Vinceremo la causa', 'Successo assicurato', 'Miglior avvocato', 'Leader assoluto', 'Garanzia di vittoria']
const fontOptions = [
  'system_professional',
  'serif_elegant',
  'modern_sans',
  'editorial_legal',
  'compact_business',
  'humanist_sans',
  'classic_serif',
  'garamond_legal',
  'geometric_sans',
  'slab_editorial',
  'high_readability',
]
const fontStacks: Record<string, { heading: string; body: string }> = {
  system_professional: { heading: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", body: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
  serif_elegant: { heading: "Georgia, 'Times New Roman', serif", body: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" },
  modern_sans: { heading: "'Aptos Display', 'Segoe UI', sans-serif", body: "'Aptos', 'Segoe UI', sans-serif" },
  editorial_legal: { heading: "'Palatino Linotype', Palatino, Georgia, serif", body: "Georgia, 'Times New Roman', serif" },
  compact_business: { heading: "'Segoe UI Semibold', 'Segoe UI', sans-serif", body: "'Segoe UI', sans-serif" },
  humanist_sans: { heading: "'Trebuchet MS', 'Segoe UI', sans-serif", body: "'Trebuchet MS', 'Segoe UI', sans-serif" },
  classic_serif: { heading: "Georgia, 'Times New Roman', serif", body: "Georgia, 'Times New Roman', serif" },
  garamond_legal: { heading: "Garamond, 'Palatino Linotype', Georgia, serif", body: "Garamond, 'Palatino Linotype', Georgia, serif" },
  geometric_sans: { heading: "Avenir, Montserrat, 'Segoe UI', sans-serif", body: "Avenir, Montserrat, 'Segoe UI', sans-serif" },
  slab_editorial: { heading: "Rockwell, 'Roboto Slab', Georgia, serif", body: "'Segoe UI', sans-serif" },
  high_readability: { heading: "Verdana, Geneva, sans-serif", body: "Verdana, Geneva, sans-serif" },
}
const textSizeOptions = ['14px', '15px', '16px', '17px', '18px']
const headingSizeOptions = ['28px', '32px', '34px', '38px', '42px', '48px']
const sectionTitleSizeOptions = ['22px', '24px', '26px', '30px', '34px']
const lineHeightOptions = ['1.35', '1.5', '1.65', '1.8']
const sectionSpacingOptions = ['18px', '24px', '28px', '36px', '44px']
const cardPaddingOptions = ['14px', '18px', '20px', '24px', '30px']
const buttonRadiusOptions = ['6px', '10px', '16px', '999px']
const shadowOptions = ['none', 'soft', 'deep', 'layered']
const animationOptions = ['none', 'fade-up', 'soft-reveal', 'scale-in', 'slide-up']
const headerEffectOptions = ['none', 'true', 'transparent', 'compact']
const sectionDividerOptions = ['none', 'subtle', 'accent-line', 'boxed']
const alignmentOptions = ['start', 'center', 'end', 'justify']
const templateLabels = ['Classico istituzionale', 'Boutique legale', 'Moderno minimale', 'Penale', 'Famiglia e minori', 'Impresa e contratti', 'Tributario', 'Immobiliare']
const colorKeys = [
  ['primary', 'Principale'],
  ['secondary', 'Secondario'],
  ['accent', 'Accento'],
  ['bg', 'Sfondo'],
] as const
const colorFallbacks = { primary: '#1f3f6d', secondary: '#0f1726', accent: '#b38b55', bg: '#f6f8fb' } as const

function initialPageId(): number | undefined {
  const value = new URLSearchParams(window.location.search).get('page_id')
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined
}

function cloneBlock(block: BuilderBlock): BuilderBlock {
  return normaliseBlock(JSON.parse(JSON.stringify(block)))
}

function clampIndex(index: number, blocks: BuilderBlock[]): number {
  if (!blocks.length) return -1
  return Math.max(0, Math.min(index, blocks.length - 1))
}

function siteDraftFrom(site: BuilderSite): SiteDraft {
  return {
    siteName: site.siteName,
    siteTitle: site.title,
    siteDescription: site.description,
    claim: site.claim,
    contactEmail: site.contactEmail,
    contactPhone: site.contactPhone,
    whatsappNumber: site.whatsappNumber,
    address: site.address,
    city: site.city,
    province: site.province,
    zipCode: site.zipCode,
    publicSlug: site.publicSlug,
    logoUrl: site.logoUrl,
    faviconUrl: site.faviconUrl,
    footerText: site.footerText,
    privacyUrl: site.privacyUrl,
    cookiePolicyUrl: site.cookiePolicyUrl,
    accessibilityStatementUrl: site.accessibilityStatementUrl,
    legalDisclaimer: site.legalDisclaimer,
    cookieBannerEnabled: site.cookieBannerEnabled,
    analyticsEnabled: site.analyticsEnabled,
  }
}

function pageDraftFrom(page: BuilderPage): PageDraft {
  return {
    title: page.title,
    slug: page.slug,
    excerpt: page.excerpt,
    seoTitle: page.seoTitle || page.title,
    seoDescription: page.seoDescription || page.excerpt,
    showInMenu: page.showInMenu,
    home: page.home,
  }
}

function formatDate(value: string): string {
  if (!value) return 'Non indicata'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function publicationScore(validation: SitoStudioBuilderData['validation']): number {
  const warnings = validation.groups.flatMap((group) => group.items).filter((item) => item.severity === 'warning').length
  const info = validation.groups.flatMap((group) => group.items).filter((item) => item.severity === 'info').length
  return Math.max(0, Math.min(100, 100 - validation.blocking * 22 - warnings * 7 - info * 2))
}

function compactUrl(value: string, fallback: string): string {
  const clean = value || fallback
  return clean.replace(/^https?:\/\//, '').replace(/\/$/, '')
}

function setThemeValue(theme: BuilderTheme, group: 'tokens' | 'typography' | 'layout' | 'effects', key: string, value: string): BuilderTheme {
  const target = theme[group]
  return { ...theme, [group]: { ...target, [key]: value } }
}

function formatRichText(value: string, format: RichTextFormat): string {
  const markers = {
    italic: ['<em>', '</em>'],
    underline: ['<u>', '</u>'],
    sup: ['<sup>', '</sup>'],
    sub: ['<sub>', '</sub>'],
  }[format]
  const text = value.trim()
  return text ? `${markers[0]}${text}${markers[1]}` : value
}

function richNodes(value: string): ReactNode {
  const pieces = String(value || '').split(/(<\/?(?:em|u|sup|sub)>)/gi)
  const stack: Array<'em' | 'u' | 'sup' | 'sub'> = []
  return pieces.map((piece, index) => {
    const tag = piece.match(/^<\/?(em|u|sup|sub)>$/i)?.[1]?.toLowerCase() as 'em' | 'u' | 'sup' | 'sub' | undefined
    if (tag) {
      if (piece.startsWith('</')) {
        const stackIndex = stack.lastIndexOf(tag)
        if (stackIndex >= 0) stack.splice(stackIndex, 1)
      } else {
        stack.push(tag)
      }
      return null
    }
    let node: ReactNode = piece
    stack.slice().reverse().forEach((entry) => {
      if (entry === 'em') node = <em key={`em-${index}`}>{node}</em>
      if (entry === 'u') node = <u key={`u-${index}`}>{node}</u>
      if (entry === 'sup') node = <sup key={`sup-${index}`}>{node}</sup>
      if (entry === 'sub') node = <sub key={`sub-${index}`}>{node}</sub>
    })
    return <span key={`${piece}-${index}`}>{node}</span>
  })
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  area = false,
  rows = 3,
  type = 'text',
  inputRef,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  area?: boolean
  rows?: number
  type?: string
  inputRef?: RefObject<HTMLInputElement | HTMLTextAreaElement | null>
}) {
  return (
    <label className="iu-builder-field">
      <span>{label}</span>
      {area ? (
        <textarea ref={inputRef as RefObject<HTMLTextAreaElement | null> | undefined} value={value} rows={rows} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input ref={inputRef as RefObject<HTMLInputElement | null> | undefined} type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  )
}

function SelectField({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return (
    <label className="iu-builder-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {values.map((entry) => <option value={entry} key={entry}>{optionLabel(entry)}</option>)}
      </select>
    </label>
  )
}

function ButtonGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: Array<{ value: string; label: string; icon?: LucideIcon }>
  onChange: (value: string) => void
}) {
  return (
    <div className="iu-builder-button-group" aria-label={label}>
      <span>{label}</span>
      <div>
        {options.map((option) => {
          const Icon = option.icon
          return (
            <button className={value === option.value ? 'is-active' : ''} type="button" onClick={() => onChange(option.value)} key={option.value} title={option.label}>
              {Icon ? <Icon size={14} aria-hidden="true" /> : null}
              <small>{option.label}</small>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function RichTextToolbar({
  field,
  label,
  onFormat,
}: {
  field: TextFieldKey
  label: string
  onFormat: (field: TextFieldKey, format: RichTextFormat) => void
}) {
  const actions: Array<{ format: RichTextFormat; label: string; icon: LucideIcon }> = [
    { format: 'italic', label: 'Corsivo', icon: Italic },
    { format: 'underline', label: 'Sottolineato', icon: Underline },
    { format: 'sup', label: 'Apice', icon: Superscript },
    { format: 'sub', label: 'Pedice', icon: Subscript },
  ]

  return (
    <div className="iu-builder-format-toolbar" aria-label={`Formattazione ${label}`}>
      <span>{label}</span>
      {actions.map(({ format, label: actionLabel, icon: Icon }) => (
        <button type="button" onClick={() => onFormat(field, format)} title={`${actionLabel} ${label.toLowerCase()}`} key={`${field}-${format}`}>
          <Icon size={14} />
        </button>
      ))}
    </div>
  )
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="iu-builder-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span aria-hidden="true" />
      <strong>{label}</strong>
    </label>
  )
}

function SectionTitle({ icon: Icon, title, subtitle }: { icon: LucideIcon; title: string; subtitle?: string }) {
  return (
    <div className="iu-builder-section-title">
      <Icon size={17} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        {subtitle ? <span>{subtitle}</span> : null}
      </div>
    </div>
  )
}

function ValidationList({ validation }: { validation: SitoStudioBuilderData['validation'] }) {
  return (
    <div className="iu-builder-checklist">
      {validation.groups.map((group) => (
        <article key={group.id}>
          <strong>{group.label}</strong>
          {group.items.length ? group.items.slice(0, 3).map((item, index) => (
            <span className={`is-${item.severity}`} key={`${group.id}-${index}`}>
              {item.severity === 'error' ? <AlertTriangle size={14} /> : item.severity === 'warning' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
              {item.message}
            </span>
          )) : (
            <span className="is-ok"><CheckCircle2 size={14} /> Nessun rilievo immediato.</span>
          )}
        </article>
      ))}
    </div>
  )
}

function blockTitle(block: BuilderBlock, presets: BuilderPreset[]): string {
  return block.title || blockLabel(block.type, presets)
}

function blockText(block: BuilderBlock): string {
  return block.subtitle || block.text
}

function visibleForSize(block: BuilderBlock, previewSize: PreviewSize): boolean {
  return block.visibility?.[previewSize] !== false
}

function fileTitle(fileName: string): string {
  return fileName
    .replace(/\.[^.]+$/, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function BuilderLivePreview({
  site,
  page,
  pages,
  blocks,
  presets,
  theme,
  previewSize,
  score,
  dirty,
  onPreviewSize,
}: {
  site: SiteDraft
  page: PageDraft
  pages: BuilderPage[]
  blocks: BuilderBlock[]
  presets: BuilderPreset[]
  theme: BuilderTheme
  previewSize: PreviewSize
  score: number
  dirty: boolean
  onPreviewSize: (size: PreviewSize) => void
}) {
  const visibleBlocks = blocks.filter((block) => visibleForSize(block, previewSize))
  const hero = visibleBlocks.find((block) => block.type.includes('hero')) || visibleBlocks[0]
  const footerBlock = [...visibleBlocks].reverse().find((block) => block.type.includes('footer'))
  const contentBlocks = visibleBlocks.filter((block) => block !== hero && block !== footerBlock)
  const visiblePages = pages.filter((entry) => entry.showInMenu).slice(0, 5)
  const primary = theme.tokens.primary || '#1f3b63'
  const secondary = theme.tokens.secondary || '#0f1726'
  const accent = theme.tokens.accent || '#b38b55'
  const background = theme.tokens.bg || '#f6f8fb'
  const surface = theme.tokens.surface || '#ffffff'
  const text = theme.tokens.text || '#101828'
  const fontPreset = theme.typography.font_preset || 'system_professional'
  const fonts = fontStacks[fontPreset] || fontStacks.system_professional
  const headingSize = theme.typography.heading_size || '34px'
  const sectionTitleSize = theme.typography.section_title_size || '26px'
  const textSize = theme.typography.font_size_base || '16px'
  const lineHeight = theme.typography.line_height || '1.65'
  const sectionSpacing = theme.layout.section_spacing || '28px'
  const cardPadding = theme.layout.card_padding || '20px'
  const buttonRadius = theme.layout.button_radius || '999px'
  const pageTitle = hero?.title || page.title || site.siteName || 'Sito Studio'
  const pageSubtitle = hero?.subtitle || hero?.text || site.claim || site.siteDescription
  const buttonText = hero?.button_text
  const contactLine = [site.address, site.city, site.province].filter(Boolean).join(' - ')
  const footerText = footerBlock ? blockText(footerBlock) : site.footerText
  const footerTitle = footerBlock ? blockTitle(footerBlock, presets) : site.siteName || 'Studio legale'
  const effectClass = [
    theme.effects.animation && theme.effects.animation !== 'none' ? 'has-soft-animation' : '',
    theme.effects.animation === 'scale-in' ? 'has-scale-animation' : '',
    theme.effects.animation === 'slide-up' ? 'has-slide-animation' : '',
    theme.effects.card_shadow && theme.effects.card_shadow !== 'none' ? `has-shadow-${theme.effects.card_shadow}` : '',
    theme.effects.fixed_header === 'true' ? 'has-fixed-header' : '',
    theme.effects.fixed_header === 'transparent' ? 'has-transparent-header' : '',
    theme.effects.fixed_header === 'compact' ? 'has-compact-header' : '',
    theme.effects.button_hover === 'true' ? 'has-button-hover' : '',
    theme.effects.section_divider && theme.effects.section_divider !== 'none' ? `has-divider-${theme.effects.section_divider}` : '',
    theme.effects.image_treatment && theme.effects.image_treatment !== 'none' ? `has-image-${theme.effects.image_treatment}` : '',
  ].filter(Boolean).join(' ')
  const renderCards = (block: BuilderBlock, fallbackText: string) => {
    const items = block.items.length ? block.items : [{
      title: blockTitle(block, presets),
      text: blockText(block) || fallbackText,
      image_url: block.image_url,
      image_alt: block.image_alt,
      button_text: block.button_text,
      button_url: block.button_url,
    }]
    return (
      <div className="iu-builder-public-cards">
        {items.filter((item) => item.title || item.text || item.image_url).map((item, index) => (
          <article key={`${item.title}-${index}`}>
            {item.image_url ? <img src={item.image_url} alt={item.image_alt || item.title || 'Immagine sezione'} /> : null}
            <strong>{richNodes(item.title || 'Elemento da completare')}</strong>
            <span>{richNodes(item.text || fallbackText)}</span>
            {item.button_text ? <em>{item.button_text}</em> : null}
          </article>
        ))}
      </div>
    )
  }
  const renderContentBlock = (block: BuilderBlock, index: number) => {
    const title = blockTitle(block, presets)
    const textValue = blockText(block)
    const type = block.type.toLowerCase()
    const alignmentClass = `is-align-${block.alignment || 'start'}`
    if (type.includes('faq')) {
      const items = block.items.length ? block.items : [{ title, text: textValue || 'Aggiungi risposta nella scheda Contenuti.', image_url: '', image_alt: '', button_text: '', button_url: '' }]
      return (
        <section className={`iu-builder-public-section ${alignmentClass}`} key={`${block.type}-${index}`}>
          <h2>{richNodes(title)}</h2>
          <div className="iu-builder-public-faq">
            {items.map((item, itemIndex) => (
              <details open={itemIndex === 0} key={`${item.title}-${itemIndex}`}>
                <summary>{richNodes(item.title || 'Domanda da completare')}</summary>
                <p>{richNodes(item.text || 'Aggiungi una risposta chiara e professionale.')}</p>
              </details>
            ))}
          </div>
        </section>
      )
    }
    if (type.includes('contact') || type.includes('contatt') || type.includes('map') || type.includes('sedi')) {
      return (
        <section className={`iu-builder-public-section ${alignmentClass}`} key={`${block.type}-${index}`}>
          <h2>{richNodes(title)}</h2>
          {textValue ? <p>{richNodes(textValue)}</p> : null}
          <div className="iu-builder-public-contact">
            {site.contactPhone ? <span><Phone size={15} /> {site.contactPhone}</span> : null}
            {site.contactEmail ? <span><Mail size={15} /> {site.contactEmail}</span> : null}
            {contactLine ? <span><MapPin size={15} /> {contactLine}</span> : null}
          </div>
        </section>
      )
    }
    if (type.includes('cta')) {
      return (
        <section className={`iu-builder-public-cta ${alignmentClass}`} key={`${block.type}-${index}`}>
          <div>
            <h2>{richNodes(title)}</h2>
            {textValue ? <p>{richNodes(textValue)}</p> : null}
          </div>
          {block.button_text ? <button type="button">{block.button_text}</button> : null}
        </section>
      )
    }
    return (
      <section className={`iu-builder-public-section ${alignmentClass}`} key={`${block.type}-${index}`}>
        <h2>{richNodes(title)}</h2>
        {block.image_url ? <img className="iu-builder-public-wide-image" src={block.image_url} alt={block.image_alt || title} /> : null}
        {textValue ? <p>{richNodes(textValue)}</p> : null}
        {block.items.length ? renderCards(block, 'Completa il testo nella scheda Contenuti.') : null}
        {block.button_text ? <button className="iu-builder-public-inline-button" type="button">{block.button_text}</button> : null}
      </section>
    )
  }

  return (
    <section className="iu-builder-preview-shell" aria-label="Anteprima live">
      <header className="iu-builder-preview-head">
        <div>
          <h2>Anteprima live</h2>
          <p>Spazio anteprima grande e piu leggibile</p>
        </div>
        <div className="iu-builder-device-tabs" aria-label="Formato anteprima">
          {(['desktop', 'tablet', 'mobile'] as const).map((value) => (
            <button className={previewSize === value ? 'is-active' : ''} type="button" onClick={() => onPreviewSize(value)} key={value}>
              {optionLabel(value)}
            </button>
          ))}
        </div>
      </header>

      <div className="iu-builder-scorebar">Pronto alla pubblicazione: {score}%{dirty ? ' - modifiche da salvare' : ''}</div>

      <div
        className={`iu-builder-browser iu-builder-browser--${previewSize}`}
        style={{
          '--site-primary': primary,
          '--site-secondary': secondary,
          '--site-accent': accent,
          '--site-bg': background,
          '--site-surface': surface,
          '--site-text': text,
          '--site-heading-font': fonts.heading,
          '--site-body-font': fonts.body,
          '--site-heading-size': headingSize,
          '--site-section-title-size': sectionTitleSize,
          '--site-text-size': textSize,
          '--site-line-height': lineHeight,
          '--site-section-spacing': sectionSpacing,
          '--site-card-padding': cardPadding,
          '--site-button-radius': buttonRadius,
        } as CSSProperties}
      >
        <div className="iu-builder-browser__chrome">
          <span className="is-red" />
          <span className="is-yellow" />
          <span className="is-green" />
          <strong>{compactUrl(site.publicSlug ? `https://${site.publicSlug}.iusentra.it` : '', 'sito-studio.iusentra.it')}</strong>
        </div>
        <div className={`iu-builder-public-page ${effectClass}`}>
          <header className="iu-builder-public-nav">
            <div className="iu-builder-public-brand">
              {site.logoUrl ? <img src={site.logoUrl} alt={site.siteName || 'Logo studio'} /> : null}
              <strong>{site.siteName || site.siteTitle || 'Sito Studio'}</strong>
            </div>
            <button className="iu-builder-public-menu-button" type="button"><PanelTop size={14} /> Menu</button>
            <nav>
              {visiblePages.length ? visiblePages.map((entry) => <span key={entry.id}>{entry.title}</span>) : <span>Menu da completare</span>}
            </nav>
          </header>
          <section className={`iu-builder-public-hero is-align-${hero?.alignment || 'start'}`}>
            <div>
              <h1>{richNodes(pageTitle)}</h1>
              {pageSubtitle ? <p>{richNodes(pageSubtitle)}</p> : <p>Completa claim e descrizione nella scheda Setup.</p>}
              {buttonText ? <button type="button">{buttonText}</button> : null}
            </div>
            <aside>
              <strong>Consulenza riservata</strong>
              <span>{site.contactEmail || site.contactPhone ? 'Recapiti dello studio disponibili.' : 'Completa i recapiti in Setup.'}</span>
              {site.contactPhone ? <small>{site.contactPhone}</small> : null}
              {site.contactEmail ? <small>{site.contactEmail}</small> : null}
            </aside>
          </section>
          {contentBlocks.length ? contentBlocks.map(renderContentBlock) : (
            <section className="iu-builder-public-section">
              <h2>Contenuti da completare</h2>
              <p>Aggiungi blocchi o elementi reali dalla scheda Blocchi.</p>
            </section>
          )}
          <div className="iu-builder-live-note">Anteprima aggiornata automaticamente a ogni modifica</div>
          <footer className="iu-builder-public-footer">
            <div>
              <strong>{richNodes(footerTitle)}</strong>
              <p>{richNodes(footerText || site.legalDisclaimer || 'Footer completo generato dai dati studio.')}</p>
              {site.legalDisclaimer && site.legalDisclaimer !== footerText ? <small>{richNodes(site.legalDisclaimer)}</small> : null}
            </div>
            <nav>
              {site.privacyUrl ? <span>Privacy</span> : null}
              {site.cookiePolicyUrl ? <span>Cookie</span> : null}
              {site.accessibilityStatementUrl ? <span>Accessibilita</span> : null}
              {site.contactEmail ? <span>{site.contactEmail}</span> : null}
            </nav>
          </footer>
        </div>
      </div>
    </section>
  )
}

export function SitoStudioBuilderPage() {
  const [data, setData] = useState<SitoStudioBuilderData>(emptySitoStudioBuilderData)
  const [blocks, setBlocks] = useState<BuilderBlock[]>([])
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [previewSize, setPreviewSize] = useState<PreviewSize>('desktop')
  const [theme, setTheme] = useState<BuilderTheme>(emptySitoStudioBuilderData.theme)
  const [siteDraft, setSiteDraft] = useState<SiteDraft>(() => siteDraftFrom(emptySitoStudioBuilderData.site))
  const [pageDraft, setPageDraft] = useState<PageDraft>(() => pageDraftFrom(emptySitoStudioBuilderData.activePage))
  const [newPage, setNewPage] = useState({ title: '', slug: '', excerpt: '' })
  const [assetFile, setAssetFile] = useState<File | null>(null)
  const [assetForm, setAssetForm] = useState({ altText: '', title: '', category: 'immagini' })
  const [panelWidth, setPanelWidth] = useState(380)
  const [activeTab, setActiveTab] = useState<BuilderTabId>('aspetto')
  const [aiMode, setAiMode] = useState('sobrio')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const titleInputRef = useRef<HTMLInputElement | null>(null)
  const subtitleInputRef = useRef<HTMLInputElement | null>(null)
  const bodyInputRef = useRef<HTMLTextAreaElement | null>(null)
  const resizingRef = useRef(false)

  useEffect(() => {
    document.body.classList.add('iu-builder-pro-fullscreen')
    return () => document.body.classList.remove('iu-builder-pro-fullscreen')
  }, [])

  const syncPayload = (payload: SitoStudioBuilderData, nextBlocks?: BuilderBlock[]) => {
    const effectiveBlocks = nextBlocks?.length ? nextBlocks : payload.activeBlocks
    setData(payload)
    setTheme(payload.theme)
    setSiteDraft(siteDraftFrom(payload.site))
    setPageDraft(pageDraftFrom(payload.activePage))
    setBlocks(effectiveBlocks)
    setSelectedIndex((current) => clampIndex(current < 0 ? 0 : current, effectiveBlocks))
    setDirty(false)
  }

  const loadBuilder = useCallback((pageId?: number, pushUrl = false) => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getSitoStudioBuilder(pageId, controller.signal)
      .then((payload) => {
        syncPayload(payload)
        if (pushUrl && payload.activePageId) {
          window.history.pushState({}, '', `/sito-studio/builder?page_id=${payload.activePageId}`)
        }
      })
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setError('Editor Sito Studio non disponibile.')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => loadBuilder(initialPageId()), [loadBuilder])

  const selectedBlock = useMemo(() => blocks[selectedIndex] || null, [blocks, selectedIndex])
  const score = useMemo(() => publicationScore(data.validation), [data.validation])
  const activeTabInfo = tabs.find((tab) => tab.id === activeTab) || tabs[0]

  const applyMutation = (result: BuilderMutationResult) => {
    if (result.validation) setData((current) => ({ ...current, validation: result.validation! }))
    if (result.asset) setData((current) => ({ ...current, assets: [result.asset!, ...current.assets] }))
    if (result.assets && result.assets.length) setData((current) => ({ ...current, assets: result.assets! }))
    if (result.payload) {
      syncPayload(result.payload, result.blocks?.length ? result.blocks : undefined)
    } else if (result.blocks?.length) {
      setBlocks(result.blocks)
      setSelectedIndex((current) => clampIndex(current, result.blocks!))
      setDirty(false)
    }
  }

  const run = async (action: () => Promise<BuilderMutationResult>) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await action()
      if (!result.ok) throw new Error(result.message)
      applyMutation(result)
      setStatus(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operazione non completata.')
    } finally {
      setBusy(false)
    }
  }

  const updateBlockAt = (targetIndex: number, patch: Partial<BuilderBlock>) => {
    setBlocks((current) => current.map((block, index) => index === targetIndex ? { ...block, ...patch } : block))
    setDirty(true)
  }

  const updateBlock = (patch: Partial<BuilderBlock>) => {
    if (selectedIndex < 0) return
    updateBlockAt(selectedIndex, patch)
  }

  const addBlock = (preset: BuilderPreset) => {
    setBlocks((current) => {
      const next = [...current, cloneBlock(preset.defaults)]
      setSelectedIndex(next.length - 1)
      return next
    })
    setDirty(true)
    setStatus('Blocco aggiunto alla pagina.')
  }

  const moveBlock = (index: number, direction: -1 | 1) => {
    setBlocks((current) => {
      const target = index + direction
      if (target < 0 || target >= current.length) return current
      const next = [...current]
      ;[next[index], next[target]] = [next[target], next[index]]
      setSelectedIndex(target)
      return next
    })
    setDirty(true)
  }

  const duplicateBlock = (index: number) => {
    setBlocks((current) => {
      const next = [...current]
      next.splice(index + 1, 0, cloneBlock(current[index]))
      setSelectedIndex(index + 1)
      return next
    })
    setDirty(true)
  }

  const deleteBlock = (index: number) => {
    setBlocks((current) => {
      const next = current.filter((_block, blockIndex) => blockIndex !== index)
      setSelectedIndex(clampIndex(index, next))
      return next
    })
    setDirty(true)
  }

  const updateItem = (itemIndex: number, patch: Partial<BuilderBlockItem>) => {
    if (!selectedBlock) return
    updateBlock({ items: selectedBlock.items.map((item, index) => index === itemIndex ? { ...item, ...patch } : item) })
  }

  const attachAsset = (asset: BuilderAsset) => {
    if (!selectedBlock) return
    updateBlock({ image_url: asset.url, image_alt: asset.altText })
    setStatus('Immagine collegata al blocco selezionato.')
  }

  const saveTheme = () => {
    run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/design', {
      theme_template: theme.templateCode || data.site.themeTemplate,
      font_preset: theme.typography.font_preset || 'system_professional',
      font_size_base: theme.typography.font_size_base || '16px',
      line_height: theme.typography.line_height || '1.65',
      heading_size: theme.typography.heading_size || '34px',
      section_title_size: theme.typography.section_title_size || '26px',
      container_width: theme.layout.container || 'wide',
      density: theme.layout.density || 'standard',
      section_spacing: theme.layout.section_spacing || '28px',
      card_padding: theme.layout.card_padding || '20px',
      button_radius: theme.layout.button_radius || '999px',
      animation: theme.effects.animation || 'fade-up',
      animation_speed: theme.effects.speed || 'standard',
      card_shadow: theme.effects.card_shadow || 'none',
      fixed_header: theme.effects.fixed_header || 'none',
      button_hover: theme.effects.button_hover || 'none',
      section_divider: theme.effects.section_divider || 'none',
      image_treatment: theme.effects.image_treatment || 'none',
      focus_ring: theme.effects.focus_ring || 'professional',
      ...theme.tokens,
    }))
  }

  const saveCurrentWork = () => run(async () => {
    const siteResult = await postBuilderJson('/api/v1/ui/sito-studio/builder/site', siteDraft)
    if (!siteResult.ok) return siteResult
    if (data.activePageId) {
      const pageResult = await postBuilderJson(`/api/v1/ui/sito-studio/builder/pages/${data.activePageId}/settings`, pageDraft)
      if (!pageResult.ok) return pageResult
      const blockResult = await saveBuilderBlocks(data.activePageId, blocks)
      return { ...blockResult, message: 'Bozza salvata.' }
    }
    return { ...siteResult, message: 'Dati sito salvati.' }
  })

  const submitNewPage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newPage.title.trim()) return
    run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/pages', newPage))
    setNewPage({ title: '', slug: '', excerpt: '' })
  }

  const selectAssetFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null
    setAssetFile(file)
    if (!file) return
    const title = fileTitle(file.name)
    setAssetForm((current) => ({
      ...current,
      title: current.title.trim() ? current.title : title,
      altText: current.altText.trim() ? current.altText : title,
    }))
  }

  const submitAsset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    if (!assetFile) {
      setError('Seleziona una immagine da caricare.')
      return
    }
    const title = assetForm.title.trim() || fileTitle(assetFile.name) || 'Immagine studio'
    const altText = assetForm.altText.trim() || title
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await uploadBuilderAsset(assetFile, { ...assetForm, title, altText })
      if (!result.ok) throw new Error(result.message)
      if (result.asset) {
        setData((current) => ({ ...current, assets: [result.asset!, ...current.assets.filter((asset) => asset.id !== result.asset!.id)] }))
      } else {
        applyMutation(result)
      }
      if (result.asset && selectedBlock) {
        updateBlock({ image_url: result.asset.url, image_alt: result.asset.altText || result.asset.title || altText })
        setStatus('Immagine caricata e collegata al blocco selezionato.')
      } else {
        setStatus(result.message)
      }
      setAssetFile(null)
      setAssetForm({ altText: '', title: '', category: 'immagini' })
      form.reset()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Caricamento immagine non completato.')
    } finally {
      setBusy(false)
    }
  }

  const generateSite = () => run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/genera', {
    template: theme.templateCode || data.site.themeTemplate,
    style: aiMode,
    site_type: 'studio legale',
  }))

  const validateSite = () => run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/valida', {}))
  const publishSite = () => data.activePageId ? run(() => publishBuilderBlocks(data.activePageId, blocks)) : undefined
  const copyPublicLink = () => {
    if (!data.publicUrl) return
    navigator.clipboard?.writeText(data.publicUrl)
    setStatus('Link pubblico copiato.')
  }

  const setSite = (patch: Partial<SiteDraft>) => {
    setSiteDraft((current) => ({ ...current, ...patch }))
    setDirty(true)
  }

  const setPage = (patch: Partial<PageDraft>) => {
    setPageDraft((current) => ({ ...current, ...patch }))
    setDirty(true)
  }

  const setThemeDraft = (nextTheme: BuilderTheme) => {
    setTheme(nextTheme)
    setDirty(true)
  }

  const applyTextFormat = (field: TextFieldKey, format: RichTextFormat) => {
    if (!selectedBlock) return
    const refs = { title: titleInputRef, subtitle: subtitleInputRef, text: bodyInputRef }
    const input = refs[field].current
    const currentValue = selectedBlock[field] || ''
    const start = input?.selectionStart ?? 0
    const end = input?.selectionEnd ?? currentValue.length
    const selected = currentValue.slice(start, end) || currentValue
    const nextValue = `${currentValue.slice(0, start)}${formatRichText(selected, format)}${currentValue.slice(end)}`
    updateBlock({ [field]: nextValue } as Partial<BuilderBlock>)
    requestAnimationFrame(() => input?.focus())
  }

  const startPanelResize = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    if (resizingRef.current) return
    resizingRef.current = true
    const startX = event.clientX
    const startWidth = panelWidth
    const updateWidth = (moveEvent: MouseEvent) => {
      const nextWidth = Math.round(Math.max(320, Math.min(620, startWidth + moveEvent.clientX - startX)))
      setPanelWidth(nextWidth)
    }
    const stopResize = () => {
      window.removeEventListener('mousemove', updateWidth)
      window.removeEventListener('mouseup', stopResize)
      resizingRef.current = false
    }
    window.addEventListener('mousemove', updateWidth)
    window.addEventListener('mouseup', stopResize)
  }

  const faqPreset = data.blockPresets.find((preset) => preset.type.includes('faq'))

  const renderTabContent = () => {
    if (activeTab === 'setup') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Settings2} title="Dati studio" subtitle="Base usata per generare sito, contatti e footer." />
          <Field label="Nome studio" value={siteDraft.siteName} onChange={(siteName) => setSite({ siteName })} />
          <Field label="Claim" value={siteDraft.claim} onChange={(claim) => setSite({ claim })} />
          <Field label="Descrizione breve" value={siteDraft.siteDescription} area rows={4} onChange={(siteDescription) => setSite({ siteDescription })} />
          <div className="iu-builder-two">
            <Field label="Email" value={siteDraft.contactEmail} type="email" onChange={(contactEmail) => setSite({ contactEmail })} />
            <Field label="Telefono" value={siteDraft.contactPhone} onChange={(contactPhone) => setSite({ contactPhone })} />
          </div>
          <Field label="Indirizzo" value={siteDraft.address} onChange={(address) => setSite({ address })} />
          <div className="iu-builder-two">
            <Field label="Citta" value={siteDraft.city} onChange={(city) => setSite({ city })} />
            <Field label="Provincia" value={siteDraft.province} onChange={(province) => setSite({ province })} />
          </div>
          <Field label="Logo" value={siteDraft.logoUrl} onChange={(logoUrl) => setSite({ logoUrl })} />
          <SectionTitle icon={WandSparkles} title="Wizard guidato" subtitle="Prepara pagine e blocchi usando dati reali gia presenti." />
          <button className="iu-builder-primary" type="button" onClick={generateSite} disabled={busy}><WandSparkles size={15} /> Genera bozza sito</button>
        </div>
      )
    }

    if (activeTab === 'pagine') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={FilePlus2} title="Aggiungi pagina" subtitle="Crea pagine in bozza, poi scegli visibilita e menu." />
          <form className="iu-builder-new-page" onSubmit={submitNewPage}>
            <Field label="Titolo" value={newPage.title} onChange={(title) => setNewPage((current) => ({ ...current, title }))} />
            <Field label="URL pagina" value={newPage.slug} onChange={(slug) => setNewPage((current) => ({ ...current, slug }))} />
            <Field label="Descrizione" value={newPage.excerpt} area onChange={(excerpt) => setNewPage((current) => ({ ...current, excerpt }))} />
            <button type="submit" disabled={busy || !newPage.title.trim()}><Plus size={15} /> Aggiungi pagina</button>
          </form>
          <SectionTitle icon={FileText} title="Pagine del sito" subtitle="Home, menu principale e menu footer." />
          <div className="iu-builder-page-list">
            {data.pages.map((page) => (
              <article className={page.id === data.activePageId ? 'is-active' : ''} key={page.id}>
                <button type="button" onClick={() => loadBuilder(page.id, true)}>
                  <strong>{page.title}</strong>
                  <span>{page.statusLabel} - {page.showInMenu ? 'nel menu' : 'nascosta dal menu'}</span>
                </button>
                <div>
                  <button type="button" title="Duplica pagina" aria-label="Duplica pagina" onClick={() => run(() => postBuilderJson(`/api/v1/ui/sito-studio/builder/pages/${page.id}/duplicate`, {}))}><Copy size={14} /></button>
                  <button type="button" title="Nascondi dal menu" aria-label="Nascondi dal menu" onClick={() => run(() => postBuilderJson(`/api/v1/ui/sito-studio/builder/pages/${page.id}/settings`, { ...page, showInMenu: !page.showInMenu, home: page.home }))}>{page.showInMenu ? <EyeOff size={14} /> : <Eye size={14} />}</button>
                  {!page.home ? <button type="button" title="Elimina pagina" aria-label="Elimina pagina" onClick={() => run(() => deleteBuilderPage(page.id))}><Trash2 size={14} /></button> : null}
                </div>
              </article>
            ))}
          </div>
          <SectionTitle icon={Home} title="Pagina selezionata" />
          <Field label="Titolo pagina" value={pageDraft.title} onChange={(title) => setPage({ title })} />
          <Field label="URL pagina" value={pageDraft.slug} onChange={(slug) => setPage({ slug })} />
          <Field label="Descrizione menu" value={pageDraft.excerpt} area onChange={(excerpt) => setPage({ excerpt })} />
          <ToggleRow label="Pagina visibile nel menu" checked={pageDraft.showInMenu} onChange={(showInMenu) => setPage({ showInMenu })} />
          <ToggleRow label="Imposta come homepage" checked={pageDraft.home} onChange={(home) => setPage({ home })} />
          <div className="iu-builder-chip-grid">{starterPages.map((label) => <span key={label}>{label}</span>)}</div>
        </div>
      )
    }

    if (activeTab === 'blocchi') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Layers3} title="Blocchi disponibili" subtitle="Aggiungi sezioni operative alla pagina selezionata." />
          <div className="iu-builder-palette">
            {data.blockPresets.map((preset) => (
              <button type="button" onClick={() => addBlock(preset)} key={preset.type}>
                <Plus size={14} />
                {blockLabel(preset.type, data.blockPresets)}
              </button>
            ))}
          </div>
          <SectionTitle icon={PanelTop} title="Struttura pagina" />
          <div className="iu-builder-block-list">
            {blocks.map((block, index) => (
              <article className={selectedIndex === index ? 'is-active' : ''} key={`${block.type}-${index}`}>
                <button type="button" onClick={() => setSelectedIndex(index)}>
                  <strong>{block.title || blockLabel(block.type, data.blockPresets)}</strong>
                  <span>{blockLabel(block.type, data.blockPresets)} - {optionLabel(block.spacing)}</span>
                </button>
                <div>
                  <button type="button" onClick={() => moveBlock(index, -1)} disabled={index === 0} aria-label="Sposta su"><ArrowUp size={14} /></button>
                  <button type="button" onClick={() => moveBlock(index, 1)} disabled={index === blocks.length - 1} aria-label="Sposta giu"><ArrowDown size={14} /></button>
                  <button type="button" onClick={() => duplicateBlock(index)} aria-label="Duplica"><Copy size={14} /></button>
                  <button type="button" onClick={() => updateBlockAt(index, { visibility: { desktop: false, tablet: false, mobile: false } })} aria-label="Nascondi"><EyeOff size={14} /></button>
                  <button type="button" onClick={() => deleteBlock(index)} aria-label="Elimina"><Trash2 size={14} /></button>
                </div>
              </article>
            ))}
          </div>
          {selectedBlock ? (
            <SelectField label="Converti in altro blocco" value={selectedBlock.type} values={data.blockPresets.map((preset) => preset.type)} onChange={(type) => updateBlock({ type })} />
          ) : null}
        </div>
      )
    }

    if (activeTab === 'contenuti') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Type} title="Testi del blocco" subtitle="La scheda piu usata: modifica testi e pulsanti." />
          {selectedBlock ? (
            <>
              <ButtonGroup
                label="Allineamento blocco"
                value={selectedBlock.alignment || 'start'}
                options={[
                  { value: 'start', label: 'Sinistra', icon: AlignLeft },
                  { value: 'center', label: 'Centrato', icon: AlignCenter },
                  { value: 'end', label: 'Destra', icon: AlignRight },
                  { value: 'justify', label: 'Giustificato', icon: AlignJustify },
                ]}
                onChange={(alignment) => updateBlock({ alignment })}
              />
              <div className="iu-builder-format-stack" aria-label="Formattazione testo">
                <RichTextToolbar field="title" label="Titolo" onFormat={applyTextFormat} />
                <RichTextToolbar field="subtitle" label="Sottotitolo" onFormat={applyTextFormat} />
                <RichTextToolbar field="text" label="Corpo" onFormat={applyTextFormat} />
              </div>
              <Field inputRef={titleInputRef} label="Titolo blocco" value={selectedBlock.title} onChange={(title) => updateBlock({ title })} />
              <Field inputRef={subtitleInputRef} label="Sottotitolo" value={selectedBlock.subtitle} onChange={(subtitle) => updateBlock({ subtitle })} />
              <Field inputRef={bodyInputRef} label="Corpo testo" value={selectedBlock.text} area rows={5} onChange={(text) => updateBlock({ text })} />
              <Field label="Testo pulsante" value={selectedBlock.button_text} onChange={(button_text) => updateBlock({ button_text })} />
              <Field label="Link pulsante" value={selectedBlock.button_url} onChange={(button_url) => updateBlock({ button_url })} />
              <div className="iu-builder-ai-actions">
                <a href="/sito-studio/redazione-ai"><Bot size={14} /> Migliora testo</a>
                <button type="button" onClick={validateSite}><ShieldCheck size={14} /> Controlla deontologia</button>
                {faqPreset ? <button type="button" onClick={() => addBlock(faqPreset)}><Plus size={14} /> Genera FAQ</button> : null}
              </div>
              <SectionTitle icon={Layers3} title="Elementi interni" />
              <div className="iu-builder-items">
                {selectedBlock.items.map((item, index) => (
                  <article className="iu-builder-item" key={index}>
                    <Field label="Titolo elemento" value={item.title} onChange={(title) => updateItem(index, { title })} />
                    <Field label="Testo elemento" value={item.text} area onChange={(text) => updateItem(index, { text })} />
                  </article>
                ))}
                <button className="iu-builder-outline" type="button" onClick={() => updateBlock({ items: [...selectedBlock.items, { title: 'Nuovo elemento', text: '', image_url: '', image_alt: '', button_text: '', button_url: '' }] })}><Plus size={15} /> Aggiungi elemento</button>
              </div>
            </>
          ) : <p className="iu-builder-muted">Seleziona un blocco per modificare i contenuti.</p>}
        </div>
      )
    }

    if (activeTab === 'aspetto') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Palette} title="Template" subtitle="Scegli modello e impostazioni grafiche." />
          <div className="iu-builder-template-list">
            {(data.templates.length ? data.templates : templateLabels.map((label, index) => ({ code: `template-${index}`, name: label, description: 'Modello grafico', active: false }))).map((template) => (
              <button
                className={template.code === theme.templateCode || template.active ? 'is-active' : ''}
                type="button"
                disabled={busy}
                onClick={() => {
                  setThemeDraft({ ...theme, templateCode: template.code })
                  run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/template', { templateCode: template.code }))
                }}
                key={template.code}
              >
                <span>
                  <strong>{template.name}</strong>
                  <small>{template.description || 'Istituzionale'}</small>
                </span>
                {template.code === theme.templateCode || template.active ? <Check size={16} /> : null}
              </button>
            ))}
          </div>
          <SectionTitle icon={Palette} title="Colori" />
          <div className="iu-builder-swatch-row">
            {colorKeys.map(([key, label]) => (
              <label key={key} title={label}>
                <input type="color" value={theme.tokens[key] || colorFallbacks[key]} onChange={(event) => setThemeDraft(setThemeValue(theme, 'tokens', key, event.target.value))} />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <SelectField label="Font" value={theme.typography.font_preset || 'system_professional'} values={fontOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'typography', 'font_preset', value))} />
          <div className="iu-builder-two">
            <SelectField label="Dimensione testo" value={theme.typography.font_size_base || '16px'} values={textSizeOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'typography', 'font_size_base', value))} />
            <SelectField label="Interlinea" value={theme.typography.line_height || '1.65'} values={lineHeightOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'typography', 'line_height', value))} />
          </div>
          <div className="iu-builder-two">
            <SelectField label="Titolo hero" value={theme.typography.heading_size || '34px'} values={headingSizeOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'typography', 'heading_size', value))} />
            <SelectField label="Titoli sezioni" value={theme.typography.section_title_size || '26px'} values={sectionTitleSizeOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'typography', 'section_title_size', value))} />
          </div>
          <SectionTitle icon={PanelBottom} title="Layout e spaziature" />
          <div className="iu-builder-two">
            <SelectField label="Spazio sezioni" value={theme.layout.section_spacing || '28px'} values={sectionSpacingOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'layout', 'section_spacing', value))} />
            <SelectField label="Padding card" value={theme.layout.card_padding || '20px'} values={cardPaddingOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'layout', 'card_padding', value))} />
          </div>
          <SelectField label="Raggio bottoni" value={theme.layout.button_radius || '999px'} values={buttonRadiusOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'layout', 'button_radius', value))} />
          <SectionTitle icon={PanelBottom} title="Effetti professionali" />
          <SelectField label="Movimento sezioni" value={theme.effects.animation || 'fade-up'} values={animationOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'effects', 'animation', value))} />
          <SelectField label="Ombra card" value={theme.effects.card_shadow || 'none'} values={shadowOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'effects', 'card_shadow', value))} />
          <SelectField label="Header" value={theme.effects.fixed_header || 'none'} values={headerEffectOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'effects', 'fixed_header', value))} />
          <SelectField label="Separatore sezioni" value={theme.effects.section_divider || 'none'} values={sectionDividerOptions} onChange={(value) => setThemeDraft(setThemeValue(theme, 'effects', 'section_divider', value))} />
          <div className="iu-builder-effect-list">
            {[
              ['button_hover', 'Hover bottoni', 'true'],
              ['focus_ring', 'Focus professionale', 'professional'],
              ['image_treatment', 'Immagini editoriali', 'editorial'],
            ].map(([key, label, value]) => (
              <ToggleRow
                key={key}
                label={label}
                checked={theme.effects[key] === value}
                onChange={(checked) => setThemeDraft(setThemeValue(theme, 'effects', key, checked ? value : 'none'))}
              />
            ))}
          </div>
          <button className="iu-builder-primary" type="button" onClick={saveTheme} disabled={busy}><Save size={15} /> Salva aspetto</button>
        </div>
      )
    }

    if (activeTab === 'media') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={UploadCloud} title="Carica media" subtitle="Immagini e testi alternativi restano nella libreria studio." />
          <form className="iu-builder-upload" onSubmit={submitAsset}>
            <input type="file" accept="image/*" onChange={selectAssetFile} />
            {assetFile ? (
              <div className="iu-builder-selected-file">
                <ImagePlus size={15} />
                <span>{assetFile.name}</span>
                <small>{Math.max(1, Math.round(assetFile.size / 1024))} KB</small>
              </div>
            ) : null}
            <Field label="Testo alternativo" value={assetForm.altText} onChange={(altText) => setAssetForm((current) => ({ ...current, altText }))} />
            <Field label="Titolo immagine" value={assetForm.title} onChange={(title) => setAssetForm((current) => ({ ...current, title }))} />
            <button type="submit" disabled={busy || !assetFile}><UploadCloud size={15} /> {selectedBlock ? 'Carica e usa nel blocco' : 'Carica immagine'}</button>
          </form>
          <div className="iu-builder-two">
            <Field label="Logo studio" value={siteDraft.logoUrl} onChange={(logoUrl) => setSite({ logoUrl })} />
            <Field label="Favicon" value={siteDraft.faviconUrl} onChange={(faviconUrl) => setSite({ faviconUrl })} />
          </div>
          <SectionTitle icon={ImagePlus} title="Libreria media" />
          <div className="iu-builder-asset-grid">
            {data.assets.length ? data.assets.map((asset) => (
              <article key={`${asset.id}-${asset.url}`}>
                {asset.url ? <img src={asset.url} alt={asset.altText || asset.title} /> : <span />}
                <strong>{asset.title}</strong>
                <small>{asset.altText || 'Testo alternativo da completare'}</small>
                <div>
                  <button type="button" onClick={() => attachAsset(asset)} disabled={!selectedBlock}><Link2 size={14} /> Usa nel blocco</button>
                  <button type="button" onClick={() => run(() => deleteBuilderAsset(asset.id))}><Trash2 size={14} /> Rimuovi</button>
                </div>
              </article>
            )) : (
              <article className="iu-builder-empty-media">
                <ImagePlus size={18} />
                <strong>Nessuna immagine caricata</strong>
                <small>Carica logo, immagine hero o foto dello studio per usarle nella preview live.</small>
              </article>
            )}
          </div>
        </div>
      )
    }

    if (activeTab === 'seo') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Search} title="SEO sito" subtitle="Titolo, descrizione e indirizzo pubblico." />
          <Field label="Titolo SEO sito" value={siteDraft.siteTitle} onChange={(siteTitle) => setSite({ siteTitle })} />
          <Field label="Meta description sito" value={siteDraft.siteDescription} area rows={4} onChange={(siteDescription) => setSite({ siteDescription })} />
          <Field label="Dominio / URL pubblico" value={siteDraft.publicSlug} onChange={(publicSlug) => setSite({ publicSlug })} />
          <SectionTitle icon={FileText} title="SEO pagina" />
          <Field label="Titolo SEO pagina" value={pageDraft.seoTitle} onChange={(seoTitle) => setPage({ seoTitle })} />
          <Field label="Meta description pagina" value={pageDraft.seoDescription} area rows={4} onChange={(seoDescription) => setPage({ seoDescription })} />
          <Field label="Slug pagina" value={pageDraft.slug} onChange={(slug) => setPage({ slug })} />
          <div className="iu-builder-google-preview">
            <span>{compactUrl(data.publicUrl, 'sito-studio.iusentra.it')}/{pageDraft.slug}</span>
            <strong>{pageDraft.seoTitle || siteDraft.siteTitle || pageDraft.title}</strong>
            <p>{pageDraft.seoDescription || siteDraft.siteDescription || 'Descrizione da completare.'}</p>
          </div>
          <button className="iu-builder-outline" type="button" onClick={() => {
            setPage({ seoTitle: pageDraft.seoTitle || pageDraft.title, seoDescription: pageDraft.seoDescription || pageDraft.excerpt || siteDraft.siteDescription })
            setStatus('Suggerimento SEO preparato dai dati presenti.')
          }}><WandSparkles size={15} /> Suggerisci SEO</button>
        </div>
      )
    }

    if (activeTab === 'privacy') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={ShieldCheck} title="Privacy e conformita" subtitle="Controlli per sito di studio legale." />
          <Field label="Privacy policy" value={siteDraft.privacyUrl} onChange={(privacyUrl) => setSite({ privacyUrl })} />
          <Field label="Cookie policy" value={siteDraft.cookiePolicyUrl} onChange={(cookiePolicyUrl) => setSite({ cookiePolicyUrl })} />
          <Field label="Avviso deontologico" value={siteDraft.legalDisclaimer} area rows={4} onChange={(legalDisclaimer) => setSite({ legalDisclaimer })} />
          <ToggleRow label="Banner cookie attivo" checked={siteDraft.cookieBannerEnabled} onChange={(cookieBannerEnabled) => setSite({ cookieBannerEnabled })} />
          <ValidationList validation={data.validation} />
          <SectionTitle icon={AlertTriangle} title="Frasi da segnalare" />
          <div className="iu-builder-chip-grid">{blockedClaims.map((claim) => <span key={claim}>{claim}</span>)}</div>
        </div>
      )
    }

    if (activeTab === 'ai') {
      return (
        <div className="iu-builder-tab-stack">
          <SectionTitle icon={Bot} title="AI governata" subtitle="Le azioni passano dal servizio sicuro, nessuna chiave nel browser." />
          <SelectField label="Tono" value={aiMode} values={['sobrio', 'istituzionale', 'moderno', 'empatico', 'corporate']} onChange={setAiMode} />
          <div className="iu-builder-ai-grid">
            <button type="button" onClick={generateSite}><WandSparkles size={16} /> Genera bozza homepage</button>
            {faqPreset ? <button type="button" onClick={() => addBlock(faqPreset)}><Plus size={16} /> Genera FAQ</button> : null}
            <button type="button" onClick={validateSite}><ShieldCheck size={16} /> Controlla deontologia</button>
            <a href="/sito-studio/redazione-ai"><Bot size={16} /> Apri redazione assistita</a>
          </div>
          <p className="iu-builder-muted">Usa la redazione assistita per migliorare tutti i testi, semplificare, preparare descrizioni e controllare il tono prima della pubblicazione.</p>
        </div>
      )
    }

    return (
      <div className="iu-builder-tab-stack">
        <SectionTitle icon={Rocket} title="Centro controllo finale" subtitle="Controlli, URL pubblico e versioni." />
        <div className="iu-builder-publish-score">
          <strong>{score}%</strong>
          <span>{data.validation.blocking ? `${data.validation.blocking} errori bloccanti` : 'Nessun errore bloccante'}</span>
        </div>
        <ValidationList validation={data.validation} />
        <Field label="URL pubblico" value={data.publicUrl || siteDraft.publicSlug} onChange={(publicSlug) => setSite({ publicSlug })} />
        <div className="iu-builder-action-grid">
          <button type="button" onClick={validateSite} disabled={busy}><ShieldCheck size={15} /> Controlla sito</button>
          <button type="button" onClick={saveCurrentWork} disabled={busy}><Save size={15} /> Salva bozza</button>
          <button type="button" onClick={publishSite} disabled={busy || !data.activePageId}><Send size={15} /> Pubblica</button>
          <button type="button" onClick={copyPublicLink} disabled={!data.publicUrl}><Copy size={15} /> Copia link pubblico</button>
        </div>
        <SectionTitle icon={RefreshCw} title="Versioni precedenti" />
        <div className="iu-builder-revision-list">
          {data.revisions.length ? data.revisions.slice(0, 6).map((revision) => (
            <button type="button" onClick={() => run(() => postBuilderJson(`/api/v1/ui/sito-studio/builder/revisions/${revision.id}/restore`, {}))} key={revision.id}>
              <RefreshCw size={14} />
              <span>{revision.label}</span>
              <small>{formatDate(revision.createdAt)}</small>
            </button>
          )) : <p className="iu-builder-muted">Nessuna versione precedente disponibile.</p>}
        </div>
      </div>
    )
  }

  const hasPayload = data.ok && Boolean(data.activePageId)

  return (
    <main className="iu-content iu-builder-pro" aria-label="Sito Studio Builder Pro">
      <header className="iu-builder-topbar-pro">
        <div>
          <h1 data-allow-technical-text="true">Sito Studio Builder Pro</h1>
          <p>Pannello stretto con tab verticali, anteprima live grande.</p>
        </div>
        <div>
          <button type="button" onClick={saveCurrentWork} disabled={busy || loading}><Save size={15} /> Salva</button>
          <button type="button" onClick={validateSite} disabled={busy || loading}><ShieldCheck size={15} /> Controlla</button>
          <button className="is-primary" type="button" onClick={publishSite} disabled={busy || loading || !data.activePageId}><Send size={15} /> Pubblica</button>
        </div>
      </header>

      {loading ? <LoadingState title="Caricamento editor" message="Lettura pagine, blocchi, immagini e controlli reali." /> : null}
      {!loading && error ? <EmptyState title="Editor non disponibile" message={error} /> : null}
      {!loading && !error && !hasPayload ? <EmptyState title="Nessuna pagina configurata" message="Crea una pagina per iniziare la composizione del sito studio." /> : null}

      {!loading && !error && hasPayload ? (
        <div className="iu-builder-pro-grid" style={{ '--builder-panel-width': `${panelWidth}px` } as CSSProperties}>
          <aside className="iu-builder-left-pro" aria-label="Pannello strumenti builder">
            <nav className="iu-builder-tab-rail" aria-label="Schede builder">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <button className={activeTab === tab.id ? 'is-active' : ''} type="button" onClick={() => setActiveTab(tab.id)} title={tab.label} aria-label={tab.label} key={tab.id}>
                    <Icon size={18} aria-hidden="true" />
                    <span>{tab.short}</span>
                  </button>
                )
              })}
            </nav>
            <section className="iu-builder-tab-panel" aria-label={activeTabInfo.label}>
              <header>
                <h2>{activeTabInfo.label}</h2>
                <p>{activeTabInfo.description}</p>
              </header>
              {status ? <div className="iu-builder-inline-status is-success">{status}</div> : null}
              {error ? <div className="iu-builder-inline-status is-danger">{error}</div> : null}
              <div className="iu-builder-tab-scroll">{renderTabContent()}</div>
            </section>
          </aside>
          <button
            className="iu-builder-resize-handle"
            type="button"
            aria-label="Ridimensiona pannello strumenti"
            title={`Pannello ${panelWidth}px`}
            onMouseDown={startPanelResize}
          >
            <span>{panelWidth}px</span>
          </button>

          <BuilderLivePreview
            site={siteDraft}
            page={pageDraft}
            pages={data.pages}
            blocks={blocks}
            presets={data.blockPresets}
            theme={theme}
            previewSize={previewSize}
            score={score}
            dirty={dirty}
            onPreviewSize={setPreviewSize}
          />
        </div>
      ) : null}
    </main>
  )
}
