import { CheckCircle2, FileSearch, ShieldCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState } from '@/components/iusentra'
import { approveWorkflowAgentRun, rejectWorkflowAgentRun, type AgentRun } from './api'

const statusLabel: Record<string, string> = {
  pending: 'In attesa',
  running: 'In corso',
  done: 'Letto',
  needs_approval: 'Da approvare',
  executed: 'Eseguito',
  blocked: 'Bloccato',
  failed: 'Errore',
  cancelled: 'Rifiutato',
}

export function AgentRunPreview({ run, onRunChange }: { run: AgentRun; onRunChange?: (run: AgentRun) => void }) {
  const pendingStepIds = run.proposals.filter((proposal) => proposal.status === 'pending').map((proposal) => proposal.step_id)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function approveAll() {
    setBusy(true)
    const payload = await approveWorkflowAgentRun(run.id, pendingStepIds)
    setBusy(false)
    if (payload.run) onRunChange?.(payload.run)
    setMessage(payload.ok ? 'Proposte approvate ed eseguite dove consentito.' : payload.message || 'Approvazione non completata.')
  }

  async function rejectAll() {
    setBusy(true)
    const payload = await rejectWorkflowAgentRun(run.id, pendingStepIds, 'Non approvato dalla revisione.')
    setBusy(false)
    if (payload.run) onRunChange?.(payload.run)
    setMessage(payload.ok ? 'Proposte rifiutate.' : payload.message || 'Rifiuto non completato.')
  }

  return (
    <div className="grid gap-4">
      <Card size="sm">
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center justify-between gap-2">
            {run.plan.title}
            <Badge variant={run.status === 'executed' ? 'default' : 'secondary'}>{statusLabel[run.status] || run.status}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted-foreground">
          <p>{run.plan.description}</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <span>Base manuale: <strong className="text-foreground">{run.plan.baseline_minutes} min</strong></span>
            <span>Revisione stimata: <strong className="text-foreground">{run.plan.expected_review_minutes} min</strong></span>
            <span>Risparmio: <strong className="text-foreground">{run.metrics?.saving_percentage ?? 0}%</strong></span>
          </div>
          {run.plan.warnings?.length ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
              {run.plan.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <section className="grid gap-3 lg:grid-cols-2">
        <Card size="sm">
          <CardHeader><CardTitle className="flex items-center gap-2"><FileSearch aria-hidden="true" /> Piano e letture</CardTitle></CardHeader>
          <CardContent className="grid gap-2">
            {run.plan.steps.map((step) => (
              <div key={step.id} className="rounded-md border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <strong>{step.title}</strong>
                  <Badge variant={step.mutates_state ? 'secondary' : 'outline'}>{step.mutates_state ? 'Revisione' : statusLabel[step.status] || step.status}</Badge>
                </div>
                {step.error_message ? <p className="mt-1 text-sm text-destructive">{step.error_message}</p> : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card size="sm">
          <CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden="true" /> Proposte da revisione</CardTitle></CardHeader>
          <CardContent className="grid gap-3">
            {run.proposals.length ? run.proposals.map((proposal) => (
              <div key={proposal.id} className="rounded-md border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <strong>{proposal.title}</strong>
                  <Badge variant={proposal.status === 'pending' ? 'secondary' : 'outline'}>{statusLabel[proposal.status] || proposal.status}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{proposal.impact || 'Proposta operativa da approvare.'}</p>
              </div>
            )) : <IusEmptyState title="Nessuna proposta in attesa" message="Il percorso ha completato solo letture operative." icon={CheckCircle2} />}
            {pendingStepIds.length ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={approveAll} disabled={busy}><CheckCircle2 aria-hidden="true" /> Approva selezione</Button>
                <Button type="button" variant="outline" onClick={rejectAll} disabled={busy}><XCircle aria-hidden="true" /> Rifiuta</Button>
              </div>
            ) : null}
            {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

