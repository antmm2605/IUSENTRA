import { useState } from 'react'
import { formatDateTimeIt } from '@/formatting'
import { safeInternalHref } from '../presentation'
import type { PresidioRecipientSummary } from '../types'

export function RecipientPecProof({ recipient }: { recipient: PresidioRecipientSummary }) {
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  async function save(href: string, label: string) {
    const local = safeInternalHref(href)
    if (!local) return
    setBusy(true)
    setStatus('')
    try {
      const response = await fetch(local, { credentials: 'same-origin', cache: 'no-store' })
      if (!response.ok || !response.headers.get('Content-Type')?.startsWith('message/rfc822')) {
        throw new Error('Originale EML non disponibile. Riprova tra poco.')
      }
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = label.replace(/[^a-z0-9]+/gi, '-').replace(/-$/, '') + '.eml'
      anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 10000)
      setStatus('Originale EML ricevuto. Controlla i download del browser.')
    } catch {
      setStatus('Scaricamento non riuscito. Riprova tra poco.')
    } finally {
      setBusy(false)
    }
  }

  return <>
    {recipient.pec_proof?.length ? <ul aria-label="Prove della notifica PEC">
      {recipient.pec_proof.map((proof) => <li key={proof.label}>
        {proof.href ? <button type="button" disabled={busy} onClick={() => void save(proof.href, proof.label)}>{proof.label} · Scarica originale EML</button> : <span>{proof.label} · {proof.status}</span>}
        {proof.date ? <small>{formatDateTimeIt(proof.date)}{proof.folder ? ` · ${proof.folder}` : ''}</small> : null}
      </li>)}
    </ul> : null}
    {status ? <small role="status">{status}</small> : null}
    {recipient.pec_proof?.length ? (recipient.protocol_replies?.length ? <ul aria-label="Risposte protocollate del destinatario">
      {recipient.protocol_replies.map((reply) => <li key={reply.href}>
        <a href={safeInternalHref(reply.href)} target="_blank" rel="noreferrer">Risposta del destinatario · Protocollo {reply.number}</a>
        <small>{formatDateTimeIt(reply.received_at)} · {reply.folder}</small>
      </li>)}
    </ul> : <small>Nessuna risposta protocollata collegata.</small>) : null}
  </>
}
