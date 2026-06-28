import { CheckCircle2, History, Palette, RotateCcw, ShieldCheck } from 'lucide-react'
import type { BuilderRevision, BuilderTemplate, BuilderTheme, SitoStudioBuilderData } from '../../sitoStudioBuilderData'
import { optionLabel } from '../../sitoStudioBuilderData'

const colorFields = [
  ['primary', 'Primario'],
  ['secondary', 'Secondario'],
  ['accent', 'Accento'],
  ['bg', 'Sfondo'],
  ['surface', 'Superficie'],
  ['text', 'Testo'],
]

function formatDate(value: string): string {
  if (!value) return 'Data non indicata'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

export function BuilderAdminPanels({
  validation,
  revisions,
  theme,
  templates,
  busy,
  onValidate,
  onRestore,
  onThemeChange,
  onSaveTheme,
}: {
  validation: SitoStudioBuilderData['validation']
  revisions: BuilderRevision[]
  theme: BuilderTheme
  templates: BuilderTemplate[]
  busy: boolean
  onValidate: () => void
  onRestore: (revisionId: number) => void
  onThemeChange: (theme: BuilderTheme) => void
  onSaveTheme: () => void
}) {
  const template = templates.find((item) => item.code === theme.templateCode)
  const setToken = (key: string, value: string) => onThemeChange({ ...theme, tokens: { ...theme.tokens, [key]: value } })
  const setFont = (value: string) => onThemeChange({ ...theme, typography: { ...theme.typography, font_preset: value } })

  return (
    <div className="iu-builder-admin-panels">
      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Controlli</span>
            <h2>Qualita professionale</h2>
          </div>
          <button className="iu-builder-outline" type="button" onClick={onValidate} disabled={busy}>
            <ShieldCheck size={15} />
            Riesegui
          </button>
        </header>
        <div className="iu-builder-validation">
          {validation.groups.map((group) => (
            <article key={group.id}>
              <strong>{group.label}</strong>
              {group.items.length ? group.items.slice(0, 4).map((item, index) => (
                <span className={`is-${item.severity}`} key={`${group.id}-${index}`}>{item.message}</span>
              )) : <span className="is-ok"><CheckCircle2 size={14} /> Nessun rilievo immediato.</span>}
            </article>
          ))}
        </div>
      </section>

      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Revisioni</span>
            <h2>Recupero controllato</h2>
          </div>
          <History size={17} />
        </header>
        <div className="iu-builder-revisions">
          {revisions.length ? revisions.slice(0, 6).map((revision) => (
            <button type="button" onClick={() => onRestore(revision.id)} disabled={busy} key={revision.id}>
              <RotateCcw size={14} />
              <span>{revision.label}</span>
              <small>{formatDate(revision.createdAt)}</small>
            </button>
          )) : <p className="iu-builder-muted">Nessuna revisione disponibile.</p>}
        </div>
      </section>

      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Aspetto</span>
            <h2>Parametri grafici</h2>
          </div>
          <Palette size={17} />
        </header>
        <div className="iu-builder-design">
          <label className="iu-builder-field">
            <span>Modello attivo</span>
            <input value={template?.name || 'Modello non indicato'} readOnly />
          </label>
          <label className="iu-builder-field">
            <span>Preset font</span>
            <select value={theme.typography.font_preset || 'system_professional'} onChange={(event) => setFont(event.target.value)}>
              {['system_professional', 'serif_elegant', 'modern_sans', 'editorial_legal', 'compact_business'].map((value) => (
                <option value={value} key={value}>{optionLabel(value)}</option>
              ))}
            </select>
          </label>
          <div className="iu-builder-colors">
            {colorFields.map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <input type="color" value={theme.tokens[key] || '#1e3a8a'} onChange={(event) => setToken(key, event.target.value)} />
              </label>
            ))}
          </div>
          <button className="iu-builder-primary" type="button" onClick={onSaveTheme} disabled={busy}>Salva parametri grafici</button>
        </div>
      </section>
    </div>
  )
}
