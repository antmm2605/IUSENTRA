import { useEffect, useState } from 'react'
import { Badge } from './dashboard'
import type { FascicoloSentenzeEconomicheItem } from '../fascicoliData'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'

export function EconomicEvidenceCard({ item, onSourceOpenChange }: { item: FascicoloSentenzeEconomicheItem; onSourceOpenChange: (open: boolean) => void }) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [expanded, setExpanded] = useState(false)
  const sources = (item.sources || []).filter(s => s.href)
  useEffect(() => { onSourceOpenChange(Boolean(source)); return () => onSourceOpenChange(false) }, [source, onSourceOpenChange])
  const content = <><span>{item.label}</span><strong>{item.value}</strong><small>{item.hint}</small></>
  return <article className={sources.length ? 'has-source' : undefined}>
    {sources.length ? <button type="button" className="iu-economic-source-card" aria-label={`Apri fonte: ${item.label}, ${item.value}`} onClick={() => sources.length === 1 ? setSource(sources[0]) : setExpanded(v => !v)}>
      <div className="iu-economic-source-card__content">{content}</div><Badge tone={item.tone}>{item.label.includes('verificare') ? 'Verifica' : 'Rilevato'}</Badge><small className="iu-economic-source-card__action">{sources.length === 1 ? 'Apri fonte' : `Consulta ${sources.length} fonti`}</small>
    </button> : <div>{content}</div>}
    {!sources.length ? <Badge tone={item.tone}>{item.label.includes('verificare') ? 'Verifica' : 'Rilevato'}</Badge> : null}
    {expanded ? <div>{sources.map(s => <button type="button" key={s.href} onClick={() => setSource(s)}>{s.label}</button>)}</div> : null}
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </article>
}
