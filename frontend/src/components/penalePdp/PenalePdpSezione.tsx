import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ExternalLink, FileUp, Gavel, ListChecks, RefreshCw, Send } from 'lucide-react'
import { Badge } from '../dashboard'
import { penaleApi } from './penaleApi'
import { CasellaPec } from './CasellaPec'
import { DepositiElenco } from './DepositiElenco'
import { ImportaPdp } from './ImportaPdp'
import { NuovoDeposito } from './NuovoDeposito'
import { ProcedimentoPanel } from './ProcedimentoPanel'
import type { Quadro } from './types'
import './penalePdp.css'

type Scheda = 'deposito' | 'depositi' | 'procedimento' | 'importa'

/** Deposito penale telematico (PDP): prepara, controlla, registra; l'invio lo fa l'avvocato sul portale. */
export default function PenalePdpSezione({ fascicoloId, onDocumenti }: { fascicoloId: string; onDocumenti?: () => void }) {
  const [quadro, setQuadro] = useState<Quadro | null>(null)
  const [errore, setErrore] = useState('')
  const [scheda, setScheda] = useState<Scheda>('deposito')
  const [depositoAperto, setDepositoAperto] = useState('')

  const ricarica = useCallback(async (signal?: AbortSignal) => {
    try {
      setQuadro(await penaleApi.quadro(fascicoloId, signal))
      setErrore('')
    } catch (e) {
      if (!signal?.aborted) setErrore(e instanceof Error ? e.message : 'Deposito penale non disponibile.')
    }
  }, [fascicoloId])

  useEffect(() => {
    const abort = new AbortController()
    void ricarica(abort.signal)
    return () => abort.abort()
  }, [ricarica])

  if (errore) return <div className="iu-pdp" role="alert"><p className="iu-pdp-errore">{errore}</p><button type="button" onClick={() => void ricarica()}><RefreshCw size={14}/> Riprova</button></div>
  if (!quadro) return <div className="iu-pdp" role="status">Caricamento del procedimento penale…</div>

  const p = quadro.procedimento
  const registro = quadro.registri.find((r) => r.corrente) || quadro.registri[0]
  const inCorso = quadro.depositi.filter((d) => !d.definitivo && !['BOZZA', 'PRONTO'].includes(d.stato)).length
  const schede: Array<{ id: Scheda; etichetta: string; icona: ReactNode; conta?: number }> = [
    { id: 'deposito', etichetta: 'Nuovo deposito', icona: <Send size={15}/> },
    { id: 'depositi', etichetta: 'Depositi', icona: <ListChecks size={15}/>, conta: quadro.depositi.length },
    { id: 'procedimento', etichetta: 'Procedimento e soggetti', icona: <Gavel size={15}/>, conta: quadro.soggetti.length },
    { id: 'importa', etichetta: 'Importa dal PDP', icona: <FileUp size={15}/> },
  ]
  const salvato = (id: string) => { setDepositoAperto(id); setScheda('depositi'); void ricarica(); onDocumenti?.() }

  return (
    <div className="iu-pdp">
      <header className="iu-pdp-testata">
        <div className="iu-pdp-testata__dati">
          <strong>{registro ? registro.protocollo : 'Registro da indicare'}</strong>
          <span>{p.ufficioEtichetta || 'Ufficio da indicare'}{registro?.magistrato ? ` · ${registro.magistrato}` : ''}</span>
        </div>
        <div className="iu-pdp-testata__stati">
          <Badge tone={p.autorizzato ? 'success' : 'warning'}>{p.autorizzato ? 'Procedimento autorizzato' : 'Non ancora autorizzato'}</Badge>
          {quadro.canale ? <Badge tone={quadro.canale.obbligatorio ? 'info' : 'neutral'}>{quadro.canale.etichetta}</Badge> : null}
          {inCorso ? <Badge tone="warning">{inCorso} in lavorazione</Badge> : null}
        </div>
        <nav className="iu-pdp-testata__link" aria-label="Portali ministeriali">
          <a href={quadro.link.pdp} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Apri il PDP</a>
          <a href={quadro.link.avvisi} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Avvisi in cancelleria</a>
          <a href={quadro.link.accessoAtti}>Accesso agli atti e PEC</a>
        </nav>
      </header>
      {quadro.canale ? <p className="iu-pdp-nota">{quadro.canale.nota}</p> : null}
      {!p.autorizzato ? (
        <p className="iu-pdp-avviso">Finché il procedimento non è autorizzato il PDP accetta solo gli atti del menu «Depositi» (nomina, costituzioni, denuncia, querela…).
          Dopo l’accoglimento della nomina, o con «Aggiorna elenco» sul PDP, si sbloccano gli atti successivi.</p>
      ) : null}
      <CasellaPec />
      <div className="iu-pdp-schede" role="tablist" aria-label="Deposito penale">
        {schede.map((s) => (
          <button key={s.id} type="button" role="tab" aria-selected={scheda === s.id} className={scheda === s.id ? 'is-attiva' : ''} onClick={() => setScheda(s.id)}>
            {s.icona} {s.etichetta}{typeof s.conta === 'number' ? <span className="iu-pdp-conta">{s.conta}</span> : null}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {scheda === 'deposito' ? <NuovoDeposito fascicoloId={fascicoloId} quadro={quadro} onSalvato={salvato} onDocumenti={() => { void ricarica(); onDocumenti?.() }}/> : null}
        {scheda === 'depositi' ? <DepositiElenco fascicoloId={fascicoloId} quadro={quadro} aperto={depositoAperto} onAggiorna={() => void ricarica()} onNuovo={() => setScheda('deposito')}/> : null}
        {scheda === 'procedimento' ? <ProcedimentoPanel fascicoloId={fascicoloId} quadro={quadro} onAggiorna={() => void ricarica()}/> : null}
        {scheda === 'importa' ? <ImportaPdp fascicoloId={fascicoloId} onImportato={() => void ricarica()}/> : null}
      </div>
    </div>
  )
}
