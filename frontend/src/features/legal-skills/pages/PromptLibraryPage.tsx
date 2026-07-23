import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookMarked, ClipboardCopy, FolderOpen, Library, PlayCircle, Scale, Search, Star, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IusEmptyState, IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { getFascicoliPage, type FascicoloRow } from '../../../fascicoliData'
import { fetchPromptLibraryAree, fetchPromptLibraryPrompt, runPromptLibraryPrompt, searchPromptLibrary } from '../api'
import { can } from '../permissions'
import type { PromptLibraryArea, PromptLibraryDetail, PromptLibraryEntry, PromptLibraryForma } from '../types'

const TUTTE = '__tutte__'
const RISULTATI_VISIBILI = 60

type FascicoloSelezionato = { id: string; etichetta: string }

function fascicoloIniziale(): FascicoloSelezionato | null {
  const id = new URLSearchParams(window.location.search).get('fascicolo')?.trim()
  return id ? { id, etichetta: '' } : null
}

export function PromptLibraryPage() {
  const [aree, setAree] = useState<PromptLibraryArea[]>([])
  const [areePreferite, setAreePreferite] = useState<string[]>([])
  const [forme, setForme] = useState<PromptLibraryForma[]>([])
  const [totalePrompt, setTotalePrompt] = useState(0)
  const [query, setQuery] = useState('')
  const [areaFiltro, setAreaFiltro] = useState(TUTTE)
  const [formaFiltro, setFormaFiltro] = useState(TUTTE)
  const [risultati, setRisultati] = useState<PromptLibraryEntry[]>([])
  const [totaleRisultati, setTotaleRisultati] = useState(0)
  const [dettaglio, setDettaglio] = useState<PromptLibraryDetail | null>(null)
  const [fascicolo, setFascicolo] = useState<FascicoloSelezionato | null>(fascicoloIniziale)
  const [ricercaFascicolo, setRicercaFascicolo] = useState('')
  const [opzioniFascicolo, setOpzioniFascicolo] = useState<FascicoloRow[]>([])
  const [copiato, setCopiato] = useState(false)
  const [eseguendo, setEseguendo] = useState(false)
  const [erroreEsecuzione, setErroreEsecuzione] = useState('')
  const [loading, setLoading] = useState(true)
  const [ricercaInCorso, setRicercaInCorso] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchPromptLibraryAree(controller.signal)
      .then((payload) => {
        if (!payload.ok) {
          setError(payload.message || 'Libreria prompt non disponibile per questo studio.')
          return
        }
        setAree(payload.aree || [])
        setAreePreferite(payload.aree_preferite || [])
        setForme(payload.forme || [])
        setTotalePrompt(payload.totale_prompt || 0)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setRicercaInCorso(true)
    const timer = window.setTimeout(() => {
      searchPromptLibrary(
        {
          q: query,
          area: areaFiltro === TUTTE ? '' : areaFiltro,
          forma: formaFiltro === TUTTE ? '' : formaFiltro,
        },
        controller.signal,
      )
        .then((payload) => {
          if (!payload.ok) return
          setRisultati(payload.prompts || [])
          setTotaleRisultati(payload.totale || 0)
        })
        .finally(() => setRicercaInCorso(false))
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, areaFiltro, formaFiltro])

  useEffect(() => {
    if (!ricercaFascicolo.trim()) {
      setOpzioniFascicolo([])
      return
    }
    const timer = window.setTimeout(() => {
      getFascicoliPage({ q: ricercaFascicolo.trim(), pageSize: 8 }).then((pagina) => {
        setOpzioniFascicolo(pagina.items || [])
      })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [ricercaFascicolo])

  const apriDettaglio = useCallback(
    (promptId: string) => {
      setCopiato(false)
      fetchPromptLibraryPrompt(promptId, fascicolo?.id).then((payload) => {
        if (payload.ok && payload.prompt) {
          setDettaglio(payload.prompt)
          const contesto = payload.prompt.contesto_fascicolo
          if (contesto && fascicolo && !fascicolo.etichetta) {
            setFascicolo({ id: fascicolo.id, etichetta: [contesto.numero, contesto.titolo].filter(Boolean).join(' — ') })
          }
        } else if (payload.code === 'fascicolo_not_found') {
          setFascicolo(null)
          setError('Fascicolo indicato non trovato: il prompt resta generico.')
        }
      })
    },
    [fascicolo],
  )

  useEffect(() => {
    if (dettaglio) apriDettaglio(dettaglio.prompt_id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fascicolo?.id])

  const selezionaFascicolo = useCallback((riga: FascicoloRow) => {
    setFascicolo({ id: riga.id, etichetta: [riga.ref || riga.internalRef, riga.title].filter(Boolean).join(' — ') })
    setRicercaFascicolo('')
    setOpzioniFascicolo([])
  }, [])

  const copiaTesto = useCallback(() => {
    if (!dettaglio?.testo) return
    navigator.clipboard?.writeText(dettaglio.testo).then(() => {
      setCopiato(true)
      window.setTimeout(() => setCopiato(false), 2500)
    })
  }, [dettaglio])

  const eseguiConLex = useCallback(() => {
    if (!dettaglio || eseguendo) return
    setEseguendo(true)
    setErroreEsecuzione('')
    runPromptLibraryPrompt({ prompt_id: dettaglio.prompt_id, fascicolo: fascicolo?.id })
      .then((payload) => {
        if (payload.ok && payload.result?.run_id) {
          window.location.assign(`/legal-skills/runs/${payload.result.run_id}`)
          return
        }
        if (payload.code === 'profile_incomplete') {
          setErroreEsecuzione('Completa prima il profilo studio Legal Skills: serve per generare bozze governate.')
        } else {
          setErroreEsecuzione(payload.message || 'Esecuzione non disponibile in questo momento.')
        }
        setEseguendo(false)
      })
      .catch(() => {
        setErroreEsecuzione('Esecuzione non disponibile in questo momento.')
        setEseguendo(false)
      })
  }, [dettaglio, eseguendo, fascicolo])

  const risultatiVisibili = useMemo(() => risultati.slice(0, RISULTATI_VISIBILI), [risultati])
  const areePreferiteDettaglio = useMemo(
    () => aree.filter((area) => area.preferita),
    [aree],
  )
  const contesto = dettaglio?.contesto_fascicolo

  if (loading) return <IusLoadingState title="Caricamento libreria prompt" message="Recupero aree e catalogo LegalSkills Italia." />
  if (error && !aree.length) return <IusErrorState title="Libreria prompt non attiva" message={error} />

  return (
    <IusPageShell
      title="Libreria Prompt — LegalSkills Italia"
      description={`${totalePrompt} prompt operativi in ${aree.length} aree del diritto, con riferimenti normativi e forme di lavoro della prassi forense.`}
      icon={Library}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills"><BookMarked aria-hidden="true" /> Catalogo skill</a></Button>}
    >
      <div className="grid gap-4">
        <Card size="sm">
          <CardContent className="grid gap-3 pt-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_14rem_14rem]">
              <div className="relative">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Cerca in tutta la libreria: istituto, norma, tag (es. licenziamento, art. 1454 c.c.)"
                  className="pl-9"
                  aria-label="Cerca prompt"
                />
              </div>
              <Select value={areaFiltro} onValueChange={setAreaFiltro}>
                <SelectTrigger aria-label="Filtra per area">
                  <SelectValue placeholder="Tutte le aree" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TUTTE}>Tutte le aree ({aree.length})</SelectItem>
                  {aree.map((area) => (
                    <SelectItem key={area.area_id} value={area.area_id}>
                      {area.preferita ? '★ ' : ''}{area.nome} ({area.numero_prompt})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={formaFiltro} onValueChange={setFormaFiltro}>
                <SelectTrigger aria-label="Filtra per forma">
                  <SelectValue placeholder="Tutte le forme" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TUTTE}>Tutte le forme</SelectItem>
                  {forme.map((forma) => (
                    <SelectItem key={forma.forma_id} value={forma.forma_id}>
                      {forma.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {areePreferiteDettaglio.length ? (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="flex items-center gap-1 text-muted-foreground"><Star aria-hidden="true" className="size-4" /> Aree del tuo studio:</span>
                {areePreferiteDettaglio.map((area) => (
                  <Button
                    key={area.area_id}
                    size="sm"
                    variant={areaFiltro === area.area_id ? 'default' : 'outline'}
                    onClick={() => setAreaFiltro(areaFiltro === area.area_id ? TUTTE : area.area_id)}
                  >
                    {area.nome}
                  </Button>
                ))}
              </div>
            ) : null}

            <div className="grid gap-2">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="flex items-center gap-1 text-muted-foreground"><FolderOpen aria-hidden="true" className="size-4" /> Precompila dal fascicolo:</span>
                {fascicolo ? (
                  <Badge variant="secondary" className="flex items-center gap-1">
                    {fascicolo.etichetta || `Fascicolo ${fascicolo.id}`}
                    <button type="button" aria-label="Rimuovi fascicolo" onClick={() => setFascicolo(null)}>
                      <X aria-hidden="true" className="size-3" />
                    </button>
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">nessun fascicolo collegato — i prompt restano generici.</span>
                )}
              </div>
              {!fascicolo ? (
                <div className="relative md:max-w-md">
                  <Input
                    value={ricercaFascicolo}
                    onChange={(event) => setRicercaFascicolo(event.target.value)}
                    placeholder="Cerca fascicolo per titolo, cliente o RG…"
                    aria-label="Cerca fascicolo da collegare"
                  />
                  {opzioniFascicolo.length ? (
                    <div className="mt-2 grid gap-1">
                      {opzioniFascicolo.map((riga) => (
                        <Button
                          key={riga.id}
                          size="sm"
                          variant="outline"
                          className="justify-start"
                          onClick={() => selezionaFascicolo(riga)}
                        >
                          {[riga.ref || riga.internalRef, riga.title, riga.client].filter(Boolean).join(' — ')}
                        </Button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <p className="text-sm text-muted-foreground" aria-live="polite">
          {ricercaInCorso
            ? 'Ricerca in corso…'
            : `${totaleRisultati} prompt trovati${totaleRisultati > RISULTATI_VISIBILI ? ` (mostrati i primi ${RISULTATI_VISIBILI}: restringi con filtri o ricerca)` : ''}.`}
        </p>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <section className="grid content-start gap-2" aria-label="Risultati ricerca prompt">
            {risultatiVisibili.map((entry) => (
              <Card key={entry.prompt_id} size="sm" className={entry.prompt_id === dettaglio?.prompt_id ? 'border-primary' : undefined}>
                <CardContent className="grid gap-2 pt-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{entry.titolo}</span>
                    <Badge variant="secondary">{entry.forma_label}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{entry.descrizione}</p>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge variant="outline">{entry.area_nome}</Badge>
                    {entry.riferimenti.slice(0, 2).map((riferimento) => (
                      <span key={riferimento} className="text-muted-foreground">{riferimento}</span>
                    ))}
                  </div>
                  <div>
                    <Button size="sm" variant="outline" onClick={() => apriDettaglio(entry.prompt_id)}>
                      Apri prompt
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
            {!risultatiVisibili.length && !ricercaInCorso ? (
              <IusEmptyState title="Nessun prompt trovato" message="Prova a modificare la ricerca o i filtri per area e forma." icon={Search} />
            ) : null}
          </section>

          <aside className="grid content-start gap-3">
            {dettaglio ? (
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2"><Scale aria-hidden="true" /> {dettaglio.titolo}</CardTitle>
                  <p className="text-sm text-muted-foreground">{dettaglio.forma_descrizione}</p>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">{dettaglio.area_nome}</Badge>
                    <Badge variant="secondary">{dettaglio.forma_label}</Badge>
                    {dettaglio.tags.map((tag) => (
                      <Badge key={tag} variant="outline">{tag}</Badge>
                    ))}
                  </div>
                  {contesto ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/40 p-2 text-sm">
                      <FolderOpen aria-hidden="true" className="size-4 text-muted-foreground" />
                      <span>
                        Precompilato dal fascicolo {[contesto.numero, contesto.titolo].filter(Boolean).join(' — ')}
                        {contesto.rg ? ` (${contesto.rg})` : ''}
                      </span>
                    </div>
                  ) : null}
                  <div className="grid gap-1 text-sm">
                    <span className="font-medium">Riferimenti normativi</span>
                    <ul className="list-inside list-disc text-muted-foreground">
                      {dettaglio.riferimenti.map((riferimento) => (
                        <li key={riferimento}>{riferimento}</li>
                      ))}
                    </ul>
                  </div>
                  <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                    {dettaglio.testo}
                  </pre>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" onClick={copiaTesto}>
                      <ClipboardCopy aria-hidden="true" /> {copiato ? 'Copiato negli appunti' : 'Copia prompt'}
                    </Button>
                    {can('legal_skills.esegui') ? (
                      <Button size="sm" variant="outline" onClick={eseguiConLex} disabled={eseguendo}>
                        <PlayCircle aria-hidden="true" /> {eseguendo ? 'Esecuzione in corso…' : 'Esegui con Lex'}
                      </Button>
                    ) : null}
                    <span className="text-xs text-muted-foreground">Bozza per revisione: l'output va sempre verificato dall'avvocato.</span>
                  </div>
                  {erroreEsecuzione ? (
                    <p className="text-sm text-destructive" role="alert">
                      {erroreEsecuzione}{' '}
                      {erroreEsecuzione.startsWith('Completa') ? (
                        <a className="underline" href="/legal-skills/profile/cold-start">Configura il profilo</a>
                      ) : null}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ) : (
              <IusEmptyState
                title="Seleziona un prompt"
                message="Apri un prompt dai risultati per leggere il testo completo, i riferimenti normativi e copiarlo negli appunti. Collega un fascicolo per averlo già precompilato con i dati reali."
                icon={Library}
              />
            )}
          </aside>
        </div>
      </div>
    </IusPageShell>
  )
}
