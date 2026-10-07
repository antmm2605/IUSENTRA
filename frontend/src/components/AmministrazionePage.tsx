import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, CircleAlert, ClipboardCheck, Database, ExternalLink, FlaskConical, MonitorCheck, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  emptyDataConsistencyPage,
  emptyAmministrazionePage,
  getDataConsistencyPage,
  getAmministrazionePage,
  type DataConsistencyPageData,
  type AmministrazionePageData,
} from '../amministrazioneData'
import {
  emptyProductReadinessPage,
  getProductReadinessPage,
  type ProductReadinessCapability,
  type ProductReadinessPageData,
} from '../productReadinessData'
import { buttonTone, type LegacyModule, type OperationalModule } from '../studioData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { displaySourceLabel, displayWritesLabel } from '../displayText'
import { formatDateTimeIt } from '../formatting'
import './AmministrazionePage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

const metricHrefs: Record<string, string> = {utenti:'/utenti', attivi:'/utenti?stato=attivi', profili:'/profili?vista=ruoli-usati', audit:'/audit', override:'/utenti?stato=override'}

function WarningPanel({ data }: { data: AmministrazionePageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi">
      <div className="iu-adminhub-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-adminhub-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ModuleList({ modules, legacy = false }: { modules: Array<OperationalModule | LegacyModule>; legacy?: boolean }) {
  if (!modules.length) return <EmptyState title={legacy ? 'Nessuna area protetta' : 'Nessun modulo operativo disponibile'} />
  return (
    <div className="iu-adminhub-modules">
      {modules.map((record) => (
        <ButtonLink className="iu-adminhub-module" tone={legacy ? 'warning' : 'neutral'} href={record.href} aria-label={`Apri ${record.label}`} key={record.id}>
          <div>
            {legacy ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}
            <strong>{record.label}</strong>
            <span>{record.note}</span>
          </div>
          <Badge tone={record.tone}>{record.status}</Badge>
          <span>Apri →</span>
        </ButtonLink>
      ))}
    </div>
  )
}

function SecurityPanel({ data }: { data: AmministrazionePageData }) {
  const security = data.security
  return (
    <Panel title="Sicurezza e permessi" subtitle="Indicatori aggregati senza credenziali o dati riservati">
      <div className="iu-adminhub-security">
        <ButtonLink href="/profili" tone="neutral" aria-label="Consulta sicurezza e permessi">
          <span>Stato</span>
          <strong>{security.status || 'non indicato'}</strong>
          <small>Consulta profili →</small>
        </ButtonLink>
        <ButtonLink href="/audit" tone="neutral" aria-label="Apri registro attività">
          <span>Registro</span>
          <strong>{security.canReadAudit ? 'visibile' : 'permesso richiesto'}</strong>
          <small>Apri registro →</small>
        </ButtonLink>
        <ButtonLink href="/utenti?stato=override" tone="neutral" aria-label="Apri utenti con permessi personalizzati">
          <span>Override permessi</span>
          <strong>{formatValue(security.permissionOverrides || 0)}</strong>
          <small>Filtra utenti →</small>
        </ButtonLink>
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: AmministrazionePageData }) {
  return (
    <Panel title="Qualità dati" subtitle="Informazioni operative, impostazioni sensibili protette.">
      <div className="iu-adminhub-contract">
        <span>Origine: {displaySourceLabel(data.source || '')}</span>
        <span>Generato: {formatDateTimeIt(data.generated_at, 'Non disponibile')}</span>
        <span>Azioni: {displayWritesLabel(data.contracts.writes || '')}</span>
        <span>Operativo: {data.contracts.operational ? 'sì' : 'no'}</span>
        <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'sì'}</span>
      </div>
    </Panel>
  )
}

function EvidenceIcon({ kind }: { kind: string }) {
  if (kind === 'ci') return <FlaskConical size={15} aria-hidden="true" />
  if (kind === 'browser') return <MonitorCheck size={15} aria-hidden="true" />
  return <ShieldCheck size={15} aria-hidden="true" />
}

function CapabilityDetail({ capability }: { capability: ProductReadinessCapability }) {
  return (
    <details className="iu-readiness-capability">
      <summary>
        <span className="iu-readiness-capability__main">
          <strong>{capability.module}</strong>
          <small>{capability.owner} · {capability.lastSmoke.label}</small>
        </span>
        <Badge tone={capability.statusTone}>{capability.statusLabel}</Badge>
      </summary>
      <div className="iu-readiness-capability__body">
        <p className="iu-readiness-capability__note">{capability.statusNote}</p>
        <dl className="iu-readiness-capability__facts">
          <div><dt>Versione regole</dt><dd>{capability.version || 'Non disponibile'}</dd></div>
          <div><dt>Feature flag</dt><dd>{capability.featureFlag || 'Nessun flag dedicato censito'}</dd></div>
          <div><dt>Route</dt><dd><code>{capability.route || 'Da definire'}</code></dd></div>
          <div><dt>API</dt><dd><code>{capability.api || 'Da definire'}</code></dd></div>
          <div><dt>Backend</dt><dd>{capability.backend || 'Da verificare'}</dd></div>
          <div><dt>Storage</dt><dd>{capability.storage || 'Da verificare'}</dd></div>
          <div><dt>Permessi</dt><dd>{capability.permissions.join(', ') || 'Da definire'}</dd></div>
          <div><dt>Operazioni</dt><dd>{capability.operations.join(', ') || 'Da definire'}</dd></div>
          <div><dt>Locale</dt><dd>{capability.environment.local}</dd></div>
          <div><dt>Produzione</dt><dd>{capability.environment.production}</dd></div>
          <div><dt>Dipendenze</dt><dd>{capability.dependencies.join(', ') || 'Nessuna'}</dd></div>
          <div><dt>Incidenti</dt><dd>{capability.incidents.label}</dd></div>
        </dl>
        <section className="iu-readiness-evidence" aria-label={`Prove ${capability.module}`}>
          {capability.evidence.map((evidence) => (
            <article key={`${capability.id}-${evidence.kind}`}>
              <EvidenceIcon kind={evidence.kind} />
              <div>
                <span>{evidence.label}</span>
                <strong>{evidence.status}</strong>
                {evidence.reference ? <small>{evidence.reference}</small> : null}
                {evidence.lastVerified ? <small>Verificata: {formatDateTimeIt(evidence.lastVerified, 'Non disponibile')}</small> : null}
                {evidence.note ? <small>{evidence.note}</small> : null}
              </div>
            </article>
          ))}
        </section>
        <div className="iu-readiness-capability__closing">
          <p><strong>Limitazione:</strong> {capability.limitations}</p>
          <p><strong>Rollback:</strong> {capability.rollback}</p>
          <p><strong>Prossima azione:</strong> {capability.nextAction}</p>
          <p><strong>Test associati:</strong> {capability.tests.join(', ') || 'Da censire'}</p>
        </div>
      </div>
    </details>
  )
}

function ProductReadinessView({ data, loading, error }: { data: ProductReadinessPageData; loading: boolean; error: string }) {
  const hasData = data.capabilities.length > 0
  const [filter, setFilter] = useState('')
  const [query, setQuery] = useState('')
  const visibleCapabilities = data.capabilities.filter(item => (!filter || item.status === filter) && `${item.module} ${item.owner} ${item.statusLabel} ${item.statusNote}`.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT')))
  return (
    <Page
      title="Prontezza prodotto"
      subtitle="Registro P0 generato: mostra prove reali, prove mancanti e prossime azioni senza dichiarazioni promozionali."
      actions={<ButtonLink href="/amministrazione" tone="neutral"><ArrowLeft size={15} />Torna ad amministrazione</ButtonLink>}
    >
      {loading ? <LoadingState title="Caricamento prontezza prodotto" message="Lettura del catalogo di rilascio in corso." /> : null}
      {!loading && error ? <EmptyState title="Registro di prontezza non disponibile" message={error} action={<ButtonLink href="/amministrazione" tone="primary">Torna ad amministrazione</ButtonLink>} /> : null}
      {!loading && !error && !hasData ? <EmptyState title="Nessuna capability P0 disponibile" message="Il catalogo non ha restituito superfici verificabili." action={<ButtonLink href="/amministrazione" tone="primary">Torna ad amministrazione</ButtonLink>} /> : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-readiness-banner" aria-label="Regola di verità del registro">
            <CircleAlert size={20} aria-hidden="true" />
            <div>
              <strong>{data.scope}</strong>
              <span>Una prova assente resta “da verificare”: il registro non converte il codice o un test esistente in una certificazione operativa.</span>
            </div>
          </section>
          {data.warnings.length ? (
            <Panel title="Avvisi di verità" subtitle="Condizioni che impediscono una dichiarazione di completezza">
              <div className="iu-adminhub-warnings">
                {data.warnings.map((warning) => <div className="iu-adminhub-warning" key={`${warning.code}-${warning.message}`}><Badge tone="warning">{warning.code}</Badge><span>{warning.message}</span></div>)}
              </div>
            </Panel>
          ) : null}
          <section className="iu-readiness-kpis" aria-label="Riepilogo capability P0">
            <KpiCard label="Flussi P0" value={formatValue(data.summary.total)} note="Superfici censite" active={!filter} onClick={() => setFilter('')} actionLabel="Mostra tutti" />
            <KpiCard label="Verificate" value={formatValue(data.summary.verified)} note="Con prova corrente registrata" active={filter === 'verificata'} onClick={() => setFilter('verificata')} actionLabel="Filtra registro" />
            <KpiCard label="Da verificare" value={formatValue(data.summary.pending)} note="Prove browser e fornitore ancora richieste" active={filter === 'da verificare'} onClick={() => setFilter('da verificare')} actionLabel="Filtra registro" />
            <KpiCard label="Parziali" value={formatValue(data.summary.partial)} note="Prove presenti con limiti dichiarati" active={filter === 'parziale'} onClick={() => setFilter('parziale')} actionLabel="Filtra registro" />
            <KpiCard label="Bloccate" value={formatValue(data.summary.blocked)} note="Requisiti che impediscono il flusso" active={filter === 'bloccata'} onClick={() => setFilter('bloccata')} actionLabel="Filtra registro" />
          </section>
          <section className="iu-adminhub-filters" aria-label="Ricerca registro di prontezza"><label>Cerca flussi<input type="search" value={query} onChange={event => setQuery(event.currentTarget.value)}/></label><Button type="button" tone="neutral" disabled={!filter && !query} onClick={() => {setFilter('');setQuery('')}}>Azzera filtri</Button><span role="status">{visibleCapabilities.length} di {data.capabilities.length} flussi</span></section>
          <Panel title="Contratto del registro" subtitle={`Registro ${data.registryVersion || 'non disponibile'} · applicazione ${data.applicationVersion || 'non disponibile'}`}>
            <div className="iu-readiness-contract">
              <span><Database size={15} aria-hidden="true" />Fonte: {data.contracts.sourceOfTruth || 'Non disponibile'}</span>
              <span><ClipboardCheck size={15} aria-hidden="true" />Scritture: {displayWritesLabel(data.contracts.writes)}</span>
              <span><ShieldCheck size={15} aria-hidden="true" />Fornitori: {data.contracts.providerCalls ? 'contattati' : 'non contattati'}</span>
              <span>Generato: {formatDateTimeIt(data.generatedAt, 'Non disponibile')}</span>
            </div>
          </Panel>
          <Panel title="Capability P0" subtitle="Apri una riga per route, API, dati, prove, limiti e rollback.">
            <div className="iu-readiness-capabilities">
              {visibleCapabilities.map((capability) => <CapabilityDetail capability={capability} key={capability.id} />)}
              {!visibleCapabilities.length ? <EmptyState title="Nessun flusso corrisponde ai filtri" /> : null}
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}

type EventFilters = {status:string;query:string;page:number}
function DataConsistencyView({ data, loading, error, onRefresh, filters, onFilters }: { data: DataConsistencyPageData; loading: boolean; error: string; onRefresh: () => void; filters:EventFilters;onFilters:(filters:EventFilters)=>void }) {
  const readableDomains = data.domains.filter((domain) => domain.status === 'PRESIDIATO').length
  const [mode,setMode]=useState<'domini'|'eventi'>('domini')
  const [readableOnly,setReadableOnly]=useState(false)
  const [eventQuery,setEventQuery]=useState(filters.query)
  const visibleDomains=data.domains.filter(domain=>!readableOnly||domain.status==='PRESIDIATO')
  const showEvents=(status:string)=>{setMode('eventi');onFilters({...filters,status,page:1})}
  return (
    <Page
      title="Coerenza dati"
      subtitle="Controllo in sola lettura dell’archivio SQL dello studio."
      actions={
        <>
          <Button tone="neutral" onClick={onRefresh} disabled={loading}><RefreshCw size={15} />Aggiorna controllo</Button>
          <ButtonLink href="/amministrazione" tone="neutral"><ArrowLeft size={15} />Torna ad amministrazione</ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Controllo coerenza dati" message="Lettura dell’archivio SQL dello studio in corso." /> : null}
      {!loading && error ? <EmptyState title="Controllo coerenza incompleto" message={error} action={<Button tone="neutral" onClick={onRefresh}>Riprova controllo</Button>} /> : null}
      {data.domains.length > 0 ? (
        <>
          <section className="iu-consistency-banner" aria-label="Regola di verità della coerenza dati">
            <Database size={20} aria-hidden="true" />
            <div>
              <strong>Fonte operativa: {data.sourceOfTruth === 'sqlite' ? 'Database SQLite' : data.sourceOfTruth === 'postgresql' ? 'Database PostgreSQL' : 'Archivio SQL'}</strong>
              <span>Tenant: {data.tenantScope || 'studio corrente'} · I mirror JSON non sono stati letti né usati come fallback.</span>
            </div>
          </section>
          {data.warnings.length ? <Panel title="Anomalie da presidiare"><div className="iu-adminhub-warnings">{data.warnings.map((warning) => <div className="iu-adminhub-warning" key={`${warning.code}-${warning.message}`}><Badge tone="warning">{warning.code}</Badge><span>{warning.message}</span></div>)}</div></Panel> : null}
          <section className="iu-readiness-kpis iu-consistency-kpis" aria-label="Riepilogo coerenza dati">
            <KpiCard label="Domini leggibili" value={formatValue(readableDomains)} note={`${data.domains.length} domini P0 censiti`} onClick={()=>{setMode('domini');setReadableOnly(true)}} active={mode==='domini'&&readableOnly} actionLabel="Consulta domini" />
            <KpiCard label="Eventi in attesa" value={data.outbox.readable?formatValue(data.outbox.pending):'Non disponibile'} note="Eventi interni da elaborare" onClick={()=>showEvents('PENDING')} active={mode==='eventi'&&filters.status==='PENDING'} actionLabel="Consulta eventi" />
            <KpiCard label="Eventi completati" value={data.outbox.readable?formatValue(data.outbox.processed):'Non disponibile'} note="Consegne interne registrate" onClick={()=>showEvents('PROCESSED')} active={mode==='eventi'&&filters.status==='PROCESSED'} actionLabel="Consulta eventi" />
            <KpiCard label="Eventi con errore" value={data.outbox.readable?formatValue(data.outbox.failed):'Non disponibile'} note="Da analizzare prima di un ritentativo" onClick={()=>showEvents('FAILED')} active={mode==='eventi'&&filters.status==='FAILED'} actionLabel="Consulta eventi" />
          </section>
          <Panel title="Contratto di controllo" subtitle={`Generato: ${formatDateTimeIt(data.generatedAt, 'Non disponibile')}`}>
            <div className="iu-readiness-contract">
              <span><ClipboardCheck size={15} aria-hidden="true" />Scritture: {displayWritesLabel(data.contracts.writes)}</span>
              <span><ShieldCheck size={15} aria-hidden="true" />Fallback JSON: {data.contracts.fallbackUsed ? 'rilevato' : 'assente'}</span>
              <span><Database size={15} aria-hidden="true" />Scansione JSON: {data.contracts.jsonScanned ? 'rilevata' : 'assente'}</span>
              <span>Eventi totali: {data.outbox.readable ? formatValue(data.outbox.total) : 'Non disponibile'}</span>
            </div>
          </Panel>
          <nav className="iu-adminhub-filters" aria-label="Contesto coerenza dati"><Button tone="neutral" aria-pressed={mode==='domini'} onClick={()=>{setMode('domini');setReadableOnly(false)}}>Tutti i domini</Button><Button tone="neutral" aria-pressed={mode==='eventi'&&!filters.status} onClick={()=>showEvents('')}>Tutti gli eventi</Button></nav>
          {mode==='domini' ? <Panel title="Domini P0" subtitle={`${visibleDomains.length} di ${data.domains.length} domini · Apri una riga per tabelle e conteggi.`}>
            <div className="iu-consistency-domains">
              {visibleDomains.map((domain) => (
                <details className="iu-consistency-domain" key={domain.id}>
                  <summary>
                    <span><strong>{domain.label}</strong><small>{domain.repository}</small></span>
                    <span className="iu-consistency-domain__summary"><strong>{domain.records === null ? 'Non leggibile' : formatValue(domain.records)}</strong><Badge tone={domain.status === 'PRESIDIATO' ? 'success' : 'danger'}>{domain.status === 'PRESIDIATO' ? 'presidiato' : 'non leggibile'}</Badge></span>
                  </summary>
                  <div className="iu-consistency-domain__body">
                    <p>JSON: {domain.jsonRole}.</p>
                    <div className="iu-consistency-tables">
                      {domain.tables.map((table) => <div key={table.table}><code>{table.table}</code><strong>{table.count === null ? 'Non leggibile' : formatValue(table.count)}</strong>{table.reason ? <small>{table.reason}</small> : null}</div>)}
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </Panel> : <Panel title="Registro eventi interni" subtitle="Consultazione in sola lettura, senza eseguire o ritentare operazioni.">
            <form className="iu-adminhub-filters" onSubmit={event=>{event.preventDefault();onFilters({...filters,query:eventQuery,page:1})}}><label>Cerca eventi<input aria-label="Cerca eventi" type="search" value={eventQuery} onChange={event=>setEventQuery(event.currentTarget.value)} placeholder="Evento, categoria o riferimento" /></label><label>Stato evento<select aria-label="Stato evento" value={filters.status} onChange={event=>showEvents(event.currentTarget.value)}><option value="">Tutti gli stati</option><option value="PENDING">In attesa</option><option value="PROCESSED">Completati</option><option value="FAILED">Con errore</option></select></label><Button type="submit">Cerca</Button><Button type="button" tone="neutral" disabled={!filters.status&&!filters.query&&!eventQuery} onClick={()=>{setEventQuery('');onFilters({status:'',query:'',page:1})}}>Azzera filtri</Button></form>
            {!data.events.readable ? <EmptyState title="Registro eventi non leggibile" message="I conteggi e l’elenco non costituiscono una conferma dell’assenza di eventi. Riprova il controllo." /> : <><p role="status">{formatValue(data.events.total)} eventi · Pagina {data.events.page} di {Math.max(1,Math.ceil(data.events.total/data.events.pageSize))}</p><div className="iu-consistency-events">{data.events.records.map(item=><article key={item.id}><div><strong>{item.eventType}</strong><Badge tone={item.status==='FAILED'?'danger':item.status==='PROCESSED'?'success':'info'}>{item.status==='FAILED'?'Con errore':item.status==='PROCESSED'?'Completato':item.status==='PENDING'?'In attesa':'Stato non riconosciuto'}</Badge></div><p>{item.aggregateType} · Riferimento {item.aggregateId}</p><small>Registrato: {formatDateTimeIt(item.createdAt,'Data non disponibile')} · Tentativi: {item.attempts}</small>{item.processedAt?<small>Elaborato: {formatDateTimeIt(item.processedAt,'Data non disponibile')}</small>:null}</article>)}</div>{!data.events.total?<EmptyState title="Nessun evento corrisponde ai filtri" message="Il registro SQL non contiene eventi per la selezione corrente."/>:null}<nav className="iu-adminhub-filters" aria-label="Pagine registro eventi"><Button tone="neutral" disabled={data.events.page<=1} onClick={()=>onFilters({...filters,page:data.events.page-1})}>Precedente</Button><Button tone="neutral" disabled={data.events.page*data.events.pageSize>=data.events.total} onClick={()=>onFilters({...filters,page:data.events.page+1})}>Successiva</Button></nav></>}
          </Panel>}
        </>
      ) : null}
    </Page>
  )
}

export function AmministrazionePage() {
  const [data, setData] = useState<AmministrazionePageData>(emptyAmministrazionePage)
  const [readiness, setReadiness] = useState<ProductReadinessPageData>(emptyProductReadinessPage)
  const [consistency, setConsistency] = useState<DataConsistencyPageData>(emptyDataConsistencyPage)
  const [eventFilters,setEventFilters]=useState<EventFilters>({status:'',query:'',page:1})
  const consistencyRequest=useRef(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const readinessSelected = new URLSearchParams(window.location.search).get('tab') === 'prontezza-prodotto'
  const consistencySelected = new URLSearchParams(window.location.search).get('tab') === 'consistenza-dati'

  const refreshConsistency = useCallback(() => {
    const requestId=++consistencyRequest.current
    setLoading(true)
    setError('')
    getDataConsistencyPage(eventFilters)
      .then((payload) => {
        if(requestId!==consistencyRequest.current)return
        setConsistency(payload)
        setError(payload.ok ? '' : payload.warnings[0]?.message || 'Coerenza dati non disponibile.')
      })
      .catch(() => {if(requestId===consistencyRequest.current)setError('Coerenza dati non disponibile.')})
      .finally(() => {if(requestId===consistencyRequest.current)setLoading(false)})
  }, [eventFilters])

  useEffect(() => {
    if (consistencySelected) {
      refreshConsistency()
      return
    }
    let active = true
    setLoading(true)
    setError('')
    const request = readinessSelected ? getProductReadinessPage() : getAmministrazionePage()
    request
      .then((payload) => {
        if (!active) return
        if (readinessSelected) {
          const readinessPayload = payload as ProductReadinessPageData
          setReadiness(readinessPayload)
          setError(readinessPayload.ok ? '' : readinessPayload.warnings[0]?.message || 'Registro di prontezza non disponibile.')
          return
        }
        const administrationPayload = payload as AmministrazionePageData
        setData(administrationPayload)
        setError(administrationPayload.ok ? '' : administrationPayload.warnings[0]?.message || 'Pagina amministrazione non disponibile.')
      })
      .catch(() => {
        if (active) setError(readinessSelected ? 'Registro di prontezza non disponibile.' : 'Pagina amministrazione non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [consistencySelected, readinessSelected, refreshConsistency])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.operational_routes.length > 0 || data.sections.some((section) => section.items.length > 0),
    [data],
  )

  if (readinessSelected) return <ProductReadinessView data={readiness} loading={loading} error={error} />
  if (consistencySelected) return <DataConsistencyView data={consistency} loading={loading} error={error} onRefresh={refreshConsistency} filters={eventFilters} onFilters={setEventFilters} />

  return (
    <Page
      title="Amministrazione"
      subtitle="Quadro amministrativo reale per utenti, profili, audit, sicurezza e moduli protetti."
      actions={
        <>
          <ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>
          <ButtonLink href="/profili" tone="primary">Apri profili</ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento amministrazione" message="Lettura degli archivi amministrativi in corso." /> : null}
      {!loading && error ? (
        <EmptyState title="Amministrazione non disponibile" message={error} action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>} />
      ) : null}
      {!loading && !error && !hasData ? (
        <EmptyState
          title="Nessun dato amministrativo disponibile"
          message="Il centro amministrativo non ha ricevuto dati visualizzabili dagli archivi."
          action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-adminhub-banner" aria-label="Quadro amministrativo operativo">
            <strong>Regia amministrativa operativa</strong>
            <span>Utenti, profili, audit e backup sono collegamenti operativi; le impostazioni sensibili restano presidiate.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-adminhub-kpis" aria-label="Indicatori amministrazione">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={formatValue(metric.value)}
                note={metric.note}
                href={metricHrefs[metric.id]}
                actionLabel="Apri nel contesto"
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <SecurityPanel data={data} />
          <Panel title="Moduli amministrativi" subtitle={`${data.operational_routes.length} funzioni operative`}>
            <ModuleList modules={data.operational_routes} />
          </Panel>
          <Panel title="Impostazioni presidiate" subtitle="Percorsi mantenuti sotto controllo amministrativo">
            <ModuleList modules={data.legacy_routes} legacy />
          </Panel>
          <section className="iu-adminhub-grid" aria-label="Sezioni amministrazione">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind === 'roles' ? 'Utenti per ruolo' : section.kind === 'security' ? 'Stato degli account' : 'Permessi per ruolo'} key={section.id}>
                {section.items.length ? (
                  <div className="iu-adminhub-list">
                    {section.items.map((item) => (
                      <ButtonLink className="iu-adminhub-list__item" tone="neutral" aria-label={`Consulta ${item.label}`} href={section.kind === 'roles' ? `/utenti?ruolo=${encodeURIComponent(item.id.replace(/^ruolo-/, ''))}` : section.kind === 'security' ? `/utenti?stato=${encodeURIComponent(item.id === 'non-attivi' ? 'disabilitati' : item.id)}` : `/profili?vista=permessi&q=${encodeURIComponent(item.note)}`} key={item.id}>
                        <span>{item.label}</span>
                        <strong>{formatValue(item.value)}</strong>
                        {item.note ? <small>{item.note}</small> : null}
                      </ButtonLink>
                    ))}
                  </div>
                ) : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Collegamenti operativi">
            <div className="iu-adminhub-actions">
              {data.actions.map((action) => (
                <ButtonLink href={action.href} tone={buttonTone(action.tone)} key={action.id}>
                  <ExternalLink size={15} />
                  {action.label}
                </ButtonLink>
              ))}
            </div>
          </Panel>
          <ContractPanel data={data} />
        </>
      ) : null}
    </Page>
  )
}
