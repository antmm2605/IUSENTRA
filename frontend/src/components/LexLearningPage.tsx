import { useBusyActivity } from '../ui/useBusyActivity'
import { useEffect, useState } from 'react'
import {
  BookOpenText,
  BrainCircuit,
  CalendarClock,
  ClipboardCheck,
  ExternalLink,
  Landmark,
  RefreshCcw,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { apiJson } from '../lib/apiClient'
import './LexLearningPage.css'

type LexLearningProposta = {
  titolo: string
  tipo: string
  descrizione: string
  modulo: string
  confidenza: number
  revisione_umana: boolean
  creato_il: string
}

type LexLearningLettura = {
  titolo: string
  url: string
  stato: string
  area: string
  fonte: string
  caratteri: number
  citazioni: number
  letto_il: string
}

type LexLearningJob = {
  job_id: string
  abilitato: boolean
  stato: string
  pianificazione: string
  console: string
  console_visibile?: boolean
  ultimo_giro?: { data?: string; esito?: string; riuscito?: boolean; messaggio?: string }
}

type LexLearningPayload = {
  ok: boolean
  memoria_presente: boolean
  directory: string
  conteggi: Record<string, number>
  proposte: LexLearningProposta[]
  letture: LexLearningLettura[]
  job_notturno: LexLearningJob
}

const emptyPayload: LexLearningPayload = {
  ok: false,
  memoria_presente: false,
  directory: '',
  conteggi: {},
  proposte: [],
  letture: [],
  job_notturno: { job_id: '', abilitato: false, stato: '', pianificazione: '', console: '/admin/pianificazioni' },
}

const STAT_LABELS: Array<[string, string]> = [
  ['citations', 'Citazioni di norme'],
  ['legal_terms', 'Termini giuridici'],
  ['source_readings', 'Letture di fonti'],
  ['improvement_proposals', 'Proposte in revisione'],
  ['research_questions', 'Domande di ricerca'],
  ['trust_assessments', 'Fonti valutate'],
]

function tipoProposta(tipo: string): string {
  // Il server manda già il tipo in italiano; le sigle interne non si mostrano mai.
  return /^[a-z_]+$/.test(tipo) || !tipo ? 'Proposta' : tipo
}

function statoLettura(stato: string): { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' } {
  if (stato === 'ok') return { label: 'Letta', tone: 'success' }
  if (stato === 'robots_blocked') return { label: 'Il sito non consente la lettura automatica', tone: 'warning' }
  if (stato === 'empty_text') return { label: 'Testo vuoto', tone: 'warning' }
  if (stato === 'too_large') return { label: 'Documento troppo grande', tone: 'warning' }
  if (!stato) return { label: 'Stato non indicato', tone: 'neutral' }
  return { label: 'Lettura non riuscita', tone: 'danger' }
}

function dataItaliana(value: string): string {
  if (!value) return 'n.d.'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(parsed)
}

/** Stato del job senza ripetere il badge «Attivo/In pausa» (verifica visiva LEX-19). */
function statoJobLeggibile(stato: string | undefined, pianificazione: string | undefined): string {
  const testo = (stato || '').trim()
  const ridondante = /^(attivo|in pausa|disattivo)$/i.test(testo)
  if (pianificazione) return ridondante || !testo ? `Pianificata ${pianificazione}` : `${testo} — ${pianificazione}`
  return testo || 'Stato non disponibile.'
}

export function LexLearningPage() {
  const [data, setData] = useState<LexLearningPayload>(emptyPayload)
  const [loading, setLoading] = useState(true)
  useBusyActivity(loading, 'Caricamento dell’apprendimento locale…')

  const load = async () => {
    setLoading(true)
    const payload = await apiJson<LexLearningPayload>('/api/v1/ui/lex-learning', emptyPayload)
    setData({ ...emptyPayload, ...payload })
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  const job = data.job_notturno
  return (
    <main className="lex-learning-page">
      <header className="lex-learning-page__header">
        <div>
          <h1><BrainCircuit size={22} aria-hidden /> Cosa sta imparando Lex</h1>
          <p>
            Ogni notte Lex legge solo le fonti ufficiali ammesse, conserva ciò che ha letto in una memoria
            consultabile e propone miglioramenti che entrano in uso solo dopo la tua approvazione.
          </p>
        </div>
        <button
          type="button"
          className="iu-button iu-button--secondary lex-learning-page__refresh"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCcw size={16} aria-hidden /> Aggiorna
        </button>
      </header>

      <Panel
        title="Lettura notturna pianificata"
        subtitle="Ogni notte Lex legge le Gazzette Ufficiali nuove e le fonti che gli mancano"
        icon={<CalendarClock size={18} aria-hidden />}
        action={
          job.console_visibile ? (
            <Button variant="ghost" href={job.console || '/admin/pianificazioni'} title="Apri la console Pianificazioni della piattaforma">
              Console Pianificazioni <ExternalLink size={14} aria-hidden />
            </Button>
          ) : undefined
        }
      >
        <div className="lex-learning-page__job">
          <Badge tone={job.abilitato ? 'success' : 'neutral'}>{job.abilitato ? 'Attivo' : 'In pausa'}</Badge>
          <span className="lex-learning-page__job-note">
            {loading ? 'Caricamento…' : statoJobLeggibile(job.stato, job.pianificazione)}
          </span>
        </div>
        {job.ultimo_giro?.data ? (
          <p className="lex-learning-page__job-note">
            Ultimo giro: {dataItaliana(job.ultimo_giro.data)} · {job.ultimo_giro.esito || 'esito non indicato'}
            {job.ultimo_giro.messaggio ? ` · ${job.ultimo_giro.messaggio.replace(/^Sequenza notturna, fase \d+: /, '')}` : ''}
          </p>
        ) : null}
      </Panel>

      <Panel title="Memoria di apprendimento" subtitle={data.memoria_presente ? 'Ciò che Lex ha letto, conservato nell’archivio dello studio e consultabile in sola lettura.' : 'La memoria si riempie con la lettura notturna.'} icon={<Landmark size={18} aria-hidden />}>
        {data.memoria_presente ? (
          <div className="lex-learning-page__stats">
            {STAT_LABELS.map(([key, label]) => (
              <div className="lex-learning-page__stat" key={key}>
                <strong>{data.conteggi[key] ?? 0}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="lex-learning-page__empty">
            {loading
              ? 'Caricamento…'
              : 'La memoria è ancora vuota: si riempie notte dopo notte con le letture, le citazioni e le proposte di Lex.'}
          </p>
        )}
      </Panel>

      <Panel
        title="Proposte di miglioramento"
        subtitle="Nascono da ciò che Lex ha letto: nessuna entra in uso senza la tua approvazione"
        icon={<ClipboardCheck size={18} aria-hidden />}
        count={data.proposte.length}
      >
        {data.proposte.length ? (
          <ul className="lex-learning-page__list">
            {data.proposte.map((proposta, index) => (
              <li key={`${proposta.titolo}-${index}`}>
                <div className="lex-learning-page__list-head">
                  <Badge tone="info">{tipoProposta(proposta.tipo)}</Badge>
                  <strong>{proposta.titolo || 'Proposta senza titolo'}</strong>
                  <Badge tone="warning">Da approvare</Badge>
                </div>
                <p>{proposta.descrizione}</p>
                <small>
                  Attendibilità {Math.round(proposta.confidenza * 100)}% · {dataItaliana(proposta.creato_il)}
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="lex-learning-page__empty">{loading ? 'Caricamento…' : 'Nessuna proposta in coda di revisione.'}</p>
        )}
      </Panel>

      <Panel
        title="Ultime letture di fonti ufficiali"
        subtitle="Solo fonti ufficiali; Lex rispetta le regole di accesso di ogni sito"
        icon={<BookOpenText size={18} aria-hidden />}
        count={data.letture.length}
      >
        {data.letture.length ? (
          <ul className="lex-learning-page__list">
            {data.letture.map((lettura, index) => {
              const stato = statoLettura(lettura.stato)
              return (
                <li key={`${lettura.url}-${index}`}>
                  <div className="lex-learning-page__list-head">
                    <Badge tone={stato.tone}>{stato.label}</Badge>
                    <strong>{lettura.titolo || 'Fonte'}</strong>
                    {lettura.area ? <Badge tone="neutral">{lettura.area}</Badge> : null}
                  </div>
                  <small>
                    {lettura.citazioni} citazioni · {lettura.caratteri.toLocaleString('it-IT')} caratteri · {dataItaliana(lettura.letto_il)}
                    {lettura.fonte ? ` · ${lettura.fonte}` : ''}
                  </small>
                  {lettura.url ? (
                    <a href={lettura.url} target="_blank" rel="noreferrer noopener" className="lex-learning-page__link">
                      Apri la fonte ufficiale <ExternalLink size={12} aria-hidden />
                    </a>
                  ) : null}
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="lex-learning-page__empty">{loading ? 'Caricamento…' : 'Nessuna lettura registrata nella memoria durevole.'}</p>
        )}
      </Panel>
    </main>
  )
}
