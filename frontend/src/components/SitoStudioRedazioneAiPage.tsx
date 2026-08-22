import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'
import { Bot, FilePenLine, Globe2, ImagePlus, Newspaper, RefreshCw, Send, ShieldCheck, Sparkles } from 'lucide-react'
import {
  emptyAiForm,
  emptySitoStudioAiData,
  getSitoStudioAi,
  postSitoStudioAi,
  type AiArticle,
  type AiGenerateForm,
  type AiJob,
  type SitoStudioAiData,
} from '../sitoStudioAiData'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import './SitoStudioRedazioneAiPage.css'

function StatCard({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <article className="iu-site-ai-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`iu-site-ai-field ${wide ? 'is-wide' : ''}`.trim()}>
      <span>{label}</span>
      {children}
    </label>
  )
}

function JobCard({ job, busy, onCreateDraft }: { job: AiJob; busy: boolean; onCreateDraft: (jobId: number) => void }) {
  return (
    <article className="iu-site-ai-row">
      <div className="iu-site-ai-row__main">
        <div className="iu-site-ai-row__head">
          <strong>{job.title}</strong>
          <span>{job.statusLabel}</span>
        </div>
        <p>{job.excerpt || job.topic || 'Bozza pronta per la revisione dello studio.'}</p>
        {job.risks.length ? (
          <div className="iu-site-ai-risks">
            {job.risks.slice(0, 4).map((risk, index) => (
              <span key={`${job.id}-${risk.area}-${index}`}>
                <ShieldCheck size={13} />
                {risk.area}: {risk.severityLabel}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="iu-site-ai-row__actions">
        {job.draftAvailable ? (
          <Button tone="success" type="button" disabled={busy} onClick={() => onCreateDraft(job.id)}>
            <FilePenLine size={15} />
            Crea bozza
          </Button>
        ) : (
          <ButtonLink tone="neutral" href={`/sito-studio/articoli/${job.articleId}/modifica`}>
            <FilePenLine size={15} />
            Apri articolo
          </ButtonLink>
        )}
      </div>
    </article>
  )
}

function ArticleCard({
  article,
  busy,
  onImage,
  onPublish,
}: {
  article: AiArticle
  busy: boolean
  onImage: (articleId: number) => void
  onPublish: (articleId: number) => void
}) {
  return (
    <article className="iu-site-ai-row">
      <div className="iu-site-ai-row__main">
        <div className="iu-site-ai-row__head">
          <strong>{article.title}</strong>
          <span>{article.statusLabel}</span>
        </div>
        <p>{article.excerpt || 'Articolo presente nel sito studio.'}</p>
        <div className="iu-site-ai-risks">
          <span><Newspaper size={13} />{article.category}</span>
          {article.coverUrl ? <span><ImagePlus size={13} />Immagine collegata</span> : null}
        </div>
      </div>
      <div className="iu-site-ai-row__actions">
        <ButtonLink tone="neutral" href={article.editHref}>
          <FilePenLine size={15} />
          Modifica
        </ButtonLink>
        <Button tone="neutral" type="button" disabled={busy} onClick={() => onImage(article.id)}>
          <ImagePlus size={15} />
          Immagine
        </Button>
        {!article.published ? (
          <Button tone="success" type="button" disabled={busy} onClick={() => onPublish(article.id)}>
            <Send size={15} />
            Pubblica
          </Button>
        ) : null}
      </div>
    </article>
  )
}

function ArticleForm({
  form,
  setForm,
  onSubmit,
  busy,
}: {
  form: AiGenerateForm
  setForm: Dispatch<SetStateAction<AiGenerateForm>>
  onSubmit: () => void
  busy: boolean
}) {
  const patch = (key: keyof AiGenerateForm, value: string) => setForm((current) => ({ ...current, [key]: value }))
  return (
    <section className="iu-site-ai-panel iu-site-ai-panel--form">
      <header>
        <span><Sparkles size={15} />Nuova bozza</span>
        <h2>Prepara articolo</h2>
      </header>
      <div className="iu-site-ai-form">
        <Field label="Argomento" wide>
          <input value={form.argomento} onChange={(event) => patch('argomento', event.currentTarget.value)} placeholder="es. separazione consensuale: documenti necessari" required />
        </Field>
        <Field label="Area di diritto">
          <input value={form.area_diritto} onChange={(event) => patch('area_diritto', event.currentTarget.value)} placeholder="Famiglia, lavoro, civile" />
        </Field>
        <Field label="Servizio collegato">
          <input value={form.servizio_collegato} onChange={(event) => patch('servizio_collegato', event.currentTarget.value)} placeholder="Consulenza famiglia" />
        </Field>
        <Field label="Destinatari">
          <select value={form.pubblico_destinatario} onChange={(event) => patch('pubblico_destinatario', event.currentTarget.value)}>
            {['Privati', 'Imprese', 'Famiglie', 'Lavoratori', 'Amministratori'].map((label) => <option key={label}>{label}</option>)}
          </select>
        </Field>
        <Field label="Tono">
          <select value={form.tono} onChange={(event) => patch('tono', event.currentTarget.value)}>
            {['divulgativo', 'tecnico', 'istituzionale', 'sintetico', 'approfondito'].map((label) => <option key={label}>{label}</option>)}
          </select>
        </Field>
        <Field label="Lunghezza">
          <select value={form.lunghezza} onChange={(event) => patch('lunghezza', event.currentTarget.value)}>
            {['media', 'breve', 'lunga'].map((label) => <option key={label}>{label}</option>)}
          </select>
        </Field>
        <Field label="Parole chiave">
          <input value={form.parole_chiave_seo} onChange={(event) => patch('parole_chiave_seo', event.currentTarget.value)} placeholder="separate da virgola" />
        </Field>
        <Field label="Invito finale" wide>
          <input value={form.call_to_action} onChange={(event) => patch('call_to_action', event.currentTarget.value)} placeholder="Invita a contattare lo studio senza promettere risultati" />
        </Field>
        <Field label="Fonte indicata" wide>
          <input value={form.fonte_manual} onChange={(event) => patch('fonte_manual', event.currentTarget.value)} placeholder="Facoltativa, da verificare prima della pubblicazione" />
        </Field>
        <Field label="Note interne" wide>
          <textarea value={form.note_interne} onChange={(event) => patch('note_interne', event.currentTarget.value)} rows={4} />
        </Field>
      </div>
      <Button type="button" tone="primary" disabled={busy || !form.argomento.trim()} onClick={onSubmit}>
        <Bot size={16} />
        Genera bozza
      </Button>
    </section>
  )
}

export function SitoStudioRedazioneAiPage() {
  const [data, setData] = useState<SitoStudioAiData>(emptySitoStudioAiData)
  const [form, setForm] = useState<AiGenerateForm>(emptyAiForm)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const loadPage = useCallback(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    getSitoStudioAi(controller.signal)
      .then(setData)
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setError('Redazione assistita non disponibile.')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => loadPage(), [loadPage])

  const run = async (action: () => Promise<{ ok: boolean; message: string; payload?: SitoStudioAiData }>) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await action()
      if (!result.ok) throw new Error(result.message)
      if (result.payload) setData(result.payload)
      setStatus(result.message)
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operazione non completata.')
      return false
    } finally {
      setBusy(false)
    }
  }

  const latestJobs = useMemo(() => data.jobs.slice(0, 8), [data.jobs])
  const latestArticles = useMemo(() => data.articles.slice(0, 10), [data.articles])

  return (
    <Page
      title="Redazione assistita Sito Studio"
      subtitle="Bozze articolo, revisione professionale, immagini editoriali e pubblicazione manuale."
      actions={
        <>
          <ButtonLink href="/sito-studio/builder" tone="neutral"><FilePenLine size={16} /> Editor</ButtonLink>
          <ButtonLink href="/sito-studio" tone="neutral"><Globe2 size={16} /> Cruscotto</ButtonLink>
          <Button tone="neutral" type="button" disabled={busy} onClick={loadPage}><RefreshCw size={16} /> Aggiorna</Button>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento redazione" message="Lettura bozze, articoli e controlli dello studio." /> : null}
      {!loading && error ? <EmptyState title="Redazione non disponibile" message={error} /> : null}
      {!loading && !error ? (
        <section className="iu-site-ai-page" aria-label="Redazione assistita del sito">
          <section className="iu-site-ai-stats" aria-label="Riepilogo redazione">
            <StatCard label="Lavori" value={data.summary.jobs} note="bozze preparate" />
            <StatCard label="Articoli" value={data.summary.articles} note="nel sito studio" />
            <StatCard label="Bozze" value={data.summary.drafts} note="da revisionare" />
            <StatCard label="Pubblicati" value={data.summary.published} note="visibili sul sito" />
          </section>
          {status ? <section className="iu-site-ai-message is-success">{status}</section> : null}
          {error ? <section className="iu-site-ai-message is-danger">{error}</section> : null}

          <div className="iu-site-ai-layout">
            <ArticleForm
              form={form}
              setForm={setForm}
              busy={busy}
              onSubmit={() => run(() => postSitoStudioAi('/api/v1/ui/sito-studio/redazione-ai/articolo/genera', form)).then((ok) => {
                if (ok) setForm(emptyAiForm)
              })}
            />

            <section className="iu-site-ai-panel">
              <header>
                <span><Bot size={15} />Lavori recenti</span>
                <h2>Bozze generate</h2>
              </header>
              {latestJobs.length ? (
                <div className="iu-site-ai-list">
                  {latestJobs.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      busy={busy}
                      onCreateDraft={(jobId) => run(() => postSitoStudioAi(`/api/v1/ui/sito-studio/redazione-ai/jobs/${jobId}/crea-bozza`, {}))}
                    />
                  ))}
                </div>
              ) : <EmptyState title="Nessuna bozza assistita" message="Inserisci un argomento reale per preparare il primo articolo." />}
            </section>
          </div>

          <section className="iu-site-ai-panel">
            <header>
              <span><Newspaper size={15} />Articoli sito</span>
              <h2>Revisione e pubblicazione</h2>
            </header>
            {latestArticles.length ? (
              <div className="iu-site-ai-list">
                {latestArticles.map((article) => (
                  <ArticleCard
                    key={article.id}
                    article={article}
                    busy={busy}
                    onImage={(articleId) => run(() => postSitoStudioAi(`/api/v1/ui/sito-studio/redazione-ai/articoli/${articleId}/genera-immagine`, {}))}
                    onPublish={(articleId) => run(() => postSitoStudioAi(`/api/v1/ui/sito-studio/redazione-ai/articoli/${articleId}/pubblica`, {}))}
                  />
                ))}
              </div>
            ) : <EmptyState title="Nessun articolo" message="Le bozze create compariranno qui per revisione, immagine e pubblicazione." />}
          </section>
        </section>
      ) : null}
    </Page>
  )
}
