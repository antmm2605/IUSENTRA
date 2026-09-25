import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, Trash2 } from 'lucide-react'
import { penaleApi } from './penaleApi'
import { EsitoControlli } from './EsitoControlli'
import { RicevutaPanel } from './RicevutaPanel'
import { SchedaPdp } from './SchedaPdp'
import { VerificaRicevutaPanel } from './VerificaRicevuta'
import type { Deposito, Quadro, SchedaPortale } from './types'

type Props = { fascicoloId: string; quadro: Quadro; deposito: Deposito; onAggiorna: () => void }

/** Dettaglio di un deposito: controlli, scheda da copiare nel PDP, ricevute e stato. */
export function DepositoDettaglio({ fascicoloId, quadro, deposito: d, onAggiorna }: Props) {
  const [scheda, setScheda] = useState<SchedaPortale | null>(null)
  const [errore, setErrore] = useState('')
  const [lavoro, setLavoro] = useState(false)
  useEffect(() => {
    let attivo = true
    penaleApi.dettaglio(fascicoloId, d.id).then((r) => { if (attivo) setScheda(r.scheda) }).catch(() => undefined)
    return () => { attivo = false }
  }, [fascicoloId, d.id, d.aggiornatoIl])
  const esegui = async (azione: () => Promise<unknown>) => {
    setLavoro(true); setErrore('')
    try { await azione(); onAggiorna() } catch (e) { setErrore(e instanceof Error ? e.message : 'Operazione non riuscita.') } finally { setLavoro(false) }
  }
  const inPreparazione = d.stato === 'BOZZA' || d.stato === 'PRONTO'
  const ricontrolla = () => esegui(() => penaleApi.prepara(fascicoloId, {
    atto: d.atto, ufficio: d.ufficio, soggetti: d.soggetti.map((s) => s.id || '').filter(Boolean),
    file: d.file.map((f) => ({ documentoId: f.documentoId, ruolo: f.ruolo, oggetto: f.oggetto, tipoAtto: f.tipoAtto })),
    dati: Object.fromEntries(Object.entries(d.dati).map(([k, v]) => [k, String(v ?? '')])), procuraSpeciale: Boolean(d.controlli.procuraSpeciale),
  }, d.id))
  return (
    <div className="iu-pdp-dettaglio">
      {d.motivazione ? <p className="iu-pdp-errore">Motivazione del rigetto: {d.motivazione}</p> : null}
      <VerificaRicevutaPanel verifica={d.verificaRicevuta}/>
      {d.controlli.esiti?.length ? <EsitoControlli controlli={d.controlli}/> : null}
      {inPreparazione && scheda ? <SchedaPdp scheda={scheda} linkPdp={quadro.link.pdp}/> : null}
      <div className="iu-pdp-azioni">
        {inPreparazione ? (
          <>
            <a className="iu-pdp-primario" href={quadro.link.pdp} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Apri il PDP e deposita</a>
            <button type="button" disabled={lavoro} onClick={() => void ricontrolla()}><RefreshCw size={14}/> Ricontrolla</button>
            <button type="button" disabled={lavoro} onClick={() => void esegui(() => penaleApi.elimina(fascicoloId, d.id))}><Trash2 size={14}/> Elimina bozza</button>
          </>
        ) : null}
        {!inPreparazione ? (
          <label className="iu-pdp-stato">Stato sul PDP
            <select value={d.stato} disabled={lavoro} onChange={(e) => void esegui(() => penaleApi.stato(fascicoloId, d.id, { stato: e.target.value }))}>
              {quadro.stati.filter((s) => !['BOZZA', 'PRONTO'].includes(s.codice)).map((s) => <option key={s.codice} value={s.codice} title={s.descrizione}>{s.etichetta}</option>)}
            </select>
          </label>
        ) : null}
      </div>
      <RicevutaPanel fascicoloId={fascicoloId} deposito={d} onRegistrata={onAggiorna}/>
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </div>
  )
}
