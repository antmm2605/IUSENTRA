import { useEffect, useRef, useState } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { CalendarClock, FolderOpen, Gavel, RefreshCw, Send } from 'lucide-react'
import {
  dataItaliana,
  emptyLexOperativo,
  getLexOperativo,
  type LexOperativoData,
} from '../lexOperativoData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './LexOperativoPage.css'

const ORIZZONTI = [7, 14, 30]

function orizzonteIniziale(): number {
  try {
    const valore = Number(new URLSearchParams(window.location.search).get('giorni'))
    return ORIZZONTI.includes(valore) ? valore : 14
  } catch {
    return 14
  }
}

function toneLabel(tone: string): string {
  if (tone === 'danger') return 'Urgente'
  if (tone === 'warning') return 'Attenzione'
  if (tone === 'success') return 'In ordine'
  if (tone === 'info') return 'Informazione'
  return 'Da valutare'
}

export function LexOperativoPage() {
  const [giorni, setGiorni] = useState<number>(orizzonteIniziale)
  const [data, setData] = useState<LexOperativoData>(emptyLexOperativo)
  const [loading, setLoading] = useState(true)
  const [area, setArea] = useState('')
  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const refreshFlight = useRef<Promise<void> | null>(null)
  const [error, setError] = useState('')
  const matches = (values: unknown[]) => values.join(' ').toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
  const fascicoli = data.fascicolo.cards.filter(item => matches([item.title, item.numero, item.tribunale, item.missing, ...item.warnings, ...item.nextActions]))
  const udienze = data.udienza.cases.filter(item => matches([item.title, item.cliente, item.udienza, ...item.criticalPoints]))
  const telematici = data.telematico.cases.filter(item => matches([item.serviceLabel, item.officeName, item.practiceTitle, item.status]))
  const azioni = data.operativo.actions.filter(item => matches([item.title, item.description]))
  const scadenze = data.operativo.urgentDeadlines.filter(item => matches([item.titolo, dataItaliana(item.data)]))
  function refresh(): Promise<void> {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    const flight = (async () => {
      try {
        const payload = await getLexOperativo(giorni)
        if (!payload.ok) throw new Error('Dati non disponibili')
        setData(payload)
        setError('')
      } catch { setError('Aggiornamento non riuscito. I dati e i filtri restano conservati: riprova.') }
      finally { setRefreshing(false); refreshFlight.current = null }
    })()
    refreshFlight.current = flight
    return flight
  }
  useOperationalRefresh(['fascicoli', 'agenda', 'scadenze', 'comunicazioni'], refresh)

  useEffect(() => {
    let attivo = true
    setLoading(true)
    getLexOperativo(giorni)
      .then((payload) => {
        if (attivo) { setData(payload); setError('') }
      })
      .catch(() => { if (attivo) setError('Impossibile leggere i presidi operativi: riprova.') })
      .finally(() => {
        if (attivo) setLoading(false)
      })
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('giorni', String(giorni))
      window.history.replaceState(window.history.state, '', url.toString())
    } catch {
      /* URL non aggiornabile: resta solo lo stato della pagina */
    }
    return () => {
      attivo = false
    }
  }, [giorni])

  return (
    <Page
      title="Lex Operativo"
      subtitle="Cosa manca nei fascicoli, quali udienze preparare, quali avvisi telematici chiudere e la prossima azione della giornata."
      actions={
        <>
          <label className="iu-lexop-range">
            <span>Orizzonte</span>
            <select value={giorni} onChange={(event) => setGiorni(Number(event.target.value))} aria-label="Orizzonte in giorni">
              {ORIZZONTI.map((opzione) => <option value={opzione} key={opzione}>{opzione} giorni</option>)}
            </select>
          </label>
          <Button type="button" onClick={refresh} disabled={loading || refreshing} tone="neutral">
            <RefreshCw size={16} aria-hidden="true" />
            {refreshing ? 'Aggiornamento…' : 'Aggiorna'}
          </Button>
        </>
      }
    >
      {refreshing ? <p role="status">Aggiornamento dei dati in corso. I filtri restano conservati.</p> : null}
      {loading ? <LoadingState title="Lettura in corso" message="Lex legge fascicoli, udienze, telematico e scadenze dello studio." /> : null}
      {error ? <div role="alert">{error}<Button type="button" tone="neutral" onClick={refresh}>Riprova aggiornamento</Button></div> : null}
      {!loading && !data.ok ? (
        <EmptyState title="Quadro operativo non disponibile" message={data.error || 'Non è stato possibile leggere i dati dello studio. Riprova tra poco.'} />
      ) : null}
      {!loading && data.ok ? (
        <>
          <section className="iu-lexop-kpis" aria-label="Indicatori operativi">
            <KpiCard label="Fascicoli in presidio" value={String(data.fascicolo.cards.length)} note="documenti chiave, rischi aperti e lacune" active={area === 'fascicoli'} onClick={() => setArea(current => current === 'fascicoli' ? '' : 'fascicoli')} />
            <KpiCard label="Udienze da preparare" value={String(data.udienza.cases.length)} note="timeline, allegati e punti critici" active={area === 'udienze'} onClick={() => setArea(current => current === 'udienze' ? '' : 'udienze')} />
            <KpiCard label="Avvisi telematici" value={String(data.telematico.warnings)} note="errori, depositi e importazioni da verificare" active={area === 'telematico'} onClick={() => setArea(current => current === 'telematico' ? '' : 'telematico')} />
            <KpiCard label="Azioni prioritarie" value={String(data.operativo.actions.length)} note="scadenze, arretrati e prossimi passi" active={area === 'azioni'} onClick={() => setArea(current => current === 'azioni' ? '' : 'azioni')} />
          </section>
          <div className="iu-lexop-filters"><label>Cerca nei presidi<input type="search" value={query} onChange={event => setQuery(event.currentTarget.value)} placeholder="Fascicolo, cliente, udienza o attività…" /></label><Button type="button" tone="neutral" disabled={!area && !query} onClick={() => { setArea(''); setQuery('') }}>Azzera filtri</Button></div>
          <section className="iu-lexop-grid">
            {!area || area === 'fascicoli' ? (
            <Panel
              title="Quadro fascicoli"
              subtitle={data.fascicolo.summary || data.fascicolo.label}
              actions={<ButtonLink href="/workspace-intelligente" tone="neutral"><FolderOpen size={16} aria-hidden="true" />Cabina studio</ButtonLink>}
            >
              {fascicoli.length ? (
                <ul className="iu-lexop-list">
                  {fascicoli.map((item) => (
                    <li key={item.id || item.title}>
                      <a href={item.id ? `/fascicoli/${encodeURIComponent(item.id)}` : '/fascicoli'}><strong>{item.title}</strong></a>
                      <small>{[item.numero || 'Senza numero', item.tribunale].filter(Boolean).join(' · ')}</small>
                      {item.missing ? <p>{item.missing}</p> : null}
                      {item.nextActions.length ? <ul className="iu-lexop-mini">{item.nextActions.map((azione) => <li key={azione}>{azione}</li>)}</ul> : null}
                      {item.warnings.length ? <div className="iu-lexop-tags">{item.warnings.map((avviso) => <Badge tone="warning" key={avviso}>{avviso}</Badge>)}</div> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title={query ? 'Nessun risultato nei fascicoli' : 'Nessun fascicolo da evidenziare'} message={query ? 'Modifica la ricerca per visualizzare altri presidi.' : "Nell'orizzonte scelto non ci sono fascicoli con lacune o rischi aperti."} />}
            </Panel>
            ) : null}
            {!area || area === 'udienze' ? (
            <Panel
              title="Preparazione udienza"
              subtitle={data.udienza.summary || data.udienza.label}
              actions={<ButtonLink href="/wizard-pro" tone="neutral"><Gavel size={16} aria-hidden="true" />Preparazione guidata</ButtonLink>}
            >
              {data.udienza.metrics.length ? (
                <dl className="iu-lexop-metrics">
                  {data.udienza.metrics.map((metrica) => (
                    <div key={metrica.label}><dt>{metrica.label}</dt><dd>{metrica.value}</dd></div>
                  ))}
                </dl>
              ) : null}
              {udienze.length ? (
                <ul className="iu-lexop-list">
                  {udienze.map((item, indice) => (
                    <li key={`${item.title}-${indice}`}>
                      <a href={item.id ? `/fascicoli/${encodeURIComponent(item.id)}` : '/wizard-pro'}><strong>{item.title}</strong></a>
                      <small>{[item.cliente || 'Cliente da verificare', item.udienza].filter(Boolean).join(' · ')}</small>
                      <p>Timeline: {item.timeline || 'da costruire'} · documenti acquisiti {item.acquisiti} · mancanti {item.mancanti}</p>
                      {item.criticalPoints.length ? <div className="iu-lexop-tags">{item.criticalPoints.map((punto) => <Badge tone="danger" key={punto}>{punto}</Badge>)}</div> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title={query ? 'Nessun risultato nelle udienze' : 'Nessuna udienza critica'} message={query ? 'Modifica la ricerca per visualizzare altre udienze.' : 'Non ci sono udienze da presidiare adesso.'} />}
            </Panel>
            ) : null}
            {!area || area === 'telematico' ? (
            <Panel
              title="Regia telematica"
              subtitle={data.telematico.summary || data.telematico.label}
              actions={<ButtonLink href="/telematico" tone="neutral"><Send size={16} aria-hidden="true" />Cabina telematica</ButtonLink>}
            >
              <dl className="iu-lexop-metrics">
                <div><dt>Esiti in attesa</dt><dd>{data.controlTower.pendingOutcomes}</dd></div>
                <div><dt>Importazioni incomplete</dt><dd>{data.controlTower.importsIncomplete}</dd></div>
                <div><dt>Fascicoli bloccati</dt><dd>{data.controlTower.blocked}</dd></div>
              </dl>
              {telematici.length ? (
                <ul className="iu-lexop-list">
                  {telematici.map((item, indice) => (
                    <li key={`${item.serviceLabel}-${indice}`}>
                      <strong>{item.serviceLabel}</strong>
                      <small>{[item.officeName || 'Ufficio da verificare', item.practiceTitle].filter(Boolean).join(' · ')}</small>
                      <p>Stato: {item.status || 'non indicato'} · attività aperte {item.openTasks}</p>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title={query ? 'Nessun risultato negli avvisi telematici' : 'Nessun avviso telematico attivo'} />}
            </Panel>
            ) : null}
            {!area || area === 'azioni' ? (
            <Panel
              title="Prossima azione giusta"
              subtitle={data.operativo.summary || data.operativo.label}
              actions={<ButtonLink href="/" tone="neutral"><CalendarClock size={16} aria-hidden="true" />Panoramica</ButtonLink>}
            >
              {azioni.length ? (
                <ul className="iu-lexop-list">
                  {azioni.map((azione, indice) => (
                    <li key={`${azione.title}-${indice}`}>
                      <div className="iu-lexop-row"><strong>{azione.title}</strong><Badge tone={azione.tone}>{toneLabel(azione.tone)}</Badge></div>
                      {azione.description ? <p>{azione.description}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title={query ? 'Nessun risultato nelle azioni' : 'Nessuna azione da proporre'} />}
              {scadenze.length ? (
                <div className="iu-lexop-sub">
                  <strong>Scadenze che stanno diventando problemi</strong>
                  <ul className="iu-lexop-mini">
                    {scadenze.map((scadenza, indice) => (
                      <li key={`${scadenza.titolo}-${indice}`}>{scadenza.titolo} · {dataItaliana(scadenza.data)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </Panel>
            ) : null}
          </section>
        </>
      ) : null}
    </Page>
  )
}
