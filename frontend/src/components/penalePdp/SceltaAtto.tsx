import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { penaleApi } from './penaleApi'
import type { AttoCatalogo, Quadro } from './types'

type Props = {
  fascicoloId: string
  quadro: Quadro
  ufficio: string
  soggetti: string[]
  scelto: string
  onScegli: (atto: AttoCatalogo) => void
}

/** Il catalogo del PDP filtrato come fa il portale: ufficio, ruolo dei soggetti, fase, testo. */
export function SceltaAtto({ fascicoloId, quadro, ufficio, soggetti, scelto, onScegli }: Props) {
  const [tipo, setTipo] = useState<'1' | '0'>(quadro.procedimento.autorizzato ? '0' : '1')
  const [fase, setFase] = useState('')
  const [cerca, setCerca] = useState('')
  const [atti, setAtti] = useState<AttoCatalogo[]>([])
  const [errore, setErrore] = useState('')
  const chiaveSoggetti = soggetti.join(',')
  useEffect(() => {
    if (!ufficio) { setAtti([]); return }
    let attivo = true
    const attesa = window.setTimeout(() => {
      penaleApi.atti(fascicoloId, { ufficio, principali: tipo, fase, cerca, soggetti: chiaveSoggetti })
        .then((r) => { if (attivo) { setAtti(r.atti); setErrore('') } })
        .catch((e: unknown) => { if (attivo) setErrore(e instanceof Error ? e.message : 'Catalogo non disponibile.') })
    }, 180)
    return () => { attivo = false; window.clearTimeout(attesa) }
  }, [fascicoloId, ufficio, tipo, fase, cerca, chiaveSoggetti])
  const nomeFase = (codice: string) => quadro.fasi.find((f) => f.codice === codice)?.descrizione || ''
  return (
    <div className="iu-pdp-catalogo">
      <div className="iu-pdp-filtri">
        <div className="iu-pdp-segmenti" role="radiogroup" aria-label="Tipo di atto">
          <button type="button" role="radio" aria-checked={tipo === '1'} className={tipo === '1' ? 'is-attiva' : ''} onClick={() => setTipo('1')}>Menu «Depositi»</button>
          <button type="button" role="radio" aria-checked={tipo === '0'} className={tipo === '0' ? 'is-attiva' : ''} onClick={() => setTipo('0')}>Atti successivi</button>
        </div>
        {tipo === '0' ? (
          <select aria-label="Fase" value={fase} onChange={(e) => setFase(e.target.value)}>
            <option value="">Tutte le fasi</option>
            {quadro.fasi.map((f) => <option key={f.codice} value={f.codice}>{f.descrizione}</option>)}
          </select>
        ) : null}
        <label className="iu-pdp-cerca"><Search size={14}/><input type="search" placeholder="Cerca tipo atto" value={cerca} onChange={(e) => setCerca(e.target.value)}/></label>
      </div>
      {tipo === '0' && !quadro.procedimento.autorizzato ? (
        <p className="iu-pdp-avviso">Procedimento non ancora autorizzato: puoi preparare l’atto, ma il PDP lo accetterà solo dopo l’autorizzazione.</p>
      ) : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
      <ul className="iu-pdp-atti" aria-label="Atti depositabili">
        {atti.map((a) => (
          <li key={a.codice}>
            <button type="button" className={scelto === a.codice ? 'is-scelto' : ''} aria-pressed={scelto === a.codice} onClick={() => onScegli(a)}>
              <strong>{a.nome}</strong>
              <span>{[a.fase && nomeFase(a.fase), a.norma, a.confermaRicezione && 'conferma di ricezione'].filter(Boolean).join(' · ') || 'Atto del PDP'}</span>
            </button>
          </li>
        ))}
        {!atti.length && ufficio ? <li className="iu-pdp-nota">Nessun atto per questi filtri: il PDP non lo consente verso questo ufficio o per questi soggetti.</li> : null}
        {!ufficio ? <li className="iu-pdp-nota">Scegli l’ufficio di destinazione.</li> : null}
      </ul>
    </div>
  )
}
