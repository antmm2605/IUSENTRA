import { useState } from 'react'
import { CheckCircle2, Send, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  postPceApprove,
  postPcePublish,
  postPceSubmitReview,
  statusLabel,
  type PceCard,
  type PceValidation,
} from './procedureCompletionData'

export function ProcedureCompletionReviewPanel({
  card,
  validation,
  permissions,
  onUpdated,
}: {
  card: PceCard
  validation: PceValidation | null
  permissions: string[]
  onUpdated: (esito: { card: PceCard | null; validation: PceValidation | null }) => void
}) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [errore, setErrore] = useState('')

  const can = (permesso: string) => permissions.includes(permesso)

  const run = (azione: () => Promise<{ ok: boolean; errore: string; card: PceCard | null; validation: PceValidation | null }>) => {
    setBusy(true)
    setErrore('')
    azione()
      .then((esito) => {
        if (esito.ok) onUpdated({ card: esito.card, validation: esito.validation })
        else setErrore(esito.errore || 'Operazione non completata.')
      })
      .finally(() => setBusy(false))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <ShieldCheck size={18} aria-hidden="true" />
          Revisione avvocato
        </CardTitle>
      </CardHeader>
      <CardContent className="pce-stack">
        <div className="pce-row">
          <span>Stato</span>
          <Badge variant={card.status === 'published' ? 'default' : 'secondary'}>{statusLabel(card.status)}</Badge>
        </div>
        {card.review_avvocato.reviewer ? (
          <p className="pce-hint">
            Revisionata da {card.review_avvocato.reviewer}
            {card.review_avvocato.reason ? ` - ${card.review_avvocato.reason}` : ''}
          </p>
        ) : (
          <p className="pce-hint">Nessuna revisione registrata: la scheda resta una bozza.</p>
        )}
        {validation ? (
          <div className="pce-validation">
            {validation.blocking_errors.map((msg) => (
              <p className="pce-validation__error" key={msg}>{msg}</p>
            ))}
            {validation.errors.map((msg) => (
              <p className="pce-validation__error" key={msg}>{msg}</p>
            ))}
            {validation.warnings.map((msg) => (
              <p className="pce-validation__warning" key={msg}>{msg}</p>
            ))}
            {validation.privacy_review_required ? (
              <p className="pce-validation__warning">Richiesta verifica privacy sulle fonti interne.</p>
            ) : null}
          </div>
        ) : null}
        <label className="pce-field">
          <span>Motivazione (registrata in audit)</span>
          <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={2} />
        </label>
        {errore ? <p className="pce-validation__error" role="alert">{errore}</p> : null}
        <div className="pce-actions">
          {can('procedure_completion.esegui') && card.status === 'draft' ? (
            <Button type="button" disabled={busy} onClick={() => run(() => postPceSubmitReview(card.id, reason))}>
              <Send size={14} aria-hidden="true" /> Invia in revisione
            </Button>
          ) : null}
          {can('procedure_completion.approva') && card.status !== 'published' ? (
            <Button
              type="button"
              variant="secondary"
              disabled={busy || (validation ? !validation.approvable : false)}
              onClick={() => run(() => postPceApprove(card.id, reason))}
            >
              <CheckCircle2 size={14} aria-hidden="true" /> Approva come avvocato
            </Button>
          ) : null}
          {can('procedure_completion.pubblica') && card.status === 'approved' ? (
            <Button
              type="button"
              disabled={busy || (validation ? !validation.publishable : false)}
              onClick={() => run(() => postPcePublish(card.id))}
            >
              Pubblica scheda
            </Button>
          ) : null}
        </div>
        <p className="pce-hint">
          La pubblicazione richiede fonti ufficiali o tecniche, citazioni verificabili e approvazione: in mancanza resta bloccata.
        </p>
      </CardContent>
    </Card>
  )
}
