import { FilePlus2, LayoutTemplate, Plus, Search, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import type { BuilderPage, BuilderPreset, BuilderTemplate } from '../../sitoStudioBuilderData'
import { blockLabel } from '../../sitoStudioBuilderData'

export function BuilderSidebar({
  pages,
  activePageId,
  presets,
  templates,
  busy,
  onPageSelect,
  onCreatePage,
  onDeletePage,
  onAddBlock,
  onApplyTemplate,
}: {
  pages: BuilderPage[]
  activePageId: number
  presets: BuilderPreset[]
  templates: BuilderTemplate[]
  busy: boolean
  onPageSelect: (pageId: number) => void
  onCreatePage: (values: { title: string; slug: string; excerpt: string }) => void
  onDeletePage: (pageId: number) => void
  onAddBlock: (preset: BuilderPreset) => void
  onApplyTemplate: (templateCode: string) => void
}) {
  const [newPageOpen, setNewPageOpen] = useState(false)
  const [newPage, setNewPage] = useState({ title: '', slug: '', excerpt: '' })
  const submitNewPage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newPage.title.trim()) return
    onCreatePage(newPage)
    setNewPage({ title: '', slug: '', excerpt: '' })
    setNewPageOpen(false)
  }
  return (
    <aside className="iu-builder-side" aria-label="Strumenti builder">
      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Pagine</span>
            <h2>Struttura sito</h2>
          </div>
          <button className="iu-builder-iconlink" type="button" onClick={() => setNewPageOpen((value) => !value)} title="Nuova pagina">
            <FilePlus2 size={16} />
            Nuova
          </button>
        </header>
        {newPageOpen ? (
          <form className="iu-builder-new-page" onSubmit={submitNewPage}>
            <input placeholder="Titolo pagina" value={newPage.title} onChange={(event) => setNewPage((current) => ({ ...current, title: event.target.value }))} />
            <input placeholder="Indirizzo breve" value={newPage.slug} onChange={(event) => setNewPage((current) => ({ ...current, slug: event.target.value }))} />
            <textarea placeholder="Descrizione per ricerca e anteprima" value={newPage.excerpt} onChange={(event) => setNewPage((current) => ({ ...current, excerpt: event.target.value }))} />
            <button type="submit" disabled={busy || !newPage.title.trim()}>Crea pagina</button>
          </form>
        ) : null}
        <div className="iu-builder-pages">
          {pages.map((page) => (
            <article className={`iu-builder-page${page.id === activePageId ? ' is-active' : ''}`} key={page.id}>
              <button type="button" onClick={() => onPageSelect(page.id)}>
                <strong>{page.title}</strong>
                <span>{page.statusLabel} - {page.blocksCount} blocchi</span>
              </button>
              {!page.home ? (
                <button className="iu-builder-page__delete" type="button" disabled={busy} onClick={() => onDeletePage(page.id)} title="Rimuovi pagina">
                  <Trash2 size={14} />
                </button>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Palette</span>
            <h2>Blocchi disponibili</h2>
          </div>
          <Search size={17} />
        </header>
        <div className="iu-builder-palette">
          {presets.map((preset) => (
            <button type="button" onClick={() => onAddBlock(preset)} key={preset.type}>
              <Plus size={14} />
              {blockLabel(preset.type, presets)}
            </button>
          ))}
        </div>
      </section>

      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Grafica</span>
            <h2>Modelli</h2>
          </div>
          <LayoutTemplate size={17} />
        </header>
        <div className="iu-builder-templates">
          {templates.map((template) => (
            <button
              className={`iu-builder-template${template.active ? ' is-active' : ''}`}
              type="button"
              disabled={busy}
              onClick={() => onApplyTemplate(template.code)}
              key={template.code}
            >
              <strong>{template.name}</strong>
              <span>{template.description}</span>
            </button>
          ))}
        </div>
      </section>
    </aside>
  )
}
