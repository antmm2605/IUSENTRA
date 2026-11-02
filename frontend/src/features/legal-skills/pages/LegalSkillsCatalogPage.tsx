import { useEffect, useMemo, useState } from 'react'
import { BookOpenCheck, FileSearch, Library, PlayCircle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { isFeatureFlagEnabledSync } from '@/lib/featureFlags'
import { fetchLegalSkillPacks, fetchLegalSkills, fetchLegalSkillsProfile, fetchScheduledLegalSkillAgents } from '../api'
import type { LegalSkill, LegalSkillPack, LegalSkillProfile, ScheduledLegalSkillAgent } from '../types'
import { EscalationBox } from '../components/EscalationBox'

/** «/legal-skills/packs/<id>/skills»: il pack scelto con le sue skill (verifica visiva LEX-24). */
function packDallUrl(): string {
  if (typeof window === 'undefined') return ''
  const match = /^\/legal-skills\/packs\/([^/]+)\/skills\/?$/.exec(window.location.pathname)
  return match ? decodeURIComponent(match[1]) : ''
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
        if (!packsPayload.ok) setError(packsPayload.message || 'Legal Skills non disponibile per questo studio.')
        setPacks(packsPayload.packs || [])
        setProfile(profilePayload.profile || null)
        setAgents(agentsPayload.agents || [])
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const enabledAgents = useMemo(() => agents.filter((agent) => agent.enabled), [agents])

  if (loading) return <IusLoadingState title="Caricamento Legal Skills" message="Recupero pack e profilo dello studio." />
  if (error && !packs.length) return <IusErrorState title="Legal Skills non attivo" message={error} />

  return (
    <IusPageShell
      title="Legal Skills"
      description="Pack operativi Lex per revisioni guidate, fonti e risultati da approvare."
      icon={BookOpenCheck}
      area="lex"
      actions={
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><a href="/legal-skills/prompt"><Library aria-hidden="true" /> Libreria Prompt</a></Button>
          <Button asChild><a href="/legal-skills/profile"><ShieldCheck aria-hidden="true" /> Profilo</a></Button>
        </div>
      }
    >
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
                  <Badge variant="outline">{pack.jurisdiction}</Badge>
                  <Badge variant="secondary">{pack.source_mode === 'strict' ? 'Fonti rigorose' : 'Fonti bilanciate'}</Badge>
                </div>
                <p className="text-muted-foreground">{pack.skills_count || pack.skills?.length || 0} skill disponibili.</p>
                {packScelto === pack.pack_id ? (
                  skillPack === null ? <p className="text-muted-foreground">Caricamento delle skill del pack…</p>
                    : skillPack.length ? <ul className="grid gap-2">{skillPack.map((skill) => <li key={skill.skill_id}><strong>{skill.name}</strong><br /><span className="text-muted-foreground">{skill.description}</span></li>)}</ul>
                      : <p className="text-muted-foreground">Nessuna skill consultabile in questo pack.</p>
                ) : null}
              </CardContent>
              <CardFooter className="justify-between">
                {packScelto === pack.pack_id
                  ? <Button asChild size="sm" variant="outline"><a href="/legal-skills">Tutti i pack</a></Button>
                  : <Button asChild size="sm" variant="outline"><a href={`/legal-skills/packs/${pack.pack_id}/skills`}>Apri pack</a></Button>}
                <Button asChild size="sm"><a href={`/legal-skills/run?pack=${pack.pack_id}`}><PlayCircle aria-hidden="true" /> Esegui</a></Button>
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
            <EscalationBox message="Completa il profilo prima di generare output sostanziali. Il motore blocca risultati privi di contesto studio." />
          )}
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><FileSearch aria-hidden="true" /> Presidi attivi</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {enabledAgents.length ? `${enabledAgents.length} agente schedulato attivo.` : 'Nessun agente schedulato attivo.'}
            </CardContent>
          </Card>
        </aside>
      </div>
      {!packs.length ? (
        <IusEmptyState title="Nessun pack disponibile" message="Attiva Legal Skills dalle impostazioni prima di usare il catalogo." icon={BookOpenCheck} />
      ) : null}
    </IusPageShell>
  )
}
