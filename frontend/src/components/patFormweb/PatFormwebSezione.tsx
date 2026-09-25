import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ClipboardList, ExternalLink, FileText, Landmark, RefreshCw, ShieldCheck, UsersRound, Wifi, WifiOff } from 'lucide-react'
import { Badge } from '../dashboard'
import { patApi } from './patApi'
import { DocumentiPat, PartiPat } from './PartiDocumenti'
import { ProcedimentoPat } from './ProcedimentoPat'
import { RiepilogoDepositi } from './RiepilogoDepositi'
import { SchedaFormweb } from './SchedaFormweb'
import type { CatalogoPat, Connessione, QuadroPat } from './types'
import './patFormweb.css'

type Scheda = 'scheda' | 'procedimento' | 'parti' | 'documenti' | 'riepilogo'

/** Deposito amministrativo telematico: IUSENTRA prepara e verifica, l'avvocato compila e invia dal Formweb. */
export default function PatFormwebSezione({ fascicoloId, onDocumenti }: { fascicoloId: string; onDocumenti?: () => void }) {
  const [quadro, setQuadro] = useState<QuadroPat | null>(null)
  const [catalogo, setCatalogo] = useState<CatalogoPat | null>(null)
  const [connessione, setConnessione] = useState<Connessione | null>(null)
  const [errore, setErrore] = useState('')
  const [tipo, setTipo] = useState('ricorso')
  const [tipoScelto, setTipoScelto] = useState(false)
  const [scheda, setScheda] = useState<Scheda>('scheda')
  const [conferma, setConferma] = useState('')

  const ricarica = useCallback(async (signal?: AbortSignal) => {
    try {
      setQuadro(await patApi.quadro(fascicoloId, tipo, signal))
      setErrore('')
    } catch (e) {
      if (!signal?.aborted) setErrore(e instanceof Error ? e.message : 'Deposito amministrativo non disponibile.')
    }
  }, [fascicoloId, tipo])

  useEffect(() => {
    const abort = new AbortController()
    void ricarica(abort.signal)
    return () => abort.abort()
  }, [ricarica])

  useEffect(() => {
    // Con l'NRG già noto (anche letto dai documenti) il ricorso è depositato: si parte dai depositi successivi.
    if (!tipoScelto && quadro?.tipoSuggerito && quadro.tipoSuggerito !== tipo) setTipo(quadro.tipoSuggerito)
  }, [quadro?.tipoSuggerito, tipo, tipoScelto])

  useEffect(() => {
    const abort = new AbortController()
    patApi.catalogo(abort.signal).then(setCatalogo).catch(() => undefined)
    patApi.connessione(abort.signal).then(setConnessione).catch(() => undefined)
    return () => abort.abort()
  }, [])

  if (errore) return <div className="iu-pat" role="alert"><p className="iu-pat-errore">{errore}</p><button type="button" onClick={() => void ricarica()}><RefreshCw size={14}/> Riprova</button></div>
  if (!quadro) return <div className="iu-pat" role="status">Caricamento del deposito amministrativo…</div>

  const p = quadro.procedimento
  const sede = catalogo?.sedi.find((s) => s.codice === p.sede)?.descrizione || 'Sede da indicare'
  const tipoRicorso = quadro.tipiRicorso.find((t) => t.codice === p.tipoRicorso)?.descrizione
  const aggiorna = (nuovo: QuadroPat) => setQuadro(nuovo)
  const scegliTipo = (nuovo: string) => { setTipoScelto(true); setTipo(nuovo) }
  const letti = quadro.letti || {}
  const sedeLetta = letti.sede ? catalogo?.sedi.find((s) => s.codice === letti.sede?.valore)?.descrizione || letti.sede.valore : ''
  const fonti = Array.from(new Set([...(letti.nrg?.documenti || []), ...(letti.sede?.documenti || [])]))
  const confermaLetti = async () => {
    try {
      aggiorna(await patApi.procedimento(fascicoloId, tipo, { ...(letti.sede ? { sede: letti.sede.valore } : {}), ...(letti.nrg ? { nrg: letti.nrg.valore } : {}) }))
      setConferma('Dati confermati nel procedimento.')
    } catch (e) {
      setConferma(e instanceof Error ? e.message : 'Conferma non riuscita.')
    }
  }
  const schede: Array<{ id: Scheda; etichetta: string; icona: ReactNode; conta?: number }> = [
    { id: 'scheda', etichetta: 'Prepara il deposito', icona: <ClipboardList size={15}/> },
    { id: 'procedimento', etichetta: 'Procedimento', icona: <Landmark size={15}/> },
    { id: 'parti', etichetta: 'Parti', icona: <UsersRound size={15}/>, conta: quadro.parti.length },
    { id: 'documenti', etichetta: 'Documenti', icona: <FileText size={15}/>, conta: quadro.documenti.filter((d) => d.ruolo !== 'escludi').length },
    { id: 'riepilogo', etichetta: 'Verifica e depositi', icona: <ShieldCheck size={15}/>, conta: quadro.depositi.length },
  ]
  return (
    <div className="iu-pat">
      <header className="iu-pat-testata">
        <div className="iu-pat-testata__dati">
          <strong>{sede}{p.nrg ? ` · NRG ${p.nrg}` : ''}</strong>
          <span>{tipoRicorso || 'Tipo di ricorso da indicare'} · assistito {p.posizione || 'ricorrente'}</span>
        </div>
        <div className="iu-pat-testata__stati">
          {connessione ? <Badge tone={connessione.raggiungibile ? 'success' : 'danger'}>{connessione.raggiungibile ? <Wifi size={13}/> : <WifiOff size={13}/>} {connessione.raggiungibile ? 'Portale raggiungibile' : 'Portale non raggiungibile'}</Badge> : null}
          <Badge tone={quadro.scheda.pronto ? 'success' : 'warning'}>{quadro.scheda.pronto ? 'Pronto per il Formweb' : `${quadro.scheda.mancanti.length} dati da indicare`}</Badge>
        </div>
        <a className="iu-pat-link" href={quadro.linkPortale} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Portale dell’Avvocato</a>
      </header>
      {letti.nrg || letti.sede ? (
        <div className="iu-pat-avviso iu-pat-letti" role="status">
          <span>
            <strong>Letto dai documenti del fascicolo:</strong>{' '}
            {[sedeLetta, letti.nrg ? `NRG ${letti.nrg.valore} (R.G. ${letti.nrg.rg})` : ''].filter(Boolean).join(' · ')}
            {fonti.length ? <small> — da {fonti.map((f) => `«${f}»`).join(', ')}</small> : null}
          </span>
          <button type="button" className="iu-pat-primario" onClick={() => void confermaLetti()}>Conferma e usa</button>
        </div>
      ) : null}
      {conferma ? <p className="iu-pat-nota" role="status">{conferma}</p> : null}
      <p className="iu-pat-nota">Dal 1° febbraio 2026 il deposito si fa dal Formweb del Portale dell’Avvocato (SPID, CIE o CNS). IUSENTRA prepara dati, parti e file e controlla il riepilogo: l’invio resta a te.</p>
      <div className="iu-pat-schede" role="tablist" aria-label="Deposito amministrativo">
        {schede.map((s) => (
          <button key={s.id} type="button" role="tab" aria-selected={scheda === s.id} className={scheda === s.id ? 'is-attiva' : ''} onClick={() => setScheda(s.id)}>
            {s.icona} {s.etichetta}{typeof s.conta === 'number' ? <span className="iu-pat-conta">{s.conta}</span> : null}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {scheda === 'scheda' ? <SchedaFormweb fascicoloId={fascicoloId} scheda={quadro.scheda} catalogo={catalogo} tipo={tipo} onTipo={scegliTipo}/> : null}
        {scheda === 'procedimento' ? <ProcedimentoPat quadro={quadro} catalogo={catalogo} onSalva={async (dati) => aggiorna(await patApi.procedimento(fascicoloId, tipo, dati))}/> : null}
        {scheda === 'parti' ? <PartiPat fascicoloId={fascicoloId} parti={quadro.parti} onRuolo={async (id, ruolo) => aggiorna(await patApi.parte(fascicoloId, tipo, id, ruolo))}/> : null}
        {scheda === 'documenti' ? <DocumentiPat fascicoloId={fascicoloId} documenti={quadro.documenti} onSalva={async (id, ruolo, descr) => aggiorna(await patApi.documento(fascicoloId, tipo, id, ruolo, descr))}/> : null}
        {scheda === 'riepilogo' ? <RiepilogoDepositi fascicoloId={fascicoloId} tipo={tipo} tipi={catalogo?.depositi || []} depositi={quadro.depositi} onAggiorna={() => { void ricarica(); onDocumenti?.() }}/> : null}
      </div>
    </div>
  )
}
