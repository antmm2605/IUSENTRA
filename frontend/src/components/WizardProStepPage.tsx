import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, CalendarDays, Check, FolderOpen, Gavel, MapPin, Printer, Video } from 'lucide-react'
import { FloatingLex } from './FloatingLex'
import { PassoDocumenti, PassoEsito, PassoPartenza, PassoQuadro, PassoStrategia, type Azioni } from './PreparazioneUdienzaPassi'
import { inviaPreparazione } from './preparazioneUdienzaApi'
import type { SchedaUdienza } from './preparazioneUdienzaTipi'
import './WizardProPage.css'

function idDallIndirizzo(): { id: string; passo: number } {
  const trovato = window.location.pathname.match(/\/wizard-pro\/([^/]+)\/(?:step\/([1-5])|completo)/)
  return { id: decodeURIComponent(trovato?.[1] || ''), passo: trovato?.[2] ? Number(trovato[2]) : 5 }
}

/** Preparazione di una udienza: cinque passi in una sola pagina, con salvataggio immediato. */
export function WizardProStepPage({ sessionId, initialStep = 1, embedded = false }: { sessionId?: string; initialStep?: number; embedded?: boolean } = {}) {
  const [{ id, passo: passoIniziale }] = useState(() => sessionId ? { id: sessionId, passo: initialStep } : idDallIndirizzo())
  const [s, setS] = useState<SchedaUdienza | null>(null)
  const [passo, setPasso] = useState(passoIniziale)
  const [avviso, setAvviso] = useState<{ testo: string; ok: boolean } | null>(null)
  const [occupato, setOccupato] = useState(false)

  useEffect(() => {
    fetch(`/api/v1/ui/preparazione-udienza/${encodeURIComponent(id)}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((r) => r.json()).then((d: SchedaUdienza) => setS(d)).catch(() => setS({ ok: false, message: 'Preparazione non disponibile.' } as SchedaUdienza))
  }, [id])

  const vaiA = useCallback((n: number) => {
    setPasso(n)
    if (!embedded) {
      window.history.replaceState(window.history.state, '', `/wizard-pro/${encodeURIComponent(id)}/step/${n}`)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [id, embedded])

  const azione: Azioni['azione'] = useCallback(async (nome, corpo) => {
    // Risposta immediata sullo schermo; il server conferma o ripristina.
    setS((attuale) => {
      if (!attuale) return attuale
      if (nome === 'verifica') return { ...attuale, verifiche: attuale.verifiche.map((v) => (v.id === corpo.id ? { ...v, fatta: Boolean(corpo.fatta) } : v)) }
      if (nome === 'documento') return { ...attuale, documenti: attuale.documenti.map((d) => (d.indice === corpo.indice ? { ...d, stato: String(corpo.stato) } : d)) }
      if (nome === 'passo' && corpo.campi) return { ...attuale, campi: { ...attuale.campi, ...(corpo.campi as Record<string, string | boolean>) } }
      return attuale
    })
    setOccupato(true)
    const r = await inviaPreparazione(`/api/v1/ui/preparazione-udienza/${encodeURIComponent(id)}/${nome}`, corpo)
    setOccupato(false)
    if (r.dati) setS({ ...(r.dati as SchedaUdienza), puoModificare: s?.puoModificare })
    else if (!r.ok) {
      const ricarica = await fetch(`/api/v1/ui/preparazione-udienza/${encodeURIComponent(id)}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
      const dati = ricarica ? await ricarica.json().catch(() => null) as SchedaUdienza | null : null
      if (dati?.ok) setS(dati)
    }
    if (!r.ok || nome === 'esito') setAvviso({ testo: String(r.message || ''), ok: Boolean(r.ok) })
    return r
  }, [id, s?.puoModificare])

  const salvaCampi: Azioni['salvaCampi'] = useCallback(async (n, campi, conferma = false) => {
    const r = await azione('passo', { passo: n, campi, conferma })
    if (r.ok && conferma && n < 5) vaiA(n + 1)
  }, [azione, vaiA])

  if (!s) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina">Caricamento della preparazione…</p></main>
  if (!s.ok || !Array.isArray(s.passi) || !s.passi.length) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina is-errore" role="alert">{s.message || 'Preparazione non disponibile.'}</p></main>
  const attuale = s.passi.find((p) => p.n === passo) || s.passi[0]
  const a: Azioni = { salvaCampi, azione, occupato }
  const Corpo = [PassoQuadro, PassoDocumenti, PassoStrategia, PassoPartenza, PassoEsito][passo - 1]

  return (
    <main className="iu-content iu-pu iu-pu-sessione">
      <header className="iu-pu-scheda">
        <div className="iu-pu-scheda__titolo">
          <span className="iu-pu-kicker"><Gavel size={15}/> Preparazione udienza · {s.stato}</span>
          <h1>{s.titolo}</h1>
          <p className="iu-pu-quando"><CalendarDays size={16}/> {s.udienza.quando}</p>
          <p className="iu-pu-dove">
            {s.udienza.luogo ? <span><MapPin size={13}/> {s.udienza.luogo}</span> : null}
            {s.udienza.ufficio && s.udienza.ufficio !== s.udienza.luogo ? <span>{s.udienza.ufficio}</span> : null}
            {s.udienza.rg ? <span>R.G. {s.udienza.rg}</span> : null}
            {s.udienza.giudice ? <span>{s.udienza.giudice}</span> : null}
            {s.udienza.collegamento ? <a href={s.udienza.collegamento} target="_blank" rel="noreferrer"><Video size={13}/> Collegamento da remoto</a> : null}
          </p>
        </div>
        <div className="iu-pu-scheda__azioni">
          {s.causa.fascicolo?.href ? <a className="iu-pu-btn" href={s.causa.fascicolo.href}><FolderOpen size={14}/> Fascicolo</a> : null}
          <a className="iu-pu-btn" href={s.udienza.agendaHref}><CalendarDays size={14}/> Agenda</a>
          <button type="button" className="iu-pu-btn" onClick={() => window.print()}><Printer size={14}/> Stampa la scheda</button>
        </div>
      </header>

      {avviso ? <p className={`iu-pu-stato-pagina ${avviso.ok ? 'is-ok' : 'is-errore'}`} role="status">{avviso.testo}</p> : null}

      <div className="iu-pu-corpo">
        <nav className="iu-pu-passi" aria-label="Passi della preparazione">
          <ol>
            {s.passi.map((p) => (
              <li key={p.n}>
                <button type="button" className={`${p.n === passo ? 'is-attivo' : ''} ${p.fatto ? 'is-fatto' : ''}`} aria-current={p.n === passo ? 'step' : undefined} onClick={() => vaiA(p.n)}>
                  <i>{p.fatto ? <Check size={13}/> : p.n}</i><span><strong>{p.titolo}</strong><small>{p.descrizione}</small></span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <section className="iu-pu-contenuto" aria-label={attuale.titolo}>
          <header><h2>{attuale.n}. {attuale.titolo}</h2><p>{attuale.descrizione}</p></header>
          <Corpo key={`${passo}-${s.id}`} s={s} a={a}/>
          {passo < 5 && s.puoModificare ? (
            <footer className="iu-pu-piede">
              <span>{attuale.fatto ? 'Passo completato: puoi ancora modificarlo.' : 'Le modifiche si salvano da sole.'}</span>
              <button type="button" className="iu-pu-btn is-primario" disabled={occupato} onClick={() => void salvaCampi(passo, {}, true)}>
                {attuale.fatto ? 'Avanti' : 'Fatto, passo successivo'} <ArrowRight size={14}/>
              </button>
            </footer>
          ) : null}
        </section>
      </div>
      {!embedded ? <FloatingLex context="preparazione-udienza" title="Lex udienza" body="Legge fascicolo, termini e documenti dell'udienza e ti aiuta a preparare argomenti ed eccezioni."
        primaryHref="#lex" primaryLabel="Apri Lex" secondaryHref={s.causa.fascicolo?.href || '/fascicoli'} secondaryLabel="Fascicolo"/> : null}
    </main>
  )
}

export default WizardProStepPage
