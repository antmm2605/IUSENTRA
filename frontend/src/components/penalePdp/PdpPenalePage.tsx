import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Clock3, ExternalLink, FileSignature, Gavel, RefreshCw, Scale } from 'lucide-react'
import { penaleApi } from './penaleApi'
import { CasellaPec } from './CasellaPec'
import { CalendarioObblighi } from './CalendarioObblighi'
import { ProcedimentiPdp, type Filtro } from './ProcedimentiPdp'
import type { PanoramicaPdp } from './types'
import './penalePdp.css'

const FILTRI: Array<{ id: Filtro; etichetta: string }> = [
  { id: 'tutti', etichetta: 'Tutti' },
  { id: 'da-fare', etichetta: 'Da fare' },
  { id: 'attesa', etichetta: 'In attesa di esito' },
  { id: 'non-autorizzati', etichetta: 'Non autorizzati' },
]

/**
 * Pagina PDP Penale: il PDP è una maschera web per l'avvocato (CNS/CIE), senza servizi per i gestionali.
 * IUSENTRA elenca i procedimenti penali, lo stato dei depositi preparati e la prossima azione.
 */
export default function PdpPenalePage() {
  const [dati, setDati] = useState<PanoramicaPdp | null>(null)
  const [errore, setErrore] = useState('')
  const [filtro, setFiltro] = useState<Filtro>('tutti')
  const [cerca, setCerca] = useState('')

  const carica = useCallback(async (signal?: AbortSignal) => {
    try { setDati(await penaleApi.panoramica(signal)); setErrore('') } catch (e) {
      if (!signal?.aborted) setErrore(e instanceof Error ? e.message : 'Depositi penali non disponibili.')
    }
  }, [])
  useEffect(() => { const a = new AbortController(); void carica(a.signal); return () => a.abort() }, [carica])

  const conteggi = useMemo(() => ({
    'da-fare': dati?.procedimenti.filter((p) => ['RIFARE', 'INVIARE', 'COMPLETARE', 'REGISTRO', 'NOMINA'].includes(p.azione.codice)).length ?? 0,
    attesa: dati?.procedimenti.filter((p) => p.azione.codice === 'ESITO').length ?? 0,
    'non-autorizzati': dati?.totali.nonAutorizzati ?? 0,
    tutti: dati?.totali.procedimenti ?? 0,
  }), [dati])

  const t = dati?.totali
  const tessere = t ? [
    { etichetta: 'Procedimenti penali', valore: t.procedimenti, icona: <Scale size={17}/> },
    { etichetta: 'Da rifare', valore: t.daRifare, icona: <AlertTriangle size={17}/>, tono: t.daRifare ? 'danger' : '' },
    { etichetta: 'In preparazione', valore: t.inPreparazione, icona: <FileSignature size={17}/> },
    { etichetta: 'In attesa di esito', valore: t.inAttesaEsito, icona: <Clock3 size={17}/> },
    { etichetta: 'Accolti', valore: t.accolti, icona: <CheckCircle2 size={17}/> },
  ] : []

  return (
    <main className="iu-content iu-pdp-pagina">
      <section className="iu-pdp-pagina__testa">
        <div>
          <span className="iu-pdp-pagina__occhiello"><Gavel size={15}/> Processo penale telematico</span>
          <h1>PDP Penale</h1>
          <p>IUSENTRA prepara e controlla il deposito nel fascicolo penale; l’invio lo fai tu sul Portale Deposito atti Penali con CNS o CIE,
            poi carichi la ricevuta e IUSENTRA la confronta con quanto preparato.</p>
        </div>
        <nav aria-label="Portali ministeriali">
          <a className="iu-pdp-pagina__primario" href={dati?.link.pdp || 'https://servizipst.giustizia.it/PST/PAVVP/'} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Apri il PDP</a>
          <a href={dati?.link.avvisi || 'https://servizipst.giustizia.it/PST/AvvisiPenale'} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Avvisi in cancelleria</a>
          <button type="button" onClick={() => void carica()}><RefreshCw size={14}/> Aggiorna</button>
        </nav>
      </section>
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
      {!dati && !errore ? <p className="iu-pdp-nota" role="status">Caricamento dei procedimenti penali…</p> : null}
      {dati ? (
        <>
          <section className="iu-pdp-pagina__tessere" aria-label="Riepilogo">
            {tessere.map((x) => (
              <div key={x.etichetta} className={x.tono ? `is-${x.tono}` : ''}>{x.icona}<strong>{x.valore}</strong><span>{x.etichetta}</span></div>
            ))}
          </section>
          <div className="iu-pdp"><CasellaPec/></div>
          <section className="iu-pdp-pagina__elenco">
            <header>
              <h2>Procedimenti</h2>
              <div className="iu-pdp-segmenti" role="tablist" aria-label="Filtra i procedimenti">
                {FILTRI.map((f) => (
                  <button key={f.id} type="button" role="tab" aria-selected={filtro === f.id} className={filtro === f.id ? 'is-attiva' : ''} onClick={() => setFiltro(f.id)}>
                    {f.etichetta} <span className="iu-pdp-conta">{conteggi[f.id]}</span>
                  </button>
                ))}
              </div>
              <input type="search" value={cerca} onChange={(e) => setCerca(e.target.value)} placeholder="Cerca fascicolo, cliente, registro…" aria-label="Cerca procedimento"/>
            </header>
            <ProcedimentiPdp procedimenti={dati.procedimenti} filtro={filtro} cerca={cerca}/>
          </section>
          <CalendarioObblighi calendario={dati.calendario} fonte={dati.fonteCalendario}/>
        </>
      ) : null}
    </main>
  )
}
