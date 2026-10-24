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
  const isStudio = (source: GiurisprudenzaSource) =>
    source.id === 'manuale_interno' || source.accessMode === 'Materiale autorizzato'
  const isArchive = (source: GiurisprudenzaSource) =>
    !isStudio(source) && (source.id === 'openga' || (source.corpusCount ?? 0) > 0)
  const groups = [
    { title: 'Archivi collegati a IUSENTRA', items: sources.filter(isArchive) },
    { title: 'Siti ufficiali da consultare', items: sources.filter(source => !isArchive(source) && !isStudio(source)) },
    { title: 'Materiale dello studio', items: sources.filter(isStudio) },
  ]
  function card(source: GiurisprudenzaSource) {
    const publicReady = source.id === 'openga' && inventory?.ok && Number.isInteger(inventory.decisioni)
    const corpusReady = (source.corpusCount ?? 0) > 0 && !isStudio(source)
    const studio = isStudio(source)
    return <article className="iu-legal-source iu-od-source-card" key={source.id}>
      <header className="iu-legal-source__header"><div>
        <span className="iu-od-source-badge">{source.kind || 'Fonte'}</span><h4>{source.label}</h4>
      </div><Badge tone={publicReady || corpusReady ? 'success' : 'neutral'}>{publicReady || corpusReady ? 'Archivio presente' : studio ? 'Materiale dello studio' : 'Sito esterno'}</Badge></header>
      {source.id === 'openga' ? <>
        <p><strong>{publicReady ? inventory.decisioni!.toLocaleString('it-IT') + ' decisioni' : inventory === null ? 'Verifica del catalogo…' : 'Conteggio non disponibile'}</strong></p>
        <p>Ricerca in IUSENTRA per estremi, oggetto ed esito. Il catalogo non comprende motivazioni e testi integrali.</p>
      </> : corpusReady ? <>
        <p><strong>{source.corpusCount!.toLocaleString('it-IT')} decisioni nell’archivio collegato</strong></p>
        <p>{source.corpusFullTextCount?.toLocaleString('it-IT') ?? 'Numero non verificato'} con testo integrale.</p>
      </> : studio ? <p>{source.count.toLocaleString('it-IT')} schede salvate nello studio.</p> : <>
        <p>Consultazione sul sito ufficiale.</p>
        <p>{source.corpusCount === 0 ? 'Nessuna decisione importata nel corpus dello studio.' : 'Disponibilità nel corpus dello studio non verificata.'}</p>
      </>}
      <details>
        <summary>Copertura e accesso</summary>
        {source.coverage && <p>{source.coverage}</p>}
        {source.accessMode && <p>Accesso: {source.accessMode}.</p>}
        {!studio && <p>Schede salvate nello studio: {source.count.toLocaleString('it-IT')}. Questo numero non è il totale della fonte.</p>}
        {source.resolutionNote && <p>{source.resolutionNote}</p>}
      </details>
      <footer className="iu-od-action-row iu-legal-source__actions">
        {source.id === 'openga' && <ButtonLink href="#ricerca-openga" tone="neutral">Cerca decisioni</ButtonLink>}
        {source.sourceHref && <ButtonLink href={source.sourceHref} tone="neutral" target="_blank" rel="noreferrer">Apri sito della fonte</ButtonLink>}
        {source.legacyHref && <ButtonLink href={source.legacyHref} tone="neutral">Scheda fonte</ButtonLink>}
      </footer>
    </article>
  }
  return <Panel title="Fonti e archivi" subtitle="Gli archivi collegati contengono dati consultabili da IUSENTRA. I siti esterni si aprono separatamente e non sono archivi importati.">
    {groups.filter(group => group.items.length > 0).map(group => <section key={group.title}>
      <h3>{group.title}</h3>
      <div className="iu-legal-source-grid">{group.items.map(card)}</div>
    </section>)}
  </Panel>
}
