import { useEffect, useState } from 'react'
import { FileSearch } from 'lucide-react'
import type { FascicoloPaymentItem } from '../fascicoliData'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import './EconomicVerificationPanel.css'

export function EconomicVerificationPanel({ payment, onSourceOpenChange }: { payment: FascicoloPaymentItem; onSourceOpenChange: (open: boolean) => void }) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  useEffect(() => { onSourceOpenChange(Boolean(source)); return () => onSourceOpenChange(false) }, [source, onSourceOpenChange])
  const contribution = payment.kind === 'contributo_unificato'
  const heading = contribution ? 'Verifiche e fonti del contributo unificato' : 'Fonte della liquidazione e importo letto'
  const sources = payment.fontiVerifica || []
  const missing = payment.verificheMancanti || []
  if (!sources.length && !missing.length) return null
  return (
    <section className="iu-economic-verification" aria-label={heading}>
      <details>
        <summary><FileSearch size={16}/> {heading}</summary>
        {missing.length ? <ul aria-label="Riscontri da completare">{missing.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{contribution ? 'Versamento verificato sul contenuto, cliente e RG.' : 'Importo e citazione provengono dalla fonte collegata qui sotto.'}</p>}
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
