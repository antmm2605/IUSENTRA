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
  ['citations', 'Citazioni normalizzate'],
  ['legal_terms', 'Termini giuridici'],
  ['source_readings', 'Letture di fonti'],
  ['improvement_proposals', 'Proposte in revisione'],
  ['research_questions', 'Domande di ricerca'],
  ['trust_assessments', 'Valutazioni di fiducia'],
]

function tipoProposta(tipo: string): string {
  if (tipo === 'ontologia') return 'Ontologia'
  if (tipo === 'connettore_dedicato') return 'Connettore dedicato'
  if (tipo === 'estrattore_citazioni') return 'Estrattore citazioni'
  return tipo || 'Proposta'
}

function statoLettura(stato: string): { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' } {
  if (stato === 'ok') return { label: 'Letta', tone: 'success' }
  if (stato === 'robots_blocked') return { label: 'Robots (fail-closed)', tone: 'warning' }
  if (stato === 'empty_text') return { label: 'Testo vuoto', tone: 'warning' }
  if (stato === 'too_large') return { label: 'Oltre soglia byte', tone: 'warning' }
  if (!stato) return { label: 'n.d.', tone: 'neutral' }
  return { label: stato, tone: 'danger' }
}

function dataItaliana(value: string): string {
  if (!value) return 'n.d.'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(parsed)
}

export function LexLearningPage() {
  const [data, setData] = useState<LexLearningPayload>(emptyPayload)
  const [loading, setLoading] = useState(true)

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
    <div className="lex-learning-page">
      <header className="lex-learning-page__header">
        <div>
          <h1><BrainCircuit size={22} aria-hidden /> Apprendimento Lex</h1>
          <p>
            Ciclo di apprendimento autonomo governato: Lex legge SOLO fonti ufficiali ammesse dalla policy,
            costruisce memoria ispezionabile e propone miglioramenti che restano sempre in revisione umana.
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
        title="Job notturno delegato"
        subtitle="Apprendimento autonomo Lex (web) — attivazione solo dalla console Pianificazioni"
        icon={<CalendarClock size={18} aria-hidden />}
        action={
          <Button variant="ghost" href={job.console || '/admin/pianificazioni'} title="Apri la console Pianificazioni">
            Console Pianificazioni <ExternalLink size={14} aria-hidden />
          </Button>
        }
      >
        <div className="lex-learning-page__job">
          <Badge tone={job.abilitato ? 'success' : 'neutral'}>{job.abilitato ? 'Attivo' : 'In pausa'}</Badge>
          <span className="lex-learning-page__job-note">
            {loading ? 'Caricamento…' : job.stato || 'Stato non disponibile.'}
            {job.pianificazione ? ` — ${job.pianificazione}` : ''}
          </span>
        </div>
      </Panel>

      <Panel title="Memoria di apprendimento" subtitle={data.memoria_presente ? data.directory : 'La memoria durevole si popola con il job notturno o con i cicli governati.'} icon={<Landmark size={18} aria-hidden />}>
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
              : 'Nessuna memoria durevole ancora presente su questo server: attiva il job notturno dalla console Pianificazioni per iniziare ad accumulare letture, citazioni e proposte notte dopo notte.'}
          </p>
        )}
      </Panel>

      <Panel
        title="Proposte di miglioramento"
        subtitle="Generate dal ciclo con evidenze: nessuna viene mai applicata in automatico"
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
                  <Badge tone="warning">Revisione umana</Badge>
                </div>
                <p>{proposta.descrizione}</p>
                <small>
                  Modulo: {proposta.modulo || 'n.d.'} · Confidenza {Math.round(proposta.confidenza * 100)}% · {dataItaliana(proposta.creato_il)}
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
        subtitle="Robots.txt e rate-limit sempre rispettati; fonti fuori policy respinte"
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
                      {lettura.url}
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
    </div>
  )
}
