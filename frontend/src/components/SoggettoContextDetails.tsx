import type { SoggettoRow } from '../soggettiData'
import './SoggettoContextDetails.css'

export function SoggettoContextDetails({ item }: { item: SoggettoRow }) {
  return <section className="iu-sogg-context-details" aria-label="Dati e collegamenti del soggetto">
    <h2>Dati anagrafici e recapiti</h2>
    <dl>
      <div><dt>Identificativo</dt><dd>{item.identifier && item.identifier !== '-' ? item.identifier : 'Non presente'}</dd></div>
      <div><dt>Sede</dt><dd>{[item.city, item.province && `(${item.province})`].filter(Boolean).join(' ') || 'Non presente'}</dd></div>
      <div><dt>Telefono</dt><dd>{item.phone || 'Non presente'}</dd></div>
      <div><dt>Email</dt><dd>{item.email || 'Non presente'}</dd></div>
      <div><dt>PEC</dt><dd>{item.pec || 'Non presente'}</dd></div>
      {item.clientId ? <div><dt>Cliente collegato</dt><dd><a href={`/clienti/${encodeURIComponent(item.clientId)}`}>{item.clientName || 'Apri cliente'}</a></dd></div> : null}
    </dl>
    <h2>Fascicoli collegati</h2>
    {item.matterIds.length ? <ul>{item.matterIds.map((id, index) => <li key={id}>
      <a href={`/fascicoli/${encodeURIComponent(id)}`}>{item.matterRefs[index] || `Apri fascicolo ${index + 1}`}</a>
    </li>)}</ul> : <p>Nessun fascicolo collegato a questo soggetto.</p>}
    {item.missingFields.length ? <p role="status">Dati da verificare: {item.missingFields.join(', ')}.</p> : null}
  </section>
}