import { useState, type ChangeEvent } from 'react'
import { AlertTriangle, CheckCircle2, FileSignature, Info } from 'lucide-react'
import { csrfHeader } from '../../api/csrf'

type EsitoVoce = { codice: string; livello: 'ok' | 'avviso' | 'errore'; messaggio: string }
type EsitoVerifica = { ok: boolean; errore?: string; modulo?: string; versione?: string; esiti?: EsitoVoce[]; allegati?: Array<{ nome: string; byte: number }> }

const ICONE = { ok: <CheckCircle2 size={14} aria-hidden="true"/>, avviso: <Info size={14} aria-hidden="true"/>, errore: <AlertTriangle size={14} aria-hidden="true"/> }

/**
 * Il modulo si firma in Adobe Reader sul suo campo firma (PAdES-BES), che prima esegue i controlli del modello.
 * Dopo la firma l'avvocato carica qui il file: IUSENTRA controlla versione, firma sull'intero file e allegati.
 */
export function VerificaModuloFirmato() {
  const [canale, setCanale] = useState<'pec' | 'upload'>('pec')
  const [esito, setEsito] = useState<EsitoVerifica | null>(null)
  const [inCorso, setInCorso] = useState(false)

  const verifica = async (evento: ChangeEvent<HTMLInputElement>) => {
    const file = evento.currentTarget.files?.[0]
    evento.currentTarget.value = ''
    if (!file) return
    const dati = new FormData()
    dati.append('file', file)
    dati.append('canale', canale)
    setInCorso(true)
    try {
      const risposta = await fetch('/api/v1/ui/pat/moduli/verifica', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', ...csrfHeader() }, body: dati })
      setEsito(await risposta.json().catch(() => ({ ok: false, errore: 'Risposta non valida.' })) as EsitoVerifica)
    } catch {
      setEsito({ ok: false, errore: 'Connessione interrotta: riprova.' })
    } finally {
      setInCorso(false)
    }
  }

  return (
    <section className="iu-pat-verifica-firmato" aria-label="Verifica del modulo firmato">
      <header>
        <strong><FileSignature size={15} aria-hidden="true"/> Verifica il modulo firmato</strong>
        <span>Dopo aver incorporato gli allegati e firmato in Adobe Reader, carica qui il modulo: controllo versione, firma PAdES sull'intero file, nomi e dimensioni degli allegati.</span>
      </header>
      <div className="iu-pat-verifica-firmato__azioni">
        <label>Invio
          <select value={canale} onChange={(e) => setCanale(e.currentTarget.value === 'upload' ? 'upload' : 'pec')}>
            <option value="pec">Via PEC (10 MB per allegato, 30 MB in tutto)</option>
            <option value="upload">Via upload (30 MB per allegato, 50 MB in tutto)</option>
          </select></label>
        <label className="iu-pat-verifica-firmato__file">{inCorso ? 'Verifica in corso…' : 'Carica il modulo firmato'}
          <input type="file" accept="application/pdf,.pdf" onChange={(e) => void verifica(e)} disabled={inCorso}/></label>
      </div>
      {esito ? (
        <div role="status" className={esito.ok ? 'iu-pat-verifica-firmato__esito is-ok' : 'iu-pat-verifica-firmato__esito is-errore'}>
          <strong>{esito.ok ? 'Modulo pronto per l’invio' : 'Il modulo va corretto prima dell’invio'}</strong>
          {esito.errore ? <span>{esito.errore}</span> : null}
          <ul>
            {(esito.esiti || []).map((voce, indice) => (
              <li key={`${voce.codice}-${indice}`} className={`is-${voce.livello}`}>{ICONE[voce.livello]} {voce.messaggio}</li>
            ))}
          </ul>
          {esito.allegati?.length ? <small>Allegati incorporati: {esito.allegati.map((a) => a.nome).join(', ')}</small> : null}
        </div>
      ) : null}
    </section>
  )
}
