import { useEffect, useState } from 'react'
import { CheckCircle2, FileCheck2, PenSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { approveLegalSkillRun, exportLegalSkillRun, fetchLegalSkillRun, importDraftToEditor } from '../api'
import type { LegalSkillRunResult } from '../types'
import { CitationList } from '../components/CitationList'
import { ReviewerNoteBox } from '../components/ReviewerNoteBox'
import { SkillFindingTable } from '../components/SkillFindingTable'
import { SkillRunStatusBadge } from '../components/SkillRunStatusBadge'
import { can } from '../permissions'

function routeRunId() {
  return window.location.pathname.match(/^\/legal-skills\/runs\/([^/]+)$/)?.[1] || ''
}

export function LegalSkillsReviewPage() {
  const runId = routeRunId()
  const [loading, setLoading] = useState(Boolean(runId))
  const [error, setError] = useState('')
  const [result, setResult] = useState<LegalSkillRunResult | null>(null)
  const [exportMessage, setExportMessage] = useState('')

  useEffect(() => {
    if (!runId) return
    const controller = new AbortController()
    fetchLegalSkillRun(runId, controller.signal)
      .then((payload) => {
        if (!payload.ok || !payload.result) setError(payload.message || 'Risultato non disponibile.')
        setResult(payload.result || null)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [runId])

  const approve = async () => {
    if (!result) return
    const payload = await approveLegalSkillRun(result.run_id)
    if (payload.ok && payload.result) setResult(payload.result)
    else setError(payload.message || 'Approvazione non riuscita.')
  }

  const exportResult = async () => {
    if (!result) return
    const payload = await exportLegalSkillRun(result.run_id)
    if (payload.ok) setExportMessage('Esportazione pronta nel registro della revisione.')
    else setError(payload.message || 'Esportazione bloccata.')
  }

  const [openingEditor, setOpeningEditor] = useState(false)
  const openInEditor = async () => {
    if (!result?.fascicolo_id || !result.answer || openingEditor) return
    setOpeningEditor(true)
    const payload = await importDraftToEditor(result.fascicolo_id, {
      answer: result.answer,
      title: result.prompt_titolo || 'Bozza Legal Skills',
    })
    if (payload.ok && payload.open_url) {
      window.location.assign(payload.open_url)
      return
    }
    setError(payload.message || 'Apertura nell’editor professionale non riuscita.')
    setOpeningEditor(false)
  }

  if (!runId) {
    return (
      <IusPageShell title="Revisione Legal Skills" description="Apri un risultato dalla pagina di esecuzione." icon={FileCheck2} area="lex">
        <IusEmptyState title="Nessun risultato selezionato" message="Esegui una skill e poi apri la scheda di revisione." actionHref="/legal-skills/run" actionLabel="Esegui skill" icon={FileCheck2} />
      </IusPageShell>
    )
  }
  if (loading) return <IusLoadingState title="Caricamento revisione" message="Recupero risultato e presidi." />

  return (
    <IusPageShell
      title="Revisione Legal Skills"
      description="Controlla bozza, fonti e punti da approvare prima di usare il risultato."
      icon={FileCheck2}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills/run">Nuova esecuzione</a></Button>}
    >
      {error ? <IusErrorState title="Attenzione" message={error} /> : null}
      {result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2">
              Risultato Legal Skills
              <SkillRunStatusBadge status={result.status} />
              <Badge variant="outline">Confidenza {result.confidence}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <ReviewerNoteBox note={result.reviewer_note} />
            <p className="text-sm leading-6">{result.answer}</p>
            <SkillFindingTable findings={result.findings || []} />
            <CitationList citations={result.citations || []} />
            {exportMessage ? <p className="rounded-lg border bg-muted p-3 text-sm">{exportMessage}</p> : null}
            <div className="flex flex-wrap justify-end gap-2">
              {result.fascicolo_id ? (
                <Button type="button" variant="outline" onClick={openInEditor} disabled={openingEditor}>
                  <PenSquare aria-hidden="true" />
                  {openingEditor ? 'Apertura in corso…' : "Apri nell'editor professionale"}
                </Button>
              ) : null}
              {can('legal_skills.approva') ? (
                <Button type="button" onClick={approve} disabled={!result.needs_review} variant="outline">
                  <CheckCircle2 aria-hidden="true" />
                  {result.needs_review ? 'Approva' : 'Approvato'}
                </Button>
              ) : null}
              {can('legal_skills.esporta') ? (
                <Button type="button" onClick={exportResult} disabled={result.disable_exports || !result.approved_at}>
                  Esporta risultato
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </IusPageShell>
  )
}
