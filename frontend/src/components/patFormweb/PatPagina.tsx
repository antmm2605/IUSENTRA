import { useEffect, useState, type ReactNode } from 'react'
import { ArrowRight, ExternalLink, FileText, Plus, Wifi, WifiOff } from 'lucide-react'
import { ensureJson } from '../../lib/apiClient'
import { Badge } from '../dashboard'
import { patApi } from './patApi'
import type { Connessione } from './types'
import './patFormweb.css'

type Riga = {
  id: string
  titolo: string
  numero: string
  cliente: string
  sede: string
  nrg: string
  tipoRicorso: string
  mancanti: string[]
  ultimoDeposito: { tipo: string; stato: string; quando: string } | null
  link: string
}
type Panoramica = {
  ok: boolean
  fascicoli: Riga[]
  totali: { fascicoli: number; daCompletare: number; inviati: number; depositati: number; rifiutati: number }
  depositi: Array<{ id: string; nome: string; link: string }>
  linkPortale: string
}

/**
 * La pagina /pat: i fascicoli amministrativi con lo stato del deposito Formweb e l'accesso rapido al Portale
 * dell'Avvocato. Il modulo PDF ministeriale per la PEC resta disponibile come canale residuale.
 */
export function PatPagina({ residuale }: { residuale: ReactNode }) {
  const [dati, setDati] = useState<Panoramica | null>(null)
  const [connessione, setConnessione] = useState<Connessione | null>(null)
  const [errore, setErrore] = useState('')
  const [pec, setPec] = useState(() => typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('modulo') === 'pec')

  useEffect(() => {
    const abort = new AbortController()
    ensureJson<Panoramica>('/api/v1/ui/amministrativo/panoramica', { signal: abort.signal }).then(setDati)
      .catch((e) => { if (!abort.signal.aborted) setErrore(e instanceof Error ? e.message : 'Elenco non disponibile.') })
    patApi.connessione(abort.signal).then(setConnessione).catch(() => undefined)
    return () => abort.abort()
  }, [])

  return (
    <div className="iu-pat iu-pat-pagina">
      <header className="iu-pat-testata">
        <div className="iu-pat-testata__dati">
          <strong>Processo amministrativo telematico</strong>
          <span>Prepari nel fascicolo, depositi dal Formweb del Portale dell’Avvocato (SPID, CIE o CNS), IUSENTRA verifica il riepilogo.</span>
        </div>
        <div className="iu-pat-testata__stati">
          {connessione ? <Badge tone={connessione.raggiungibile ? 'success' : 'danger'}>{connessione.raggiungibile ? <Wifi size={13}/> : <WifiOff size={13}/>} {connessione.raggiungibile ? `Portale raggiungibile (${connessione.millisecondi} ms)` : 'Portale non raggiungibile'}</Badge> : null}
          {dati ? <Badge tone="info">{dati.totali.fascicoli} fascicoli</Badge> : null}
          {dati?.totali.daCompletare ? <Badge tone="warning">{dati.totali.daCompletare} da completare</Badge> : null}
          {dati?.totali.rifiutati ? <Badge tone="danger">{dati.totali.rifiutati} rifiutati</Badge> : null}
        </div>
        <a className="iu-pat-link" href={dati?.linkPortale || 'https://pe.prod.cloud.giustizia-amministrativa.it'} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Portale dell’Avvocato</a>
      </header>
      <div className="iu-pat-barra">
        <a className="iu-pat-primario" href="/fascicoli/nuovo?tipo=AMMINISTRATIVO"><Plus size={15}/> Nuovo fascicolo amministrativo</a>
        {(dati?.depositi || []).slice(0, 3).map((d) => <a key={d.id} href={d.link} target="_blank" rel="noreferrer"><ExternalLink size={14}/> {d.nome} nel Formweb</a>)}
      </div>
      {errore ? <p className="iu-pat-errore">{errore}</p> : null}
      {!dati && !errore ? <p role="status">Caricamento dei fascicoli amministrativi…</p> : null}
      {dati ? (
        <ul className="iu-pat-elenco">
          {dati.fascicoli.map((r) => (
            <li key={r.id}>
              <div>
                <strong>{r.titolo}</strong>
                <span>{[r.numero, r.cliente, r.sede, r.nrg ? `NRG ${r.nrg}` : '', r.tipoRicorso].filter(Boolean).join(' · ')}</span>
                {r.mancanti.length ? <small className="iu-pat-testo-errore">Da indicare: {r.mancanti.join(', ')}</small> : <small className="iu-pat-testo-ok">Dati della bozza pronti</small>}
              </div>
              {r.ultimoDeposito ? <Badge tone={r.ultimoDeposito.stato === 'depositato' ? 'success' : r.ultimoDeposito.stato === 'rifiutato' ? 'danger' : 'info'}>{r.ultimoDeposito.tipo}: {r.ultimoDeposito.stato}</Badge> : null}
              <a className="iu-pat-primario" href={r.link}>Prepara il deposito <ArrowRight size={14}/></a>
            </li>
          ))}
          {!dati.fascicoli.length ? <li>Nessun fascicolo amministrativo aperto: creane uno con «Nuovo fascicolo amministrativo».</li> : null}
        </ul>
      ) : null}
      <details className="iu-pat-residuale" open={pec} onToggle={(e) => setPec((e.target as HTMLDetailsElement).open)}>
        <summary><FileText size={15}/> Modulo PDF ministeriale per il deposito via PEC (canale residuale)</summary>
        {pec ? residuale : null}
      </details>
    </div>
  )
}
