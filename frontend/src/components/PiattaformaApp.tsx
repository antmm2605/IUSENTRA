import { useEffect, useState } from 'react'
import { ExternalLink, LayoutDashboard, LogOut, Menu, Search, X } from 'lucide-react'
import { csrfHeader } from '../api/csrf'
import { eseguiAzionePiattaforma, getPaginaPiattaforma, type AzionePf, type EsitoAzione, type PaginaPiattaforma, type Sezione, type ValoriAzione } from '../piattaformaData'
import { ModuloAzione, PulsanteAzione, type EseguiAzione } from './PiattaformaAzioni'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import './PiattaformaApp.css'

// Sezioni del pannello ancora servite dalle viste classiche: restano nel menu
// finché non passano all'applicazione React.
const ALTRE_SEZIONI = [
  { label: 'Studi', href: '/admin/studi' },
  { label: 'Utenti di piattaforma', href: '/admin/utenti-piattaforma' },
  { label: 'Aggiornamenti legali', href: '/admin/aggiornamenti-legali/' },
  { label: 'Copertura AI', href: '/admin/copertura-ai/' },
  { label: 'Server e manutenzione', href: '/admin/server-manutenzione' },
  { label: 'Supporto remoto', href: '/admin/supporto-remoto' },
]

type AzioniVista = { busy: boolean; onRun: EseguiAzione }

function SezioneView({ sezione, busy, onRun }: { sezione: Sezione } & AzioniVista) {
  if (sezione.kind === 'metrics') {
    return (
      <section className="iu-pf-metrics" aria-label={sezione.title || 'Indicatori'}>
        {sezione.items.map((item, index) => (
          <article key={`${item.label}-${index}`} className={`iu-pf-metric is-${item.tone}`}>
            <span>{item.label}</span>
            <strong>{item.value || '0'}</strong>
            {item.note ? <small>{item.note}</small> : null}
          </article>
        ))}
      </section>
    )
  }
  if (sezione.kind === 'status') {
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2>{sezione.subtitle ? <p>{sezione.subtitle}</p> : null}</header>
        <ul className="iu-pf-status">
          {sezione.items.map((item, index) => (
            <li key={`${item.title}-${index}`}>
              <div>
                <strong>{item.title}</strong>
                {item.summary ? <span>{item.summary}</span> : null}
                {item.detail ? <small>{item.detail}</small> : null}
              </div>
              {item.statusLabel ? <Badge tone={item.tone === 'neutral' ? 'neutral' : item.tone}>{item.statusLabel}</Badge> : null}
            </li>
          ))}
        </ul>
      </section>
    )
  }
  if (sezione.kind === 'table') {
    const conAzioni = sezione.rows.some((row) => row.actions.length > 0)
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2>{sezione.subtitle ? <p>{sezione.subtitle}</p> : null}</header>
        {sezione.rows.length ? (
          <div className="iu-pf-table-wrap" role="region" aria-label={sezione.title} tabIndex={0}>
            <table className="iu-pf-table">
              <thead><tr>{sezione.columns.map((c) => <th key={c.key} scope="col">{c.label}</th>)}{conAzioni ? <th scope="col"><span className="iu-pf-sr">Azioni</span></th> : null}</tr></thead>
              <tbody>
                {sezione.rows.map((row, index) => (
                  <tr key={index} className={row.tone !== 'neutral' ? `is-${row.tone}` : ''}>
                    {sezione.columns.map((c, colIndex) => (
                      <td key={c.key}>
                        {colIndex === 0 && row.href ? (
                          <a href={row.href} target={row.external ? '_blank' : undefined} rel={row.external ? 'noopener noreferrer' : undefined}>{row.cells[c.key]}</a>
                        ) : row.cells[c.key]}
                      </td>
                    ))}
                    {conAzioni ? (
                      <td className="iu-pf-row-actions">
                        {row.actions.map((azione) => <PulsanteAzione key={`${azione.key}-${JSON.stringify(azione.params)}`} azione={azione} disabled={busy} onRun={onRun} compact />)}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="iu-pf-empty">{sezione.empty}</p>}
      </section>
    )
  }
  if (sezione.kind === 'facts') {
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2></header>
        <dl className="iu-pf-facts">
          {sezione.items.map((item) => (
            <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
          ))}
        </dl>
      </section>
    )
  }
  if (sezione.kind === 'shortcuts') {
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2></header>
        <div className="iu-pf-shortcuts">
          {sezione.items.map((item) => (
            <a key={item.href} href={item.href}>
              <strong>{item.label}</strong>
              {item.detail ? <span>{item.detail}</span> : null}
            </a>
          ))}
        </div>
      </section>
    )
  }
  if (sezione.kind === 'actions') {
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2>{sezione.subtitle ? <p>{sezione.subtitle}</p> : null}</header>
        <div className="iu-pf-actions">
          {sezione.items.map((azione) => <PulsanteAzione key={`${azione.key}-${JSON.stringify(azione.params)}`} azione={azione} disabled={busy} onRun={onRun} />)}
        </div>
      </section>
    )
  }
  if (sezione.kind === 'form') {
    return (
      <section className="iu-pf-card">
        <header><h2>{sezione.title}</h2>{sezione.subtitle ? <p>{sezione.subtitle}</p> : null}</header>
        <ModuloAzione azione={sezione.action} fields={sezione.fields} disabled={busy} onRun={onRun} />
      </section>
    )
  }
  return (
    <section className={`iu-pf-card iu-pf-notes is-${sezione.tone}`}>
      <header><h2>{sezione.title}</h2></header>
      <ul>{sezione.items.map((item, index) => <li key={index}>{item}</li>)}</ul>
    </section>
  )
}

function paginaIniziale(): string {
  const root = document.getElementById('piattaforma-react-root')
  return root?.dataset.pagina || ''
}

export default function PiattaformaApp() {
  const pagina = paginaIniziale()
  const [data, setData] = useState<PaginaPiattaforma | null>(null)
  const [filtro, setFiltro] = useState(new URLSearchParams(window.location.search).get('q') || '')
  const [menuAperto, setMenuAperto] = useState(false)
  const [uscita, setUscita] = useState(false)
  const [busy, setBusy] = useState(false)
  const [esito, setEsito] = useState<EsitoAzione | null>(null)

  function ricerca(): string {
    const params = new URLSearchParams(window.location.search)
    params.delete('_legacy')
    return params.toString() ? `?${params}` : ''
  }

  async function eseguiAzione(azione: AzionePf, values: ValoriAzione) {
    setBusy(true)
    setEsito({ ok: true, message: `${azione.label}: operazione in corso…`, tone: 'info', sections: [] })
    try {
      const risultato = await eseguiAzionePiattaforma(pagina, azione, values)
      setEsito(risultato)
      if (risultato.ok) {
        const aggiornata = await getPaginaPiattaforma(pagina, ricerca())
        setData(aggiornata)
      }
    } finally {
      setBusy(false)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  async function esci() {
    setUscita(true)
    try {
      await fetch('/logout', { method: 'POST', headers: csrfHeader(), credentials: 'same-origin', redirect: 'manual' })
    } finally {
      window.location.assign('/login')
    }
  }

  useEffect(() => {
    let active = true
    getPaginaPiattaforma(pagina, ricerca()).then((result) => { if (active) setData(result) })
    return () => { active = false }
  }, [pagina])

  useEffect(() => {
    if (data?.title) document.title = `${data.title} - Piattaforma IUSENTRA`
  }, [data?.title])

  return (
    <div className={`iu-pf-app${menuAperto ? ' is-menu-open' : ''}`}>
      <button type="button" className="iu-pf-menu-toggle" aria-expanded={menuAperto} aria-controls="iu-pf-nav" onClick={() => setMenuAperto((aperto) => !aperto)}>
        {menuAperto ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
        <span>{menuAperto ? 'Chiudi menu' : 'Menu'}</span>
      </button>
      <aside id="iu-pf-nav" className="iu-pf-nav" aria-label="Pannello di piattaforma">
        <a className="iu-pf-brand" href="/admin/"><LayoutDashboard size={18} aria-hidden="true" /> Piattaforma</a>
        <nav>
          <p>Pagine</p>
          {(data?.menu || []).map((item) => (
            <a key={item.key} href={item.href} aria-current={item.key === pagina ? 'page' : undefined}>{item.label}</a>
          ))}
          <p>Altre sezioni</p>
          {ALTRE_SEZIONI.map((item) => <a key={item.href} href={item.href}>{item.label}</a>)}
        </nav>
        <footer className="iu-pf-user">
          {data?.user ? <strong>{data.user}</strong> : null}
          <span>Superamministratore</span>
          <button type="button" onClick={esci} disabled={uscita}><LogOut size={15} aria-hidden="true" /> {uscita ? 'Uscita…' : 'Esci'}</button>
        </footer>
      </aside>
      <main className="iu-pf-main">
        {!data ? <LoadingState title="Caricamento della pagina" /> : null}
        {data && !data.ok ? <EmptyState title="Pagina non disponibile" message={data.message} /> : null}
        {data && data.ok ? (
          <>
            <header className="iu-pf-header">
              <div>
                <h1>{data.title}</h1>
                {data.subtitle ? <p>{data.subtitle}</p> : null}
              </div>
              <div className="iu-pf-links">
                {data.links.map((item) => (
                  <ButtonLink key={item.href} href={item.href} tone={item.tone === 'neutral' ? 'neutral' : 'primary'} target={item.external ? '_blank' : undefined} rel={item.external ? 'noopener noreferrer' : undefined}>
                    {item.label}{item.external ? <ExternalLink size={13} aria-hidden="true" /> : null}
                  </ButtonLink>
                ))}
              </div>
            </header>
            {data.filter && data.filter.options.length ? (
              <div className="iu-pf-filter">
                <label>
                  <span>{data.filter.label}</span>
                  <select
                    value={data.filter.value}
                    onChange={(event) => {
                      const value = event.currentTarget.value
                      const params = new URLSearchParams()
                      if (value) params.set(data.filter?.name || 'q', value)
                      window.location.search = params.toString()
                    }}
                  >
                    {data.filter.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
              </div>
            ) : null}
            {data.filter && !data.filter.options.length ? (
              <form className="iu-pf-filter" role="search" onSubmit={(event) => { event.preventDefault(); const params = new URLSearchParams(); if (filtro.trim()) params.set(data.filter?.name || 'q', filtro.trim()); window.location.search = params.toString() }}>
                <label>
                  <span>{data.filter.label}</span>
                  <input type="search" value={filtro} onChange={(event) => { const value = event.currentTarget.value; setFiltro(value) }} />
                </label>
                <button type="submit"><Search size={15} aria-hidden="true" /> Cerca</button>
              </form>
            ) : null}
            {esito ? (
              <section className={`iu-pf-esito is-${esito.tone}`} role={esito.ok ? 'status' : 'alert'} aria-live="polite">
                <div>
                  <strong>{esito.message}</strong>
                  <button type="button" onClick={() => setEsito(null)} aria-label="Chiudi il messaggio"><X size={15} aria-hidden="true" /></button>
                </div>
                {esito.sections.map((sezione, index) => <SezioneView key={`esito-${sezione.kind}-${index}`} sezione={sezione} busy={busy} onRun={eseguiAzione} />)}
              </section>
            ) : null}
            {data.sections.map((sezione, index) => <SezioneView key={`${sezione.kind}-${index}`} sezione={sezione} busy={busy} onRun={eseguiAzione} />)}
          </>
        ) : null}
      </main>
    </div>
  )
}
