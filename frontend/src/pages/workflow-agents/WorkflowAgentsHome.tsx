import { useEffect, useState } from 'react'
import { Bot, Clock3, PlayCircle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { AgentMetricsPanel } from './AgentMetricsPanel'
import { fetchWorkflowAgentsHome, previewWorkflowAgent, type WorkflowAgentsHomePayload } from './api'

export function WorkflowAgentsHome() {
  const [payload, setPayload] = useState<WorkflowAgentsHomePayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyCode, setBusyCode] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchWorkflowAgentsHome(controller.signal)
      .then((data) => {
        if (!data.ok) setError(data.message || 'Regia Agentica non disponibile.')
        setPayload(data)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  async function runPreview(code: string) {
    setBusyCode(code)
    const result = await previewWorkflowAgent(code)
    setBusyCode('')
    if (result.run?.id) {
      window.location.href = `/workflow-agents/runs/${result.run.id}`
      return
    }
    setError(result.message || 'Preview non avviata.')
  }

  if (loading) return <IusLoadingState title="Caricamento Regia Agentica" message="Recupero percorsi, metriche e ultime attività." />
  if (!payload) return <IusErrorState title="Regia non disponibile" message={error || 'Dati non disponibili.'} />

  const canPreview = payload.feature_flags.enabled

  return (
    <IusPageShell
      title="Regia Agentica Studio"
      description="Lex pianifica letture operative, prepara proposte e misura il tempo risparmiato senza scritture automatiche."
      icon={Bot}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/workflow-agents/approvals"><ShieldCheck aria-hidden="true" /> Coda approvazioni</a></Button>}
    >
      {error ? <IusErrorState title="Avviso operativo" message={error} /> : null}
      <AgentMetricsPanel metrics={payload.metrics} />

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {payload.workflows.map((workflow) => (
          <Card key={workflow.code} size="sm">
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2">
                {workflow.title}
                <Badge variant={workflow.risk_level === 'high' ? 'destructive' : 'secondary'}>{workflow.risk_level === 'high' ? 'Alta cautela' : 'Governato'}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-muted-foreground">
              <p>{workflow.description}</p>
              <span className="flex items-center gap-2"><Clock3 size={15} /> Base manuale stimata: {workflow.baseline_minutes} minuti</span>
            </CardContent>
            <CardFooter className="justify-between gap-2">
              <Button type="button" onClick={() => runPreview(workflow.code)} disabled={!canPreview || busyCode === workflow.code}>
                <PlayCircle aria-hidden="true" /> Esegui preview
              </Button>
              {!payload.feature_flags.writeActions ? <Badge variant="outline">Scritture spente</Badge> : null}
            </CardFooter>
          </Card>
        ))}
      </section>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Ultimi percorsi</h2>
        {payload.latest_runs.length ? payload.latest_runs.map((run) => (
          <a key={run.id} className="rounded-md border px-3 py-2 text-sm transition hover:bg-muted" href={`/workflow-agents/runs/${run.id}`}>
            <strong>{run.plan.title}</strong>
            <span className="ml-2 text-muted-foreground">{run.metrics?.saving_percentage ?? 0}% riduzione misurata</span>
          </a>
        )) : <IusEmptyState title="Nessun percorso ancora eseguito" message="Avvia una preview per generare piano, evidenze e proposte approvabili." icon={Bot} />}
      </section>
    </IusPageShell>
  )
}

export default WorkflowAgentsHome
