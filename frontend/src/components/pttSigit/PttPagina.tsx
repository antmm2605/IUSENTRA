import { useEffect, useState } from 'react'
import { ArrowRight, CalendarClock, ExternalLink, FileSearch, LifeBuoy, Plus, Wifi, WifiOff } from 'lucide-react'
import { ensureJson } from '../../lib/apiClient'
import { Badge } from '../dashboard'
import { pttApi } from './pttApi'
import type { Connessione, Termine } from './types'
import '../patFormweb/patFormweb.css'
import './pttSigit.css'

type Riga = {
  id: string
  titolo: string
  numero: string
  cliente: string
  corte: string
  rg: string
  mancanti: string[]
  termine: Termine | null
  ultimoDeposito: { tipo: string; stato: string; quando: string } | null
  link: string
}
type Panoramica = {
  ok: boolean
  fascicoli: Riga[]
  totali: { fascicoli: number; daCompletare: number; termini: number; depositati: number; anomalie: number }
  portale: string
  telecontenzioso: string
  registrazione: string
  consultazione: string
  assistenza: string
  numeroVerde: string
}

const dataIt = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString('it-IT')

/**
 * La pagina /sigit: i fascicoli tributari con i termini in scadenza e lo stato della NIR, i collegamenti al PTT,
 * al Telecontenzioso e alla consultazione pubblica. Sotto restano acquisizione dal portale e controlli del canale.
 */
export function PttPagina() {
  const [dati, setDati] = useState<Panoramica | null>(null)
  const [connessione, setConnessione] = useState<Connessione | null>(null)
  const [errore, setErrore] = useState('')

  useEffect(() => {
    const abort = new AbortController()
    ensureJson<Panoramica>('/api/v1/ui/tributario/panoramica', { signal: abort.signal }).then(setDati)
      .catch((e) => { if (!abort.signal.aborted) setErrore(e instanceof Error ? e.message : 'Elenco non disponibile.') })
    pttApi.connessione(abort.signal).then(setConnessione).catch(() => undefined)
    return () => abort.abort()
  }, [])

  return (
    <div className="iu-pat iu-pat-pagina iu-ptt">
      <header className="iu-pat-testata">
        <div className="iu-pat-testata__dati">
          <strong>Processo tributario telematico</strong>
          <span>Prepari nel fascicolo nota di iscrizione, file, CUT e termini; depositi dal PTT del SIGIT con SPID, CIE o CNS.</span>
        </div>
        <div className="iu-pat-testata__stati">
          {connessione ? <Badge tone={connessione.raggiungibile ? 'success' : 'danger'}>{connessione.raggiungibile ? <Wifi size={13}/> : <WifiOff size={13}/>} {connessione.raggiungibile ? `PTT raggiungibile (${connessione.millisecondi} ms)` : 'PTT non raggiungibile'}</Badge> : null}
          {dati ? <Badge tone="info">{dati.totali.fascicoli} fascicoli</Badge> : null}
          {dati?.totali.termini ? <Badge tone="danger"><CalendarClock size={13}/> {dati.totali.termini} termini entro 30 giorni</Badge> : null}
          {dati?.totali.anomalie ? <Badge tone="warning">{dati.totali.anomalie} NIR con anomalie</Badge> : null}
        </div>
        <a className="iu-pat-link" href={dati?.portale || 'https://sigit.finanze.it/NIRWeb/login.jsp'} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Area riservata PTT</a>
      </header>
      <div className="iu-pat-barra">
        <a className="iu-pat-primario" href="/fascicoli/nuovo?tipo=TRIBUTARIO"><Plus size={15}/> Nuovo fascicolo tributario</a>
        {dati ? <a href={dati.telecontenzioso} target="_blank" rel="noreferrer"><FileSearch size={14}/> Telecontenzioso</a> : null}
        {dati ? <a href={dati.consultazione} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Consultazione pubblica e udienze</a> : null}
        {dati ? <a href={dati.registrazione} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Registrazione al PTT</a> : null}
        {dati ? <a href={dati.assistenza} target="_blank" rel="noreferrer"><LifeBuoy size={14}/> Assistenza · {dati.numeroVerde}</a> : null}
      </div>
      {errore ? <p className="iu-pat-errore">{errore}</p> : null}
      {!dati && !errore ? <p role="status">Caricamento dei fascicoli tributari…</p> : null}
      {dati ? (
        <ul className="iu-pat-elenco">
          {dati.fascicoli.map((r) => (
            <li key={r.id}>
              <div>
                <strong>{r.titolo}</strong>
                <span>{[r.numero, r.cliente, r.corte, r.rg ? `RG ${r.rg}` : ''].filter(Boolean).join(' · ')}</span>
                {r.termine ? <small className={r.termine.giorni <= 10 ? 'iu-pat-testo-errore' : ''}><CalendarClock size={12}/> {r.termine.titolo}: {dataIt(r.termine.scadenza)}{r.termine.giorni >= 0 ? ` (fra ${r.termine.giorni} giorni)` : ' (scaduto)'}</small> : null}
                {r.mancanti.length ? <small className="iu-pat-testo-errore">Da indicare: {r.mancanti.join(', ')}</small> : <small className="iu-pat-testo-ok">Dati della NIR pronti</small>}
              </div>
              {r.ultimoDeposito ? <Badge tone={r.ultimoDeposito.stato.includes('anomalia') || r.ultimoDeposito.stato === 'rigettata' ? 'warning' : r.ultimoDeposito.stato === 'depositata' || r.ultimoDeposito.stato === 'acquisita' ? 'success' : 'info'}>{r.ultimoDeposito.stato}</Badge> : null}
              <a className="iu-pat-primario" href={r.link}>Prepara il deposito <ArrowRight size={14}/></a>
            </li>
          ))}
          {!dati.fascicoli.length ? <li>Nessun fascicolo tributario: creane uno con «Nuovo fascicolo tributario».</li> : null}
        </ul>
      ) : null}
    </div>
  )
}
