import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bot, ExternalLink, Globe2, RefreshCw, Save, Send } from 'lucide-react'
import {
  emptySitoStudioBuilderData,
  deleteBuilderPage,
  getSitoStudioBuilder,
  normaliseBlock,
  postBuilderJson,
  publishBuilderBlocks,
  saveBuilderBlocks,
  uploadBuilderAsset,
  type BuilderAsset,
  type BuilderBlock,
  type BuilderBlockItem,
  type BuilderPreset,
  type BuilderTheme,
  type SitoStudioBuilderData,
} from '../sitoStudioBuilderData'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { BuilderAdminPanels } from './sitoStudioBuilder/BuilderAdminPanels'
import { BuilderCanvas, type PreviewSize } from './sitoStudioBuilder/BuilderCanvas'
import { BuilderProperties } from './sitoStudioBuilder/BuilderProperties'
import { BuilderSidebar } from './sitoStudioBuilder/BuilderSidebar'
import './SitoStudioBuilderPage.css'
import './SitoStudioBuilderPage.panels.css'

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

export function SitoStudioBuilderPage() {
  const [data, setData] = useState<SitoStudioBuilderData>(emptySitoStudioBuilderData)
  const [blocks, setBlocks] = useState<BuilderBlock[]>([])
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [previewSize, setPreviewSize] = useState<PreviewSize>('desktop')
  const [previewVersion, setPreviewVersion] = useState(1)
  const [theme, setTheme] = useState<BuilderTheme>(emptySitoStudioBuilderData.theme)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const loadBuilder = useCallback((pageId?: number, pushUrl = false) => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getSitoStudioBuilder(pageId, controller.signal)
      .then((payload) => {
        setData(payload)
        setBlocks(payload.activeBlocks)
        setTheme(payload.theme)
        setSelectedIndex(clampIndex(0, payload.activeBlocks))
        setDirty(false)
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

  const applyPayload = (payload?: SitoStudioBuilderData, nextBlocks?: BuilderBlock[]) => {
    if (payload) {
      setData(payload)
      setTheme(payload.theme)
      setBlocks(nextBlocks?.length ? nextBlocks : payload.activeBlocks)
      setSelectedIndex((current) => clampIndex(current, nextBlocks?.length ? nextBlocks : payload.activeBlocks))
      setDirty(false)
      setPreviewVersion((value) => value + 1)
    }
  }

  const run = async (action: () => Promise<{ ok: boolean; message: string; payload?: SitoStudioBuilderData; blocks?: BuilderBlock[]; validation?: SitoStudioBuilderData['validation']; asset?: BuilderAsset }>) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await action()
      if (!result.ok) throw new Error(result.message)
      if (result.validation) setData((current) => ({ ...current, validation: result.validation! }))
      if (result.asset) setData((current) => ({ ...current, assets: [result.asset!, ...current.assets] }))
      applyPayload(result.payload, result.blocks)
      setStatus(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operazione non completata.')
    } finally {
      setBusy(false)
    }
  }

  const updateBlock = (patch: Partial<BuilderBlock>) => {
    setBlocks((current) => current.map((block, index) => index === selectedIndex ? { ...block, ...patch } : block))
    setDirty(true)
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
    const items = selectedBlock.items.map((item, index) => index === itemIndex ? { ...item, ...patch } : item)
    updateBlock({ items })
  }

  const moveItem = (itemIndex: number, direction: -1 | 1) => {
    if (!selectedBlock) return
    const target = itemIndex + direction
    if (target < 0 || target >= selectedBlock.items.length) return
    const items = [...selectedBlock.items]
    ;[items[itemIndex], items[target]] = [items[target], items[itemIndex]]
    updateBlock({ items })
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
      ...theme.tokens,
    }))
  }

  const hasPayload = data.ok && Boolean(data.activePageId)

  return (
    <Page
      title="Editor Sito Studio"
      subtitle="Composizione pagine, blocchi, immagini, controlli professionali e pubblicazione del sito."
      actions={
        <>
          <ButtonLink href="/sito-studio" tone="neutral"><Globe2 size={16} /> Cruscotto</ButtonLink>
          <ButtonLink href="/sito-studio/redazione-ai" tone="neutral"><Bot size={16} /> Redazione AI</ButtonLink>
          <ButtonLink href={data.publicUrl || '/sito-studio'} tone="success" target="_blank" rel="noopener"><ExternalLink size={16} /> Apri sito</ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento editor" message="Lettura pagine, blocchi, immagini e controlli reali." /> : null}
      {!loading && error ? <EmptyState title="Editor non disponibile" message={error} /> : null}
      {!loading && !error && !hasPayload ? <EmptyState title="Nessuna pagina configurata" message="Crea una pagina per iniziare la composizione del sito studio." /> : null}

      {!loading && !error && hasPayload ? (
        <>
          <section className="iu-builder-commandbar" aria-label="Azioni editor sito">
            <div>
              <span>{data.site.siteName || 'Sito Studio'}</span>
              <strong>{dirty ? 'Modifiche non salvate' : 'Pagina allineata'}</strong>
            </div>
            {status ? <p className="is-success">{status}</p> : null}
            {error ? <p className="is-danger">{error}</p> : null}
            <button type="button" onClick={() => setPreviewVersion((value) => value + 1)} disabled={busy}>
              <RefreshCw size={15} />
              Aggiorna anteprima
            </button>
            <button type="button" onClick={() => run(() => saveBuilderBlocks(data.activePageId, blocks))} disabled={busy || !data.activePageId}>
              <Save size={15} />
              Salva bozza
            </button>
            <button className="is-primary" type="button" onClick={() => run(() => publishBuilderBlocks(data.activePageId, blocks))} disabled={busy || !data.activePageId}>
              <Send size={15} />
              Pubblica
            </button>
          </section>

          <div className="iu-builder-workspace">
            <BuilderSidebar
              pages={data.pages}
              activePageId={data.activePageId}
              presets={data.blockPresets}
              templates={data.templates}
              busy={busy}
              onPageSelect={(pageId) => loadBuilder(pageId, true)}
              onCreatePage={(values) => run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/pages', values))}
              onDeletePage={(pageId) => run(() => deleteBuilderPage(pageId))}
              onAddBlock={addBlock}
              onApplyTemplate={(templateCode) => run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/template', { templateCode }))}
            />
            <BuilderCanvas
              page={data.activePage}
              blocks={blocks}
              presets={data.blockPresets}
              selectedIndex={selectedIndex}
              previewSize={previewSize}
              previewUrl={data.activePreviewUrl || data.publicUrl}
              previewVersion={previewVersion}
              onSelect={setSelectedIndex}
              onMove={moveBlock}
              onDuplicate={duplicateBlock}
              onDelete={deleteBlock}
              onPreviewSize={setPreviewSize}
              onRefreshPreview={() => setPreviewVersion((value) => value + 1)}
            />
            <BuilderProperties
              block={selectedBlock}
              blockIndex={selectedIndex}
              presets={data.blockPresets}
              assets={data.assets}
              busy={busy}
              onUpdate={updateBlock}
              onAddItem={() => updateBlock({ items: [...(selectedBlock?.items || []), { title: 'Nuovo elemento', text: '', image_url: '', image_alt: '', button_text: '', button_url: '' }] })}
              onUpdateItem={updateItem}
              onMoveItem={moveItem}
              onDuplicateItem={(itemIndex) => selectedBlock && updateBlock({ items: selectedBlock.items.flatMap((item, index) => index === itemIndex ? [item, { ...item }] : [item]) })}
              onDeleteItem={(itemIndex) => selectedBlock && updateBlock({ items: selectedBlock.items.filter((_item, index) => index !== itemIndex) })}
              onAttachAsset={attachAsset}
              onUploadAsset={(file, values) => run(() => uploadBuilderAsset(file, values))}
            />
          </div>

          <BuilderAdminPanels
            validation={data.validation}
            revisions={data.revisions}
            theme={theme}
            templates={data.templates}
            busy={busy}
            onValidate={() => run(() => postBuilderJson('/api/v1/ui/sito-studio/builder/valida', {}))}
            onRestore={(revisionId) => run(() => postBuilderJson(`/api/v1/ui/sito-studio/builder/revisions/${revisionId}/restore`, {}))}
            onThemeChange={setTheme}
            onSaveTheme={saveTheme}
          />
        </>
      ) : null}
    </Page>
  )
}
