import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { BookOpen, Copy, ExternalLink, Search, X } from 'lucide-react'
import { ensureJson } from '../api/client'
import { matchesCatalogueAct } from './codiciLeggiSearch'
import './EditorNormativaPanel.css'

/**
 * Consultazione della normativa accanto all'atto in redazione (richiesta dell'avvocato del 01/11/2026).
 *
 * Legge solo l'archivio locale dei codici e delle leggi (lo stesso di «Codici e leggi», con data di
 * consolidamento e fonte ufficiale): nessun testo è generato o riassunto. La citazione si copia, non
 * entra nell'atto da sola, perché la scelta del riferimento resta dell'avvocato.
 */
type Act = { key?: string; id: number; title: string; label: string; category: string; articles: number; updated_at: string; materia?: string; tipo?: string }
type Article = { id: number; number: string; title: string; act_title: string }
type FullArticle = Article & { text: string; act_label: string; updated_at: string; source_url: string; source_label?: string; only_heading?: boolean; consolidated_at?: string }

const base = '/api/v1/ui/ricerca-legale/normativa'

export function citazione(articolo: Pick<FullArticle, 'number' | 'act_label' | 'act_title'>): string {
  return `art. ${articolo.number} ${articolo.act_label || articolo.act_title}`.trim()
}

function dataIt(value = ''): string {
  return /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10).split('-').reverse().join('/') : ''
}

export function EditorNormativaPanel({ onClose }: { onClose: () => void }) {
  const [acts, setActs] = useState<Act[]>([])
  const [filtroAtto, setFiltroAtto] = useState('')
  const [atto, setAtto] = useState('')
  const [articolo, setArticolo] = useState('')
  const [parole, setParole] = useState('')
  const [risultati, setRisultati] = useState<Article[] | null>(null)
  const [scelto, setScelto] = useState<FullArticle | null>(null)
  const [occupato, setOccupato] = useState(false)
  const [errore, setErrore] = useState('')
  const [copiato, setCopiato] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    ensureJson<{ items: Act[] }>(`${base}/atti`, { signal: controller.signal })
      .then((data) => setActs(data.items || []))
      .catch((e) => { if (!controller.signal.aborted) setErrore(e?.status === 403 ? 'Non hai il permesso per consultare le fonti.' : 'Archivio dei codici e delle leggi non disponibile.') })
    return () => controller.abort()
  }, [])

  const attiVisibili = useMemo(() => (filtroAtto ? acts.filter((a) => matchesCatalogueAct(a, filtroAtto)) : acts).slice(0, 60), [acts, filtroAtto])

  async function cerca(event: FormEvent) {
    event.preventDefault()
    if (!atto && !articolo.trim() && !parole.trim()) { setErrore('Indica un codice o una legge, un articolo o alcune parole.'); return }
    setOccupato(true); setErrore(''); setScelto(null)
    try {
      const params = new URLSearchParams({ act: atto, article: articolo.trim(), q: parole.trim(), offset: '0' })
      const data = await ensureJson<{ items: Article[] }>(`${base}/articoli?${params}`)
      setRisultati(data.items || [])
      if (data.items?.length === 1) await apri(data.items[0].id)
    } catch {
      setRisultati([]); setErrore('Ricerca non riuscita. Controlla il numero dell’articolo e riprova.')
    } finally { setOccupato(false) }
  }

  async function apri(id: number) {
    setOccupato(true); setErrore('')
    try {
      const data = await ensureJson<{ item: FullArticle }>(`${base}/articoli/${id}`)
      setScelto(data.item)
    } catch { setErrore('Il testo non è disponibile. Riprova ad aprire l’articolo.') } finally { setOccupato(false) }
  }

  async function copia(testo: string, cosa: string) {
    try { await navigator.clipboard.writeText(testo); setCopiato(cosa) } catch { setCopiato(''); setErrore('Copia non consentita dal browser: seleziona il testo e copialo a mano.') }
  }

  return (
    <aside className="iu-normativa-panel" aria-label="Normativa">
      <header>
        <strong><BookOpen size={15}/> Normativa</strong>
        <button type="button" aria-label="Chiudi la normativa" onClick={onClose}><X size={15}/></button>
      </header>
      <form className="iu-normativa-panel__form" onSubmit={cerca}>
        <label><span>Codice o legge</span>
          <input value={filtroAtto} placeholder="es. c.c., c.p.c., 53/1994" onChange={(e) => setFiltroAtto(e.target.value)}/>
        </label>
        <select aria-label="Atto normativo" value={atto} onChange={(e) => setAtto(e.target.value)}>
          <option value="">Tutti i codici e le leggi</option>
          {attiVisibili.map((a) => <option key={a.id} value={String(a.id)}>{a.label || a.title}</option>)}
        </select>
        <div className="iu-normativa-panel__row">
          <label><span>Articolo</span><input value={articolo} inputMode="text" placeholder="es. 2043" onChange={(e) => setArticolo(e.target.value)}/></label>
          <label><span>Parole</span><input value={parole} placeholder="es. danno ingiusto" onChange={(e) => setParole(e.target.value)}/></label>
        </div>
        <button type="submit" disabled={occupato}><Search size={14}/> {occupato ? 'Ricerca…' : 'Cerca'}</button>
      </form>
      {errore ? <p className="iu-normativa-panel__errore" role="alert">{errore}</p> : null}
      {scelto ? (
        <article className="iu-normativa-panel__testo">
          <button type="button" className="iu-normativa-panel__indietro" onClick={() => setScelto(null)}>← Risultati</button>
          <h4>Art. {scelto.number} — {scelto.act_label || scelto.act_title}</h4>
          {scelto.title ? <p className="iu-normativa-panel__rubrica">{scelto.title}</p> : null}
          <p className="iu-normativa-panel__meta">
            {dataIt(scelto.consolidated_at || scelto.updated_at) ? `Testo aggiornato al ${dataIt(scelto.consolidated_at || scelto.updated_at)}` : 'Data di aggiornamento non indicata'}
            {scelto.source_url ? <> · <a href={scelto.source_url} target="_blank" rel="noopener noreferrer">{scelto.source_label || 'Fonte ufficiale'} <ExternalLink size={11}/></a></> : null}
          </p>
          {scelto.only_heading ? <p className="iu-normativa-panel__meta">Nell’archivio c’è solo la rubrica: consulta la fonte ufficiale.</p> : null}
          <div className="iu-normativa-panel__corpo">{scelto.text}</div>
          <div className="iu-normativa-panel__azioni">
            <button type="button" onClick={() => copia(citazione(scelto), 'citazione')}><Copy size={13}/> Copia citazione</button>
            <button type="button" onClick={() => copia(scelto.text, 'testo')} disabled={!scelto.text}><Copy size={13}/> Copia testo</button>
          </div>
          {copiato ? <p className="iu-normativa-panel__meta" role="status">{copiato === 'citazione' ? 'Citazione copiata' : 'Testo copiato'}: incollalo nell’atto dove serve.</p> : null}
        </article>
      ) : risultati ? (
        <div className="iu-normativa-panel__risultati">
          {risultati.length ? risultati.map((r) => (
            <button type="button" key={r.id} onClick={() => apri(r.id)}>
              <strong>Art. {r.number}</strong> <span>{r.act_title}</span>{r.title ? <small>{r.title}</small> : null}
            </button>
          )) : <p>Nessun articolo trovato nell’archivio.</p>}
        </div>
      ) : <p className="iu-normativa-panel__meta">Il testo resta accanto all’atto mentre scrivi: cerca per codice, articolo o parole.</p>}
    </aside>
  )
}
