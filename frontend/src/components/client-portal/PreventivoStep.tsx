import { useState } from 'react'
import { Download, FileCheck2, FileX2 } from 'lucide-react'
import { clientPortalDocumentUrl } from '../../clientPortalData'
import { acceptPreventivo, declinePreventivo, type PreventivoSummary, type SigningConsentsPayload } from '../../clientPortalSigning'

type PreventivoStepProps = {
  preventivi: PreventivoSummary[]
  consents: SigningConsentsPayload
  onResult: (ok: boolean, message: string, overview?: unknown) => void
}

function euro(value: number): string {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(value || 0)
}

const STATO_LABEL: Record<string, string> = {
  INVIATO: 'In attesa di risposta',
  APERTO: 'In attesa di risposta',
  ACCETTATO: 'Accettato',
  CONVERTITO: 'Convertito in incarico',
  RIFIUTATO: 'Rifiutato',
}

export function PreventivoStep({ preventivi, consents, onResult }: PreventivoStepProps) {
  const [readConfirmed, setReadConfirmed] = useState<Record<string, boolean>>({})
  const [declineReason, setDeclineReason] = useState<Record<string, string>>({})
  const [declining, setDeclining] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState('')

  if (!preventivi.length) {
    return <p className="iu-client-portal-muted">Nessun preventivo disponibile al momento: lo studio ti avviserà quando sarà pronto.</p>
  }

  const accept = async (preventivo: PreventivoSummary) => {
    setBusy(preventivo.id)
    const response = await acceptPreventivo(preventivo.id, {
      accepted: true,
      pdfSha256: preventivo.pdfSha256,
      declaration: consents.preventivo.text,
    })
    setBusy('')
    onResult(response.ok, response.message || (response.ok ? 'Preventivo accettato.' : 'Operazione non completata.'), response.overview)
  }

  const decline = async (preventivo: PreventivoSummary) => {
    setBusy(preventivo.id)
    const response = await declinePreventivo(preventivo.id, declineReason[preventivo.id] || '')
    setBusy('')
    setDeclining((current) => ({ ...current, [preventivo.id]: false }))
    onResult(response.ok, response.message || 'Operazione non completata.', response.overview)
  }

  return (
    <div className="iu-signing-list">
      {preventivi.map((preventivo) => {
        const decided = ['ACCETTATO', 'CONVERTITO', 'RIFIUTATO'].includes(preventivo.stato)
        const canDecide = ['INVIATO', 'APERTO'].includes(preventivo.stato)
        return (
          <article className={`iu-signing-card ${preventivo.highlighted ? 'is-highlighted' : ''}`} key={preventivo.id}>
            <header className="iu-signing-card__head">
              <div>
                <strong>Preventivo {preventivo.numero}</strong>
                <span>{preventivo.oggetto}</span>
              </div>
              <span className={`iu-signing-badge is-${preventivo.stato.toLowerCase()}`}>
                {STATO_LABEL[preventivo.stato] || preventivo.stato}
              </span>
            </header>
            <dl className="iu-signing-card__meta">
              <div><dt>Totale</dt><dd>{euro(preventivo.totale)}</dd></div>
              <div><dt>Versione</dt><dd>{preventivo.versione}</dd></div>
              {preventivo.pdfSha256 ? (
                <div><dt>Impronta documento</dt><dd><code>{preventivo.pdfSha256.slice(0, 16)}…</code></dd></div>
              ) : null}
            </dl>
            {preventivo.documentId ? (
              <a className="iu-client-portal-button secondary" href={clientPortalDocumentUrl(preventivo.documentId)}>
                <Download size={15} aria-hidden="true" />Scarica il PDF del preventivo
              </a>
            ) : null}
            {canDecide ? (
              <div className="iu-signing-card__decide">
                <label className="iu-signing-consent">
                  <input
                    type="checkbox"
                    checked={Boolean(readConfirmed[preventivo.id])}
                    onChange={(event) => setReadConfirmed((current) => ({ ...current, [preventivo.id]: event.target.checked }))}
                  />
                  <span>{consents.preventivo.text}</span>
                </label>
                <div className="iu-signing-actions">
                  <button
                    className="iu-client-portal-button"
                    type="button"
                    disabled={!readConfirmed[preventivo.id] || busy === preventivo.id}
                    onClick={() => void accept(preventivo)}
                  >
                    <FileCheck2 size={16} aria-hidden="true" />
                    {busy === preventivo.id ? 'Invio in corso…' : 'Accetto il preventivo'}
                  </button>
                  <button
                    className="iu-client-portal-button secondary"
                    type="button"
                    disabled={busy === preventivo.id}
                    onClick={() => setDeclining((current) => ({ ...current, [preventivo.id]: !current[preventivo.id] }))}
                  >
                    <FileX2 size={16} aria-hidden="true" />Non accetto
                  </button>
                </div>
                {declining[preventivo.id] ? (
                  <div className="iu-signing-decline">
                    <label htmlFor={`decline-${preventivo.id}`}>Motivo del rifiuto (facoltativo)</label>
                    <textarea
                      id={`decline-${preventivo.id}`}
                      maxLength={500}
                      value={declineReason[preventivo.id] || ''}
                      onChange={(event) => setDeclineReason((current) => ({ ...current, [preventivo.id]: event.target.value }))}
                      placeholder="Esempio: preferisco un compenso a forfait."
                    />
                    <button className="iu-client-portal-button danger" type="button" disabled={busy === preventivo.id} onClick={() => void decline(preventivo)}>
                      Confermo il rifiuto
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
            {decided && preventivo.accettatoIl ? (
              <p className="iu-client-portal-muted">Risposta registrata: lo studio ha ricevuto l’esito.</p>
            ) : null}
          </article>
        )
      })}
    </div>
  )
}
