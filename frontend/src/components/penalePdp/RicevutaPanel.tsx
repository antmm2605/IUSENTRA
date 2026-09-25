import { useState, type FormEvent } from 'react'
import { FileCheck2, FileUp } from 'lucide-react'
import { penaleApi } from './penaleApi'
import type { Deposito } from './types'

/**
 * Ricevuta di deposito o di esito scaricata dal PDP: IUSENTRA legge identificativo, data, ufficio, procedimento,
 * atto, soggetti e allegati e li confronta con il deposito preparato (art. 87 co. 6-bis D.Lgs. 150/2022).
 */
export function RicevutaPanel({ fascicoloId, deposito, onRegistrata }: { fascicoloId: string; deposito: Deposito; onRegistrata: () => void }) {
  const [lavoro, setLavoro] = useState(false)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [nomeFile, setNomeFile] = useState('')
  const invia = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const form = evento.currentTarget
    setLavoro(true); setErrore(''); setMessaggio('')
    try {
      const esito = await penaleApi.ricevuta(fascicoloId, deposito.id, new FormData(form))
      setMessaggio(`Registrata: ${esito.deposito.statoEtichetta}${esito.deposito.identificativo ? ` · invio ${esito.deposito.identificativo}` : ''}.`)
      form.reset()
      setNomeFile('')
      onRegistrata()
    } catch (e) { setErrore(e instanceof Error ? e.message : 'Ricevuta non registrata.') } finally { setLavoro(false) }
  }
  const definitivo = deposito.definitivo && deposito.esitoId
  if (definitivo) return null
  return (
    <form className="iu-pdp-ricevuta" onSubmit={(e) => void invia(e)}>
      <h5><FileCheck2 size={15}/> {deposito.ricevutaId ? 'Ricevuta di esito' : 'Ricevuta del PDP'}</h5>
      <p className="iu-pdp-nota">Carica il PDF scaricato dal PDP: il deposito vale dalla ricevuta di accettazione ed è tempestivo entro le 24 del giorno di scadenza.</p>
      <div className="iu-pdp-form">
        <label className="iu-pdp-carica"><FileUp size={14}/> {nomeFile || 'Scegli la ricevuta (PDF)'}
          <input type="file" name="ricevuta" accept="application/pdf,.pdf" onChange={(e) => setNomeFile(e.target.files?.[0]?.name || '')}/></label>
        <label>Identificativo invio<input name="identificativo" placeholder="AAAA/NNNNNNN" defaultValue={deposito.identificativo}/></label>
        <label>Data e ora invio<input name="dataInvio" type="datetime-local"/></label>
        <button type="submit" disabled={lavoro}>{lavoro ? 'Lettura…' : 'Registra ricevuta'}</button>
      </div>
      {messaggio ? <p className="iu-pdp-ok" role="status">{messaggio}</p> : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </form>
  )
}
