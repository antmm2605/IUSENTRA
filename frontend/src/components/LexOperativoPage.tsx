import { useEffect, useState } from 'react'
import { CalendarClock, FolderOpen, Gavel, RefreshCw, Send } from 'lucide-react'
import {
  dataItaliana,
  emptyLexOperativo,
  getLexOperativo,
  type LexOperativoData,
} from '../lexOperativoData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
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

  useEffect(() => {
    let attivo = true
    setLoading(true)
    getLexOperativo(giorni)
      .then((payload) => {
        if (attivo) setData(payload)
      })
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
          <ButtonLink href={`/lex-operativo?giorni=${giorni}`} tone="neutral">
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Lettura in corso" message="Lex legge fascicoli, udienze, telematico e scadenze dello studio." /> : null}
      {!loading && !data.ok ? (
        <EmptyState title="Quadro operativo non disponibile" message={data.error || 'Non è stato possibile leggere i dati dello studio. Riprova tra poco.'} />
      ) : null}
      {!loading && data.ok ? (
        <>
          <section className="iu-lexop-kpis" aria-label="Indicatori operativi">
            <KpiCard label="Fascicoli in presidio" value={String(data.fascicolo.cards.length)} note="documenti chiave, rischi aperti e lacune" />
            <KpiCard label="Udienze da preparare" value={String(data.udienza.cases.length)} note="timeline, allegati e punti critici" />
            <KpiCard label="Avvisi telematici" value={String(data.telematico.warnings)} note="errori, depositi e importazioni da verificare" />
            <KpiCard label="Azioni prioritarie" value={String(data.operativo.actions.length)} note="scadenze, arretrati e prossimi passi" />
          </section>
          <section className="iu-lexop-grid">
            <Panel
              title="Quadro fascicoli"
              subtitle={data.fascicolo.summary || data.fascicolo.label}
              actions={<ButtonLink href="/workspace-intelligente" tone="neutral"><FolderOpen size={16} aria-hidden="true" />Cabina studio</ButtonLink>}
            >
              {data.fascicolo.cards.length ? (
                <ul className="iu-lexop-list">
                  {data.fascicolo.cards.map((item) => (
                    <li key={item.id || item.title}>
                      <a href={item.id ? `/fascicoli/${encodeURIComponent(item.id)}` : '/fascicoli'}><strong>{item.title}</strong></a>
                      <small>{[item.numero || 'Senza numero', item.tribunale].filter(Boolean).join(' · ')}</small>
                      {item.missing ? <p>{item.missing}</p> : null}
                      {item.nextActions.length ? <ul className="iu-lexop-mini">{item.nextActions.map((azione) => <li key={azione}>{azione}</li>)}</ul> : null}
                      {item.warnings.length ? <div className="iu-lexop-tags">{item.warnings.map((avviso) => <Badge tone="warning" key={avviso}>{avviso}</Badge>)}</div> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Nessun fascicolo da evidenziare" message="Nell'orizzonte scelto non ci sono fascicoli con lacune o rischi aperti." />}
            </Panel>
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
              {data.udienza.cases.length ? (
                <ul className="iu-lexop-list">
                  {data.udienza.cases.map((item, indice) => (
                    <li key={`${item.title}-${indice}`}>
                      <strong>{item.title}</strong>
                      <small>{[item.cliente || 'Cliente da verificare', item.udienza].filter(Boolean).join(' · ')}</small>
                      <p>Timeline: {item.timeline || 'da costruire'} · documenti acquisiti {item.acquisiti} · mancanti {item.mancanti}</p>
                      {item.criticalPoints.length ? <div className="iu-lexop-tags">{item.criticalPoints.map((punto) => <Badge tone="danger" key={punto}>{punto}</Badge>)}</div> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Nessuna udienza critica" message="Non ci sono udienze da presidiare adesso." />}
            </Panel>
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
              {data.telematico.cases.length ? (
                <ul className="iu-lexop-list">
                  {data.telematico.cases.map((item, indice) => (
                    <li key={`${item.serviceLabel}-${indice}`}>
                      <strong>{item.serviceLabel}</strong>
                      <small>{[item.officeName || 'Ufficio da verificare', item.practiceTitle].filter(Boolean).join(' · ')}</small>
                      <p>Stato: {item.status || 'non indicato'} · attività aperte {item.openTasks}</p>
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Nessun avviso telematico attivo" />}
            </Panel>
            <Panel
              title="Prossima azione giusta"
              subtitle={data.operativo.summary || data.operativo.label}
              actions={<ButtonLink href="/" tone="neutral"><CalendarClock size={16} aria-hidden="true" />Panoramica</ButtonLink>}
            >
              {data.operativo.actions.length ? (
                <ul className="iu-lexop-list">
                  {data.operativo.actions.map((azione, indice) => (
                    <li key={`${azione.title}-${indice}`}>
                      <div className="iu-lexop-row"><strong>{azione.title}</strong><Badge tone={azione.tone}>{toneLabel(azione.tone)}</Badge></div>
                      {azione.description ? <p>{azione.description}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : <EmptyState title="Nessuna azione da proporre" />}
              {data.operativo.urgentDeadlines.length ? (
                <div className="iu-lexop-sub">
                  <strong>Scadenze che stanno diventando problemi</strong>
                  <ul className="iu-lexop-mini">
                    {data.operativo.urgentDeadlines.map((scadenza, indice) => (
                      <li key={`${scadenza.titolo}-${indice}`}>{scadenza.titolo} · {dataItaliana(scadenza.data)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </Panel>
          </section>
        </>
      ) : null}
    </Page>
  )
}
