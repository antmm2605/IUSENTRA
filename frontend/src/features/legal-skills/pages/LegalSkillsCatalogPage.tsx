import { useEffect, useMemo, useState } from 'react'
import { BookOpenCheck, FileSearch, PlayCircle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { fetchLegalSkillPacks, fetchLegalSkillsProfile, fetchScheduledLegalSkillAgents } from '../api'
import type { LegalSkillPack, LegalSkillProfile, ScheduledLegalSkillAgent } from '../types'
import { EscalationBox } from '../components/EscalationBox'

export function LegalSkillsCatalogPage() {
  const [packs, setPacks] = useState<LegalSkillPack[]>([])
  const [profile, setProfile] = useState<LegalSkillProfile | null>(null)
  const [agents, setAgents] = useState<ScheduledLegalSkillAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    Promise.all([
      fetchLegalSkillPacks(controller.signal),
      fetchLegalSkillsProfile(controller.signal),
      fetchScheduledLegalSkillAgents(controller.signal),
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
      actions={<Button asChild><a href="/legal-skills/profile"><ShieldCheck aria-hidden="true" /> Profilo</a></Button>}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {packs.map((pack) => (
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
              </CardContent>
              <CardFooter className="justify-between">
                <Button asChild size="sm" variant="outline"><a href={`/legal-skills/packs/${pack.pack_id}/skills`}>Apri pack</a></Button>
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
