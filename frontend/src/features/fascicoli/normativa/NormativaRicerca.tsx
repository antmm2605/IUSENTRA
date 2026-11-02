import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ExternalLink, Search } from 'lucide-react'
import { cercaNormativa, leggiArticolo } from './normativaApi'
import type { ArticoloTrovato } from './types'

type Articolo = Awaited<ReturnType<typeof leggiArticolo>>['item']

function dataIt(value = ''): string {
  return /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10).split('-').reverse().join('/') : ''
}

/** Ricerca nell'archivio «Codici e leggi», limitata per impostazione alle materie della pratica. */
export function NormativaRicerca({ materie }: { materie: string[] }) {
  const [parole, setParole] = useState('')
  const [soloMaterie, setSoloMaterie] = useState(materie.length > 0)
  const [risultati, setRisultati] = useState<{ items: ArticoloTrovato[]; total: number } | null>(null)
  const [scelto, setScelto] = useState<Articolo | null>(null)
  const [errore, setErrore] = useState('')
  const [occupato, setOccupato] = useState(false)
  const controllo = useRef<AbortController | null>(null)
  useEffect(() => () => controllo.current?.abort(), [])

  async function cerca(event: FormEvent) {
    event.preventDefault()
    const testo = parole.trim()
    if (testo.length < 3) { setErrore('Scrivi almeno tre lettere.'); return }
    controllo.current?.abort()
    const corrente = new AbortController()
    controllo.current = corrente
    setOccupato(true); setErrore(''); setScelto(null)
    try {
      const data = await cercaNormativa(testo, materie, soloMaterie, corrente.signal)
      setRisultati({ items: data.items || [], total: data.total || 0 })
    } catch (error) {
      if (corrente.signal.aborted) return
      const status = (error as { status?: number })?.status
      setRisultati(null)
      setErrore(status === 403 ? 'Non hai il permesso per consultare le fonti.' : status === 503 ? 'L’archivio dei codici e delle leggi non è ancora disponibile.' : 'Ricerca non riuscita: riprova.')
    } finally { if (!corrente.signal.aborted) setOccupato(false) }
  }

  async function apri(id: number) {
    setErrore('')
    try { setScelto((await leggiArticolo(id)).item) } catch { setErrore('Il testo dell’articolo non è disponibile.') }
  }

  return (
    <section className="iu-fas-normativa__ricerca" aria-label="Cerca nella normativa">
      <form onSubmit={cerca}>
        <label className="iu-fas-normativa__campo">
          <span>Cerca nei codici e nelle leggi</span>
          <input type="search" value={parole} placeholder="es. termine per l’appello" onChange={(event) => setParole(event.target.value)}/>
        </label>
        <button type="submit" disabled={occupato}><Search size={14} aria-hidden="true"/> {occupato ? 'Ricerca…' : 'Cerca'}</button>
      </form>
      {materie.length ? (
        <label className="iu-fas-normativa__filtro">
          <input type="checkbox" checked={soloMaterie} onChange={(event) => setSoloMaterie(event.target.checked)}/>
          <span>Solo le materie della pratica: {materie.join(', ')}</span>
        </label>
      ) : null}
      {errore ? <p className="iu-fas-normativa__nota" role="alert">{errore}</p> : null}
      {scelto ? (
        <article className="iu-fas-normativa__articolo">
          <button type="button" className="iu-fas-normativa__espandi" onClick={() => setScelto(null)}>← Risultati</button>
          <strong>Art. {scelto.number} — {scelto.act_label || scelto.act_title}</strong>
          {scelto.title ? <span>{scelto.title}</span> : null}
          <small>
            {dataIt(scelto.consolidated_at || scelto.updated_at) ? `Testo dall’archivio Normattiva di IUSENTRA, versione al ${dataIt(scelto.consolidated_at || scelto.updated_at)}` : 'Testo dall’archivio Normattiva di IUSENTRA'}
            {scelto.source_url ? <> · <a href={scelto.source_url} target="_blank" rel="noopener noreferrer">{scelto.source_label || 'Fonte ufficiale'} <ExternalLink size={11} aria-hidden="true"/></a></> : null}
          </small>
          {scelto.only_heading ? <p className="iu-fas-normativa__nota">Nell’archivio c’è solo la rubrica: consulta la fonte ufficiale.</p> : null}
          <div className="iu-fas-normativa__corpo">{scelto.text}</div>
        </article>
      ) : risultati ? (
        <div className="iu-fas-normativa__risultati" aria-live="polite">
          <small>{risultati.total === 1 ? '1 articolo trovato' : risultati.total ? `${risultati.total} articoli trovati${risultati.total > risultati.items.length ? `, primi ${risultati.items.length}` : ''}` : 'Nessun articolo trovato nell’archivio.'}</small>
          {risultati.items.map((articolo) => (
            <button type="button" key={articolo.id} onClick={() => apri(articolo.id)}>
              <strong>Art. {articolo.number}</strong> <span>{articolo.act_title}</span>{articolo.title ? <small>{articolo.title}</small> : null}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  )
}
