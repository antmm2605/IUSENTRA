import { useEffect, useState } from 'react'
import { FileSearch } from 'lucide-react'
import type { FascicoloPaymentItem } from '../fascicoliData'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import './EconomicVerificationPanel.css'

export function EconomicVerificationPanel({ payment, onSourceOpenChange, expanded = false }: { payment: FascicoloPaymentItem; onSourceOpenChange?: (open: boolean) => void; expanded?: boolean }) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  useEffect(() => { onSourceOpenChange?.(Boolean(source)); return () => onSourceOpenChange?.(false) }, [source, onSourceOpenChange])
  const contribution = payment.kind === 'contributo_unificato'
  const heading = contribution ? 'Verifiche e fonti del contributo unificato' : `Verifiche e fonti: ${payment.displayLabel || payment.label}`
  const sources = payment.fontiVerifica || []
  const missing = payment.verificheMancanti || []
  const verifiedMessage = contribution
    ? payment.status === 'non_previsto'
      ? 'Esenzione verificata con la fonte, il cliente, il R.G. e l’ufficio giudiziario.'
      : payment.status === 'pagato'
        ? 'Versamento verificato con la fonte, il cliente, il R.G. e l’ufficio giudiziario.'
        : 'Le fonti consultate sono riportate qui sotto; il versamento non è confermato.'
    : 'Importo e citazione provengono dalla fonte collegata qui sotto.'
  if (!sources.length && !missing.length && !expanded) return null
  return (
    <section className="iu-economic-verification" aria-label={heading}>
      <details open={expanded || undefined}>
        <summary><FileSearch size={16}/> {heading}</summary>
        {missing.length ? <ul aria-label="Riscontri da completare">{missing.map((item) => <li key={item}>{item}</li>)}</ul> : sources.length ? <p>{verifiedMessage}</p> : null}
        {!sources.length ? <p>Non è disponibile un collegamento verificato alla fonte di questa voce. Il documento deve essere recuperato e controllato prima della conferma.</p> : null}
        {payment.importiLetti?.length ? <p>Importi letti nelle fonti: {payment.importiLetti.join(' · ')}. Gli importi da verificare non alimentano automaticamente le anticipazioni.</p> : null}
        <ol className="iu-economic-verification__sources">
          {sources.map((item) => (
            <li key={`${item.fattoId}-${item.documentoId}`}>
              <div>
                <strong>{item.nome}</strong>
                <p>{item.contesto}</p>
                {item.riscontri.map((check) => <small key={check}>{check}</small>)}
              </div>
              {item.previewHref ? <button type="button" onClick={() => setSource({ href: item.previewHref, label: item.nome, context: 'Fonte della verifica economica del fascicolo' })}>Apri fonte</button> : <small>Collegamento alla fonte da verificare nell’archivio.</small>}
            </li>
          ))}
        </ol>
      </details>
      <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
    </section>
  )
}
