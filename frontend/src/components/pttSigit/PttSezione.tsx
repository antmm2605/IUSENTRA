import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { CalendarClock, ClipboardList, ExternalLink, FileText, Landmark, RefreshCw, Send, Wifi, WifiOff } from 'lucide-react'
import { Badge } from '../dashboard'
import { DepositiPtt } from './DepositiPtt'
import { DocumentiPtt } from './DocumentiPtt'
import { ProcedimentoPtt } from './ProcedimentoPtt'
import { SchedaNir } from './SchedaNir'
import { pttApi } from './pttApi'
import type { CatalogoPtt, Connessione, QuadroPtt } from './types'
import '../patFormweb/patFormweb.css'
import './pttSigit.css'

type Scheda = 'scheda' | 'procedimento' | 'documenti' | 'depositi'

/** Deposito tributario telematico: IUSENTRA prepara NIR, file, CUT e termini; l'avvocato valida e trasmette dal PTT. */
export default function PttSezione({ fascicoloId, onDocumenti }: { fascicoloId: string; onDocumenti?: () => void }) {
  const [quadro, setQuadro] = useState<QuadroPtt | null>(null)
  const [catalogo, setCatalogo] = useState<CatalogoPtt | null>(null)
  const [connessione, setConnessione] = useState<Connessione | null>(null)
  const [errore, setErrore] = useState('')
  const [tipo, setTipo] = useState('')
  const [scheda, setScheda] = useState<Scheda>('scheda')

  const ricarica = useCallback(async (signal?: AbortSignal) => {
    try {
      const nuovo = await pttApi.quadro(fascicoloId, tipo, signal)
      setQuadro(nuovo)
      if (!tipo) setTipo(nuovo.tipoSuggerito)
      setErrore('')
    } catch (e) {
      if (!signal?.aborted) setErrore(e instanceof Error ? e.message : 'Deposito tributario non disponibile.')
    }
  }, [fascicoloId, tipo])

  useEffect(() => {
    const abort = new AbortController()
    void ricarica(abort.signal)
    return () => abort.abort()
  }, [ricarica])

  useEffect(() => {
    const abort = new AbortController()
    pttApi.catalogo(abort.signal).then(setCatalogo).catch(() => undefined)
    pttApi.connessione(abort.signal).then(setConnessione).catch(() => undefined)
    return () => abort.abort()
  }, [])

  if (errore) return <div className="iu-pat" role="alert"><p className="iu-pat-errore">{errore}</p><button type="button" onClick={() => void ricarica()}><RefreshCw size={14}/> Riprova</button></div>
  if (!quadro) return <div className="iu-pat" role="status">Caricamento del deposito tributario…</div>

  const p = quadro.procedimento
  const corte = catalogo?.sedi.find((s) => s.codice === p.corte)
  const proposta = quadro.propostaCorte
  const tipoAttivo = tipo || quadro.tipoSuggerito
  const aggiorna = (nuovo: QuadroPtt) => setQuadro(nuovo)
  const vicino = quadro.termini.find((t) => t.giorni >= 0 && t.giorni <= 10)
  const schede: Array<{ id: Scheda; etichetta: string; icona: ReactNode; conta?: number }> = [
    { id: 'scheda', etichetta: 'Prepara il deposito', icona: <ClipboardList size={15}/> },
    { id: 'procedimento', etichetta: 'Nota di iscrizione', icona: <Landmark size={15}/> },
    { id: 'documenti', etichetta: 'Documenti', icona: <FileText size={15}/>, conta: quadro.documenti.filter((d) => d.ruolo !== 'escludi').length },
    { id: 'depositi', etichetta: 'Depositi', icona: <Send size={15}/>, conta: quadro.depositi.length },
  ]
  return (
    <div className="iu-pat iu-ptt">
      <header className="iu-pat-testata">
        <div className="iu-pat-testata__dati">
          <strong>{corte?.nome || 'Corte di giustizia tributaria da indicare'}{p.rg ? ` · RG ${p.rg}` : ''}</strong>
          <span>{quadro.parti.ricorrenti[0]?.denominazione || 'Ricorrente da indicare'} c/ {quadro.parti.resistenti.map((r) => r.denominazione).join(', ') || 'ente impositore da indicare'}{proposta ? ' · Corte proposta dall’ufficio o dall’ente: confermala nella nota di iscrizione' : ''}</span>
        </div>
        <div className="iu-pat-testata__stati">
          {connessione ? <Badge tone={connessione.raggiungibile ? 'success' : 'danger'}>{connessione.raggiungibile ? <Wifi size={13}/> : <WifiOff size={13}/>} {connessione.raggiungibile ? 'PTT raggiungibile' : 'PTT non raggiungibile'}</Badge> : null}
          {vicino ? <Badge tone={vicino.giorni <= 3 ? 'danger' : 'warning'}><CalendarClock size={13}/> {vicino.titolo.split(':')[0]}: {vicino.giorni === 0 ? 'oggi' : `${vicino.giorni} gg`}</Badge> : null}
          <Badge tone={quadro.scheda.pronto ? 'success' : 'warning'}>{quadro.scheda.pronto ? 'Pronto per il PTT' : `${quadro.scheda.mancanti.length} dati da indicare`}</Badge>
        </div>
        <a className="iu-pat-link" href={quadro.linkPortale} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Area riservata PTT</a>
      </header>
      <p className="iu-pat-nota">Dal 1° luglio 2019 ricorsi, appelli e atti successivi si depositano solo nel PTT del SIGIT (SPID, CIE o CNS). IUSENTRA prepara la nota di iscrizione a ruolo, i file, il CUT e i termini: validazione e trasmissione restano a te.</p>
      <div className="iu-pat-schede" role="tablist" aria-label="Deposito tributario">
        {schede.map((s) => (
          <button key={s.id} type="button" role="tab" aria-selected={scheda === s.id} className={scheda === s.id ? 'is-attiva' : ''} onClick={() => setScheda(s.id)}>
            {s.icona} {s.etichetta}{typeof s.conta === 'number' ? <span className="iu-pat-conta">{s.conta}</span> : null}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {scheda === 'scheda' ? <SchedaNir fascicoloId={fascicoloId} scheda={quadro.scheda} catalogo={catalogo} tipo={tipoAttivo} onTipo={setTipo} termini={quadro.termini}/> : null}
        {scheda === 'procedimento' ? <ProcedimentoPtt quadro={quadro} catalogo={catalogo} tipo={tipoAttivo} onSalva={async (dati) => aggiorna(await pttApi.procedimento(fascicoloId, tipoAttivo, dati))}/> : null}
        {scheda === 'documenti' ? <DocumentiPtt fascicoloId={fascicoloId} documenti={quadro.documenti} catalogo={catalogo} onSalva={async (id, dati) => aggiorna(await pttApi.documento(fascicoloId, tipoAttivo, id, dati))}/> : null}
        {scheda === 'depositi' ? <DepositiPtt fascicoloId={fascicoloId} tipo={tipoAttivo} catalogo={catalogo} depositi={quadro.depositi} onAggiorna={() => { void ricarica(); onDocumenti?.() }}/> : null}
      </div>
    </div>
  )
}
