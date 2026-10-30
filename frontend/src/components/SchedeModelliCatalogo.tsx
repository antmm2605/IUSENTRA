import { useMemo, useState } from 'react'
import { Button } from '../ui/Button'
import { filtraModelli, filtriModelliVuoti, indicizzaModelli, type ModelloNorme } from '../schedeModelliCatalogo'

export function SchedeModelliCatalogo({ modelli, onSelect, busy }: { modelli: ModelloNorme[]; onSelect: (id: string) => void; busy: boolean }) {
  const [filtri, setFiltri] = useState(filtriModelliVuoti)
  const [pagina, setPagina] = useState(1)
  const index = useMemo(() => indicizzaModelli(modelli), [modelli])
  const risultati = useMemo(() => filtraModelli(index, filtri), [index, filtri])
  const opzioni = useMemo(() => ({
    materia: [...new Set(modelli.map(row => row.materia))].sort((a,b) => a.localeCompare(b,'it')),
    tipo: [...new Set(modelli.map(row => row.tipo))].sort((a,b) => a.localeCompare(b,'it')),
    provenienza: [...new Set(modelli.map(row => row.provenienza))].sort((a,b) => a.localeCompare(b,'it')),
  }), [modelli])
  const perPagina = 24
  const pagine = Math.max(1, Math.ceil(risultati.length / perPagina))
  const corrente = Math.min(pagina, pagine)
  const visibili = risultati.slice((corrente - 1) * perPagina, corrente * perPagina)
  const collegate = modelli.filter(row => row.stato_norme === 'associate').length
  function filtra(key: keyof typeof filtri, value: string) { setFiltri(previous => ({ ...previous, [key]: value })); setPagina(1) }
  return <section className="iu-od-source-card iu-sf-catalogo" aria-label="Catalogo completo dei modelli" aria-busy={busy}>
    <header><h2>Trova il modello d’atto</h2><p>{busy && !modelli.length ? 'Caricamento del catalogo completo…' : `${modelli.length.toLocaleString('it-IT')} voci del catalogo · cerca per titolo, codice, materia o riferimento normativo.`}</p></header>
    {modelli.length ? <div className="iu-sf-catalogo-stati" aria-label="Copertura delle associazioni normative">
      <Button tone="neutral" aria-pressed={!filtri.norme} onClick={() => filtra('norme','')}>Tutti: {modelli.length.toLocaleString('it-IT')}</Button>
      <Button tone="neutral" aria-pressed={filtri.norme === 'associate'} onClick={() => filtra('norme','associate')}>Norme collegate: {collegate.toLocaleString('it-IT')}</Button>
      <Button tone="neutral" aria-pressed={filtri.norme === 'da_associare'} onClick={() => filtra('norme','da_associare')}>Da associare: {(modelli.length-collegate).toLocaleString('it-IT')}</Button>
    </div> : null}
    <div className="iu-sf-catalogo-filtri">
      <label className="iu-sf-catalogo-query">Cerca modello<input type="search" value={filtri.testo} placeholder="Es. decreto ingiuntivo, sfratto, CIV_ORD_001, art163…" onChange={event => filtra('testo',event.target.value)} /></label>
      <label>Materia<select value={filtri.materia} onChange={event => filtra('materia',event.target.value)}><option value="">Tutte le materie</option>{opzioni.materia.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>Tipo di modello<select value={filtri.tipo} onChange={event => filtra('tipo',event.target.value)}><option value="">Tutti i tipi</option>{opzioni.tipo.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>Provenienza<select value={filtri.provenienza} onChange={event => filtra('provenienza',event.target.value)}><option value="">Tutte le provenienze</option>{opzioni.provenienza.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <Button tone="neutral" onClick={() => { setFiltri(filtriModelliVuoti); setPagina(1) }}>Azzera filtri</Button>
    </div>
    <p role="status">{busy ? 'Caricamento del catalogo…' : `${risultati.length.toLocaleString('it-IT')} modelli trovati · ${visibili.length ? (corrente-1)*perPagina+1 : 0}–${Math.min(corrente*perPagina,risultati.length)} visualizzati`}</p>
    {!busy && !risultati.length ? <p>Nessun modello corrisponde ai filtri. Prova meno parole o azzera i filtri.</p> : null}
    <ul className="iu-sf-catalogo-risultati">{visibili.map(row => <li key={row.id}>
      <div><small>{row.codice} · {row.provenienza}</small><h3><button type="button" className="iu-sf-modello-apri" onClick={() => onSelect(row.id)} aria-label={`Apri norme: ${row.titolo} · ${row.codice} · ${row.provenienza}`}>{row.titolo}</button></h3><p>{row.materia} · {row.tipo}</p><span>{row.stato_norme === 'associate' ? `${row.numero_riferimenti} riferimenti normativi collegati` : 'Normativa specifica da associare'}</span></div>
      {row.compilazione_url ? <a className="iu-sf-compila-modello" href={row.compilazione_url} aria-label={`Compila modello: ${row.titolo} · ${row.codice} · ${row.provenienza}`}>Compila modello</a> : null}
      <Button tone="neutral" onClick={() => onSelect(row.id)} aria-label={`Consulta norme: ${row.titolo} · ${row.codice} · ${row.provenienza}`}>Consulta norme</Button>
    </li>)}</ul>
    <nav aria-label="Pagine del catalogo modelli"><Button tone="neutral" disabled={corrente <= 1} onClick={() => setPagina(value => value-1)}>Modelli precedenti</Button><span>Pagina {corrente} di {pagine}</span><Button tone="neutral" disabled={corrente >= pagine} onClick={() => setPagina(value => value+1)}>Modelli successivi</Button></nav>
  </section>
}
