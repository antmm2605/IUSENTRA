import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, BookMarked, CheckCircle2, Circle, Clock, Library, Route, Scale } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { fetchPathway, fetchPathways, setPathwayStepState } from '../api'
import { FascicoloPicker, fascicoloDaUrl, type FascicoloSelezionato } from '../components/FascicoloPicker'
import { can } from '../permissions'
import type { Pathway, PathwayStep } from '../types'

export function PromptPathwaysPage() {
  const [percorsi, setPercorsi] = useState<Pathway[]>([])
  const [selezionato, setSelezionato] = useState<Pathway | null>(null)
  const [fascicolo, setFascicolo] = useState<FascicoloSelezionato | null>(fascicoloDaUrl)
  const [loading, setLoading] = useState(true)
  const [aggiornando, setAggiornando] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchPathways(controller.signal)
      .then((payload) => {
        if (!payload.ok) {
          setError(payload.message || 'Percorsi guidati non disponibili per questo studio.')
          return
        }
        setPercorsi(payload.percorsi || [])
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const apriPercorso = useCallback(
    (percorsoId: string) => {
      fetchPathway(percorsoId, fascicolo?.id).then((payload) => {
        if (payload.ok && payload.percorso) setSelezionato(payload.percorso)
        else if (payload.code === 'fascicolo_not_found') {
          setFascicolo(null)
          setError('Fascicolo indicato non trovato: il percorso resta senza avanzamento.')
        }
      })
    },
    [fascicolo],
  )

  useEffect(() => {
    if (selezionato) apriPercorso(selezionato.percorso_id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fascicolo?.id])

  const segnaPasso = useCallback(
    (passo: PathwayStep, completato: boolean) => {
      if (!selezionato || !fascicolo) return
      setAggiornando(passo.passo_id)
      setPathwayStepState(selezionato.percorso_id, passo.passo_id, { fascicolo: fascicolo.id, completato })
        .then((payload) => {
          if (payload.ok && payload.percorso) setSelezionato(payload.percorso)
        })
        .finally(() => setAggiornando(''))
    },
    [selezionato, fascicolo],
  )

  const passi = useMemo(() => selezionato?.passi || [], [selezionato])
  const completati = useMemo(() => passi.filter((passo) => passo.completato).length, [passi])
  const puoTracciare = can('legal_skills.esegui')

  if (loading) return <IusLoadingState title="Caricamento percorsi" message="Recupero i percorsi guidati per procedimento." />
  if (error && !percorsi.length) return <IusErrorState title="Percorsi non attivi" message={error} />

  return (
    <IusPageShell
      title="Percorsi guidati — LegalSkills Italia"
      description="Sequenze operative per procedimento: ogni passo richiama il prompt giusto, con termini e riferimenti normativi da verificare."
      icon={Route}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills/prompt"><Library aria-hidden="true" /> Libreria Prompt</a></Button>}
    >
      <div className="grid gap-4">
        <Card size="sm">
          <CardContent className="pt-4">
            <FascicoloPicker
              fascicolo={fascicolo}
              onSelect={setFascicolo}
              onClear={() => setFascicolo(null)}
              etichettaVuota="collega un fascicolo per tracciare l'avanzamento e precompilare i prompt."
            />
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
          <section className="grid content-start gap-2" aria-label="Percorsi disponibili">
            {percorsi.map((percorso) => (
              <Card
                key={percorso.percorso_id}
                size="sm"
                className={percorso.percorso_id === selezionato?.percorso_id ? 'border-primary' : undefined}
              >
                <CardContent className="grid gap-2 pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{percorso.nome}</span>
                    <Badge variant="secondary">{percorso.numero_passi} passi</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{percorso.descrizione}</p>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    {percorso.riferimenti.slice(0, 2).map((riferimento) => (
                      <span key={riferimento}>{riferimento}</span>
                    ))}
                  </div>
                  <div>
                    <Button size="sm" variant="outline" onClick={() => apriPercorso(percorso.percorso_id)}>
                      Apri percorso <ArrowRight aria-hidden="true" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </section>

          <aside className="grid content-start gap-3">
            {selezionato ? (
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Scale aria-hidden="true" /> {selezionato.nome}</CardTitle>
                  <p className="text-sm text-muted-foreground">{selezionato.descrizione}</p>
                  {fascicolo ? (
                    <p className="text-sm text-muted-foreground">
                      Avanzamento: {completati}/{passi.length} passi completati per {fascicolo.etichetta || `fascicolo ${fascicolo.id}`}.
                    </p>
                  ) : null}
                </CardHeader>
                <CardContent className="grid gap-3">
                  {passi.map((passo, indice) => {
                    const prossimo = Boolean(fascicolo) && selezionato.prossimo_passo === passo.passo_id
                    return (
                      <div key={passo.passo_id} className={`grid gap-2 rounded-md border p-3 ${prossimo ? 'border-primary' : ''}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          {passo.completato ? (
                            <CheckCircle2 aria-hidden="true" className="size-4 text-primary" />
                          ) : (
                            <Circle aria-hidden="true" className="size-4 text-muted-foreground" />
                          )}
                          <span className="font-medium">{indice + 1}. {passo.nome}</span>
                          {prossimo ? <Badge>Prossimo passo</Badge> : null}
                          {passo.prompt_forma ? <Badge variant="outline">{passo.prompt_forma}</Badge> : null}
                        </div>
                        <p className="text-sm text-muted-foreground">{passo.descrizione}</p>
                        {passo.termini.length ? (
                          <ul className="grid gap-1 text-sm">
                            {passo.termini.map((termine) => (
                              <li key={termine} className="flex items-start gap-1">
                                <Clock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                                <span>{termine}</span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          {passo.riferimenti.map((riferimento) => (
                            <span key={riferimento}>{riferimento}</span>
                          ))}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button asChild size="sm" variant="outline">
                            <a href={`/legal-skills/prompt?prompt=${encodeURIComponent(passo.prompt_ref)}${fascicolo ? `&fascicolo=${encodeURIComponent(fascicolo.id)}` : ''}`}>
                              <BookMarked aria-hidden="true" /> Apri prompt
                            </a>
                          </Button>
                          {fascicolo && puoTracciare ? (
                            <Button
                              size="sm"
                              variant={passo.completato ? 'ghost' : 'default'}
                              disabled={aggiornando === passo.passo_id}
                              onClick={() => segnaPasso(passo, !passo.completato)}
                            >
                              {passo.completato ? 'Riapri passo' : 'Segna completato'}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </CardContent>
              </Card>
            ) : (
              <IusEmptyState
                title="Seleziona un percorso"
                message="Apri un percorso per vedere i passi, i termini da presidiare e i prompt collegati. Con un fascicolo collegato puoi tracciare l'avanzamento."
                icon={Route}
              />
            )}
          </aside>
        </div>
      </div>
    </IusPageShell>
  )
}
