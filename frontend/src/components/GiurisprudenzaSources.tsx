import { useEffect, useState } from 'react'
import { apiJson } from '../lib/apiClient'
import type { GiurisprudenzaSource } from '../giurisprudenzaData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { Panel } from '../ui/Panel'

type Inventory = { ok: boolean; decisioni?: number; relazioni?: number }

export function GiurisprudenzaSources({ sources }: { sources: GiurisprudenzaSource[] }) {
  const [inventory, setInventory] = useState<Inventory | null>(null)
  const hasOpenGA = sources.some(source => source.id === 'openga')
  useEffect(() => {
    if (!hasOpenGA) return
    const controller = new AbortController()
    void apiJson<Inventory>('/api/v1/ui/giurisprudenza/catalogo-amministrativo', { ok: false },
      { signal: controller.signal, activity: false })
      .then(value => { if (!controller.signal.aborted) setInventory(value) })
      .catch(() => { if (!controller.signal.aborted) setInventory({ ok: false }) })
    return () => controller.abort()
  }, [hasOpenGA])
  if (!sources.length) return null
  return <Panel title="Fonti e archivi" subtitle="Le schede dello studio e i cataloghi pubblici sono archivi distinti. I conteggi indicano sempre il proprio archivio.">
    <div className="iu-legal-source-grid">{sources.map(source => {
      const corpusReady = typeof source.corpusCount === 'number' && source.corpusCount > 0
      const publicReady = source.id === 'openga' && inventory?.ok && Number.isInteger(inventory.decisioni)
      return <article className="iu-legal-source iu-od-source-card" key={source.id}>
        <header className="iu-legal-source__header"><div>
          <span className="iu-od-source-badge">{source.kind || 'Fonte'}</span><h3>{source.label}</h3>
        </div><Badge tone={publicReady || corpusReady ? 'success' : 'neutral'}>{publicReady ? 'Catalogo disponibile' : corpusReady ? 'Archivio disponibile' : source.id === 'manuale_interno' ? 'Archivio dello studio' : 'Sito esterno'}</Badge></header>
        <dl className="iu-legal-meta">
          {source.coverage && <div><dt>Copertura dichiarata dalla fonte</dt><dd>{source.coverage}</dd></div>}
          {source.accessMode && <div><dt>Accesso alla fonte</dt><dd>{source.accessMode}</dd></div>}
          <div><dt>Schede salvate nello studio</dt><dd>{source.count.toLocaleString('it-IT')}</dd></div>
          {source.id !== 'openga' && source.id !== 'manuale_interno' && <div><dt>Decisioni nell’archivio collegato</dt><dd>{source.corpusCount == null ? 'Disponibilità non verificata' : source.corpusCount.toLocaleString('it-IT')}</dd></div>}
          {corpusReady && <div><dt>Con testo integrale</dt><dd>{source.corpusFullTextCount?.toLocaleString('it-IT') ?? 'Non verificato'}</dd></div>}
          {source.id === 'openga' && <div><dt>Decisioni nel catalogo pubblico installato</dt><dd>{publicReady
            ? inventory.decisioni!.toLocaleString('it-IT')
            : inventory === null ? 'Verifica in corso…' : 'Conteggio non disponibile'}</dd></div>}
        </dl>
        {source.id === 'openga' ? <p>Il catalogo pubblico contiene estremi, oggetto ed esito. Il conteggio non indica testi integrali o schede dello studio.</p>
          : source.id !== 'manuale_interno' && <p>Il sito ufficiale resta consultabile separatamente. Le schede salvate nello studio non sono il totale delle decisioni della fonte.</p>}
        {source.resolutionNote && <p className="iu-legal-source__resolution">{source.resolutionNote}</p>}
        <footer className="iu-od-action-row iu-legal-source__actions">
          {source.id === 'openga' && <ButtonLink href="#ricerca-openga" tone="neutral">Cerca nel catalogo OpenGA</ButtonLink>}
          {source.sourceHref && <ButtonLink href={source.sourceHref} tone="neutral" target="_blank" rel="noreferrer">Apri sito della fonte</ButtonLink>}
          {source.legacyHref && <ButtonLink href={source.legacyHref} tone="neutral">Scheda fonte</ButtonLink>}
        </footer>
      </article>
    })}</div>
  </Panel>
}
