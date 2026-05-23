import { useEffect, useState } from 'react'
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { approveWorkflowAgentRun, fetchWorkflowAgentApprovals, rejectWorkflowAgentRun, type AgentProposal } from './api'

export function AgentApprovalQueue() {
  const [approvals, setApprovals] = useState<AgentProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')

  function reload() {
    const controller = new AbortController()
    setLoading(true)
    fetchWorkflowAgentApprovals(controller.signal)
      .then((payload) => {
        if (!payload.ok) setError(payload.message || 'Coda non disponibile.')
        setApprovals(payload.approvals || [])
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }

  useEffect(reload, [])

  async function approve(proposal: AgentProposal) {
    setBusyId(proposal.id)
    await approveWorkflowAgentRun(proposal.run_id, [proposal.step_id])
    setBusyId('')
    reload()
  }

  async function reject(proposal: AgentProposal) {
    setBusyId(proposal.id)
    await rejectWorkflowAgentRun(proposal.run_id, [proposal.step_id], 'Rifiutato dalla coda approvazioni.')
    setBusyId('')
    reload()
  }

  if (loading) return <IusLoadingState title="Caricamento approvazioni" message="Recupero le proposte in attesa." />
  if (error && !approvals.length) return <IusErrorState title="Coda non disponibile" message={error} />

  return (
    <IusPageShell
      title="Coda Approvazioni Agentiche"
      description="Azioni proposte dalla regia: nessuna scrittura parte senza conferma umana."
      icon={ShieldCheck}
      area="lex"
    >
      <div className="grid gap-3">
        {approvals.length ? approvals.map((proposal) => (
          <Card key={proposal.id} size="sm">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center justify-between gap-2">
                {proposal.title}
                <Badge variant="secondary">{proposal.risk_level === 'high' ? 'Rischio alto' : 'Da valutare'}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-muted-foreground">
              <p>{proposal.impact || 'Proposta operativa in attesa di revisione.'}</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={() => approve(proposal)} disabled={busyId === proposal.id}><CheckCircle2 aria-hidden="true" /> Approva</Button>
                <Button type="button" variant="outline" onClick={() => reject(proposal)} disabled={busyId === proposal.id}><XCircle aria-hidden="true" /> Rifiuta</Button>
                <Button asChild type="button" variant="ghost"><a href={`/workflow-agents/runs/${proposal.run_id}`}>Apri dettaglio</a></Button>
              </div>
            </CardContent>
          </Card>
        )) : <IusEmptyState title="Nessuna proposta in attesa" message="Le prossime preview agentiche appariranno qui prima di qualsiasi scrittura." icon={ShieldCheck} />}
      </div>
    </IusPageShell>
  )
}

export default AgentApprovalQueue
