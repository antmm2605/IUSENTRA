import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, FileSearch, PlayCircle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { approveLegalSkillRun, fetchLegalSkillPacks, fetchLegalSkills, fetchLegalSkillsProfile, runLegalSkill } from '../api'
import type { LegalSkill, LegalSkillPack, LegalSkillProfile, LegalSkillRunResult } from '../types'
import { CitationList } from '../components/CitationList'
import { EscalationBox } from '../components/EscalationBox'
import { ReviewerNoteBox } from '../components/ReviewerNoteBox'
import { SkillFindingTable } from '../components/SkillFindingTable'
import { SkillRunStatusBadge } from '../components/SkillRunStatusBadge'
import { can } from '../permissions'

function routePrefill() {
  const url = new URL(window.location.href)
  const match = window.location.pathname.match(/^\/legal-skills\/packs\/([^/]+)\/skills\/([^/]+)\/run$/)
  return {
    packId: match?.[1] || url.searchParams.get('pack') || '',
    skillId: match?.[2] || url.searchParams.get('skill') || '',
  }
}

export function LegalSkillsRunPage() {
  const prefill = routePrefill()
  const [packs, setPacks] = useState<LegalSkillPack[]>([])
  const [skills, setSkills] = useState<LegalSkill[]>([])
  const [profile, setProfile] = useState<LegalSkillProfile | null>(null)
  const [packId, setPackId] = useState(prefill.packId)
  const [skillId, setSkillId] = useState(prefill.skillId)
  const [question, setQuestion] = useState('')
  const [documentText, setDocumentText] = useState('')
  const [sourceMode, setSourceMode] = useState('strict')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<LegalSkillRunResult | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([fetchLegalSkillPacks(controller.signal), fetchLegalSkillsProfile(controller.signal)])
      .then(([packsPayload, profilePayload]) => {
        setPacks(packsPayload.packs || [])
        setProfile(profilePayload.profile || null)
        if (!packsPayload.ok) setError(packsPayload.message || 'Legal Skills non disponibile per questo studio.')
        const firstPack = prefill.packId || packsPayload.packs?.[0]?.pack_id || ''
        if (firstPack) setPackId(firstPack)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!packId) {
      setSkills([])
      return
    }
    const controller = new AbortController()
    fetchLegalSkills(packId, controller.signal).then((payload) => {
      setSkills(payload.skills || [])
      const nextSkill = prefill.skillId || payload.skills?.[0]?.skill_id || ''
      if (!skillId && nextSkill) setSkillId(nextSkill)
    })
    return () => controller.abort()
  }, [packId])

  const selectedSkill = useMemo(() => skills.find((skill) => skill.skill_id === skillId) || null, [skills, skillId])

  const submit = async () => {
    if (!packId || !skillId) return
    setRunning(true)
    setError('')
    const payload = await runLegalSkill({
      pack_id: packId,
      skill_id: skillId,
      question,
      source_mode: sourceMode,
      context: { destination: 'studio' },
      documents: documentText.trim() ? [{ title: 'Materiale indicato dallo studio', text: documentText }] : [],
    })
    setRunning(false)
    if (!payload.ok || !payload.result) {
      setError(payload.message || 'Esecuzione non riuscita.')
      return
    }
    setResult(payload.result)
  }

  const approve = async () => {
    if (!result?.run_id) return
    const payload = await approveLegalSkillRun(result.run_id)
    if (payload.ok && payload.result) setResult(payload.result)
    else setError(payload.message || 'Approvazione non riuscita.')
  }

  if (loading) return <IusLoadingState title="Preparazione skill" message="Recupero catalogo e profilo." />

  return (
    <IusPageShell
      title="Esegui Legal Skill"
      description="Genera una bozza guidata con fonti, lacune e revisione obbligatoria."
      icon={PlayCircle}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills">Catalogo</a></Button>}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="grid gap-4">
          {profile?.status !== 'ready' ? (
            <EscalationBox message="Completa il profilo Legal Skills prima di chiedere un risultato sostanziale. Senza profilo il motore blocca la risposta." />
          ) : null}
          {error ? <IusErrorState title="Attenzione" message={error} /> : null}
          <Card>
            <CardHeader>
              <CardTitle>Richiesta</CardTitle>
              {selectedSkill ? <p className="text-sm text-muted-foreground">{selectedSkill.description}</p> : null}
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-3">
                <label className="grid gap-1 text-sm font-medium">
                  Pack
                  <select className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm" value={packId} onChange={(event) => { setPackId(event.target.value); setSkillId('') }}>
                    {packs.map((pack) => <option key={pack.pack_id} value={pack.pack_id}>{pack.name}</option>)}
                  </select>
                </label>
                <label className="grid gap-1 text-sm font-medium">
                  Skill
                  <select className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm" value={skillId} onChange={(event) => setSkillId(event.target.value)}>
                    {skills.map((skill) => <option key={skill.skill_id} value={skill.skill_id}>{skill.name}</option>)}
                  </select>
                </label>
                <label className="grid gap-1 text-sm font-medium">
                  Fonti
                  <select className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm" value={sourceMode} onChange={(event) => setSourceMode(event.target.value)}>
                    <option value="strict">Rigorose</option>
                    <option value="balanced">Bilanciate</option>
                    <option value="broad">Bozza ampia</option>
                  </select>
                </label>
              </div>
              <label className="grid gap-1 text-sm font-medium">
                Obiettivo
                <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Indica cosa deve controllare la skill." />
              </label>
              <label className="grid gap-1 text-sm font-medium">
                Documenti o note da analizzare
                <Textarea className="min-h-40" value={documentText} onChange={(event) => setDocumentText(event.target.value)} placeholder="Incolla solo materiale reale dello studio o lascia vuoto per ottenere un blocco prudenziale." />
              </label>
              <div className="flex justify-end">
                <Button type="button" onClick={submit} disabled={running || !packId || !skillId}>
                  <PlayCircle aria-hidden="true" />
                  {running ? 'Esecuzione...' : 'Esegui skill'}
                </Button>
              </div>
            </CardContent>
          </Card>
          {result ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  Risultato <SkillRunStatusBadge status={result.status} />
                  <Badge variant="outline">Confidenza {result.confidence}</Badge>
                  <Badge variant="outline">{result.source_mode === 'strict' ? 'Fonti rigorose' : 'Fonti bilanciate'}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <ReviewerNoteBox note={result.reviewer_note} />
                <p className="text-sm leading-6">{result.answer}</p>
                <SkillFindingTable findings={result.findings || []} />
                <CitationList citations={result.citations || []} />
                <div className="flex flex-wrap justify-end gap-2">
                  {can('legal_skills.approva') ? (
                    <Button type="button" variant="outline" onClick={approve} disabled={!result.needs_review}>
                      <CheckCircle2 aria-hidden="true" />
                      {result.needs_review ? 'Approva risultato' : 'Gia approvato'}
                    </Button>
                  ) : null}
                  <Button asChild type="button" variant="outline"><a href={`/legal-skills/runs/${result.run_id}`}>Apri revisione</a></Button>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </section>
        <aside className="grid content-start gap-3">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden="true" /> Presidi</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm text-muted-foreground">
              <p>La risposta resta bozza fino ad approvazione.</p>
              <p>Le esportazioni sono bloccate quando le fonti non bastano.</p>
            </CardContent>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileSearch aria-hidden="true" /> Contesto richiesto</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {selectedSkill?.required_context?.length ? selectedSkill.required_context.join(', ') : 'Materiale reale dello studio.'}
            </CardContent>
          </Card>
        </aside>
      </div>
    </IusPageShell>
  )
}
