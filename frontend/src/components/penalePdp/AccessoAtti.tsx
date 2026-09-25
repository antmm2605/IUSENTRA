import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { KeyRound, MailSearch, FileSignature, RefreshCw } from 'lucide-react'
import { Badge } from '../dashboard'
import { penaleApi } from './penaleApi'
import { AccessoAttiAzioni } from './AccessoAttiAzioni'
import { AccessoAttiElenchi } from './AccessoAttiElenchi'
import { dataOra, type AccessoAtti as Dati } from './types'

const STATO_DOWNLOAD: Record<string, { etichetta: string; tono: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }> = {
  missing: { etichetta: 'Link non ancora arrivato', tono: 'neutral' },
  scheduled: { etichetta: 'Download programmato', tono: 'info' },
  open: { etichetta: 'Download aperto', tono: 'success' },
  expired: { etichetta: 'Link scaduto', tono: 'danger' },
}

/**
 * Accesso agli atti (art. 116 c.p.p.): richiesta, link valido 3 giorni e password via PEC ReGIndE.
 * Le azioni usano le stesse funzioni collaudate della procedura esistente.
 */
export function AccessoAtti({ fascicoloId, onDocumenti }: { fascicoloId: string; onDocumenti?: () => void }) {
  const [dati, setDati] = useState<Dati | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [lavoro, setLavoro] = useState('')

  const ricarica = useCallback(async (signal?: AbortSignal) => {
    try { setDati(await penaleApi.accesso(fascicoloId, signal)); setErrore('') } catch (e) {
      if (!signal?.aborted) setErrore(e instanceof Error ? e.message : 'Accesso agli atti non disponibile.')
    }
  }, [fascicoloId])
  useEffect(() => { const a = new AbortController(); void ricarica(a.signal); return () => a.abort() }, [ricarica])

  const esegui = async (azione: string, form?: HTMLFormElement | FormData) => {
    setLavoro(azione); setErrore(''); setMessaggio('')
    try {
      const corpo = form instanceof FormData ? form : form ? new FormData(form) : new FormData()
      const esito = await penaleApi.azioneAccesso(fascicoloId, azione, corpo)
      setMessaggio(esito.messaggi.map((m) => m.testo).join(' ') || 'Operazione registrata.')
      if (form instanceof HTMLFormElement) form.reset()
      await ricarica()
      if (['genera-richiesta', 'importa-scaricato'].includes(azione)) onDocumenti?.()
    } catch (e) { setErrore(e instanceof Error ? e.message : 'Operazione non riuscita.') } finally { setLavoro('') }
  }
  const invia = (azione: string) => (evento: FormEvent<HTMLFormElement>) => { evento.preventDefault(); void esegui(azione, evento.currentTarget) }

  if (!dati) return errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : <p className="iu-pdp-nota" role="status">Caricamento dell'accesso agli atti…</p>
  const download = STATO_DOWNLOAD[dati.download.stato] || STATO_DOWNLOAD.missing
  const fatti = dati.checklist.filter((c) => c.fatto).length
  return (
    <div className="iu-pdp-accesso">
      <div className="iu-pdp-accesso__stato">
        <Badge tone={download.tono}>{download.etichetta}{dati.download.finoAl ? ` · fino al ${dataOra(dati.download.finoAl)}` : ''}</Badge>
        <Badge tone={dati.download.passwordDisponibile ? 'success' : 'neutral'}><KeyRound size={12}/> {dati.download.passwordDisponibile ? 'Password ricevuta' : 'Password non ancora ricevuta'}</Badge>
        <Badge tone="info">Percorso {fatti}/{dati.checklist.length}</Badge>
      </div>
      <p className="iu-pdp-nota">La richiesta si deposita sul PDP (atto «Accesso, copia e visione atti», art. 116 c.p.p.). Se accolta arriva un link valido 3 giorni
        e la password via PEC all'indirizzo ReGIndE: IUSENTRA la cerca nella casella dello studio e importa nel fascicolo il pacchetto scaricato.</p>
      <div className="iu-pdp-azioni">
        <button type="button" className="iu-pdp-primario" disabled={Boolean(lavoro)} onClick={() => void esegui('genera-richiesta')}><FileSignature size={15}/> Genera la richiesta (PDF)</button>
        <button type="button" disabled={Boolean(lavoro)} onClick={() => void esegui('cerca-pec')}><MailSearch size={15}/> Cerca link e password nella PEC</button>
        <button type="button" disabled={Boolean(lavoro)} onClick={() => void ricarica()}><RefreshCw size={14}/> Aggiorna</button>
      </div>
      {lavoro ? <p className="iu-pdp-nota" role="status">Operazione in corso…</p> : null}
      {messaggio ? <p className="iu-pdp-ok" role="status">{messaggio}</p> : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
      <ol className="iu-pdp-percorso">
        {dati.checklist.map((c) => <li key={c.titolo} className={c.fatto ? 'is-fatto' : ''}><strong>{c.titolo}</strong>{c.dettaglio ? <span>{c.dettaglio}</span> : null}</li>)}
      </ol>
      <AccessoAttiAzioni dati={dati} lavoro={Boolean(lavoro)} invia={invia}/>
      <AccessoAttiElenchi dati={dati} lavoro={Boolean(lavoro)} invia={invia} completa={(id) => { const f = new FormData(); f.append('task_id', id); void esegui('completa-attivita', f) }}/>
    </div>
  )
}
