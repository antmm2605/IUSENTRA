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
  const missing = payment.verificheMancanti || []
  // Il contributo dice lo stesso stato del conto economico e del quadro (pct/contributo_unificato_stato.py).
  const stato = contribution ? payment.statoContributo : null
  // Senza letture dell'archivio, la fonte è il documento che decide lo stato (ricevuta o autocertificazione).
  const sources = payment.fontiVerifica?.length
    ? payment.fontiVerifica
    : stato?.documento?.href
      ? [{ fattoId: 'stato-contributo', documentoId: stato.documento.id, nome: stato.documento.nome, contesto: stato.dettaglio, previewHref: stato.documento.href, riscontri: [] }]
      : []
  const verifiedMessage = stato
    ? `${stato.etichetta}${stato.norma ? ` (${stato.norma})` : ''}. ${stato.dettaglio}`.trim()
    : contribution
      ? 'Le fonti del contributo sono riportate qui sotto: aprile per verificare ricevuta o autocertificazione.'
      : 'Importo e citazione provengono dalla fonte collegata qui sotto.'
  if (!sources.length && !missing.length && !expanded) return null
  return (
    <section className="iu-economic-verification" aria-label={heading}>
      <details open={expanded || undefined}>
        <summary><FileSearch size={16}/> {heading}</summary>
        {stato || (!missing.length && sources.length) ? <p>{verifiedMessage}</p> : null}
        {missing.length ? <ul aria-label="Riscontri da completare">{missing.map((item) => <li key={item}>{item}</li>)}</ul> : null}
        {!sources.length ? <p>{contribution ? 'Nessuna ricevuta (pagoPA, F23), nota di iscrizione a ruolo o autocertificazione di esenzione collegata al contributo: va recuperata e controllata prima della conferma.' : 'Non è disponibile un collegamento verificato alla fonte di questa voce. Il documento deve essere recuperato e controllato prima della conferma.'}</p> : null}
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
