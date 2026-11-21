import { useEffect, useMemo, useState } from 'react'
import { BookOpenCheck, FileSearch, Library, PlayCircle, Route, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { isFeatureFlagEnabledSync } from '@/lib/featureFlags'
import { fetchLegalSkillPacks, fetchLegalSkills, fetchLegalSkillsProfile, fetchScheduledLegalSkillAgents } from '../api'
import type { LegalSkill, LegalSkillPack, LegalSkillProfile, ScheduledLegalSkillAgent } from '../types'
import { EscalationBox } from '../components/EscalationBox'
import { PercorsiGuidati } from '../components/PercorsiGuidati'

/** «/legal-skills/packs/<id>/skills»: l'area di revisione scelta con le sue revisioni (verifica visiva LEX-24). */
function packDallUrl(): string {
  if (typeof window === 'undefined') return ''
  const match = /^\/legal-skills\/packs\/([^/]+)\/skills\/?$/.exec(window.location.pathname)
  return match ? decodeURIComponent(match[1]) : ''
}

/** «1 revisione disponibile», «3 revisioni disponibili»: niente parole tecniche a video. */
export function revisioniDisponibili(numero: number): string {
  if (numero === 1) return '1 revisione disponibile.'
  return `${numero} revisioni disponibili.`
}

export function LegalSkillsCatalogPage() {
  const packScelto = useMemo(packDallUrl, [])
  const [skillPack, setSkillPack] = useState<LegalSkill[] | null>(null)
  const [packs, setPacks] = useState<LegalSkillPack[]>([])
  const [profile, setProfile] = useState<LegalSkillProfile | null>(null)
  const [agents, setAgents] = useState<ScheduledLegalSkillAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!packScelto) return
    const controller = new AbortController()
    fetchLegalSkills(packScelto, controller.signal)
      .then((payload) => setSkillPack(payload.ok ? payload.skills || [] : []))
      .catch(() => setSkillPack([]))
    return () => controller.abort()
  }, [packScelto])

  useEffect(() => {
    const controller = new AbortController()
    const scheduledAgentsEnabled = isFeatureFlagEnabledSync('lex.legalSkills.scheduledAgents')
    setLoading(true)
    Promise.all([
      fetchLegalSkillPacks(controller.signal),
      fetchLegalSkillsProfile(controller.signal),
      scheduledAgentsEnabled
        ? fetchScheduledLegalSkillAgents(controller.signal)
        : Promise.resolve({ ok: true, agents: [] }),
    ])
      .then(([packsPayload, profilePayload, agentsPayload]) => {
        if (!packsPayload.ok) setError(packsPayload.message || 'Le revisioni guidate non sono disponibili per questo studio.')
        setPacks(packsPayload.packs || [])
        setProfile(profilePayload.profile || null)
        setAgents(agentsPayload.agents || [])
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const enabledAgents = useMemo(() => agents.filter((agent) => agent.enabled), [agents])

  if (loading) return <IusLoadingState title="Caricamento delle procedure guidate" message="Recupero le procedure e il profilo dello studio." />

  return (
    <IusPageShell
      title="Procedure guidate"
      description="Le procedure passo per passo dei procedimenti più frequenti, con termini e norme vigenti, e le revisioni guidate che Lex prepara per la tua approvazione."
      icon={BookOpenCheck}
      area="lex"
      actions={
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><a href="/legal-skills/prompt"><Library aria-hidden="true" /> Richieste pronte per Lex</a></Button>
          <Button asChild><a href="/legal-skills/profile"><ShieldCheck aria-hidden="true" /> Profilo dello studio</a></Button>
        </div>
      }
    >
      {!packScelto ? (
        <section className="grid gap-3" aria-labelledby="procedure-per-procedimento">
          <h2 id="procedure-per-procedimento" className="flex items-center gap-2 text-lg font-semibold"><Route aria-hidden="true" /> Procedure per procedimento</h2>
          <PercorsiGuidati />
        </section>
      ) : null}
      <h2 id="revisioni-guidate" className="mt-6 flex items-center gap-2 text-lg font-semibold"><BookOpenCheck aria-hidden="true" /> Revisioni guidate con Lex</h2>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {packs.filter((pack) => !packScelto || pack.pack_id === packScelto).map((pack) => (
            <Card key={pack.pack_id} size="sm">
              <CardHeader>
                <CardTitle>{pack.name}</CardTitle>
                <p className="text-sm text-muted-foreground">{pack.description}</p>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{pack.jurisdiction === 'IT' ? 'Diritto italiano' : pack.jurisdiction}</Badge>
                  <Badge variant="secondary">{pack.source_mode === 'strict' ? 'Fonti rigorose' : 'Fonti bilanciate'}</Badge>
                </div>
                <p className="text-muted-foreground">{revisioniDisponibili(pack.skills_count || pack.skills?.length || 0)}</p>
                {packScelto === pack.pack_id ? (
                  skillPack === null ? <p className="text-muted-foreground">Caricamento delle revisioni…</p>
                    : skillPack.length ? <ul className="grid gap-2">{skillPack.map((skill) => <li key={skill.skill_id}><strong>{skill.name}</strong><br /><span className="text-muted-foreground">{skill.description}</span></li>)}</ul>
                      : <p className="text-muted-foreground">Nessuna revisione consultabile in quest'area.</p>
                ) : null}
              </CardContent>
              <CardFooter className="justify-between">
                {packScelto === pack.pack_id
                  ? <Button asChild size="sm" variant="outline"><a href="/legal-skills">Tutte le aree</a></Button>
                  : <Button asChild size="sm" variant="outline"><a href={`/legal-skills/packs/${pack.pack_id}/skills`}>Vedi le revisioni</a></Button>}
                <Button asChild size="sm"><a href={`/legal-skills/run?pack=${pack.pack_id}`}><PlayCircle aria-hidden="true" /> Avvia una revisione</a></Button>
              </CardFooter>
            </Card>
          ))}
        </section>
        <aside className="grid content-start gap-3">
          {profile?.status === 'ready' ? (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden="true" /> Profilo pronto</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm text-muted-foreground">
                <p>{profile.firm_name || 'Studio configurato'}</p>
                <p>{profile.practice_areas.join(', ')}</p>
              </CardContent>
            </Card>
          ) : (
            <EscalationBox message="Completa il profilo dello studio prima di avviare una revisione: senza il contesto dello studio Lex non prepara risultati." />
          )}
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileSearch aria-hidden="true" /> Revisioni programmate</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {enabledAgents.length === 1 ? '1 revisione programmata attiva.' : enabledAgents.length ? `${enabledAgents.length} revisioni programmate attive.` : 'Nessuna revisione programmata attiva.'}
            </CardContent>
          </Card>
        </aside>
      </div>
      {!packs.length ? (
        <IusEmptyState title="Nessuna revisione guidata disponibile" message={error || 'Le revisioni guidate non sono attive per questo studio: le procedure qui sopra restano consultabili.'} icon={BookOpenCheck} />
      ) : null}
    </IusPageShell>
  )
}
