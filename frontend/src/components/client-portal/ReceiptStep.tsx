import { useEffect, useState } from 'react'
import { Download, ReceiptText } from 'lucide-react'
import { clientPortalDocumentUrl } from '../../clientPortalData'
import { loadSigningReceipt } from '../../clientPortalSigning'

type ReceiptData = {
  generatoIl?: string
  preventivo?: { numero: string; stato: string; impronta: string } | null
  conferimento?: { numero: string; stato: string; impronta: string } | null
  firma?: { eseguita: boolean; via: string; documentoFirmatoId: string; improntaFirmato: string; tipo: string }
  identita?: { inviata: boolean; stato: string }
}

export function ReceiptStep() {
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [message, setMessage] = useState('Caricamento ricevuta…')

  useEffect(() => {
    void (async () => {
      const response = await loadSigningReceipt()
      if (response.ok && response.receipt) {
        setReceipt(response.receipt as ReceiptData)
        setMessage('')
      } else {
        setMessage(response.message || 'Ricevuta non disponibile.')
      }
    })()
  }, [])

  if (!receipt) return <p className="iu-client-portal-muted">{message}</p>

  return (
    <div className="iu-signing-receipt">
      <p className="iu-signing-receipt__title">
        <ReceiptText size={17} aria-hidden="true" />Riepilogo del percorso completato {receipt.generatoIl ? `— ${receipt.generatoIl}` : ''}
      </p>
      <dl className="iu-signing-card__meta">
        {receipt.preventivo ? (
          <div><dt>Preventivo {receipt.preventivo.numero}</dt><dd>{receipt.preventivo.stato} · impronta <code>{receipt.preventivo.impronta}…</code></dd></div>
        ) : null}
        {receipt.conferimento ? (
          <div><dt>Conferimento {receipt.conferimento.numero}</dt><dd>impronta <code>{receipt.conferimento.impronta}…</code></dd></div>
        ) : null}
        {receipt.firma ? (
          <div><dt>Firma</dt><dd>{receipt.firma.tipo}</dd></div>
        ) : null}
        {receipt.identita?.inviata ? (
          <div><dt>Documento d’identità</dt><dd>{receipt.identita.stato === 'approvato' ? 'Approvato' : 'In revisione presso lo studio'}</dd></div>
        ) : null}
      </dl>
      {receipt.firma?.documentoFirmatoId ? (
        <a className="iu-client-portal-button secondary" href={clientPortalDocumentUrl(receipt.firma.documentoFirmatoId)}>
          <Download size={15} aria-hidden="true" />Scarica il documento firmato
        </a>
      ) : null}
      <p className="iu-client-portal-muted">
        Conserva questa pagina come promemoria: lo studio custodisce il documento firmato e le relative evidenze.
      </p>
    </div>
  )
}
