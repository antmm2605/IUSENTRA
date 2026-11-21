import { useBusyActivity } from '../../ui/useBusyActivity'
import { useEffect, useState } from 'react'
import { Bot, Clock3, PlayCircle, ShieldCheck, Sunrise } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { fetchWorkflowAgentsHome, previewWorkflowAgent, type WorkflowAgentsHomePayload } from './api'

export function dataOraIt(valore?: string): string {
  if (!valore) return ''
  const data = new Date(valore)
  if (Number.isNaN(data.getTime())) return ''
  return data.toLocaleString('it-IT', { timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function WorkflowAgentsHome() {
  const [payload, setPayload] = useState<WorkflowAgentsHomePayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyCode, setBusyCode] = useState('')
  useBusyActivity(Boolean(busyCode), 'Preparazione della lavorazione…')

  useEffect(() => {
    const controller = new AbortController()
    fetchWorkflowAgentsHome(controller.signal)
      .then((data) => {
        if (!data.ok) setError(data.message || 'Lavori automatici di Lex non disponibili.')
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
    setError(result.message || 'Anteprima non avviata.')
  }

  if (loading) return <IusLoadingState title="Caricamento dei lavori automatici di Lex" message="Recupero dei lavori e degli ultimi giri." />
  if (!payload) return <IusErrorState title="Lavori automatici non disponibili" message={error || 'Dati non disponibili.'} />

  const canPreview = payload.feature_flags.enabled

  return (
    <IusPageShell
      title="Lavori automatici di Lex"
      description="Lex legge i dati dello studio e prepara proposte: nulla cambia finché non approvi."
      icon={Bot}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/workflow-agents/approvals"><ShieldCheck aria-hidden="true" /> Coda approvazioni</a></Button>}
    >
      {error ? <IusErrorState title="Avviso operativo" message={error} /> : null}
      {payload.presidio_mattutino ? (
        <Card size="sm">
          <CardContent className="flex flex-wrap items-center gap-2 pt-4 text-sm text-muted-foreground">
            <Sunrise size={16} aria-hidden="true" />
            <span>
              Il controllo automatico di ogni mattina (fascicoli, scadenze, agenda e comunicazioni) è{' '}
              <a className="underline" href={payload.presidio_mattutino.href}>{payload.presidio_mattutino.titolo}</a>
              {payload.presidio_mattutino.pianificazione ? `, ${payload.presidio_mattutino.pianificazione.toLowerCase()}` : ''}.
              {payload.presidio_mattutino.ultimo_giro?.data
                ? ` Ultimo giro: ${dataOraIt(payload.presidio_mattutino.ultimo_giro.data)} · ${payload.presidio_mattutino.ultimo_giro.esito || 'esito non indicato'}.`
                : ' Nessun giro registrato.'}
              {' '}I lavori qui sotto si avviano a mano.
            </span>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {payload.workflows.map((workflow) => (
          <Card key={workflow.code} size="sm">
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2">
                {workflow.title}
                <Badge variant={workflow.risk_level === 'high' ? 'destructive' : 'secondary'}>{workflow.risk_level === 'high' ? 'Alta cautela' : 'Con controllo'}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-muted-foreground">
              <p>{workflow.description}</p>
              {payload.ultimi_giri?.[workflow.code] ? (
                <div className="grid gap-1">
                  <a className="flex items-center gap-2 underline" href={`/workflow-agents/runs/${payload.ultimi_giri[workflow.code].run_id}`}>
                    <Clock3 size={15} aria-hidden="true" /> Ultimo giro: {dataOraIt(payload.ultimi_giri[workflow.code].data)} · {payload.ultimi_giri[workflow.code].esito}
                  </a>
                  {payload.ultimi_giri[workflow.code].problemi.map((problema) => <span key={problema} className="text-destructive">{problema}</span>)}
                </div>
              ) : <span className="flex items-center gap-2"><Clock3 size={15} aria-hidden="true" /> Mai avviato</span>}
            </CardContent>
            <CardFooter className="justify-between gap-2">
              <Button type="button" onClick={() => runPreview(workflow.code)} disabled={!canPreview || busyCode === workflow.code}>
                <PlayCircle aria-hidden="true" /> Esegui anteprima
              </Button>
              {!payload.feature_flags.writeActions ? <Badge variant="outline">Solo anteprima: nessuna modifica ai dati</Badge> : null}
            </CardFooter>
          </Card>
        ))}
      </section>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Ultimi giri</h2>
        {payload.latest_runs.length ? payload.latest_runs.map((run) => (
          <a key={run.id} className="rounded-md border px-3 py-2 text-sm transition hover:bg-muted" href={`/workflow-agents/runs/${run.id}`}>
            <strong>{run.plan.title}</strong>
            {run.created_at ? <span className="ml-2 text-muted-foreground">{dataOraIt(run.created_at)}</span> : null}
          </a>
        )) : <IusEmptyState title="Nessun percorso ancora eseguito" message="Avvia un'anteprima per generare piano, evidenze e proposte approvabili." icon={Bot} />}
      </section>
    </IusPageShell>
  )
}

export default WorkflowAgentsHome
