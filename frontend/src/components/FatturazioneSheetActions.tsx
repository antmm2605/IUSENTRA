import { useState } from 'react'
import { Copy, Link2, Trash2 } from 'lucide-react'
import { createFatturazionePaymentLink, deleteFatturazioneDraft } from '../fatturazioneData'
import type { FatturazioneDetail } from '../fatturazioneData'
import { Button, ButtonLink } from '../ui/Button'
import './FatturazioneSheetActions.css'

// Azioni della scheda parcella che vivevano nella vista storica /fatturazione/<id>:
// link di pagamento per il cliente ed eliminazione della sola bozza.
export function FatturazioneSheetActions({
  detail,
  onReloadDetail,
  onDeleted,
}: {
  detail: FatturazioneDetail
  onReloadDetail: () => Promise<void>
  onDeleted: () => Promise<void>
}) {
  const [days, setDays] = useState(30)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [freshHref, setFreshHref] = useState('')
  const actions = detail.sheetActions
  const href = freshHref || actions.paymentLink.href
  const subject = `Link pagamento parcella ${detail.number || ''}`.trim()
  const body = href ? `Gentile ${detail.customerName || 'cliente'},\n\npuò pagare la parcella ${detail.number || ''} di ${detail.amountDisplay || ''} da questo link:\n${href}` : ''

  async function createLink() {
    setBusy('link')
    setMessage(null)
    const result = await createFatturazionePaymentLink(detail.id, days)
    setBusy('')
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) {
      setFreshHref(result.paymentHref)
      await onReloadDetail()
    }
  }

  async function copyLink() {
    if (!href) return
    try {
      await navigator.clipboard.writeText(href)
      setMessage({ ok: true, text: 'Link copiato negli appunti.' })
    } catch {
      setMessage({ ok: false, text: 'Copia non riuscita: seleziona il link e copialo a mano.' })
    }
  }

  async function removeDraft() {
    if (!window.confirm(`Eliminare la bozza ${detail.number || ''}? L'operazione non è reversibile.`)) return
    setBusy('delete')
    const result = await deleteFatturazioneDraft(detail.id)
    setBusy('')
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) await onDeleted()
  }

  if (!actions.paymentLink.canCreate && !href && !actions.canDelete) return null

  return (
    <section className="iu-fatt-sheet-actions" aria-label="Pagamento online e bozza">
      {actions.paymentLink.canCreate || href ? (
        <div className="iu-fatt-sheet-actions__block">
          <h3><Link2 size={16} aria-hidden="true" /> Pagamento online</h3>
          {href ? (
            <>
              <p className="iu-fatt-sheet-actions__link">
                <a href={href} target="_blank" rel="noopener noreferrer">{href}</a>
                {actions.paymentLink.expiresAt ? <small>Valido fino al {actions.paymentLink.expiresAt.split('-').reverse().join('/')}</small> : null}
              </p>
              <div className="iu-fatt-sheet-actions__row">
                <Button type="button" tone="neutral" onClick={() => void copyLink()}><Copy size={15} aria-hidden="true" /> Copia link</Button>
                <ButtonLink href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`} tone="neutral">Invia per email</ButtonLink>
                <ButtonLink href={`https://wa.me/?text=${encodeURIComponent(body)}`} tone="neutral" target="_blank" rel="noopener noreferrer">WhatsApp</ButtonLink>
              </div>
            </>
          ) : <p>Nessun link attivo: crealo per far pagare il cliente con carta dalla pagina pubblica dello studio.</p>}
          {actions.paymentLink.canCreate ? (
            <div className="iu-fatt-sheet-actions__row">
              <label>
                Validità (giorni)
                <input type="number" min={1} max={90} value={days} onChange={(event) => { const value = Number(event.currentTarget.value) || 30; setDays(value) }} />
              </label>
              <Button type="button" tone="primary" disabled={busy === 'link'} onClick={() => void createLink()}>
                {busy === 'link' ? 'Creazione…' : href ? 'Rinnova link' : 'Crea link di pagamento'}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
      {actions.canDelete ? (
        <div className="iu-fatt-sheet-actions__block">
          <h3><Trash2 size={16} aria-hidden="true" /> Bozza</h3>
          <p>La bozza non è ancora un documento fiscale e si può eliminare.</p>
          <Button type="button" tone="danger" disabled={busy === 'delete'} onClick={() => void removeDraft()}>
            {busy === 'delete' ? 'Eliminazione…' : 'Elimina bozza'}
          </Button>
        </div>
      ) : null}
      {message ? <p className={message.ok ? 'iu-fatt-sheet-actions__msg' : 'iu-fatt-sheet-actions__msg is-error'} role="status">{message.text}</p> : null}
    </section>
  )
}
