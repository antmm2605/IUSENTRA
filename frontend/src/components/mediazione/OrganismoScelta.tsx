import { useEffect, useMemo, useState } from 'react'
import { ensureJson } from '../../lib/apiClient'
import { formatDateTimeIt } from '../../formatting'
import { ButtonLink } from '../../ui/Button'
import { ActionButton as Button } from './ActionButton'
import type { Organism, OrganismDetail, Procedure } from './types'
import { ControlloFonti } from './ControlloFonti'

export function OrganismoScelta({ base, value, change, acquire, busy, dirty }: {
  base: string; value: Procedure; change: (patch: Partial<Procedure>) => void
  acquire: (url: string) => void; busy: boolean; dirty: boolean
}) {
  const [items, setItems] = useState<Organism[]>([])
  const [detail, setDetail] = useState<OrganismDetail | null>(null)
  const [region, setRegion] = useState('')
  const [province, setProvince] = useState('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [detailBusy, setDetailBusy] = useState(false)
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    ensureJson<{ organismi: Organism[] }>(`${base}/organismi`, { signal: abort.signal })
      .then((r) => setItems(r.organismi)).catch(() => { if (!abort.signal.aborted) setError('Registro non disponibile. Riprova il caricamento.') })
    return () => abort.abort()
  }, [base, retry])
  useEffect(() => {
    const abort = new AbortController()
    setDetail((current) => current?.numero === value.organismo_numero ? current : null)
    setDetailBusy(Boolean(value.organismo_numero))
    setError('')
    if (value.organismo_numero) ensureJson<{ organismo: OrganismDetail }>(`${base}/organismi?numero=${encodeURIComponent(value.organismo_numero)}`, { signal: abort.signal })
      .then((r) => setDetail(r.organismo)).catch(() => { if (!abort.signal.aborted) setError('Sedi e risorse non disponibili. Riprova il caricamento.') })
      .finally(() => { if (!abort.signal.aborted) setDetailBusy(false) })
    return () => abort.abort()
  }, [base, value.organismo_numero, retry])
  const regions = useMemo(() => [...new Set(items.flatMap((o) => o.territori.map((t) => t.regione)).filter(Boolean))].sort(), [items])
  const provinces = useMemo(() => [...new Set(items.flatMap((o) => o.territori.filter((t) => !region || t.regione === region).map((t) => t.provincia)).filter(Boolean))].sort(), [items, region])
  const filtered = items.filter((o) => (!query || `${o.nome} ${o.numero}`.toLocaleLowerCase('it').includes(query.toLocaleLowerCase('it'))) && ((!region && !province) || o.territori.some((t) => (!region || region === t.regione) && (!province || province === t.provincia))))
  const selected = items.find((o) => o.numero === value.organismo_numero)
  const options = selected && !filtered.includes(selected) ? [selected, ...filtered] : filtered
  return <section aria-label="Organismo e modulistica" className="iu-mediazione-block">
    <h3>Organismo, sede e moduli</h3>
    <div className="iu-mediazione-grid">
      <label>Regione<select value={region} onChange={(e) => { setRegion(e.target.value); setProvince('') }}><option value="">Tutte le regioni</option>{regions.map((r) => <option key={r}>{r}</option>)}</select></label>
      <label>Provincia<select value={province} onChange={(e) => setProvince(e.target.value)}><option value="">Tutte le province</option>{provinces.map((p) => <option key={p}>{p}</option>)}</select></label>
      <label>Cerca organismo<input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Denominazione o numero di registro" /></label>
    </div>
    {error ? <p role="alert">{error} <Button onClick={() => setRetry(retry + 1)}>Riprova</Button></p> : !items.length ? <p role="status">Caricamento registro…</p> : <p>{filtered.length} organismi corrispondono ai filtri territoriali.</p>}
    <label>Organismo scelto<select value={value.organismo_numero} onChange={(e) => change({ organismo_numero: e.target.value, sede_id: '', modulo_ufficiale_documento: '', modulo_verificato: false, modulo_fonte: undefined })}>
      <option value="">Scegli un organismo</option>{options.map((o) => <option key={o.numero} value={o.numero}>{o.nome} — n. {o.numero}</option>)}
    </select></label>
    {detail ? <>
      <label>Sede del procedimento<select value={value.sede_id} onChange={(e) => change({ sede_id: e.target.value })}><option value="">Scegli la sede</option>{detail.sedi.map((o) => <option key={o.id} value={o.id}>{o.city} ({o.province}) — {o.address}{o.legal ? ' · sede legale' : ''}</option>)}</select></label>
      <div className="iu-mediazione-actions">{detail.sito ? <ButtonLink tone="neutral" href={detail.sito} target="_blank" rel="noopener noreferrer">Sito dell’organismo</ButtonLink> : null}<ButtonLink tone="neutral" href={`/ricerca-legale/mediazione?scheda=registro-mediazione-organismo-${detail.numero}`} target="_blank" rel="noopener noreferrer">Scheda nel registro</ButtonLink></div>
      <p>I moduli e le istruzioni sono quelli pubblicati dall’ente. Prima del deposito verifica che siano aggiornati e adatti al procedimento. Nessun dato della pratica viene inviato aprendo questi collegamenti.</p>
      {detail.risorse_verificate_il ? <p>Collegamenti rilevati il {formatDateTimeIt(detail.risorse_verificate_il)}.</p> : null}
      {detail.controllo_fonti ? <ControlloFonti value={detail.controllo_fonti} busy={detailBusy} reload={() => setRetry((current) => current + 1)} /> : null}
      {detail.risorse.length ? <ul className="iu-mediazione-resources">{detail.risorse.filter((r) => r.kind !== 'sedi').map((r) => <li key={r.url}>
        <a href={r.url} target="_blank" rel="noopener noreferrer">{r.label || r.kind}</a>
        {['istanza', 'modulistica', 'adesione', 'procura', 'privacy', 'proroga', 'proposta', 'verbale', 'incarico', 'regolamento', 'tariffe'].includes(r.kind) && /\.(?:pdf|docx?)(?:\?|$)/i.test(r.url) ? <Button disabled={busy || dirty || !value.id} title={dirty || !value.id ? 'Salva prima il procedimento per associare il modulo all’organismo scelto.' : undefined} onClick={() => acquire(r.url)}>Acquisisci modulo nel fascicolo</Button> : null}
      </li>)}</ul> : <p>Nessun collegamento a moduli rilevato per questo ente. Consulta il suo sito per verificare la modulistica richiesta.</p>}
    </> : value.organismo_numero ? <p role="status">Caricamento sedi e modulistica dell’organismo…</p> : null}
  </section>
}
