import { useState, type FormEvent } from 'react'
import { ExternalLink, Search } from 'lucide-react'
import { prassiQueryString, testoSuRichiestaHref, type PrassiVoce, type SentenzaAmministrativa } from './prassiData'
import './PrassiETestiAmministrativi.css'

// Ricerca nel testo integrale di circolari e risoluzioni dell'Agenzia delle Entrate, circolari e messaggi dell'INPS
// e sentenze del Consiglio di Stato, del CGA e dei TAR (archivi acquisiti dalle fonti ufficiali in sfondo); una
// sentenza per estremi si apre subito, anche se il suo testo non è ancora in archivio.
export function PrassiETestiAmministrativi() {
  const [domanda, setDomanda] = useState('')
  const [fonte, setFonte] = useState('')
  const [prassi, setPrassi] = useState<PrassiVoce[]>([])
  const [sentenze, setSentenze] = useState<SentenzaAmministrativa[]>([])
  const [stato, setStato] = useState('')
  const [organo, setOrgano] = useState('Consiglio di Stato')
  const [numero, setNumero] = useState('')
  const [anno, setAnno] = useState('')
  const estremiCompleti = /^\d{1,6}$/.test(numero.trim()) && /^\d{4}$/.test(anno.trim()) && organo.trim().length > 1

  const cerca = async (evento: FormEvent) => {
    evento.preventDefault()
    if (domanda.trim().length < 3) { setStato('Scrivi almeno tre lettere.'); return }
    setStato('Ricerca in corso…')
    try {
      const [p, g] = await Promise.all([
        fonte === 'ga' ? Promise.resolve({ items: [] }) : fetch(`/api/v1/ui/prassi${prassiQueryString(domanda, fonte)}`, { credentials: 'same-origin' }).then((r) => r.json()),
        fonte && fonte !== 'ga' ? Promise.resolve({ items: [] }) : fetch(`/api/v1/ui/giustizia-amministrativa/testi${prassiQueryString(domanda, '')}`, { credentials: 'same-origin' }).then((r) => r.json()),
      ])
      setPrassi(Array.isArray(p.items) ? p.items : [])
      setSentenze(Array.isArray(g.items) ? g.items : [])
      setStato((p.items?.length || 0) + (g.items?.length || 0) ? '' : (p.message || g.message || 'Nessun documento trovato con queste parole.'))
    } catch {
      setStato('Ricerca non disponibile in questo momento.')
    }
  }

  return (
    <section className="iu-prassi iu-od-source-card" aria-label="Prassi e sentenze amministrative: ricerca nel testo">
      <h2>Prassi e sentenze amministrative</h2>
      <p>Circolari e risoluzioni dell’Agenzia delle Entrate, circolari e messaggi dell’INPS, sentenze del Consiglio di Stato, del CGA e dei TAR: ricerca nel testo integrale preso dalle fonti ufficiali.</p>
      <form className="iu-prassi__form" onSubmit={cerca}>
        <input value={domanda} onChange={(e) => setDomanda(e.currentTarget.value)} placeholder="Parole o frase fra virgolette" aria-label="Parole da cercare" />
        <select value={fonte} onChange={(e) => setFonte(e.currentTarget.value)} aria-label="Fonte">
          <option value="">Tutte le fonti</option>
          <option value="Agenzia delle Entrate">Agenzia delle Entrate</option>
          <option value="INPS">INPS</option>
          <option value="ga">Consiglio di Stato, CGA e TAR</option>
        </select>
        <button type="submit"><Search size={14} /> Cerca</button>
      </form>
      <form className="iu-prassi__form" aria-label="Apri una sentenza amministrativa per numero e anno" onSubmit={(e) => {
        e.preventDefault()
        if (estremiCompleti) window.open(testoSuRichiestaHref(organo, numero, anno), '_blank', 'noopener')
      }}>
        <input list="iu-prassi-organi" value={organo} onChange={(e) => setOrgano(e.currentTarget.value)} aria-label="Organo (es. TAR Lazio)" />
        <datalist id="iu-prassi-organi">
          <option value="Consiglio di Stato" /><option value="CGA" /><option value="TAR Lazio" /><option value="TAR Calabria" />
          <option value="TAR Reggio Calabria" /><option value="TAR Veneto" />
        </datalist>
        <input value={numero} onChange={(e) => setNumero(e.currentTarget.value)} inputMode="numeric" placeholder="Numero" aria-label="Numero della sentenza" />
        <input value={anno} onChange={(e) => setAnno(e.currentTarget.value)} inputMode="numeric" placeholder="Anno (aaaa)" aria-label="Anno della sentenza" />
        <button type="submit" disabled={!estremiCompleti}><ExternalLink size={14} /> Apri il testo</button>
      </form>
      {stato ? <p role="status">{stato}</p> : null}
      {prassi.length ? <ul className="iu-prassi__elenco">{prassi.map((v) => (
        <li key={v.id}><strong>{v.ente} · {v.tipo} n. {v.numero} del {v.data.split('-').reverse().join('/')}</strong>
          <span>{v.oggetto}</span>{v.brano ? <small>{v.brano}</small> : null}
          <a href={v.url} target="_blank" rel="noreferrer">Fonte ufficiale <ExternalLink size={12} /></a></li>
      ))}</ul> : null}
      {sentenze.length ? <ul className="iu-prassi__elenco">{sentenze.map((s) => (
        <li key={s.id}><strong>{s.nome_sede} · {s.tipo.toLowerCase()} n. {Number(s.numero.slice(4))}/{s.anno}{s.pubblicato_il ? ` (pubbl. ${s.pubblicato_il})` : ''}</strong>
          <span>{s.oggetto}</span>{s.brano ? <small>{s.brano}</small> : null}
          <a href={s.url} target="_blank" rel="noreferrer">Testo ufficiale <ExternalLink size={12} /></a></li>
      ))}</ul> : null}
    </section>
  )
}

export default PrassiETestiAmministrativi
