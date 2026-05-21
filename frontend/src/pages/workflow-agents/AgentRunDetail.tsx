import { useEffect, useMemo, useState } from 'react'
import { Bot, FileSearch } from 'lucide-react'
import { IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { fetchWorkflowAgentRun, type AgentRun } from './api'
import { AgentRunPreview } from './AgentRunPreview'

function runIdFromPath() {
  const parts = window.location.pathname.split('/').filter(Boolean)
  return parts[2] || ''
}

export function AgentRunDetail() {
  const runId = useMemo(runIdFromPath, [])
  const [run, setRun] = useState<AgentRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchWorkflowAgentRun(runId, controller.signal)
      .then((payload) => {
        if (!payload.ok || !payload.run) setError(payload.message || 'Percorso non disponibile.')
        setRun(payload.run)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [runId])

  if (loading) return <IusLoadingState title="Caricamento regia" message="Recupero piano, proposte e metriche." />
  if (error || !run) return <IusErrorState title="Percorso non disponibile" message={error || 'Il percorso richiesto non è disponibile per questo studio.'} />

  return (
    <IusPageShell
      title="Dettaglio Regia Agentica"
      description="Piano, letture, proposte approvabili, audit e risparmio misurato."
      icon={Bot}
      area="lex"
      actions={<a className="iu-btn" href="/workflow-agents/approvals"><FileSearch size={16} /> Coda approvazioni</a>}
    >
      <AgentRunPreview run={run} onRunChange={setRun} />
    </IusPageShell>
  )
}

export default AgentRunDetail
