import { useEffect, useState } from 'react'
import { ExternalLink, Globe2, RefreshCw, X } from 'lucide-react'
import type { LegalIntelligenceRecord } from '../legalIntelligenceData'
import { ensureJson } from '../lib/apiClient'
import { mediazioneWebsite } from '../lib/mediazioneWebsite'
import { formatDateTimeIt } from '../formatting'
import { Button, ButtonLink } from '../ui/Button'
import './MediazioneOrganismoDetail.css'

type Office = { legal: boolean; address: string; city: string; postal_code: string; province: string; region: string; phone: string; email: string; pec: string }
type Detail = { available: boolean; offices?: Office[]; checked_at?: string; source_url?: string }

export function MediazioneOrganismoDetail({ record, region, province, onClose }: { record: LegalIntelligenceRecord; region: string; province: string; onClose: () => void }) {
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  const [all, setAll] = useState(false)
  useEffect(() => setAll(false), [record.id, region, province])
  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(false)
    if (record.registryKind !== 'organismo') return () => controller.abort()
    ensureJson<Detail>(`/api/v1/ui/legal-intelligence/mediazione/organismi/${encodeURIComponent(record.registryNumber)}/sedi`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setData(value) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [record.registryNumber, record.registryKind, retry])
  const website = mediazioneWebsite(record.website)
  const offices = (data?.offices || []).filter((o) => all || ((!region || o.region === region) && (!province || o.province === province)))
  const fields = [
    ['N. registro', record.registryNumber], ['Sezione', record.registrySection],
    ['Natura', record.organismoType], ['Stato nel registro', record.stateLabel],
    ['Codice fiscale', record.taxCode], ['Partita IVA', record.vatNumber], ['Email', record.email],
  ]
  return <section className="iu-med-detail" aria-label={`Scheda ${record.title}`}>
    <h3>{record.title}</h3>
    <dl className="iu-med-detail__facts">{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Non indicato nel registro'}</dd></div>)}</dl>
    <div className="iu-med-detail__actions">
      {website ? <ButtonLink href={website} target="_blank" rel="noopener noreferrer" tone="primary"><Globe2 size={16} />Apri sito web</ButtonLink> : null}
      {record.sourceHref ? <ButtonLink href={record.sourceHref} target="_blank" rel="noopener noreferrer" tone="neutral"><ExternalLink size={16} />Registro ministeriale</ButtonLink> : null}
    </div>
    {record.registryKind === 'organismo' ? <div className="iu-med-detail__offices">
      <div className="iu-med-detail__actions">
        <h4>Sedi dell'organismo</h4>
        <Button tone="neutral" disabled={!data && !error} onClick={() => setRetry(retry + 1)}><RefreshCw size={16} />Rileggi sedi</Button>
      </div>
      {error ? <p role="alert">Non è stato possibile caricare le sedi. <Button tone="neutral" onClick={() => setRetry(retry + 1)}>Riprova</Button></p>
        : !data ? <p role="status">Caricamento sedi…</p>
        : !data.available ? <p>Sedi non ancora acquisite dal registro ministeriale.</p>
        : <>
          <p>{offices.length} {offices.length === 1 ? 'sede mostrata' : 'sedi mostrate'} su {data.offices?.length}. Consultazione del {formatDateTimeIt(data.checked_at)}.</p>
          {(region || province) && !all && offices.length < (data.offices?.length || 0) ? <Button tone="neutral" onClick={() => setAll(true)}>Mostra tutte le sedi dell'organismo</Button> : null}
          <ul className="iu-med-detail__office-list">{offices.map((office, index) => <li key={index}>
            <strong>{office.city} ({office.province}){office.legal ? ', sede legale' : ''}</strong>
            <span>{office.address}, {office.postal_code} · {office.region}</span>
            {office.phone ? <span>Telefono: {office.phone}</span> : null}
            {office.email ? <span>Email: {office.email}</span> : null}
            {office.pec ? <span>PEC: {office.pec}</span> : null}
          </li>)}</ul>
          {data.source_url ? <a href={data.source_url} target="_blank" rel="noopener noreferrer">Verifica le sedi nel registro ministeriale</a> : null}
        </>}
    </div> : null}
    <footer className="iu-med-detail__footer"><Button tone="neutral" onClick={onClose}><X size={16} />Chiudi questa scheda</Button></footer>
  </section>
}
